"""Die Dokumentation im Programm.

Wer wissen will, was ein Knopf tut, soll nicht erst ein PDF suchen
muessen. Die Dokumentation liegt deshalb als HTML bei und wird im
Programm angezeigt - dieselbe Datei im Quellbaum, im AppImage und in der
.exe, gefunden ueber dieselbe Suchreihenfolge wie die uebrigen
mitgelieferten Dateien.
"""

from __future__ import annotations

import pathlib

from . import pfade

ORDNER = "hilfe"
DATEI = "dokumentation.html"


def dokumentationsdatei() -> pathlib.Path | None:
    """Wo die Dokumentation liegt - oder nichts, wenn sie fehlt."""
    orte: list[pathlib.Path] = []
    fertig = pfade.mitgeliefert()
    if fertig:
        orte.append(fertig / ORDNER / DATEI)
    # Im Quellbaum liegt sie neben dem Paket, auch ohne Datenordner.
    orte.append(pathlib.Path(__file__).resolve().parent.parent / "daten" / ORDNER / DATEI)
    for ort in orte:
        if ort.is_file():
            return ort
    return None


def dokumentation() -> str:
    """Die Dokumentation als HTML.

    Fehlt die Datei, kommt ein kurzer Hinweis zurueck statt einer
    Ausnahme: ein Hilfefenster, das beim Oeffnen abstuerzt, hilft am
    wenigsten.
    """
    datei = dokumentationsdatei()
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
