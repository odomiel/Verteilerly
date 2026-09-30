"""Versionsschema von Verteilerly.

Eine Version ist das Datum des Releases: ``jahr.monat.tag``, also
``2026.09.05``. Wird an einem Tag mehr als einmal gebaut, haengt an den
folgenden Builds ein ``b`` mit der Nummer des Builds:

    2026.09.05      erster Build des Tages
    2026.09.05b2    zweiter Build desselben Tages
    2026.09.05b3    dritter Build desselben Tages

Damit ist an der Version sofort ablesbar, von wann ein Stand ist - was bei
einem portablen Programm ohne Installation nuetzlich ist, weil auf einem
Stick durchaus mehrere Staende nebeneinander liegen koennen.
"""

from __future__ import annotations

import datetime as _datetime
import re
from typing import Iterable, NamedTuple

VERSION = "2026.09.30b2"

_MUSTER = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})(?:b(\d+))?$")


class UngueltigeVersion(ValueError):
    """Die Zeichenkette ist keine Verteilerly-Version."""


class Version(NamedTuple):
    """Eine zerlegte Version - vergleichbar und wieder zusammensetzbar."""

    datum: _datetime.date
    build: int  # 1 = erster Build des Tages

    def __str__(self) -> str:
        basis = f"{self.datum:%Y.%m.%d}"
        return basis if self.build <= 1 else f"{basis}b{self.build}"


def zerlegen(version: str) -> Version:
    """Liest eine Versionszeichenkette."""
    treffer = _MUSTER.match(version.strip())
    if not treffer:
        raise UngueltigeVersion(
            f"{version!r} ist keine Version - erwartet wird 2026.09.05 oder 2026.09.05b2"
        )
    jahr, monat, tag, build = treffer.groups()
    try:
        datum = _datetime.date(int(jahr), int(monat), int(tag))
    except ValueError as fehler:
        raise UngueltigeVersion(f"{version!r}: {fehler}") from None

    nummer = int(build) if build else 1
    if build is not None and nummer < 2:
        # b1 waere derselbe Stand wie die Version ohne Zusatz.
        raise UngueltigeVersion(
            f"{version!r}: der erste Build des Tages traegt kein 'b'"
        )
    return Version(datum, nummer)


def zusammensetzen(datum: _datetime.date, build: int = 1) -> str:
    """Baut eine Versionszeichenkette."""
    if build < 1:
        raise UngueltigeVersion("Die Buildnummer beginnt bei 1")
    return str(Version(datum, build))


def naechste_version(
    bestehende: Iterable[str], datum: _datetime.date | None = None
) -> str:
    """Die naechste Version fuer ``datum``, gemessen an den bisherigen.

    Unbekannte Zeichenketten werden uebergangen, damit ein handgesetztes
    Git-Tag den Release nicht blockiert.
    """
    datum = datum or _datetime.date.today()

    hoechster_build = 0
    for eintrag in bestehende:
        try:
            version = zerlegen(eintrag)
        except UngueltigeVersion:
            continue
        if version.datum == datum:
            hoechster_build = max(hoechster_build, version.build)

    return zusammensetzen(datum, hoechster_build + 1)


def sortierschluessel(version: str) -> tuple[_datetime.date, int]:
    """Schluessel zum Sortieren von Versionen in zeitlicher Reihenfolge."""
    zerlegt = zerlegen(version)
    return zerlegt.datum, zerlegt.build
