"""Tests zu den Blattvorlagen."""

import pathlib
import tempfile
import unittest

from verteilerly.blattvorlagen import (
    STANDARD,
    Blattvorlage,
    Blattvorlagen,
    BlattvorlagenFehler,
    blattvorlage_aus_yaml,
)
from verteilerly.layout import Rechteck, Text, blaetter, leistenblatt
from verteilerly.modell import Projekt, Verteiler
from verteilerly.pfade import blattvorlagenordner, mitgeliefert


def _texte(blatt) -> list[str]:
    return [e.text for e in blatt.elemente if isinstance(e, Text)]


def _projekt() -> Projekt:
    v = Verteiler.aus_geometrie(3, 4, 10, name="Muster")
    v.kabel_anlegen("Leitung", 1, 1, 4)
    v.leiste(1).stift(1).a.bemerkung = "Magnetkontakt"
    v.leiste(1).stift(1).a.bezeichnung = "Linie"
    return Projekt(verteiler=v, briefkopf={"firma": "Musterfirma"})


class TestVorgaben(unittest.TestCase):
    def test_leere_vorlage_ist_das_bisherige_blatt(self):
        """Die Vorgaben sind genau das Blatt der Mustertabellen."""
        self.assertEqual(STANDARD.rand, 12.0)
        self.assertEqual(
            [s.feld for s in STANDARD.spalten],
            ["stift", "ader", "farbe", "bezeichnung", "rangierung", "bemerkung", "kabel"],
        )

    def test_breiten_werden_auf_das_blatt_gestreckt(self):
        vorlage = Blattvorlage(spalten=STANDARD.spalten[:2])
        breiten = vorlage.breiten(100)
        self.assertAlmostEqual(sum(breiten), 100)
        self.assertGreater(breiten[0], breiten[1])   # Anteil 10 gegen 7

    def test_spalte_nachschlagen(self):
        self.assertEqual(STANDARD.spalte("kabel").ueberschrift, "Kabel")
        self.assertIsNone(STANDARD.spalte("gibtsnicht"))


class TestAusYaml(unittest.TestCase):
    def test_nur_das_abweichende_muss_dastehen(self):
        vorlage = blattvorlage_aus_yaml({"id": "eng", "name": "Eng", "rand": 8}, "eng.yaml")
        self.assertEqual(vorlage.rand, 8)
        self.assertEqual(vorlage.spalten, STANDARD.spalten)
        self.assertEqual(vorlage.schrift_normal, STANDARD.schrift_normal)

    def test_spalten_als_kurzform(self):
        vorlage = blattvorlage_aus_yaml(
            {"id": "k", "name": "K", "spalten": ["stift", "rangierung"]}, "k.yaml"
        )
        self.assertEqual([s.feld for s in vorlage.spalten], ["stift", "rangierung"])
        self.assertEqual(vorlage.spalten[1].ueberschrift, "Rangierung")

    def test_unbekanntes_feld_wird_abgewiesen(self):
        with self.assertRaises(BlattvorlagenFehler) as fehler:
            blattvorlage_aus_yaml(
                {"id": "x", "name": "X", "spalten": ["widerstand"]}, "x.yaml"
            )
        self.assertIn("widerstand", str(fehler.exception))

    def test_unbekannte_marke_im_schriftfeld(self):
        with self.assertRaises(BlattvorlagenFehler):
            blattvorlage_aus_yaml(
                {"id": "x", "name": "X", "schriftfeld": [["firma", "wetter"]]}, "x.yaml"
            )

    def test_ohne_namen_kein_eintrag(self):
        with self.assertRaises(BlattvorlagenFehler):
            blattvorlage_aus_yaml({"id": "x"}, "x.yaml")

    def test_zahl_muss_eine_zahl_sein(self):
        with self.assertRaises(BlattvorlagenFehler):
            blattvorlage_aus_yaml({"id": "x", "name": "X", "rand": "breit"}, "x.yaml")

    def test_null_buchten_je_blatt(self):
        with self.assertRaises(BlattvorlagenFehler):
            blattvorlage_aus_yaml(
                {"id": "x", "name": "X", "buchten_je_blatt": 0}, "x.yaml"
            )


