"""Das Benutzerhandbuch als PDF - gesetzt aus der Dokumentation."""

# Erst das Paket: es legt Einstellungs- und Arbeitsordner der
# Testreihe um, bevor etwas aus verteilerly Pfade liest.
from . import TESTHEIM  # noqa: F401

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "werkzeuge"))

try:
    from PySide6.QtGui import QGuiApplication  # noqa: F401
except ImportError:  # pragma: no cover - ohne Qt wird nichts gesetzt
    QGuiApplication = None

import handbuch  # noqa: E402

from verteilerly import hilfe  # noqa: E402
from verteilerly.version import VERSION  # noqa: E402

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None


@unittest.skipIf(QGuiApplication is None or PdfReader is None, "Qt oder pypdf fehlt")
class TestHandbuch(unittest.TestCase):
    """Je Sprache ein PDF - mit Titelblatt, Verzeichnis und Fusszeilen."""

    @classmethod
    def setUpClass(cls):
        cls._ordner = tempfile.TemporaryDirectory()
        ordner = pathlib.Path(cls._ordner.name)
        # Einmal setzen, beide Sprachen pruefen: das Setzen kostet Zeit.
        cls.pfade = {
            sprache: handbuch.handbuch_schreiben(sprache, ordner)
            for sprache in sorted(handbuch.SPRACHEN)
        }
        cls.seiten = {
            sprache: [
                (blatt.extract_text() or "")
                for blatt in PdfReader(str(pfad)).pages
            ]
            for sprache, pfad in cls.pfade.items()
        }

    @classmethod
    def tearDownClass(cls):
        cls._ordner.cleanup()

    @staticmethod
    def _bereinigt(text: str) -> str:
        """Ohne Trennzeichen - die PDF-Auslese setzt Tabulatoren."""
        return " ".join(text.split())

    def test_je_sprache_eine_datei_mit_der_fassung_im_namen(self):
        for sprache, pfad in self.pfade.items():
            with self.subTest(sprache=sprache):
                self.assertTrue(pfad.is_file())
                self.assertIn(VERSION, pfad.name)
                self.assertGreater(pfad.stat().st_size, 50_000)

    def test_das_titelblatt_nennt_fassung_und_lizenz(self):
        for sprache, seiten in self.seiten.items():
            with self.subTest(sprache=sprache):
                erstes = self._bereinigt(seiten[0])
                self.assertIn("Verteilerly", erstes)
                self.assertIn(VERSION, erstes)
                self.assertIn("GPL-3.0-or-later", erstes)

    def test_jeder_abschnitt_steht_im_verzeichnis(self):
        """Das Verzeichnis zaehlt dieselben Abschnitte wie die Hilfe."""
        for sprache, seiten in self.seiten.items():
            with self.subTest(sprache=sprache):
                verzeichnis = self._bereinigt(seiten[1])
                for _marke, titel in hilfe.abschnitte(hilfe.dokumentation(sprache)):
                    self.assertIn(self._bereinigt(titel), verzeichnis)

    def test_die_seitenzahlen_des_verzeichnisses_steigen(self):
        """Sonst zeigte es irgendwohin - der haeufigste Fehler beim Setzen."""
        for sprache, seiten in self.seiten.items():
            with self.subTest(sprache=sprache):
                import re

                verzeichnis = self._bereinigt(seiten[1])
                seitenzahlen = []
                for _marke, titel in hilfe.abschnitte(hilfe.dokumentation(sprache)):
                    # Hinter jedem Titel steht seine Seite.
                    treffer = re.search(
                        re.escape(self._bereinigt(titel)) + r"\s+(\d+)", verzeichnis
                    )
                    self.assertIsNotNone(treffer, titel)
                    seitenzahlen.append(int(treffer.group(1)))
                self.assertEqual(seitenzahlen, sorted(seitenzahlen))
                self.assertGreaterEqual(seitenzahlen[0], 3)
                self.assertLessEqual(seitenzahlen[-1], len(seiten))

    def test_jede_seite_ausser_dem_titelblatt_traegt_ihre_zahl(self):
        for sprache, seiten in self.seiten.items():
            with self.subTest(sprache=sprache):
                worte = handbuch.SPRACHEN[sprache]
                for nummer, text in enumerate(seiten[1:], start=2):
                    erwartet = worte["seite"].format(nummer, len(seiten))
                    self.assertIn(erwartet, self._bereinigt(text))

    def test_der_text_der_hilfe_steht_darin(self):
        """Gesetzt wird die Dokumentation, nicht ein zweiter Text."""
        proben = {
            "de": ("Doppelader", "Rangierung", "Blattvorlage"),
            "en": ("pair", "jumper", "sheet template"),
        }
        for sprache, seiten in self.seiten.items():
            with self.subTest(sprache=sprache):
                ganz = self._bereinigt(" ".join(seiten))
                for wort in proben[sprache]:
                    self.assertIn(wort, ganz)

    def test_qt_bricht_selbst_in_seiten_um(self):
        """Darauf steht das Setzen: eine Seite ist ein Streifen."""
        hoehe = 100.0
        dok = handbuch._dokument("<p>" + "Wort " * 400 + "</p>", 200.0, hoehe)
        seiten = handbuch._seitenzahl(dok)
        self.assertGreater(seiten, 1)
        gesamt = dok.documentLayout().documentSize().height()
        # Jede Seite ist ein Streifen der Hoehe nach - und zusammen
        # decken sie den ganzen Text ab.
        self.assertGreaterEqual(seiten * hoehe, gesamt - hoehe)


if __name__ == "__main__":
    unittest.main()
