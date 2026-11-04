"""Tests zur Erweiterung *Projekt*: mehrere Verteiler auf einmal anlegen.

Zwei Haelften: der **Plan** (``anlage.py``, ohne Qt) wird gegen einen
Temp-Ordner gerechnet - geschrieben wird dort erst, wenn der Test es
verlangt -, und der **Dialog** gegen ein echtes Hauptfenster, aber ohne
Dateidialog und ohne ``exec()``.

Ein Auge gilt dabei durchgehend den **Beilagen**: sie gehoeren dem
Projektordner und werden **einmal** gelegt, nicht je Verteiler.
"""

from __future__ import annotations

# Erst das Paket: es legt Einstellungs- und Arbeitsordner der
# Testreihe um, bevor etwas aus verteilerly Pfade liest.
from . import TESTHEIM  # noqa: F401

import os
import pathlib
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

ANWENDUNG = QApplication.instance() or QApplication([])

from verteilerly.erweiterungen.projekt import (  # noqa: E402
    SCHLUESSEL_BEILAGEN,
    SCHLUESSEL_EIGENER_ORDNER,
    SCHLUESSEL_ORDNER,
    anlage,
    erweiterung,
)
from verteilerly.erweiterungen.projekt.anlage import (  # noqa: E402
    Angabe,
    Beilage,
    ablagename,
    anlegen,
    planen,
    sicherer_name,
    sicherer_unterordner,
)
from verteilerly.modell import Projekt, Verteiler  # noqa: E402

from . import bauteil_zurueckgeben, einstellung_bewahren  # noqa: E402


def _projekt_fuer(angabe: Angabe) -> Projekt:
    """Ein winziger Verteiler je Zeile - die Geometrie ist hier nicht die Frage."""
    return Projekt(
        verteiler=Verteiler.aus_geometrie(
            1, 1, 2, angabe.name.strip(), angabe.nummer.strip()
        ),
        briefkopf={"firma": "Beliebig GmbH"},
    )


class TestNamen(unittest.TestCase):
    """Ein Ordnername muss auf jedem Dateisystem heissen, wie er heisst."""

    def test_verbotene_zeichen_werden_zu_leerzeichen(self):
        self.assertEqual(sicherer_name("HVt/UVt"), "HVt UVt")
        self.assertEqual(sicherer_name('a:b*c?"d'), "a b c d")

    def test_punkt_und_leerzeichen_am_ende_fallen_weg(self):
        """Windows laesst sie stillschweigend fallen - dann hiesse die Datei anders."""
        self.assertEqual(sicherer_name(" Verteiler 1. "), "Verteiler 1")

    def test_nichts_brauchbares_ergibt_nichts(self):
        self.assertEqual(sicherer_name("..."), "")
        self.assertEqual(sicherer_name("/"), "")

    def test_lang_wird_gekuerzt(self):
        self.assertEqual(len(sicherer_name("x" * 300)), anlage.NAME_HOECHSTENS)

    def test_ein_unterordner_fuehrt_nicht_hinaus(self):
        """``..`` und ein absoluter Pfad sind kein Unterordner."""
        self.assertEqual(sicherer_unterordner("../../weg"), "weg")
        # Aus einem absoluten Pfad wird ein tiefer Unterordner - er
        # faengt nicht mehr an der Wurzel an.
        self.assertEqual(sicherer_unterordner("/etc/passwd"), "etc/passwd")
        self.assertEqual(sicherer_unterordner("Fotos\\2026"), "Fotos/2026")
        self.assertEqual(sicherer_unterordner(".."), "")

    def test_die_nummer_steht_vorn(self):
        """So liegen die Ordner in der Reihenfolge der Anlage."""
        self.assertEqual(
            ablagename(Angabe("Verteiler Keller", "1.1")), "1.1 Verteiler Keller"
        )
        self.assertEqual(ablagename(Angabe("Keller")), "Keller")
        self.assertEqual(ablagename(Angabe("", "1.1")), "1.1")

    def test_eine_eigene_angabe_gilt(self):
        self.assertEqual(
            ablagename(Angabe("Keller", "1.1", "Mein Ordner")), "Mein Ordner"
        )


