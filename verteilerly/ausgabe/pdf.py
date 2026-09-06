"""PDF-Ausgabe: zeichnet die Blaetter des Layoutmodells.

Es gibt keinen zweiten Satz Blattregeln - hier wird nur uebersetzt, was
layout.py beschrieben hat. Der Ursprung liegt dort oben links, bei
ReportLab unten links; das ist der ganze Unterschied.
"""

from __future__ import annotations

import pathlib

from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from ..layout import MITTE, RECHTS, Blatt, Linie, Rechteck, Text, blaetter
from ..modell import Projekt
from ..version import VERSION
from . import AusgabeFehler

PT_JE_MM = 72.0 / 25.4
SCHRIFT = "Helvetica"
SCHRIFT_FETT = "Helvetica-Bold"
KUERZUNG = "…"


def pdf_schreiben(projekt: Projekt, ziel: pathlib.Path) -> pathlib.Path:
    """Schreibt die vollstaendige Dokumentation als PDF."""
    ziel = pathlib.Path(ziel)
    seiten = blaetter(projekt)
    if not seiten:
        raise AusgabeFehler("Der Verteiler hat keine Blätter.")

    # Erst vollstaendig schreiben, dann an den Platz ruecken: ein Abbruch
    # laesst so keine halbe Datei zurueck.
    vorlaeufig = ziel.with_name(ziel.name + ".neu")
    try:
        blech = canvas.Canvas(str(vorlaeufig), pageCompression=1)
        blech.setTitle(projekt.feld("dokumenttitel", "Verteilerdokumentation"))
        blech.setAuthor(projekt.feld("erstellt_von", projekt.feld("firma")))
        blech.setSubject(projekt.verteiler.name)
        blech.setCreator(f"Verteilerly {VERSION}")

        for blatt in seiten:
            _blatt_zeichnen(blech, blatt)
            blech.showPage()
        blech.save()
        vorlaeufig.replace(ziel)
    except OSError as fehler:
        vorlaeufig.unlink(missing_ok=True)
        raise AusgabeFehler(str(fehler)) from fehler
    return ziel


def _blatt_zeichnen(blech: canvas.Canvas, blatt: Blatt) -> None:
    hoehe_pt = blatt.hoehe * PT_JE_MM
    blech.setPageSize((blatt.breite * PT_JE_MM, hoehe_pt))

    for element in blatt.elemente:
        if isinstance(element, Rechteck):
            _rechteck(blech, element, hoehe_pt)
        elif isinstance(element, Linie):
            _linie(blech, element, hoehe_pt)
        elif isinstance(element, Text):
            _text(blech, element, hoehe_pt)


def _y(oben_mm: float, hoehe_pt: float) -> float:
    """Layout zaehlt von oben, das PDF von unten."""
    return hoehe_pt - oben_mm * PT_JE_MM


def _rechteck(blech: canvas.Canvas, element: Rechteck, hoehe_pt: float) -> None:
    x = element.x * PT_JE_MM
    breite = element.breite * PT_JE_MM
    hoehe = element.hoehe * PT_JE_MM
    y = _y(element.y, hoehe_pt) - hoehe

    if element.fuellung:
        blech.setFillColor(HexColor(element.fuellung))
    if element.rand:
        blech.setStrokeColor(HexColor(element.rand))
        blech.setLineWidth(element.staerke * PT_JE_MM)
    blech.rect(x, y, breite, hoehe, stroke=1 if element.rand else 0,
               fill=1 if element.fuellung else 0)


def _linie(blech: canvas.Canvas, element: Linie, hoehe_pt: float) -> None:
    blech.setStrokeColor(HexColor(element.farbe))
    blech.setLineWidth(element.staerke * PT_JE_MM)
    blech.line(
        element.x1 * PT_JE_MM,
        _y(element.y1, hoehe_pt),
        element.x2 * PT_JE_MM,
        _y(element.y2, hoehe_pt),
    )


def _text(blech: canvas.Canvas, element: Text, hoehe_pt: float) -> None:
    schrift = SCHRIFT_FETT if element.fett else SCHRIFT
    breite_pt = element.breite * PT_JE_MM
    text = _einpassen(str(element.text), schrift, element.groesse, breite_pt)
    if not text:
        return

    blech.setFont(schrift, element.groesse)
    blech.setFillColor(HexColor(element.farbe))

    # Senkrecht mittig: die Grundlinie liegt um die halbe Versalhoehe
    # unter der Mitte des Kastens.
    mitte = _y(element.y + element.hoehe / 2, hoehe_pt)
    grundlinie = mitte - element.groesse * 0.35
    x = element.x * PT_JE_MM

    if element.ausrichtung == RECHTS:
        blech.drawRightString(x + breite_pt, grundlinie, text)
    elif element.ausrichtung == MITTE:
        blech.drawCentredString(x + breite_pt / 2, grundlinie, text)
    else:
        blech.drawString(x, grundlinie, text)


def _einpassen(text: str, schrift: str, groesse: float, breite_pt: float) -> str:
    """Kuerzt, was nicht in den Kasten passt - lieber Punkte als Ueberdruck."""
    if not text or stringWidth(text, schrift, groesse) <= breite_pt:
        return text
    punkte = stringWidth(KUERZUNG, schrift, groesse)
    gekuerzt = text
    while gekuerzt and stringWidth(gekuerzt, schrift, groesse) + punkte > breite_pt:
        gekuerzt = gekuerzt[:-1]
    return (gekuerzt.rstrip() + KUERZUNG) if gekuerzt else ""
