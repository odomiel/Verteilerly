"""Tests zur Anmeldung bei der Dateiverwaltung.

Geschrieben wird immer in einen eigenen ``XDG_DATA_HOME``: die Tests
sollen die Arbeitsflaeche des Rechners nicht umstellen.
"""

import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

from verteilerly import verknuepfung
from verteilerly.verknuepfung import VerknuepfungFehler


class TestAufruf(unittest.TestCase):
    """Womit die Dateiverwaltung das Programm startet."""

    def test_aus_dem_quellbaum_mit_demselben_python(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("APPIMAGE", None)
            aufruf = verknuepfung.aufruf()
        self.assertIn("-m verteilerly", aufruf)
        self.assertIn(pathlib.Path(sys.executable).name, aufruf)

    def test_als_appimage_die_datei_selbst(self):
        with mock.patch.dict(os.environ, {"APPIMAGE": "/stick/Verteilerly.AppImage"}):
            self.assertEqual(verknuepfung.aufruf(), "/stick/Verteilerly.AppImage")

    def test_ein_pfad_mit_leerzeichen_steht_in_anfuehrungszeichen(self):
        with mock.patch.dict(os.environ, {"APPIMAGE": "/mein Ordner/Verteilerly"}):
            self.assertEqual(verknuepfung.aufruf(), '"/mein Ordner/Verteilerly"')


@unittest.skipUnless(sys.platform.startswith("linux"), "nur unter Linux")
class TestLinuxAnmelden(unittest.TestCase):
    """Dateityp und Desktop-Eintrag im eigenen Datenordner."""

    def setUp(self):
        self._ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self._ordner.cleanup)
        self.ordner = pathlib.Path(self._ordner.name)
        stelle = mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(self.ordner)})
        stelle.start()
        self.addCleanup(stelle.stop)

    def test_beide_dateien_entstehen(self):
        geschrieben = verknuepfung.anmelden()
        mime = self.ordner / "mime" / "packages" / "verteilerly.xml"
        desktop = self.ordner / "applications" / "verteilerly.desktop"
        self.assertTrue(mime.is_file())
        self.assertTrue(desktop.is_file())
        self.assertEqual(geschrieben, [str(mime), str(desktop)])

    def test_der_dateityp_kennt_beide_endungen(self):
        """Gespeichert wird `.vtly`, gelesen auch die alte Schreibweise."""
        verknuepfung.anmelden()
        xml = (self.ordner / "mime" / "packages" / "verteilerly.xml").read_text(
            encoding="utf-8"
        )
        self.assertIn('pattern="*.vtly"', xml)
        self.assertIn('pattern="*.vtly.json"', xml)
        self.assertIn(verknuepfung.MIMETYP, xml)

    def test_der_eintrag_nennt_den_aufruf_und_die_datei(self):
        verknuepfung.anmelden()
        eintrag = (self.ordner / "applications" / "verteilerly.desktop").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"Exec={verknuepfung.aufruf()} %f", eintrag)
        self.assertIn(f"MimeType={verknuepfung.MIMETYP};", eintrag)

    def test_danach_gilt_sie_als_angemeldet(self):
        self.assertFalse(verknuepfung.angemeldet())
        verknuepfung.anmelden()
        self.assertTrue(verknuepfung.angemeldet())

    def test_ein_anderer_aufruf_gilt_nicht_als_angemeldet(self):
        """Ein Abbild, das umgezogen ist, muss neu angemeldet werden."""
        verknuepfung.anmelden()
        with mock.patch.dict(os.environ, {"APPIMAGE": "/woanders/Verteilerly"}):
            self.assertFalse(verknuepfung.angemeldet())

    def test_das_sinnbild_ist_eine_zugabe(self):
        """Ohne Zeichner wird keines geschrieben - angemeldet ist sie doch."""
        verknuepfung.anmelden()
        self.assertFalse(verknuepfung.symbolort().exists())
        verknuepfung.anmelden(lambda ziel: pathlib.Path(ziel).write_bytes(b"PNG"))
        self.assertTrue(verknuepfung.symbolort().is_file())

    def test_ein_zeichner_der_faellt_haelt_nichts_auf(self):
        def kaputt(_ziel):
            raise RuntimeError("kein Bild")

        geschrieben = verknuepfung.anmelden(kaputt)
        self.assertEqual(len(geschrieben), 2)
        self.assertTrue(verknuepfung.angemeldet())

    def test_was_sich_nicht_schreiben_laesst_wird_gemeldet(self):
        # Eine Datei als Ordner: das Anlegen muss scheitern.
        (self.ordner / "mime").write_text("kein Ordner", encoding="utf-8")
        with self.assertRaises(VerknuepfungFehler):
            verknuepfung.anmelden()


