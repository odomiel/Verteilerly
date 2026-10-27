"""Tests zu den Erweiterungen und zum Blattvorlagen-Editor."""

import dataclasses
import html
import os
import pathlib
import re
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

ANWENDUNG = QApplication.instance() or QApplication([])

from verteilerly import erweiterungen, pfade  # noqa: E402
from verteilerly.blattvorlagen import (  # noqa: E402
    STANDARD,
    Blattvorlagen,
    blattvorlage_aus_yaml,
)
from verteilerly.erweiterungen import Fund  # noqa: E402

from . import BEISPIELVORLAGE, bauteil_zurueckgeben  # noqa: E402

WURZEL = pathlib.Path(__file__).resolve().parent.parent


class Programmattrappe:
    """Die Schnittstelle, wie eine Erweiterung sie sieht - ohne Fenster."""

    def __init__(self, ordner=None, vorlagen=None) -> None:
        self.eintraege: list = []
        self.meldungen: list[str] = []
        self.ordner = ordner
        self._vorlagen = vorlagen or Blattvorlagen([BEISPIELVORLAGE])
        self.fenster = None

    def menueeintrag(self, text, aufruf, hinweis="", kuerzel=""):
        self.eintraege.append((text, aufruf))

    def meldung(self, text, dauer=8000):
        self.meldungen.append(text)

    def projekt(self):
        return None

    def blattvorlagen(self):
        return self._vorlagen

    def blattvorlage(self):
        return STANDARD

    def blattvorlagen_neu_laden(self):
        self._vorlagen = Blattvorlagen.aus_ordnern([self.ordner])
        self._vorlagen.aufnehmen(BEISPIELVORLAGE)

    def blattvorlagenordner(self):
        return self.ordner

    def farben(self):
        from verteilerly.gui.thema import HELL

        return HELL


class TestFinden(unittest.TestCase):
    """Eingebaute sind an, fremde werden erst eingeschaltet ausgefuehrt."""

    def setUp(self):
        self._ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self._ordner.cleanup)
        self.ordner = pathlib.Path(self._ordner.name)

    def _datei(self, name: str, text: str) -> pathlib.Path:
        datei = self.ordner / name
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_text(text, encoding="utf-8")
        return datei

    def _fremd(self, kennung: str) -> Fund:
        return next(f for f in erweiterungen.finden([self.ordner]) if f.kennung == kennung)

    def test_die_eingebauten_sind_dabei_und_an(self):
        funde = {f.kennung: f for f in erweiterungen.finden([])}
        editor = funde["blattvorlageneditor"]
        self.assertTrue(editor.eingebaut)
        self.assertIsNotNone(editor.erweiterung)
        self.assertEqual(editor.fehler, "")
        self.assertTrue(erweiterungen.eingeschaltet(editor, set(), set()))
        self.assertFalse(erweiterungen.eingeschaltet(editor, set(), {"blattvorlageneditor"}))

    def test_eine_eingebaute_traegt_die_fassung_des_programms(self):
        """Sie wird mit dem Programm ausgeliefert - also dessen Schema."""
        from verteilerly.version import VERSION, zerlegen

        for fund in erweiterungen.finden([]):
            with self.subTest(erweiterung=fund.kennung):
                self.assertEqual(fund.version, VERSION)
                # Wirft, wenn es keine Verteilerly-Version ist.
                zerlegen(fund.version)

    def test_eine_fremde_zaehlt_wie_sie_will_und_wird_dabei_nicht_ausgefuehrt(self):
        """Die Fassung wird gelesen wie der Docstring, nicht ausgeführt."""
        marke = self.ordner / "ausgefuehrt"
        self._datei("modul.py", f'"""Modul: zum Testen."""\n'
                                f'version = "7.3-beta"\n'
                                f'open({str(marke)!r}, "w").close()\n')
        self._datei("doppel.py", '"""Doppel."""\n__version__ = "0.1+git"\n')
        self._datei("klasse.py", (
            '"""Klasse."""\n'
            "from verteilerly.erweiterungen import Erweiterung\n"
            "class K(Erweiterung):\n"
            "    kennung = 'klasse'\n    version = 'v2'\n"
            "    def einrichten(self, programm):\n        pass\n"
            "erweiterung = K()\n"
        ))
        self._datei("ohne.py", '"""Ohne Fassung."""\n')
        self.assertEqual(self._fremd("modul").version, "7.3-beta")
        self.assertEqual(self._fremd("doppel").version, "0.1+git")
        self.assertEqual(self._fremd("klasse").version, "v2")
        self.assertEqual(self._fremd("ohne").version, "")
        self.assertFalse(marke.exists())

    def test_beim_laden_gilt_was_die_erweiterung_selbst_sagt(self):
        self._datei("spaet.py", (
            '"""Spät."""\n'
            'version = "aus der Datei"\n'
            "from verteilerly.erweiterungen import Erweiterung\n"
            "class Spaet(Erweiterung):\n"
            "    kennung = 'spaet'\n    name = 'Spät'\n"
            "    version = 'aus dem Objekt'\n"
            "    def einrichten(self, programm):\n        pass\n"
            "erweiterung = Spaet()\n"
        ))
        fund = self._fremd("spaet")
        self.assertEqual(fund.version, "aus der Datei")
        erweiterungen.laden(fund)
        self.assertEqual(fund.fehler, "")
        self.assertEqual(fund.version, "aus dem Objekt")

    def test_eine_fremde_wird_beim_finden_nicht_ausgefuehrt(self):
        """Fremder Code laeuft erst, wenn jemand ihn eingeschaltet hat."""
        marke = self.ordner / "ausgefuehrt"
        self._datei("probe.py", f'"""Probe: nur zum Testen.\n\nMehr Text."""\n'
                                f'open({str(marke)!r}, "w").close()\n')
        fund = self._fremd("probe")
        self.assertFalse(fund.eingebaut)
        self.assertEqual(fund.beschreibung, "Probe: nur zum Testen.")
        self.assertIsNone(fund.erweiterung)
        self.assertFalse(marke.exists())
        self.assertFalse(erweiterungen.eingeschaltet(fund, set(), set()))
        self.assertTrue(erweiterungen.eingeschaltet(fund, {"probe"}, set()))

    def test_laden_fuehrt_aus_und_haengt_die_erweiterung_an(self):
        self._datei("gruss.py", (
            "from verteilerly.erweiterungen import Erweiterung\n"
            "class Gruss(Erweiterung):\n"
            "    kennung = 'gruss'\n    name = 'Gruß'\n    beschreibung = 'Grüßt'\n"
            "    def einrichten(self, programm):\n"
            "        programm.menueeintrag('Grüßen', lambda: None)\n"
            "erweiterung = Gruss()\n"
        ))
        fund = self._fremd("gruss")
        erweiterungen.laden(fund)
        self.assertEqual(fund.fehler, "")
        self.assertEqual((fund.name, fund.beschreibung), ("Gruß", "Grüßt"))
        programm = Programmattrappe()
        fund.erweiterung.einrichten(programm)
        self.assertEqual([t for t, _ in programm.eintraege], ["Grüßen"])

    def test_ein_fehler_beim_laden_wird_festgehalten(self):
        self._datei("kaputt.py", "import gibtesnicht\n")
        fund = self._fremd("kaputt")
        erweiterungen.laden(fund)
        self.assertIsNone(fund.erweiterung)
        self.assertIn("ModuleNotFoundError", fund.fehler)
        self.assertNotIn("verteilerly_erweiterung_kaputt", sys.modules)

    def test_ohne_objekt_erweiterung_gilt_sie_nicht(self):
        self._datei("leer.py", "x = 1\n")
        fund = self._fremd("leer")
        erweiterungen.laden(fund)
        self.assertIsNone(fund.erweiterung)
        self.assertIn("Erweiterung", fund.fehler)

    def test_auch_ein_paket_ist_eine_erweiterung(self):
        self._datei("paket/teil.py", "WORT = 'aus dem Paket'\n")
        self._datei("paket/__init__.py", (
            '"""Paket: mit einem eigenen Modul."""\n'
            "from verteilerly.erweiterungen import Erweiterung\n"
            "from .teil import WORT\n"
            "class Paket(Erweiterung):\n"
            "    kennung = 'paket'\n    name = WORT\n"
            "    def einrichten(self, programm):\n        pass\n"
            "erweiterung = Paket()\n"
        ))
        fund = self._fremd("paket")
        self.assertEqual(fund.beschreibung, "Paket: mit einem eigenen Modul.")
        erweiterungen.laden(fund)
        self.assertEqual(fund.fehler, "")
        self.assertEqual(fund.name, "aus dem Paket")

    def test_eine_eingebaute_kennung_ist_vergeben(self):
        self._datei("blattvorlageneditor.py", "x = 1\n")
        fremde = [f for f in erweiterungen.finden([self.ordner]) if not f.eingebaut]
        self.assertEqual(len(fremde), 1)
        self.assertIn("eingebaute", fremde[0].fehler)

    def test_was_keine_erweiterung_ist_bleibt_liegen(self):
        self._datei("_privat.py", "x = 1\n")
        self._datei("notiz.txt", "nichts\n")
        self._datei("ordner_ohne_init/modul.py", "x = 1\n")
        fremde = [f for f in erweiterungen.finden([self.ordner]) if not f.eingebaut]
        self.assertEqual(fremde, [])

    def test_bei_gleichem_namen_gilt_der_erste_ort(self):
        zweiter = self.ordner / "zweiter"
        self._datei("a.py", '"""Erster."""\n')
        self._datei("zweiter/a.py", '"""Zweiter."""\n')
        fremde = [f for f in erweiterungen.finden([self.ordner, zweiter]) if not f.eingebaut]
        self.assertEqual([(f.kennung, f.beschreibung) for f in fremde], [("a", "Erster.")])

    def test_die_wahl_steht_als_text_mit_kommas(self):
        self.assertEqual(erweiterungen.wahl_lesen(" hallo, gruss,,"), {"hallo", "gruss"})
        self.assertEqual(erweiterungen.wahl_lesen(None), set())
        self.assertEqual(erweiterungen.wahl_schreiben({"b", "a"}), "a,b")

    def test_das_beispiel_der_anleitung_laeuft(self):
        """Was die Hilfe als Beispiel zeigt, ist eine gueltige Erweiterung."""
        for name in ("dokumentation.html", "dokumentation_en.html"):
            with self.subTest(seite=name):
                text = (WURZEL / "daten" / "hilfe" / name).read_text(encoding="utf-8")
                beispiel = next(
                    html.unescape(block) for block in re.findall(r"<pre>(.*?)</pre>", text, re.S)
                    if "import Erweiterung" in block
                )
                ordner = self.ordner / name
                ordner.mkdir()
                (ordner / "hallo.py").write_text(beispiel, encoding="utf-8")
                fund = next(f for f in erweiterungen.finden([ordner]) if f.kennung == "hallo")
                self.assertTrue(fund.beschreibung)
                # Die Fassung steht in der Klasse und wird gelesen, nicht
                # ausgeführt.
                self.assertEqual(fund.version, "1.0")
                erweiterungen.laden(fund)
                self.assertEqual(fund.fehler, "")
                programm = Programmattrappe()
                fund.erweiterung.einrichten(programm)
                self.assertEqual(len(programm.eintraege), 1)
                programm.eintraege[0][1]()
                self.assertEqual(len(programm.meldungen), 1)


