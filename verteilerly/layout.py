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
    BLATTARTEN,
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

# Ein Punkt ist 1/72 Zoll hoch; Schriftgroessen stehen in Punkt, das
# Blatt in Millimetern.
PUNKT_IN_MM = 25.4 / 72.0
# Wie weit die Grundlinien eines umgebrochenen Textes auseinanderliegen,
# gemessen an der Schriftgroesse.
ZEILENABSTAND = 1.15
# Womit eine Zeile endet, die auch dann nicht passt.
KUERZUNG = "…"
# So weit darf eine Schrift schrumpfen, damit ein Text in sein Feld
# passt; darunter liest es niemand mehr. Beide Zeichner halten
# sich daran, darum steht die Zahl hier.
KLEINSTE_SCHRIFT = 5.0
SCHRITT = 0.25
# Wo eine Zeile umbrechen darf: nach einem Leerzeichen und nach den
# Zeichen, die in Kabelnamen ohnehin gliedern (K12/3-4, Haus_Nord).
TRENNZEICHEN = " -/\\_·,;"
# Womit ein getrenntes Wort am Zeilenende endet.
TRENNSTRICH = "-"
# So viele Buchstaben bleiben beim Trennen mindestens stehen und werden
# mindestens mitgenommen - ein einzelner Buchstabe sieht nach Versehen aus.
MINDESTENS_VOR = 2
MINDESTENS_NACH = 2
SELBSTLAUTE = "aeiouyäöüáàâéèêíìîóòôúùû"
# Womit eine Silbe beginnen kann. Aus einer Gruppe von Mitlauten wandert
# der laengste dieser Anlaute in die naechste Zeile - der Rest bleibt
# stehen (Wohn-zim-mer, Licht-schacht, Zu-cker).
ANLAUTE = (
    "schl", "schm", "schn", "schr", "schw", "sch",
    "spl", "spr", "str", "pfl", "pfr",
    "bl", "br", "ch", "ck", "dr", "fl", "fr", "gl", "gn", "gr", "kl", "kn",
    "kr", "kw", "ph", "pf", "pl", "pr", "qu", "sk", "sl", "sm", "sn", "sp",
    "st", "sw", "th", "tr", "tw", "zw",
)

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
    #: Darf der Text auf mehrere Zeilen umbrechen und dabei die Schrift
    #: so gross nehmen, wie der Kasten sie traegt? Ohne das bleibt es bei
    #: einer Zeile, die notfalls schrumpft.
    umbruch: bool = False
    #: Bis zu welcher Groesse eine einzelne Zeile dem Umbruch vorgezogen
    #: wird - kleiner gesetzt sieht luftiger aus als zwei volle Zeilen.
    einzeilig_ab: float = 0.0

    @property
    def zeilenlaenge(self) -> float:
        """Wie viel Platz die Zeile hat - quer gedreht ist das die Hoehe."""
        return self.hoehe if self.drehung else self.breite


# -- Wie breit ein Text wird, ohne ihn zu zeichnen --------------------------
#
# Die Zeichenbreiten einer gewoehnlichen Groteske, als Anteil der
# Schriftgroesse (Helvetica-Massen). Damit rechnet das Layoutmodell
# selbst aus, wo ein Feld umbricht - sonst braeche die Vorschau an
# anderen Stellen als das PDF und die Mappe an einer dritten. Wer
# zeichnet, misst danach mit seiner eigenen Schrift nach und
# verkleinert notfalls; groesser wird es nie.