class TestAbgeschottet(unittest.TestCase):
    """Die Testreihe sieht die Anmeldung des Benutzers nicht."""

    def test_der_desktop_eintrag_liegt_im_ordner_der_testreihe(self):
        """Sonst liest ein Test die echte Zuordnung - und hing an ihr."""
        eigen = pathlib.Path.home() / ".local" / "share"
        for ort in verknuepfung._linux_orte():
            self.assertNotIn(eigen, ort.parents, str(ort))
        self.assertIn(
            pathlib.Path(os.environ["XDG_DATA_HOME"]),
            verknuepfung._linux_orte()[1].parents,
        )


class TestWerGeradeOeffnet(unittest.TestCase):
    """Worauf die Zuordnung zeigt - und ob das dieses Programm ist."""

    def setUp(self):
        self._ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self._ordner.cleanup)
        self.ordner = pathlib.Path(self._ordner.name)
        stelle = mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(self.ordner)})
        stelle.start()
        self.addCleanup(stelle.stop)

    def _desktop(self):
        return self.ordner / "applications" / "verteilerly.desktop"

    def test_ohne_anmeldung_ist_nichts_eingetragen(self):
        self.assertEqual(verknuepfung.angemeldeter_aufruf(), "")
        self.assertEqual(verknuepfung.anderes_programm(), "")

    def test_nach_der_anmeldung_steht_der_eigene_aufruf_da(self):
        verknuepfung.anmelden()
        self.assertEqual(verknuepfung.angemeldeter_aufruf(), verknuepfung.aufruf())
        self.assertEqual(verknuepfung.anderes_programm(), "")

    def test_ein_fremder_eintrag_wird_als_solcher_gemeldet(self):
        """Der Fall einer portablen Ausgabe: eingetragen ist eine andere Datei."""
        verknuepfung.anmelden()
        datei = self._desktop()
        datei.write_text(
            datei.read_text(encoding="utf-8").replace(
                f"Exec={verknuepfung.aufruf()} %f",
                "Exec=/stick/VerteilerlyPortable.exe %f",
            ),
            encoding="utf-8",
        )
        self.assertEqual(
            verknuepfung.angemeldeter_aufruf(), "/stick/VerteilerlyPortable.exe"
        )
        self.assertEqual(
            verknuepfung.anderes_programm(), "/stick/VerteilerlyPortable.exe"
        )
        self.assertFalse(verknuepfung.angemeldet())

    def test_der_platzhalter_gehoert_nicht_zum_befehl(self):
        for befehl, erwartet in (
            ('"C:\\Verteilerly.exe" "%1"', '"C:\\Verteilerly.exe"'),
            ("/stick/Verteilerly %f", "/stick/Verteilerly"),
            ("/stick/Verteilerly %U", "/stick/Verteilerly"),
            ("/stick/Verteilerly", "/stick/Verteilerly"),
        ):
            self.assertEqual(verknuepfung._ohne_platzhalter(befehl), erwartet)


class TestFremdesSystem(unittest.TestCase):
    def test_was_das_programm_nicht_kennt_sagt_es(self):
        with mock.patch.object(sys, "platform", "sunos5"):
            self.assertFalse(verknuepfung.moeglich())
            self.assertFalse(verknuepfung.angemeldet())
            with self.assertRaises(VerknuepfungFehler):
                verknuepfung.anmelden()


if __name__ == "__main__":
    unittest.main()
