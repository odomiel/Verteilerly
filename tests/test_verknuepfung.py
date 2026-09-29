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
    """Worauf die Zuordnung zeigt - und ob das dieses Programm ist.

    Geschrieben wird hier von Hand: das Programm traegt nichts mehr ein,
    es liest nur. Also legt der Test hin, was eine Dateiverwaltung
    hinterlaesst - Dateityp, Programmeintrag, Wahl des Anwenders.
    """

    def setUp(self):
        self._ordner = tempfile.TemporaryDirectory()
        self.addCleanup(self._ordner.cleanup)
        self.ordner = pathlib.Path(self._ordner.name)
        stelle = mock.patch.dict(
            os.environ,
            {
                "XDG_DATA_HOME": str(self.ordner / "share"),
                "XDG_CONFIG_HOME": str(self.ordner / "conf"),
            },
        )
        stelle.start()
        self.addCleanup(stelle.stop)

    def _eintragen(self, befehl=None, vorgabe=None, weggenommen=False):
        """Legt Dateityp, Programmeintrag und Wahl an - wie ein System es tut."""
        mime, desktop = verknuepfung._linux_orte()
        mime.parent.mkdir(parents=True, exist_ok=True)
        mime.write_text("<mime-info/>", encoding="utf-8")
        desktop.parent.mkdir(parents=True, exist_ok=True)
        desktop.write_text(
            "[Desktop Entry]\nType=Application\nName=Verteilerly\n"
            f"Exec={befehl or verknuepfung.aufruf()} %f\n"
            f"MimeType={verknuepfung.MIMETYP};\n",
            encoding="utf-8",
        )
        if vorgabe or weggenommen:
            datei = self.ordner / "conf" / "mimeapps.list"
            datei.parent.mkdir(parents=True, exist_ok=True)
            abschnitt = (
                "[Removed Associations]" if weggenommen else "[Default Applications]"
            )
            wert = verknuepfung.DESKTOPDATEI if weggenommen else vorgabe
            datei.write_text(
                f"{abschnitt}\n{verknuepfung.MIMETYP}={wert}\n", encoding="utf-8"
            )

    def test_ohne_alles_ist_nichts_eingetragen(self):
        self.assertEqual(verknuepfung.angemeldeter_aufruf(), "")
        self.assertEqual(verknuepfung.anderes_programm(), "")
        self.assertFalse(verknuepfung.angemeldet())
        self.assertFalse(verknuepfung.eigene_eintraege())

    def test_unser_eintrag_gilt_als_verknuepft(self):
        self._eintragen()
        self.assertEqual(verknuepfung.angemeldeter_aufruf(), verknuepfung.aufruf())
        self.assertTrue(verknuepfung.angemeldet())
        self.assertEqual(verknuepfung.anderes_programm(), "")

    def test_ein_fremder_eintrag_wird_als_solcher_gemeldet(self):
        """Der Fall einer tragbaren Ausgabe: eingetragen ist eine andere Datei."""
        self._eintragen(befehl="/stick/VerteilerlyPortable.exe")
        self.assertEqual(
            verknuepfung.angemeldeter_aufruf(), "/stick/VerteilerlyPortable.exe"
        )
        self.assertEqual(
            verknuepfung.anderes_programm(), "/stick/VerteilerlyPortable.exe"
        )
        self.assertFalse(verknuepfung.angemeldet())
        self.assertTrue(verknuepfung.aufgehoben())

    def test_die_wahl_des_anwenders_geht_vor(self):
        self._eintragen(vorgabe="texteditor.desktop")
        self.assertEqual(verknuepfung.anderes_programm(), "texteditor.desktop")
        self.assertFalse(verknuepfung.angemeldet())

    def test_eine_weggenommene_zuordnung_oeffnet_nichts(self):
        self._eintragen(weggenommen=True)
        self.assertEqual(verknuepfung.angemeldeter_aufruf(), verknuepfung.KEINE)
        self.assertFalse(verknuepfung.angemeldet())
        self.assertEqual(verknuepfung.anderes_programm(), "")

    def test_der_platzhalter_gehoert_nicht_zum_befehl(self):
        for befehl, erwartet in (
            ('"C:\\Verteilerly.exe" "%1"', '"C:\\Verteilerly.exe"'),
            ("/stick/Verteilerly %f", "/stick/Verteilerly"),
            ("/stick/Verteilerly %U", "/stick/Verteilerly"),
            ("/stick/Verteilerly", "/stick/Verteilerly"),
        ):
            self.assertEqual(verknuepfung._ohne_platzhalter(befehl), erwartet)


