"""Tests zum Layoutmodell."""

import unittest

from verteilerly.blattvorlagen import MITTE, RECHTS, STANDARD, Blattvorlage
from verteilerly.layout import (
    Blatt,
    Linie,
    Rechteck,
    Text,
    blaetter,
    deckblatt,
    leistenblatt,
    verteilerbelegungen,
)

RAND = STANDARD.rand
SCHRIFTFELD_H = STANDARD.schriftfeld_hoehe
from verteilerly.modell import Aderadresse, Kabelabschnitt, Projekt, Verteiler
from . import BEISPIELVORLAGE


def _texte(blatt: Blatt) -> list[str]:
    return [e.text for e in blatt.elemente if isinstance(e, Text)]


class TestBlattfolge(unittest.TestCase):
    def test_abgewaehlte_blattarten_fehlen_und_gezaehlt_wird_der_rest(self):
        """Ohne Deckblatt beginnt die Verteilerbelegung bei Blatt 1."""
        projekt = Projekt(verteiler=Verteiler.aus_geometrie(1, 4, 10, name="Probe"))
        alle = blaetter(projekt)

        def fusszeile(blatt):
            return [e.text for e in blatt.elemente
                    if isinstance(e, Text) and e.text.startswith("Blatt ")]

        ohne_deckblatt = blaetter(projekt, blattarten={"belegung", "leisten"})
        self.assertEqual(len(ohne_deckblatt), len(alle) - 1)
        self.assertEqual(fusszeile(ohne_deckblatt[0]), [f"Blatt 1 von {len(alle) - 1}"])
        self.assertEqual(ohne_deckblatt[0].titel, alle[1].titel)

        nur_leisten = blaetter(projekt, blattarten={"leisten"})
        self.assertEqual(len(nur_leisten), 4)
        self.assertEqual(fusszeile(nur_leisten[-1]), ["Blatt 4 von 4"])
        self.assertEqual(blaetter(projekt, blattarten=set()), [])

    def test_deckblatt_belegung_dann_je_leiste_eines(self):
        """Deckblatt, Belegung, dann je Leiste ein Blatt."""
        for buchten, leisten, da, erwartet in [
            (1, 4, 10, 6),
            (1, 2, 20, 4),
            (2, 6, 10, 14),
            (4, 6, 10, 29),   # Deckblatt, vier Buchten, 24 Leistenblätter
        ]:
            with self.subTest(geometrie=(buchten, leisten, da)):
                v = Verteiler.aus_geometrie(buchten, leisten, da)
                folge = blaetter(Projekt(verteiler=v))
                self.assertEqual(len(folge), erwartet)
                self.assertEqual(folge[0].titel, "Deckblatt")
                # Eine Bucht je Blatt steht hochkant, zwei nebeneinander
                # quer.
                self.assertEqual(folge[1].quer, buchten == 2)
                self.assertEqual(folge[-1].titel, f"Leiste {buchten * leisten}")

    def test_die_belegung_fuellt_das_blatt(self):
        """Kein leerer Streifen am rechten Rand."""
        from verteilerly.layout import Rechteck

        for buchten, leisten in ((1, 4), (2, 4), (2, 10), (2, 2)):
            with self.subTest(buchten=buchten, leisten=leisten):
                projekt = Projekt(
                    verteiler=Verteiler.aus_geometrie(buchten, leisten, 10)
                )
                blatt = verteilerbelegungen(projekt)[0]
                grenze = (
                    blatt.hoehe - STANDARD.rand - STANDARD.schriftfeld_hoehe - 6
                )
                kaesten = [
                    e for e in blatt.elemente
                    if isinstance(e, Rechteck) and e.y + e.hoehe <= grenze + 0.1
                ]
                rechts = max(e.x + e.breite for e in kaesten)
                frei = blatt.breite - STANDARD.rand - rechts
                self.assertLess(frei, 10, "zu viel Luft am rechten Rand")
                self.assertGreaterEqual(frei, -0.01, "über den Rand hinaus")

    def test_die_leistenbeschriftung_steht_in_einer_flucht(self):
        """Immer am linken Rand, gleich wie breit die Spalte gerade ist."""
        for buchten, leisten in ((1, 4), (2, 4), (2, 6), (2, 12), (3, 4)):
            with self.subTest(buchten=buchten, leisten=leisten):
                projekt = Projekt(
                    verteiler=Verteiler.aus_geometrie(buchten, leisten, 10)
                )
                blatt = verteilerbelegungen(projekt)[0]
                beschriftungen = [
                    e for e in blatt.elemente
                    if isinstance(e, Text) and e.text.startswith("Leiste ")
                ]
                self.assertTrue(beschriftungen)
                for e in beschriftungen:
                    self.assertEqual(e.ausrichtung, "links")
                # Dieselbe Fluchtlinie wie Überschrift und Schriftfeld.
                self.assertAlmostEqual(
                    min(e.x for e in beschriftungen), STANDARD.rand, places=6
                )

    def test_der_kabelname_steht_mitten_im_block(self):
        """Die Auskunft des Blattes, nicht eine Fussnote in der Ecke."""
        from verteilerly.layout import (
            belegungsmasse,
            kabelbeschriftung_groesse,
            kabelfeld,
        )

        v = Verteiler.aus_geometrie(1, 4, 10)
        v.kabel_anlegen("Wohnzimmer Nord", 1, 1, 4)
        blatt = verteilerbelegungen(Projekt(verteiler=v))[0]
        name = next(
            e for e in blatt.elemente
            if isinstance(e, Text) and e.text == "Wohnzimmer Nord"
        )
        masse = belegungsmasse(v.buchten)
        block_h = masse.zelle_hoehe
        block_b = 4 * masse.zelle_breite
        self.assertEqual(name.ausrichtung, "mitte")
        self.assertTrue(name.umbruch)
        # Das Feld sitzt mittig im Block und laesst ringsum Luft: ein
        # Name von Rand zu Rand sieht vollgestopft aus.
        self.assertLess(name.breite, block_b)
        self.assertLess(name.hoehe, block_h)
        feld = kabelfeld(name.x - (block_b - name.breite) / 2,
                         name.y - (block_h - name.hoehe) / 2,
                         block_b, block_h)
        self.assertAlmostEqual(name.breite, feld.breite, places=6)
        self.assertAlmostEqual(name.hoehe, feld.hoehe, places=6)
        self.assertGreater(name.groesse, masse.schrift)
        self.assertEqual(name.groesse, kabelbeschriftung_groesse(feld.hoehe))

    def test_die_kabelschrift_bleibt_im_block(self):
        """Eine Zeile darf nicht hoeher werden als ihr Platz."""
        from verteilerly.layout import (
            PUNKT_IN_MM,
            ZEILENABSTAND,
            kabelbeschriftung_groesse,
        )

        for hoehe in (3.0, 6.0, 9.0, 22.0):
            with self.subTest(hoehe=hoehe):
                groesse = kabelbeschriftung_groesse(hoehe)
                self.assertLessEqual(groesse, STANDARD.schrift_mittel)
                if groesse > STANDARD.schrift_klein:
                    self.assertLessEqual(
                        groesse * ZEILENABSTAND * PUNKT_IN_MM, hoehe
                    )

    def test_der_name_laesst_im_block_luft(self):
        """Von Rand zu Rand sieht der Block vollgestopft aus."""
        from verteilerly.layout import kabelfeld

        for breite, hoehe in ((6.9, 22.6), (16.5, 22.6), (49.5, 9.0)):
            with self.subTest(breite=breite):
                feld = kabelfeld(10.0, 20.0, breite, hoehe)
                self.assertLessEqual(feld.breite, breite * STANDARD.fuellgrad_kabel)
                self.assertLessEqual(feld.hoehe, hoehe * STANDARD.fuellgrad_kabel)
                # Mittig: was oben fehlt, fehlt unten auch.
                self.assertAlmostEqual(
                    feld.x - 10.0, 10.0 + breite - (feld.x + feld.breite),
                    places=6,
                )
                self.assertAlmostEqual(
                    feld.y - 20.0, 20.0 + hoehe - (feld.y + feld.hoehe),
                    places=6,
                )

    def test_die_vorlage_bestimmt_die_luft_im_kabelblock(self):
        """Fuellgrad und Polster gehoeren der Blattvorlage."""
        from verteilerly.layout import kabelfeld

        eng = STANDARD.mit(fuellgrad_kabel=0.6, polster_kabel=1.5)
        weit = kabelfeld(0.0, 0.0, 16.5, 22.6)
        schmal = kabelfeld(0.0, 0.0, 16.5, 22.6, eng)
        self.assertLess(schmal.breite, weit.breite)
        self.assertAlmostEqual(schmal.breite, 16.5 * 0.6, places=6)
        # Das Polster greift, wo der Fuellgrad zu viel liesse.
        kurz = kabelfeld(0.0, 0.0, 4.0, 22.6, eng)
        self.assertAlmostEqual(kurz.breite, 4.0 - 2 * 1.5, places=6)

    def test_die_buchten_stehen_nicht_uebereinander(self):
        """Verteilt wird in die Breite, nicht gestapelt."""
        from verteilerly.layout import Rechteck

        projekt = Projekt(verteiler=Verteiler.aus_geometrie(2, 4, 10))
        blatt = verteilerbelegungen(projekt)[0]
        oben = min(
            e.y for e in blatt.elemente
            if isinstance(e, Rechteck) and e.hoehe < 30
        )
        erste_zeile = [
            e for e in blatt.elemente
            if isinstance(e, Rechteck) and abs(e.y - oben) < 0.1
        ]
        self.assertEqual(len(erste_zeile), 2, "je Bucht ein Kasten nebeneinander")

    def test_eine_bucht_steht_hochkant(self):
        """Schmal und hoch - quer bliebe die halbe Seite leer."""
        eine = verteilerbelegungen(
            Projekt(verteiler=Verteiler.aus_geometrie(1, 4, 10))
        )[0]
        zwei = verteilerbelegungen(
            Projekt(verteiler=Verteiler.aus_geometrie(2, 4, 10))
        )[0]
        self.assertFalse(eine.quer)
        self.assertGreater(eine.hoehe, eine.breite)
        self.assertTrue(zwei.quer)

    def test_ab_drei_buchten_eine_bucht_je_blatt(self):
        """Zu zweit gruppiert bliebe für die letzte ein halbes Blatt."""
        for buchten, erwartet in [(1, 1), (2, 1), (3, 3), (4, 4), (5, 5)]:
            with self.subTest(buchten=buchten):
                v = Verteiler.aus_geometrie(buchten, 4, 10)
                belegung = verteilerbelegungen(Projekt(verteiler=v))
                self.assertEqual(len(belegung), erwartet)
                # Eine Bucht je Blatt heißt hochkant.
                if buchten > 2:
                    self.assertFalse(any(b.quer for b in belegung))

    def test_lange_buchten_bekommen_eigene_blaetter(self):
        """Zwei lange Buchten nebeneinander wären nur noch Striche."""
        for leisten, erwartet in [(12, 1), (13, 1), (14, 2), (20, 2)]:
            with self.subTest(leisten=leisten):
                v = Verteiler.aus_geometrie(2, leisten, 10)
                belegung = verteilerbelegungen(Projekt(verteiler=v))
                self.assertEqual(len(belegung), erwartet)
                if erwartet > 1:
                    self.assertFalse(any(b.quer for b in belegung))
                    self.assertEqual(belegung[0].titel, "Bucht 1")

    def test_bis_zwei_buchten_bleibt_es_ein_blatt_ohne_bucht(self):
        v = Verteiler.aus_geometrie(2, 6, 10)
        belegung = verteilerbelegungen(Projekt(verteiler=v))
        self.assertEqual([b.titel for b in belegung], ["Verteilerbelegung"])

    def test_blatt_heisst_nach_seiner_bucht(self):
        v = Verteiler.aus_geometrie(5, 4, 10)
        belegung = verteilerbelegungen(Projekt(verteiler=v))
        self.assertEqual(
            [b.titel for b in belegung],
            ["Bucht 1", "Bucht 2", "Bucht 3", "Bucht 4", "Bucht 5"],
        )

    def test_zwei_buchten_teilen_sich_ein_blatt(self):
        """Nur dort steht noch der Doppelname."""
        v = Verteiler.aus_geometrie(2, 4, 10)
        belegung = verteilerbelegungen(
            Projekt(verteiler=v), Blattvorlage(id="eng", buchten_je_blatt=1)
        )
        self.assertEqual([b.titel for b in belegung], ["Bucht 1", "Bucht 2"])

    def test_jede_leiste_steht_auf_genau_einer_bucht(self):
        v = Verteiler.aus_geometrie(4, 6, 10)
        gefunden = []
        for blatt in verteilerbelegungen(Projekt(verteiler=v)):
            gefunden += [t for t in _texte(blatt) if t.startswith("Leiste ")]
        self.assertEqual(len(gefunden), len(v.alle_leisten))
        self.assertEqual(len(set(gefunden)), len(v.alle_leisten))

    def test_kopfzeile_nennt_die_bucht_des_blattes(self):
        v = Verteiler.aus_geometrie(4, 6, 10)
        blaetter_ = verteilerbelegungen(Projekt(verteiler=v))
        for nummer, blatt in enumerate(blaetter_, 1):
            with self.subTest(bucht=nummer):
                self.assertIn(f"Verteilerbelegung — Bucht {nummer}", _texte(blatt))

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


