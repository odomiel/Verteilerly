"""Tests zur Projektdatei."""

import json
import pathlib
import tempfile
import unittest

from verteilerly import projektdatei
from verteilerly.modell import Aderadresse, Kabelabschnitt, Projekt, Verteiler
from verteilerly.projektdatei import ProjektdateiFehler


def beispielprojekt() -> Projekt:
    """Baut die rangierte Mustertabelle im Datenmodell nach."""
    verteiler = Verteiler.aus_geometrie(1, 4, 10, "Verteiler Name", "1.1")
    verteiler.kabel_anlegen(
        "4DA Leitung zu Wohnzimmer", 1, 1, 4, kabeltyp="jystyv", da_gesamt=4
    )
    verteiler.kabel_anlegen("2DA zu Schlafzimmer", 3, 1, 2, kabeltyp="jystyv")
    verteiler.rangierung_anlegen(Aderadresse.parse("1 1a"), Aderadresse.parse("3 2a"))
    verteiler.rangierung_anlegen(Aderadresse.parse("1 1b"), Aderadresse.parse("3 2b"))

    stift = verteiler.leiste(1).stift(1)
    stift.a.bezeichnung = stift.b.bezeichnung = "Linie"
    stift.a.bemerkung = "Magnetkontakt"
    stift.b.bemerkung = "Fenster"

    return Projekt(
        verteiler=verteiler,
        briefkopf={
            "firma": "Firma Beliebig, Beliebige Strasse 7, 77777 Beliebiger Ort",
            "kunde": "Kunde Beliebig, Beliebige Strasse 7, 77777 Beliebiger Ort",
            "anlagennummer": "123456",
            "kundennummer": "654321",
            "erstellt_am": "01.01.70",
            "erstellt_von": "John Doe",
        },
        eigene_felder={"Aufmass": "geprueft am 02.01.70"},
    )


