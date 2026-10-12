"""Das Werkzeug fuer die Releases bei GitHub - ohne Netz geprueft."""

import hashlib
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

    def test_probe_sendet_nichts(self):
        """Sie kommt ohne Token aus - und darf also nichts ansprechen."""
        import io
        import contextlib

        with tempfile.TemporaryDirectory() as ordner:
            datei = pathlib.Path(ordner) / f"Verteilerly-{VERSION}.probe"
            datei.write_bytes(b"Probe")
            ausgabe = io.StringIO()
            with mock.patch.object(
                github_release, "slug_finden",
                side_effect=AssertionError("darf nicht gefragt werden"),
            ), contextlib.redirect_stdout(ausgabe):
                stand = github_release.main(["--probe", str(datei)])
        self.assertEqual(stand, 0)
        self.assertIn("nichts gesendet", ausgabe.getvalue())

    def test_eine_fremde_datei_wird_angemerkt(self):
        import io
        import contextlib

        with tempfile.TemporaryDirectory() as ordner:
            datei = pathlib.Path(ordner) / "ohne-fassung.bin"
            datei.write_bytes(b"x")
            fehlerstrom = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(fehlerstrom):
                github_release.main(["--probe", str(datei)])
        self.assertIn("WARNUNG", fehlerstrom.getvalue())


if __name__ == "__main__":
    unittest.main()
