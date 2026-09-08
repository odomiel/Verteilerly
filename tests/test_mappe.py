"""Tests zur Excel-Mappe im Blattbild.

Geprueft wird, was Excel von der Blattvorlage uebernimmt: Spaltenfolge und
-breite, Schriftgroessen, der verbundene Kabelblock samt Drehung und die
Seiteneinrichtung. Wie es dann aussieht, entscheidet Excel selbst - das
laesst sich hier nicht nachmessen.
"""

import pathlib
import tempfile
import unittest

from openpyxl import load_workbook

from verteilerly.ausgabe import xlsx_schreiben
from verteilerly.ausgabe.mappe import spaltenbreite, zeilenhoehe
from verteilerly.blattvorlagen import STANDARD, Blattvorlagen
from verteilerly.modell import Aderadresse, Projekt, Verteiler
from verteilerly.pfade import mitgeliefert


def _projekt() -> Projekt:
    v = Verteiler.aus_geometrie(1, 2, 10, name="Hauptverteiler", nummer="V-01")
    v.kabel_anlegen("Linie 1 — Melderkreis", 1, 1, 5, kabeltyp="jystyv")
    v.kabel_anlegen("Zuleitung BMZ", 1, 7, 3, da_gesamt=4)
    v.rangierung_anlegen(Aderadresse(1, 1, "a"), Aderadresse(2, 2, "a"))
    v.ader(Aderadresse(1, 1, "a")).bezeichnung = "Melder 1a"
    return Projekt(verteiler=v, briefkopf={"firma": "Musterfirma"})


class TestMasse(unittest.TestCase):
    def test_millimeter_werden_umgerechnet(self):
        # 25.4 mm sind ein Zoll: 96 Bildpunkte, 72 Punkt.
        self.assertAlmostEqual(zeilenhoehe(25.4), 72.0, places=1)
        self.assertAlmostEqual(spaltenbreite(25.4), (96 - 5) / 7, places=1)

    def test_keine_spalte_verschwindet(self):
        self.assertGreaterEqual(spaltenbreite(0.1), 1.0)