class TestProjektdatei(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.pfad = pathlib.Path(self.ordner.name) / "verteiler.vtly.json"

    def tearDown(self):
        self.ordner.cleanup()

    def test_vermerk_ueberlebt_das_speichern(self):
        """Der Freitext gehoert zur Ader und damit in die Datei."""
        projekt = beispielprojekt()
        v = projekt.verteiler
        v.vermerk_setzen(Aderadresse.parse("1 2a"), "zur Klemmleiste", zuerst=True)
        v.vermerk_setzen(Aderadresse.parse("1 3a"), "extern")
        projektdatei.speichern(projekt, self.pfad)

        zurueck = projektdatei.laden(self.pfad).verteiler
        self.assertEqual(zurueck.ader(Aderadresse.parse("1 2a")).vermerk,
                         "zur Klemmleiste")
        self.assertTrue(zurueck.ader(Aderadresse.parse("1 2a")).vermerk_zuerst)
        self.assertEqual(zurueck.ader(Aderadresse.parse("1 3a")).vermerk, "extern")
        self.assertFalse(zurueck.ader(Aderadresse.parse("1 3a")).vermerk_zuerst)

    def test_ader_ohne_vermerk_bleibt_schlank(self):
        projektdatei.speichern(beispielprojekt(), self.pfad)
        text = self.pfad.read_text(encoding="utf-8")
        self.assertNotIn("vermerk", text)

    def test_roundtrip(self):
        original = beispielprojekt()
        projektdatei.speichern(original, self.pfad)
        geladen = projektdatei.laden(self.pfad)
        self.assertEqual(projektdatei.als_dict(original), projektdatei.als_dict(geladen))

    def test_inhalte_ueberstehen_das_speichern(self):
        projektdatei.speichern(beispielprojekt(), self.pfad)
        p = projektdatei.laden(self.pfad)

        self.assertEqual(p.verteiler.name, "Verteiler Name")
        self.assertEqual(p.verteiler.da_gesamt, 40)
        self.assertEqual(len(p.verteiler.kabel), 2)
        self.assertEqual(p.verteiler.kabel[0].beschriftung, "4DA Leitung zu Wohnzimmer")
        self.assertEqual(p.verteiler.leiste(1).stift(1).a.bemerkung, "Magnetkontakt")
        self.assertEqual(p.briefkopf["anlagennummer"], "123456")
        self.assertEqual(p.feld("Aufmass"), "geprueft am 02.01.70")

        # Die Gegenstelle ergibt sich auch nach dem Laden von selbst.
        self.assertEqual(
            [str(z) for z in p.verteiler.ziele_von(Aderadresse.parse("3 2a"))],
            ["1 1a"],
        )

    def test_mehrteiliges_kabel_ueberlebt(self):
        v = Verteiler.aus_geometrie(1, 4, 10)
        v.kabel_anlegen_mehrteilig(
            "6DA ueber zwei Leisten",
            [Kabelabschnitt(1, 9, 2), Kabelabschnitt(2, 1, 4)],
            da_gesamt=6,
        )
        projektdatei.speichern(Projekt(verteiler=v), self.pfad)
        kabel = projektdatei.laden(self.pfad).verteiler.kabel[0]
        self.assertEqual(len(kabel.abschnitte), 2)
        self.assertEqual(kabel.da_aufgelegt, 6)

    def test_gekuerztes_kabel_ueberlebt(self):
        """da_gesamt bleibt groesser als das Aufgelegte."""
        v = Verteiler.aus_geometrie(1, 4, 10)
        v.kabel_anlegen("6DA, 5 aufgelegt", 1, 1, 5, da_gesamt=6)
        projektdatei.speichern(Projekt(verteiler=v), self.pfad)
        kabel = projektdatei.laden(self.pfad).verteiler.kabel[0]
        self.assertEqual((kabel.da_gesamt, kabel.da_aufgelegt), (6, 5))
        self.assertTrue(kabel.gekuerzt)

    def test_datei_ist_lesbares_json(self):
        """Auch ohne das Programm auswertbar."""
        projektdatei.speichern(beispielprojekt(), self.pfad)
        text = self.pfad.read_text(encoding="utf-8")
        self.assertIn('"dateikennung": "verteilerly-projekt"', text)
        self.assertIn("Wohnzimmer", text)  # Umlaute und Klartext unmaskiert
        self.assertIsInstance(json.loads(text), dict)

    def test_fremde_datei_abgelehnt(self):
        self.pfad.write_text('{"irgendwas": 1}', encoding="utf-8")
        with self.assertRaises(ProjektdateiFehler):
            projektdatei.laden(self.pfad)

    def test_kaputtes_json_abgelehnt(self):
        self.pfad.write_text("{kein json", encoding="utf-8")
        with self.assertRaises(ProjektdateiFehler):
            projektdatei.laden(self.pfad)

    def test_falsch_gebaute_datei_ergibt_eine_meldung(self):
        """Gueltiges JSON, aber kein Projekt - eine Meldung, kein Absturz."""
        kopf = {"dateikennung": projektdatei.DATEIKENNUNG, "formatversion": 9}
        faelle = {
            "nummer fehlt": {"buchten": [{"leisten": []}]},
            "bucht ist Text": {"buchten": ["x"]},
            "leisten ist Zahl": {"buchten": [{"nummer": 1, "leisten": 5}]},
            "kabel ohne abschnittsangaben": {"kabel": [{"abschnitte": [{}]}]},
            "rangierung ist Text": {"rangierungen": ["x"]},
            "verteiler ist Liste": [],
        }
        for fall, verteiler in faelle.items():
            with self.subTest(fall=fall):
                self.pfad.write_text(
                    json.dumps({**kopf, "verteiler": verteiler}), encoding="utf-8"
                )
                with self.assertRaises(ProjektdateiFehler):
                    projektdatei.laden(self.pfad)

    def test_binaerdatei_abgelehnt(self):
        self.pfad.write_bytes(b"\xff\xfe\x00kein Text")
        with self.assertRaises(ProjektdateiFehler):
            projektdatei.laden(self.pfad)

    def test_zu_tief_verschachtelt_abgelehnt(self):
        self.pfad.write_text("[" * 100_000, encoding="utf-8")
        with self.assertRaises(ProjektdateiFehler):
            projektdatei.laden(self.pfad)

    def test_kuenftige_formatversion_abgelehnt(self):
        daten = projektdatei.als_dict(beispielprojekt())
        daten["formatversion"] = 99
        self.pfad.write_text(json.dumps(daten), encoding="utf-8")
        with self.assertRaises(ProjektdateiFehler):
            projektdatei.laden(self.pfad)

    def test_speichern_laesst_bei_fehler_die_alte_datei_stehen(self):
        projektdatei.speichern(beispielprojekt(), self.pfad)
        vorher = self.pfad.read_text(encoding="utf-8")
        kaputt = Projekt(verteiler=Verteiler())
        kaputt.briefkopf["x"] = object()  # nicht serialisierbar
        with self.assertRaises(TypeError):
            projektdatei.speichern(kaputt, self.pfad)
        self.assertEqual(self.pfad.read_text(encoding="utf-8"), vorher)


class TestFeldauswahl(unittest.TestCase):
    """Die Auswahl übersteht das Speichern."""

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.ziel = pathlib.Path(self.ordner.name) / "p.vtly.json"

    def test_ausgeblendete_felder_kommen_zurueck(self):
        projekt = beispielprojekt()
        projekt.briefkopf["firma"] = "Musterfirma"
        projekt.eigene_felder["Standort"] = "Keller"
        projekt.sichtbarkeit_setzen("firma", False)
        projekt.sichtbarkeit_setzen("Standort", False)
        projektdatei.speichern(projekt, self.ziel)

        zurueck = projektdatei.laden(self.ziel)
        self.assertEqual(zurueck.ausgeblendet, {"firma", "Standort"})
        self.assertEqual(zurueck.briefkopf["firma"], "Musterfirma")
        self.assertEqual(zurueck.eigene_felder["Standort"], "Keller")

    def test_datei_ohne_auswahl_zeigt_alles(self):
        daten = projektdatei.als_dict(beispielprojekt())
        del daten["ausgeblendet"]
        self.assertEqual(projektdatei.aus_dict(daten).ausgeblendet, set())

    def test_die_inhalte_der_eigenen_felder_kommen_zurueck(self):
        """Die Inhalte gehören dem Projekt - die Namen der Blattvorlage."""
        projekt = beispielprojekt()
        projekt.eigene_felder["Standort"] = "Keller"
        projektdatei.speichern(projekt, self.ziel)
        self.assertEqual(
            projektdatei.laden(self.ziel).eigene_felder["Standort"], "Keller"
        )

    def test_die_blattarten_stehen_nicht_mehr_in_der_datei(self):
        """Sie gehören seit Fassung 10 der Blattvorlage."""
        daten = projektdatei.als_dict(beispielprojekt())
        self.assertNotIn("eigene_felder_auf", daten)
        self.assertEqual(daten["formatversion"], projektdatei.FORMATVERSION)

    def test_eigene_beschriftungen_kommen_zurueck(self):
        """Das eigene Wort steht in der Projektdatei."""
        projekt = beispielprojekt()
        projekt.beschriftungen = {"kunde": "Auftraggeber", "firma": "Firma"}
        projektdatei.speichern(projekt, self.ziel)
        zurueck = projektdatei.laden(self.ziel)
        # Nur die Abweichung wird geschrieben, nicht die halbe Vorgabe.
        self.assertEqual(zurueck.beschriftungen, {"kunde": "Auftraggeber"})
        self.assertEqual(zurueck.beschriftung("firma"), "Firma")

    def test_datei_ohne_beschriftungen_nimmt_die_vorgabe(self):
        daten = projektdatei.als_dict(beispielprojekt())
        del daten["beschriftungen"]
        self.assertEqual(projektdatei.aus_dict(daten).beschriftung("kunde"), "Kunde")

    def test_textstil_ueberlebt_das_speichern(self):
        """Der Stil gehört zum Verteiler, nicht zum Arbeitsplatz."""
        from verteilerly.modell import Textstil

        projekt = beispielprojekt()
        ader = projekt.verteiler.leiste(1).stift(1).ader("a")
        ader.stil_setzen("bezeichnung", Textstil("mitte", fett=True, kursiv=True))
        projektdatei.speichern(projekt, self.ziel)

        zurueck = projektdatei.laden(self.ziel)
        stil = zurueck.verteiler.leiste(1).stift(1).ader("a").stil("bezeichnung")
        self.assertEqual(stil, Textstil("mitte", fett=True, kursiv=True))

    def test_geteilte_zelle_ueberlebt_das_speichern(self):
        """Anteil und zweiter Text gehören zum Verteiler."""
        from verteilerly.modell import Zellenteilung

        projekt = beispielprojekt()
        ader = projekt.verteiler.leiste(1).stift(1).ader("a")
        ader.teilung_setzen("bemerkung", Zellenteilung(25, "T. M."))
        projektdatei.speichern(projekt, self.ziel)

        zurueck = projektdatei.laden(self.ziel)
        teilung = zurueck.verteiler.leiste(1).stift(1).ader("a").teilung("bemerkung")
        self.assertTrue(teilung.geteilt)
        self.assertEqual((teilung.anteil, teilung.text), (25, "T. M."))

    def test_ohne_stil_steht_nichts_in_der_datei(self):
        daten = projektdatei.als_dict(beispielprojekt())
        erste = daten["verteiler"]["buchten"][0]["leisten"][0]["stifte"][0]
        self.assertNotIn("stile", erste["a"])

    def test_eine_aeltere_datei_mit_blattarten_wird_uebergangen(self):
        """Bis Fassung 9 stand die Wahl hier - lesen darf sie nicht stören."""
        daten = projektdatei.als_dict(beispielprojekt())
        daten["eigene_felder_auf"] = ["belegung"]
        daten["eigene_felder"] = {"Standort": "Keller"}
        daten["formatversion"] = 9
        projekt = projektdatei.aus_dict(daten)
        self.assertEqual(projekt.eigene_felder, {"Standort": "Keller"})
        self.assertFalse(hasattr(projekt, "eigene_felder_auf"))


class TestAeltereDateien(unittest.TestCase):
    """Fassung 1 nannte die Buchten noch Reihen."""

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.ziel = pathlib.Path(self.ordner.name) / "alt.vtly.json"

        daten = projektdatei.als_dict(beispielprojekt())
        daten["formatversion"] = 1
        daten["verteiler"]["reihen"] = daten["verteiler"].pop("buchten")
        self.ziel.write_text(json.dumps(daten), encoding="utf-8")

    def test_alte_datei_wird_weiter_gelesen(self):
        projekt = projektdatei.laden(self.ziel)
        self.assertEqual(len(projekt.verteiler.buchten), 1)
        self.assertEqual(projekt.verteiler.da_gesamt, 40)
        self.assertEqual(len(projekt.verteiler.kabel), 2)

    def test_geschrieben_wird_die_neue_fassung(self):
        projekt = projektdatei.laden(self.ziel)
        neu = projektdatei.als_dict(projekt)
        self.assertEqual(neu["formatversion"], projektdatei.FORMATVERSION)
        self.assertIn("buchten", neu["verteiler"])
        self.assertNotIn("reihen", neu["verteiler"])

    def test_unbekannte_fassung_wird_abgewiesen(self):
        daten = projektdatei.als_dict(beispielprojekt())
        daten["formatversion"] = 99
        with self.assertRaises(ProjektdateiFehler):
            projektdatei.aus_dict(daten)


class TestLeistenschreibweise(unittest.TestCase):
    """Wie die Leisten heißen, gehört zum Verteiler."""

    def _projekt(self):
        from verteilerly.modell import Projekt, Verteiler

        return Projekt(verteiler=Verteiler.aus_geometrie(1, 2, 10, name="Probe"))

    def test_buchstaben_stehen_in_der_datei(self):
        from verteilerly.modell import LEISTEN_BUCHSTABEN

        projekt = self._projekt()
        projekt.leisten_schreibweise = LEISTEN_BUCHSTABEN
        daten = projektdatei.als_dict(projekt)
        self.assertEqual(daten["leisten_schreibweise"], "buchstaben")
        self.assertEqual(
            projektdatei.aus_dict(daten).leisten_schreibweise, "buchstaben"
        )

    def test_gezaehlt_steht_nicht_in_der_datei(self):
        """Geschrieben wird nur, was von der Vorgabe abweicht."""
        daten = projektdatei.als_dict(self._projekt())
        self.assertNotIn("leisten_schreibweise", daten)

    def test_eine_aeltere_datei_zaehlt_weiter(self):
        daten = projektdatei.als_dict(self._projekt())
        daten["formatversion"] = 8
        self.assertEqual(projektdatei.aus_dict(daten).leisten_schreibweise, "zahlen")

    def test_was_das_programm_nicht_kennt_wird_gezaehlt(self):
        daten = projektdatei.als_dict(self._projekt())
        daten["leisten_schreibweise"] = "roemisch"
        self.assertEqual(projektdatei.aus_dict(daten).leisten_schreibweise, "zahlen")


if __name__ == "__main__":
    unittest.main()
