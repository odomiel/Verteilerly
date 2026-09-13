"""Excel im Blattbild: dieselben Blaetter, nur als Tabelle.

Excel ist ein Raster, das Blatt eine Zeichnung - genau nachbauen laesst
sich ein PDF hier nicht. Das Leistenblatt ist aber selbst eine Tabelle:
Spalten, Kopfzeile, zwei Zeilen je Stift. Genau das wird hier gesetzt,
mit den Massen und Schriftgroessen der gewaehlten Blattvorlage, und zwar
so, dass ein Ausdruck aus Excel dem PDF nahekommt.

Was Excel nicht nachbilden kann, ist die freie Lage in Millimetern. Der
Kabelblock wird darum ueber seine Zeilen verbunden statt frei gezeichnet,
und das Schriftfeld steht unter der Tabelle statt am Blattfuss.
"""

from __future__ import annotations

from ..blattvorlagen import STANDARD, Blattvorlage
from ..layout import (
    FUELLUNG_KABEL,
    FUELLUNG_KOPF,
    LINIE,
    LINIE_FEIN,
    buchtnamen,
    kopfgruppen,
    schriftfeldwerte,
    schriftfeldzeilen,
    zeilenstile,
    zeilenteilungen,
    zeilenwerte,
    zellentext,
)
from ..modell import LEERER_STIL, UNGETEILT, Projekt

SCHRIFTART = "Arial"          # was Helvetica im PDF am naechsten kommt
PT_JE_MM = 72.0 / 25.4
PX_JE_MM = 96.0 / 25.4
# Excel misst Spalten in Zeichenbreiten der Standardschrift: ein Zeichen
# sind rund sieben Bildpunkte, dazu kommt der Zellrand.
PX_JE_ZEICHEN = 7.0
ZELLRAND_PX = 5.0


def spaltenbreite(mm: float) -> float:
    """Millimeter in Excels Spaltenmass."""
    return max(1.0, round((mm * PX_JE_MM - ZELLRAND_PX) / PX_JE_ZEICHEN, 2))


def zeilenhoehe(mm: float) -> float:
    """Millimeter in Punkt - so misst Excel Zeilenhoehen."""
    return round(mm * PT_JE_MM, 2)


def _hex(farbe: str) -> str:
    return "FF" + farbe.lstrip("#").upper()


class _Werkzeug:
    """Die Bausteine von openpyxl, einmal geholt und benannt."""

    def __init__(self) -> None:
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter

        self.Alignment = Alignment
        self.Border = Border
        self.Font = Font
        self.Fuellung = PatternFill
        self.Side = Side
        self.spaltenname = get_column_letter

    def strich(self, farbe: str, kraeftig: bool = False):
        return self.Side(
            style="thin" if not kraeftig else "medium", color=_hex(farbe)
        )

    def rahmen(self, **seiten):
        return self.Border(**seiten)

    def schrift(self, groesse: float, fett: bool = False, farbe: str = "#000000",
                kursiv: bool = False):
        return self.Font(
            name=SCHRIFTART, size=groesse, bold=fett, italic=kursiv,
            color=_hex(farbe),
        )

    def lage(self, ausrichtung: str = "links", gedreht: int = 0):
        waagerecht = {"links": "left", "mitte": "center", "rechts": "right"}
        return self.Alignment(
            horizontal=waagerecht.get(ausrichtung, "left"),
            vertical="center",
            text_rotation=gedreht,
            wrap_text=False,
        )


def blaetter_eintragen(
    mappe, projekt: Projekt, vorlage: Blattvorlage = STANDARD
) -> list:
    """Legt Deckblatt, Verteilerbelegung und die Leistenblaetter an."""
    zeug = _Werkzeug()
    blaetter = [_deckblatt(mappe, projekt, vorlage, zeug)]
    blaetter.append(_belegung(mappe, projekt, vorlage, zeug))
    for leiste in projekt.verteiler.alle_leisten:
        blaetter.append(_leistenblatt(mappe, projekt, leiste.nummer, vorlage, zeug))
    return blaetter


