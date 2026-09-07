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


if __name__ == "__main__":
    unittest.main()
