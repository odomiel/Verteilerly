#!/usr/bin/env python3
"""Das Benutzerhandbuch als PDF - je Sprache eines.

    python3 werkzeuge/handbuch.py                   beide Sprachen
    python3 werkzeuge/handbuch.py --sprache en      nur eine
    python3 werkzeuge/handbuch.py --ordner /tmp     woanders ablegen

**Geschrieben wird das Handbuch nicht hier.** Es steht als HTML in
``daten/hilfe`` - dieselbe Datei, die das Programm unter *Hilfe ▸
Dokumentation* zeigt und die ``tests/test_hilfe.py`` gegen die Menues
haelt. Dieses Werkzeug setzt sie nur: Titelblatt, Inhaltsverzeichnis mit
Seitenzahlen, Fusszeile. Ein von Hand geschriebenes zweites Handbuch
liefe nach der ersten Aenderung auseinander.

Gesetzt wird mit Qt (``QTextDocument`` und ``QPdfWriter``) - dieselbe
Schriftmaschine, die auch die Hilfe im Programm zeichnet, und kein
weiteres Paket. Zwei Dinge sind dabei zu wissen:

* **Umgebrochen hat Qt schon.** Ein Dokument mit gesetzter ``pageSize``
  wird in Seiten gesetzt, ohne eine Zeile zu zerschneiden;
  ``pageCount()`` sagt, wie viele es sind. Gezeichnet wird darum Seite
  fuer Seite derselbe Streifen.
* **Gerechnet wird in Punkten.** Das Dokument haengt an keinem
  Ausgabegeraet und rechnete Punktgroessen ueber die 96 dpi des Schirms
  um - auf Papier waere alles ein Drittel zu gross. Die Masse stehen
  deshalb in px (ein px ist hier ein typografischer Punkt), und der
  Maler rechnet am Ende auf die Aufloesung des PDF hoch.

Die Seitenzahlen des Verzeichnisses entstehen in zwei Durchgaengen:
erst wird der Text gesetzt, dann wird nachgesehen, auf welcher Seite
jede Ueberschrift zu liegen kommt - und weil das Verzeichnis selbst
Seiten braucht, wird die Rechnung wiederholt, bis sie steht.
"""

from __future__ import annotations

import argparse
import datetime
import os
import pathlib
import sys

# Ohne Bildschirm gesetzt: Qt braucht eine Anwendung fuer Schriftmasse,
# aber keinen Schirm.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from verteilerly import LIZENZ, hilfe  # noqa: E402
from verteilerly.version import VERSION  # noqa: E402

#: Je Sprache: Dateiname, Titel und die paar Woerter, die das Werkzeug
#: selbst beisteuert. Der Rest des Handbuchs ist die Dokumentation.
SPRACHEN = {
    "de": {
        "datei": "Verteilerly-Handbuch-{0}.pdf",
        "titel": "Benutzerhandbuch",
        "inhalt": "Inhalt",
        "seite": "Seite {0} von {1}",
        "stand": "Stand: {0}",
        "fassung": "Fassung {0}",
        "quelle": (
            "Dieses Handbuch ist die Dokumentation, die das Programm unter "
            "<i>Hilfe ▸ Dokumentation</i> zeigt — gesetzt als PDF."
        ),
    },
    "en": {
        "datei": "Verteilerly-Manual-{0}.pdf",
        "titel": "User manual",
        "inhalt": "Contents",
        "seite": "Page {0} of {1}",
        "stand": "As of {0}",
        "fassung": "Version {0}",
        "quelle": (
            "This manual is the documentation the program shows under "
            "<i>Help ▸ Documentation</i>, set as a PDF."
        ),
    },
}

#: Wie der Text gesetzt wird - wie in der Hilfe, nur fuer Papier.
STILBLATT = (
    "h1 { font-size: 18px; }"
    "h2 { font-size: 13px; margin-top: 16px; }"
    "h3 { font-size: 11px; }"
    "h4 { font-size: 10px; }"
    "p, li, td, th { line-height: 135%; }"
    "th { text-align: left; }"
    "pre { margin-left: 10px; font-size: 8px; }"
    "code { font-size: 8px; }"
    "table { margin: 6px 0; }"
    ".anriss { font-size: 10px; }"
)

