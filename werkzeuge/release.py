#!/usr/bin/env python3
"""Naechste Release-Version bestimmen und als Git-Tag setzen.

Die Version ist das Releasedatum (``2026.09.05``); mehrere Builds an einem
Tag bekommen ``b2``, ``b3`` und so weiter. Die bisherigen Versionen werden
aus den Git-Tags gelesen, damit es keine zweite Quelle gibt, die aus dem
Tritt geraten kann.

    python3 werkzeuge/release.py            zeigt die naechste Version an
    python3 werkzeuge/release.py --setzen   schreibt sie und setzt das Tag
"""

from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import subprocess
import sys

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from verteilerly.version import (  # noqa: E402
    UngueltigeVersion,
    naechste_version,
    sortierschluessel,
)

VERSIONSDATEI = WURZEL / "verteilerly" / "version.py"


def git(*argumente: str) -> str:
    ergebnis = subprocess.run(
        ["git", "-C", str(WURZEL), *argumente],
        capture_output=True,
        text=True,
        check=True,
    )
    return ergebnis.stdout.strip()


def vorhandene_tags() -> list[str]:
    ausgabe = git("tag", "--list")
    return [zeile.strip() for zeile in ausgabe.splitlines() if zeile.strip()]


def versionsdatei_schreiben(version: str) -> None:
    """Setzt VERSION in verteilerly/version.py auf den neuen Wert."""
    text = VERSIONSDATEI.read_text(encoding="utf-8")
    neu, ersetzt = re.subn(
        r'^VERSION = "[^"]*"$', f'VERSION = "{version}"', text, count=1, flags=re.M
    )
    if not ersetzt:
        raise SystemExit(f"VERSION nicht gefunden in {VERSIONSDATEI}")
    VERSIONSDATEI.write_text(neu, encoding="utf-8")


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument(
        "--setzen",
        action="store_true",
        help="Versionsdatei schreiben, committen und das Tag setzen",
    )
    zerleger.add_argument(
        "--datum",
        help="Releasedatum als JJJJ-MM-TT (Vorgabe: heute)",
    )
    argumente = zerleger.parse_args()

    datum = (
        datetime.date.fromisoformat(argumente.datum)
        if argumente.datum
        else datetime.date.today()
    )

    tags = vorhandene_tags()
    version = naechste_version(tags, datum)

    bekannt = []
    for tag in tags:
        try:
            sortierschluessel(tag)
        except UngueltigeVersion:
            continue
        bekannt.append(tag)
    bekannt.sort(key=sortierschluessel)

    print(f"bisherige Releases: {', '.join(bekannt) if bekannt else 'keine'}")
    print(f"naechste Version  : {version}")

    if not argumente.setzen:
        print("\n(nur angezeigt - mit --setzen wird das Tag geschrieben)")
        return 0

    if git("status", "--porcelain"):
        print("\nAbbruch: das Arbeitsverzeichnis ist nicht sauber.", file=sys.stderr)
        return 1

    versionsdatei_schreiben(version)
    git("add", str(VERSIONSDATEI.relative_to(WURZEL)))
    git("commit", "-m", f"Release {version}")
    git("tag", "-a", version, "-m", f"Verteilerly {version}")
    print(f"\nTag {version} gesetzt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