class TestQuerstrich(unittest.TestCase):
    """Ein Querstrich im Schriftfeld: eine Linie, kein Text."""

    def _blatt(self, marken):
        import dataclasses

        from verteilerly.blattvorlagen import STANDARD
        from verteilerly.layout import leistenblatt

        vorlage = dataclasses.replace(STANDARD, schriftfeld=(marken,))
        projekt = Projekt(
            verteiler=Verteiler.aus_geometrie(1, 2, 10, name="Probe"),
            briefkopf={"firma": "Musterfirma"},
        )
        return leistenblatt(projekt, 1, vorlage), vorlage, projekt

    def test_aus_der_marke_wird_eine_linie(self):
        from verteilerly.layout import STRICH, Linie

        ohne, _, _ = self._blatt(("firma", "verteiler"))
        mit, _, _ = self._blatt(("firma", "strich", "verteiler"))
        linien = lambda blatt: [e for e in blatt.elemente if isinstance(e, Linie)]
        self.assertEqual(len(linien(mit)), len(linien(ohne)) + 1)
        strich = [e for e in linien(mit) if e not in linien(ohne)]
        self.assertTrue(strich, "kein zusätzlicher Strich")
        self.assertEqual(strich[0].y1, strich[0].y2, "der Strich liegt quer")
        # Er schliesst mit der Umrandung ab, statt Luft zu lassen.
        from verteilerly.blattvorlagen import STANDARD

        self.assertAlmostEqual(strich[0].x1, STANDARD.rand, places=6)
        self.assertAlmostEqual(
            strich[0].x2, mit.breite - STANDARD.rand, places=6
        )
        # Die Marke selbst steht nirgends als Text.
        self.assertFalse([e for e in mit.elemente
                          if isinstance(e, Text) and STRICH in e.text])

    def test_in_tabellen_steht_kein_strich(self):
        from verteilerly.layout import STRICH, schriftfeldwerte

        _, vorlage, projekt = self._blatt(("firma", "strich", "verteiler"))
        werte = schriftfeldwerte(projekt, 1, vorlage)
        self.assertEqual([name for name, _ in werte if name == STRICH], [])
        self.assertEqual(len(werte), 2)


class TestEintragsausrichtung(unittest.TestCase):
    """Jede Angabe des Schriftfeldes liegt, wie ihr Eintrag es sagt."""

    def _blatt(self, ausrichtung):
        import dataclasses

        from verteilerly.blattvorlagen import STANDARD, Schriftfeldeintrag
        from verteilerly.layout import leistenblatt

        vorlage = dataclasses.replace(STANDARD, schriftfeld=(
            (Schriftfeldeintrag("firma", ausrichtung),),
        ))
        projekt = Projekt(
            verteiler=Verteiler.aus_geometrie(1, 2, 10, name="Probe"),
            briefkopf={"firma": "Musterfirma"},
        )
        return leistenblatt(projekt, 1, vorlage)

    def _wert(self, blatt):
        return next(e for e in blatt.elemente
                    if isinstance(e, Text) and e.text == "Musterfirma")

    def test_der_wert_folgt_der_ausrichtung_des_eintrags(self):
        for ausrichtung in ("links", "mitte", "rechts"):
            with self.subTest(ausrichtung=ausrichtung):
                self.assertEqual(
                    self._wert(self._blatt(ausrichtung)).ausrichtung, ausrichtung
                )

    def test_die_beschriftung_bleibt_am_linken_rand(self):
        """Ausgerichtet wird der Wert - die Beschriftung hält die Zeilen."""
        blatt = self._blatt("rechts")
        beschriftung = next(e for e in blatt.elemente
                            if isinstance(e, Text) and e.text == "Firma")
        self.assertEqual(beschriftung.ausrichtung, "links")
        self.assertLess(beschriftung.x, self._wert(blatt).x)


class TestLeistenmitBuchstaben(unittest.TestCase):
    """Heißt die Leiste A, steht A auf dem Blatt."""

    def setUp(self):
        from verteilerly.modell import LEISTEN_BUCHSTABEN

        self.projekt = Projekt(
            verteiler=Verteiler.aus_geometrie(1, 3, 10, name="Probe"),
            leisten_schreibweise=LEISTEN_BUCHSTABEN,
        )

    def test_die_blaetter_heissen_nach_der_leiste(self):
        titel = [blatt.titel for blatt in blaetter(self.projekt)]
        self.assertEqual(titel[2:], ["Leiste A", "Leiste B", "Leiste C"])

    def test_die_verteilerbelegung_beschriftet_mit_buchstaben(self):
        belegung = blaetter(self.projekt)[1]
        beschriftungen = [
            e.text for e in belegung.elemente
            if isinstance(e, Text) and e.text.startswith("Leiste")
        ]
        self.assertEqual(beschriftungen, ["Leiste A", "Leiste B", "Leiste C"])

    def test_im_schriftfeld_steht_der_buchstabe(self):
        from verteilerly.layout import schriftfeldwerte

        werte = dict(schriftfeldwerte(self.projekt, 2, blatttitel="Leiste B"))
        self.assertEqual(werte["Leiste"], "B")

    def test_eine_rangierung_zeigt_auf_dieselbe_leiste(self):
        from verteilerly.layout import zeilenwerte
        from verteilerly.modell import Aderadresse

        self.projekt.verteiler.rangierung_anlegen(
            Aderadresse(1, 1, "a"), Aderadresse(3, 2, "a")
        )
        werte = zeilenwerte(self.projekt, 1, 1, "a")
        self.assertEqual(werte["rangierung"], "C 2a")