class TestImHauptfenster(unittest.TestCase):
    def setUp(self):
        from verteilerly.gui.hauptfenster import Hauptfenster

        self.fenster = Hauptfenster()
        bauteil_zurueckgeben(self, self.fenster)

    def _menue(self):
        return next(
            a.menu() for a in self.fenster.menuBar().actions()
            if a.text().replace("&", "") == "Erweiterungen"
        )

    def test_das_menue_steht_zwischen_tools_und_hilfe(self):
        leiste = [a.text().replace("&", "") for a in self.fenster.menuBar().actions()]
        self.assertEqual(leiste[leiste.index("Tools") + 1], "Erweiterungen")
        self.assertEqual(leiste[leiste.index("Erweiterungen") + 1], "Hilfe")

    def test_der_editor_steht_ueber_dem_verwalten(self):
        eintraege = [a for a in self._menue().actions()]
        texte = [a.text().replace("&", "") for a in eintraege if not a.isSeparator()]
        self.assertEqual(
            texte,
            ["Blattvorlagen-Editor…", "Protokoll…", "Rechtschreibung…",
             "Erweiterungen verwalten…"],
        )
        editor = next(a for a in eintraege if "Blattvorlagen" in a.text())
        self.assertEqual(editor.property("erweiterung"), "blattvorlageneditor")
        self.assertFalse(editor.property("fremd"))

    def test_das_protokoll_hoert_die_statuszeile_mit(self):
        """Was das Programm meldet, steht danach in der Datei."""
        fund = next(
            x for x in self.fenster.erweiterungen if x.kennung == "protokoll"
        )
        protokoll = fund.erweiterung
        self.assertIsNotNone(protokoll)
        # Sie liegt im Arbeitsordner der Testreihe, nicht im echten.
        self.assertTrue(
            str(protokoll.datei()).startswith(str(pfade.eigener_datenordner()))
        )
        self.fenster.statusBar().showMessage("Probe für das Protokoll")
        self.assertIn("Probe für das Protokoll", protokoll.schreiber.lesen())

    def test_ein_fehler_im_aufruf_haelt_das_programm_nicht_an(self):
        from verteilerly.gui import erweiterungen as oberflaeche
        from verteilerly.gui.erweiterungen import Schnittstelle

        fund = Fund("probe", "Probe", eingebaut=False)
        schnittstelle = Schnittstelle(
            self.fenster, self._menue(), self.fenster._erweiterungstrenner, fund
        )
        handlung = schnittstelle.menueeintrag("Kaputt", lambda: 1 / 0)
        self.assertTrue(handlung.property("fremd"))
        with mock.patch.object(oberflaeche.QMessageBox, "critical") as gezeigt:
            handlung.trigger()
        self.assertTrue(gezeigt.called)
        self.assertIn("ZeroDivisionError", gezeigt.call_args[0][2])

    def test_verwalten_merkt_die_wahl_fuer_den_naechsten_start(self):
        from PySide6.QtCore import Qt
        from verteilerly.gui.erweiterungen import ErweiterungenDialog

        from . import einstellung_bewahren

        f = self.fenster
        einstellung_bewahren(self, f.einstellungen, "erweiterungen_an")
        einstellung_bewahren(self, f.einstellungen, "erweiterungen_aus")

        def ausschalten(dialog):
            dialog.eintraege["blattvorlageneditor"].setCheckState(0, Qt.CheckState.Unchecked)
            return ErweiterungenDialog.DialogCode.Accepted

        with mock.patch.object(ErweiterungenDialog, "exec", ausschalten):
            f.erweiterungen_verwalten()
        self.assertEqual(f.einstellungen.value("erweiterungen_aus"), "blattvorlageneditor")
        # Der Editor bleibt bis zum naechsten Start im Menue.
        self.assertTrue(any("Blattvorlagen" in a.text() for a in self._menue().actions()))

    def test_nur_eingebaute_laedt_keine_eigene(self):
        """Der Haken haelt auch eine eingeschaltete eigene Erweiterung aus."""
        from verteilerly import pfade

        from . import einstellung_bewahren

        f = self.fenster
        einstellung_bewahren(self, f.einstellungen, "erweiterungen_an")
        einstellung_bewahren(self, f.einstellungen, "erweiterungen_nur_eingebaute")
        f.einstellungen.setValue("erweiterungen_an", "hallo")

        with tempfile.TemporaryDirectory() as ordner:
            (pathlib.Path(ordner) / "hallo.py").write_text(
                "from verteilerly.erweiterungen import Erweiterung\n"
                "class Hallo(Erweiterung):\n"
                "    kennung = 'hallo'\n"
                "    def einrichten(self, programm):\n"
                "        programm.menueeintrag('Hallo sagen', lambda: None)\n"
                "erweiterung = Hallo()\n",
                encoding="utf-8",
            )
            ohne_schalter = {
                k: v for k, v in os.environ.items() if k != erweiterungen.OHNE_FREMDE
            }
            for nur_eingebaute, geladen in ((True, False), (False, True)):
                with self.subTest(nur_eingebaute=nur_eingebaute):
                    sys.modules.pop("verteilerly_erweiterung_hallo", None)
                    f.einstellungen.setValue("erweiterungen_nur_eingebaute", nur_eingebaute)
                    with mock.patch.dict(os.environ, ohne_schalter, clear=True), \
                         mock.patch.object(
                             pfade, "erweiterungsordner_alle",
                             return_value=[pathlib.Path(ordner)],
                         ):
                        f._erweiterungen_einrichten()
                    hallo = next(fund for fund in f.erweiterungen if fund.kennung == "hallo")
                    self.assertEqual(hallo.erweiterung is not None, geladen)
                    self.assertEqual(
                        any(a.text() == "Hallo sagen" for a in self._menue().actions()),
                        geladen,
                    )
        sys.modules.pop("verteilerly_erweiterung_hallo", None)

    def test_nur_eingebaute_ist_die_vorgabe(self):
        from . import einstellung_bewahren

        f = self.fenster
        einstellung_bewahren(self, f.einstellungen, "erweiterungen_nur_eingebaute")
        f.einstellungen.remove("erweiterungen_nur_eingebaute")
        self.assertTrue(f._nur_eingebaute())

    def test_verwalten_merkt_nur_eingebaute(self):
        from verteilerly.gui.erweiterungen import ErweiterungenDialog

        from . import einstellung_bewahren

        f = self.fenster
        einstellung_bewahren(self, f.einstellungen, "erweiterungen_nur_eingebaute")
        f.einstellungen.setValue("erweiterungen_nur_eingebaute", False)

        def abschalten(dialog):
            dialog.nur_eingebaute_haken.setChecked(True)
            return ErweiterungenDialog.DialogCode.Accepted

        with mock.patch.object(ErweiterungenDialog, "exec", abschalten):
            f.erweiterungen_verwalten()
        self.assertTrue(f._nur_eingebaute())


