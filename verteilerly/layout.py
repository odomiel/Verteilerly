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
from .modell import (
    BLATTBESCHRIFTUNG,
    LEERER_STIL,
    STILFELDER,
    TEILBARE_FELDER,
    UNGETEILT,
    Bucht,
    Projekt,
    Textstil,
    Verteiler,
    Zellenteilung,
    mehrzahl,
)

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

# Wie breit eine DA-Zelle der Verteilerbelegung hoechstens werden darf,
# gemessen an ihrer Hoehe: breiter gezogen wird sie zum Balken.
BREITE_HOECHSTENS = 2.0
# Ab wie vielen Leisten je Bucht diese ein eigenes Blatt bekommt.
# Zwei lange Buchten nebeneinander waeren nur noch Striche.
LEISTEN_JE_BLATT = 13

# Wie viel der linken Schriftfeldhaelfte die Beschriftungen bekommen
# (Bauart "beispiel"). "Erstellt", "Geprueft" und "Verteiler Nr." sind
# kurz; was darueber hinausgeht, fehlt den Werten daneben - ein Name wie
# "Max Mustermann" braucht mehr Platz als das Wort "Stand".
BESCHRIFTUNGSANTEIL = 0.28


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
    # Am Ende, damit die vorhandenen Aufrufe mit festen Stellen bleiben.
    kursiv: bool = False

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

# Die Vorgabe steht im Modell; was hier gezeichnet wird, sagt das
# Projekt - es darf jedes Wort ersetzen.
BESCHRIFTUNG = BLATTBESCHRIFTUNG


def _wert(projekt: Projekt, name: str, vorgabe: str = "") -> str:
    """Der Wert eines Feldes - abgewaehlte Felder bleiben leer."""
    return projekt.anzeigewert(name, vorgabe)


def _paar(projekt: Projekt, vorsilbe: str) -> str:
    """„am“ und „von“ eines Projektdatenfeldes zu einer Zeile."""
    datum = _wert(projekt, f"{vorsilbe}_am")
    name = _wert(projekt, f"{vorsilbe}_von")
    if vorsilbe == "gezeichnet":
        kuerzel = _wert(projekt, "kuerzel")
        name = f"{name} ({kuerzel})" if name and kuerzel else name or kuerzel
    return " · ".join(t for t in (datum, name) if t)


# Marken, die kein Projektdatenfeld sind - sie gehoeren zum Blatt selbst und
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
    marke: str,
    projekt: Projekt,
    blatt: Blatt,
    leiste: int | None,
    blattart: str = "leisten",
) -> list[tuple[str, str]]:
    """Was hinter einer Marke des Schriftfeldes steht."""
    v = projekt.verteiler
    eigene = list(projekt.eigene_felder_hier(blattart).items())
    if marke == "eigene":
        # Auf der Verteilerbelegung stehen sie am Platz der Leiste -
        # zweimal braucht sie niemand.
        return [] if blattart == "belegung" else eigene
    if marke == "leiste" and blattart == "belegung":
        # Dieses Blatt zeigt alle Leisten, also keine einzelne: der Platz
        # gehoert hier den eigenen Feldern.
        return eigene
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
    return [(projekt.beschriftung(marke), wert)]


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
    blattart: str = "leisten",
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
        for eintrag in _eintraege(marke, projekt, traeger, leiste, blattart)
    ]


def schriftfeldspalten(
    projekt: Projekt,
    leiste: int | None = None,
    vorlage: Blattvorlage = STANDARD,
    blattart: str = "leisten",
    blatttitel: str = "",
) -> list[list[tuple[str, str]]]:
    """Das Schriftfeld in Bloecken, wie die Blattvorlage es aufteilt.

    Eine Liste je Block, darin die Zeilen aus Beschriftung und Wert.
    Gezeichnetes Blatt und Excel-Mappe fragen dieselbe Stelle.
    """
    traeger = Blatt(0, 0, titel=blatttitel)
    return [
        schriftfeldzeilen(
            [eintrag
             for marke in marken
             for eintrag in _eintraege(marke, projekt, traeger, leiste, blattart)]
        )
        for marken in vorlage.schriftfeld
    ]


