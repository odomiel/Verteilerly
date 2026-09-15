#!/usr/bin/env python3
"""Die Abhaengigkeiten gegen PyPI und das Abbild-Python pruefen.

Ein Programm, das seine Bausteine selbst mitbringt, versteinert leicht:
im Abbild steckt, was am Baurechner zufaellig installiert war. Der erste
Bau eines Tages sieht darum nach, ob es neuere Fassungen gibt - einmal
taeglich, nicht bei jedem Bau, denn es fragt uebers Netz.

Geprueft wird auch der Unterbau des AppImage: die Python-AppImage von
python-appimage, mit der gebaut wird. Sie kommt nicht von PyPI und faellt
darum sonst durch jedes Raster - dabei ist sie der groesste Baustein,
den das Abbild mitschleppt.

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
ANFORDERUNGEN = (WURZEL / "requirements.txt",)
MERKZETTEL = WURZEL / "bau" / ".geprueft.json"
PYPI = "https://pypi.org/pypi/{}/json"
WARTEZEIT = 8.0          # Sekunden je Paket - ein Bau soll nicht haengen

# Der Unterbau des AppImage. Welche Datei geholt wird, steht im
# Bauskript; eine zweite Angabe hier gaebe es nur, damit sie eines Tages
# nicht mehr stimmt.
BAUSKRIPT = WURZEL / "werkzeuge" / "appimage.py"
PYTHON_ABBILDER = (
    "https://api.github.com/repos/niess/python-appimage/releases?per_page=100"
)
# Dieselbe Bauart wie die eingebaute: manylinux2014 (glibc 2.17) und kein
# "t" hinter der cp-Nummer - das waere der Free-threaded-Bau, fuer den es
# kein Qt-Rad gibt.
PYTHON_ABBILD_MUSTER = re.compile(
    r"python(\d+)\.(\d+)\.(\d+)-cp\d+-cp\d+-manylinux2014_x86_64\.AppImage"
)


def gefordert(datei: pathlib.Path | None = None) -> list[str]:
    """Die Pakete aus den Anforderungsdateien.

    Sie sind die eine Quelle; eine zweite Liste im Pruefwerkzeug gaebe es
    nur, damit sie eines Tages nicht mehr stimmt. Ohne Angabe werden alle
    gelesen, in ihrer Reihenfolge und ohne Doppelte.
    """
    dateien = [datei] if datei is not None else list(ANFORDERUNGEN)
    namen: list[str] = []
    for eine in dateien:
        if not eine.is_file():
            continue
        for zeile in eine.read_text(encoding="utf-8").splitlines():
            zeile = zeile.split("#")[0].strip()
            if not zeile:
                continue
            treffer = re.match(r"^[A-Za-z0-9._-]+", zeile)
            if treffer and treffer.group(0) not in namen:
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
        zeilen.append(f"  {name:16} {hier or '—':14} {hinweis}")
    return "\n".join(zeilen)


def python_basis(datei: pathlib.Path | None = None) -> str:
    """Mit welcher Python-AppImage gebaut wird - aus dem Bauskript gelesen.

    Dort steht sie als BASIS_URL; sie hier noch einmal hinzuschreiben
    hiesse, zwei Angaben zu pflegen und eine zu vergessen.
    """
    datei = datei or BAUSKRIPT
    try:
        text = datei.read_text(encoding="utf-8")
    except OSError:
        return ""
    treffer = PYTHON_ABBILD_MUSTER.search(text)
    return ".".join(treffer.groups()) if treffer else ""


def python_abbilder(wartezeit: float = WARTEZEIT) -> list[str]:
    """Welche Python-AppImages es gibt - passender Bauart, neueste zuerst.

    GitHub verlangt eine Kennung des Aufrufers; ohne sie kaeme 403
    zurueck. Geht etwas schief, ist die Liste leer: gemeldet wird dann
    "nicht erreicht", abgebrochen wird nie.
    """
    anfrage = urllib.request.Request(
        PYTHON_ABBILDER,
        headers={
            "User-Agent": "Verteilerly-Abhaengigkeitspruefung",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=wartezeit) as antwort:
            daten = json.loads(antwort.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return []
    fassungen = set()
    for ausgabe in daten if isinstance(daten, list) else []:
        for stueck in ausgabe.get("assets", []):
            treffer = PYTHON_ABBILD_MUSTER.fullmatch(str(stueck.get("name", "")))
            if treffer:
                fassungen.add(".".join(treffer.groups()))
    return sorted(fassungen, key=_teile, reverse=True)


def python_pruefen(wartezeit: float = WARTEZEIT) -> tuple[str, str, str]:
    """(eingebaut, neueste derselben Reihe, neueste Reihe ueberhaupt).

    Zweierlei, weil es zweierlei Entscheidungen sind: eine neue Ausgabe
    derselben Reihe (3.14.7 → 3.14.8) ist ein Austausch, eine neue Reihe
    (3.14 → 3.15) will erst geprueft sein - die Raeder muessen mit.
    """
    hier = python_basis()
    alle = python_abbilder(wartezeit)
    if not hier or not alle:
        return hier, "", ""
    reihe = hier.rsplit(".", 1)[0] + "."
    gleiche = [f for f in alle if f.startswith(reihe)]
    neueste_reihe = alle[0]
    return (
        hier,
        gleiche[0] if gleiche else "",
        neueste_reihe if veraltet(hier, neueste_reihe) else "",
    )


def python_bericht(stand: tuple[str, str, str]) -> str:
    """Die Zeile zum Abbild-Python - im Format der uebrigen."""
    hier, dort, reihe = stand
    if not hier:
        hinweis = "im Bauskript nicht gefunden"
    elif not dort:
        hinweis = "GitHub nicht erreicht"
    elif veraltet(hier, dort):
        hinweis = f"neuer: {dort}"
    else:
        hinweis = "aktuell"
    if reihe and reihe.rsplit(".", 1)[0] != hier.rsplit(".", 1)[0]:
        hinweis += f" (neue Reihe: {reihe})"
    return f"  {'Python (Abbild)':16} {hier or '—':14} {hinweis}"


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
    stand: list[tuple[str, str, str]],
    merkzettel: pathlib.Path | None = None,
    python: tuple[str, str, str] | None = None,
) -> None:
    """Haelt fest, dass heute geprueft wurde - und was dabei herauskam."""
    merkzettel = merkzettel or MERKZETTEL
    merkzettel.parent.mkdir(parents=True, exist_ok=True)
    notiz = {
        "tag": _heute(),
        "stand": {name: {"hier": hier, "pypi": dort}
                  for name, hier, dort in stand},
    }
    if python:
        hier, dort, reihe = python
        notiz["python"] = {"hier": hier, "reihe": dort, "neueste": reihe or dort}
    merkzettel.write_text(json.dumps(notiz, indent=2), encoding="utf-8")


def taeglich(immer: bool = False, leise: bool = False) -> list[tuple[str, str, str]]:
    """Der Aufruf aus dem Bau: einmal am Tag nachsehen und melden."""
    if not immer and schon_geprueft():
        return []
    stand = pruefen()
    if not stand:
        return []
    python = python_pruefen()
    merken(stand, python=python)
    neues = [zeile for zeile in stand if veraltet(zeile[1], zeile[2])]
    hier, dort, reihe = python
    python_neu = veraltet(hier, dort) or bool(reihe)
    # flush: der Bau reicht danach an ein Unterprogramm weiter, dessen
    # Ausgabe sonst vor dieser hier stuende.
    if neues or python_neu or not leise:
        print("Abhängigkeiten (einmal täglich geprüft):")
        print(bericht(stand))
        print(python_bericht(python), flush=True)
    if neues:
        print(
            "  → neuere Fassungen vorhanden. Aktualisieren mit:\n"
            "      .venv/bin/pip install -U "
            + " ".join(name for name, _, _ in neues),
            flush=True,
        )
    if python_neu:
        print(
            "  → neuere Python-AppImage vorhanden. In werkzeuge/appimage.py\n"
            "      PYTHONFASSUNG und BASIS_URL anpassen, dann die Pfade in\n"
            "      lizenzen/QUELLEN.txt nachziehen.",
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
