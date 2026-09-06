#!/usr/bin/env python3
"""Die Angaben schreiben, die Windows unter Dateieigenschaften anzeigt.

Bei einem Programm, das ohne Installation als einzelne Datei weitergereicht
wird, sind die Eigenschaften der Datei die einzige Stelle, an der der Stand
ablesbar ist. Die Spec nimmt die erzeugte Datei auf, wenn sie da ist.

    python3 werkzeuge/windowsangaben.py
"""

from __future__ import annotations

import pathlib
import sys

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from verteilerly.version import VERSION, zerlegen  # noqa: E402

ZIEL = WURZEL / "bau" / "version.txt"

MUSTER = """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({vier}), prodvers=({vier}),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040704B0', [
        StringStruct('FileDescription', 'Dokumentation für LSA+-Verteiler'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', 'Verteilerly'),
        StringStruct('OriginalFilename', 'Verteilerly_{version}.exe'),
        StringStruct('ProductName', 'Verteilerly'),
        StringStruct('ProductVersion', '{version}'),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1031, 1200])])
  ]
)
"""


def schreiben(ziel: pathlib.Path = ZIEL) -> pathlib.Path:
    teile = zerlegen(VERSION)
    datum = teile.datum
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(
        MUSTER.format(
            vier=f"{datum.year}, {datum.month}, {datum.day}, {teile.build}",
            version=VERSION,
        ),
        encoding="utf-8",
    )
    return ziel


def main() -> int:
    datei = schreiben()
    print(f"· {datei} ({VERSION})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