class TestVerwaltenDialog(unittest.TestCase):
    def test_zeigt_herkunft_fehler_und_wahl(self):
        from PySide6.QtCore import Qt
        from verteilerly.gui.erweiterungen import ErweiterungenDialog

        funde = erweiterungen.finden([]) + [
            Fund("hallo", "hallo", "Sagt Hallo", "7.3-beta", eingebaut=False,
                 ort=pathlib.Path("/x/hallo.py")),
            Fund("kaputt", "kaputt", eingebaut=False, ort=pathlib.Path("/x/kaputt.py"),
                 fehler="ModuleNotFoundError: gibtesnicht"),
        ]
        dialog = ErweiterungenDialog(funde, {"kaputt"}, set(), None)
        self.addCleanup(dialog.close)
        hallo, kaputt = dialog.eintraege["hallo"], dialog.eintraege["kaputt"]
        self.assertEqual(hallo.text(2), "hallo.py")
        self.assertEqual(hallo.checkState(0), Qt.CheckState.Unchecked)
        self.assertIn("gibtesnicht", kaputt.text(3))
        self.assertEqual(kaputt.checkState(0), Qt.CheckState.Checked)
        self.assertFalse(dialog.ordnerknopf.isEnabled())

        # Die Spalte Version: eigene Zählweise, eingebaut die des Programms,
        # ohne Angabe ein Strich.
        from verteilerly.gui.erweiterungen import OHNE_FASSUNG
        from verteilerly.version import VERSION

        self.assertEqual(hallo.text(1), "7.3-beta")
        self.assertEqual(kaputt.text(1), OHNE_FASSUNG)
        self.assertEqual(dialog.eintraege["blattvorlageneditor"].text(1), VERSION)
        self.assertEqual(
            [dialog.liste.headerItem().text(s) for s in range(4)],
            ["Erweiterung", "Version", "Herkunft", "Beschreibung"],
        )

        hallo.setCheckState(0, Qt.CheckState.Checked)
        dialog.eintraege["blattvorlageneditor"].setCheckState(0, Qt.CheckState.Unchecked)
        self.assertEqual(dialog.wahl(), ({"hallo", "kaputt"}, {"blattvorlageneditor"}))

    def test_nur_eingebaute_graut_die_eigenen_aus(self):
        from PySide6.QtCore import Qt
        from verteilerly.gui.erweiterungen import ErweiterungenDialog

        funde = erweiterungen.finden([]) + [
            Fund("hallo", "hallo", eingebaut=False, ort=pathlib.Path("/x/hallo.py")),
        ]
        dialog = ErweiterungenDialog(funde, {"hallo"}, set(), None, nur_eingebaute=True)
        self.addCleanup(dialog.close)
        hallo = dialog.eintraege["hallo"]
        eingebaut = dialog.eintraege["blattvorlageneditor"]
        self.assertTrue(dialog.nur_eingebaute())
        self.assertTrue(hallo.isDisabled())
        self.assertFalse(eingebaut.isDisabled())
        # Der Haken der eigenen bleibt stehen - fuer den Tag, an dem der
        # Schalter wieder fort ist.
        self.assertEqual(hallo.checkState(0), Qt.CheckState.Checked)
        self.assertEqual(dialog.wahl(), ({"hallo"}, set()))

        dialog.nur_eingebaute_haken.setChecked(False)
        self.assertFalse(dialog.nur_eingebaute())
        self.assertFalse(hallo.isDisabled())


class TestBlattvorlagenEditor(unittest.TestCase):
    def setUp(self):
        from verteilerly.erweiterungen.blattvorlageneditor.dialog import EditorDialog

        self._ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self._ordner.cleanup)
        self.ordner = pathlib.Path(self._ordner.name)
        self.programm = Programmattrappe(self.ordner)
        self.dialog = EditorDialog(self.programm)
        bauteil_zurueckgeben(self, self.dialog)
        self.addCleanup(self.dialog.done, 0)

    def test_der_editor_ist_ein_fenster_und_laesst_sich_maximieren(self):
        """Als Dialog oder Werkzeugfenster gäbe es keinen Maximieren-Knopf."""
        from PySide6.QtCore import Qt

        from verteilerly.gui.passform import freie_fensterart

        art = self.dialog.windowFlags()
        self.assertEqual(art & Qt.WindowType.WindowType_Mask, Qt.WindowType.Window)
        self.assertTrue(art & Qt.WindowType.WindowMaximizeButtonHint)
        self.assertTrue(art & Qt.WindowType.WindowMinimizeButtonHint)
        # dialoge_freistellen() stellt nur echte Dialoge um - dieses Fenster
        # bliebe also, wie es ist.
        self.assertNotEqual(
            art & Qt.WindowType.WindowType_Mask, Qt.WindowType.Dialog
        )
        self.assertEqual(
            freie_fensterart(art) & Qt.WindowType.WindowType_Mask,
            Qt.WindowType.Tool,
            "freie_fensterart macht aus allem ein Werkzeugfenster - "
            "der Filter darf dieses Fenster gar nicht erst anfassen",
        )

    def test_ohne_offenen_verteiler_zeigt_er_ein_beispiel(self):
        d = self.dialog
        self.assertEqual(d.basis.id, STANDARD.id)
        self.assertGreaterEqual(len(d.blaetter), 3)
        self.assertEqual(d.blattwahl.count(), len(d.blaetter))
        self.assertIsNotNone(d.flaeche.blatt)
        self.assertFalse(d.geaendert)
        self.assertTrue(d.speichern_knopf.isEnabled())

    def test_eine_aenderung_zeichnet_das_blatt_neu(self):
        d = self.dialog
        vorher = d.flaeche.blatt
        d.zahlen["rand"].setValue(20.0)
        self.assertTrue(d.geaendert)
        d._neu_zeichnen()
        self.assertEqual(d.vorlage().rand, 20.0)
        self.assertIsNot(d.flaeche.blatt, vorher)

    def test_die_spalten_lassen_sich_umstellen(self):
        d = self.dialog
        felder = [s.feld for s in d.spaltenliste()]
        d.spalten.setCurrentCell(0, 0)
        d._spalte_schieben(1)
        self.assertEqual([s.feld for s in d.spaltenliste()][:2], [felder[1], felder[0]])
        d._spalte_hinzu()
        self.assertEqual(len(d.spaltenliste()), len(felder) + 1)
        d.spalten.setCurrentCell(0, 0)
        d._spalte_weg()
        self.assertEqual(len(d.spaltenliste()), len(felder))
        self.assertEqual(d.vorlage().spalten, tuple(d.spaltenliste()))

    def test_die_letzte_spalte_bleibt(self):
        d = self.dialog
        d._spalten_setzen(STANDARD.spalten[:1])
        d.spalten.setCurrentCell(0, 0)
        d._spalte_weg()
        self.assertEqual(len(d.spaltenliste()), 1)

    def test_eine_andere_ausgangsvorlage_stellt_alle_felder_um(self):
        d = self.dialog
        d.basiswahl.setCurrentIndex(d.basiswahl.findData(BEISPIELVORLAGE.id))
        self.assertEqual(d.basis.id, BEISPIELVORLAGE.id)
        self.assertEqual(d.zahlen["schriftfeld_hoehe"].value(), 38.0)
        self.assertFalse(d.geaendert)

    def test_gespeichert_wird_immer_eine_neue_datei(self):
        d = self.dialog
        d.zahlen["rand"].setValue(18.0)
        d.zahlen["schrift_klein"].setValue(6.5)
        kennung = d.speichern("Breiter Rand")
        datei = self.ordner / f"{kennung}.yaml"
        self.assertEqual(kennung, "breiter-rand")
        import yaml

        inhalt = yaml.safe_load(datei.read_text(encoding="utf-8"))
        self.assertEqual(inhalt["rand"], 18)
        self.assertEqual(inhalt["schrift"], {"klein": 6.5})
        self.assertNotIn("zelle_breite", inhalt.get("belegung", {}))
        self.assertEqual(blattvorlage_aus_yaml(inhalt).rand, 18.0)
        self.assertFalse(d.geaendert)
        self.assertEqual(d.basis.id, kennung)

        vorher = datei.read_text(encoding="utf-8")
        d.zahlen["rand"].setValue(25.0)
        zweite = d.speichern("Breiter Rand")
        self.assertEqual(zweite, "breiter-rand-2")
        self.assertEqual(datei.read_text(encoding="utf-8"), vorher)

    def test_eine_vorhandene_vorlage_wird_geladen_und_zurueckgeschrieben(self):
        """Bearbeiten heißt: in dieselbe Datei zurück, nicht in eine neue."""
        import yaml

        d = self.dialog
        kennung = d.speichern("Erste Fassung")
        datei = self.ordner / f"{kennung}.yaml"
        # Neu laden, so wie sie jetzt auf der Platte liegt.
        d.basiswahl.setCurrentIndex(d.basiswahl.findData(kennung))
        self.assertEqual(d.basis.id, kennung)
        self.assertEqual(d.name.text(), "Erste Fassung")
        self.assertEqual(d.vorlagendatei(), datei)
        self.assertTrue(d.ueberschreiben_knopf.isEnabled())

        d.zahlen["rand"].setValue(21.0)
        d.name.setText("Zweite Fassung")
        d._neu_zeichnen()
        self.assertEqual(d.ueberschreiben(), kennung)
        self.assertEqual(sorted(p.name for p in self.ordner.glob("*.yaml")),
                         [datei.name])
        inhalt = yaml.safe_load(datei.read_text(encoding="utf-8"))
        self.assertEqual((inhalt["id"], inhalt["name"], inhalt["rand"]),
                         (kennung, "Zweite Fassung", 21))
        self.assertFalse(d.geaendert)
        self.assertEqual(d.basis.name, "Zweite Fassung")

    def test_ohne_eigene_datei_wird_nichts_ueberschrieben(self):
        """Die eingebaute Vorgabe steht im Programm, nicht im Arbeitsordner."""
        d = self.dialog
        self.assertEqual(d.basis.id, "standard")
        self.assertIsNone(d.vorlagendatei())
        self.assertFalse(d.ueberschreiben_knopf.isEnabled())
        self.assertTrue(d.speichern_knopf.isEnabled())
        self.assertIsNone(d.ueberschreiben())
        self.assertEqual(list(self.ordner.glob("*.yaml")), [])

    def test_ohne_namen_laesst_sich_nichts_speichern(self):
        d = self.dialog
        d.name.setText("   ")
        d._neu_zeichnen()
        self.assertIn("name", d.meldung.text())
        self.assertFalse(d.speichern_knopf.isEnabled())
        self.assertFalse(d.ueberschreiben_knopf.isEnabled())

    def test_was_eine_datei_abwiese_laesst_sich_nicht_speichern(self):
        from verteilerly.blattvorlagen import BlattvorlagenFehler
        from verteilerly.erweiterungen.blattvorlageneditor import dialog as modul

        d = self.dialog
        with mock.patch.object(modul, "blattvorlage_aus_yaml",
                               side_effect=BlattvorlagenFehler("Rand passt nicht")):
            d._neu_zeichnen()
        self.assertIn("Rand passt nicht", d.meldung.text())
        self.assertFalse(d.speichern_knopf.isEnabled())
        d._neu_zeichnen()
        self.assertEqual(d.meldung.text(), "")
        self.assertTrue(d.speichern_knopf.isEnabled())

    def test_ungespeichertes_wird_nicht_stillschweigend_verworfen(self):
        from verteilerly.erweiterungen.blattvorlageneditor import dialog as modul
        from verteilerly.gui.sprache import Knopf

        d = self.dialog
        d.show()
        d.zahlen["rand"].setValue(21.0)
        with mock.patch.object(modul, "frage", return_value=Knopf.Cancel) as gefragt:
            d.reject()
        self.assertTrue(gefragt.called)
        self.assertTrue(d.isVisible())
        with mock.patch.object(modul, "frage", return_value=Knopf.Discard):
            d.reject()
        self.assertFalse(d.isVisible())