def _breitentabelle() -> dict[str, float]:
    tabelle: dict[str, float] = {}
    for zeichen, breite in (
        (" !,./:;|", 0.278), ("'", 0.191), ("\"", 0.355), ("()[]{}*`", 0.333),
        ("-", 0.333), ("+<=>~", 0.584), ("%", 0.889), ("&", 0.667),
        ("0123456789", 0.556), ("?", 0.556), ("@", 1.015), ("^", 0.469),
        ("ABDEHKNRSUVXY", 0.7), ("CGOQ", 0.76), ("FLTZ", 0.6), ("I", 0.278),
        ("J", 0.5), ("MW", 0.89), ("PR", 0.69),
        ("abcdeghknopqsuvxyzäöü", 0.54), ("fijlt", 0.24), ("mw", 0.78),
        ("r", 0.333), ("ß", 0.556), ("_", 0.556), ("…—", 1.0), ("·", 0.278),
    ):
        for z in zeichen:
            tabelle[z] = breite
    return tabelle


BREITEN = _breitentabelle()
BREITE_VORGABE = 0.556
# Die Schrift der Oberflaeche baut etwas breiter als die des PDF. Mit
# diesem Zuschlag ist das gemeinsame Mass fuer beide auf der sicheren
# Seite - lieber eine Stufe kleiner als ein Feld, das ueberlaeuft.
BREITENZUSCHLAG = 1.08


def geschaetzte_breite(text: str, groesse: float) -> float:
    """Wie breit diese Zeile wird - in der Einheit der Schriftgroesse."""
    anteil = sum(BREITEN.get(z, BREITE_VORGABE) for z in str(text))
    return anteil * groesse * BREITENZUSCHLAG


def umgebrochene_zeilen(
    text: str,
    breite: float,
    hoehe: float,
    groesse: float,
    einzeilig_ab: float = 0.0,
) -> tuple[float, list[str]]:
    """Schriftgroesse in Punkt und die Zeilen eines umbrechenden Feldes.

    Kasten in Millimetern, Schrift in Punkt - so, wie das Zeichenmodell
    beides fuehrt. Gerechnet wird mit dem gemeinsamen Mass, damit
    Vorschau, PDF und Mappe dieselben Zeilen zeigen.
    """
    gross, zeilen = umbruch_einpassen(
        text, breite, hoehe,
        groesse * PUNKT_IN_MM,
        KLEINSTE_SCHRIFT * PUNKT_IN_MM,
        SCHRITT * PUNKT_IN_MM,
        geschaetzte_breite,
        einzeilig_ab * PUNKT_IN_MM,
    )
    # Krumme Zahlen wie 6.749999 helfen niemandem - auch nicht der Mappe.
    return round(gross / PUNKT_IN_MM, 2), zeilen


def textzeilen(element: Text) -> tuple[float, list[str]]:
    """Dasselbe fuer ein fertiges Textfeld des Zeichenmodells."""
    return umgebrochene_zeilen(
        str(element.text), element.breite, element.hoehe, element.groesse,
        element.einzeilig_ab,
    )


def _stuecke(text: str) -> list[str]:
    """Zerlegt den Text an den Stellen, an denen eine Zeile enden darf.

    Jedes Stueck traegt sein Trennzeichen am Ende; aneinandergehaengt
    ergeben sie wieder den Text.
    """
    stuecke: list[str] = []
    laufend = ""
    for zeichen in text:
        laufend += zeichen
        if zeichen in TRENNZEICHEN:
            stuecke.append(laufend)
            laufend = ""
    if laufend:
        stuecke.append(laufend)
    return stuecke


def _laengster_anfang(text: str, laenge: float, misst, anhang: str = "") -> int:
    """Wie viele Zeichen vom Anfang noch in die Zeile passen.

    ``anhang`` ist, was am Zeilenende dazukommt - der Trennstrich zaehlt
    mit, sonst laeuft die getrennte Zeile doch ueber den Rand.
    """
    passend = 0
    for bis in range(1, len(text) + 1):
        if misst(text[:bis].rstrip() + anhang) > laenge:
            break
        passend = bis
    return passend


def _hat_selbstlaut(teil: str) -> bool:
    return any(z in SELBSTLAUTE for z in teil.lower())


