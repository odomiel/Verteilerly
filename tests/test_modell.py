"""Tests zum Datenmodell."""

import unittest

from verteilerly import modell, schreibweisen
from verteilerly.modell import (
    RANGIERVORLAGEN,
    Aderadresse,
    Kabelabschnitt,
    ModellFehler,
    Projekt,
    UeberlaufFehler,
    Verteiler,
    adressen_lesen,
    adressen_schreiben,
)


class TestGeometrie(unittest.TestCase):
    def test_mustermasse(self):
        """Die drei Muster ergeben ihre bekannte DA-Zahl."""
        for buchten, leisten, da, erwartet in [
            (1, 4, 10, 40),   # 40 DA in vier Leisten
            (1, 2, 20, 40),   # 40 DA in zwei Leisten
            (2, 6, 10, 120),  # 120 DA in zwei Buchten
        ]:
            with self.subTest(geometrie=(buchten, leisten, da)):
                self.assertEqual(
                    Verteiler.aus_geometrie(buchten, leisten, da).da_gesamt, erwartet
                )

    def test_leisten_laufen_ueber_buchten_durch(self):
        """Bucht 1 traegt Leiste 1-6, Bucht 2 die Leisten 7-12."""
        v = Verteiler.aus_geometrie(2, 6, 10)
        self.assertEqual([l.nummer for l in v.buchten[0].leisten], list(range(1, 7)))
        self.assertEqual([l.nummer for l in v.buchten[1].leisten], list(range(7, 13)))

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

    def test_liest_jede_schreibweise(self):
        """Getippt werden darf jede Form, gleich welche eingestellt ist."""
        gemeint = Aderadresse(3, 2, "a")
        for text in ["3 2a", "L3 2a", "L3-2a", "l3-2a", "3-2a"]:
            with self.subTest(text=text):
                self.assertEqual(Aderadresse.parse(text), gemeint)

    def test_schreibt_in_der_gewaehlten_schreibweise(self):
        adresse = Aderadresse(3, 2, "a")
        self.assertEqual(adresse.anzeige(schreibweisen.EINFACH), "3 2a")
        self.assertEqual(adresse.anzeige(schreibweisen.STRICH), "3-2a")
        self.assertEqual(adresse.anzeige(schreibweisen.MIT_L), "L3 2a")
        self.assertEqual(adresse.anzeige(schreibweisen.MIT_STRICH), "L3-2a")
        # Ohne Angabe bleibt es bei der Grundform - so steht es auch in
        # der Projektdatei.
        self.assertEqual(adresse.anzeige(), str(adresse))

    def test_unlesbares_abgelehnt(self):
        for text in ["", "3", "3 2c", "abc", "3 2a x"]:
            with self.subTest(text=text), self.assertRaises(ModellFehler):
                Aderadresse.parse(text)

    def test_die_leiste_darf_ihr_buchstabe_sein(self):
        """Wer Buchstaben eingestellt hat, tippt auch welche."""
        self.assertEqual(Aderadresse.parse("C 2a"), Aderadresse(3, 2, "a"))
        self.assertEqual(Aderadresse.parse("c-2a"), Aderadresse(3, 2, "a"))
        # Ein einzelnes L ist die Leiste, kein Zierat - mit Nummer dahinter
        # bleibt es der Zierat.
        self.assertEqual(Aderadresse.parse("L 2a"), Aderadresse(12, 2, "a"))
        self.assertEqual(Aderadresse.parse("L3 2a"), Aderadresse(3, 2, "a"))

    def test_buchstaben_stehen_auch_in_der_anzeige(self):
        from verteilerly.modell import LEISTEN_BUCHSTABEN

        adresse = Aderadresse(3, 2, "a")
        self.assertEqual(
            adresse.anzeige(schreibweisen.MIT_L, LEISTEN_BUCHSTABEN), "LC 2a"
        )
        self.assertEqual(adresse.anzeige(None, LEISTEN_BUCHSTABEN), "C 2a")
        # Gespeichert wird weiter die Nummer.
        self.assertEqual(str(adresse), "3 2a")


