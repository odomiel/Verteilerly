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

import os
import pathlib
import shutil
import sys

DATENORDNER = "daten"
UNTERORDNER = ("vorlagen", "kabeltypen", "blattvorlagen")
ANWENDUNG = "Verteilerly"


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


def einstellungsordner() -> pathlib.Path:
    """Wo Qt die Verteilerly.conf ablegt."""
    if sys.platform.startswith("win"):
        wurzel = os.environ.get("APPDATA") or pathlib.Path.home() / "AppData" / "Roaming"
    else:
        wurzel = os.environ.get("XDG_CONFIG_HOME") or pathlib.Path.home() / ".config"
    return pathlib.Path(wurzel) / ANWENDUNG


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


def grundausstattung_auslegen() -> list[pathlib.Path]:
    """Legt die mitgelieferten Dateien in den Arbeitsordner.

    Kopiert wird nur, was dort noch nicht liegt: eigene Aenderungen
    bleiben unangetastet, und eine spaetere Fassung bringt ihre neuen
    Dateien nach. Zurueckgegeben wird, was tatsaechlich angelegt wurde.
    """
    quelle = mitgeliefert()
    ziel = eigener_datenordner()
    if quelle is None or quelle == ziel or not _beschreibbar(ziel):
        return []

    angelegt: list[pathlib.Path] = []
    for name in UNTERORDNER:
        von = quelle / name
        if not von.is_dir():
            continue
        nach = ziel / name
        nach.mkdir(parents=True, exist_ok=True)
        for datei in sorted(von.glob("*.yaml")):
            fertig = nach / datei.name
            if not fertig.exists():
                shutil.copy2(datei, fertig)
                angelegt.append(fertig)
    return angelegt
