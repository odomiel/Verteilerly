"""Tests zum Bestand: welche Bausteine drinstecken."""

import unittest
from unittest import mock

from verteilerly import bestand


class TestAbhaengigkeiten(unittest.TestCase):
    def test_jeder_baustein_hat_fassung_und_lizenz(self):
        teile = bestand.abhaengigkeiten()
        self.assertGreaterEqual(len(teile), 6)
        for teil in teile:
            with self.subTest(baustein=teil.name):
                self.assertTrue(teil.fassung)
                self.assertIn(teil.lizenz, ("PSF", "LGPLv3", "BSD", "MIT"))

    def test_die_fassungen_kommen_aus_dem_laufenden_programm(self):
        """Nicht aus einer Liste - sonst stimmt sie eines Tages nicht mehr."""
        import sys

        import yaml
        from PySide6 import QtCore

        nach_name = {teil.name: teil.fassung for teil in bestand.abhaengigkeiten()}
        self.assertEqual(nach_name["Python"], sys.version.split()[0])
        self.assertEqual(nach_name["Qt"], QtCore.qVersion())
        self.assertEqual(nach_name["PyYAML"], yaml.__version__)

    def test_ein_fehlender_baustein_bricht_nicht_ab(self):
        """Der Bericht soll sagen, was fehlt, statt daran zu scheitern."""
        with mock.patch("builtins.__import__", side_effect=ImportError):
            self.assertEqual(bestand._fassung("gibtesnicht"), bestand.FEHLT)
        fehlend = bestand.Baustein("X", bestand.FEHLT, "MIT")
        self.assertFalse(fehlend.vorhanden)

    def test_umgebung_nennt_die_orte(self):
        namen = [name for name, _ in bestand.umgebung()]
        self.assertEqual(namen, ["System", "Gepackt", "Arbeitsordner", "Einstellungen"])
        werte = dict(bestand.umgebung())
        self.assertIn("Verteilerly.conf", werte["Einstellungen"])


if __name__ == "__main__":
    unittest.main()
