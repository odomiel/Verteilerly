"""Tests zum Datenmodell."""

import unittest

from verteilerly.modell import (
    Aderadresse,
    Kabelabschnitt,
    ModellFehler,
    UeberlaufFehler,
    Verteiler,
)


class TestGeometrie(unittest.TestCase):
    def test_mustermasse(self):
        """Die drei Muster ergeben ihre bekannte DA-Zahl."""
        for reihen, leisten, da, erwartet in [
            (1, 4, 10, 40),   # 40 DA in vier Leisten
            (1, 2, 20, 40),   # 40 DA in zwei Leisten
            (2, 6, 10, 120),  # 120 DA in zwei Buchten
        ]:
            with self.subTest(geometrie=(reihen, leisten, da)):
                self.assertEqual(
                    Verteiler.aus_geometrie(reihen, leisten, da).da_gesamt, erwartet
                )

    def test_leisten_laufen_ueber_reihen_durch(self):
        """Reihe 1 traegt Leiste 1-6, Reihe 2 die Leisten 7-12."""
        v = Verteiler.aus_geometrie(2, 6, 10)
        self.assertEqual([l.nummer for l in v.reihen[0].leisten], list(range(1, 7)))
        self.assertEqual([l.nummer for l in v.reihen[1].leisten], list(range(7, 13)))

    def test_leere_geometrie_abgelehnt(self):
        with self.assertRaises(ModellFehler):
            Verteiler.aus_geometrie(1, 0, 10)

    def test_unbekannte_leiste(self):
        v = Verteiler.aus_geometrie(1, 4, 10)
        with self.assertRaises(ModellFehler):
            v.leiste(5)
        with self.assertRaises(ModellFehler):
            v.leiste(1).stift(11)


class TestAderadresse(unittest.TestCase):
    def test_lesen_und_schreiben(self):
        """Format '<Leiste> <Stift><Ader>'."""
        adresse = Aderadresse.parse("3 2a")
        self.assertEqual((adresse.leiste, adresse.stift, adresse.seite), (3, 2, "a"))
        self.assertEqual(str(adresse), "3 2a")

    def test_toleriert_leerraum_und_grossschreibung(self):
        self.assertEqual(str(Aderadresse.parse("  12   7B ")), "12 7b")

    def test_unlesbares_abgelehnt(self):
        for text in ["", "3", "3 2c", "abc", "3-2a"]:
            with self.subTest(text=text), self.assertRaises(ModellFehler):
                Aderadresse.parse(text)


