"""Tests zum Layoutmodell."""

import unittest

from verteilerly.blattvorlagen import STANDARD, Blattvorlage
from verteilerly.layout import (
    Blatt,
    Rechteck,
    Text,
    blaetter,
    leistenblatt,
    verteilerbelegungen,
)

RAND = STANDARD.rand
SCHRIFTFELD_H = STANDARD.schriftfeld_hoehe
from verteilerly.modell import Aderadresse, Projekt, Verteiler


def _texte(blatt: Blatt) -> list[str]:
    return [e.text for e in blatt.elemente if isinstance(e, Text)]


class TestBlattfolge(unittest.TestCase):
    def test_deckblatt_belegung_dann_je_leiste_eines(self):
        """Deckblatt, Belegung, dann je Leiste ein Blatt."""
        for buchten, leisten, da, erwartet in [
            (1, 4, 10, 6),
            (1, 2, 20, 4),
            (2, 6, 10, 14),
            (4, 6, 10, 27),   # Deckblatt, zwei Buchten, 24 Leistenblätter
        ]:
            with self.subTest(geometrie=(buchten, leisten, da)):
                v = Verteiler.aus_geometrie(buchten, leisten, da)
                folge = blaetter(Projekt(verteiler=v))
                self.assertEqual(len(folge), erwartet)
                self.assertEqual(folge[0].titel, "Deckblatt")
                self.assertTrue(folge[1].quer)   # die Verteilerbelegung
                self.assertEqual(folge[-1].titel, f"Leiste {buchten * leisten}")

    def test_ab_drei_buchten_eine_bucht_je_blatt(self):
        """Mehr als zwei Buchten nebeneinander waeren nur noch gequetscht."""
        for buchten, erwartet in [(1, 1), (2, 1), (3, 2), (4, 2), (5, 3)]:
            with self.subTest(buchten=buchten):
                v = Verteiler.aus_geometrie(buchten, 4, 10)
                belegung = verteilerbelegungen(Projekt(verteiler=v))
                self.assertEqual(len(belegung), erwartet)

    def test_bis_zwei_buchten_bleibt_es_ein_blatt_ohne_bucht(self):
        v = Verteiler.aus_geometrie(2, 6, 10)
        belegung = verteilerbelegungen(Projekt(verteiler=v))
        self.assertEqual([b.titel for b in belegung], ["Verteilerbelegung"])

    def test_blatt_heisst_nach_seinen_buchten(self):
        v = Verteiler.aus_geometrie(5, 4, 10)
        belegung = verteilerbelegungen(Projekt(verteiler=v))
        self.assertEqual(
            [b.titel for b in belegung],
            ["Buchten 1 und 2", "Buchten 3 und 4", "Bucht 5"],
        )

    def test_jede_leiste_steht_auf_genau_einer_bucht(self):
        v = Verteiler.aus_geometrie(4, 6, 10)
        gefunden = []
        for blatt in verteilerbelegungen(Projekt(verteiler=v)):
            gefunden += [t for t in _texte(blatt) if t.startswith("Leiste ")]
        self.assertEqual(len(gefunden), len(v.alle_leisten))
        self.assertEqual(len(set(gefunden)), len(v.alle_leisten))

    def test_kopfzeile_nennt_die_buchten_des_blattes(self):
        v = Verteiler.aus_geometrie(4, 6, 10)
        erste, zweite = verteilerbelegungen(Projekt(verteiler=v))
        self.assertIn("Verteilerbelegung — Buchten 1 und 2", _texte(erste))
        self.assertIn("Verteilerbelegung — Buchten 3 und 4", _texte(zweite))

    def test_bleibt_eine_bucht_uebrig_steht_sie_allein(self):
        v = Verteiler.aus_geometrie(3, 4, 10)
        letztes = verteilerbelegungen(Projekt(verteiler=v))[-1]
        self.assertEqual(letztes.titel, "Bucht 3")

    def test_buchten_je_blatt_ist_die_grenze(self):
        self.assertEqual(STANDARD.buchten_je_blatt, 2)

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

    def test_abgewaehltes_feld_steht_auf_keinem_blatt(self):
        """Der Wert bleibt im Projekt, das Blatt zeigt ihn nicht."""
        self.projekt.sichtbarkeit_setzen("firma", False)
        self.projekt.sichtbarkeit_setzen("Standort", False)
        for blatt in blaetter(self.projekt):
            with self.subTest(blatt=blatt.titel):
                self.assertNotIn("Musterfirma", _texte(blatt))
                self.assertNotIn("Keller", _texte(blatt))
        self.assertEqual(self.projekt.briefkopf["firma"], "Musterfirma")

    def test_mit_dem_feld_geht_auch_die_beschriftung(self):
        """Eine Zeile „Kunde“ ohne Kunden wäre schlimmer als gar keine."""
        self.projekt.briefkopf["kunde"] = "Kunde AG"
        self.projekt.sichtbarkeit_setzen("kunde", False)
        self.projekt.sichtbarkeit_setzen("Standort", False)
        for blatt in blaetter(self.projekt):
            with self.subTest(blatt=blatt.titel):
                self.assertNotIn("Kunde", _texte(blatt))
                self.assertNotIn("Standort", _texte(blatt))

    def test_leeres_feld_behaelt_seine_beschriftung(self):
        """Angewählt und leer heißt: hier wird von Hand eingetragen."""
        texte = _texte(leistenblatt(self.projekt, 1))
        self.assertIn("Geprüft", texte)          # im Briefkopf nicht gefüllt
        self.assertIn("Stand", texte)

    def test_paar_faellt_erst_weg_wenn_beide_haelften_weg_sind(self):
        self.projekt.sichtbarkeit_setzen("geprueft_am", False)
        self.assertIn("Geprüft", _texte(leistenblatt(self.projekt, 1)))
        self.projekt.sichtbarkeit_setzen("geprueft_von", False)
        self.assertNotIn("Geprüft", _texte(leistenblatt(self.projekt, 1)))

    def test_blatteigene_marken_bleiben_immer(self):
        """Verteiler, Leiste und Blatt gehören zum Blatt, nicht zum Briefkopf."""
        for name in ("verteiler", "verteilernummer", "leiste", "blatt"):
            self.projekt.sichtbarkeit_setzen(name, False)
        texte = _texte(leistenblatt(self.projekt, 1))
        self.assertIn("Verteiler", texte)
        self.assertIn("Leiste", texte)

    def test_halb_abgewaehltes_paar(self):
        """Erstellt am/von: fällt eine Hälfte weg, bleibt die andere."""
        self.projekt.briefkopf["erstellt_von"] = "T. Mirik"
        self.projekt.sichtbarkeit_setzen("erstellt_am", False)
        texte = " ".join(_texte(blaetter(self.projekt)[0]))
        self.assertIn("T. Mirik", texte)
        self.assertNotIn("01.09.2026", texte)

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


