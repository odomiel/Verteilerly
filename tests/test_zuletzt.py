"""Tests zu *Datei ▸ Zuletzt geöffnet*.

Die Liste selbst (``einstellungen.zuletzt_*``) laeuft gegen eine eigene
Conf im Temp-Ordner, das Menue gegen ein echtes Hauptfenster - dessen
Conf ist die der Testreihe, der Schluessel wird darum bewahrt.
"""

from __future__ import annotations

# Erst das Paket: es legt Einstellungs- und Arbeitsordner der
# Testreihe um, bevor etwas aus verteilerly Pfade liest.
from . import TESTHEIM  # noqa: F401

import os
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

ANWENDUNG = QApplication.instance() or QApplication([])

from verteilerly import einstellungen, projektdatei  # noqa: E402
from verteilerly.modell import Projekt, Verteiler  # noqa: E402

from . import bauteil_zurueckgeben, einstellung_bewahren  # noqa: E402


def _ordner(test) -> pathlib.Path:
    ordner = pathlib.Path(tempfile.mkdtemp(prefix="zuletzt-"))
    test.addCleanup(shutil.rmtree, ordner, True)
    return ordner


def _projektdatei(ordner: pathlib.Path, name: str) -> pathlib.Path:
    pfad = ordner / f"{name}.vtly"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    projektdatei.speichern(
        Projekt(verteiler=Verteiler.aus_buchten([(1, 10)], name, "1")), pfad
    )
    return pfad


class TestListe(unittest.TestCase):
    def setUp(self):
        self.ordner = _ordner(self)
        self.conf = QSettings(str(self.ordner / "p.conf"), QSettings.Format.IniFormat)

    def test_neueste_zuerst_und_hoechstens_fuenf(self):
        for nummer in range(7):
            einstellungen.zuletzt_merken(self.conf, self.ordner / f"v{nummer}.vtly")
        namen = [pathlib.Path(p).name for p in einstellungen.zuletzt_geoeffnet(self.conf)]
        self.assertEqual(namen, ["v6.vtly", "v5.vtly", "v4.vtly", "v3.vtly", "v2.vtly"])
        self.assertEqual(einstellungen.ZULETZT_HOECHSTENS, 5)

    def test_ein_gemerkter_rueckt_nur_auf(self):
        a, b = self.ordner / "a.vtly", self.ordner / "b.vtly"
        einstellungen.zuletzt_merken(self.conf, a)
        einstellungen.zuletzt_merken(self.conf, b)
        einstellungen.zuletzt_merken(self.conf, a)
        self.assertEqual(einstellungen.zuletzt_geoeffnet(self.conf), [str(a), str(b)])

    def test_ein_einzelner_eintrag_bleibt_eine_liste(self):
        einstellungen.zuletzt_merken(self.conf, self.ordner / "a.vtly")
        self.conf.sync()
        frisch = QSettings(str(self.ordner / "p.conf"), QSettings.Format.IniFormat)
        self.assertEqual(
            einstellungen.zuletzt_geoeffnet(frisch), [str(self.ordner / "a.vtly")]
        )

    def test_vergessen_einzeln_und_alle(self):
        a, b = self.ordner / "a.vtly", self.ordner / "b.vtly"
        einstellungen.zuletzt_merken(self.conf, a)
        einstellungen.zuletzt_merken(self.conf, b)
        einstellungen.zuletzt_vergessen(self.conf, a)
        self.assertEqual(einstellungen.zuletzt_geoeffnet(self.conf), [str(b)])
        einstellungen.zuletzt_vergessen(self.conf)
        self.assertEqual(einstellungen.zuletzt_geoeffnet(self.conf), [])

    def test_unlesbares_gibt_eine_leere_liste(self):
        for wert in ("kein json", '{"a": 1}', "[1, 2]"):
            self.conf.setValue(einstellungen.SCHLUESSEL_ZULETZT, wert)
            self.assertEqual(einstellungen.zuletzt_geoeffnet(self.conf), [])

    def test_reist_nicht_im_paket_mit(self):
        from verteilerly.gui.hauptfenster import _darf_uebernehmen

        self.assertFalse(_darf_uebernehmen(einstellungen.SCHLUESSEL_ZULETZT))