class TestSchriftfeld(unittest.TestCase):
    """Je Blatt korrekt, nicht kopiert."""

    def setUp(self):
        import dataclasses

        from verteilerly.blattvorlagen import STANDARD, Schriftfeldeintrag

        v = Verteiler.aus_geometrie(1, 4, 10, name="Muster", nummer="V-01")
        self.projekt = Projekt(
            verteiler=v,
            briefkopf={"firma": "Musterfirma", "erstellt_am": "01.09.2026"},
            eigene_felder={"Standort": "Keller"},
        )
        # Welche eigenen Felder ein Blatt zeigt, sagt die Blattvorlage -
        # und **wo** sie stehen: jedes Feld steht mit seinem Namen in
        # genau einem Block.
        self.vorlage = dataclasses.replace(
            STANDARD,
            eigene_felder=("Standort",),
            schriftfeld=(
                *STANDARD.schriftfeld[:-1],
                (*STANDARD.schriftfeld[-1], Schriftfeldeintrag("Standort")),
            ),
        )

    def _vorlage(self, **felder):
        import dataclasses

        return dataclasses.replace(self.vorlage, **felder)

    def test_jedes_leistenblatt_traegt_seine_eigene_nummer(self):
        folge = blaetter(self.projekt, self.vorlage)
        for nummer, blatt in enumerate(folge[2:], 1):
            with self.subTest(leiste=nummer):
                self.assertIn(str(nummer), _texte(blatt))

    def test_stammdaten_stehen_auf_jedem_blatt(self):
        for blatt in blaetter(self.projekt, self.vorlage):
            with self.subTest(blatt=blatt.titel):
                self.assertIn("Musterfirma", _texte(blatt))
                self.assertIn("Muster", _texte(blatt))

    def test_eigene_felder_erscheinen(self):
        self.assertIn("Keller", _texte(blaetter(self.projekt, self.vorlage)[0]))

    def test_abgewaehltes_feld_steht_auf_keinem_blatt(self):
        """Der Wert bleibt im Projekt, das Blatt zeigt ihn nicht."""
        self.projekt.sichtbarkeit_setzen("firma", False)
        self.projekt.sichtbarkeit_setzen("Standort", False)
        for blatt in blaetter(self.projekt, self.vorlage):
            with self.subTest(blatt=blatt.titel):
                self.assertNotIn("Musterfirma", _texte(blatt))
                self.assertNotIn("Keller", _texte(blatt))
        self.assertEqual(self.projekt.briefkopf["firma"], "Musterfirma")

    def test_mit_dem_feld_geht_auch_die_beschriftung(self):
        """Eine Zeile „Kunde“ ohne Kunden wäre schlimmer als gar keine."""
        self.projekt.briefkopf["kunde"] = "Kunde AG"
        self.projekt.sichtbarkeit_setzen("kunde", False)
        self.projekt.sichtbarkeit_setzen("Standort", False)
        for blatt in blaetter(self.projekt, self.vorlage):
            with self.subTest(blatt=blatt.titel):
                self.assertNotIn("Kunde", _texte(blatt))
                self.assertNotIn("Standort", _texte(blatt))

    def test_leeres_feld_behaelt_seine_beschriftung(self):
        """Angewählt und leer heißt: hier wird von Hand eingetragen."""
        texte = _texte(leistenblatt(self.projekt, 1, self.vorlage))
        self.assertIn("Geprüft", texte)          # in den Projektdaten nicht gefüllt
        self.assertIn("Stand", texte)

    def test_paar_faellt_erst_weg_wenn_beide_haelften_weg_sind(self):
        self.projekt.sichtbarkeit_setzen("geprueft_am", False)
        self.assertIn("Geprüft", _texte(leistenblatt(self.projekt, 1, self.vorlage)))
        self.projekt.sichtbarkeit_setzen("geprueft_von", False)
        self.assertNotIn("Geprüft", _texte(leistenblatt(self.projekt, 1, self.vorlage)))

    def test_blatteigene_marken_bleiben_immer(self):
        """Verteiler, Leiste und Blatt gehören zum Blatt, nicht zu den Projektdaten."""
        for name in ("verteiler", "verteilernummer", "leiste", "blatt"):
            self.projekt.sichtbarkeit_setzen(name, False)
        texte = _texte(leistenblatt(self.projekt, 1, self.vorlage))
        self.assertIn("Verteiler", texte)
        self.assertIn("Leiste", texte)

    def test_die_belegung_fuehrt_keine_leiste(self):
        """Sie gilt allen Leisten - die Zeile bliebe leer."""
        texte = _texte(verteilerbelegungen(self.projekt, self.vorlage)[0])
        self.assertNotIn("Leiste", texte)

    def test_eigene_felder_stehen_auch_dort_an_ihrem_platz(self):
        texte = _texte(verteilerbelegungen(self.projekt, self.vorlage)[0])
        self.assertEqual(texte.count("Standort"), 1)
        self.assertEqual(texte.count("Keller"), 1)

    def test_auf_dem_deckblatt_steht_ein_eigenes_feld_auch_leer(self):
        """Die Vorlage hat die Zeile angelegt - dann gehört sie aufs Blatt."""
        from verteilerly.layout import deckblattzeilen

        vorlage = self._vorlage(eigene_felder=("Standort", "Monteur"))
        zeilen = dict(deckblattzeilen(self.projekt, vorlage))
        self.assertEqual(zeilen["Standort"], "Keller")
        self.assertIn("Monteur", zeilen, "die leere Zeile fehlte auf dem Deckblatt")
        self.assertEqual(zeilen["Monteur"], "")
        texte = _texte(deckblatt(self.projekt, vorlage))
        self.assertIn("Monteur", texte)

    def test_ein_leeres_projektdatenfeld_bleibt_dem_deckblatt_fern(self):
        """Nur die eigenen Felder stehen leer da - „Geprüft" nicht."""
        from verteilerly.layout import deckblattzeilen

        zeilen = dict(deckblattzeilen(self.projekt, self.vorlage))
        self.assertNotIn("Geprüft", zeilen)

    def test_eine_abgewaehlte_blattart_laesst_das_deckblatt_leer(self):
        from verteilerly.layout import deckblattzeilen

        vorlage = self._vorlage(eigene_felder_auf=("leisten",))
        self.assertNotIn("Standort", dict(deckblattzeilen(self.projekt, vorlage)))

    def test_ein_feld_steht_in_dem_block_in_den_es_gesetzt_wurde(self):
        """Mehrere eigene Felder lassen sich unabhängig verteilen."""
        from verteilerly.blattvorlagen import Schriftfeldeintrag
        from verteilerly.layout import schriftfeldspalten

        self.projekt.eigene_felder["Monteur"] = "Müller"
        vorlage = self._vorlage(
            eigene_felder=("Standort", "Monteur"),
            schriftfeld=(
                (Schriftfeldeintrag("firma"), Schriftfeldeintrag("Standort")),
                (Schriftfeldeintrag("verteiler"),),
                (Schriftfeldeintrag("erstellt"), Schriftfeldeintrag("Monteur")),
            ),
        )
        bloecke = [
            [name for name, _wert, _aus in block]
            for block in schriftfeldspalten(self.projekt, 1, vorlage)
        ]
        self.assertIn("Standort", bloecke[0])
        self.assertNotIn("Monteur", bloecke[0])
        self.assertIn("Monteur", bloecke[2])
        self.assertNotIn("Standort", bloecke[2])

    def test_abgewaehlte_blattart_zeigt_die_felder_nicht(self):
        """Der Inhalt bleibt, nur dieses Blatt fuehrt ihn nicht."""
        nur_leisten = self._vorlage(eigene_felder_auf=("leisten",))
        self.assertNotIn(
            "Keller", _texte(verteilerbelegungen(self.projekt, nur_leisten)[0])
        )
        self.assertNotIn("Keller", _texte(deckblatt(self.projekt, nur_leisten)))
        self.assertIn("Keller", _texte(leistenblatt(self.projekt, 1, nur_leisten)))
        self.assertEqual(self.projekt.eigene_felder["Standort"], "Keller")

    def test_leistenblatt_fuehrt_weiter_seine_leiste(self):
        texte = _texte(leistenblatt(self.projekt, 1, self.vorlage))
        self.assertIn("Leiste", texte)
        self.assertIn("Standort", texte)

    def test_halb_abgewaehltes_paar(self):
        """Erstellt am/von: fällt eine Hälfte weg, bleibt die andere."""
        self.projekt.briefkopf["erstellt_von"] = "T. Mirik"
        self.projekt.sichtbarkeit_setzen("erstellt_am", False)
        texte = " ".join(_texte(blaetter(self.projekt, self.vorlage)[0]))
        self.assertIn("T. Mirik", texte)
        self.assertNotIn("01.09.2026", texte)

    def test_leere_felder_bleiben_leer(self):
        """Ein nicht gefuelltes Feld erzeugt keinen leeren Text."""
        for blatt in blaetter(self.projekt, self.vorlage):
            self.assertNotIn("", _texte(blatt))


class TestUmgekehrteBelegung(unittest.TestCase):
    """Von rechts nach links - wie an einem Verteiler, der so belegt wird."""

    def _blatt(self, umgekehrt):
        v = Verteiler.aus_geometrie(1, 1, 10, name="Probe")
        v.kabel_anlegen("Erstes", 1, 1, 3)
        v.kabel_anlegen("Letztes", 1, 9, 2)
        projekt = Projekt(verteiler=v, belegung_umgekehrt=umgekehrt)
        return verteilerbelegungen(projekt)[0]

    def _blocke(self, blatt):
        """Je Kabel die linke Kante seines Blocks."""
        return {
            e.text: e.x for e in blatt.elemente
            if isinstance(e, Text) and e.text in ("Erstes", "Letztes")
        }

    def test_normalform_beginnt_links(self):
        stellen = self._blocke(self._blatt(False))
        self.assertLess(stellen["Erstes"], stellen["Letztes"])

    def test_umgekehrt_beginnt_rechts(self):
        stellen = self._blocke(self._blatt(True))
        self.assertGreater(stellen["Erstes"], stellen["Letztes"])

    def test_der_kasten_der_leiste_bleibt_wo_er_ist(self):
        """Gespiegelt wird der Inhalt, nicht das Blatt."""
        from verteilerly.layout import Rechteck

        kaesten = [
            max((e for e in self._blatt(u).elemente if isinstance(e, Rechteck)),
                key=lambda r: r.breite)
            for u in (False, True)
        ]
        self.assertAlmostEqual(kaesten[0].x, kaesten[1].x, places=6)
        self.assertAlmostEqual(kaesten[0].breite, kaesten[1].breite, places=6)

    def test_der_block_bleibt_so_breit_wie_seine_doppeladern(self):
        from verteilerly.layout import Rechteck

        breiten = []
        for umgekehrt in (False, True):
            blatt = self._blatt(umgekehrt)
            kaesten = sorted(
                (e for e in blatt.elemente if isinstance(e, Rechteck)),
                key=lambda r: r.breite,
            )
            breiten.append(sorted(round(r.breite, 4) for r in kaesten))
        self.assertEqual(breiten[0], breiten[1])

    def test_die_da_nummern_laufen_mit(self):
        import dataclasses

        from verteilerly.blattvorlagen import STANDARD

        vorlage = dataclasses.replace(STANDARD, da_nummern=True, zelle_breite=8.0)
        v = Verteiler.aus_geometrie(1, 1, 10, name="Probe")
        stellen = []
        for umgekehrt in (False, True):
            blatt = verteilerbelegungen(
                Projekt(verteiler=v, belegung_umgekehrt=umgekehrt), vorlage
            )[0]
            zahlen = {
                e.text: e.x for e in blatt.elemente
                if isinstance(e, Text) and e.text in ("1", "10")
            }
            stellen.append(zahlen)
        self.assertLess(stellen[0]["1"], stellen[0]["10"])
        self.assertGreater(stellen[1]["1"], stellen[1]["10"])

    def test_leistenblatt_und_adressen_bleiben_unberuehrt(self):
        """Gedreht wird nur das Bild der Belegung."""
        v = Verteiler.aus_geometrie(1, 1, 10, name="Probe")
        v.leiste(1).stift(1).a.bezeichnung = "Erste Ader"
        projekt = Projekt(verteiler=v, belegung_umgekehrt=True)
        texte = _texte(leistenblatt(projekt, 1))
        self.assertIn("Erste Ader", texte)
        # Die erste Zeile des Blattes bleibt Stift 1.
        stifte = [t for t in texte if t in ("1", "10")]
        self.assertEqual(stifte[0], "1")


