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
        SPALTE_BEZEICHNUNG,
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


class TestTextknoepfe(unittest.TestCase):
    """Ausrichtung, fett und kursiv für die gewählte Zelle."""

    def setUp(self):
        from verteilerly.gui.leistenansicht import LeistenAnsicht

        self.ansicht = LeistenAnsicht()
        self.addCleanup(self.ansicht.close)
        self.ansicht.verteiler_setzen(Verteiler.aus_geometrie(1, 2, 10))
        self.ansicht.leiste_zeigen(1)
        self.ader = self.ansicht.modell._leiste.stift(1).ader("a")

    def _waehlen(self, zeile, spalte):
        self.ansicht.tabelle.setCurrentIndex(self.ansicht.modell.index(zeile, spalte))

    def test_ohne_gestaltbare_zelle_sind_sie_aus(self):
        """Was nicht geht, ist ausgegraut."""
        self._waehlen(0, SPALTE_STIFT)
        self.assertFalse(any(k.isEnabled() for k in self.ansicht.textknoepfe))

    def test_bei_einer_textzelle_sind_sie_an(self):
        self._waehlen(0, SPALTE_BEZEICHNUNG)
        self.assertTrue(all(k.isEnabled() for k in self.ansicht.textknoepfe))

    def test_mittig_und_fett_landen_in_der_ader(self):
        from verteilerly.modell import MITTE

        self._waehlen(0, SPALTE_BEZEICHNUNG)
        self.ansicht.ausrichtungsknoepfe[MITTE].click()
        self.ansicht.fett.click()
        stil = self.ader.stil("bezeichnung")
        self.assertEqual(stil.ausrichtung, "mitte")
        self.assertTrue(stil.fett)

    def test_nochmals_derselbe_knopf_nimmt_die_ausrichtung_zurueck(self):
        from verteilerly.modell import RECHTS

        self._waehlen(0, SPALTE_BEZEICHNUNG)
        self.ansicht.ausrichtungsknoepfe[RECHTS].click()
        self.ansicht.ausrichtungsknoepfe[RECHTS].click()
        self.assertEqual(self.ader.stil("bezeichnung").ausrichtung, "")

    def test_kursiv_schaltet_hin_und_her(self):
        self._waehlen(0, SPALTE_BEZEICHNUNG)
        self.ansicht.kursiv.click()
        self.assertTrue(self.ader.stil("bezeichnung").kursiv)
        self.ansicht.kursiv.click()
        self.assertFalse(self.ader.stil("bezeichnung").kursiv)

    def test_die_knoepfe_zeigen_die_gewaehlte_zelle(self):
        from verteilerly.modell import MITTE, Textstil

        self.ader.stil_setzen("bezeichnung", Textstil(MITTE, fett=True))
        self._waehlen(0, SPALTE_BEZEICHNUNG)
        self.assertTrue(self.ansicht.ausrichtungsknoepfe[MITTE].isChecked())
        self.assertTrue(self.ansicht.fett.isChecked())
        self.assertFalse(self.ansicht.kursiv.isChecked())
        # Eine andere Zelle hat ihren eigenen Stil.
        self._waehlen(1, SPALTE_BEZEICHNUNG)
        self.assertFalse(self.ansicht.fett.isChecked())

    def test_beide_rangierfelder_gehoeren_zu_einer_zelle(self):
        """Auf dem Blatt stehen sie nebeneinander in einer."""
        self._waehlen(0, SPALTE_RANGIERUNG)
        self.ansicht.fett.click()
        self._waehlen(0, SPALTE_RANGIERUNG_2)
        self.assertTrue(self.ansicht.fett.isChecked())

    def test_die_tabelle_zeigt_den_stil(self):
        from verteilerly.modell import RECHTS, Textstil

        self.ader.stil_setzen("bezeichnung", Textstil(RECHTS, fett=True, kursiv=True))
        index = self.ansicht.modell.index(0, SPALTE_BEZEICHNUNG)
        schrift = self.ansicht.modell.data(index, Qt.ItemDataRole.FontRole)
        self.assertTrue(schrift.bold())
        self.assertTrue(schrift.italic())
        lage = self.ansicht.modell.data(index, Qt.ItemDataRole.TextAlignmentRole)
        self.assertTrue(lage & int(Qt.AlignmentFlag.AlignRight))


class TestSchmaleLeistenansicht(unittest.TestCase):
    """Die Ansicht darf die Vorschau nicht aus dem Fenster schieben."""

    def _ansicht(self, kabelnamen=()):
        from verteilerly.gui.leistenansicht import LeistenAnsicht

        ansicht = LeistenAnsicht()
        self.addCleanup(ansicht.close)
        verteiler = Verteiler.aus_geometrie(1, 4, 10, name="Probe")
        for nummer, name in enumerate(kabelnamen, start=1):
            verteiler.kabel_anlegen(name, 1, nummer, 1)
        ansicht.verteiler_setzen(verteiler)
        ansicht.show()
        ANWENDUNG.processEvents()
        return ansicht

    def test_lange_kabelnamen_machen_sie_nicht_breiter(self):
        """Genau das schob die Vorschau hinaus, bis nichts mehr zu sehen war."""
        schmal = self._ansicht().minimumSizeHint().width()
        breit = self._ansicht([
            f"Musterleitung Obergeschoss Zimmer {i} vom Hauptverteiler im Keller"
            for i in range(1, 9)
        ]).minimumSizeHint().width()
        self.assertEqual(breit, schmal)

    def test_die_kopfleiste_bleibt_das_maß(self):
        """Schmaler als ihre Knöpfe wird sie nicht - die Tabelle rollt."""
        from verteilerly.gui.leistenansicht import SCHMALSTENS

        ansicht = self._ansicht()
        raender = ansicht.layout().contentsMargins()
        noetig = (
            ansicht.kopfleiste.minimumSize().width()
            + raender.left() + raender.right()
        )
        self.assertGreaterEqual(
            ansicht.minimumSizeHint().width(), min(noetig, SCHMALSTENS)
        )
        self.assertLessEqual(ansicht.minimumSizeHint().width(), max(noetig, SCHMALSTENS))


class TestZelleTeilen(unittest.TestCase):
    """Knopf und Prozentfeld für zwei Beschriftungsfelder."""

    def setUp(self):
        from verteilerly.gui.leistenansicht import LeistenAnsicht

        self.ansicht = LeistenAnsicht()
        self.addCleanup(self.ansicht.close)
        self.verteiler = Verteiler.aus_geometrie(1, 2, 10)
        self.ansicht.verteiler_setzen(self.verteiler)
        self.ansicht.leiste_zeigen(1)
        self.ader = self.verteiler.leiste(1).stift(1).ader("a")

    def _waehlen(self, zeile, spalte):
        self.ansicht.tabelle.setCurrentIndex(self.ansicht.modell.index(zeile, spalte))

    def test_nur_bezeichnung_und_bemerkung_lassen_sich_teilen(self):
        for spalte, teilbar in (
            (SPALTE_BEZEICHNUNG, True),
            (SPALTE_BEMERKUNG, True),
            (SPALTE_FARBE, False),
            (SPALTE_RANGIERUNG, False),
            (SPALTE_STIFT, False),
        ):
            with self.subTest(spalte=spalte):
                self._waehlen(0, spalte)
                self.assertEqual(self.ansicht.teilen.isEnabled(), teilbar)

    def test_der_knopf_teilt_und_hebt_wieder_auf(self):
        self._waehlen(0, SPALTE_BEZEICHNUNG)
        self.ansicht.teilen.click()
        self.assertTrue(self.ader.teilung("bezeichnung").geteilt)
        self.ansicht.teilen.click()
        self.assertFalse(self.ader.teilung("bezeichnung").geteilt)

    def test_das_prozentfeld_gilt_nur_bei_geteilter_zelle(self):
        self._waehlen(0, SPALTE_BEZEICHNUNG)
        self.assertFalse(self.ansicht.anteil.isEnabled())
        self.ansicht.teilen.click()
        self.assertTrue(self.ansicht.anteil.isEnabled())

    def test_der_anteil_landet_in_der_ader(self):
        self._waehlen(0, SPALTE_BEZEICHNUNG)
        self.ansicht.teilen.click()
        self.ansicht.anteil.setValue(25)
        self.assertEqual(self.ader.teilung("bezeichnung").anteil, 25)

    def test_die_knoepfe_zeigen_die_gewaehlte_zelle(self):
        from verteilerly.modell import Zellenteilung

        self.ader.teilung_setzen("bezeichnung", Zellenteilung(35, "Nst. 42"))
        self._waehlen(0, SPALTE_BEZEICHNUNG)
        self.assertTrue(self.ansicht.teilen.isChecked())
        self.assertEqual(self.ansicht.anteil.value(), 35)
        self._waehlen(1, SPALTE_BEZEICHNUNG)
        self.assertFalse(self.ansicht.teilen.isChecked())

    def test_aufheben_behaelt_den_zweiten_text(self):
        from verteilerly.modell import Zellenteilung

        self.ader.teilung_setzen("bezeichnung", Zellenteilung(35, "Nst. 42"))
        self._waehlen(0, SPALTE_BEZEICHNUNG)
        self.ansicht.teilen.click()
        self.assertEqual(self.ader.teilung("bezeichnung").text, "Nst. 42")

    def test_der_editor_hat_zwei_felder(self):
        from verteilerly.modell import Zellenteilung

        self.ader.bezeichnung = "Amt 1"
        self.ader.teilung_setzen("bezeichnung", Zellenteilung(30, "Nst. 42"))
        index = self.ansicht.modell.index(0, SPALTE_BEZEICHNUNG)
        self.ansicht.tabelle.setCurrentIndex(index)
        self.ansicht.tabelle.edit(index)
        kasten = getattr(self.ansicht.tabelle.focusWidget(), "behaelter", None)
        self.assertIsNotNone(kasten)
        self.assertEqual([f.text() for f in kasten.felder], ["Amt 1", "Nst. 42"])

    def test_beide_felder_werden_gespeichert(self):
        from verteilerly.modell import Zellenteilung

        self.ader.bezeichnung = "Amt 1"
        self.ader.teilung_setzen("bezeichnung", Zellenteilung(30, "Nst. 42"))
        index = self.ansicht.modell.index(0, SPALTE_BEZEICHNUNG)
        self.ansicht.tabelle.setCurrentIndex(index)
        self.ansicht.tabelle.edit(index)
        kasten = getattr(self.ansicht.tabelle.focusWidget(), "behaelter", None)
        kasten.felder[0].setText("Amt 2")
        kasten.felder[1].setText("Nst. 7")
        self.ansicht.delegat.setModelData(kasten, self.ansicht.modell, index)
        self.assertEqual(self.ader.bezeichnung, "Amt 2")
        self.assertEqual(self.ader.teilung("bezeichnung").text, "Nst. 7")

    def test_tab_geht_ins_zweite_feld_statt_in_die_naechste_zelle(self):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent
        from verteilerly.modell import Zellenteilung

        self.ader.teilung_setzen("bezeichnung", Zellenteilung(30, "Nst. 42"))
        index = self.ansicht.modell.index(0, SPALTE_BEZEICHNUNG)
        self.ansicht.tabelle.setCurrentIndex(index)
        self.ansicht.tabelle.edit(index)
        kasten = getattr(self.ansicht.tabelle.focusWidget(), "behaelter", None)
        taste = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier
        )
        self.assertTrue(self.ansicht.delegat.eventFilter(kasten.felder[0], taste))


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestEnterInGeteilterZelle(unittest.TestCase):
    """Enter geht geradewegs nach unten, nicht schräg."""

    def setUp(self):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent
        from verteilerly.gui.leistenansicht import LeistenAnsicht
        from verteilerly.modell import Zellenteilung

        self.QEvent, self.QKeyEvent = QEvent, QKeyEvent
        self.Zellenteilung = Zellenteilung
        self.ansicht = LeistenAnsicht()
        self.addCleanup(self.ansicht.close)
        self.verteiler = Verteiler.aus_geometrie(1, 2, 10)
        self.ansicht.verteiler_setzen(self.verteiler)
        self.ansicht.leiste_zeigen(1)
        self.ansicht.show()
        self.addCleanup(self.ansicht.hide)
        self.modell = self.ansicht.modell
        self.tabelle = self.ansicht.tabelle

    def _teilen(self, *zeilen, anteil=40):
        for zeile in zeilen:
            self.modell.teilung_setzen(
                self.modell.index(zeile, SPALTE_BEZEICHNUNG),
                self.Zellenteilung(anteil=anteil),
            )

    def _felder(self, zeile, spalte=SPALTE_BEZEICHNUNG):
        index = self.modell.index(zeile, spalte)
        self.tabelle.setCurrentIndex(index)
        self.tabelle.edit(index)
        ANWENDUNG.processEvents()
        return getattr(self.tabelle.focusWidget(), "behaelter", None)

    def _enter(self, feld, text=""):
        feld.setFocus()
        if text:
            feld.setText(text)
        ANWENDUNG.sendEvent(
            feld,
            self.QKeyEvent(
                self.QEvent.Type.KeyPress,
                Qt.Key.Key_Return,
                Qt.KeyboardModifier.NoModifier,
            ),
        )
        ANWENDUNG.processEvents()

    def _offenes_feld(self):
        """Das Eingabefeld, in dem die Marke gerade steht - oder None."""
        gerade = self.tabelle.focusWidget()
        return gerade if getattr(gerade, "behaelter", None) is not None else None

    def test_aus_dem_rechten_feld_geht_es_gerade_nach_unten(self):
        """Früher landete die Marke eine Spalte weiter rechts."""
        self._teilen(0, 1)
        kasten = self._felder(0)
        self._enter(kasten.felder[1], "rechts")
        self.assertEqual(self.tabelle.currentIndex().row(), 1)
        self.assertEqual(self.tabelle.currentIndex().column(), SPALTE_BEZEICHNUNG)

    def test_und_der_text_steht_im_zweiten_feld(self):
        self._teilen(0, 1)
        kasten = self._felder(0)
        self._enter(kasten.felder[1], "Nst. 42")
        index = self.modell.index(0, SPALTE_BEZEICHNUNG)
        self.assertEqual(self.modell.teilung(index).text, "Nst. 42")

    def test_die_naechste_geteilte_zeile_oeffnet_im_rechten_feld(self):
        self._teilen(0, 1)
        kasten = self._felder(0)
        self._enter(kasten.felder[1], "rechts")
        feld = self._offenes_feld()
        self.assertIsNotNone(feld, "kein Eingabefeld offen")
        self.assertIs(feld, feld.behaelter.felder[1])

    def test_aus_dem_linken_feld_bleibt_es_beim_blossen_weiterruecken(self):
        self._teilen(0, 1)
        kasten = self._felder(0)
        self._enter(kasten.felder[0], "links")
        self.assertEqual(self.tabelle.currentIndex().row(), 1)
        self.assertEqual(self.tabelle.currentIndex().column(), SPALTE_BEZEICHNUNG)
        self.assertIsNone(self._offenes_feld())

    def test_ist_die_zeile_darunter_ungeteilt_rueckt_nur_die_marke(self):
        self._teilen(0)
        kasten = self._felder(0)
        self._enter(kasten.felder[1], "rechts")
        self.assertEqual(self.tabelle.currentIndex().row(), 1)
        self.assertEqual(self.tabelle.currentIndex().column(), SPALTE_BEZEICHNUNG)
        self.assertIsNone(self._offenes_feld())

    def test_in_der_letzten_zeile_bleibt_die_marke_stehen(self):
        letzte = self.modell.rowCount() - 1
        self._teilen(letzte)
        kasten = self._felder(letzte)
        self._enter(kasten.felder[1], "Ende")
        self.assertEqual(self.tabelle.currentIndex().row(), letzte)
        self.assertEqual(self.tabelle.currentIndex().column(), SPALTE_BEZEICHNUNG)

    def test_ein_verlassenes_feld_behaelt_seinen_text(self):
        """Wer woanders hinklickt, statt Enter zu drücken, verliert nichts."""
        self._teilen(0)
        kasten = self._felder(0)
        kasten.felder[1].setFocus()
        kasten.felder[1].setText("weggeklickt")
        self.tabelle.setFocus()
        ANWENDUNG.processEvents()
        index = self.modell.index(0, SPALTE_BEZEICHNUNG)
        self.assertEqual(self.modell.teilung(index).text, "weggeklickt")

    def test_esc_verwirft_auch_in_der_geteilten_zelle(self):
        self._teilen(0)
        kasten = self._felder(0)
        kasten.felder[1].setFocus()
        kasten.felder[1].setText("verworfen")
        ANWENDUNG.sendEvent(
            kasten.felder[1],
            self.QKeyEvent(
                self.QEvent.Type.KeyPress,
                Qt.Key.Key_Escape,
                Qt.KeyboardModifier.NoModifier,
            ),
        )
        ANWENDUNG.processEvents()
        index = self.modell.index(0, SPALTE_BEZEICHNUNG)
        self.assertEqual(self.modell.teilung(index).text, "")