class TestBeilagenBestand(unittest.TestCase):
    """Wie der Bestand in der Conf steht."""

    def test_hin_und_zurueck(self):
        beilagen = [
            Beilage(pathlib.Path("/tmp/a.txt"), "Dokumentation"),
            Beilage(pathlib.Path("/tmp/b.txt"), ""),
        ]
        wieder = anlage.beilagen_lesen(anlage.beilagen_schreiben(beilagen))
        self.assertEqual(wieder, beilagen)

    def test_eine_zeile_ohne_tabulator_ist_die_quelle(self):
        beilagen = anlage.beilagen_lesen("/tmp/a.txt\n\n")
        self.assertEqual(beilagen, [Beilage(pathlib.Path("/tmp/a.txt"), "")])

    def test_nichts_ergibt_nichts(self):
        self.assertEqual(anlage.beilagen_lesen(None), [])
        self.assertEqual(anlage.beilagen_lesen(""), [])


class TestWasEineBeilageMitbringt(unittest.TestCase):
    """Eine Datei bringt sich selbst, ein Ordner seinen Inhalt."""

    def test_eine_datei_kommt_in_ihr_fach(self):
        quelle = pathlib.Path(tempfile.mkdtemp()) / "Checkliste.txt"
        quelle.write_text("haken", encoding="utf-8")
        dateien, faecher = anlage.beilagendateien(Beilage(quelle, "Dokumentation"))
        self.assertEqual(dateien, ((quelle, "Dokumentation/Checkliste.txt"),))
        self.assertEqual(faecher, ("Dokumentation",))

    def test_ohne_fach_kommt_sie_unmittelbar_hinein(self):
        quelle = pathlib.Path(tempfile.mkdtemp()) / "Checkliste.txt"
        quelle.write_text("haken", encoding="utf-8")
        dateien, faecher = anlage.beilagendateien(Beilage(quelle, ""))
        self.assertEqual(dateien, ((quelle, "Checkliste.txt"),))
        self.assertEqual(faecher, ())

    def test_ein_ordner_bringt_seinen_inhalt_mit(self):
        muster = pathlib.Path(tempfile.mkdtemp()) / "Muster"
        (muster / "tief").mkdir(parents=True)
        (muster / "oben.txt").write_text("o", encoding="utf-8")
        (muster / "tief" / "unten.txt").write_text("u", encoding="utf-8")
        dateien, faecher = anlage.beilagendateien(Beilage(muster, "Vorlagen"))
        self.assertEqual(
            sorted(ziel for _quelle, ziel in dateien),
            ["Vorlagen/oben.txt", "Vorlagen/tief/unten.txt"],
        )
        self.assertIn("Vorlagen", faecher)
        self.assertIn("Vorlagen/tief", faecher)

    def test_ein_leerer_ordner_bringt_sich_selbst_mit(self):
        """So laesst sich ein leeres Fach vorgeben."""
        leer = pathlib.Path(tempfile.mkdtemp()) / "leer"
        leer.mkdir()
        dateien, faecher = anlage.beilagendateien(Beilage(leer, "Fotos"))
        self.assertEqual(dateien, ())
        self.assertEqual(faecher, ("Fotos",))

    def test_eine_verschwundene_quelle_bringt_nichts_mit(self):
        weg = Beilage(pathlib.Path(tempfile.mkdtemp()) / "nichts.txt", "")
        self.assertTrue(weg.fehlt)
        self.assertEqual(anlage.beilagendateien(weg), ((), ()))