class TestProtokollschreiber(unittest.TestCase):
    """Die Datei im Arbeitsordner - eine Zeile je Ereignis."""

    def setUp(self):
        from verteilerly.erweiterungen.protokoll.schreiber import Schreiber

        self._ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self._ordner.cleanup)
        self.datei = pathlib.Path(self._ordner.name) / "Verteilerly.log"
        self.schreiber = Schreiber(self.datei)

    def test_jede_zeile_traegt_zeitpunkt_und_art(self):
        self.assertTrue(self.schreiber.schreiben("EREIGNIS", "Neuer Verteiler"))
        zeile = self.schreiber.lesen().splitlines()[0]
        self.assertRegex(zeile, r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d  EREIGNIS\s+Neuer Verteiler$")

    def test_ein_bericht_steht_eingerueckt_darunter(self):
        self.schreiber.schreiben("FEHLER", "RuntimeError: kaputt", "Zeile 1\nZeile 2")
        zeilen = self.schreiber.lesen().splitlines()
        self.assertIn("RuntimeError: kaputt", zeilen[0])
        self.assertEqual(zeilen[1:], ["    Zeile 1", "    Zeile 2"])

    def test_ein_ereignis_bleibt_eine_zeile(self):
        """Ein Umbruch im Text würde die Spalten sprengen."""
        self.schreiber.schreiben("EREIGNIS", "zwei\nZeilen   mit  Luft")
        self.assertEqual(len(self.schreiber.lesen().splitlines()), 1)
        self.assertIn("zwei Zeilen mit Luft", self.schreiber.lesen())

    def test_die_datei_waechst_nicht_ueber_die_grenze(self):
        from verteilerly.erweiterungen.protokoll.schreiber import Schreiber

        schreiber = Schreiber(self.datei, hoechstens=2000)
        for nummer in range(200):
            schreiber.schreiben("EREIGNIS", f"Ereignis {nummer}")
        inhalt = schreiber.lesen()
        self.assertLessEqual(len(inhalt.encode("utf-8")), 2000)
        # Das Neueste bleibt, das Älteste geht, und es steht dabei.
        self.assertIn("Ereignis 199", inhalt)
        self.assertNotIn("Ereignis 0 ", inhalt)
        self.assertIn("gekürzt", inhalt.splitlines()[0])

    def test_was_sich_nicht_schreiben_laesst_haelt_nichts_auf(self):
        from verteilerly.erweiterungen.protokoll.schreiber import Schreiber

        # Eine Datei als Ordner: das Anlegen muss scheitern.
        sperre = pathlib.Path(self._ordner.name) / "sperre"
        sperre.write_text("keine Ordner", encoding="utf-8")
        schreiber = Schreiber(sperre / "tief" / "Verteilerly.log")
        self.assertFalse(schreiber.schreiben("EREIGNIS", "geht nicht"))
        self.assertTrue(schreiber.letzter_fehler)
        self.assertEqual(schreiber.lesen(), "")

    def test_leeren_faengt_von_vorn_an(self):
        self.schreiber.schreiben("EREIGNIS", "alt")
        self.assertTrue(self.schreiber.leeren())
        self.assertEqual(self.schreiber.lesen(), "")


class TestProtokollerweiterung(unittest.TestCase):
    """Sie hängt sich an die Statuszeile und an sys.excepthook."""

    def setUp(self):
        from verteilerly.erweiterungen.protokoll import Protokoll
        from verteilerly.erweiterungen.protokoll.schreiber import Schreiber

        self._ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self._ordner.cleanup)
        self.protokoll = Protokoll()
        self.protokoll.schreiber = Schreiber(
            pathlib.Path(self._ordner.name) / "Verteilerly.log"
        )

    def test_die_startzeilen_nennen_fassung_python_und_qt(self):
        from verteilerly.version import VERSION

        zeile = self.protokoll._startzeilen()[0]
        self.assertIn(VERSION, zeile)
        self.assertIn("Python", zeile)
        self.assertIn("Qt", zeile)

    def test_die_startzeilen_sagen_woher_die_einstellungen_kamen(self):
        """Damit sich zwei Startwege am Protokoll vergleichen lassen."""
        beisammen = "\n".join(self.protokoll._startzeilen())
        for stueck in ("Programm:", "Einstellungen:", "Aufruf:", "Arbeitsverzeichnis"):
            self.assertIn(stueck, beisammen)

    def test_ein_ereignis_landet_in_der_datei(self):
        self.protokoll.ereignis("Neuer Verteiler: 40 DA")
        self.protokoll.ereignis("   ")          # das Löschen der Statuszeile
        zeilen = self.protokoll.schreiber.lesen().splitlines()
        self.assertEqual(len(zeilen), 1)
        self.assertIn("Neuer Verteiler: 40 DA", zeilen[0])

    def test_ein_unerwarteter_fehler_kommt_ins_protokoll(self):
        from PySide6.QtWidgets import QMessageBox

        gerufen = []
        self.protokoll._voriger_haken = lambda *args: gerufen.append(args[0])
        try:
            raise RuntimeError("etwas ging schief")
        except RuntimeError:
            with mock.patch.object(QMessageBox, "critical") as gezeigt:
                self.protokoll.unerwartet(*sys.exc_info())
        inhalt = self.protokoll.schreiber.lesen()
        self.assertIn("FEHLER", inhalt)
        self.assertIn("RuntimeError: etwas ging schief", inhalt)
        self.assertIn("Traceback", inhalt)
        # Gemeldet wird es auch, und der bisherige Haken läuft weiter:
        # wer aus einem Terminal startet, sieht seinen Bericht wie immer.
        self.assertTrue(gezeigt.called)
        self.assertEqual(gerufen, [RuntimeError])

    def test_strg_c_geht_unberuehrt_durch(self):
        gerufen = []
        self.protokoll._voriger_haken = lambda *args: gerufen.append(args[0])
        try:
            raise KeyboardInterrupt
        except KeyboardInterrupt:
            self.protokoll.unerwartet(*sys.exc_info())
        self.assertEqual(self.protokoll.schreiber.lesen(), "")
        self.assertEqual(gerufen, [KeyboardInterrupt])

    def test_ohne_fenster_wird_nur_gemeldet_was_faellt(self):
        """In der Testreihe und im Selbstbericht gibt es keine Statuszeile."""
        self.protokoll._an_die_statuszeile(Programmattrappe())
        self.assertEqual(self.protokoll.schreiber.lesen(), "")


