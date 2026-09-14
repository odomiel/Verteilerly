"""Die Dokumentation im Programm.

Sie muss mitkommen, sich lesen lassen und zu den Menues passen - eine
Dokumentation, die einen Eintrag nicht kennt, ist schlimmer als keine.
"""

from __future__ import annotations

import os
import re
import unittest
from unittest import mock

from verteilerly import hilfe

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QApplication
except ImportError:                              # pragma: no cover
    QApplication = None

ANWENDUNG = QApplication.instance() or QApplication([]) if QApplication else None


def _sauber(text: str) -> str:
    """Ein Menüeintrag ohne Merktaste und Auslassungspunkte."""
    return text.replace("&", "").replace("…", "").strip()


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

    def test_die_lizenz_steht_ohne_oder_spaeter_da(self):
        """Im Programm steht die Fassung, nicht die Wahlmöglichkeit."""
        text = _klartext(self.html)
        self.assertIn("GNU GPL, Version 3", text)
        stelle = text.index("GNU GPL")
        self.assertNotIn("oder später", text[stelle:stelle + 120])

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

    def test_die_kuerzeltabelle_stimmt_mit_den_menues_ueberein(self):
        """Ein gedrucktes Kürzel, das nichts auslöst, ist schlimmer als keines."""
        import re

        roh = hilfe.dokumentation()
        tabelle = re.search(r"<tr><th>Menü</th>.*?</table>", roh, re.S)
        self.assertIsNotNone(tabelle, "Die Tabelle der Menüeinträge fehlt")

        gedruckt = {}
        for zeile in re.findall(r"<tr>(.*?)</tr>", tabelle.group(0), re.S):
            zellen = [
                _sauber(re.sub(r"<[^>]+>", "", z))
                for z in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", zeile, re.S)
            ]
            if len(zellen) >= 2 and zellen[0] != "Menü":
                gedruckt[zellen[-2]] = zellen[-1]

        abweichung = []
        for name, kuerzel in self._kuerzel().items():
            soll = kuerzel.replace("Ctrl", "Strg").replace("Shift", "Umschalt")
            ist = gedruckt.get(name)
            if ist is None or ist != soll:
                abweichung.append(f"{name}: Programm {soll!r}, Doku {ist!r}")
        self.assertEqual(abweichung, [])

    def _kuerzel(self) -> dict:
        """Jeder Menüeintrag mit seinem Tastenkürzel."""
        gefunden: dict[str, str] = {}

        def sammeln(menue):
            for handlung in menue.actions():
                if handlung.isSeparator():
                    continue
                if handlung.menu() is not None:
                    sammeln(handlung.menu())
                    continue
                # Die Schreibweisen heißen wie ihr Beispiel und stehen
                # nicht als Menüeintrag in der Tabelle.
                if handlung.actionGroup() is not None:
                    continue
                gefunden[_sauber(handlung.text())] = handlung.shortcut().toString()

        for handlung in self.fenster.menuBar().actions():
            if handlung.menu() is not None:
                sammeln(handlung.menu())
        return gefunden

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
class TestEnglischeDokumentation(unittest.TestCase):
    """Dieselbe Seite auf Englisch, gegen dieselben Menüs."""

    def setUp(self):
        from verteilerly import sprachen
        from verteilerly.gui.hauptfenster import Hauptfenster

        self.sprachen = sprachen
        self.addCleanup(sprachen.sprache_setzen, sprachen.VORGABE)
        sprachen.sprache_setzen("en")
        self.fenster = Hauptfenster()
        self.addCleanup(self.fenster.close)
        self.roh = hilfe.dokumentation()
        self.text = _klartext(self.roh)

    def test_die_englische_datei_wird_gewaehlt(self):
        datei = hilfe.dokumentationsdatei()
        self.assertEqual(datei.name, "dokumentation_en.html")

    def test_ohne_englische_datei_bleibt_es_bei_der_deutschen(self):
        """Eine halb übersetzte Hilfe wäre schlimmer als eine ganz deutsche."""
        with mock.patch.object(hilfe, "_dateinamen", return_value=["dokumentation.html"]):
            self.assertEqual(hilfe.dokumentationsdatei().name, "dokumentation.html")

    def test_dieselben_abschnitte_wie_auf_deutsch(self):
        marken_en = [marke for marke, _ in hilfe.abschnitte(self.roh)]
        marken_de = [marke for marke, _ in hilfe.abschnitte(hilfe.dokumentation("de"))]
        self.assertEqual(marken_en, marken_de)

    def test_jeder_englische_menueeintrag_steht_im_text(self):
        gefunden: list[str] = []

        def sammeln(menue):
            for handlung in menue.actions():
                if handlung.isSeparator():
                    continue
                gefunden.append(handlung.text())
                if handlung.menu() is not None:
                    sammeln(handlung.menu())

        for handlung in self.fenster.menuBar().actions():
            gefunden.append(handlung.text())
            if handlung.menu() is not None:
                sammeln(handlung.menu())
        eintraege = sorted({_sauber(name) for name in gefunden if _sauber(name)})
        fehlend = [name for name in eintraege if name not in self.text]
        self.assertEqual(fehlend, [])

    def test_die_kuerzeltabelle_stimmt_mit_den_menues_ueberein(self):
        tabelle = re.search(r"<tr><th>Menu</th>.*?</table>", self.roh, re.S)
        self.assertIsNotNone(tabelle, "Die Tabelle der Menüeinträge fehlt")
        gedruckt = {}
        for zeile in re.findall(r"<tr>(.*?)</tr>", tabelle.group(0), re.S):
            zellen = [
                _sauber(re.sub(r"<[^>]+>", "", z))
                for z in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", zeile, re.S)
            ]
            if len(zellen) >= 2 and zellen[0] != "Menu":
                gedruckt[zellen[-2]] = zellen[-1]

        abweichung = []
        for handlung in self.fenster.findChildren(QAction):
            name = _sauber(handlung.text())
            if not name or handlung.actionGroup() is not None:
                continue
            if name not in gedruckt:
                continue
            if gedruckt[name] != handlung.shortcut().toString():
                abweichung.append(
                    f"{name}: Programm {handlung.shortcut().toString()!r}, "
                    f"Doku {gedruckt[name]!r}"
                )
        self.assertEqual(abweichung, [])
        # Und jeder Menüeintrag mit Kürzel steht auch in der Tabelle.
        mit_kuerzel = {
            _sauber(h.text())
            for h in self.fenster.findChildren(QAction)
            if h.shortcut().toString() and _sauber(h.text())
        }
        self.assertEqual(sorted(mit_kuerzel - set(gedruckt)), [])

    def test_der_dialog_zeigt_die_englische_seite(self):
        from verteilerly.gui.dialoge import DokumentationDialog

        dialog = DokumentationDialog()
        self.addCleanup(dialog.close)
        self.assertIn("Overview", dialog.text.toPlainText())
        self.assertEqual(dialog.verzeichnis.item(0).text(), "1 Overview")
        self.assertEqual(dialog.suchfeld.placeholderText(),
                         "Search the documentation (Ctrl+F)")


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


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestSucheInDerDokumentation(unittest.TestCase):
    """Wer ein Wort sucht, soll nicht zwölf Abschnitte durchsehen."""

    def setUp(self):
        from verteilerly.gui.dialoge import DokumentationDialog

        self.dialog = DokumentationDialog()
        self.addCleanup(self.dialog.close)
        self.dialog.show()
        self.addCleanup(self.dialog.hide)
        ANWENDUNG.processEvents()

    def _suchen(self, wort):
        self.dialog.suchfeld.setText(wort)
        ANWENDUNG.processEvents()
        return self.dialog.treffer

    def test_das_feld_sagt_wofuer_es_da_ist(self):
        self.assertIn("Strg+F", self.dialog.suchfeld.placeholderText())

    def test_ein_wort_wird_gefunden_und_gezaehlt(self):
        treffer = self._suchen("Rangierung")
        self.assertGreater(len(treffer), 1)
        self.assertIn(f"von {len(treffer)}", self.dialog.zaehler.text())
        self.assertEqual(self.dialog.stelle, 0)

    def test_gross_und_klein_ist_einerlei(self):
        gross = len(self._suchen("Kabel"))
        klein = len(self._suchen("kabel"))
        self.assertEqual(gross, klein)
        self.assertGreater(gross, 1)

    def test_jeder_treffer_wird_angestrichen(self):
        treffer = self._suchen("Leiste")
        self.assertEqual(len(self.dialog.text.extraSelections()), len(treffer))

    def test_weiter_und_zurueck_gehen_im_kreis(self):
        treffer = self._suchen("Bucht")
        self.assertGreater(len(treffer), 2)
        self.dialog.weiterspringen(1)
        self.assertEqual(self.dialog.stelle, 1)
        self.dialog.weiterspringen(-1)
        self.assertEqual(self.dialog.stelle, 0)
        self.dialog.weiterspringen(-1)
        self.assertEqual(self.dialog.stelle, len(treffer) - 1, "nicht im Kreis")

    def test_ein_einzelnes_zeichen_sucht_noch_nicht(self):
        """Sonst stünde bei jedem Anfangsbuchstaben der halbe Text an."""
        self.assertEqual(self._suchen("K"), [])
        self.assertIn("weiter tippen", self.dialog.zaehler.text())

    def test_was_es_nicht_gibt_wird_gesagt(self):
        self.assertEqual(self._suchen("Zwirbelwutz"), [])
        self.assertEqual(self.dialog.zaehler.text(), "nicht gefunden")
        self.assertFalse(self.dialog.vor.isEnabled())
        self.assertFalse(self.dialog.zurueck.isEnabled())

    def test_ohne_treffer_springt_nichts(self):
        self._suchen("Zwirbelwutz")
        self.dialog.weiterspringen(1)          # darf nicht scheitern
        self.assertEqual(self.dialog.stelle, -1)

    def test_ein_geleertes_feld_raeumt_die_anstriche_weg(self):
        self._suchen("Kabel")
        self._suchen("")
        self.assertEqual(self.dialog.text.extraSelections(), [])
        self.assertEqual(self.dialog.zaehler.text(), "")

    def test_esc_raeumt_erst_die_suche_weg(self):
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtGui import QKeyEvent

        self._suchen("Kabel")
        taste = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
        )
        ANWENDUNG.sendEvent(self.dialog, taste)
        ANWENDUNG.processEvents()
        self.assertEqual(self.dialog.suchfeld.text(), "")
        self.assertTrue(self.dialog.isVisible(), "der Dialog ist mit zugegangen")

    def test_strg_f_fuehrt_ins_suchfeld(self):
        self.dialog.text.setFocus()
        self.dialog.suche_aufrufen()
        self.assertTrue(self.dialog.suchfeld.hasFocus())

    def test_gesucht_wird_ab_der_sichtbaren_stelle(self):
        """Wer im Abschnitt über Kabel liest, meint den Treffer von dort."""
        marke = self.dialog.verzeichnis.item(
            self.dialog.verzeichnis.count() - 1
        )
        self.dialog.verzeichnis.setCurrentItem(marke)
        ANWENDUNG.processEvents()
        self._suchen("Verteilerly")
        self.assertGreater(self.dialog.stelle, 0)


if __name__ == "__main__":
    unittest.main()