def _trennstellen(wort: str) -> list[int]:
    """Alle Stellen, an denen dieses Wort getrennt werden darf.

    Kein Woerterbuch, sondern die Regel, die ohne eines auskommt: zwischen
    zwei Selbstlauten steht eine Gruppe Mitlaute, und von ihr wandert
    genau so viel in die naechste Zeile, wie eine Silbe beginnen kann -
    ein einzelner Mitlaut ganz (Ka-bel), aus einer Gruppe der Anlaut, den
    es im Deutschen gibt (Wohn-zim-mer, Licht-schacht, Melder-kreis).
    In Zahlen wird gar nicht getrennt: "12-\n3" laese sich als etwas
    anderes.
    """
    klein = wort.lower()
    stellen: list[int] = []
    i = 0
    while i < len(wort):
        if klein[i] not in SELBSTLAUTE:
            i += 1
            continue
        # Hinter dem Selbstlaut die Gruppe der Mitlaute abschreiten.
        anfang = i + 1
        while anfang < len(wort) and klein[anfang] in SELBSTLAUTE:
            anfang += 1
        ende = anfang
        while ende < len(wort) and klein[ende].isalpha() and klein[ende] not in SELBSTLAUTE:
            ende += 1
        if ende >= len(wort) or not klein[ende] in SELBSTLAUTE or ende == anfang:
            i = anfang if anfang > i else i + 1
            continue
        gruppe = klein[anfang:ende]
        # Der laengste Anlaut, mit dem die naechste Silbe beginnen darf.
        mitnehmen = 1
        for anlaut in ANLAUTE:
            if len(anlaut) > mitnehmen and gruppe.endswith(anlaut):
                mitnehmen = len(anlaut)
        stelle = ende - min(mitnehmen, len(gruppe))
        if MINDESTENS_VOR <= stelle <= len(wort) - MINDESTENS_NACH:
            stellen.append(stelle)
        i = ende
    return stellen


def _trennstelle(wort: str, hoechstens: int) -> int:
    """Die spaeteste erlaubte Trennstelle bis ``hoechstens`` Zeichen."""
    wort = wort.rstrip()
    for stelle in sorted(_trennstellen(wort), reverse=True):
        if stelle > hoechstens:
            continue
        vorher, nachher = wort[:stelle], wort[stelle:]
        if wort[stelle - 1].isdigit() or wort[stelle].isdigit():
            continue
        if not (_hat_selbstlaut(vorher) and _hat_selbstlaut(nachher)):
            continue
        if not vorher[-1].isalpha() or not nachher[0].isalpha():
            continue
        return stelle
    return 0


def _worttrennung(wort: str, laenge: float, misst) -> tuple[str, int]:
    """Was von diesem Wort auf die Zeile kommt - und wie viel davon weg ist.

    Zurueck kommen die Zeile samt Trennstrich und die Zahl der Zeichen,
    die damit verbraucht sind. Gibt es keine ordentliche Stelle, wird
    ohne Strich abgeschnitten: ein Trennstrich mitten in einer
    Kabelnummer waere schlimmer als keiner.
    """
    mit_strich = _laengster_anfang(wort, laenge, misst, TRENNSTRICH)
    stelle = _trennstelle(wort, mit_strich)
    if stelle:
        return wort[:stelle] + TRENNSTRICH, stelle
    glatt = _laengster_anfang(wort, laenge, misst) or 1
    return wort[:glatt].rstrip(), glatt


