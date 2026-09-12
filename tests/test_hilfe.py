"""Die Dokumentation im Programm.

Sie muss mitkommen, sich lesen lassen und zu den Menues passen - eine
Dokumentation, die einen Eintrag nicht kennt, ist schlimmer als keine.
"""

from __future__ import annotations

import os
import re
import unittest

from verteilerly import hilfe

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
except ImportError:                              # pragma: no cover
    QApplication = None

ANWENDUNG = QApplication.instance() or QApplication([]) if QApplication else None


def _klartext(html: str) -> str:
    ohne = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", ohne.replace("&nbsp;", " "))


class TestDokumentation(unittest.TestCase):
    def setUp(self):
        self.html = hilfe.dokumentation()

    def test_die_datei_liegt_bei(self):
        datei = hilfe.dokumentationsdatei()
        self.assertIsNotNone(datei)
        self.assertTrue(datei.is_file())

    def test_sie_hat_hand_und_fuss(self):
        self.assertIn("<h1>", self.html)
        self.assertGreater(len(self.html), 5000)

    def test_verzeichnis_aus_den_ueberschriften(self):
        abschnitte = hilfe.abschnitte(self.html)
        self.assertGreaterEqual(len(abschnitte), 10)
        for marke, titel in abschnitte:
            with self.subTest(marke=marke):
                self.assertTrue(marke)
                self.assertTrue(titel)
                # Jede Sprungmarke muss es im Text auch geben.
                self.assertIn(f'name="{marke}"', self.html)

    def test_jeder_bereich_kommt_vor(self):
        text = _klartext(self.html)
        for wort in (
            "Doppelader", "Rangierung", "Kabel", "Blattvorlage", "Projektdaten",
            "Verteilerbelegung", "Deckblatt", "Excel", "Arbeitsordner",
        ):
            with self.subTest(wort=wort):
                self.assertIn(wort, text)

    def test_ohne_datei_kommt_ein_hinweis_statt_eines_absturzes(self):
        from unittest.mock import patch

        with patch.object(hilfe, "dokumentationsdatei", return_value=None):
            self.assertIn("nicht gefunden", hilfe.dokumentation())


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestGegenDieMenues(unittest.TestCase):
    """Was im Menü steht, muss in der Dokumentation stehen."""

    def setUp(self):
        from verteilerly.gui.hauptfenster import Hauptfenster

        self.fenster = Hauptfenster()
        self.addCleanup(self.fenster.close)
        self.text = _klartext(hilfe.dokumentation())

    def _eintraege(self):
        """Jeden Eintrag der Menueleiste, auch aus den Untermenues."""
        gefunden: list[str] = []

        def sammeln(menue):
            for handlung in menue.actions():
                if handlung.isSeparator():
                    continue
                if handlung.menu() is not None:
                    gefunden.append(handlung.text())
                    sammeln(handlung.menu())
                    continue
                gefunden.append(handlung.text())

        for handlung in self.fenster.menuBar().actions():
            gefunden.append(handlung.text())
            if handlung.menu() is not None:
                sammeln(handlung.menu())
        sauber = [
            name.replace("&", "").replace("…", "").strip() for name in gefunden
        ]
        return sorted({name for name in sauber if name})

    def test_jeder_menueeintrag_steht_im_text(self):
        fehlend = [name for name in self._eintraege() if name not in self.text]
        self.assertEqual(fehlend, [])

    def test_kein_kuerzel_ist_doppelt_vergeben(self):
        """Zwei Einträge auf derselben Taste heben sich gegenseitig auf."""
        from PySide6.QtGui import QAction

        belegt: dict[str, str] = {}
        doppelt = []
        for handlung in self.fenster.findChildren(QAction):
            kuerzel = handlung.shortcut().toString()
            if not kuerzel:
                continue
            if kuerzel in belegt:
                doppelt.append(f"{kuerzel}: {belegt[kuerzel]} / {handlung.text()}")
            belegt[kuerzel] = handlung.text()
        self.assertEqual(doppelt, [])


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestDokumentationDialog(unittest.TestCase):
    """Hilfe ▸ Dokumentation."""

    def setUp(self):
        from verteilerly.gui.dialoge import DokumentationDialog

        self.dialog = DokumentationDialog()
        self.addCleanup(self.dialog.close)

    def test_der_text_steht_darin(self):
        self.assertIn("Verteilerly", self.dialog.text.toPlainText())
        self.assertGreater(len(self.dialog.text.toPlainText()), 3000)

    def test_das_verzeichnis_fuehrt_jeden_abschnitt(self):
        self.assertEqual(self.dialog.verzeichnis.count(), len(hilfe.abschnitte()))

    def test_ein_eintrag_springt_an_seine_marke(self):
        from PySide6.QtCore import Qt

        eintrag = self.dialog.verzeichnis.item(3)
        self.assertTrue(eintrag.data(Qt.ItemDataRole.UserRole))
        self.dialog.verzeichnis.setCurrentItem(eintrag)     # darf nicht scheitern

    def test_die_seite_bringt_keine_eigenen_farben_mit(self):
        """Sonst wäre sie im dunklen Erscheinungsbild unlesbar."""
        self.assertNotIn("color:", hilfe.dokumentation())
        self.assertNotIn("bgcolor", hilfe.dokumentation())


if __name__ == "__main__":
    unittest.main()