class TestPlanen(unittest.TestCase):
    """Gerechnet, nicht geschrieben."""

    def setUp(self):
        self.ordner = pathlib.Path(tempfile.mkdtemp(prefix="projekt-"))

    def test_je_zeile_ein_ordner_mit_der_datei_darin(self):
        plan = planen([Angabe("Keller", "1.1"), Angabe("Dach", "1.2")], self.ordner)
        self.assertEqual(plan.ordner, self.ordner)
        self.assertEqual(len(plan.anlagen), 2)
        self.assertEqual(len(plan.moegliche), 2)
        self.assertEqual(plan.anlagen[0].ordner, self.ordner / "1.1 Keller")
        self.assertEqual(plan.anlagen[0].datei.name, "1.1 Keller.vtly")
        # Gerechnet heisst: auf der Platte steht noch nichts.
        self.assertEqual(list(self.ordner.iterdir()), [])

    def test_leere_zeilen_fallen_weg(self):
        plan = planen([Angabe(), Angabe("Keller"), Angabe("  ", " ")], self.ordner)
        self.assertEqual([x.angabe.name for x in plan.anlagen], ["Keller"])

    def test_ohne_eigenen_ordner_liegen_alle_im_projektordner(self):
        plan = planen(
            [Angabe("Keller"), Angabe("Dach")], self.ordner, eigener_ordner=False
        )
        self.assertEqual({x.ordner for x in plan.anlagen}, {self.ordner})
        self.assertEqual(
            [x.datei.name for x in plan.anlagen], ["Keller.vtly", "Dach.vtly"]
        )

    def test_derselbe_name_zweimal_ist_ein_grund(self):
        plan = planen([Angabe("Keller"), Angabe("keller")], self.ordner)
        self.assertTrue(plan.anlagen[0].geht)
        self.assertFalse(plan.anlagen[1].geht)

    def test_eine_vorhandene_datei_bleibt_stehen(self):
        (self.ordner / "Keller").mkdir()
        (self.ordner / "Keller" / "Keller.vtly").write_text("{}", encoding="utf-8")
        plan = planen([Angabe("Keller")], self.ordner)
        self.assertFalse(plan.anlagen[0].geht)

    def test_ein_name_ohne_brauchbare_zeichen_ist_ein_grund(self):
        plan = planen([Angabe("///")], self.ordner)
        self.assertFalse(plan.anlagen[0].geht)

    def test_die_beilagen_haengen_am_plan_nicht_an_der_zeile(self):
        """Sie gehoeren dem Projektordner - einmal, nicht je Verteiler."""
        quelle = pathlib.Path(tempfile.mkdtemp()) / "Checkliste.txt"
        quelle.write_text("haken", encoding="utf-8")
        plan = planen(
            [Angabe("Keller"), Angabe("Dach")], self.ordner,
            [Beilage(quelle, "Dokumentation")],
        )
        self.assertEqual(plan.dateien, ((quelle, "Dokumentation/Checkliste.txt"),))
        self.assertEqual(plan.faecher, ("Dokumentation",))
        for teil in plan.anlagen:
            self.assertFalse(hasattr(teil, "dateien"))

    def test_der_haken_aendert_an_den_beilagen_nichts(self):
        quelle = pathlib.Path(tempfile.mkdtemp()) / "Checkliste.txt"
        quelle.write_text("haken", encoding="utf-8")
        beilagen = [Beilage(quelle, "")]
        mit = planen([Angabe("Keller")], self.ordner, beilagen)
        ohne = planen(
            [Angabe("Keller")], self.ordner, beilagen, eigener_ordner=False
        )
        self.assertEqual(mit.dateien, ohne.dateien)


