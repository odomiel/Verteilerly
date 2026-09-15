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
                self.assertIn(
                    teil.lizenz,
                    ("GPL-3.0-or-later", "PSF", "LGPLv3", "BSD", "MIT"),
                )

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
        self.assertEqual(
            namen,
            ["System", "Gepackt", "Arbeitsordner", "Einstellungen", "Lizenzen"],
        )
        werte = dict(bestand.umgebung())
        self.assertIn("Verteilerly.conf", werte["Einstellungen"])


class TestLizenz(unittest.TestCase):
    """Verteilerly ist freie Software und sagt es auch."""

    def test_das_programm_steht_obenan(self):
        erster = bestand.abhaengigkeiten()[0]
        self.assertEqual(erster.name, "Verteilerly")
        self.assertEqual(erster.lizenz, "GPL-3.0-or-later")

    def test_die_lizenztexte_liegen_bei(self):
        ordner = bestand.lizenzordner()
        self.assertIsNotNone(ordner, "Der Ordner lizenzen/ fehlt")
        vorhanden = {datei.name for datei in ordner.iterdir()}
        for name in ("LGPL-3.0.txt", "QUELLEN.txt"):
            with self.subTest(datei=name):
                self.assertIn(name, vorhanden)
        # Der GPL-Text heißt im Quellbaum LICENSE und liegt neben dem
        # Ordner; ausgelegt und im Abbild heißt er GPL-3.0.txt.
        self.assertTrue(
            "GPL-3.0.txt" in vorhanden or (ordner.parent / "LICENSE").is_file()
        )

    def test_die_lizenz_des_programms_liegt_im_wurzelverzeichnis(self):
        import pathlib

        lizenz = pathlib.Path(__file__).resolve().parent.parent / "LICENSE"
        text = lizenz.read_text(encoding="utf-8")
        self.assertIn("GNU GENERAL PUBLIC LICENSE", text)
        self.assertIn("Version 3, 29 June 2007", text)

    def test_quellen_nennt_jeden_bestandteil_mit_lizenz(self):
        """Wer weitergibt, muss sagen können, woher der Quelltext kommt."""
        ordner = bestand.lizenzordner()
        text = (ordner / "QUELLEN.txt").read_text(encoding="utf-8")
        for wort in ("GPL-3.0-or-later", "LGPL-3.0", "Qt", "PySide6", "Python",
                     "ReportLab", "openpyxl", "PyYAML", "Pillow", "AppImage"):
            with self.subTest(wort=wort):
                self.assertIn(wort, text)

    def test_der_quellbaum_traegt_alle_lizenztexte(self):
        """Was ins Abbild und in die .exe wandert, steht auch hier.

        Geprueft am Quellbaum, nicht an der ausgelegten Kopie im
        Arbeitsordner - die hinkt nach, bis das Programm einmal lief.
        """
        import pathlib

        ordner = pathlib.Path(__file__).resolve().parent.parent / "lizenzen"
        for name in ("LGPL-3.0.txt", "LGPL-2.1.txt", "ICU.txt", "zstd.txt",
                     "GCC-Laufzeitausnahme-3.1.txt", "Qt-Fremdbestandteile.txt",
                     "Python-Fremdbestandteile.txt", "QUELLEN.txt"):
            with self.subTest(datei=name):
                self.assertTrue((ordner / name).is_file())
        quellen = (ordner / "QUELLEN.txt").read_text(encoding="utf-8")
        for wort in ("ICU", "GLib", "LGPL-2.1", "zstd", "libatomic",
                     "Qt-Fremdbestandteile.txt", "Python-Fremdbestandteile.txt",
                     "charset-normalizer", "Independent JPEG Group",
                     "FreeType Project", "PyInstaller", "Visual C++"):
            with self.subTest(wort=wort):
                self.assertIn(wort, quellen)

    def test_das_paket_nennt_seine_lizenz(self):
        import verteilerly

        self.assertEqual(verteilerly.LIZENZ, "GPL-3.0-or-later")
        self.assertIn("GNU General Public License", verteilerly.__doc__)


if __name__ == "__main__":
    unittest.main()
