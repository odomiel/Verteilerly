"""Tests zu den Bauskripten.

Gebaut wird hier nichts - PyInstaller packt den Python, der es aufruft,
und braucht für die .exe Windows. Prüfbar ist trotzdem das Rezept: die
Spec wird mit Attrappen ausgeführt und dann nachgesehen, was bei
PyInstaller angekommen wäre.
"""

# Erst das Paket: es legt Einstellungs- und Arbeitsordner der
# Testreihe um, bevor etwas aus verteilerly Pfade liest.
from . import TESTHEIM  # noqa: F401

import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "werkzeuge"))

from verteilerly.version import VERSION  # noqa: E402


def spec_ausfuehren() -> dict:
    """Führt Verteilerly.spec mit Attrappen aus und fängt die Aufrufe ab."""
    aufrufe: dict = {}

    def analysis(skripte, **kw):
        aufrufe["analysis"] = {"skripte": skripte, **kw}
        return type("A", (), {"pure": [], "zipped_data": [], "scripts": [],
                              "binaries": [], "datas": []})()

    def pyz(*args, **kw):
        return object()

    def exe(*args, **kw):
        aufrufe["exe"] = kw
        return object()

    quelle = (WURZEL / "Verteilerly.spec").read_text(encoding="utf-8")
    umgebung = {
        "Analysis": analysis, "PYZ": pyz, "EXE": exe,
        "SPECPATH": str(WURZEL), "__file__": str(WURZEL / "Verteilerly.spec"),
    }
    exec(compile(quelle, "Verteilerly.spec", "exec"), umgebung)   # noqa: S102
    aufrufe["namensraum"] = umgebung
    return aufrufe


