"""Tests zur Leistenansicht.

Die Tabelle laeuft ohne Fenster: die Qt-Plattform "offscreen" genuegt,
weil nur das Modell geprueft wird, nicht das Bild.
"""

import os
import pathlib
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from verteilerly.gui.dialoge import DA_VORGABEN, NeuerVerteilerDialog
    from verteilerly.gui.vorschau import Vorschau
    from verteilerly.gui.leistenansicht import (
        SPALTE_ADER,
        SPALTE_BEMERKUNG,
        SPALTE_FARBE,
        SPALTE_KABEL,
        SPALTE_RANGIERUNG,
        SPALTE_STIFT,
        LeistenModell,
    )

    ANWENDUNG = QApplication.instance() or QApplication([])
except ImportError:  # ohne Qt laufen wenigstens die uebrigen Tests
    ANWENDUNG = None

from verteilerly.modell import Aderadresse, Projekt, Verteiler
from verteilerly.vorlagen import Vorlage, Vorlagen


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")


class TestLeistenModell(unittest.TestCase):
    def setUp(self):
        self.v = Verteiler.aus_geometrie(1, 4, 10)
        self.m = LeistenModell()
        self.m.setzen(self.v, 1)

    def _text(self, zeile, spalte):
        return self.m.data(self.m.index(zeile, spalte), Qt.ItemDataRole.DisplayRole)

    def _setzen(self, zeile, spalte, wert):
        return self.m.setData(
            self.m.index(zeile, spalte), wert, Qt.ItemDataRole.EditRole
        )

    def test_je_doppelader_zwei_zeilen(self):
        self.assertEqual(self.m.rowCount(), 20)

    def test_stiftnummer_nur_in_der_a_zeile(self):
        """Wie in den Mustertabellen steht die Nummer einmal je Stift."""
        self.assertEqual((self._text(0, SPALTE_STIFT), self._text(0, SPALTE_ADER)), ("1", "a"))
        self.assertEqual((self._text(1, SPALTE_STIFT), self._text(1, SPALTE_ADER)), ("", "b"))
        self.assertEqual(self._text(2, SPALTE_STIFT), "2")

    def test_adresse_zur_zeile(self):
        self.assertEqual(self.m.adresse(3), Aderadresse.parse("1 2b"))

    def test_farbe_und_bemerkung_landen_im_modell(self):
        self.assertTrue(self._setzen(0, SPALTE_FARBE, "rt"))
        self.assertTrue(self._setzen(1, SPALTE_BEMERKUNG, "defekt"))
        stift = self.v.leiste(1).stift(1)
        self.assertEqual(stift.a.farbe, "rt")
        self.assertEqual(stift.b.bemerkung, "defekt")

    def test_rangierung_wird_getippt_und_gespiegelt(self):
        self.assertTrue(self._setzen(0, SPALTE_RANGIERUNG, "3 2a"))
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG), "3 2a")
        self.assertEqual(self.v.ziele_von(Aderadresse.parse("3 2a")), [Aderadresse.parse("1 1a")])

    def test_zwei_rangierungen_je_feld(self):
        self.assertTrue(self._setzen(0, SPALTE_RANGIERUNG, "3 2a   4 5b"))
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG), "3 2a   4 5b")

    def test_fehlerhafte_eingabe_meldet_und_aendert_nichts(self):
        gemeldet = []
        self.m.fehler_gemeldet.connect(gemeldet.append)
        self.assertFalse(self._setzen(0, SPALTE_RANGIERUNG, "9 1a"))
        self.assertEqual(len(gemeldet), 1)
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG), "")

    def test_kabelname_nur_an_der_ersten_zeile_des_blocks(self):
        self.v.kabel_anlegen("Leitung zur Werkstatt", 1, 2, 3)
        self.assertEqual(self._text(0, SPALTE_KABEL), "")          # DA 1, frei
        self.assertEqual(self._text(2, SPALTE_KABEL), "Leitung zur Werkstatt")
        self.assertEqual(self._text(3, SPALTE_KABEL), "")          # b-Zeile
        self.assertEqual(self._text(4, SPALTE_KABEL), "")          # DA 3, im Block

    def test_leere_leiste_hat_keine_zeilen(self):
        self.m.setzen(None, None)
        self.assertEqual(self.m.rowCount(), 0)


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestVorschau(unittest.TestCase):
    """Die Vorschau haelt sich an dieselbe Blattfolge wie das PDF."""

    def setUp(self):
        self.v = Verteiler.aus_geometrie(1, 4, 10, name="Muster")
        self.vorschau = Vorschau()
        self.vorschau.projekt_setzen(Projekt(verteiler=self.v))

    def test_blattfolge_steht_zur_wahl(self):
        self.assertEqual(self.vorschau.auswahl.count(), 6)
        self.assertEqual(self.vorschau.auswahl.itemText(0), "Deckblatt")

    def test_sprung_zur_leiste(self):
        self.vorschau.blatt_zeigen("Leiste 3")
        self.assertEqual(self.vorschau.auswahl.currentText(), "Leiste 3")
        self.assertEqual(self.vorschau.flaeche.blatt.titel, "Leiste 3")

    def test_auffrischen_haelt_die_stelle(self):
        self.vorschau.blatt_zeigen("Leiste 2")
        self.v.kabel_anlegen("Leitung", 2, 1, 4)
        self.vorschau.aktualisieren()
        self.assertEqual(self.vorschau.auswahl.currentText(), "Leiste 2")

    def test_blattvorlage_waehlen_zeichnet_neu(self):
        """Die Vorschau folgt der gewählten Blattvorlage."""
        from verteilerly.blattvorlagen import Blattvorlage, Blattvorlagen

        knapp = Blattvorlage(id="knapp", name="Knapp", buchten_je_blatt=1)
        self.vorschau.blattvorlagen_setzen(Blattvorlagen([knapp]))
        self.assertEqual(self.vorschau.vorlagenwahl.count(), 2)
        self.vorschau.vorlagenwahl.setCurrentIndex(
            self.vorschau.vorlagenwahl.findData("knapp")
        )
        self.assertEqual(self.vorschau.blattvorlage.id, "knapp")

    def test_ohne_projekt_kein_blatt(self):
        self.vorschau.projekt_setzen(None)
        self.assertEqual(self.vorschau.auswahl.count(), 0)
        self.assertIsNone(self.vorschau.flaeche.blatt)


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestMenuezustaende(unittest.TestCase):
    """Ausgegraut ist, was gerade nicht geht."""

    def setUp(self):
        from verteilerly.gui.hauptfenster import Hauptfenster

        self.fenster = Hauptfenster()
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)

    def _projekt(self, mit_kabel=True):
        verteiler = Verteiler.aus_geometrie(1, 4, 10, name="Probe")
        if mit_kabel:
            verteiler.kabel_anlegen("Leitung", 1, 1, 4)
        self.fenster._projekt_setzen(Projekt(verteiler=verteiler), None)

    def test_ohne_verteiler_ist_fast_alles_aus(self):
        f = self.fenster
        for name in ("aktion_speichern", "aktion_speichern_unter", "aktion_pdf",
                     "aktion_xlsx", "aktion_csv", "aktion_kabel",
                     "aktion_kabel_weg", "aktion_vorlage", "aktion_briefkopf"):
            with self.subTest(aktion=name):
                self.assertFalse(getattr(f, name).isEnabled(), name)

    def test_neuer_und_oeffnen_gehen_immer(self):
        """Sonst käme man aus dem leeren Fenster nicht heraus."""
        eintraege = {
            a.text(): a for a in self.fenster.menuBar().actions()[0].menu().actions()
        }
        self.assertTrue(eintraege["&Neuer Verteiler…"].isEnabled())
        self.assertTrue(eintraege["Ö&ffnen…"].isEnabled())
        self.assertTrue(eintraege["&Beenden"].isEnabled())

    def test_mit_verteiler_geht_die_ausgabe(self):
        self._projekt()
        f = self.fenster
        for name in ("aktion_pdf", "aktion_xlsx", "aktion_csv", "aktion_kabel",
                     "aktion_vorlage", "aktion_briefkopf", "aktion_speichern_unter"):
            with self.subTest(aktion=name):
                self.assertTrue(getattr(f, name).isEnabled(), name)

    def test_kabel_entfernen_nur_auf_einem_kabel(self):
        self._projekt()
        f = self.fenster
        self.assertFalse(f.aktion_kabel_weg.isEnabled())   # noch nichts gewählt

        f.uebersicht.auswahl = (1, 2)                      # dort liegt das Kabel
        f._auswahl_gemeldet((1, 2))
        self.assertTrue(f.aktion_kabel_weg.isEnabled())

        f.uebersicht.auswahl = (1, 9)                      # freie Doppelader
        f._auswahl_gemeldet((1, 9))
        self.assertFalse(f.aktion_kabel_weg.isEnabled())

        f.uebersicht.auswahl = None                        # abgewählt
        f._auswahl_gemeldet(None)
        self.assertFalse(f.aktion_kabel_weg.isEnabled())

    def test_speichern_nur_wenn_es_etwas_zu_speichern_gibt(self):
        self._projekt()
        f = self.fenster
        self.assertTrue(f.aktion_speichern.isEnabled())    # noch nie gesichert

        f.pfad = pathlib.Path(self.ordner.name) / "p.vtly.json"
        f.speichern()
        self.assertFalse(f.aktion_speichern.isEnabled())   # nichts offen

        f._belegung_geaendert()
        self.assertTrue(f.aktion_speichern.isEnabled())    # wieder etwas offen

    def test_jeder_eintrag_sagt_wofuer_er_da_ist(self):
        """Der Statushinweis erscheint auch bei ausgegrauten Einträgen."""
        for name in ("aktion_speichern", "aktion_pdf", "aktion_kabel",
                     "aktion_kabel_weg", "aktion_vorlage", "aktion_briefkopf"):
            with self.subTest(aktion=name):
                self.assertTrue(getattr(self.fenster, name).statusTip())

    def test_leere_auswahlfelder_sind_aus(self):
        f = self.fenster
        self.assertFalse(f.leistenansicht.auswahl.isEnabled())
        self.assertFalse(f.vorschau.auswahl.isEnabled())
        self._projekt()
        self.assertTrue(f.leistenansicht.auswahl.isEnabled())
        f.vorschau.aktualisieren()
        self.assertTrue(f.vorschau.auswahl.isEnabled())


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestBriefkopfDialog(unittest.TestCase):
    """Felder an- und abwählen, ohne sie zu löschen."""

    def setUp(self):
        from verteilerly.gui.dialoge import BriefkopfDialog

        self.projekt = Projekt(
            verteiler=Verteiler.aus_geometrie(1, 4, 10, name="Probe"),
            briefkopf={"firma": "Musterfirma", "kundennummer": "K-1"},
            eigene_felder={"Standort": "Keller", "Vertrag": "bis 2028"},
        )
        self.projekt.sichtbarkeit_setzen("kundennummer", False)
        self.projekt.sichtbarkeit_setzen("Vertrag", False)
        self.dialog = BriefkopfDialog(self.projekt)

    def _zeile(self, name):
        for i in range(self.dialog.eigene.rowCount()):
            if self.dialog.eigene.item(i, 0).text() == name:
                return self.dialog.eigene.item(i, 0)
        raise AssertionError(f"Zeile {name} fehlt")

    def test_haken_zeigen_den_stand(self):
        self.assertTrue(self.dialog.haken["firma"].isChecked())
        self.assertFalse(self.dialog.haken["kundennummer"].isChecked())
        self.assertEqual(
            self._zeile("Standort").checkState(), Qt.CheckState.Checked
        )
        self.assertEqual(
            self._zeile("Vertrag").checkState(), Qt.CheckState.Unchecked
        )

    def test_abgewaehltes_feld_zeigt_seinen_inhalt_weiter(self):
        """Nicht löschen heißt: der Wert steht noch da, nur grau."""
        self.assertEqual(self.dialog.felder["kundennummer"].text(), "K-1")
        self.assertFalse(self.dialog.felder["kundennummer"].isEnabled())

    def test_abwaehlen_loescht_nichts(self):
        self.dialog.haken["firma"].setChecked(False)
        self.dialog.uebernehmen()
        self.assertIn("firma", self.projekt.ausgeblendet)
        self.assertEqual(self.projekt.briefkopf["firma"], "Musterfirma")
        self.assertFalse(self.projekt.sichtbar("firma"))

    def test_wieder_anwaehlen(self):
        self.dialog.haken["kundennummer"].setChecked(True)
        self._zeile("Vertrag").setCheckState(Qt.CheckState.Checked)
        self.dialog.uebernehmen()
        self.assertTrue(self.projekt.sichtbar("kundennummer"))
        self.assertTrue(self.projekt.sichtbar("Vertrag"))
        self.assertEqual(self.projekt.ausgeblendet, set())

    def test_eigenes_feld_abwaehlen_behaelt_den_wert(self):
        self._zeile("Standort").setCheckState(Qt.CheckState.Unchecked)
        self.dialog.uebernehmen()
        self.assertIn("Standort", self.projekt.ausgeblendet)
        self.assertEqual(self.projekt.eigene_felder["Standort"], "Keller")

    def test_alle_und_keine(self):
        self.dialog._alle_haken(False)
        self.assertFalse(any(h.isChecked() for h in self.dialog.haken.values()))
        self.dialog._alle_haken(True)
        self.assertTrue(all(h.isChecked() for h in self.dialog.haken.values()))

    def test_neues_feld_ist_zunaechst_angewaehlt(self):
        self.dialog._zeile_anhaengen("Neu", "Wert")
        self.assertEqual(self._zeile("Neu").checkState(), Qt.CheckState.Checked)


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestEinstellungen(unittest.TestCase):
    """Die Einstellungen liegen als Datei, nicht in der Registry."""

    def test_hauptfenster_schreibt_in_die_vorgesehene_datei(self):
        from verteilerly import pfade
        from verteilerly.gui.hauptfenster import Hauptfenster

        fenster = Hauptfenster()
        self.assertEqual(
            pathlib.Path(fenster.einstellungen.fileName()), pfade.einstellungsdatei()
        )
        from PySide6.QtCore import QSettings

        self.assertEqual(
            fenster.einstellungen.format(), QSettings.Format.IniFormat
        )


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestNeuerVerteilerDialog(unittest.TestCase):
    """Vorlage wählen, eigene Geometrie angeben, Vorlage sichern."""

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.vorlagen = Vorlagen(
            [Vorlage("klein", "Klein", 1, 4, 10, standard=True)]
        )
        self.dialog = NeuerVerteilerDialog(
            self.vorlagen, None, pathlib.Path(self.ordner.name)
        )
        self.dialog.eigen.setChecked(True)

    def test_da_stehen_zur_wahl(self):
        gewaehlt = [
            self.dialog.dawahl.itemText(i)
            for i in range(self.dialog.dawahl.count())
        ]
        self.assertEqual(gewaehlt, ["8 DA", "10 DA", "20 DA", "Benutzerdefiniert"])
        self.assertEqual(
            [self.dialog.dawahl.itemData(i) for i in range(3)], list(DA_VORGABEN)
        )

    def test_vorgabe_ist_zehn(self):
        self.assertEqual(self.dialog.da_je_leiste(), 10)

    def test_vorgabe_braucht_kein_zahlenfeld(self):
        self.dialog.dawahl.setCurrentIndex(0)
        self.assertEqual(self.dialog.da_je_leiste(), 8)
        # isVisibleTo, weil der Dialog im Test nicht auf den Schirm kommt.
        self.assertFalse(self.dialog.da.isVisibleTo(self.dialog))

    def test_benutzerdefiniert_blendet_das_zahlenfeld_ein(self):
        self.dialog.dawahl.setCurrentIndex(self.dialog.dawahl.count() - 1)
        self.dialog.da.setValue(16)
        self.assertTrue(self.dialog.da.isVisibleTo(self.dialog))
        self.assertEqual(self.dialog.da_je_leiste(), 16)
        self.assertIn("64 DA", self.dialog.summe.text())   # 4 Leisten zu 16

    def test_verteiler_folgt_der_wahl(self):
        self.dialog.dawahl.setCurrentIndex(2)      # 20 DA
        self.dialog.buchten.setValue(2)
        self.dialog.leisten.setValue(3)
        verteiler = self.dialog.verteiler()
        self.assertEqual(verteiler.da_gesamt, 120)
        self.assertEqual(verteiler.leiste(1).da_anzahl, 20)

    def test_geometrie_laesst_sich_als_vorlage_sichern(self):
        self.dialog.dawahl.setCurrentIndex(0)      # 8 DA
        self.dialog.leisten.setValue(5)
        vorlage = Vorlage.aus_verteiler(self.dialog.geometrie(), "Werkstatt")
        self.assertEqual(vorlage.da_je_leiste, 8)
        self.assertEqual(vorlage.da_gesamt, 40)

    def test_neue_vorlage_steht_sofort_zur_wahl(self):
        vorlage = Vorlage.aus_verteiler(self.dialog.geometrie(), "Werkstatt")
        self.vorlagen.aufnehmen(vorlage)
        self.dialog._vorlagenliste_auffrischen(vorlage.id)
        self.assertEqual(self.dialog.vorlagenwahl.currentData(), "werkstatt")
        self.assertEqual(self.dialog.vorlagenwahl.count(), 2)

    def test_ohne_ordner_kein_speichern(self):
        dialog = NeuerVerteilerDialog(self.vorlagen, None, None)
        self.assertFalse(dialog.als_vorlage.isEnabled())


if __name__ == "__main__":
    unittest.main()
