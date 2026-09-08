"""Layoutmodell: Blaetter als Zeichenanweisungen.

Hier entsteht das Blatt einmal - in Millimetern, ohne Qt und ohne
ReportLab. Vorschau und PDF zeichnen dasselbe Modell ab; sie koennen
deshalb nicht auseinanderlaufen.

Wie das Blatt aussieht, sagt die Blattvorlage; was darauf steht, kommt
aus dem Projekt. Der Ursprung liegt oben links, x laeuft nach rechts,
y nach unten.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .blattvorlagen import LINKS, MITTE, RECHTS, STANDARD, Blattvorlage
from .modell import Bucht, Projekt, Verteiler

# -- Papier ----------------------------------------------------------------

A4_HOCH = (210.0, 297.0)
A4_QUER = (297.0, 210.0)

# -- Farben auf dem Papier -------------------------------------------------
# Ein Blatt ist Papier, kein Fenster: schwarze Schrift, graue Linien,
# auch wenn das Programm im dunklen Farbsatz laeuft.

TINTE = "#000000"
TINTE_LEISE = "#555555"
LINIE = "#7A7A7A"
LINIE_FEIN = "#B4B4B4"
FUELLUNG_KOPF = "#E8E8E8"
FUELLUNG_KABEL = "#EFEFEF"


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
    """Text in einem Kasten, senkrecht mittig.

    ``drehung`` ist der Winkel gegen den Uhrzeigersinn: 90 laesst den Text
    von unten nach oben laufen, wie in schmalen Spalten technischer
    Zeichnungen ueblich. Der Kasten bleibt derselbe - gedreht wird nur,
    was darin steht, und dann ist seine Hoehe die Laenge der Zeile.
    """

    x: float
    y: float
    breite: float
    hoehe: float
    text: str
    groesse: float = 8.5
    ausrichtung: str = LINKS
    fett: bool = False
    farbe: str = TINTE
    drehung: float = 0.0

    @property
    def zeilenlaenge(self) -> float:
        """Wie viel Platz die Zeile hat - quer gedreht ist das die Hoehe."""
        return self.hoehe if self.drehung else self.breite


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

BESCHRIFTUNG = {
    "firma": "Firma",
    "kunde": "Kunde",
    "anlagennummer": "Anlage",
    "kundennummer": "Kunden-Nr.",
    "verteiler": "Verteiler",
    "verteilernummer": "Verteiler-Nr.",
    "leiste": "Leiste",
    "blatt": "Blatt",
    "erstellt": "Erstellt",
    "stand": "Stand",
    "geprueft": "Geprüft",
    "gezeichnet": "Gezeichnet",
    "dokumenttitel": "Titel",
}


def _wert(projekt: Projekt, name: str, vorgabe: str = "") -> str:
    """Der Wert eines Feldes - abgewaehlte Felder bleiben leer."""
    return projekt.anzeigewert(name, vorgabe)


def _paar(projekt: Projekt, vorsilbe: str) -> str:
    """„am“ und „von“ eines Briefkopffeldes zu einer Zeile."""
    datum = _wert(projekt, f"{vorsilbe}_am")
    name = _wert(projekt, f"{vorsilbe}_von")
    if vorsilbe == "gezeichnet":
        kuerzel = _wert(projekt, "kuerzel")
        name = f"{name} ({kuerzel})" if name and kuerzel else name or kuerzel
    return " · ".join(t for t in (datum, name) if t)


# Marken, die kein Briefkopffeld sind - sie gehoeren zum Blatt selbst und
# lassen sich nicht abwaehlen.
BLATTMARKEN = ("verteiler", "verteilernummer", "leiste", "blatt")
# Marken, die aus mehreren Feldern zusammengesetzt sind.
PAARMARKEN = {
    "erstellt": ("erstellt_am", "erstellt_von"),
    "stand": ("stand_am", "stand_von"),
    "geprueft": ("geprueft_am", "geprueft_von"),
    "gezeichnet": ("gezeichnet_am", "gezeichnet_von", "kuerzel"),
}


def _marke_sichtbar(marke: str, projekt: Projekt) -> bool:
    """Soll diese Zeile des Schriftfeldes ueberhaupt erscheinen?

    Ein abgewaehltes Feld verschwindet mitsamt seiner Beschriftung - eine
    Zeile „Kunde“ ohne Kunden waere schlimmer als gar keine. Ein leeres,
    aber angewaehltes Feld bleibt dagegen stehen: die Beschriftung ist
    dann die Zeile, in die von Hand eingetragen wird.
    """
    if marke in BLATTMARKEN:
        return True
    if marke in PAARMARKEN:
        return any(projekt.sichtbar(teil) for teil in PAARMARKEN[marke])
    return projekt.sichtbar(marke)


def _eintraege(
    marke: str, projekt: Projekt, blatt: Blatt, leiste: int | None
) -> list[tuple[str, str]]:
    """Was hinter einer Marke des Schriftfeldes steht."""
    v = projekt.verteiler
    if marke == "eigene":
        return list(projekt.sichtbare_eigene_felder().items())
    if not _marke_sichtbar(marke, projekt):
        return []
    if marke == "verteiler":
        wert = v.name
    elif marke == "verteilernummer":
        wert = v.nummer
    elif marke == "leiste":
        wert = "" if leiste is None else str(leiste)
    elif marke == "blatt":
        wert = blatt.titel
    elif marke in ("erstellt", "stand", "geprueft", "gezeichnet"):
        wert = _paar(projekt, marke)
    else:
        wert = _wert(projekt, marke)
    return [(BESCHRIFTUNG.get(marke, marke), wert)]


def schriftfeldzeilen(eintraege: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Verteilt mehrzeilige Werte auf eigene Zeilen.

    Eine Anschrift steht in einer Zeile je Zeile - Firma, Strasse, Ort -
    und nicht hintereinanderweg. Die Beschriftung steht nur an der ersten.
    """
    zeilen: list[tuple[str, str]] = []
    for name, wert in eintraege:
        teile = str(wert).split("\n") or [""]
        for i, teil in enumerate(teile):
            zeilen.append((name if i == 0 else "", teil.strip()))
    return zeilen


