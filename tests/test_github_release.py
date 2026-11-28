"""Das Werkzeug fuer die Releases bei GitHub - ohne Netz geprueft."""

# Erst das Paket: es legt Einstellungs- und Arbeitsordner der
# Testreihe um, bevor etwas aus verteilerly Pfade liest.
from . import TESTHEIM  # noqa: F401

import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "werkzeuge"))

import github_release  # noqa: E402

from verteilerly.version import VERSION  # noqa: E402


class TestFassungUndNotiz(unittest.TestCase):
    """Was das Werkzeug aus dem Repo liest."""

    def test_die_fassung_kommt_aus_der_versionsdatei(self):
        """Gelesen, nicht importiert: das Werkzeug laeuft ohne venv."""
        self.assertEqual(github_release.fassung_lesen(), VERSION)

    def test_der_vorige_tag_ist_der_davor(self):
        vorher = github_release.voriger_tag(VERSION)
        self.assertTrue(vorher)
        self.assertNotEqual(vorher, VERSION)

    def test_die_notiz_nennt_aenderungen_und_pruefsummen(self):
        with tempfile.TemporaryDirectory() as ordner:
            datei = pathlib.Path(ordner) / f"Verteilerly-{VERSION}.probe"
            datei.write_bytes(b"Probe")
            notiz = github_release.notiz_bauen(VERSION, [datei])
        self.assertIn("## Dateien", notiz)
        self.assertIn(datei.name, notiz)
        self.assertIn(hashlib.sha256(b"Probe").hexdigest(), notiz)

    def test_die_release_commits_bleiben_draussen(self):
        """Sie sagen nur, dass eine Fassung gesetzt wurde."""
        notiz = github_release.notiz_bauen(VERSION, [])
        for zeile in notiz.splitlines():
            self.assertFalse(zeile.startswith("* Release "), zeile)

    def test_die_pruefsumme_ist_die_von_hashlib(self):
        with tempfile.NamedTemporaryFile(delete=False) as datei:
            datei.write(b"Verteilerly")
            name = datei.name
        try:
            self.assertEqual(
                github_release.pruefsumme(pathlib.Path(name)),
                hashlib.sha256(b"Verteilerly").hexdigest(),
            )
        finally:
            pathlib.Path(name).unlink()


class TestTextNachziehen(unittest.TestCase):
    """Der Nachtrag: die .exe kommt spaeter ans selbe Release."""

    def setUp(self):
        self.gesendet = []

        def gefangen(art, url, koepfe, inhalt=None, antwortkoepfe=None):
            self.gesendet.append((art, url, inhalt))
            return 200, b"{}"

        self.flicken = mock.patch.object(
            github_release, "_anfrage", side_effect=gefangen
        )
        self.flicken.start()
        self.addCleanup(self.flicken.stop)

    def test_ein_geaenderter_text_wird_geschrieben(self):
        release = {"id": 7, "body": "alt"}
        self.assertTrue(
            github_release.text_nachziehen("wer/was", release, "neu", "tok")
        )
        art, url, inhalt = self.gesendet[0]
        self.assertEqual(art, "PATCH")
        self.assertTrue(url.endswith("/releases/7"))
        self.assertEqual(json.loads(inhalt)["body"], "neu")
        # Der Aufrufer sieht den neuen Stand, ohne noch einmal zu fragen.
        self.assertEqual(release["body"], "neu")

    def test_derselbe_text_kostet_keine_anfrage(self):
        release = {"id": 7, "body": "gleich"}
        self.assertFalse(
            github_release.text_nachziehen("wer/was", release, "gleich", "tok")
        )
        self.assertEqual(self.gesendet, [])

    def test_ein_fehler_bricht_ab_statt_stillzuhalten(self):
        self.flicken.stop()
        with mock.patch.object(
            github_release, "_anfrage", return_value=(403, b"nein")
        ), self.assertRaises(SystemExit):
            github_release.text_nachziehen("wer/was", {"id": 7}, "neu", "tok")
        self.flicken.start()


