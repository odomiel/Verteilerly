"""Auskunft darueber, wer die Projektdateien oeffnet.

Ein Doppelklick auf eine Projektdatei soll Verteilerly oeffnen. Dieses
Modul **schreibt das nicht ein** - es sagt nur, wie es steht:

* welche ausfuehrbare Datei zu verknuepfen ist (``zu_verknuepfen()``) -
  bei einer Ausgabe mit Starter der **Starter**, nicht das Programm
  dahinter, sonst laeuft der Doppelklick daran vorbei;
* womit die Dateiverwaltung gerade oeffnet (``angemeldeter_aufruf()``)
  und ob das wir sind (``angemeldet()``).

**Verknuepft wird von Hand**, in der Dateiverwaltung: unter Windows ueber
*Öffnen mit ▸ Andere App ▸ Immer diese App*, unter Linux ueber
*Öffnen mit ▸ Andere Anwendung*. Das Programm hat das eine Weile selbst
geschrieben; verlaesslich war es nicht, weil die Wahl des Anwenders jeder
Anmeldung vorgeht und eine Ausgabe mit Starter sich ohnehin nicht selbst
eintragen kann.

Gefragt ist darum immer, was die Dateiverwaltung **tut**, nicht was
irgendwo eingetragen steht: unter Windows zaehlt zuerst
``FileExts\\.vtly\\UserChoice``, unter Linux die ``mimeapps.list``.

Dieses Modul kennt kein Qt; die Oberflaeche zeigt nur, was es meldet.
"""

from __future__ import annotations

import os
import pathlib
import sys


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
#: Woran ein Starter zu erkennen ist - PortableApps benennt ihn so.
STARTERMUSTER = "*Portable.exe"
#: Steht fuer „ausdruecklich nichts": die Zuordnung ist weggenommen
#: (``[Removed Associations]``, eine gesperrte Kennung). Dann oeffnet
#: **niemand** die Datei - das ist etwas anderes als „nicht eingetragen".
KEINE = "-"


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


def starter() -> pathlib.Path | None:
    """Der Starter, der dieses Programm gestartet hat - falls es einen gibt.

    Eine PortableApps-Ausgabe legt ``<Ordner>\\VerteilerlyPortable.exe`` vor
    ``<Ordner>\\App\\Verteilerly\\Verteilerly.exe``: der Starter richtet
    Ordner und Umgebung ein und ruft dann das Programm. Das Programm sieht
    nur sich selbst - verknuepft gehoert der Starter, sonst laeuft der
    Doppelklick an ihm vorbei.
    """
    if not getattr(sys, "frozen", False) or not sys.platform.startswith("win"):
        return None
    hier = pathlib.Path(sys.executable).resolve().parent
    for ordner in [hier, *list(hier.parents)[:3]]:
        for kandidat in sorted(ordner.glob(STARTERMUSTER)):
            if kandidat.resolve() != pathlib.Path(sys.executable).resolve():
                return kandidat
    return None


def zu_verknuepfen() -> pathlib.Path | None:
    """Die ausfuehrbare Datei, mit der die Projektdateien zu verknuepfen sind.

    Als AppImage die Abbilddatei selbst (nicht der Einhaengepunkt unter
    ``/tmp``, der beim Beenden verschwindet), unter Windows der Starter,
    wenn es einen gibt, sonst die laufende ``.exe``. Aus dem Quellbaum
    ``None``: dort startet ein Python mit ``-m verteilerly``, da ist
    nichts zu verknuepfen.
    """
    abbild = os.environ.get("APPIMAGE")
    if abbild:
        return pathlib.Path(abbild).resolve()
    los = starter()
    if los is not None:
        return los
    if getattr(sys, "frozen", False):
        return pathlib.Path(sys.executable).resolve()
    return None


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


