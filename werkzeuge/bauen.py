#!/usr/bin/env python3
"""Verteilerly verpacken.

Ein Aufruf, zwei Plattformen - der Unterschied liegt nur im Verpacken:

    python3 werkzeuge/bauen.py            fuer die laufende Plattform
    python3 werkzeuge/bauen.py --exe      erzwingt den Windows-Weg
    python3 werkzeuge/bauen.py --appimage erzwingt den Linux-Weg
    python3 werkzeuge/bauen.py --sauber   Bau- und Zielordner vorher leeren

Windows: werkzeuge/exe.py baut eine einzelne .exe mit PyInstaller.
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

from verteilerly.version import VERSION  # noqa: E402

BAUORDNER = WURZEL / "bau"
ZIELORDNER = WURZEL / "auslieferung"


def weiterreichen(skript: str, argumente: list[str]) -> int:
    return subprocess.run(
        [sys.executable, str(WURZEL / "werkzeuge" / skript), *argumente]
    ).returncode


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    gruppe = zerleger.add_mutually_exclusive_group()
    gruppe.add_argument("--exe", action="store_true", help="Windows-.exe bauen")
    gruppe.add_argument("--appimage", action="store_true", help="AppImage bauen")
    zerleger.add_argument("--sauber", action="store_true",
                          help="Bau- und Zielordner vorher leeren")
    argumente, rest = zerleger.parse_known_args()

    if argumente.sauber:
        for ordner in (BAUORDNER, ZIELORDNER):
            shutil.rmtree(ordner, ignore_errors=True)

    windows = argumente.exe or (
        not argumente.appimage and sys.platform.startswith("win")
    )
    print(f"Verteilerly {VERSION} — {'Windows-.exe' if windows else 'AppImage'}")
    return weiterreichen("exe.py" if windows else "appimage.py", rest)


if __name__ == "__main__":
    raise SystemExit(main())