class TestKabel(unittest.TestCase):
    def setUp(self):
        self.v = Verteiler.aus_geometrie(1, 4, 10)

    def test_anlegen_und_belegung(self):
        kabel = self.v.kabel_anlegen("4DA zu Wohnzimmer", 1, 1, 4)
        self.assertEqual(kabel.da_aufgelegt, 4)
        self.assertIs(self.v.kabel_an(1, 4), kabel)
        self.assertIsNone(self.v.kabel_an(1, 5))

    def test_freie_startposition_und_mehrere_kabel(self):
        """Mehrere Kabel je Leiste, Startposition frei."""
        self.v.kabel_anlegen("erstes", 1, 1, 4)
        zweites = self.v.kabel_anlegen("zweites", 1, 5, 2)
        self.assertEqual(zweites.abschnitte[0].start_da, 5)
        self.assertEqual(len(self.v.kabel), 2)

    def test_ueberlappung_abgelehnt(self):
        self.v.kabel_anlegen("erstes", 1, 1, 4)
        with self.assertRaises(ModellFehler):
            self.v.kabel_anlegen("zweites", 1, 4, 2)

    def test_ueberlauf_meldet_rest(self):
        """Passt es nicht, wird mit passend/rest gefragt."""
        with self.assertRaises(UeberlaufFehler) as gefangen:
            self.v.kabel_anlegen("6DA", 1, 8, 6)
        self.assertEqual((gefangen.exception.passend, gefangen.exception.rest), (3, 3))

    def test_fortsetzung_auf_anderer_leiste(self):
        """Der Rest laeuft auf einer waehlbaren Leiste weiter."""
        kabel = self.v.kabel_anlegen_mehrteilig(
            "6DA ueber zwei Leisten",
            [Kabelabschnitt(1, 8, 3), Kabelabschnitt(2, 1, 3)],
        )
        self.assertEqual(kabel.da_aufgelegt, 6)
        self.assertFalse(kabel.gekuerzt)
        # Die Kabel-DA zaehlt ueber den Leistenwechsel hinweg durch.
        self.assertEqual(
            kabel.positionen(),
            [(1, 1, 8), (2, 1, 9), (3, 1, 10), (4, 2, 1), (5, 2, 2), (6, 2, 3)],
        )

    def test_rest_verfaellt(self):
        """Nur der passende Teil wird aufgelegt."""
        kabel = self.v.kabel_anlegen_mehrteilig(
            "6DA, Rest verfaellt", [Kabelabschnitt(1, 8, 3)], da_gesamt=6
        )
        self.assertEqual(kabel.da_aufgelegt, 3)
        self.assertTrue(kabel.gekuerzt)

    def test_kuerzen(self):
        """Von einem 6-DA-Kabel werden nur 5 DA aufgelegt."""
        kabel = self.v.kabel_anlegen("6DA, 5 aufgelegt", 1, 1, 5, da_gesamt=6)
        self.assertEqual((kabel.da_gesamt, kabel.da_aufgelegt), (6, 5))
        self.assertTrue(kabel.gekuerzt)
        self.assertIsNone(self.v.kabel_an(1, 6))

    def test_mehr_auflegen_als_das_kabel_hat(self):
        with self.assertRaises(ModellFehler):
            self.v.kabel_anlegen("4DA", 1, 1, 5, da_gesamt=4)


class TestRangierung(unittest.TestCase):
    def setUp(self):
        self.v = Verteiler.aus_geometrie(1, 4, 10)
        self.a = Aderadresse.parse("1 1a")
        self.b = Aderadresse.parse("3 2a")

    def test_gegenstelle_ohne_zweiten_datensatz(self):
        """Ein Objekt, an beiden Enden sichtbar."""
        self.v.rangierung_anlegen(self.a, self.b)
        self.assertEqual(len(self.v.rangierungen), 1)
        self.assertEqual([str(z) for z in self.v.ziele_von(self.a)], ["3 2a"])
        self.assertEqual([str(z) for z in self.v.ziele_von(self.b)], ["1 1a"])

    def test_zwei_rangierungen_je_feld(self):
        """Bis zu zwei - die dritte wird abgewiesen."""
        self.v.rangierung_anlegen(self.a, self.b)
        self.v.rangierung_anlegen(self.a, Aderadresse.parse("4 5a"))
        self.assertEqual(len(self.v.ziele_von(self.a)), 2)
        with self.assertRaises(ModellFehler):
            self.v.rangierung_anlegen(self.a, Aderadresse.parse("2 7a"))

    def test_loeschen_wirkt_auf_beide_enden(self):
        """Es kann keine halbe Rangierung zurueckbleiben."""
        self.v.rangierung_anlegen(self.a, self.b)
        self.v.rangierung_entfernen(self.b, self.a)  # Richtung egal
        self.assertEqual(self.v.ziele_von(self.a), [])
        self.assertEqual(self.v.ziele_von(self.b), [])

    def test_pruefungen(self):
        """Selbstbezug, unbekanntes Ziel, Doppeleintrag."""
        with self.assertRaises(ModellFehler):
            self.v.rangierung_anlegen(self.a, self.a)
        with self.assertRaises(ModellFehler):
            self.v.rangierung_anlegen(self.a, Aderadresse.parse("9 1a"))
        self.v.rangierung_anlegen(self.a, self.b)
        with self.assertRaises(ModellFehler):
            self.v.rangierung_anlegen(self.b, self.a)

    def test_entfernen_was_es_nicht_gibt(self):
        with self.assertRaises(ModellFehler):
            self.v.rangierung_entfernen(self.a, self.b)


if __name__ == "__main__":
    unittest.main()