def _seiteneinrichtung(blatt, quer: bool = False) -> None:
    """A4, damit ein Ausdruck aus Excel wie das PDF aussieht."""
    blatt.page_setup.paperSize = blatt.PAPERSIZE_A4
    blatt.page_setup.orientation = "landscape" if quer else "portrait"
    blatt.page_setup.fitToWidth = 1
    blatt.page_setup.fitToHeight = 0
    blatt.sheet_properties.pageSetUpPr.fitToPage = True
    blatt.page_margins.left = blatt.page_margins.right = 0.5
    blatt.page_margins.top = blatt.page_margins.bottom = 0.5


# -- Deckblatt --------------------------------------------------------------


def _deckblatt(mappe, projekt: Projekt, vorlage: Blattvorlage, zeug) -> object:
    blatt = mappe.active
    blatt.title = "Deckblatt"
    v = projekt.verteiler

    blatt.column_dimensions["A"].width = 26
    blatt.column_dimensions["B"].width = 52

    blatt["A1"] = projekt.anzeigewert("dokumenttitel", "Verteilerdokumentation")
    blatt["A1"].font = zeug.schrift(vorlage.schrift_gross, True)
    blatt.row_dimensions[1].height = zeilenhoehe(12)

    blatt["A3"] = v.name
    blatt["A3"].font = zeug.schrift(vorlage.schrift_mittel, True)
    blatt["B3"] = v.nummer

    zeile = 5
    for name, wert in schriftfeldzeilen(
        schriftfeldwerte(projekt, None, vorlage, "Deckblatt", "deckblatt")
    ):
        blatt.cell(row=zeile, column=1, value=name).font = zeug.schrift(
            vorlage.schrift_klein, False, "#555555"
        )
        blatt.cell(row=zeile, column=2, value=wert).font = zeug.schrift(
            vorlage.schrift_normal
        )
        zeile += 1

    zeile += 1
    for beschreibung, zahl in (
        ("Buchten", len(v.buchten)),
        ("Leisten", len(v.alle_leisten)),
        ("Doppeladern", v.da_gesamt),
        ("Kabel", len(v.kabel)),
        ("Rangierungen", len(v.rangierungen)),
    ):
        blatt.cell(row=zeile, column=1, value=beschreibung).font = zeug.schrift(
            vorlage.schrift_klein, False, "#555555"
        )
        blatt.cell(row=zeile, column=2, value=zahl).font = zeug.schrift(
            vorlage.schrift_normal
        )
        zeile += 1

    _seiteneinrichtung(blatt)
    return blatt


# -- Verteilerbelegung ------------------------------------------------------


def _belegung(mappe, projekt: Projekt, vorlage: Blattvorlage, zeug) -> object:
    """Jede Leiste eine Zeile aus DA-Zellen, Kabel als verbundener Block."""
    blatt = mappe.create_sheet("Verteilerbelegung")
    v = projekt.verteiler
    breiteste = max((l.da_anzahl for l in v.alle_leisten), default=0)

    blatt.column_dimensions["A"].width = spaltenbreite(vorlage.leistenlabel)
    for i in range(breiteste):
        blatt.column_dimensions[zeug.spaltenname(2 + i)].width = spaltenbreite(
            vorlage.zelle_breite
        )

    zeile = 1
    for bucht in v.buchten:
        blatt.cell(row=zeile, column=1, value=buchtnamen([bucht])).font = zeug.schrift(
            vorlage.schrift_normal, True
        )
        zeile += 1
        for leiste in bucht.leisten:
            zelle = blatt.cell(row=zeile, column=1, value=f"Leiste {leiste.nummer}")
            zelle.font = zeug.schrift(vorlage.schrift_klein, False, "#555555")
            zelle.alignment = zeug.lage("rechts")
            blatt.row_dimensions[zeile].height = zeilenhoehe(vorlage.zelle_hoehe)

            for da in range(1, leiste.da_anzahl + 1):
                feld = blatt.cell(row=zeile, column=1 + da, value=str(da))
                feld.font = zeug.schrift(vorlage.schrift_klein - 1, False, "#555555")
                feld.alignment = zeug.lage("mitte")
                feld.border = zeug.rahmen(
                    left=zeug.strich(LINIE_FEIN), right=zeug.strich(LINIE_FEIN),
                    top=zeug.strich(LINIE), bottom=zeug.strich(LINIE),
                )

            for kabel in v.kabel:
                for abschnitt in kabel.abschnitte:
                    if abschnitt.leiste != leiste.nummer:
                        continue
                    von = 1 + abschnitt.start_da
                    bis = 1 + abschnitt.end_da
                    blatt.merge_cells(
                        start_row=zeile, start_column=von,
                        end_row=zeile, end_column=bis,
                    )
                    feld = blatt.cell(row=zeile, column=von, value=kabel.beschriftung)
                    feld.font = zeug.schrift(vorlage.schrift_klein, True)
                    feld.alignment = zeug.lage("links")
                    feld.fill = zeug.Fuellung(
                        "solid", start_color=_hex(FUELLUNG_KABEL)
                    )
            zeile += 1
        zeile += 1

    # Wie auf dem gezeichneten Blatt: eine Bucht steht hochkant, ab zwei
    # quer.
    _seiteneinrichtung(blatt, quer=len(v.buchten) > 1)
    return blatt


