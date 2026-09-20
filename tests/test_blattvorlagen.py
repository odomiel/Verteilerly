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
from . import BEISPIELVORLAGE


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

    def test_luft_im_kabelblock_steht_in_der_vorlage(self):
        """Was das Blatt aussehen laesst, sagt die Blattvorlage."""
        vorlage = blattvorlage_aus_yaml({
            "id": "eng", "name": "Eng",
            "belegung": {"fuellgrad_kabel": 0.6, "polster_kabel": 1.5},
        })
        self.assertEqual(vorlage.fuellgrad_kabel, 0.6)
        self.assertEqual(vorlage.polster_kabel, 1.5)
        # Weggelassen bleibt es bei der Vorgabe.
        schlicht = blattvorlage_aus_yaml({"id": "x", "name": "X"})
        self.assertEqual(schlicht.fuellgrad_kabel, STANDARD.fuellgrad_kabel)
        self.assertEqual(schlicht.polster_kabel, STANDARD.polster_kabel)

    def test_ein_unsinniger_fuellgrad_wird_abgewiesen(self):
        for belegung in ({"fuellgrad_kabel": 2.0}, {"fuellgrad_kabel": 0.0},
                         {"polster_kabel": -1.0}):
            with self.subTest(belegung=belegung):
                with self.assertRaises(BlattvorlagenFehler):
                    blattvorlage_aus_yaml(
                        {"id": "x", "name": "X", "belegung": belegung}
                    )

    def test_null_buchten_je_blatt(self):
        with self.assertRaises(BlattvorlagenFehler):
            blattvorlage_aus_yaml(
                {"id": "x", "name": "X", "buchten_je_blatt": 0}, "x.yaml"
            )


class TestAlsYaml(unittest.TestCase):
    """Die Umkehrung des Lesens - fuer den Blattvorlagen-Editor."""

    def test_der_standard_schreibt_nur_kennung_und_name(self):
        import dataclasses

        from verteilerly.blattvorlagen import STANDARD, blattvorlage_als_yaml

        vorlage = dataclasses.replace(STANDARD, id="x", name="X", standard=False,
                                      beschreibung="")
        self.assertEqual(blattvorlage_als_yaml(vorlage), {"id": "x", "name": "X"})

    def test_hin_und_zurueck_bleibt_alles_gleich(self):
        import dataclasses

        import yaml

        from verteilerly.blattvorlagen import (
            STANDARD,
            blattvorlage_als_yaml,
            blattvorlage_aus_yaml,
        )

        from verteilerly.blattvorlagen import Schriftfeldeintrag

        eigene = dataclasses.replace(
            STANDARD, id="probe", name="Probe", standard=False, rand=17.5,
            schrift_klein=6.0, spalten=STANDARD.spalten[:3], da_nummern=True,
            fuellgrad_kabel=0.5, zelle_hoehe=7.25, buchten_je_blatt=3,
            schriftfeld=(
                (Schriftfeldeintrag("firma"),
                 Schriftfeldeintrag("strich"),
                 Schriftfeldeintrag("verteiler", "rechts")),
                (Schriftfeldeintrag("erstellt", "mitte"),),
            ),
        )
        vorlagen = [BEISPIELVORLAGE, eigene]
        for datei in sorted(blattvorlagenordner().glob("*.yaml")):
            vorlagen.append(blattvorlage_aus_yaml(
                yaml.safe_load(datei.read_text(encoding="utf-8")), datei.name
            ))
        for vorlage in vorlagen:
            with self.subTest(vorlage=vorlage.id):
                inhalt = yaml.safe_load(yaml.safe_dump(blattvorlage_als_yaml(vorlage)))
                self.assertEqual(blattvorlage_aus_yaml(inhalt), vorlage)

    def test_ganze_zahlen_stehen_ohne_komma(self):
        import dataclasses

        from verteilerly.blattvorlagen import STANDARD, blattvorlage_als_yaml

        inhalt = blattvorlage_als_yaml(dataclasses.replace(STANDARD, id="x", name="X", rand=20.0))
        self.assertIsInstance(inhalt["rand"], int)

    def test_wer_bearbeitet_darf_ausdruecklich_ueberschreiben(self):
        """Eine vorhandene Vorlage zu ändern heißt: dieselbe Datei neu."""
        import dataclasses
        import tempfile

        import yaml

        from verteilerly.blattvorlagen import (
            STANDARD,
            blattvorlage_speichern,
        )

        with tempfile.TemporaryDirectory() as ordner:
            ordner = pathlib.Path(ordner)
            vorlage = dataclasses.replace(
                STANDARD, id="probe", name="Probe", standard=False
            )
            erste = blattvorlage_speichern(vorlage, ordner)
            zweite = blattvorlage_speichern(
                dataclasses.replace(vorlage, rand=20.0), ordner, ueberschreiben=True
            )
            self.assertEqual(erste, zweite)
            self.assertEqual(sorted(p.name for p in ordner.glob("*.yaml")),
                             ["probe.yaml"])
            inhalt = yaml.safe_load(erste.read_text(encoding="utf-8"))
            self.assertEqual(inhalt["rand"], 20)

    def test_speichern_ueberschreibt_nie(self):
        import dataclasses

        from verteilerly.blattvorlagen import (
            STANDARD,
            BlattvorlagenFehler,
            blattvorlage_speichern,
            freie_kennung,
        )

        with tempfile.TemporaryDirectory() as name:
            ordner = pathlib.Path(name)
            vorlage = dataclasses.replace(STANDARD, id="eng", name="Eng", standard=False)
            ziel = blattvorlage_speichern(vorlage, ordner)
            self.assertEqual(ziel, ordner / "eng.yaml")
            vorher = ziel.read_text(encoding="utf-8")
            with self.assertRaises(BlattvorlagenFehler):
                blattvorlage_speichern(dataclasses.replace(vorlage, rand=30.0), ordner)
            self.assertEqual(ziel.read_text(encoding="utf-8"), vorher)
            self.assertEqual(freie_kennung("Eng", set(), ordner), "eng-2")
            self.assertEqual(freie_kennung("Eng", {"eng-2"}, ordner), "eng-3")
            self.assertEqual(freie_kennung("Ganz Neu", set(), ordner), "ganz-neu")