class TestAnlegen(unittest.TestCase):
    """Jetzt wird geschrieben."""

    def setUp(self):
        self.ordner = pathlib.Path(tempfile.mkdtemp(prefix="projekt-"))
        quelle = pathlib.Path(tempfile.mkdtemp())
        self.muster = quelle / "Checkliste.txt"
        self.muster.write_text("haken", encoding="utf-8")
        self.leer = quelle / "leer"
        self.leer.mkdir()

    def _plan(self, **mehr):
        return planen(
            [Angabe("Keller", "1.1"), Angabe("Dach", "1.2")], self.ordner,
            [Beilage(self.muster, "Dokumentation"), Beilage(self.leer, "Fotos")],
            **mehr
        )

    def test_je_verteiler_ein_ordner_die_beilagen_einmal(self):
        bericht = anlegen(self._plan(), _projekt_fuer)
        self.assertEqual(bericht.angelegt, 2)
        self.assertEqual(bericht.beigelegt, 1)
        self.assertEqual(bericht.gruende, [])
        self.assertEqual(bericht.ordner, self.ordner)
        for name in ("1.1 Keller", "1.2 Dach"):
            self.assertTrue((self.ordner / name / f"{name}.vtly").is_file())
            # Im Verteilerordner liegt nur seine Datei.
            self.assertEqual(
                [x.name for x in (self.ordner / name).iterdir()], [f"{name}.vtly"]
            )
        self.assertTrue(
            (self.ordner / "Dokumentation" / "Checkliste.txt").is_file()
        )

    def test_ein_leeres_fach_entsteht_auch(self):
        anlegen(self._plan(), _projekt_fuer)
        self.assertTrue((self.ordner / "Fotos").is_dir())
        self.assertEqual(list((self.ordner / "Fotos").iterdir()), [])

    def test_was_geschrieben_wurde_laesst_sich_lesen(self):
        from verteilerly import projektdatei

        anlegen(self._plan(), _projekt_fuer)
        projekt = projektdatei.laden(
            self.ordner / "1.1 Keller" / "1.1 Keller.vtly"
        )
        self.assertEqual(projekt.verteiler.name, "Keller")
        self.assertEqual(projekt.verteiler.nummer, "1.1")
        self.assertEqual(projekt.briefkopf["firma"], "Beliebig GmbH")

    def test_ein_zweiter_durchgang_ueberschreibt_nichts(self):
        anlegen(self._plan(), _projekt_fuer)
        bericht = anlegen(self._plan(), _projekt_fuer)
        self.assertEqual(bericht.angelegt, 0)
        self.assertEqual(len(bericht.gruende), 2)
        # Ohne eine einzige Zeile entsteht auch keine Beilage noch einmal.
        self.assertEqual(bericht.beigelegt, 0)
        self.assertEqual(bericht.uebergangen, 0)

    def test_ein_dritter_verteiler_kommt_in_denselben_ordner(self):
        """Ein zweiter Durchgang ergaenzt, was fehlt."""
        anlegen(self._plan(), _projekt_fuer)
        plan = planen(
            [Angabe("Dachboden", "1.3")], self.ordner,
            [Beilage(self.muster, "Dokumentation")],
        )
        bericht = anlegen(plan, _projekt_fuer)
        self.assertEqual(bericht.angelegt, 1)
        # Die Beilage lag schon da - sie wird gezaehlt, nicht ersetzt.
        self.assertEqual(bericht.uebergangen, 1)
        self.assertEqual(bericht.beigelegt, 0)

    def test_eine_vorhandene_beilage_wird_uebergangen_nicht_ersetzt(self):
        ordner = self.ordner / "Dokumentation"
        ordner.mkdir(parents=True)
        (ordner / "Checkliste.txt").write_text("von Hand", encoding="utf-8")
        bericht = anlegen(self._plan(), _projekt_fuer)
        self.assertEqual(bericht.uebergangen, 1)
        self.assertEqual(
            (ordner / "Checkliste.txt").read_text(encoding="utf-8"), "von Hand"
        )

    def test_eine_zeile_mit_grund_wird_uebergangen_die_andere_nicht(self):
        plan = self._plan()
        plan.anlagen[0].grund = "Probe"
        bericht = anlegen(plan, _projekt_fuer)
        self.assertEqual(bericht.angelegt, 1)
        self.assertEqual(bericht.gruende, ["1.1 Keller: Probe"])

    def test_ohne_eine_einzige_zeile_entsteht_kein_ordner(self):
        """Ein Projekt aus lauter Gruenden ist keines."""
        plan = self._plan()
        for teil in plan.anlagen:
            teil.grund = "Probe"
        bericht = anlegen(plan, _projekt_fuer)
        self.assertEqual(bericht.angelegt, 0)
        self.assertIsNone(bericht.ordner)
        self.assertEqual(list(self.ordner.iterdir()), [])

    def test_ein_fehler_haelt_den_rest_nicht_auf(self):
        """Ein gesperrter Ordner soll nicht die anderen Verteiler kosten."""
        def launisch(angabe):
            if angabe.name == "Keller":
                raise OSError("kein Platz")
            return _projekt_fuer(angabe)

        bericht = anlegen(self._plan(), launisch)
        self.assertEqual(bericht.angelegt, 1)
        self.assertEqual(len(bericht.gruende), 1)
        self.assertTrue((self.ordner / "1.2 Dach" / "1.2 Dach.vtly").is_file())

    def test_ohne_eigenen_ordner_liegt_alles_nebeneinander(self):
        bericht = anlegen(self._plan(eigener_ordner=False), _projekt_fuer)
        self.assertEqual(bericht.angelegt, 2)
        self.assertEqual(bericht.beigelegt, 1)
        self.assertTrue((self.ordner / "1.1 Keller.vtly").is_file())
        self.assertTrue((self.ordner / "1.2 Dach.vtly").is_file())
        self.assertTrue((self.ordner / "Dokumentation" / "Checkliste.txt").is_file())