class TestBriefkopffelder(unittest.TestCase):
    """Welche Projektdatenfelder eine Blattvorlage führt."""

    def _vorlage(self, *marken):
        import dataclasses

        from verteilerly.blattvorlagen import STANDARD, Schriftfeldeintrag

        return dataclasses.replace(
            STANDARD,
            schriftfeld=(tuple(Schriftfeldeintrag(m) for m in marken),),
        )

    def test_eine_marke_ein_feld(self):
        from verteilerly.layout import briefkopffelder

        self.assertEqual(
            briefkopffelder(self._vorlage("firma", "kunde")),
            ("firma", "kunde", "dokumenttitel"),
        )

    def test_eine_paarmarke_steht_fuer_ihre_felder(self):
        from verteilerly.layout import briefkopffelder

        felder = briefkopffelder(self._vorlage("erstellt"))
        self.assertIn("erstellt_am", felder)
        self.assertIn("erstellt_von", felder)

    def test_gezeichnet_bringt_auch_das_kuerzel(self):
        from verteilerly.layout import briefkopffelder

        self.assertIn("kuerzel", briefkopffelder(self._vorlage("gezeichnet")))

    def test_was_zum_blatt_gehoert_ist_kein_projektdatenfeld(self):
        from verteilerly.layout import briefkopffelder

        self.assertEqual(
            briefkopffelder(self._vorlage("verteiler", "leiste", "blatt", "strich")),
            ("dokumenttitel",),
        )

    def test_der_dokumenttitel_gilt_immer(self):
        """Er benennt das PDF und überschreibt das Deckblatt."""
        from verteilerly.layout import briefkopffelder

        self.assertIn("dokumenttitel", briefkopffelder(self._vorlage("firma")))

    def test_ein_eigenes_feld_zaehlt_nicht_mit(self):
        import dataclasses

        from verteilerly.blattvorlagen import Schriftfeldeintrag
        from verteilerly.layout import briefkopffelder

        vorlage = dataclasses.replace(
            self._vorlage("firma"),
            eigene_felder=("Auftrag",),
            schriftfeld=((Schriftfeldeintrag("firma"), Schriftfeldeintrag("Auftrag")),),
        )
        self.assertEqual(briefkopffelder(vorlage), ("firma", "dokumenttitel"))

    def test_die_reihenfolge_ist_die_der_felderliste(self):
        from verteilerly.layout import briefkopffelder
        from verteilerly.modell import BRIEFKOPF_FELDER

        felder = briefkopffelder(self._vorlage("kunde", "firma"))
        self.assertEqual(
            list(felder),
            [name for name in BRIEFKOPF_FELDER if name in felder],
        )

    def test_die_mustertabellen_fuehren_alles(self):
        """Ihr Schriftfeld steht fest im Programm."""
        import dataclasses

        from verteilerly.blattvorlagen import STANDARD
        from verteilerly.layout import briefkopffelder
        from verteilerly.modell import BRIEFKOPF_FELDER

        vorlage = dataclasses.replace(STANDARD, schriftfeld_art="beispiel")
        self.assertEqual(briefkopffelder(vorlage), BRIEFKOPF_FELDER)


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


class TestRangierfelder(unittest.TestCase):
    """Zwei Rangierungen, zwei Felder - mittig in ihrem Feld."""

    def setUp(self):
        from verteilerly.layout import rangierfelder

        self.rangierfelder = rangierfelder
        self.v = Verteiler.aus_geometrie(1, 4, 10, name="Muster")
        self.projekt = Projekt(verteiler=self.v)

    def _spaltenbreite(self) -> float:
        from verteilerly.blattvorlagen import STANDARD

        breiten = STANDARD.breiten(210.0 - 2 * STANDARD.rand)
        stelle = [s.feld for s in STANDARD.spalten].index("rangierung")
        return breiten[stelle]

    def _text(self, blatt, text):
        return next(
            e for e in blatt.elemente if isinstance(e, Text) and e.text == text
        )

    def test_jeder_eintrag_bekommt_sein_feld(self):
        self.v.rangierung_anlegen(Aderadresse.parse("1 1a"), Aderadresse.parse("2 2a"))
        self.v.rangierung_anlegen(Aderadresse.parse("1 1a"), Aderadresse.parse("3 4b"))
        self.assertEqual(
            self.rangierfelder(self.projekt, 1, 1, "a"), ["2 2a", "3 4b"]
        )

    def test_ohne_eintrag_bleiben_die_felder_leer(self):
        self.assertEqual(self.rangierfelder(self.projekt, 1, 1, "a"), ["", ""])

    def test_ein_eintrag_laesst_das_zweite_feld_frei(self):
        self.v.rangierung_anlegen(Aderadresse.parse("1 1a"), Aderadresse.parse("2 2a"))
        self.assertEqual(self.rangierfelder(self.projekt, 1, 1, "a"), ["2 2a", ""])

    def test_was_ueber_die_felder_hinausgeht_bleibt_im_letzten(self):
        """Sichtbar bleibt alles - lieber eng als verschwunden.

        Heute laesst das Modell je Ader zwei Eintraege zu; waeren es
        einmal mehr, duerfte keiner stillschweigend wegfallen.
        """
        from unittest import mock

        with mock.patch.object(
            self.v, "rangiereintraege", return_value=["2 2a", "3 4b", "4 5a"]
        ):
            felder = self.rangierfelder(self.projekt, 1, 1, "a")
        self.assertEqual(len(felder), 2)
        self.assertEqual(felder[0], "2 2a")
        self.assertIn("3 4b", felder[1])
        self.assertIn("4 5a", felder[1])

    def test_auf_dem_blatt_stehen_beide_nebeneinander(self):
        self.v.rangierung_anlegen(Aderadresse.parse("1 1a"), Aderadresse.parse("2 2a"))
        self.v.rangierung_anlegen(Aderadresse.parse("1 1a"), Aderadresse.parse("3 4b"))
        blatt = leistenblatt(self.projekt, 1)
        links = self._text(blatt, "2 2a")
        rechts = self._text(blatt, "3 4b")
        self.assertAlmostEqual(links.y, rechts.y)
        self.assertAlmostEqual(links.breite, rechts.breite, places=6)
        self.assertGreater(rechts.x, links.x + links.breite - 0.01)
        # Zusammen fuellen sie die Spalte - ohne Strich dazwischen.
        self.assertLess(
            rechts.x + rechts.breite - links.x, self._spaltenbreite()
        )
        self.assertFalse([
            e for e in blatt.elemente
            if isinstance(e, Linie) and e.x1 == e.x2
            and links.x < e.x1 < rechts.x
        ])

    def test_die_eintraege_stehen_mittig_in_ihrem_feld(self):
        self.v.rangierung_anlegen(Aderadresse.parse("1 1a"), Aderadresse.parse("2 2a"))
        blatt = leistenblatt(self.projekt, 1)
        self.assertEqual(self._text(blatt, "2 2a").ausrichtung, MITTE)

    def test_der_zellenstil_geht_vor(self):
        """Wer die Zelle ausrichtet, bestimmt - wie bei jedem Feld."""
        from verteilerly.modell import Textstil

        self.v.rangierung_anlegen(Aderadresse.parse("1 1a"), Aderadresse.parse("2 2a"))
        self.v.leiste(1).stift(1).ader("a").stil_setzen(
            "rangierung", Textstil(ausrichtung=RECHTS)
        )
        blatt = leistenblatt(self.projekt, 1)
        self.assertEqual(self._text(blatt, "2 2a").ausrichtung, RECHTS)

    def test_die_ueberschrift_bleibt_wie_die_vorlage_sie_setzt(self):
        """Mittig stehen die Werte, nicht die Spaltenueberschrift."""
        from verteilerly.blattvorlagen import STANDARD

        blatt = leistenblatt(self.projekt, 1)
        kopf = self._text(blatt, "Rangierung")
        stelle = [s.feld for s in STANDARD.spalten].index("rangierung")
        self.assertEqual(kopf.ausrichtung, STANDARD.spalten[stelle].ausrichtung)