class TestSpec(unittest.TestCase):
    """Eine einzelne .exe, ohne Installation."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.aufrufe = spec_ausfuehren()
        except ImportError as fehler:      # PyInstaller nicht vorhanden
            raise unittest.SkipTest(str(fehler)) from None

    def test_version_kommt_aus_der_versionsdatei(self):
        """Die Spec liest sie selbst - ein direkter Aufruf benennt gleich."""
        self.assertEqual(self.aufrufe["namensraum"]["VERSION"], VERSION)

    def test_dateiname_traegt_die_version(self):
        self.assertEqual(self.aufrufe["exe"]["name"], f"Verteilerly_{VERSION}")

    def test_kein_konsolenfenster(self):
        self.assertFalse(self.aufrufe["exe"]["console"])

    def test_symbol_und_versionsangaben(self):
        self.assertTrue(str(self.aufrufe["exe"]["icon"]).endswith("Verteilerly.ico"))
        self.assertTrue(pathlib.Path(self.aufrufe["exe"]["icon"]).is_file())

    def test_gebaut_wird_das_startmodul(self):
        self.assertEqual(
            self.aufrufe["analysis"]["skripte"], ["verteilerly/__main__.py"]
        )

    def test_die_grundausstattung_wandert_mit(self):
        """Vorlagen, Blattvorlagen und Kabeltypen stecken in der Datei."""
        ziele = {ziel for _, ziel in self.aufrufe["analysis"]["datas"]}
        for ordner in ("vorlagen", "kabeltypen", "blattvorlagen"):
            with self.subTest(ordner=ordner):
                self.assertIn(os.path.join("daten", ordner), ziele)
        dateien = [
            pathlib.Path(quelle).name
            for quelle, _ in self.aufrufe["analysis"]["datas"]
        ]
        self.assertIn("40da-4x10.yaml", dateien)

    def test_die_wortlisten_wandern_mit(self):
        """Ohne sie stünde die englische Oberfläche deutsch da."""
        ziele = {ziel for _, ziel in self.aufrufe["analysis"]["datas"]}
        self.assertIn(os.path.join("daten", "sprachen"), ziele)
        dateien = [
            pathlib.Path(quelle).name
            for quelle, _ in self.aufrufe["analysis"]["datas"]
        ]
        self.assertIn("en.yaml", dateien)
        self.assertIn("standard.yaml", dateien)

    def test_die_lizenzen_wandern_mit(self):
        """Was weitergegeben wird, trägt seine Lizenzen bei sich."""
        dateien = {
            pathlib.Path(quelle).name: ziel
            for quelle, ziel in self.aufrufe["analysis"]["datas"]
        }
        self.assertEqual(dateien.get("LICENSE"), ".")
        for name in ("LGPL-3.0.txt", "QUELLEN.txt", "Qt-Fremdbestandteile.txt",
                     "Python-Fremdbestandteile.txt", "reportlab-LICENSE.txt",
                     "pillow-LICENSE.txt", "PyYAML-LICENSE.txt",
                     "openpyxl-LICENCE.rst.txt"):
            with self.subTest(datei=name):
                self.assertEqual(dateien.get(name), "lizenzen")

    def test_das_eigene_paket_wird_vollstaendig_eingesammelt(self):
        versteckt = self.aufrufe["analysis"]["hiddenimports"]
        for modul in ("verteilerly.gui.dialoge", "verteilerly.ausgabe.pdf"):
            with self.subTest(modul=modul):
                self.assertIn(modul, versteckt)

    def test_der_ballast_bleibt_draussen(self):
        heraus = self.aufrufe["analysis"]["excludes"]
        for modul in ("PySide6.QtWebEngineCore", "PySide6.QtQml", "tkinter",
                      "PySide6.QtOpenGL", "PySide6.QtDBus", "PIL._avif",
                      "PIL._webp", "sqlite3"):
            with self.subTest(modul=modul):
                self.assertIn(modul, heraus)
        self.assertNotIn("PySide6.QtWidgets", heraus)

    def test_openssl_kommt_mit(self):
        """Die Nachfrage nach einer neueren Fassung laeuft ueber HTTPS."""
        heraus = self.aufrufe["analysis"]["excludes"]
        for modul in ("_ssl", "_hashlib", "ssl"):
            with self.subTest(modul=modul):
                self.assertNotIn(modul, heraus)

    def test_die_gpl_tastatur_bleibt_draussen(self):
        """Qt Virtual Keyboard steht nur unter der GPL-3 - samt Anhang raus."""
        mitnehmen = self.aufrufe["namensraum"]["mitnehmen"]
        for datei in ("PySide6\\Qt6VirtualKeyboard.dll",
                      "PySide6/plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll",
                      "PySide6/Qt6Quick.dll", "PySide6/Qt6QmlModels.dll",
                      "PySide6/Qt6Network.dll", "PySide6/opengl32sw.dll",
                      "PySide6/plugins/imageformats/qtiff.dll"):
            with self.subTest(weg=datei):
                self.assertFalse(mitnehmen((datei, datei, "BINARY")))
        for datei in ("PySide6\\Qt6Widgets.dll", "PySide6/Qt6Gui.dll",
                      "PySide6/plugins/platforms/qwindows.dll",
                      "PySide6/plugins/styles/qmodernwindowsstyle.dll",
                      "PySide6/plugins/imageformats/qsvg.dll", "python314.dll"):
            with self.subTest(bleibt=datei):
                self.assertTrue(mitnehmen((datei, datei, "BINARY")))

    def test_pillow_bleibt_drin(self):
        """Beim Windows-Build gefunden: ohne Pillow startet die .exe nicht.

        reportlab.lib.colors zieht über reportlab.lib.utils PIL nach - wird
        es ausgeschlossen, bricht der erste Import des Hauptfensters mit
        ModuleNotFoundError ab.
        """
        self.assertNotIn("PIL", self.aufrufe["analysis"]["excludes"])
        self.assertNotIn("Pillow", self.aufrufe["analysis"]["excludes"])

    def test_reportlab_zieht_pillow_wirklich_nach(self):
        """Die Begründung für den Test darüber - nicht nur behauptet."""
        import subprocess

        ergebnis = subprocess.run(
            [sys.executable, "-c",
             "import sys; from reportlab.lib.colors import HexColor;"
             "print(any(m.startswith('PIL') for m in sys.modules))"],
            capture_output=True, text=True, cwd=str(WURZEL),
        )
        self.assertEqual(ergebnis.stdout.strip(), "True", ergebnis.stderr)


class TestPowershellSkript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (WURZEL / "build_windows.ps1").read_text(encoding="utf-8")

    def test_baut_ueber_die_spec(self):
        self.assertIn("PyInstaller --noconfirm", self.text)
        self.assertIn("Verteilerly.spec", self.text)

    def test_prueft_das_ergebnis(self):
        self.assertIn("if (-not (Test-Path $Exe))", self.text)
        self.assertIn("auslieferung\\Verteilerly_$Version.exe", self.text)

    def test_kennt_den_versionsschalter(self):
        self.assertIn("param([switch]$Bump", self.text)
        self.assertIn("release.py --setzen", self.text)

    def test_bricht_bei_fehlern_ab(self):
        self.assertIn('$ErrorActionPreference = "Stop"', self.text)

    def test_probelauf_liest_den_selbstbericht(self):
        self.assertIn("--selbsttest", self.text)
        self.assertIn("ergebnis=ok", self.text)


class TestWindowsangaben(unittest.TestCase):
    def test_versionsdatei_traegt_die_fassung(self):
        import windowsangaben

        with tempfile.TemporaryDirectory() as ordner:
            datei = windowsangaben.schreiben(pathlib.Path(ordner) / "version.txt")
            inhalt = datei.read_text(encoding="utf-8")
        self.assertIn(f"'FileVersion', '{VERSION}'", inhalt)
        self.assertIn(f"Verteilerly_{VERSION}.exe", inhalt)
        self.assertRegex(inhalt, r"filevers=\(2026, \d+, \d+, \d+\)")


class TestSelbstbericht(unittest.TestCase):
    """Den liest der Probelauf des Bauskripts."""

    def test_startmodul_nutzt_absolute_importe(self):
        """Beim Windows-Build gefunden: relative Importe tragen im Bundle nicht.

        PyInstaller startet __main__.py als Skript, nicht als Teil des
        Pakets - „from .pfade import …“ scheitert dann.
        """
        quelle = (WURZEL / "verteilerly" / "__main__.py").read_text(encoding="utf-8")
        self.assertNotIn("from .", quelle)
        self.assertIn("from verteilerly import pfade", quelle)

    def test_bericht_nennt_fassung_und_bestand(self):
        with tempfile.TemporaryDirectory() as ordner:
            ziel = pathlib.Path(ordner) / "bericht.txt"
            umgebung = dict(os.environ, QT_QPA_PLATFORM="offscreen")
            ergebnis = subprocess.run(
                [sys.executable, "-m", "verteilerly", "--selbsttest", str(ziel)],
                cwd=str(WURZEL), env=umgebung, capture_output=True, text=True,
            )
            self.assertEqual(ergebnis.returncode, 0, ergebnis.stderr)
            werte = dict(
                zeile.split("=", 1)
                for zeile in ziel.read_text(encoding="utf-8").splitlines()
                if "=" in zeile
            )
        self.assertEqual(werte["version"], VERSION)
        self.assertEqual(werte["ergebnis"], "ok")
        self.assertGreaterEqual(int(werte["vorlagen"]), 2)
        self.assertGreaterEqual(int(werte["blattvorlagen"]), 3)
        self.assertGreaterEqual(int(werte["kabeltypen"]), 3)


class TestSymbol(unittest.TestCase):
    def test_gpl_bibliotheken_bleiben_draussen(self):
        """readline und gdbm stehen unter der GPL-3 und werden nie benutzt."""
        import appimage

        for name in ("_gdbm", "_dbm", "readline"):
            with self.subTest(modul=name):
                self.assertIn(name, appimage.UNNOETIGE_MODULE)
        for name in ("libgdbm", "libgdbm_compat", "libreadline"):
            with self.subTest(bibliothek=name):
                self.assertIn(name, appimage.UNNOETIGE_BIBLIOTHEKEN)

    def test_ballast_bleibt_draussen(self):
        """Was die Oberfläche nie anfasst, wiegt trotzdem."""
        import appimage

        # Gezeichnet wird mit QPainter - OpenGL verweist nur auf sich selbst.
        self.assertNotIn("OpenGL", appimage.QT_BEHALTEN)
        # Das Programm liest keine Bilddateien.
        self.assertNotIn("imageformats", appimage.PLUGINS_BEHALTEN)
        for werkzeug in ("qmlls", "designer", "assistant", "linguist"):
            with self.subTest(werkzeug=werkzeug):
                self.assertIn(werkzeug, appimage.QT_WERKZEUGE)
        for muster in ("PIL/_avif.*.so", "pillow.libs/libavif-*.so*"):
            with self.subTest(muster=muster):
                self.assertIn(muster, appimage.PILLOW_WEG)

    def test_der_kern_von_pillow_bleibt(self):
        """Ohne PIL._imaging lässt sich reportlab nicht importieren."""
        import appimage

        gefahr = [m for m in appimage.PILLOW_WEG if "_imaging." in m]
        self.assertEqual(gefahr, [])
        self.assertNotIn("pillow.libs/libjpeg-*.so*", appimage.PILLOW_WEG)

    def test_openssl_kommt_mit_sqlite_nicht(self):
        """Seit der Updatepruefung braucht das Programm HTTPS.

        Eine Datenbank dagegen fuehrt es weiterhin nicht: ein Verteiler
        ist eine Datei.
        """
        import appimage

        for modul in ("_ssl", "_hashlib"):
            with self.subTest(modul=modul):
                self.assertNotIn(modul, appimage.UNNOETIGE_MODULE)
        for lib in ("libcrypto", "libssl"):
            with self.subTest(bibliothek=lib):
                self.assertNotIn(lib, appimage.UNNOETIGE_BIBLIOTHEKEN)
        self.assertIn("_sqlite3", appimage.UNNOETIGE_MODULE)
        self.assertIn("libsqlite3", appimage.UNNOETIGE_BIBLIOTHEKEN)

    def test_certifi_bleibt_trotzdem_draussen(self):
        """Geprueft wird gegen den Zertifikatspeicher des Rechners.

        Ein eigener Satz Wurzelzertifikate im Abbild veraltete und
        muesste gepflegt werden - certifi steht ausserdem unter der
        MPL-2.0.
        """
        import appimage

        self.assertIn("certifi", appimage.BASIS_WEG)

    def test_was_die_python_basis_mitbringt_bleibt_draussen(self):
        """certifi steht unter der MPL-2.0 und wird nie gebraucht."""
        import appimage

        for name in ("pip", "certifi", "build", "packaging", "pyproject_hooks",
                     "sitecustomize"):
            with self.subTest(paket=name):
                self.assertIn(name, appimage.BASIS_WEG)
        self.assertIn("reportlab/fonts", appimage.REPORTLAB_WEG)
        self.assertIn("_curses", appimage.UNNOETIGE_MODULE)
        for lib in ("libncursesw", "libtinfo", "libXft", "libXrender"):
            with self.subTest(bibliothek=lib):
                self.assertIn(lib, appimage.UNNOETIGE_BIBLIOTHEKEN)

    def test_ohne_strip_wird_trotzdem_gebaut(self):
        import appimage

        with mock.patch.object(appimage.shutil, "which", return_value=None):
            self.assertEqual(appimage.symbole_strippen(), 0)

    def test_das_abbild_traegt_die_lizenzen(self):
        import appimage

        self.assertEqual(appimage.LIZENZEN.name, "lizenzen")
        self.assertTrue((appimage.LIZENZEN / "QUELLEN.txt").is_file())
        self.assertTrue((appimage.WURZEL / "LICENSE").is_file())

    def test_symboldatei_liegt_bei(self):
        """Die Spec nimmt sie nur, wenn sie da ist."""
        self.assertTrue((WURZEL / "assets" / "Verteilerly.ico").is_file())


if __name__ == "__main__":
    unittest.main()


class TestLizenztexte(unittest.TestCase):
    """Die Lizenzdateien der Pakete kommen als flache Texte mit."""

    def test_die_pakete_bringen_ihre_texte(self):
        import lizenztexte

        namen = [name for name, _ in lizenztexte.pakettexte()]
        for name in ("reportlab-LICENSE.txt", "pillow-LICENSE.txt",
                     "PyYAML-LICENSE.txt", "openpyxl-LICENCE.rst.txt",
                     "charset-normalizer-LICENSE.txt"):
            with self.subTest(datei=name):
                self.assertIn(name, namen)
        self.assertEqual(len(namen), len(set(namen)))

    def test_jede_quelle_ist_eine_datei(self):
        import lizenztexte

        for name, quelle in lizenztexte.pakettexte():
            with self.subTest(datei=name):
                self.assertTrue(quelle.is_file())
                self.assertTrue(name.endswith(".txt"))

    def test_die_python_lizenz_nimmt_die_erste_vorhandene(self):
        import lizenztexte

        with tempfile.TemporaryDirectory() as ordner:
            da = pathlib.Path(ordner) / "LICENSE.txt"
            da.write_text("PSF", encoding="utf-8")
            fehlt = pathlib.Path(ordner) / "fehlt.txt"
            self.assertEqual(lizenztexte.python_lizenz([fehlt, da]), da)
            self.assertIsNone(lizenztexte.python_lizenz([fehlt]))

    def test_die_qt_liste_passt_zur_qt_fassung(self):
        """Nach einem Qt-Wechsel: werkzeuge/qt_fremdbestandteile.py aufrufen."""
        from PySide6.QtCore import qVersion

        text = (WURZEL / "lizenzen" / "Qt-Fremdbestandteile.txt").read_text(encoding="utf-8")
        treffer = re.search(r"^Qt-Fassung: (\d+\.\d+)", text, re.MULTILINE)
        self.assertIsNotNone(treffer)
        self.assertEqual(treffer.group(1), ".".join(qVersion().split(".")[:2]))
        # Was in Core, Gui und Widgets steckt, steht immer darin. XSVG
        # stand hier bis Qt 6.11: in qtsvg 6.12 gibt es keine einzige
        # qt_attribution.json mehr, die Komponente ist aus dem Modul
        # verschwunden - geprueft am Quelltext, nicht geraten.
        for teil in ("PCRE2", "HarfBuzz-NG", "LibJPEG-turbo", "Freetype 2"):
            with self.subTest(teil=teil):
                self.assertIn(teil, text)


class TestAbhaengigkeitspruefung(unittest.TestCase):
    """Der erste Bau des Tages sieht nach neueren Fassungen."""

    def setUp(self):
        import abhaengigkeiten

        self.modul = abhaengigkeiten
        self.ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self.ordner.cleanup)
        self.merkzettel = pathlib.Path(self.ordner.name) / ".geprueft.json"

    def test_die_pakete_kommen_aus_requirements(self):
        """Eine Quelle, keine zweite Liste, die veraltet."""
        namen = self.modul.gefordert()
        for paket in ("PySide6", "reportlab", "openpyxl", "PyYAML", "pyinstaller"):
            with self.subTest(paket=paket):
                self.assertIn(paket, namen)

    def test_kein_paket_steht_zweimal_da(self):
        namen = self.modul.gefordert()
        self.assertEqual(len(namen), len(set(namen)))

    def test_eine_fehlende_liste_stoert_nicht(self):
        with mock.patch.object(
            self.modul, "ANFORDERUNGEN",
            (pathlib.Path(self.ordner.name) / "gibtsnicht.txt",),
        ):
            self.assertEqual(self.modul.gefordert(), [])

    def test_kommentare_und_bedingungen_fallen_weg(self):
        datei = pathlib.Path(self.ordner.name) / "r.txt"
        datei.write_text(
            "# Kopfzeile\nPySide6>=6.9      # LGPLv3\n\nreportlab>=4.2\n",
            encoding="utf-8",
        )
        self.assertEqual(self.modul.gefordert(datei), ["PySide6", "reportlab"])

    def test_fassungen_werden_der_reihe_nach_verglichen(self):
        self.assertTrue(self.modul.veraltet("6.9.1", "6.11.2"))
        self.assertTrue(self.modul.veraltet("6.22.2", "6.22.3"))
        self.assertFalse(self.modul.veraltet("6.11.2", "6.11.2"))
        self.assertFalse(self.modul.veraltet("6.11.2", "6.9.1"))

    def test_unvergleichbares_gilt_nicht_als_veraltet(self):
        """Lieber nichts melden als Unsinn melden."""
        self.assertFalse(self.modul.veraltet("", "6.11.2"))
        self.assertFalse(self.modul.veraltet("6.11.2", ""))
        self.assertFalse(self.modul.veraltet("1.0", "1.0rc1"))

    def test_ohne_netz_wird_gemeldet_statt_abgebrochen(self):
        """Gebaut wird auch im Keller."""
        import urllib.error

        with mock.patch.object(
            self.modul.urllib.request, "urlopen",
            side_effect=urllib.error.URLError("kein Netz"),
        ):
            self.assertEqual(self.modul.neueste("PySide6"), "")
        stand = [("PySide6", "6.11.2", "")]
        self.assertIn("PyPI nicht erreicht", self.modul.bericht(stand))

    def test_der_bericht_nennt_die_neuere_fassung(self):
        stand = [("pyinstaller", "6.22.2", "6.22.3")]
        self.assertIn("neuer: 6.22.3", self.modul.bericht(stand))

    def test_einmal_am_tag(self):
        self.assertFalse(self.modul.schon_geprueft(self.merkzettel))
        self.modul.merken([("PySide6", "6.11.2", "6.11.2")], self.merkzettel)
        self.assertTrue(self.modul.schon_geprueft(self.merkzettel))

    def test_ein_alter_merkzettel_zaehlt_nicht(self):
        self.merkzettel.write_text('{"tag": "1970-01-01"}', encoding="utf-8")
        self.assertFalse(self.modul.schon_geprueft(self.merkzettel))

    def test_ein_kaputter_merkzettel_stoert_nicht(self):
        self.merkzettel.write_text("kein JSON", encoding="utf-8")
        self.assertFalse(self.modul.schon_geprueft(self.merkzettel))

    def _taeglich(self, **kw) -> None:
        """Ruft die Prüfung auf, ohne den Testlauf vollzuschreiben."""
        import contextlib
        import io

        with contextlib.redirect_stdout(io.StringIO()):
            self.modul.taeglich(**kw)

    def test_der_zweite_bau_des_tages_fragt_nicht_noch_einmal(self):
        with mock.patch.object(self.modul, "MERKZETTEL", self.merkzettel), \
             mock.patch.object(self.modul, "pruefen",
                               return_value=[("PySide6", "6.11.2", "6.11.2")]) as gefragt:
            self._taeglich()
            self._taeglich()
        self.assertEqual(gefragt.call_count, 1)

    def test_mit_immer_wird_trotzdem_gefragt(self):
        with mock.patch.object(self.modul, "MERKZETTEL", self.merkzettel), \
             mock.patch.object(self.modul, "pruefen",
                               return_value=[("PySide6", "6.11.2", "6.11.2")]) as gefragt:
            self._taeglich()
            self._taeglich(immer=True)
        self.assertEqual(gefragt.call_count, 2)

    # -- Der Unterbau des AppImage ------------------------------------

    def test_die_eingebaute_python_fassung_kommt_aus_dem_bauskript(self):
        """Eine Quelle: was appimage.py holt, ist die geprüfte Fassung."""
        import appimage

        fassung = self.modul.python_basis()
        self.assertTrue(fassung.startswith(appimage.PYTHONFASSUNG + "."), fassung)
        self.assertIn(fassung, appimage.BASIS_URL)

    def test_ohne_bauskript_wird_nichts_behauptet(self):
        fehlt = pathlib.Path(self.ordner.name) / "gibtsnicht.py"
        self.assertEqual(self.modul.python_basis(fehlt), "")

    def test_nur_abbilder_derselben_bauart_zaehlen(self):
        """manylinux2014 und kein Free-threaded-Bau - sonst fehlt Qt."""
        ausgaben = [{"assets": [
            {"name": "python3.14.8-cp314-cp314-manylinux2014_x86_64.AppImage"},
            {"name": "python3.15.0-cp315-cp315-manylinux_2_28_x86_64.AppImage"},
            {"name": "python3.14.9-cp314-cp314t-manylinux2014_x86_64.AppImage"},
            {"name": "python3.14.8-cp314-cp314-manylinux2014_aarch64.AppImage"},
            {"name": "irgendwas.tar.gz"},
        ]}]
        with mock.patch.object(self.modul, "urllib") as netz:
            netz.request.urlopen.return_value.__enter__.return_value.read.return_value = (
                json.dumps(ausgaben).encode("utf-8")
            )
            self.assertEqual(self.modul.python_abbilder(), ["3.14.8"])

    def test_die_neueste_steht_vorn(self):
        ausgaben = [{"assets": [
            {"name": f"python{f}-cp314-cp314-manylinux2014_x86_64.AppImage"}
            for f in ("3.13.15", "3.14.10", "3.14.9")
        ]}]
        with mock.patch.object(self.modul, "urllib") as netz:
            netz.request.urlopen.return_value.__enter__.return_value.read.return_value = (
                json.dumps(ausgaben).encode("utf-8")
            )
            self.assertEqual(
                self.modul.python_abbilder(), ["3.14.10", "3.14.9", "3.13.15"]
            )

    def test_github_verlangt_eine_kennung(self):
        """Ohne User-Agent käme 403 zurück."""
        with mock.patch.object(self.modul.urllib.request, "urlopen") as ruf:
            ruf.return_value.__enter__.return_value.read.return_value = b"[]"
            self.modul.python_abbilder()
        anfrage = ruf.call_args[0][0]
        # urllib schreibt die Kopfzeilen als "User-agent" fort.
        self.assertTrue(anfrage.has_header("User-agent"), anfrage.headers)
        self.assertIn("Verteilerly", anfrage.get_header("User-agent"))

    def _python_stand(self, hier, alle):
        with mock.patch.object(self.modul, "python_basis", return_value=hier), \
             mock.patch.object(self.modul, "python_abbilder", return_value=alle):
            return self.modul.python_pruefen()

    def test_eine_neue_ausgabe_derselben_reihe_wird_gemeldet(self):
        stand = self._python_stand("3.14.7", ["3.14.8", "3.14.7", "3.13.15"])
        self.assertEqual(stand[:2], ("3.14.7", "3.14.8"))
        self.assertIn("neuer: 3.14.8", self.modul.python_bericht(stand))

    def test_eine_neue_reihe_wird_getrennt_genannt(self):
        """3.13 → 3.14 ist keine Kleinigkeit: die Räder müssen mit."""
        stand = self._python_stand("3.13.15", ["3.14.8", "3.13.15"])
        zeile = self.modul.python_bericht(stand)
        self.assertIn("aktuell", zeile)
        self.assertIn("neue Reihe: 3.14.8", zeile)

    def test_die_aktuelle_fassung_meldet_nichts(self):
        stand = self._python_stand("3.14.8", ["3.14.8", "3.13.15"])
        self.assertEqual(self.modul.python_bericht(stand).split()[-1], "aktuell")

    def test_ohne_github_wird_gemeldet_statt_abgebrochen(self):
        import urllib.error

        with mock.patch.object(
            self.modul.urllib.request, "urlopen",
            side_effect=urllib.error.URLError("kein Netz"),
        ):
            self.assertEqual(self.modul.python_abbilder(), [])
        stand = self._python_stand("3.14.7", [])
        self.assertIn("GitHub nicht erreicht", self.modul.python_bericht(stand))

    def test_der_merkzettel_haelt_auch_das_python_fest(self):
        self.modul.merken(
            [("PySide6", "6.11.2", "6.11.2")], self.merkzettel,
            python=("3.14.7", "3.14.8", "3.14.8"),
        )
        notiz = json.loads(self.merkzettel.read_text(encoding="utf-8"))
        self.assertEqual(notiz["python"]["hier"], "3.14.7")
        self.assertEqual(notiz["python"]["reihe"], "3.14.8")

    def test_die_taegliche_pruefung_nennt_das_abbild_python(self):
        import contextlib
        import io

        gedruckt = io.StringIO()
        with mock.patch.object(self.modul, "MERKZETTEL", self.merkzettel), \
             mock.patch.object(self.modul, "pruefen",
                               return_value=[("PySide6", "6.11.2", "6.11.2")]), \
             mock.patch.object(self.modul, "python_pruefen",
                               return_value=("3.14.7", "3.14.8", "3.14.8")), \
             contextlib.redirect_stdout(gedruckt):
            self.modul.taeglich()
        text = gedruckt.getvalue()
        self.assertIn("Python (Abbild)", text)
        self.assertIn("neuer: 3.14.8", text)
        self.assertIn("PYTHONFASSUNG und BASIS_URL", text)

    def test_bei_leise_meldet_sich_nur_das_neue_python(self):
        """Auch wenn die Pakete aktuell sind, soll das Abbild auffallen."""
        import contextlib
        import io

        gedruckt = io.StringIO()
        with mock.patch.object(self.modul, "MERKZETTEL", self.merkzettel), \
             mock.patch.object(self.modul, "pruefen",
                               return_value=[("PySide6", "6.11.2", "6.11.2")]), \
             mock.patch.object(self.modul, "python_pruefen",
                               return_value=("3.13.15", "3.13.15", "3.14.8")), \
             contextlib.redirect_stdout(gedruckt):
            self.modul.taeglich(leise=True)
        self.assertIn("neue Reihe: 3.14.8", gedruckt.getvalue())

    def test_bauen_ruft_die_pruefung_auf(self):
        quelle = (WURZEL / "werkzeuge" / "bauen.py").read_text(encoding="utf-8")
        self.assertIn("abhaengigkeiten.taeglich()", quelle)
        self.assertIn("--ohne-pruefung", quelle)