class TestKennungUndToken(unittest.TestCase):
    """Beides steht ausserhalb des Repos - es wird oeffentlich gespiegelt."""

    def setUp(self):
        self._ordner = tempfile.TemporaryDirectory()
        self.ordner = pathlib.Path(self._ordner.name)
        self.addCleanup(self._ordner.cleanup)
        ersatz = mock.patch.object(github_release, "CONFORDNER", self.ordner)
        ersatz.start()
        self.addCleanup(ersatz.stop)

    def test_aus_der_umgebung(self):
        with mock.patch.dict(
            "os.environ",
            {"VERTEILERLY_GITHUB_SLUG": "eigner/repo", "GITHUB_TOKEN": "gehEIM"},
        ):
            self.assertEqual(github_release.slug_finden(), "eigner/repo")
            self.assertEqual(github_release.token_finden(), "gehEIM")

    def test_aus_der_datei_daneben(self):
        (self.ordner / "github_repo").write_text("eigner/repo\n")
        (self.ordner / "github_token").write_text("gehEIM\n")
        with mock.patch.dict(
            "os.environ", {"VERTEILERLY_GITHUB_SLUG": "", "GITHUB_TOKEN": ""}
        ):
            self.assertEqual(github_release.slug_finden(), "eigner/repo")
            self.assertEqual(github_release.token_finden(), "gehEIM")

    def test_ohne_beides_sagt_es_wo_es_hingehoert(self):
        with mock.patch.dict(
            "os.environ", {"VERTEILERLY_GITHUB_SLUG": "", "GITHUB_TOKEN": ""}
        ):
            with self.assertRaises(SystemExit) as fehler:
                github_release.slug_finden()
            self.assertIn("github_repo", str(fehler.exception))
            with self.assertRaises(SystemExit) as fehler:
                github_release.token_finden()
            self.assertIn("github_token", str(fehler.exception))

    def test_zwei_zeilen_brechen_ab_ohne_den_inhalt(self):
        """Der neue Token unter dem alten: urllib zeigte sonst beide."""
        (self.ordner / "github_token").write_text("altesGEHEIM\nneuesGEHEIM\n")
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": ""}):
            with self.assertRaises(SystemExit) as fehler:
                github_release.token_finden()
        self.assertIn("einen Token in einer Zeile", str(fehler.exception))
        self.assertNotIn("GEHEIM", str(fehler.exception))

    def test_im_quelltext_steht_keine_kennung(self):
        """Das Repo wird oeffentlich gespiegelt - dort gehoert nichts hin."""
        quelle = pathlib.Path(github_release.__file__).read_text(encoding="utf-8")
        self.assertNotIn("github.com/odomiel", quelle)
        for verdacht in ("ghp_", "github_pat_"):
            self.assertNotIn(verdacht, quelle)


class TestKoepfeUndProbe(unittest.TestCase):
    def test_die_koepfe_tragen_token_und_api_fassung(self):
        koepfe = github_release._koepfe("gehEIM", {"Content-Type": "x/y"})
        self.assertEqual(koepfe["Authorization"], "Bearer gehEIM")
        self.assertIn("X-GitHub-Api-Version", koepfe)
        self.assertEqual(koepfe["Content-Type"], "x/y")

    def _probe(self, antwort=(200, b"{}"), name=None, token="gehEIM"):
        """--probe mit untergeschobenem Zugang; gibt (stand, aus, fehler, anfragen)."""
        import io
        import contextlib

        anfragen = []

        def gefangen(art, url, koepfe, inhalt=None, antwortkoepfe=None):
            anfragen.append((art, url))
            if isinstance(antwort, Exception):
                raise antwort
            return antwort

        with tempfile.TemporaryDirectory() as ordner:
            datei = pathlib.Path(ordner) / (name or f"Verteilerly-{VERSION}.probe")
            datei.write_bytes(b"Probe")
            aus, fehler = io.StringIO(), io.StringIO()
            with mock.patch.object(github_release, "slug_finden",
                                   return_value="wer/was"), \
                    mock.patch.object(github_release, "token_finden",
                                      return_value=token), \
                    mock.patch.object(github_release, "_anfrage",
                                      side_effect=gefangen), \
                    contextlib.redirect_stdout(aus), \
                    contextlib.redirect_stderr(fehler):
                stand = github_release.main(["--probe", str(datei)])
        return stand, aus.getvalue(), fehler.getvalue(), anfragen

    def test_probe_fragt_nur_lesend(self):
        """Ein GET aufs Repo - kein Release, kein Anhang."""
        stand, aus, _, anfragen = self._probe()
        self.assertEqual(stand, 0)
        self.assertIn("nichts gesendet", aus)
        self.assertIn("Token gilt", aus)
        self.assertEqual(anfragen, [("GET", f"{github_release.API}/repos/wer/was")])

    def test_probe_meldet_einen_abgewiesenen_token(self):
        """So fiel er am 10.11.2026 erst nach drei Minuten Warten auf."""
        stand, aus, fehler, _ = self._probe(antwort=(401, b"Bad credentials"))
        self.assertEqual(stand, 1)
        self.assertIn("Token abgewiesen", fehler)
        self.assertNotIn("gehEIM", aus + fehler)

    def test_probe_meldet_ein_unsichtbares_repo(self):
        stand, _, fehler, _ = self._probe(antwort=(404, b""))
        self.assertEqual(stand, 1)
        self.assertIn("wer/was", fehler)

    def test_probe_ohne_netz_bricht_nicht_zusammen(self):
        import urllib.error

        stand, _, fehler, _ = self._probe(antwort=urllib.error.URLError("weg"))
        self.assertEqual(stand, 1)
        self.assertIn("nicht erreicht", fehler)

    def test_probe_ohne_token_sagt_es(self):
        import io
        import contextlib

        with tempfile.TemporaryDirectory() as ordner:
            datei = pathlib.Path(ordner) / f"Verteilerly-{VERSION}.probe"
            datei.write_bytes(b"Probe")
            fehler = io.StringIO()
            with mock.patch.object(github_release, "slug_finden",
                                   return_value="wer/was"), \
                    mock.patch.object(github_release, "token_finden",
                                      side_effect=SystemExit("kein github_token")), \
                    mock.patch.object(github_release, "_anfrage",
                                      side_effect=AssertionError("ohne Token nicht")), \
                    contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(fehler):
                stand = github_release.main(["--probe", str(datei)])
        self.assertEqual(stand, 1)
        self.assertIn("github_token", fehler.getvalue())

    def test_der_echte_lauf_wartet_nicht_mit_abgewiesenem_token(self):
        with tempfile.TemporaryDirectory() as ordner:
            datei = pathlib.Path(ordner) / f"Verteilerly-{VERSION}.probe"
            datei.write_bytes(b"Probe")
            with mock.patch.object(github_release, "slug_finden",
                                   return_value="wer/was"), \
                    mock.patch.object(github_release, "token_finden",
                                      return_value="gehEIM"), \
                    mock.patch.object(github_release, "_anfrage",
                                      return_value=(401, b"")), \
                    mock.patch.object(github_release, "auf_tag_warten",
                                      side_effect=AssertionError("nicht warten")), \
                    mock.patch("sys.stdout"), \
                    self.assertRaises(SystemExit) as abbruch:
                github_release.main([str(datei)])
        self.assertIn("Token abgewiesen", str(abbruch.exception))

    def test_eine_fremde_datei_wird_angemerkt(self):
        _, _, fehler, _ = self._probe(name="ohne-fassung.bin")
        self.assertIn("WARNUNG", fehler)


