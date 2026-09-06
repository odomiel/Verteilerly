"""Tests zu den Bauskripten.

Gebaut wird hier nichts - PyInstaller packt den Python, der es aufruft,
und braucht für die .exe Windows. Prüfbar ist trotzdem das Rezept: die
Spec wird mit Attrappen ausgeführt und dann nachgesehen, was bei
PyInstaller angekommen wäre.
"""

import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "werkzeuge"))

from verteilerly.version import VERSION  # noqa: E402


def spec_ausfuehren() -> dict:
    """Führt Verteilerly.spec mit Attrappen aus und fängt die Aufrufe ab."""
    aufrufe: dict = {}

    def analysis(skripte, **kw):
        aufrufe["analysis"] = {"skripte": skripte, **kw}
        return type("A", (), {"pure": [], "zipped_data": [], "scripts": [],
                              "binaries": [], "datas": []})()

    def pyz(*args, **kw):
        return object()

    def exe(*args, **kw):
        aufrufe["exe"] = kw
        return object()

    quelle = (WURZEL / "Verteilerly.spec").read_text(encoding="utf-8")
    umgebung = {
        "Analysis": analysis, "PYZ": pyz, "EXE": exe,
        "SPECPATH": str(WURZEL), "__file__": str(WURZEL / "Verteilerly.spec"),
    }
    exec(compile(quelle, "Verteilerly.spec", "exec"), umgebung)   # noqa: S102
    aufrufe["namensraum"] = umgebung
    return aufrufe


class TestSpec(unittest.TestCase):
    """Eine einzelne .exe, ohne Installation."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.aufrufe = spec_ausfuehren()
        except ImportError as fehler:      # PyInstaller nicht vorhanden
            raise unittest.SkipTest(str(fehler)) from None

    def test_version_kommt_aus_der_versionsdatei(self):
        """Die Spec liest sie selbst - ein direkter Aufruf benennt gleich."""
        self.assertEqual(self.aufrufe["namensraum"]["VERSION"], VERSION)

    def test_dateiname_traegt_die_version(self):
        self.assertEqual(self.aufrufe["exe"]["name"], f"Verteilerly_{VERSION}")

    def test_kein_konsolenfenster(self):
        self.assertFalse(self.aufrufe["exe"]["console"])

    def test_symbol_und_versionsangaben(self):
        self.assertTrue(str(self.aufrufe["exe"]["icon"]).endswith("Verteilerly.ico"))
        self.assertTrue(pathlib.Path(self.aufrufe["exe"]["icon"]).is_file())

    def test_gebaut_wird_das_startmodul(self):
        self.assertEqual(
            self.aufrufe["analysis"]["skripte"], ["verteilerly/__main__.py"]
        )

    def test_die_grundausstattung_wandert_mit(self):
        """Vorlagen, Blattvorlagen und Kabeltypen stecken in der Datei."""
        ziele = {ziel for _, ziel in self.aufrufe["analysis"]["datas"]}
        for ordner in ("vorlagen", "kabeltypen", "blattvorlagen"):
            with self.subTest(ordner=ordner):
                self.assertIn(os.path.join("daten", ordner), ziele)
        dateien = [
            pathlib.Path(quelle).name
            for quelle, _ in self.aufrufe["analysis"]["datas"]
        ]
        self.assertIn("40da-4x10.yaml", dateien)
        self.assertIn("standard.yaml", dateien)

    def test_das_eigene_paket_wird_vollstaendig_eingesammelt(self):
        versteckt = self.aufrufe["analysis"]["hiddenimports"]
        for modul in ("verteilerly.gui.dialoge", "verteilerly.ausgabe.pdf"):
            with self.subTest(modul=modul):
                self.assertIn(modul, versteckt)

    def test_der_ballast_bleibt_draussen(self):
        heraus = self.aufrufe["analysis"]["excludes"]
        for modul in ("PySide6.QtWebEngineCore", "PySide6.QtQml", "tkinter"):
            with self.subTest(modul=modul):
                self.assertIn(modul, heraus)
        self.assertNotIn("PySide6.QtWidgets", heraus)

    def test_pillow_bleibt_drin(self):
        """Beim Windows-Build gefunden: ohne Pillow startet die .exe nicht.

        reportlab.lib.colors zieht über reportlab.lib.utils PIL nach - wird
        es ausgeschlossen, bricht der erste Import des Hauptfensters mit
        ModuleNotFoundError ab.
        """
        self.assertNotIn("PIL", self.aufrufe["analysis"]["excludes"])
        self.assertNotIn("Pillow", self.aufrufe["analysis"]["excludes"])

    def test_reportlab_zieht_pillow_wirklich_nach(self):
        """Die Begründung für den Test darüber - nicht nur behauptet."""
        import subprocess

        ergebnis = subprocess.run(
            [sys.executable, "-c",
             "import sys; from reportlab.lib.colors import HexColor;"
             "print(any(m.startswith('PIL') for m in sys.modules))"],
            capture_output=True, text=True, cwd=str(WURZEL),
        )
        self.assertEqual(ergebnis.stdout.strip(), "True", ergebnis.stderr)


class TestPowershellSkript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (WURZEL / "build_windows.ps1").read_text(encoding="utf-8")

    def test_baut_ueber_die_spec(self):
        self.assertIn("PyInstaller --noconfirm", self.text)
        self.assertIn("Verteilerly.spec", self.text)

    def test_prueft_das_ergebnis(self):
        self.assertIn("if (-not (Test-Path $Exe))", self.text)
        self.assertIn("auslieferung\\Verteilerly_$Version.exe", self.text)

    def test_kennt_den_versionsschalter(self):
        self.assertIn("param([switch]$Bump", self.text)
        self.assertIn("release.py --setzen", self.text)

    def test_bricht_bei_fehlern_ab(self):
        self.assertIn('$ErrorActionPreference = "Stop"', self.text)

    def test_probelauf_liest_den_selbstbericht(self):
        self.assertIn("--selbsttest", self.text)
        self.assertIn("ergebnis=ok", self.text)


class TestWindowsangaben(unittest.TestCase):
    def test_versionsdatei_traegt_die_fassung(self):
        import windowsangaben

        with tempfile.TemporaryDirectory() as ordner:
            datei = windowsangaben.schreiben(pathlib.Path(ordner) / "version.txt")
            inhalt = datei.read_text(encoding="utf-8")
        self.assertIn(f"'FileVersion', '{VERSION}'", inhalt)
        self.assertIn(f"Verteilerly_{VERSION}.exe", inhalt)
        self.assertRegex(inhalt, r"filevers=\(2026, \d+, \d+, \d+\)")


class TestSelbstbericht(unittest.TestCase):
    """Den liest der Probelauf des Bauskripts."""

    def test_startmodul_nutzt_absolute_importe(self):
        """Beim Windows-Build gefunden: relative Importe tragen im Bundle nicht.

        PyInstaller startet __main__.py als Skript, nicht als Teil des
        Pakets - „from .pfade import …“ scheitert dann.
        """
        quelle = (WURZEL / "verteilerly" / "__main__.py").read_text(encoding="utf-8")
        self.assertNotIn("from .", quelle)
        self.assertIn("from verteilerly import pfade", quelle)

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


class TestSymbol(unittest.TestCase):
    def test_symboldatei_liegt_bei(self):
        """Die Spec nimmt sie nur, wenn sie da ist."""
        self.assertTrue((WURZEL / "assets" / "Verteilerly.ico").is_file())


if __name__ == "__main__":
    unittest.main()
