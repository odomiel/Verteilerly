"""Tests zur Datensuche."""

import os
import pathlib
import tempfile
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

    def test_appdir_traegt_die_mitgelieferten_daten(self):
        """Im AppImage liegt die Grundausstattung im eingehängten AppDir."""
        with mock.patch.dict(os.environ, {"APPDIR": "/tmp/.mount_abc"}):
            self.assertIn(pathlib.Path("/tmp/.mount_abc/daten"), pfade._kandidaten())

    def test_stick_geht_vor_appdir(self):
        """Was der Anwender daneben legt, gilt vor dem Mitgelieferten."""
        with mock.patch.dict(
            os.environ,
            {"APPIMAGE": "/stick/Verteilerly.AppImage", "APPDIR": "/tmp/.mount_abc"},
        ):
            orte = pfade._kandidaten()
        self.assertLess(
            orte.index(pathlib.Path("/stick/daten")),
            orte.index(pathlib.Path("/tmp/.mount_abc/daten")),
        )

    def test_mitgeliefertes_verzeichnis_als_rueckfall(self):
        """PyInstaller entpackt die Beigabe nach _MEIPASS."""
        with mock.patch.object(pfade.sys, "_MEIPASS", "/tmp/_MEIxyz", create=True):
            self.assertIn(pathlib.Path("/tmp/_MEIxyz/daten"), pfade._kandidaten())

    def test_fehlermeldung_nennt_die_gesuchten_orte(self):
        with mock.patch.object(pfade, "_kandidaten", return_value=[pathlib.Path("/nix")]):
            with self.assertRaises(FileNotFoundError) as fehler:
                pfade.datenordner()
        self.assertIn("/nix", str(fehler.exception))


class TestSchreibort(unittest.TestCase):
    """Eigene Vorlagen brauchen einen Ort, an dem geschrieben werden darf."""

    def test_neben_dem_programm_wenn_dort_geschrieben_werden_darf(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                pfade.eigener_datenordner(), pfade.programmordner() / pfade.DATENORDNER
            )

    def test_neben_der_appimage_datei(self):
        """Auf dem Stick liegt der Ordner neben der AppImage-Datei."""
        with tempfile.TemporaryDirectory() as stick:
            datei = pathlib.Path(stick) / "Verteilerly.AppImage"
            datei.write_text("")
            with mock.patch.dict(
                os.environ, {"APPIMAGE": str(datei), "APPDIR": "/tmp/.mount_x"}
            ):
                self.assertEqual(
                    pfade.eigener_datenordner(), pathlib.Path(stick) / "daten"
                )

    def test_nur_lesbares_abbild_weicht_ins_benutzerverzeichnis_aus(self):
        """Genau der Fall aus dem AppImage: Errno 30, Dateisystem nur lesbar."""
        with tempfile.TemporaryDirectory() as heim:
            stick = pathlib.Path(heim) / "nur-lesen"
            stick.mkdir()
            stick.chmod(0o555)
            try:
                umgebung = {
                    "APPIMAGE": str(stick / "Verteilerly.AppImage"),
                    "APPDIR": "/tmp/.mount_x",
                    "XDG_DATA_HOME": str(pathlib.Path(heim) / "share"),
                }
                with mock.patch.dict(os.environ, umgebung), mock.patch.object(
                    pfade, "gepackt", return_value=True
                ):
                    ziel = pfade.eigener_datenordner()
            finally:
                stick.chmod(0o755)
            self.assertEqual(
                ziel, pathlib.Path(heim) / "share" / "verteilerly" / "daten"
            )

    def test_benutzerordner_wird_auch_gelesen(self):
        with tempfile.TemporaryDirectory() as heim:
            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": heim}):
                self.assertIn(
                    pathlib.Path(heim) / "verteilerly" / "daten", pfade._kandidaten()
                )

    def test_unterordner_nimmt_den_ort_der_ihn_hat(self):
        """Ein halb gefüllter Benutzerordner darf die Kabeltypen nicht verdecken."""
        with tempfile.TemporaryDirectory() as heim:
            (pathlib.Path(heim) / "verteilerly" / "daten" / "vorlagen").mkdir(parents=True)
            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": heim}):
                self.assertTrue(pfade.kabeltypenordner().is_dir())
                self.assertIn("standard.yaml", [d.name for d in pfade.kabeltypenordner().iterdir()])


if __name__ == "__main__":
    unittest.main()