class TestZuVerknuepfen(unittest.TestCase):
    """Welche ausfuehrbare Datei die Dateiverwaltung braucht."""

    def test_aus_dem_quellbaum_ist_nichts_zu_verknuepfen(self):
        self.assertIsNone(verknuepfung.zu_verknuepfen())
        self.assertIsNone(verknuepfung.starter())

    def test_als_appimage_die_abbilddatei(self):
        with mock.patch.dict(os.environ, {"APPIMAGE": "/stick/Verteilerly.AppImage"}):
            self.assertEqual(
                verknuepfung.zu_verknuepfen(),
                pathlib.Path("/stick/Verteilerly.AppImage"),
            )

    def test_als_exe_die_exe(self):
        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        exe = pathlib.Path(ordner.name) / "Verteilerly.exe"
        exe.write_bytes(b"MZ")
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch.object(sys, "frozen", True, create=True), \
             mock.patch.object(sys, "executable", str(exe)):
            self.assertEqual(verknuepfung.zu_verknuepfen(), exe.resolve())

    def test_mit_starter_der_starter(self):
        """PortableApps: der Starter gehört verknüpft, nicht die innere .exe."""
        ordner = tempfile.TemporaryDirectory()
        self.addCleanup(ordner.cleanup)
        grund = pathlib.Path(ordner.name)
        starter = grund / "VerteilerlyPortable.exe"
        starter.write_bytes(b"MZ")
        innen = grund / "App" / "Verteilerly"
        innen.mkdir(parents=True)
        exe = innen / "Verteilerly.exe"
        exe.write_bytes(b"MZ")
        with mock.patch.object(sys, "platform", "win32"), \
             mock.patch.object(sys, "frozen", True, create=True), \
             mock.patch.object(sys, "executable", str(exe)):
            self.assertEqual(verknuepfung.starter(), starter)
            self.assertEqual(verknuepfung.zu_verknuepfen(), starter)


class _Winreg:
    """Eine Registrierung aus einem Dict - damit Windows hier pruefbar ist.

    Der Windows-Weg laesst sich sonst nur auf Windows probieren, und dann
    erst beim Anwender. Nachgebaut ist nur, was ``verknuepfung`` braucht:
    Schluessel oeffnen und einen Wert lesen.
    """

    HKEY_CURRENT_USER = "HKCU"
    HKEY_LOCAL_MACHINE = "HKLM"
    HKEY_CLASSES_ROOT = "HKCR"

    def __init__(self, inhalt: dict):
        #: {(wurzel, schluessel): {name: wert}}
        self.inhalt = inhalt

    class _Offen:
        def __init__(self, werte):
            self.werte = werte

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def OpenKey(self, wurzel, schluessel):        # noqa: N802 - winreg-Name
        for (w, s), werte in self.inhalt.items():
            if w == wurzel and s.lower() == schluessel.lower():
                return self._Offen(werte)
        raise OSError("nicht da")

    def QueryValueEx(self, offen, name):          # noqa: N802 - winreg-Name
        if name not in offen.werte:
            raise OSError("kein Wert")
        return offen.werte[name], 1


