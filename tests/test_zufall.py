"""Tests zur Erweiterung *Zufallsverteiler*.

Das Wuerfeln (``fuellung.py``, ohne Qt) laeuft mit festem Startwert und
wird gegen die Regeln des Modells gehalten: was dort entsteht, muss die
Projektdatei beim Lesen wieder durchlassen. Der Dialog und der Weg ins
Fenster laufen gegen ein echtes Hauptfenster, ohne ``exec()``.
"""

from __future__ import annotations

# Erst das Paket: es legt Einstellungs- und Arbeitsordner der
# Testreihe um, bevor etwas aus verteilerly Pfade liest.
from . import TESTHEIM  # noqa: F401

import os
import pathlib
import random
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

ANWENDUNG = QApplication.instance() or QApplication([])

from verteilerly import projektdatei  # noqa: E402
from verteilerly.erweiterungen.zufall import (  # noqa: E402
    SCHLUESSEL_VORLAGE,
    erweiterung,
)
from verteilerly.erweiterungen.zufall.fuellung import (  # noqa: E402
    fuellen,
    zufallsprojekt,
)
from verteilerly.farbcodes import Kabeltypen  # noqa: E402
from verteilerly.modell import RANGIERVORLAGEN, Verteiler  # noqa: E402

from . import bauteil_zurueckgeben, einstellung_bewahren  # noqa: E402

WURZEL = pathlib.Path(__file__).resolve().parent.parent
KABELTYPEN = Kabeltypen.laden(WURZEL / "daten" / "kabeltypen")


def _verteiler(bauplan=((4, 10),) * 2) -> Verteiler:
    return Verteiler.aus_buchten(list(bauplan), "", "")


class TestFuellung(unittest.TestCase):
    """Was gewuerfelt wird, haelt die Regeln des Modells ein."""

    def setUp(self):
        self.projekt = zufallsprojekt(_verteiler(), KABELTYPEN, random.Random(7))
        self.verteiler = self.projekt.verteiler

    def test_derselbe_startwert_gibt_denselben_verteiler(self):
        zweiter = zufallsprojekt(_verteiler(), KABELTYPEN, random.Random(7))
        # Das Datum ist heute in beiden - der Rest kommt aus dem Zufall.
        self.assertEqual(
            projektdatei.als_dict(zweiter), projektdatei.als_dict(self.projekt)
        )

    def test_es_liegen_kabel_mit_farben_und_bezeichnungen(self):
        self.assertTrue(self.verteiler.kabel)
        for kabel in self.verteiler.kabel:
            self.assertTrue(kabel.beschriftung)
            self.assertIn(kabel.kabeltyp, KABELTYPEN)
            for _, leiste, da in kabel.positionen():
                ader = self.verteiler.leiste(leiste).stift(da).a
                self.assertTrue(ader.farbe)
                self.assertTrue(ader.bezeichnung)

    def test_rangiert_wird_quer_und_seitengleich(self):
        self.assertTrue(self.verteiler.rangierungen)
        for rangierung in self.verteiler.rangierungen:
            self.assertNotEqual(rangierung.von.leiste, rangierung.nach.leiste)
            self.assertEqual(rangierung.von.seite, rangierung.nach.seite)

    def test_vermerke_kommen_aus_den_vorlagen(self):
        """Ein freier Text im Rangierfeld waere ein Fehler beim Bestaetigen."""
        for leiste in self.verteiler.alle_leisten:
            for stift in leiste.stifte:
                for ader in (stift.a, stift.b):
                    if ader.vermerk:
                        self.assertIn(ader.vermerk, RANGIERVORLAGEN)

    def test_die_projektdatei_liest_es_wieder_ein(self):
        """Ihre Pruefung beim Lesen ist der Massstab fuer Widersprueche."""
        for startwert in range(30):
            projekt = zufallsprojekt(
                _verteiler(((10, 25), (3, 100))), KABELTYPEN,
                random.Random(startwert),
            )
            daten = projektdatei.als_dict(projekt)
            wieder = projektdatei.aus_dict(daten)
            self.assertEqual(projektdatei.als_dict(wieder), daten)

    def test_projektdaten_und_name_sind_gesetzt(self):
        self.assertTrue(self.verteiler.name)
        self.assertTrue(self.verteiler.nummer)
        for feld in ("firma", "kunde", "erstellt_am"):
            self.assertTrue(self.projekt.briefkopf.get(feld), feld)

    def test_ohne_kabeltypen_bleiben_die_farben_leer(self):
        verteiler = _verteiler()
        stand = fuellen(verteiler, None, random.Random(3))
        self.assertGreater(stand.kabel, 0)
        self.assertTrue(all(k.kabeltyp is None for k in verteiler.kabel))

    def test_eine_einzelne_leiste_kommt_ohne_rangierung_aus(self):
        verteiler = _verteiler(((1, 10),))
        stand = fuellen(verteiler, KABELTYPEN, random.Random(1))
        self.assertEqual(stand.rangierungen, 0)
        self.assertEqual(verteiler.rangierungen, [])


