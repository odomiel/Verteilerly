"""Tests zu Vorlagen und Kabeltypen.

Massstab sind die Mustertabellen: die automatische Vorbefuellung muss
dieselben Farben erzeugen, die dort von Hand eingetragen sind.
"""

import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

from verteilerly.farbcodes import (
    KabeltypFehler,
    Kabeltypen,
    farben_eintragen,
    farben_loeschen,
    farbplan,
)
from verteilerly.modell import Verteiler
from verteilerly.vorlagen import (
    Vorlage,
    Vorlagen,
    VorlagenFehler,
    kennung_bilden,
    vorlage_aus_yaml,
    vorlage_speichern,
)

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
                {"id": "x", "name": "X", "buchten": 0,
                 "leisten_je_bucht": 4, "da_je_leiste": 10}
            )

    def test_eigene_vorlage_aus_dem_ordner(self):
        """Eine neue Datei genuegt, keine Programmaenderung."""
        with tempfile.TemporaryDirectory() as ordner:
            pfad = pathlib.Path(ordner) / "eigen.yaml"
            pfad.write_text(
                "id: eigen\nname: Eigener\nbuchten: 3\n"
                "leisten_je_bucht: 2\nda_je_leiste: 20\n",
                encoding="utf-8",
            )
            geladen = Vorlagen.laden(pathlib.Path(ordner))
            self.assertEqual(geladen.holen("eigen").da_gesamt, 120)


class TestVorlageSpeichern(unittest.TestCase):
    """Eine eigene Grundstruktur wird zur Vorlage."""

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.ziel = pathlib.Path(self.ordner.name)

    def test_kennung_aus_dem_namen(self):
        self.assertEqual(kennung_bilden("120 DA — Bucht Süd (groß)"), "120-da-bucht-sued-gross")
        self.assertEqual(kennung_bilden("  "), "vorlage")

    def test_geometrie_eines_verteilers_wird_vorlage(self):
        v = Verteiler.aus_geometrie(2, 6, 10)
        vorlage = Vorlage.aus_verteiler(v, "Keller")
        self.assertEqual(
            (vorlage.buchten, vorlage.leisten_je_bucht, vorlage.da_je_leiste), (2, 6, 10)
        )
        self.assertEqual(vorlage.id, "keller")

    def test_ungleicher_verteiler_bekommt_einen_bauplan(self):
        """Was drei Zahlen nicht fassen, fasst die Liste je Bucht."""
        v = Verteiler.aus_geometrie(2, 6, 10)
        v.buchten[1].leisten.pop()
        vorlage = Vorlage.aus_verteiler(v, "Krumm")
        self.assertEqual(vorlage.bauplan, ((6, 10), (5, 10)))
        self.assertFalse(vorlage.gleichmaessig)
        self.assertEqual(vorlage.leisten_gesamt, 11)
        self.assertEqual(vorlage.da_gesamt, 110)

    def test_verschiedene_leistengroessen_je_bucht(self):
        vorlage = Vorlage.aus_verteiler(
            Verteiler.aus_buchten([(4, 10), (2, 20), (6, 8)]), "Bunt"
        )
        self.assertEqual(vorlage.bauplan, ((4, 10), (2, 20), (6, 8)))
        gebaut = vorlage.verteiler()
        self.assertEqual(
            [(len(b.leisten), b.leisten[0].da_anzahl) for b in gebaut.buchten],
            [(4, 10), (2, 20), (6, 8)],
        )

    def test_gleichmaessig_bleibt_bei_drei_zahlen(self):
        """Der Regelfall soll nicht umständlicher werden."""
        vorlage = Vorlage.aus_verteiler(Verteiler.aus_geometrie(2, 6, 10), "Glatt")
        self.assertEqual(vorlage.bauplan, ())
        self.assertTrue(vorlage.gleichmaessig)

    def test_eine_bucht_mit_gemischten_leisten_geht_nicht(self):
        """Vorerst hat jede Bucht eine Leistengröße."""
        v = Verteiler.aus_geometrie(1, 4, 10)
        v.buchten[0].leisten[2].stifte = v.buchten[0].leisten[2].stifte[:5]
        with self.assertRaises(VorlagenFehler):
            Vorlage.aus_verteiler(v, "Gemischt")

    def test_bauplan_wandert_durch_die_datei(self):
        vorlage = Vorlage.aus_verteiler(
            Verteiler.aus_buchten([(4, 10), (2, 20)]), "Bunt"
        )
        vorlage_speichern(vorlage, self.ziel)
        zurueck = Vorlagen.laden(self.ziel).holen("bunt")
        self.assertEqual(zurueck, vorlage)
        self.assertEqual(zurueck.bauplan, ((4, 10), (2, 20)))

    def test_gespeicherte_vorlage_wird_wieder_gelesen(self):
        vorlage = Vorlage.aus_verteiler(
            Verteiler.aus_geometrie(3, 4, 8), "Werkstatt", beschreibung="Halle 2"
        )
        datei = vorlage_speichern(vorlage, self.ziel)
        self.assertTrue(datei.exists())
        zurueck = Vorlagen.laden(self.ziel).holen("werkstatt")
        self.assertEqual(zurueck, vorlage)

    def test_vorhandene_vorlage_nur_auf_ansage_ueberschreiben(self):
        vorlage = Vorlage.aus_verteiler(Verteiler.aus_geometrie(1, 4, 10), "Keller")
        vorlage_speichern(vorlage, self.ziel)
        with self.assertRaises(VorlagenFehler):
            vorlage_speichern(vorlage, self.ziel)
        self.assertTrue(vorlage_speichern(vorlage, self.ziel, ueberschreiben=True))

    def test_vorlage_mit_alten_feldnamen(self):
        """Vor der Umbenennung hießen die Buchten Reihen."""
        vorlage = vorlage_aus_yaml(
            {
                "id": "alt",
                "name": "Alte Vorlage",
                "reihen": 2,
                "leisten_je_reihe": 6,
                "da_je_leiste": 10,
            },
            "alt.yaml",
        )
        self.assertEqual((vorlage.buchten, vorlage.leisten_je_bucht), (2, 6))
        self.assertEqual(vorlage.da_gesamt, 120)

    def test_aufnehmen_zeigt_die_vorlage_sofort(self):
        vorlagen = Vorlagen.laden(self.ziel)
        vorlage = Vorlage.aus_verteiler(Verteiler.aus_geometrie(1, 2, 20), "Klein")
        vorlagen.aufnehmen(vorlage)
        self.assertIn("klein", vorlagen)
        self.assertEqual(vorlagen.holen("klein"), vorlage)