def beispielschriftfeld(
    projekt: Projekt,
    leiste: int | None = None,
    blattart: str = "leisten",
) -> tuple[
    list[tuple[str, str, str]], list[tuple[str, str]], list[tuple[str, list[str]]]
]:
    """Die drei Teile dieses Schriftfeldes, als reine Werte.

    Erstens die Matrix - je Zeile Beschriftung, Datum und Name -,
    zweitens der Verteiler mit Nummer, Leiste und den eigenen Feldern,
    drittens die beiden Anschriften mit ihren Zeilen. Wer daraus ein
    Blatt zeichnet oder eine Tabelle baut, nimmt dieselben Werte.
    """
    matrix = [
        (
            projekt.beschriftung(marke),
            _wert(projekt, marke + "_am"),
            _wert(projekt, marke + "_von"),
        )
        for marke in ("erstellt", "stand", "geprueft")
        if _marke_sichtbar(marke, projekt)
    ]

    v = projekt.verteiler
    verteiler = [
        (_mit_doppelpunkt(projekt.beschriftung("verteiler")), v.name),
        (_mit_doppelpunkt(projekt.beschriftung("verteilernummer")), v.nummer),
    ]
    if blattart == "belegung":
        verteiler += list(projekt.eigene_felder_hier("belegung").items())
    else:
        verteiler.append((
            _mit_doppelpunkt(projekt.beschriftung("leiste")),
            "" if leiste is None else str(leiste),
        ))
        verteiler += list(projekt.eigene_felder_hier(blattart).items())

    anschriften: list[tuple[str, list[str]]] = []
    for marke in ("firma", "kunde"):
        if not _marke_sichtbar(marke, projekt):
            anschriften.append((projekt.beschriftung(marke), []))
            continue
        zeilen = [teil.strip() for teil in _wert(projekt, marke).split("\n")]
        anschriften.append((projekt.beschriftung(marke), [t for t in zeilen if t]))
    return matrix, verteiler, anschriften


def schriftfeld(
    blatt: Blatt,
    projekt: Projekt,
    leiste: int | None = None,
    vorlage: Blattvorlage = STANDARD,
    blattart: str = "leisten",
) -> None:
    """Der Kopf jedes Blattes, vollstaendig aus den Projektdaten.

    Die Leistennummer kommt aus dem Aufruf, nicht aus einer Kopie des
    Vorblatts - genau der Fehler, der in einer Mustertabelle steckt.

    Wie die Felder liegen, sagt die Blattvorlage: in Spalten aus
    Beschriftung und Wert oder in der Aufteilung der Mustertabellen.
    """
    if vorlage.schriftfeld_art == "beispiel":
        _schriftfeld_beispiel(blatt, projekt, leiste, vorlage, blattart)
        return

    rand = vorlage.rand
    hoehe = vorlage.schriftfeld_hoehe
    oben = blatt.hoehe - rand - hoehe
    breite = blatt.breite - 2 * rand

    blatt.rechteck(rand, oben, breite, hoehe, fuellung=None, staerke=0.4)

    spalten = schriftfeldspalten(
        projekt, leiste, vorlage, blattart, blatt.titel
    )

    # Namen brauchen mehr Platz als Nummern - daher ungleiche Spalten.
    anteile = schriftfeldanteile(len(spalten), vorlage.schriftfeld_anteile)
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