class TestSchriftfeldEditor(unittest.TestCase):
    """Die Bloecke des Schriftfeldes - der Briefkopf am Blattfuss."""

    def setUp(self):
        from verteilerly.blattvorlagen import STANDARDSCHRIFTFELD
        from verteilerly.erweiterungen.blattvorlageneditor.schriftfeld import SchriftfeldEditor

        self.editor = SchriftfeldEditor()
        bauteil_zurueckgeben(self, self.editor)
        self.editor.setzen(STANDARDSCHRIFTFELD, ())
        self.gemeldet = []
        self.editor.geaendert.connect(lambda: self.gemeldet.append(True))

    def test_die_bloecke_der_vorlage_stehen_da(self):
        from verteilerly.blattvorlagen import STANDARDSCHRIFTFELD

        bloecke, anteile = self.editor.werte()
        self.assertEqual(bloecke, STANDARDSCHRIFTFELD)
        self.assertEqual(anteile, ())
        self.assertEqual(len(self.editor.listen), len(STANDARDSCHRIFTFELD))
        self.assertEqual(self.editor.listen[0].item(0).text(), "Firma")
        self.assertFalse(self.gemeldet)

    def test_angaben_und_bloecke_lassen_sich_aendern(self):
        e = self.editor
        e.marke_hinzufuegen(0, "dokumenttitel")
        self.assertEqual(e.werte()[0][0][-1].marke, "dokumenttitel")
        e.marke_entfernen(0, 0)
        self.assertNotIn("firma", [x.marke for x in e.werte()[0][0]])
        e.block_hinzufuegen()
        self.assertEqual(len(e.werte()[0]), 4)
        self.assertEqual(e.werte()[0][3], ())
        e.block_entfernen()
        e.block_entfernen()
        e.block_entfernen()
        # Einer bleibt.
        e.block_entfernen()
        self.assertEqual(len(e.werte()[0]), 1)
        self.assertFalse(e.block_weg.isEnabled())
        self.assertTrue(self.gemeldet)

    def test_eigene_breiten_gibt_es_nur_mit_haken(self):
        e = self.editor
        self.assertFalse(e.breiten[0].isEnabled())
        e.eigene_breiten.setChecked(True)
        self.assertTrue(all(feld.isEnabled() for feld in e.breiten))
        e.breiten[0].setValue(2.0)
        anteile = e.werte()[1]
        self.assertEqual(len(anteile), 3)
        self.assertEqual(anteile[0], 2.0)
        e.eigene_breiten.setChecked(False)
        self.assertEqual(e.werte()[1], ())

    def test_ein_querstrich_ist_eine_angabe_wie_andere(self):
        """Keine Angabe, sondern ein Strich quer durch den Block."""
        from verteilerly.blattvorlagen import SCHRIFTFELDMARKEN
        from verteilerly.erweiterungen.blattvorlageneditor.schriftfeld import MARKENNAMEN

        self.assertIn("strich", SCHRIFTFELDMARKEN)
        self.assertEqual(MARKENNAMEN["strich"], "Querstrich")
        e = self.editor
        e.marke_hinzufuegen(1, "strich")
        self.assertEqual(e.werte()[0][1][-1].marke, "strich")
        self.assertEqual(e.listen[1].item(e.listen[1].count() - 1).text(), "Querstrich")

    def test_hinter_jeder_angabe_steht_ein_ausrichtungsknopf(self):
        """Nur der Querstrich braucht keinen - er hat nichts auszurichten."""
        e = self.editor
        liste = e.listen[0]
        for stelle in range(liste.count()):
            with self.subTest(zeile=stelle):
                self.assertIsNotNone(liste.itemWidget(liste.item(stelle)))
        e.marke_hinzufuegen(0, "strich")
        liste = e.listen[0]
        letzte = liste.item(liste.count() - 1)
        self.assertIsNone(liste.itemWidget(letzte))

    def test_die_ausrichtung_gehoert_der_angabe(self):
        e = self.editor
        e.ausrichten(0, 1, "rechts")
        block = e.werte()[0][0]
        self.assertEqual(block[1].ausrichtung, "rechts")
        self.assertEqual(block[0].ausrichtung, "links")
        self.assertTrue(self.gemeldet)

    def test_die_ausrichtung_zieht_mit_in_den_anderen_block(self):
        """Gezogen wird der Eintrag, nicht nur sein Name."""
        from PySide6.QtCore import QModelIndex, Qt
        from PySide6.QtWidgets import QApplication
        from verteilerly.erweiterungen.blattvorlageneditor.schriftfeld import (
            AUSRICHTUNG,
        )

        e = self.editor
        e.ausrichten(0, 0, "mitte")
        von, nach = e.listen[0], e.listen[1]
        paket = von.model().mimeData([von.model().index(0, 0)])
        nach.model().dropMimeData(paket, Qt.DropAction.MoveAction, 0, 0, QModelIndex())
        angekommen = nach.item(0)
        self.assertEqual(angekommen.data(AUSRICHTUNG), "mitte")
        # Der Knopf kommt gleich nach dem Fallenlassen dazu.
        QApplication.processEvents()
        self.assertIsNotNone(nach.itemWidget(angekommen))

    def test_jeder_block_laesst_sich_einzeln_loeschen(self):
        e = self.editor
        erster, dritter = e.werte()[0][0], e.werte()[0][2]
        e.block_loeschen(1)
        self.assertEqual(e.werte()[0], (erster, dritter))
        # Der letzte Block bleibt, auch wenn man es versucht.
        e.block_loeschen(0)
        e.block_loeschen(0)
        self.assertEqual(len(e.werte()[0]), 1)

    def test_eigene_breiten_gehen_mit_dem_geloeschten_block(self):
        e = self.editor
        e.eigene_breiten.setChecked(True)
        e.breiten[0].setValue(1.0)
        e.breiten[1].setValue(2.0)
        e.breiten[2].setValue(3.0)
        e.block_loeschen(1)
        self.assertEqual(e.werte()[1], (1.0, 3.0))


class TestEigeneBauartImEditor(unittest.TestCase):
    """Ein Schriftfeld, das im Programm steht, baut der Editor nicht um."""

    def setUp(self):
        from verteilerly.erweiterungen.blattvorlageneditor.dialog import EditorDialog

        self._ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self._ordner.cleanup)
        self.ordner = pathlib.Path(self._ordner.name)
        self.dialog = EditorDialog(Programmattrappe(self.ordner))
        bauteil_zurueckgeben(self, self.dialog)
        self.addCleanup(self.dialog.done, 0)

    def test_die_vorlage_bleibt_wie_sie_ist(self):
        """Sonst zeigte die Vorschau ein anderes Blatt als das Programm."""
        self.dialog.basis_uebernehmen(BEISPIELVORLAGE)
        vorlage = self.dialog.vorlage()
        self.assertEqual(vorlage.schriftfeld_art, "beispiel")
        self.assertEqual(vorlage.schriftfeld, BEISPIELVORLAGE.schriftfeld)
        self.assertEqual(
            vorlage.schriftfeld_anteile, BEISPIELVORLAGE.schriftfeld_anteile
        )

    def test_die_bloecke_sind_gesperrt_und_begruendet(self):
        self.dialog.basis_uebernehmen(BEISPIELVORLAGE)
        self.assertFalse(self.dialog.schriftfeld.isEnabled())
        self.assertFalse(self.dialog.schriftfeldhinweis.isHidden())
        self.assertIn("beispiel", self.dialog.schriftfeldhinweis.text())

    def test_die_hoehe_bleibt_einstellbar(self):
        """Sie wirkt auch auf diese Bauart."""
        self.dialog.basis_uebernehmen(BEISPIELVORLAGE)
        hoehe = self.dialog.zahlen["schriftfeld_hoehe"]
        self.assertTrue(hoehe.isEnabled())
        hoehe.setValue(44.0)
        self.assertEqual(self.dialog.vorlage().schriftfeld_hoehe, 44.0)

    def test_eine_blockvorlage_bleibt_einstellbar(self):
        from verteilerly.blattvorlagen import STANDARD

        self.dialog.basis_uebernehmen(STANDARD)
        self.assertTrue(self.dialog.schriftfeld.isEnabled())
        self.assertTrue(self.dialog.schriftfeldhinweis.isHidden())
        self.assertTrue(self.dialog.teilungszeile.isHidden())
        self.assertEqual(self.dialog.vorlage().schriftfeld_art, "standard")

    def test_die_bauart_steht_auf_der_geladenen_vorlage(self):
        self.dialog.basis_uebernehmen(BEISPIELVORLAGE)
        self.assertEqual(self.dialog.bauart.currentData(), "beispiel")
        # 0.42 zu 0.58 - die linke Haelfte steht im Feld.
        self.assertAlmostEqual(self.dialog.linke_haelfte.value(), 0.42)
        self.assertFalse(self.dialog.teilungszeile.isHidden())

    def test_die_bauart_laesst_sich_umschalten(self):
        """Hin zu den Mustertabellen und wieder zurueck zu Bloecken."""
        from verteilerly.blattvorlagen import STANDARD

        d = self.dialog
        d.basis_uebernehmen(STANDARD)
        d.bauart.setCurrentIndex(d.bauart.findData("beispiel"))
        d.linke_haelfte.setValue(0.40)
        vorlage = d.vorlage()
        self.assertEqual(vorlage.schriftfeld_art, "beispiel")
        self.assertEqual(vorlage.schriftfeld_anteile, (0.4, 0.6))
        self.assertFalse(d.schriftfeld.isEnabled())

        d.bauart.setCurrentIndex(d.bauart.findData("standard"))
        self.assertEqual(d.vorlage().schriftfeld_art, "standard")
        self.assertTrue(d.schriftfeld.isEnabled())
        self.assertTrue(d.schriftfeldhinweis.isHidden())

    def test_die_umgeschaltete_bauart_uebersteht_die_datei(self):
        from verteilerly.blattvorlagen import (
            STANDARD,
            blattvorlage_als_yaml,
            blattvorlage_aus_yaml,
        )

        d = self.dialog
        d.basis_uebernehmen(STANDARD)
        d.bauart.setCurrentIndex(d.bauart.findData("beispiel"))
        d.linke_haelfte.setValue(0.42)
        gelesen = blattvorlage_aus_yaml(
            blattvorlage_als_yaml(d.vorlage()), "Probe"
        )
        self.assertEqual(gelesen.schriftfeld_art, "beispiel")
        self.assertEqual(gelesen.schriftfeld_anteile, (0.42, 0.58))

    def test_das_blatt_ist_dasselbe_wie_aus_der_datei(self):
        """Der Pruefstein: beide Wege zeichnen dieselben Texte."""
        from verteilerly.layout import blaetter

        self.dialog.basis_uebernehmen(BEISPIELVORLAGE)
        texte = lambda vorlage: [
            element.text
            for blatt in blaetter(self.dialog.projekt, vorlage)
            for element in blatt.elemente
            if hasattr(element, "text")
        ]
        self.assertEqual(texte(self.dialog.vorlage()), texte(BEISPIELVORLAGE))


