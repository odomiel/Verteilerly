"""Vorlagendateien pruefen, bevor sie ins Programm kommen.

Geprueft wird mit denselben Funktionen wie im Betrieb: was das Programm
beim Start beanstandet, muss der Bericht hier ebenso nennen - sonst
sagte der Bericht etwas anderes als das Programm tut.
"""

from __future__ import annotations

# Erst das Paket: es legt Einstellungs- und Arbeitsordner der
# Testreihe um, bevor etwas aus verteilerly Pfade liest.
from . import TESTHEIM  # noqa: F401

import pathlib
import tempfile
import unittest

from verteilerly.pfade import mitgeliefert
from verteilerly.pruefung import ARTEN, SICHERUNG, auffrischen, pruefen


class TestMitgelieferte(unittest.TestCase):
    """Was das Programm selbst ausliefert, muss durchgehen."""

    def test_jede_mitgelieferte_datei_ist_in_ordnung(self):
        orte = {
            "vorlage": "vorlagen",
            "blattvorlage": "blattvorlagen",
            "kabeltypen": "kabeltypen",
        }
        for art, ordner in orte.items():
            for datei in sorted((mitgeliefert() / ordner).glob("*.yaml")):
                with self.subTest(art=art, datei=datei.name):
                    bericht = pruefen(datei, art)
                    self.assertTrue(bericht.gut, bericht.fehler)
                    self.assertEqual(bericht.hinweise, [])
                    self.assertTrue(bericht.angaben)
                    self.assertIn("Ordnung", bericht.urteil)

    def test_die_arten_sind_vollstaendig(self):
        self.assertEqual(
            [art for art, _wie in ARTEN],
            ["vorlage", "blattvorlage", "kabeltypen"],
        )


