"""Tests zur Erweiterung *CSV2Excel*.

Gestartet wird nichts: ``Csv2Excel.starten`` ist ausgewechselt, und die
CSV landet im Temp-Ordner des Tests statt in dem des Rechners. Die
Rueckfragen kommen aus ``QMessageBox`` und sind ersetzt - eine
unbeantwortete haenge die Reihe auf.
"""

from __future__ import annotations

# Erst das Paket: es legt Einstellungs- und Arbeitsordner der
# Testreihe um, bevor etwas aus verteilerly Pfade liest.
from . import TESTHEIM  # noqa: F401

import os
import pathlib
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

ANWENDUNG = QApplication.instance() or QApplication([])

from verteilerly import erweiterungen  # noqa: E402
from verteilerly.erweiterungen.csv2excel import (  # noqa: E402
    SCHLUESSEL_EXPORT,
    SCHLUESSEL_PROGRAMM,
    SCHLUESSEL_SOFORT,
    Csv2Excel,
    uebergabe,
)
from verteilerly.modell import Projekt, Verteiler  # noqa: E402

from . import bauteil_zurueckgeben, einstellung_bewahren  # noqa: E402


def _projekt(name: str = "Hauptverteiler") -> Projekt:
    return Projekt(verteiler=Verteiler.aus_buchten([(2, 10)], name, "1.1"))


class TestUebergabe(unittest.TestCase):
    """Name, Aufruf und Pruefung des Pfads - ohne Qt."""

    def test_der_name_folgt_der_projektdatei(self):
        pfad = pathlib.Path("/irgendwo/Halle Ost.vtly")
        self.assertEqual(uebergabe.dateiname(_projekt(), pfad), "Halle Ost.csv")
        self.assertEqual(
            uebergabe.dateiname(_projekt(), pfad, uebergabe.VTLY), "Halle Ost.vtly"
        )
        # Eine alte .vtly.json gibt ihren Stamm her, nicht ihre Endung.
        alt = pathlib.Path("/irgendwo/Halle Ost.vtly.json")
        self.assertEqual(
            uebergabe.dateiname(_projekt(), alt, uebergabe.VTLY), "Halle Ost.vtly"
        )

    def test_ohne_datei_heisst_sie_wie_der_verteiler(self):
        self.assertEqual(uebergabe.dateiname(_projekt("HVt/UVt"), None), "HVt UVt.csv")

    def test_ohne_jeden_namen_bleibt_verteiler(self):
        self.assertEqual(uebergabe.dateiname(_projekt(""), None), "verteiler.csv")

    def test_das_format_aus_der_conf(self):
        self.assertEqual(uebergabe.format_lesen(None), uebergabe.CSV)
        self.assertEqual(uebergabe.format_lesen("VTLY"), uebergabe.VTLY)
        self.assertEqual(uebergabe.format_lesen("fragen"), uebergabe.FRAGEN)
        # Was eine spaetere Fassung schreibt, faellt auf die CSV zurueck.
        self.assertEqual(uebergabe.format_lesen("xlsx"), uebergabe.CSV)

    def test_der_aufruf(self):
        csv = pathlib.Path("/tmp/a.csv")
        self.assertEqual(uebergabe.argumente(csv), [str(csv)])
        self.assertEqual(
            uebergabe.argumente(csv, "D:/Excel", True),
            [str(csv), "--export", "D:/Excel", "--start"],
        )

    def test_der_pfad_wird_geprueft(self):
        with tempfile.TemporaryDirectory() as ordner:
            datei = pathlib.Path(ordner) / uebergabe.PROGRAMMNAME
            self.assertIn("noch nicht eingestellt", uebergabe.programm_grund(""))
            self.assertIn("nicht mehr", uebergabe.programm_grund(str(datei)))
            self.assertIn("keine Programmdatei", uebergabe.programm_grund(ordner))
            datei.write_bytes(b"MZ")
            self.assertEqual(uebergabe.programm_grund(str(datei)), "")