class TestLeistennamen(unittest.TestCase):
    """Leisten heißen 1, 2, 3 - oder A, B, C."""

    def test_aus_der_nummer_wird_ein_buchstabe(self):
        from verteilerly.modell import LEISTEN_BUCHSTABEN, leistenname

        namen = [leistenname(n, LEISTEN_BUCHSTABEN) for n in (1, 3, 26, 27, 28, 53)]
        self.assertEqual(namen, ["A", "C", "Z", "AA", "AB", "BA"])
        # Gezählt bleibt gezählt.
        self.assertEqual(leistenname(3), "3")

    def test_und_wieder_zurueck(self):
        from verteilerly.modell import (
            LEISTEN_BUCHSTABEN,
            leistenname,
            leistennummer,
        )

        for nummer in (1, 2, 26, 27, 100):
            with self.subTest(nummer=nummer):
                self.assertEqual(
                    leistennummer(leistenname(nummer, LEISTEN_BUCHSTABEN)), nummer
                )
        self.assertEqual(leistennummer("12"), 12)
        self.assertEqual(leistennummer("c"), 3)

    def test_was_keine_leiste_ist_wird_abgewiesen(self):
        from verteilerly.modell import leistennummer

        for text in ("", "  ", "A1", "-", "Ä"):
            with self.subTest(text=text), self.assertRaises(ModellFehler):
                leistennummer(text)

    def test_das_projekt_kennt_seine_schreibweise(self):
        from verteilerly.modell import LEISTEN_BUCHSTABEN, Projekt

        projekt = Projekt(verteiler=Verteiler.aus_geometrie(1, 2, 10))
        self.assertEqual(projekt.leistenname(2), "2")
        projekt.leisten_schreibweise = LEISTEN_BUCHSTABEN
        self.assertEqual(projekt.leistenname(2), "B")


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


class TestAdresstexte(unittest.TestCase):
    """Die Rangierspalte wird getippt - Text hin und zurueck."""

    def test_zwei_adressen_lesen(self):
        self.assertEqual(
            adressen_lesen("3 2a   5 4a"),
            [Aderadresse(3, 2, "a"), Aderadresse(5, 4, "a")],
        )

    def test_leerer_text_ergibt_nichts(self):
        self.assertEqual(adressen_lesen("   "), [])

    def test_schreiben_ist_die_umkehrung(self):
        text = "3 2a   5 4b"
        self.assertEqual(adressen_schreiben(adressen_lesen(text)), text)

    def test_fremder_text_wird_abgewiesen(self):
        for text in ["3 2a xyz", "Leiste 3", "3 2c"]:
            with self.subTest(text=text), self.assertRaises(ModellFehler):
                adressen_lesen(text)


class TestVermerk(unittest.TestCase):
    """Im Rangierfeld darf auch ein Freitext stehen."""

    def setUp(self):
        self.v = Verteiler.aus_geometrie(1, 4, 10)
        self.a = Aderadresse.parse("1 1a")
        self.b = Aderadresse.parse("3 2a")

    def test_vermerk_steht_neben_dem_ziel(self):
        self.v.rangierung_anlegen(self.a, self.b)
        self.v.vermerk_setzen(self.a, "zur Klemmleiste")
        self.assertEqual(
            self.v.rangiereintraege(self.a), ["3 2a", "zur Klemmleiste"]
        )
        self.assertEqual(self.v.rangierfeld(self.a), "3 2a   zur Klemmleiste")

    def test_vermerk_behaelt_sein_feld(self):
        """Die Einträge tauschen die Plätze nicht."""
        self.v.vermerk_setzen(self.a, "extern", zuerst=True)
        self.v.rangierung_anlegen(self.a, self.b)
        self.assertEqual(self.v.rangiereintraege(self.a), ["extern", "3 2a"])

    def test_vermerk_wird_nicht_gespiegelt(self):
        """Er meint kein Ziel - die Gegenstelle geht ihn nichts an."""
        self.v.vermerk_setzen(self.a, "extern")
        self.assertEqual(self.v.ader(self.b).vermerk, "")

    def test_ohne_freies_feld_wird_abgewiesen(self):
        self.v.rangierung_anlegen(self.a, self.b)
        self.v.rangierung_anlegen(self.a, Aderadresse.parse("4 5b"))
        with self.assertRaises(ModellFehler):
            self.v.vermerk_setzen(self.a, "passt nicht mehr")

    def test_leeren_raeumt_auch_die_stelle(self):
        self.v.vermerk_setzen(self.a, "extern", zuerst=True)
        self.v.vermerk_setzen(self.a, "")
        self.assertEqual(self.v.rangiereintraege(self.a), [])
        self.assertFalse(self.v.ader(self.a).vermerk_zuerst)

    def test_vermerk_folgt_der_schreibweise_nicht(self):
        self.v.rangierung_anlegen(self.a, self.b)
        self.v.vermerk_setzen(self.a, "extern")
        self.assertEqual(
            self.v.rangiereintraege(self.a, schreibweisen.MIT_STRICH),
            ["L3-2a", "extern"],
        )


