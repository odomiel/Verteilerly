"""Tests zum Paket aus Vorlagen und Einstellungen."""

import json
import pathlib
import tempfile
import unittest
import zipfile

from verteilerly import paket


class TestPaket(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.wurzel = pathlib.Path(self.ordner.name)

        self.daten = self.wurzel / "daten"
        for unter, name in (("vorlagen", "eigen.yaml"),
                            ("blattvorlagen", "eng.yaml"),
                            ("kabeltypen", "hausmarke.yaml")):
            (self.daten / unter).mkdir(parents=True, exist_ok=True)
            (self.daten / unter / name).write_text(
                f"id: {name[:-5]}\nname: Probe\n", encoding="utf-8"
            )
        (self.daten / "vorlagen" / "notiz.txt").write_text("kein YAML", encoding="utf-8")

        self.conf = self.wurzel / "Verteilerly.conf"
        self.conf.write_text("[briefkopf]\nfirma=Musterfirma\n", encoding="utf-8")
        self.ziel = self.wurzel / "paket.zip"

    def test_sichern_nimmt_die_yaml_dateien_und_die_conf(self):
        bericht = paket.sichern(self.ziel, self.daten, self.conf)
        self.assertEqual(bericht["vorlagen"], 1)
        self.assertEqual(bericht["blattvorlagen"], 1)
        self.assertEqual(bericht["kabeltypen"], 1)
        self.assertEqual(bericht["einstellungen"], 1)

        with zipfile.ZipFile(self.ziel) as datei:
            namen = set(datei.namelist())
        self.assertIn("vorlagen/eigen.yaml", namen)
        self.assertIn("Verteilerly.conf", namen)
        self.assertNotIn("vorlagen/notiz.txt", namen)   # nur YAML

    def test_ohne_einstellungen_geht_auch(self):
        bericht = paket.sichern(self.ziel, self.daten)
        self.assertEqual(bericht["einstellungen"], 0)
        self.assertEqual(paket.inhalt(self.ziel)["einstellungen"], 0)

    def test_hin_und_zurueck(self):
        paket.sichern(self.ziel, self.daten, self.conf)

        neu = self.wurzel / "anderswo"
        conf_neu = self.wurzel / "anderswo.conf"
        bericht = paket.einspielen(self.ziel, neu, conf_neu)

        self.assertEqual(bericht["vorlagen"], 1)
        self.assertEqual(
            (neu / "vorlagen" / "eigen.yaml").read_text(encoding="utf-8"),
            (self.daten / "vorlagen" / "eigen.yaml").read_text(encoding="utf-8"),
        )
        self.assertIn("Musterfirma", conf_neu.read_text(encoding="utf-8"))

    def test_gleichnamiges_wird_ersetzt_fremdes_bleibt(self):
        paket.sichern(self.ziel, self.daten, self.conf)
        (self.daten / "vorlagen" / "eigen.yaml").write_text("überschrieben\n",
                                                            encoding="utf-8")
        (self.daten / "vorlagen" / "meine.yaml").write_text("bleibt\n", encoding="utf-8")

        paket.einspielen(self.ziel, self.daten, self.conf)
        self.assertIn("id: eigen",
                      (self.daten / "vorlagen" / "eigen.yaml").read_text(encoding="utf-8"))
        self.assertEqual(
            (self.daten / "vorlagen" / "meine.yaml").read_text(encoding="utf-8"), "bleibt\n"
        )

    def test_nur_das_gewaehlte_geht_hinein(self):
        bericht = paket.sichern(
            self.ziel, self.daten, self.conf, {"vorlagen", "kabeltypen"}
        )
        self.assertEqual(bericht["vorlagen"], 1)
        self.assertEqual(bericht["blattvorlagen"], 0)
        self.assertEqual(bericht["einstellungen"], 0)

        with zipfile.ZipFile(self.ziel) as datei:
            namen = set(datei.namelist())
        self.assertNotIn("blattvorlagen/eng.yaml", namen)
        self.assertNotIn("Verteilerly.conf", namen)

    def test_nur_das_gewaehlte_kommt_an(self):
        paket.sichern(self.ziel, self.daten, self.conf)

        neu = self.wurzel / "anderswo"
        conf_neu = self.wurzel / "anderswo.conf"
        bericht = paket.einspielen(self.ziel, neu, conf_neu, {"blattvorlagen"})

        self.assertEqual(bericht["blattvorlagen"], 1)
        self.assertEqual(bericht["vorlagen"], 0)
        self.assertEqual(bericht["einstellungen"], 0)
        self.assertTrue((neu / "blattvorlagen" / "eng.yaml").is_file())
        self.assertFalse((neu / "vorlagen").exists())
        self.assertFalse(conf_neu.exists())

    def test_bestand_zaehlt_den_arbeitsordner(self):
        """Was zur Wahl steht, bevor überhaupt gepackt wird."""
        bericht = paket.bestand(self.daten, self.conf)
        self.assertEqual(bericht["vorlagen"], 1)
        self.assertEqual(bericht["kabeltypen"], 1)
        self.assertEqual(bericht["einstellungen"], 1)
        self.assertEqual(paket.bestand(self.daten)["einstellungen"], 0)
        self.assertEqual(
            paket.bestand(self.wurzel / "leer")["vorlagen"], 0
        )

    def test_inhalt_zeigt_was_drin_ist(self):
        paket.sichern(self.ziel, self.daten, self.conf)
        bericht = paket.inhalt(self.ziel)
        self.assertEqual(bericht["blattvorlagen"], 1)
        self.assertTrue(bericht["version"])
        self.assertTrue(bericht["erstellt"])

    def test_fremdes_archiv_wird_abgewiesen(self):
        fremd = self.wurzel / "fremd.zip"
        with zipfile.ZipFile(fremd, "w") as datei:
            datei.writestr("vorlagen/eigen.yaml", "id: x\n")
        with self.assertRaises(paket.PaketFehler):
            paket.inhalt(fremd)
        with self.assertRaises(paket.PaketFehler):
            paket.einspielen(fremd, self.daten)

    def test_keine_datei_ausserhalb_des_arbeitsordners(self):
        """Ein Paket aus fremder Hand darf nirgendwo sonst schreiben."""
        boese = self.wurzel / "boese.zip"
        with zipfile.ZipFile(boese, "w") as datei:
            datei.writestr(paket.MERKZETTEL, json.dumps({"kennung": paket.KENNUNG}))
            datei.writestr("../../entwischt.yaml", "id: x\n")
            datei.writestr("vorlagen/../../auch.yaml", "id: x\n")
            datei.writestr("/absolut.yaml", "id: x\n")
            datei.writestr("vorlagen/gut.yaml", "id: gut\n")

        ziel = self.wurzel / "ziel"
        bericht = paket.einspielen(boese, ziel)
        self.assertEqual(bericht["vorlagen"], 1)
        self.assertTrue((ziel / "vorlagen" / "gut.yaml").is_file())
        entwischt = list(self.wurzel.rglob("entwischt.yaml")) + \
            list(self.wurzel.rglob("auch.yaml")) + list(self.wurzel.rglob("absolut.yaml"))
        self.assertEqual(entwischt, [])

    def test_kaputte_datei_meldet_sich(self):
        kaputt = self.wurzel / "kaputt.zip"
        kaputt.write_text("kein ZIP", encoding="utf-8")
        with self.assertRaises(paket.PaketFehler):
            paket.inhalt(kaputt)


if __name__ == "__main__":
    unittest.main()