# -- Leistenblatt -----------------------------------------------------------


def _leistenblatt(
    mappe, projekt: Projekt, leiste_nr: int, vorlage: Blattvorlage, zeug
) -> object:
    v = projekt.verteiler
    leiste = v.leiste(leiste_nr)
    blatt = mappe.create_sheet(f"Leiste {leiste_nr}")
    spalten = vorlage.spalten
    breiten = vorlage.breiten(210.0 - 2 * vorlage.rand)

    for i, breite in enumerate(breiten, 1):
        blatt.column_dimensions[zeug.spaltenname(i)].width = spaltenbreite(breite)

    blatt.cell(row=1, column=1, value=f"Leiste {leiste_nr}").font = zeug.schrift(
        vorlage.schrift_mittel, True
    )
    letzte = zeug.spaltenname(len(spalten))
    blatt[f"{letzte}1"] = f"{leiste.da_anzahl} DA"
    blatt[f"{letzte}1"].font = zeug.schrift(vorlage.schrift_normal, False, "#555555")
    blatt[f"{letzte}1"].alignment = zeug.lage("rechts")
    blatt.row_dimensions[1].height = zeilenhoehe(8)

    KOPFZEILE = 3
    for i, spalte in enumerate(spalten, 1):
        feld = blatt.cell(row=KOPFZEILE, column=i, value=spalte.ueberschrift)
        feld.font = zeug.schrift(vorlage.schrift_klein, True)
        feld.alignment = zeug.lage(spalte.ausrichtung)
        feld.fill = zeug.Fuellung("solid", start_color=_hex(FUELLUNG_KOPF))
        feld.border = zeug.rahmen(
            top=zeug.strich(LINIE, True), bottom=zeug.strich(LINIE, True),
            left=zeug.strich(LINIE_FEIN), right=zeug.strich(LINIE_FEIN),
        )
    # „Stift“ steht über der Nummer und über a und b - wie auf dem Blatt.
    for erste, anzahl in kopfgruppen(spalten):
        if anzahl > 1:
            blatt.merge_cells(
                start_row=KOPFZEILE, start_column=erste + 1,
                end_row=KOPFZEILE, end_column=erste + anzahl,
            )
    blatt.row_dimensions[KOPFZEILE].height = zeilenhoehe(vorlage.kopfzeile_hoehe)

    erste_zeile = KOPFZEILE + 1
    zeile = erste_zeile
    for stift in leiste.stifte:
        for seite in ("a", "b"):
            werte = zeilenwerte(projekt, leiste_nr, stift.nummer, seite)
            stile = zeilenstile(projekt, leiste_nr, stift.nummer, seite)
            teilungen = zeilenteilungen(projekt, leiste_nr, stift.nummer, seite)
            for i, spalte in enumerate(spalten, 1):
                # Eine geteilte Zelle gibt es im Raster nicht: beide
                # Felder stehen hier hintereinander.
                text = zellentext(
                    werte.get(spalte.feld, ""),
                    teilungen.get(spalte.feld, UNGETEILT),
                )
                feld = blatt.cell(row=zeile, column=i, value=text)
                # Derselbe Zellenstil wie auf dem Blatt.
                stil = stile.get(spalte.feld, LEERER_STIL)
                feld.font = zeug.schrift(
                    vorlage.schrift_normal, stil.fett, kursiv=stil.kursiv
                )
                feld.alignment = zeug.lage(stil.ausrichtung or spalte.ausrichtung)
                # Unter der b-Zeile trennt ein kraeftiger Strich die Stifte.
                feld.border = zeug.rahmen(
                    left=zeug.strich(LINIE_FEIN), right=zeug.strich(LINIE_FEIN),
                    bottom=zeug.strich(LINIE, seite == "b"),
                )
            blatt.row_dimensions[zeile].height = zeilenhoehe(
                min(vorlage.zeilenhoehe_max, 5.5)
            )
            zeile += 1

    _kabelbloecke(blatt, projekt, leiste_nr, vorlage, zeug, erste_zeile)
    _schriftfeld(blatt, projekt, leiste_nr, vorlage, zeug, zeile + 1, len(spalten))
    blatt.freeze_panes = blatt.cell(row=erste_zeile, column=1)
    _seiteneinrichtung(blatt)
    return blatt