def zeilen_umbrechen(text: str, laenge: float, misst) -> list[str]:
    """Bricht einen Text auf Zeilen von hoechstens ``laenge`` um.

    Gemessen wird nicht hier: ``misst(zeile)`` gibt zurueck, wie breit
    eine Zeile wird. So bleibt das Layoutmodell ohne Qt und ohne
    ReportLab, und beide Zeichner brechen dennoch an denselben Stellen
    um. Ein Wort, das allein nicht passt, wird getrennt - mit
    Trennstrich und an einer Stelle, an der man trennen darf.
    """
    zeilen: list[str] = []
    laufend = ""
    for stueck in _stuecke(str(text)):
        if laufend and misst((laufend + stueck).rstrip()) > laenge:
            zeilen.append(laufend.rstrip())
            laufend = stueck.lstrip()
        else:
            laufend += stueck
        while len(laufend.strip()) > 1 and misst(laufend.rstrip()) > laenge:
            zeile, verbraucht = _worttrennung(laufend, laenge, misst)
            if verbraucht >= len(laufend.rstrip()):
                break
            zeilen.append(zeile)
            laufend = laufend[verbraucht:]
    if laufend.strip():
        zeilen.append(laufend.rstrip())
    return zeilen


def _gekuerzt(zeile: str, laenge: float, misst) -> str:
    """Setzt Punkte ans Ende, wenn der Rest nicht mehr aufs Blatt passt."""
    if misst(zeile + KUERZUNG) <= laenge:
        return zeile + KUERZUNG
    kurz = zeile
    while kurz and misst(kurz.rstrip() + KUERZUNG) > laenge:
        kurz = kurz[:-1]
    return (kurz.rstrip() + KUERZUNG) if kurz.strip() else KUERZUNG


def umbruch_einpassen(
    text: str,
    breite: float,
    hoehe: float,
    groesse: float,
    kleinste: float,
    schritt: float,
    misst,
    einzeilig_ab: float = 0.0,
) -> tuple[float, list[str]]:
    """Die groesste Schrift, mit der der Text umgebrochen ins Feld passt.

    ``misst(zeile, groesse)`` gibt die Breite einer Zeile; Kastenmasse,
    Schriftgroesse und dieses Mass stehen in derselben Einheit - das PDF
    rechnet in Punkt, die Vorschau in Bildpunkten. Zurueck kommen die
    gewaehlte Groesse und die fertigen Zeilen. Passt es auch bei der
    kleinsten Schrift nicht, bleibt stehen, was in den Kasten geht, und
    die letzte Zeile endet mit Punkten.

    ``einzeilig_ab`` sagt, bis zu welcher Groesse eine einzelne Zeile
    einem Umbruch vorgezogen wird: eine Stufe kleiner gesetzt sieht
    luftiger aus als zwei Zeilen, die das Feld ausfuellen. Erst darunter
    wird umgebrochen - dann ist das Feld wirklich zu klein.
    """
    text = str(text)
    if not text.strip() or breite <= 0 or hoehe <= 0:
        return groesse, [text]

    einzeln = text.strip()
    einzeilig = max(kleinste, groesse)
    while einzeilig_ab and einzeilig >= einzeilig_ab:
        if (misst(einzeln, einzeilig) <= breite
                and einzeilig * ZEILENABSTAND <= hoehe):
            return einzeilig, [einzeln]
        einzeilig -= schritt

    stuecke = [st.rstrip() for st in _stuecke(text) if st.strip()]

    def versuchen(ganze_woerter: bool) -> tuple[float, list[str]] | None:
        """Die groesste Schrift, mit der es aufgeht - von oben herab."""
        gewaehlt = max(kleinste, groesse)
        while True:
            if ganze_woerter and any(
                misst(st, gewaehlt) > breite for st in stuecke
            ):
                zeilen = None
            else:
                zeilen = zeilen_umbrechen(
                    text, breite, lambda z: misst(z, gewaehlt)
                )
                if len(zeilen) * gewaehlt * ZEILENABSTAND <= hoehe:
                    return gewaehlt, zeilen
            if gewaehlt <= kleinste:
                return None
            gewaehlt = max(kleinste, gewaehlt - schritt)

    # Erst so, dass kein Wort mitten durchgeschnitten wird: eine Stufe
    # kleiner zu setzen ist lesbarer als "Melderkre-is".
    ergebnis = versuchen(True) or versuchen(False)
    if ergebnis:
        return ergebnis
    zeilen = zeilen_umbrechen(text, breite, lambda z: misst(z, kleinste))

    passen = max(1, int(hoehe / (kleinste * ZEILENABSTAND)))
    if len(zeilen) > passen:
        zeilen = zeilen[:passen]
        zeilen[-1] = _gekuerzt(
            zeilen[-1], breite, lambda z: misst(z, kleinste)
        )
    return kleinste, zeilen


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

