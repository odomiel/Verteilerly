"""Die Oberflaeche auf Deutsch oder Englisch.

Die wichtigste Pruefung steht ganz unten: sie liest jeden Aufruf von
``u`` aus dem Quelltext und vergleicht ihn mit der Wortliste. Ein Satz,
der eingewickelt ist, aber nicht im Katalog steht, bliebe im englischen
Programm deutsch stehen - und niemand merkte es.
"""

from __future__ import annotations

import ast
import pathlib
import tempfile
import unittest

import yaml

from verteilerly import sprachen
from verteilerly.modell import mehrzahl

WURZEL = pathlib.Path(__file__).resolve().parent.parent
PAKET = WURZEL / "verteilerly"


def texte_aus_dem_quelltext() -> list[str]:
    """Jeder Text, der durch die Uebersetzung geht - aus dem Quelltext.

    Zweierlei zaehlt: was in ``u("…")`` steht, und die beiden Woerter
    von ``mehrzahl``, die dort selbst uebersetzt werden.
    """
    gefunden: list[str] = []
    for datei in sorted(PAKET.rglob("*.py")):
        baum = ast.parse(datei.read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if not (isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Name)):
                continue
            if knoten.func.id == "u" and knoten.args:
                erste = knoten.args[0]
                if isinstance(erste, ast.Constant) and isinstance(erste.value, str):
                    gefunden.append(erste.value)
            elif knoten.func.id == "mehrzahl" and len(knoten.args) >= 3:
                for arg in knoten.args[1:3]:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        gefunden.append(arg.value)
    return sorted(set(gefunden))


class TestSprachwahl(unittest.TestCase):
    def setUp(self):
        self.addCleanup(sprachen.sprache_setzen, sprachen.VORGABE)

    def test_deutsch_ist_die_vorgabe(self):
        sprachen.sprache_setzen("de")
        self.assertEqual(sprachen.sprache(), "de")
        self.assertEqual(sprachen.u("Neuer Verteiler"), "Neuer Verteiler")

    def test_englisch_uebersetzt(self):
        sprachen.sprache_setzen("en")
        self.assertEqual(sprachen.sprache(), "en")
        self.assertEqual(sprachen.u("Neuer Verteiler"), "New distribution frame")

    def test_eine_unbekannte_sprache_fuehrt_zurueck_aufs_deutsche(self):
        """Eine von Hand geänderte Einstellungsdatei legt nichts lahm."""
        self.assertEqual(sprachen.sprache_setzen("klingonisch"), "de")
        self.assertEqual(sprachen.u("Neuer Verteiler"), "Neuer Verteiler")

    def test_ohne_uebersetzung_bleibt_der_deutsche_satz_stehen(self):
        sprachen.sprache_setzen("en")
        self.assertEqual(sprachen.u("Diesen Satz gibt es nicht"),
                         "Diesen Satz gibt es nicht")

    def test_die_sprachen_heissen_in_ihrer_eigenen_sprache(self):
        self.assertEqual(sprachen.name("de"), "Deutsch")
        self.assertEqual(sprachen.name("en"), "English")

    def test_die_mehrzahl_geht_durch_die_uebersetzung(self):
        """So muss keine der vielen Aufrufstellen davon wissen."""
        sprachen.sprache_setzen("de")
        self.assertEqual(mehrzahl(1, "Leiste", "Leisten"), "1 Leiste")
        self.assertEqual(mehrzahl(4, "Leiste", "Leisten"), "4 Leisten")
        sprachen.sprache_setzen("en")
        self.assertEqual(mehrzahl(1, "Leiste", "Leisten"), "1 strip")
        self.assertEqual(mehrzahl(4, "Leiste", "Leisten"), "4 strips")

    def test_eine_kaputte_wortliste_stoert_nicht(self):
        with tempfile.TemporaryDirectory() as ordner:
            datei = pathlib.Path(ordner) / "xx.yaml"
            datei.write_text("kein: [gueltiges, {yaml", encoding="utf-8")
            import unittest.mock as mock

            with mock.patch.object(sprachen, "sprachdatei", return_value=datei):
                self.assertEqual(sprachen.katalog_laden("xx"), {})