def schriftfeldwerte(
    projekt: Projekt,
    leiste: int | None = None,
    vorlage: Blattvorlage = STANDARD,
    blatttitel: str = "",
) -> list[tuple[str, str]]:
    """Beschriftung und Wert jeder Zeile des Schriftfeldes.

    Dieselbe Auswahl wie auf dem gezeichneten Blatt - nur ohne Kaesten,
    damit auch eine Tabelle sie fuellen kann.
    """
    traeger = Blatt(0, 0, titel=blatttitel)
    return [
        eintrag
        for marken in vorlage.schriftfeld
        for marke in marken
        for eintrag in _eintraege(marke, projekt, traeger, leiste)
    ]


def schriftfeld(
    blatt: Blatt,
    projekt: Projekt,
    leiste: int | None = None,
    vorlage: Blattvorlage = STANDARD,
) -> None:
    """Der Kopf jedes Blattes, vollstaendig aus den Projektdaten.

    Die Leistennummer kommt aus dem Aufruf, nicht aus einer Kopie des
    Vorblatts - genau der Fehler, der in einer Mustertabelle steckt.

    Wie die Felder liegen, sagt die Blattvorlage: in Spalten aus
    Beschriftung und Wert oder in der Aufteilung der Mustertabellen.
    """
    if vorlage.schriftfeld_art == "beispiel":
        _schriftfeld_beispiel(blatt, projekt, leiste, vorlage)
        return

    rand = vorlage.rand
    hoehe = vorlage.schriftfeld_hoehe
    oben = blatt.hoehe - rand - hoehe
    breite = blatt.breite - 2 * rand

    blatt.rechteck(rand, oben, breite, hoehe, fuellung=None, staerke=0.4)

    spalten = [
        schriftfeldzeilen(
            [eintrag
             for marke in marken
             for eintrag in _eintraege(marke, projekt, blatt, leiste)]
        )
        for marken in vorlage.schriftfeld
    ]

    # Namen brauchen mehr Platz als Nummern - daher ungleiche Spalten.
    anteile = _schriftfeldanteile(len(spalten), vorlage.schriftfeld_anteile)
    x = rand
    for i, spalte in enumerate(spalten):
        spaltenbreite = breite * anteile[i]
        if i:
            blatt.linie(x, oben, x, oben + hoehe, 0.2, LINIE_FEIN)
        zeilenhoehe = hoehe / max(len(spalte), 4)
        label_b = 20.0
        for j, (name, wert) in enumerate(spalte):
            y = oben + j * zeilenhoehe
            blatt.text(
                x + 2, y, label_b - 2, zeilenhoehe, name,
                vorlage.schrift_klein, LINKS, False, TINTE_LEISE,
            )
            blatt.text(
                x + label_b + 2, y, spaltenbreite - label_b - 4, zeilenhoehe, wert,
                vorlage.schrift_normal, LINKS,
            )
        x += spaltenbreite


