"""Tests zur Ausgabe."""

import csv
import tempfile
import unittest
from pathlib import Path

from reportlab.pdfbase.pdfmetrics import stringWidth

from verteilerly.ausgabe import (
    AusgabeFehler,
    belegungszeilen,
    csv_schreiben,
    kabelzeilen,
    pdf_schreiben,
    xlsx_schreiben,
)
from verteilerly.ausgabe.pdf import (
    KLEINSTE_SCHRIFT,
    PT_JE_MM,
    SCHRIFT,
    SCHRIFT_FETT,
    _einpassen,
    _passende_groesse,
)
from verteilerly.ausgabe.tabellen import SPALTEN
from verteilerly.layout import Text, blaetter
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


class TestSchriftschnitt(unittest.TestCase):
    """Fett und kursiv gibt es im PDF als eigene Schnitte."""

    def test_die_vier_schnitte(self):
        from verteilerly.ausgabe.pdf import _schriftschnitt

        self.assertEqual(_schriftschnitt(False, False), "Helvetica")
        self.assertEqual(_schriftschnitt(True, False), "Helvetica-Bold")
        self.assertEqual(_schriftschnitt(False, True), "Helvetica-Oblique")
        self.assertEqual(_schriftschnitt(True, True), "Helvetica-BoldOblique")


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

    def test_nur_die_gewaehlten_blattarten(self):
        """Nur die Leistenblaetter - und gezaehlt wird ab 1."""
        pdf_schreiben(_projekt(), self.ziel, blattarten={"leisten"})
        from pypdf import PdfReader

        seiten = PdfReader(str(self.ziel)).pages
        self.assertEqual(len(seiten), 4)
        self.assertIn("Blatt 1 von 4", seiten[0].extract_text())

    def test_ohne_jede_blattart_gibt_es_nichts(self):
        from verteilerly.ausgabe import AusgabeFehler

        with self.assertRaises(AusgabeFehler):
            pdf_schreiben(_projekt(), self.ziel, blattarten=set())
        self.assertFalse(self.ziel.exists())

    def test_buchten_landen_als_eigene_seiten_im_pdf(self):
        """Ab drei Buchten bekommt jede Bucht eine eigene Seite."""
        projekt = _projekt()
        projekt.verteiler = Verteiler.aus_geometrie(4, 4, 10, name="Groß")
        pdf_schreiben(projekt, self.ziel)
        from pypdf import PdfReader

        seiten = PdfReader(str(self.ziel)).pages
        self.assertEqual(len(seiten), 1 + 4 + 16)
        kopf = "\n".join(s.extract_text() for s in seiten[1:5])
        for nummer in range(1, 5):
            self.assertIn(f"Bucht {nummer}", kopf)
        # Eine Bucht je Blatt heißt hochkant.
        for seite in seiten[1:5]:
            self.assertLess(float(seite.mediabox.width), float(seite.mediabox.height))

    def test_hoch_und_querformat(self):
        """Die Verteilerbelegung liegt quer, die Leistenblätter hoch."""
        pdf_schreiben(_projekt(), self.ziel)
        from pypdf import PdfReader

        seiten = PdfReader(str(self.ziel)).pages
        masse = [(float(s.mediabox.width), float(s.mediabox.height)) for s in seiten]
        self.assertLess(masse[0][0], masse[0][1])   # Deckblatt hoch
        # Der Probeverteiler hat eine Bucht - die Belegung steht hochkant.
        self.assertLess(masse[1][0], masse[1][1])
        self.assertLess(masse[2][0], masse[2][1])   # Leiste 1 hoch
        self.assertAlmostEqual(masse[0][0], 210 * PT_JE_MM, places=3)

    def test_zwei_buchten_legen_die_belegung_quer(self):
        """Zwei Buchten passen im Hochformat nicht nebeneinander."""
        from pypdf import PdfReader

        projekt = _projekt()
        projekt.verteiler = Verteiler.aus_geometrie(2, 4, 10, name="Breit")
        pdf_schreiben(projekt, self.ziel)
        seite = PdfReader(str(self.ziel)).pages[1]
        self.assertGreater(float(seite.mediabox.width), float(seite.mediabox.height))

    def test_inhalte_stehen_im_pdf(self):
        pdf_schreiben(_projekt(), self.ziel)
        from pypdf import PdfReader

        text = "\n".join(s.extract_text() for s in PdfReader(str(self.ziel)).pages)
        for erwartet in ["Musterfirma", "Leiste 1", "Magnetkontakt", "3 2a"]:
            with self.subTest(text=erwartet):
                self.assertIn(erwartet, text)

    def test_ein_eigenes_feld_der_blattvorlage_steht_im_pdf(self):
        """Welche eigenen Felder ein Blatt zeigt, sagt die Blattvorlage."""
        import dataclasses

        from pypdf import PdfReader

        from verteilerly.blattvorlagen import STANDARD

        from verteilerly.blattvorlagen import Schriftfeldeintrag

        vorlage = dataclasses.replace(
            STANDARD,
            eigene_felder=("Standort",),
            schriftfeld=(
                *STANDARD.schriftfeld[:-1],
                (*STANDARD.schriftfeld[-1], Schriftfeldeintrag("Standort")),
            ),
        )
        pdf_schreiben(_projekt(), self.ziel, vorlage)
        text = "\n".join(s.extract_text() for s in PdfReader(str(self.ziel)).pages)
        self.assertIn("Standort", text)
        self.assertIn("Keller", text)

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