class TestWortliste(unittest.TestCase):
    """Der Katalog liegt als YAML bei und muss vollständig sein."""

    @classmethod
    def setUpClass(cls):
        cls.datei = sprachen.sprachdatei("en")
        cls.katalog = sprachen.katalog_laden("en")

    def test_die_datei_liegt_bei(self):
        self.assertIsNotNone(self.datei, "daten/sprachen/en.yaml fehlt")
        self.assertTrue(self.datei.is_file())

    def test_jeder_eingewickelte_satz_steht_darin(self):
        """Sonst bliebe er im englischen Programm deutsch stehen."""
        fehlend = [t for t in texte_aus_dem_quelltext() if t not in self.katalog]
        self.assertEqual(fehlend, [], f"{len(fehlend)} Sätze ohne Übersetzung")

    def test_die_liste_traegt_nichts_ueberfluessiges(self):
        """Was nirgends mehr vorkommt, ist beim Ändern übersehen worden."""
        gebraucht = set(texte_aus_dem_quelltext())
        # Die Beschriftungen der Projektdaten und der Blattarten kommen
        # aus Tabellen im Modell, nicht aus u("…") im Quelltext.
        from verteilerly.modell import (
            BLATTART_BESCHRIFTUNG,
            BLATTART_NAMEN,
            BRIEFKOPF_BESCHRIFTUNG,
        )
        from verteilerly.gui.leistenansicht import UEBERSCHRIFTEN

        # Die Arten der Vorlagenprüfung stehen als Tabelle im Modul und
        # gehen erst beim Anzeigen durch u(…).
        from verteilerly.pruefung import ARTEN

        gebraucht |= {wie for _art, wie in ARTEN}
        gebraucht |= set(BRIEFKOPF_BESCHRIFTUNG.values())
        gebraucht |= set(BLATTART_BESCHRIFTUNG.values())
        gebraucht |= set(BLATTART_NAMEN.values())
        gebraucht |= {t for t in UEBERSCHRIFTEN if t}
        # Der Blattvorlagen-Editor fuehrt seine Beschriftungen als Tabellen,
        # die eingebauten Erweiterungen Name und Beschreibung als Attribute.
        from verteilerly import erweiterungen
        from verteilerly.erweiterungen.blattvorlageneditor import dialog as editor

        for gruppe, felder in editor.ZAHLEN:
            gebraucht.add(gruppe)
            gebraucht |= {feld[1] for feld in felder}
        gebraucht |= {beschriftung for _feld, beschriftung in editor.SCHALTER}
        gebraucht.add(editor.SCHRIFTFELDHOEHE[1])
        from verteilerly.erweiterungen.blattvorlageneditor.schriftfeld import MARKENNAMEN

        gebraucht |= set(MARKENNAMEN.values())
        for tabelle in (editor.FELDNAMEN, editor.AUSRICHTUNGSNAMEN,
                        editor.SCHRIFTFELDNAMEN):
            gebraucht |= set(tabelle.values())
        for fund in erweiterungen.finden():
            gebraucht |= {fund.name, fund.beschreibung}
        uebrig = sorted(set(self.katalog) - gebraucht)
        self.assertEqual(uebrig, [])

    def test_die_platzhalter_bleiben_erhalten(self):
        """Ein verlorenes {0} wäre eine leere Stelle im Satz."""
        import re

        muster = re.compile(r"\{(\d+)")
        falsch = []
        for deutsch, englisch in self.katalog.items():
            if sorted(muster.findall(deutsch)) != sorted(muster.findall(englisch)):
                falsch.append(f"{deutsch!r} → {englisch!r}")
        self.assertEqual(falsch, [])

    def test_nichts_blieb_unuebersetzt_stehen(self):
        """Eine Zeile, die deutsch wie englisch gleich lautet, ist vergessen."""
        # Zahlen, Kürzel und Eigennamen dürfen gleich bleiben.
        erlaubt = {"OK", "PDF", "CSV", "{0}\n{1}", "{0} / {1}", "{0} · {1}: {2}",
                   "{0} ({1})", " ({0})", ", ",
                   # "Export", "Tools" und "Name" heißen in beiden Sprachen so.
                   "Export ({0})", "&Tools", "Name: {0}"}
        gleich = [
            deutsch for deutsch, englisch in self.katalog.items()
            if deutsch == englisch and deutsch not in erlaubt
        ]
        self.assertEqual(gleich, [])

    def test_die_wortliste_ist_lesbares_yaml(self):
        inhalt = yaml.safe_load(self.datei.read_text(encoding="utf-8"))
        self.assertIsInstance(inhalt, dict)
        self.assertGreater(len(inhalt), 300)


if __name__ == "__main__":
    unittest.main()