def _schriftfeldanteile(
    anzahl: int, vorgabe: tuple[float, ...] = ()
) -> list[float]:
    """Wie sich die Bloecke des Schriftfeldes die Breite teilen."""
    if len(vorgabe) == anzahl and sum(vorgabe) > 0:
        summe = sum(vorgabe)
        return [teil / summe for teil in vorgabe]
    if anzahl == 3:
        return [0.38, 0.26, 0.36]
    return [1.0 / anzahl] * anzahl


def _schriftfeld_beispiel(
    blatt: Blatt, projekt: Projekt, leiste: int | None, vorlage: Blattvorlage
) -> None:
    """Das Schriftfeld der Mustertabellen, Feld fuer Feld nachgebaut.

    Links oben eine Matrix: die Spalten Datum und Name, die Zeilen
    Erstellt, Stand und Geprueft. Links unten der Verteiler mit Nummer
    und Leiste. Rechts daneben zwei Kaesten uebereinander - Firma oben,
    Kunde unten -, in denen die Anschrift zeilenweise steht.
    """
    rand = vorlage.rand
    hoehe = vorlage.schriftfeld_hoehe
    oben = blatt.hoehe - rand - hoehe
    breite = blatt.breite - 2 * rand

    # Wie sich die beiden Haelften teilen, sagt die Blattvorlage: links
    # die Matrix und der Verteiler, rechts die beiden Anschriften.
    linkes = breite * _schriftfeldanteile(2, vorlage.schriftfeld_anteile)[0]
    mitte_y = oben + hoehe / 2

    blatt.rechteck(rand, oben, breite, hoehe, fuellung=None, staerke=0.4)
    blatt.linie(rand + linkes, oben, rand + linkes, oben + hoehe, 0.2, LINIE_FEIN)
    blatt.linie(rand, mitte_y, rand + breite, mitte_y, 0.2, LINIE_FEIN)

    _beispiel_matrix(blatt, projekt, vorlage, rand, oben, linkes, hoehe / 2)
    _beispiel_verteiler(
        blatt, projekt, leiste, vorlage, rand, mitte_y, linkes, hoehe / 2
    )

    anschriften = rand + linkes
    weite = breite - linkes
    for i, marke in enumerate(("firma", "kunde")):
        _beispiel_anschrift(
            blatt, projekt, vorlage, marke,
            anschriften, oben + i * hoehe / 2, weite, hoehe / 2,
        )


