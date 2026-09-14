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

from ..blattvorlagen import STANDARD, Blattvorlage
from ..layout import (
    MITTE,
    RECHTS,
    ZEILENABSTAND,
    Blatt,
    Linie,
    Rechteck,
    Text,
    blaetter,
    umbruch_einpassen,
)
from ..modell import Projekt
from ..version import VERSION
from . import AusgabeFehler

PT_JE_MM = 72.0 / 25.4
SCHRIFT = "Helvetica"
SCHRIFT_FETT = "Helvetica-Bold"
SCHRIFT_KURSIV = "Helvetica-Oblique"
SCHRIFT_FETT_KURSIV = "Helvetica-BoldOblique"
KUERZUNG = "…"
# Wie weit ein Text schrumpfen darf, damit er in sein Feld passt. Unter
# 5 pt liest es niemand mehr - dann wird lieber gekuerzt.
KLEINSTE_SCHRIFT = 5.0
SCHRITT = 0.25


def pdf_schreiben(
    projekt: Projekt, ziel: pathlib.Path, vorlage: Blattvorlage = STANDARD
) -> pathlib.Path:
    """Schreibt die vollstaendige Dokumentation als PDF."""
    ziel = pathlib.Path(ziel)
    seiten = blaetter(projekt, vorlage)
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


def _schriftschnitt(fett: bool, kursiv: bool) -> str:
    """Der Schnitt zu fett und kursiv - alle vier gehoeren zum PDF-Standard."""
    if fett and kursiv:
        return SCHRIFT_FETT_KURSIV
    if fett:
        return SCHRIFT_FETT
    if kursiv:
        return SCHRIFT_KURSIV
    return SCHRIFT


def _text(blech: canvas.Canvas, element: Text, hoehe_pt: float) -> None:
    schrift = _schriftschnitt(element.fett, element.kursiv)
    laenge_pt = element.zeilenlaenge * PT_JE_MM
    if element.umbruch and not element.drehung:
        _text_umgebrochen(blech, element, schrift, hoehe_pt)
        return
    groesse = _passende_groesse(str(element.text), schrift, element.groesse, laenge_pt)
    text = _einpassen(str(element.text), schrift, groesse, laenge_pt)
    if not text:
        return

    blech.setFont(schrift, groesse)
    blech.setFillColor(HexColor(element.farbe))

    if element.drehung:
        _text_gedreht(blech, element, text, schrift, groesse, hoehe_pt)
        return

    # Senkrecht mittig: die Grundlinie liegt um die halbe Versalhoehe
    # unter der Mitte des Kastens.
    mitte = _y(element.y + element.hoehe / 2, hoehe_pt)
    grundlinie = mitte - groesse * 0.35
    x = element.x * PT_JE_MM
    breite_pt = element.breite * PT_JE_MM

    if element.ausrichtung == RECHTS:
        blech.drawRightString(x + breite_pt, grundlinie, text)
    elif element.ausrichtung == MITTE:
        blech.drawCentredString(x + breite_pt / 2, grundlinie, text)
    else:
        blech.drawString(x, grundlinie, text)


def _text_umgebrochen(
    blech: canvas.Canvas, element: Text, schrift: str, hoehe_pt: float
) -> None:
    """Text auf mehreren Zeilen, mittig im Kasten.

    Wie die Zeilen laufen, rechnet das Layoutmodell; gemessen wird mit
    den Massen von ReportLab. Gezeichnet werden sie von oben nach unten,
    zusammen mittig um die Mitte des Kastens.
    """
    breite_pt = element.breite * PT_JE_MM
    hoehe_kasten = element.hoehe * PT_JE_MM
    groesse, zeilen = umbruch_einpassen(
        str(element.text), breite_pt, hoehe_kasten, element.groesse,
        KLEINSTE_SCHRIFT, SCHRITT,
        lambda zeile, gr: stringWidth(zeile, schrift, gr),
    )
    zeilen = [z for z in zeilen if z.strip()]
    if not zeilen:
        return

    blech.setFont(schrift, groesse)
    blech.setFillColor(HexColor(element.farbe))
    abstand = groesse * ZEILENABSTAND
    mitte = _y(element.y + element.hoehe / 2, hoehe_pt)
    oben = mitte + abstand * len(zeilen) / 2
    x = element.x * PT_JE_MM
    for i, zeile in enumerate(zeilen):
        grundlinie = oben - abstand * (i + 0.5) - groesse * 0.35
        if element.ausrichtung == RECHTS:
            blech.drawRightString(x + breite_pt, grundlinie, zeile)
        elif element.ausrichtung == MITTE:
            blech.drawCentredString(x + breite_pt / 2, grundlinie, zeile)
        else:
            blech.drawString(x, grundlinie, zeile)


def _text_gedreht(
    blech: canvas.Canvas,
    element: Text,
    text: str,
    schrift: str,
    groesse: float,
    hoehe_pt: float,
) -> None:
    """Text quer im Kasten - von unten nach oben zu lesen.

    Gedreht wird das Blatt, nicht der Text: nach ``rotate`` laeuft die
    Zeile nach oben, und was danach gezeichnet wird, rechnet wieder in
    gewoehnlichen Koordinaten.
    """
    breite_pt = element.breite * PT_JE_MM
    unten = _y(element.y + element.hoehe, hoehe_pt)
    laenge_pt = element.hoehe * PT_JE_MM
    # Die Grundlinie liegt um die halbe Versalhoehe neben der Mitte des
    # Kastens - beim gedrehten Text heisst "neben" nach rechts.
    grundlinie = element.x * PT_JE_MM + breite_pt / 2 + groesse * 0.35

    blech.saveState()
    blech.translate(grundlinie, unten)
    blech.rotate(element.drehung)
    if element.ausrichtung == RECHTS:
        blech.drawRightString(laenge_pt, 0, text)
    elif element.ausrichtung == MITTE:
        blech.drawCentredString(laenge_pt / 2, 0, text)
    else:
        blech.drawString(0, 0, text)
    blech.restoreState()


def _passende_groesse(
    text: str, schrift: str, groesse: float, breite_pt: float
) -> float:
    """Verkleinert die Schrift, bis der Text in sein Feld passt.

    Ein langer Kabelname soll lesbar bleiben, statt abgeschnitten zu
    werden. Unter KLEINSTE_SCHRIFT wird nicht weiter verkleinert - dann
    kuerzt _einpassen, denn winzige Schrift hilft auch niemandem.
    """
    if not text.strip() or breite_pt <= 0:
        return groesse
    breite = stringWidth(text, schrift, groesse)
    if breite <= breite_pt:
        return groesse
    # Ein Schritt unter die rechnerische Groesse, damit Rundungen nicht
    # doch noch ueber den Rand laufen.
    passend = groesse * breite_pt / breite
    passend = max(KLEINSTE_SCHRIFT, (passend // SCHRITT) * SCHRITT)
    return min(groesse, passend)


def _einpassen(text: str, schrift: str, groesse: float, breite_pt: float) -> str:
    """Kuerzt, was nicht in den Kasten passt - lieber Punkte als Ueberdruck."""
    if not text or stringWidth(text, schrift, groesse) <= breite_pt:
        return text
    punkte = stringWidth(KUERZUNG, schrift, groesse)
    gekuerzt = text
    while gekuerzt and stringWidth(gekuerzt, schrift, groesse) + punkte > breite_pt:
        gekuerzt = gekuerzt[:-1]
    return (gekuerzt.rstrip() + KUERZUNG) if gekuerzt else ""
