#!/usr/bin/env python3
"""Die Abhaengigkeiten gegen PyPI pruefen.

Ein Programm, das seine Bausteine selbst mitbringt, versteinert leicht:
im Abbild steckt, was am Baurechner zufaellig installiert war. Der erste
Bau eines Tages sieht darum nach, ob es neuere Fassungen gibt - einmal
taeglich, nicht bei jedem Bau, denn es fragt uebers Netz.

    python3 werkzeuge/abhaengigkeiten.py           einmal taeglich
    python3 werkzeuge/abhaengigkeiten.py --immer   jetzt nachsehen
    python3 werkzeuge/abhaengigkeiten.py --leise   nur bei Neuem melden

Gemeldet wird, nicht abgebrochen: ob eine neuere Fassung taugt, steht
auf einem anderen Blatt, und ohne Netz soll sich trotzdem bauen lassen.
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

WURZEL = pathlib.Path(__file__).resolve().parent.parent
ANFORDERUNGEN = WURZEL / "requirements.txt"
MERKZETTEL = WURZEL / "bau" / ".geprueft.json"
PYPI = "https://pypi.org/pypi/{}/json"
WARTEZEIT = 8.0          # Sekunden je Paket - ein Bau soll nicht haengen


def gefordert(datei: pathlib.Path | None = None) -> list[str]:
    """Die Pakete aus requirements.txt - eine Quelle, keine zweite Liste."""
    datei = datei or ANFORDERUNGEN
    if not datei.is_file():
        return []
    namen = []
    for zeile in datei.read_text(encoding="utf-8").splitlines():
        zeile = zeile.split("#")[0].strip()
        if not zeile:
            continue
        treffer = re.match(r"^[A-Za-z0-9._-]+", zeile)
        if treffer:
            namen.append(treffer.group(0))
    return namen


def installiert(name: str) -> str:
    """Welche Fassung hier liegt - oder nichts, wenn das Paket fehlt."""
    import importlib.metadata as metadaten

    try:
        return metadaten.version(name)
    except metadaten.PackageNotFoundError:
        return ""


def neueste(name: str, wartezeit: float = WARTEZEIT) -> str:
    """Was PyPI als neueste Fassung nennt - oder nichts, wenn es nicht geht."""
    try:
        with urllib.request.urlopen(PYPI.format(name), timeout=wartezeit) as antwort:
            daten = json.loads(antwort.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return ""
    return str(daten.get("info", {}).get("version") or "")


def _teile(fassung: str) -> tuple:
    """Fassungen vergleichbar machen: 6.11.2 kommt nach 6.9.1."""
    return tuple(
        int(teil) if teil.isdigit() else teil
        for teil in re.split(r"[._-]", fassung)
    )


def veraltet(hier: str, dort: str) -> bool:
    """Gibt es dort etwas Neueres? Bei Unvergleichbarem: nein."""
    if not hier or not dort or hier == dort:
        return False
    try:
        return _teile(dort) > _teile(hier)
    except TypeError:                 # Buchstaben gegen Zahlen
        return False


def pruefen(namen: list[str] | None = None) -> list[tuple[str, str, str]]:
    """Je Paket (Name, hier, auf PyPI). Leeres Feld heisst: nicht erfahren."""
    return [(name, installiert(name), neueste(name)) for name in (namen or gefordert())]


def bericht(stand: list[tuple[str, str, str]]) -> str:
    """Der Stand als Text - eine Zeile je Paket."""
    zeilen = []
    for name, hier, dort in stand:
        if not dort:
            hinweis = "PyPI nicht erreicht"
        elif veraltet(hier, dort):
            hinweis = f"neuer: {dort}"
        elif not hier:
            hinweis = "hier nicht installiert"
        else:
            hinweis = "aktuell"
        zeilen.append(f"  {name:14} {hier or '—':14} {hinweis}")
    return "\n".join(zeilen)


def _heute() -> str:
    return datetime.date.today().isoformat()


def schon_geprueft(merkzettel: pathlib.Path | None = None) -> bool:
    """Lief die Pruefung heute schon?"""
    merkzettel = merkzettel or MERKZETTEL
    try:
        return json.loads(merkzettel.read_text(encoding="utf-8")).get("tag") == _heute()
    except (OSError, ValueError):
        return False


def merken(
    stand: list[tuple[str, str, str]], merkzettel: pathlib.Path | None = None
) -> None:
    """Haelt fest, dass heute geprueft wurde - und was dabei herauskam."""
    merkzettel = merkzettel or MERKZETTEL
    merkzettel.parent.mkdir(parents=True, exist_ok=True)
    merkzettel.write_text(
        json.dumps(
            {
                "tag": _heute(),
                "stand": {name: {"hier": hier, "pypi": dort}
                          for name, hier, dort in stand},
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def taeglich(immer: bool = False, leise: bool = False) -> list[tuple[str, str, str]]:
    """Der Aufruf aus dem Bau: einmal am Tag nachsehen und melden."""
    if not immer and schon_geprueft():
        return []
    stand = pruefen()
    if not stand:
        return []
    merken(stand)
    neues = [zeile for zeile in stand if veraltet(zeile[1], zeile[2])]
    # flush: der Bau reicht danach an ein Unterprogramm weiter, dessen
    # Ausgabe sonst vor dieser hier stuende.
    if neues or not leise:
        print("Abhängigkeiten (einmal täglich geprüft):")
        print(bericht(stand), flush=True)
    if neues:
        print(
            "  → neuere Fassungen vorhanden. Aktualisieren mit:\n"
            "      .venv/bin/pip install -U "
            + " ".join(name for name, _, _ in neues),
            flush=True,
        )
    return stand


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--immer", action="store_true",
                          help="auch dann prüfen, wenn es heute schon lief")
    zerleger.add_argument("--leise", action="store_true",
                          help="nur melden, wenn es etwas Neueres gibt")
    argumente = zerleger.parse_args()
    stand = taeglich(immer=True if argumente.immer else False, leise=argumente.leise)
    if not stand and not argumente.immer:
        print("Heute schon geprüft — mit --immer noch einmal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
