"""Layoutmodell: Blaetter als Zeichenanweisungen.

Hier entsteht das Blatt einmal - in Millimetern, ohne Qt und ohne
ReportLab. Vorschau und PDF zeichnen dasselbe Modell ab; sie koennen
deshalb nicht auseinanderlaufen.

Der Ursprung liegt oben links, x laeuft nach rechts, y nach unten.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .modell import Projekt, Verteiler, adressen_schreiben

# -- Papier ----------------------------------------------------------------

A4_HOCH = (210.0, 297.0)
A4_QUER = (297.0, 210.0)
RAND = 12.0

# -- Farben auf dem Papier -------------------------------------------------
# Ein Blatt ist Papier, kein Fenster: schwarze Schrift, graue Linien,
# auch wenn das Programm im dunklen Farbsatz laeuft.

TINTE = "#000000"
TINTE_LEISE = "#555555"
LINIE = "#7A7A7A"
LINIE_FEIN = "#B4B4B4"
FUELLUNG_KOPF = "#E8E8E8"
FUELLUNG_KABEL = "#EFEFEF"

# -- Schriftgroessen in Punkt ----------------------------------------------

GROSS = 20.0
MITTEL = 11.0
NORMAL = 8.5
KLEIN = 7.0

LINKS, MITTE, RECHTS = "links", "mitte", "rechts"


# -- Zeichenanweisungen ----------------------------------------------------


@dataclass(frozen=True)
class Linie:
    x1: float
    y1: float
    x2: float
    y2: float
    staerke: float = 0.2
    farbe: str = LINIE


@dataclass(frozen=True)
class Rechteck:
    x: float
    y: float
    breite: float
    hoehe: float
    fuellung: str | None = None
    rand: str | None = LINIE
    staerke: float = 0.2


@dataclass(frozen=True)
class Text:
    """Text in einem Kasten, senkrecht mittig."""

    x: float
    y: float
    breite: float
    hoehe: float
    text: str
    groesse: float = NORMAL
    ausrichtung: str = LINKS
    fett: bool = False
    farbe: str = TINTE


@dataclass
class Blatt:
    """Ein Blatt Papier samt allem, was darauf steht."""

    breite: float
    hoehe: float
    titel: str = ""
    elemente: list[object] = field(default_factory=list)

    @property
    def quer(self) -> bool:
        return self.breite > self.hoehe

    def rechteck(self, *args, **kw) -> None:
        self.elemente.append(Rechteck(*args, **kw))

    def linie(self, *args, **kw) -> None:
        self.elemente.append(Linie(*args, **kw))

    def text(self, *args, **kw) -> None:
        if str(args[4] if len(args) > 4 else kw.get("text", "")).strip():
            self.elemente.append(Text(*args, **kw))


# -- Schriftfeld -----------------------------------------------------------

SCHRIFTFELD_H = 26.0


def _wert(projekt: Projekt, name: str, vorgabe: str = "") -> str:
    return projekt.feld(name, vorgabe)


def schriftfeld(blatt: Blatt, projekt: Projekt, leiste: int | None = None) -> None:
    """Der Kopf jedes Blattes, vollstaendig aus den Projektdaten.

    Die Leistennummer kommt aus dem Aufruf, nicht aus einer Kopie des
    Vorblatts - genau der Fehler, der in einer Mustertabelle steckt.
    """
    v = projekt.verteiler
    oben = blatt.hoehe - RAND - SCHRIFTFELD_H
    breite = blatt.breite - 2 * RAND

    blatt.rechteck(RAND, oben, breite, SCHRIFTFELD_H, fuellung=None, staerke=0.4)

    spalten = [
        [
            ("Firma", _wert(projekt, "firma")),
            ("Kunde", _wert(projekt, "kunde")),
            ("Anlage", _wert(projekt, "anlagennummer")),
            ("Kunden-Nr.", _wert(projekt, "kundennummer")),
        ],
        [
            ("Verteiler", v.name),
            ("Verteiler-Nr.", v.nummer),
            ("Leiste", "" if leiste is None else str(leiste)),
            ("Blatt", blatt.titel),
        ],
        [
            ("Erstellt", _paar(projekt, "erstellt")),
            ("Stand", _paar(projekt, "stand")),
            ("Geprüft", _paar(projekt, "geprueft")),
            ("Gezeichnet", _paar(projekt, "gezeichnet")),
        ],
    ]
    for name, wert in projekt.eigene_felder.items():
        spalten[2].append((name, wert))

    # Namen brauchen mehr Platz als Nummern - daher ungleiche Spalten.
    anteile = (0.38, 0.26, 0.36)
    x = RAND
    for i, spalte in enumerate(spalten):
        spaltenbreite = breite * anteile[i]
        if i:
            blatt.linie(x, oben, x, oben + SCHRIFTFELD_H, 0.2, LINIE_FEIN)
        zeilenhoehe = SCHRIFTFELD_H / max(len(spalte), 4)
        label_b = 20.0
        for j, (name, wert) in enumerate(spalte):
            y = oben + j * zeilenhoehe
            blatt.text(
                x + 2, y, label_b - 2, zeilenhoehe, name, KLEIN, LINKS, False, TINTE_LEISE
            )
            blatt.text(
                x + label_b + 2, y, spaltenbreite - label_b - 4, zeilenhoehe, wert,
                NORMAL, LINKS,
            )
        x += spaltenbreite


def _paar(projekt: Projekt, vorsilbe: str) -> str:
    """„am“ und „von“ eines Briefkopffeldes zu einer Zeile."""
    datum = _wert(projekt, f"{vorsilbe}_am")
    name = _wert(projekt, f"{vorsilbe}_von")
    if vorsilbe == "gezeichnet":
        kuerzel = _wert(projekt, "kuerzel")
        name = f"{name} ({kuerzel})" if name and kuerzel else name or kuerzel
    return " · ".join(t for t in (datum, name) if t)


def _fusszeile(blatt: Blatt, nummer: int, gesamt: int) -> None:
    y = blatt.hoehe - RAND + 1
    blatt.text(
        RAND, y, blatt.breite - 2 * RAND, 6,
        f"Blatt {nummer} von {gesamt}", KLEIN, RECHTS, False, TINTE_LEISE,
    )


# -- Deckblatt -------------------------------------------------------------


def deckblatt(projekt: Projekt) -> Blatt:
    blatt = Blatt(*A4_HOCH, titel="Deckblatt")
    v = projekt.verteiler
    breite = blatt.breite - 2 * RAND
    y = 55.0

    blatt.text(
        RAND, y, breite, 14,
        _wert(projekt, "dokumenttitel", "Verteilerdokumentation"),
        GROSS, LINKS, True,
    )
    y += 16
    blatt.linie(RAND, y, RAND + breite, y, 0.6, TINTE)
    y += 10

    zeilen = [
        ("Verteiler", v.name),
        ("Verteilernummer", v.nummer),
        ("Aufbau", _aufbau(v)),
        ("Doppeladern", str(v.da_gesamt)),
        ("Kabel", str(len(v.kabel))),
        ("Rangierungen", str(len(v.rangierungen))),
        ("Firma", _wert(projekt, "firma")),
        ("Kunde", _wert(projekt, "kunde")),
        ("Anlagennummer", _wert(projekt, "anlagennummer")),
        ("Kundennummer", _wert(projekt, "kundennummer")),
        ("Erstellt", _paar(projekt, "erstellt")),
        ("Stand", _paar(projekt, "stand")),
        ("Geprüft", _paar(projekt, "geprueft")),
        ("Gezeichnet", _paar(projekt, "gezeichnet")),
    ]
    zeilen += list(projekt.eigene_felder.items())

    for name, wert in zeilen:
        if not str(wert).strip():
            continue
        blatt.text(RAND, y, 46, 7, name, NORMAL, LINKS, False, TINTE_LEISE)
        blatt.text(RAND + 48, y, breite - 48, 7, str(wert), MITTEL)
        y += 7.6

    schriftfeld(blatt, projekt)
    return blatt


def _aufbau(v: Verteiler) -> str:
    if not v.reihen:
        return ""
    leisten = len(v.reihen[0].leisten)
    da = v.reihen[0].leisten[0].da_anzahl if leisten else 0
    return f"{len(v.reihen)} Reihen × {leisten} Leisten × {da} DA"


# -- Verteilerbelegung -----------------------------------------------------

ZELLE_B = 6.0
ZELLE_H = 9.0
LEISTENLABEL_B = 14.0
ABSTAND_LEISTEN = 3.0
ABSTAND_REIHEN = 12.0


def verteilerbelegung(projekt: Projekt) -> Blatt:
    """Jede Leiste ein Kasten aus DA-Zellen, Kabel als Block.

    Querformat, weil zwei Reihen im Hochformat nicht nebeneinander
    passen. Die Zellen werden so weit vergroessert, wie das Blatt
    es hergibt - ein 40-DA-Verteiler soll die Seite nicht als Briefmarke
    in der Ecke fuellen.
    """
    blatt = Blatt(*A4_QUER, titel="Verteilerbelegung")
    v = projekt.verteiler

    blatt.text(RAND, RAND, 120, 8, "Verteilerbelegung", MITTEL, LINKS, True)

    oben = RAND + 12
    platz_b = blatt.breite - 2 * RAND
    platz_h = blatt.hoehe - RAND - SCHRIFTFELD_H - 6 - oben
    faktor = _belegungsfaktor(v, platz_b, platz_h)

    zelle_b = ZELLE_B * faktor
    zelle_h = ZELLE_H * faktor
    # Die Beschriftung waechst nur begrenzt mit - sonst frisst sie die Zellen.
    label_b = LEISTENLABEL_B * min(faktor, 1.5)
    luft_l = ABSTAND_LEISTEN * faktor
    luft_r = ABSTAND_REIHEN * faktor
    schrift = KLEIN if faktor < 1.4 else NORMAL

    kaesten: dict[int, tuple[float, float, int]] = {}
    x = RAND
    for reihe in v.reihen:
        breiteste = max((l.da_anzahl for l in reihe.leisten), default=0)
        y = oben
        for leiste in reihe.leisten:
            kaesten[leiste.nummer] = (x + label_b, y, leiste.da_anzahl)
            y += zelle_h + luft_l
        x += label_b + breiteste * zelle_b + luft_r

    for nummer, (kx, ky, da) in kaesten.items():
        blatt.text(
            kx - label_b, ky, label_b - 2, zelle_h,
            f"Leiste {nummer}", schrift, RECHTS,
        )
        blatt.rechteck(kx, ky, da * zelle_b, zelle_h, staerke=0.4)
        for i in range(1, da):
            zx = kx + i * zelle_b
            blatt.linie(zx, ky, zx, ky + zelle_h, 0.15, LINIE_FEIN)

    for kabel in v.kabel:
        for abschnitt in kabel.abschnitte:
            if abschnitt.leiste not in kaesten:
                continue
            kx, ky, _ = kaesten[abschnitt.leiste]
            bx = kx + (abschnitt.start_da - 1) * zelle_b
            bb = abschnitt.anzahl_da * zelle_b
            blatt.rechteck(bx, ky, bb, zelle_h, fuellung=FUELLUNG_KABEL, staerke=0.5)
            beschriftung = kabel.beschriftung
            if kabel.gekuerzt and abschnitt is kabel.abschnitte[-1]:
                beschriftung += " (gekürzt)"
            blatt.text(bx + 1, ky, bb - 2, zelle_h * 0.62, beschriftung, schrift)

    # Die DA-Nummern zuletzt, damit sie auch auf einem Kabelblock stehen.
    for _, (kx, ky, da) in kaesten.items() if zelle_b >= 4.5 else ():
        for i in range(da):
            blatt.text(
                kx + i * zelle_b, ky + zelle_h * 0.6, zelle_b, zelle_h * 0.4,
                str(i + 1), KLEIN, MITTE, False, TINTE_LEISE,
            )

    schriftfeld(blatt, projekt)
    return blatt


def _belegungsfaktor(v: Verteiler, platz_b: float, platz_h: float) -> float:
    """Wie stark die Grundmasse vergroessert werden duerfen."""
    if not v.reihen:
        return 1.0
    breite = sum(
        LEISTENLABEL_B + max((l.da_anzahl for l in r.leisten), default=0) * ZELLE_B
        + ABSTAND_REIHEN
        for r in v.reihen
    ) - ABSTAND_REIHEN
    leisten = max(len(r.leisten) for r in v.reihen)
    hoehe = leisten * (ZELLE_H + ABSTAND_LEISTEN) - ABSTAND_LEISTEN
    # Kleiner als 1 bei sehr grossen Verteilern, sonst passt das Blatt nicht.
    return max(0.3, min(platz_b / breite, platz_h / hoehe, 3.0))


# -- Leistenblatt ----------------------------------------------------------

SPALTEN = (
    ("Stift", 10.0, MITTE),
    ("", 7.0, MITTE),
    ("Farbe", 16.0, LINKS),
    ("Bezeichnung", 46.0, LINKS),
    ("Rangierung", 30.0, LINKS),
    ("Bemerkung", 44.0, LINKS),
    ("Kabel", 33.0, LINKS),
)
KOPF_H = 7.0
ZEILE_H_MAX = 9.5
ZEILE_H_MIN = 4.2


def leistenblatt(projekt: Projekt, leiste_nr: int) -> Blatt:
    v = projekt.verteiler
    leiste = v.leiste(leiste_nr)
    blatt = Blatt(*A4_HOCH, titel=f"Leiste {leiste_nr}")

    blatt.text(RAND, RAND, 120, 8, f"Leiste {leiste_nr}", MITTEL, LINKS, True)
    blatt.text(
        RAND, RAND, blatt.breite - 2 * RAND, 8,
        f"{leiste.da_anzahl} DA", NORMAL, RECHTS, False, TINTE_LEISE,
    )

    oben = RAND + 12
    tabellenbreite = sum(b for _, b, _ in SPALTEN)
    zeile_h = _zeilenhoehe(blatt, oben, leiste.da_anzahl)

    x = RAND
    blatt.rechteck(RAND, oben, tabellenbreite, KOPF_H, fuellung=FUELLUNG_KOPF, staerke=0.4)
    for name, breite, ausrichtung in SPALTEN:
        blatt.text(x + 1.5, oben, breite - 3, KOPF_H, name, KLEIN, ausrichtung, True)
        x += breite

    y = oben + KOPF_H
    for stift in leiste.stifte:
        kabel = v.kabel_an(leiste_nr, stift.nummer)
        for seite in ("a", "b"):
            ader = stift.ader(seite)
            ziele = v.ziele_von(_adresse(leiste_nr, stift.nummer, seite))
            werte = [
                str(stift.nummer) if seite == "a" else "",
                seite,
                ader.farbe,
                ader.bezeichnung,
                adressen_schreiben(ziele),
                ader.bemerkung,
                "",
            ]
            x = RAND
            for (_, breite, ausrichtung), wert in zip(SPALTEN, werte):
                blatt.text(x + 1.5, y, breite - 3, zeile_h, wert, NORMAL, ausrichtung)
                x += breite
            # Feine Linie zwischen a und b, kraeftige zwischen den Stiften.
            fein = seite == "a"
            blatt.linie(
                RAND, y + zeile_h, RAND + tabellenbreite, y + zeile_h,
                0.15 if fein else 0.3, LINIE_FEIN if fein else LINIE,
            )
            y += zeile_h

    _kabelklammern(blatt, v, leiste_nr, oben + KOPF_H, tabellenbreite, zeile_h)

    x = RAND
    unten = oben + KOPF_H + leiste.da_anzahl * 2 * zeile_h
    for _, breite, _ in SPALTEN:
        blatt.linie(x, oben, x, unten, 0.2, LINIE)
        x += breite
    blatt.linie(x, oben, x, unten, 0.2, LINIE)
    blatt.rechteck(RAND, oben, tabellenbreite, unten - oben, staerke=0.4)

    schriftfeld(blatt, projekt, leiste_nr)
    return blatt


def _zeilenhoehe(blatt: Blatt, oben: float, da_anzahl: int) -> float:
    """Die Tabelle nutzt das Blatt aus - 20 DA sind 40 Zeilen und passen auch."""
    platz = blatt.hoehe - RAND - SCHRIFTFELD_H - 6 - (oben + KOPF_H)
    return max(ZEILE_H_MIN, min(ZEILE_H_MAX, platz / (da_anzahl * 2)))


def _adresse(leiste: int, stift: int, seite: str):
    from .modell import Aderadresse

    return Aderadresse(leiste, stift, seite)


def _kabelklammern(
    blatt: Blatt,
    v: Verteiler,
    leiste_nr: int,
    oben: float,
    tabellenbreite: float,
    zeile_h: float,
) -> None:
    """Die Klammer rechts umfasst genau die belegten Zeilen - 4 DA sind 8."""
    breite = SPALTEN[-1][1]
    x = RAND + tabellenbreite - breite
    for kabel in v.kabel:
        for abschnitt in kabel.abschnitte:
            if abschnitt.leiste != leiste_nr:
                continue
            y = oben + (abschnitt.start_da - 1) * 2 * zeile_h
            hoehe = abschnitt.anzahl_da * 2 * zeile_h
            blatt.rechteck(x, y, breite, hoehe, fuellung=FUELLUNG_KABEL, staerke=0.4)
            blatt.text(
                x + 1.5, y, breite - 3, min(hoehe, zeile_h * 2),
                kabel.beschriftung, KLEIN,
            )
            if kabel.gekuerzt and hoehe >= zeile_h * 2:
                blatt.text(
                    x + 1.5, y + zeile_h * 2, breite - 3, zeile_h * 2,
                    f"gekürzt: {kabel.da_aufgelegt} von {kabel.da_gesamt} DA",
                    KLEIN, LINKS, False, TINTE_LEISE,
                )


# -- Blattfolge ------------------------------------------------------------


def blaetter(projekt: Projekt) -> list[Blatt]:
    """Deckblatt, Verteilerbelegung, je Leiste ein Blatt."""
    folge = [deckblatt(projekt), verteilerbelegung(projekt)]
    for leiste in projekt.verteiler.alle_leisten:
        folge.append(leistenblatt(projekt, leiste.nummer))
    for i, blatt in enumerate(folge, 1):
        _fusszeile(blatt, i, len(folge))
    return folge
