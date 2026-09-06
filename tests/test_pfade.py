"""Tests zur Datensuche und zum Arbeitsordner."""

import os
import pathlib
import tempfile
import unittest
from unittest import mock

from verteilerly import pfade


class TestArbeitsordner(unittest.TestCase):
    """Wohin eigene Vorlagen und Kabeltypen gehören."""

    def test_linux_neben_die_einstellungen(self):
        """Dorthin, wo auch die Verteilerly.conf liegt."""
        with tempfile.TemporaryDirectory() as heim:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": heim}), \
                 mock.patch.object(pfade.sys, "platform", "linux"):
                self.assertEqual(
                    pfade.benutzerdatenordner(), pathlib.Path(heim) / "Verteilerly"
                )
                self.assertEqual(
                    pfade.benutzerdatenordner(), pfade.einstellungsordner()
                )

    def test_windows_neben_das_programm(self):
        """Eine Datei, ein Ordner - der Stick bleibt vollständig."""
        with mock.patch.object(pfade.sys, "platform", "win32"):
            self.assertEqual(
                pfade.benutzerdatenordner(),
                pfade.programmordner() / pfade.DATENORDNER,
            )

    def test_geschrieben_wird_in_den_arbeitsordner(self):
        with tempfile.TemporaryDirectory() as heim:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": heim}), \
                 mock.patch.object(pfade.sys, "platform", "linux"):
                self.assertEqual(
                    pfade.eigener_vorlagenordner(),
                    pathlib.Path(heim) / "Verteilerly" / "vorlagen",
                )

    def test_nur_lesbarer_arbeitsordner_weicht_aus(self):
        """Lässt sich dort nicht schreiben, geht es neben das Programm."""
        with tempfile.TemporaryDirectory() as heim:
            gesperrt = pathlib.Path(heim) / "gesperrt"
            gesperrt.mkdir()
            gesperrt.chmod(0o555)
            try:
                with mock.patch.object(
                    pfade, "benutzerdatenordner", return_value=gesperrt / "Verteilerly"
                ), mock.patch.dict(os.environ, {}, clear=True):
                    ziel = pfade.eigener_datenordner()
            finally:
                gesperrt.chmod(0o755)
        self.assertEqual(ziel, pfade.programmordner() / pfade.DATENORDNER)


class TestDatensuche(unittest.TestCase):
    def test_quellbaum_wird_gefunden(self):
        self.assertTrue(pfade.vorlagenordner().is_dir())
        self.assertTrue(pfade.kabeltypenordner().is_dir())

    def test_mitgeliefertes_ist_der_quellbaum(self):
        self.assertEqual(
            pfade.mitgeliefert(),
            pathlib.Path(pfade.__file__).resolve().parent.parent / "daten",
        )

    def test_ordner_neben_der_appimage_datei_geht_vor(self):
        """Ein daten-Ordner neben der Datei ist eine Ansage."""
        with mock.patch.dict(os.environ, {"APPIMAGE": "/stick/Verteilerly.AppImage"}):
            self.assertEqual(pfade.appimage(), pathlib.Path("/stick"))
            self.assertEqual(pfade._kandidaten()[0], pathlib.Path("/stick/daten"))

    def test_arbeitsordner_steht_vor_dem_mitgelieferten(self):
        orte = pfade._kandidaten()
        self.assertLess(
            orte.index(pfade.benutzerdatenordner()), orte.index(pfade.mitgeliefert())
        )

    def test_appdir_traegt_die_mitgelieferten_daten(self):
        with tempfile.TemporaryDirectory() as ort:
            (pathlib.Path(ort) / "daten").mkdir()
            with mock.patch.dict(os.environ, {"APPDIR": ort}):
                self.assertEqual(pfade.mitgeliefert(), pathlib.Path(ort) / "daten")

    def test_unterordner_nimmt_den_ort_der_ihn_hat(self):
        """Ein halb gefüllter Arbeitsordner darf die Kabeltypen nicht verdecken."""
        with tempfile.TemporaryDirectory() as heim:
            (pathlib.Path(heim) / "Verteilerly" / "vorlagen").mkdir(parents=True)
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": heim}), \
                 mock.patch.object(pfade.sys, "platform", "linux"):
                self.assertEqual(
                    pfade.vorlagenordner(), pathlib.Path(heim) / "Verteilerly" / "vorlagen"
                )
                self.assertIn(
                    "standard.yaml",
                    [d.name for d in pfade.kabeltypenordner().iterdir()],
                )

    def test_fehlermeldung_nennt_die_gesuchten_orte(self):
        with mock.patch.object(pfade, "_kandidaten", return_value=[pathlib.Path("/nix")]):
            with self.assertRaises(FileNotFoundError) as fehler:
                pfade.datenordner()
        self.assertIn("/nix", str(fehler.exception))


class TestGrundausstattung(unittest.TestCase):
    """Beim ersten Start wird das Mitgelieferte ausgelegt."""

    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.ziel = pathlib.Path(self.ordner.name) / "Verteilerly"
        self.zielsetzer = mock.patch.object(
            pfade, "eigener_datenordner", return_value=self.ziel
        )
        self.zielsetzer.start()
        self.addCleanup(self.zielsetzer.stop)

    def test_vorlagen_und_kabeltypen_landen_im_arbeitsordner(self):
        angelegt = pfade.grundausstattung_auslegen()
        self.assertTrue(angelegt)
        self.assertTrue((self.ziel / "vorlagen" / "40da-4x10.yaml").is_file())
        self.assertTrue((self.ziel / "kabeltypen" / "standard.yaml").is_file())

    def test_zweiter_start_legt_nichts_nach(self):
        pfade.grundausstattung_auslegen()
        self.assertEqual(pfade.grundausstattung_auslegen(), [])

    def test_eigene_aenderungen_bleiben(self):
        """Eine bearbeitete Vorlage darf nicht überschrieben werden."""
        pfade.grundausstattung_auslegen()
        datei = self.ziel / "vorlagen" / "40da-4x10.yaml"
        datei.write_text("id: eigen\nname: Eigen\nbuchten: 1\n"
                         "leisten_je_bucht: 1\nda_je_leiste: 8\n", encoding="utf-8")
        pfade.grundausstattung_auslegen()
        self.assertIn("id: eigen", datei.read_text(encoding="utf-8"))

    def test_fehlende_datei_kommt_nach(self):
        """Eine spätere Fassung bringt ihre neuen Dateien mit."""
        pfade.grundausstattung_auslegen()
        (self.ziel / "vorlagen" / "40da-4x10.yaml").unlink()
        angelegt = pfade.grundausstattung_auslegen()
        self.assertEqual([d.name for d in angelegt], ["40da-4x10.yaml"])

    def test_ohne_mitgeliefertes_passiert_nichts(self):
        with mock.patch.object(pfade, "mitgeliefert", return_value=None):
            self.assertEqual(pfade.grundausstattung_auslegen(), [])


if __name__ == "__main__":
    unittest.main()