RAND_MM = 18.0             # Seitenrand
FUSS_PT = 22.0             # Streifen am Seitenfuss fuer die Seitenzahl
SCHRIFT_PT = 9.5           # Grundschrift des Textes
FUSSSCHRIFT_PT = 7.5


def _anwendung():
    """Eine Qt-Anwendung, einmal je Lauf."""
    from PySide6.QtGui import QGuiApplication

    vorhanden = QGuiApplication.instance()
    return vorhanden or QGuiApplication([])


def _schreiber(ziel: pathlib.Path):
    """Ein QPdfWriter auf A4 mit unseren Raendern."""
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter

    schreiber = QPdfWriter(str(ziel))
    schreiber.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    schreiber.setPageMargins(
        QMarginsF(RAND_MM, RAND_MM, RAND_MM, RAND_MM),
        QPageLayout.Unit.Millimeter,
    )
    schreiber.setResolution(300)
    schreiber.setTitle(f"Verteilerly {VERSION}")
    schreiber.setCreator(f"Verteilerly {VERSION}")
    return schreiber


def _dokument(html: str, breite: float, hoehe: float):
    """Ein in Seiten gesetztes Textdokument."""
    from PySide6.QtCore import QSizeF
    from PySide6.QtGui import QFont, QTextDocument

    dok = QTextDocument()
    dok.setDefaultStyleSheet(STILBLATT)
    schrift = QFont()
    schrift.setPixelSize(round(SCHRIFT_PT))
    dok.setDefaultFont(schrift)
    dok.setHtml(html)
    dok.setPageSize(QSizeF(breite, hoehe))
    # Gesetzt wird erst, wenn jemand nach der Groesse fragt - ohne das
    # haette kein Absatz Zeilen und das Dokument eine einzige Seite.
    dok.documentLayout().documentSize()
    return dok


def _seitenzahl(dok) -> int:
    """Wie viele Seiten das Dokument fuellt."""
    return max(1, dok.pageCount())


def _titelblatt(worte: dict, heute: str) -> str:
    """Das Titelblatt als HTML."""
    return (
        "<h1>Verteilerly</h1>"
        f"<p style='font-size: 14px;'>{worte['titel']}</p>"
        f"<p>{worte['fassung'].format(VERSION)}<br>"
        f"{worte['stand'].format(heute)}</p>"
        f"<p>{worte['quelle']}</p>"
        f"<p style='font-size: 8px;'>{LIZENZ}</p>"
    )


def _verzeichnis(worte: dict, eintraege: list[tuple[str, int]]) -> str:
    """Das Inhaltsverzeichnis als HTML - Titel und Seitenzahl."""
    zeilen = "".join(
        f"<tr><td>{titel}</td><td align='right' width='60'>{seite}</td></tr>"
        for titel, seite in eintraege
    )
    return (
        f"<h1>{worte['inhalt']}</h1>"
        f"<table width='100%' cellpadding='3'>{zeilen}</table>"
    )


def _ueberschriften(html: str) -> list[str]:
    """Die Abschnittstitel in ihrer Reihenfolge."""
    return [titel for _marke, titel in hilfe.abschnitte(html)]


def _ueberschriftenseiten(dok, hoehe: float) -> list[int]:
    """Auf welcher Seite jede Abschnittsueberschrift beginnt - ab 1.

    Gesucht wird nicht nach dem Text: derselbe Titel steht auch in
    Tabellen, und die erste Fundstelle waere die falsche. Qt merkt sich
    die Ebene jeder Ueberschrift am Absatzformat - genommen werden also
    die Absaetze der Ebene 2, in ihrer Reihenfolge.
    """
    seiten: list[int] = []
    block = dok.begin()
    while block.isValid():
        if block.blockFormat().headingLevel() == 2:
            oben = dok.documentLayout().blockBoundingRect(block).top()
            seiten.append(int(oben / hoehe) + 1)
        block = block.next()
    return seiten


