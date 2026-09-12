"""Vorlagen und Einstellungen als Paket sichern und einspielen.

Wer an zwei Rechnern arbeitet oder einen neu aufsetzt, will seine
Verteilervorlagen, Blattvorlagen, Kabeltypen und seine Einstellungen
mitnehmen - nicht Datei fuer Datei zusammensuchen. Ein Paket ist eine
gewoehnliche ZIP-Datei mit genau diesen Sachen und einem Merkzettel, an
dem sich beim Einspielen erkennen laesst, dass es eines von uns ist.

Beim Einspielen wird nichts blind ausgepackt: uebernommen werden nur die
bekannten Unterordner, nur ``*.yaml`` und die Einstellungsdatei, und nur
Namen ohne Pfadanteil. Ein Paket aus fremder Hand soll nichts ausserhalb
des Arbeitsordners anlegen koennen.
"""

from __future__ import annotations

import datetime
import json
import pathlib
import zipfile

from .version import VERSION

KENNUNG = "verteilerly-paket"
MERKZETTEL = "paket.json"
CONFNAME = "Verteilerly.conf"
# Was ein Paket tragen darf - mehr wird weder eingepackt noch ausgepackt.
UNTERORDNER = ("vorlagen", "blattvorlagen", "kabeltypen")
ENDUNG = ".yaml"


class PaketFehler(Exception):
    """Das Paket ist keines oder laesst sich nicht schreiben."""


def _dateien(datenordner: pathlib.Path) -> list[tuple[str, pathlib.Path]]:
    """Die YAML-Dateien des Arbeitsordners, mit ihrem Namen im Paket."""
    gefunden: list[tuple[str, pathlib.Path]] = []
    for name in UNTERORDNER:
        ordner = datenordner / name
        if not ordner.is_dir():
            continue
        for datei in sorted(ordner.glob(f"*{ENDUNG}")):
            gefunden.append((f"{name}/{datei.name}", datei))
    return gefunden


def sichern(
    ziel: pathlib.Path,
    datenordner: pathlib.Path,
    einstellungen: pathlib.Path | None = None,
) -> dict[str, int]:
    """Schreibt Vorlagen und Einstellungen in eine ZIP-Datei.

    Zurueck kommt, was hineingegangen ist - je Unterordner die Zahl der
    Dateien und ob die Einstellungen dabei sind.
    """
    ziel = pathlib.Path(ziel)
    dateien = _dateien(pathlib.Path(datenordner))
    conf = pathlib.Path(einstellungen) if einstellungen else None
    mit_conf = bool(conf and conf.is_file())

    merkzettel = {
        "kennung": KENNUNG,
        "version": VERSION,
        "erstellt": datetime.datetime.now().isoformat(timespec="seconds"),
        "dateien": [name for name, _ in dateien],
        "einstellungen": mit_conf,
    }

    try:
        with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED) as paket:
            paket.writestr(MERKZETTEL, json.dumps(merkzettel, indent=2))
            for name, datei in dateien:
                paket.write(datei, name)
            if mit_conf:
                paket.write(conf, CONFNAME)
    except OSError as fehler:
        raise PaketFehler(str(fehler)) from fehler

    bericht = {name: 0 for name in UNTERORDNER}
    for name, _ in dateien:
        bericht[name.split("/")[0]] += 1
    bericht["einstellungen"] = int(mit_conf)
    return bericht


def _brauchbar(name: str) -> bool:
    """Nimmt nur, was ins Paket gehoert - ohne Pfadanteil.

    Ein Paket aus fremder Hand soll nichts ausserhalb des Arbeitsordners
    anlegen koennen; ".." und absolute Pfade fliegen deshalb heraus.
    """
    if name == CONFNAME:
        return True
    teile = name.split("/")
    if len(teile) != 2:
        return False
    ordner, datei = teile
    if ordner not in UNTERORDNER or not datei.endswith(ENDUNG):
        return False
    return datei not in ("", ".", "..") and "\\" not in datei


def inhalt(quelle: pathlib.Path) -> dict:
    """Was in einem Paket steckt - ohne etwas auszupacken."""
    try:
        with zipfile.ZipFile(pathlib.Path(quelle)) as paket:
            try:
                merkzettel = json.loads(paket.read(MERKZETTEL))
            except KeyError:
                raise PaketFehler(
                    "Das ist kein Verteilerly-Paket: der Merkzettel fehlt"
                ) from None
            namen = [n for n in paket.namelist() if _brauchbar(n)]
    except zipfile.BadZipFile as fehler:
        raise PaketFehler(f"Die Datei ist kein Paket: {fehler}") from fehler
    except OSError as fehler:
        raise PaketFehler(str(fehler)) from fehler

    if merkzettel.get("kennung") != KENNUNG:
        raise PaketFehler("Das ist kein Verteilerly-Paket")

    bericht = {name: 0 for name in UNTERORDNER}
    for name in namen:
        if name != CONFNAME:
            bericht[name.split("/")[0]] += 1
    bericht["einstellungen"] = int(CONFNAME in namen)
    bericht["version"] = merkzettel.get("version", "")
    bericht["erstellt"] = merkzettel.get("erstellt", "")
    return bericht


def einspielen(
    quelle: pathlib.Path,
    datenordner: pathlib.Path,
    einstellungen: pathlib.Path | None = None,
) -> dict[str, int]:
    """Packt ein Paket in den Arbeitsordner aus.

    Gleichnamige Dateien werden ersetzt - das ist der Sinn der Sache:
    ein Paket bringt den Stand mit, den es enthaelt. Was im Paket fehlt,
    bleibt unangetastet.
    """
    quelle = pathlib.Path(quelle)
    datenordner = pathlib.Path(datenordner)
    inhalt(quelle)                       # prueft Kennung und Lesbarkeit

    bericht = {name: 0 for name in UNTERORDNER}
    bericht["einstellungen"] = 0
    try:
        with zipfile.ZipFile(quelle) as paket:
            for name in paket.namelist():
                if not _brauchbar(name):
                    continue
                if name == CONFNAME:
                    if einstellungen is None:
                        continue
                    ziel = pathlib.Path(einstellungen)
                else:
                    ziel = datenordner / name
                    bericht[name.split("/")[0]] += 1
                ziel.parent.mkdir(parents=True, exist_ok=True)
                ziel.write_bytes(paket.read(name))
                if name == CONFNAME:
                    bericht["einstellungen"] = 1
    except OSError as fehler:
        raise PaketFehler(str(fehler)) from fehler
    return bericht