class TestKuerzungAnzeigen(unittest.TestCase):
    """Der Zusatz am gekürzten Kabel lässt sich abschalten."""

    def _projekt(self, zeigen: bool) -> Projekt:
        v = Verteiler.aus_geometrie(1, 2, 10)
        v.kabel_anlegen("Halle Ost", 1, 1, 3, da_gesamt=6)
        projekt = Projekt(verteiler=v)
        projekt.kuerzung_zeigen = zeigen
        return projekt

    def _kabeltext(self, projekt, vorlage=STANDARD):
        blatt = leistenblatt(projekt, 1, vorlage)
        return [
            e for e in blatt.elemente
            if isinstance(e, Text) and ("Halle" in e.text or "gekürzt" in e.text)
        ]

    def test_angezeigt_steht_der_zusatz_dabei(self):
        texte = self._kabeltext(self._projekt(True))
        self.assertEqual(len(texte), 1)
        self.assertIn("gekürzt: 3 von 6 DA", texte[0].text)

    def test_abgeschaltet_steht_nur_noch_der_name(self):
        """Ohne den Zusatz bleibt mehr Platz fuer den Namen."""
        from verteilerly.layout import textzeilen

        mit = self._kabeltext(self._projekt(True))[0]
        ohne = self._kabeltext(self._projekt(False))
        self.assertEqual(len(ohne), 1)
        self.assertEqual(ohne[0].text, "Halle Ost")
        # Gesetzt wird er mindestens so gross wie mit dem Zusatz - und
        # weil er kuerzer ist, braucht er weniger Zeilen.
        self.assertGreaterEqual(textzeilen(ohne[0])[0], textzeilen(mit)[0])
        self.assertLessEqual(len(textzeilen(ohne[0])[1]), len(textzeilen(mit)[1]))

    def test_der_name_nimmt_die_groesse_die_der_block_traegt(self):
        """Ein kurzer Name stand sonst winzig in viel Weiss."""
        from verteilerly.layout import kabelbeschriftung_groesse

        v = Verteiler.aus_geometrie(1, 2, 10)
        v.kabel_anlegen("Halle Ost", 1, 1, 4)
        text = next(
            e for e in leistenblatt(Projekt(verteiler=v), 1).elemente
            if isinstance(e, Text) and "Halle" in e.text
        )
        self.assertGreater(text.groesse, STANDARD.schrift_klein)
        self.assertEqual(
            text.groesse, kabelbeschriftung_groesse(text.breite - 3, STANDARD)
        )

    def test_auch_waagerecht_bleibt_der_zusatz_weg(self):
        vorlage = STANDARD.mit(kabel_gedreht=False)
        mit = self._kabeltext(self._projekt(True), vorlage)
        self.assertEqual(len(mit), 2)        # Name und Zusatz untereinander
        ohne = self._kabeltext(self._projekt(False), vorlage)
        self.assertEqual(len(ohne), 1)
        # Ohne den Zusatz steht dem Namen der ganze Block offen.
        self.assertGreater(ohne[0].hoehe, mit[0].hoehe)

    def test_ein_schmaler_block_haengt_den_zusatz_an_den_namen(self):
        """Sonst rutschte er unter den Block, in die naechste Zeile."""
        v = Verteiler.aus_geometrie(1, 2, 10)
        v.kabel_anlegen("Halle Ost", 1, 1, 1, da_gesamt=6)
        projekt = Projekt(verteiler=v)
        projekt.kuerzung_zeigen = True
        texte = self._kabeltext(projekt, STANDARD.mit(kabel_gedreht=False))
        self.assertEqual(len(texte), 1)
        self.assertIn("gekürzt: 1 von 6 DA", texte[0].text)

    def test_auf_der_belegung_faellt_das_wort_weg(self):
        blatt = verteilerbelegungen(self._projekt(True))[0]
        texte = [e.text for e in blatt.elemente if isinstance(e, Text)]
        self.assertIn("Halle Ost (gekürzt)", texte)
        blatt = verteilerbelegungen(self._projekt(False))[0]
        texte = [e.text for e in blatt.elemente if isinstance(e, Text)]
        self.assertIn("Halle Ost", texte)
        self.assertNotIn("Halle Ost (gekürzt)", texte)

    def test_ein_ungekuerztes_kabel_merkt_nichts_davon(self):
        """Der Schalter gilt nur dort, wo der Zusatz gestanden hätte."""
        groessen = []
        for zeigen in (True, False):
            v = Verteiler.aus_geometrie(1, 2, 10)
            v.kabel_anlegen("Halle Ost", 1, 1, 3)
            projekt = Projekt(verteiler=v)
            projekt.kuerzung_zeigen = zeigen
            text = next(
                e for e in leistenblatt(projekt, 1).elemente
                if isinstance(e, Text) and "Halle" in e.text
            )
            groessen.append((text.groesse, text.hoehe))
        self.assertEqual(groessen[0], groessen[1])


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

    def test_der_name_bricht_auch_quer_um(self):
        """Ueber eine Doppelader blieb sonst ein Rest mit Punkten.

        Quer gelesen ist die Hoehe der Klammer die Laenge der Zeile und
        die Breite der Spalte der Platz, auf dem die Zeilen sich
        stapeln - ``textzeilen`` dreht beides mit.
        """
        from verteilerly.layout import PUNKT_IN_MM, ZEILENABSTAND, textzeilen

        v = Verteiler.aus_geometrie(1, 2, 10)
        v.kabel_anlegen("Melderkreis Erdgeschoss West", 1, 1, 1)
        blatt = leistenblatt(Projekt(verteiler=v), 1)
        feld = next(
            e for e in blatt.elemente
            if isinstance(e, Text) and "Melderkreis" in e.text
        )
        self.assertTrue(feld.umbruch)
        self.assertEqual(feld.zeilen_hoechstens, STANDARD.zeilen_kabel)
        groesse, zeilen = textzeilen(feld)
        self.assertEqual(len(zeilen), 2)
        self.assertEqual(" ".join(zeilen), "Melderkreis Erdgeschoss West")
        # Gestapelt wird ueber die Breite, nicht ueber die Hoehe.
        self.assertLessEqual(
            len(zeilen) * groesse * ZEILENABSTAND * PUNKT_IN_MM, feld.breite
        )

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
        from verteilerly.layout import schriftfeldanteile

        self.assertEqual(schriftfeldanteile(3), [0.38, 0.26, 0.36])
        self.assertEqual(schriftfeldanteile(3, (1.0, 1.0, 2.0)), [0.25, 0.25, 0.5])
        # Passt die Angabe nicht zur Zahl der Blöcke, bleibt es beim Augenmaß.
        self.assertEqual(schriftfeldanteile(3, (1.0, 1.0)), [0.38, 0.26, 0.36])


class TestTextstilAufDemBlatt(unittest.TestCase):
    """Der Zellenstil geht vor, die Blattvorlage bleibt Vorgabe."""

    def setUp(self):
        from verteilerly.modell import Textstil

        self.Textstil = Textstil
        self.projekt = Projekt(
            verteiler=Verteiler.aus_geometrie(1, 2, 10, name="M", nummer="1")
        )
        self.ader = self.projekt.verteiler.leiste(1).stift(1).ader("a")
        self.ader.bezeichnung = "Probe"

    def _feld(self):
        for element in leistenblatt(self.projekt, 1).elemente:
            if isinstance(element, Text) and element.text == "Probe":
                return element
        self.fail("Die Bezeichnung steht nicht auf dem Blatt")

    def test_ohne_stil_gilt_die_blattvorlage(self):
        feld = self._feld()
        self.assertEqual(feld.ausrichtung, STANDARD.spalten[3].ausrichtung)
        self.assertFalse(feld.fett)
        self.assertFalse(feld.kursiv)

    def test_der_zellenstil_geht_vor(self):
        self.ader.stil_setzen(
            "bezeichnung", self.Textstil("rechts", fett=True, kursiv=True)
        )
        feld = self._feld()
        self.assertEqual(feld.ausrichtung, "rechts")
        self.assertTrue(feld.fett)
        self.assertTrue(feld.kursiv)

    def test_nur_diese_zelle(self):
        self.ader.stil_setzen("bezeichnung", self.Textstil(fett=True))
        self.projekt.verteiler.leiste(1).stift(2).ader("a").bezeichnung = "Andere"
        andere = [
            e for e in leistenblatt(self.projekt, 1).elemente
            if isinstance(e, Text) and e.text == "Andere"
        ]
        self.assertFalse(andere[0].fett)


class TestGeteilteZelle(unittest.TestCase):
    """Zwei Beschriftungsfelder nebeneinander, ohne Trennstrich."""

    def setUp(self):
        from verteilerly.modell import Zellenteilung

        self.Zellenteilung = Zellenteilung
        self.projekt = Projekt(
            verteiler=Verteiler.aus_geometrie(1, 2, 10, name="M", nummer="1")
        )
        self.ader = self.projekt.verteiler.leiste(1).stift(1).ader("a")
        self.ader.bezeichnung = "Amt 1"

    def _felder(self, *texte):
        gefunden = {
            e.text: e for e in leistenblatt(self.projekt, 1).elemente
            if isinstance(e, Text) and e.text in texte
        }
        return [gefunden.get(t) for t in texte]

    def test_ungeteilt_steht_nur_ein_feld(self):
        self.ader.teilung_setzen("bezeichnung", self.Zellenteilung(30, "Nst. 42"))
        self.ader.teilung_setzen(
            "bezeichnung",
            self.Zellenteilung(30, "Nst. 42", geteilt=False),
        )
        links, rechts = self._felder("Amt 1", "Nst. 42")
        self.assertIsNotNone(links)
        self.assertIsNone(rechts)

    def test_geteilt_stehen_beide_nebeneinander(self):
        self.ader.teilung_setzen("bezeichnung", self.Zellenteilung(30, "Nst. 42"))
        links, rechts = self._felder("Amt 1", "Nst. 42")
        self.assertIsNotNone(rechts)
        self.assertGreater(rechts.x, links.x + links.breite - 0.01)
        self.assertAlmostEqual(rechts.y, links.y)

    def test_der_anteil_bestimmt_die_breite(self):
        self.ader.teilung_setzen("bezeichnung", self.Zellenteilung(25, "Nst. 42"))
        links, rechts = self._felder("Amt 1", "Nst. 42")
        gesamt = links.breite + rechts.breite
        self.assertAlmostEqual(rechts.breite / (gesamt + 1.0), 0.25, places=2)

    def test_zwischen_beiden_steht_kein_strich(self):
        """Auf dem Blatt soll es aussehen wie eine Zelle."""
        from verteilerly.layout import Linie

        self.ader.teilung_setzen("bezeichnung", self.Zellenteilung(30, "Nst. 42"))
        links, rechts = self._felder("Amt 1", "Nst. 42")
        oben, unten = links.y, links.y + links.hoehe
        senkrecht = [
            e for e in leistenblatt(self.projekt, 1).elemente
            if isinstance(e, Linie) and e.x1 == e.x2
            and links.x < e.x1 < rechts.x
            # Nur, was diese Zeile durchschneidet - die Spaltenstriche
            # der Tabelle und das Schriftfeld gehen uns hier nichts an.
            and min(e.y1, e.y2) < unten and max(e.y1, e.y2) > oben
        ]
        self.assertEqual(senkrecht, [])

    def test_fuer_die_tabelle_stehen_beide_hintereinander(self):
        from verteilerly.layout import zellentext

        teilung = self.Zellenteilung(30, "Nst. 42")
        self.assertEqual(zellentext("Amt 1", teilung), "Amt 1 Nst. 42")
        from dataclasses import replace

        self.assertEqual(
            zellentext("Amt 1", replace(teilung, geteilt=False)), "Amt 1"
        )


class TestAufbauzeile(unittest.TestCase):
    """Das Deckblatt zählt Buchten und Leisten in der richtigen Zahlform."""

    def _aufbau(self, buchten, leisten, da=10):
        projekt = Projekt(
            verteiler=Verteiler.aus_geometrie(buchten, leisten, da, name="M")
        )
        texte = _texte(deckblatt(projekt))
        return texte[texte.index("Aufbau") + 1]

    def test_eine_bucht_ist_eine_bucht(self):
        self.assertEqual(self._aufbau(1, 4), "1 Bucht × 4 Leisten × 10 DA")

    def test_eine_leiste_ist_eine_leiste(self):
        self.assertEqual(self._aufbau(1, 1), "1 Bucht × 1 Leiste × 10 DA")

    def test_mehrere_bleiben_mehrzahl(self):
        self.assertEqual(self._aufbau(2, 4), "2 Buchten × 4 Leisten × 10 DA")


