"""Tests zu Vorlagen und Kabeltypen.

Massstab sind die Mustertabellen: die automatische Vorbefuellung muss
dieselben Farben erzeugen, die dort von Hand eingetragen sind.
"""

import pathlib
import tempfile
import unittest

from verteilerly.farbcodes import KabeltypFehler, Kabeltypen, farben_eintragen
from verteilerly.modell import Verteiler
from verteilerly.vorlagen import Vorlagen, VorlagenFehler, vorlage_aus_yaml

DATEN = pathlib.Path(__file__).resolve().parent.parent / "daten"


class TestVorlagen(unittest.TestCase):
    def setUp(self):
        self.vorlagen = Vorlagen.laden(DATEN / "vorlagen")

    def test_alle_drei_beispiele_vorhanden(self):
        self.assertEqual(len(self.vorlagen), 3)
        for kennung in ("40da-4x10", "40da-2x20", "120da-2x6x10"):
            self.assertIn(kennung, self.vorlagen)

    def test_masse_stimmen(self):
        self.assertEqual(self.vorlagen.holen("120da-2x6x10").da_gesamt, 120)
        self.assertEqual(self.vorlagen.holen("120da-2x6x10").leisten_gesamt, 12)
        self.assertEqual(self.vorlagen.holen("40da-2x20").leisten_gesamt, 2)

    def test_default_vorlage(self):
        """Eine Vorlage ist als Standard gekennzeichnet."""
        self.assertEqual(self.vorlagen.standard.id, "40da-4x10")

    def test_vorlage_baut_verteiler(self):
        v = self.vorlagen.holen("120da-2x6x10").verteiler("Name", "1.1")
        self.assertEqual(v.da_gesamt, 120)
        self.assertEqual(v.name, "Name")

    def test_sortierung_nach_groesse(self):
        self.assertEqual([v.da_gesamt for v in self.vorlagen.alle], [40, 40, 120])

    def test_unvollstaendige_vorlage_abgelehnt(self):
        with self.assertRaises(VorlagenFehler):
            vorlage_aus_yaml({"id": "x", "name": "X"}, "x.yaml")

    def test_unsinnige_masse_abgelehnt(self):
        with self.assertRaises(VorlagenFehler):
            vorlage_aus_yaml(
                {"id": "x", "name": "X", "reihen": 0,
                 "leisten_je_reihe": 4, "da_je_leiste": 10}
            )

    def test_eigene_vorlage_aus_dem_ordner(self):
        """Eine neue Datei genuegt, keine Programmaenderung."""
        with tempfile.TemporaryDirectory() as ordner:
            pfad = pathlib.Path(ordner) / "eigen.yaml"
            pfad.write_text(
                "id: eigen\nname: Eigener\nreihen: 3\n"
                "leisten_je_reihe: 2\nda_je_leiste: 20\n",
                encoding="utf-8",
            )
            geladen = Vorlagen.laden(pathlib.Path(ordner))
            self.assertEqual(geladen.holen("eigen").da_gesamt, 120)