def _blatt_zeichnen(maler, dok, nummer: int, hoehe: float, breite: float) -> None:
    """Zeichnet die n-te Seite des Dokuments - ab 0."""
    from PySide6.QtCore import QRectF

    streifen = QRectF(0, nummer * hoehe, breite, hoehe)
    maler.save()
    maler.translate(0, -nummer * hoehe)
    maler.setClipRect(streifen)
    dok.drawContents(maler, streifen)
    maler.restore()


def _fusszeile(maler, text: str, breite: float, hoehe: float) -> None:
    """Schreibt die Seitenzahl in den Streifen am Fuss.

    Sie steht **im** Satzspiegel, in dem Streifen, den die Seitenhoehe
    dafuer freigelassen hat - unter dem Rand waere sie ausserhalb der
    Malflaeche und bliebe abgeschnitten.
    """
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QFont

    fuss = QFont()
    fuss.setPixelSize(round(FUSSSCHRIFT_PT))
    maler.save()
    maler.setFont(fuss)
    kasten = QRectF(0, hoehe, breite, FUSS_PT)
    maler.drawText(
        kasten,
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
        text,
    )
    maler.restore()


def handbuch_schreiben(sprache: str, ordner: pathlib.Path) -> pathlib.Path:
    """Setzt die Dokumentation dieser Sprache als PDF und gibt den Pfad."""
    from PySide6.QtGui import QPainter

    worte = SPRACHEN[sprache]
    html = hilfe.dokumentation(sprache)
    heute = datetime.date.today().isoformat()
    ordner.mkdir(parents=True, exist_ok=True)
    ziel = ordner / worte["datei"].format(VERSION)

    _anwendung()
    schreiber = _schreiber(ziel)
    flaeche = schreiber.pageLayout().paintRectPoints()
    breite, hoehe = float(flaeche.width()), float(flaeche.height())
    texthoehe = hoehe - FUSS_PT
    hochrechnung = schreiber.resolution() / 72.0

    text = _dokument(html, breite, texthoehe)
    textseiten = _seitenzahl(text)

    # Erst das Verzeichnis: seine Laenge verschiebt die Seitenzahlen des
    # Textes, und die stehen in ihm. Zwei Durchgaenge genuegen, der
    # dritte ist die Sicherheit.
    titel = _ueberschriften(html)
    lagen = _ueberschriftenseiten(text, texthoehe)
    versatz = 2                      # Titelblatt und ein Verzeichnisblatt
    for _runde in range(3):
        eintraege = [(t, seite + versatz) for t, seite in zip(titel, lagen)]
        verzeichnis = _dokument(_verzeichnis(worte, eintraege), breite, texthoehe)
        verzeichnisseiten = _seitenzahl(verzeichnis)
        if 1 + verzeichnisseiten == versatz:
            break
        versatz = 1 + verzeichnisseiten

    gesamt = versatz + textseiten
    titelblatt = _dokument(_titelblatt(worte, heute), breite, texthoehe)

    maler = QPainter(schreiber)
    maler.scale(hochrechnung, hochrechnung)
    try:
        _blatt_zeichnen(maler, titelblatt, 0, texthoehe, breite)
        nummer = 1
        for dok, seiten in ((verzeichnis, verzeichnisseiten),
                            (text, textseiten)):
            for seite in range(seiten):
                schreiber.newPage()
                nummer += 1
                _blatt_zeichnen(maler, dok, seite, texthoehe, breite)
                _fusszeile(maler, worte["seite"].format(nummer, gesamt),
                           breite, texthoehe)
    finally:
        maler.end()
    return ziel


def main(argv: list[str] | None = None) -> int:
    zerleger = argparse.ArgumentParser(
        description="Das Benutzerhandbuch als PDF setzen."
    )
    zerleger.add_argument(
        "--sprache", choices=sorted(SPRACHEN), action="append",
        help="nur diese Sprache (mehrfach moeglich; ohne Angabe alle)",
    )
    zerleger.add_argument(
        "--ordner", default=str(WURZEL / "auslieferung"),
        help="wohin die PDF kommen (Vorgabe: auslieferung/)",
    )
    werte = zerleger.parse_args(argv)
    ordner = pathlib.Path(werte.ordner)
    for sprache in werte.sprache or sorted(SPRACHEN):
        ziel = handbuch_schreiben(sprache, ordner)
        print(f"· {sprache}: {ziel} ({ziel.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