def schriftfeldanteile(
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
    blatt: Blatt,
    projekt: Projekt,
    leiste: int | None,
    vorlage: Blattvorlage,
    blattart: str = "leisten",
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
    linkes = breite * schriftfeldanteile(2, vorlage.schriftfeld_anteile)[0]
    mitte_y = oben + hoehe / 2

    blatt.rechteck(rand, oben, breite, hoehe, fuellung=None, staerke=0.4)
    blatt.linie(rand + linkes, oben, rand + linkes, oben + hoehe, 0.2, LINIE_FEIN)
    blatt.linie(rand, mitte_y, rand + breite, mitte_y, 0.2, LINIE_FEIN)

    _beispiel_matrix(blatt, projekt, vorlage, rand, oben, linkes, hoehe / 2)
    _beispiel_verteiler(
        blatt, projekt, leiste, vorlage, rand, mitte_y, linkes, hoehe / 2, blattart
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
    marken = beispielschriftfeld(projekt)[0]
    zeilen = len(marken) + 1                      # die Kopfzeile zaehlt mit
    zeile_h = hoehe / max(zeilen, 4)
    label_b = breite * BESCHRIFTUNGSANTEIL
    spalte_b = (breite - label_b) / 2

    for i, ueberschrift in enumerate(("Datum", "Name")):
        blatt.text(
            x + label_b + i * spalte_b, y, spalte_b, zeile_h, ueberschrift,
            vorlage.schrift_klein, MITTE, False, TINTE_LEISE,
        )

    for j, (beschriftung, datum, name) in enumerate(marken, 1):
        zeile_y = y + j * zeile_h
        blatt.text(
            x + 2, zeile_y, label_b - 3, zeile_h, beschriftung,
            vorlage.schrift_klein, LINKS, False, TINTE_LEISE,
        )
        for i, wert in enumerate((datum, name)):
            blatt.text(
                x + label_b + i * spalte_b, zeile_y, spalte_b, zeile_h,
                wert, vorlage.schrift_normal, MITTE,
            )


def _mit_doppelpunkt(text: str) -> str:
    """Wie es die Mustertabelle haelt: "Verteiler:", aber "Verteiler-Nr."."""
    return text if text.endswith((":", ".")) else text + ":"


def _beispiel_verteiler(
    blatt: Blatt, projekt: Projekt, leiste: int | None, vorlage: Blattvorlage,
    x: float, y: float, breite: float, hoehe: float, blattart: str = "leisten",
) -> None:
    """Verteiler, Nummer und Leiste - Beschriftung links, Wert daneben.

    Auf der Verteilerbelegung gibt es keine einzelne Leiste; dort stehen
    an ihrer Stelle die eigenen Felder.
    """
    zeilen = beispielschriftfeld(projekt, leiste, blattart)[1]
    # Die Zeilenhoehe richtet sich nach der Matrix darueber, damit beide
    # Haelften dieselbe Schrift tragen; der Block steht dann aber mittig
    # zwischen den beiden Strichen statt oben angeschlagen.
    zeile_h = hoehe / max(len(zeilen), 4)
    erste = y + (hoehe - zeile_h * len(zeilen)) / 2
    # Dieselbe Fluchtlinie wie die Matrix darueber.
    label_b = breite * BESCHRIFTUNGSANTEIL
    for j, (name, wert) in enumerate(zeilen):
        zeile_y = erste + j * zeile_h
        blatt.text(
            x + 2, zeile_y, label_b - 3, zeile_h, name,
            vorlage.schrift_klein, LINKS, False, TINTE_LEISE,
        )
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
    beschriftung, zeilen = dict(
        (m, (b, z))
        for m, (b, z) in zip(
            ("firma", "kunde"), beispielschriftfeld(projekt)[2]
        )
    )[marke]
    if not zeilen:
        blatt.text(
            x + 3, y, breite - 6, hoehe, beschriftung,
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


def deckblattzeilen(
    projekt: Projekt, vorlage: Blattvorlage = STANDARD
) -> list[tuple[str, str]]:
    """Was auf dem Deckblatt steht - Beschriftung und Wert.

    Leere Zeilen fallen weg, mehrzeilige Anschriften stehen zeilenweise.
    Gezeichnetes Blatt und Excel-Mappe fragen dieselbe Stelle.

    Das Deckblatt hat Platz und schreibt die Woerter deshalb aus:
    "Verteilernummer" statt "Verteiler-Nr.". Wer ein Wort selbst gesetzt
    hat, bekommt seines - auch hier.
    """
    v = projekt.verteiler

    def wort(marke: str, vorgabe: str) -> str:
        return projekt.beschriftungen.get(marke, "").strip() or vorgabe

    zeilen = [
        (wort("verteiler", "Verteiler"), v.name),
        (wort("verteilernummer", "Verteilernummer"), v.nummer),
        ("Aufbau", _aufbau(v)),
        ("Doppeladern", str(v.da_gesamt)),
        ("Kabel", str(len(v.kabel))),
        ("Rangierungen", str(len(v.rangierungen))),
        (wort("firma", "Firma"), _wert(projekt, "firma")),
        (wort("kunde", "Kunde"), _wert(projekt, "kunde")),
        (wort("anlagennummer", "Anlagennummer"), _wert(projekt, "anlagennummer")),
        (wort("kundennummer", "Kundennummer"), _wert(projekt, "kundennummer")),
        (wort("erstellt", "Erstellt"), _paar(projekt, "erstellt")),
        (wort("stand", "Stand"), _paar(projekt, "stand")),
        (wort("geprueft", "Geprüft"), _paar(projekt, "geprueft")),
        (wort("gezeichnet", "Gezeichnet"), _paar(projekt, "gezeichnet")),
        ("Blattvorlage", vorlage.name if not vorlage.standard else ""),
    ]
    zeilen += list(projekt.eigene_felder_hier("deckblatt").items())
    # Eine Anschrift steht auch hier zeilenweise.
    return schriftfeldzeilen([(n, w) for n, w in zeilen if str(w).strip()])


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

    for name, wert in deckblattzeilen(projekt, vorlage):
        if name:
            blatt.text(
                rand, y, 46, 7, name, vorlage.schrift_normal, LINKS, False, TINTE_LEISE
            )
        blatt.text(rand + 48, y, breite - 48, 7, str(wert), vorlage.schrift_mittel)
        y += 7.6

    # Kein Schriftfeld: das Deckblatt ist selbst eines. Alles, was dort
    # unten stuende, steht hier schon in der Liste - zweimal dasselbe auf
    # einem Blatt ist kein Kopf, sondern eine Wiederholung.
    return blatt


def _aufbau(v: Verteiler) -> str:
    if not v.buchten:
        return ""
    leisten = len(v.buchten[0].leisten)
    da = v.buchten[0].leisten[0].da_anzahl if leisten else 0
    return " × ".join((
        mehrzahl(len(v.buchten), "Bucht", "Buchten"),
        mehrzahl(leisten, "Leiste", "Leisten"),
        f"{da} DA",
    ))


# -- Verteilerbelegung -----------------------------------------------------


def verteilerbelegungen(
    projekt: Projekt, vorlage: Blattvorlage = STANDARD
) -> list[Blatt]:
    """Die Verteilerbelegung, bei Bedarf auf mehrere Blaetter verteilt.

    Mehr Buchten nebeneinander, als die Vorlage zulaesst, waeren auf A4
    quer nur noch gequetscht. Die weiteren bekommen deshalb eigene
    Blaetter, benannt nach den Buchten, die darauf stehen.

    Zwei Faelle bekommen **jede Bucht auf ein eigenes Blatt**, und damit
    hochkant: mehr als zwei Buchten - zu zweit gruppiert bliebe
    sonst ein halbes Blatt fuer die letzte - und lange Buchten von mehr
    als dreizehn Leisten, die nebeneinander nur noch Striche waeren.
    """
    alle = projekt.verteiler.buchten
    je_blatt = max(1, vorlage.buchten_je_blatt)
    lang = any(len(b.leisten) > LEISTEN_JE_BLATT for b in alle)
    if len(alle) > 2 or lang:
        je_blatt = 1
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

    **Eine** Bucht steht hochkant: sie ist schmal und hoch, im Querformat
    bliebe die halbe Seite leer. Ab zwei Buchten quer, weil zwei
    nebeneinander im Hochformat nicht passen.

    Die Zellen werden so weit vergroessert, wie das Blatt es hergibt - ein
    40-DA-Verteiler soll die Seite nicht als Briefmarke in der Ecke
    fuellen -, und was dann noch uebrig ist, wird als Luft verteilt:
    zwischen die Buchten in der Breite, zwischen die Leisten in der Hoehe.
    Sonst draengte sich alles oben links zusammen.
    """
    v = projekt.verteiler
    buchten = list(v.buchten if buchten is None else buchten)
    rand = vorlage.rand

    titel = buchtnamen(buchten) if benennen else "Verteilerbelegung"
    hochkant = len(buchten) <= 1
    blatt = Blatt(*(A4_HOCH if hochkant else A4_QUER), titel=titel)
    ueberschrift = f"Verteilerbelegung — {titel}" if benennen else "Verteilerbelegung"
    blatt.text(rand, rand, 170, 8, ueberschrift, vorlage.schrift_mittel, LINKS, True)

    oben = rand + 12
    platz_b = blatt.breite - 2 * rand
    platz_h = blatt.hoehe - rand - vorlage.schriftfeld_hoehe - 6 - oben
    faktor = _belegungsfaktor(buchten, platz_b, platz_h, vorlage)

    zelle_h = vorlage.zelle_hoehe * faktor
    zelle_b = vorlage.zelle_breite * faktor
    # Die Beschriftung waechst nur begrenzt mit - sonst frisst sie die Zellen.
    label_b = vorlage.leistenlabel * min(faktor, 1.5)
    luft_l = vorlage.abstand_leisten * faktor
    luft_r = vorlage.abstand_buchten * faktor
    schrift = vorlage.schrift_klein if faktor < 1.4 else vorlage.schrift_normal

    # Bleibt in der Breite etwas uebrig, weil die Hoehe das Mass setzt,
    # duerfen die Zellen breiter werden - bis zum Doppelten. Eine etwas
    # breitere Zelle faellt kaum auf, ein leeres Drittel Blatt schon.
    spalten = sum(max((l.da_anzahl for l in b.leisten), default=0) for b in buchten)
    if spalten:
        passend = (
            platz_b - label_b * len(buchten) - luft_r * (len(buchten) - 1)
        ) / spalten
        zelle_b = max(zelle_b, min(passend, zelle_b * BREITE_HOECHSTENS))

    # Was nach dem Vergroessern uebrig bleibt, wird verteilt statt am
    # rechten und unteren Rand liegen zu lassen.
    breiten = [
        label_b + max((l.da_anzahl for l in b.leisten), default=0) * zelle_b
        for b in buchten
    ]
    # Der Rest ist, was nach den Buchten und der bisherigen Luft bleibt.
    luecken_b = len(buchten) - 1
    luft_r = _luft_verteilen(
        platz_b - sum(breiten) - luft_r * luecken_b, luecken_b, luft_r, platz_b
    )
    zeilen = max((len(b.leisten) for b in buchten), default=0)
    luecken_h = zeilen - 1
    # In der Hoehe hoechstens eine Zellenhoehe Luft je Leiste: weiter
    # auseinandergezogen sieht die Bucht aus wie eine Leiter.
    luft_l = _luft_verteilen(
        platz_h - zeilen * zelle_h - luft_l * luecken_h, luecken_h, luft_l, zelle_h
    )

    gesamt_b = sum(breiten) + luft_r * (len(buchten) - 1)
    gesamt_h = zeilen * zelle_h + luft_l * max(zeilen - 1, 0)
    kaesten: dict[int, tuple[float, float, int]] = {}
    # Was jetzt noch uebrig ist, liegt als Rand aussen herum.
    x = rand + max(platz_b - gesamt_b, 0) / 2
    oben_mitte = oben + max(platz_h - gesamt_h, 0) / 2
    for bucht, breite in zip(buchten, breiten):
        y = oben_mitte
        for leiste in bucht.leisten:
            kaesten[leiste.nummer] = (x + label_b, y, leiste.da_anzahl)
            y += zelle_h + luft_l
        x += breite + luft_r

    # Kein Raster in der Leiste: gezeichnet werden nur die Kabel. Was frei
    # ist - links, rechts oder beides -, bleibt eine durchgehende Flaeche,
    # und der Block zeigt durch seine Breite, wie viele Doppeladern er
    # belegt.
    for nummer, (kx, ky, da) in kaesten.items():
        # Linksbuendig, nicht an den Kasten geschoben: so beginnt die
        # Beschriftung jeder Leiste auf derselben Fluchtlinie wie das
        # Schriftfeld darunter, gleich wie breit die Spalte gerade ist.
        blatt.text(
            kx - label_b, ky, label_b - 2, zelle_h, f"Leiste {nummer}", schrift, LINKS
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

    schriftfeld(blatt, projekt, None, vorlage, "belegung")
    return blatt


def _luft_verteilen(
    rest: float, luecken: int, grundluft: float, hoechstens: float
) -> float:
    """Verteilt uebrigen Platz auf die Luecken - bis zu einem Mass.

    Ohne Luecke gibt es nichts zu verteilen; dann bleibt der Rest als
    Rand aussen herum, und der Aufrufer setzt das Ganze in die Mitte.
    """
    if rest <= 0 or luecken < 1:
        return grundluft
    return min(grundluft + rest / luecken, hoechstens)


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


def zeilenstile(
    projekt: Projekt, leiste_nr: int, stift_nr: int, seite: str
) -> dict[str, Textstil]:
    """Wie der Text in den Spalten dieser Zeile steht.

    Wie ``zeilenwerte`` eine Stelle fuer beide Wege: Blatt und Mappe
    fragen dasselbe.
    """
    ader = projekt.verteiler.leiste(leiste_nr).stift(stift_nr).ader(seite)
    return {feld: ader.stil(feld) for feld in STILFELDER}


def zellentext(wert: str, teilung: Zellenteilung) -> str:
    """Beide Felder einer Zelle als ein Text.

    Fuer Tabellen: Excel und CSV sind ein Raster, dort gibt es keine
    halbe Spalte. Was auf dem Blatt nebeneinander steht, steht dort
    hintereinander.
    """
    if not teilung.geteilt or not teilung.text:
        return wert
    return f"{wert} {teilung.text}".strip()


def zeilenteilungen(
    projekt: Projekt, leiste_nr: int, stift_nr: int, seite: str
) -> dict[str, Zellenteilung]:
    """Welche Zellen dieser Zeile zwei Beschriftungsfelder tragen."""
    ader = projekt.verteiler.leiste(leiste_nr).stift(stift_nr).ader(seite)
    return {feld: ader.teilung(feld) for feld in TEILBARE_FELDER}


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

    # Die Zeilenstriche enden vor der Kabelspalte: dort steht das Kabel
    # als ein Block, und was frei bleibt, ist eine durchgehende Flaeche -
    # wie in der Verteilerbelegung.
    kabelspalte = next(
        (i for i, spalte in enumerate(vorlage.spalten) if spalte.feld == "kabel"), None
    )
    zeilenbreite = (
        tabellenbreite if kabelspalte is None else sum(breiten[:kabelspalte])
    )

    y = oben + kopf_h
    for stift in leiste.stifte:
        for seite in ("a", "b"):
            werte = zeilenwerte(projekt, leiste_nr, stift.nummer, seite)
            stile = zeilenstile(projekt, leiste_nr, stift.nummer, seite)
            teilungen = zeilenteilungen(projekt, leiste_nr, stift.nummer, seite)
            x = rand
            for spalte, breite in zip(vorlage.spalten, breiten):
                # Der Zellenstil geht vor; wo keiner gesetzt ist, gilt,
                # was die Blattvorlage fuer die Spalte haelt.
                stil = stile.get(spalte.feld, LEERER_STIL)
                lage = stil.ausrichtung or spalte.ausrichtung
                teilung = teilungen.get(spalte.feld, UNGETEILT)
                # Eine geteilte Zelle traegt zwei Felder nebeneinander -
                # ohne Strich dazwischen: auf dem Blatt soll es aussehen
                # wie eine Zelle mit zwei Angaben.
                for text, teil_x, teil_b in _zellenfelder(
                    x + 1.5, breite - 3, werte.get(spalte.feld, ""), teilung
                ):
                    blatt.text(
                        teil_x, y, teil_b, zeile_h, text,
                        vorlage.schrift_normal, lage,
                        stil.fett, TINTE, 0.0, stil.kursiv,
                    )
                x += breite
            # Feine Linie zwischen a und b, kraeftige zwischen den Stiften.
            fein = seite == "a"
            blatt.linie(
                rand, y + zeile_h, rand + zeilenbreite, y + zeile_h,
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

    schriftfeld(blatt, projekt, leiste_nr, vorlage, "leisten")
    return blatt


def _zellenfelder(
    x: float, breite: float, text: str, teilung: Zellenteilung
) -> list[tuple[str, float, float]]:
    """Die Felder einer Zelle: eines, oder zwei nebeneinander.

    Der Anteil gilt dem rechten Feld; zwischen beiden bleibt ein
    Fingerbreit Luft, damit die Texte sich nicht beruehren.
    """
    if not teilung.geteilt:
        return [(text, x, breite)]
    luft = 1.0
    rechts_b = breite * teilung.anteil / 100.0
    links_b = breite - rechts_b - luft
    return [
        (text, x, max(links_b, 1.0)),
        (teilung.text, x + breite - rechts_b, rechts_b),
    ]


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
