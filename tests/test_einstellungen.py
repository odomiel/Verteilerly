"""Tests zum gemerkten Briefkopf."""

import os
import pathlib
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    ANWENDUNG = QApplication.instance() or QApplication([])
except ImportError:                                   # pragma: no cover
    ANWENDUNG = None

from verteilerly import einstellungen as sp
from verteilerly.modell import Projekt, Verteiler


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestBriefkopfMerken(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.datei = pathlib.Path(self.ordner.name) / "Verteilerly.conf"
        self.einstellungen = QSettings(str(self.datei), QSettings.Format.IniFormat)

    def _projekt(self):
        projekt = Projekt(
            verteiler=Verteiler.aus_geometrie(1, 4, 10, name="Erster"),
            briefkopf={"firma": "Musterfirma", "kuerzel": "MI"},
            eigene_felder={"Standort": "Keller"},
        )
        projekt.sichtbarkeit_setzen("kuerzel", False)
        return projekt

    def test_die_felder_stehen_in_der_conf(self):
        sp.briefkopf_sichern(self.einstellungen, self._projekt())
        inhalt = self.datei.read_text(encoding="utf-8")
        self.assertIn("[briefkopf]", inhalt)
        self.assertIn("firma=Musterfirma", inhalt)
        self.assertIn("[eigene_felder]", inhalt)
        self.assertIn("felder_ausgeblendet=kuerzel", inhalt)

    def test_gelesen_wird_dasselbe(self):
        sp.briefkopf_sichern(self.einstellungen, self._projekt())
        briefkopf, eigene, ausgeblendet = sp.briefkopf_laden(self.einstellungen)
        self.assertEqual(briefkopf, {"firma": "Musterfirma", "kuerzel": "MI"})
        self.assertEqual(eigene, {"Standort": "Keller"})
        self.assertEqual(ausgeblendet, {"kuerzel"})

    def test_ein_neuer_verteiler_erbt_den_briefkopf(self):
        sp.briefkopf_sichern(self.einstellungen, self._projekt())
        neu = sp.briefkopf_uebernehmen(
            self.einstellungen, Projekt(verteiler=Verteiler.aus_geometrie(1, 2, 20))
        )
        self.assertEqual(neu.briefkopf["firma"], "Musterfirma")
        self.assertEqual(neu.eigene_felder["Standort"], "Keller")
        self.assertFalse(neu.sichtbar("kuerzel"))

    def test_die_vorgabe_ueberschreibt_keine_eingabe(self):
        sp.briefkopf_sichern(self.einstellungen, self._projekt())
        projekt = Projekt(briefkopf={"firma": "Andere Firma"})
        sp.briefkopf_uebernehmen(self.einstellungen, projekt)
        self.assertEqual(projekt.briefkopf["firma"], "Andere Firma")
        self.assertEqual(projekt.briefkopf["kuerzel"], "MI")

    def test_ohne_gemerkten_briefkopf_passiert_nichts(self):
        projekt = sp.briefkopf_uebernehmen(self.einstellungen, Projekt())
        self.assertEqual(projekt.briefkopf, {})
        self.assertEqual(projekt.ausgeblendet, set())

    def test_geloeschte_felder_verschwinden_auch_aus_der_conf(self):
        """Sonst kämen längst entfernte Felder beim nächsten Verteiler zurück."""
        sp.briefkopf_sichern(self.einstellungen, self._projekt())
        weniger = Projekt(briefkopf={"firma": "Musterfirma"})
        sp.briefkopf_sichern(self.einstellungen, weniger)
        briefkopf, eigene, _ = sp.briefkopf_laden(self.einstellungen)
        self.assertEqual(briefkopf, {"firma": "Musterfirma"})
        self.assertEqual(eigene, {})

    def test_feldnamen_mit_komma_und_leerzeichen(self):
        """QSettings trennt Listen mit Komma - der Name darf eins enthalten."""
        projekt = Projekt(eigene_felder={"Standort, Raum": "Keller"})
        projekt.sichtbarkeit_setzen("Standort, Raum", False)
        sp.briefkopf_sichern(self.einstellungen, projekt)
        _, eigene, ausgeblendet = sp.briefkopf_laden(self.einstellungen)
        self.assertEqual(eigene, {"Standort, Raum": "Keller"})
        self.assertEqual(ausgeblendet, {"Standort, Raum"})

    def test_hauptfenster_reicht_beides_durch(self):
        from verteilerly.gui.hauptfenster import Hauptfenster

        fenster = Hauptfenster()
        fenster._projekt_setzen(self._projekt(), None)
        fenster.briefkopf_merken()

        geerbt = fenster.neues_projekt(Verteiler.aus_geometrie(1, 2, 20, name="Zweiter"))
        self.assertEqual(geerbt.briefkopf["firma"], "Musterfirma")
        self.assertEqual(geerbt.verteiler.name, "Zweiter")


if __name__ == "__main__":
    unittest.main()
