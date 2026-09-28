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
#: Steht fuer „ausdruecklich nichts": der Anwender hat die Zuordnung von
#: aussen aufgehoben. Unsere Dateien liegen dann noch da und taeuschen eine
#: Anmeldung vor - gefragt ist aber, was die Dateiverwaltung wirklich tut.
KEINE = "-"


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
    mime, _desktop = _linux_orte()
    if not mime.is_file():
        return False
    eingetragen = _linux_angemeldeter_aufruf()
    return bool(eingetragen) and eingetragen != KEINE and aufruf() in eingetragen


def _linux_angemeldeter_aufruf() -> str:
    """Womit die Dateiverwaltung gerade oeffnet.

    Zuerst die **Wahl des Anwenders**: steht der Dateityp in einer
    ``mimeapps.list``, gilt der dort genannte Desktop-Eintrag - auch wenn
    das ein anderes Programm ist oder unser Eintrag noch daliegt. Erst
    ohne solche Wahl gilt unser eigener Eintrag ueber ``MimeType=``.
    """
    gewaehlt = _linux_gewaehlte_desktopdatei()
    if gewaehlt and gewaehlt != DESKTOPDATEI:
        return _linux_exec(_linux_desktopdatei_finden(gewaehlt)) or gewaehlt
    if gewaehlt == "":
        # Keine Wahl getroffen - dann oeffnet, wer den Typ anmeldet.
        pass
    _mime, desktop = _linux_orte()
    return _linux_exec(desktop)


def _linux_exec(datei) -> str:
    """Die Exec-Zeile eines Desktop-Eintrags, ohne Platzhalter."""
    if datei is None:
        return ""
    try:
        zeilen = datei.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for zeile in zeilen:
        if zeile.startswith("Exec="):
            return _ohne_platzhalter(zeile[len("Exec="):])
    return ""


def _mimeapps_dateien() -> list[pathlib.Path]:
    """Wo die Wahl des Anwenders stehen kann - das Wichtigste zuerst."""
    conf = pathlib.Path(
        os.environ.get("XDG_CONFIG_HOME") or pathlib.Path.home() / ".config"
    )
    daten = pathlib.Path(
        os.environ.get("XDG_DATA_HOME") or pathlib.Path.home() / ".local" / "share"
    )
    return [conf / "mimeapps.list", daten / "applications" / "mimeapps.list"]


def _linux_gewaehlte_desktopdatei() -> str:
    """Welcher Desktop-Eintrag fuer unseren Dateityp gewaehlt ist.

    Leer, wenn niemand gewaehlt hat; ``KEINE``, wenn die Wahl ausdruecklich
    weggenommen wurde (``[Removed Associations]``) - dann oeffnet uns die
    Dateiverwaltung **nicht** mehr, obwohl unsere Dateien noch daliegen.
    """
    for datei in _mimeapps_dateien():
        try:
            zeilen = datei.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        abschnitt = ""
        for zeile in zeilen:
            blank = zeile.strip()
            if blank.startswith("[") and blank.endswith("]"):
                abschnitt = blank
                continue
            if "=" not in blank or not blank.startswith(MIMETYP):
                continue
            typ, wert = blank.split("=", 1)
            if typ.strip() != MIMETYP:
                continue
            eintraege = [s for s in wert.replace(";", " ").split() if s]
            if abschnitt == "[Removed Associations]":
                if DESKTOPDATEI in eintraege:
                    return KEINE
                continue
            if eintraege:
                return eintraege[0]
    return ""


def _linux_desktopdatei_finden(name: str):
    """Die Desktop-Datei dieses Namens - in den ueblichen Ordnern."""
    orte = [
        pathlib.Path(
            os.environ.get("XDG_DATA_HOME")
            or pathlib.Path.home() / ".local" / "share"
        )
        / "applications"
    ]
    for grund in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":"):
        if grund:
            orte.append(pathlib.Path(grund) / "applications")
    for ort in orte:
        datei = ort / name
        if datei.is_file():
            return datei
    return None


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
    eingetragen = _windows_angemeldeter_aufruf()
    return bool(eingetragen) and eingetragen != KEINE and aufruf() in eingetragen