def _beispiel_matrix(
    blatt: Blatt, projekt: Projekt, vorlage: Blattvorlage,
    x: float, y: float, breite: float, hoehe: float,
) -> None:
    """Erstellt / Stand / Geprueft, je mit Datum und Name."""
    marken = [m for m in ("erstellt", "stand", "geprueft")
              if _marke_sichtbar(m, projekt)]
    zeilen = len(marken) + 1                      # die Kopfzeile zaehlt mit
    zeile_h = hoehe / max(zeilen, 4)
    label_b = breite * 0.42
    spalte_b = (breite - label_b) / 2

    for i, ueberschrift in enumerate(("Datum", "Name")):
        blatt.text(
            x + label_b + i * spalte_b, y, spalte_b, zeile_h, ueberschrift,
            vorlage.schrift_klein, MITTE, False, TINTE_LEISE,
        )

    for j, marke in enumerate(marken, 1):
        zeile_y = y + j * zeile_h
        blatt.text(
            x + 2, zeile_y, label_b - 3, zeile_h, BESCHRIFTUNG[marke],
            vorlage.schrift_klein, LINKS, False, TINTE_LEISE,
        )
        for i, teil in enumerate(("_am", "_von")):
            blatt.text(
                x + label_b + i * spalte_b, zeile_y, spalte_b, zeile_h,
                _wert(projekt, marke + teil), vorlage.schrift_normal, MITTE,
            )


def _beispiel_verteiler(
    blatt: Blatt, projekt: Projekt, leiste: int | None, vorlage: Blattvorlage,
    x: float, y: float, breite: float, hoehe: float,
) -> None:
    """Verteiler, Nummer und Leiste - der Name unter seiner Beschriftung."""
    v = projekt.verteiler
    zeilen: list[tuple[str, str, bool]] = [
        ("Verteiler:", "", False),
        ("", v.name, True),                       # der Name steht darunter
        ("Verteiler Nr.", v.nummer, False),
        ("Leiste:", "" if leiste is None else str(leiste), False),
    ]
    zeile_h = hoehe / max(len(zeilen), 4)
    label_b = breite * 0.42
    for j, (name, wert, breit) in enumerate(zeilen):
        zeile_y = y + j * zeile_h
        if name:
            blatt.text(
                x + 2, zeile_y, label_b - 3, zeile_h, name,
                vorlage.schrift_klein, LINKS, False, TINTE_LEISE,
            )
        if breit:
            blatt.text(
                x + 4, zeile_y, breite - 6, zeile_h, wert, vorlage.schrift_normal
            )
        else:
            blatt.text(
                x + label_b, zeile_y, breite - label_b - 2, zeile_h, wert,
                vorlage.schrift_normal, MITTE,
            )


def _beispiel_anschrift(
    blatt: Blatt, projekt: Projekt, vorlage: Blattvorlage, marke: str,
    x: float, y: float, breite: float, hoehe: float,
) -> None:
    """Ein Kasten mit einer Anschrift - Zeile fuer Zeile, mittig."""
    if not _marke_sichtbar(marke, projekt):
        return
    zeilen = [teil.strip() for teil in _wert(projekt, marke).split("\n")]
    zeilen = [teil for teil in zeilen if teil]
    if not zeilen:
        blatt.text(
            x + 3, y, breite - 6, hoehe, BESCHRIFTUNG[marke],
            vorlage.schrift_klein, LINKS, False, TINTE_LEISE,
        )
        return

    zeile_h = min(vorlage.schrift_normal * 0.45 + 1.4, hoehe / len(zeilen))
    block = zeile_h * len(zeilen)
    erste = y + (hoehe - block) / 2
    for i, teil in enumerate(zeilen):
        blatt.text(
            x + 3, erste + i * zeile_h, breite - 6, zeile_h, teil,
            vorlage.schrift_normal, MITTE,
        )


def _fusszeile(blatt: Blatt, nummer: int, gesamt: int, vorlage: Blattvorlage) -> None:
    y = blatt.hoehe - vorlage.rand + 1
    blatt.text(
        vorlage.rand, y, blatt.breite - 2 * vorlage.rand, 6,
        f"Blatt {nummer} von {gesamt}",
        vorlage.schrift_klein, RECHTS, False, TINTE_LEISE,
    )


# -- Deckblatt -------------------------------------------------------------