class TestFremdeVermerke(unittest.TestCase):
    """Welche Vermerke in keiner Vorlage stehen."""

    def setUp(self):
        self.projekt = Projekt(verteiler=Verteiler.aus_geometrie(1, 2, 10))
        self.v = self.projekt.verteiler

    def _vermerk(self, adresse, text):
        self.v.vermerk_setzen(Aderadresse.parse(adresse), text)

    def test_nur_was_keine_vorlage_kennt(self):
        self._vermerk("1 1a", "direkt")
        self._vermerk("1 2a", "zur Klemmleiste")
        self.assertEqual(
            modell.fremde_vermerke(self.projekt, RANGIERVORLAGEN),
            ["zur Klemmleiste"],
        )

    def test_gross_und_klein_sind_dieselbe_vorlage(self):
        self._vermerk("1 1a", "Direkt")
        self.assertEqual(modell.fremde_vermerke(self.projekt, RANGIERVORLAGEN), [])

    def test_jeder_text_steht_nur_einmal(self):
        self._vermerk("1 1a", "n.b.")
        self._vermerk("1 2b", "n.b.")
        self._vermerk("2 3a", "extern")
        self.assertEqual(
            modell.fremde_vermerke(self.projekt, RANGIERVORLAGEN),
            ["n.b.", "extern"],
        )

    def test_ohne_vermerke_ist_nichts_zu_melden(self):
        self.assertEqual(modell.fremde_vermerke(self.projekt, RANGIERVORLAGEN), [])


class TestRangierungenSetzen(unittest.TestCase):
    """Die Spalte wird als Ganzes gesetzt, nicht Zeile fuer Zeile."""

    def setUp(self):
        self.v = Verteiler.aus_geometrie(1, 4, 10)
        self.a = Aderadresse.parse("1 1a")

    def test_setzen_legt_an_und_spiegelt(self):
        self.v.rangierungen_setzen(self.a, adressen_lesen("3 2a"))
        self.assertEqual(self.v.ziele_von(self.a), [Aderadresse.parse("3 2a")])
        self.assertEqual(self.v.ziele_von(Aderadresse.parse("3 2a")), [self.a])

    def test_kuerzen_entfernt_auch_die_gegenstelle(self):
        self.v.rangierungen_setzen(self.a, adressen_lesen("3 2a   4 5b"))
        self.v.rangierungen_setzen(self.a, adressen_lesen("3 2a"))
        self.assertEqual(self.v.ziele_von(Aderadresse.parse("4 5b")), [])

    def test_leeren_raeumt_das_feld(self):
        self.v.rangierungen_setzen(self.a, adressen_lesen("3 2a"))
        self.v.rangierungen_setzen(self.a, [])
        self.assertEqual(self.v.ziele_von(self.a), [])
        self.assertEqual(self.v.ziele_von(Aderadresse.parse("3 2a")), [])

    def test_hoechstens_zwei_je_feld(self):
        with self.assertRaises(ModellFehler):
            self.v.rangierungen_setzen(self.a, adressen_lesen("2 1a   3 1a   4 1a"))

    def test_die_folge_bleibt_wie_angegeben(self):
        """Wer das erste Feld ändert, findet es hinterher im ersten."""
        erst, dann = adressen_lesen("3 2a   4 5b")
        self.v.rangierungen_setzen(self.a, [erst, dann])
        self.assertEqual(self.v.ziele_von(self.a), [erst, dann])

        neu = adressen_lesen("2 1a")[0]
        self.v.rangierungen_setzen(self.a, [neu, dann])
        self.assertEqual(self.v.ziele_von(self.a), [neu, dann])

        self.v.rangierungen_setzen(self.a, [dann, neu])
        self.assertEqual(self.v.ziele_von(self.a), [dann, neu])

    def test_nichts_wird_halb_uebernommen(self):
        """Scheitert eine Angabe, bleibt der alte Stand vollstaendig stehen."""
        self.v.rangierungen_setzen(self.a, adressen_lesen("3 2a"))
        with self.assertRaises(ModellFehler):
            self.v.rangierungen_setzen(self.a, [Aderadresse.parse("2 1a"), self.a])
        self.assertEqual(self.v.ziele_von(self.a), [Aderadresse.parse("3 2a")])