def _wie_windows(befehlszeile: str) -> str:
    """Zum Vergleichen: ohne Anfuehrungszeichen, klein geschrieben.

    Dieselbe Datei steht in der Registrierung mal mit, mal ohne
    Anfuehrungszeichen und in beliebiger Schreibweise - Windows nimmt es
    damit nicht genau, und ein Vergleich Zeichen fuer Zeichen meldete
    sonst Unterschiede, die keine sind.
    """
    return _ohne_platzhalter(befehlszeile).replace('"', "").strip().casefold()


def _windows_angemeldet() -> bool:
    """Oeffnet der Doppelklick dieses Programm?

    Verglichen wird mit **zwei** Dateien: dem laufenden Programm und der,
    die zu verknuepfen waere. Bei einer Ausgabe mit Starter sind das
    verschiedene - eingetragen gehoert der Starter, laufen tut das
    Programm dahinter -, und beides ist richtig.
    """
    eingetragen = _windows_angemeldeter_aufruf()
    if not eingetragen or eingetragen == KEINE:
        return False
    steht_da = _wie_windows(eingetragen)
    ziel = zu_verknuepfen()
    unsere = [_wie_windows(aufruf())]
    if ziel is not None:
        unsere.append(_wie_windows(str(ziel)))
    return any(eigen and eigen in steht_da for eigen in unsere)


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


class VerknuepfungFehler(Exception):
    """Das Eintragen oder Aufheben ging schief."""


#: Wie es um die Verknuepfung steht - ``zustand()`` gibt eines davon.
OHNE = "ohne"            # nichts eingetragen
UNSER = "unser"          # unsere Kennung, und sie zeigt auf die richtige Datei
VERALTET = "veraltet"    # unsere Kennung, aber sie zeigt woandershin
FREMD = "fremd"          # ein anderes Programm oeffnet
GESPERRT = "gesperrt"    # ausdruecklich niemand


def befehl(datei: pathlib.Path | None = None) -> str:
    """Der Befehl, der in die Registrierung gehoert - samt ``"%1"``.

    Eingetragen wird, was ``zu_verknuepfen()`` nennt: bei einer Ausgabe
    mit Starter der **Starter**. Das ist auch der Grund, warum die
    Verknuepfung ein Update uebersteht - der Starter behaelt seinen Namen
    und seinen Platz, waehrend das Programm dahinter ausgetauscht wird.
    """
    ziel = datei or zu_verknuepfen()
    # Immer in Anfuehrungszeichen: ein Pfad mit Leerzeichen zerfiele sonst
    # in zwei Stuecke, und Windows schreibt es selbst auch so.
    return f'"{pathlib.Path(ziel)}" "%1"' if ziel else f'{aufruf()} "%1"'


def _windows_schluessel(befehlszeile: str, symbol: str) -> tuple:
    """Die vier Werte, die eine Verknuepfung unter Windows ausmachen."""
    return (
        (rf"Software\Classes\{ENDUNGEN[0]}", "", PROGRAMMKENNUNG),
        (rf"Software\Classes\{ENDUNGEN[0]}\OpenWithProgids",
         PROGRAMMKENNUNG, ""),
        (rf"Software\Classes\{PROGRAMMKENNUNG}", "", "Verteilerly-Projekt"),
        (rf"Software\Classes\{PROGRAMMKENNUNG}\DefaultIcon", "", symbol),
        (rf"Software\Classes\{PROGRAMMKENNUNG}\shell\open\command", "",
         befehlszeile),
    )


