"""Erweiterungen: was das Programm um eigene Werkzeuge ergaenzt.

Zwei Sorten gibt es. **Eingebaute** liegen in diesem Paket und stehen in
``EINGEBAUT``; eine feste Liste statt einer Suche, damit AppImage und .exe
sie ebenso finden wie der Quellbaum. **Fremde** sind Python-Dateien oder
-Pakete im Ordner ``erweiterungen`` des Arbeitsordners.

Beide sind ein Modul mit einem Objekt ``erweiterung``, das von
``Erweiterung`` erbt und in ``einrichten()`` seine Menueeintraege anmeldet.

Fremder Code laeuft mit allen Rechten des Programms. Darum wird eine
fremde Erweiterung erst geladen - und das heisst: ausgefuehrt -, wenn sie
eingeschaltet ist; bis dahin liest ``finden()`` nur ihren Docstring aus
der Datei, ohne sie auszufuehren. Eingebaute sind von Haus aus an, fremde
aus. Eine Erweiterung, die sich nicht laden oder einrichten laesst, wird
uebergangen; der Grund steht an ihrem ``Fund``.

Dieses Modul kennt kein Qt. Was eine Erweiterung vom Fenster sieht,
reicht ``gui.erweiterungen.Schnittstelle`` herein.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import pathlib
import re
import sys
from dataclasses import dataclass

from ..sprachen import u

#: Die eingebauten Erweiterungen - Module dieses Pakets.
EINGEBAUT = ("blattvorlageneditor",)

#: Ist diese Umgebungsvariable gesetzt, wird keine fremde Erweiterung
#: geladen - fuer den Fall, dass eine den Start verhindert, und fuer die
#: Testreihe, die sonst den echten Arbeitsordner mitlaede.
OHNE_FREMDE = "VERTEILERLY_OHNE_FREMDE_ERWEITERUNGEN"


class Erweiterung:
    """Grundlage jeder Erweiterung.

    ``kennung`` ist eindeutig und steht in der Verteilerly.conf, ``name``
    und ``beschreibung`` zeigt der Dialog *Erweiterungen verwalten*.
    ``einrichten()`` bekommt die Schnittstelle zum Programm und meldet dort
    an, was die Erweiterung anbietet - etwa mit ``menueeintrag()``.
    """

    kennung: str = ""
    name: str = ""
    beschreibung: str = ""

    def einrichten(self, programm) -> None:
        raise NotImplementedError


@dataclass
class Fund:
    """Eine gefundene Erweiterung - geladen oder nicht."""

    kennung: str
    name: str
    beschreibung: str = ""
    eingebaut: bool = True
    #: Datei oder Paketordner einer fremden Erweiterung.
    ort: pathlib.Path | None = None
    erweiterung: Erweiterung | None = None
    fehler: str = ""


def _erweiterung_aus(modul) -> Erweiterung:
    erweiterung = getattr(modul, "erweiterung", None)
    if not isinstance(erweiterung, Erweiterung):
        raise TypeError(u("kein Objekt „erweiterung“ vom Typ Erweiterung"))
    return erweiterung


def _meldung(fehler: BaseException) -> str:
    return f"{type(fehler).__name__}: {fehler}"


def _eingebaute() -> list[Fund]:
    funde = []
    for name in EINGEBAUT:
        try:
            erweiterung = _erweiterung_aus(importlib.import_module(f"{__name__}.{name}"))
        except Exception as fehler:  # noqa: BLE001 - eine kaputte nimmt das Programm nicht mit
            funde.append(Fund(name, name, fehler=_meldung(fehler)))
            continue
        funde.append(Fund(
            erweiterung.kennung or name, erweiterung.name or name,
            erweiterung.beschreibung, erweiterung=erweiterung,
        ))
    return funde


def _docstring(datei: pathlib.Path) -> str:
    """Die erste Zeile des Docstrings - gelesen, nicht ausgefuehrt."""
    try:
        text = ast.get_docstring(ast.parse(datei.read_text(encoding="utf-8"))) or ""
    except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
        return ""
    zeilen = text.strip().splitlines()
    return zeilen[0] if zeilen else ""


def _fremde(ordner_liste) -> list[Fund]:
    funde: list[Fund] = []
    gesehen: set[str] = set()
    for ordner in ordner_liste:
        ordner = pathlib.Path(ordner)
        if not ordner.is_dir():
            continue
        for ort in sorted(ordner.iterdir()):
            if ort.name.startswith(("_", ".")):
                continue
            if ort.is_file() and ort.suffix == ".py":
                datei, kennung = ort, ort.stem
            elif ort.is_dir() and (ort / "__init__.py").is_file():
                datei, kennung = ort / "__init__.py", ort.name
            else:
                continue
            # Der wichtigste Ort kommt zuerst - bei gleichem Namen gilt er.
            if kennung in gesehen:
                continue
            gesehen.add(kennung)
            funde.append(Fund(kennung, kennung, _docstring(datei), eingebaut=False, ort=ort))
    return funde


def finden(ordner_liste=()) -> list[Fund]:
    """Alle Erweiterungen: die eingebauten, dann die fremden aus ``ordner_liste``.

    Fremde werden dabei nicht ausgefuehrt; dafuer ist ``laden()`` da.
    """
    eingebaut = _eingebaute()
    vergeben = {fund.kennung for fund in eingebaut}
    fremde = _fremde(ordner_liste)
    for fund in fremde:
        if fund.kennung in vergeben:
            fund.fehler = u("Die Kennung {0!r} trägt schon eine eingebaute Erweiterung").format(fund.kennung)
    return eingebaut + fremde


def eingeschaltet(fund: Fund, an, aus) -> bool:
    """Eingebaute sind an, bis sie ausgeschaltet werden - fremde umgekehrt."""
    if fund.eingebaut:
        return fund.kennung not in aus
    return fund.kennung in an


def laden(fund: Fund) -> None:
    """Fuehrt eine fremde Erweiterung aus und haengt sie an den Fund.

    Was dabei schiefgeht - ein Syntaxfehler, ein fehlendes Modul, kein
    Objekt ``erweiterung`` -, steht danach in ``fund.fehler``.
    """
    if fund.erweiterung is not None or fund.fehler or fund.ort is None:
        return
    paket = fund.ort.is_dir()
    datei = fund.ort / "__init__.py" if paket else fund.ort
    modulname = "verteilerly_erweiterung_" + re.sub(r"\W", "_", fund.kennung)
    try:
        bauplan = importlib.util.spec_from_file_location(
            modulname, datei,
            submodule_search_locations=[str(fund.ort)] if paket else None,
        )
        modul = importlib.util.module_from_spec(bauplan)
        sys.modules[modulname] = modul
        bauplan.loader.exec_module(modul)
        erweiterung = _erweiterung_aus(modul)
    except (Exception, SystemExit) as fehler:  # noqa: BLE001 - fremder Code
        sys.modules.pop(modulname, None)
        fund.fehler = _meldung(fehler)
        return
    fund.erweiterung = erweiterung
    fund.name = erweiterung.name or fund.kennung
    fund.beschreibung = erweiterung.beschreibung or fund.beschreibung


def wahl_lesen(text) -> set[str]:
    """Kennungen aus der Verteilerly.conf - als Text mit Kommas gemerkt."""
    return {teil.strip() for teil in str(text or "").split(",") if teil.strip()}


def wahl_schreiben(kennungen) -> str:
    return ",".join(sorted(kennungen))
