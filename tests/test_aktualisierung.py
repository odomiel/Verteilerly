"""Die taegliche Nachfrage nach einer neueren Fassung - ohne Netz geprueft."""

import datetime
import io
import json
import unittest
from unittest import mock

from verteilerly import aktualisierung
from verteilerly.version import VERSION


def _antwort(inhalt: dict):
    """Eine Antwort, wie urlopen sie liefert - als Kontextverwalter."""
    strom = io.BytesIO(json.dumps(inhalt).encode())
    strom.__enter__ = lambda: strom
    strom.__exit__ = lambda *a: False
    return strom


class TestFaellig(unittest.TestCase):
    """Einmal am Tag, nicht bei jedem Start."""

    def test_am_selben_tag_nicht_noch_einmal(self):
        heute = datetime.date(2026, 10, 12)
        self.assertFalse(aktualisierung.faellig("2026-10-12", heute))

    def test_am_naechsten_tag_wieder(self):
        heute = datetime.date(2026, 10, 13)
        self.assertTrue(aktualisierung.faellig("2026-10-12", heute))

    def test_ohne_merkzettel_und_bei_unfug_wird_gesehen(self):
        """Lieber einmal zu viel nachsehen als nie wieder."""
        heute = datetime.date(2026, 10, 12)
        for wert in ("", "   ", "gestern", "2026-13-40", None):
            with self.subTest(wert=wert):
                self.assertTrue(aktualisierung.faellig(wert, heute))


class TestVergleich(unittest.TestCase):
    def test_neuer_ist_neuer(self):
        self.assertTrue(aktualisierung.neuer_als("2099.01.01", "2026.10.12"))
        self.assertTrue(aktualisierung.neuer_als("2026.10.12b4", "2026.10.12b3"))

    def test_gleich_und_aelter_ist_nicht_neuer(self):
        self.assertFalse(aktualisierung.neuer_als("2026.10.12", "2026.10.12"))
        self.assertFalse(aktualisierung.neuer_als("2026.10.11", "2026.10.12"))

    def test_was_keine_fassung_ist_zaehlt_nicht(self):
        """Eine fremde Antwort darf keine Meldung ausloesen."""
        for unfug in ("", "latest", "v1.2.3", "2026.13.40"):
            with self.subTest(wert=unfug):
                self.assertFalse(aktualisierung.neuer_als(unfug, "2026.10.12"))


class TestNachsehen(unittest.TestCase):
    """Gefragt wird die Releaseliste - mit allem, was schiefgehen kann."""

    def setUp(self):
        frei = mock.patch.dict("os.environ", {aktualisierung.OHNE_PRUEFUNG: ""})
        frei.start()
        self.addCleanup(frei.stop)
        umfeld = mock.patch.object(aktualisierung, "_umgebung", lambda: object())
        umfeld.start()
        self.addCleanup(umfeld.stop)

    def test_die_fassung_kommt_aus_dem_tag(self):
        antwort = _antwort({"tag_name": "2099.01.01",
                            "html_url": "https://example.invalid/r"})
        with mock.patch("urllib.request.urlopen", return_value=antwort):
            gefunden = aktualisierung.nachsehen()
        self.assertEqual(gefunden["fassung"], "2099.01.01")
        self.assertEqual(gefunden["seite"], "https://example.invalid/r")

    def test_ein_v_davor_stoert_nicht(self):
        antwort = _antwort({"tag_name": "v2099.01.01"})
        with mock.patch("urllib.request.urlopen", return_value=antwort):
            self.assertEqual(aktualisierung.nachsehen()["fassung"], "2099.01.01")

    def test_ohne_netz_kommt_nichts(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("kein Netz")):
            self.assertIsNone(aktualisierung.nachsehen())

    def test_eine_krumme_antwort_kommt_nicht_durch(self):
        for inhalt in ({}, {"tag_name": ""}, {"etwas": "anderes"}):
            with self.subTest(inhalt=inhalt):
                with mock.patch("urllib.request.urlopen",
                                return_value=_antwort(inhalt)):
                    self.assertIsNone(aktualisierung.nachsehen())

    def test_ohne_zertifikate_wird_nicht_gefragt(self):
        """Lieber nicht pruefen als ungeprueft verbinden."""
        with mock.patch.object(aktualisierung, "_umgebung", lambda: None), \
                mock.patch("urllib.request.urlopen") as gefragt:
            self.assertIsNone(aktualisierung.nachsehen())
            gefragt.assert_not_called()

    def test_gemeldet_wird_nur_was_neuer_ist(self):
        with mock.patch.object(aktualisierung, "nachsehen",
                               return_value={"fassung": VERSION, "seite": "x"}):
            self.assertIsNone(aktualisierung.neuere_fassung())
        with mock.patch.object(aktualisierung, "nachsehen",
                               return_value={"fassung": "2099.01.01", "seite": "x"}):
            self.assertEqual(
                aktualisierung.neuere_fassung()["fassung"], "2099.01.01"
            )


class TestAbschaltbar(unittest.TestCase):
    def test_die_testreihe_geht_nicht_ins_netz(self):
        """tests/__init__ setzt die Sperre - hier steht sie zur Probe."""
        self.assertFalse(aktualisierung.erlaubt())

    def test_gesperrt_wird_gar_nicht_erst_gefragt(self):
        with mock.patch("urllib.request.urlopen") as gefragt:
            self.assertIsNone(aktualisierung.nachsehen())
            gefragt.assert_not_called()


class TestZertifikate(unittest.TestCase):
    def test_der_speicher_des_rechners_wird_gesucht(self):
        datei, ordner = aktualisierung.zertifikatsspeicher()
        self.assertTrue(
            datei or ordner,
            "auf diesem Rechner sollte ein Zertifikatspeicher liegen",
        )

    def test_ohne_speicher_kein_umfeld(self):
        with mock.patch.object(aktualisierung, "zertifikatsspeicher",
                               return_value=(None, None)), \
                mock.patch("os.name", "posix"):
            self.assertIsNone(aktualisierung._umgebung())


if __name__ == "__main__":
    unittest.main()
