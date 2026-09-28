"""Verteilerly als Programm fuer Projektdateien anmelden.

Ein Doppelklick auf eine Projektdatei soll das Programm oeffnen. Wie das
geht, sagt das Betriebssystem:

* **Linux** fuehrt Dateitypen (shared-mime-info): eine XML sagt, dass
  ``*.vtly`` ein ``application/x-verteilerly-projekt`` ist, ein
  Desktop-Eintrag sagt, wer diesen Typ oeffnet. Beides liegt unter
  ``~/.local/share``, danach werden die Datenbanken aufgefrischt.
* **Windows** fuehrt Endungen in der Registrierung: ``.vtly`` zeigt auf
  eine Programmkennung, und die traegt den Aufrufbefehl. Geschrieben
  wird nur unter ``HKEY_CURRENT_USER`` - das braucht keine
  Verwalterrechte und gilt fuer den angemeldeten Benutzer.

Angemeldet wird **auf Wunsch**, nicht beim Start: ein Programm, das sich
ungefragt in die Dateiverwaltung eintraegt, ist ein schlechter Gast. Und
es wird **nichts geraten**: laeuft das Programm aus dem Quellbaum, steht
der Aufruf mit demselben Python da, mit dem es gerade laeuft.

Dieses Modul kennt kein Qt; die Oberflaeche zeigt nur, was es meldet.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

from .modell import ModellFehler
from .sprachen import u

#: Der Dateityp, unter dem Linux die Projektdatei fuehrt.
MIMETYP = "application/x-verteilerly-projekt"
#: Die Programmkennung in der Windows-Registrierung.
PROGRAMMKENNUNG = "Verteilerly.Projekt"
#: Was doppelt angeklickt werden darf. Die erste ist die, mit der
#: gespeichert wird; die zweite gibt es nur unter Linux - Windows kennt
#: bloss die letzte Endung, und `.json` gehoert nicht uns.
ENDUNGEN = (".vtly", ".vtly.json")
#: Wie die Dateien heissen, die unter Linux angelegt werden.
DESKTOPDATEI = "verteilerly.desktop"
MIMEDATEI = "verteilerly.xml"


class VerknuepfungFehler(ModellFehler):
    """Die Anmeldung liess sich nicht schreiben."""


def aufruf() -> str:
    """Der Befehl, mit dem die Dateiverwaltung das Programm startet.

    Als AppImage die Datei selbst, als .exe das Programm, aus dem
    Quellbaum derselbe Python mit ``-m verteilerly``.
    """
    abbild = os.environ.get("APPIMAGE")
    if abbild:
        return _gequotet(pathlib.Path(abbild).resolve())
    if getattr(sys, "frozen", False):
        return _gequotet(pathlib.Path(sys.executable).resolve())
    return f'{_gequotet(pathlib.Path(sys.executable).resolve())} -m verteilerly'


def _gequotet(pfad: pathlib.Path) -> str:
    """Ein Pfad mit Leerzeichen braucht Anfuehrungszeichen."""
    text = str(pfad)
    return f'"{text}"' if " " in text else text


# -- Linux -----------------------------------------------------------------


def _linux_orte() -> tuple[pathlib.Path, pathlib.Path]:
    grund = pathlib.Path(
        os.environ.get("XDG_DATA_HOME") or pathlib.Path.home() / ".local" / "share"
    )
    return grund / "mime" / "packages" / MIMEDATEI, grund / "applications" / DESKTOPDATEI


def _mime_xml() -> str:
    muster = "\n".join(
        f'    <glob pattern="*{endung}" weight="60"/>' for endung in ENDUNGEN
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">\n'
        f'  <mime-type type="{MIMETYP}">\n'
        "    <comment>Verteilerly-Projekt</comment>\n"
        "    <comment xml:lang=\"en\">Verteilerly project</comment>\n"
        '    <sub-class-of type="application/json"/>\n'
        f"{muster}\n"
        "  </mime-type>\n"
        "</mime-info>\n"
    )


def _desktop_eintrag() -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Verteilerly\n"
        "Comment=Dokumentation für LSA+-Verteiler\n"
        f"Exec={aufruf()} %f\n"
        "Icon=verteilerly\n"
        "Terminal=false\n"
        "Categories=Office;Engineering;\n"
        f"MimeType={MIMETYP};\n"
    )


def symbolort() -> pathlib.Path:
    """Wohin das Sinnbild gehoert, damit die Dateiverwaltung es findet."""
    grund = pathlib.Path(
        os.environ.get("XDG_DATA_HOME") or pathlib.Path.home() / ".local" / "share"
    )
    return grund / "icons" / "hicolor" / "256x256" / "apps" / "verteilerly.png"


def _linux_anmelden(symbol_schreiben=None) -> list[str]:
    mime, desktop = _linux_orte()
    getan = []
    for ziel, inhalt in ((mime, _mime_xml()), (desktop, _desktop_eintrag())):
        try:
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_text(inhalt, encoding="utf-8")
        except OSError as fehler:
            raise VerknuepfungFehler(
                u("{0} liess sich nicht schreiben: {1}").format(ziel, fehler)
            ) from None
        getan.append(str(ziel))
    desktop.chmod(0o755)

    # Das Sinnbild zeichnet die Oberflaeche - dieses Modul kennt kein Qt.
    # Ohne Sinnbild ist der Eintrag trotzdem gueltig, nur grau.
    if symbol_schreiben is not None:
        ziel = symbolort()
        try:
            ziel.parent.mkdir(parents=True, exist_ok=True)
            symbol_schreiben(ziel)
            getan.append(str(ziel))
        except Exception:      # noqa: BLE001 - eine Zugabe, kein Grund zum Abbruch
            pass

    # Die Datenbanken merken die neuen Dateien nicht von selbst. Fehlt
    # ein Werkzeug, ist das kein Grund zum Abbruch: viele Arbeitsplaetze
    # lesen die Dateien beim naechsten Anmelden ohnehin neu ein.
    for befehl in (
        ["update-mime-database", str(mime.parent.parent)],
        ["update-desktop-database", str(desktop.parent)],
        ["xdg-mime", "default", DESKTOPDATEI, MIMETYP],
        ["gtk-update-icon-cache", "-f", "-t", str(symbolort().parents[2])],
    ):
        if shutil.which(befehl[0]) is None:
            continue
        try:
            subprocess.run(befehl, check=False, capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            continue
    return getan


def _linux_angemeldet() -> bool:
    mime, desktop = _linux_orte()
    if not (mime.is_file() and desktop.is_file()):
        return False
    return aufruf() in desktop.read_text(encoding="utf-8", errors="replace")


def _linux_angemeldeter_aufruf() -> str:
    """Womit die Dateiverwaltung gerade oeffnet - laut Desktop-Eintrag."""
    _mime, desktop = _linux_orte()
    try:
        zeilen = desktop.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for zeile in zeilen:
        if zeile.startswith("Exec="):
            return _ohne_platzhalter(zeile[len("Exec="):])
    return ""


# -- Windows ---------------------------------------------------------------


def _windows_anmelden() -> list[str]:
    import winreg

    befehl = f'{aufruf()} "%1"'
    eintraege = (
        (rf"Software\Classes\{ENDUNGEN[0]}", "", PROGRAMMKENNUNG),
        (rf"Software\Classes\{PROGRAMMKENNUNG}", "", "Verteilerly-Projekt"),
        (rf"Software\Classes\{PROGRAMMKENNUNG}\DefaultIcon", "", f"{aufruf()},0"),
        (rf"Software\Classes\{PROGRAMMKENNUNG}\shell\open\command", "", befehl),
    )
    getan = []
    for schluessel, name, wert in eintraege:
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, schluessel) as offen:
                winreg.SetValueEx(offen, name, 0, winreg.REG_SZ, wert)
        except OSError as fehler:
            raise VerknuepfungFehler(
                u("{0} liess sich nicht schreiben: {1}").format(schluessel, fehler)
            ) from None
        getan.append(f"HKCU\\{schluessel}")
    _windows_bescheid_sagen()
    return getan


def _windows_bescheid_sagen() -> None:
    """Sagt der Oberflaeche, dass sich eine Verknuepfung geaendert hat."""
    try:
        import ctypes

        # SHCNE_ASSOCCHANGED, SHCNF_IDLIST
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception:      # noqa: BLE001 - ohne Bescheid wirkt es spaeter
        pass


def _windows_angemeldet() -> bool:
    return aufruf() in _windows_angemeldeter_aufruf()


def _windows_angemeldeter_aufruf() -> str:
    """Womit die Dateiverwaltung gerade oeffnet - laut Registrierung."""
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            rf"Software\Classes\{PROGRAMMKENNUNG}\shell\open\command",
        ) as offen:
            wert, _art = winreg.QueryValueEx(offen, "")
    except OSError:
        return ""
    return _ohne_platzhalter(str(wert))


# -- Nach aussen -----------------------------------------------------------


def moeglich() -> bool:
    """Kennt dieses Betriebssystem einen Weg, den wir gehen koennen?"""
    return sys.platform.startswith(("linux", "win"))


def _ohne_platzhalter(befehl: str) -> str:
    """Der Befehl ohne die Stelle, an der die Datei eingesetzt wird.

    Windows schreibt ``"%1"``, ein Desktop-Eintrag ``%f`` oder ``%u`` -
    fuer den Vergleich mit ``aufruf()`` stoert das nur.
    """
    text = befehl.strip()
    for platzhalter in ('"%1"', "%1", "%f", "%F", "%u", "%U"):
        if text.endswith(platzhalter):
            text = text[: -len(platzhalter)].strip()
    return text


def angemeldeter_aufruf() -> str:
    """Womit die Dateiverwaltung eine Projektdatei gerade oeffnet.

    Leer, wenn nichts angemeldet ist. Geworfen wird nicht: die Auskunft
    ist eine Nebensache, sie darf keinen Start aufhalten.
    """
    try:
        if sys.platform.startswith("win"):
            return _windows_angemeldeter_aufruf()
        if sys.platform.startswith("linux"):
            return _linux_angemeldeter_aufruf()
    except Exception:      # noqa: BLE001 - eine Auskunft, kein Betrieb
        return ""
    return ""


def anderes_programm() -> str:
    """Der eingetragene Aufruf, wenn er ein **anderes** Verteilerly meint.

    Eine portable Ausgabe kann unter jedem Namen an jedem Ort liegen -
    ``VerteilerlyPortable.exe`` auf einem Stick neben einer aelteren
    ``Verteilerly.exe`` im Download-Ordner. Der Doppelklick nimmt, was
    eingetragen ist, und das ist nach einem Umzug oder einem Wechsel der
    Ausgabe nicht mehr das laufende Programm: es liest dann seine
    Einstellungen woanders, und der Anwender haelt seine fuer verloren.
    Damit das auffaellt, sagt diese Funktion, worauf die Zuordnung zeigt -
    und die Oberflaeche sagt es weiter.
    """
    eingetragen = angemeldeter_aufruf()
    if not eingetragen or aufruf() in eingetragen:
        return ""
    return eingetragen


def angemeldet() -> bool:
    """Steht Verteilerly schon als Programm fuer seine Dateien?"""
    if sys.platform.startswith("win"):
        return _windows_angemeldet()
    if sys.platform.startswith("linux"):
        return _linux_angemeldet()
    return False


def anmelden(symbol_schreiben=None) -> list[str]:
    """Meldet Verteilerly an und sagt, was dabei geschrieben wurde.

    ``symbol_schreiben`` legt das Sinnbild ab, wenn eines gebraucht wird
    - unter Linux. Dieses Modul zeichnet es nicht selbst: es kennt kein
    Qt, und die Anmeldung soll auch ohne Oberflaeche laufen.
    """
    if sys.platform.startswith("win"):
        return _windows_anmelden()
    if sys.platform.startswith("linux"):
        return _linux_anmelden(symbol_schreiben)
    raise VerknuepfungFehler(
        u("Für {0} kennt das Programm keinen Weg").format(sys.platform)
    )
