"""Tests zur Erweiterung *Projekt*: mehrere Verteiler auf einmal anlegen.

Zwei Haelften: der **Plan** (``anlage.py``, ohne Qt) wird gegen einen
Temp-Ordner gerechnet - geschrieben wird dort erst, wenn der Test es
verlangt -, und der **Dialog** gegen ein echtes Hauptfenster, aber ohne
Dateidialog und ohne ``exec()``.
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
    SCHLUESSEL_ZIEL,
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


class TestPlanen(unittest.TestCase):
    """Gerechnet, nicht geschrieben."""

    def setUp(self):
        self.ziel = pathlib.Path(tempfile.mkdtemp(prefix="projekt-"))

    def test_je_zeile_ein_ordner_mit_der_datei_darin(self):
        plan = planen([Angabe("Keller", "1.1"), Angabe("Dach", "1.2")], self.ziel)
        self.assertEqual(len(plan), 2)
        self.assertTrue(all(x.geht for x in plan))
        self.assertEqual(plan[0].ordner, self.ziel / "1.1 Keller")
        self.assertEqual(plan[0].datei.name, "1.1 Keller.vtly")
        # Gerechnet heisst: auf der Platte steht noch nichts.
        self.assertEqual(list(self.ziel.iterdir()), [])

    def test_leere_zeilen_fallen_weg(self):
        plan = planen([Angabe(), Angabe("Keller"), Angabe("  ", " ")], self.ziel)
        self.assertEqual([x.angabe.name for x in plan], ["Keller"])

    def test_ohne_eigenen_ordner_liegen_alle_im_zielordner(self):
        plan = planen(
            [Angabe("Keller"), Angabe("Dach")], self.ziel, eigener_ordner=False
        )
        self.assertEqual({x.ordner for x in plan}, {self.ziel})
        self.assertEqual([x.datei.name for x in plan], ["Keller.vtly", "Dach.vtly"])

    def test_derselbe_name_zweimal_ist_ein_grund(self):
        plan = planen([Angabe("Keller"), Angabe("keller")], self.ziel)
        self.assertTrue(plan[0].geht)
        self.assertFalse(plan[1].geht)

    def test_eine_vorhandene_datei_bleibt_stehen(self):
        (self.ziel / "Keller").mkdir()
        (self.ziel / "Keller" / "Keller.vtly").write_text("{}", encoding="utf-8")
        plan = planen([Angabe("Keller")], self.ziel)
        self.assertFalse(plan[0].geht)

    def test_ein_name_ohne_brauchbare_zeichen_ist_ein_grund(self):
        plan = planen([Angabe("///")], self.ziel)
        self.assertFalse(plan[0].geht)

    def test_jeder_bekommt_die_beilagen(self):
        quelle = pathlib.Path(tempfile.mkdtemp()) / "Checkliste.txt"
        quelle.write_text("haken", encoding="utf-8")
        plan = planen(
            [Angabe("Keller"), Angabe("Dach")], self.ziel,
            [Beilage(quelle, "Dokumentation")],
        )
        for anlagenteil in plan:
            self.assertEqual(
                anlagenteil.dateien, ((quelle, "Dokumentation/Checkliste.txt"),)
            )
            self.assertEqual(anlagenteil.faecher, ("Dokumentation",))

    def test_in_einem_ordner_traegt_die_erste_zeile_die_beilagen(self):
        """Den Projektordner gibt es einmal - also die Beilagen auch."""
        quelle = pathlib.Path(tempfile.mkdtemp()) / "Checkliste.txt"
        quelle.write_text("haken", encoding="utf-8")
        plan = planen(
            [Angabe("Keller"), Angabe("Dach")], self.ziel,
            [Beilage(quelle, "")], eigener_ordner=False,
        )
        self.assertEqual(len(plan[0].dateien), 1)
        self.assertEqual(plan[1].dateien, ())

    def test_scheitert_die_erste_traegt_die_naechste_die_beilagen(self):
        quelle = pathlib.Path(tempfile.mkdtemp()) / "Checkliste.txt"
        quelle.write_text("haken", encoding="utf-8")
        (self.ziel / "Keller.vtly").write_text("{}", encoding="utf-8")
        plan = planen(
            [Angabe("Keller"), Angabe("Dach")], self.ziel,
            [Beilage(quelle, "")], eigener_ordner=False,
        )
        self.assertFalse(plan[0].geht)
        self.assertEqual(len(plan[1].dateien), 1)

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


class TestAnlegen(unittest.TestCase):
    """Jetzt wird geschrieben."""

    def setUp(self):
        self.ziel = pathlib.Path(tempfile.mkdtemp(prefix="projekt-"))
        self.muster = pathlib.Path(tempfile.mkdtemp()) / "Checkliste.txt"
        self.muster.write_text("haken", encoding="utf-8")

    def _plan(self, **mehr):
        return planen(
            [Angabe("Keller", "1.1"), Angabe("Dach", "1.2")], self.ziel,
            [Beilage(self.muster, "Dokumentation")], **mehr
        )

    def test_je_verteiler_ein_ordner_mit_datei_und_beilage(self):
        bericht = anlegen(self._plan(), _projekt_fuer)
        self.assertEqual(bericht.angelegt, 2)
        self.assertEqual(bericht.beigelegt, 2)
        self.assertEqual(bericht.gruende, [])
        for name in ("1.1 Keller", "1.2 Dach"):
            self.assertTrue((self.ziel / name / f"{name}.vtly").is_file())
            self.assertTrue(
                (self.ziel / name / "Dokumentation" / "Checkliste.txt").is_file()
            )

    def test_was_geschrieben_wurde_laesst_sich_lesen(self):
        from verteilerly import projektdatei

        anlegen(self._plan(), _projekt_fuer)
        projekt = projektdatei.laden(
            self.ziel / "1.1 Keller" / "1.1 Keller.vtly"
        )
        self.assertEqual(projekt.verteiler.name, "Keller")
        self.assertEqual(projekt.verteiler.nummer, "1.1")
        self.assertEqual(projekt.briefkopf["firma"], "Beliebig GmbH")

    def test_ein_zweiter_durchgang_ueberschreibt_nichts(self):
        anlegen(self._plan(), _projekt_fuer)
        bericht = anlegen(self._plan(), _projekt_fuer)
        self.assertEqual(bericht.angelegt, 0)
        self.assertEqual(len(bericht.gruende), 2)

    def test_eine_vorhandene_beilage_wird_uebergangen_nicht_ersetzt(self):
        ordner = self.ziel / "1.1 Keller" / "Dokumentation"
        ordner.mkdir(parents=True)
        (ordner / "Checkliste.txt").write_text("von Hand", encoding="utf-8")
        bericht = anlegen(self._plan(), _projekt_fuer)
        self.assertEqual(bericht.uebergangen, 1)
        self.assertEqual(
            (ordner / "Checkliste.txt").read_text(encoding="utf-8"), "von Hand"
        )

    def test_eine_zeile_mit_grund_wird_uebergangen_die_andere_nicht(self):
        plan = self._plan()
        plan[0].grund = "Probe"
        bericht = anlegen(plan, _projekt_fuer)
        self.assertEqual(bericht.angelegt, 1)
        self.assertEqual(bericht.gruende, ["1.1 Keller: Probe"])

    def test_ein_fehler_haelt_den_rest_nicht_auf(self):
        """Ein gesperrter Ordner soll nicht die anderen Verteiler kosten."""
        def launisch(angabe):
            if angabe.name == "Keller":
                raise OSError("kein Platz")
            return _projekt_fuer(angabe)

        bericht = anlegen(self._plan(), launisch)
        self.assertEqual(bericht.angelegt, 1)
        self.assertEqual(len(bericht.gruende), 1)
        self.assertTrue((self.ziel / "1.2 Dach" / "1.2 Dach.vtly").is_file())

    def test_ohne_eigenen_ordner_liegt_alles_nebeneinander(self):
        bericht = anlegen(self._plan(eigener_ordner=False), _projekt_fuer)
        self.assertEqual(bericht.angelegt, 2)
        self.assertEqual(bericht.beigelegt, 1)
        self.assertTrue((self.ziel / "1.1 Keller.vtly").is_file())
        self.assertTrue((self.ziel / "1.2 Dach.vtly").is_file())
        self.assertTrue((self.ziel / "Dokumentation" / "Checkliste.txt").is_file())


class TestDialog(unittest.TestCase):
    """Der Dialog - mit echtem Fenster, ohne Dateidialog und ohne exec()."""

    def setUp(self):
        from verteilerly.erweiterungen import Fund
        from verteilerly.erweiterungen.projekt.dialog import ProjektDialog
        from verteilerly.gui.erweiterungen import Schnittstelle
        from verteilerly.gui.hauptfenster import Hauptfenster

        self.fenster = Hauptfenster()
        bauteil_zurueckgeben(self, self.fenster)
        for schluessel in (SCHLUESSEL_ZIEL, SCHLUESSEL_BEILAGEN,
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
        self.ziel = pathlib.Path(tempfile.mkdtemp(prefix="projekt-"))
        self.dialog = ProjektDialog(self.schnittstelle, self.fenster)
        bauteil_zurueckgeben(self, self.dialog)
        self.dialog.ziel.setText(str(self.ziel))

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

    def test_ohne_zielordner_laesst_sich_nichts_anlegen(self):
        self._zeile(0, "Keller")
        self.assertTrue(self.dialog.anlegenknopf.isEnabled())
        self.dialog.ziel.setText("")
        self.assertFalse(self.dialog.anlegenknopf.isEnabled())

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
        self._zeile(0, "Keller", "1.1")
        bericht = self.dialog.ausfuehren()
        self.assertEqual(bericht.angelegt, 1)
        self.assertTrue((self.ziel / "1.1 Keller" / "1.1 Keller.vtly").is_file())

    def test_der_offene_verteiler_bleibt_unberuehrt(self):
        self.fenster._projekt_setzen(
            Projekt(verteiler=Verteiler.aus_geometrie(1, 1, 2, name="Offen")), None
        )
        self._zeile(0, "Keller")
        self.dialog.ausfuehren()
        self.assertEqual(self.fenster.projekt.verteiler.name, "Offen")
        self.assertFalse(self.fenster.veraendert)

    def test_gemerkt_werden_ziel_beilagen_und_haken(self):
        quelle = pathlib.Path(tempfile.mkdtemp()) / "Checkliste.txt"
        quelle.write_text("haken", encoding="utf-8")
        self.dialog.beilage_anhaengen(Beilage(quelle, "Dokumentation"))
        self.dialog.eigener_ordner_haken.setChecked(False)
        erweiterung.merken(self.fenster.einstellungen, self.dialog)
        self.assertEqual(
            erweiterung.zielordner(self.fenster.einstellungen), str(self.ziel)
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
