"""Tests zur Datensuche und zum Arbeitsordner."""

import os
import pathlib
import shutil
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


class TestEinstellungsdatei(unittest.TestCase):
    """Eine Datei an einem bekannten Ort, keine Registry."""

    def test_windows_neben_dem_programm(self):
        with mock.patch.object(pfade.sys, "platform", "win32"):
            self.assertEqual(
                pfade.einstellungsdatei(),
                pfade.programmordner() / "Verteilerly.conf",
            )

    def test_windows_weicht_aus_wenn_dort_nicht_zu_schreiben_ist(self):
        """Im Programmverzeichnis darf nicht immer geschrieben werden."""
        with tempfile.TemporaryDirectory() as ort:
            gesperrt = pathlib.Path(ort) / "programme"
            gesperrt.mkdir()
            gesperrt.chmod(0o555)
            try:
                with mock.patch.object(pfade.sys, "platform", "win32"), \
                     mock.patch.object(pfade, "programmordner", return_value=gesperrt), \
                     mock.patch.dict(os.environ, {"APPDATA": ort}):
                    ziel = pfade.einstellungsdatei()
            finally:
                gesperrt.chmod(0o755)
        self.assertEqual(
            ziel, pathlib.Path(ort) / "Verteilerly" / "Verteilerly.conf"
        )

    def test_linux_bleibt_im_einstellungsordner(self):
        """Genau die Datei, die Qt dort ohnehin angelegt hat."""
        with tempfile.TemporaryDirectory() as heim:
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": heim}), \
                 mock.patch.object(pfade.sys, "platform", "linux"):
                self.assertEqual(
                    pfade.einstellungsdatei(),
                    pathlib.Path(heim) / "Verteilerly" / "Verteilerly.conf",
                )


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
            eigene = pathlib.Path(heim) / "Verteilerly" / "vorlagen"
            eigene.mkdir(parents=True)
            (eigene / "eigen.yaml").write_text(
                "id: eigen\nname: Eigen\nbuchten: 1\n"
                "leisten_je_bucht: 1\nda_je_leiste: 8\n",
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": heim}), \
                 mock.patch.object(pfade.sys, "platform", "linux"):
                self.assertEqual(pfade.vorlagenordner(), eigene)
                self.assertIn(
                    "standard.yaml",
                    [d.name for d in pfade.kabeltypenordner().iterdir()],
                )

    def test_leerer_ordner_verdeckt_die_daten_nicht(self):
        """Ein übriggebliebenes, leeres daten/vorlagen neben der AppImage-Datei.

        Genau das ließ den Probelauf des AppImage-Baus scheitern: der leere
        Ordner gewann, und plötzlich gab es keine einzige Vorlage.
        """
        with tempfile.TemporaryDirectory() as stick:
            leer = pathlib.Path(stick) / "daten" / "vorlagen"
            leer.mkdir(parents=True)
            with mock.patch.dict(
                os.environ, {"APPIMAGE": str(pathlib.Path(stick) / "V.AppImage")}
            ):
                gefunden = pfade.vorlagenordner()
        self.assertNotEqual(gefunden, leer)
        self.assertTrue(any(gefunden.glob("*.yaml")))

    def test_leerer_ordner_gilt_wenn_es_nichts_anderes_gibt(self):
        """Ohne gefüllten Ordner bleibt der leere - sonst gäbe es gar keinen."""
        with tempfile.TemporaryDirectory() as ort:
            leer = pathlib.Path(ort) / "vorlagen"
            leer.mkdir()
            with mock.patch.object(
                pfade, "_kandidaten", return_value=[pathlib.Path(ort)]
            ):
                self.assertEqual(pfade.vorlagenordner(), leer)

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

        # Das Mitgelieferte als Kopie: so lässt sich eine neue Fassung
        # nachstellen, ohne im Quellbaum zu schreiben.
        self.quelle = pathlib.Path(self.ordner.name) / "beiliegend"
        shutil.copytree(pfade.mitgeliefert(), self.quelle)

        for name, wert in (("eigener_datenordner", self.ziel),
                           ("mitgeliefert", self.quelle)):
            setzer = mock.patch.object(pfade, name, return_value=wert)
            setzer.start()
            self.addCleanup(setzer.stop)

    def _neue_fassung(self, unterordner: str, name: str) -> None:
        """Stellt nach, dass eine spätere Programmfassung die Datei ändert."""
        datei = self.quelle / unterordner / name
        datei.write_text(
            datei.read_text(encoding="utf-8") + "\n# neue Fassung\n",
            encoding="utf-8",
        )

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

    def test_unberuehrte_datei_wird_aufgefrischt(self):
        """Eine spätere Fassung darf verbessern, was niemand angefasst hat."""
        pfade.grundausstattung_auslegen()
        datei = self.ziel / "blattvorlagen" / "standard.yaml"
        vorher = datei.read_text(encoding="utf-8")

        # Die mitgelieferte Datei ändert sich - so, wie es eine neue
        # Programmfassung täte.
        self._neue_fassung("blattvorlagen", "standard.yaml")
        aufgefrischt = pfade.grundausstattung_auslegen()

        self.assertEqual([d.name for d in aufgefrischt], ["standard.yaml"])
        self.assertIn("# neue Fassung", datei.read_text(encoding="utf-8"))
        self.assertNotEqual(vorher, datei.read_text(encoding="utf-8"))

    def test_bearbeitete_datei_wird_nicht_aufgefrischt(self):
        """Wer eine Zeile geändert hat, behält sie - auch gegen eine Neufassung."""
        pfade.grundausstattung_auslegen()
        datei = self.ziel / "blattvorlagen" / "standard.yaml"
        datei.write_text("id: standard\nname: Meins\n", encoding="utf-8")

        self._neue_fassung("blattvorlagen", "standard.yaml")
        self.assertEqual(pfade.grundausstattung_auslegen(), [])
        self.assertEqual(
            datei.read_text(encoding="utf-8"), "id: standard\nname: Meins\n"
        )

    def test_ohne_merkzettel_wird_nichts_angetastet(self):
        """Ein Arbeitsordner aus einer Fassung ohne Merkzettel bleibt, wie er ist."""
        pfade.grundausstattung_auslegen()
        (self.ziel / pfade.MERKZETTEL).unlink()
        datei = self.ziel / "blattvorlagen" / "standard.yaml"
        vorher = datei.read_text(encoding="utf-8")

        self._neue_fassung("blattvorlagen", "standard.yaml")
        self.assertEqual(pfade.grundausstattung_auslegen(), [])
        self.assertEqual(datei.read_text(encoding="utf-8"), vorher)

    def test_ohne_mitgeliefertes_passiert_nichts(self):
        with mock.patch.object(pfade, "mitgeliefert", return_value=None):
            self.assertEqual(pfade.grundausstattung_auslegen(), [])


if __name__ == "__main__":
    unittest.main()
