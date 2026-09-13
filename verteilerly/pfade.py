"""Wo die Daten liegen.

Vorlagen und Kabeltypen sollen ohne Auspacken zu aendern sein. Der
Arbeitsordner dafuer haengt an der Plattform:

* Windows: neben dem Programm - eine Datei, ein Ordner, ein Stick.
* Linux: dort, wo auch die Einstellungen liegen (``~/.config/Verteilerly``);
  im AppImage laesst sich neben dem Programm nicht schreiben, dort liegt
  die Grundausstattung in einem Nur-Lese-Abbild.

Beim ersten Start wird die mitgelieferte Grundausstattung in diesen
Ordner ausgelegt. Gelesen wird darueber hinaus aus allen Orten, an denen
Daten liegen koennen - ein Ordner ``daten`` neben der AppImage-Datei geht
vor, damit ein vollstaendig portabler Stick weiter moeglich ist.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import sys

DATENORDNER = "daten"
UNTERORDNER = ("vorlagen", "kabeltypen", "blattvorlagen")
# Die Lizenztexte liegen neben dem Datenordner, nicht darin: sie gehoeren
# zum Programm, nicht zum Bestand des Anwenders.
LIZENZORDNER = "lizenzen"
LIZENZ_EIGEN = "GPL-3.0.txt"
ANWENDUNG = "Verteilerly"
# Merkzettel im Arbeitsordner: welche Datei mit welchem Inhalt ausgelegt
# wurde. Daran ist spaeter zu erkennen, ob der Anwender sie angefasst hat.
MERKZETTEL = ".ausgelegt.json"
# Wer eine mitgelieferte Vorlage loescht, will sie los sein - ohne
# Vermerk legte der naechste Start sie wieder aus.
LOESCHZETTEL = ".geloescht.json"


def gepackt() -> bool:
    """Laeuft das Programm als AppImage oder .exe (PyInstaller)?"""
    return getattr(sys, "frozen", False)


def programmordner() -> pathlib.Path:
    """Der Ordner, in dem das Programm liegt."""
    if gepackt():
        return pathlib.Path(sys.executable).resolve().parent
    return pathlib.Path(__file__).resolve().parent.parent


def appimage() -> pathlib.Path | None:
    """Der Ordner der AppImage-Datei, sofern das Programm so laeuft.

    Im AppImage liegt sys.executable im Einhaengepunkt unter /tmp - die
    AppImage-Datei selbst liegt woanders, etwa auf einem Stick.
    """
    ort = os.environ.get("APPIMAGE")
    return pathlib.Path(ort).resolve().parent if ort else None


# -- Arbeitsordner ---------------------------------------------------------


EINSTELLUNGSDATEI = f"{ANWENDUNG}.conf"


def einstellungsordner() -> pathlib.Path:
    """Der Ordner im Benutzerprofil - unter Linux auch der Arbeitsordner."""
    if sys.platform.startswith("win"):
        wurzel = os.environ.get("APPDATA") or pathlib.Path.home() / "AppData" / "Roaming"
    else:
        wurzel = os.environ.get("XDG_CONFIG_HOME") or pathlib.Path.home() / ".config"
    return pathlib.Path(wurzel) / ANWENDUNG


def einstellungsdatei() -> pathlib.Path:
    """Wo die Verteilerly.conf liegt.

    Unter Windows neben dem Programm - eine Datei, ein Ordner, ein Stick,
    und ohne Registry. Laesst sich dort nicht schreiben, weicht sie
    ins Benutzerprofil aus. Unter Linux bleibt sie im Einstellungsordner,
    wo Qt sie ohnehin ablegt; im AppImage waere neben dem Programm nichts
    zu schreiben.
    """
    if sys.platform.startswith("win"):
        neben_programm = programmordner() / EINSTELLUNGSDATEI
        if _beschreibbar(neben_programm.parent):
            return neben_programm
    return einstellungsordner() / EINSTELLUNGSDATEI


def benutzerdatenordner() -> pathlib.Path:
    """Der Arbeitsordner fuer Vorlagen und Kabeltypen."""
    if sys.platform.startswith("win"):
        return programmordner() / DATENORDNER
    return einstellungsordner()


def _beschreibbar(ordner: pathlib.Path) -> bool:
    """Laesst sich der Ordner anlegen oder beschreiben?"""
    vorhanden = ordner
    while not vorhanden.exists() and vorhanden != vorhanden.parent:
        vorhanden = vorhanden.parent
    return os.access(vorhanden, os.W_OK)


def eigener_datenordner() -> pathlib.Path:
    """Wohin geschrieben wird - der erste Ort, an dem es geht."""
    orte = [benutzerdatenordner()]
    neben_appimage = appimage()
    if neben_appimage:
        orte.append(neben_appimage / DATENORDNER)
    orte.append(programmordner() / DATENORDNER)
    for ort in orte:
        if _beschreibbar(ort):
            return ort
    return orte[0]


def eigener_vorlagenordner() -> pathlib.Path:
    return eigener_datenordner() / "vorlagen"


# -- Mitgeliefertes und Suchreihenfolge ------------------------------------


def mitgeliefert() -> pathlib.Path | None:
    """Die Grundausstattung, die mit dem Programm kommt."""
    orte = []
    eingehaengt = os.environ.get("APPDIR")          # AppImage
    if eingehaengt:
        orte.append(pathlib.Path(eingehaengt) / DATENORDNER)
    entpackt = getattr(sys, "_MEIPASS", None)       # PyInstaller
    if entpackt:
        orte.append(pathlib.Path(entpackt) / DATENORDNER)
    orte.append(pathlib.Path(__file__).resolve().parent.parent / DATENORDNER)
    for ort in orte:
        if ort.is_dir():
            return ort
    return None


def _kandidaten() -> list[pathlib.Path]:
    """Alle Orte, an denen Daten liegen koennen - der wichtigste zuerst."""
    orte: list[pathlib.Path] = []
    neben_appimage = appimage()
    if neben_appimage:
        # Ein Datenordner neben der AppImage-Datei ist eine Ansage.
        orte.append(neben_appimage / DATENORDNER)
    orte.append(benutzerdatenordner())
    orte.append(programmordner() / DATENORDNER)
    fertig = mitgeliefert()
    if fertig:
        orte.append(fertig)
    ohne_doppelte: list[pathlib.Path] = []
    for ort in orte:
        if ort not in ohne_doppelte:
            ohne_doppelte.append(ort)
    return ohne_doppelte


def datenordner_alle() -> list[pathlib.Path]:
    """Alle vorhandenen Datenordner."""
    return [ort for ort in _kandidaten() if ort.is_dir()]


def datenordner() -> pathlib.Path:
    """Der erste vorhandene Datenordner."""
    for ort in _kandidaten():
        if ort.is_dir():
            return ort
    gesucht = "\n  ".join(str(o) for o in _kandidaten())
    raise FileNotFoundError(f"Datenordner nicht gefunden. Gesucht wurde in:\n  {gesucht}")


def _unterordner(name: str) -> pathlib.Path:
    """Der erste Datenordner, der diesen Unterordner gefuellt enthaelt.

    Ein leerer Ordner zaehlt nicht: ein uebriggebliebenes, leeres
    ``daten/vorlagen`` neben der AppImage-Datei wuerde sonst die
    mitgelieferten Dateien verdecken - und zwar lautlos.
    """
    vorhanden = None
    for ort in _kandidaten():
        wenn = ort / name
        if not wenn.is_dir():
            continue
        if any(wenn.glob("*.yaml")):
            return wenn
        vorhanden = vorhanden or wenn
    return vorhanden or datenordner() / name


def vorlagenordner() -> pathlib.Path:
    return _unterordner("vorlagen")


def vorlagenordner_alle() -> list[pathlib.Path]:
    """Jeder Ort, an dem Vorlagen liegen koennen."""
    return [ort / "vorlagen" for ort in datenordner_alle() if (ort / "vorlagen").is_dir()]


def kabeltypenordner() -> pathlib.Path:
    return _unterordner("kabeltypen")


def blattvorlagenordner() -> pathlib.Path:
    return _unterordner("blattvorlagen")


def blattvorlagenordner_alle() -> list[pathlib.Path]:
    """Jeder Ort, an dem Blattvorlagen liegen koennen."""
    return [
        ort / "blattvorlagen"
        for ort in datenordner_alle()
        if (ort / "blattvorlagen").is_dir()
    ]


# -- Erstausstattung -------------------------------------------------------


def _fingerabdruck(datei: pathlib.Path) -> str:
    return hashlib.sha256(datei.read_bytes()).hexdigest()


def _merkzettel_lesen(ordner: pathlib.Path) -> dict[str, str]:
    try:
        return dict(json.loads((ordner / MERKZETTEL).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return {}


def _merkzettel_schreiben(ordner: pathlib.Path, stand: dict[str, str]) -> None:
    try:
        (ordner / MERKZETTEL).write_text(
            json.dumps(stand, indent=2, sort_keys=True), encoding="utf-8"
        )
    except OSError:
        # Ohne Merkzettel wird spaeter eben nichts aufgefrischt - das ist
        # kein Grund, den Start abzubrechen.
        pass


def mitgelieferte_lizenzen() -> pathlib.Path | None:
    """Der Ordner mit den Lizenztexten, wie das Programm ihn mitbringt.

    Im AppImage liegt er im Einhaengepunkt unter ``/tmp`` und ist nach
    dem Beenden weg; ``lizenzen_auslegen()`` legt darum eine Kopie in den
    Arbeitsordner.
    """
    orte = []
    fertig = mitgeliefert()
    if fertig:
        orte.append(fertig.parent / LIZENZORDNER)
    entpackt = getattr(sys, "_MEIPASS", None)       # PyInstaller
    if entpackt:
        orte.append(pathlib.Path(entpackt) / LIZENZORDNER)
    orte.append(pathlib.Path(__file__).resolve().parent.parent / LIZENZORDNER)
    for ort in orte:
        if ort.is_dir():
            return ort
    return None


def lizenzordner() -> pathlib.Path | None:
    """Wo die Lizenztexte zu lesen sind - die ausgelegte Kopie zuerst.

    Sie bleibt liegen, wenn das Programm beendet ist; der mitgelieferte
    Ordner im Abbild tut das nicht.
    """
    ausgelegt = eigener_datenordner() / LIZENZORDNER
    if ausgelegt.is_dir() and any(ausgelegt.glob("*.txt")):
        return ausgelegt
    return mitgelieferte_lizenzen()


def lizenzen_auslegen() -> list[pathlib.Path]:
    """Legt die Lizenztexte neben die Einstellungen.

    Im AppImage stecken sie im Einhaengepunkt; wer nach dem Beenden
    nachlesen will, was er weitergeben darf, faende dort nichts mehr.
    Sie werden darum wie die Grundausstattung ausgelegt - und wie diese
    nur aufgefrischt, solange sie unberuehrt sind.
    """
    quelle = mitgelieferte_lizenzen()
    ziel = eigener_datenordner()
    if quelle is None or quelle == ziel / LIZENZORDNER or not _beschreibbar(ziel):
        return []

    merkzettel = _merkzettel_lesen(ziel)
    nach = ziel / LIZENZORDNER
    nach.mkdir(parents=True, exist_ok=True)
    texte = {datei.name: datei for datei in sorted(quelle.glob("*.txt"))}
    # Im Quellbaum heisst die eigene Lizenz LICENSE und liegt neben dem
    # Ordner; im Abbild liegt sie als GPL-3.0.txt darin. Ausgelegt wird
    # sie in beiden Faellen unter demselben Namen.
    eigene = quelle.parent / "LICENSE"
    if LIZENZ_EIGEN not in texte and eigene.is_file():
        texte[LIZENZ_EIGEN] = eigene

    geschrieben: list[pathlib.Path] = []
    for name, datei in sorted(texte.items()):
        fertig = nach / name
        marke = f"{LIZENZORDNER}/{name}"
        mitgebracht = _fingerabdruck(datei)
        if fertig.exists():
            unberuehrt = merkzettel.get(marke) == _fingerabdruck(fertig)
            if not unberuehrt or merkzettel.get(marke) == mitgebracht:
                continue
        shutil.copy2(datei, fertig)
        merkzettel[marke] = mitgebracht
        geschrieben.append(fertig)

    if geschrieben:
        _merkzettel_schreiben(ziel, merkzettel)
    return geschrieben


def geloeschte(ordner: pathlib.Path | None = None) -> set[str]:
    """Welche mitgelieferten Dateien der Anwender weghaben will.

    Vermerkt wird die Marke, nicht der Pfad: "vorlagen/40da-4x10.yaml".
    """
    ziel = pathlib.Path(ordner) if ordner else eigener_datenordner()
    try:
        gelesen = json.loads((ziel / LOESCHZETTEL).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {str(marke) for marke in gelesen or ()}


def _loeschzettel_schreiben(marken: set[str], ziel: pathlib.Path) -> None:
    try:
        if marken:
            (ziel / LOESCHZETTEL).write_text(
                json.dumps(sorted(marken), indent=2), encoding="utf-8"
            )
        else:
            (ziel / LOESCHZETTEL).unlink(missing_ok=True)
    except OSError:
        pass


def loeschen_merken(marke: str, ordner: pathlib.Path | None = None) -> None:
    """Haelt fest, dass diese mitgelieferte Datei nicht wiederkommen soll."""
    ziel = pathlib.Path(ordner) if ordner else eigener_datenordner()
    _loeschzettel_schreiben(geloeschte(ziel) | {marke}, ziel)


def loeschvermerke_aufheben(
    bereich: str = "", ordner: pathlib.Path | None = None
) -> int:
    """Nimmt die Vermerke zurueck - alle oder die eines Unterordners."""
    ziel = pathlib.Path(ordner) if ordner else eigener_datenordner()
    vorher = geloeschte(ziel)
    bleiben = {
        marke for marke in vorher
        if bereich and not marke.startswith(f"{bereich}/")
    }
    _loeschzettel_schreiben(bleiben, ziel)
    return len(vorher) - len(bleiben)


def grundausstattung_auslegen() -> list[pathlib.Path]:
    """Legt die mitgelieferten Dateien in den Arbeitsordner.

    Angelegt wird, was dort noch fehlt. Aufgefrischt wird eine Datei nur
    dann, wenn sie noch genau so daliegt, wie sie ausgelegt wurde: dann
    hat niemand sie angefasst, und eine spaetere Fassung darf sie
    verbessern. Sobald jemand eine Zeile geaendert hat, bleibt sie
    unangetastet - eigene Aenderungen wiegen schwerer als jede Vorgabe.

    Die Lizenztexte gehen denselben Weg, damit sie nach dem Beenden noch
    dasind.

    Zurueckgegeben wird, was angelegt oder aufgefrischt wurde.
    """
    return _vorlagen_auslegen() + lizenzen_auslegen()


def _vorlagen_auslegen() -> list[pathlib.Path]:
    """Vorlagen, Kabeltypen und Blattvorlagen - der Bestand des Anwenders."""
    quelle = mitgeliefert()
    ziel = eigener_datenordner()
    if quelle is None or quelle == ziel or not _beschreibbar(ziel):
        return []

    merkzettel = _merkzettel_lesen(ziel)
    weggeworfen = geloeschte(ziel)
    geschrieben: list[pathlib.Path] = []
    for name in UNTERORDNER:
        von = quelle / name
        if not von.is_dir():
            continue
        nach = ziel / name
        nach.mkdir(parents=True, exist_ok=True)
        for datei in sorted(von.glob("*.yaml")):
            fertig = nach / datei.name
            marke = f"{name}/{datei.name}"
            if marke in weggeworfen:
                continue
            mitgebracht = _fingerabdruck(datei)
            if fertig.exists():
                unberuehrt = merkzettel.get(marke) == _fingerabdruck(fertig)
                if not unberuehrt or merkzettel.get(marke) == mitgebracht:
                    continue
            shutil.copy2(datei, fertig)
            merkzettel[marke] = mitgebracht
            geschrieben.append(fertig)

    if geschrieben:
        _merkzettel_schreiben(ziel, merkzettel)
    return geschrieben
