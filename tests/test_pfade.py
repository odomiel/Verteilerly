"""Tests zur Datensuche."""

import os
import pathlib
import unittest
from unittest import mock

from verteilerly import pfade


class TestDatensuche(unittest.TestCase):
    def test_quellbaum_wird_gefunden(self):
        self.assertTrue(pfade.vorlagenordner().is_dir())
        self.assertTrue(pfade.kabeltypenordner().is_dir())

    def test_neben_der_appimage_zuerst(self):
        """Auf dem Stick liegt der Datenordner neben der AppImage-Datei."""
        with mock.patch.dict(os.environ, {"APPIMAGE": "/stick/Verteilerly.AppImage"}):
            self.assertEqual(pfade.appimage(), pathlib.Path("/stick"))
            self.assertEqual(pfade._kandidaten()[0], pathlib.Path("/stick/daten"))

    def test_ohne_appimage_kein_zusaetzlicher_ort(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(pfade.appimage())
            self.assertNotIn(pathlib.Path("/stick/daten"), pfade._kandidaten())

    def test_mitgeliefertes_verzeichnis_als_rueckfall(self):
        """PyInstaller entpackt die Beigabe nach _MEIPASS."""
        with mock.patch.object(pfade.sys, "_MEIPASS", "/tmp/_MEIxyz", create=True):
            self.assertIn(pathlib.Path("/tmp/_MEIxyz/daten"), pfade._kandidaten())

    def test_fehlermeldung_nennt_die_gesuchten_orte(self):
        with mock.patch.object(pfade, "_kandidaten", return_value=[pathlib.Path("/nix")]):
            with self.assertRaises(FileNotFoundError) as fehler:
                pfade.datenordner()
        self.assertIn("/nix", str(fehler.exception))


if __name__ == "__main__":
    unittest.main()
