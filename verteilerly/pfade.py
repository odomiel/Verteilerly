"""Wo die Daten liegen.

Vorlagen und Kabeltypen liegen neben dem Programm, damit der portable
Betrieb von einem Stick aus funktioniert. Gesucht wird deshalb zuerst
neben der ausfuehrbaren Datei, dann im Quellbaum.

Zum Lesen zaehlen alle diese Orte, zum Schreiben nur einer: das AppImage
traegt seine Grundausstattung in einem Nur-Lese-Abbild, dort laesst sich
keine eigene Vorlage ablegen.
"""

from __future__ import annotations

import os
import pathlib
import sys

DATENORDNER = "daten"


def gepackt() -> bool:
    """Laeuft das Programm als AppImage oder .exe (PyInstaller)?"""
    return getattr(sys, "frozen", False)


def programmordner() -> pathlib.Path:
    """Der Ordner, in dem das Programm liegt."""
    if gepackt():
        return pathlib.Path(sys.executable).resolve().parent
    return pathlib.Path(__file__).resolve().parent.parent


def appimage() -> pathlib.Path | None:
    """Die AppImage-Datei selbst, sofern das Programm so laeuft.

    Im AppImage liegt sys.executable im Einhaengepunkt unter /tmp - neben
    dem Stick liegt aber die AppImage-Datei, und dort sucht der Anwender
    seinen Datenordner.
    """
    ort = os.environ.get("APPIMAGE")
    return pathlib.Path(ort).resolve().parent if ort else None


def _kandidaten() -> list[pathlib.Path]:
    orte = []
    neben_appimage = appimage()
    if neben_appimage:
        orte.append(neben_appimage / DATENORDNER)
    orte.append(programmordner() / DATENORDNER)
    # Im AppImage liegt die mitgelieferte Grundausstattung im AppDir.
    eingehaengt = os.environ.get("APPDIR")
    if eingehaengt:
        orte.append(pathlib.Path(eingehaengt) / DATENORDNER)
    # PyInstaller entpackt Beigaben nach _MEIPASS; von dort kommt die
    # mitgelieferte Grundausstattung, falls daneben nichts liegt.
    mitgeliefert = getattr(sys, "_MEIPASS", None)
    if mitgeliefert:
        orte.append(pathlib.Path(mitgeliefert) / DATENORDNER)
    quellbaum = pathlib.Path(__file__).resolve().parent.parent / DATENORDNER
    if quellbaum not in orte:
        orte.append(quellbaum)
    # Zuletzt das Benutzerverzeichnis: dorthin gehen eigene Vorlagen, wenn
    # neben dem Programm nicht zu schreiben ist. Es steht hinten an, damit
    # die vollstaendige Grundausstattung vorgeht.
    eigen = benutzerordner() / DATENORDNER
    if eigen not in orte:
        orte.append(eigen)
    return orte


def datenordner_alle() -> list[pathlib.Path]:
    """Alle vorhandenen Datenordner - der wichtigste zuerst."""
    return [ort for ort in _kandidaten() if ort.is_dir()]


def datenordner() -> pathlib.Path:
    """Der erste vorhandene Datenordner."""
    for ort in _kandidaten():
        if ort.is_dir():
            return ort
    gesucht = "\n  ".join(str(o) for o in _kandidaten())
    raise FileNotFoundError(f"Datenordner nicht gefunden. Gesucht wurde in:\n  {gesucht}")


def _unterordner(name: str) -> pathlib.Path:
    """Der erste Datenordner, der diesen Unterordner wirklich enthaelt."""
    for ort in _kandidaten():
        if (ort / name).is_dir():
            return ort / name
    return datenordner() / name


def vorlagenordner() -> pathlib.Path:
    return _unterordner("vorlagen")


def vorlagenordner_alle() -> list[pathlib.Path]:
    """Jeder Ort, an dem Vorlagen liegen koennen."""
    return [ort / "vorlagen" for ort in datenordner_alle() if (ort / "vorlagen").is_dir()]


def kabeltypenordner() -> pathlib.Path:
    return _unterordner("kabeltypen")


# -- Schreiben -------------------------------------------------------------


def _beschreibbar(ordner: pathlib.Path) -> bool:
    """Laesst sich der Ordner anlegen oder beschreiben?"""
    vorhanden = ordner
    while not vorhanden.exists() and vorhanden != vorhanden.parent:
        vorhanden = vorhanden.parent
    return os.access(vorhanden, os.W_OK)


def benutzerordner() -> pathlib.Path:
    """Der Rueckfallort im Benutzerverzeichnis."""
    if sys.platform.startswith("win"):
        wurzel = os.environ.get("APPDATA") or pathlib.Path.home() / "AppData" / "Roaming"
        return pathlib.Path(wurzel) / "Verteilerly"
    wurzel = os.environ.get("XDG_DATA_HOME") or pathlib.Path.home() / ".local" / "share"
    return pathlib.Path(wurzel) / "verteilerly"


def eigener_datenordner() -> pathlib.Path:
    """Wohin eigene Vorlagen kommen.

    Zuerst neben das Programm - dann bleibt der Stick vollstaendig.
    Im AppImage geht das nicht: der mitgelieferte
    Datenordner liegt im Nur-Lese-Abbild. Dann faellt die Ablage auf das
    Benutzerverzeichnis zurueck, statt die Eingabe zu verwerfen.
    """
    orte = []
    neben_appimage = appimage()
    if neben_appimage:
        orte.append(neben_appimage / DATENORDNER)
    if not gepackt() or not os.environ.get("APPDIR"):
        orte.append(programmordner() / DATENORDNER)
    for ort in orte:
        if _beschreibbar(ort):
            return ort
    return benutzerordner() / DATENORDNER


def eigener_vorlagenordner() -> pathlib.Path:
    """Der Ordner, in den eine gesicherte Vorlage geschrieben wird."""
    return eigener_datenordner() / "vorlagen"