class TestKabeltypen(unittest.TestCase):
    def setUp(self):
        self.typen = Kabeltypen.laden(DATEN / "kabeltypen")

    def test_jystyv_4x2_wie_im_beispiel(self):
        """Leiste 1 aus der rangierten Mustertabelle."""
        typ = self.typen.holen("jystyv")
        self.assertEqual(
            [typ.farben(da, 4) for da in range(1, 5)],
            [("rt", "bl"), ("ws", "ge"), ("ws", "gn"), ("ws", "br")],
        )

    def test_jystyv_2x2_sonderfall(self):
        """Leiste 3 aus dem Beispiel: erste b-Ader sw statt bl."""
        typ = self.typen.holen("jystyv")
        self.assertEqual(
            [typ.farben(da, 2) for da in range(1, 3)],
            [("rt", "sw"), ("ws", "ge")],
        )

    def test_jystyv_ganze_tabelle(self):
        """Die Farbtabelle des Elektronik-Kompendiums, Größe für Größe.

        Die b-Ader läuft endlos durch; rot ist die a-Ader nur, wo eine
        neue Lage beginnt - beim 10x2 also bei der 9., nicht bei der 6.
        Doppelader.
        """
        typ = self.typen.holen("jystyv")
        erwartet = {
            2: [("rt", "sw"), ("ws", "ge")],
            4: [("rt", "bl"), ("ws", "ge"), ("ws", "gn"), ("ws", "br")],
            6: [("rt", "bl"), ("ws", "ge"), ("ws", "gn"), ("ws", "br"),
                ("ws", "sw"), ("ws", "bl")],
            10: [("rt", "bl"), ("ws", "ge"), ("ws", "gn"), ("ws", "br"),
                 ("ws", "sw"), ("ws", "bl"), ("ws", "ge"), ("ws", "gn"),
                 ("rt", "br"), ("ws", "sw")],
            16: [("rt", "bl"), ("ws", "ge"), ("ws", "gn"), ("ws", "br"),
                 ("ws", "sw"), ("ws", "bl"), ("ws", "ge"), ("ws", "gn"),
                 ("ws", "br"), ("ws", "sw"), ("ws", "bl"), ("rt", "ge"),
                 ("ws", "gn"), ("ws", "br"), ("ws", "sw"), ("ws", "bl")],
            20: [("rt", "bl"), ("ws", "ge"), ("ws", "gn"), ("ws", "br"),
                 ("ws", "sw"), ("ws", "bl"), ("ws", "ge"), ("ws", "gn"),
                 ("ws", "br"), ("ws", "sw"), ("ws", "bl"), ("ws", "ge"),
                 ("ws", "gn"), ("rt", "br"), ("ws", "sw"), ("ws", "bl"),
                 ("ws", "ge"), ("ws", "gn"), ("ws", "br"), ("rt/ws", "sw")],
        }
        for gesamt, farben in erwartet.items():
            for da, (a, b) in enumerate(farben, 1):
                with self.subTest(kabel=f"{gesamt}x2", da=da):
                    self.assertEqual(typ.farben(da, gesamt), (a, b))

    def test_jystyv_die_sechste_ist_nicht_rot(self):
        """Der gemeldete Fehler: beim 10x2 ging es bei DA 6 mit rt/bl weiter."""
        typ = self.typen.holen("jystyv")
        self.assertEqual(typ.farben(6, 10), ("ws", "bl"))
        self.assertEqual(typ.farben(9, 10), ("rt", "br"))

    def test_jystyv_grosse_kabel(self):
        typ = self.typen.holen("jystyv")
        self.assertEqual(typ.farben(15, 24), ("rt", "sw"))
        self.assertEqual(typ.farben(23, 24), ("rt", "gn"))
        for da in (22, 37, 47):
            with self.subTest(da=da):
                self.assertEqual(typ.farben(da, 50), ("rt", "ge"))

    def test_lagenbeginn_haengt_an_der_kabelgroesse(self):
        typ = self.typen.holen("jystyv")
        self.assertEqual(typ.lagenbeginn(10), {1, 9})
        self.assertEqual(typ.lagenbeginn(16), {1, 12})
        self.assertEqual(typ.lagenbeginn(50), {1, 22, 37, 47})

    def test_unbekannte_groesse_wird_nicht_geraten(self):
        """Lieber nur die erste Doppelader rot als eine falsche."""
        typ = self.typen.holen("jystyv")
        self.assertFalse(typ.lagen_bekannt(12))
        self.assertEqual(typ.lagenbeginn(12), {1})
        self.assertEqual(typ.farben(9, 12), ("ws", "br"))
        self.assertTrue(typ.lagen_bekannt(10))

    def test_ohne_kabelgroesse_nur_die_erste_lage(self):
        typ = self.typen.holen("jystyv")
        self.assertEqual(typ.farben(1, None), ("rt", "bl"))
        self.assertEqual(typ.farben(9, None), ("ws", "br"))

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


