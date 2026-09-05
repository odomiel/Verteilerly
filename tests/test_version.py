"""Tests zum Versionsschema."""

import datetime
import unittest

from verteilerly.version import (
    UngueltigeVersion,
    naechste_version,
    sortierschluessel,
    zerlegen,
    zusammensetzen,
)

TAG = datetime.date(2026, 9, 5)


class TestVersionsschema(unittest.TestCase):
    def test_erster_build_ist_nur_das_datum(self):
        self.assertEqual(zusammensetzen(TAG), "2026.09.05")

    def test_weitere_builds_bekommen_b_mit_nummer(self):
        self.assertEqual(zusammensetzen(TAG, 2), "2026.09.05b2")
        self.assertEqual(zusammensetzen(TAG, 12), "2026.09.05b12")

    def test_monat_und_tag_zweistellig(self):
        self.assertEqual(zusammensetzen(datetime.date(2027, 1, 7)), "2027.01.07")

    def test_zerlegen_und_zusammensetzen_passen_zusammen(self):
        for text in ["2026.09.05", "2026.09.05b2", "2027.12.31b10"]:
            with self.subTest(version=text):
                self.assertEqual(str(zerlegen(text)), text)

    def test_folge_an_einem_tag(self):
        bisher: list[str] = []
        for erwartet in ["2026.09.05", "2026.09.05b2", "2026.09.05b3"]:
            neu = naechste_version(bisher, TAG)
            self.assertEqual(neu, erwartet)
            bisher.append(neu)

    def test_neuer_tag_beginnt_von_vorn(self):
        bisher = ["2026.09.05", "2026.09.05b2"]
        self.assertEqual(
            naechste_version(bisher, datetime.date(2026, 9, 6)), "2026.09.06"
        )

    def test_fremde_tags_stoeren_nicht(self):
        bisher = ["v1.0", "irgendwas", "2026.09.05"]
        self.assertEqual(naechste_version(bisher, TAG), "2026.09.05b2")

    def test_ungueltiges_abgelehnt(self):
        for text in [
            "2026.9.5",       # nicht zweistellig
            "2026.09.05b1",   # der erste Build traegt kein b
            "v2026.09.05",    # kein Praefix vorgesehen
            "2026.13.01",     # Monat gibt es nicht
            "2026.09.05b",    # Nummer fehlt
            "",
        ]:
            with self.subTest(version=text), self.assertRaises(UngueltigeVersion):
                zerlegen(text)

    def test_zeitliche_sortierung(self):
        versionen = ["2026.09.06", "2026.09.05b10", "2026.09.05", "2026.09.05b2"]
        self.assertEqual(
            sorted(versionen, key=sortierschluessel),
            ["2026.09.05", "2026.09.05b2", "2026.09.05b10", "2026.09.06"],
        )


if __name__ == "__main__":
    unittest.main()