def eintragen(datei: pathlib.Path | None = None) -> list[str]:
    """Traegt die Verknuepfung ein - nur unter Windows, nur fuer diesen Benutzer.

    Geschrieben wird unter ``HKEY_CURRENT_USER``: das braucht keine
    erhoehten Rechte und gilt fuer den, der es anstoesst.

    **Die Wahl des Anwenders bleibt unberuehrt.** Steht unter
    ``FileExts\\.vtly\\UserChoice`` etwas, gilt weiter das - diese Wahl
    laesst sich nicht von aussen setzen (Windows sichert sie mit einem
    Streuwert ab). Unsere Eintraege sind dann die Grundlage, auf der
    *Öffnen mit* uns anbietet.
    """
    if not sys.platform.startswith("win"):
        raise VerknuepfungFehler(
            "Eingetragen wird nur unter Windows; unter Linux geschieht das "
            "in der Dateiverwaltung."
        )
    import winreg

    ziel = datei or zu_verknuepfen()
    if ziel is None:
        raise VerknuepfungFehler(
            "Hier ist nichts zu verknuepfen: dieses Verteilerly laeuft aus "
            "dem Quelltext."
        )
    befehlszeile = befehl(ziel)
    symbol = f"{_gequotet(pathlib.Path(ziel))},0"
    getan: list[str] = []
    for schluessel, name, wert in _windows_schluessel(befehlszeile, symbol):
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, schluessel) as offen:
                winreg.SetValueEx(offen, name, 0, winreg.REG_SZ, wert)
        except OSError as fehler:
            raise VerknuepfungFehler(
                f"{schluessel} liess sich nicht schreiben: {fehler}"
            ) from None
        getan.append(rf"HKCU\{schluessel}")
    _windows_bescheid_sagen()
    return getan


def aufheben() -> list[str]:
    """Nimmt unsere Eintraege wieder heraus.

    Angefasst wird nur, was uns gehoert: die Programmkennung und - wenn
    sie auf uns zeigt - die Endung. Die Wahl des Anwenders bleibt stehen,
    sie gehoert ihm.
    """
    if not sys.platform.startswith("win"):
        raise VerknuepfungFehler(
            "Aufgehoben wird nur unter Windows; unter Linux geschieht das "
            "in der Dateiverwaltung."
        )
    import winreg

    weg = [
        rf"Software\Classes\{PROGRAMMKENNUNG}\shell\open\command",
        rf"Software\Classes\{PROGRAMMKENNUNG}\shell\open",
        rf"Software\Classes\{PROGRAMMKENNUNG}\shell",
        rf"Software\Classes\{PROGRAMMKENNUNG}\DefaultIcon",
        rf"Software\Classes\{PROGRAMMKENNUNG}",
    ]
    getan: list[str] = []
    for schluessel in weg:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, schluessel)
        except OSError:
            continue        # war nicht da - dann ist auch nichts zu tun
        getan.append(rf"HKCU\{schluessel}")
    if _windows_wert(rf"Software\Classes\{ENDUNGEN[0]}", "") == PROGRAMMKENNUNG:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                             rf"Software\Classes\{ENDUNGEN[0]}")
            getan.append(rf"HKCU\Software\Classes\{ENDUNGEN[0]}")
        except OSError:
            pass
    _windows_bescheid_sagen()
    return getan


def _windows_bescheid_sagen() -> None:
    """Sagt der Oberflaeche, dass sich eine Verknuepfung geaendert hat.

    Ohne das wirkt der Eintrag erst nach dem naechsten Anmelden.
    """
    try:
        import ctypes

        # SHCNE_ASSOCCHANGED, SHCNF_IDLIST
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception:      # noqa: BLE001 - ohne Bescheid wirkt es eben spaeter
        pass


def eingetragener_befehl() -> str:
    """Was **unsere** Programmkennung gerade startet - ohne ``"%1"``.

    Nicht dasselbe wie ``angemeldeter_aufruf()``: das sagt, was die
    Dateiverwaltung tut, auch wenn das ein anderes Programm ist.
    """
    if not sys.platform.startswith("win"):
        return ""
    gefunden = _windows_wert(
        rf"Software\Classes\{PROGRAMMKENNUNG}\shell\open\command", ""
    )
    return _ohne_platzhalter(gefunden) if gefunden else ""