class TestBericht(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.ziel = pathlib.Path(self.ordner.name)

    def _datei(self, name: str, inhalt: str) -> pathlib.Path:
        pfad = self.ziel / name
        pfad.write_text(inhalt, encoding="utf-8")
        return pfad

    def test_eine_gute_blattvorlage_wird_vorgelesen(self):
        pfad = self._datei(
            "eng.yaml",
            "id: eng\nname: Eng\nbeschreibung: Schmal\n"
            "spalten: [stift, ader, rangierung]\nbuchten_je_blatt: 1\n",
        )
        bericht = pruefen(pfad, "blattvorlage")
        self.assertTrue(bericht.gut)
        gelesen = " | ".join(bericht.angaben)
        self.assertIn("eng", gelesen)
        self.assertIn("stift, ader, rangierung", gelesen)
        self.assertIn("Schmal", gelesen)

    def test_ein_fehler_kommt_als_fehler_zurueck(self):
        pfad = self._datei("x.yaml", "id: x\nname: X\nbuchten_je_blatt: 0\n")
        bericht = pruefen(pfad, "blattvorlage")
        self.assertFalse(bericht.gut)
        self.assertIn("buchten_je_blatt", bericht.fehler)
        self.assertIn("nicht lesen", bericht.urteil)

    def test_kaputtes_yaml_wirft_nicht(self):
        pfad = self._datei("krumm.yaml", "kein: [gueltiges, {yaml")
        bericht = pruefen(pfad, "blattvorlage")
        self.assertFalse(bericht.gut)
        self.assertTrue(bericht.fehler)

    def test_eine_fehlende_datei_wirft_nicht(self):
        bericht = pruefen(self.ziel / "gibtsnicht.yaml", "vorlage")
        self.assertFalse(bericht.gut)
        self.assertTrue(bericht.fehler)

    def test_kein_abbild_einer_vorlage(self):
        """Eine Liste statt einer Abbildung ist keine Vorlage."""
        pfad = self._datei("liste.yaml", "- eins\n- zwei\n")
        bericht = pruefen(pfad, "blattvorlage")
        self.assertFalse(bericht.gut)

    def test_ein_vertippter_schluessel_steht_als_anmerkung_da(self):
        pfad = self._datei("eng.yaml", "id: eng\nname: Eng\nzeilenhohe_max: 7\n")
        bericht = pruefen(pfad, "blattvorlage")
        self.assertTrue(bericht.gut)          # gelesen wird sie trotzdem
        self.assertIn("zeilenhohe_max", " ".join(bericht.hinweise))
        self.assertIn("Anmerkungen", bericht.urteil)

    def test_der_dateiname_soll_die_kennung_tragen(self):
        """Sonst finden Umbenennen und Löschen die Datei später nicht."""
        pfad = self._datei("irgendwas.yaml", "id: eng\nname: Eng\n")
        bericht = pruefen(pfad, "blattvorlage")
        self.assertTrue(bericht.gut)
        self.assertIn("eng.yaml", " ".join(bericht.hinweise))

    def test_eine_verteilervorlage_zeigt_ihre_masse(self):
        pfad = self._datei(
            "gross.yaml",
            "id: gross\nname: Groß\nbuchten: 2\nleisten_je_bucht: 6\n"
            "da_je_leiste: 10\n",
        )
        bericht = pruefen(pfad, "vorlage")
        self.assertTrue(bericht.gut)
        gelesen = " | ".join(bericht.angaben)
        self.assertIn("2 × 6", gelesen)
        self.assertIn("120", gelesen)

    def test_kabeltypen_zaehlen_nur_die_eigene_datei(self):
        """Was danebenliegt, geht diesen Bericht nichts an."""
        self._datei("stoerung.yaml", "kein: [gueltiges, {yaml")
        pfad = self._datei(
            "eigen.yaml",
            "kuerzel: {rt: rot, bl: blau}\n"
            "kabeltypen:\n"
            "  - {id: probe, name: Probe, regel: liste, adern: [rt, bl]}\n",
        )
        bericht = pruefen(pfad, "kabeltypen")
        self.assertTrue(bericht.gut, bericht.fehler)
        gelesen = " | ".join(bericht.angaben)
        self.assertIn("Probe", gelesen)
        self.assertIn("1", gelesen)

    def test_eine_alte_blattvorlage_laesst_sich_auffrischen(self):
        """Was abgelegt ist, traegt der Bericht als Aufzufrischendes."""
        pfad = self._datei(
            "alt.yaml",
            "id: alt\n"
            "name: Alte Vorlage\n"
            "eigene_felder: [Auftrag, Revision]\n"
            "schriftfeld:\n"
            "  - [firma, eigene]\n"
            "  - [verteiler, leiste]\n"
            "belegung:\n"
            "  zelle_hoehe: 12\n"
            "  zeilen_kabel: 3\n",
        )
        bericht = pruefen(pfad, "blattvorlage")
        # Lesbar bleibt sie - sonst waere nichts aufzufrischen.
        self.assertTrue(bericht.gut, bericht.fehler)
        self.assertEqual(len(bericht.aufzufrischen), 2)
        self.assertIn("älteren Fassung", bericht.urteil)
        # Die Meldung nennt die Angabe, die Fassung und den Ersatz.
        gemeldet = " | ".join(bericht.hinweise)
        for stueck in ("eigene", "2026.09.30", "zeilen_kabel", "2026.10.04b7"):
            with self.subTest(stueck=stueck):
                self.assertIn(stueck, gemeldet)

        ergebnis = auffrischen(pfad, "blattvorlage")
        self.assertTrue(ergebnis.gelungen, ergebnis.fehler)
        self.assertEqual(len(ergebnis.aenderungen), 2)
        self.assertEqual(ergebnis.sicherung.name, "alt.yaml" + SICHERUNG)
        self.assertIn("eigene", ergebnis.sicherung.read_text(encoding="utf-8"))

        danach = pruefen(pfad, "blattvorlage")
        self.assertTrue(danach.gut, danach.fehler)
        self.assertEqual(danach.aufzufrischen, [])
        self.assertEqual(danach.hinweise, [])
        # Die eigenen Felder stehen jetzt einzeln im ersten Block.
        self.assertIn("Auftrag", danach.angaben[3])
        self.assertIn("Revision", danach.angaben[3])

    def test_zweimal_auffrischen_aendert_nichts_mehr(self):
        pfad = self._datei(
            "einmal.yaml",
            "id: einmal\nname: Einmal\neigene_felder: [Auftrag]\n"
            "schriftfeld:\n  - [firma, eigene]\n",
        )
        auffrischen(pfad, "blattvorlage")
        stand = pfad.read_text(encoding="utf-8")
        zweite = auffrischen(pfad, "blattvorlage")
        self.assertTrue(zweite.gelungen)
        self.assertEqual(zweite.aenderungen, [])
        self.assertIsNone(zweite.sicherung)
        self.assertEqual(pfad.read_text(encoding="utf-8"), stand)
        self.assertIn("nichts", zweite.urteil)

    def test_eine_heile_vorlage_hat_nichts_aufzufrischen(self):
        pfad = self._datei("heil.yaml", "id: heil\nname: Heil\nrand: 12\n")
        self.assertEqual(pruefen(pfad, "blattvorlage").aufzufrischen, [])
        self.assertEqual(auffrischen(pfad, "blattvorlage").aenderungen, [])

    def test_andere_arten_frischt_niemand_auf(self):
        """Verteilervorlagen und Kabeltypen haben nie etwas abgelegt."""
        pfad = self._datei("v.yaml", "id: v\nname: V\nbuchten: 1\n"
                           "leisten_je_bucht: 2\nda_je_leiste: 10\n")
        ergebnis = auffrischen(pfad, "vorlage")
        self.assertFalse(ergebnis.gelungen)
        self.assertIn("nichts aufzufrischen", ergebnis.fehler)

    def test_eine_unlesbare_datei_wird_nicht_ueberschrieben(self):
        pfad = self._datei("kaputt.yaml", "kein: [gueltiges, {yaml")
        vorher = pfad.read_text(encoding="utf-8")
        ergebnis = auffrischen(pfad, "blattvorlage")
        self.assertFalse(ergebnis.gelungen)
        self.assertEqual(pfad.read_text(encoding="utf-8"), vorher)
        self.assertFalse(pfad.with_suffix(".yaml" + SICHERUNG).exists())

    def test_eine_unbekannte_art_wird_gesagt(self):
        bericht = pruefen(self.ziel / "x.yaml", "wetterbericht")
        self.assertFalse(bericht.gut)
        self.assertIn("wetterbericht", bericht.fehler)


if __name__ == "__main__":
    unittest.main()