class TestEigeneBeschriftungen(unittest.TestCase):
    """Wem „Kunde" nicht passt, schreibt „Auftraggeber" hin."""

    def setUp(self):
        self.projekt = Projekt(
            verteiler=Verteiler.aus_geometrie(1, 2, 10, name="Muster", nummer="V-01"),
            briefkopf={"kunde": "Kunde AG", "firma": "Musterfirma"},
        )

    def test_das_eigene_wort_steht_auf_dem_blatt(self):
        self.projekt.beschriftungen["kunde"] = "Auftraggeber"
        texte = _texte(leistenblatt(self.projekt, 1))
        self.assertIn("Auftraggeber", texte)
        self.assertNotIn("Kunde", texte)
        # Der Inhalt bleibt, nur die Überschrift heißt anders.
        self.assertIn("Kunde AG", texte)

    def test_auch_auf_dem_deckblatt(self):
        self.projekt.beschriftungen["kunde"] = "Auftraggeber"
        texte = _texte(deckblatt(self.projekt))
        self.assertIn("Auftraggeber", texte)
        self.assertNotIn("Kunde", texte)

    def test_ohne_eigenes_wort_bleibt_das_deckblatt_ausgeschrieben(self):
        """Dort ist Platz: „Verteilernummer", nicht „Verteiler-Nr."."""
        texte = _texte(deckblatt(self.projekt))
        self.assertIn("Verteilernummer", texte)
        self.assertIn("Verteiler-Nr.", _texte(leistenblatt(self.projekt, 1)))

    def test_auf_jedem_blatt_dasselbe_wort(self):
        self.projekt.beschriftungen["geprueft"] = "Kontrolliert"
        for blatt in blaetter(self.projekt):
            with self.subTest(blatt=blatt.titel):
                self.assertNotIn("Geprüft", _texte(blatt))

    def test_auch_in_der_beispielvorlage(self):
        """Dort stand „Verteiler:" fest im Quelltext."""
        vorlage = BEISPIELVORLAGE
        self.projekt.beschriftungen["verteiler"] = "Kasten"
        texte = _texte(leistenblatt(self.projekt, 1, vorlage))
        self.assertIn("Kasten:", texte)
        self.assertNotIn("Verteiler:", texte)

    def test_der_doppelpunkt_verdoppelt_sich_nicht(self):
        vorlage = BEISPIELVORLAGE
        self.projekt.beschriftungen["verteiler"] = "Kasten:"
        self.assertIn("Kasten:", _texte(leistenblatt(self.projekt, 1, vorlage)))


class TestSchriftfeldBeispiel(unittest.TestCase):
    """Das Schriftfeld der Mustertabellen, Feld für Feld."""

    def setUp(self):
        self.vorlage = BEISPIELVORLAGE
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

    def test_datum_und_name_bekommen_mehr_platz_als_ihre_beschriftung(self):
        """„Stand" ist ein kurzes Wort, „Max Mustermann" ein langer Name."""
        felder = {e.text: e for e in self._blatt().elemente if isinstance(e, Text)}
        for spalte in ("Datum", "Name"):
            with self.subTest(spalte=spalte):
                self.assertGreater(
                    felder[spalte].breite, felder["Erstellt"].breite
                )

    def test_der_name_wird_nicht_eingequetscht(self):
        """Ein üblicher Name muss ohne Schrumpfen hineinpassen."""
        from reportlab.pdfbase.pdfmetrics import stringWidth

        self.projekt.briefkopf["erstellt_von"] = "Max Mustermann"
        felder = {e.text: e for e in self._blatt().elemente if isinstance(e, Text)}
        noetig = stringWidth(
            "Max Mustermann", "Helvetica", self.vorlage.schrift_normal
        ) / (72 / 25.4)
        self.assertLess(noetig, felder["Max Mustermann"].breite)

    def test_beide_bloecke_auf_einer_fluchtlinie(self):
        """Matrix und Verteilerblock beginnen ihre Werte an derselben Stelle."""
        felder = {e.text: e for e in self._blatt().elemente if isinstance(e, Text)}
        self.assertEqual(felder["01.01.1970"].x, felder["Verteiler Name"].x)
        self.assertEqual(felder["Erstellt"].x, felder["Verteiler-Nr."].x)

    def test_verteilerblock_unter_der_matrix(self):
        blatt = self._blatt()
        stellen = {e.text: e.y for e in blatt.elemente if isinstance(e, Text)}
        self.assertIn("Verteiler:", stellen)
        self.assertIn("Verteiler-Nr.", stellen)
        self.assertIn("Leiste:", stellen)
        # Der Block steht unter der Matrix …
        self.assertGreater(stellen["Verteiler:"], stellen["Erstellt"])
        # … und seine Zeilen folgen aufeinander.
        self.assertGreater(stellen["Verteiler-Nr."], stellen["Verteiler:"])
        self.assertGreater(stellen["Leiste:"], stellen["Verteiler-Nr."])

    def _verteilerblock(self, blatt):
        """Oberkante und Unterkante der Zeilen in der linken unteren Haelfte."""
        from verteilerly.layout import schriftfeldanteile

        mitte = blatt.hoehe - self.vorlage.rand - self.vorlage.schriftfeld_hoehe / 2
        linkes = (blatt.breite - 2 * self.vorlage.rand) * schriftfeldanteile(
            2, self.vorlage.schriftfeld_anteile
        )[0]
        felder = [
            e for e in blatt.elemente
            if isinstance(e, Text)
            and e.y >= mitte - 0.01
            and e.x < self.vorlage.rand + linkes - 0.01
        ]
        return min(e.y for e in felder), max(e.y + e.hoehe for e in felder)

    def test_verteilerblock_steht_mittig_zwischen_den_strichen(self):
        """Weniger Zeilen als Platz: die Luft gehört oben und unten gleich."""
        blatt = self._blatt()
        mitte = blatt.hoehe - self.vorlage.rand - self.vorlage.schriftfeld_hoehe / 2
        unten = blatt.hoehe - self.vorlage.rand
        hoch, tief = self._verteilerblock(blatt)
        self.assertAlmostEqual(hoch - mitte, unten - tief, places=6)
        self.assertGreater(hoch - mitte, 0)

    def test_auch_die_belegung_steht_mittig(self):
        """Dort fehlt die Leiste, es sind also noch weniger Zeilen."""
        blatt = verteilerbelegungen(self.projekt, self.vorlage)[0]
        mitte = blatt.hoehe - self.vorlage.rand - self.vorlage.schriftfeld_hoehe / 2
        unten = blatt.hoehe - self.vorlage.rand
        hoch, tief = self._verteilerblock(blatt)
        self.assertAlmostEqual(hoch - mitte, unten - tief, places=6)
        self.assertGreater(hoch - mitte, 0)

    def test_voller_block_fuellt_die_haelfte(self):
        """Mit genug eigenen Feldern bleibt keine Luft - und nichts ragt heraus."""
        self.projekt.eigene_felder = {"Standort": "Keller", "Vertrag": "2028"}
        blatt = self._blatt()
        mitte = blatt.hoehe - self.vorlage.rand - self.vorlage.schriftfeld_hoehe / 2
        unten = blatt.hoehe - self.vorlage.rand
        hoch, tief = self._verteilerblock(blatt)
        self.assertGreaterEqual(hoch, mitte - 0.01)
        self.assertLessEqual(tief, unten + 0.01)

    def test_der_name_steht_neben_seiner_beschriftung(self):
        """Wie die übrigen Zeilen des Feldes - nicht darunter."""
        blatt = self._blatt()
        felder = {
            e.text: e for e in blatt.elemente if isinstance(e, Text)
        }
        self.assertEqual(felder["Verteiler Name"].y, felder["Verteiler:"].y)
        self.assertGreater(felder["Verteiler Name"].x, felder["Verteiler:"].x)
        # Auf derselben Fluchtlinie wie Nummer und Leiste.
        self.assertEqual(felder["Verteiler Name"].x, felder["1.1"].x)

    def test_anschriften_stehen_rechts_und_untereinander(self):
        blatt = self._blatt()
        anschrift = [
            e for e in blatt.elemente
            if isinstance(e, Text) and e.text.startswith(("Firma Beliebig",
                                                          "Beliebige Straße",
                                                          "77777"))
        ]
        self.assertEqual(len(anschrift), 3)
        # Rechts vom Verteilerblock - nicht rechts von der Blattmitte, die
        # Teilung liegt links davon - und der Reihe nach untereinander.
        verteilerblock = max(
            e.x + e.breite for e in blatt.elemente
            if isinstance(e, Text) and e.text == "Verteiler-Nr."
        )
        self.assertGreater(min(e.x for e in anschrift), verteilerblock)
        self.assertEqual([e.y for e in anschrift], sorted(e.y for e in anschrift))

    def test_anschriften_bekommen_die_groessere_haelfte(self):
        """Firma und Kunde brauchen mehr Platz als eine Verteilernummer."""
        blatt = self._blatt()
        trenner = min(
            e.x for e in blatt.elemente
            if isinstance(e, Text) and e.text.startswith("Firma Beliebig")
        )
        links = max(
            e.x for e in blatt.elemente
            if isinstance(e, Text) and e.text == "Verteiler-Nr."
        )
        self.assertLess(links, trenner)
        # Die linke Hälfte ist die kleinere - so sagt es die Vorlage.
        self.assertLess(self.vorlage.schriftfeld_anteile[0], 0.5)
        self.assertAlmostEqual(sum(self.vorlage.schriftfeld_anteile), 1.0, places=3)

    def test_die_vorlage_bestimmt_die_teilung(self):
        from verteilerly.layout import Linie

        def trennstrich(anteil):
            vorlage = self.vorlage.mit(schriftfeld_anteile=(anteil, 1 - anteil))
            blatt = leistenblatt(self.projekt, 1, vorlage)
            senkrecht = [
                e for e in blatt.elemente
                if isinstance(e, Linie) and e.y1 != e.y2 and e.y1 > 240
            ]
            return min(e.x1 for e in senkrecht)

        self.assertLess(trennstrich(0.3), trennstrich(0.7))

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


class TestBlattkopf(unittest.TestCase):
    """Über der Tabelle steht nichts mehr - das sagt das Schriftfeld."""

    def _blatt(self, vorlage=STANDARD):
        v = Verteiler.aus_geometrie(1, 2, 10, name="Probe")
        return leistenblatt(Projekt(verteiler=v), 1, vorlage)

    def test_keine_ueberschrift_ueber_der_tabelle(self):
        texte = _texte(self._blatt())
        self.assertNotIn("Leiste 1", texte[:3])
        self.assertNotIn("10 DA", texte)

    def test_die_leiste_steht_weiter_im_schriftfeld(self):
        blatt = self._blatt()
        stellen = {e.text: e.y for e in blatt.elemente if isinstance(e, Text)}
        self.assertIn("Leiste", stellen)
        self.assertGreater(stellen["Leiste"], blatt.hoehe / 2)   # unten

    def test_die_tabelle_beginnt_am_rand(self):
        blatt = self._blatt()
        kopf = [
            e for e in blatt.elemente
            if isinstance(e, Rechteck) and e.fuellung == "#E8E8E8"
        ]
        self.assertEqual(kopf[0].y, STANDARD.rand)

    def test_gewonnener_platz_geht_an_die_zeilen(self):
        """Zwölf Millimeter mehr - die Zeilen dürfen höher werden."""
        v = Verteiler.aus_geometrie(1, 2, 20)
        blatt = leistenblatt(Projekt(verteiler=v), 1)
        zeilen = [
            e for e in blatt.elemente
            if isinstance(e, Linie) and e.y1 == e.y2 and e.x1 == STANDARD.rand
        ]
        hoehen = {round(b.y1 - a.y1, 3) for a, b in zip(zeilen, zeilen[1:])}
        self.assertTrue(hoehen)
        self.assertLessEqual(max(hoehen), STANDARD.zeilenhoehe_max)


