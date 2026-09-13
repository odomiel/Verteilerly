#!/usr/bin/env python3
"""Verteilerly verpacken.

Ein Aufruf, zwei Plattformen - der Unterschied liegt nur im Verpacken:

    python3 werkzeuge/bauen.py            fuer die laufende Plattform
    python3 werkzeuge/bauen.py --exe      erzwingt den Windows-Weg
    python3 werkzeuge/bauen.py --appimage erzwingt den Linux-Weg
    python3 werkzeuge/bauen.py --sauber   Bau- und Zielordner vorher leeren
    python3 werkzeuge/bauen.py --ohne-pruefung  ohne Blick auf PyPI

Der erste Bau eines Tages sieht nach, ob es neuere Fassungen der
Abhaengigkeiten gibt (werkzeuge/abhaengigkeiten.py). Gemeldet wird nur:
ob eine neuere Fassung taugt, entscheidet niemand nebenbei, und ohne
Netz soll sich trotzdem bauen lassen. Gemerkt wird der Tag in
bau/.geprueft.json - nach --sauber wird also wieder nachgesehen.

Windows: build_windows.ps1 baut ueber Verteilerly.spec eine einzelne .exe.
Linux:   werkzeuge/appimage.py baut ein AppImage, das Python und Qt selbst
         mitbringt.

Gebaut wird immer auf der Zielplattform: PyInstaller packt den Python,
der es aufruft, und uebersetzt nicht ueber die Plattform hinweg.
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import abhaengigkeiten  # noqa: E402  - liegt neben dieser Datei

from verteilerly.version import VERSION  # noqa: E402

BAUORDNER = WURZEL / "bau"
ZIELORDNER = WURZEL / "auslieferung"


def appimage_bauen(argumente: list[str]) -> int:
    return subprocess.run(
        [sys.executable, str(WURZEL / "werkzeuge" / "appimage.py"), *argumente]
    ).returncode


def exe_bauen(argumente: list[str]) -> int:
    """Reicht an das PowerShell-Skript weiter - dort steht das Rezept."""
    skript = WURZEL / "build_windows.ps1"
    if not sys.platform.startswith("win"):
        print(
            "Die .exe muss unter Windows gebaut werden - PyInstaller packt den\n"
            "Python, der es aufruft, und übersetzt nicht über die Plattform\n"
            "hinweg. Dort dann:\n"
            f"    powershell -ExecutionPolicy Bypass -File {skript.name}\n"
            "Siehe BUILD_WINDOWS.md.",
            file=sys.stderr,
        )
        return 1
    return subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(skript), *argumente]
    ).returncode


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    gruppe = zerleger.add_mutually_exclusive_group()
    gruppe.add_argument("--exe", action="store_true", help="Windows-.exe bauen")
    gruppe.add_argument("--appimage", action="store_true", help="AppImage bauen")
    zerleger.add_argument("--sauber", action="store_true",
                          help="Bau- und Zielordner vorher leeren")
    zerleger.add_argument("--ohne-pruefung", action="store_true",
                          help="die tägliche Prüfung der Abhängigkeiten auslassen")
    argumente, rest = zerleger.parse_known_args()

    windows = argumente.exe or (
        not argumente.appimage and sys.platform.startswith("win")
    )
    # flush, weil das Verpacken gleich an ein Unterprogramm weiterreicht:
    # dessen Ausgabe ginge sonst dieser hier voraus.
    print(
        f"Verteilerly {VERSION} — {'Windows-.exe' if windows else 'AppImage'}",
        flush=True,
    )

    if argumente.sauber:
        for ordner in (BAUORDNER, ZIELORDNER):
            shutil.rmtree(ordner, ignore_errors=True)

    # Nach dem Aufräumen, nicht davor: der Merkzettel liegt im Bauordner
    # und wäre sonst gleich wieder weg.
    if not argumente.ohne_pruefung:
        abhaengigkeiten.taeglich()

    return exe_bauen(rest) if windows else appimage_bauen(rest)


if __name__ == "__main__":
    raise SystemExit(main())