class TestFeldauswahl(unittest.TestCase):
    """Felder abwählen, ohne sie zu löschen."""

    def setUp(self):
        from verteilerly.modell import Projekt

        self.projekt = Projekt(
            briefkopf={"firma": "Musterfirma", "kunde": "Kunde AG"},
            eigene_felder={"Standort": "Keller"},
        )

    def test_zunaechst_ist_alles_sichtbar(self):
        self.assertTrue(self.projekt.sichtbar("firma"))
        self.assertTrue(self.projekt.sichtbar("Standort"))
        self.assertEqual(self.projekt.ausgeblendet, set())

    def test_abwaehlen_behaelt_den_wert(self):
        self.projekt.sichtbarkeit_setzen("firma", False)
        self.assertFalse(self.projekt.sichtbar("firma"))
        self.assertEqual(self.projekt.feld("firma"), "Musterfirma")
        self.assertEqual(self.projekt.anzeigewert("firma"), "")

    def test_wieder_anwaehlen(self):
        self.projekt.sichtbarkeit_setzen("firma", False)
        self.projekt.sichtbarkeit_setzen("firma", True)
        self.assertEqual(self.projekt.anzeigewert("firma"), "Musterfirma")

    def test_eigene_felder_werden_gefiltert(self):
        self.assertEqual(self.projekt.sichtbare_eigene_felder(), {"Standort": "Keller"})
        self.projekt.sichtbarkeit_setzen("Standort", False)
        self.assertEqual(self.projekt.sichtbare_eigene_felder(), {})
        self.assertEqual(self.projekt.eigene_felder, {"Standort": "Keller"})


class TestEigeneFelderJeBlattart(unittest.TestCase):
    """Welche eigenen Felder ein Blatt zeigt, sagt die Blattvorlage."""

    def setUp(self):
        import dataclasses

        from verteilerly.blattvorlagen import STANDARD
        from verteilerly.modell import Projekt

        self.projekt = Projekt(eigene_felder={"Standort": "Keller"})
        self.vorlage = dataclasses.replace(STANDARD, eigene_felder=("Standort",))

    def _ersetzen(self, **felder):
        import dataclasses

        return dataclasses.replace(self.vorlage, **felder)

    def test_auf_jeder_blattart_der_vorlage(self):
        from verteilerly.modell import BLATTARTEN

        for art in BLATTARTEN:
            with self.subTest(art=art):
                self.assertEqual(
                    self.projekt.eigene_felder_hier(art, self.vorlage),
                    [("Standort", "Keller")],
                )

    def test_eine_abgewaehlte_blattart_bleibt_leer(self):
        vorlage = self._ersetzen(eigene_felder_auf=("belegung",))
        self.assertEqual(
            self.projekt.eigene_felder_hier("belegung", vorlage),
            [("Standort", "Keller")],
        )
        self.assertEqual(self.projekt.eigene_felder_hier("deckblatt", vorlage), [])
        self.assertEqual(self.projekt.eigene_felder_hier("leisten", vorlage), [])

    def test_was_die_vorlage_nicht_kennt_steht_nicht_auf_dem_blatt(self):
        """Der Inhalt bleibt trotzdem erhalten - eine andere Vorlage zeigt ihn."""
        vorlage = self._ersetzen(eigene_felder=())
        self.assertEqual(self.projekt.eigene_felder_hier("leisten", vorlage), [])
        self.assertEqual(self.projekt.eigene_felder, {"Standort": "Keller"})

    def test_ein_feld_ohne_inhalt_steht_als_leere_zeile_da(self):
        """Ein Schriftfeld darf zum Ausfüllen von Hand danebenstehen."""
        vorlage = self._ersetzen(eigene_felder=("Standort", "Monteur"))
        self.assertEqual(
            self.projekt.eigene_felder_hier("leisten", vorlage),
            [("Standort", "Keller"), ("Monteur", "")],
        )

    def test_die_reihenfolge_ist_die_der_vorlage(self):
        vorlage = self._ersetzen(eigene_felder=("Monteur", "Standort"))
        self.assertEqual(
            [name for name, _ in self.projekt.eigene_felder_hier("leisten", vorlage)],
            ["Monteur", "Standort"],
        )

    def test_abgewaehltes_feld_kommt_auch_hier_nicht(self):
        self.projekt.sichtbarkeit_setzen("Standort", False)
        self.assertEqual(self.projekt.eigene_felder_hier("belegung", self.vorlage), [])

    def test_ohne_vorlage_steht_was_das_projekt_hat(self):
        """Eine Datenliste zeichnet kein Blatt - sie nimmt den Bestand."""
        self.assertEqual(
            self.projekt.eigene_felder_hier("leisten"), [("Standort", "Keller")]
        )