class TestKopfzeile(unittest.TestCase):
    """„Stift“ steht über der Nummer und über a und b."""

    def _kopf(self, vorlage=STANDARD):
        v = Verteiler.aus_geometrie(1, 2, 10)
        blatt = leistenblatt(Projekt(verteiler=v), 1, vorlage)
        oben = vorlage.rand
        return blatt, [
            e for e in blatt.elemente
            if isinstance(e, Text) and abs(e.y - oben) < 0.01
        ]

    def test_spalte_ohne_ueberschrift_gehoert_zur_vorigen(self):
        from verteilerly.layout import kopfgruppen

        self.assertEqual(kopfgruppen(STANDARD.spalten)[0], (0, 2))
        # Jede Spalte kommt in genau einer Gruppe vor.
        gezaehlt = sum(anzahl for _, anzahl in kopfgruppen(STANDARD.spalten))
        self.assertEqual(gezaehlt, len(STANDARD.spalten))

    def test_ueberschrift_reicht_ueber_beide_spalten(self):
        blatt, kopf = self._kopf()
        breiten = STANDARD.breiten(blatt.breite - 2 * STANDARD.rand)
        stift = [e for e in kopf if e.text == "Stift"][0]
        self.assertAlmostEqual(stift.breite, breiten[0] + breiten[1] - 3, places=3)

    def test_kein_strich_durch_die_ueberschrift(self):
        """Zwischen Nummer und a/b beginnt der Strich erst darunter."""
        blatt, _ = self._kopf()
        breiten = STANDARD.breiten(blatt.breite - 2 * STANDARD.rand)
        oben = STANDARD.rand
        x = STANDARD.rand + breiten[0]
        striche = [
            e for e in blatt.elemente
            if isinstance(e, Linie) and abs(e.x1 - x) < 0.01 and e.y1 != e.y2
        ]
        self.assertTrue(striche)
        self.assertAlmostEqual(
            min(e.y1 for e in striche), oben + STANDARD.kopfzeile_hoehe, places=3
        )
        # Vor der Farbspalte läuft der Strich dagegen ganz durch.
        x2 = STANDARD.rand + breiten[0] + breiten[1]
        durch = [
            e for e in blatt.elemente
            if isinstance(e, Linie) and abs(e.x1 - x2) < 0.01 and e.y1 != e.y2
        ]
        self.assertAlmostEqual(min(e.y1 for e in durch), oben, places=3)

    def test_gilt_fuer_jede_mitgelieferte_vorlage(self):
        from verteilerly.blattvorlagen import Blattvorlagen
        from verteilerly.layout import kopfgruppen
        from verteilerly.pfade import mitgeliefert

        for vorlage in Blattvorlagen.laden(mitgeliefert() / "blattvorlagen").alle:
            with self.subTest(vorlage=vorlage.id):
                felder = [s.feld for s in vorlage.spalten]
                if "ader" not in felder:
                    continue
                stelle = felder.index("ader")
                gruppen = dict(kopfgruppen(vorlage.spalten))
                self.assertEqual(gruppen.get(stelle - 1), 2)


class TestBelegungsblatt(unittest.TestCase):
    """Nur wo ein Kabel liegt, ist die Leiste unterteilt."""

    def _blatt(self, vorlage=STANDARD):
        v = Verteiler.aus_geometrie(1, 4, 10)
        v.kabel_anlegen("4 DA zu Wohnzimmer", 1, 1, 4)     # am Anfang
        v.kabel_anlegen("2 DA zur Garage", 2, 5, 2)        # mittendrin
        v.kabel_anlegen("3 DA zum Dach", 3, 8, 3)          # am Ende
        return verteilerbelegungen(Projekt(verteiler=v), vorlage)[0]

    def _senkrechte(self, blatt, oben: float, unten: float) -> list:
        return [
            e for e in blatt.elemente
            if isinstance(e, Linie) and e.x1 == e.x2 and oben <= e.y1 < unten
        ]

    def test_freie_flaechen_bleiben_durchgehend(self):
        """Ob am Anfang, in der Mitte oder am Ende - links und rechts
        vom Kabel steht kein Raster."""
        blatt = self._blatt()
        # Nur die Leistenkästen, nicht das Schriftfeld darunter.
        schriftfeld_oben = blatt.hoehe - STANDARD.rand - STANDARD.schriftfeld_hoehe
        kaesten = [
            e for e in blatt.elemente
            if isinstance(e, Rechteck) and not e.fuellung and e.y < schriftfeld_oben
        ]
        self.assertEqual(len(kaesten), 4)
        for kasten in kaesten:
            with self.subTest(leiste=round(kasten.y, 1)):
                self.assertEqual(
                    self._senkrechte(blatt, kasten.y, kasten.y + kasten.hoehe), []
                )

    def test_das_kabel_ist_der_einzige_block(self):
        blatt = self._blatt()
        bloecke = [e for e in blatt.elemente if isinstance(e, Rechteck) and e.fuellung]
        self.assertEqual(len(bloecke), 3)
        # Seine Breite sagt, wie viele Doppeladern er belegt.
        schmal, breit = min(bloecke, key=lambda e: e.breite), max(
            bloecke, key=lambda e: e.breite
        )
        self.assertAlmostEqual(breit.breite / schmal.breite, 2.0, places=3)

    def test_keine_da_nummern_mehr(self):
        for text in _texte(self._blatt()):
            with self.subTest(text=text):
                self.assertNotIn(text, [str(i) for i in range(1, 11)])

    def test_wer_die_nummern_will_bekommt_sie(self):
        """Die Vorlage entscheidet - abgeschafft ist nichts."""
        blatt = self._blatt(STANDARD.mit(da_nummern=True))
        self.assertIn("10", _texte(blatt))


class TestKabelspalteImLeistenblatt(unittest.TestCase):
    """Auch hier ist frei eine durchgehende Fläche."""

    def _blatt(self, vorlage=STANDARD):
        v = Verteiler.aus_geometrie(1, 2, 10)
        v.kabel_anlegen("4 DA zu Wohnzimmer", 1, 1, 4)
        return leistenblatt(Projekt(verteiler=v), 1, vorlage)

    def _waagerechte(self, blatt) -> list:
        return [
            e for e in blatt.elemente
            if isinstance(e, Linie) and e.y1 == e.y2 and e.x1 == STANDARD.rand
        ]

    def test_zeilenstriche_enden_vor_der_kabelspalte(self):
        blatt = self._blatt()
        breiten = STANDARD.breiten(blatt.breite - 2 * STANDARD.rand)
        kabelspalte = [s.feld for s in STANDARD.spalten].index("kabel")
        ende = STANDARD.rand + sum(breiten[:kabelspalte])

        striche = self._waagerechte(blatt)
        self.assertEqual(len(striche), 20)          # 10 DA sind 20 Zeilen
        for strich in striche:
            with self.subTest(y=round(strich.y1, 1)):
                self.assertAlmostEqual(strich.x2, ende, places=3)

    def test_ohne_kabelspalte_laufen_sie_durch(self):
        ohne = STANDARD.mit(
            spalten=tuple(s for s in STANDARD.spalten if s.feld != "kabel")
        )
        blatt = self._blatt(ohne)
        breite = blatt.breite - 2 * STANDARD.rand
        for strich in self._waagerechte(blatt):
            self.assertAlmostEqual(strich.x2, STANDARD.rand + breite, places=3)

    def test_der_kabelblock_bleibt(self):
        blatt = self._blatt()
        bloecke = [
            e for e in blatt.elemente
            if isinstance(e, Rechteck) and e.fuellung == "#EFEFEF"
        ]
        self.assertEqual(len(bloecke), 1)


class TestDeckblattOhneSchriftfeld(unittest.TestCase):
    """Das Deckblatt ist selbst eines - unten steht nichts noch einmal."""

    def _blatt(self, vorlage=STANDARD):
        v = Verteiler.aus_geometrie(1, 2, 10, name="Probe", nummer="1.1")
        projekt = Projekt(
            verteiler=v,
            briefkopf={"firma": "Musterfirma", "erstellt_am": "01.01.1970"},
        )
        return deckblatt(projekt, vorlage)

    def test_kein_schriftfeldkasten_am_blattfuss(self):
        blatt = self._blatt()
        unten = blatt.hoehe - STANDARD.rand - STANDARD.schriftfeld_hoehe
        kaesten = [
            e for e in blatt.elemente
            if isinstance(e, Rechteck) and e.y >= unten - 0.01
        ]
        self.assertEqual(kaesten, [])

    def test_jede_angabe_steht_genau_einmal(self):
        texte = _texte(self._blatt())
        for wert in ("Musterfirma", "Probe", "1.1"):
            with self.subTest(wert=wert):
                self.assertEqual(texte.count(wert), 1)

    def test_die_fusszeile_bleibt(self):
        folge = blaetter(Projekt(verteiler=Verteiler.aus_geometrie(1, 2, 10)))
        self.assertIn("Blatt 1 von 4", _texte(folge[0]))

    def test_die_uebrigen_blaetter_behalten_ihr_schriftfeld(self):
        projekt = Projekt(
            verteiler=Verteiler.aus_geometrie(1, 2, 10, name="Probe"),
            briefkopf={"firma": "Musterfirma"},
        )
        for blatt in blaetter(projekt)[1:]:
            with self.subTest(blatt=blatt.titel):
                self.assertIn("Musterfirma", _texte(blatt))