class TestFarbenFolgenDemKabel(unittest.TestCase):
    """Was die Automatik gesetzt hat, darf sie auch wieder ändern."""

    def setUp(self):
        self.typen = Kabeltypen.laden(DATEN / "kabeltypen")
        self.v = Verteiler.aus_geometrie(1, 4, 10)
        self.kabel = self.v.kabel_anlegen("4DA", 1, 1, 4, kabeltyp="jystyv")
        farben_eintragen(self.v, self.kabel, self.typen)

    def _farben(self, bis=4):
        leiste = self.v.leiste(1)
        return [
            (leiste.stift(n).a.farbe, leiste.stift(n).b.farbe)
            for n in range(1, bis + 1)
        ]

    def test_abnehmen_nimmt_die_farben_mit(self):
        """Sonst stünde die alte Folge noch da, wenn die nächste aufliegt."""
        self.assertEqual(farben_loeschen(self.v, self.kabel, self.typen), 8)
        self.assertEqual(self._farben(), [("", "")] * 4)

    def test_von_hand_eingetragenes_bleibt_beim_abnehmen(self):
        self.v.leiste(1).stift(2).a.farbe = "türkis"
        farben_loeschen(self.v, self.kabel, self.typen)
        self.assertEqual(self.v.leiste(1).stift(2).a.farbe, "türkis")
        self.assertEqual(self.v.leiste(1).stift(2).b.farbe, "")

    def test_ein_neues_kabel_faerbt_die_freien_adern(self):
        farben_loeschen(self.v, self.kabel, self.typen)
        self.v.kabel_entfernen(self.kabel)
        neu = self.v.kabel_anlegen("neu", 1, 1, 4, kabeltyp="fernmeldekabel")
        farben_eintragen(self.v, neu, self.typen)
        self.assertNotEqual(self._farben()[1], ("ws", "ge"))
        self.assertTrue(all(a and b for a, b in self._farben()))

    def test_geaenderte_groesse_zieht_die_farben_nach(self):
        """Wo eine neue Lage beginnt, hängt an der Gesamtgröße."""
        lang = self.v.kabel_anlegen("10DA", 2, 1, 10, kabeltyp="jystyv", da_gesamt=10)
        farben_eintragen(self.v, lang, self.typen)
        # Bei 10 DA beginnt mit der neunten Doppelader die zweite Lage.
        self.assertEqual(self.v.leiste(2).stift(9).a.farbe, "rt")

        vorher = farbplan(self.v, lang, self.typen)
        lang.da_gesamt = 20
        gefuellt = farben_eintragen(self.v, lang, self.typen, statt=vorher)
        self.assertEqual(self.v.leiste(2).stift(9).a.farbe, "ws")
        self.assertTrue(gefuellt)

    def test_geaenderter_kabeltyp_zieht_die_farben_nach(self):
        vorher = farbplan(self.v, self.kabel, self.typen)
        self.kabel.kabeltyp = "din47100"
        farben_eintragen(self.v, self.kabel, self.typen, statt=vorher)
        self.assertNotEqual(self._farben()[0], ("rt", "bl"))

    def test_dabei_bleibt_von_hand_eingetragenes_stehen(self):
        """Die Automatik ist Vorschlag, nicht Sperre."""
        self.v.leiste(1).stift(1).a.farbe = "türkis"
        vorher = farbplan(self.v, self.kabel, self.typen)
        self.kabel.kabeltyp = "din47100"
        farben_eintragen(self.v, self.kabel, self.typen, statt=vorher)
        self.assertEqual(self.v.leiste(1).stift(1).a.farbe, "türkis")

    def test_mit_ueberschreiben_geht_auch_das(self):
        self.v.leiste(1).stift(1).a.farbe = "türkis"
        vorher = farbplan(self.v, self.kabel, self.typen)
        self.kabel.kabeltyp = "din47100"
        farben_eintragen(
            self.v, self.kabel, self.typen, ueberschreiben=True, statt=vorher
        )
        self.assertNotEqual(self.v.leiste(1).stift(1).a.farbe, "türkis")

    def test_ohne_aenderung_wird_nichts_gezaehlt(self):
        vorher = farbplan(self.v, self.kabel, self.typen)
        self.assertEqual(
            farben_eintragen(self.v, self.kabel, self.typen, statt=vorher), 0
        )

    def test_ohne_kabeltyp_gibt_es_nichts_zu_loeschen(self):
        ohne = self.v.kabel_anlegen("ohne Typ", 2, 1, 4)
        self.v.leiste(2).stift(1).a.farbe = "vi"
        self.assertEqual(farben_loeschen(self.v, ohne, self.typen), 0)
        self.assertEqual(self.v.leiste(2).stift(1).a.farbe, "vi")