class TestBeschriftungen(unittest.TestCase):
    """Eigene Wörter für die Zeilen des Schriftfeldes."""

    def setUp(self):
        from verteilerly.modell import Projekt

        self.projekt = Projekt()

    def test_ohne_eigenes_wort_gilt_die_vorgabe(self):
        self.assertEqual(self.projekt.beschriftung("kunde"), "Kunde")
        self.assertEqual(self.projekt.beschriftung("verteilernummer"), "Verteiler-Nr.")

    def test_eigenes_wort_geht_vor(self):
        self.projekt.beschriftungen["kunde"] = "Auftraggeber"
        self.assertEqual(self.projekt.beschriftung("kunde"), "Auftraggeber")

    def test_leeres_wort_faellt_auf_die_vorgabe_zurueck(self):
        self.projekt.beschriftungen["kunde"] = "   "
        self.assertEqual(self.projekt.beschriftung("kunde"), "Kunde")

    def test_unbekannte_marke_heisst_wie_sie_heisst(self):
        self.assertEqual(self.projekt.beschriftung("standort"), "standort")

    def test_gemerkt_wird_nur_die_abweichung(self):
        self.projekt.beschriftungen = {
            "kunde": "Auftraggeber", "firma": "Firma", "leiste": "  "
        }
        self.assertEqual(
            self.projekt.eigene_beschriftungen(), {"kunde": "Auftraggeber"}
        )


class TestMehrzahl(unittest.TestCase):
    """Ein Verteiler mit einer Bucht hat nicht "1 Buchten"."""

    def test_eins_bleibt_einzahl(self):
        from verteilerly.modell import mehrzahl

        self.assertEqual(mehrzahl(1, "Bucht", "Buchten"), "1 Bucht")
        self.assertEqual(mehrzahl(1, "Leiste", "Leisten"), "1 Leiste")

    def test_alles_andere_ist_mehrzahl(self):
        from verteilerly.modell import mehrzahl

        self.assertEqual(mehrzahl(0, "Bucht", "Buchten"), "0 Buchten")
        self.assertEqual(mehrzahl(2, "Bucht", "Buchten"), "2 Buchten")
        self.assertEqual(mehrzahl(12, "Leiste", "Leisten"), "12 Leisten")


class TestTextstil(unittest.TestCase):
    """Wie der Text einer Zelle gesetzt ist."""

    def setUp(self):
        from verteilerly.modell import Ader

        self.ader = Ader("a")

    def test_ohne_angabe_ist_der_stil_leer(self):
        from verteilerly.modell import Textstil

        self.assertEqual(self.ader.stil("bezeichnung"), Textstil())
        self.assertTrue(self.ader.stil("bezeichnung").leer)

    def test_setzen_und_lesen(self):
        from verteilerly.modell import Textstil

        self.ader.stil_setzen("bezeichnung", Textstil("mitte", fett=True))
        stil = self.ader.stil("bezeichnung")
        self.assertEqual(stil.ausrichtung, "mitte")
        self.assertTrue(stil.fett)
        self.assertFalse(stil.kursiv)
        # Andere Spalten bleiben unberührt.
        self.assertTrue(self.ader.stil("bemerkung").leer)

    def test_ein_leerer_stil_wird_nicht_aufgehoben(self):
        """Die Projektdatei soll nur tragen, was jemand eingestellt hat."""
        from verteilerly.modell import Textstil

        self.ader.stil_setzen("bezeichnung", Textstil("mitte"))
        self.ader.stil_setzen("bezeichnung", Textstil())
        self.assertEqual(self.ader.stile, {})

    def test_unbekanntes_feld_wird_abgelehnt(self):
        from verteilerly.modell import ModellFehler, Textstil

        with self.assertRaises(ModellFehler):
            self.ader.stil_setzen("stift", Textstil(fett=True))

    def test_unbekannte_ausrichtung_wird_abgelehnt(self):
        from verteilerly.modell import ModellFehler, Textstil

        with self.assertRaises(ModellFehler):
            Textstil("schraeg")

    def test_hin_und_zurueck_als_dict(self):
        from verteilerly.modell import Textstil

        stil = Textstil("rechts", kursiv=True)
        self.assertEqual(stil.als_dict(), {"ausrichtung": "rechts", "kursiv": True})
        self.assertEqual(Textstil.aus_dict(stil.als_dict()), stil)
        self.assertEqual(Textstil.aus_dict({}), Textstil())
        self.assertEqual(Textstil().als_dict(), {})