class TestUmbruch(unittest.TestCase):
    """Wie ein Text auf mehrere Zeilen kommt.

    Gemessen wird hier mit einer festen Zeichenbreite - das Layoutmodell
    kennt keine Schriften, es bekommt das Mass gereicht.
    """

    def setUp(self):
        from verteilerly.layout import umbruch_einpassen, zeilen_umbrechen

        self.umbrechen = zeilen_umbrechen
        self.einpassen = umbruch_einpassen
        self.misst = lambda zeile, groesse=1.0: len(zeile) * groesse * 0.6

    def test_umgebrochen_wird_am_leerzeichen(self):
        zeilen = self.umbrechen(
            "Wohnzimmer Nord", 7, lambda z: self.misst(z)
        )
        self.assertEqual(zeilen, ["Wohnzimmer", "Nord"])

    def test_auch_der_schraegstrich_taugt_als_stelle(self):
        """Kabelnamen gliedern sich selbst: K12/3-4."""
        zeilen = self.umbrechen("K12/3-4", 3, lambda z: self.misst(z))
        self.assertEqual(zeilen, ["K12/", "3-4"])

    def test_ein_wort_das_nirgends_passt_wird_getrennt(self):
        zeilen = self.umbrechen(
            "Unteilbarkeitserklaerung", 6, lambda z: self.misst(z)
        )
        self.assertTrue(len(zeilen) > 1)
        for zeile in zeilen[:-1]:
            self.assertTrue(zeile.endswith("-"), zeile)
        self.assertEqual(
            "".join(z.rstrip("-") for z in zeilen), "Unteilbarkeitserklaerung"
        )
        for zeile in zeilen:
            # Der Trennstrich zaehlt mit - sonst laeuft die Zeile ueber.
            self.assertLessEqual(self.misst(zeile), 6)

    def test_was_passt_bleibt_auf_einer_zeile(self):
        self.assertEqual(self.umbrechen("Kurz", 60, self.misst), ["Kurz"])

    def test_die_schrift_schrumpft_erst_wenn_die_zeilen_nicht_reichen(self):
        """Ein hoher Kasten nimmt lieber zwei Zeilen als kleine Schrift."""
        groesse, zeilen = self.einpassen(
            "Wohnzimmer Nord", 20, 10, 3.0, 1.0, 0.25, self.misst
        )
        self.assertEqual(groesse, 3.0)
        self.assertEqual(zeilen, ["Wohnzimmer", "Nord"])

    def test_ein_flacher_kasten_zwingt_zur_kleineren_schrift(self):
        groesse, zeilen = self.einpassen(
            "Wohnzimmer Nord", 20, 3.5, 3.0, 1.0, 0.25, self.misst
        )
        self.assertLess(groesse, 3.0)
        self.assertLessEqual(len(zeilen) * groesse * 1.15, 3.5)

    def test_was_auch_klein_nicht_passt_endet_mit_punkten(self):
        groesse, zeilen = self.einpassen(
            "Ein sehr langer Kabelname", 3, 1.5, 3.0, 1.0, 0.25, self.misst
        )
        self.assertEqual(groesse, 1.0)
        self.assertEqual(len(zeilen), 1)
        self.assertTrue(zeilen[0].endswith("…"))
        self.assertLessEqual(self.misst(zeilen[0], 1.0), 3)

    def test_lieber_eine_stufe_kleiner_als_mitten_im_wort_getrennt(self):
        """„Melderkre-is" liest sich schlechter als eine kleinere Schrift."""
        groesse, zeilen = self.einpassen(
            "Melderkreis Erdgeschoss", 8, 20, 3.0, 1.0, 0.25, self.misst
        )
        self.assertEqual(zeilen, ["Melderkreis", "Erdgeschoss"])
        self.assertLess(groesse, 3.0)

    def test_passt_kein_wort_wird_doch_getrennt(self):
        """Irgendwann hilft nur noch der harte Schnitt."""
        groesse, zeilen = self.einpassen(
            "Unteilbarkeitserklaerung", 3, 20, 3.0, 1.0, 0.25, self.misst
        )
        self.assertGreater(len(zeilen), 1)
        self.assertEqual(
            "".join(z.rstrip("-") for z in zeilen), "Unteilbarkeitserklaerung"
        )

    def test_getrennt_wird_zwischen_den_silben(self):
        """Nicht irgendwo: der Anlaut wandert mit in die neue Zeile."""
        from verteilerly.layout import _trennstellen

        for wort, erwartet in (
            ("Kabelname", ["Ka-belname", "Kabel-name", "Kabelna-me"]),
            ("Wohnzimmer", ["Wohn-zimmer", "Wohnzim-mer"]),
            ("Lichtschacht", ["Licht-schacht"]),
            ("Melderkreis", ["Mel-derkreis", "Melder-kreis"]),
            ("Zucker", ["Zu-cker"]),
        ):
            with self.subTest(wort=wort):
                getrennt = [
                    f"{wort[:i]}-{wort[i:]}" for i in _trennstellen(wort)
                ]
                self.assertEqual(getrennt, erwartet)

    def test_in_zahlen_wird_nicht_getrennt(self):
        """„K12-\n345" läse sich als eine andere Nummer."""
        from verteilerly.layout import _trennstellen

        self.assertEqual(_trennstellen("K12345678"), [])
        zeilen = self.umbrechen("K12345678", 3, self.misst)
        self.assertTrue(len(zeilen) > 1)
        for zeile in zeilen:
            self.assertFalse(zeile.endswith("-"), zeile)

    def test_ein_einzelner_buchstabe_bleibt_nicht_stehen(self):
        from verteilerly.layout import _trennstellen

        for wort in ("Ebene", "Ofen"):
            with self.subTest(wort=wort):
                for stelle in _trennstellen(wort):
                    self.assertGreaterEqual(stelle, 2)
                    self.assertGreaterEqual(len(wort) - stelle, 2)

    def test_der_trennstrich_zaehlt_zur_zeile(self):
        """Sonst passte die Zeile nur ohne ihn."""
        zeilen = self.umbrechen("Kabelname", 4, self.misst)
        self.assertEqual(zeilen, ["Kabel-", "name"])
        self.assertLessEqual(self.misst("Kabel-"), 4)

    def test_umgebrochen_wird_vor_dem_verkleinern(self):
        """Zwei Zeilen in voller Groesse statt einer geschrumpften.

        Bis 2026.10.04 ging eine kleiner gesetzte einzelne Zeile vor
        (``einzeilig_ab``): der Kabelname schrumpfte, obwohl der Block
        zwei Zeilen in voller Groesse getragen haette.
        """
        groesse, zeilen = self.einpassen(
            "Wohnzimmer Nord", 12, 20, 3.0, 1.0, 0.25, self.misst
        )
        self.assertEqual(zeilen, ["Wohnzimmer", "Nord"])
        self.assertEqual(groesse, 2.0)
        self.assertLessEqual(max(self.misst(z, groesse) for z in zeilen), 12)
        # Auf einer Zeile haette dieselbe Groesse nicht gereicht - und
        # genau die kleinere Zeile stand hier bisher.
        self.assertGreater(self.misst("Wohnzimmer Nord", groesse), 12)

    def test_mehr_als_zwei_zeilen_werden_nicht_gesetzt(self):
        """Drei Zeilen stehen im Block wie ein Absatz."""
        ohne = self.einpassen(
            "Melderkreis Erdgeschoss West", 12, 20, 3.0, 1.0, 0.25, self.misst
        )
        self.assertGreater(len(ohne[1]), 2)       # ohne Deckel wie bisher
        groesse, zeilen = self.einpassen(
            "Melderkreis Erdgeschoss West", 12, 20, 3.0, 1.0, 0.25, self.misst,
            hoechstens=2,
        )
        self.assertEqual(len(zeilen), 2)
        self.assertLess(groesse, ohne[0])         # dafuer eine Stufe kleiner
        self.assertLessEqual(max(self.misst(z, groesse) for z in zeilen), 12)

    def test_eine_dritte_zeile_geht_vor_dem_kuerzen(self):
        """Der Deckel gibt nach, bevor ein Name verloren geht.

        Zwei Zeilen sind die Regel - geht der Text auch bei kleinster
        Schrift nicht hinein, ist eine dritte Zeile das kleinere Uebel:
        sie ist zu lesen, ein Rest mit Punkten nicht.
        """
        lang = "Wohnzimmer Nord Erdgeschoss Treppenhaus Ost"
        groesse, zeilen = self.einpassen(
            lang, 12, 20, 3.0, 1.0, 0.25, self.misst, hoechstens=2,
        )
        self.assertEqual(len(zeilen), 3)
        self.assertEqual(" ".join(zeilen), lang)
        self.assertLessEqual(max(self.misst(z, groesse) for z in zeilen), 12)

    def test_auch_die_dritte_zeile_hat_ein_ende(self):
        """Irgendwann bleibt nur das Kuerzen - dann nach drei Zeilen."""
        from verteilerly.layout import ZEILEN_NOTFALLS

        groesse, zeilen = self.einpassen(
            "Ein sehr langer Kabelname ueber viele Zeilen", 4, 20, 3.0, 1.0,
            0.25, self.misst, hoechstens=2,
        )
        self.assertEqual(len(zeilen), 2 + ZEILEN_NOTFALLS)
        self.assertTrue(zeilen[-1].endswith("…"))

    def test_leerer_text_bleibt_leer(self):
        self.assertEqual(self.umbrechen("", 10, self.misst), [])


class TestTeilnummernAufDenBlaettern(unittest.TestCase):
    """Jedes aufgelegte Stück einer Leitung trägt seine Nummer."""

    def _projekt(self):
        v = Verteiler.aus_geometrie(1, 2, 10)
        v.kabel_anlegen_mehrteilig(
            "Halle Ost",
            [Kabelabschnitt(1, 9, 2), Kabelabschnitt(2, 1, 4)],
            da_gesamt=6,
        )
        return Projekt(verteiler=v)

    def _texte(self, blatt):
        return [e.text for e in blatt.elemente if isinstance(e, Text)]

    def test_die_belegung_nennt_beide_stuecke(self):
        texte = self._texte(verteilerbelegungen(self._projekt())[0])
        self.assertIn("Halle Ost (1)", texte)
        self.assertIn("Halle Ost (2)", texte)

    def test_auf_dem_leistenblatt_steht_die_nummer_am_namen(self):
        projekt = self._projekt()
        erste = [t for t in self._texte(leistenblatt(projekt, 1)) if "Halle" in t]
        zweite = [t for t in self._texte(leistenblatt(projekt, 2)) if "Halle" in t]
        self.assertTrue(all("(1)" in t for t in erste), erste)
        self.assertTrue(all("(2)" in t for t in zweite), zweite)

    def test_eine_leitung_in_einem_stueck_bekommt_keine_nummer(self):
        v = Verteiler.aus_geometrie(1, 2, 10)
        v.kabel_anlegen("Halle Ost", 1, 1, 4)
        texte = self._texte(verteilerbelegungen(Projekt(verteiler=v))[0])
        self.assertIn("Halle Ost", texte)

    def test_der_zusatz_zur_kuerzung_steht_hinter_der_nummer(self):
        v = Verteiler.aus_geometrie(1, 2, 10)
        v.kabel_anlegen_mehrteilig(
            "Halle Ost",
            [Kabelabschnitt(1, 9, 2), Kabelabschnitt(2, 1, 3)],
            da_gesamt=6,
        )
        projekt = Projekt(verteiler=v)
        projekt.kuerzung_zeigen = True
        texte = self._texte(verteilerbelegungen(projekt)[0])
        self.assertIn("Halle Ost (1)", texte)
        self.assertIn("Halle Ost (2) (gekürzt)", texte)
