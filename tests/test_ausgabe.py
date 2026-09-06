"""Tests zur Ausgabe."""

import csv
import tempfile
import unittest
from pathlib import Path

from verteilerly.ausgabe import (
    AusgabeFehler,
    belegungszeilen,
    csv_schreiben,
    kabelzeilen,
    pdf_schreiben,
    xlsx_schreiben,
)
from verteilerly.ausgabe.pdf import PT_JE_MM, SCHRIFT, _einpassen
from verteilerly.ausgabe.tabellen import SPALTEN
from verteilerly.modell import Aderadresse, Projekt, Verteiler


def _projekt() -> Projekt:
    v = Verteiler.aus_geometrie(1, 4, 10, name="Muster", nummer="V-01")
    v.kabel_anlegen("Leitung zur Halle", 1, 1, 4, kabeltyp="jystyv", da_gesamt=6)
    v.rangierung_anlegen(Aderadresse.parse("1 1a"), Aderadresse.parse("3 2a"))
    v.leiste(1).stift(1).a.farbe = "rt"
    v.leiste(1).stift(1).a.bemerkung = "Magnetkontakt"
    return Projekt(
        verteiler=v,
        briefkopf={"firma": "Musterfirma", "erstellt_am": "01.09.2026"},
        eigene_felder={"Standort": "Keller"},
    )


class TestPdf(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.ziel = Path(self.ordner.name) / "probe.pdf"

    def test_eine_seite_je_blatt(self):
        pdf_schreiben(_projekt(), self.ziel)
        from pypdf import PdfReader

        seiten = PdfReader(str(self.ziel)).pages
        self.assertEqual(len(seiten), 6)

    def test_hoch_und_querformat(self):
        """Die Verteilerbelegung liegt quer, die Leistenblätter hoch."""
        pdf_schreiben(_projekt(), self.ziel)
        from pypdf import PdfReader

        seiten = PdfReader(str(self.ziel)).pages
        masse = [(float(s.mediabox.width), float(s.mediabox.height)) for s in seiten]
        self.assertLess(masse[0][0], masse[0][1])   # Deckblatt hoch
        self.assertGreater(masse[1][0], masse[1][1])  # Verteilerbelegung quer
        self.assertLess(masse[2][0], masse[2][1])   # Leiste 1 hoch
        self.assertAlmostEqual(masse[0][0], 210 * PT_JE_MM, places=3)

    def test_inhalte_stehen_im_pdf(self):
        pdf_schreiben(_projekt(), self.ziel)
        from pypdf import PdfReader

        text = "\n".join(s.extract_text() for s in PdfReader(str(self.ziel)).pages)
        for erwartet in ["Musterfirma", "Leiste 1", "Magnetkontakt", "3 2a", "Keller"]:
            with self.subTest(text=erwartet):
                self.assertIn(erwartet, text)

    def test_umlaute_bleiben_erhalten(self):
        projekt = _projekt()
        projekt.verteiler.leiste(1).stift(2).a.bemerkung = "Tür gekürzt"
        pdf_schreiben(projekt, self.ziel)
        from pypdf import PdfReader

        text = "\n".join(s.extract_text() for s in PdfReader(str(self.ziel)).pages)
        self.assertIn("Tür gekürzt", text)

    def test_keine_halbe_datei_bei_fehler(self):
        with self.assertRaises(AusgabeFehler):
            pdf_schreiben(_projekt(), Path(self.ordner.name) / "fehlt" / "x.pdf")
        self.assertFalse(self.ziel.exists())

    def test_zu_langer_text_wird_gekuerzt(self):
        """Lieber Punkte als Text, der über die Spalte hinausläuft."""
        kurz = _einpassen("Leitung", SCHRIFT, 8.5, 200)
        self.assertEqual(kurz, "Leitung")
        lang = _einpassen("Leitung zum Nebengebäude Ost", SCHRIFT, 8.5, 30)
        self.assertTrue(lang.endswith("…"))
        self.assertLess(len(lang), len("Leitung zum Nebengebäude Ost"))


class TestTabellen(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.projekt = _projekt()

    def test_eine_zeile_je_ader(self):
        zeilen = belegungszeilen(self.projekt)
        self.assertEqual(len(zeilen), 80)
        self.assertEqual(len(zeilen[0]), len(SPALTEN))

    def test_zeile_traegt_die_werte_der_ader(self):
        erste = belegungszeilen(self.projekt)[0]
        self.assertEqual(erste[:5], [1, 1, 1, "a", "1 1a"])
        self.assertEqual(erste[5], "rt")
        self.assertEqual(erste[7], "3 2a")
        self.assertEqual(erste[9], "Leitung zur Halle")

    def test_kabelzeile_haelt_die_kuerzung_fest(self):
        zeile = kabelzeilen(self.projekt)[0]
        self.assertEqual(zeile[2:5], [6, 4, "ja"])
        self.assertIn("Leiste 1 DA 1", zeile[5])

    def test_csv_hat_kopfzeile_und_alle_adern(self):
        ziel = csv_schreiben(self.projekt, Path(self.ordner.name) / "probe.csv")
        with ziel.open(encoding="utf-8-sig", newline="") as datei:
            zeilen = list(csv.reader(datei, delimiter=";"))
        self.assertEqual(zeilen[0], list(SPALTEN))
        self.assertEqual(len(zeilen), 81)

    def test_csv_beginnt_mit_bom(self):
        """Ohne BOM zerlegt Excel die Umlaute."""
        ziel = csv_schreiben(self.projekt, Path(self.ordner.name) / "probe.csv")
        self.assertTrue(ziel.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_xlsx_hat_drei_blaetter(self):
        ziel = xlsx_schreiben(self.projekt, Path(self.ordner.name) / "probe.xlsx")
        from openpyxl import load_workbook

        mappe = load_workbook(ziel)
        self.assertEqual(mappe.sheetnames, ["Belegung", "Kabel", "Projekt"])
        self.assertEqual(mappe["Belegung"].max_row, 81)
        self.assertEqual(mappe["Belegung"].freeze_panes, "A2")

    def test_xlsx_haelt_zahlen_als_zahlen(self):
        """Sonst sortiert Excel 10 vor 2."""
        ziel = xlsx_schreiben(self.projekt, Path(self.ordner.name) / "probe.xlsx")
        from openpyxl import load_workbook

        blatt = load_workbook(ziel)["Belegung"]
        self.assertEqual(blatt.cell(row=2, column=2).value, 1)
        self.assertIsInstance(blatt.cell(row=2, column=3).value, int)

    def test_briefkopf_erscheint_mit_beschriftung(self):
        ziel = xlsx_schreiben(self.projekt, Path(self.ordner.name) / "probe.xlsx")
        from openpyxl import load_workbook

        felder = {
            r[0].value: r[1].value
            for r in load_workbook(ziel)["Projekt"].iter_rows()
        }
        self.assertEqual(felder["Firma"], "Musterfirma")
        self.assertEqual(felder["Standort"], "Keller")


if __name__ == "__main__":
    unittest.main()
