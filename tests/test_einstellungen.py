"""Tests zu den gemerkten Projektdaten."""

import os
import pathlib
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    ANWENDUNG = QApplication.instance() or QApplication([])
except ImportError:                                   # pragma: no cover
    ANWENDUNG = None

from verteilerly import einstellungen as sp
from verteilerly.modell import Projekt, Verteiler


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestProjektdatenMerken(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.datei = pathlib.Path(self.ordner.name) / "Verteilerly.conf"
        self.einstellungen = QSettings(str(self.datei), QSettings.Format.IniFormat)

    def _projekt(self):
        projekt = Projekt(
            verteiler=Verteiler.aus_geometrie(1, 4, 10, name="Erster"),
            briefkopf={"firma": "Musterfirma", "kuerzel": "MI"},
            eigene_felder={"Standort": "Keller"},
        )
        projekt.sichtbarkeit_setzen("kuerzel", False)
        return projekt

    def test_die_felder_stehen_in_der_conf(self):
        sp.briefkopf_sichern(self.einstellungen, self._projekt())
        inhalt = self.datei.read_text(encoding="utf-8")
        self.assertIn("[briefkopf]", inhalt)
        self.assertIn("firma=Musterfirma", inhalt)
        self.assertIn("[eigene_felder]", inhalt)
        self.assertIn("felder_ausgeblendet=kuerzel", inhalt)

    def test_gelesen_wird_dasselbe(self):
        sp.briefkopf_sichern(self.einstellungen, self._projekt())
        briefkopf, eigene, ausgeblendet = sp.briefkopf_laden(self.einstellungen)
        self.assertEqual(briefkopf, {"firma": "Musterfirma", "kuerzel": "MI"})
        self.assertEqual(eigene, {"Standort": "Keller"})
        self.assertEqual(ausgeblendet, {"kuerzel"})

    def test_ein_neuer_verteiler_erbt_den_briefkopf(self):
        sp.briefkopf_sichern(self.einstellungen, self._projekt())
        neu = sp.briefkopf_uebernehmen(
            self.einstellungen, Projekt(verteiler=Verteiler.aus_geometrie(1, 2, 20))
        )
        self.assertEqual(neu.briefkopf["firma"], "Musterfirma")
        self.assertEqual(neu.eigene_felder["Standort"], "Keller")
        self.assertFalse(neu.sichtbar("kuerzel"))

    def test_die_vorgabe_ueberschreibt_keine_eingabe(self):
        sp.briefkopf_sichern(self.einstellungen, self._projekt())
        projekt = Projekt(briefkopf={"firma": "Andere Firma"})
        sp.briefkopf_uebernehmen(self.einstellungen, projekt)
        self.assertEqual(projekt.briefkopf["firma"], "Andere Firma")
        self.assertEqual(projekt.briefkopf["kuerzel"], "MI")

    def test_ohne_gemerkten_briefkopf_passiert_nichts(self):
        projekt = sp.briefkopf_uebernehmen(self.einstellungen, Projekt())
        self.assertEqual(projekt.briefkopf, {})
        self.assertEqual(projekt.ausgeblendet, set())

    def test_geloeschte_felder_verschwinden_auch_aus_der_conf(self):
        """Sonst kämen längst entfernte Felder beim nächsten Verteiler zurück."""
        sp.briefkopf_sichern(self.einstellungen, self._projekt())
        weniger = Projekt(briefkopf={"firma": "Musterfirma"})
        sp.briefkopf_sichern(self.einstellungen, weniger)
        briefkopf, eigene, _ = sp.briefkopf_laden(self.einstellungen)
        self.assertEqual(briefkopf, {"firma": "Musterfirma"})
        self.assertEqual(eigene, {})

    def test_feldnamen_mit_komma_und_leerzeichen(self):
        """QSettings trennt Listen mit Komma - der Name darf eins enthalten."""
        projekt = Projekt(eigene_felder={"Standort, Raum": "Keller"})
        projekt.sichtbarkeit_setzen("Standort, Raum", False)
        sp.briefkopf_sichern(self.einstellungen, projekt)
        _, eigene, ausgeblendet = sp.briefkopf_laden(self.einstellungen)
        self.assertEqual(eigene, {"Standort, Raum": "Keller"})
        self.assertEqual(ausgeblendet, {"Standort, Raum"})

    def test_hauptfenster_reicht_die_vorgaben_durch(self):
        """Was als Vorgabe gemerkt ist, steht im nächsten Verteiler."""
        from verteilerly.gui.hauptfenster import Hauptfenster

        fenster = Hauptfenster()
        sp.briefkopf_sichern(fenster.einstellungen, self._projekt())

        geerbt = fenster.neues_projekt(Verteiler.aus_geometrie(1, 2, 20, name="Zweiter"))
        self.assertEqual(geerbt.briefkopf["firma"], "Musterfirma")
        self.assertEqual(geerbt.verteiler.name, "Zweiter")

        fenster.einstellungen.beginGroup("briefkopf")
        fenster.einstellungen.remove("")
        fenster.einstellungen.endGroup()
        fenster.einstellungen.sync()


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestVorgaben(unittest.TestCase):
    """Die Vorgaben werden eigens gesetzt, nicht nebenbei gemerkt."""

    def setUp(self):
        from verteilerly.gui.hauptfenster import Hauptfenster

        self.fenster = Hauptfenster()
        self.addCleanup(self._conf_leeren)

    def _conf_leeren(self):
        for gruppe in ("briefkopf", "eigene_felder"):
            self.fenster.einstellungen.beginGroup(gruppe)
            self.fenster.einstellungen.remove("")
            self.fenster.einstellungen.endGroup()
        self.fenster.einstellungen.setValue("felder_ausgeblendet", [])
        self.fenster.einstellungen.sync()

    def _vorgaben_setzen(self, **werte):
        from unittest import mock

        from verteilerly.gui.dialoge import ProjektdatenDialog

        def tippen(dialog):
            for name, wert in werte.items():
                feld = dialog.projektdaten.felder[name]
                if hasattr(feld, "setPlainText"):
                    feld.setPlainText(wert)
                else:
                    feld.setText(wert)
            return ProjektdatenDialog.DialogCode.Accepted

        with mock.patch.object(ProjektdatenDialog, "exec", tippen):
            self.fenster.vorgaben_bearbeiten()

    def test_vorgaben_landen_in_der_conf(self):
        self._vorgaben_setzen(firma="Musterfirma", kuerzel="JD")
        briefkopf, _, _ = sp.briefkopf_laden(self.fenster.einstellungen)
        self.assertEqual(briefkopf, {"firma": "Musterfirma", "kuerzel": "JD"})

    def test_im_neuen_verteiler_ist_nur_angehakt_was_es_gibt(self):
        """Was die Vorgaben nicht füllen, gehört auf kein Blatt."""
        from unittest import mock

        from verteilerly.gui.dialoge import NeuerVerteilerDialog

        self._vorgaben_setzen(firma="Musterfirma", kuerzel="JD")
        gesehen = {}

        def anlegen(dialog):
            gesehen["angehakt"] = {
                name for name, haken in dialog.projektdaten.haken.items()
                if haken.isChecked()
            }
            dialog.name.setText("Neu")
            return NeuerVerteilerDialog.DialogCode.Accepted

        with mock.patch.object(NeuerVerteilerDialog, "exec", anlegen):
            self.fenster.neuer_verteiler()

        self.assertEqual(gesehen["angehakt"], {"firma", "kuerzel"})
        self.assertEqual(
            self.fenster.projekt.briefkopf, {"firma": "Musterfirma", "kuerzel": "JD"}
        )
        self.assertIn("kunde", self.fenster.projekt.ausgeblendet)

    def test_ein_bearbeiteter_briefkopf_aendert_die_vorgaben_nicht(self):
        """Sonst überschriebe der letzte Kunde die Vorgabe ungefragt."""
        from unittest import mock

        from verteilerly.gui.dialoge import ProjektdatenDialog

        self._vorgaben_setzen(firma="Musterfirma")
        self.fenster._projekt_setzen(
            Projekt(verteiler=Verteiler.aus_geometrie(1, 2, 10)), None
        )

        def aendern(dialog):
            dialog.projektdaten.felder["firma"].setPlainText("Ganz andere Firma")
            return ProjektdatenDialog.DialogCode.Accepted

        with mock.patch.object(ProjektdatenDialog, "exec", aendern):
            self.fenster.projektdaten_bearbeiten()

        self.assertEqual(self.fenster.projekt.briefkopf["firma"], "Ganz andere Firma")
        self.assertEqual(
            sp.briefkopf_laden(self.fenster.einstellungen)[0]["firma"], "Musterfirma"
        )

    def test_geoeffnete_verteiler_bleiben_unberuehrt(self):
        """Eine geöffnete Datei gilt, wie sie ist - ohne Vorgaben darin."""
        import json
        import tempfile
        from pathlib import Path

        from verteilerly import projektdatei

        self._vorgaben_setzen(firma="Musterfirma", kuerzel="JD")
        alt = Projekt(
            verteiler=Verteiler.aus_geometrie(1, 2, 10, name="Alt"),
            briefkopf={"firma": "Alte Firma"},
        )
        with tempfile.TemporaryDirectory() as ordner:
            pfad = Path(ordner) / "alt.vtly.json"
            projektdatei.speichern(alt, pfad)
            geladen = projektdatei.laden(pfad)
            self.fenster._projekt_setzen(geladen, pfad)

        self.assertEqual(self.fenster.projekt.briefkopf, {"firma": "Alte Firma"})
        self.assertNotIn("kuerzel", self.fenster.projekt.briefkopf)


@unittest.skipIf(ANWENDUNG is None, "PySide6 ist nicht vorhanden")
class TestNeuerVerteilerMitProjektdaten(unittest.TestCase):
    """Was im Dialog steht, gilt; die conf ergänzt nur."""

    def test_getippter_briefkopf_schlaegt_die_vorgabe(self):
        from unittest import mock

        from verteilerly.gui.dialoge import NeuerVerteilerDialog
        from verteilerly.gui.hauptfenster import Hauptfenster
        from verteilerly.modell import Verteiler

        fenster = Hauptfenster()
        fenster.einstellungen.beginGroup("briefkopf")
        fenster.einstellungen.setValue("firma", "Gemerkte Firma")
        fenster.einstellungen.setValue("kuerzel", "GM")
        fenster.einstellungen.endGroup()
        fenster.einstellungen.sync()

        def antworten(dialog):
            dialog.name.setText("Neu")
            dialog.projektdaten.felder["firma"].setPlainText("Andere Firma")
            return NeuerVerteilerDialog.DialogCode.Accepted

        with mock.patch.object(NeuerVerteilerDialog, "exec", antworten):
            fenster.neuer_verteiler()

        # Getipptes bleibt, Fehlendes kommt aus der conf.
        self.assertEqual(fenster.projekt.briefkopf["firma"], "Andere Firma")
        self.assertEqual(fenster.projekt.briefkopf["kuerzel"], "GM")

        fenster.einstellungen.beginGroup("briefkopf")
        fenster.einstellungen.remove("")
        fenster.einstellungen.endGroup()
        fenster.einstellungen.sync()


if __name__ == "__main__":
    unittest.main()