#: Eine Zeile des Schriftfeldes, die nur ein Querstrich ist. Sie traegt
#: dieses Zeichen als Beschriftung - kein Text eines Anwenders faengt so
#: an, und so bleibt die Zeile eine gewoehnliche (Name, Wert)-Zeile.
STRICH = "\x00strich"

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
    if marke == "strich":
        return [(STRICH, "")]
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
        wert = "" if leiste is None else projekt.leistenname(leiste)
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
        zeile
        for block in vorlage.schriftfeld
        for eintrag in block
        for zeile in _eintraege(eintrag.marke, projekt, traeger, leiste, blattart)
        # Eine Tabelle hat keine Striche - dort zaehlen nur die Angaben.
        if zeile[0] != STRICH
    ]


def schriftfeldspalten(
    projekt: Projekt,
    leiste: int | None = None,
    vorlage: Blattvorlage = STANDARD,
    blattart: str = "leisten",
    blatttitel: str = "",
) -> list[list[tuple[str, str, str]]]:
    """Das Schriftfeld in Bloecken, wie die Blattvorlage es aufteilt.

    Eine Liste je Block, darin die Zeilen aus Beschriftung, Wert und
    Ausrichtung. Gezeichnetes Blatt und Excel-Mappe fragen dieselbe
    Stelle - die Ausrichtung gehoert dem Eintrag, nicht dem Zeichner.
    """
    traeger = Blatt(0, 0, titel=blatttitel)
    return [
        [
            (name, wert, eintrag.ausrichtung)
            for eintrag in block
            for name, wert in schriftfeldzeilen(
                _eintraege(eintrag.marke, projekt, traeger, leiste, blattart)
            )
        ]
        for block in vorlage.schriftfeld
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
            "" if leiste is None else projekt.leistenname(leiste),
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
        for j, (name, wert, ausrichtung) in enumerate(spalte):
            y = oben + j * zeilenhoehe
            if name == STRICH:
                # Von Kante zu Kante: der Strich schliesst mit der
                # Umrandung ab - links und rechts Luft zu lassen sieht aus
                # wie ein vergessener Rest, nicht wie eine Trennung.
                mitte = y + zeilenhoehe / 2
                blatt.linie(
                    x, mitte, x + spaltenbreite, mitte, 0.2, LINIE_FEIN
                )
                continue
            blatt.text(
                x + 2, y, label_b - 2, zeilenhoehe, name,
                vorlage.schrift_klein, LINKS, False, TINTE_LEISE,
            )
            blatt.text(
                x + label_b + 2, y, spaltenbreite - label_b - 4, zeilenhoehe, wert,
                vorlage.schrift_normal, ausrichtung,
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
    """Wie es die Mustertabellen halten: "Verteiler:", aber "Verteiler-Nr."."""
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
    gruppen = belegungsgruppen(projekt, vorlage)
    if len(gruppen) == 1:
        return [verteilerbelegung(projekt, gruppen[0], vorlage=vorlage)]
    return [
        verteilerbelegung(projekt, gruppe, benennen=True, vorlage=vorlage)
        for gruppe in gruppen
    ]


def belegungsgruppen(
    projekt: Projekt, vorlage: Blattvorlage = STANDARD
) -> list[list[Bucht]]:
    """Welche Buchten sich ein Blatt teilen.

    Die Excel-Mappe legt danach ihre Blaetter an: dieselbe Aufteilung wie
    im PDF, damit auf beiden Wegen dasselbe zusammensteht.
    """
    alle = projekt.verteiler.buchten
    je_blatt = max(1, vorlage.buchten_je_blatt)
    lang = any(len(b.leisten) > LEISTEN_JE_BLATT for b in alle)
    if len(alle) > 2 or lang:
        je_blatt = 1
    return [alle[i:i + je_blatt] for i in range(0, len(alle), je_blatt)] or [[]]


def buchtnamen(buchten: list[Bucht]) -> str:
    """Wie das Blatt heisst, das diese Buchten traegt."""
    if not buchten:
        return "Verteilerbelegung"
    erste, letzte = buchten[0].nummer, buchten[-1].nummer
    return f"Bucht {erste}" if erste == letzte else f"Buchten {erste} und {letzte}"


@dataclass(frozen=True)
class Belegungsmasse:
    """Wie gross die Zellen der Verteilerbelegung auf dem Blatt werden.

    Die Masse haengen am Blatt, nicht an der Vorlage allein: ein
    40-DA-Verteiler soll die Seite nicht als Briefmarke in der Ecke
    fuellen. Damit die Excel-Mappe dasselbe Blatt fuellt, rechnet sie
    nicht selbst, sondern fragt hier.
    """

    zelle_breite: float
    zelle_hoehe: float
    label_breite: float
    luft_leisten: float
    luft_buchten: float
    schrift: float
    hochkant: bool
    platz_breite: float
    platz_hoehe: float


def belegungsmasse(
    buchten: list[Bucht], vorlage: Blattvorlage = STANDARD
) -> Belegungsmasse:
    """Zellenmass und Luft fuer diese Buchten auf einem Blatt."""
    rand = vorlage.rand
    hochkant = len(buchten) <= 1
    blatt_b, blatt_h = A4_HOCH if hochkant else A4_QUER
    oben = rand + 12
    platz_b = blatt_b - 2 * rand
    platz_h = blatt_h - rand - vorlage.schriftfeld_hoehe - 6 - oben

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
    return Belegungsmasse(
        zelle_breite=zelle_b, zelle_hoehe=zelle_h, label_breite=label_b,
        luft_leisten=luft_l, luft_buchten=luft_r, schrift=schrift,
        hochkant=hochkant, platz_breite=platz_b, platz_hoehe=platz_h,
    )


def kabelbeschriftung_groesse(
    platz_hoehe: float, vorlage: Blattvorlage = STANDARD
) -> float:
    """Wie gross der Kabelname hoechstens werden darf.

    ``platz_hoehe`` ist die Hoehe, die ihm im Block bleibt; eine Zeile
    darin braucht ``ZEILENABSTAND`` mal ihre Schriftgroesse. Mehr als die
    mittlere Schrift der Vorlage wird es nicht - ein Kabelname ist keine
    Ueberschrift.
    """
    hoechstens = max(platz_hoehe, 0.5) / PUNKT_IN_MM / ZEILENABSTAND
    return max(min(vorlage.schrift_mittel, hoechstens), vorlage.schrift_klein)


@dataclass(frozen=True)
class Kabelfeld:
    """Wo der Kabelname im Block steht und wie gross er dort wird.

    Der Platz ist kleiner als der Block: erst der Fuellgrad, dann das
    Mindestpolster - was beide zulassen, bleibt uebrig. Blatt und Mappe
    fragen dieselbe Stelle, damit beide dasselbe zeigen.
    """

    x: float
    y: float
    breite: float
    hoehe: float
    groesse: float
    #: Bis hierher ist eine einzelne Zeile besser als ein Umbruch.
    einzeilig_ab: float


def kabelfeld(
    x: float,
    y: float,
    breite: float,
    hoehe: float,
    vorlage: Blattvorlage = STANDARD,
) -> Kabelfeld:
    """Das Textfeld des Kabelnamens in einem Block dieser Groesse."""
    grad, polster = vorlage.fuellgrad_kabel, vorlage.polster_kabel
    platz_b = max(min(breite * grad, breite - 2 * polster), 1.0)
    platz_h = max(min(hoehe * grad, hoehe - 2 * polster), 1.0)
    return Kabelfeld(
        x=x + (breite - platz_b) / 2,
        y=y + (hoehe - platz_h) / 2,
        breite=platz_b,
        hoehe=platz_h,
        groesse=kabelbeschriftung_groesse(platz_h, vorlage),
        einzeilig_ab=vorlage.schrift_klein,
    )


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
    masse = belegungsmasse(buchten, vorlage)
    platz_b, platz_h = masse.platz_breite, masse.platz_hoehe
    zelle_h, zelle_b = masse.zelle_hoehe, masse.zelle_breite
    label_b = masse.label_breite
    luft_l, luft_r = masse.luft_leisten, masse.luft_buchten
    schrift = masse.schrift
    breiten = [
        label_b + max((l.da_anzahl for l in b.leisten), default=0) * zelle_b
        for b in buchten
    ]
    zeilen = max((len(b.leisten) for b in buchten), default=0)

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
            kx - label_b, ky, label_b - 2, zelle_h,
            f"Leiste {projekt.leistenname(nummer)}", schrift, LINKS,
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
            # Mitten in den Block, so gross wie er es traegt, notfalls
            # auf mehrere Zeilen: der Kabelname ist die Auskunft dieses
            # Blattes, nicht eine Fussnote in seiner linken oberen Ecke.
            feld = kabelfeld(bx, ky, bb, zelle_h, vorlage)
            blatt.text(
                feld.x, feld.y, feld.breite, feld.hoehe,
                beschriftung, feld.groesse, MITTE, umbruch=True,
                einzeilig_ab=feld.einzeilig_ab,
            )

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
            _adresse(leiste_nr, stift_nr, seite), projekt.schreibweise,
            projekt.leisten_schreibweise,
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
    blatt = Blatt(*A4_HOCH, titel=f"Leiste {projekt.leistenname(leiste_nr)}")
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


def zeilenhoehe_leiste(
    da_anzahl: int, vorlage: Blattvorlage = STANDARD, blatthoehe: float = A4_HOCH[1]
) -> float:
    """Wie hoch eine Zeile des Leistenblatts wird.

    Die Tabelle nutzt das Blatt aus - 20 DA sind 40 Zeilen und passen
    auch. Die Excel-Mappe fragt dieselbe Stelle, sonst stuende dort eine
    halbleere Seite.
    """
    platz = (
        blatthoehe - vorlage.rand - vorlage.schriftfeld_hoehe - 6
        - (vorlage.rand + vorlage.kopfzeile_hoehe)
    )
    return max(
        vorlage.zeilenhoehe_min,
        min(vorlage.zeilenhoehe_max, platz / max(da_anzahl * 2, 1)),
    )


def _zeilenhoehe(
    blatt: Blatt, oben: float, da_anzahl: int, vorlage: Blattvorlage
) -> float:
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


def blaetter(
    projekt: Projekt,
    vorlage: Blattvorlage = STANDARD,
    blattarten=BLATTARTEN,
) -> list[Blatt]:
    """Deckblatt, Verteilerbelegung, je Leiste ein Blatt - soweit gewaehlt.

    Gezaehlt wird, was herauskommt: ohne Deckblatt beginnt die
    Verteilerbelegung bei Blatt 1.
    """
    folge: list[Blatt] = []
    if "deckblatt" in blattarten:
        folge.append(deckblatt(projekt, vorlage))
    if "belegung" in blattarten:
        folge += verteilerbelegungen(projekt, vorlage)
    if "leisten" in blattarten:
        for leiste in projekt.verteiler.alle_leisten:
            folge.append(leistenblatt(projekt, leiste.nummer, vorlage))
    for i, blatt in enumerate(folge, 1):
        _fusszeile(blatt, i, len(folge), vorlage)
    return folge