class TestMenue(unittest.TestCase):
    def setUp(self):
        from verteilerly import pfade
        from verteilerly.gui.hauptfenster import Hauptfenster

        conf = QSettings(str(pfade.einstellungsdatei()), QSettings.Format.IniFormat)
        einstellung_bewahren(self, conf, einstellungen.SCHLUESSEL_ZULETZT)
        conf.setValue(einstellungen.SCHLUESSEL_ZULETZT, "[]")
        conf.sync()
        self.fenster = Hauptfenster()
        bauteil_zurueckgeben(self, self.fenster)
        self.ordner = _ordner(self)

    def _eintraege(self):
        return [
            a for a in self.fenster.zuletzt_menue.actions()
            if not a.isSeparator() and a.property("verlauf")
        ]

    def _leeren(self):
        return next(
            a for a in self.fenster.zuletzt_menue.actions()
            if a.text().replace("&", "") == "Liste leeren"
        )

    def test_steht_im_dateimenue_unter_schreibgeschuetzt_oeffnen(self):
        datei = next(
            a.menu() for a in self.fenster.menuBar().actions()
            if a.text().replace("&", "") == "Datei"
        )
        texte = [a.text().replace("&", "") for a in datei.actions()]
        stelle = texte.index("Schreibgeschützt öffnen…")
        self.assertEqual(texte[stelle + 1], "Zuletzt geöffnet")

    def test_leer_steht_ein_grauer_hinweis(self):
        eintraege = self._eintraege()
        self.assertEqual(len(eintraege), 1)
        self.assertFalse(eintraege[0].isEnabled())
        self.assertFalse(self._leeren().isEnabled())

    def test_oeffnen_und_speichern_kommen_in_die_liste(self):
        a = _projektdatei(self.ordner, "Halle A")
        b = _projektdatei(self.ordner, "Halle B")
        self.assertTrue(self.fenster.datei_oeffnen(a))
        self.assertTrue(self.fenster.datei_oeffnen(b))
        texte = [x.text() for x in self._eintraege()]
        self.assertEqual(texte, ["&1 Halle B.vtly", "&2 Halle A.vtly"])
        self.assertEqual(self._eintraege()[0].toolTip(), str(b))
        self.assertTrue(self._leeren().isEnabled())

        c = self.ordner / "Halle C.vtly"
        with mock.patch(
            "verteilerly.gui.hauptfenster.QFileDialog.getSaveFileName",
            return_value=(str(c), ""),
        ):
            self.assertTrue(self.fenster.speichern_unter())
        self.assertEqual(self._eintraege()[0].text(), "&1 Halle C.vtly")

    def test_ein_klick_oeffnet_den_verteiler(self):
        a = _projektdatei(self.ordner, "Halle A")
        _projektdatei(self.ordner, "Halle B")
        self.fenster.datei_oeffnen(a)
        self.fenster.datei_oeffnen(self.ordner / "Halle B.vtly")
        self._eintraege()[1].trigger()
        self.assertEqual(self.fenster.pfad, a)
        self.assertEqual(self.fenster.projekt.verteiler.name, "Halle A")

    def test_gleiche_namen_bekommen_den_ordner(self):
        a = _projektdatei(self.ordner / "Nord", "HV")
        b = _projektdatei(self.ordner / "Sued", "HV")
        self.fenster.datei_oeffnen(a)
        self.fenster.datei_oeffnen(b)
        self.assertEqual(
            [x.text() for x in self._eintraege()], ["&1 HV.vtly — Sued", "&2 HV.vtly — Nord"]
        )

    def test_ein_kaufmannsund_im_namen_bleibt_stehen(self):
        self.fenster.datei_oeffnen(_projektdatei(self.ordner, "Lager & Hof"))
        self.assertEqual(self._eintraege()[0].text(), "&1 Lager && Hof.vtly")

    def test_eine_verschwundene_datei_fliegt_heraus(self):
        a = _projektdatei(self.ordner, "Halle A")
        self.fenster.datei_oeffnen(a)
        a.unlink()
        with mock.patch("verteilerly.gui.hauptfenster.QMessageBox.warning") as warnung:
            self.assertFalse(self.fenster.zuletzt_oeffnen(a))
        warnung.assert_called_once()
        self.assertEqual(len(self._eintraege()), 1)
        self.assertFalse(self._eintraege()[0].isEnabled())

    def test_ein_geaenderter_verteiler_wird_erst_gefragt(self):
        a = _projektdatei(self.ordner, "Halle A")
        with mock.patch.object(self.fenster, "_darf_verwerfen", return_value=False):
            self.assertFalse(self.fenster.zuletzt_oeffnen(a))
        self.assertIsNone(self.fenster.pfad)

    def test_liste_leeren(self):
        self.fenster.datei_oeffnen(_projektdatei(self.ordner, "Halle A"))
        self._leeren().trigger()
        self.assertEqual(
            einstellungen.zuletzt_geoeffnet(self.fenster.einstellungen), []
        )
        self.assertFalse(self._leeren().isEnabled())


if __name__ == "__main__":
    unittest.main()