class TestSchriftgroessen(unittest.TestCase):
    """Die Schrift passt sich dem Feld an."""

    def test_langer_text_wird_kleiner_statt_gekuerzt(self):
        lang = "geprüft am 07.09.2026, Schleifenwiderstand i.O."
        breite = 41 * PT_JE_MM
        klein = _passende_groesse(lang, SCHRIFT, 8.5, breite)
        self.assertLess(klein, 8.5)
        self.assertGreaterEqual(klein, KLEINSTE_SCHRIFT)
        self.assertLessEqual(stringWidth(lang, SCHRIFT, klein), breite)
        # Verkleinert reicht der Platz - gekuerzt wird dann nicht mehr.
        self.assertEqual(_einpassen(lang, SCHRIFT, klein, breite), lang)

    def test_passender_text_behaelt_seine_groesse(self):
        self.assertEqual(
            _passende_groesse("Melder 1a", SCHRIFT, 8.5, 43 * PT_JE_MM), 8.5
        )

    def test_unter_der_untergrenze_wird_gekuerzt(self):
        endlos = "Verteiler " * 30
        breite = 30 * PT_JE_MM
        klein = _passende_groesse(endlos, SCHRIFT, 8.5, breite)
        self.assertEqual(klein, KLEINSTE_SCHRIFT)
        self.assertTrue(_einpassen(endlos, SCHRIFT, klein, breite).endswith("…"))

    def test_quer_gesetzter_text_misst_sich_an_der_hoehe(self):
        """Ein langer Kabelname passt quer in die schmale Spalte."""
        from verteilerly.layout import Text

        lang = "Linie 1 — Melderkreis Erdgeschoss West"
        quer = Text(0, 0, 12, 90, lang, 7.0, drehung=90)
        laengs = Text(0, 0, 12, 90, lang, 7.0)
        self.assertEqual(quer.zeilenlaenge, 90)
        self.assertEqual(laengs.zeilenlaenge, 12)
        # Quer bleibt die Schrift, wie sie ist; waagerecht müsste sie
        # bis zur Untergrenze schrumpfen und würde dann noch gekürzt.
        self.assertEqual(
            _passende_groesse(lang, SCHRIFT, 7.0, quer.zeilenlaenge * PT_JE_MM), 7.0
        )
        self.assertEqual(
            _passende_groesse(lang, SCHRIFT, 7.0, laengs.zeilenlaenge * PT_JE_MM),
            KLEINSTE_SCHRIFT,
        )

    def test_quer_gesetzter_text_steht_im_pdf(self):
        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        ziel = Path(ordner.name) / "quer.pdf"

        v = Verteiler.aus_geometrie(1, 2, 10, name="Probe")
        v.kabel_anlegen("Linie 1 — Melderkreis Erdgeschoss West", 1, 1, 5)
        pdf_schreiben(Projekt(verteiler=v), ziel)

        from pypdf import PdfReader

        text = "\n".join(s.extract_text() for s in PdfReader(str(ziel)).pages)
        self.assertIn("Melderkreis Erdgeschoss West", text)

    def test_der_kabelname_bricht_um_statt_zu_schrumpfen(self):
        """Im schmalen Block steht er auf mehreren Zeilen."""
        from verteilerly.layout import (
            PUNKT_IN_MM,
            ZEILENABSTAND,
            umgebrochene_zeilen,
        )

        lang = "Melderkreis Erdgeschoss West"
        breite, hoehe = 18.0, 22.0        # Millimeter, Schrift in Punkt
        groesse, zeilen = umgebrochene_zeilen(lang, breite, hoehe, 11.0)
        self.assertGreater(len(zeilen), 1)
        self.assertEqual(" ".join(zeilen), lang)
        self.assertLessEqual(
            len(zeilen) * groesse * ZEILENABSTAND * PUNKT_IN_MM, hoehe
        )
        for zeile in zeilen:
            self.assertLessEqual(
                stringWidth(zeile, SCHRIFT, groesse), breite * PT_JE_MM
            )

    def test_alle_drei_wege_brechen_an_derselben_stelle(self):
        """Vorschau, PDF und Mappe fragen dasselbe Mass.

        Frueher rechnete jeder mit seiner eigenen Schrift - und dieselbe
        Beschriftung stand in der Vorschau zweizeilig, im PDF einzeilig
        ueber den ganzen Block und in der Mappe unverkleinert.
        """
        from verteilerly.layout import Text, textzeilen, verteilerbelegungen

        v = Verteiler.aus_geometrie(1, 4, 10, name="Muster")
        v.kabel_anlegen("Melderkreis Erdgeschoss West", 1, 1, 1)
        blatt = verteilerbelegungen(Projekt(verteiler=v))[0]
        feld = next(
            e for e in blatt.elemente
            if isinstance(e, Text) and e.text.startswith("Melderkreis")
        )
        groesse, zeilen = textzeilen(feld)
        self.assertEqual(zeilen, ["Melderkreis", "Erdgeschoss", "West"])
        # Was das gemeinsame Mass sagt, haelt auch Helvetica ein: das PDF
        # muss nicht nachtraeglich verkleinern.
        for zeile in zeilen:
            self.assertLessEqual(
                stringWidth(zeile, SCHRIFT, groesse), feld.breite * PT_JE_MM
            )

    def test_der_umgebrochene_kabelname_steht_im_pdf(self):
        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        ziel = Path(ordner.name) / "umbruch.pdf"

        v = Verteiler.aus_geometrie(1, 2, 10, name="Probe")
        v.kabel_anlegen("Melderkreis Erdgeschoss West", 1, 1, 2)
        pdf_schreiben(Projekt(verteiler=v), ziel)

        from pypdf import PdfReader

        text = "\n".join(s.extract_text() for s in PdfReader(str(ziel)).pages)
        # Umgebrochen steht jedes Wort noch da - gekuerzt waere es weg.
        for wort in ("Melderkreis", "Erdgeschoss", "West"):
            with self.subTest(wort=wort):
                self.assertIn(wort, text)

    def test_eine_zeile_kleiner_geht_vor_zwei_vollen(self):
        """Ein kleiner Block soll nicht vollgestopft aussehen.

        „Melder 1" passt in den schmalen Block nur umgebrochen, wenn die
        Schrift ihre volle Groesse behaelt - eine Stufe kleiner steht es
        auf einer Zeile und laesst Luft.
        """
        from verteilerly.layout import Text, textzeilen, verteilerbelegungen

        v = Verteiler.aus_geometrie(1, 4, 10, name="Muster")
        v.kabel_anlegen("Melder 1", 1, 1, 1)
        blatt = verteilerbelegungen(Projekt(verteiler=v))[0]
        feld = next(
            e for e in blatt.elemente
            if isinstance(e, Text) and e.text == "Melder 1"
        )
        groesse, zeilen = textzeilen(feld)
        self.assertEqual(zeilen, ["Melder 1"])
        self.assertLess(groesse, feld.groesse)
        # Kleiner als die kleine Schrift der Vorlage wird dafuer nicht
        # gesetzt - dann waere der Umbruch das Bessere.
        self.assertGreaterEqual(groesse, feld.einzeilig_ab)
        self.assertLessEqual(
            stringWidth(zeilen[0], SCHRIFT, groesse), feld.breite * PT_JE_MM
        )

    def test_kein_text_eines_blattes_laeuft_ueber(self):
        """Die Probe aufs Ganze: jedes Feld jedes Blattes nachgemessen."""
        v = Verteiler.aus_geometrie(2, 4, 10, name="Hauptverteiler Technikzentrale")
        v.kabel_anlegen("Linie 1 — Melderkreis Erdgeschoss West", 1, 1, 5)
        for da in range(1, 6):
            for seite in ("a", "b"):
                ader = v.ader(Aderadresse(1, da, seite))
                ader.bezeichnung = f"Melder {da}{seite} Treppenhaus Ost"
                ader.bemerkung = "geprüft am 07.09.2026, Schleifenwiderstand i.O."
        projekt = Projekt(verteiler=v, briefkopf={"firma": "Musterfirma GmbH & Co. KG"})

        from verteilerly.layout import ZEILENABSTAND, textzeilen

        for blatt in blaetter(projekt):
            for element in blatt.elemente:
                if not isinstance(element, Text) or not element.text.strip():
                    continue
                schrift = SCHRIFT_FETT if element.fett else SCHRIFT
                breite = element.zeilenlaenge * PT_JE_MM
                with self.subTest(blatt=blatt.titel, text=element.text):
                    if element.umbruch:
                        # Ein umgebrochener Text muss in Breite und Hoehe
                        # passen - eine Zeile zu viel liefe unten hinaus.
                        groesse, zeilen = textzeilen(element)
                        for zeile in zeilen:
                            self.assertLessEqual(
                                stringWidth(zeile, schrift, groesse), breite
                            )
                        self.assertLessEqual(
                            len(zeilen) * groesse * ZEILENABSTAND,
                            element.hoehe * PT_JE_MM,
                        )
                        continue
                    groesse = _passende_groesse(
                        element.text, schrift, element.groesse, breite
                    )
                    text = _einpassen(element.text, schrift, groesse, breite)
                    self.assertLessEqual(stringWidth(text, schrift, groesse), breite)