class TestZuruecksetzenImEditor(unittest.TestCase):
    """Wer sich verkonfiguriert hat, holt die geladene Vorlage zurück."""

    def setUp(self):
        from verteilerly.erweiterungen.blattvorlageneditor import dialog as editor

        self._ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self._ordner.cleanup)
        self.ordner = pathlib.Path(self._ordner.name)
        self.dialog = editor.EditorDialog(Programmattrappe(self.ordner))
        bauteil_zurueckgeben(self, self.dialog)
        self.addCleanup(self.dialog.done, 0)
        # Die Rueckfrage haengt sonst die Testreihe auf.
        self.verwerfen = mock.patch.object(
            editor, "frage", lambda *a, **k: editor.Knopf.Discard
        )
        self.verwerfen.start()
        self.addCleanup(self.verwerfen.stop)

    def test_ohne_aenderung_ist_der_knopf_aus(self):
        self.assertFalse(self.dialog.zuruecksetzen_knopf.isEnabled())

    def test_jede_aenderung_schaltet_ihn_an(self):
        self.dialog.zahlen["rand"].setValue(20.0)
        self.assertTrue(self.dialog.zuruecksetzen_knopf.isEnabled())

    def test_zuruecksetzen_holt_jeden_wert_zurueck(self):
        d = self.dialog
        d.basis_uebernehmen(BEISPIELVORLAGE)
        d.zahlen["rand"].setValue(30.0)
        d.name.setText("verkonfiguriert")
        d.bauart.setCurrentIndex(d.bauart.findData("standard"))

        d.zuruecksetzen()
        vorlage = d.vorlage()
        self.assertEqual(vorlage.rand, BEISPIELVORLAGE.rand)
        self.assertEqual(vorlage.name, BEISPIELVORLAGE.name)
        self.assertEqual(vorlage.schriftfeld_art, "beispiel")
        self.assertFalse(d.zuruecksetzen_knopf.isEnabled())

    def test_eine_abgelehnte_rueckfrage_aendert_nichts(self):
        from verteilerly.erweiterungen.blattvorlageneditor import dialog as editor

        d = self.dialog
        d.zahlen["rand"].setValue(30.0)
        with mock.patch.object(editor, "frage", lambda *a, **k: editor.Knopf.Cancel):
            d.zuruecksetzen()
        self.assertEqual(d.vorlage().rand, 30.0)
        self.assertTrue(d.zuruecksetzen_knopf.isEnabled())


class TestEigeneFelderImEditor(unittest.TestCase):
    """Die Namen der eigenen Felder gehören der Blattvorlage."""

    def setUp(self):
        from verteilerly.erweiterungen.blattvorlageneditor.dialog import EditorDialog

        self._ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self._ordner.cleanup)
        self.ordner = pathlib.Path(self._ordner.name)
        self.dialog = EditorDialog(Programmattrappe(self.ordner))
        bauteil_zurueckgeben(self, self.dialog)
        self.addCleanup(self.dialog.done, 0)

    def _setzen(self, *namen):
        self.dialog.eigene.clear()
        for name in namen:
            self.dialog.eigene.addItem(name)

    def test_die_standardvorlage_hat_keine(self):
        self.assertEqual(self.dialog.eigenefelder(), ())
        self.assertTrue(
            all(h.isChecked() for h in self.dialog.eigene_auf.values()),
            "gezeigt würden sie auf jeder Blattart",
        )

    def test_angelegte_namen_stehen_in_der_vorlage(self):
        self._setzen("Auftrag", "Monteur")
        self.assertEqual(
            self.dialog.vorlage().eigene_felder, ("Auftrag", "Monteur")
        )

    def test_leere_und_doppelte_namen_fallen_weg(self):
        self._setzen("Auftrag", "", "Auftrag", "  ")
        self.assertEqual(self.dialog.vorlage().eigene_felder, ("Auftrag",))

    def test_die_reihenfolge_laesst_sich_schieben(self):
        self._setzen("Auftrag", "Monteur")
        self.dialog.eigene.setCurrentRow(1)
        self.dialog._eigenes_schieben(-1)
        self.assertEqual(
            self.dialog.vorlage().eigene_felder, ("Monteur", "Auftrag")
        )

    def test_am_rand_schiebt_nichts_hinaus(self):
        self._setzen("Auftrag", "Monteur")
        self.dialog.eigene.setCurrentRow(0)
        self.dialog._eigenes_schieben(-1)
        self.dialog.eigene.setCurrentRow(1)
        self.dialog._eigenes_schieben(1)
        self.assertEqual(
            self.dialog.vorlage().eigene_felder, ("Auftrag", "Monteur")
        )

    def test_entfernen_nimmt_die_markierte_zeile(self):
        self._setzen("Auftrag", "Monteur")
        self.dialog.eigene.setCurrentRow(0)
        self.dialog._eigenes_weg()
        self.assertEqual(self.dialog.vorlage().eigene_felder, ("Monteur",))

    def test_die_blattarten_stehen_in_der_vorlage(self):
        self._setzen("Auftrag")
        self.dialog.eigene_auf["deckblatt"].setChecked(False)
        self.assertEqual(
            self.dialog.vorlage().eigene_felder_auf, ("belegung", "leisten")
        )

    def test_sie_ueberleben_den_rundlauf_durch_die_datei(self):
        from verteilerly.blattvorlagen import (
            blattvorlage_als_yaml,
            blattvorlage_aus_yaml,
        )

        self._setzen("Auftrag", "Monteur")
        self.dialog.eigene_auf["belegung"].setChecked(False)
        vorlage = self.dialog.vorlage()
        zurueck = blattvorlage_aus_yaml(blattvorlage_als_yaml(vorlage), "probe")
        self.assertEqual(zurueck.eigene_felder, ("Auftrag", "Monteur"))
        self.assertEqual(zurueck.eigene_felder_auf, ("deckblatt", "leisten"))

    def test_eine_geladene_vorlage_fuellt_die_liste(self):
        import dataclasses

        vorlage = dataclasses.replace(
            STANDARD,
            id="mit_feldern",
            name="Mit Feldern",
            eigene_felder=("Auftrag",),
            eigene_felder_auf=("leisten",),
        )
        self.dialog.basis_uebernehmen(vorlage)
        self.assertEqual(self.dialog.eigenefelder(), ("Auftrag",))
        self.assertTrue(self.dialog.eigene_auf["leisten"].isChecked())
        self.assertFalse(self.dialog.eigene_auf["deckblatt"].isChecked())

    def test_ein_platziertes_feld_steht_gleich_auf_dem_blatt(self):
        from verteilerly.layout import Text, leistenblatt

        self._setzen("Auftrag")
        self.dialog.schriftfeld.eigene_felder_setzen(("Auftrag",))
        self.dialog.schriftfeld.marke_hinzufuegen(0, "Auftrag")
        self.dialog.projekt.eigene_felder["Auftrag"] = "A-42"
        blatt = leistenblatt(self.dialog.projekt, 1, self.dialog.vorlage())
        texte = [e.text for e in blatt.elemente if isinstance(e, Text)]
        self.assertIn("Auftrag", texte)
        self.assertIn("A-42", texte)

    def test_zwei_felder_lassen_sich_auf_bloecke_verteilen(self):
        """Genau der Zweck: jedes Feld dorthin, wo es gebraucht wird."""
        self._setzen("Auftrag", "Monteur")
        self.dialog.schriftfeld.eigene_felder_setzen(("Auftrag", "Monteur"))
        self.dialog.schriftfeld.marke_hinzufuegen(0, "Auftrag")
        self.dialog.schriftfeld.marke_hinzufuegen(2, "Monteur")
        bloecke = [
            [eintrag.marke for eintrag in block]
            for block in self.dialog.vorlage().schriftfeld
        ]
        self.assertIn("Auftrag", bloecke[0])
        self.assertIn("Monteur", bloecke[2])
        self.assertNotIn("Monteur", bloecke[0])

    def test_die_eigenen_felder_stehen_im_auswahlmenue(self):
        self._setzen("Auftrag")
        self.dialog._eigene_geaendert()
        self.assertEqual(self.dialog.schriftfeld._eigene, ("Auftrag",))

    def test_ein_umbenanntes_feld_nimmt_seinen_eintrag_mit(self):
        """Sonst zeigte das Schriftfeld auf eine Marke, die es nicht gibt."""
        self._setzen("Auftrag")
        self.dialog.schriftfeld.eigene_felder_setzen(("Auftrag",))
        self.dialog.schriftfeld.marke_hinzufuegen(0, "Auftrag")
        self.dialog.eigene.item(0).setText("Bestellung")
        self.dialog._eigene_geaendert()
        marken = [
            eintrag.marke for block in self.dialog.vorlage().schriftfeld
            for eintrag in block
        ]
        self.assertNotIn("Auftrag", marken)
        # Und die Vorlage besteht weiter die Prüfung.
        from verteilerly.blattvorlagen import (
            blattvorlage_als_yaml,
            blattvorlage_aus_yaml,
        )

        zurueck = blattvorlage_aus_yaml(
            blattvorlage_als_yaml(self.dialog.vorlage()), "probe"
        )
        self.assertEqual(zurueck.eigene_felder, ("Bestellung",))

    def test_die_alte_sammelmarke_wird_uebergangen(self):
        """Bis 2026.09.30 stand „eigene" für alle Felder."""
        from verteilerly.blattvorlagen import blattvorlage_aus_yaml

        hinweise = []
        vorlage = blattvorlage_aus_yaml(
            {"id": "alt", "name": "Alt", "eigene_felder": ["Auftrag"],
             "schriftfeld": [["firma", "eigene"]]},
            "alt.yaml", hinweise,
        )
        self.assertEqual(
            [e.marke for e in vorlage.schriftfeld[0]], ["firma"]
        )
        self.assertTrue(any("eigene" in h for h in hinweise))