class TestZellenteilung(unittest.TestCase):
    """Eine Zelle als zwei Beschriftungsfelder."""

    def setUp(self):
        from verteilerly.modell import Ader

        self.ader = Ader("a")

    def test_zunaechst_ungeteilt(self):
        self.assertFalse(self.ader.teilung("bezeichnung").geteilt)
        self.assertEqual(self.ader.teilungen, {})

    def test_teilen_und_beschriften(self):
        from verteilerly.modell import Zellenteilung

        self.ader.teilung_setzen("bezeichnung", Zellenteilung(30, "Nst. 42"))
        teilung = self.ader.teilung("bezeichnung")
        self.assertTrue(teilung.geteilt)
        self.assertEqual(teilung.anteil, 30)
        self.assertEqual(teilung.text, "Nst. 42")
        self.assertFalse(self.ader.teilung("bemerkung").geteilt)

    def test_aufheben_behaelt_den_text(self):
        """Abwählen ist kein Löschen - wie bei den Feldern."""
        from dataclasses import replace
        from verteilerly.modell import Zellenteilung

        self.ader.teilung_setzen("bezeichnung", Zellenteilung(30, "Nst. 42"))
        alt = self.ader.teilung("bezeichnung")
        self.ader.teilung_setzen("bezeichnung", replace(alt, geteilt=False))
        self.assertFalse(self.ader.teilung("bezeichnung").geteilt)
        self.assertEqual(self.ader.teilung("bezeichnung").text, "Nst. 42")

    def test_ohne_text_und_ohne_teilung_bleibt_nichts_stehen(self):
        from verteilerly.modell import Zellenteilung

        self.ader.teilung_setzen("bezeichnung", Zellenteilung(30))
        self.ader.teilung_setzen("bezeichnung", Zellenteilung(geteilt=False))
        self.assertEqual(self.ader.teilungen, {})

    def test_nicht_teilbare_spalte(self):
        from verteilerly.modell import ModellFehler, Zellenteilung

        with self.assertRaises(ModellFehler):
            self.ader.teilung_setzen("farbe", Zellenteilung())

    def test_der_anteil_hat_grenzen(self):
        from verteilerly.modell import ANTEIL_MAX, ANTEIL_MIN, ModellFehler, Zellenteilung

        with self.assertRaises(ModellFehler):
            Zellenteilung(ANTEIL_MIN - 1)
        with self.assertRaises(ModellFehler):
            Zellenteilung(ANTEIL_MAX + 1)
        self.assertEqual(Zellenteilung(ANTEIL_MIN).anteil, ANTEIL_MIN)

    def test_eine_datei_mit_unsinnigem_anteil_wird_gerade_gezogen(self):
        from verteilerly.modell import ANTEIL_MAX, Zellenteilung

        self.assertEqual(Zellenteilung.aus_dict({"anteil": 300}).anteil, ANTEIL_MAX)