def _kabelbloecke(
    blatt, projekt: Projekt, leiste_nr: int, vorlage: Blattvorlage, zeug, erste: int
) -> None:
    """Die Kabelklammer: ueber ihre Zeilen verbunden, wie auf dem Blatt."""
    stelle = next(
        (i for i, s in enumerate(vorlage.spalten, 1) if s.feld == "kabel"), None
    )
    if stelle is None:
        return

    for kabel in projekt.verteiler.kabel:
        for abschnitt in kabel.abschnitte:
            if abschnitt.leiste != leiste_nr:
                continue
            von = erste + (abschnitt.start_da - 1) * 2
            bis = von + abschnitt.anzahl_da * 2 - 1
            beschriftung = kabel.beschriftung
            if kabel.gekuerzt:
                beschriftung += (
                    f" (gekürzt: {kabel.da_aufgelegt} von {kabel.da_gesamt} DA)"
                )
            blatt.merge_cells(
                start_row=von, start_column=stelle, end_row=bis, end_column=stelle
            )
            feld = blatt.cell(row=von, column=stelle, value=beschriftung)
            feld.font = zeug.schrift(vorlage.schrift_klein)
            feld.alignment = zeug.lage(
                "mitte" if vorlage.kabel_gedreht else "links",
                gedreht=90 if vorlage.kabel_gedreht else 0,
            )
            feld.fill = zeug.Fuellung("solid", start_color=_hex(FUELLUNG_KABEL))
            for zeile in range(von, bis + 1):
                blatt.cell(row=zeile, column=stelle).border = zeug.rahmen(
                    left=zeug.strich(LINIE), right=zeug.strich(LINIE),
                    top=zeug.strich(LINIE) if zeile == von else None,
                    bottom=zeug.strich(LINIE) if zeile == bis else None,
                )


def _schriftfeld(
    blatt, projekt: Projekt, leiste_nr: int, vorlage: Blattvorlage, zeug,
    zeile: int, spaltenzahl: int,
) -> None:
    """Was auf dem Blatt unten steht, steht hier unter der Tabelle."""
    eintraege = schriftfeldzeilen(
        schriftfeldwerte(projekt, leiste_nr, vorlage, f"Leiste {leiste_nr}")
    )
    if not eintraege:
        return
    for name, wert in eintraege:
        blatt.cell(row=zeile, column=1, value=name).font = zeug.schrift(
            vorlage.schrift_klein, False, "#555555"
        )
        feld = blatt.cell(row=zeile, column=2, value=wert)
        feld.font = zeug.schrift(vorlage.schrift_normal)
        if spaltenzahl >= 3:
            blatt.merge_cells(
                start_row=zeile, start_column=2, end_row=zeile, end_column=3
            )
        zeile += 1
