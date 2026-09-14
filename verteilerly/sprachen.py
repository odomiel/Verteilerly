"""Die Oberflaeche auf Deutsch oder Englisch.

**Die Quellsprache bleibt Deutsch.** Im Quelltext steht der deutsche Satz
lesbar da und ist zugleich der Schluessel, unter dem die Uebersetzung
nachgeschlagen wird::

    self.setWindowTitle(u("Neuer Verteiler"))

Damit ist jede Stelle auch ohne Katalog zu lesen, und fehlt eine
Uebersetzung, erscheint der deutsche Satz unveraendert - lieber ein
deutsches Wort als ein leeres Feld. Eine Pruefung wacht darueber, dass
der Katalog vollstaendig bleibt (``tests/test_sprachen.py``): sie liest
jeden Aufruf von ``u`` aus dem Quelltext und vergleicht ihn mit der
Wortliste.

Der Katalog liegt als YAML bei (``daten/sprachen/en.yaml``) und wird wie
die uebrigen mitgelieferten Dateien gefunden. Er wandert **nicht** in den
Arbeitsordner: er gehoert zum Programm, nicht zum Bestand des Anwenders -
wie die Dokumentation.

Texte mit Platzhaltern tragen geschweifte Klammern und werden nach dem
Nachschlagen gefuellt::

    u("{zahl} Leisten").format(zahl=4)

So steht im Katalog ein ganzer Satz und nicht ein Stueck davon; im
Englischen darf der Platzhalter an einer anderen Stelle stehen.
"""

from __future__ import annotations

import pathlib

from . import pfade

ORDNER = "sprachen"

#: Kennung, Name in der eigenen Sprache - so steht sie im Menue.
SPRACHEN = (
    ("de", "Deutsch"),
    ("en", "English"),
)
VORGABE = "de"

_aktuell = VORGABE
_katalog: dict[str, str] = {}


def sprachdatei(kennung: str) -> pathlib.Path | None:
    """Wo die Wortliste dieser Sprache liegt - oder nichts."""
    orte: list[pathlib.Path] = []
    fertig = pfade.mitgeliefert()
    if fertig:
        orte.append(fertig / ORDNER / f"{kennung}.yaml")
    # Im Quellbaum liegt sie neben dem Paket, auch ohne Datenordner.
    orte.append(
        pathlib.Path(__file__).resolve().parent.parent
        / "daten" / ORDNER / f"{kennung}.yaml"
    )
    for ort in orte:
        if ort.is_file():
            return ort
    return None


def katalog_laden(kennung: str) -> dict[str, str]:
    """Die Wortliste einer Sprache; fehlt sie, bleibt es beim Deutschen."""
    if kennung == VORGABE:
        return {}
    datei = sprachdatei(kennung)
    if datei is None:
        return {}
    import yaml

    try:
        gelesen = yaml.safe_load(datei.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(gelesen, dict):
        return {}
    return {
        str(deutsch): str(fremd)
        for deutsch, fremd in gelesen.items()
        if str(fremd).strip()
    }


def sprache_setzen(kennung: str) -> str:
    """Stellt die Sprache ein und laedt ihre Wortliste.

    Eine unbekannte Kennung fuehrt zurueck aufs Deutsche: eine
    Einstellungsdatei von Hand geaendert, und schon stuende sonst ein
    leeres Programm da.
    """
    global _aktuell, _katalog
    bekannt = {kennung for kennung, _ in SPRACHEN}
    _aktuell = kennung if kennung in bekannt else VORGABE
    _katalog = katalog_laden(_aktuell)
    return _aktuell


def sprache() -> str:
    """Welche Sprache gerade gilt."""
    return _aktuell


def name(kennung: str = "") -> str:
    """Der Name einer Sprache, wie er im Menue steht."""
    gesucht = kennung or _aktuell
    for eine, wie in SPRACHEN:
        if eine == gesucht:
            return wie
    return gesucht


def u(text: str) -> str:
    """Der Text in der eingestellten Sprache.

    Ohne Uebersetzung kommt der deutsche Text zurueck - unveraendert und
    ohne Meldung: ein fehlendes Wort soll die Oberflaeche nicht anhalten.
    """
    return _katalog.get(text, text)


def uebersetzt(text: str) -> bool:
    """Ob fuer diesen Text eine Uebersetzung vorliegt - fuer die Pruefung."""
    return text in _katalog