class TestSchriftfeldImEditor(unittest.TestCase):
    def setUp(self):
        from verteilerly.erweiterungen.blattvorlageneditor.dialog import EditorDialog

        self._ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self._ordner.cleanup)
        self.ordner = pathlib.Path(self._ordner.name)
        self.dialog = EditorDialog(Programmattrappe(self.ordner))
        bauteil_zurueckgeben(self, self.dialog)
        self.addCleanup(self.dialog.done, 0)

    def test_das_beispiel_hat_projektdaten(self):
        """Sonst stuenden im Schriftfeld nur Beschriftungen."""
        self.assertIn("Musterfirma", self.dialog.projekt.briefkopf["firma"])

    def test_die_ausgangsvorlage_stellt_das_schriftfeld_ein(self):
        d = self.dialog
        d.basiswahl.setCurrentIndex(d.basiswahl.findData(BEISPIELVORLAGE.id))
        self.assertEqual(d.schriftfeld.werte()[0], BEISPIELVORLAGE.schriftfeld)
        # Zwei Breiten zu drei Blöcken passen nicht - der Blockeditor
        # teilt dann nach Augenmaß, wie beim Lesen einer Datei.
        self.assertEqual(d.schriftfeld.werte()[1], ())

    def test_der_editor_baut_nur_schriftfelder_in_bloecken(self):
        """Die feste Aufteilung der Mustertabellen stellt er nicht ein.

        Er schreibt sie aber auch nicht um: die Vorlage behaelt ihre
        Bauart samt Breiten, sonst zeigte die Vorschau ein anderes Blatt
        als das Programm zeichnet.
        """
        d = self.dialog
        d.basiswahl.setCurrentIndex(d.basiswahl.findData(BEISPIELVORLAGE.id))
        self.assertEqual(BEISPIELVORLAGE.schriftfeld_art, "beispiel")
        self.assertEqual(d.vorlage().schriftfeld_art, "beispiel")
        self.assertEqual(
            d.vorlage().schriftfeld_anteile, BEISPIELVORLAGE.schriftfeld_anteile
        )
        self.assertFalse(d.schriftfeld.isEnabled())

    def test_der_briefkopf_wird_gespeichert_und_wieder_gelesen(self):
        import yaml

        d = self.dialog
        d.schriftfeld.block_entfernen()
        d.schriftfeld.marke_hinzufuegen(0, "dokumenttitel")
        d.schriftfeld.marke_hinzufuegen(0, "strich")
        d.schriftfeld.ausrichten(0, 0, "rechts")
        d.schriftfeld.eigene_breiten.setChecked(True)
        d.schriftfeld.breiten[0].setValue(3.0)
        d.schriftfeld.breiten[1].setValue(1.0)
        d._neu_zeichnen()
        self.assertTrue(d.speichern_knopf.isEnabled())
        kennung = d.speichern("Eigener Briefkopf")
        inhalt = yaml.safe_load((self.ordner / f"{kennung}.yaml").read_text(encoding="utf-8"))
        self.assertEqual(len(inhalt["schriftfeld"]), 2)
        self.assertEqual(inhalt["schriftfeld"][0][-2:], ["dokumenttitel", "strich"])
        # Nur was abweicht, steht lang da - der Rest bleibt die bloße Marke.
        self.assertEqual(
            inhalt["schriftfeld"][0][0], {"marke": "firma", "ausrichtung": "rechts"}
        )
        self.assertEqual(inhalt["schriftfeld_anteile"], [3, 1])
        gelesen = blattvorlage_aus_yaml(inhalt)
        self.assertEqual(gelesen.schriftfeld, d.vorlage().schriftfeld)
        self.assertEqual(gelesen.schriftfeld_anteile, (3.0, 1.0))