class TestImFenster(unittest.TestCase):
    """Menueeintrag, Dialog und der Weg des Projekts ins Fenster."""

    def setUp(self):
        from verteilerly.erweiterungen import Fund
        from verteilerly.gui.erweiterungen import Schnittstelle
        from verteilerly.gui.hauptfenster import Hauptfenster

        self.fenster = Hauptfenster()
        bauteil_zurueckgeben(self, self.fenster)
        einstellung_bewahren(self, self.fenster.einstellungen, SCHLUESSEL_VORLAGE)
        menue = next(
            a.menu() for a in self.fenster.menuBar().actions()
            if a.text().replace("&", "") == "Erweiterungen"
        )
        self.programm = Schnittstelle(
            self.fenster, menue, self.fenster._erweiterungstrenner,
            Fund("zufall", "Zufallsverteiler"),
        )
        self.kennung = self.fenster.vorlagen.alle[-1].id

    def test_ein_neuer_ungespeicherter_verteiler_steht_im_fenster(self):
        self.assertTrue(
            erweiterung.anlegen(self.programm, self.kennung, random.Random(5))
        )
        projekt = self.fenster.projekt
        self.assertIsNotNone(projekt)
        self.assertIsNone(self.fenster.pfad)
        vorlage = self.fenster.vorlagen.holen(self.kennung)
        self.assertEqual(projekt.verteiler.da_gesamt, vorlage.da_gesamt)
        self.assertTrue(projekt.verteiler.kabel)
        self.assertIn("Zufallsverteiler", self.fenster.statusBar().currentMessage())

    def test_abgebrochen_bleibt_der_offene_verteiler(self):
        erweiterung.anlegen(self.programm, self.kennung, random.Random(5))
        vorher = self.fenster.projekt
        with mock.patch.object(self.fenster, "_darf_verwerfen", return_value=False):
            self.assertFalse(
                erweiterung.anlegen(self.programm, self.kennung, random.Random(6))
            )
        self.assertIs(self.fenster.projekt, vorher)

    def test_der_dialog_waehlt_die_gemerkte_vorlage_vor(self):
        from verteilerly.erweiterungen.zufall.dialog import ZufallsDialog

        dialog = ZufallsDialog(self.fenster.vorlagen, self.kennung, self.fenster)
        bauteil_zurueckgeben(self, dialog)
        self.assertEqual(dialog.vorlage(), self.kennung)

    def test_ohne_gemerkte_steht_die_standardvorlage_da(self):
        from verteilerly.erweiterungen.zufall.dialog import ZufallsDialog

        dialog = ZufallsDialog(self.fenster.vorlagen, "", self.fenster)
        bauteil_zurueckgeben(self, dialog)
        standard = [v.id for v in self.fenster.vorlagen.alle if v.standard]
        erwartet = standard[0] if standard else self.fenster.vorlagen.alle[0].id
        self.assertEqual(dialog.vorlage(), erwartet)

    def test_bestaetigt_wird_die_wahl_gemerkt(self):
        from verteilerly.erweiterungen.zufall import dialog as dialogmodul

        with mock.patch.object(
            dialogmodul.ZufallsDialog, "exec",
            return_value=dialogmodul.ZufallsDialog.DialogCode.Accepted,
        ), mock.patch.object(
            dialogmodul.ZufallsDialog, "vorlage", return_value=self.kennung
        ):
            erweiterung.oeffnen(self.programm)
        self.assertEqual(
            self.fenster.einstellungen.value(SCHLUESSEL_VORLAGE), self.kennung
        )
        self.assertIsNotNone(self.fenster.projekt)


if __name__ == "__main__":
    unittest.main()