def deckblatt(projekt: Projekt, vorlage: Blattvorlage = STANDARD) -> Blatt:
    blatt = Blatt(*A4_HOCH, titel="Deckblatt")
    v = projekt.verteiler
    rand = vorlage.rand
    breite = blatt.breite - 2 * rand
    y = 55.0

    blatt.text(
        rand, y, breite, 14,
        _wert(projekt, "dokumenttitel", "Verteilerdokumentation"),
        vorlage.schrift_gross, LINKS, True,
    )
    y += 16
    blatt.linie(rand, y, rand + breite, y, 0.6, TINTE)
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
        ("Blattvorlage", vorlage.name if not vorlage.standard else ""),
    ]
    zeilen += list(projekt.sichtbare_eigene_felder().items())

    # Eine Anschrift steht auch hier zeilenweise.
    for name, wert in schriftfeldzeilen([(n, w) for n, w in zeilen if str(w).strip()]):
        if name:
            blatt.text(
                rand, y, 46, 7, name, vorlage.schrift_normal, LINKS, False, TINTE_LEISE
            )
        blatt.text(rand + 48, y, breite - 48, 7, str(wert), vorlage.schrift_mittel)
        y += 7.6

    schriftfeld(blatt, projekt, None, vorlage)
    return blatt


def _aufbau(v: Verteiler) -> str:
    if not v.buchten:
        return ""
    leisten = len(v.buchten[0].leisten)
    da = v.buchten[0].leisten[0].da_anzahl if leisten else 0
    return f"{len(v.buchten)} Buchten × {leisten} Leisten × {da} DA"


# -- Verteilerbelegung -----------------------------------------------------


def verteilerbelegungen(
    projekt: Projekt, vorlage: Blattvorlage = STANDARD
) -> list[Blatt]:
    """Die Verteilerbelegung, bei Bedarf auf mehrere Blaetter verteilt.

    Mehr Buchten nebeneinander, als die Vorlage zulaesst, waeren auf A4
    quer nur noch gequetscht. Die weiteren bekommen deshalb eigene
    Blaetter, benannt nach den Buchten, die darauf stehen.
    """
    alle = projekt.verteiler.buchten
    je_blatt = max(1, vorlage.buchten_je_blatt)
    gruppen = [alle[i:i + je_blatt] for i in range(0, len(alle), je_blatt)] or [[]]
    if len(gruppen) == 1:
        return [verteilerbelegung(projekt, gruppen[0], vorlage=vorlage)]
    return [
        verteilerbelegung(projekt, gruppe, benennen=True, vorlage=vorlage)
        for gruppe in gruppen
    ]


def buchtnamen(buchten: list[Bucht]) -> str:
    """Wie das Blatt heisst, das diese Buchten traegt."""
    if not buchten:
        return "Verteilerbelegung"
    erste, letzte = buchten[0].nummer, buchten[-1].nummer
    return f"Bucht {erste}" if erste == letzte else f"Buchten {erste} und {letzte}"