class TestMitgelieferte(unittest.TestCase):
    def setUp(self):
        self.vorlagen = Blattvorlagen.laden(blattvorlagenordner())

    def test_die_mitgelieferten_vorlagen(self):
        beiliegend = Blattvorlagen.laden(mitgeliefert() / "blattvorlagen")
        self.assertEqual(
            sorted(v.id for v in beiliegend.alle),
            ["ausfuehrlich", "knapp", "standard"],
        )

    def test_eine_angabe_darf_ihre_ausrichtung_mitbringen(self):
        """Kurzform ist die bloße Marke, lang geht es mit Ausrichtung."""
        from verteilerly.blattvorlagen import blattvorlage_aus_yaml

        vorlage = blattvorlage_aus_yaml(
            {"id": "x", "name": "X", "schriftfeld": [
                ["firma", {"marke": "verteiler", "ausrichtung": "rechts"}]
            ]},
            "x.yaml",
        )
        block = vorlage.schriftfeld[0]
        self.assertEqual(block[0].ausrichtung, "links")
        self.assertEqual(block[1].ausrichtung, "rechts")

    def test_eine_ausrichtung_die_es_nicht_gibt_wird_abgewiesen(self):
        from verteilerly.blattvorlagen import (
            BlattvorlagenFehler,
            blattvorlage_aus_yaml,
        )

        with self.assertRaises(BlattvorlagenFehler):
            blattvorlage_aus_yaml(
                {"id": "x", "name": "X", "schriftfeld": [
                    [{"marke": "firma", "ausrichtung": "schräg"}]
                ]},
                "x.yaml",
            )

    def test_ein_vertippter_schluessel_der_angabe_wird_gemeldet(self):
        from verteilerly.blattvorlagen import blattvorlage_aus_yaml

        hinweise = []
        blattvorlage_aus_yaml(
            {"id": "x", "name": "X", "schriftfeld": [
                [{"marke": "firma", "ausrichtng": "rechts"}]
            ]},
            "x.yaml",
            hinweise,
        )
        self.assertTrue([h for h in hinweise if "ausrichtng" in h])

    def test_die_beispielvorlage_wird_nicht_mitgeliefert(self):
        """Nur die Bauart blieb im Programm, nicht die Vorlage."""
        self.assertFalse((mitgeliefert() / "blattvorlagen" / "beispiel.yaml").is_file())

    def test_die_bauart_beispiel_steht_jeder_vorlage_offen(self):
        """Wer dieses Schriftfeld will, setzt es selbst."""
        vorlage = BEISPIELVORLAGE
        self.assertEqual(vorlage.schriftfeld_art, "beispiel")
        self.assertEqual(
            [[eintrag.marke for eintrag in block] for block in vorlage.schriftfeld],
            [
                ["verteiler", "verteilernummer", "leiste"],
                ["erstellt", "stand", "geprueft"],
                ["firma", "kunde"],
            ],
        )
        # Für zwei Anschriften braucht das Schriftfeld mehr Höhe.
        self.assertGreater(vorlage.schriftfeld_hoehe, STANDARD.schriftfeld_hoehe)

    def test_eine_verschwundene_vorlage_faellt_auf_den_standard_zurueck(self):
        """Was in der conf steht, muss es nicht mehr geben."""
        vorlagen = Blattvorlagen.laden(mitgeliefert() / "blattvorlagen")
        self.assertEqual(vorlagen.gewaehlt("gibtsnicht").id, vorlagen.standard.id)
        self.assertEqual(vorlagen.gewaehlt("knapp").id, "knapp")
        # Auch die ausgebaute Beispielvorlage legt nichts lahm.
        self.assertEqual(vorlagen.gewaehlt("beispiel").id, vorlagen.standard.id)

    def test_umbenennen_aendert_nur_den_namen(self):
        """Die Kennung bleibt - sie ist der Dateiname."""
        from verteilerly.blattvorlagen import blattvorlage_umbenennen
        import shutil

        with tempfile.TemporaryDirectory() as ordner:
            ziel = pathlib.Path(ordner)
            shutil.copy2(mitgeliefert() / "blattvorlagen" / "knapp.yaml", ziel)
            vorlagen = Blattvorlagen.laden(ziel)
            neu = blattvorlage_umbenennen(
                vorlagen.holen("knapp"), "Nur Rangierungen", ziel
            )
            self.assertEqual(neu.id, "knapp")
            self.assertEqual(neu.name, "Nur Rangierungen")
            wieder = Blattvorlagen.laden(ziel).holen("knapp")
            self.assertEqual(wieder.name, "Nur Rangierungen")
            # Alles andere steht unverändert da - auch die Kommentare.
            self.assertEqual(
                [s.feld for s in wieder.spalten],
                [s.feld for s in vorlagen.holen("knapp").spalten],
            )
            text = (ziel / "knapp.yaml").read_text(encoding="utf-8")
            self.assertTrue(text.lstrip().startswith("#"), "Kommentar verloren")

    def test_eine_mitgelieferte_wird_dabei_uebernommen(self):
        """Im Abbild lässt sich nichts schreiben - die Datei entsteht neu."""
        from verteilerly.blattvorlagen import blattvorlage_umbenennen

        with tempfile.TemporaryDirectory() as ordner:
            ziel = pathlib.Path(ordner)
            beiliegend = Blattvorlagen.laden(mitgeliefert() / "blattvorlagen")
            blattvorlage_umbenennen(
                beiliegend.holen("knapp"), "Eigene Fassung", ziel,
                [mitgeliefert() / "blattvorlagen"],
            )
            self.assertTrue((ziel / "knapp.yaml").is_file())
            self.assertEqual(Blattvorlagen.laden(ziel).holen("knapp").name,
                             "Eigene Fassung")

    def test_ein_leerer_name_wird_abgelehnt(self):
        from verteilerly.blattvorlagen import blattvorlage_umbenennen

        with tempfile.TemporaryDirectory() as ordner:
            with self.assertRaises(BlattvorlagenFehler):
                blattvorlage_umbenennen(STANDARD, "   ", pathlib.Path(ordner))

    def test_ohne_datei_entsteht_eine(self):
        """Die eingebaute Vorgabe hat keine - dann wird eine geschrieben."""
        from verteilerly.blattvorlagen import blattvorlage_umbenennen

        with tempfile.TemporaryDirectory() as ordner:
            ziel = pathlib.Path(ordner)
            blattvorlage_umbenennen(STANDARD, "Hausnorm", ziel)
            self.assertEqual(Blattvorlagen.laden(ziel).holen("standard").name,
                             "Hausnorm")

    def test_loeschen_nimmt_die_datei_weg(self):
        """Wie bei den Verteilervorlagen - die Datei ist die Vorlage."""
        from verteilerly.blattvorlagen import blattvorlage_loeschen
        import shutil

        with tempfile.TemporaryDirectory() as ordner:
            ziel = pathlib.Path(ordner)
            shutil.copy2(mitgeliefert() / "blattvorlagen" / "knapp.yaml", ziel)
            self.assertTrue(blattvorlage_loeschen("knapp", ziel))
            self.assertFalse((ziel / "knapp.yaml").exists())
            # Eine, die dort nie lag, ist auch kein Fehler: die
            # mitgelieferte bleibt im Abbild liegen, der Vermerk regelt es.
            self.assertFalse(blattvorlage_loeschen("knapp", ziel))

    def test_gestrichene_marken_bleiben_beim_laden_weg(self):
        """Der Löschvermerk wirkt auch gegen das Abbild."""
        vorlagen = Blattvorlagen.aus_ordnern(
            [mitgeliefert() / "blattvorlagen"], {"blattvorlagen/knapp.yaml"}
        )
        self.assertNotIn("knapp", [v.id for v in vorlagen.alle])
        self.assertIn("ausfuehrlich", [v.id for v in vorlagen.alle])

    def test_entfernen_nimmt_sie_aus_der_sammlung(self):
        vorlagen = Blattvorlagen.laden(mitgeliefert() / "blattvorlagen")
        vorlagen.entfernen("knapp")
        self.assertNotIn("knapp", [v.id for v in vorlagen.alle])
        # Die eingebaute Vorgabe bleibt - ohne sie gäbe es kein Blatt.
        vorlagen.entfernen("standard")
        self.assertEqual([v.id for v in vorlagen.alle if v.id == "standard"],
                         ["standard"])

    def test_eine_kaputte_datei_nimmt_die_anderen_nicht_mit(self):
        """Wer eine Vorlage schreibt, vertippt sich."""
        with tempfile.TemporaryDirectory() as ordner:
            ziel = pathlib.Path(ordner)
            (ziel / "kaputt.yaml").write_text(
                "id: kaputt\nname: Kaputt\nbuchten_je_blatt: 0\n", encoding="utf-8"
            )
            (ziel / "krumm.yaml").write_text("kein: [gueltiges, {yaml", encoding="utf-8")
            (ziel / "eng.yaml").write_text("id: eng\nname: Eng\n", encoding="utf-8")
            wunden: list[str] = []
            vorlagen = Blattvorlagen.aus_ordnern([ziel], fehler=wunden)

        self.assertIn("eng", [v.id for v in vorlagen.alle])
        self.assertNotIn("kaputt", [v.id for v in vorlagen.alle])
        self.assertEqual(len(wunden), 2, wunden)
        # Die Meldung nennt Datei und Grund, und zwar je einmal.
        kaputt = next(w for w in wunden if w.startswith("kaputt.yaml"))
        self.assertEqual(kaputt.count("kaputt.yaml"), 1)
        self.assertIn("buchten_je_blatt", kaputt)

    def test_ohne_liste_wird_trotzdem_uebergangen(self):
        """Der Aufrufer muss sich nicht fuer die Gruende interessieren."""
        with tempfile.TemporaryDirectory() as ordner:
            ziel = pathlib.Path(ordner)
            (ziel / "kaputt.yaml").write_text("id: x\n", encoding="utf-8")
            vorlagen = Blattvorlagen.aus_ordnern([ziel])
        self.assertEqual([v.id for v in vorlagen.alle], ["standard"])

    def test_ein_vertippter_schluessel_wird_gemeldet(self):
        """Sonst faellt er nirgends auf - die Vorgabe greift ja."""
        hinweise: list[str] = []
        vorlage = blattvorlage_aus_yaml(
            {
                "id": "x", "name": "X",
                "zeilenhohe_max": 7,
                "belegung": {"zelle_hoeh": 12},
                "spalten": [{"feld": "stift", "uberschrift": "S"}],
            },
            "x.yaml", hinweise,
        )
        # Gelesen wird sie trotzdem: sie kann aus einer neueren Fassung sein.
        self.assertEqual(vorlage.id, "x")
        self.assertEqual(vorlage.zeilenhoehe_max, STANDARD.zeilenhoehe_max)
        self.assertEqual(len(hinweise), 3, hinweise)
        self.assertTrue(all(h.startswith("x.yaml: ") for h in hinweise))
        self.assertIn("zeilenhohe_max", hinweise[0])
        self.assertIn("belegung", " ".join(hinweise))
        self.assertIn("spalten", " ".join(hinweise))

    def test_bekannte_schluessel_geben_keine_meldung(self):
        hinweise: list[str] = []
        blattvorlage_aus_yaml(
            {
                "id": "x", "name": "X", "beschreibung": "", "standard": False,
                "rand": 10, "schriftfeld_hoehe": 30, "kopfzeile_hoehe": 7,
                "zeilenhoehe_max": 9, "zeilenhoehe_min": 5,
                "schrift": {"gross": 20, "mittel": 11, "normal": 9, "klein": 7},
                "spalten": ["stift", {"feld": "kabel", "ueberschrift": "K",
                                      "anteil": 12, "ausrichtung": "mitte"}],
                "schriftfeld": [["firma"]], "schriftfeld_art": "standard",
                "schriftfeld_anteile": [0.5, 0.5], "buchten_je_blatt": 1,
                "da_nummern": True, "kabel_gedreht": False,
                "belegung": {"zelle_breite": 6, "zelle_hoehe": 9,
                             "leistenlabel": 14, "abstand_leisten": 3,
                             "abstand_buchten": 12, "fuellgrad_kabel": 0.8,
                             "polster_kabel": 0.5},
            },
            "x.yaml", hinweise,
        )
        self.assertEqual(hinweise, [])

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