class TestKabelGroesseAendern(unittest.TestCase):
    """Ein aufgelegtes Kabel wächst und schrumpft am Ende."""

    def setUp(self):
        from verteilerly.modell import Verteiler

        self.v = Verteiler.aus_geometrie(1, 2, 10)
        self.kabel = self.v.kabel_anlegen("Probe", 1, 3, 4, da_gesamt=4)

    def _lage(self):
        return [(a.leiste, a.start_da, a.anzahl_da) for a in self.kabel.abschnitte]

    def test_waechst_am_ende(self):
        self.v.kabel_auflegen_aendern(self.kabel, 6)
        self.assertEqual(self._lage(), [(1, 3, 6)])
        self.assertEqual(self.kabel.da_gesamt, 6)

    def test_schrumpft_am_ende(self):
        self.v.kabel_auflegen_aendern(self.kabel, 2)
        self.assertEqual(self._lage(), [(1, 3, 2)])
        # Die Nennweite bleibt - das Kabel ist dann eben gekürzt.
        self.assertEqual(self.kabel.da_gesamt, 4)
        self.assertTrue(self.kabel.gekuerzt)

    def test_die_freien_doppeladern_sind_wieder_frei(self):
        self.v.kabel_auflegen_aendern(self.kabel, 2)
        self.assertIsNone(self.v.kabel_an(1, 5))
        self.assertIs(self.v.kabel_an(1, 4), self.kabel)

    def test_gleich_gross_aendert_nichts(self):
        self.v.kabel_auflegen_aendern(self.kabel, 4)
        self.assertEqual(self._lage(), [(1, 3, 4)])

    def test_unter_eine_doppelader_geht_nicht(self):
        from verteilerly.modell import ModellFehler

        with self.assertRaises(ModellFehler):
            self.v.kabel_auflegen_aendern(self.kabel, 0)

    def test_ueber_das_leistenende_hinaus_meldet_ueberlauf(self):
        from verteilerly.modell import UeberlaufFehler

        with self.assertRaises(UeberlaufFehler) as gefangen:
            self.v.kabel_auflegen_aendern(self.kabel, 12)
        # Ab DA 3 passen acht auf die Leiste, vier bleiben übrig.
        self.assertEqual((gefangen.exception.passend, gefangen.exception.rest), (8, 4))
        self.assertEqual(self._lage(), [(1, 3, 4)], "nichts halb geändert")

    def test_ein_fremdes_kabel_im_weg_wird_gemeldet(self):
        from verteilerly.modell import ModellFehler

        self.v.kabel_anlegen("Nachbar", 1, 8, 2)
        with self.assertRaises(ModellFehler):
            self.v.kabel_auflegen_aendern(self.kabel, 8)

    def test_verlaengern_haengt_einen_abschnitt_an(self):
        self.v.kabel_auflegen_aendern(self.kabel, 8)      # bis ans Leistenende
        self.v.kabel_verlaengern(self.kabel, 2, 1, 4)
        self.assertEqual(self._lage(), [(1, 3, 8), (2, 1, 4)])
        self.assertEqual(self.kabel.da_aufgelegt, 12)
        self.assertEqual(self.kabel.da_gesamt, 12)

    def test_die_farbfolge_laeuft_ueber_den_neuen_abschnitt_weiter(self):
        self.v.kabel_auflegen_aendern(self.kabel, 8)
        self.v.kabel_verlaengern(self.kabel, 2, 1, 2)
        stellen = self.kabel.positionen()
        self.assertEqual(stellen[0][0], 1)
        self.assertEqual(stellen[-1], (10, 2, 2))

    def test_ein_belegter_platz_nimmt_keinen_abschnitt(self):
        from verteilerly.modell import ModellFehler

        self.v.kabel_anlegen("Nachbar", 2, 1, 3)
        with self.assertRaises(ModellFehler):
            self.v.kabel_verlaengern(self.kabel, 2, 1, 2)


class TestUngleicheBuchten(unittest.TestCase):
    """Nicht jeder Verteiler ist gleichmäßig gewachsen."""

    def test_jede_bucht_ihre_eigene_groesse(self):
        from verteilerly.modell import Verteiler

        v = Verteiler.aus_buchten([(4, 10), (2, 20), (6, 8)], name="Bunt")
        self.assertEqual([len(b.leisten) for b in v.buchten], [4, 2, 6])
        self.assertEqual(
            [{l.da_anzahl for l in b.leisten} for b in v.buchten],
            [{10}, {20}, {8}],
        )
        self.assertEqual(v.da_gesamt, 4 * 10 + 2 * 20 + 6 * 8)

    def test_die_leisten_zaehlen_durch(self):
        """Über alle Buchten hinweg, auch bei ungleichen."""
        from verteilerly.modell import Verteiler

        v = Verteiler.aus_buchten([(2, 10), (3, 20)])
        self.assertEqual([l.nummer for l in v.alle_leisten], [1, 2, 3, 4, 5])
        self.assertEqual(v.leiste(3).da_anzahl, 20)

    def test_gleichmaessig_bleibt_gleichmaessig(self):
        from verteilerly.modell import Verteiler

        aus_zahlen = Verteiler.aus_geometrie(2, 3, 10)
        aus_plan = Verteiler.aus_buchten([(3, 10), (3, 10)])
        self.assertEqual(
            [(l.nummer, l.da_anzahl) for l in aus_zahlen.alle_leisten],
            [(l.nummer, l.da_anzahl) for l in aus_plan.alle_leisten],
        )

    def test_ohne_bucht_geht_es_nicht(self):
        from verteilerly.modell import ModellFehler, Verteiler

        with self.assertRaises(ModellFehler):
            Verteiler.aus_buchten([])

    def test_null_leisten_oder_null_da_werden_abgelehnt(self):
        from verteilerly.modell import ModellFehler, Verteiler

        with self.assertRaises(ModellFehler):
            Verteiler.aus_buchten([(4, 10), (0, 10)])
        with self.assertRaises(ModellFehler):
            Verteiler.aus_buchten([(4, 0)])