class TestKabeltypen(unittest.TestCase):
    def setUp(self):
        self.typen = Kabeltypen.laden(DATEN / "kabeltypen")

    def test_jystyv_4x2_wie_im_beispiel(self):
        """Leiste 1 aus der rangierten Mustertabelle."""
        typ = self.typen.holen("jystyv")
        self.assertEqual(
            [typ.farben(da, 8) for da in range(1, 5)],
            [("rt", "bl"), ("ws", "ge"), ("ws", "gn"), ("ws", "br")],
        )

    def test_jystyv_2x2_sonderfall(self):
        """Leiste 3 aus dem Beispiel: erste b-Ader sw statt bl."""
        typ = self.typen.holen("jystyv")
        self.assertEqual(
            [typ.farben(da, 2) for da in range(1, 3)],
            [("rt", "sw"), ("ws", "ge")],
        )

    def test_jystyv_zweite_lage_wiederholt_sich(self):
        typ = self.typen.holen("jystyv")
        self.assertEqual(typ.farben(6, 20), ("rt", "bl"))
        self.assertEqual(typ.farben(10, 20), ("ws", "sw"))

    def test_sternvierer_ringe(self):
        typ = self.typen.holen("fernmeldekabel")
        self.assertEqual(typ.farben(1), ("rt", "rt·"))
        self.assertEqual(typ.farben(2), ("rt··", "rt:"))
        self.assertEqual(typ.farben(3)[0], "gn")   # naechster Vierer
        self.assertEqual(typ.farben(11)[0], "rt")  # Zehnerbuendel voll

    def test_din47100_paarweise(self):
        typ = self.typen.holen("din47100")
        self.assertEqual(typ.farben(1), ("ws", "br"))
        self.assertEqual(typ.farben(22), ("bl-sw", "rt-sw"))
        self.assertEqual(typ.farben(23), ("ws", "br"))  # Code beginnt erneut

    def test_unbekannter_typ(self):
        with self.assertRaises(KabeltypFehler):
            self.typen.holen("gibtsnicht")

    def test_kuerzelverzeichnis(self):
        self.assertEqual(self.typen.kuerzel["rt"], "rot")
        self.assertEqual(self.typen.kuerzel["ws"], "weiss")


class TestFarbenEintragen(unittest.TestCase):
    def setUp(self):
        self.typen = Kabeltypen.laden(DATEN / "kabeltypen")
        self.v = Verteiler.aus_geometrie(1, 4, 10)

    def test_beispiel_wird_reproduziert(self):
        """Dieselben Farben wie von Hand in der Mustertabelle."""
        kabel = self.v.kabel_anlegen("4DA zu Wohnzimmer", 1, 1, 4, kabeltyp="jystyv")
        self.assertEqual(farben_eintragen(self.v, kabel, self.typen), 8)
        leiste = self.v.leiste(1)
        self.assertEqual(
            [(leiste.stift(n).a.farbe, leiste.stift(n).b.farbe) for n in range(1, 5)],
            [("rt", "bl"), ("ws", "ge"), ("ws", "gn"), ("ws", "br")],
        )
        self.assertEqual(leiste.stift(5).a.farbe, "")

    def test_handeintrag_bleibt_stehen(self):
        """Die Automatik ist Vorschlag, nicht Sperre."""
        kabel = self.v.kabel_anlegen("4DA", 1, 1, 4, kabeltyp="jystyv")
        self.v.leiste(1).stift(1).a.farbe = "vi"
        farben_eintragen(self.v, kabel, self.typen)
        self.assertEqual(self.v.leiste(1).stift(1).a.farbe, "vi")
        farben_eintragen(self.v, kabel, self.typen, ueberschreiben=True)
        self.assertEqual(self.v.leiste(1).stift(1).a.farbe, "rt")

    def test_ohne_kabeltyp_bleibt_leer(self):
        kabel = self.v.kabel_anlegen("ohne Typ", 1, 1, 4)
        self.assertEqual(farben_eintragen(self.v, kabel, self.typen), 0)
        self.assertEqual(self.v.leiste(1).stift(1).a.farbe, "")

    def test_farben_laufen_ueber_den_leistenwechsel_durch(self):
        """Die Kabel-DA zaehlt ueber die Fortsetzung hinweg weiter."""
        from verteilerly.modell import Kabelabschnitt

        kabel = self.v.kabel_anlegen_mehrteilig(
            "6DA ueber zwei Leisten",
            [Kabelabschnitt(1, 9, 2), Kabelabschnitt(2, 1, 4)],
            kabeltyp="jystyv",
        )
        farben_eintragen(self.v, kabel, self.typen)
        # DA 1-2 auf Leiste 1, DA 3-6 auf Leiste 2 - ohne Neubeginn der Folge.
        self.assertEqual(self.v.leiste(1).stift(9).b.farbe, "bl")
        self.assertEqual(self.v.leiste(1).stift(10).b.farbe, "ge")
        self.assertEqual(self.v.leiste(2).stift(1).b.farbe, "gn")
        self.assertEqual(self.v.leiste(2).stift(4).b.farbe, "bl")


if __name__ == "__main__":
    unittest.main()
