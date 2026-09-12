"""Tests zur Leistenansicht.

Die Tabelle laeuft ohne Fenster: die Qt-Plattform "offscreen" genuegt,
weil nur das Modell geprueft wird, nicht das Bild.
"""

import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QMessageBox

    from verteilerly.gui.dialoge import DA_VORGABEN, NeuerVerteilerDialog
    from verteilerly.gui.vorschau import Vorschau
    from verteilerly.gui.leistenansicht import (
        SPALTE_ADER,
        SPALTE_BEMERKUNG,
        SPALTE_FARBE,
        SPALTE_KABEL,
        SPALTE_RANGIERUNG,
        SPALTE_RANGIERUNG_2,
        SPALTE_STIFT,
        UEBERSCHRIFTEN,
        LeistenAnsicht,
        LeistenModell,
        ZusammengefassteKopfzeile,
    )

    ANWENDUNG = QApplication.instance() or QApplication([])
except ImportError:  # ohne Qt laufen wenigstens die uebrigen Tests
    ANWENDUNG = None

from verteilerly.modell import BRIEFKOPF_FELDER, Aderadresse, Projekt, Verteiler
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

    def test_je_rangierung_ein_feld(self):
        """Zwei Ziele, zwei Zellen - eine Überschrift darüber."""
        self.assertTrue(self._setzen(0, SPALTE_RANGIERUNG, "3 2a"))
        self.assertTrue(self._setzen(0, SPALTE_RANGIERUNG_2, "4 5b"))
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG), "3 2a")
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG_2), "4 5b")
        self.assertEqual(UEBERSCHRIFTEN[SPALTE_RANGIERUNG], "Rangierung")
        self.assertEqual(UEBERSCHRIFTEN[SPALTE_RANGIERUNG_2], "")

    def test_das_zweite_feld_laesst_das_erste_stehen(self):
        self._setzen(0, SPALTE_RANGIERUNG, "3 2a")
        self._setzen(0, SPALTE_RANGIERUNG_2, "4 5b")
        self._setzen(0, SPALTE_RANGIERUNG_2, "2 1a")
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG), "3 2a")
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG_2), "2 1a")

    def test_geaendertes_erstes_feld_bleibt_das_erste(self):
        """Sonst sprängen die beiden Einträge beim Tippen hin und her."""
        self._setzen(0, SPALTE_RANGIERUNG, "3 2a")
        self._setzen(0, SPALTE_RANGIERUNG_2, "4 5b")
        self._setzen(0, SPALTE_RANGIERUNG, "2 1a")
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG), "2 1a")
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG_2), "4 5b")

    def test_ein_feld_leeren_loescht_nur_dieses(self):
        self._setzen(0, SPALTE_RANGIERUNG, "3 2a")
        self._setzen(0, SPALTE_RANGIERUNG_2, "4 5b")
        self._setzen(0, SPALTE_RANGIERUNG, "")
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG), "4 5b")
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG_2), "")
        self.assertEqual(
            self.v.ziele_von(Aderadresse.parse("3 2a")), []
        )

    def test_die_ueberschrift_reicht_ueber_beide_felder(self):
        """Eine Kopfzeile über den zwei Rangierfeldern, kein Strich dazwischen."""
        ansicht = LeistenAnsicht()
        kopf = ansicht.tabelle.horizontalHeader()
        self.assertIsInstance(kopf, ZusammengefassteKopfzeile)
        self.assertIn(SPALTE_RANGIERUNG, kopf._erste)
        self.assertIn(SPALTE_RANGIERUNG_2, kopf._weitere)
        self.assertNotIn(SPALTE_FARBE, kopf._weitere)

    def test_stift_reicht_ueber_nummer_und_ader(self):
        """Wie auf dem Blatt: eine Überschrift über beiden Spalten."""
        ansicht = LeistenAnsicht()
        kopf = ansicht.tabelle.horizontalHeader()
        self.assertIn(SPALTE_STIFT, kopf._erste)
        self.assertIn(SPALTE_ADER, kopf._weitere)
        self.assertEqual(UEBERSCHRIFTEN[SPALTE_STIFT], "Stift")
        self.assertEqual(UEBERSCHRIFTEN[SPALTE_ADER], "")

    def test_die_alte_schreibweise_geht_weiter(self):
        """„3 2a   4 5b“ in ein Feld getippt verteilt sich auf beide."""
        self.assertTrue(self._setzen(0, SPALTE_RANGIERUNG, "3 2a   4 5b"))
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG), "3 2a")
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG_2), "4 5b")

    def test_felder_folgen_der_schreibweise(self):
        """Umgestellt wird die Anzeige, getippt werden darf alles."""
        from verteilerly import schreibweisen

        self._setzen(0, SPALTE_RANGIERUNG, "3 2a")
        self.m.schreibweise_setzen(schreibweisen.MIT_STRICH)
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG), "L3-2a")

        # In der neuen Schreibweise getippt landet dieselbe Ader im Modell.
        self._setzen(0, SPALTE_RANGIERUNG, "L4-5b")
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG), "L4-5b")
        self.assertEqual(
            self.v.ziele_von(Aderadresse(4, 5, "b")), [Aderadresse(1, 1, "a")]
        )

        # Und die alte Form bleibt lesbar, gleich was eingestellt ist.
        self._setzen(0, SPALTE_RANGIERUNG, "2 1a")
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG), "L2-1a")

    def test_ohne_freitext_bleibt_ein_tippfehler_ein_fehler(self):
        """Abgeschaltet meldet das Feld wieder, was es nicht lesen kann."""
        gemeldet = []
        self.m.fehler_gemeldet.connect(gemeldet.append)
        self.assertFalse(self._setzen(0, SPALTE_RANGIERUNG, "zur Klemmleiste"))
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG), "")
        self.assertTrue(gemeldet)

    def test_freitext_landet_als_vermerk_an_der_ader(self):
        self.m.freitext_erlauben(True)
        self.assertTrue(self._setzen(0, SPALTE_RANGIERUNG, "zur Klemmleiste"))
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG), "zur Klemmleiste")
        self.assertEqual(
            self.v.ader(Aderadresse(1, 1, "a")).vermerk, "zur Klemmleiste"
        )
        # Ein Vermerk ist kein Ziel - gespiegelt wird nichts.
        self.assertEqual(self.v.rangierungen, [])

    def test_vermerk_und_ziel_nebeneinander(self):
        self.m.freitext_erlauben(True)
        self._setzen(0, SPALTE_RANGIERUNG, "extern")
        self._setzen(0, SPALTE_RANGIERUNG_2, "3 2a")
        # Der Vermerk bleibt in seinem Feld.
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG), "extern")
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG_2), "3 2a")
        self.assertEqual(
            self.v.ziele_von(Aderadresse(3, 2, "a")), [Aderadresse(1, 1, "a")]
        )

    def test_zweiter_vermerk_wird_abgewiesen(self):
        gemeldet = []
        self.m.fehler_gemeldet.connect(gemeldet.append)
        self.m.freitext_erlauben(True)
        self._setzen(0, SPALTE_RANGIERUNG, "extern")
        self.assertFalse(self._setzen(0, SPALTE_RANGIERUNG_2, "auch extern"))
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG_2), "")
        self.assertTrue(gemeldet)

    def test_vermerk_leeren_laesst_das_ziel_stehen(self):
        self.m.freitext_erlauben(True)
        self._setzen(0, SPALTE_RANGIERUNG, "extern")
        self._setzen(0, SPALTE_RANGIERUNG_2, "3 2a")
        self._setzen(0, SPALTE_RANGIERUNG, "")
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG), "3 2a")
        self.assertEqual(self.v.ader(Aderadresse(1, 1, "a")).vermerk, "")

    def test_ziel_geht_dem_freitext_vor(self):
        """Was sich als Ziel lesen lässt, bleibt ein Ziel."""
        self.m.freitext_erlauben(True)
        self._setzen(0, SPALTE_RANGIERUNG, "3 2a")
        self.assertEqual(self.v.ader(Aderadresse(1, 1, "a")).vermerk, "")
        self.assertEqual(len(self.v.rangierungen), 1)

    def test_fehlerhafte_eingabe_meldet_und_aendert_nichts(self):
        gemeldet = []
        self.m.fehler_gemeldet.connect(gemeldet.append)
        self.assertFalse(self._setzen(0, SPALTE_RANGIERUNG, "9 1a"))
        self.assertEqual(len(gemeldet), 1)
        self.assertEqual(self._text(0, SPALTE_RANGIERUNG), "")

    def test_kabelname_ist_an_der_ersten_zeile_aenderbar(self):
        """Der Tippfehler in einer Beschriftung ist kein Grund,
        das Kabel abzunehmen."""
        kabel = self.v.kabel_anlegen("Linei 1 Tipfehler", 1, 3, 4, da_gesamt=6)
        zeile = (3 - 1) * 2                       # Stift 3, Ader a

        # Angezeigt wird der Zusatz, getippt wird die reine Beschriftung.
        self.assertEqual(self._text(zeile, SPALTE_KABEL), "Linei 1 Tipfehler (gekürzt)")
        self.assertEqual(
            self.m.data(self.m.index(zeile, SPALTE_KABEL), Qt.ItemDataRole.EditRole),
            "Linei 1 Tipfehler",
        )
        self.assertTrue(self._setzen(zeile, SPALTE_KABEL, "Linie 1 — Melderkreis"))
        self.assertEqual(kabel.beschriftung, "Linie 1 — Melderkreis")
        self.assertEqual(
            self._text(zeile, SPALTE_KABEL), "Linie 1 — Melderkreis (gekürzt)"
        )

    def test_kabel_ohne_beschriftung_laesst_sich_beschriften(self):
        """Ein Kabel ohne Text war in der Spalte nicht anzuklicken."""
        kabel = self.v.kabel_anlegen("", 1, 3, 4)
        zeile = (3 - 1) * 2

        self.assertTrue(
            self.m.flags(self.m.index(zeile, SPALTE_KABEL))
            & Qt.ItemFlag.ItemIsEditable
        )
        self.assertTrue(self._setzen(zeile, SPALTE_KABEL, "Linie 1"))
        self.assertEqual(kabel.beschriftung, "Linie 1")
        self.assertEqual(self._text(zeile, SPALTE_KABEL), "Linie 1")

    def test_kabelspalte_nur_dort_aenderbar_wo_das_kabel_anfaengt(self):
        self.v.kabel_anlegen("Leitung", 1, 3, 4)
        zeile = (3 - 1) * 2

        def aenderbar(z):
            return bool(
                self.m.flags(self.m.index(z, SPALTE_KABEL))
                & Qt.ItemFlag.ItemIsEditable
            )

        self.assertTrue(aenderbar(zeile))
        self.assertFalse(aenderbar(zeile + 1))    # b-Zeile desselben Stifts
        self.assertFalse(aenderbar(0))            # dort liegt kein Kabel

    def test_kabelname_nur_an_der_ersten_zeile_des_blocks(self):
        self.v.kabel_anlegen("Leitung zur Werkstatt", 1, 2, 3)
        self.assertEqual(self._text(0, SPALTE_KABEL), "")          # DA 1, frei
        self.assertEqual(self._text(2, SPALTE_KABEL), "Leitung zur Werkstatt")
        self.assertEqual(self._text(3, SPALTE_KABEL), "")          # b-Zeile
        self.assertEqual(self._text(4, SPALTE_KABEL), "")          # DA 3, im Block

    def test_pfeile_schalten_durch_die_leisten(self):
        """Leiste für Leiste, ohne das Aufklappmenü."""
        ansicht = LeistenAnsicht()
        ansicht.verteiler_setzen(self.v)
        gemeldet = []
        ansicht.leiste_gewechselt.connect(gemeldet.append)

        self.assertEqual(ansicht.auswahl.currentData(), 1)
        self.assertFalse(ansicht.zurueck.isEnabled())    # am Anfang
        self.assertTrue(ansicht.vor.isEnabled())

        ansicht.vor.click()
        self.assertEqual(ansicht.auswahl.currentData(), 2)
        self.assertEqual(gemeldet[-1], 2)
        self.assertTrue(ansicht.zurueck.isEnabled())

        ansicht.zurueck.click()
        self.assertEqual(ansicht.auswahl.currentData(), 1)

    def test_pfeile_enden_an_der_letzten_leiste(self):
        ansicht = LeistenAnsicht()
        ansicht.verteiler_setzen(self.v)
        for _ in range(10):
            ansicht.vor.click()
        self.assertEqual(ansicht.auswahl.currentData(), 4)   # vier Leisten
        self.assertFalse(ansicht.vor.isEnabled())
        self.assertTrue(ansicht.zurueck.isEnabled())

    def test_ohne_verteiler_sind_die_pfeile_aus(self):
        ansicht = LeistenAnsicht()
        ansicht.verteiler_setzen(None)
        self.assertFalse(ansicht.zurueck.isEnabled())
        self.assertFalse(ansicht.vor.isEnabled())

    def test_leere_leiste_hat_keine_zeilen(self):
        self.m.setzen(None, None)
        self.assertEqual(self.m.rowCount(), 0)


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestThema(unittest.TestCase):
    """Der dunkle Satz ist eine vollwertige Alternative."""

    def test_ankreuzfelder_haben_eine_eigene_regel(self):
        """Ohne sie zeichnet Fusion sie dunkel auf dunkel."""
        from verteilerly.gui.thema import DUNKEL, HELL, stilblatt

        for farben in (HELL, DUNKEL):
            with self.subTest(satz=farben.name):
                blatt = stilblatt(farben)
                self.assertIn("QCheckBox::indicator", blatt)
                # Angekreuzt ist gefüllt, offen trägt es die Feldfarbe.
                self.assertIn(f"background: {farben.akzent}", blatt)
                self.assertIn(f"background: {farben.flaeche}", blatt)


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestUebersicht(unittest.TestCase):
    """Im Bearbeitungsmodus bleibt jede Leiste unterteilt."""

    def test_auch_leere_leisten_bleiben_unterteilt(self):
        from PySide6.QtGui import QImage

        from verteilerly.gui.uebersicht import ZELLE_B, Uebersicht

        v = Verteiler.aus_geometrie(1, 2, 10)
        v.kabel_anlegen("Leitung", 1, 1, 4)
        ansicht = Uebersicht()
        ansicht.verteiler_setzen(v)
        ansicht.resize(520, 200)
        bild = QImage(ansicht.size(), QImage.Format.Format_RGB32)
        ansicht.render(bild)

        # Waagerecht durch die zweite Leiste - dort liegt kein Kabel.
        kasten = ansicht._kaesten[2]
        y = kasten.center().y()
        grund = bild.pixel(kasten.left() + ZELLE_B // 2, y)
        striche = sum(
            1
            for x in range(kasten.left() + 1, kasten.right())
            if bild.pixel(x, y) != grund
        )
        # Neun Trennstriche zwischen zehn Doppeladern, dazu die Ränder.
        self.assertGreaterEqual(striche, 9)


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

    def test_blattvorlage_umstellen_zeichnet_neu(self):
        """Die Vorschau folgt der gewählten Blattvorlage."""
        from verteilerly.blattvorlagen import Blattvorlage, Blattvorlagen

        knapp = Blattvorlage(id="knapp", name="Knapp", buchten_je_blatt=1)
        self.vorschau.blattvorlagen_setzen(Blattvorlagen([knapp]))
        # Gewählt wird nicht mehr hier, aber der Name steht daneben.
        self.assertEqual(self.vorschau.blattvorlage.id, "standard")
        self.assertEqual(self.vorschau.vorlagenname.text(), "Standard")

        gemeldet = []
        self.vorschau.blattvorlage_gewechselt.connect(gemeldet.append)
        self.vorschau.blattvorlage_setzen("knapp")
        self.assertEqual(self.vorschau.blattvorlage.id, "knapp")
        self.assertEqual(self.vorschau.vorlagenname.text(), knapp.name)
        self.assertEqual(gemeldet, ["knapp"])

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
                     "aktion_kabel_weg", "aktion_vorlage", "aktion_projektdaten"):
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
                     "aktion_vorlage", "aktion_projektdaten", "aktion_speichern_unter"):
            with self.subTest(aktion=name):
                self.assertTrue(getattr(f, name).isEnabled(), name)

    def test_kabel_bearbeiten_folgt_der_auswahl(self):
        """Der Eintrag greift nur, wo wirklich ein Kabel liegt."""
        f = self.fenster
        self._projekt()
        f.uebersicht.auswahl = None
        f.aktionen_auffrischen()
        self.assertFalse(f.aktion_kabel_aendern.isEnabled())

        f.uebersicht.auswahl = (1, 1)
        f.aktionen_auffrischen()
        self.assertTrue(f.aktion_kabel_aendern.isEnabled())
        self.assertTrue(f.aktion_kabel_weg.isEnabled())

    def test_bearbeiten_aendert_beschriftung_und_typ(self):
        from verteilerly.gui.dialoge import KabelDialog

        f = self.fenster
        self._projekt()
        kabel = f.projekt.verteiler.kabel[0]

        def antworten(dialog):
            dialog.beschriftung.setText("Linie 1 — neu")
            dialog.kabel_da.setValue(kabel.da_aufgelegt + 2)
            return KabelDialog.DialogCode.Accepted

        with mock.patch.object(KabelDialog, "exec", antworten):
            f.kabel_bearbeiten(kabel)

        self.assertEqual(kabel.beschriftung, "Linie 1 — neu")
        self.assertEqual(kabel.da_gesamt, kabel.da_aufgelegt + 2)
        self.assertTrue(kabel.gekuerzt)
        self.assertIn(kabel, f.projekt.verteiler.kabel)

    def test_bearbeiten_kann_das_kabel_abnehmen(self):
        from verteilerly.gui.dialoge import KabelDialog

        f = self.fenster
        self._projekt()
        kabel = f.projekt.verteiler.kabel[0]

        def entfernen(dialog):
            dialog._entfernen()
            return KabelDialog.DialogCode.Accepted

        with mock.patch.object(KabelDialog, "exec", entfernen):
            f.kabel_bearbeiten(kabel)
        self.assertEqual(f.projekt.verteiler.kabel, [])

    def test_abgebrochenes_bearbeiten_aendert_nichts(self):
        from verteilerly.gui.dialoge import KabelDialog

        f = self.fenster
        self._projekt()
        kabel = f.projekt.verteiler.kabel[0]
        vorher = kabel.beschriftung

        with mock.patch.object(
            KabelDialog, "exec", lambda dialog: KabelDialog.DialogCode.Rejected
        ):
            f.kabel_bearbeiten(kabel)
        self.assertEqual(kabel.beschriftung, vorher)
        self.assertIn(kabel, f.projekt.verteiler.kabel)

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

    def test_geaenderter_verteilername_steht_im_fenstertitel(self):
        from verteilerly.gui.dialoge import ProjektdatenDialog

        f = self.fenster
        self._projekt()
        self.assertIn("Probe", f.windowTitle())

        def umbenennen(dialog):
            dialog.verteilername.setText("Verteiler Keller")
            return ProjektdatenDialog.DialogCode.Accepted

        with mock.patch.object(ProjektdatenDialog, "exec", umbenennen):
            f.projektdaten_bearbeiten()
        self.assertEqual(f.projekt.verteiler.name, "Verteiler Keller")
        self.assertIn("Verteiler Keller", f.windowTitle())

    def test_paket_hin_und_zurueck(self):
        """Sichern, etwas verstellen, einspielen - es ist wieder da."""
        import tempfile
        from pathlib import Path

        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QFileDialog

        from verteilerly import pfade
        from verteilerly.gui.dialoge import PaketDialog

        f = self.fenster
        with tempfile.TemporaryDirectory() as ordner:
            # Eigene Einstellungsdatei und eigener Arbeitsordner: die
            # übrigen Fenster der Testreihe schreiben sonst dazwischen.
            conf = Path(ordner) / "Verteilerly.conf"
            daten = Path(ordner) / "daten"
            (daten / "vorlagen").mkdir(parents=True)
            (daten / "vorlagen" / "eigen.yaml").write_text(
                "id: eigen\nname: Eigen\n", encoding="utf-8"
            )
            f.einstellungen = QSettings(str(conf), QSettings.Format.IniFormat)
            f.einstellungen.setValue("blattvorlage", "knapp")
            f.einstellungen.setValue("schreibweise", "mit_strich")
            f.einstellungen.sync()
            ziel = str(Path(ordner) / "paket.zip")

            with mock.patch.object(pfade, "einstellungsdatei", return_value=conf), \
                 mock.patch.object(pfade, "eigener_datenordner", return_value=daten):
                with mock.patch.object(
                    QFileDialog, "getSaveFileName", return_value=(ziel, "")
                ), mock.patch.object(
                    PaketDialog, "exec",
                    lambda dialog: PaketDialog.DialogCode.Accepted,
                ):
                    f.paket_sichern()
                self.assertTrue(Path(ziel).is_file())

                # Nach dem Sichern verstellen und die eigene Vorlage löschen …
                f.einstellungen.setValue("blattvorlage", "standard")
                f.einstellungen.setValue("schreibweise", "einfach")
                (daten / "vorlagen" / "eigen.yaml").unlink()

                with mock.patch.object(
                    QFileDialog, "getOpenFileName", return_value=(ziel, "")
                ), mock.patch.object(
                    PaketDialog, "exec",
                    lambda dialog: PaketDialog.DialogCode.Accepted,
                ):
                    f.paket_einspielen()

                # … und das Paket bringt beides zurück, ohne Neustart.
                self.assertTrue((daten / "vorlagen" / "eigen.yaml").is_file())
                self.assertEqual(f.einstellungen.value("blattvorlage"), "knapp")
                self.assertEqual(f.vorschau.blattvorlage.id, "knapp")
                self.assertEqual(f.schreibweise.id, "mit_strich")

    def test_auswahl_bietet_nur_an_was_es_gibt(self):
        """Ein Paket ohne Kabeltypen kann keine mitbringen."""
        from verteilerly.gui.dialoge import PaketDialog

        dialog = PaketDialog(
            "Probe", {"vorlagen": 3, "blattvorlagen": 0, "kabeltypen": 2,
                      "einstellungen": 1}
        )
        self.assertEqual(dialog.auswahl(), {"vorlagen", "kabeltypen", "einstellungen"})
        self.assertFalse(dialog.haken["blattvorlagen"].isEnabled())
        self.assertIn("(3)", dialog.haken["vorlagen"].text())

        # Ohne einen einzigen Haken gibt es nichts zu tun.
        for haken in dialog.haken.values():
            haken.setChecked(False)
        self.assertFalse(dialog.knoepfe.buttons()[0].isEnabled())

    def test_kein_paket_wird_abgewiesen(self):
        import tempfile
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog

        f = self.fenster
        with tempfile.TemporaryDirectory() as ordner:
            fremd = Path(ordner) / "fremd.zip"
            fremd.write_text("kein ZIP", encoding="utf-8")
            gemeldet = {}
            with mock.patch.object(
                QFileDialog, "getOpenFileName", return_value=(str(fremd), "")
            ), mock.patch.object(
                QMessageBox, "critical",
                lambda *args: gemeldet.setdefault("titel", args[1]),
            ):
                f.paket_einspielen()
        self.assertEqual(gemeldet.get("titel"), "Kein Paket")

    def test_ueber_nennt_die_bausteine_mit_fassung(self):
        """Was drinsteckt, ist im Programm nachzusehen."""
        from PySide6.QtWidgets import QMessageBox

        from verteilerly import bestand

        gezeigt = {}

        def fangen(eltern, titel, text):
            gezeigt["text"] = text

        with mock.patch.object(QMessageBox, "about", fangen):
            self.fenster.ueber()

        for teil in bestand.abhaengigkeiten():
            with self.subTest(baustein=teil.name):
                self.assertIn(teil.name, gezeigt["text"])
                self.assertIn(teil.fassung, gezeigt["text"])
                self.assertIn(teil.lizenz, gezeigt["text"])

    def test_jeder_eintrag_sagt_wofuer_er_da_ist(self):
        """Der Statushinweis erscheint auch bei ausgegrauten Einträgen."""
        for name in ("aktion_speichern", "aktion_pdf", "aktion_kabel",
                     "aktion_kabel_weg", "aktion_vorlage", "aktion_projektdaten"):
            with self.subTest(aktion=name):
                self.assertTrue(getattr(self.fenster, name).statusTip())

    def test_schreibweise_wirkt_und_wird_gemerkt(self):
        """Die Wahl gilt für Editor, Blatt und Ausgabe."""
        from verteilerly import schreibweisen

        f = self.fenster
        self._projekt()
        f.schreibweise_waehlen("mit_strich")
        self.assertIs(f.schreibweise, schreibweisen.MIT_STRICH)
        self.assertIs(f.leistenansicht.modell.schreibweise, schreibweisen.MIT_STRICH)
        self.assertEqual(f.projekt.rangierung_schreibweise, "mit_strich")
        self.assertEqual(f.einstellungen.value("schreibweise"), "mit_strich")
        angehakt = [e for e in f.schreibweisen_gruppe.actions() if e.isChecked()]
        self.assertEqual([e.data() for e in angehakt], ["mit_strich"])

        # Auch ein danach geöffnetes Projekt folgt der Wahl.
        self._projekt()
        self.assertEqual(f.projekt.rangierung_schreibweise, "mit_strich")
        f.schreibweise_waehlen("einfach")

    def test_blattvorlage_ist_unter_einstellungen_zu_aendern(self):
        """Die Wahl steckt im Einstellungsmenü, nicht mehr am Blattrand."""
        from verteilerly.gui.dialoge import BlattvorlagenDialog

        f = self.fenster
        self._projekt()
        vorher = f.vorschau.blattvorlage.id
        ziel = next(v.id for v in f.blattvorlagen.alle if v.id != vorher)

        def waehlen(dialog):
            stelle = next(
                i for i in range(dialog.liste.count())
                if dialog.liste.item(i).data(Qt.ItemDataRole.UserRole) == ziel
            )
            dialog.liste.setCurrentRow(stelle)
            return BlattvorlagenDialog.DialogCode.Accepted

        with mock.patch.object(BlattvorlagenDialog, "exec", waehlen):
            f.blattvorlage_waehlen()
        self.assertEqual(f.vorschau.blattvorlage.id, ziel)
        self.assertEqual(f.einstellungen.value("blattvorlage"), ziel)

        f.vorschau.blattvorlage_setzen(vorher)

    def test_einstellungsmenue_sammelt_die_einstellungen(self):
        """Was in der Verteilerly.conf steht, steht auch unter Einstellungen."""
        from PySide6.QtWidgets import QMenu

        menues = {
            menue.title().replace("&", ""): menue
            for menue in self.fenster.menuBar().findChildren(QMenu)
        }
        self.assertIn("Einstellungen", menues)
        eintraege = [
            eintrag.text().replace("&", "")
            for eintrag in menues["Einstellungen"].actions()
            if eintrag.text()
        ]
        self.assertEqual(
            eintraege,
            ["Blattvorlage…", "Vorgaben für neue Verteiler…",
             "Vorlagen und Einstellungen sichern…",
             "Vorlagen und Einstellungen einspielen…",
             "Schreibweise der Rangierungen", "Freitext im Rangierfeld zulassen"],
        )

    def test_jede_schreibweise_steht_im_menue(self):
        from verteilerly import schreibweisen

        eintraege = self.fenster.schreibweisen_gruppe.actions()
        self.assertEqual(
            [e.text() for e in eintraege],
            [w.beispiel for w in schreibweisen.SCHREIBWEISEN],
        )
        # Genau einer ist angehakt - die eingestellte Schreibweise.
        angehakt = [e for e in eintraege if e.isChecked()]
        self.assertEqual(len(angehakt), 1)
        self.assertEqual(angehakt[0].data(), self.fenster.schreibweise.id)

    def test_freitext_wird_gemerkt_und_durchgereicht(self):
        """Die Wahl gilt für den Editor und steht in der Conf."""
        f = self.fenster
        self._projekt()
        f.freitext_erlauben(True)
        self.assertTrue(f.leistenansicht.modell.freitext_erlaubt)
        self.assertTrue(f.aktion_freitext.isChecked())
        self.assertTrue(f.einstellungen.value("freitext", False, type=bool))

        # Auch ein danach geöffnetes Projekt erbt die Wahl.
        self._projekt()
        self.assertTrue(f.leistenansicht.modell.freitext_erlaubt)

        f.freitext_erlauben(False)
        self.assertFalse(f.leistenansicht.modell.freitext_erlaubt)

    def test_leere_auswahlfelder_sind_aus(self):
        f = self.fenster
        self.assertFalse(f.leistenansicht.auswahl.isEnabled())
        self.assertFalse(f.vorschau.auswahl.isEnabled())
        self._projekt()
        self.assertTrue(f.leistenansicht.auswahl.isEnabled())
        f.vorschau.aktualisieren()
        self.assertTrue(f.vorschau.auswahl.isEnabled())


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestProjektdatenDialog(unittest.TestCase):
    """Felder an- und abwählen, ohne sie zu löschen."""

    def setUp(self):
        from verteilerly.gui.dialoge import ProjektdatenDialog

        self.projekt = Projekt(
            verteiler=Verteiler.aus_geometrie(1, 4, 10, name="Probe"),
            briefkopf={"firma": "Musterfirma", "kundennummer": "K-1"},
            eigene_felder={"Standort": "Keller", "Vertrag": "bis 2028"},
        )
        self.projekt.sichtbarkeit_setzen("kundennummer", False)
        self.projekt.sichtbarkeit_setzen("Vertrag", False)
        self.dialog = ProjektdatenDialog(self.projekt)

    def _zeile(self, name):
        for i in range(self.dialog.eigene.rowCount()):
            if self.dialog.eigene.item(i, 0).text() == name:
                return self.dialog.eigene.item(i, 0)
        raise AssertionError(f"Zeile {name} fehlt")

    def test_verteilerdaten_stehen_im_dialog(self):
        """Name und Nummer sind auch nachträglich zu ändern."""
        self.assertEqual(self.dialog.verteilername.text(), "Probe")
        self.dialog.verteilername.setText("Verteiler Keller")
        self.dialog.verteilernummer.setText("2.3")
        self.dialog.uebernehmen()
        self.assertEqual(self.projekt.verteiler.name, "Verteiler Keller")
        self.assertEqual(self.projekt.verteiler.nummer, "2.3")

    def test_verteilerdaten_lassen_sich_nicht_abwaehlen(self):
        """Ein Blatt ohne Verteilernamen wäre keines."""
        self.assertNotIn("verteilername", self.dialog.haken)
        self.dialog._alle_haken(False)
        self.dialog.uebernehmen()
        self.assertEqual(self.projekt.verteiler.name, "Probe")

    def test_adressfelder_sind_mehrzeilig(self):
        """Firma und Kunde tragen eine Anschrift, keine Zeile."""
        from PySide6.QtWidgets import QLineEdit, QPlainTextEdit

        from verteilerly.gui.dialoge import ADRESSFELDER

        for name in ADRESSFELDER:
            with self.subTest(feld=name):
                self.assertIsInstance(self.dialog.felder[name], QPlainTextEdit)
        self.assertIsInstance(self.dialog.felder["kuerzel"], QLineEdit)

    def test_adressfeld_zeigt_drei_zeilen_ohne_rollen(self):
        """Die übliche Anschrift muss ganz zu sehen sein."""
        from PySide6.QtGui import QFontMetrics

        from verteilerly.gui.dialoge import ADRESSZEILEN

        feld = self.dialog.felder["firma"]
        noetig = (
            ADRESSZEILEN * QFontMetrics(feld.font()).lineSpacing()
            + 2 * feld.frameWidth()
            + 2 * int(feld.document().documentMargin())
        )
        self.assertGreaterEqual(feld.height(), noetig)

    def test_anschrift_ueberlebt_das_uebernehmen(self):
        anschrift = "Firma Beliebig\nBeliebige Straße 7\n77777 Ort"
        self.dialog.felder["firma"].setPlainText(anschrift + "\n")
        self.dialog.uebernehmen()
        self.assertEqual(self.projekt.briefkopf["firma"], anschrift)

    def test_haken_zeigen_den_stand(self):
        self.assertTrue(self.dialog.haken["firma"].isChecked())
        self.assertFalse(self.dialog.haken["kundennummer"].isChecked())
        self.assertEqual(
            self._zeile("Standort").checkState(), Qt.CheckState.Checked
        )
        self.assertEqual(
            self._zeile("Vertrag").checkState(), Qt.CheckState.Unchecked
        )

    def test_abgewaehltes_feld_bleibt_beschreibbar(self):
        """Auch im Projektdatendialog sperrt der Haken das Feld nicht."""
        self.dialog.haken["kundennummer"].setChecked(False)
        self.assertTrue(self.dialog.felder["kundennummer"].isEnabled())

    def test_abgewaehltes_feld_zeigt_seinen_inhalt_weiter(self):
        """Nicht löschen heißt: der Wert steht noch da - und bleibt änderbar."""
        self.assertFalse(self.dialog.haken["kundennummer"].isChecked())
        self.assertEqual(self.dialog.felder["kundennummer"].text(), "K-1")
        self.assertTrue(self.dialog.felder["kundennummer"].isEnabled())

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
class TestDeutscheDialoge(unittest.TestCase):
    """Kein englischer Knopf in einem deutschen Programm."""

    def test_rueckfrage_ist_durchweg_deutsch(self):
        from PySide6.QtWidgets import QMessageBox

        from verteilerly.gui.sprache import fragekasten

        kasten = fragekasten(
            None,
            "Änderungen verwerfen?",
            "Der Verteiler wurde geändert.",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        self.assertEqual(
            sorted(b.text() for b in kasten.buttons()),
            ["Abbrechen", "Speichern", "Verwerfen"],
        )
        self.assertEqual(
            kasten.standardButton(kasten.defaultButton()),
            QMessageBox.StandardButton.Save,
        )

    def test_ja_und_nein(self):
        from PySide6.QtWidgets import QMessageBox

        from verteilerly.gui.sprache import fragekasten

        kasten = fragekasten(
            None, "Kabel entfernen?", "Wirklich?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        self.assertEqual(
            sorted(b.text() for b in kasten.buttons()), ["Ja", "Nein"]
        )

    def test_qt_spricht_deutsch(self):
        """Auch die Dialoge, die Qt selbst zeichnet - etwa der Dateidialog."""
        from PySide6.QtWidgets import QMessageBox

        from verteilerly.gui.sprache import deutsch_einrichten

        self.assertTrue(deutsch_einrichten(ANWENDUNG))
        kasten = QMessageBox()
        kasten.setStandardButtons(QMessageBox.StandardButton.Cancel)
        self.assertEqual(
            kasten.button(QMessageBox.StandardButton.Cancel).text(), "Abbrechen"
        )


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
class TestProjektdatenImNeuenVerteiler(unittest.TestCase):
    """Die gemerkten Vorgaben stehen gleich beim Anlegen zur Hand."""

    def setUp(self):
        self.vorlagen = Vorlagen([
            Vorlage(id="a", name="40 DA", buchten=1, leisten_je_bucht=4,
                    da_je_leiste=10, standard=True)
        ])

    def _dialog(self, **kw):
        return NeuerVerteilerDialog(self.vorlagen, None, None, **kw)

    def test_gemerkte_werte_stehen_schon_drin(self):
        dialog = self._dialog(
            briefkopf={"firma": "Musterfirma", "kuerzel": "JD"},
            ausgeblendet={"kundennummer"},
        )
        self.assertEqual(dialog.projektdaten.felder["kuerzel"].text(), "JD")
        self.assertFalse(dialog.projektdaten.haken["kundennummer"].isChecked())
        self.assertTrue(dialog.projektdaten.haken["firma"].isChecked())

    def test_projekt_traegt_den_getippten_briefkopf(self):
        dialog = self._dialog(briefkopf={"firma": "Musterfirma"})
        dialog.name.setText("Verteiler Keller")
        dialog.projektdaten.felder["kunde"].setPlainText("Kunde Beliebig\nStraße 7")
        dialog.projektdaten.haken["dokumenttitel"].setChecked(False)

        projekt = dialog.projekt()
        self.assertEqual(projekt.verteiler.name, "Verteiler Keller")
        self.assertEqual(projekt.briefkopf["firma"], "Musterfirma")
        self.assertEqual(projekt.briefkopf["kunde"], "Kunde Beliebig\nStraße 7")
        self.assertIn("dokumenttitel", projekt.ausgeblendet)

    def test_leere_felder_bleiben_weg(self):
        projekt = self._dialog().projekt()
        self.assertEqual(projekt.briefkopf, {})

    def test_nur_gefuellte_felder_sind_angehakt(self):
        """Was die Vorgaben nicht füllen, gehört auf kein Blatt."""
        dialog = self._dialog(
            briefkopf={"firma": "Musterfirma", "kuerzel": "JD"},
            ausgeblendet={"kunde", "anlagennummer", "kundennummer", "gezeichnet_am",
                          "gezeichnet_von", "erstellt_am", "erstellt_von", "stand_am",
                          "stand_von", "geprueft_am", "geprueft_von", "dokumenttitel"},
        )
        angehakt = {n for n, h in dialog.projektdaten.haken.items() if h.isChecked()}
        self.assertEqual(angehakt, {"firma", "kuerzel"})

    def test_abgewaehlte_felder_bleiben_beschreibbar(self):
        """Sonst ließe sich gerade dort nichts eintragen, wo etwas fehlt."""
        dialog = self._dialog(ausgeblendet=set(BRIEFKOPF_FELDER))
        gesperrt = [
            name for name, feld in dialog.projektdaten.felder.items()
            if not feld.isEnabled()
        ]
        self.assertEqual(gesperrt, [])

        dialog.projektdaten.felder["anlagennummer"].setText("123456")
        self.assertEqual(dialog.projekt().briefkopf["anlagennummer"], "123456")

    def test_wer_tippt_hakt_das_feld_an(self):
        """Sonst tippt man einen Kunden ein und findet ihn auf keinem Blatt."""
        dialog = self._dialog(ausgeblendet=set(BRIEFKOPF_FELDER))
        self.assertFalse(dialog.projektdaten.haken["kunde"].isChecked())

        dialog.projektdaten.felder["kunde"].setPlainText("Kunde Müller")
        self.assertTrue(dialog.projektdaten.haken["kunde"].isChecked())
        self.assertEqual(dialog.projekt().briefkopf["kunde"], "Kunde Müller")

    def test_blattvorlage_steht_schon_beim_anlegen_zur_wahl(self):
        """Gewählt wird beim Anlegen, geändert unter Einstellungen."""
        from verteilerly.blattvorlagen import Blattvorlage, Blattvorlagen

        knapp = Blattvorlage(id="knapp", name="Knapp")
        dialog = self._dialog(
            blattvorlagen=Blattvorlagen([knapp]), blattvorlage="knapp"
        )
        self.assertEqual(dialog.blattvorlage(), "knapp")
        self.assertEqual(dialog.blattvorlagenwahl.count(), 2)

        dialog.blattvorlagenwahl.setCurrentIndex(
            dialog.blattvorlagenwahl.findData("standard")
        )
        self.assertEqual(dialog.blattvorlage(), "standard")

    def test_beide_dialoge_bauen_dieselben_felder(self):
        """Ein Bauteil für beide - sonst laufen sie auseinander."""
        from verteilerly.gui.dialoge import ProjektdatenDialog

        neu = self._dialog()
        pflege = ProjektdatenDialog(Projekt(verteiler=Verteiler.aus_geometrie(1, 4, 10)))
        self.assertEqual(
            list(neu.projektdaten.felder), list(pflege.felder)
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
