"""Wo die Daten liegen.

Vorlagen und Kabeltypen liegen neben dem Programm, damit der portable
Betrieb von einem Stick aus funktioniert. Gesucht wird deshalb zuerst
neben der ausfuehrbaren Datei, dann im Quellbaum.
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
    return orte


def datenordner() -> pathlib.Path:
    """Der erste vorhandene Datenordner."""
    for ort in _kandidaten():
        if ort.is_dir():
            return ort
    gesucht = "\n  ".join(str(o) for o in _kandidaten())
    raise FileNotFoundError(f"Datenordner nicht gefunden. Gesucht wurde in:\n  {gesucht}")


def vorlagenordner() -> pathlib.Path:
    return datenordner() / "vorlagen"


def kabeltypenordner() -> pathlib.Path:
    return datenordner() / "kabeltypen"
