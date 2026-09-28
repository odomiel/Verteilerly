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
        stelle = mock.patch.dict(
            os.environ,
            {
                "XDG_DATA_HOME": str(self.ordner),
                "XDG_CONFIG_HOME": str(self.ordner / "conf"),
            },
        )
        stelle.start()
        self.addCleanup(stelle.stop)

    def test_die_drei_dateien_entstehen(self):
        """Dateityp, Programmeintrag - und die Wahl in der mimeapps.list."""
        geschrieben = verknuepfung.anmelden()
        mime = self.ordner / "mime" / "packages" / "verteilerly.xml"
        desktop = self.ordner / "applications" / "verteilerly.desktop"
        mimeapps = self.ordner / "conf" / "mimeapps.list"
        self.assertTrue(mime.is_file())
        self.assertTrue(desktop.is_file())
        self.assertEqual(geschrieben, [str(mime), str(desktop), str(mimeapps)])
        self.assertIn(
            f"{verknuepfung.MIMETYP}={verknuepfung.DESKTOPDATEI}",
            mimeapps.read_text(encoding="utf-8"),
        )

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
        self.assertEqual(len(geschrieben), 3)
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


class TestVonAussenAufgehoben(unittest.TestCase):
    """Die Dateiverwaltung nimmt ein anderes Programm - wir merken es."""

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
        verknuepfung.anmelden()

    def _mimeapps(self, inhalt: str) -> None:
        datei = self.ordner / "conf" / "mimeapps.list"
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_text(inhalt, encoding="utf-8")

    def test_frisch_angemeldet_ist_alles_in_ordnung(self):
        self.assertTrue(verknuepfung.angemeldet())
        self.assertTrue(verknuepfung.eigene_eintraege())
        self.assertFalse(verknuepfung.aufgehoben())

    def test_ein_anderes_programm_als_vorgabe_faellt_auf(self):
        """Der Fall »Öffnen mit ▸ Immer« - unsere Dateien liegen noch da."""
        self._mimeapps(
            "[Default Applications]\n"
            f"{verknuepfung.MIMETYP}=texteditor.desktop\n"
        )
        self.assertFalse(verknuepfung.angemeldet())
        self.assertTrue(verknuepfung.eigene_eintraege())
        self.assertTrue(verknuepfung.aufgehoben())
        self.assertEqual(verknuepfung.anderes_programm(), "texteditor.desktop")

    def test_eine_weggenommene_zuordnung_faellt_auf(self):
        self._mimeapps(
            "[Removed Associations]\n"
            f"{verknuepfung.MIMETYP}={verknuepfung.DESKTOPDATEI}\n"
        )
        self.assertFalse(verknuepfung.angemeldet())
        self.assertTrue(verknuepfung.aufgehoben())
        # Ein fremdes Programm ist es nicht - es öffnet einfach nichts.
        self.assertEqual(verknuepfung.anderes_programm(), "")

    def test_wieder_angemeldet_ist_wieder_gut(self):
        self._mimeapps(
            "[Default Applications]\n"
            f"{verknuepfung.MIMETYP}=texteditor.desktop\n"
        )
        self.assertTrue(verknuepfung.aufgehoben())
        self._mimeapps(
            "[Default Applications]\n"
            f"{verknuepfung.MIMETYP}={verknuepfung.DESKTOPDATEI}\n"
        )
        self.assertTrue(verknuepfung.angemeldet())
        self.assertFalse(verknuepfung.aufgehoben())

    def test_wieder_anmelden_hebt_den_widerruf_auf(self):
        """Sonst liefe der Rat »unter Tools wieder anmelden« ins Leere."""
        self._mimeapps(
            "[Removed Associations]\n"
            f"{verknuepfung.MIMETYP}={verknuepfung.DESKTOPDATEI}\n"
        )
        self.assertTrue(verknuepfung.aufgehoben())
        verknuepfung.anmelden()
        self.assertTrue(verknuepfung.angemeldet())
        self.assertFalse(verknuepfung.aufgehoben())

    def test_wieder_anmelden_holt_die_vorgabe_zurueck(self):
        """Auch wenn ein anderes Programm als Vorgabe eingetragen war."""
        self._mimeapps(
            "[Default Applications]\n"
            f"{verknuepfung.MIMETYP}=texteditor.desktop\n"
            "text/plain=texteditor.desktop\n"
        )
        verknuepfung.anmelden()
        self.assertTrue(verknuepfung.angemeldet())
        # Was anderen Typen gehört, bleibt unberührt.
        inhalt = (self.ordner / "conf" / "mimeapps.list").read_text(
            encoding="utf-8"
        )
        self.assertIn("text/plain=texteditor.desktop", inhalt)

    def test_ohne_eigene_eintraege_ist_nichts_aufgehoben(self):
        """Der erste Start hat nie angemeldet - da fehlt nichts."""
        for datei in verknuepfung._linux_orte():
            datei.unlink()
        self.assertFalse(verknuepfung.eigene_eintraege())
        self.assertFalse(verknuepfung.aufgehoben())