class TestKabelspalte(unittest.TestCase):
    """Schmale Kabelspalte, Beschriftung quer darin."""

    def _kabeltexte(self, vorlage):
        v = Verteiler.aus_geometrie(1, 2, 10)
        v.kabel_anlegen("Linie 1 — Melderkreis Erdgeschoss West", 1, 1, 5)
        blatt = leistenblatt(Projekt(verteiler=v), 1, vorlage)
        return [
            e for e in blatt.elemente
            if isinstance(e, Text) and "Melderkreis" in e.text
        ]

    def test_beschriftung_steht_quer(self):
        gedreht = self._kabeltexte(STANDARD)
        self.assertEqual(len(gedreht), 1)
        self.assertEqual(gedreht[0].drehung, 90)
        # Quer gelesen ist die Hoehe der Klammer die Laenge der Zeile.
        self.assertEqual(gedreht[0].zeilenlaenge, gedreht[0].hoehe)
        self.assertGreater(gedreht[0].hoehe, gedreht[0].breite)

    def test_waagerecht_bleibt_waagerecht(self):
        waagerecht = self._kabeltexte(STANDARD.mit(kabel_gedreht=False))
        self.assertEqual(waagerecht[0].drehung, 0)
        self.assertEqual(waagerecht[0].zeilenlaenge, waagerecht[0].breite)

    def test_gekuerztes_kabel_sagt_es_auch_quer(self):
        v = Verteiler.aus_geometrie(1, 2, 10)
        v.kabel_anlegen("Zuleitung BMZ", 1, 1, 3, da_gesamt=4)
        blatt = leistenblatt(Projekt(verteiler=v), 1)
        quer = [e for e in blatt.elemente if isinstance(e, Text) and e.drehung]
        self.assertEqual(len(quer), 1)
        self.assertIn("gekürzt: 3 von 4 DA", quer[0].text)