class TestRechtschreibdialog(unittest.TestCase):
    """Der Dialog der Rechtschreibpruefung - ohne eine einzige Anfrage.

    Gefragt wird hier nie: die Befunde werden von Hand gesetzt. Geprueft
    wird, was der Dialog daraus macht - und dass vor dem ersten Senden
    an eine auswaertige Adresse gefragt wird.
    """

    def setUp(self):
        from verteilerly.erweiterungen.rechtschreibung import (
            SCHLUESSEL_LANGUAGETOOL, SCHLUESSEL_SERVER, SCHLUESSEL_SPRACHE,
            SCHLUESSEL_WOERTERBUCH, SCHLUESSEL_ZUGESTIMMT,
        )
        from verteilerly.erweiterungen.rechtschreibung.dialog import RechtschreibDialog
        from verteilerly.gui.erweiterungen import Schnittstelle
        from verteilerly.gui.hauptfenster import Hauptfenster
        from verteilerly.modell import Aderadresse, Projekt, Verteiler

        from . import einstellung_bewahren

        self.Dialog = RechtschreibDialog
        self.fenster = Hauptfenster()
        bauteil_zurueckgeben(self, self.fenster)
        for schluessel in (SCHLUESSEL_SERVER, SCHLUESSEL_SPRACHE,
                           SCHLUESSEL_ZUGESTIMMT, SCHLUESSEL_LANGUAGETOOL,
                           SCHLUESSEL_WOERTERBUCH):
            einstellung_bewahren(self, self.fenster.einstellungen, schluessel)

        verteiler = Verteiler.aus_geometrie(1, 2, 4, name="Muster")
        verteiler.ader(Aderadresse(1, 1, "a")).bezeichnung = "Melder Werkstat"
        self.projekt = Projekt(verteiler=verteiler)
        self.fenster._projekt_setzen(self.projekt, None)

        menue = next(
            a.menu() for a in self.fenster.menuBar().actions()
            if a.text().replace("&", "") == "Erweiterungen"
        )
        self.schnittstelle = Schnittstelle(
            self.fenster, menue, self.fenster._erweiterungstrenner,
            Fund("rechtschreibung", "Rechtschreibprüfung"),
        )
        self.dialog = RechtschreibDialog(self.schnittstelle, self.fenster)
        bauteil_zurueckgeben(self, self.dialog)

    def _befund(self, wort="Werkstat", ersatz="Werkstatt"):
        from verteilerly.erweiterungen.rechtschreibung import pruefer

        stelle = next(
            s for s in pruefer.zu_pruefen(self.projekt) if wort in s.text
        )
        return pruefer.Befund(
            stelle, stelle.text.index(wort), len(wort), "Tippfehler", (ersatz,)
        )

    def _zeigen(self, *befunde):
        # Kein Faden: die erste Zeile wird gleich ausgewaehlt, und ein
        # Befund des Woerterbuchs schickte dann einen Faden nach
        # Vorschlaegen los - der laedt 4 MB und laeuft Sekunden.
        from verteilerly.erweiterungen.rechtschreibung import dialog as dialogmodul

        with mock.patch.object(dialogmodul.threading, "Thread"):
            self.dialog._ergebnis(list(befunde), "")

    def test_die_liste_zeigt_ort_wort_und_vorschlag(self):
        self._zeigen(self._befund())
        eintrag = self.dialog.liste.topLevelItem(0)
        self.assertIn("Leiste", eintrag.text(0))
        self.assertEqual(eintrag.text(2), "Werkstat")
        self.assertEqual(eintrag.text(4), "Werkstatt")
        self.assertIn("1", self.dialog.stand.text())

    def test_uebernehmen_aendert_das_projekt_und_meldet_es(self):
        from verteilerly.modell import Aderadresse

        self._zeigen(self._befund())
        with mock.patch.object(
            type(self.fenster), "_belegung_geaendert"
        ) as gemeldet:
            self.dialog.uebernehmen()
        self.assertTrue(gemeldet.called)
        self.assertEqual(
            self.projekt.verteiler.ader(Aderadresse(1, 1, "a")).bezeichnung,
            "Melder Werkstatt",
        )
        # Die erledigte Stelle steht nicht mehr in der Liste.
        self.assertEqual(self.dialog.liste.topLevelItemCount(), 0)

    def test_schreibgeschuetzt_bleibt_uebernehmen_aus(self):
        self._zeigen(self._befund())
        self.fenster.schreibschutz_setzen(True)
        self.dialog._knoepfe_auffrischen()
        self.assertFalse(self.dialog.uebernehmen_knopf.isEnabled())
        self.assertTrue(self.dialog.springen_knopf.isEnabled())

    def test_springen_zeigt_die_stelle(self):
        befund = self._befund()
        self._zeigen(befund)
        with mock.patch.object(type(self.fenster), "_zur_fundstelle") as gezeigt:
            self.dialog.springen()
        self.assertEqual(gezeigt.call_args[0][0], befund.stelle)

    def test_vor_dem_ersten_senden_wird_gefragt(self):
        from verteilerly.erweiterungen.rechtschreibung import (
            SCHLUESSEL_ZUGESTIMMT, dialog as dialogmodul, pruefer,
        )

        self.dialog.lt_haken.setChecked(True)
        self.dialog.serverfeld.setText(pruefer.SERVER)
        with mock.patch.object(
            dialogmodul, "frage", return_value=dialogmodul.Knopf.No
        ) as gefragt, mock.patch.object(pruefer, "pruefen") as geprueft:
            self.dialog.pruefen()
        self.assertTrue(gefragt.called)
        self.assertFalse(geprueft.called)
        self.assertFalse(self.fenster.einstellungen.value(SCHLUESSEL_ZUGESTIMMT, ""))

    def test_der_eigene_server_wird_nicht_erst_erfragt(self):
        from verteilerly.erweiterungen.rechtschreibung import dialog as dialogmodul

        self.dialog.lt_haken.setChecked(True)
        self.dialog.serverfeld.setText("http://localhost:8081/v2/check")
        with mock.patch.object(dialogmodul, "frage") as gefragt, \
                mock.patch.object(dialogmodul.threading, "Thread") as faden:
            self.dialog.pruefen()
        self.assertFalse(gefragt.called)
        self.assertTrue(faden.called)

    def test_ohne_languagetool_wird_nichts_gefragt_und_nichts_gesendet(self):
        """Das Woerterbuch allein schickt nichts hinaus - also keine Rueckfrage."""
        from verteilerly.erweiterungen.rechtschreibung import (
            dialog as dialogmodul, pruefer,
        )

        self.dialog.lt_haken.setChecked(False)
        self.dialog.wb_haken.setChecked(True)
        self.dialog.serverfeld.setText(pruefer.SERVER)
        with mock.patch.object(dialogmodul, "frage") as gefragt, \
                mock.patch.object(pruefer, "abrufen") as gesendet, \
                mock.patch.object(dialogmodul.threading, "Thread") as faden:
            self.dialog.pruefen()
        self.assertFalse(gefragt.called)
        self.assertFalse(gesendet.called)
        self.assertTrue(faden.called)

    def test_ohne_pruefer_passiert_gar_nichts(self):
        from verteilerly.erweiterungen.rechtschreibung import dialog as dialogmodul

        self.dialog.lt_haken.setChecked(False)
        self.dialog.wb_haken.setChecked(False)
        with mock.patch.object(dialogmodul.threading, "Thread") as faden:
            self.dialog.pruefen()
        self.assertFalse(faden.called)
        self.assertIn("Prüfer", self.dialog.stand.text())

    def test_die_beiden_schalter_werden_gemerkt(self):
        from verteilerly.erweiterungen.rechtschreibung import (
            SCHLUESSEL_LANGUAGETOOL, SCHLUESSEL_WOERTERBUCH,
            dialog as dialogmodul,
        )

        self.dialog.lt_haken.setChecked(True)
        self.dialog.wb_haken.setChecked(False)
        self.dialog.serverfeld.setText("http://localhost:8081/v2/check")
        with mock.patch.object(dialogmodul.threading, "Thread"):
            self.dialog.pruefen()
        werte = self.fenster.einstellungen
        self.assertTrue(werte.value(SCHLUESSEL_LANGUAGETOOL, False, type=bool))
        self.assertFalse(werte.value(SCHLUESSEL_WOERTERBUCH, True, type=bool))

    def test_ein_aufgenommenes_wort_verschwindet_aus_der_liste(self):
        """Und zwar jedes Vorkommen - nicht nur die angeklickte Zeile."""
        from verteilerly.erweiterungen.rechtschreibung import (
            dialog as dialogmodul, pruefer,
        )

        befund = self._befund()
        aus_woerterbuch = dataclasses.replace(
            befund, vorschlaege=(), quelle=pruefer.WOERTERBUCH
        )
        self._zeigen(aus_woerterbuch)
        with mock.patch.object(
            dialogmodul.woerterbuch, "eigenes_wort_aufnehmen", return_value=True
        ) as aufgenommen:
            self.dialog.wort_aufnehmen()
        self.assertEqual(aufgenommen.call_args[0][0], "Werkstat")
        self.assertEqual(self.dialog.liste.topLevelItemCount(), 0)

    def test_das_pfeilmenue_zaehlt_jeden_vorschlag_auf(self):
        befund = dataclasses.replace(
            self._befund(), vorschlaege=("Werkstatt", "Werkstätte", "Werkstoff")
        )
        self._zeigen(befund)
        self.assertEqual(
            [a.text() for a in self.dialog.vorschlagsmenue.actions()],
            ["Werkstatt", "Werkstätte", "Werkstoff"],
        )

    def test_aus_dem_pfeilmenue_kommt_der_gewaehlte_vorschlag(self):
        """Der Knopf nimmt den ersten, das Menue den angeklickten."""
        from verteilerly.modell import Aderadresse

        self._zeigen(dataclasses.replace(
            self._befund(), vorschlaege=("Werkstatt", "Werkstätte")
        ))
        with mock.patch.object(type(self.fenster), "_belegung_geaendert"):
            self.dialog.vorschlagsmenue.actions()[1].trigger()
        self.assertEqual(
            self.projekt.verteiler.ader(Aderadresse(1, 1, "a")).bezeichnung,
            "Melder Werkstätte",
        )

    def test_schreibgeschuetzt_bleibt_auch_das_pfeilmenue_aus(self):
        self.fenster.schreibschutz_setzen(True)
        self._zeigen(dataclasses.replace(
            self._befund(), vorschlaege=("Werkstatt", "Werkstätte")
        ))
        self.assertFalse(
            any(a.isEnabled() for a in self.dialog.vorschlagsmenue.actions())
        )

    def test_aufnehmen_gibt_es_nur_fuer_das_woerterbuch(self):
        """Was LanguageTool meldet, ist keine Frage des Wortschatzes."""
        self._zeigen(self._befund())
        self.assertFalse(self.dialog.aufnehmen_knopf.isEnabled())

    def test_vorschlaege_kommen_nachtraeglich_in_die_zeile(self):
        """Das Woerterbuch schlaegt erst vor, wenn jemand hinsieht."""
        from verteilerly.erweiterungen.rechtschreibung import pruefer

        befund = dataclasses.replace(
            self._befund(), vorschlaege=(), quelle=pruefer.WOERTERBUCH
        )
        self._zeigen(befund)
        self.assertEqual(self.dialog.liste.topLevelItem(0).text(4), "")
        self.assertFalse(self.dialog.uebernehmen_knopf.isEnabled())

        self.dialog._vorschlaege_eingetroffen("Werkstat", ("Werkstatt", "Werkstoff"))
        self.assertEqual(
            self.dialog.liste.topLevelItem(0).text(4), "Werkstatt, Werkstoff"
        )
        self.assertTrue(self.dialog.uebernehmen_knopf.isEnabled())
        # Nachgereichte Vorschlaege stehen auch im Pfeilmenue.
        self.assertEqual(
            [a.text() for a in self.dialog.vorschlagsmenue.actions()],
            ["Werkstatt", "Werkstoff"],
        )
        with mock.patch.object(type(self.fenster), "_belegung_geaendert"):
            self.dialog.uebernehmen()
        from verteilerly.modell import Aderadresse
        self.assertEqual(
            self.projekt.verteiler.ader(Aderadresse(1, 1, "a")).bezeichnung,
            "Melder Werkstatt",
        )


if __name__ == "__main__":
    unittest.main()