class TestTabellen(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.projekt = _projekt()

    def test_eine_zeile_je_ader(self):
        zeilen = belegungszeilen(self.projekt)
        self.assertEqual(len(zeilen), 80)
        self.assertEqual(len(zeilen[0]), len(SPALTEN))

    def test_mit_buchstaben_heisst_die_leiste_anders(self):
        """Spalte, Adresse und Rangierfeld folgen der Wahl - die Nummer bleibt."""
        from verteilerly.modell import LEISTEN_BUCHSTABEN

        self.projekt.leisten_schreibweise = LEISTEN_BUCHSTABEN
        erste = belegungszeilen(self.projekt)[0]
        self.assertEqual(erste[1], "A")
        self.assertEqual(erste[4], "A 1a")
        # Gezählt bleibt Zahl: dann sortiert Excel richtig.
        self.projekt.leisten_schreibweise = "zahlen"
        self.assertEqual(belegungszeilen(self.projekt)[0][1], 1)

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

    def _csv_zeilen(self) -> list[list[str]]:
        ziel = csv_schreiben(self.projekt, Path(self.ordner.name) / "probe.csv")
        with ziel.open(encoding="utf-8-sig", newline="") as datei:
            return list(csv.reader(datei, delimiter=";"))

    def test_csv_hat_kopfzeile_und_alle_adern(self):
        """Oben bleibt die Belegung - die erste Zeile ist ihre Kopfzeile."""
        zeilen = self._csv_zeilen()
        self.assertEqual(zeilen[0], list(SPALTEN))
        # 80 Adern, danach eine Leerzeile: dort endet der erste Block.
        self.assertEqual(len(zeilen[:81]), 81)
        self.assertEqual(zeilen[81], [])

    def test_csv_traegt_auch_kabel_und_projektdaten(self):
        """Dieselben Angaben wie die Mappe, als Blöcke darunter."""
        zeilen = self._csv_zeilen()
        flach = [";".join(z) for z in zeilen]
        self.assertIn("Kabel je Leiste", flach)
        self.assertIn("Projektdaten", flach)
        # Der Briefkopf steht unten, so wie das Schriftfeld am Blattfuß.
        self.assertGreater(flach.index("Projektdaten"), flach.index("Kabel je Leiste"))
        werte = {z[0]: z[1] for z in zeilen if len(z) == 2}
        self.assertEqual(werte.get("Verteiler"), self.projekt.verteiler.name)
        self.assertEqual(werte.get("Firma"), "Musterfirma")

    def test_eine_anschrift_bleibt_in_einer_zeile(self):
        """Sonst zerfiele die Tabelle an dieser Stelle in drei Zeilen."""
        self.projekt.briefkopf["kunde"] = "Firma Beliebig\nBeliebige Straße 7"
        zeilen = self._csv_zeilen()
        werte = {z[0]: z[1] for z in zeilen if len(z) == 2}
        self.assertEqual(werte.get("Kunde"), "Firma Beliebig · Beliebige Straße 7")

    def test_ohne_kabel_kein_leerer_block(self):
        from verteilerly.modell import Projekt, Verteiler

        leer = Projekt(verteiler=Verteiler.aus_geometrie(1, 1, 2, name="Leer"))
        ziel = csv_schreiben(leer, Path(self.ordner.name) / "leer.csv")
        text = ziel.read_text(encoding="utf-8-sig")
        self.assertNotIn("Kabel je Leiste", text)
        self.assertIn("Projektdaten", text)

    def test_csv_beginnt_mit_bom(self):
        """Ohne BOM zerlegt Excel die Umlaute."""
        ziel = csv_schreiben(self.projekt, Path(self.ordner.name) / "probe.csv")
        self.assertTrue(ziel.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_xlsx_traegt_blattbild_und_daten(self):
        """Vorn die Blätter, dahinter dieselben Daten als Tabelle."""
        ziel = xlsx_schreiben(self.projekt, Path(self.ordner.name) / "probe.xlsx")
        from openpyxl import load_workbook

        mappe = load_workbook(ziel)
        self.assertEqual(
            mappe.sheetnames,
            ["Deckblatt", "Verteilerbelegung", "Leiste 1", "Leiste 2", "Leiste 3",
             "Leiste 4", "Daten je Ader", "Kabel je Leiste", "Projektdaten"],
        )
        self.assertEqual(mappe["Daten je Ader"].max_row, 81)
        self.assertEqual(mappe["Daten je Ader"].freeze_panes, "A2")

    def test_xlsx_haelt_zahlen_als_zahlen(self):
        """Sonst sortiert Excel 10 vor 2."""
        ziel = xlsx_schreiben(self.projekt, Path(self.ordner.name) / "probe.xlsx")
        from openpyxl import load_workbook

        blatt = load_workbook(ziel)["Daten je Ader"]
        self.assertEqual(blatt.cell(row=2, column=2).value, 1)
        self.assertIsInstance(blatt.cell(row=2, column=3).value, int)

    def test_xlsx_uebernimmt_den_zellenstil(self):
        """Fett, kursiv und Ausrichtung kommen mit nach Excel."""
        from openpyxl import load_workbook
        from verteilerly.modell import Textstil

        ader = self.projekt.verteiler.leiste(1).stift(1).ader("a")
        ader.bezeichnung = "Hausanschluss"
        ader.stil_setzen("bezeichnung", Textstil("rechts", fett=True, kursiv=True))
        ziel = xlsx_schreiben(self.projekt, Path(self.ordner.name) / "probe.xlsx")

        blatt = load_workbook(ziel)["Leiste 1"]
        feld = next(
            zelle
            for zeile in blatt.iter_rows()
            for zelle in zeile
            if zelle.value == "Hausanschluss"
        )
        self.assertTrue(feld.font.bold)
        self.assertTrue(feld.font.italic)
        self.assertEqual(feld.alignment.horizontal, "right")

    def test_geteilte_zelle_steht_im_raster_hintereinander(self):
        """Excel hat keine halbe Spalte."""
        from openpyxl import load_workbook
        from verteilerly.modell import Zellenteilung

        ader = self.projekt.verteiler.leiste(1).stift(1).ader("a")
        ader.bezeichnung = "Amt 1"
        ader.teilung_setzen("bezeichnung", Zellenteilung(30, "Nst. 42"))
        ziel = xlsx_schreiben(self.projekt, Path(self.ordner.name) / "probe.xlsx")

        mappe = load_workbook(ziel)
        werte = [
            z.value for r in mappe["Leiste 1"].iter_rows() for z in r
            if isinstance(z.value, str) and z.value.startswith("Amt 1")
        ]
        self.assertEqual(werte, ["Amt 1 Nst. 42"])
        daten = [
            r[6] for r in mappe["Daten je Ader"].iter_rows(values_only=True)
            if r[6] and str(r[6]).startswith("Amt 1")
        ]
        self.assertEqual(daten, ["Amt 1 Nst. 42"])

    def test_briefkopf_erscheint_mit_beschriftung(self):
        ziel = xlsx_schreiben(self.projekt, Path(self.ordner.name) / "probe.xlsx")
        from openpyxl import load_workbook

        felder = {
            r[0].value: r[1].value
            for r in load_workbook(ziel)["Projektdaten"].iter_rows()
        }
        self.assertEqual(felder["Firma"], "Musterfirma")
        self.assertEqual(felder["Standort"], "Keller")


if __name__ == "__main__":
    unittest.main()