class TestTokenAblauf(unittest.TestCase):
    def setUp(self):
        import datetime

        self.jetzt = datetime.datetime(2026, 11, 28, tzinfo=datetime.timezone.utc)

    def _ablauf(self, wert):
        return github_release.token_ablauf(
            {"github-authentication-token-expiration": wert}
        )

    def test_der_kopf_wird_gelesen_mit_utc_und_versatz(self):
        utc = self._ablauf("2027-10-31 23:00:00 UTC")
        versatz = self._ablauf("2027-11-01 00:00:00 +0100")
        self.assertEqual(utc, versatz)
        self.assertEqual((utc.year, utc.month, utc.day), (2027, 10, 31))

    def test_ohne_oder_mit_unsinn_kein_ablauf(self):
        self.assertIsNone(github_release.token_ablauf({}))
        self.assertIsNone(self._ablauf("bald"))
        self.assertEqual(github_release.ablauf_hinweis(None), "")

    def test_gewarnt_wird_erst_kurz_vorher(self):
        fern = self._ablauf("2027-10-31 23:00:00 UTC")
        nah = self._ablauf("2026-12-10 12:00:00 UTC")
        self.assertEqual(github_release.ablauf_hinweis(fern, self.jetzt), "")
        hinweis = github_release.ablauf_hinweis(nah, self.jetzt)
        self.assertIn("10.12.2026", hinweis)
        self.assertIn("12 Tagen", hinweis)

    def test_die_probe_warnt_vor_dem_ablauf(self):
        import contextlib
        import datetime
        import io

        bald = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=5)

        def gefangen(art, url, koepfe, inhalt=None, antwortkoepfe=None):
            antwortkoepfe["github-authentication-token-expiration"] = (
                f"{bald:%Y-%m-%d %H:%M:%S} UTC"
            )
            return 200, b"{}"

        fehler = io.StringIO()
        with mock.patch.object(github_release, "_anfrage", side_effect=gefangen), \
                contextlib.redirect_stderr(fehler):
            self.assertEqual(github_release.zugang_pruefen("wer/was", "tok"), "")
        self.assertIn("laeuft am", fehler.getvalue())
        self.assertNotIn("tok", fehler.getvalue())



if __name__ == "__main__":
    unittest.main()