class TestVonHausAusAus(unittest.TestCase):
    """Eingebaut, aber erst an, wenn man sie einschaltet."""

    def _fund(self):
        return next(f for f in erweiterungen.finden([]) if f.kennung == "csv2excel")

    def test_sie_wird_gefunden_und_ist_aus(self):
        fund = self._fund()
        self.assertTrue(fund.eingebaut)
        self.assertFalse(fund.von_haus_aus_an)
        self.assertFalse(erweiterungen.eingeschaltet(fund, set(), set()))
        self.assertTrue(erweiterungen.eingeschaltet(fund, {"csv2excel"}, set()))

    def test_die_anderen_eingebauten_bleiben_an(self):
        andere = [f for f in erweiterungen.finden([]) if f.kennung != "csv2excel"]
        self.assertTrue(andere)
        self.assertTrue(all(erweiterungen.eingeschaltet(f, set(), set()) for f in andere))

    def test_der_haken_im_verwalten_landet_in_an(self):
        from PySide6.QtCore import Qt
        from verteilerly.gui.erweiterungen import ErweiterungenDialog

        dialog = ErweiterungenDialog(erweiterungen.finden([]), set(), set(), None)
        bauteil_zurueckgeben(self, dialog)
        eintrag = dialog.eintraege["csv2excel"]
        self.assertEqual(eintrag.checkState(0), Qt.CheckState.Unchecked)
        self.assertEqual(dialog.wahl(), (set(), set()))
        eintrag.setCheckState(0, Qt.CheckState.Checked)
        self.assertEqual(dialog.wahl(), ({"csv2excel"}, set()))
        # "Nur mitgelieferte" sperrt sie nicht - sie ist mitgeliefert.
        dialog.nur_eingebaute_haken.setChecked(True)
        self.assertFalse(eintrag.isDisabled())


class TestImFenster(unittest.TestCase):
    """Der Knopf steht in der Werkzeugleiste, solange sie eingeschaltet ist."""

    def _fenster(self, an: bool):
        """Ein Hauptfenster - die Wahl steht vorher in der Conf der Testreihe."""
        from verteilerly import pfade
        from verteilerly.gui.hauptfenster import Hauptfenster

        conf = QSettings(str(pfade.einstellungsdatei()), QSettings.Format.IniFormat)
        einstellung_bewahren(self, conf, "erweiterungen_an")
        conf.setValue("erweiterungen_an", "csv2excel" if an else "")
        conf.sync()
        fenster = Hauptfenster()
        bauteil_zurueckgeben(self, fenster)
        return fenster

    @staticmethod
    def _leiste(fenster):
        """Die Werkzeugleiste als Woerter - Export als EXPORT, Trenner als |."""
        leiste = fenster.werkzeugleiste
        woerter = []
        for handlung in leiste.actions():
            if handlung.isSeparator():
                woerter.append("|")
            elif leiste.widgetForAction(handlung) is fenster.export_knopf:
                woerter.append("EXPORT")
            else:
                woerter.append(handlung.text().replace("&", ""))
        return woerter

    def test_ausgeschaltet_kein_knopf(self):
        fenster = self._fenster(an=False)
        self.assertNotIn("An CSV2Excel", self._leiste(fenster))
        menueleiste = [a.text().replace("&", "") for a in fenster.menuBar().actions()]
        self.assertNotIn("An CSV2Excel", menueleiste)

    def test_eingeschaltet_zwischen_export_und_kabel_auflegen(self):
        fenster = self._fenster(an=True)
        leiste = self._leiste(fenster)
        stelle = leiste.index("EXPORT")
        self.assertEqual(
            leiste[stelle:stelle + 4], ["EXPORT", "An CSV2Excel", "|", "Kabel auflegen…"]
        )
        knopf = next(a for a in fenster.werkzeugleiste.actions() if a.text() == "An CSV2Excel")
        self.assertEqual(knopf.property("erweiterung"), "csv2excel")
        self.assertFalse(knopf.property("fremd"))
        # Ohne Verteiler aus wie Export, mit einem an.
        self.assertFalse(knopf.isEnabled())
        fenster._projekt_setzen(_projekt(), None)
        self.assertTrue(knopf.isEnabled())
        # In der Menueleiste steht er nicht.
        menueleiste = [a.text().replace("&", "") for a in fenster.menuBar().actions()]
        self.assertEqual(menueleiste[-1], "Hilfe")

        menue = next(
            a.menu() for a in fenster.menuBar().actions()
            if a.text().replace("&", "") == "Erweiterungen"
        )
        texte = [a.text().replace("&", "") for a in menue.actions() if not a.isSeparator()]
        self.assertIn("CSV2Excel einrichten…", texte)
        self.assertEqual(texte[-1], "Erweiterungen verwalten…")

    def test_knopf_und_eintrag_stehen_in_der_hilfe(self):
        from verteilerly import hilfe

        text = hilfe.dokumentation()
        for wort in ("An CSV2Excel", "CSV2Excel einrichten"):
            self.assertIn(wort, text)
        englisch = (pathlib.Path(__file__).resolve().parent.parent
                    / "daten" / "hilfe" / "dokumentation_en.html").read_text(encoding="utf-8")
        for wort in ("To CSV2Excel", "Set up CSV2Excel"):
            self.assertIn(wort, englisch)