class TestAnschriftImSchriftfeld(unittest.TestCase):
    """Eine Anschrift steht untereinander, wie in den Vorlagen."""

    def _projekt(self) -> Projekt:
        return Projekt(
            verteiler=Verteiler.aus_geometrie(1, 2, 10, name="Verteiler Name"),
            briefkopf={
                "firma": "Firma Beliebig\nBeliebige Straße 7\n77777 Beliebiger Ort",
                "kunde": "Kunde Beliebig",
            },
        )

    def test_zeilen_werden_aufgeteilt(self):
        from verteilerly.layout import schriftfeldzeilen

        zeilen = schriftfeldzeilen(
            [("Firma", "Firma Beliebig\nBeliebige Straße 7"), ("Kunde", "")]
        )
        self.assertEqual(
            zeilen,
            [("Firma", "Firma Beliebig"), ("", "Beliebige Straße 7"), ("Kunde", "")],
        )

    def test_anschrift_steht_zeilenweise_auf_dem_blatt(self):
        blatt = leistenblatt(self._projekt(), 1)
        texte = _texte(blatt)
        for zeile in ("Firma Beliebig", "Beliebige Straße 7", "77777 Beliebiger Ort"):
            with self.subTest(zeile=zeile):
                self.assertIn(zeile, texte)
        # Die Beschriftung steht nur an der ersten Zeile.
        self.assertEqual(texte.count("Firma"), 1)

    def test_einzeiliges_bleibt_eine_zeile(self):
        blatt = leistenblatt(self._projekt(), 1)
        self.assertIn("Kunde Beliebig", _texte(blatt))

    def test_anteile_der_bloecke_aus_der_vorlage(self):
        from verteilerly.layout import _schriftfeldanteile

        self.assertEqual(_schriftfeldanteile(3), [0.38, 0.26, 0.36])
        self.assertEqual(_schriftfeldanteile(3, (1.0, 1.0, 2.0)), [0.25, 0.25, 0.5])
        # Passt die Angabe nicht zur Zahl der Blöcke, bleibt es beim Augenmaß.
        self.assertEqual(_schriftfeldanteile(3, (1.0, 1.0)), [0.38, 0.26, 0.36])


class TestSchriftfeldBeispiel(unittest.TestCase):
    """Das Schriftfeld der Mustertabellen, Feld für Feld."""

    def setUp(self):
        from verteilerly.blattvorlagen import Blattvorlagen
        from verteilerly.pfade import mitgeliefert

        self.vorlage = Blattvorlagen.laden(
            mitgeliefert() / "blattvorlagen"
        ).holen("beispiel")
        self.projekt = Projekt(
            verteiler=Verteiler.aus_geometrie(1, 2, 10, name="Verteiler Name",
                                              nummer="1.1"),
            briefkopf={
                "firma": "Firma Beliebig\nBeliebige Straße 7\n77777 Beliebiger Ort",
                "kunde": "Kunde Beliebig",
                "erstellt_am": "01.01.1970",
                "erstellt_von": "John Doe",
            },
        )

    def _blatt(self):
        return leistenblatt(self.projekt, 1, self.vorlage)

    def test_matrix_aus_datum_und_name(self):
        texte = _texte(self._blatt())
        for erwartet in ("Datum", "Name", "Erstellt", "Stand", "Geprüft"):
            with self.subTest(feld=erwartet):
                self.assertIn(erwartet, texte)
        # Datum und Name stehen getrennt, nicht als „01.01.1970 · John Doe“.
        self.assertIn("01.01.1970", texte)
        self.assertIn("John Doe", texte)
        self.assertNotIn("01.01.1970 · John Doe", texte)

    def test_verteilerblock_unter_der_matrix(self):
        blatt = self._blatt()
        stellen = {e.text: e.y for e in blatt.elemente if isinstance(e, Text)}
        self.assertIn("Verteiler:", stellen)
        self.assertIn("Verteiler Nr.", stellen)
        self.assertIn("Leiste:", stellen)
        # Der Name steht unter seiner Beschriftung, nicht daneben.
        self.assertGreater(stellen["Verteiler Name"], stellen["Verteiler:"])
        self.assertGreater(stellen["Verteiler Nr."], stellen["Verteiler Name"])

    def test_anschriften_stehen_rechts_und_untereinander(self):
        blatt = self._blatt()
        anschrift = [
            e for e in blatt.elemente
            if isinstance(e, Text) and e.text.startswith(("Firma Beliebig",
                                                          "Beliebige Straße",
                                                          "77777"))
        ]
        self.assertEqual(len(anschrift), 3)
        # Rechts vom Verteilerblock und der Reihe nach untereinander.
        links = min(e.x for e in anschrift)
        self.assertGreater(links, blatt.breite / 2)
        self.assertEqual([e.y for e in anschrift], sorted(e.y for e in anschrift))

    def test_kunde_steht_unter_der_firma(self):
        blatt = self._blatt()
        stellen = {e.text: e.y for e in blatt.elemente if isinstance(e, Text)}
        self.assertGreater(stellen["Kunde Beliebig"], stellen["Firma Beliebig"])

    def test_abgewaehltes_feld_bleibt_leer(self):
        """Auch hier gilt: ohne Haken kein Eintrag."""
        self.projekt.sichtbarkeit_setzen("firma", False)
        self.assertNotIn("Firma Beliebig", _texte(self._blatt()))

    def test_standardvorlage_bleibt_bei_ihrer_bauart(self):
        texte = _texte(leistenblatt(self.projekt, 1, STANDARD))
        self.assertNotIn("Datum", texte)
        self.assertIn("01.01.1970 · John Doe", texte)