def stimmt() -> bool:
    """Zeigt unser Eintrag auf die Datei, die jetzt zu verknuepfen waere?

    Nach einem Update liegt dieselbe Datei am selben Platz - dann stimmt
    es weiter. Zieht das Programm um oder wird es umbenannt, steht in der
    Registrierung ein Pfad, den es nicht mehr gibt; dann ist der Eintrag
    zu erneuern, und das faellt nur auf, wenn jemand nachsieht.
    """
    eigener = eingetragener_befehl()
    return bool(eigener) and _wie_windows(eigener) == _wie_windows(befehl())


def eingetragene_datei() -> pathlib.Path | None:
    """Die Datei, auf die **unser** Eintrag zeigt - oder nichts.

    Eingetragen steht immer ein einzelner Pfad in Anfuehrungszeichen:
    ``eintragen()`` weigert sich im Quellbaum, wo ein Python mit
    ``-m verteilerly`` stuende. Was danach nicht wie eine einzelne Datei
    aussieht, gibt ``None`` - lieber nichts sagen als das Falsche.
    """
    text = eingetragener_befehl().strip().strip('"').strip()
    if not text or " -m " in text:
        return None
    return pathlib.Path(text)


def nachziehen_faellig() -> bool:
    """Darf der Eintrag ohne Rueckfrage auf diese Fassung gezogen werden?

    Die reine ``.exe`` traegt ihre Fassung im Namen
    (``Verteilerly_2026.10.13.exe``): ein Update ist dort eine **andere
    Datei**, und der Eintrag zeigt weiter auf die alte. Bei einer Ausgabe
    mit Starter stellt sich die Frage nicht - der behaelt seinen Namen.

    Nachgezogen wird nur, wenn die eingetragene Datei **nicht mehr da
    ist**: dann war es ein Update, und es gibt nichts, dem etwas
    weggenommen wuerde. Liegt sie noch da, stehen zwei Ausgaben
    nebeneinander - eine auf dem Stick, eine im Download-Ordner -, und
    dann wird nur gesagt, was ist: sonst risse die zuletzt gestartete
    Kopie die Verknuepfung stillschweigend an sich.
    """
    if not sys.platform.startswith("win"):
        return False
    if zu_verknuepfen() is None or stimmt():
        return False
    alt = eingetragene_datei()
    return alt is not None and not alt.exists()


def _windows_unsere_kennung_gilt() -> bool:
    """Zeigt die Endung - oder die Wahl des Anwenders - auf unsere Kennung?

    Das ist etwas anderes als ``angemeldet()``: die Kennung kann unsere
    sein, waehrend der Befehl dahinter auf eine Datei zeigt, die es nicht
    mehr gibt. Genau das passiert nach einem Umzug.
    """
    kennung = _windows_wert(
        rf"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts"
        rf"\{ENDUNGEN[0]}\UserChoice",
        "ProgId",
    ) or _windows_wert(rf"Software\Classes\{ENDUNGEN[0]}", "")
    return kennung.strip().casefold() == PROGRAMMKENNUNG.casefold()


def zustand() -> str:
    """Wie es um die Verknuepfung steht - eines der Woerter oben.

    Die Reihenfolge ist wichtig: **erst** fragen, ob die Kennung uns
    gehoert, dann erst, ob ein anderes Programm oeffnet. Sonst hiesse ein
    veralteter eigener Eintrag „fremd", und der Anwender suchte ein
    fremdes Programm, das es gar nicht gibt.
    """
    eingetragen = angemeldeter_aufruf()
    if eingetragen == KEINE:
        return GESPERRT
    if not sys.platform.startswith("win"):
        return UNSER if angemeldet() else (FREMD if eingetragen else OHNE)
    if _windows_unsere_kennung_gilt():
        # Geoeffnet wird ueber unsere Kennung - fragt sich nur, womit.
        return UNSER if stimmt() else VERALTET
    if eingetragen:
        # Ein anderes Programm hat den Zuschlag, auch wenn unsere
        # Schluessel noch daliegen: die Wahl des Anwenders geht vor.
        return FREMD
    return VERALTET if eingetragener_befehl() else OHNE


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


