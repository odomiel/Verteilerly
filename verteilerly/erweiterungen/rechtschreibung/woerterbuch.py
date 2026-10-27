"""Rechtschreibung ohne Netz: Hunspell-Woerterbuecher ueber spylls.

``spylls`` ist Hunspell in reinem Python - kein Compiler, keine
Systembibliothek, damit auch im AppImage und in der .exe zu haben. Es
liest dieselben ``.aff``/``.dic``-Dateien wie LibreOffice.

**Woher die Woerterbuecher kommen**, sagt ``pfade.woerterbuchordner_alle()``:
eigene vor denen des Rechners vor dem Mitgelieferten. ``vorhandene()``
sagt, welche Kennungen zu haben sind (``de_DE``, ``en_US`` …).

**Nachschlagen ist umsonst, Vorschlagen kostet.** Gemessen: 200 bekannte
Woerter nachzuschlagen dauert eine Millisekunde, **ein** Vorschlag
dagegen zweieinhalb Sekunden. Darum trennt dieses Modul beides -
``pruefen()`` sammelt nur die unbekannten Woerter, ``vorschlaege()``
holt die Vorschlaege zu **einem** davon, und zwar erst, wenn jemand die
Zeile anklickt.

**Was uebergangen wird**, und warum: Woerter unter drei Buchstaben
(davon lebt eine Verteilerbeschriftung), reine Grossschreibungen
(``LSA``, ``BMZ`` - Abkuerzungen sind in diesem Fach die Regel, und ein
Woerterbuch kennt keine davon) und alles, was in der eigenen Wortliste
steht. Ein Wort mit Bindestrich gilt als richtig, wenn jeder Teil es
ist: ``Melder-Kreis`` kennt kein Woerterbuch als Ganzes.

**Das Woerterbuch irrt auch.** Die deutschen Kompositaregeln lassen
Zusammensetzungen durchgehen, die keine sind - ``Werkstat`` etwa wird
nicht beanstandet. Eine Rechtschreibpruefung findet Tippfehler, sie
buergt nicht fuer Richtigkeit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ... import pfade
from ...sprachen import u
from ...suche import Fundstelle
from .pruefer import VORSCHLAEGE, WOERTERBUCH, Befund

#: Wie die Datei mit den eigenen Woertern im Arbeitsordner heisst.
EIGENE_WOERTER = "woerterbuch.txt"

#: Kuerzer schlaegt kein Woerterbuch nach - „a", „ab", „DA" sind in
#: einer Verteilerbeschriftung keine Rechtschreibung.
MINDESTLAENGE = 3

#: Ein Wort: Buchstaben, mit Bindestrich oder Apostroph dazwischen.
_WORTE = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*")

#: Einmal geladen, dann gehalten: das Laden dauert rund eine Sekunde.
_GELADEN: dict[str, object] = {}


class WoerterbuchFehler(Exception):
    """Kein Woerterbuch, oder keines, das sich lesen laesst."""


@dataclass(frozen=True)
class Woerterbuchfund:
    """Ein Woerterbuch mit seiner Kennung und dem Ort, an dem es liegt."""

    kennung: str
    ort: object            # pathlib.Path ohne Endung


def verfuegbar() -> bool:
    """Ist spylls ueberhaupt da?

    Es steht in ``requirements.txt`` und reist mit; wer aus dem
    Quelltext startet, kann es trotzdem vergessen haben. Dann bleibt die
    Pruefung ohne Netz eben aus, statt das Programm mitzunehmen.
    """
    try:
        import spylls.hunspell       # noqa: F401
    except Exception:                # noqa: BLE001 - fehlt es, fehlt es
        return False
    return True


def vorhandene() -> dict[str, object]:
    """Welche Woerterbuecher zu haben sind: Kennung -> Pfad ohne Endung.

    Der erste Fund gewinnt - die Reihenfolge der Ordner entscheidet.
    """
    gefunden: dict[str, object] = {}
    for ordner in pfade.woerterbuchordner_alle():
        for aff in sorted(ordner.glob("*.aff")):
            if not aff.with_suffix(".dic").is_file():
                continue
            gefunden.setdefault(aff.stem, aff.with_suffix(""))
    return gefunden


def passendes(sprache: str) -> Woerterbuchfund | None:
    """Das Woerterbuch zur Sprache - ``de-DE`` findet auch ``de_DE_frami``.

    Gesucht wird in drei Stufen: genau diese Kennung, dann eine, die so
    anfaengt (die Auslieferungen haengen gern ``_frami`` an), dann
    irgendeine derselben Sprache. ``auto`` hat keines: raten kann das
    Woerterbuch nicht, dafuer ist LanguageTool da.
    """
    kennung = (sprache or "").strip().replace("-", "_")
    if not kennung or kennung == "auto":
        return None
    vorrat = vorhandene()
    if kennung in vorrat:
        return Woerterbuchfund(kennung, vorrat[kennung])
    for name in sorted(vorrat):
        if name.startswith(kennung):
            return Woerterbuchfund(name, vorrat[name])
    sprachteil = kennung.split("_")[0]
    for name in sorted(vorrat):
        if name.split("_")[0] == sprachteil:
            return Woerterbuchfund(name, vorrat[name])
    return None


def laden(fund: Woerterbuchfund):
    """Das Woerterbuch - beim zweiten Mal aus dem Gedaechtnis."""
    schluessel = str(fund.ort)
    if schluessel not in _GELADEN:
        try:
            from spylls.hunspell import Dictionary
        except Exception as fehler:      # noqa: BLE001
            raise WoerterbuchFehler(u(
                "Für die Prüfung ohne Netz fehlt spylls."
            )) from fehler
        try:
            _GELADEN[schluessel] = Dictionary.from_files(str(fund.ort))
        except Exception as fehler:      # noqa: BLE001 - krumme Datei
            raise WoerterbuchFehler(u(
                "Das Wörterbuch {0} ist nicht zu lesen ({1})."
            ).format(fund.kennung, f"{type(fehler).__name__}: {fehler}")) from fehler
    return _GELADEN[schluessel]


def woerter(text: str):
    """Die Woerter eines Textes mit ihrer Stelle darin."""
    for treffer in _WORTE.finditer(text or ""):
        yield treffer.group(0), treffer.start()


def uebergangen(wort: str, eigene: frozenset[str] = frozenset()) -> bool:
    """Woerter, zu denen ein Woerterbuch nichts zu sagen hat."""
    if len(wort) < MINDESTLAENGE:
        return True
    if wort == wort.upper():
        # Reine Grossschreibung ist in diesem Fach eine Abkuerzung.
        return True
    return wort.casefold() in eigene


def pruefen(
    stellen: list[Fundstelle],
    fund: Woerterbuchfund,
    eigene: frozenset[str] = frozenset(),
) -> list[Befund]:
    """Alle Stellen nachschlagen - ohne Vorschlaege, die kosten zu viel."""
    woerterbuch = laden(fund)
    befunde: list[Befund] = []
    bekannt: dict[str, bool] = {}
    for stelle in stellen:
        for wort, von in woerter(stelle.text):
            if uebergangen(wort, eigene):
                continue
            if wort not in bekannt:
                bekannt[wort] = _kennt(woerterbuch, wort)
            if bekannt[wort]:
                continue
            befunde.append(Befund(
                stelle=stelle,
                von=von,
                laenge=len(wort),
                meldung=u("Unbekanntes Wort"),
                regel=fund.kennung,
                art="misspelling",
                quelle=WOERTERBUCH,
            ))
    return befunde


def _kennt(woerterbuch, wort: str) -> bool:
    """Steht das Wort im Woerterbuch - notfalls Teil fuer Teil?"""
    try:
        if woerterbuch.lookup(wort):
            return True
    except Exception:            # noqa: BLE001 - ein Wort reisst nichts mit
        return True
    if "-" in wort:
        teile = [teil for teil in wort.split("-") if teil]
        return bool(teile) and all(
            len(teil) < MINDESTLAENGE or woerterbuch.lookup(teil) for teil in teile
        )
    return False


def vorschlaege(
    fund: Woerterbuchfund, wort: str, hoechstens: int = VORSCHLAEGE
) -> tuple[str, ...]:
    """Vorschlaege zu **einem** Wort - der teure Teil, darum einzeln."""
    woerterbuch = laden(fund)
    try:
        gefunden = []
        for vorschlag in woerterbuch.suggest(wort):
            gefunden.append(vorschlag)
            if len(gefunden) >= hoechstens:
                break
        return tuple(gefunden)
    except Exception:            # noqa: BLE001 - ohne Vorschlag eben ohne
        return ()


# -- Die eigenen Woerter ---------------------------------------------------


def eigene_datei():
    """Wo die eigene Wortliste steht - im Arbeitsordner, wie alles andere."""
    return pfade.eigener_datenordner() / EIGENE_WOERTER


def eigene_lesen(datei=None) -> frozenset[str]:
    """Die eigene Wortliste, kleingeschrieben; eine fehlende ist leer."""
    datei = datei or eigene_datei()
    try:
        zeilen = datei.read_text(encoding="utf-8").splitlines()
    except OSError:
        return frozenset()
    return frozenset(
        zeile.strip().casefold() for zeile in zeilen
        if zeile.strip() and not zeile.lstrip().startswith("#")
    )


def eigenes_wort_aufnehmen(wort: str, datei=None) -> bool:
    """Haengt ein Wort an die Liste - und legt sie an, wenn sie fehlt."""
    wort = (wort or "").strip()
    if not wort:
        return False
    datei = datei or eigene_datei()
    if wort.casefold() in eigene_lesen(datei):
        return True
    try:
        neu = not datei.exists()
        with datei.open("a", encoding="utf-8") as liste:
            if neu:
                liste.write(
                    "# Woerter, die die Rechtschreibpruefung nicht "
                    "beanstanden soll - eines je Zeile.\n"
                )
            liste.write(wort + "\n")
    except OSError:
        return False
    return True