class TestMitgelieferte(unittest.TestCase):
    def setUp(self):
        self.vorlagen = Blattvorlagen.laden(blattvorlagenordner())

    def test_die_mitgelieferten_vorlagen(self):
        beiliegend = Blattvorlagen.laden(mitgeliefert() / "blattvorlagen")
        self.assertEqual(
            sorted(v.id for v in beiliegend.alle),
            ["ausfuehrlich", "beispiel", "knapp", "standard"],
        )

    def test_beispielvorlage_folgt_den_ods_dateien(self):
        """Die Spalten der Vorlage, dazu die Kabelspalte, Anschriften im Feld."""
        vorlage = Blattvorlagen.laden(mitgeliefert() / "blattvorlagen").holen("beispiel")
        felder = [spalte.feld for spalte in vorlage.spalten]
        self.assertEqual(
            felder,
            ["stift", "ader", "farbe", "bezeichnung", "rangierung", "bemerkung",
             "kabel"],
        )
        # Sie ist schmal und quer - so nimmt sie den breiten nichts weg.
        self.assertTrue(vorlage.kabel_gedreht)
        self.assertLess(
            vorlage.spalte("kabel").anteil, vorlage.spalte("bemerkung").anteil / 3
        )
        self.assertEqual(
            vorlage.schriftfeld,
            (
                ("verteiler", "verteilernummer", "leiste"),
                ("erstellt", "stand", "geprueft"),
                ("firma", "kunde"),
            ),
        )
        self.assertEqual(vorlage.schriftfeld_art, "beispiel")
        # Für zwei Anschriften braucht das Schriftfeld mehr Höhe.
        self.assertGreater(vorlage.schriftfeld_hoehe, STANDARD.schriftfeld_hoehe)

    def test_standard_steht_vorn(self):
        self.assertEqual(self.vorlagen.standard.id, "standard")
        self.assertEqual(self.vorlagen.alle[0].id, "standard")

    def test_standard_entspricht_den_vorgaben(self):
        """Die mitgelieferte Datei darf das eingebaute Blatt nicht verändern.

        Geprüft wird die beiliegende Datei, nicht die im Arbeitsordner:
        die darf der Anwender ändern, ohne dass ein Test darüber klagt.
        """
        beiliegend = Blattvorlagen.laden(mitgeliefert() / "blattvorlagen")
        datei = beiliegend.holen("standard")
        for feld in ("rand", "schriftfeld_hoehe", "zeilenhoehe_max", "schrift_normal"):
            self.assertEqual(getattr(datei, feld), getattr(STANDARD, feld), feld)
        self.assertEqual(datei.spalten, STANDARD.spalten)

    def test_kabelspalte_steht_quer_und_schmal(self):
        """Die Kabelspalte ist schmal - der Name steht quer darin."""
        beiliegend = Blattvorlagen.laden(mitgeliefert() / "blattvorlagen")
        standard = beiliegend.holen("standard")
        self.assertTrue(standard.kabel_gedreht)
        self.assertLess(standard.spalte("kabel").anteil,
                        standard.spalte("bezeichnung").anteil / 2)
        # Wo die Spalte breit ist, bleibt der Name waagerecht.
        self.assertFalse(beiliegend.holen("knapp").kabel_gedreht)

    def test_keine_mitgelieferte_vorlage_zeigt_da_nummern(self):
        """Die Zahlen 1 bis 10 in jeder Zelle waren mehr Raster als Auskunft."""
        for vorlage in Blattvorlagen.laden(mitgeliefert() / "blattvorlagen").alle:
            with self.subTest(vorlage=vorlage.id):
                self.assertFalse(vorlage.da_nummern)

    def test_die_eingebaute_ist_immer_dabei(self):
        with tempfile.TemporaryDirectory() as leer:
            vorlagen = Blattvorlagen.laden(pathlib.Path(leer))
        self.assertEqual([v.id for v in vorlagen.alle], ["standard"])

    def test_spaeterer_ordner_gewinnt(self):
        with tempfile.TemporaryDirectory() as eigen:
            (pathlib.Path(eigen) / "knapp.yaml").write_text(
                "id: knapp\nname: Mein Knapp\n", encoding="utf-8"
            )
            vorlagen = Blattvorlagen.aus_ordnern(
                [blattvorlagenordner(), pathlib.Path(eigen)]
            )
        self.assertEqual(vorlagen.holen("knapp").name, "Mein Knapp")


class TestWirkungAufDasBlatt(unittest.TestCase):
    def setUp(self):
        self.projekt = _projekt()
        self.vorlagen = Blattvorlagen.laden(blattvorlagenordner())

    def test_knapp_laesst_bezeichnung_und_bemerkung_weg(self):
        knapp = self.vorlagen.holen("knapp")
        texte = _texte(leistenblatt(self.projekt, 1, knapp))
        self.assertNotIn("Bemerkung", texte)
        self.assertNotIn("Magnetkontakt", texte)
        self.assertIn("Rangierung", texte)
        self.assertIn("Kabel", texte)

    def test_standard_zeigt_alles(self):
        texte = _texte(leistenblatt(self.projekt, 1, STANDARD))
        self.assertIn("Magnetkontakt", texte)
        self.assertIn("Linie", texte)

    def test_eine_bucht_je_blatt_ergibt_mehr_blaetter(self):
        """Bei zwei Buchten: Standard ein Belegungsblatt, Ausführlich zwei."""
        ausfuehrlich = self.vorlagen.holen("ausfuehrlich")
        zwei = Projekt(verteiler=Verteiler.aus_geometrie(2, 4, 10))
        with_standard = blaetter(zwei, STANDARD)
        with_ausf = blaetter(zwei, ausfuehrlich)
        self.assertEqual(len(with_standard) + 1, len(with_ausf))
        self.assertEqual(with_ausf[1].titel, "Bucht 1")

    def test_ohne_kabelspalte_keine_klammer(self):
        ohne = Blattvorlage(
            id="ohne", name="Ohne Kabel", spalten=STANDARD.spalten[:5]
        )
        blatt = leistenblatt(self.projekt, 1, ohne)
        gefuellt = [e for e in blatt.elemente if isinstance(e, Rechteck) and e.fuellung]
        # Nur noch die Kopfzeile ist gefüllt, keine Kabelklammer.
        self.assertEqual(len(gefuellt), 1)

    def test_tabelle_bleibt_auf_dem_blatt(self):
        for vorlage in self.vorlagen.alle:
            for blatt in blaetter(self.projekt, vorlage):
                with self.subTest(vorlage=vorlage.id, blatt=blatt.titel):
                    for element in blatt.elemente:
                        rechts = getattr(element, "x", 0) + getattr(element, "breite", 0)
                        self.assertLessEqual(rechts, blatt.breite - vorlage.rand + 0.01)

    def test_eigene_vorlage_steht_auf_dem_deckblatt(self):
        """Wer nicht die Standardvorlage nimmt, soll es dem Blatt ansehen."""
        knapp = self.vorlagen.holen("knapp")
        self.assertIn(knapp.name, _texte(blaetter(self.projekt, knapp)[0]))
        self.assertNotIn(
            "Standard", _texte(blaetter(self.projekt, STANDARD)[0])
        )


if __name__ == "__main__":
    unittest.main()