class TestDialog(unittest.TestCase):
    """Der Dialog - mit echtem Fenster, ohne Dateidialog und ohne exec()."""

    def setUp(self):
        from verteilerly.erweiterungen import Fund
        from verteilerly.erweiterungen.projekt.dialog import ProjektDialog
        from verteilerly.gui.erweiterungen import Schnittstelle
        from verteilerly.gui.hauptfenster import Hauptfenster

        self.fenster = Hauptfenster()
        bauteil_zurueckgeben(self, self.fenster)
        for schluessel in (SCHLUESSEL_ORDNER, SCHLUESSEL_BEILAGEN,
                           SCHLUESSEL_EIGENER_ORDNER):
            einstellung_bewahren(self, self.fenster.einstellungen, schluessel)
        menue = next(
            a.menu() for a in self.fenster.menuBar().actions()
            if a.text().replace("&", "") == "Erweiterungen"
        )
        self.schnittstelle = Schnittstelle(
            self.fenster, menue, self.fenster._erweiterungstrenner,
            Fund("projekt", "Projekt"),
        )
        self.ordner = pathlib.Path(tempfile.mkdtemp(prefix="projekt-"))
        self.dialog = ProjektDialog(self.schnittstelle, self.fenster)
        bauteil_zurueckgeben(self, self.dialog)
        self.dialog.ordnerfeld.setText(str(self.ordner))

    def _zeile(self, zeile: int, name: str, nummer: str = "") -> None:
        self.dialog.tabelle.item(zeile, 0).setText(name)
        self.dialog.tabelle.item(zeile, 1).setText(nummer)

    def test_drei_leere_zeilen_stehen_bereit(self):
        self.assertEqual(self.dialog.tabelle.rowCount(), 3)
        self.assertFalse(self.dialog.anlegenknopf.isEnabled())

    def test_der_ordnername_folgt_name_und_nummer(self):
        self._zeile(0, "Keller", "1.1")
        self.assertEqual(self.dialog.tabelle.item(0, 2).text(), "1.1 Keller")

    def test_eine_eigene_schreibweise_bleibt_stehen(self):
        """Was von Hand kommt, bleibt - wie bei den Adernfarben."""
        self._zeile(0, "Keller", "1.1")
        self.dialog.tabelle.item(0, 2).setText("Mein Ordner")
        self._zeile(0, "Keller neu", "1.1")
        self.assertEqual(self.dialog.tabelle.item(0, 2).text(), "Mein Ordner")

    def test_die_letzte_spalte_sagt_wohin(self):
        self._zeile(0, "Keller", "1.1")
        self.assertEqual(
            self.dialog.tabelle.item(0, 3).text(), "1.1 Keller/1.1 Keller.vtly"
        )

    def test_die_letzte_spalte_sagt_warum_nicht(self):
        self._zeile(0, "Keller")
        self._zeile(1, "keller")
        self.assertTrue(self.dialog.tabelle.item(1, 3).text())
        self.assertNotEqual(
            self.dialog.tabelle.item(0, 3).text(),
            self.dialog.tabelle.item(1, 3).text(),
        )

    def test_ohne_projektordner_laesst_sich_nichts_anlegen(self):
        self._zeile(0, "Keller")
        self.assertTrue(self.dialog.anlegenknopf.isEnabled())
        self.dialog.ordnerfeld.setText("")
        self.assertFalse(self.dialog.anlegenknopf.isEnabled())

    def test_die_summe_zaehlt_die_beilagen_einmal(self):
        quelle = pathlib.Path(tempfile.mkdtemp()) / "Checkliste.txt"
        quelle.write_text("haken", encoding="utf-8")
        self._zeile(0, "Keller")
        self._zeile(1, "Dach")
        self.dialog.beilage_anhaengen(Beilage(quelle, "Dokumentation"))
        self.dialog._vorschau_auffrischen()
        self.assertIn("2", self.dialog.summe.text())
        self.assertIn("1", self.dialog.summe.text())

    def test_eine_zeile_mehr_und_eine_weniger(self):
        self.dialog.zeile_anhaengen("Dach")
        self.assertEqual(self.dialog.tabelle.rowCount(), 4)
        self.dialog.tabelle.setCurrentCell(3, 0)
        self.dialog._zeile_entfernen()
        self.assertEqual(self.dialog.tabelle.rowCount(), 3)

    def test_eine_fehlende_beilage_wird_gesagt(self):
        weg = pathlib.Path(tempfile.mkdtemp()) / "nichts.txt"
        self.dialog.beilage_anhaengen(Beilage(weg, "Dokumentation"))
        self.dialog._vorschau_auffrischen()
        self.assertIn("nichts.txt", self.dialog.beilagenhinweis.text())

    def test_jedes_projekt_bekommt_seine_eigenen_sammlungen(self):
        """Zwei Projekte an einem Briefkopf waeren eine Falle."""
        eines = self.dialog.projekt_fuer(Angabe("Keller", "1.1"))
        anderes = self.dialog.projekt_fuer(Angabe("Dach", "1.2"))
        self.assertIsNot(eines.briefkopf, anderes.briefkopf)
        self.assertIsNot(eines.ausgeblendet, anderes.ausgeblendet)
        self.assertEqual(eines.verteiler.nummer, "1.1")

    def test_was_die_blattvorlage_nicht_fuehrt_ist_abgewaehlt(self):
        projekt = self.dialog.projekt_fuer(Angabe("Keller"))
        self.assertTrue(
            self.dialog.projektdaten.verborgene() <= projekt.ausgeblendet
        )

    def test_ausfuehren_legt_an_was_dasteht(self):
        quelle = pathlib.Path(tempfile.mkdtemp()) / "Checkliste.txt"
        quelle.write_text("haken", encoding="utf-8")
        self._zeile(0, "Keller", "1.1")
        self._zeile(1, "Dach", "1.2")
        self.dialog.beilage_anhaengen(Beilage(quelle, "Dokumentation"))
        bericht = self.dialog.ausfuehren()
        self.assertEqual(bericht.angelegt, 2)
        self.assertTrue((self.ordner / "1.1 Keller" / "1.1 Keller.vtly").is_file())
        # Einmal im Projektordner, nicht in jedem Verteilerordner.
        self.assertTrue((self.ordner / "Dokumentation" / "Checkliste.txt").is_file())
        self.assertFalse((self.ordner / "1.1 Keller" / "Dokumentation").exists())
        self.assertEqual(bericht.beigelegt, 1)

    def test_der_offene_verteiler_bleibt_unberuehrt(self):
        self.fenster._projekt_setzen(
            Projekt(verteiler=Verteiler.aus_geometrie(1, 1, 2, name="Offen")), None
        )
        self._zeile(0, "Keller")
        self.dialog.ausfuehren()
        self.assertEqual(self.fenster.projekt.verteiler.name, "Offen")
        self.assertFalse(self.fenster.veraendert)

    def test_gemerkt_werden_ordner_beilagen_und_haken(self):
        quelle = pathlib.Path(tempfile.mkdtemp()) / "Checkliste.txt"
        quelle.write_text("haken", encoding="utf-8")
        self.dialog.beilage_anhaengen(Beilage(quelle, "Dokumentation"))
        self.dialog.eigener_ordner_haken.setChecked(False)
        erweiterung.merken(self.fenster.einstellungen, self.dialog)
        self.assertEqual(
            erweiterung.projektordner(self.fenster.einstellungen), str(self.ordner)
        )
        self.assertEqual(
            erweiterung.beilagen(self.fenster.einstellungen),
            [Beilage(quelle, "Dokumentation")],
        )
        self.assertFalse(erweiterung.eigener_ordner(self.fenster.einstellungen))

    def test_der_bericht_steht_in_der_statuszeile(self):
        self._zeile(0, "Keller")
        erweiterung.melden(self.schnittstelle, self.dialog.ausfuehren())
        self.assertIn("1", self.fenster.statusBar().currentMessage())


if __name__ == "__main__":
    unittest.main()
