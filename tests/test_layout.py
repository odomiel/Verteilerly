"""Tests zum Layoutmodell."""

import unittest

from verteilerly.layout import (
    RAND,
    REIHEN_JE_BLATT,
    SCHRIFTFELD_H,
    Blatt,
    Rechteck,
    Text,
    blaetter,
    leistenblatt,
    verteilerbelegungen,
)
from verteilerly.modell import Aderadresse, Projekt, Verteiler


def _texte(blatt: Blatt) -> list[str]:
    return [e.text for e in blatt.elemente if isinstance(e, Text)]


class TestBlattfolge(unittest.TestCase):
    def test_deckblatt_belegung_dann_je_leiste_eines(self):
        """Deckblatt, Belegung, dann je Leiste ein Blatt."""
        for reihen, leisten, da, erwartet in [
            (1, 4, 10, 6),
            (1, 2, 20, 4),
            (2, 6, 10, 14),
            (4, 6, 10, 27),   # Deckblatt, zwei Buchten, 24 Leistenblätter
        ]:
            with self.subTest(geometrie=(reihen, leisten, da)):
                v = Verteiler.aus_geometrie(reihen, leisten, da)
                folge = blaetter(Projekt(verteiler=v))
                self.assertEqual(len(folge), erwartet)
                self.assertEqual(folge[0].titel, "Deckblatt")
                self.assertTrue(folge[1].quer)   # die Verteilerbelegung
                self.assertEqual(folge[-1].titel, f"Leiste {reihen * leisten}")

    def test_ab_drei_reihen_eine_bucht_je_blatt(self):
        """Mehr als zwei Reihen nebeneinander waeren nur noch gequetscht."""
        for reihen, erwartet in [(1, 1), (2, 1), (3, 2), (4, 2), (5, 3)]:
            with self.subTest(reihen=reihen):
                v = Verteiler.aus_geometrie(reihen, 4, 10)
                belegung = verteilerbelegungen(Projekt(verteiler=v))
                self.assertEqual(len(belegung), erwartet)

    def test_bis_zwei_reihen_bleibt_es_ein_blatt_ohne_bucht(self):
        v = Verteiler.aus_geometrie(2, 6, 10)
        belegung = verteilerbelegungen(Projekt(verteiler=v))
        self.assertEqual([b.titel for b in belegung], ["Verteilerbelegung"])

    def test_buchten_werden_durchnummeriert(self):
        v = Verteiler.aus_geometrie(5, 4, 10)
        belegung = verteilerbelegungen(Projekt(verteiler=v))
        self.assertEqual([b.titel for b in belegung], ["Bucht 1", "Bucht 2", "Bucht 3"])

    def test_jede_leiste_steht_auf_genau_einer_bucht(self):
        v = Verteiler.aus_geometrie(4, 6, 10)
        gefunden = []
        for blatt in verteilerbelegungen(Projekt(verteiler=v)):
            gefunden += [t for t in _texte(blatt) if t.startswith("Leiste ")]
        self.assertEqual(len(gefunden), len(v.alle_leisten))
        self.assertEqual(len(set(gefunden)), len(v.alle_leisten))

    def test_bucht_traegt_ihre_reihen_im_kopf(self):
        v = Verteiler.aus_geometrie(4, 6, 10)
        erste, zweite = verteilerbelegungen(Projekt(verteiler=v))
        self.assertIn("Reihen 1 und 2", _texte(erste))
        self.assertIn("Reihen 3 und 4", _texte(zweite))

    def test_ungerade_letzte_bucht_nennt_eine_reihe(self):
        v = Verteiler.aus_geometrie(3, 4, 10)
        self.assertIn("Reihe 3", _texte(verteilerbelegungen(Projekt(verteiler=v))[-1]))

    def test_reihen_je_blatt_ist_die_grenze(self):
        self.assertEqual(REIHEN_JE_BLATT, 2)

    def test_ausrichtung(self):
        """Leistenblätter hoch, die Verteilerbelegung quer."""
        folge = blaetter(Projekt(verteiler=Verteiler.aus_geometrie(2, 6, 10)))
        self.assertFalse(folge[0].quer)
        self.assertTrue(folge[1].quer)
        self.assertFalse(folge[2].quer)

    def test_alles_bleibt_auf_dem_blatt(self):
        """Auch ein sehr grosser Verteiler laeuft nicht ueber den Rand."""
        for geometrie in [(1, 4, 10), (1, 2, 20), (2, 6, 10), (3, 8, 20), (5, 6, 20)]:
            v = Verteiler.aus_geometrie(*geometrie)
            for blatt in blaetter(Projekt(verteiler=v)):
                with self.subTest(geometrie=geometrie, blatt=blatt.titel):
                    for element in blatt.elemente:
                        rechts = getattr(element, "x", 0) + getattr(element, "breite", 0)
                        self.assertLessEqual(rechts, blatt.breite - RAND + 0.01)