class TestVorlagenVerwalten(unittest.TestCase):
    """Umbenennen, löschen, wiederherstellen."""

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.ziel = pathlib.Path(self.ordner.name)
        for datei in (DATEN / "vorlagen").glob("*.yaml"):
            shutil.copy2(datei, self.ziel)

    def _alle(self):
        return [v.id for v in Vorlagen.laden(self.ziel).alle]

    def test_loeschen_nimmt_die_datei_weg(self):
        from verteilerly.vorlagen import vorlage_loeschen

        kennung = self._alle()[0]
        self.assertTrue(vorlage_loeschen(kennung, self.ziel))
        self.assertNotIn(kennung, self._alle())
        self.assertFalse((self.ziel / f"{kennung}.yaml").exists())

    def test_loeschen_ohne_datei_sagt_das(self):
        from verteilerly.vorlagen import vorlage_loeschen

        self.assertFalse(vorlage_loeschen("gibtsnicht", self.ziel))

    def test_umbenennen_aendert_den_namen_nicht_die_kennung(self):
        from verteilerly.vorlagen import vorlage_umbenennen

        vorlage = Vorlagen.laden(self.ziel).holen(self._alle()[0])
        neu = vorlage_umbenennen(vorlage, "Mein Liebling", self.ziel)
        self.assertEqual(neu.name, "Mein Liebling")
        self.assertEqual(neu.id, vorlage.id)
        # Und es steht so in der Datei.
        zurueck = Vorlagen.laden(self.ziel).holen(vorlage.id)
        self.assertEqual(zurueck.name, "Mein Liebling")
        self.assertEqual(zurueck.da_gesamt, vorlage.da_gesamt)

    def test_ein_leerer_name_wird_abgelehnt(self):
        from verteilerly.vorlagen import vorlage_umbenennen

        vorlage = Vorlagen.laden(self.ziel).holen(self._alle()[0])
        with self.assertRaises(VorlagenFehler):
            vorlage_umbenennen(vorlage, "   ", self.ziel)

    def test_geloeschte_bleiben_beim_laden_draussen(self):
        kennung = self._alle()[0]
        uebrig = Vorlagen.aus_ordnern(
            [self.ziel], {f"vorlagen/{kennung}.yaml"}
        )
        self.assertNotIn(kennung, [v.id for v in uebrig.alle])
        self.assertTrue((self.ziel / f"{kennung}.yaml").exists())


