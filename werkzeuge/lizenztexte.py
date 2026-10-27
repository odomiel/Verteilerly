"""Die Lizenztexte der Python-Pakete, die mit ins Programm wandern.

MIT und BSD verlangen, dass Copyright und Lizenzhinweis jede Weitergabe
begleiten - auch die gebaute. pip legt die Texte in die dist-info-Ordner;
in einer .exe kommen die gar nicht mit, und im AppImage stecken sie im
Einhaengepunkt. Beide Bauwege legen sie darum als flache Textdateien nach
``lizenzen/``, von wo das Programm sie in den Arbeitsordner auslegt.
"""

from __future__ import annotations

import importlib.metadata
import pathlib
import re

# Was aus requirements.txt samt Nachzug ins Programm wandert und seine
# Lizenz als Datei mitbringt. PySide6 und shiboken6 bringen keine mit -
# fuer sie steht LGPL-3.0.txt in lizenzen/.
PAKETE = ("reportlab", "pillow", "openpyxl", "et_xmlfile", "PyYAML",
          "charset_normalizer", "spylls")

_LIZENZDATEI = re.compile(r"^(LICEN[CS]E|COPYING|NOTICE)", re.IGNORECASE)


def _normiert(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def pakettexte(suchpfad=None) -> list[tuple[str, pathlib.Path]]:
    """(Zielname, Quelle) je Lizenzdatei der Pakete aus ``PAKETE``.

    ``suchpfad`` ist eine Liste von site-packages-Ordnern - fuer das
    AppDir, dessen Pakete nicht die des bauenden Pythons sind. Ohne
    Angabe gilt der Suchpfad des laufenden Interpreters. Ein fehlendes
    Paket fehlt eben; gemeldet wird das beim Pruefen, nicht hier.
    """
    gesucht = {_normiert(name) for name in PAKETE}
    optionen = {"path": [str(ort) for ort in suchpfad]} if suchpfad else {}
    gefunden: dict[str, list[tuple[str, pathlib.Path]]] = {}
    for verteilung in importlib.metadata.distributions(**optionen):
        name = verteilung.metadata["Name"]
        schluessel = _normiert(name)
        if schluessel not in gesucht or schluessel in gefunden:
            continue
        texte = []
        for datei in verteilung.files or ():
            teil = pathlib.PurePosixPath(str(datei))
            if ".dist-info" not in str(teil.parent) or not _LIZENZDATEI.match(teil.name):
                continue
            quelle = pathlib.Path(verteilung.locate_file(datei))
            if quelle.is_file():
                ziel = f"{name}-{teil.name}"
                if not ziel.lower().endswith(".txt"):
                    ziel += ".txt"
                texte.append((ziel, quelle))
        gefunden[schluessel] = sorted(texte)
    return [text for schluessel in sorted(gefunden) for text in gefunden[schluessel]]


def python_lizenz(kandidaten) -> pathlib.Path | None:
    """Die LICENSE.txt des mitgelieferten Pythons - die erste, die es gibt."""
    for ort in kandidaten:
        ort = pathlib.Path(ort)
        if ort.is_file():
            return ort
    return None
