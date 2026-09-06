"""Tests zu den Bauskripten.

Gebaut wird hier nichts - PyInstaller braucht Windows, und das AppImage
lädt ein halbes Gigabyte. Geprüft wird, was sich ohne Bau prüfen lässt:
der zusammengesetzte Aufruf, die Versionsangaben für Windows und der
Selbstbericht des Programms.
"""

import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "werkzeuge"))

import exe  # noqa: E402

from verteilerly.version import VERSION  # noqa: E402


class TestExeAufruf(unittest.TestCase):
    """Eine einzelne .exe, ohne Installation."""

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.bau = pathlib.Path(self.ordner.name)
        self.befehl = exe.befehl_bauen(
            self.bau / "Verteilerly.ico", self.bau / "version.txt"
        )

    def test_eine_datei_ohne_konsole(self):
        self.assertIn("--onefile", self.befehl)
        self.assertIn("--windowed", self.befehl)

    def test_daten_wandern_mit_hinein(self):
        stelle = self.befehl.index("--add-data")
        quelle, ziel = self.befehl[stelle + 1].split(os.pathsep)
        self.assertTrue(pathlib.Path(quelle).is_dir())
        self.assertEqual(ziel, "daten")

    def test_symbol_und_versionsangaben(self):
        self.assertIn("--icon", self.befehl)
        self.assertIn("--version-file", self.befehl)

    def test_ergebnis_landet_in_der_auslieferung(self):
        stelle = self.befehl.index("--distpath")
        self.assertEqual(pathlib.Path(self.befehl[stelle + 1]).name, "auslieferung")

    def test_der_ballast_bleibt_draussen(self):
        for modul in ("PySide6.QtWebEngineCore", "PySide6.QtQml", "tkinter"):
            with self.subTest(modul=modul):
                self.assertIn(modul, self.befehl)
        self.assertNotIn("PySide6.QtWidgets", self.befehl)

    def test_gebaut_wird_das_startmodul(self):
        self.assertTrue(self.befehl[-1].endswith("__main__.py") or
                        any(t.endswith("__main__.py") for t in self.befehl))


class TestWindowsAngaben(unittest.TestCase):
    def test_versionsdatei_traegt_die_fassung(self):
        with tempfile.TemporaryDirectory() as ordner:
            datei = exe.versionsdatei_schreiben(pathlib.Path(ordner))
            inhalt = datei.read_text(encoding="utf-8")
        self.assertIn(VERSION, inhalt)
        self.assertIn("Verteilerly.exe", inhalt)
        self.assertIn("filevers=(2026, ", inhalt)

    def test_ohne_windows_wird_nicht_gebaut(self):
        """Ein Bau auf der falschen Plattform bricht mit Hinweis ab."""
        if sys.platform.startswith("win"):
            self.skipTest("läuft unter Windows")
        with self.assertRaises(SystemExit) as fehler:
            exe.voraussetzungen_pruefen(streng=True)
        self.assertIn("Windows", str(fehler.exception))

    def test_zeigen_geht_auf_jeder_plattform(self):
        exe.voraussetzungen_pruefen(streng=False)   # wirft nicht


class TestSelbstbericht(unittest.TestCase):
    """Der Probelauf des Bauskripts liest diesen Bericht."""

    def test_bericht_nennt_fassung_und_bestand(self):
        with tempfile.TemporaryDirectory() as ordner:
            ziel = pathlib.Path(ordner) / "bericht.txt"
            umgebung = dict(os.environ, QT_QPA_PLATFORM="offscreen")
            ergebnis = subprocess.run(
                [sys.executable, "-m", "verteilerly", "--selbsttest", str(ziel)],
                cwd=str(WURZEL), env=umgebung, capture_output=True, text=True,
            )
            self.assertEqual(ergebnis.returncode, 0, ergebnis.stderr)
            werte = dict(
                zeile.split("=", 1)
                for zeile in ziel.read_text(encoding="utf-8").splitlines()
                if "=" in zeile
            )
        self.assertEqual(werte["version"], VERSION)
        self.assertEqual(werte["ergebnis"], "ok")
        self.assertGreaterEqual(int(werte["vorlagen"]), 3)
        self.assertGreaterEqual(int(werte["blattvorlagen"]), 3)
        self.assertGreaterEqual(int(werte["kabeltypen"]), 3)


if __name__ == "__main__":
    unittest.main()