class TestLoeschvermerke(unittest.TestCase):
    """Was gelöscht ist, legt der nächste Start nicht wieder aus."""

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.ziel = pathlib.Path(self.ordner.name) / "Verteilerly"
        self.ziel.mkdir()
        from verteilerly import pfade

        self.pfade = pfade
        flicken = mock.patch.object(
            pfade, "eigener_datenordner", return_value=self.ziel
        )
        flicken.start()
        self.addCleanup(flicken.stop)

    def test_ein_vermerk_haelt_die_datei_draussen(self):
        self.pfade.grundausstattung_auslegen()
        datei = next((self.ziel / "vorlagen").glob("*.yaml"))
        marke = f"vorlagen/{datei.name}"

        datei.unlink()
        self.pfade.loeschen_merken(marke)
        self.pfade.grundausstattung_auslegen()
        self.assertFalse(datei.exists(), "wurde wieder ausgelegt")

    def test_ohne_vermerk_kommt_sie_wieder(self):
        self.pfade.grundausstattung_auslegen()
        datei = next((self.ziel / "vorlagen").glob("*.yaml"))
        datei.unlink()
        self.pfade.grundausstattung_auslegen()
        self.assertTrue(datei.exists())

    def test_vermerke_lassen_sich_wieder_aufheben(self):
        self.pfade.loeschen_merken("vorlagen/a.yaml")
        self.pfade.loeschen_merken("blattvorlagen/b.yaml")
        self.assertEqual(self.pfade.loeschvermerke_aufheben("vorlagen"), 1)
        self.assertEqual(self.pfade.geloeschte(), {"blattvorlagen/b.yaml"})


if __name__ == "__main__":
    unittest.main()