class TestWindowsZuordnung(unittest.TestCase):
    """Was die Registrierung sagt - nachgestellt, ohne Windows."""

    BEFEHL = r'"C:\Portable\Verteilerly.exe" "%1"'
    EIGEN = r'"C:\Portable\Verteilerly.exe"'

    def _mit(self, inhalt):
        gefaelscht = _Winreg(inhalt)
        stelle = mock.patch.dict(sys.modules, {"winreg": gefaelscht})
        stelle.start()
        self.addCleanup(stelle.stop)
        plattform = mock.patch.object(sys, "platform", "win32")
        plattform.start()
        self.addCleanup(plattform.stop)
        ruf = mock.patch.object(verknuepfung, "aufruf", lambda: self.EIGEN)
        ruf.start()
        self.addCleanup(ruf.stop)

    #: Unsere Schluessel, wie ``_windows_anmelden`` sie schreibt.
    def _unsere(self):
        kennung = verknuepfung.PROGRAMMKENNUNG
        return {
            ("HKCU", r"Software\Classes\.vtly"): {"": kennung},
            ("HKCU", rf"Software\Classes\{kennung}\shell\open\command"): {
                "": self.BEFEHL
            },
        }

    def test_ohne_wahl_gilt_unsere_zuordnung(self):
        self._mit(self._unsere())
        self.assertEqual(verknuepfung.angemeldeter_aufruf(), self.EIGEN)
        self.assertTrue(verknuepfung.angemeldet())
        self.assertTrue(verknuepfung.eigene_eintraege())
        self.assertFalse(verknuepfung.aufgehoben())
        self.assertEqual(verknuepfung.anderes_programm(), "")

    def test_ohne_alles_ist_nichts_eingetragen(self):
        self._mit({})
        self.assertEqual(verknuepfung.angemeldeter_aufruf(), "")
        self.assertFalse(verknuepfung.angemeldet())
        self.assertFalse(verknuepfung.eigene_eintraege())
        self.assertFalse(verknuepfung.aufgehoben())

    def test_die_wahl_des_anwenders_geht_vor(self):
        """»Öffnen mit ▸ Immer« - unsere Schlüssel stehen unberührt da."""
        inhalt = self._unsere()
        inhalt[
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer"
                     r"\FileExts\.vtly\UserChoice")
        ] = {"ProgId": "Applications\\notepad.exe"}
        inhalt[
            ("HKCU", r"Software\Classes\Applications\notepad.exe\shell\open\command")
        ] = {"": r'"C:\Windows\notepad.exe" "%1"'}
        self._mit(inhalt)
        self.assertEqual(
            verknuepfung.angemeldeter_aufruf(), r'"C:\Windows\notepad.exe"'
        )
        self.assertFalse(verknuepfung.angemeldet())
        self.assertTrue(verknuepfung.eigene_eintraege())
        self.assertTrue(verknuepfung.aufgehoben())
        self.assertIn("notepad", verknuepfung.anderes_programm())

    def test_zeigt_die_wahl_auf_uns_ist_alles_gut(self):
        inhalt = self._unsere()
        inhalt[
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer"
                     r"\FileExts\.vtly\UserChoice")
        ] = {"ProgId": verknuepfung.PROGRAMMKENNUNG}
        self._mit(inhalt)
        self.assertTrue(verknuepfung.angemeldet())
        self.assertFalse(verknuepfung.aufgehoben())

    USERCHOICE = (
        r"Software\Microsoft\Windows\CurrentVersion\Explorer"
        r"\FileExts\.vtly\UserChoice"
    )

    def test_eine_andere_ausgabe_desselben_programms_faellt_auf(self):
        """Die Registrierung zeigt auf eine ältere .exe."""
        inhalt = self._unsere()
        inhalt[
            ("HKCU", rf"Software\Classes\{verknuepfung.PROGRAMMKENNUNG}"
                     r"\shell\open\command")
        ] = {"": r'"C:\Alt\Verteilerly_2026.09.27b5.exe" "%1"'}
        self._mit(inhalt)
        self.assertFalse(verknuepfung.angemeldet())
        self.assertIn("2026.09.27b5", verknuepfung.anderes_programm())


class TestFremdesSystem(unittest.TestCase):
    def test_was_das_programm_nicht_kennt_sagt_es(self):
        with mock.patch.object(sys, "platform", "sunos5"):
            self.assertFalse(verknuepfung.moeglich())
            self.assertFalse(verknuepfung.angemeldet())
            self.assertEqual(verknuepfung.angemeldeter_aufruf(), "")
            self.assertFalse(verknuepfung.eigene_eintraege())


if __name__ == "__main__":
    unittest.main()