def verteilerbelegung(
    projekt: Projekt,
    buchten: list[Bucht] | None = None,
    benennen: bool = False,
    vorlage: Blattvorlage = STANDARD,
) -> Blatt:
    """Jede Leiste ein Kasten aus DA-Zellen, Kabel als Block.

    Querformat, weil zwei Buchten im Hochformat nicht nebeneinander
    passen. Die Zellen werden so weit vergroessert, wie das Blatt
    es hergibt - ein 40-DA-Verteiler soll die Seite nicht als Briefmarke
    in der Ecke fuellen.
    """
    v = projekt.verteiler
    buchten = list(v.buchten if buchten is None else buchten)
    rand = vorlage.rand

    titel = buchtnamen(buchten) if benennen else "Verteilerbelegung"
    blatt = Blatt(*A4_QUER, titel=titel)
    ueberschrift = f"Verteilerbelegung — {titel}" if benennen else "Verteilerbelegung"
    blatt.text(rand, rand, 170, 8, ueberschrift, vorlage.schrift_mittel, LINKS, True)

    oben = rand + 12
    platz_b = blatt.breite - 2 * rand
    platz_h = blatt.hoehe - rand - vorlage.schriftfeld_hoehe - 6 - oben
    faktor = _belegungsfaktor(buchten, platz_b, platz_h, vorlage)

    zelle_b = vorlage.zelle_breite * faktor
    zelle_h = vorlage.zelle_hoehe * faktor
    # Die Beschriftung waechst nur begrenzt mit - sonst frisst sie die Zellen.
    label_b = vorlage.leistenlabel * min(faktor, 1.5)
    luft_l = vorlage.abstand_leisten * faktor
    luft_r = vorlage.abstand_buchten * faktor
    schrift = vorlage.schrift_klein if faktor < 1.4 else vorlage.schrift_normal

    kaesten: dict[int, tuple[float, float, int]] = {}
    x = rand
    for bucht in buchten:
        breiteste = max((l.da_anzahl for l in bucht.leisten), default=0)
        y = oben
        for leiste in bucht.leisten:
            kaesten[leiste.nummer] = (x + label_b, y, leiste.da_anzahl)
            y += zelle_h + luft_l
        x += label_b + breiteste * zelle_b + luft_r

    # Kein Raster in der Leiste: gezeichnet werden nur die Kabel. Was frei
    # ist - links, rechts oder beides -, bleibt eine durchgehende Flaeche,
    # und der Block zeigt durch seine Breite, wie viele Doppeladern er
    # belegt.
    for nummer, (kx, ky, da) in kaesten.items():
        blatt.text(
            kx - label_b, ky, label_b - 2, zelle_h, f"Leiste {nummer}", schrift, RECHTS
        )
        blatt.rechteck(kx, ky, da * zelle_b, zelle_h, staerke=0.4)

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
    # Keine Vorlage fuehrt sie noch - die Zahlen 1 bis 10 in jeder Zelle
    # waren mehr Raster als Auskunft. Wer sie will, schaltet sie in seiner
    # Blattvorlage wieder ein.
    if vorlage.da_nummern and zelle_b >= 4.5:
        for nummer, (kx, ky, da) in kaesten.items():
            for i in range(da):
                blatt.text(
                    kx + i * zelle_b, ky + zelle_h * 0.6, zelle_b, zelle_h * 0.4,
                    str(i + 1), vorlage.schrift_klein, MITTE, False, TINTE_LEISE,
                )

    schriftfeld(blatt, projekt, None, vorlage)
    return blatt


def _belegungsfaktor(
    buchten: list[Bucht], platz_b: float, platz_h: float, vorlage: Blattvorlage
) -> float:
    """Wie stark die Grundmasse auf diesem Blatt wachsen duerfen."""
    if not buchten:
        return 1.0
    breite = sum(
        vorlage.leistenlabel
        + max((l.da_anzahl for l in b.leisten), default=0) * vorlage.zelle_breite
        + vorlage.abstand_buchten
        for b in buchten
    ) - vorlage.abstand_buchten
    leisten = max(len(b.leisten) for b in buchten)
    hoehe = (
        leisten * (vorlage.zelle_hoehe + vorlage.abstand_leisten)
        - vorlage.abstand_leisten
    )
    # Kleiner als 1 bei sehr grossen Verteilern, sonst passt das Blatt nicht.
    return max(0.3, min(platz_b / breite, platz_h / hoehe, 3.0))


# -- Leistenblatt ----------------------------------------------------------


def kopfgruppen(spalten) -> list[tuple[int, int]]:
    """Welche Spalten sich eine Ueberschrift teilen.

    Eine Spalte ohne eigene Ueberschrift gehoert zur vorigen: so steht
    „Stift“ ueber der Nummer und ueber a und b, wie in den Vorlagen.
    Zurueck kommt je Gruppe die erste Spalte und ihre Zahl.
    """
    gruppen: list[list[int]] = []
    for i, spalte in enumerate(spalten):
        if gruppen and not str(spalte.ueberschrift).strip():
            gruppen[-1].append(i)
        else:
            gruppen.append([i])
    return [(teile[0], len(teile)) for teile in gruppen]