class _Winreg:
    """Eine Registrierung aus einem Dict - damit Windows hier pruefbar ist.

    Der Windows-Weg laesst sich sonst nur auf Windows probieren, und dann
    erst beim Anwender. Nachgebaut ist nur, was ``verknuepfung`` braucht:
    Schluessel oeffnen und einen Wert lesen.
    """

    HKEY_CURRENT_USER = "HKCU"
    HKEY_LOCAL_MACHINE = "HKLM"
    HKEY_CLASSES_ROOT = "HKCR"

    def __init__(self, inhalt: dict, verweigert: bool = False):
        #: {(wurzel, schluessel): {name: wert}}
        self.inhalt = inhalt
        #: Ob das Loeschen abgewiesen wird - so verhaelt sich ein
        #: geschuetzter Schluessel.
        self.verweigert = verweigert

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

    def DeleteKey(self, wurzel, schluessel):      # noqa: N802 - winreg-Name
        for platz in list(self.inhalt):
            w, s = platz
            if w == wurzel and s.lower() == schluessel.lower():
                if self.verweigert:
                    raise PermissionError("nicht erlaubt")
                del self.inhalt[platz]
                return
        raise FileNotFoundError("nicht da")


class TestWindowsZuordnung(unittest.TestCase):
    """Was die Registrierung sagt - nachgestellt, ohne Windows."""

    BEFEHL = r'"C:\Portable\Verteilerly.exe" "%1"'
    EIGEN = r'"C:\Portable\Verteilerly.exe"'

    def _mit(self, inhalt, verweigert=False):
        gefaelscht = _Winreg(inhalt, verweigert)
        self.registrierung = gefaelscht
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

    def test_die_vorgehende_wahl_laesst_sich_aufheben(self):
        """Setzen darf man sie nicht, löschen schon - danach gelten wir."""
        inhalt = self._unsere()
        inhalt[("HKCU", self.USERCHOICE)] = {"ProgId": "Applications\\notepad.exe"}
        self._mit(inhalt)
        self.assertFalse(verknuepfung.angemeldet())
        getan = verknuepfung.wahl_aufheben()
        self.assertEqual(len(getan), 1)
        self.assertIn("UserChoice", getan[0])
        self.assertTrue(verknuepfung.angemeldet())
        self.assertFalse(verknuepfung.aufgehoben())

    def test_ohne_wahl_gibt_es_nichts_aufzuheben(self):
        self._mit(self._unsere())
        self.assertEqual(verknuepfung.wahl_aufheben(), [])

    def test_ein_geschuetzter_schluessel_wird_gemeldet(self):
        inhalt = self._unsere()
        inhalt[("HKCU", self.USERCHOICE)] = {"ProgId": "Applications\\notepad.exe"}
        self._mit(inhalt, verweigert=True)
        with self.assertRaises(VerknuepfungFehler):
            verknuepfung.wahl_aufheben()

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
            with self.assertRaises(VerknuepfungFehler):
                verknuepfung.anmelden()


if __name__ == "__main__":
    unittest.main()