class TestSchriftfeld(unittest.TestCase):
    """Je Blatt korrekt, nicht kopiert."""

    def setUp(self):
        v = Verteiler.aus_geometrie(1, 4, 10, name="Muster", nummer="V-01")
        self.projekt = Projekt(
            verteiler=v,
            briefkopf={"firma": "Musterfirma", "erstellt_am": "01.09.2026"},
            eigene_felder={"Standort": "Keller"},
        )

    def test_jedes_leistenblatt_traegt_seine_eigene_nummer(self):
        folge = blaetter(self.projekt)
        for nummer, blatt in enumerate(folge[2:], 1):
            with self.subTest(leiste=nummer):
                self.assertIn(str(nummer), _texte(blatt))

    def test_stammdaten_stehen_auf_jedem_blatt(self):
        for blatt in blaetter(self.projekt):
            with self.subTest(blatt=blatt.titel):
                self.assertIn("Musterfirma", _texte(blatt))
                self.assertIn("Muster", _texte(blatt))

    def test_eigene_felder_erscheinen(self):
        self.assertIn("Keller", _texte(blaetter(self.projekt)[0]))

    def test_leere_felder_bleiben_leer(self):
        """Ein nicht gefuelltes Feld erzeugt keinen leeren Text."""
        for blatt in blaetter(self.projekt):
            self.assertNotIn("", _texte(blatt))


class TestLeistenblatt(unittest.TestCase):
    def setUp(self):
        self.v = Verteiler.aus_geometrie(1, 4, 10, name="Muster")
        self.projekt = Projekt(verteiler=self.v)

    def test_zwei_zeilen_je_doppelader(self):
        blatt = leistenblatt(self.projekt, 1)
        self.assertEqual(_texte(blatt).count("a"), 10)
        self.assertEqual(_texte(blatt).count("b"), 10)

    def test_werte_der_adern_stehen_auf_dem_blatt(self):
        self.v.leiste(1).stift(1).a.farbe = "rt"
        self.v.leiste(1).stift(1).a.bemerkung = "Magnetkontakt"
        self.v.rangierung_anlegen(Aderadresse.parse("1 1a"), Aderadresse.parse("3 2a"))
        texte = _texte(leistenblatt(self.projekt, 1))
        self.assertIn("rt", texte)
        self.assertIn("Magnetkontakt", texte)
        self.assertIn("3 2a", texte)

    def test_kabelklammer_umfasst_die_belegten_zeilen(self):
        """Auf dem Blatt: 4 DA sind 8 Zeilen."""
        self.v.kabel_anlegen("Leitung", 1, 3, 4)
        blatt = leistenblatt(self.projekt, 1)
        klammern = [
            e for e in blatt.elemente if isinstance(e, Rechteck) and e.fuellung
        ]
        self.assertTrue(klammern)
        klammer = max(klammern, key=lambda e: e.hoehe)
        zeile_h = klammer.hoehe / 8
        # Die Klammer beginnt bei DA 3, also nach vier Zeilen.
        kopf = min(e.y for e in blatt.elemente if isinstance(e, Rechteck))
        self.assertAlmostEqual(klammer.y - kopf - 7.0, 4 * zeile_h, places=6)

    def test_zwanzig_da_passen_ueber_das_schriftfeld(self):
        v = Verteiler.aus_geometrie(1, 2, 20, name="Muster")
        blatt = leistenblatt(Projekt(verteiler=v), 1)
        grenze = blatt.hoehe - RAND - SCHRIFTFELD_H
        tabelle = [
            e.y + e.hoehe
            for e in blatt.elemente
            if isinstance(e, Rechteck) and e.y < grenze
        ]
        self.assertLessEqual(max(tabelle), grenze)


if __name__ == "__main__":
    unittest.main()