class TestMehrereZellenAufEinmal(unittest.TestCase):
    """Markierte Zellen werden zusammen gestaltet."""

    def setUp(self):
        from PySide6.QtCore import QItemSelection, QItemSelectionModel
        from verteilerly.gui.leistenansicht import LeistenAnsicht

        self.QItemSelection = QItemSelection
        self.QItemSelectionModel = QItemSelectionModel
        self.ansicht = LeistenAnsicht()
        self.addCleanup(self.ansicht.close)
        self.verteiler = Verteiler.aus_geometrie(1, 2, 10)
        self.ansicht.verteiler_setzen(self.verteiler)
        self.ansicht.leiste_zeigen(1)

    def _ader(self, zeile):
        stift = self.verteiler.leiste(1).stift(zeile // 2 + 1)
        return stift.ader("a" if zeile % 2 == 0 else "b")

    def _markieren(self, von, bis, spalte):
        modell = self.ansicht.modell
        self.ansicht.tabelle.setCurrentIndex(modell.index(von, spalte))
        self.ansicht.tabelle.selectionModel().select(
            self.QItemSelection(modell.index(von, spalte), modell.index(bis, spalte)),
            self.QItemSelectionModel.SelectionFlag.Select,
        )

    def test_fett_gilt_fuer_alle_markierten(self):
        self._markieren(0, 3, SPALTE_BEZEICHNUNG)
        self.ansicht.fett.click()
        for zeile in range(4):
            with self.subTest(zeile=zeile):
                self.assertTrue(self._ader(zeile).stil("bezeichnung").fett)
        self.assertFalse(self._ader(4).stil("bezeichnung").fett)

    def test_ausrichtung_gilt_fuer_alle_markierten(self):
        from verteilerly.modell import MITTE

        self._markieren(0, 3, SPALTE_BEZEICHNUNG)
        self.ansicht.ausrichtungsknoepfe[MITTE].click()
        self.assertEqual(
            [self._ader(z).stil("bezeichnung").ausrichtung for z in range(4)],
            ["mitte"] * 4,
        )

    def test_teilen_gilt_fuer_alle_markierten(self):
        self._markieren(0, 3, SPALTE_BEMERKUNG)
        self.ansicht.teilen.click()
        self.ansicht.anteil.setValue(25)
        for zeile in range(4):
            with self.subTest(zeile=zeile):
                teilung = self._ader(zeile).teilung("bemerkung")
                self.assertTrue(teilung.geteilt)
                self.assertEqual(teilung.anteil, 25)
        self.assertFalse(self._ader(4).teilung("bemerkung").geteilt)

    def test_alle_bekommen_dasselbe_nicht_ihr_gegenteil(self):
        """Eine gemischte Auswahl wird gleichgezogen, nicht umgedreht."""
        from verteilerly.modell import Textstil

        self._ader(1).stil_setzen("bezeichnung", Textstil(fett=True))
        self._markieren(0, 3, SPALTE_BEZEICHNUNG)
        self.ansicht.fett.click()      # die aktuelle Zelle (0) ist nicht fett
        self.assertEqual(
            [self._ader(z).stil("bezeichnung").fett for z in range(4)], [True] * 4
        )

    def test_marke_in_einer_spalte_ohne_stil_sperrt_die_knoepfe_nicht(self):
        """Beim Ziehen steht die Marke auf der ersten Zelle - oft der Stift."""
        modell = self.ansicht.modell
        self.ansicht.tabelle.setCurrentIndex(modell.index(0, SPALTE_STIFT))
        self.assertFalse(self.ansicht.fett.isEnabled())
        self.ansicht.tabelle.selectionModel().select(
            self.QItemSelection(modell.index(0, SPALTE_STIFT), modell.index(0, SPALTE_KABEL)),
            self.QItemSelectionModel.SelectionFlag.Select,
        )
        self.assertTrue(self.ansicht.fett.isEnabled())
        self.ansicht.fett.click()
        self.assertTrue(self._ader(0).stil("bezeichnung").fett)

    def test_nicht_gestaltbare_zellen_in_der_auswahl_stoeren_nicht(self):
        modell = self.ansicht.modell
        self.ansicht.tabelle.setCurrentIndex(modell.index(0, SPALTE_BEZEICHNUNG))
        self.ansicht.tabelle.selectionModel().select(
            self.QItemSelection(modell.index(0, SPALTE_STIFT), modell.index(0, SPALTE_KABEL)),
            self.QItemSelectionModel.SelectionFlag.Select,
        )
        self.ansicht.fett.click()
        self.assertTrue(self._ader(0).stil("bezeichnung").fett)
        self.assertTrue(self._ader(0).stil("bemerkung").fett)
        self.assertTrue(self._ader(0).stil("farbe").fett)
        # Die Kabelspalte hat keinen Stil und wirft auch keinen Fehler.
        self.assertIsNone(modell.stil(modell.index(0, SPALTE_KABEL)))


class TestKabelDialog(unittest.TestCase):
    """Kabel auflegen und bearbeiten."""

    def setUp(self):
        from verteilerly import pfade
        from verteilerly.farbcodes import Kabeltypen
        from verteilerly.gui.dialoge import KabelDialog

        self.KabelDialog = KabelDialog
        self.typen = Kabeltypen.laden(pfade.kabeltypenordner())
        self.verteiler = Verteiler.aus_geometrie(1, 2, 10)

    def _dialog(self, kabel=None, leiste=1, start=1):
        dialog = self.KabelDialog(
            self.verteiler, self.typen, leiste, start, kabel=kabel
        )
        self.addCleanup(dialog.close)
        return dialog

    def _beschriftungen(self, dialog):
        from PySide6.QtWidgets import QFormLayout

        form = dialog.findChild(QFormLayout)
        return [
            form.itemAt(i, QFormLayout.ItemRole.LabelRole).widget().text()
            for i in range(form.rowCount())
            if form.itemAt(i, QFormLayout.ItemRole.LabelRole)
        ]

    def test_der_dialog_faengt_mit_dem_haeufigsten_kabel_an(self):
        """Zwei Doppeladern, J-Y(St)Y - das liegt im Bestand am häufigsten."""
        from verteilerly.gui.dialoge import VORGABE_KABEL_DA, VORGABE_KABELTYP

        dialog = self._dialog()
        self.assertEqual(dialog.kabel_da.value(), VORGABE_KABEL_DA)
        self.assertEqual(dialog.auflegen_da.value(), VORGABE_KABEL_DA)
        self.assertEqual(dialog.kabeltyp.currentData(), VORGABE_KABELTYP)
        angaben = dialog.angaben()
        self.assertEqual(angaben["da_gesamt"], VORGABE_KABEL_DA)
        self.assertEqual(angaben["kabeltyp"], VORGABE_KABELTYP)

    def test_ohne_den_vorgabetyp_bleibt_es_bei_von_hand(self):
        """Wer ihn weggeworfen hat, bekommt wieder „ohne“ zu sehen."""
        from verteilerly.farbcodes import Kabeltypen

        dialog = self.KabelDialog(self.verteiler, Kabeltypen({}, {}), 1, 1)
        self.addCleanup(dialog.close)
        self.assertIsNone(dialog.kabeltyp.currentData())

    def test_der_startpunkt_heisst_stift(self):
        beschriftungen = self._beschriftungen(self._dialog())
        self.assertIn("Ab Stift:", beschriftungen)
        self.assertNotIn("Ab Doppelader:", beschriftungen)

    def test_die_kabelgroesse_zieht_das_auflegen_mit(self):
        """Der Regelfall ist, dass ein Kabel ganz aufgelegt wird."""
        dialog = self._dialog()
        dialog.kabel_da.setValue(6)
        self.assertEqual(dialog.auflegen_da.value(), 6)
        dialog.kabel_da.setValue(12)
        self.assertEqual(dialog.auflegen_da.value(), 12)
        self.assertEqual(dialog.kuerzungshinweis.text(), "")

    def test_kuerzen_bleibt_moeglich(self):
        dialog = self._dialog()
        dialog.kabel_da.setValue(6)
        dialog.auflegen_da.setValue(4)
        self.assertEqual(dialog.angaben()["anzahl_da"], 4)
        self.assertEqual(dialog.angaben()["da_gesamt"], 6)
        self.assertIn("2 DA", dialog.kuerzungshinweis.text())

    def test_beim_bearbeiten_bleibt_nur_die_lage_stehen(self):
        """Leiste und Anfang stehen fest, die Länge nicht."""
        kabel = self.verteiler.kabel_anlegen(
            "Probe", 1, 1, 4, kabeltyp="jystyv", da_gesamt=6
        )
        dialog = self._dialog(kabel=kabel)
        self.assertFalse(dialog.leiste.isEnabled())
        self.assertFalse(dialog.start.isEnabled())
        self.assertTrue(dialog.auflegen_da.isEnabled())
        self.assertEqual(dialog.kabel_da.value(), 6)
        self.assertEqual(dialog.auflegen_da.value(), 4)
        self.assertIn("2 DA", dialog.kuerzungshinweis.text())

    def test_die_groesse_zieht_das_aufgelegte_auch_beim_bearbeiten_mit(self):
        kabel = self.verteiler.kabel_anlegen(
            "Probe", 1, 1, 4, kabeltyp="jystyv", da_gesamt=6
        )
        dialog = self._dialog(kabel=kabel)
        dialog.kabel_da.setValue(10)
        self.assertEqual(dialog.auflegen_da.value(), 10)
        self.assertEqual(dialog.kuerzungshinweis.text(), "")
        # Und kürzen bleibt möglich.
        dialog.auflegen_da.setValue(7)
        self.assertIn("3 DA", dialog.kuerzungshinweis.text())


class TestEntfLeertZellen(unittest.TestCase):
    """Eine Zelle leeren, ohne sie erst zu öffnen."""

    def setUp(self):
        from PySide6.QtCore import QEvent, QItemSelection, QItemSelectionModel
        from PySide6.QtGui import QKeyEvent
        from verteilerly.gui.leistenansicht import LeistenAnsicht

        self.QEvent, self.QKeyEvent = QEvent, QKeyEvent
        self.QItemSelection = QItemSelection
        self.QItemSelectionModel = QItemSelectionModel
        self.ansicht = LeistenAnsicht()
        self.addCleanup(self.ansicht.close)
        self.verteiler = Verteiler.aus_geometrie(1, 2, 10)
        self.verteiler.kabel_anlegen("Leitung", 1, 1, 4)
        self.ansicht.verteiler_setzen(self.verteiler)
        self.ansicht.leiste_zeigen(1)
        self.ader = self.verteiler.leiste(1).stift(1).ader("a")

    def _entf(self):
        ANWENDUNG.sendEvent(
            self.ansicht.tabelle,
            self.QKeyEvent(
                self.QEvent.Type.KeyPress,
                Qt.Key.Key_Delete,
                Qt.KeyboardModifier.NoModifier,
            ),
        )

    def _waehlen(self, zeile, spalte):
        self.ansicht.tabelle.setCurrentIndex(self.ansicht.modell.index(zeile, spalte))

    def test_entf_leert_die_gewaehlte_zelle(self):
        self.ader.bezeichnung = "Amt 1"
        self._waehlen(0, SPALTE_BEZEICHNUNG)
        self._entf()
        self.assertEqual(self.ader.bezeichnung, "")

    def test_entf_leert_beide_felder_einer_geteilten_zelle(self):
        from verteilerly.modell import Zellenteilung

        self.ader.bezeichnung = "Amt 1"
        self.ader.teilung_setzen("bezeichnung", Zellenteilung(30, "Nst. 42"))
        self._waehlen(0, SPALTE_BEZEICHNUNG)
        self._entf()
        self.assertEqual(self.ader.bezeichnung, "")
        self.assertEqual(self.ader.teilung("bezeichnung").text, "")
        # Die Teilung selbst bleibt - gelöscht wird der Text, nicht die Form.
        self.assertTrue(self.ader.teilung("bezeichnung").geteilt)

    def test_entf_nimmt_eine_rangierung_weg(self):
        self.verteiler.rangierung_anlegen(
            Aderadresse(1, 1, "a"), Aderadresse(1, 5, "b")
        )
        self._waehlen(0, SPALTE_RANGIERUNG)
        self._entf()
        self.assertEqual(self.verteiler.rangierungen, [])

    def test_entf_leert_die_kabelbeschriftung_nimmt_aber_kein_kabel_ab(self):
        self._waehlen(0, SPALTE_KABEL)
        self._entf()
        self.assertEqual(self.verteiler.kabel[0].beschriftung, "")
        self.assertEqual(len(self.verteiler.kabel), 1)

    def test_stift_und_ader_bleiben(self):
        self._waehlen(0, SPALTE_STIFT)
        self._entf()
        self.assertEqual(
            self.ansicht.modell.data(self.ansicht.modell.index(0, SPALTE_STIFT)), "1"
        )

    def test_entf_leert_alle_markierten_zellen(self):
        self.ader.farbe = "rt"
        self.ader.bezeichnung = "Amt 1"
        self.ader.bemerkung = "geprüft"
        modell = self.ansicht.modell
        self._waehlen(0, SPALTE_FARBE)
        self.ansicht.tabelle.selectionModel().select(
            self.QItemSelection(modell.index(0, SPALTE_FARBE),
                                modell.index(0, SPALTE_BEMERKUNG)),
            self.QItemSelectionModel.SelectionFlag.Select,
        )
        self._entf()
        self.assertEqual(
            (self.ader.farbe, self.ader.bezeichnung, self.ader.bemerkung), ("", "", "")
        )

    def test_beim_bearbeiten_greift_entf_nicht(self):
        """Dort gehört die Taste dem Eingabefeld - sie löscht Zeichen."""
        self.ader.bezeichnung = "Bleibt"
        index = self.ansicht.modell.index(0, SPALTE_BEZEICHNUNG)
        self.ansicht.tabelle.setCurrentIndex(index)
        self.ansicht.tabelle.edit(index)
        self._entf()
        self.assertEqual(self.ader.bezeichnung, "Bleibt")


class TestEnterSpringtWeiter(unittest.TestCase):
    """Enter schließt die Eingabe und geht eine Zeile tiefer."""

    def setUp(self):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent
        from verteilerly.gui.leistenansicht import LeistenAnsicht

        self.QEvent, self.QKeyEvent = QEvent, QKeyEvent
        self.ansicht = LeistenAnsicht()
        self.addCleanup(self.ansicht.close)
        self.ansicht.verteiler_setzen(Verteiler.aus_geometrie(1, 2, 10))
        self.ansicht.leiste_zeigen(1)
        self.tabelle = self.ansicht.tabelle

    def _tippen(self, zeile, spalte, text):
        index = self.ansicht.modell.index(zeile, spalte)
        self.tabelle.setCurrentIndex(index)
        self.tabelle.edit(index)
        feld = self.tabelle.focusWidget()
        feld.setText(text)
        ANWENDUNG.sendEvent(
            feld,
            self.QKeyEvent(
                self.QEvent.Type.KeyPress,
                Qt.Key.Key_Return,
                Qt.KeyboardModifier.NoModifier,
            ),
        )

    def test_der_wert_steht_und_die_marke_ist_eine_zeile_tiefer(self):
        self._tippen(0, SPALTE_BEZEICHNUNG, "Probe")
        self.assertEqual(
            self.ansicht.modell.data(self.ansicht.modell.index(0, SPALTE_BEZEICHNUNG)),
            "Probe",
        )
        self.assertEqual(self.tabelle.currentIndex().row(), 1)
        self.assertEqual(self.tabelle.currentIndex().column(), SPALTE_BEZEICHNUNG)

    def test_in_der_letzten_zeile_bleibt_die_marke_stehen(self):
        letzte = self.ansicht.modell.rowCount() - 1
        self._tippen(letzte, SPALTE_BEZEICHNUNG, "Ende")
        self.assertEqual(self.tabelle.currentIndex().row(), letzte)

    def test_nach_einer_abgelehnten_eingabe_bleibt_sie_stehen(self):
        """Eine unlesbare Rangierung ist dort zu richten, wo sie steht."""
        self._tippen(2, SPALTE_RANGIERUNG, "kein Ziel")
        self.assertEqual(self.tabelle.currentIndex().row(), 2)

    def test_eine_angenommene_rangierung_springt_weiter(self):
        self._tippen(2, SPALTE_RANGIERUNG, "2 3a")
        self.assertEqual(self.tabelle.currentIndex().row(), 3)


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

    def test_die_pfeile_der_dateidialoge_sind_zu_sehen(self):
        """Qts eigene Bilder sind dunkel - wir malen sie selbst."""
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QStyle
        from verteilerly.gui import thema

        vorher_blatt = ANWENDUNG.styleSheet()
        vorher_palette = ANWENDUNG.palette()
        self.addCleanup(ANWENDUNG.setPalette, vorher_palette)
        self.addCleanup(ANWENDUNG.setStyleSheet, vorher_blatt)

        for satz in ("dunkel", "hell"):
            with self.subTest(satz=satz):
                farben = thema.SAETZE[satz]
                thema.anwenden(ANWENDUNG, farben)
                for bild in (
                    QStyle.StandardPixmap.SP_FileDialogBack,
                    QStyle.StandardPixmap.SP_FileDialogToParent,
                    QStyle.StandardPixmap.SP_ArrowForward,
                ):
                    symbol = ANWENDUNG.style().standardIcon(bild)
                    self.assertFalse(symbol.isNull())
                    abbild = symbol.pixmap(16, 16).toImage()
                    farbig = [
                        QColor(abbild.pixel(x, y))
                        for x in range(abbild.width())
                        for y in range(abbild.height())
                        if QColor(abbild.pixelColor(x, y)).alpha() > 200
                    ]
                    self.assertTrue(farbig, "der Pfeil ist leer")
                    soll = QColor(farben.schrift)
                    # Gemalt wird in der Schriftfarbe - hell im dunklen Satz.
                    self.assertLess(
                        abs(farbig[0].lightness() - soll.lightness()), 40,
                        f"{farbig[0].name()} statt {soll.name()}",
                    )

    def test_andere_standardbilder_bleiben_wie_sie_sind(self):
        """Nur die Pfeile werden ersetzt, nicht Qts ganzer Bildersatz."""
        from PySide6.QtWidgets import QStyle
        from verteilerly.gui import thema

        vorher_palette = ANWENDUNG.palette()
        self.addCleanup(ANWENDUNG.setPalette, vorher_palette)
        thema.anwenden(ANWENDUNG, thema.DUNKEL)
        symbol = ANWENDUNG.style().standardIcon(
            QStyle.StandardPixmap.SP_DirIcon
        )
        self.assertFalse(symbol.isNull())

    def test_auswahlknoepfe_auch(self):
        """Die Kugel muss zu sehen sein, sonst rät man, was gewählt ist."""
        from verteilerly.gui.thema import DUNKEL, HELL, stilblatt

        for farben in (HELL, DUNKEL):
            with self.subTest(satz=farben.name):
                blatt = stilblatt(farben)
                self.assertIn("QRadioButton::indicator", blatt)
                gewaehlt = blatt.split("QRadioButton::indicator:checked")[1]
                gewaehlt = gewaehlt.split("}")[0]
                # Ring und Kugel tragen die Akzentfarbe, nicht die Linie.
                self.assertIn(farben.akzent, gewaehlt)
                self.assertIn("qradialgradient", gewaehlt)

    def test_die_kugel_hebt_sich_vom_feld_ab(self):
        """Gezeichnet, nicht behauptet: die Bildpunkte werden verglichen."""
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QRadioButton
        from verteilerly.gui import thema

        # Das Erscheinungsbild gilt der ganzen Anwendung - hinterher
        # gehört es zurückgelegt, sonst färbt es die übrigen Prüfungen.
        vorher_blatt = ANWENDUNG.styleSheet()
        vorher_palette = ANWENDUNG.palette()
        self.addCleanup(ANWENDUNG.setPalette, vorher_palette)
        self.addCleanup(ANWENDUNG.setStyleSheet, vorher_blatt)

        for satz in ("hell", "dunkel"):
            with self.subTest(satz=satz):
                farben = thema.SAETZE[satz]
                thema.anwenden(ANWENDUNG, farben)
                knopf = QRadioButton("Aus Vorlage")
                knopf.setChecked(True)
                knopf.resize(160, 24)
                knopf.show()
                ANWENDUNG.processEvents()
                bild = knopf.grab().toImage()
                mitte = QColor(bild.pixel(8, bild.height() // 2))
                grund = QColor(farben.flaeche)
                abstand = (
                    abs(mitte.red() - grund.red())
                    + abs(mitte.green() - grund.green())
                    + abs(mitte.blue() - grund.blue())
                )
                knopf.close()
                self.assertGreater(abstand, 60, f"{mitte.name()} auf {grund.name()}")


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
class TestKabelZiehen(unittest.TestCase):
    """Ein Kabel in der Übersicht woandershin ziehen."""

    def setUp(self):
        from verteilerly.gui.uebersicht import Uebersicht

        self.verteiler = Verteiler.aus_geometrie(1, 3, 10, name="Probe")
        self.kabel = self.verteiler.kabel_anlegen("Leitung", 1, 2, 4)
        self.uebersicht = Uebersicht()
        self.addCleanup(self.uebersicht.close)
        self.uebersicht.verteiler_setzen(self.verteiler)
        self.uebersicht.resize(self.uebersicht.sizeHint())

    class _Fracht:
        """Eine Fallenlassen-Meldung, wie Qt sie schickt - nur das Nötige."""

        def __init__(self, punkt, versatz, aktion=None):
            from PySide6.QtCore import QMimeData, QPointF, Qt
            from verteilerly.gui.uebersicht import KABELFRACHT

            self._punkt = QPointF(*punkt)
            self._fracht = QMimeData()
            self._fracht.setData(KABELFRACHT, str(versatz).encode("ascii"))
            self._aktion = aktion or Qt.DropAction.MoveAction
            self.angenommen = False

        def position(self):
            return self._punkt

        def mimeData(self):
            return self._fracht

        def proposedAction(self):
            return self._aktion

        def acceptProposedAction(self):
            self.angenommen = True

        def ignore(self):
            self.angenommen = False

    def _punkt(self, leiste, da):
        """Die Mitte dieser Zelle."""
        kasten = self.uebersicht._zellrechteck(leiste, da)
        return kasten.center().x(), kasten.center().y()

    def test_angefasst_wird_die_doppelader_unter_dem_zeiger(self):
        self.assertEqual(
            self.uebersicht._versatz_im_kabel(self.kabel, (1, 4)), 2
        )
        self.assertEqual(
            self.uebersicht._versatz_im_kabel(self.kabel, (1, 2)), 0
        )

    def test_das_kabel_landet_so_wie_es_angefasst_wurde(self):
        """Wer die dritte DA greift, legt sie unter den Zeiger."""
        self.uebersicht._gezogen = self.kabel
        ziel = self.uebersicht._zielstelle(self._Fracht(self._punkt(2, 7), 2))
        self.assertEqual(ziel, (2, 5, True))

    def test_wo_es_nicht_passt_wird_nichts_angenommen(self):
        self.verteiler.kabel_anlegen("Nachbar", 2, 5, 2)
        self.uebersicht._gezogen = self.kabel
        meldung = self._Fracht(self._punkt(2, 5), 0)
        self.uebersicht.dragMoveEvent(meldung)
        self.assertFalse(meldung.angenommen)
        self.assertEqual(self.uebersicht._ziel, (2, 5, False))

        meldung = self._Fracht(self._punkt(3, 1), 0)
        self.uebersicht.dragMoveEvent(meldung)
        self.assertTrue(meldung.angenommen)

    def test_das_fallenlassen_meldet_verschieben_oder_kopieren(self):
        from PySide6.QtCore import Qt

        self.uebersicht._gezogen = self.kabel
        gemeldet = []
        self.uebersicht.kabel_umgelegt.connect(
            lambda *args: gemeldet.append(args)
        )
        self.uebersicht.dropEvent(self._Fracht(self._punkt(3, 3), 1))
        self.uebersicht._gezogen = self.kabel
        self.uebersicht.dropEvent(
            self._Fracht(self._punkt(3, 3), 1, Qt.DropAction.CopyAction)
        )
        self.assertEqual(
            [(x[1], x[2], x[3]) for x in gemeldet],
            [(3, 2, False), (3, 2, True)],
        )
        self.assertIs(gemeldet[0][0], self.kabel)

    def test_ohne_kabel_am_zeiger_geschieht_nichts(self):
        """Fremde Fracht - ein Bild, eine Datei - löst hier nichts aus."""
        gemeldet = []
        self.uebersicht.kabel_umgelegt.connect(lambda *a: gemeldet.append(a))
        self.uebersicht.dropEvent(self._Fracht(self._punkt(3, 3), 0))
        self.assertEqual(gemeldet, [])


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
class TestKabelnameInDerBelegung(unittest.TestCase):
    """Mittig im Block, umgebrochen statt abgeschnitten.

    Gemessen wird am gezeichneten Bild: nur so ist zu sehen, dass die
    Vorschau dasselbe tut wie das PDF - nicht nur, dass das Modell es so
    beschreibt.
    """

    def _tinte(self, beschriftung, da):
        """Zeichnet die Belegung und misst die Schrift im Kabelblock.

        Zurueck kommen die Zahl der Zeilen (Baender aus dunklen Zeilen),
        die Mitte der Schrift und die Mitte des Blocks - alles in
        Bildpunkten des Fensters.
        """
        from verteilerly.gui.vorschau import Blattflaeche
        from verteilerly.layout import Text as Blatttext
        from verteilerly.layout import verteilerbelegungen

        v = Verteiler.aus_geometrie(1, 4, 10, name="Muster")
        v.kabel_anlegen(beschriftung, 1, 1, da)
        blatt = verteilerbelegungen(Projekt(verteiler=v))[0]
        flaeche = Blattflaeche()
        self.addCleanup(flaeche.close)
        flaeche.resize(800, 1100)
        flaeche.blatt_setzen(blatt)
        bild = flaeche.grab().toImage()

        skala = flaeche._skala(blatt)
        links = (flaeche.width() - blatt.breite * skala) / 2
        oben = (flaeche.height() - blatt.hoehe * skala) / 2
        feld = next(
            e for e in blatt.elemente
            if isinstance(e, Blatttext) and e.text == beschriftung
        )
        # Ein Bildpunkt Abstand: der Rahmen des Blocks ist auch dunkel.
        x0 = int(links + feld.x * skala) + 1
        x1 = int(links + (feld.x + feld.breite) * skala) - 1
        y0 = int(oben + feld.y * skala) + 2
        y1 = int(oben + (feld.y + feld.hoehe) * skala) - 2

        baender, im_band, tinte = 0, False, []
        for y in range(y0, y1):
            dunkel = [
                x for x in range(x0, x1)
                if bild.pixelColor(x, y).lightness() < 120
            ]
            if dunkel and not im_band:
                baender += 1
            im_band = bool(dunkel)
            tinte.extend(dunkel)
        self.assertTrue(tinte, "keine Schrift im Kabelblock")
        return baender, (min(tinte) + max(tinte)) / 2, (x0 + x1) / 2

    def test_ein_kurzer_name_steht_auf_einer_zeile_und_mittig(self):
        zeilen, mitte, blockmitte = self._tinte("Haus Nord", 4)
        self.assertEqual(zeilen, 1)
        self.assertAlmostEqual(mitte, blockmitte, delta=2)

    def test_ein_langer_name_bricht_um(self):
        """Früher schrumpfte er auf eine unleserliche Zeile."""
        zeilen, mitte, blockmitte = self._tinte(
            "Melderkreis Erdgeschoss West", 2
        )
        self.assertGreater(zeilen, 1)
        self.assertAlmostEqual(mitte, blockmitte, delta=2)

    def test_die_vorschau_zeigt_dieselben_zeilen_wie_der_ausdruck(self):
        """Ein gemeinsames Maß, nicht jede Schrift für sich."""
        from verteilerly.layout import Text as Blatttext
        from verteilerly.layout import textzeilen, verteilerbelegungen

        for name, da in (("Haus Nord", 4), ("Melder 1", 1),
                         ("Melderkreis Erdgeschoss West", 2)):
            with self.subTest(name=name):
                v = Verteiler.aus_geometrie(1, 4, 10, name="Muster")
                v.kabel_anlegen(name, 1, 1, da)
                blatt = verteilerbelegungen(Projekt(verteiler=v))[0]
                feld = next(
                    e for e in blatt.elemente
                    if isinstance(e, Blatttext) and e.text == name
                )
                gezeichnet, _, _ = self._tinte(name, da)
                self.assertEqual(gezeichnet, len(textzeilen(feld)[1]))


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

    def test_die_conf_ist_die_der_testreihe(self):
        """Kein GUI-Test schreibt in die echte Verteilerly.conf."""
        import os

        conf = pathlib.Path(self.fenster.einstellungen.fileName())
        self.assertIn(pathlib.Path(os.environ["XDG_CONFIG_HOME"]), conf.parents)
        self.assertNotIn(pathlib.Path.home() / ".config" / "Verteilerly", conf.parents)

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
        # Die Größe zieht das Aufgelegte mit: aus 4 DA werden 6.
        self.assertEqual(kabel.da_gesamt, 6)
        self.assertEqual(kabel.da_aufgelegt, 6)
        self.assertFalse(kabel.gekuerzt)
        self.assertIn(kabel, f.projekt.verteiler.kabel)

    def test_bearbeiten_zieht_die_farben_nach(self):
        """Die Farbfolge hängt am Kabel, also folgt sie ihm."""
        from verteilerly.gui.dialoge import KabelDialog

        f = self.fenster
        verteiler = Verteiler.aus_geometrie(1, 4, 10, name="Probe")
        kabel = verteiler.kabel_anlegen(
            "Leitung", 1, 1, 10, kabeltyp="jystyv", da_gesamt=10
        )
        f._projekt_setzen(Projekt(verteiler=verteiler), None)
        from verteilerly.farbcodes import farben_eintragen

        farben_eintragen(verteiler, kabel, f.kabeltypen)
        self.assertEqual(verteiler.leiste(1).stift(9).a.farbe, "rt")
        verteiler.leiste(1).stift(1).a.farbe = "türkis"      # von Hand

        def groesser(dialog):
            # Nennweite 20 DA, aufgelegt bleiben die zehn der Leiste -
            # das Kabel ist damit gekürzt, die Lagenfolge eine andere.
            dialog.kabel_da.setValue(20)
            dialog.auflegen_da.setValue(10)
            return KabelDialog.DialogCode.Accepted

        with mock.patch.object(KabelDialog, "exec", groesser):
            f.kabel_bearbeiten(kabel)

        self.assertEqual(verteiler.leiste(1).stift(9).a.farbe, "ws")
        self.assertEqual(verteiler.leiste(1).stift(1).a.farbe, "türkis")
        self.assertIn("nachgezogen", f.statusBar().currentMessage())

    def test_bearbeiten_legt_mehr_doppeladern_auf(self):
        """Die Leitung wird größer und belegt mehr."""
        from verteilerly.gui.dialoge import KabelDialog

        f = self.fenster
        self._projekt()
        kabel = f.projekt.verteiler.kabel[0]

        with mock.patch.object(
            KabelDialog, "exec",
            lambda dialog: dialog.kabel_da.setValue(7) or KabelDialog.DialogCode.Accepted,
        ):
            f.kabel_bearbeiten(kabel)

        self.assertEqual(kabel.da_aufgelegt, 7)
        self.assertIs(f.projekt.verteiler.kabel_an(1, 7), kabel)

    def test_bearbeiten_legt_weniger_auf_und_raeumt_die_farben(self):
        from verteilerly.farbcodes import farben_eintragen
        from verteilerly.gui.dialoge import KabelDialog

        f = self.fenster
        verteiler = Verteiler.aus_geometrie(1, 4, 10, name="Probe")
        kabel = verteiler.kabel_anlegen("Leitung", 1, 1, 6, kabeltyp="jystyv")
        f._projekt_setzen(Projekt(verteiler=verteiler), None)
        farben_eintragen(verteiler, kabel, f.kabeltypen)
        self.assertTrue(verteiler.leiste(1).stift(6).a.farbe)

        with mock.patch.object(
            KabelDialog, "exec",
            lambda dialog: dialog.auflegen_da.setValue(3) or KabelDialog.DialogCode.Accepted,
        ):
            f.kabel_bearbeiten(kabel)

        self.assertEqual(kabel.da_aufgelegt, 3)
        self.assertIsNone(verteiler.kabel_an(1, 6))
        # Die Farben der freigewordenen Doppeladern gehen mit.
        self.assertEqual(verteiler.leiste(1).stift(6).a.farbe, "")
        self.assertTrue(verteiler.leiste(1).stift(3).a.farbe)
        self.assertIn("freigeräumt", f.statusBar().currentMessage())

    def test_waechst_das_kabel_ueber_die_leiste_fragt_der_ueberlauf(self):
        """Fortsetzen oder Rest verfallen lassen."""
        from verteilerly.gui.dialoge import KabelDialog, UeberlaufDialog

        f = self.fenster
        verteiler = Verteiler.aus_geometrie(1, 4, 10, name="Probe")
        kabel = verteiler.kabel_anlegen("Leitung", 1, 7, 4)
        f._projekt_setzen(Projekt(verteiler=verteiler), None)

        def fortsetzen(dialog):
            dialog.fortsetzen.setChecked(True)
            dialog.leiste.setCurrentIndex(dialog.leiste.findData(2))
            dialog.start.setValue(1)
            return UeberlaufDialog.DialogCode.Accepted

        with mock.patch.object(
            KabelDialog, "exec",
            lambda dialog: dialog.kabel_da.setValue(8) or KabelDialog.DialogCode.Accepted,
        ), mock.patch.object(UeberlaufDialog, "exec", fortsetzen):
            f.kabel_bearbeiten(kabel)

        self.assertEqual(kabel.da_aufgelegt, 8)
        self.assertEqual(len(kabel.abschnitte), 2)
        self.assertIs(verteiler.kabel_an(2, 1), kabel)

    def test_der_rest_darf_auch_verfallen(self):
        from verteilerly.gui.dialoge import KabelDialog, UeberlaufDialog

        f = self.fenster
        verteiler = Verteiler.aus_geometrie(1, 4, 10, name="Probe")
        kabel = verteiler.kabel_anlegen("Leitung", 1, 7, 4)
        f._projekt_setzen(Projekt(verteiler=verteiler), None)

        def verfallen(dialog):
            dialog.verfaellt.setChecked(True)
            return UeberlaufDialog.DialogCode.Accepted

        with mock.patch.object(
            KabelDialog, "exec",
            lambda dialog: dialog.kabel_da.setValue(8) or KabelDialog.DialogCode.Accepted,
        ), mock.patch.object(UeberlaufDialog, "exec", verfallen):
            f.kabel_bearbeiten(kabel)

        self.assertEqual(kabel.da_aufgelegt, 4)      # bis zum Leistenende
        self.assertEqual(len(kabel.abschnitte), 1)

    def test_ein_fremdes_kabel_im_weg_wird_gemeldet(self):
        from PySide6.QtWidgets import QMessageBox
        from verteilerly.gui.dialoge import KabelDialog

        f = self.fenster
        verteiler = Verteiler.aus_geometrie(1, 4, 10, name="Probe")
        kabel = verteiler.kabel_anlegen("Leitung", 1, 1, 4)
        verteiler.kabel_anlegen("Nachbar", 1, 6, 2)
        f._projekt_setzen(Projekt(verteiler=verteiler), None)

        gemeldet = {}
        with mock.patch.object(
            KabelDialog, "exec",
            lambda dialog: dialog.kabel_da.setValue(8) or KabelDialog.DialogCode.Accepted,
        ), mock.patch.object(
            QMessageBox, "warning",
            lambda eltern, titel, text: gemeldet.update(titel=titel, text=text),
        ):
            f.kabel_bearbeiten(kabel)

        self.assertEqual(gemeldet.get("titel"), "Kabel nicht geändert")
        self.assertEqual(kabel.da_aufgelegt, 4)

    def test_abnehmen_nimmt_die_farben_mit(self):
        """Sonst stünde die alte Folge noch da, wenn die nächste aufliegt."""
        from verteilerly.gui.dialoge import KabelDialog
        from verteilerly.farbcodes import farben_eintragen

        f = self.fenster
        verteiler = Verteiler.aus_geometrie(1, 4, 10, name="Probe")
        kabel = verteiler.kabel_anlegen("Leitung", 1, 1, 4, kabeltyp="jystyv")
        f._projekt_setzen(Projekt(verteiler=verteiler), None)
        farben_eintragen(verteiler, kabel, f.kabeltypen)
        verteiler.leiste(1).stift(2).a.farbe = "türkis"      # von Hand

        def entfernen(dialog):
            dialog._entfernen()
            return KabelDialog.DialogCode.Accepted

        with mock.patch.object(KabelDialog, "exec", entfernen):
            f.kabel_bearbeiten(kabel)

        self.assertEqual(verteiler.leiste(1).stift(1).a.farbe, "")
        self.assertEqual(verteiler.leiste(1).stift(2).a.farbe, "türkis")
        self.assertIn("mit entfernt", f.statusBar().currentMessage())

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

    def _ueber_kasten(self):
        """Zeigt das Über-Fenster, ohne es stehen zu lassen."""
        from PySide6.QtWidgets import QMessageBox

        gezeigt = {}
        with mock.patch.object(
            QMessageBox, "exec", lambda kasten: gezeigt.update(kasten=kasten) or 0
        ):
            self.fenster.ueber()
        return gezeigt["kasten"]

    def _ueber_text(self) -> str:
        return self._ueber_kasten().text()

    def test_ueber_verweist_auf_die_lizenztexte(self):
        """Im Netz und im Arbeitsordner - der Einhängepunkt ist weg."""
        import re

        from PySide6.QtWidgets import QLabel

        kasten = self._ueber_kasten()
        verweise = re.findall(r'href="([^"]+)"', kasten.text())
        self.assertIn("https://www.gnu.org/licenses/gpl-3.0.html", verweise)
        self.assertIn("https://www.gnu.org/licenses/lgpl-3.0.html", verweise)
        self.assertTrue(any(z.startswith("file://") for z in verweise))
        # Blauer Text allein nützt nichts - die Verweise müssen aufgehen.
        beschriftungen = [k for k in kasten.findChildren(QLabel) if k.text()]
        self.assertTrue(all(k.openExternalLinks() for k in beschriftungen))

    def test_ueber_nennt_keinen_proprietaeren_bestandteil(self):
        text = self._ueber_text()
        self.assertNotIn("proprietär", text)

    def test_ueber_nennt_die_lizenz_des_programms(self):
        text = self._ueber_text()
        self.assertIn("GNU GPL, Version 3", text)
        self.assertIn("GPL-3.0-or-later", text)

    def test_ueber_nennt_die_ki_unterstuetzung(self):
        """Wie es entstanden ist, gehört dazu."""
        text = self._ueber_text()
        self.assertIn("KI-Unterstützung", text)
        self.assertIn("Claude Code", text)

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

    def test_paket_bringt_die_wahl_der_erweiterungen_nicht_mit(self):
        """Ein Paket aus fremder Hand schaltet keine eigene Erweiterung ein."""
        import tempfile
        import zipfile
        from pathlib import Path

        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QFileDialog

        from verteilerly import paket, pfade
        from verteilerly.gui.dialoge import PaketDialog

        f = self.fenster
        with tempfile.TemporaryDirectory() as ordner:
            conf = Path(ordner) / "Verteilerly.conf"
            daten = Path(ordner) / "daten"
            f.einstellungen = QSettings(str(conf), QSettings.Format.IniFormat)
            f.einstellungen.setValue("erweiterungen_an", "meine")
            f.einstellungen.setValue("erweiterungen_nur_eingebaute", True)
            f.einstellungen.setValue("blattvorlage", "standard")
            f.einstellungen.sync()

            fremd = Path(ordner) / "fremd.zip"
            with zipfile.ZipFile(fremd, "w") as datei:
                datei.writestr(paket.MERKZETTEL, '{"kennung": "verteilerly-paket"}')
                datei.writestr(paket.CONFNAME, (
                    "[General]\nblattvorlage=knapp\n"
                    "erweiterungen_an=boese\nerweiterungen_aus=blattvorlageneditor\n"
                    "erweiterungen_nur_eingebaute=false\n"
                ))

            with mock.patch.object(pfade, "eigener_datenordner", return_value=daten), \
                 mock.patch.object(
                     QFileDialog, "getOpenFileName", return_value=(str(fremd), "")
                 ), mock.patch.object(
                     PaketDialog, "exec",
                     lambda dialog: PaketDialog.DialogCode.Accepted,
                 ):
                f.paket_einspielen()

            # Die übrigen Einstellungen kommen an …
            self.assertEqual(f.einstellungen.value("blattvorlage"), "knapp")
            # … die Wahl der Erweiterungen bleibt, wie sie war.
            self.assertEqual(f.einstellungen.value("erweiterungen_an"), "meine")
            self.assertFalse(f.einstellungen.contains("erweiterungen_aus"))
            self.assertTrue(
                f.einstellungen.value("erweiterungen_nur_eingebaute", type=bool)
            )

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
        from verteilerly import bestand

        gezeigt = {"text": self._ueber_text()}

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

    def test_leisten_heissen_auf_wunsch_mit_buchstaben(self):
        """Die Beschriftung gehört dem Verteiler - und wird als Vorgabe gemerkt."""
        from verteilerly.modell import Verteiler

        from . import einstellung_bewahren

        f = self.fenster
        einstellung_bewahren(self, f.einstellungen, "leisten_schreibweise")
        self.addCleanup(f.leistenweise_waehlen, "zahlen")
        self._projekt()
        f.leistenweise_waehlen("buchstaben")
        self.assertEqual(f.leisten_schreibweise, "buchstaben")
        self.assertEqual(f.projekt.leisten_schreibweise, "buchstaben")
        # Das Projekt ist damit geändert - es steht ja in seiner Datei.
        self.assertTrue(f.veraendert)
        self.assertEqual(f.leistenansicht.modell.leisten_schreibweise, "buchstaben")
        self.assertTrue(f.leistenansicht.auswahl.itemText(0).startswith("Leiste A"))
        angehakt = [e for e in f.leistenweisen_gruppe.actions() if e.isChecked()]
        self.assertEqual([e.data() for e in angehakt], ["buchstaben"])

        # Gemerkt wird sie als Vorgabe für den nächsten neuen Verteiler.
        self.assertEqual(
            f.einstellungen.value("leisten_schreibweise"), "buchstaben"
        )
        neu = f.neues_projekt(Verteiler.aus_geometrie(1, 2, 10))
        self.assertEqual(neu.leisten_schreibweise, "buchstaben")

    def test_der_haken_im_neuen_verteiler_gilt_und_wird_vorgabe(self):
        """Was im Dialog steht, zählt - auch das Weglassen des Hakens."""
        from unittest import mock

        from verteilerly.gui import hauptfenster as modul

        from . import einstellung_bewahren

        f = self.fenster
        einstellung_bewahren(self, f.einstellungen, "leisten_schreibweise")
        self.addCleanup(f.leistenweise_waehlen, "zahlen")

        def anlegen(haken):
            def vorbereiten(dialog):
                dialog.buchstaben.setChecked(haken)
                return modul.NeuerVerteilerDialog.DialogCode.Accepted

            with mock.patch.object(
                modul.NeuerVerteilerDialog, "exec", vorbereiten
            ):
                f.neuer_verteiler()

        anlegen(True)
        self.assertEqual(f.projekt.leisten_schreibweise, "buchstaben")
        self.assertEqual(
            f.einstellungen.value("leisten_schreibweise"), "buchstaben"
        )
        self.assertTrue(f.leistenansicht.auswahl.itemText(0).startswith("Leiste A"))

        # Der nächste Dialog hat den Haken schon - wer ihn wegnimmt,
        # bekommt Zahlen, die Vorgabe schreibt nichts dazwischen.
        anlegen(False)
        self.assertEqual(f.projekt.leisten_schreibweise, "zahlen")
        self.assertEqual(f.einstellungen.value("leisten_schreibweise"), "zahlen")

    def test_ein_geoeffnetes_projekt_bringt_seine_beschriftung_mit(self):
        """Nicht die Einstellung gilt, sondern was in der Datei steht."""
        from verteilerly.modell import Projekt, Verteiler

        from . import einstellung_bewahren

        f = self.fenster
        einstellung_bewahren(self, f.einstellungen, "leisten_schreibweise")
        self.addCleanup(f.leistenweise_waehlen, "zahlen")
        self._projekt()
        f.leistenweise_waehlen("buchstaben")

        # Ein Projekt, das Zahlen führt, bleibt bei Zahlen.
        gezaehlt = Projekt(verteiler=Verteiler.aus_geometrie(1, 2, 10, name="Alt"))
        f._projekt_setzen(gezaehlt, None)
        self.assertEqual(f.leisten_schreibweise, "zahlen")
        self.assertTrue(f.leistenansicht.auswahl.itemText(0).startswith("Leiste 1"))
        angehakt = [e for e in f.leistenweisen_gruppe.actions() if e.isChecked()]
        self.assertEqual([e.data() for e in angehakt], ["zahlen"])
        self.assertFalse(f.veraendert)

    def test_eine_unbekannte_leistenschreibweise_wird_gezaehlt(self):
        """Eine Angabe aus einer neueren Fassung hält nichts auf."""
        from verteilerly.einstellungen import leistenweise

        self.assertEqual(leistenweise("buchstaben"), "buchstaben")
        for wert in ("roemisch", "", None):
            with self.subTest(wert=wert):
                self.assertEqual(leistenweise(wert), "zahlen")

    def test_die_vorschau_bleibt_neben_einem_vollen_verteiler(self):
        """Ein Verteiler voller langer Kabelnamen schob sie sonst hinaus."""
        f = self.fenster
        f.resize(1280, 800)
        vorher = f.hauptteiler.sizes()

        verteiler = Verteiler.aus_geometrie(2, 6, 20, name="Voll")
        for nummer in range(1, 13):
            verteiler.kabel_anlegen(
                f"Musterleitung Obergeschoss Zimmer {nummer} vom Hauptverteiler",
                1, nummer, 1,
            )
        f._projekt_setzen(Projekt(verteiler=verteiler), None)
        ANWENDUNG.processEvents()
        self.assertEqual(f.hauptteiler.sizes(), vorher)

        # Und wegziehen lässt sie sich auch nicht: dafür gibt es F9.
        f.hauptteiler.setSizes([5000, 0])
        ANWENDUNG.processEvents()
        self.assertGreater(f.hauptteiler.sizes()[1], 0)
        self.assertFalse(f.hauptteiler.childrenCollapsible())

    def test_eine_datei_laesst_sich_ohne_dialog_oeffnen(self):
        """So kommt der Doppelklick aus der Dateiverwaltung herein."""
        import json

        from verteilerly import projektdatei

        f = self.fenster
        with tempfile.TemporaryDirectory() as ordner:
            pfad = pathlib.Path(ordner) / "Probe.vtly"
            projektdatei.speichern(
                Projekt(verteiler=Verteiler.aus_geometrie(1, 2, 10, name="Probe")),
                pfad,
            )
            self.assertTrue(f.datei_oeffnen(pfad))
            self.assertEqual(f.projekt.verteiler.name, "Probe")
            self.assertEqual(f.pfad, pfad)

            # Und eine kaputte Datei gibt eine Meldung, keinen Absturz.
            kaputt = pathlib.Path(ordner) / "Kaputt.vtly"
            kaputt.write_text("{kein JSON", encoding="utf-8")
            with mock.patch.object(QMessageBox, "critical") as gezeigt:
                self.assertFalse(f.datei_oeffnen(kaputt))
            self.assertTrue(gezeigt.called)
            self.assertEqual(f.projekt.verteiler.name, "Probe")

    def test_der_dialog_sagt_welche_datei_zu_verknuepfen_ist(self):
        """Er trägt nichts mehr ein - er gibt Auskunft."""
        from verteilerly import verknuepfung
        from verteilerly.gui import hauptfenster as modul

        f = self.fenster
        self.assertEqual(f.aktion_verknuepfen.isEnabled(), verknuepfung.moeglich())
        with mock.patch.object(
            modul.verknuepfung, "zu_verknuepfen",
            return_value=pathlib.Path("/stick/VerteilerlyPortable.exe"),
        ), mock.patch.object(
            modul.verknuepfung, "angemeldeter_aufruf", return_value=""
        ), mock.patch.object(
            modul.verknuepfung, "angemeldet", return_value=False
        ), mock.patch.object(QMessageBox, "information") as gezeigt:
            f.verknuepfung_zeigen()
        gemeldet = gezeigt.call_args[0][2]
        self.assertIn("/stick/VerteilerlyPortable.exe", gemeldet)
        self.assertIn("nichts eingetragen", gemeldet)
        self.assertIn("PortableApps", gemeldet)
        self.assertIn("Öffnen mit", gemeldet, "der Weg dorthin steht dabei")

    def test_der_dialog_sagt_wenn_verknuepft_ist(self):
        from verteilerly.gui import hauptfenster as modul

        f = self.fenster
        with mock.patch.object(
            modul.verknuepfung, "angemeldet", return_value=True
        ), mock.patch.object(
            modul.verknuepfung, "angemeldeter_aufruf",
            return_value="/stick/Verteilerly.AppImage",
        ):
            text = f._verknuepfungstext()
        self.assertIn("Verknüpft: ja", text)

    def test_der_dialog_nennt_das_programm_das_stattdessen_oeffnet(self):
        from verteilerly.gui import hauptfenster as modul

        f = self.fenster
        with mock.patch.object(
            modul.verknuepfung, "angemeldet", return_value=False
        ), mock.patch.object(
            modul.verknuepfung, "angemeldeter_aufruf",
            return_value="C:\\Windows\\notepad.exe",
        ):
            text = f._verknuepfungstext()
        self.assertIn("Verknüpft: nein", text)
        self.assertIn("notepad.exe", text)

    def test_eine_weggenommene_zuordnung_steht_als_solche_da(self):
        from verteilerly import verknuepfung
        from verteilerly.gui import hauptfenster as modul

        f = self.fenster
        with mock.patch.object(
            modul.verknuepfung, "angemeldet", return_value=False
        ), mock.patch.object(
            modul.verknuepfung, "angemeldeter_aufruf",
            return_value=verknuepfung.KEINE,
        ):
            text = f._verknuepfungstext()
        self.assertIn("weggenommen", text)

    def test_der_start_sagt_es_wenn_ein_anderes_programm_eingetragen_ist(self):
        from verteilerly.gui import hauptfenster as modul

        f = self.fenster
        # Aus dem Quellbaum wird nicht gefragt - das waere Laerm.
        with mock.patch.object(modul.pfade, "gepackt", return_value=False), \
             mock.patch.object(modul.verknuepfung, "anderes_programm") as gefragt:
            f._zuordnung_pruefen()
        self.assertFalse(gefragt.called)

        with mock.patch.object(modul.pfade, "gepackt", return_value=True), \
             mock.patch.object(modul.verknuepfung, "anderes_programm",
                               return_value="/stick/VerteilerlyPortable.exe"):
            f._zuordnung_pruefen()
        self.assertIn("VerteilerlyPortable.exe", f.statusBar().currentMessage())

    def test_der_start_sagt_es_wenn_die_zuordnung_aufgehoben_wurde(self):
        """Von außen weggenommen - unsere Einträge stehen noch da."""
        from verteilerly.gui import hauptfenster as modul

        f = self.fenster
        with mock.patch.object(modul.pfade, "gepackt", return_value=True), \
             mock.patch.object(modul.verknuepfung, "anderes_programm",
                               return_value=""), \
             mock.patch.object(modul.verknuepfung, "aufgehoben",
                               return_value=True):
            f.statusBar().clearMessage()
            f._zuordnung_pruefen()
        self.assertIn("nicht mehr", f.statusBar().currentMessage())

        # Und ohne Anmeldung sagt der Start nichts - da fehlt nichts.
        with mock.patch.object(modul.pfade, "gepackt", return_value=True), \
             mock.patch.object(modul.verknuepfung, "anderes_programm",
                               return_value=""), \
             mock.patch.object(modul.verknuepfung, "aufgehoben",
                               return_value=False):
            f.statusBar().clearMessage()
            f._zuordnung_pruefen()
        self.assertEqual(f.statusBar().currentMessage(), "")

    def test_ein_gezogenes_kabel_wird_verschoben_oder_kopiert(self):
        """Was die Übersicht meldet, führt das Fenster aus."""
        f = self.fenster
        verteiler = Verteiler.aus_geometrie(1, 3, 10, name="Probe")
        kabel = verteiler.kabel_anlegen("Leitung", 1, 1, 4)
        verteiler.leiste(1).stift(2).ader("a").bezeichnung = "Melder"
        f._projekt_setzen(Projekt(verteiler=verteiler), None)

        f._kabel_umlegen(kabel, 2, 5, False)
        self.assertEqual(kabel.abschnitte[0].leiste, 2)
        self.assertEqual(verteiler.leiste(2).stift(6).ader("a").bezeichnung, "Melder")
        self.assertIn("verschoben", f.statusBar().currentMessage())
        self.assertTrue(f.veraendert)

        f._kabel_umlegen(kabel, 3, 1, True)
        self.assertEqual(len(verteiler.kabel), 2)
        self.assertEqual(verteiler.kabel[-1].beschriftung, "Leitung (Kopie)")
        self.assertIn("kopiert", f.statusBar().currentMessage())

        # Auf einen belegten Platz geht es nicht - und es gibt eine Meldung,
        # kein Fenster: für eine Mausbewegung wäre das zu viel.
        f._kabel_umlegen(kabel, 3, 1, False)
        self.assertIn("belegt", f.statusBar().currentMessage())
        self.assertEqual(kabel.abschnitte[0].leiste, 2)

    def test_eine_fehlende_blattvorlage_haelt_das_fenster_nicht_auf(self):
        """Wer „beispiel" gewählt hatte, soll das Programm noch starten können."""
        from verteilerly.gui.hauptfenster import Hauptfenster

        from . import einstellung_bewahren

        f = self.fenster
        einstellung_bewahren(self, f.einstellungen, "blattvorlage")
        f.einstellungen.setValue("blattvorlage", "gibtsnicht")
        zweites = Hauptfenster()
        self.addCleanup(zweites.close)
        self.assertEqual(
            zweites.vorschau.blattvorlage.id, zweites.blattvorlagen.standard.id
        )

    def test_die_blattvorlage_laesst_sich_umbenennen(self):
        """Der Name steht im Menü, die Kennung in der conf."""
        import tempfile

        from verteilerly.gui.dialoge import BlattvorlagenDialog

        f = self.fenster
        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        ziel = pathlib.Path(ordner.name)
        vorher = f.blattvorlagen.holen("knapp").name

        def umbenennen(dialog):
            stelle = next(
                i for i in range(dialog.liste.count())
                if dialog.liste.item(i).data(Qt.ItemDataRole.UserRole) == "knapp"
            )
            dialog.liste.setCurrentRow(stelle)
            with mock.patch.object(
                dialoge.QInputDialog, "getText", return_value=("Rangierblatt", True)
            ):
                dialog.umbenennen()
            return BlattvorlagenDialog.DialogCode.Rejected

        from verteilerly.gui import dialoge

        with mock.patch.object(f, "_blattvorlagenordner", return_value=ziel), \
             mock.patch.object(BlattvorlagenDialog, "exec", umbenennen):
            f.blattvorlage_waehlen()
        self.assertTrue((ziel / "knapp.yaml").is_file())
        self.assertIn("umbenannt", f.statusBar().currentMessage())
        # Der Probelauf schreibt in einen eigenen Ordner - das Fenster
        # liest danach den echten wieder ein, dort steht der alte Name.
        self.assertEqual(f.blattvorlagen.holen("knapp").name, vorher)

    def test_ohne_beschreibbaren_ordner_bleibt_der_knopf_aus(self):
        from verteilerly.gui.dialoge import BlattvorlagenDialog

        dialog = BlattvorlagenDialog(self.fenster.blattvorlagen, "standard")
        self.addCleanup(dialog.close)
        self.assertFalse(dialog.umbenennen_knopf.isEnabled())
        self.assertFalse(dialog.loeschen_knopf.isEnabled())
        self.assertFalse(dialog.zurueck_knopf.isEnabled())
        dialog.umbenennen()          # darf nicht scheitern
        dialog.loeschen()
        self.assertEqual(dialog.umbenannt, {})
        self.assertEqual(dialog.geloescht, [])

    def test_die_blattvorlage_laesst_sich_loeschen(self):
        """Die gelöschte bleibt weg - auch nach dem Neustart."""
        import shutil
        import tempfile

        from verteilerly import pfade
        from verteilerly.gui.dialoge import BlattvorlagenDialog

        f = self.fenster
        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        ziel = pathlib.Path(ordner.name)
        shutil.copy2(
            pfade.mitgeliefert() / "blattvorlagen" / "knapp.yaml", ziel / "knapp.yaml"
        )

        def loeschen(dialog):
            stelle = next(
                i for i in range(dialog.liste.count())
                if dialog.liste.item(i).data(Qt.ItemDataRole.UserRole) == "knapp"
            )
            dialog.liste.setCurrentRow(stelle)
            with mock.patch.object(
                dialoge, "frage", return_value=QMessageBox.StandardButton.Yes
            ):
                dialog.loeschen()
            return BlattvorlagenDialog.DialogCode.Rejected

        from verteilerly.gui import dialoge, hauptfenster

        gemerkt = []
        with mock.patch.object(f, "_blattvorlagenordner", return_value=ziel), \
             mock.patch.object(hauptfenster.pfade, "loeschen_merken",
                               gemerkt.append), \
             mock.patch.object(BlattvorlagenDialog, "exec", loeschen):
            f.blattvorlage_waehlen()
        self.assertFalse((ziel / "knapp.yaml").exists())
        self.assertEqual(gemerkt, ["blattvorlagen/knapp.yaml"])
        self.assertIn("gelöscht", f.statusBar().currentMessage())

    def test_mitgelieferte_blattvorlagen_kommen_zurueck(self):
        """Derselbe Weg wie bei den Verteilervorlagen."""
        from verteilerly.gui.dialoge import BlattvorlagenDialog

        f = self.fenster

        def zurueck(dialog):
            dialog.wiederhergestellt = True
            return BlattvorlagenDialog.DialogCode.Rejected

        with mock.patch.object(f, "_mitgeliefertes_wiederherstellen") as geholt, \
             mock.patch.object(BlattvorlagenDialog, "exec", zurueck):
            f.blattvorlage_waehlen()
        geholt.assert_called_once_with("blattvorlagen")
        self.assertIn("wiederhergestellt", f.statusBar().currentMessage())

    def test_ein_nein_laesst_die_blattvorlage_stehen(self):
        from verteilerly.gui import dialoge
        from verteilerly.gui.dialoge import BlattvorlagenDialog

        dialog = BlattvorlagenDialog(
            self.fenster.blattvorlagen, "standard", ordner=pathlib.Path(".")
        )
        self.addCleanup(dialog.close)
        with mock.patch.object(
            dialoge, "frage", return_value=QMessageBox.StandardButton.No
        ):
            dialog.loeschen()
            dialog.wiederherstellen()
        self.assertEqual(dialog.geloescht, [])
        self.assertFalse(dialog.wiederhergestellt)

    def test_eine_kaputte_blattvorlage_haelt_das_fenster_nicht_auf(self):
        """Übergangen und gemeldet, statt den Start zu verhindern."""
        import shutil
        import tempfile

        from verteilerly import pfade
        from verteilerly.gui import hauptfenster

        f = self.fenster
        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        ziel = pathlib.Path(ordner.name)
        shutil.copy2(
            pfade.mitgeliefert() / "blattvorlagen" / "knapp.yaml", ziel / "knapp.yaml"
        )
        (ziel / "kaputt.yaml").write_text(
            "id: kaputt\nname: Kaputt\nbuchten_je_blatt: 0\n", encoding="utf-8"
        )

        gemeldet = []
        with mock.patch.object(hauptfenster.pfade, "blattvorlagenordner_alle",
                               return_value=[ziel]), \
             mock.patch.object(hauptfenster.QMessageBox, "warning",
                               lambda *args, **kw: gemeldet.append(args[2])):
            vorlagen = f._blattvorlagen_laden()

        self.assertIn("knapp", [v.id for v in vorlagen.alle])
        self.assertNotIn("kaputt", [v.id for v in vorlagen.alle])
        self.assertEqual(len(gemeldet), 1)
        self.assertIn("buchten_je_blatt", gemeldet[0])

    def test_ein_vertippter_schluessel_kommt_in_dieselbe_meldung(self):
        """Verteiler-, Blattvorlagen und Kabeltypen auf einem Zettel."""
        import tempfile

        from verteilerly.gui import hauptfenster

        f = self.fenster
        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        ziel = pathlib.Path(ordner.name)
        (ziel / "tipp.yaml").write_text(
            "id: tipp\nname: Tipp\nzeilenhohe_max: 7\n", encoding="utf-8"
        )

        zettel: list[str] = []
        with mock.patch.object(hauptfenster.pfade, "blattvorlagenordner_alle",
                               return_value=[ziel]):
            vorlagen = f._blattvorlagen_laden(zettel)

        # Gelesen wird sie trotzdem - nur der Schlüssel wird beanstandet.
        self.assertIn("tipp", [v.id for v in vorlagen.alle])
        self.assertEqual(len(zettel), 1)
        self.assertIn("zeilenhohe_max", zettel[0])

        gemeldet = []
        with mock.patch.object(hauptfenster.QMessageBox, "warning",
                               lambda *args, **kw: gemeldet.append(args[2])):
            f._hinweise_zeigen(zettel)
        self.assertIn("zeilenhohe_max", gemeldet[0])

    def test_geloeschte_blattvorlagen_bleiben_beim_laden_weg(self):
        """Ohne den Vermerk holte das Abbild sie zurück."""
        from verteilerly.gui import hauptfenster

        f = self.fenster
        with mock.patch.object(hauptfenster.pfade, "geloeschte",
                               return_value={"blattvorlagen/knapp.yaml"}):
            vorlagen = f._blattvorlagen_laden()
        self.assertNotIn("knapp", [v.id for v in vorlagen.alle])

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

    def test_die_ausgabe_steht_in_einem_untermenue(self):
        """Drei Wege aus dem Programm heraus - sie gehören zusammen."""
        from PySide6.QtWidgets import QMenu

        menues = {
            menue.title().replace("&", ""): menue
            for menue in self.fenster.menuBar().findChildren(QMenu)
        }
        self.assertIn("Exportieren", menues)
        eintraege = [
            eintrag.text().replace("&", "")
            for eintrag in menues["Exportieren"].actions()
        ]
        self.assertEqual(eintraege, ["Als PDF…", "Als Excel-Mappe…", "Als CSV…"])
        # Im Dateimenü stehen sie dann nicht noch einmal.
        datei = [
            eintrag.text().replace("&", "")
            for eintrag in menues["Datei"].actions() if eintrag.text()
        ]
        self.assertIn("Exportieren", datei)
        self.assertNotIn("Als PDF…", datei)
        # In der Werkzeugleiste steht der Exportknopf mit demselben Menü.
        from PySide6.QtWidgets import QToolBar

        leiste = self.fenster.findChild(QToolBar)
        self.assertIn(self.fenster.export_knopf, leiste.findChildren(type(
            self.fenster.export_knopf)))
        self.assertIs(self.fenster.export_knopf.menu(), menues["Exportieren"])

    def test_der_exportknopf_nennt_das_gewaehlte_format(self):
        """Auf dem Knopf steht, was ein Druck bewirkt."""
        knopf = self.fenster.export_knopf
        self.fenster.exportformat_setzen("pdf", ausgeben=False)
        self.assertEqual(knopf.defaultAction().text(), "Export (PDF)")
        self.fenster.exportformat_setzen("xlsx", ausgeben=False)
        self.assertEqual(knopf.defaultAction().text(), "Export (XLSX)")
        self.fenster.exportformat_setzen("csv", ausgeben=False)
        self.assertEqual(knopf.defaultAction().text(), "Export (CSV)")

    def test_der_pfeil_oeffnet_die_drei_formate(self):
        from PySide6.QtWidgets import QToolButton

        knopf = self.fenster.export_knopf
        self.assertEqual(
            knopf.popupMode(), QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )
        self.assertEqual(
            [h.text().replace("&", "") for h in knopf.menu().actions()],
            ["Als PDF…", "Als Excel-Mappe…", "Als CSV…"],
        )

    def test_der_ansichtsknopf_klappt_die_drei_bereiche_aus(self):
        """Wie der Exportknopf: ein Knopf mit Pfeil in der Werkzeugleiste."""
        from PySide6.QtWidgets import QToolBar, QToolButton

        f = self.fenster
        knopf = f.ansicht_knopf
        self.assertIn(knopf, f.findChild(QToolBar).findChildren(QToolButton))
        self.assertEqual(
            knopf.popupMode(), QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )
        self.assertEqual(
            [h.text().replace("&", "") for h in knopf.menu().actions()],
            ["Verteilerübersicht anzeigen", "Leistenansicht anzeigen",
             "Vorschau anzeigen"],
        )

    def test_die_wahl_steht_danach_auf_dem_ansichtsknopf(self):
        """Gewählt wird im Pfeilmenü, geschaltet danach mit dem Knopf."""
        f = self.fenster
        self.addCleanup(f.ansichtsknopf_setzen, "vorschau")
        self.addCleanup(f.leistenansicht_zeigen, True)
        f.aktion_leistenansicht.setChecked(True)
        f.leistenansicht_zeigen(True)
        f.ansichtsknopf_setzen("vorschau")
        self.assertIs(f.ansicht_knopf.defaultAction(), f.aktion_vorschau)

        # Die Wahl wirkt sofort und steht dann auf dem Knopf.
        f.ansichtswahl["leistenansicht"].trigger()
        self.assertTrue(f.leistenansicht.isHidden())
        self.assertIs(f.ansicht_knopf.defaultAction(), f.aktion_leistenansicht)
        self.assertEqual(
            f.ansicht_knopf.text().replace("&", ""), "Leistenansicht anzeigen"
        )
        self.assertFalse(f.ansicht_knopf.isChecked())
        self.assertFalse(f.ansichtswahl["leistenansicht"].isChecked())
        self.assertEqual(f.einstellungen.value("ansichtsknopf"), "leistenansicht")

        # Ein Druck auf den Knopf blendet denselben Bereich wieder ein.
        f.ansicht_knopf.click()
        self.assertFalse(f.leistenansicht.isHidden())
        self.assertTrue(f.ansicht_knopf.isChecked())
        self.assertTrue(f.ansichtswahl["leistenansicht"].isChecked())

    def test_f7_und_f8_stellen_den_knopf_nicht_um(self):
        """Nur die Wahl im Pfeilmenü legt einen Bereich auf den Knopf."""
        f = self.fenster
        self.addCleanup(f.uebersicht_zeigen, True)
        self.addCleanup(f.ansichtsknopf_setzen, "vorschau")
        f.ansichtsknopf_setzen("vorschau")
        f.aktion_uebersicht.setChecked(True)
        f.uebersicht_zeigen(True)
        f.aktion_uebersicht.trigger()
        self.assertTrue(f.uebersichtsbereich.isHidden())
        self.assertFalse(f.ansichtswahl["uebersicht"].isChecked())
        self.assertIs(f.ansicht_knopf.defaultAction(), f.aktion_vorschau)

    def test_ein_neues_fenster_kennt_die_wahl_des_knopfs(self):
        from verteilerly.gui.hauptfenster import Hauptfenster

        self.addCleanup(self.fenster.ansichtsknopf_setzen, "vorschau")
        self.fenster.ansichtsknopf_setzen("uebersicht")
        zweites = Hauptfenster()
        self.addCleanup(zweites.close)
        self.assertIs(zweites.ansicht_knopf.defaultAction(), zweites.aktion_uebersicht)

    def test_der_blattwahldialog_laesst_nichts_leeres_zu(self):
        from PySide6.QtWidgets import QDialogButtonBox
        from verteilerly.gui.dialoge import BlattwahlDialog

        dialog = BlattwahlDialog({"deckblatt": 1, "belegung": 1, "leisten": 4}, {"leisten"})
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.auswahl(), {"leisten"})
        self.assertIn("(4)", dialog.haken["leisten"].text())
        weiter = dialog.knoepfe.button(QDialogButtonBox.StandardButton.Ok)
        self.assertTrue(weiter.isEnabled())
        dialog.haken["leisten"].setChecked(False)
        self.assertFalse(weiter.isEnabled())

    def test_das_pdf_traegt_nur_die_gewaehlten_blaetter(self):
        """Abgewählt ist nicht im PDF - und beim nächsten Mal steht die Wahl vor."""
        from pypdf import PdfReader
        from verteilerly.gui.dialoge import BlattwahlDialog

        from . import einstellung_bewahren

        f = self.fenster
        self._projekt()
        einstellung_bewahren(self, f.einstellungen, "pdf_blaetter")
        ziel = pathlib.Path(self.ordner.name) / "teil.pdf"

        def nur_leisten(dialog):
            # Vorbelegt ist, was in der echten Conf steht - also alles setzen.
            dialog.haken["deckblatt"].setChecked(False)
            dialog.haken["belegung"].setChecked(False)
            dialog.haken["leisten"].setChecked(True)
            return BlattwahlDialog.DialogCode.Accepted

        with mock.patch.object(BlattwahlDialog, "exec", nur_leisten), \
                mock.patch.object(f, "_ausgabeziel", return_value=ziel):
            f.pdf_ausgeben()
        self.assertEqual(len(PdfReader(str(ziel)).pages), 4)
        self.assertEqual(f.einstellungen.value("pdf_blaetter"), "leisten")

        gesehen = {}

        def abbrechen(dialog):
            gesehen["auswahl"] = dialog.auswahl()
            return BlattwahlDialog.DialogCode.Rejected

        with mock.patch.object(BlattwahlDialog, "exec", abbrechen), \
                mock.patch.object(f, "_ausgabeziel") as dateidialog:
            f.pdf_ausgeben()
        self.assertEqual(gesehen["auswahl"], {"leisten"})
        # Abgebrochen wird vor dem Dateidialog.
        self.assertFalse(dateidialog.called)

    def test_der_knopf_gibt_das_gewaehlte_format_aus(self):
        self._projekt()
        self.fenster.exportformat_setzen("csv", ausgeben=False)
        with mock.patch.object(type(self.fenster), "csv_ausgeben") as gerufen:
            self.fenster.exportieren()
        self.assertTrue(gerufen.called)

    def test_was_zuletzt_gewaehlt_wurde_steht_auf_dem_knopf(self):
        """Wer einmal CSV wählt, findet es beim nächsten Druck wieder."""
        self._projekt()
        with mock.patch.object(self.fenster, "_ausgabeziel", return_value=None):
            self.fenster.xlsx_ausgeben()
        self.assertEqual(self.fenster.exportformat, "xlsx")
        self.assertEqual(
            self.fenster.export_knopf.defaultAction().text(), "Export (XLSX)"
        )
        self.assertEqual(self.fenster.einstellungen.value("exportformat"), "xlsx")
        self.fenster.exportformat_setzen("pdf", ausgeben=False)

    def test_ohne_verteiler_ist_der_knopf_aus(self):
        self.fenster._projekt_setzen(None, None)
        self.assertFalse(self.fenster.export_knopf.isEnabled())
        self._projekt()
        self.assertTrue(self.fenster.export_knopf.isEnabled())

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
            ["Blattvorlage…", "Verteilervorlagen…",
             "Vorgaben für neue Verteiler…",
             "Vorlagen und Einstellungen sichern…",
             "Vorlagen und Einstellungen einspielen…",
             "Sprache", "Schreibweise der Rangierungen",
            "Leisten beschriften",
            "Freitext im Rangierfeld zulassen"],
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

    def test_beide_leistenschreibweisen_stehen_im_menue(self):
        from verteilerly.gui.hauptfenster import LEISTENWEISEN

        eintraege = self.fenster.leistenweisen_gruppe.actions()
        self.assertEqual(
            [e.text() for e in eintraege], [b for _k, b, _e in LEISTENWEISEN]
        )
        angehakt = [e for e in eintraege if e.isChecked()]
        self.assertEqual(len(angehakt), 1)
        self.assertEqual(angehakt[0].data(), self.fenster.leisten_schreibweise)

    def test_uebersicht_und_leistenansicht_lassen_sich_ausblenden(self):
        """Wie die Vorschau - F7 und F8, und gemerkt wird es auch."""
        f = self.fenster
        self.addCleanup(f.leistenansicht_zeigen, True)
        self.addCleanup(f.uebersicht_zeigen, True)
        for aktion in (f.aktion_uebersicht, f.aktion_leistenansicht):
            aktion.setChecked(True)
        f.uebersicht_zeigen(True)
        f.leistenansicht_zeigen(True)
        self.assertEqual(f.aktion_uebersicht.shortcut().toString(), "F7")
        self.assertEqual(f.aktion_leistenansicht.shortcut().toString(), "F8")

        f.aktion_uebersicht.trigger()
        self.assertTrue(f.uebersichtsbereich.isHidden())
        self.assertFalse(f.leistenansicht.isHidden())
        self.assertFalse(f.einstellungen.value("uebersicht", True, type=bool))
        self.assertFalse(f.teiler.isHidden())

        # Ist links nichts mehr, gehört der Platz der Vorschau.
        f.aktion_leistenansicht.trigger()
        self.assertTrue(f.leistenansicht.isHidden())
        self.assertFalse(f.einstellungen.value("leistenansicht", True, type=bool))
        self.assertTrue(f.teiler.isHidden())

        f.aktion_uebersicht.trigger()
        self.assertFalse(f.uebersichtsbereich.isHidden())
        self.assertFalse(f.teiler.isHidden())
        self.assertTrue(f.einstellungen.value("uebersicht", False, type=bool))

    def test_ein_neues_fenster_uebernimmt_die_wahl(self):
        """Die Schalter stehen nach einem Neustart, wie sie verlassen wurden."""
        from verteilerly.gui.hauptfenster import Hauptfenster

        f = self.fenster
        self.addCleanup(f.leistenansicht_zeigen, True)
        f.aktion_leistenansicht.setChecked(False)
        f.leistenansicht_zeigen(False)

        zweites = Hauptfenster()
        self.addCleanup(zweites.close)
        self.assertFalse(zweites.aktion_leistenansicht.isChecked())
        self.assertTrue(zweites.leistenansicht.isHidden())
        self.assertFalse(zweites.teiler.isHidden())

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
class TestDatumEinsetzen(unittest.TestCase):
    """Das heutige Datum in alle Datumsfelder auf einmal."""

    def setUp(self):
        from verteilerly.gui.dialoge import ProjektdatenFelder

        self.felder = ProjektdatenFelder({"firma": "Musterfirma"})
        self.addCleanup(self.felder.deleteLater)

    def test_nur_dieses_feld_und_sein_haken(self):
        import datetime

        from verteilerly.modell import DATUMSFELDER

        heute = self.felder.datum_einsetzen("stand_am")
        self.assertEqual(heute, datetime.date.today().strftime("%d.%m.%Y"))
        werte = self.felder.werte()
        self.assertEqual(werte["stand_am"], heute)
        self.assertTrue(self.felder.haken["stand_am"].isChecked())
        for name in DATUMSFELDER:
            if name != "stand_am":
                with self.subTest(feld=name):
                    self.assertNotIn(name, werte)
        self.assertEqual(werte["firma"], "Musterfirma")

    def test_nur_datumsfelder_tragen_einen_knopf(self):
        from verteilerly.modell import DATUMSFELDER

        self.assertEqual(sorted(self.felder.datumsknoepfe), sorted(DATUMSFELDER))
        for name, knopf in self.felder.datumsknoepfe.items():
            with self.subTest(feld=name):
                self.assertEqual(knopf.text(), "Heute")

    def test_in_den_vorgaben_gibt_es_sie_nicht(self):
        """Ein Datum in den Vorgaben wäre im nächsten Verteiler von vorgestern."""
        from verteilerly.gui.dialoge import ProjektdatenDialog
        from verteilerly.modell import Projekt, Verteiler

        projekt = Projekt(verteiler=Verteiler.aus_geometrie(1, 2, 10))
        fuer_vorgaben = ProjektdatenDialog(projekt, vorgaben=True)
        self.addCleanup(fuer_vorgaben.done, 0)
        self.assertEqual(fuer_vorgaben.projektdaten.datumsknoepfe, {})
        # Im Projektdatendialog dagegen schon.
        fuer_projekt = ProjektdatenDialog(projekt)
        self.addCleanup(fuer_projekt.done, 0)
        self.assertTrue(fuer_projekt.projektdaten.datumsknoepfe)

    def test_ein_gegebenes_datum_wird_genommen(self):
        """So lässt sich die Probe aufs Exempel ohne Blick auf die Uhr machen."""
        self.felder.datum_einsetzen("stand_am", "01.01.2000")
        self.assertEqual(self.felder.werte()["stand_am"], "01.01.2000")

    def test_die_deutsche_schreibweise_steht_auf_dem_blatt(self):
        """Das Datum gehört dem Dokument, nicht der Sprache der Oberfläche."""
        from verteilerly import sprachen

        vorher = sprachen.sprache()
        self.addCleanup(sprachen.sprache_setzen, vorher)
        sprachen.sprache_setzen("en")
        datum = self.felder.datum_einsetzen("erstellt_am")
        self.assertRegex(datum, r"^\d\d\.\d\d\.\d{4}$")


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

    def test_blattarten_der_eigenen_felder(self):
        """Die Wahl der Blätter kommt ins Projekt."""
        self.assertTrue(all(h.isChecked() for h in self.dialog.blattarten.values()))
        self.dialog.blattarten["deckblatt"].setChecked(False)
        self.dialog.uebernehmen()
        self.assertEqual(self.projekt.eigene_felder_auf, {"belegung", "leisten"})

    def test_beschriftungen_stehen_hinter_dem_schalter(self):
        """Die Vorgabe taugt für die meisten - erst der Schalter zeigt sie."""
        self.assertFalse(self.dialog.beschriftungen.schalter.isChecked())
        self.assertFalse(self.dialog.beschriftungen.kasten.isVisibleTo(self.dialog))
        self.dialog.beschriftungen.schalter.setChecked(True)
        self.assertTrue(self.dialog.beschriftungen.kasten.isVisibleTo(self.dialog))

    def test_der_schalter_steht_in_der_auswahlzeile(self):
        """Bei „Alle / Keine", nicht unten im Dialog."""
        schalter = self.dialog.beschriftungen.schalter
        self.assertTrue(self.dialog.projektdaten.isAncestorOf(schalter))
        zeile = self.dialog.projektdaten.schnell
        self.assertIn(schalter, [
            zeile.itemAt(i).widget() for i in range(zeile.count())
        ])

    def test_die_liste_bleibt_neben_den_feldern(self):
        self.assertFalse(
            self.dialog.projektdaten.isAncestorOf(self.dialog.beschriftungen.kasten)
        )

    def test_die_liste_braucht_keinen_rollbalken(self):
        """Der Rollbalken kommt erst, wenn der Dialog dafür zu flach ist."""
        from PySide6.QtWidgets import QScrollArea

        rollen = self.dialog.beschriftungen.findChild(QScrollArea)
        inhalt = rollen.widget()
        self.assertGreaterEqual(rollen.minimumHeight(), inhalt.sizeHint().height())
        self.assertGreaterEqual(rollen.minimumWidth(), inhalt.sizeHint().width())

    def test_eigenes_wort_kommt_ins_projekt(self):
        self.dialog.beschriftungen.felder["kunde"].setText("Auftraggeber")
        self.dialog.uebernehmen()
        self.assertEqual(self.projekt.beschriftung("kunde"), "Auftraggeber")
        # Nur die Abweichung wird gemerkt.
        self.assertEqual(self.projekt.beschriftungen, {"kunde": "Auftraggeber"})

    def test_zuruecksetzen_holt_die_vorgabe(self):
        self.dialog.beschriftungen.felder["kunde"].setText("Auftraggeber")
        self.dialog.beschriftungen.zuruecksetzen()
        self.dialog.uebernehmen()
        self.assertEqual(self.projekt.beschriftungen, {})
        self.assertEqual(self.projekt.beschriftung("kunde"), "Kunde")

    def test_ein_projekt_mit_eigenen_woertern_zeigt_sie_gleich(self):
        from verteilerly.gui.dialoge import ProjektdatenDialog

        self.projekt.beschriftungen = {"kunde": "Auftraggeber"}
        dialog = ProjektdatenDialog(self.projekt)
        self.assertTrue(dialog.beschriftungen.schalter.isChecked())
        self.assertEqual(dialog.beschriftungen.felder["kunde"].text(), "Auftraggeber")
        self.assertEqual(dialog.beschriftungen.felder["firma"].text(), "Firma")

    def test_der_dialog_zeigt_die_gespeicherte_wahl(self):
        from verteilerly.gui.dialoge import ProjektdatenDialog

        self.projekt.eigene_felder_auf = {"leisten"}
        dialog = ProjektdatenDialog(self.projekt)
        self.assertFalse(dialog.blattarten["deckblatt"].isChecked())
        self.assertTrue(dialog.blattarten["leisten"].isChecked())


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

    def test_je_datumsfeld_ein_heute_knopf(self):
        """Jedes Datum für sich: erstellt und geprüft sind selten derselbe Tag."""
        import datetime

        from verteilerly.modell import DATUMSFELDER

        d = self.dialog
        self.assertEqual(sorted(d.projektdaten.datumsknoepfe), sorted(DATUMSFELDER))

        d.projektdaten.datumsknoepfe["erstellt_am"].click()
        heute = datetime.date.today().strftime("%d.%m.%Y")
        briefkopf = d.projekt().briefkopf
        self.assertEqual(briefkopf.get("erstellt_am"), heute)
        # Ausgefüllt heißt angehakt - sonst stünde es auf keinem Blatt.
        self.assertNotIn("erstellt_am", d.projekt().ausgeblendet)
        # Die anderen Datumsfelder bleiben leer, bis man sie selbst drückt.
        for name in DATUMSFELDER:
            if name != "erstellt_am":
                with self.subTest(feld=name):
                    self.assertNotIn(name, briefkopf)

    def test_buchstaben_statt_zahlen_steht_im_dialog(self):
        """Der Haken gilt für beide Wege - Vorlage wie eigene Geometrie."""
        d = self.dialog
        self.assertFalse(d.buchstaben.isChecked())
        self.assertEqual(d.projekt().leisten_schreibweise, "zahlen")
        d.buchstaben.setChecked(True)
        self.assertEqual(d.leisten_schreibweise(), "buchstaben")
        self.assertEqual(d.projekt().leisten_schreibweise, "buchstaben")
        # Auch aus einer Vorlage: die sagt, wie viele Leisten es gibt,
        # nicht wie sie heißen.
        d.aus_vorlage.setChecked(True)
        self.assertTrue(d.buchstaben.isEnabled())
        self.assertEqual(d.projekt().leisten_schreibweise, "buchstaben")

    def test_die_vorgabe_steht_im_haken_schon_da(self):
        from verteilerly.gui.dialoge import NeuerVerteilerDialog

        dialog = NeuerVerteilerDialog(
            self.vorlagen, None, None, leisten="buchstaben"
        )
        self.addCleanup(dialog.done, 0)
        self.assertTrue(dialog.buchstaben.isChecked())

    def test_erweitert_ist_zunaechst_aus(self):
        """Der Regelfall ist der gleichmäßige Verteiler."""
        self.assertFalse(self.dialog.erweitert.isChecked())
        self.assertFalse(self.dialog.buchtentabelle.isVisibleTo(self.dialog))
        self.assertEqual(self.dialog.bauplan(), [(4, 10)])

    def test_erweitert_zeigt_je_bucht_eine_zeile(self):
        self.dialog.buchten.setValue(3)
        self.dialog.erweitert.setChecked(True)
        self.assertTrue(self.dialog.buchtentabelle.isVisibleTo(self.dialog))
        self.assertEqual(self.dialog.buchtentabelle.rowCount(), 3)
        # Die bisherigen Zahlen stehen darin, nichts geht verloren.
        self.assertEqual(self.dialog.bauplan(), [(4, 10)] * 3)

    def test_die_zeilen_folgen_der_zahl_der_buchten(self):
        self.dialog.erweitert.setChecked(True)
        self.dialog.buchten.setValue(5)
        self.assertEqual(self.dialog.buchtentabelle.rowCount(), 5)
        self.dialog.buchten.setValue(2)
        self.assertEqual(self.dialog.buchtentabelle.rowCount(), 2)

    def test_jede_bucht_ihre_eigene_groesse(self):
        self.dialog.buchten.setValue(3)
        self.dialog.erweitert.setChecked(True)
        self.dialog.buchtentabelle.cellWidget(1, 0).setValue(2)
        self.dialog.buchtentabelle.cellWidget(1, 1).setValue(20)
        self.dialog.buchtentabelle.cellWidget(2, 0).setValue(6)
        self.dialog.buchtentabelle.cellWidget(2, 1).setValue(8)
        self.assertEqual(self.dialog.bauplan(), [(4, 10), (2, 20), (6, 8)])

        verteiler = self.dialog.geometrie("Bunt")
        self.assertEqual([len(b.leisten) for b in verteiler.buchten], [4, 2, 6])
        self.assertEqual(verteiler.leiste(5).da_anzahl, 20)
        self.assertEqual(verteiler.da_gesamt, 128)

    def test_die_summenzeile_rechnet_mit(self):
        self.dialog.buchten.setValue(2)
        self.dialog.erweitert.setChecked(True)
        self.dialog.buchtentabelle.cellWidget(1, 1).setValue(20)
        self.assertIn("8 Leisten", self.dialog.summe.text())
        self.assertIn("120 DA", self.dialog.summe.text())

    def test_auch_ein_ungleicher_verteiler_wird_vorlage(self):
        """Dann trägt die Vorlage den Bauplan je Bucht."""
        from verteilerly.vorlagen import Vorlagen

        self.dialog.buchten.setValue(2)
        self.dialog.erweitert.setChecked(True)
        self.assertTrue(self.dialog.als_vorlage.isEnabled())
        self.dialog.buchtentabelle.cellWidget(1, 0).setValue(2)
        self.dialog.buchtentabelle.cellWidget(1, 1).setValue(20)

        from PySide6.QtWidgets import QMessageBox

        with mock.patch(
            "verteilerly.gui.dialoge.QInputDialog.getText",
            return_value=("Bunt", True),
        ), mock.patch.object(QMessageBox, "information", lambda *a: None):
            self.dialog.vorlage_ablegen()

        abgelegt = Vorlagen.laden(pathlib.Path(self.ordner.name)).holen("bunt")
        self.assertEqual(abgelegt.bauplan, ((4, 10), (2, 20)))
        self.assertEqual(abgelegt.da_gesamt, 80)
        self.assertIn("Bucht 2", abgelegt.beschreibung)
        # Und sie steht sofort zur Wahl.
        self.assertIn(
            "bunt",
            [
                self.dialog.vorlagenwahl.itemData(i)
                for i in range(self.dialog.vorlagenwahl.count())
            ],
        )

    def test_zurueckgeschaltet_gilt_wieder_die_gleichmaessige_angabe(self):
        self.dialog.buchten.setValue(2)
        self.dialog.erweitert.setChecked(True)
        self.dialog.buchtentabelle.cellWidget(0, 1).setValue(20)
        self.dialog.erweitert.setChecked(False)
        self.assertEqual(self.dialog.bauplan(), [(4, 10), (4, 10)])
        self.assertTrue(self.dialog.leisten.isVisibleTo(self.dialog))

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


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestSprachwahlImMenue(unittest.TestCase):
    """Die Sprache steht im Einstellungsmenü und gilt nach dem Neustart."""

    def setUp(self):
        from verteilerly import sprachen
        from verteilerly.gui.hauptfenster import Hauptfenster

        self.sprachen = sprachen
        self.addCleanup(sprachen.sprache_setzen, sprachen.VORGABE)
        self.fenster = Hauptfenster()
        self.addCleanup(self.fenster.close)
        from . import einstellung_bewahren

        einstellung_bewahren(self, self.fenster.einstellungen, "sprache")

    def test_jede_sprache_steht_im_menue(self):
        eintraege = [h.text() for h in self.fenster.sprachen_gruppe.actions()]
        self.assertEqual(eintraege, ["Deutsch", "English"])
        angehakt = [h for h in self.fenster.sprachen_gruppe.actions() if h.isChecked()]
        self.assertEqual([h.data() for h in angehakt], [self.sprachen.sprache()])

    def test_die_wahl_landet_in_der_conf(self):
        from PySide6.QtWidgets import QMessageBox

        with mock.patch.object(QMessageBox, "information") as gesagt:
            self.fenster.sprache_waehlen("en")
        self.assertEqual(self.fenster.einstellungen.value("sprache"), "en")
        self.assertTrue(gesagt.called, "kein Hinweis auf den Neustart")
        self.assertIn("Neustart", self.fenster.statusBar().currentMessage())

    def test_die_laufende_oberflaeche_bleibt_wie_sie_ist(self):
        """Umgehängt wird nicht: die Menüs werden einmal beschriftet."""
        from PySide6.QtWidgets import QMessageBox

        vorher = self.fenster.aktion_suchen.text()
        with mock.patch.object(QMessageBox, "information"):
            self.fenster.sprache_waehlen("en")
        self.assertEqual(self.fenster.aktion_suchen.text(), vorher)

    def test_dieselbe_sprache_noch_einmal_gewaehlt_tut_nichts(self):
        from PySide6.QtWidgets import QMessageBox

        with mock.patch.object(QMessageBox, "information") as gesagt:
            self.fenster.sprache_waehlen(self.sprachen.sprache())
        self.assertFalse(gesagt.called)

    def test_auf_englisch_sind_die_menues_englisch(self):
        """Gebaut wird mit der Sprache, die beim Start eingestellt war."""
        from verteilerly.gui.hauptfenster import Hauptfenster

        self.sprachen.sprache_setzen("en")
        fenster = Hauptfenster()
        self.addCleanup(fenster.close)
        self.assertEqual(fenster.aktion_suchen.text(), "&Search…")
        self.assertEqual(fenster.aktion_projektdaten.text(), "&Project data…")
        self.assertEqual(fenster.statusBar().currentMessage(), "Ready")

    def test_auf_englisch_sind_auch_die_spaltenkoepfe_englisch(self):
        from verteilerly.gui.leistenansicht import LeistenAnsicht, SPALTE_BEZEICHNUNG

        self.sprachen.sprache_setzen("en")
        ansicht = LeistenAnsicht()
        self.addCleanup(ansicht.close)
        ansicht.verteiler_setzen(Verteiler.aus_geometrie(1, 2, 10))
        self.assertEqual(
            ansicht.modell.headerData(
                SPALTE_BEZEICHNUNG, Qt.Orientation.Horizontal,
                Qt.ItemDataRole.DisplayRole,
            ),
            "Designation",
        )

    def test_qt_bleibt_bei_seiner_eigenen_sprache(self):
        """Deutsche Knöpfe mitten in einem englischen Programm wären falsch."""
        from verteilerly.gui import sprache as qtsprache

        self.sprachen.sprache_setzen("en")
        self.assertFalse(qtsprache.deutsch_einrichten(ANWENDUNG))


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestSuchDialog(unittest.TestCase):
    """Die Fundstellen mit Ort, Feld und Inhalt."""

    def setUp(self):
        from verteilerly.gui.dialoge import SuchDialog
        from verteilerly.modell import Zellenteilung

        self.verteiler = Verteiler.aus_geometrie(2, 3, 10, name="Keller")
        self.projekt = Projekt(
            verteiler=self.verteiler, briefkopf={"kunde": "Firma Meier"}
        )
        ader = self.verteiler.ader(Aderadresse(2, 4, "b"))
        ader.bezeichnung = "Amt 42"
        ader.teilung_setzen("bezeichnung", Zellenteilung(35, "Nst. 17"))
        self.verteiler.ader(Aderadresse(1, 2, "a")).bemerkung = "Amtsleitung"
        self.dialog = SuchDialog(self.projekt)
        self.addCleanup(self.dialog.close)

    def _suchen(self, wort):
        self.dialog.suchfeld.setText(wort)
        ANWENDUNG.processEvents()
        return self.dialog.treffer

    def test_die_liste_zeigt_ort_feld_und_inhalt(self):
        self._suchen("Amt")
        self.assertEqual(self.dialog.liste.rowCount(), 2)
        zeile = [self.dialog.liste.item(0, s).text() for s in range(3)]
        self.assertIn("Leiste 1", zeile[0])
        self.assertEqual(zeile[1], "Bemerkung")
        self.assertEqual(zeile[2], "Amtsleitung")

    def test_der_zaehler_nennt_die_zahl(self):
        self._suchen("Amt")
        self.assertIn("2 Fundstellen", self.dialog.zaehler.text())

    def test_ohne_treffer_sagt_er_das(self):
        self._suchen("Zwirbelwutz")
        self.assertEqual(self.dialog.liste.rowCount(), 0)
        self.assertIn("kommt im Verteiler nicht vor", self.dialog.zaehler.text())
        self.assertFalse(self.dialog.springen_knopf.isEnabled())

    def test_ein_zeichen_sucht_noch_nicht(self):
        self._suchen("A")
        self.assertEqual(self.dialog.treffer, [])
        self.assertIn("zwei Zeichen", self.dialog.zaehler.text())

    def test_die_erste_fundstelle_ist_gleich_gewaehlt(self):
        treffer = self._suchen("Amt")
        self.assertEqual(self.dialog.auswahl(), treffer[0])
        self.assertTrue(self.dialog.springen_knopf.isEnabled())

    def test_springen_gibt_die_gewaehlte_zurueck(self):
        treffer = self._suchen("Amt")
        self.dialog.liste.selectRow(1)
        self.dialog.springen()
        self.assertEqual(self.dialog.gewaehlt, treffer[1])
        self.assertEqual(self.dialog.result(), self.dialog.DialogCode.Accepted)

    def test_ein_mitgegebenes_wort_steht_schon_da(self):
        from verteilerly.gui.dialoge import SuchDialog

        dialog = SuchDialog(self.projekt, None, "Amt")
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.suchfeld.text(), "Amt")
        self.assertEqual(len(dialog.treffer), 2)


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestSucheImHauptfenster(unittest.TestCase):
    """Von der Fundstelle zur Zelle."""

    def setUp(self):
        from verteilerly.gui.hauptfenster import Hauptfenster
        from verteilerly.modell import Zellenteilung

        self.fenster = Hauptfenster()
        self.addCleanup(self.fenster.close)
        verteiler = Verteiler.aus_geometrie(2, 3, 10, name="Keller")
        self.projekt = Projekt(
            verteiler=verteiler, briefkopf={"kunde": "Firma Meier"}
        )
        ader = verteiler.ader(Aderadresse(2, 4, "b"))
        ader.bezeichnung = "Amt 42"
        ader.teilung_setzen("bezeichnung", Zellenteilung(35, "Nst. 17"))
        verteiler.kabel_anlegen("Amtskabel 1", 3, 1, 4)
        self.fenster._projekt_setzen(self.projekt, None)

    def _suchen_mit(self, wort, zeile=0):
        """Ruft Bearbeiten ▸ Suchen und wählt eine Fundstelle."""
        from verteilerly.gui.dialoge import SuchDialog

        def waehlen(dialog):
            dialog.suchfeld.setText(wort)
            dialog.liste.selectRow(zeile)
            dialog.springen()
            return SuchDialog.DialogCode.Accepted

        with mock.patch.object(SuchDialog, "exec", waehlen):
            self.fenster.suchen()

    def test_der_menueeintrag_braucht_einen_verteiler(self):
        self.assertTrue(self.fenster.aktion_suchen.isEnabled())
        self.assertEqual(self.fenster.aktion_suchen.shortcut().toString(), "Ctrl+F")
        self.fenster._projekt_setzen(None, None)
        self.assertFalse(self.fenster.aktion_suchen.isEnabled())

    def test_die_marke_steht_danach_auf_der_zelle(self):
        self._suchen_mit("Nst")
        ansicht = self.fenster.leistenansicht
        self.assertEqual(ansicht.modell.leiste_nr, 2)
        marke = ansicht.tabelle.currentIndex()
        self.assertEqual(marke.row(), (4 - 1) * 2 + 1, "nicht auf Stift 4b")
        self.assertEqual(marke.column(), SPALTE_BEZEICHNUNG)

    def test_die_statuszeile_sagt_was_gefunden_wurde(self):
        self._suchen_mit("Nst")
        self.assertIn("Stift 4b", self.fenster.statusBar().currentMessage())

    def test_ein_kabel_fuehrt_auf_seine_erste_doppelader(self):
        self._suchen_mit("Amtskabel")
        ansicht = self.fenster.leistenansicht
        self.assertEqual(ansicht.modell.leiste_nr, 3)
        self.assertEqual(ansicht.tabelle.currentIndex().row(), 0)

    def test_eine_fundstelle_in_den_projektdaten_oeffnet_den_dialog(self):
        from verteilerly.gui.dialoge import ProjektdatenDialog

        with mock.patch.object(
            ProjektdatenDialog, "exec",
            return_value=ProjektdatenDialog.DialogCode.Rejected,
        ) as gezeigt:
            self._suchen_mit("Meier")
        self.assertTrue(gezeigt.called, "die Projektdaten blieben zu")

    def test_das_wort_steht_beim_naechsten_mal_wieder_da(self):
        self._suchen_mit("Amt")
        self.assertEqual(self.fenster.zuletzt_gesucht, "Amt")

    def test_ein_abgebrochener_dialog_springt_nirgends_hin(self):
        from verteilerly.gui.dialoge import SuchDialog

        vorher = self.fenster.leistenansicht.modell.leiste_nr
        with mock.patch.object(
            SuchDialog, "exec", return_value=SuchDialog.DialogCode.Rejected
        ):
            self.fenster.suchen()
        self.assertEqual(self.fenster.leistenansicht.modell.leiste_nr, vorher)


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestDialogeFreiBeweglich(unittest.TestCase):
    """Kein Dialog klebt am Hauptfenster fest.

    Eine Fensterverwaltung gibt es offscreen nicht - geprueft wird darum,
    wie sich der Dialog anmeldet. Dass Mutter ihn dann freilaesst, ist am
    Bildschirm ausprobiert und steht in ``freie_fensterart``.
    """

    def test_die_fensterart_wird_werkzeugfenster(self):
        from PySide6.QtCore import Qt

        from verteilerly.gui.passform import freie_fensterart

        art = (Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint
               | Qt.WindowType.WindowCloseButtonHint)
        neu = freie_fensterart(art)
        self.assertEqual(neu & Qt.WindowType.WindowType_Mask, Qt.WindowType.Tool)
        # Titelleiste und Schließknopf bleiben, wie sie waren.
        self.assertTrue(neu & Qt.WindowType.WindowTitleHint)
        self.assertTrue(neu & Qt.WindowType.WindowCloseButtonHint)

    def test_ohne_x11_bleibt_alles_wie_es_ist(self):
        """Offscreen, unter Windows und Wayland gibt es nichts anzuheften."""
        from verteilerly.gui import passform

        self.assertNotIn(ANWENDUNG.platformName(), passform.FREISTELLEN_AUF)
        self.assertIsNone(passform.dialoge_freistellen(ANWENDUNG))

    def _unter_x11(self):
        from verteilerly.gui import passform

        with mock.patch.object(
            passform.QGuiApplication, "platformName", return_value="xcb"
        ):
            filter_ = passform.dialoge_freistellen(ANWENDUNG)
        self.assertIsNotNone(filter_)
        self.addCleanup(ANWENDUNG.removeEventFilter, filter_)
        return filter_

    def test_jeder_dialog_wird_freigestellt_und_bleibt_modal(self):
        """Auch Qts eigene: QMessageBox und QInputDialog bauen ihr Fenster selbst."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox

        from verteilerly.gui.dialoge import PruefberichtDialog
        from verteilerly.pruefung import Bericht

        self._unter_x11()
        for dialog in (
            QDialog(), QMessageBox(), QInputDialog(),
            PruefberichtDialog(Bericht("blattvorlage", pathlib.Path("x.yaml"))),
        ):
            with self.subTest(dialog=type(dialog).__name__):
                dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
                dialog.show()
                self.addCleanup(dialog.close)
                art = dialog.windowHandle().flags() & Qt.WindowType.WindowType_Mask
                self.assertEqual(art, Qt.WindowType.Tool)
                self.assertNotEqual(
                    dialog.windowModality(), Qt.WindowModality.NonModal
                )
                dialog.close()

    def test_ein_hauptfenster_bleibt_ein_hauptfenster(self):
        """Nur Dialoge - kein anderes Fenster wird umgemeldet."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QMainWindow

        self._unter_x11()
        fenster = QMainWindow()
        fenster.show()
        self.addCleanup(fenster.close)
        self.assertEqual(
            fenster.windowHandle().flags() & Qt.WindowType.WindowType_Mask,
            Qt.WindowType.Window,
        )

    def test_das_programm_stellt_die_dialoge_beim_start_frei(self):
        """Der Filter muss dort sitzen, wo die Anwendung entsteht."""
        quelle = (pathlib.Path(__file__).resolve().parent.parent
                  / "verteilerly" / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("dialoge_freistellen(anwendung)", quelle)


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestPassform(unittest.TestCase):
    """Kein Dialog wird größer als der Bildschirm."""

    def setUp(self):
        from verteilerly.blattvorlagen import Blattvorlagen
        from verteilerly.farbcodes import Kabeltypen
        from verteilerly.gui import dialoge

        self.dialoge = dialoge
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        daten = pathlib.Path(__file__).resolve().parent.parent / "daten"
        projekt = Projekt(verteiler=Verteiler.aus_geometrie(2, 8, 10))
        vorlagen = Vorlagen([Vorlage("klein", "Klein", 1, 4, 10, standard=True)])
        self.alle = {
            "Neuer Verteiler": dialoge.NeuerVerteilerDialog(
                vorlagen, None, pathlib.Path(self.ordner.name)
            ),
            "Projektdaten": dialoge.ProjektdatenDialog(projekt),
            "Vorgaben": dialoge.ProjektdatenDialog(projekt, vorgaben=True),
            "Kabel": dialoge.KabelDialog(
                projekt.verteiler,
                Kabeltypen.laden(daten / "kabeltypen"),
                projekt.verteiler.alle_leisten[0],
                1,
            ),
            "Verteilervorlagen": dialoge.VerteilervorlagenDialog(vorlagen, None),
            "Blattvorlagen": dialoge.BlattvorlagenDialog(
                Blattvorlagen.laden(daten / "blattvorlagen")
            ),
            "Dokumentation": dialoge.DokumentationDialog(),
        }
        for dialog in self.alle.values():
            self.addCleanup(dialog.deleteLater)

    def _zeigen(self, dialog):
        dialog.show()
        ANWENDUNG.processEvents()
        self.addCleanup(dialog.hide)
        return dialog

    def test_keiner_ragt_ueber_den_bildschirm_hinaus(self):
        from verteilerly.gui import passform

        for name, dialog in self.alle.items():
            with self.subTest(dialog=name):
                self._zeigen(dialog)
                mass = passform.hoechstmass(dialog)
                self.assertLessEqual(dialog.width(), mass.width())
                self.assertLessEqual(dialog.height(), mass.height())

    def test_die_vorgaben_rollen_statt_ueberzulaufen(self):
        """Die Felder passen nicht auf 800 Bildpunkte Höhe — also rollen sie."""
        dialog = self._zeigen(self.alle["Vorgaben"])
        self.assertIsNotNone(dialog.rollbereich)
        self.assertTrue(dialog.rollbereich.verticalScrollBar().isVisible())

    def test_mit_platz_ist_kein_balken_zu_sehen(self):
        dialog = self._zeigen(self.alle["Vorgaben"])
        dialog.resize(dialog.width(), dialog.rollbereich.widget().sizeHint().height() * 2)
        ANWENDUNG.processEvents()
        self.assertFalse(dialog.rollbereich.verticalScrollBar().isVisible())

    def test_die_knopfleiste_rollt_nicht_weg(self):
        """Übernehmen und Abbrechen stehen außerhalb des Rollbereichs."""
        from PySide6.QtWidgets import QDialogButtonBox

        for name in ("Vorgaben", "Neuer Verteiler"):
            with self.subTest(dialog=name):
                dialog = self._zeigen(self.alle[name])
                leiste = dialog.findChild(QDialogButtonBox)
                self.assertIsNotNone(leiste)
                self.assertFalse(
                    dialog.rollbereich.isAncestorOf(leiste),
                    "die Knopfleiste steckt im Rollbereich",
                )
                self.assertLessEqual(
                    leiste.mapTo(dialog, leiste.rect().bottomLeft()).y(),
                    dialog.height(),
                )

    def test_ein_zu_grosser_dialog_wird_gestutzt(self):
        from verteilerly.gui import passform

        dialog = self._zeigen(self.alle["Vorgaben"])
        flaeche = passform.freie_flaeche(dialog)
        dialog.resize(flaeche.width() + 400, flaeche.height() + 400)
        self.assertTrue(passform.einpassen(dialog))
        self.assertLessEqual(dialog.width(), flaeche.width())
        self.assertLessEqual(dialog.height(), flaeche.height())

    def test_was_daneben_steht_wird_hereingeschoben(self):
        from verteilerly.gui import passform

        dialog = self._zeigen(self.alle["Kabel"])
        flaeche = passform.freie_flaeche(dialog)
        dialog.move(flaeche.right() - 20, flaeche.bottom() - 20)
        passform.einpassen(dialog)
        self.assertTrue(
            flaeche.contains(dialog.frameGeometry()),
            f"{dialog.frameGeometry()} liegt nicht in {flaeche}",
        )

    def test_ein_passender_dialog_bleibt_wie_er_ist(self):
        from verteilerly.gui import passform

        dialog = self._zeigen(self.alle["Kabel"])
        vorher = dialog.geometry()
        self.assertFalse(passform.einpassen(dialog))
        self.assertEqual(dialog.geometry(), vorher)


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestToolsMenue(unittest.TestCase):
    """Vorlagen prüfen, bevor sie ins Programm kommen."""

    def setUp(self):
        from verteilerly.gui.hauptfenster import Hauptfenster

        self.fenster = Hauptfenster()
        self.addCleanup(self.fenster.close)
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.ziel = pathlib.Path(self.ordner.name)

    def _menue(self):
        return next(
            a.menu() for a in self.fenster.menuBar().actions()
            if "Tools" in a.text()
        )

    def test_das_menue_folgt_auf_die_ansicht(self):
        """Tools nach Ansicht; dahinter die Erweiterungen, zuletzt die Hilfe."""
        namen = [
            a.text().replace("&", "") for a in self.fenster.menuBar().actions()
        ]
        self.assertEqual(
            namen[-4:], ["Ansicht", "Tools", "Erweiterungen", "Hilfe"], namen
        )

    def test_je_vorlagenart_ein_eintrag(self):
        from verteilerly.pruefung import ARTEN

        # Vor dem Trenner stehen die Prüfungen, dahinter das Anmelden
        # bei der Dateiverwaltung.
        eintraege = []
        for handlung in self._menue().actions():
            if handlung.isSeparator():
                break
            eintraege.append(handlung.text())
        self.assertEqual(len(eintraege), len(ARTEN))
        for eintrag, (_art, wie) in zip(eintraege, ARTEN):
            with self.subTest(eintrag=eintrag):
                self.assertTrue(eintrag.startswith(wie), eintrag)
                self.assertIn("prüfen", eintrag)

    def test_dahinter_steht_die_auskunft_zur_dateiverknuepfung(self):
        texte = [
            a.text().replace("&", "") for a in self._menue().actions() if a.text()
        ]
        self.assertEqual(texte[-1], "Projektdateien verknüpfen…")

    def _pruefen(self, stelle: int, datei: pathlib.Path):
        """Klickt einen Eintrag und fängt Dateidialog und Bericht ab."""
        from verteilerly.gui import hauptfenster

        gezeigt = {}
        with mock.patch.object(hauptfenster.QFileDialog, "getOpenFileName",
                               return_value=(str(datei), "")), \
             mock.patch.object(
                 hauptfenster.PruefberichtDialog, "exec",
                 lambda dialog: gezeigt.update(
                     text=dialog.text.toPlainText(), bericht=dialog.bericht
                 )):
            self._menue().actions()[stelle].trigger()
        return gezeigt

    def test_eine_gute_blattvorlage_wird_vorgelesen(self):
        datei = self.ziel / "eng.yaml"
        datei.write_text(
            "id: eng\nname: Eng\nspalten: [stift, rangierung]\n", encoding="utf-8"
        )
        gezeigt = self._pruefen(1, datei)
        self.assertTrue(gezeigt["bericht"].gut)
        self.assertIn("stift, rangierung", gezeigt["text"])
        self.assertIn("Ordnung", self.fenster.statusBar().currentMessage())

    def test_ein_fehler_steht_im_bericht_und_in_der_statuszeile(self):
        datei = self.ziel / "kaputt.yaml"
        datei.write_text("id: x\nname: X\nbuchten_je_blatt: 0\n", encoding="utf-8")
        gezeigt = self._pruefen(1, datei)
        self.assertFalse(gezeigt["bericht"].gut)
        self.assertIn("buchten_je_blatt", gezeigt["text"])
        self.assertIn("nicht lesen", self.fenster.statusBar().currentMessage())

    def test_ein_abgebrochener_dateidialog_tut_nichts(self):
        from verteilerly.gui import hauptfenster

        gezeigt = []
        with mock.patch.object(hauptfenster.QFileDialog, "getOpenFileName",
                               return_value=("", "")), \
             mock.patch.object(hauptfenster.PruefberichtDialog, "exec",
                               lambda dialog: gezeigt.append(dialog)):
            self._menue().actions()[0].trigger()
        self.assertEqual(gezeigt, [])

    def test_der_dateidialog_geht_beim_passenden_ordner_auf(self):
        ordner = self.fenster._pruefordner("blattvorlage")
        self.assertTrue(ordner.is_dir())
        self.assertEqual(ordner.name, "blattvorlagen")


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestVerteilervorlagenDialog(unittest.TestCase):
    """Verteilervorlagen umbenennen, löschen, zurückholen."""

    def setUp(self):
        from verteilerly.gui.dialoge import VerteilervorlagenDialog
        from verteilerly.vorlagen import vorlage_speichern

        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.ziel = pathlib.Path(self.ordner.name)
        self.vorlagen = Vorlagen([
            Vorlage("klein", "Klein", 1, 4, 10, standard=True),
            Vorlage("gross", "Groß", 2, 8, 10),
        ])
        for vorlage in self.vorlagen.alle:
            vorlage_speichern(vorlage, self.ziel)
        self.dialog = VerteilervorlagenDialog(self.vorlagen, self.ziel)

    def _waehlen(self, kennung):
        stelle = next(
            i for i in range(self.dialog.liste.count())
            if self.dialog.liste.item(i).data(Qt.ItemDataRole.UserRole) == kennung
        )
        self.dialog.liste.setCurrentRow(stelle)

    def test_die_liste_zeigt_alle_vorlagen(self):
        self.assertEqual(self.dialog.liste.count(), 2)
        self.assertIn("Bucht", self.dialog.hinweis.text())

    def test_umbenennen_aendert_namen_und_datei(self):
        from verteilerly.gui import dialoge

        self._waehlen("gross")
        with mock.patch.object(
            dialoge.QInputDialog, "getText", return_value=("Keller", True)
        ):
            self.dialog.umbenennen()
        self.assertEqual(self.dialog.umbenannt, {"gross": "Keller"})
        self.assertEqual(self.vorlagen.holen("gross").name, "Keller")
        self.assertIn("Keller", Vorlagen.laden(self.ziel).holen("gross").name)

    def test_abgebrochenes_umbenennen_aendert_nichts(self):
        from verteilerly.gui import dialoge

        self._waehlen("gross")
        with mock.patch.object(
            dialoge.QInputDialog, "getText", return_value=("Keller", False)
        ):
            self.dialog.umbenennen()
        self.assertEqual(self.dialog.umbenannt, {})
        self.assertEqual(self.vorlagen.holen("gross").name, "Groß")

    def test_loeschen_fragt_nach_und_nimmt_sie_aus_der_liste(self):
        from verteilerly.gui import dialoge

        self._waehlen("klein")
        with mock.patch.object(
            dialoge, "frage", return_value=QMessageBox.StandardButton.Yes
        ):
            self.dialog.loeschen()
        self.assertEqual(self.dialog.geloescht, ["klein"])
        self.assertEqual(self.dialog.liste.count(), 1)
        self.assertFalse((self.ziel / "klein.yaml").exists())

    def test_ein_nein_laesst_die_vorlage_stehen(self):
        from verteilerly.gui import dialoge

        self._waehlen("klein")
        with mock.patch.object(
            dialoge, "frage", return_value=QMessageBox.StandardButton.No
        ):
            self.dialog.loeschen()
        self.assertEqual(self.dialog.geloescht, [])
        self.assertTrue((self.ziel / "klein.yaml").exists())

    def test_wiederherstellen_meldet_sich_und_schliesst(self):
        from verteilerly.gui import dialoge

        with mock.patch.object(
            dialoge, "frage", return_value=QMessageBox.StandardButton.Yes
        ):
            self.dialog.wiederherstellen()
        self.assertTrue(self.dialog.wiederhergestellt)

    def test_ohne_ordner_bleibt_nur_das_ansehen(self):
        from verteilerly.gui.dialoge import VerteilervorlagenDialog

        dialog = VerteilervorlagenDialog(self.vorlagen, None)
        self.assertFalse(dialog.umbenennen_knopf.isEnabled())
        self.assertFalse(dialog.loeschen_knopf.isEnabled())


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestRueckgaengig(unittest.TestCase):
    """Die letzte Änderung am Verteiler zurücknehmen und wieder holen."""

    def setUp(self):
        from verteilerly.gui.hauptfenster import Hauptfenster

        self.fenster = Hauptfenster()
        self.addCleanup(self._schliessen)
        self.verteiler = Verteiler.aus_geometrie(1, 3, 10, name="Probe")
        self.kabel = self.verteiler.kabel_anlegen("Leitung", 1, 1, 4)
        self.fenster._projekt_setzen(Projekt(verteiler=self.verteiler), None)

    def _schliessen(self):
        self.fenster.veraendert = False
        self.fenster.close()

    def _leiste_des_kabels(self):
        kabel = self.fenster.projekt.verteiler.kabel[0]
        return kabel.abschnitte[0].leiste

    def _aendern(self):
        """Eine Änderung, wie sie die Bedienung macht."""
        self.fenster._kabel_umlegen(self.fenster.projekt.verteiler.kabel[0], 2, 5, False)

    def test_am_anfang_gibt_es_nichts_zurueckzunehmen(self):
        f = self.fenster
        self.assertFalse(f.aktion_rueckgaengig.isEnabled())
        self.assertFalse(f.aktion_wiederherstellen.isEnabled())

    def test_eine_aenderung_laesst_sich_zuruecknehmen(self):
        f = self.fenster
        self._aendern()
        self.assertEqual(self._leiste_des_kabels(), 2)
        self.assertTrue(f.aktion_rueckgaengig.isEnabled())
        f.rueckgaengig()
        self.assertEqual(self._leiste_des_kabels(), 1)
        self.assertFalse(f.aktion_rueckgaengig.isEnabled())
        self.assertTrue(f.aktion_wiederherstellen.isEnabled())

    def test_zurueckgenommenes_laesst_sich_wieder_holen(self):
        f = self.fenster
        self._aendern()
        f.rueckgaengig()
        f.wiederherstellen()
        self.assertEqual(self._leiste_des_kabels(), 2)
        self.assertTrue(f.aktion_rueckgaengig.isEnabled())
        self.assertFalse(f.aktion_wiederherstellen.isEnabled())

    def test_nach_einer_neuen_aenderung_ist_der_andere_weg_gegangen(self):
        """Wer zurücknimmt und dann etwas anderes tut, holt nichts mehr."""
        f = self.fenster
        self._aendern()
        f.rueckgaengig()
        from . import einstellung_bewahren

        einstellung_bewahren(self, f.einstellungen, "leisten_schreibweise")
        f.leistenweise_waehlen("buchstaben")
        self.assertFalse(f.aktion_wiederherstellen.isEnabled())

    def test_die_leiste_bleibt_stehen(self):
        f = self.fenster
        f.leistenansicht.leiste_zeigen(3)
        self._aendern()
        f.rueckgaengig()
        self.assertEqual(f.leistenansicht.modell.leiste_nr, 3)

    def test_mehr_als_die_gemerkten_schritte_fallen_hinten_weg(self):
        from verteilerly.gui import hauptfenster as hf

        f = self.fenster
        for nr in range(hf.RUECKGAENGIG_SCHRITTE + 5):
            f.projekt.verteiler.kabel[0].beschriftung = f"Leitung {nr}"
            f._belegung_geaendert()
        self.assertEqual(len(f._rueckgaengig), hf.RUECKGAENGIG_SCHRITTE)

    def test_ein_anderes_projekt_faengt_von_vorn_an(self):
        f = self.fenster
        self._aendern()
        anderer = Verteiler.aus_geometrie(1, 2, 10, name="Zweiter")
        f._projekt_setzen(Projekt(verteiler=anderer), None)
        self.assertFalse(f.aktion_rueckgaengig.isEnabled())
        self.assertFalse(f.aktion_wiederherstellen.isEnabled())

    def test_die_knoepfe_der_leistenansicht_folgen_den_handlungen(self):
        """Auf ihnen steht der Pfeil, im Hinweis der Satz samt Kürzel."""
        f = self.fenster
        zurueck = f.leistenansicht.rueckgaengig_knopf
        self.assertEqual(zurueck.text(), "↶")
        self.assertIn("Rückgängig", zurueck.toolTip())
        self.assertFalse(zurueck.isEnabled())
        self._aendern()
        self.assertTrue(zurueck.isEnabled())
        zurueck.click()
        self.assertEqual(self._leiste_des_kabels(), 1)
        self.assertTrue(f.leistenansicht.wiederherstellen_knopf.isEnabled())


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestUnlesbareConf(unittest.TestCase):
    """Eine Conf, die sich nicht lesen lässt, wird nicht überschrieben."""

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.datei = pathlib.Path(self.ordner.name) / "Verteilerly.conf"

    def _grund(self):
        from PySide6.QtCore import QSettings
        from verteilerly.gui.hauptfenster import Hauptfenster

        einstellungen = QSettings(str(self.datei), QSettings.Format.IniFormat)
        return Hauptfenster._conf_grund(einstellungen, self.datei)

    def test_eine_fehlende_datei_ist_kein_fehler(self):
        """So fängt jeder erste Start an."""
        self.assertEqual(self._grund(), "")

    def test_eine_gelesene_datei_ist_kein_fehler(self):
        self.datei.write_text("[General]\nthema=dunkel\n", encoding="utf-8")
        self.assertEqual(self._grund(), "")

    def test_eine_datei_ohne_werte_faellt_auf(self):
        """Bytes, aber kein Wert - dann hat Qt sie nicht verstanden."""
        self.datei.write_bytes(b"\x00\x01\x02 kein Ini\n[[[\nthema\n")
        self.assertTrue(self._grund())

    def test_das_fenster_schreibt_nicht_in_eine_unlesbare_datei(self):
        from unittest import mock

        from verteilerly import pfade
        from verteilerly.gui import hauptfenster as hf

        self.datei.write_bytes(b"\x00\x01\x02 kein Ini\n[[[\nthema\n")
        vorher = self.datei.read_bytes()
        gezeigt = []
        with mock.patch.object(pfade, "einstellungsdatei", lambda: self.datei), \
             mock.patch.object(hf.QMessageBox, "warning",
                               lambda *a, **k: gezeigt.append(a)):
            fenster = hf.Hauptfenster()
            self.addCleanup(fenster.close)
            self.assertTrue(fenster.einstellungen_grund)
            self.assertNotEqual(
                pathlib.Path(fenster.einstellungen.fileName()), self.datei
            )
            fenster.thema_anwenden("dunkel")
            fenster.einstellungen.sync()
        self.assertEqual(self.datei.read_bytes(), vorher)
        self.assertTrue(gezeigt, "der Anwender erfährt davon")

    def test_der_startvermerk_sagt_woher_der_lauf_seine_werte_nahm(self):
        from verteilerly.erweiterungen.protokoll import Protokoll

        zeilen = Protokoll()._startzeilen(None)
        self.assertTrue(zeilen[0].startswith("Verteilerly "))
        beisammen = "\n".join(zeilen)
        for stueck in ("Programm:", "Einstellungen:", "Aufruf:", "Arbeitsverzeichnis"):
            self.assertIn(stueck, beisammen)