class Programmattrappe:
    """Was die Erweiterung vom Programm braucht - ohne Fenster."""

    def __init__(self, conf: QSettings, projekt=None) -> None:
        self.conf = conf
        self._projekt = projekt
        self.fenster = None
        self.meldungen: list[str] = []

    def projekt(self):
        return self._projekt

    def einstellungen(self):
        return self.conf

    def meldung(self, text, dauer=8000):
        self.meldungen.append(text)


class TestUebergeben(unittest.TestCase):
    def setUp(self):
        self.ordner = pathlib.Path(tempfile.mkdtemp(prefix="csv2excel-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.ordner, ignore_errors=True))
        self.conf = QSettings(str(self.ordner / "probe.conf"), QSettings.Format.IniFormat)
        self.werkzeug = self.ordner / "werkzeug" / uebergabe.PROGRAMMNAME
        self.werkzeug.parent.mkdir()
        self.werkzeug.write_bytes(b"MZ")
        self.ablage = self.ordner / "ablage"
        patcher = mock.patch.object(uebergabe, "ablageordner", return_value=self.ablage)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.erweiterung = Csv2Excel()
        self.aufrufe: list = []

        def starten(programm, argumente, ordner):
            self.aufrufe.append((programm, argumente, ordner))
            return True

        self.erweiterung.starten = starten

    def test_schreibt_die_csv_und_startet_das_werkzeug(self):
        self.conf.setValue(SCHLUESSEL_PROGRAMM, str(self.werkzeug))
        self.conf.setValue(SCHLUESSEL_SOFORT, True)
        self.conf.setValue(SCHLUESSEL_EXPORT, "D:/Excel")
        programm = Programmattrappe(self.conf, _projekt())
        self.assertTrue(self.erweiterung.uebergeben(programm))

        csv = self.ablage / "Hauptverteiler.csv"
        self.assertTrue(csv.is_file())
        inhalt = csv.read_text(encoding="utf-8-sig")
        self.assertIn("Bucht;Leiste;Stift;Ader", inhalt)
        self.assertIn("Hauptverteiler", inhalt)
        self.assertEqual(self.aufrufe, [(
            str(self.werkzeug), [str(csv), "--export", "D:/Excel", "--start"],
            str(self.werkzeug.parent),
        )])
        self.assertIn("Hauptverteiler.csv", programm.meldungen[-1])

    def test_als_projektdatei(self):
        from verteilerly import projektdatei
        from verteilerly.erweiterungen.csv2excel import SCHLUESSEL_FORMAT

        self.conf.setValue(SCHLUESSEL_PROGRAMM, str(self.werkzeug))
        self.conf.setValue(SCHLUESSEL_FORMAT, uebergabe.VTLY)
        projekt = _projekt()
        projekt.briefkopf["kunde"] = "Ungespeichert GmbH"
        self.assertTrue(self.erweiterung.uebergeben(Programmattrappe(self.conf, projekt)))

        vtly = self.ablage / "Hauptverteiler.vtly"
        self.assertEqual(self.aufrufe[0][1], [str(vtly)])
        self.assertFalse((self.ablage / "Hauptverteiler.csv").exists())
        # Uebergeben wird der Stand im Fenster - auch was nie gespeichert war.
        gelesen = projektdatei.laden(vtly)
        self.assertEqual(gelesen.verteiler.name, "Hauptverteiler")
        self.assertEqual(gelesen.briefkopf["kunde"], "Ungespeichert GmbH")

    def test_jedes_mal_fragen(self):
        from verteilerly.erweiterungen.csv2excel import SCHLUESSEL_FORMAT

        self.conf.setValue(SCHLUESSEL_PROGRAMM, str(self.werkzeug))
        self.conf.setValue(SCHLUESSEL_FORMAT, uebergabe.FRAGEN)
        programm = Programmattrappe(self.conf, _projekt())
        for antwort, endung in ((uebergabe.VTLY, ".vtly"), (uebergabe.CSV, ".csv")):
            with mock.patch.object(self.erweiterung, "format_erfragen", return_value=antwort):
                self.assertTrue(self.erweiterung.uebergeben(programm))
            self.assertEqual(pathlib.Path(self.aufrufe[-1][1][0]).suffix, endung)

        # Abgebrochen: nichts geschrieben, nichts gestartet.
        zuvor = len(self.aufrufe)
        with mock.patch.object(self.erweiterung, "format_erfragen", return_value=None):
            self.assertFalse(self.erweiterung.uebergeben(programm))
        self.assertEqual(len(self.aufrufe), zuvor)

    def test_die_rueckfrage_bietet_beide_an(self):
        from PySide6.QtWidgets import QMessageBox

        def exec_(kasten):
            texte = [k.text() for k in kasten.buttons()]
            self.assertIn("Als CSV", texte)
            self.assertIn("Als Projektdatei (.vtly)", texte)
            knopf = next(k for k in kasten.buttons() if k.text() == "Als Projektdatei (.vtly)")
            knopf.click()
            return 0

        with mock.patch.object(QMessageBox, "exec", exec_):
            wahl = Csv2Excel.format_erfragen(Programmattrappe(self.conf, _projekt()))
        self.assertEqual(wahl, uebergabe.VTLY)

    def test_ohne_projekt_wird_nichts_gestartet(self):
        self.conf.setValue(SCHLUESSEL_PROGRAMM, str(self.werkzeug))
        with mock.patch("PySide6.QtWidgets.QMessageBox.information") as hinweis:
            self.assertFalse(self.erweiterung.uebergeben(Programmattrappe(self.conf)))
        hinweis.assert_called_once()
        self.assertEqual(self.aufrufe, [])

    def test_ohne_programm_wird_erst_eingerichtet(self):
        programm = Programmattrappe(self.conf, _projekt())
        with mock.patch("PySide6.QtWidgets.QMessageBox.information"), \
                mock.patch.object(self.erweiterung, "einstellen", return_value=False) as ein:
            self.assertFalse(self.erweiterung.uebergeben(programm))
        ein.assert_called_once()
        self.assertEqual(self.aufrufe, [])

        # Wer dort das Programm waehlt, kommt gleich weiter.
        def einstellen(programm):
            programm.einstellungen().setValue(SCHLUESSEL_PROGRAMM, str(self.werkzeug))
            return True

        with mock.patch("PySide6.QtWidgets.QMessageBox.information"), \
                mock.patch.object(self.erweiterung, "einstellen", side_effect=einstellen):
            self.assertTrue(self.erweiterung.uebergeben(programm))
        self.assertEqual(len(self.aufrufe), 1)
        self.assertEqual(self.aufrufe[0][1], [str(self.ablage / "Hauptverteiler.csv")])

    def test_scheitert_der_start_wird_es_gesagt(self):
        self.conf.setValue(SCHLUESSEL_PROGRAMM, str(self.werkzeug))
        self.erweiterung.starten = lambda *a: False
        with mock.patch("PySide6.QtWidgets.QMessageBox.warning") as warnung:
            self.assertFalse(
                self.erweiterung.uebergeben(Programmattrappe(self.conf, _projekt()))
            )
        warnung.assert_called_once()
        self.assertIn(str(self.werkzeug), warnung.call_args[0][2])


class TestEinrichtenDialog(unittest.TestCase):
    def _dialog(self, *werte):
        from verteilerly.erweiterungen.csv2excel.dialog import EinrichtenDialog

        dialog = EinrichtenDialog(*werte)
        bauteil_zurueckgeben(self, dialog)
        return dialog

    def test_zeigt_und_liefert_die_werte(self):
        dialog = self._dialog("C:/Tools/x.exe", True, "D:/Excel")
        self.assertEqual(
            (dialog.programm(), dialog.sofort(), dialog.export(), dialog.format()),
            ("C:/Tools/x.exe", True, "D:/Excel", uebergabe.CSV),
        )

    def test_die_formatwahl(self):
        from verteilerly.erweiterungen.csv2excel.dialog import EinrichtenDialog

        dialog = EinrichtenDialog(art=uebergabe.FRAGEN)
        bauteil_zurueckgeben(self, dialog)
        self.assertEqual(dialog.format(), uebergabe.FRAGEN)
        self.assertEqual(
            [dialog.formatwahl.itemText(i) for i in range(dialog.formatwahl.count())],
            ["CSV", "Projektdatei (.vtly)", "Jedes Mal fragen"],
        )
        dialog.formatwahl.setCurrentIndex(1)
        self.assertEqual(dialog.format(), uebergabe.VTLY)

    def test_ein_falscher_pfad_wird_nicht_angenommen(self):
        dialog = self._dialog("/gibt/es/nicht.exe")
        with mock.patch("PySide6.QtWidgets.QMessageBox.warning") as warnung:
            dialog._annehmen()
        warnung.assert_called_once()
        self.assertNotEqual(dialog.result(), dialog.DialogCode.Accepted)

    def test_leer_darf_es_bleiben(self):
        dialog = self._dialog()
        with mock.patch("PySide6.QtWidgets.QMessageBox.warning") as warnung:
            dialog._annehmen()
        warnung.assert_not_called()
        self.assertEqual(dialog.result(), dialog.DialogCode.Accepted)

    def test_einstellen_schreibt_in_die_conf(self):
        from verteilerly.erweiterungen.csv2excel.dialog import EinrichtenDialog

        with tempfile.TemporaryDirectory() as ordner:
            conf = QSettings(str(pathlib.Path(ordner) / "p.conf"), QSettings.Format.IniFormat)
            programm = Programmattrappe(conf)

            def exec_(dialog):
                dialog.programmfeld.setText("")
                dialog.exportfeld.setText("E:/Mappen")
                dialog.sofort_haken.setChecked(True)
                dialog.formatwahl.setCurrentIndex(dialog.formatwahl.findData("vtly"))
                return EinrichtenDialog.DialogCode.Accepted

            with mock.patch.object(EinrichtenDialog, "exec", exec_):
                self.assertTrue(Csv2Excel().einstellen(programm))
            self.assertEqual(Csv2Excel.werte(programm), ("", True, "E:/Mappen", "vtly"))


if __name__ == "__main__":
    unittest.main()