def _windows_angemeldeter_aufruf() -> str:
    """Womit die Dateiverwaltung gerade oeffnet - laut Registrierung.

    Die **Wahl des Anwenders** geht vor: was „Öffnen mit ▸ Immer" setzt,
    steht unter ``FileExts\\.vtly\\UserChoice`` und schlaegt unsere
    Zuordnung, auch wenn unsere Schluessel unberuehrt daliegen. Erst ohne
    solche Wahl gilt, was ``.vtly`` unter ``Software\\Classes`` sagt.
    """
    kennung = _windows_wert(
        rf"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts"
        rf"\{ENDUNGEN[0]}\UserChoice",
        "ProgId",
    )
    if not kennung:
        kennung = _windows_wert(rf"Software\Classes\{ENDUNGEN[0]}", "")
    if not kennung:
        return ""
    if _windows_gesperrt(kennung):
        return KEINE
    befehl = _windows_wert(rf"Software\Classes\{kennung}\shell\open\command", "")
    if not befehl:
        befehl = _windows_wert(
            rf"{kennung}\shell\open\command", "", wurzel="klassen"
        )
    return _ohne_platzhalter(befehl) if befehl else kennung


def _windows_gesperrt(kennung: str) -> bool:
    """Eine Kennung, die ausdruecklich nichts oeffnet."""
    return kennung.strip().lower() in ("", "applications\\", "unknown")


def _windows_wert(schluessel: str, name: str, wurzel: str = "benutzer") -> str:
    """Ein Wert aus der Registrierung - leer, wenn es ihn nicht gibt."""
    import winreg

    orte = (
        [winreg.HKEY_CLASSES_ROOT]
        if wurzel == "klassen"
        else [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]
    )
    for ort in orte:
        try:
            with winreg.OpenKey(ort, schluessel) as offen:
                wert, _art = winreg.QueryValueEx(offen, name)
        except OSError:
            continue
        if wert:
            return str(wert)
    return ""


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
    if not eingetragen or eingetragen == KEINE or aufruf() in eingetragen:
        return ""
    return eingetragen


def _linux_eigene_eintraege() -> bool:
    mime, desktop = _linux_orte()
    return mime.is_file() and desktop.is_file()


def _windows_eigene_eintraege() -> bool:
    return bool(
        _windows_wert(
            rf"Software\Classes\{PROGRAMMKENNUNG}\shell\open\command", ""
        )
    )


def eigene_eintraege() -> bool:
    """Liegen unsere Dateien bzw. Schluessel noch da?

    Das ist nicht dasselbe wie ``angemeldet()``: unsere Eintraege koennen
    unberuehrt sein, waehrend die Dateiverwaltung laengst ein anderes
    Programm nimmt.
    """
    try:
        if sys.platform.startswith("win"):
            return _windows_eigene_eintraege()
        if sys.platform.startswith("linux"):
            return _linux_eigene_eintraege()
    except Exception:      # noqa: BLE001 - eine Auskunft, kein Betrieb
        return False
    return False


def aufgehoben() -> bool:
    """Wurde die Zuordnung **von aussen** aufgehoben?

    Wir haben angemeldet - unsere Eintraege liegen da -, aber der
    Doppelklick kommt nicht mehr bei uns an: „Öffnen mit ▸ Immer" hat
    etwas anderes gesetzt, die Wahl wurde weggenommen
    (``[Removed Associations]``), oder die Endung zeigt woandershin. Das
    merkte das Programm bisher nicht, weil es nur seine eigenen Eintraege
    ansah - und die stehen ja noch.
    """
    return eigene_eintraege() and not angemeldet()


def angemeldet() -> bool:
    """Steht Verteilerly schon als Programm fuer seine Dateien?

    Gefragt ist, was die Dateiverwaltung **tut**, nicht was wir
    geschrieben haben.
    """
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