def zeilenwerte(
    projekt: Projekt, leiste_nr: int, stift_nr: int, seite: str
) -> dict[str, str]:
    """Was in den Spalten einer Aderzeile steht.

    Eine Stelle fuer beide Wege: das gezeichnete Blatt und die Mappe im
    Blattbild greifen auf dieselben Werte zu, damit sie nicht
    auseinanderlaufen koennen.
    """
    v = projekt.verteiler
    ader = v.leiste(leiste_nr).stift(stift_nr).ader(seite)
    return {
        # Wie in den Vorlagen: die Stiftnummer steht nur in der a-Zeile.
        "stift": str(stift_nr) if seite == "a" else "",
        "ader": seite,
        "farbe": ader.farbe,
        "bezeichnung": ader.bezeichnung,
        "rangierung": v.rangierfeld(
            _adresse(leiste_nr, stift_nr, seite), projekt.schreibweise
        ),
        "bemerkung": ader.bemerkung,
        "kabel": "",
    }


def leistenblatt(
    projekt: Projekt, leiste_nr: int, vorlage: Blattvorlage = STANDARD
) -> Blatt:
    v = projekt.verteiler
    leiste = v.leiste(leiste_nr)
    blatt = Blatt(*A4_HOCH, titel=f"Leiste {leiste_nr}")
    rand = vorlage.rand
    kopf_h = vorlage.kopfzeile_hoehe

    # Kein Blattkopf ueber der Tabelle: welche Leiste das Blatt zeigt,
    # steht im Schriftfeld - zweimal dasselbe waere nur Papier. Die
    # Tabelle beginnt dafuer gleich am Rand und hat mehr Platz.
    oben = rand
    tabellenbreite = blatt.breite - 2 * rand
    breiten = vorlage.breiten(tabellenbreite)
    zeile_h = _zeilenhoehe(blatt, oben, leiste.da_anzahl, vorlage)

    blatt.rechteck(rand, oben, tabellenbreite, kopf_h, fuellung=FUELLUNG_KOPF, staerke=0.4)
    gruppen = kopfgruppen(vorlage.spalten)
    for erste, anzahl in gruppen:
        spalte = vorlage.spalten[erste]
        x = rand + sum(breiten[:erste])
        breite = sum(breiten[erste:erste + anzahl])
        blatt.text(
            x + 1.5, oben, breite - 3, kopf_h, spalte.ueberschrift,
            vorlage.schrift_klein, spalte.ausrichtung, True,
        )

    y = oben + kopf_h
    for stift in leiste.stifte:
        for seite in ("a", "b"):
            werte = zeilenwerte(projekt, leiste_nr, stift.nummer, seite)
            x = rand
            for spalte, breite in zip(vorlage.spalten, breiten):
                blatt.text(
                    x + 1.5, y, breite - 3, zeile_h, werte.get(spalte.feld, ""),
                    vorlage.schrift_normal, spalte.ausrichtung,
                )
                x += breite
            # Feine Linie zwischen a und b, kraeftige zwischen den Stiften.
            fein = seite == "a"
            blatt.linie(
                rand, y + zeile_h, rand + tabellenbreite, y + zeile_h,
                0.15 if fein else 0.3, LINIE_FEIN if fein else LINIE,
            )
            y += zeile_h

    _kabelklammern(blatt, v, leiste_nr, oben + kopf_h, breiten, zeile_h, vorlage)

    x = rand
    unten = oben + kopf_h + leiste.da_anzahl * 2 * zeile_h
    # Wo zwei Spalten sich eine Ueberschrift teilen, beginnt der Strich
    # erst unter der Kopfzeile - sonst zerschnitte er sie.
    fortsetzung = {i for erste, anzahl in gruppen for i in range(erste + 1, erste + anzahl)}
    for i, breite in enumerate(breiten):
        blatt.linie(x, oben + (kopf_h if i in fortsetzung else 0), x, unten, 0.2, LINIE)
        x += breite
    blatt.linie(x, oben, x, unten, 0.2, LINIE)
    blatt.rechteck(rand, oben, tabellenbreite, unten - oben, staerke=0.4)

    schriftfeld(blatt, projekt, leiste_nr, vorlage)
    return blatt


