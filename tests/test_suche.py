"""Im Projekt suchen.

Gesucht wird in allem, was von Hand eingetragen wurde - und gefunden
wird mit Ort und Feld, sonst waere die Fundstelle nur eine Behauptung.
"""

from __future__ import annotations

# Erst das Paket: es legt Einstellungs- und Arbeitsordner der
# Testreihe um, bevor etwas aus verteilerly Pfade liest.
from . import TESTHEIM  # noqa: F401

import unittest

from verteilerly import schreibweisen, suche
from verteilerly.modell import Aderadresse, Projekt, Verteiler, Zellenteilung


class TestSuche(unittest.TestCase):
    def setUp(self):
        self.verteiler = Verteiler.aus_geometrie(
            2, 3, 10, name="Verteiler Keller", nummer="1.1"
        )
        self.projekt = Projekt(
            verteiler=self.verteiler,
            briefkopf={"kunde": "Firma Meier", "firma": "Netzbau GmbH"},
            eigene_felder={"Raum": "Untergeschoss"},
        )
        self.ader = self.verteiler.ader(Aderadresse(1, 2, "a"))
        self.ader.bezeichnung = "Amt 42"
        self.ader.bemerkung = "gestört"
        self.ader.farbe = "ws/bl"

    def _suchen(self, wort, schreibweise=None):
        return suche.suchen(self.projekt, wort, schreibweise)

    def _texte(self, wort):
        return [f.text for f in self._suchen(wort)]

    # -- Was gefunden wird -------------------------------------------------

    def test_die_bezeichnung_wird_gefunden(self):
        treffer = self._suchen("Amt")
        self.assertEqual(len(treffer), 1)
        self.assertEqual(treffer[0].feld, "bezeichnung")
        self.assertEqual(treffer[0].text, "Amt 42")
        self.assertEqual(treffer[0].adresse, Aderadresse(1, 2, "a"))
        self.assertEqual(treffer[0].bereich, suche.ADER)

    def test_die_fundstelle_nennt_bucht_leiste_und_stift(self):
        ort = self._suchen("Amt")[0].ort
        for teil in ("Bucht 1", "Leiste 1", "Stift 2a"):
            with self.subTest(teil=teil):
                self.assertIn(teil, ort)

    def test_bemerkung_und_farbe_zaehlen_mit(self):
        self.assertEqual(self._suchen("gestört")[0].feld, "bemerkung")
        self.assertEqual(self._suchen("ws/bl")[0].feld, "farbe")

    def test_der_zweite_text_einer_geteilten_zelle_wird_mitgesucht(self):
        """Beide Felder gehören zur Zelle."""
        self.ader.teilung_setzen("bezeichnung", Zellenteilung(35, "Nst. 17"))
        treffer = self._suchen("Nst")
        self.assertEqual(len(treffer), 1)
        self.assertEqual(treffer[0].feld, "bezeichnung")
        self.assertEqual(treffer[0].text, "Amt 42 Nst. 17")

    def test_das_rangierfeld_wird_in_der_eingestellten_schreibweise_gesucht(self):
        """Wer „L3-4b“ sieht, sucht auch danach."""
        self.verteiler.rangierung_anlegen(
            Aderadresse(1, 3, "a"), Aderadresse(3, 4, "b")
        )
        self.assertEqual(self._suchen("3 4b")[0].feld, "rangierung")
        mit_strich = schreibweisen.holen("mit_strich")
        treffer = self._suchen("L3-4b", mit_strich)
        self.assertEqual(len(treffer), 1)
        self.assertEqual(treffer[0].adresse, Aderadresse(1, 3, "a"))

    def test_ein_vermerk_wird_gefunden(self):
        """Der Vermerk steht im Rangierfeld und gehört der Ader."""
        self.verteiler.ader(Aderadresse(2, 5, "b")).vermerk = "zur Klemmleiste"
        treffer = self._suchen("Klemm")
        self.assertEqual(len(treffer), 1)
        self.assertEqual(treffer[0].feld, "rangierung")
        self.assertEqual(treffer[0].leiste, 2)

    def test_die_kabelbeschriftung_wird_gefunden(self):
        self.verteiler.kabel_anlegen("Amtskabel 1", 3, 1, 4)
        treffer = [f for f in self._suchen("Amtskabel")]
        self.assertEqual(len(treffer), 1)
        self.assertEqual(treffer[0].bereich, suche.KABEL)
        self.assertEqual(treffer[0].leiste, 3)
        self.assertEqual(treffer[0].adresse, Aderadresse(3, 1, "a"))

    def test_die_projektdaten_zaehlen_mit(self):
        """Der Kunde steht nicht in der Leiste, gesucht wird er trotzdem."""
        treffer = self._suchen("Meier")
        self.assertEqual(len(treffer), 1)
        self.assertEqual(treffer[0].bereich, suche.PROJEKTDATEN)
        self.assertEqual(treffer[0].beschriftung, "Kunde")
        self.assertIsNone(treffer[0].adresse)

    def test_auch_die_eigenen_felder(self):
        treffer = self._suchen("Untergeschoss")
        self.assertEqual(len(treffer), 1)
        self.assertEqual(treffer[0].beschriftung, "Raum")

    def test_name_und_nummer_des_verteilers(self):
        self.assertEqual(self._suchen("Keller")[0].feld, "verteilername")
        self.assertEqual(self._suchen("1.1")[0].feld, "verteilernummer")

    # -- Wie gesucht wird --------------------------------------------------

    def test_gross_und_klein_ist_einerlei(self):
        self.assertEqual(self._texte("amt"), self._texte("AMT"))
        self.assertEqual(len(self._suchen("aMt 42")), 1)

    def test_ein_einzelnes_zeichen_findet_nichts(self):
        """Sonst stünde der halbe Verteiler in der Liste."""
        self.assertEqual(self._suchen("a"), [])
        self.assertEqual(self._suchen(""), [])
        self.assertEqual(self._suchen("   "), [])

    def test_leerzeichen_ringsum_stoeren_nicht(self):
        self.assertEqual(len(self._suchen("  Amt  ")), 1)

    def test_was_es_nicht_gibt_wird_nicht_gefunden(self):
        self.assertEqual(self._suchen("Zwirbelwutz"), [])

    def test_gesucht_wird_in_der_reihenfolge_des_verteilers(self):
        self.verteiler.ader(Aderadresse(2, 1, "a")).bezeichnung = "Amt 2"
        self.verteiler.ader(Aderadresse(1, 1, "b")).bezeichnung = "Amt 1"
        self.verteiler.kabel_anlegen("Amtskabel", 3, 1, 2)
        self.projekt.briefkopf["anlagennummer"] = "Amtsbau"
        stellen = self._suchen("Amt")
        self.assertEqual(
            [f.text for f in stellen],
            ["Amt 1", "Amt 42", "Amt 2", "Amtskabel", "Amtsbau"],
        )

    def test_eine_leere_leiste_liefert_nichts(self):
        leer = Projekt(verteiler=Verteiler.aus_geometrie(1, 2, 10))
        self.assertEqual(suche.suchen(leer, "irgendwas"), [])

    def test_die_fundstelle_liest_sich_als_eine_zeile(self):
        self.assertEqual(
            str(self._suchen("Amt")[0]),
            "Bucht 1 · Leiste 1 · Stift 2a · Bezeichnung: Amt 42",
        )


if __name__ == "__main__":
    unittest.main()