class TestKabelUmlegen(unittest.TestCase):
    """Ein aufgelegtes Kabel woandershin - verschieben oder kopieren."""

    def setUp(self):
        self.v = Verteiler.aus_geometrie(1, 3, 10)
        self.kabel = self.v.kabel_anlegen("Leitung", 1, 1, 4, kabeltyp="jystyv")
        ader = self.v.leiste(1).stift(2).ader("a")
        ader.bezeichnung = "Melder"
        ader.farbe = "rt"
        ader.bemerkung = "geprüft"

    def _ader(self, leiste, da, seite="a"):
        return self.v.leiste(leiste).stift(da).ader(seite)

    def test_das_kabel_liegt_danach_woanders(self):
        self.v.kabel_verschieben(self.kabel, 2, 5)
        self.assertEqual(
            [(a.leiste, a.start_da, a.anzahl_da) for a in self.kabel.abschnitte],
            [(2, 5, 4)],
        )
        self.assertIs(self.v.kabel_an(2, 5), self.kabel)
        self.assertIsNone(self.v.kabel_an(1, 1))

    def test_die_adern_ziehen_mit_um(self):
        """Was an der Ader steht, gehört dem Kabel - nicht dem Platz."""
        self.v.kabel_verschieben(self.kabel, 2, 5)
        gewandert = self._ader(2, 6)
        self.assertEqual(gewandert.bezeichnung, "Melder")
        self.assertEqual(gewandert.farbe, "rt")
        self.assertEqual(gewandert.bemerkung, "geprüft")
        # Und der alte Platz ist leer wie vor dem Auflegen.
        self.assertEqual(self._ader(1, 2).bezeichnung, "")
        self.assertEqual(self._ader(1, 2).farbe, "")

    def test_die_rangierungen_folgen_der_ader(self):
        self.v.rangierung_anlegen(Aderadresse(1, 2, "a"), Aderadresse(3, 9, "b"))
        self.v.kabel_verschieben(self.kabel, 2, 5)
        self.assertEqual(
            [(str(r.von), str(r.nach)) for r in self.v.rangierungen],
            [("2 6a", "3 9b")],
        )

    def test_auf_derselben_leiste_verrutschen(self):
        """Alter und neuer Platz überschneiden sich - nichts darf verlorengehen."""
        self.v.kabel_verschieben(self.kabel, 1, 3)
        self.assertEqual(self._ader(1, 4).bezeichnung, "Melder")
        self.assertIsNone(self.v.kabel_an(1, 1))
        self.assertIs(self.v.kabel_an(1, 6), self.kabel)

    def test_ein_mehrteiliges_kabel_wird_wieder_eines(self):
        from verteilerly.modell import Kabelabschnitt

        geteilt = self.v.kabel_anlegen_mehrteilig(
            "Zweiteilig",
            [Kabelabschnitt(1, 9, 2), Kabelabschnitt(2, 1, 2)],
        )
        self.v.kabel_verschieben(geteilt, 3, 1)
        self.assertEqual(len(geteilt.abschnitte), 1)
        self.assertEqual(geteilt.da_aufgelegt, 4)

    def test_wo_kein_platz_ist_bleibt_es_liegen(self):
        self.v.kabel_anlegen("Nachbar", 2, 5, 2)
        for leiste, start in ((2, 4), (2, 9), (3, 0)):
            with self.subTest(ziel=(leiste, start)):
                with self.assertRaises(ModellFehler):
                    self.v.kabel_verschieben(self.kabel, leiste, start)
        # Unverändert an seinem Platz.
        self.assertIs(self.v.kabel_an(1, 1), self.kabel)
        self.assertEqual(self._ader(1, 2).bezeichnung, "Melder")

    def test_kopieren_legt_ein_zweites_daneben(self):
        zwilling = self.v.kabel_kopieren(self.kabel, 3, 1, "Leitung (Kopie)")
        self.assertEqual(len(self.v.kabel), 2)
        self.assertEqual(zwilling.kabeltyp, self.kabel.kabeltyp)
        self.assertEqual(zwilling.da_gesamt, self.kabel.da_gesamt)
        # Die Adern kommen mit, die Quelle bleibt.
        self.assertEqual(self._ader(3, 2).bezeichnung, "Melder")
        self.assertEqual(self._ader(1, 2).bezeichnung, "Melder")

    def test_eine_rangierung_wird_nicht_mitkopiert(self):
        """Eine Verbindung gibt es einmal - zwei Enden, nicht vier."""
        self.v.rangierung_anlegen(Aderadresse(1, 2, "a"), Aderadresse(3, 9, "b"))
        self.v.kabel_kopieren(self.kabel, 2, 1)
        self.assertEqual(len(self.v.rangierungen), 1)

    def test_kopieren_braucht_freien_platz(self):
        with self.assertRaises(ModellFehler):
            self.v.kabel_kopieren(self.kabel, 1, 3)
        self.assertEqual(len(self.v.kabel), 1)


if __name__ == "__main__":
    unittest.main()