def _zeilenhoehe(
    blatt: Blatt, oben: float, da_anzahl: int, vorlage: Blattvorlage
) -> float:
    """Die Tabelle nutzt das Blatt aus - 20 DA sind 40 Zeilen und passen auch."""
    platz = (
        blatt.hoehe - vorlage.rand - vorlage.schriftfeld_hoehe - 6
        - (oben + vorlage.kopfzeile_hoehe)
    )
    return max(
        vorlage.zeilenhoehe_min, min(vorlage.zeilenhoehe_max, platz / (da_anzahl * 2))
    )


def _adresse(leiste: int, stift: int, seite: str):
    from .modell import Aderadresse

    return Aderadresse(leiste, stift, seite)


def _kabelklammern(
    blatt: Blatt,
    v: Verteiler,
    leiste_nr: int,
    oben: float,
    breiten: list[float],
    zeile_h: float,
    vorlage: Blattvorlage,
) -> None:
    """Die Klammer umfasst genau die belegten Zeilen - 4 DA sind 8.

    Fuehrt die Vorlage keine Kabelspalte, entfaellt die Klammer.
    """
    stelle = next(
        (i for i, s in enumerate(vorlage.spalten) if s.feld == "kabel"), None
    )
    if stelle is None:
        return
    x = vorlage.rand + sum(breiten[:stelle])
    breite = breiten[stelle]

    for kabel in v.kabel:
        for abschnitt in kabel.abschnitte:
            if abschnitt.leiste != leiste_nr:
                continue
            y = oben + (abschnitt.start_da - 1) * 2 * zeile_h
            hoehe = abschnitt.anzahl_da * 2 * zeile_h
            blatt.rechteck(x, y, breite, hoehe, fuellung=FUELLUNG_KABEL, staerke=0.4)
            beschriftung = kabel.beschriftung
            if kabel.gekuerzt:
                zusatz = f"gekürzt: {kabel.da_aufgelegt} von {kabel.da_gesamt} DA"

            if vorlage.kabel_gedreht:
                # Quer gelesen ist die Klammer so lang wie das Kabel hoch
                # ist - ein langer Name passt hier hinein, waagerecht
                # muesste er in die schmale Spalte gequetscht werden.
                if kabel.gekuerzt:
                    beschriftung = f"{beschriftung} ({zusatz})"
                blatt.text(
                    x, y + 1.5, breite, hoehe - 3, beschriftung,
                    vorlage.schrift_klein, MITTE, drehung=90,
                )
                continue

            blatt.text(
                x + 1.5, y, breite - 3, min(hoehe, zeile_h * 2),
                beschriftung, vorlage.schrift_klein,
            )
            if kabel.gekuerzt and hoehe >= zeile_h * 2:
                blatt.text(
                    x + 1.5, y + zeile_h * 2, breite - 3, zeile_h * 2,
                    zusatz, vorlage.schrift_klein, LINKS, False, TINTE_LEISE,
                )


# -- Blattfolge ------------------------------------------------------------


def blaetter(projekt: Projekt, vorlage: Blattvorlage = STANDARD) -> list[Blatt]:
    """Deckblatt, Verteilerbelegung, je Leiste ein Blatt."""
    folge = [deckblatt(projekt, vorlage), *verteilerbelegungen(projekt, vorlage)]
    for leiste in projekt.verteiler.alle_leisten:
        folge.append(leistenblatt(projekt, leiste.nummer, vorlage))
    for i, blatt in enumerate(folge, 1):
        _fusszeile(blatt, i, len(folge), vorlage)
    return folge