class TestBlattbild(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.ziel = pathlib.Path(self.ordner.name) / "probe.xlsx"
        self.projekt = _projekt()

    def _mappe(self, vorlage=STANDARD):
        xlsx_schreiben(self.projekt, self.ziel, vorlage)
        return load_workbook(self.ziel)

    def test_je_leiste_ein_blatt(self):
        mappe = self._mappe()
        self.assertIn("Leiste 1", mappe.sheetnames)
        self.assertIn("Leiste 2", mappe.sheetnames)
        self.assertEqual(mappe.sheetnames[0], "Deckblatt")

    def test_spalten_folgen_der_blattvorlage(self):
        blatt = self._mappe()["Leiste 1"]
        self.assertEqual(
            [zelle.value or "" for zelle in blatt[3]],
            [spalte.ueberschrift for spalte in STANDARD.spalten],
        )

    def test_stiftueberschrift_reicht_ueber_beide_spalten(self):
        blatt = self._mappe()["Leiste 1"]
        self.assertIn("A3:B3", [str(r) for r in blatt.merged_cells.ranges])
        self.assertEqual(blatt["A3"].value, "Stift")

    def test_zwei_zeilen_je_stift(self):
        blatt = self._mappe()["Leiste 1"]
        self.assertEqual(blatt.cell(row=4, column=1).value, "1")
        self.assertEqual(blatt.cell(row=4, column=2).value, "a")
        self.assertFalse(blatt.cell(row=5, column=1).value)   # b-Zeile
        self.assertEqual(blatt.cell(row=5, column=2).value, "b")
        self.assertEqual(blatt.cell(row=4, column=4).value, "Melder 1a")
        self.assertEqual(blatt.cell(row=4, column=5).value, "2 2a")

    def test_kabelblock_ist_verbunden_und_gedreht(self):
        blatt = self._mappe()["Leiste 1"]
        bereiche = [str(r) for r in blatt.merged_cells.ranges]
        self.assertIn("G4:G13", bereiche)     # 5 DA sind zehn Zeilen
        zelle = blatt["G4"]
        self.assertEqual(zelle.value, "Linie 1 — Melderkreis")
        self.assertEqual(zelle.alignment.text_rotation, 90)

    def test_gekuerztes_kabel_sagt_es(self):
        blatt = self._mappe()["Leiste 1"]
        self.assertIn("gekürzt: 3 von 4 DA", blatt["G16"].value)

    def test_waagerechte_vorlage_dreht_nicht(self):
        knapp = Blattvorlagen.laden(mitgeliefert() / "blattvorlagen").holen("knapp")
        blatt = self._mappe(knapp)["Leiste 1"]
        stelle = [s.feld for s in knapp.spalten].index("kabel") + 1
        zelle = blatt.cell(row=4, column=stelle)
        self.assertEqual(zelle.alignment.text_rotation, 0)
        self.assertEqual(zelle.value, "Linie 1 — Melderkreis")

    def test_spaltenbreiten_kommen_aus_der_vorlage(self):
        blatt = self._mappe()["Leiste 1"]
        breiten = STANDARD.breiten(210.0 - 2 * STANDARD.rand)
        self.assertAlmostEqual(
            blatt.column_dimensions["A"].width, spaltenbreite(breiten[0]), places=1
        )
        # Die Kabelspalte ist die schmalste - so steht es in der Vorlage.
        self.assertLess(
            blatt.column_dimensions["G"].width, blatt.column_dimensions["D"].width
        )

    def test_schriftgroessen_kommen_aus_der_vorlage(self):
        blatt = self._mappe()["Leiste 1"]
        self.assertEqual(blatt["A3"].font.sz, STANDARD.schrift_klein)   # Kopfzeile
        self.assertEqual(blatt["D4"].font.sz, STANDARD.schrift_normal)  # Aderzeile
        self.assertTrue(blatt["A3"].font.b)

    def test_schriftfeld_steht_unter_der_tabelle(self):
        blatt = self._mappe()["Leiste 1"]
        gefunden = {
            blatt.cell(row=zeile, column=1).value: blatt.cell(row=zeile, column=2).value
            for zeile in range(24, 40)
        }
        self.assertEqual(gefunden.get("Firma"), "Musterfirma")
        self.assertEqual(gefunden.get("Verteiler"), "Hauptverteiler")
        self.assertEqual(gefunden.get("Leiste"), "1")

    def test_seite_ist_auf_a4_eingerichtet(self):
        mappe = self._mappe()
        blatt = mappe["Leiste 1"]
        self.assertEqual(blatt.page_setup.orientation, "portrait")
        self.assertEqual(str(blatt.page_setup.paperSize), str(blatt.PAPERSIZE_A4))
        self.assertEqual(blatt.page_setup.fitToWidth, 1)
        # Die Verteilerbelegung liegt quer - wie im PDF.
        self.assertEqual(mappe["Verteilerbelegung"].page_setup.orientation, "landscape")

    def test_belegung_zeigt_die_kabel_als_block(self):
        blatt = self._mappe()["Verteilerbelegung"]
        self.assertEqual(blatt.cell(row=1, column=1).value, "Bucht 1")
        self.assertEqual(blatt.cell(row=2, column=1).value, "Leiste 1")
        self.assertIn("B2:F2", [str(r) for r in blatt.merged_cells.ranges])
        self.assertEqual(blatt["B2"].value, "Linie 1 — Melderkreis")

    def test_anschrift_steht_zeilenweise_im_schriftfeld(self):
        """Firma und Kunde wie in den Mustertabellen."""
        self.projekt.briefkopf["firma"] = (
            "Firma Beliebig\nBeliebige Straße 7\n77777 Beliebiger Ort"
        )
        blatt = self._mappe()["Leiste 1"]
        gefunden = [
            (blatt.cell(row=z, column=1).value, blatt.cell(row=z, column=2).value)
            for z in range(24, 42)
        ]
        self.assertIn(("Firma", "Firma Beliebig"), gefunden)
        self.assertIn((None, "Beliebige Straße 7"), gefunden)
        self.assertIn((None, "77777 Beliebiger Ort"), gefunden)

    def test_anschrift_bricht_in_den_projektdaten_um(self):
        self.projekt.briefkopf["firma"] = "Firma Beliebig\nBeliebige Straße 7"
        blatt = self._mappe()["Projektdaten"]
        zellen = [
            blatt.cell(row=z, column=2)
            for z in range(1, blatt.max_row + 1)
            if isinstance(blatt.cell(row=z, column=2).value, str)
            and "\n" in blatt.cell(row=z, column=2).value
        ]
        self.assertTrue(zellen)
        self.assertTrue(zellen[0].alignment.wrap_text)

    def test_daten_stehen_weiter_dahinter(self):
        """Das Blattbild tritt nicht an die Stelle der Daten."""
        mappe = self._mappe()
        self.assertEqual(mappe["Daten je Ader"].max_row, 41)   # 20 DA, zwei Adern
        self.assertEqual(mappe["Daten je Ader"].cell(row=2, column=5).value, "1 1a")


if __name__ == "__main__":
    unittest.main()
