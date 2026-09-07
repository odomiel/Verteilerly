"""Tests zu den Schreibweisen der Rangierungen."""

import unittest

from verteilerly import schreibweisen
from verteilerly.ausgabe import belegungszeilen
from verteilerly.layout import Text, blaetter
from verteilerly.modell import Aderadresse, Projekt, Verteiler, adressen_schreiben


def _projekt(kennung: str) -> Projekt:
    v = Verteiler.aus_geometrie(1, 4, 10, name="Probe")
    v.rangierung_anlegen(Aderadresse(1, 1, "a"), Aderadresse(3, 2, "a"))
    return Projekt(verteiler=v, rangierung_schreibweise=kennung)


def _texte(blatt) -> list[str]:
    return [e.text for e in blatt.elemente if isinstance(e, Text)]


class TestSchreibweisen(unittest.TestCase):
    def test_jede_hat_ihr_beispiel(self):
        beispiele = [w.beispiel for w in schreibweisen.SCHREIBWEISEN]
        self.assertEqual(beispiele, ["1 1a", "1-1a", "L1 1a", "L1-1a"])

    def test_kennungen_sind_eindeutig(self):
        kennungen = [w.id for w in schreibweisen.SCHREIBWEISEN]
        self.assertEqual(len(set(kennungen)), len(kennungen))

    def test_unbekanntes_wird_zum_standard(self):
        """Eine Einstellung aus einer neueren Fassung haelt nicht auf."""
        self.assertIs(schreibweisen.holen("gibt-es-nicht"), schreibweisen.STANDARD)
        self.assertIs(schreibweisen.holen(None), schreibweisen.STANDARD)
        self.assertIs(schreibweisen.holen("mit_strich"), schreibweisen.MIT_STRICH)

    def test_zwei_rangierungen_nebeneinander(self):
        adressen = [Aderadresse(1, 1, "a"), Aderadresse(12, 7, "b")]
        self.assertEqual(
            adressen_schreiben(adressen, schreibweisen.MIT_STRICH), "L1-1a   L12-7b"
        )


class TestSchreibweiseImProjekt(unittest.TestCase):
    def test_vorgabe_ist_die_grundform(self):
        self.assertIs(Projekt().schreibweise, schreibweisen.STANDARD)

    def test_blatt_folgt_der_schreibweise(self):
        for kennung, erwartet in [
            ("einfach", "3 2a"),
            ("strich", "3-2a"),
            ("mit_l", "L3 2a"),
            ("mit_strich", "L3-2a"),
        ]:
            with self.subTest(schreibweise=kennung):
                blatt = blaetter(_projekt(kennung))[2]   # Leiste 1
                self.assertIn(erwartet, _texte(blatt))

    def test_tabellen_folgen_der_schreibweise(self):
        zeile = belegungszeilen(_projekt("mit_strich"))[0]
        self.assertEqual(zeile[4], "L1-1a")   # die eigene Adresse
        self.assertEqual(zeile[7], "L3-2a")   # ihre Rangierung

    def test_vermerk_steht_mit_im_rangierfeld(self):
        """Auf dem Blatt und in der Tabelle steht beides."""
        projekt = _projekt("mit_strich")
        projekt.verteiler.vermerk_setzen(Aderadresse(1, 1, "a"), "zur Klemmleiste")

        blatt = blaetter(projekt)[2]
        self.assertIn("L3-2a   zur Klemmleiste", _texte(blatt))
        self.assertEqual(belegungszeilen(projekt)[0][7], "L3-2a   zur Klemmleiste")

    def test_die_projektdatei_bleibt_bei_der_grundform(self):
        """Umgestellt wird die Anzeige, nicht das, was gespeichert wird."""
        import json
        import tempfile
        from pathlib import Path

        from verteilerly.projektdatei import speichern

        with tempfile.TemporaryDirectory() as ordner:
            ziel = Path(ordner) / "probe.vtly.json"
            speichern(_projekt("mit_strich"), ziel)
            daten = json.loads(ziel.read_text(encoding="utf-8"))
        rangierung = daten["verteiler"]["rangierungen"][0]
        self.assertEqual(rangierung["von"], "1 1a")
        self.assertEqual(rangierung["nach"], "3 2a")


if __name__ == "__main__":
    unittest.main()
