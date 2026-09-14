"""Die Dokumentation im Programm.

Wer wissen will, was ein Knopf tut, soll nicht erst ein PDF suchen
muessen. Die Dokumentation liegt deshalb als HTML bei und wird im
Programm angezeigt - dieselbe Datei im Quellbaum, im AppImage und in der
.exe, gefunden ueber dieselbe Suchreihenfolge wie die uebrigen
mitgelieferten Dateien.

Sie sagt, wie das Programm bedient wird.

Je Sprache eine Datei: ``dokumentation.html`` ist die deutsche,
``dokumentation_en.html`` die englische. Fehlt die fremdsprachige, wird
die deutsche gezeigt - eine halb uebersetzte Hilfe waere schlimmer als
eine ganz deutsche.
"""

from __future__ import annotations

import pathlib

from . import pfade, sprachen

ORDNER = "hilfe"
DATEI = "dokumentation.html"


def _dateinamen(sprache: str = "") -> list[str]:
    """Welche Dateien in Frage kommen - erst die Sprache, dann Deutsch."""
    kennung = sprache or sprachen.sprache()
    namen = []
    if kennung and kennung != sprachen.VORGABE:
        namen.append(f"dokumentation_{kennung}.html")
    namen.append(DATEI)
    return namen


def dokumentationsdatei(sprache: str = "") -> pathlib.Path | None:
    """Wo die Dokumentation liegt - oder nichts, wenn sie fehlt."""
    wurzeln: list[pathlib.Path] = []
    fertig = pfade.mitgeliefert()
    if fertig:
        wurzeln.append(fertig / ORDNER)
    # Im Quellbaum liegt sie neben dem Paket, auch ohne Datenordner.
    wurzeln.append(
        pathlib.Path(__file__).resolve().parent.parent / "daten" / ORDNER
    )
    for name in _dateinamen(sprache):
        for wurzel in wurzeln:
            ort = wurzel / name
            if ort.is_file():
                return ort
    return None


def dokumentation(sprache: str = "") -> str:
    """Die Dokumentation als HTML.

    Fehlt die Datei, kommt ein kurzer Hinweis zurueck statt einer
    Ausnahme: ein Hilfefenster, das beim Oeffnen abstuerzt, hilft am
    wenigsten.
    """
    datei = dokumentationsdatei(sprache)
    if datei is None:
        return (
            "<h1>Dokumentation</h1><p>Die Datei "
            f"<code>{ORDNER}/{DATEI}</code> wurde nicht gefunden.</p>"
        )
    return datei.read_text(encoding="utf-8")


def abschnitte(text: str | None = None) -> list[tuple[str, str]]:
    """Die Ueberschriften mit ihrer Sprungmarke - fuer das Verzeichnis."""
    import re

    inhalt = dokumentation() if text is None else text
    gefunden = re.findall(
        r'<h2><a name="([^"]+)"></a>(.*?)</h2>', inhalt, flags=re.S
    )
    return [
        (marke, re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", titel)
                       .replace("&nbsp;", " ")).strip())
        for marke, titel in gefunden
    ]
