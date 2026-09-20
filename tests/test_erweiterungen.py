"""Tests zu den Erweiterungen und zum Blattvorlagen-Editor."""

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

from verteilerly import erweiterungen  # noqa: E402
from verteilerly.blattvorlagen import (  # noqa: E402
    STANDARD,
    Blattvorlagen,
    blattvorlage_aus_yaml,
)
from verteilerly.erweiterungen import Fund  # noqa: E402

from . import BEISPIELVORLAGE  # noqa: E402

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
        self.addCleanup(self.fenster.close)

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
        self.assertEqual(texte, ["Blattvorlagen-Editor…", "Erweiterungen verwalten…"])
        editor = next(a for a in eintraege if "Blattvorlagen" in a.text())
        self.assertEqual(editor.property("erweiterung"), "blattvorlageneditor")
        self.assertFalse(editor.property("fremd"))

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


class TestVerwaltenDialog(unittest.TestCase):
    def test_zeigt_herkunft_fehler_und_wahl(self):
        from PySide6.QtCore import Qt
        from verteilerly.gui.erweiterungen import ErweiterungenDialog

        funde = erweiterungen.finden([]) + [
            Fund("hallo", "hallo", "Sagt Hallo", eingebaut=False, ort=pathlib.Path("/x/hallo.py")),
            Fund("kaputt", "kaputt", eingebaut=False, ort=pathlib.Path("/x/kaputt.py"),
                 fehler="ModuleNotFoundError: gibtesnicht"),
        ]
        dialog = ErweiterungenDialog(funde, {"kaputt"}, set(), None)
        self.addCleanup(dialog.close)
        hallo, kaputt = dialog.eintraege["hallo"], dialog.eintraege["kaputt"]
        self.assertEqual(hallo.text(1), "hallo.py")
        self.assertEqual(hallo.checkState(0), Qt.CheckState.Unchecked)
        self.assertIn("gibtesnicht", kaputt.text(2))
        self.assertEqual(kaputt.checkState(0), Qt.CheckState.Checked)
        self.assertFalse(dialog.ordnerknopf.isEnabled())

        hallo.setCheckState(0, Qt.CheckState.Checked)
        dialog.eintraege["blattvorlageneditor"].setCheckState(0, Qt.CheckState.Unchecked)
        self.assertEqual(dialog.wahl(), ({"hallo", "kaputt"}, {"blattvorlageneditor"}))


class TestBlattvorlagenEditor(unittest.TestCase):
    def setUp(self):
        from verteilerly.erweiterungen.blattvorlageneditor.dialog import EditorDialog

        self._ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self._ordner.cleanup)
        self.ordner = pathlib.Path(self._ordner.name)
        self.programm = Programmattrappe(self.ordner)
        self.dialog = EditorDialog(self.programm)
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


class TestSchriftfeldEditor(unittest.TestCase):
    """Die Bloecke des Schriftfeldes - der Briefkopf am Blattfuss."""

    def setUp(self):
        from verteilerly.blattvorlagen import STANDARDSCHRIFTFELD
        from verteilerly.erweiterungen.blattvorlageneditor.schriftfeld import SchriftfeldEditor

        self.editor = SchriftfeldEditor()
        self.addCleanup(self.editor.deleteLater)
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
        self.assertEqual(e.werte()[0][0][-1], "dokumenttitel")
        e.marke_entfernen(0, 0)
        self.assertNotIn("firma", e.werte()[0][0])
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
        self.assertEqual(e.werte()[0][1][-1], "strich")
        self.assertEqual(e.listen[1].item(e.listen[1].count() - 1).text(), "Querstrich")

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


class TestSchriftfeldImEditor(unittest.TestCase):
    def setUp(self):
        from verteilerly.erweiterungen.blattvorlageneditor.dialog import EditorDialog

        self._ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self._ordner.cleanup)
        self.ordner = pathlib.Path(self._ordner.name)
        self.dialog = EditorDialog(Programmattrappe(self.ordner))
        self.addCleanup(self.dialog.done, 0)

    def test_das_beispiel_hat_projektdaten(self):
        """Sonst stuenden im Schriftfeld nur Beschriftungen."""
        self.assertIn("Musterfirma", self.dialog.projekt.briefkopf["firma"])

    def test_die_ausgangsvorlage_stellt_das_schriftfeld_ein(self):
        d = self.dialog
        d.basiswahl.setCurrentIndex(d.basiswahl.findData(BEISPIELVORLAGE.id))
        self.assertEqual(d.schriftfeld.werte()[0], BEISPIELVORLAGE.schriftfeld)
        # Zwei Breiten zu drei Blöcken passen nicht - dann teilt das
        # Programm nach Augenmaß, wie beim Lesen einer Datei.
        self.assertEqual(d.schriftfeld.werte()[1], ())
        self.assertEqual(d.vorlage().schriftfeld_anteile, ())

    def test_der_editor_baut_nur_schriftfelder_in_bloecken(self):
        """Die feste Aufteilung der Mustertabellen stellt er nicht ein."""
        d = self.dialog
        d.basiswahl.setCurrentIndex(d.basiswahl.findData(BEISPIELVORLAGE.id))
        self.assertEqual(BEISPIELVORLAGE.schriftfeld_art, "beispiel")
        self.assertEqual(d.vorlage().schriftfeld_art, "standard")

    def test_der_briefkopf_wird_gespeichert_und_wieder_gelesen(self):
        import yaml

        d = self.dialog
        d.schriftfeld.block_entfernen()
        d.schriftfeld.marke_hinzufuegen(0, "dokumenttitel")
        d.schriftfeld.marke_hinzufuegen(0, "strich")
        d.schriftfeld.eigene_breiten.setChecked(True)
        d.schriftfeld.breiten[0].setValue(3.0)
        d.schriftfeld.breiten[1].setValue(1.0)
        d._neu_zeichnen()
        self.assertTrue(d.speichern_knopf.isEnabled())
        kennung = d.speichern("Eigener Briefkopf")
        inhalt = yaml.safe_load((self.ordner / f"{kennung}.yaml").read_text(encoding="utf-8"))
        self.assertEqual(len(inhalt["schriftfeld"]), 2)
        self.assertEqual(inhalt["schriftfeld"][0][-2:], ["dokumenttitel", "strich"])
        self.assertEqual(inhalt["schriftfeld_anteile"], [3, 1])
        gelesen = blattvorlage_aus_yaml(inhalt)
        self.assertEqual(gelesen.schriftfeld, d.vorlage().schriftfeld)
        self.assertEqual(gelesen.schriftfeld_anteile, (3.0, 1.0))


if __name__ == "__main__":
    unittest.main()
