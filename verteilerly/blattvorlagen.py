"""Blattvorlagen: wie die Ausgabe aussieht.

Eine Blattvorlage beschreibt das Blatt, nicht seinen Inhalt: Raender,
Schriftgroessen, welche Spalten das Leistenblatt traegt und was im
Schriftfeld steht. Sie liegt als YAML neben dem Programm und ist damit
ohne Programmaenderung erweiterbar - wie die Verteilervorlagen und die
Kabeltypen.

Die Vorgaben dieser Klasse sind genau das Blatt, das die Beispiel-
verteiler zeigen; eine Datei muss also nur angeben, was sie anders will.
"""

from __future__ import annotations

import copy
import pathlib
from dataclasses import dataclass, field, replace

import yaml

from .modell import (
    BLATTARTEN,
    LINKS,
    MITTE,
    RECHTS,
    ModellFehler,
    unbekannte_schluessel,
)
from .sprachen import u

__all_ausrichtungen__ = (LINKS, MITTE, RECHTS)
AUSRICHTUNGEN = (LINKS, MITTE, RECHTS)

# Wie das Schriftfeld aufgebaut ist. "standard" reiht Beschriftung und
# Wert in Spalten; "beispiel" baut das Feld der Mustertabellen nach - eine
# Matrix aus Datum und Name, darunter der Verteiler, rechts daneben die
# Anschriften von Firma und Kunde.
SCHRIFTFELDARTEN = ("standard", "beispiel")

# Welche Schluessel eine Blattvorlage kennt. Was hier nicht steht, wird
# gemeldet: ein vertippter Schluessel faellt sonst nirgends auf.
BLATTSCHLUESSEL = (
    "id", "name", "beschreibung", "standard",
    "rand", "schriftfeld_hoehe", "kopfzeile_hoehe",
    "zeilenhoehe_max", "zeilenhoehe_min",
    "schrift", "spalten", "schriftfeld", "schriftfeld_art",
    "schriftfeld_anteile", "eigene_felder", "eigene_felder_auf",
    "buchten_je_blatt", "da_nummern",
    "kabel_gedreht", "zeilen_kabel", "belegung",
)
SCHRIFTSCHLUESSEL = ("gross", "mittel", "normal", "klein")
BELEGUNGSSCHLUESSEL = (
    "zelle_breite", "zelle_hoehe", "leistenlabel",
    "abstand_leisten", "abstand_buchten",
    "fuellgrad_kabel", "polster_kabel",
)
SPALTENSCHLUESSEL = ("feld", "ueberschrift", "anteil", "ausrichtung")
SCHRIFTFELDSCHLUESSEL = ("marke", "ausrichtung")

# Was eine Spalte des Leistenblattes zeigen kann.
SPALTENFELDER = (
    "stift",
    "ader",
    "farbe",
    "bezeichnung",
    "rangierung",
    "bemerkung",
    "kabel",
)

@dataclass(frozen=True)
class Abgelegt:
    """Eine Angabe, die es in der Blattvorlage einmal gab.

    Hier steht alles an einer Stelle, was eine alte Datei noch tragen
    kann: wie die Angabe hiess, wo sie stand, seit wann es sie nicht
    mehr gibt und was an ihre Stelle tritt. Daraus speisen sich die
    Meldung beim Lesen **und** das Auffrischen der Datei
    (``blattvorlage_auffrischen``) - sonst sagte das eine, was das
    andere nicht taete.
    """

    name: str
    #: Wo sie stand: "schriftfeld" oder der Block, etwa "belegung".
    wo: str
    #: Die Fassung, mit der sie wegfiel.
    seit: str
    #: Was heute an ihrer Stelle steht - ein Satzteil fuer die Meldung.
    ersatz: str
    #: Wo sie stand, als Satzteil - die Meldung ist fuer Menschen.
    stelle: str


# Was im Schriftfeld stehen kann - dazu die **Namen der eigenen Felder**
# dieser Vorlage: jedes steht einzeln im Block, in dem es gebraucht wird.
#: Die alte Marke fuer *alle* eigenen Felder. Es gibt sie nicht mehr;
#: beim Lesen wird sie uebergangen, damit eine alte Datei weiter laeuft.
SAMMELMARKE = "eigene"
ABGELEGT = (
    Abgelegt(
        name=SAMMELMARKE,
        wo="schriftfeld",
        seit="2026.09.30",
        ersatz="die Namen der eigenen Felder, jeder in seinem Block",
        stelle="im Schriftfeld",
    ),
    Abgelegt(
        name="zeilen_kabel",
        wo="belegung",
        seit="2026.10.04b7",
        ersatz="zeilen_kabel auf der Blattebene, neben kabel_gedreht",
        stelle="im Block „belegung“",
    ),
)
SCHRIFTFELDMARKEN = (
    "firma",
    "kunde",
    "anlagennummer",
    "kundennummer",
    "verteiler",
    "verteilernummer",
    "leiste",
    "blatt",
    "erstellt",
    "stand",
    "geprueft",
    "gezeichnet",
    "dokumenttitel",
    # Keine Angabe, sondern ein Strich quer durch den Block - er trennt,
    # was darueber steht, von dem darunter.
    "strich",
)


class BlattvorlagenFehler(ModellFehler):
    """Eine Blattvorlage ist unbrauchbar."""


@dataclass(frozen=True)
class Spalte:
    """Eine Spalte des Leistenblattes.

    Die Breite ist ein Anteil, keine Millimeterzahl: die Spalten werden
    auf die Blattbreite gestreckt. So bleibt eine Vorlage brauchbar, auch
    wenn jemand den Rand aendert.
    """

    feld: str
    ueberschrift: str = ""
    anteil: float = 1.0
    ausrichtung: str = LINKS


@dataclass(frozen=True)
class Schriftfeldeintrag:
    """Eine Zeile des Schriftfeldes: was dort steht und wie es liegt.

    Die Ausrichtung gilt dem Wert, nicht der Beschriftung - die steht am
    linken Rand ihres Blockes und haelt die Zeilen untereinander.
    """

    marke: str
    ausrichtung: str = LINKS


def _als_eintrag(marke) -> Schriftfeldeintrag:
    """Aus einer Marke ein Eintrag - ein Eintrag bleibt, was er ist."""
    if isinstance(marke, Schriftfeldeintrag):
        return marke
    return Schriftfeldeintrag(str(marke))


STANDARDSPALTEN = (
    Spalte("stift", "Stift", 10.0, MITTE),
    Spalte("ader", "", 7.0, MITTE),
    Spalte("farbe", "Farbe", 16.0),
    Spalte("bezeichnung", "Bezeichnung", 46.0),
    Spalte("rangierung", "Rangierung", 30.0),
    Spalte("bemerkung", "Bemerkung", 44.0),
    Spalte("kabel", "Kabel", 12.0),
)

STANDARDSCHRIFTFELD = tuple(
    tuple(Schriftfeldeintrag(marke) for marke in block)
    for block in (
        ("firma", "kunde", "anlagennummer", "kundennummer"),
        ("verteiler", "verteilernummer", "leiste", "blatt"),
        ("erstellt", "stand", "geprueft", "gezeichnet"),
    )
)


@dataclass(frozen=True)
class Blattvorlage:
    """Alles, was das Aussehen eines Blattes ausmacht."""

    id: str = "standard"
    name: str = "Standard"
    beschreibung: str = ""
    standard: bool = False

    rand: float = 12.0
    schriftfeld_hoehe: float = 26.0
    kopfzeile_hoehe: float = 7.0
    zeilenhoehe_max: float = 9.5
    zeilenhoehe_min: float = 4.2

    schrift_gross: float = 20.0
    schrift_mittel: float = 11.0
    schrift_normal: float = 8.5
    schrift_klein: float = 7.0

    spalten: tuple[Spalte, ...] = STANDARDSPALTEN
    # Die Bloecke des Schriftfeldes. Eine blosse Marke darf dabeistehen,
    # __post_init__ macht einen Eintrag daraus.
    schriftfeld: tuple[tuple[Schriftfeldeintrag, ...], ...] = STANDARDSCHRIFTFELD
    schriftfeld_art: str = "standard"
    # Wie breit die Bloecke des Schriftfeldes sind. Leer heisst: nach
    # Augenmass verteilt, Namen brauchen mehr Platz als Nummern.
    schriftfeld_anteile: tuple[float, ...] = ()

    # Die eigenen Felder des Schriftfeldes: **nur die Namen**, in dieser
    # Reihenfolge. Die Inhalte gehoeren dem Projekt (Bearbeiten ▸
    # Projektdaten) - die Vorlage sagt, welche Zeilen es gibt, nicht was
    # darin steht. Hinter der Marke „eigene" stehen genau diese.
    eigene_felder: tuple[str, ...] = ()
    # Auf welchen Blattarten sie erscheinen. Leer heisst: auf keiner.
    eigene_felder_auf: tuple[str, ...] = BLATTARTEN

    buchten_je_blatt: int = 2
    da_nummern: bool = False
    # Die Kabelspalte ist schmal; quer gelesen passt der Name trotzdem
    # hinein, statt auf Winzigkeit zu schrumpfen.
    kabel_gedreht: bool = True
    # Auf wie viele Zeilen der Kabelname in der schmalen Kabelspalte des
    # Leistenblatts hoechstens umbricht. Der Block der Verteilerbelegung
    # ist breit und zaehlt nicht mit - dort nimmt der Name so viele
    # Zeilen, wie er traegt.
    zeilen_kabel: int = 2
    zelle_breite: float = 6.0
    zelle_hoehe: float = 9.0
    leistenlabel: float = 14.0
    abstand_leisten: float = 3.0
    abstand_buchten: float = 12.0
    # Wie viel seines Kabelblocks der Name hoechstens einnimmt und wie
    # viel Luft am Rahmen mindestens bleibt: ein Name von Rand zu Rand
    # liesse den Block vollgestopft aussehen.
    fuellgrad_kabel: float = 0.82
    polster_kabel: float = 0.6

    def __post_init__(self) -> None:
        # Eine blosse Marke darf fuer sich stehen: ein von Hand gebautes
        # Schriftfeld bleibt so lesbar. Was das Programm weiterreicht,
        # ist danach immer ein Schriftfeldeintrag.
        object.__setattr__(self, "schriftfeld", tuple(
            tuple(_als_eintrag(eintrag) for eintrag in block)
            for block in self.schriftfeld
        ))

    def __str__(self) -> str:
        return self.name

    def spalte(self, feld: str) -> Spalte | None:
        for spalte in self.spalten:
            if spalte.feld == feld:
                return spalte
        return None

    def breiten(self, platz: float) -> list[float]:
        """Die Spaltenbreiten in Millimetern, auf den Platz gestreckt."""
        summe = sum(s.anteil for s in self.spalten) or 1.0
        return [platz * s.anteil / summe for s in self.spalten]

    def mit(self, **aenderungen) -> Blattvorlage:
        return replace(self, **aenderungen)


STANDARD = Blattvorlage(standard=True)


# -- Aus YAML --------------------------------------------------------------


def _zahl(inhalt: dict, name: str, vorgabe: float, herkunft: str) -> float:
    if name not in inhalt:
        return vorgabe
    try:
        return float(inhalt[name])
    except (TypeError, ValueError):
        raise BlattvorlagenFehler(u("{0}: {1} ist keine Zahl").format(herkunft, name)) from None


def _spalten_aus_yaml(eintraege, herkunft: str, hinweise=None) -> tuple[Spalte, ...]:
    spalten = []
    for eintrag in eintraege:
        if isinstance(eintrag, str):
            eintrag = {"feld": eintrag}
        else:
            unbekannte_schluessel(
                eintrag, SPALTENSCHLUESSEL, herkunft, hinweise, "spalten"
            )
        feld = str(eintrag.get("feld", "")).strip()
        if feld not in SPALTENFELDER:
            bekannt = ", ".join(SPALTENFELDER)
            raise BlattvorlagenFehler(
                u("{0}: Spalte {1!r} gibt es nicht (bekannt: {2})").format(herkunft, feld, bekannt)
            )
        ausrichtung = str(eintrag.get("ausrichtung", LINKS))
        if ausrichtung not in AUSRICHTUNGEN:
            raise BlattvorlagenFehler(
                u("{0}: Ausrichtung {1!r} gibt es nicht").format(herkunft, ausrichtung)
            )
        vorgabe = STANDARD.spalte(feld)
        spalten.append(
            Spalte(
                feld=feld,
                ueberschrift=str(
                    eintrag.get("ueberschrift", vorgabe.ueberschrift if vorgabe else "")
                ),
                anteil=float(eintrag.get("anteil", vorgabe.anteil if vorgabe else 1.0)),
                ausrichtung=ausrichtung,
            )
        )
    if not spalten:
        raise BlattvorlagenFehler(u("{0}: kein einziges Feld im Leistenblatt").format(herkunft))
    return tuple(spalten)


def _schriftfeld_aus_yaml(
    eintraege,
    herkunft: str,
    hinweise=None,
    eigene_felder: tuple[str, ...] = (),
) -> tuple[tuple[Schriftfeldeintrag, ...], ...]:
    """Die Bloecke des Schriftfeldes.

    Kurzform ist die blosse Marke, lang geht es mit eigener Ausrichtung -
    wie bei den Spalten des Leistenblattes. **Ein eigenes Feld steht mit
    seinem Namen da** (``- Auftrag``) und gehoert damit in genau einen
    Block; ``eigene_felder`` sagt, welche Namen es gibt.
    """
    spalten = []
    for spalte in eintraege:
        marken = []
        for eintrag in spalte:
            if not isinstance(eintrag, dict):
                eintrag = {"marke": eintrag}
            else:
                unbekannte_schluessel(
                    eintrag, SCHRIFTFELDSCHLUESSEL, herkunft, hinweise, "schriftfeld"
                )
            marke = str(eintrag.get("marke", "")).strip()
            if marke == SAMMELMARKE:
                # Bis 2026.09.30 stand hier eine Marke fuer *alle* eigenen
                # Felder. Seither steht jedes einzeln - eine alte Datei
                # soll daran nicht scheitern, sondern es erfahren.
                if hinweise is not None:
                    hinweise.append(hinweis_abgelegt(herkunft, ABGELEGT[0]))
                continue
            if marke not in SCHRIFTFELDMARKEN and marke not in eigene_felder:
                bekannt = ", ".join((*SCHRIFTFELDMARKEN, *eigene_felder))
                raise BlattvorlagenFehler(
                    u("{0}: {1!r} gehört nicht ins Schriftfeld (bekannt: {2})").format(herkunft, marke, bekannt)
                )
            ausrichtung = str(eintrag.get("ausrichtung", LINKS))
            if ausrichtung not in AUSRICHTUNGEN:
                raise BlattvorlagenFehler(
                    u("{0}: Ausrichtung {1!r} gibt es nicht").format(herkunft, ausrichtung)
                )
            marken.append(Schriftfeldeintrag(marke, ausrichtung))
        # Ein Block, in dem nur die alte Sammelmarke stand, bleibt leer -
        # weglassen waere schlimmer: die Breiten der Bloecke verschoben
        # sich, und das Blatt saehe anders aus als gemeint.
        spalten.append(tuple(marken))
    if not spalten:
        raise BlattvorlagenFehler(u("{0}: leeres Schriftfeld").format(herkunft))
    return tuple(spalten)


def blattvorlage_aus_yaml(
    inhalt: dict, herkunft: str = "", hinweise=None
) -> Blattvorlage:
    """Liest eine Blattvorlage; alles Weggelassene bleibt beim Standard.

    ``hinweise`` nimmt auf, was zwar gelesen wurde, aber Fragen aufwirft -
    Schluessel, die das Programm nicht kennt.
    """
    wo = herkunft or "Blattvorlage"
    for feld in ("id", "name"):
        if not str(inhalt.get(feld, "")).strip():
            raise BlattvorlagenFehler(u("{0}: Blattvorlage ohne {1}").format(wo, feld))

    schrift = inhalt.get("schrift") or {}
    belegung = inhalt.get("belegung") or {}
    unbekannte_schluessel(inhalt, BLATTSCHLUESSEL, wo, hinweise)
    unbekannte_schluessel(schrift, SCHRIFTSCHLUESSEL, wo, hinweise, "schrift")
    # Was abgelegt ist, kennt das Programm - es ist kein Tippfehler und
    # wird darum auch nicht als einer gemeldet.
    abgelegte_melden(belegung, "belegung", wo, hinweise)
    unbekannte_schluessel(
        belegung, (*BELEGUNGSSCHLUESSEL, *abgelegte_namen("belegung")),
        wo, hinweise, "belegung",
    )

    # Die eigenen Felder zuerst: ihre Namen sind gueltige Marken des
    # Schriftfeldes, also muessen sie vor ihm bekannt sein.
    eigene = _eigene_aus_yaml(inhalt.get("eigene_felder"), wo, hinweise)
    vorlage = Blattvorlage(
        id=str(inhalt["id"]),
        name=str(inhalt["name"]),
        beschreibung=str(inhalt.get("beschreibung", "")),
        standard=bool(inhalt.get("standard", False)),
        rand=_zahl(inhalt, "rand", STANDARD.rand, wo),
        schriftfeld_hoehe=_zahl(
            inhalt, "schriftfeld_hoehe", STANDARD.schriftfeld_hoehe, wo
        ),
        kopfzeile_hoehe=_zahl(inhalt, "kopfzeile_hoehe", STANDARD.kopfzeile_hoehe, wo),
        zeilenhoehe_max=_zahl(inhalt, "zeilenhoehe_max", STANDARD.zeilenhoehe_max, wo),
        zeilenhoehe_min=_zahl(inhalt, "zeilenhoehe_min", STANDARD.zeilenhoehe_min, wo),
        schrift_gross=_zahl(schrift, "gross", STANDARD.schrift_gross, wo),
        schrift_mittel=_zahl(schrift, "mittel", STANDARD.schrift_mittel, wo),
        schrift_normal=_zahl(schrift, "normal", STANDARD.schrift_normal, wo),
        schrift_klein=_zahl(schrift, "klein", STANDARD.schrift_klein, wo),
        spalten=(
            _spalten_aus_yaml(inhalt["spalten"], wo, hinweise)
            if inhalt.get("spalten")
            else STANDARD.spalten
        ),
        schriftfeld=(
            _schriftfeld_aus_yaml(
                inhalt["schriftfeld"], wo, hinweise, eigene
            )
            if inhalt.get("schriftfeld")
            else STANDARD.schriftfeld
        ),
        eigene_felder=eigene,
        eigene_felder_auf=_blattarten_aus_yaml(
            inhalt.get("eigene_felder_auf"), wo, hinweise
        ),
        schriftfeld_anteile=tuple(
            float(teil) for teil in inhalt.get("schriftfeld_anteile") or ()
        ),
        schriftfeld_art=str(
            inhalt.get("schriftfeld_art", STANDARD.schriftfeld_art)
        ),
        buchten_je_blatt=int(
            _zahl(inhalt, "buchten_je_blatt", STANDARD.buchten_je_blatt, wo)
        ),
        da_nummern=bool(inhalt.get("da_nummern", STANDARD.da_nummern)),
        kabel_gedreht=bool(inhalt.get("kabel_gedreht", STANDARD.kabel_gedreht)),
        zeilen_kabel=int(
            _zahl(inhalt, "zeilen_kabel", STANDARD.zeilen_kabel, wo)
        ),
        zelle_breite=_zahl(belegung, "zelle_breite", STANDARD.zelle_breite, wo),
        zelle_hoehe=_zahl(belegung, "zelle_hoehe", STANDARD.zelle_hoehe, wo),
        leistenlabel=_zahl(belegung, "leistenlabel", STANDARD.leistenlabel, wo),
        abstand_leisten=_zahl(
            belegung, "abstand_leisten", STANDARD.abstand_leisten, wo
        ),
        abstand_buchten=_zahl(
            belegung, "abstand_buchten", STANDARD.abstand_buchten, wo
        ),
        fuellgrad_kabel=_zahl(
            belegung, "fuellgrad_kabel", STANDARD.fuellgrad_kabel, wo
        ),
        polster_kabel=_zahl(belegung, "polster_kabel", STANDARD.polster_kabel, wo),
    )
    if vorlage.schriftfeld_art not in SCHRIFTFELDARTEN:
        bekannt = ", ".join(SCHRIFTFELDARTEN)
        raise BlattvorlagenFehler(
            u("{0}: schriftfeld_art {1!r} gibt es nicht (bekannt: {2})").format(wo, vorlage.schriftfeld_art, bekannt)
        )
    if vorlage.buchten_je_blatt < 1:
        raise BlattvorlagenFehler(u("{0}: buchten_je_blatt muss mindestens 1 sein").format(wo))
    if vorlage.rand < 0 or vorlage.zeilenhoehe_min <= 0:
        raise BlattvorlagenFehler(u("{0}: Rand und Zeilenhöhe müssen positiv sein").format(wo))
    if not 0.1 <= vorlage.fuellgrad_kabel <= 1.0:
        raise BlattvorlagenFehler(
            u("{0}: fuellgrad_kabel liegt zwischen 0,1 und 1").format(wo)
        )
    if vorlage.polster_kabel < 0:
        raise BlattvorlagenFehler(u("{0}: polster_kabel darf nicht negativ sein").format(wo))
    if vorlage.zeilen_kabel < 1:
        raise BlattvorlagenFehler(
            u("{0}: zeilen_kabel muss mindestens 1 sein").format(wo)
        )
    return vorlage


# -- Als YAML --------------------------------------------------------------


def _zahlwert(wert):
    """12.0 als 12 - so, wie es ein Mensch in die Datei schriebe."""
    if isinstance(wert, float) and wert.is_integer():
        return int(wert)
    return wert


def _abweichung(ziel: dict, schluessel: str, wert, vorgabe) -> None:
    if wert != vorgabe:
        ziel[schluessel] = _zahlwert(wert)


def abgelegte_namen(wo: str) -> tuple[str, ...]:
    """Die Namen, die es an dieser Stelle einmal gab."""
    return tuple(a.name for a in ABGELEGT if a.wo == wo)


def abgelegte_melden(
    inhalt, wo: str, herkunft: str, hinweise: list[str] | None
) -> None:
    """Sagt zu jeder abgelegten Angabe, die noch dasteht, was mit ihr ist.

    Ohne das meldete sie sich als unbekannter Schluessel - also als
    moeglicher Tippfehler, obwohl das Programm sie genau kennt.
    """
    if hinweise is None or not isinstance(inhalt, dict):
        return
    for abgelegt in ABGELEGT:
        if abgelegt.wo == wo and abgelegt.name in inhalt:
            hinweise.append(hinweis_abgelegt(herkunft, abgelegt))


def hinweis_abgelegt(herkunft: str, abgelegt: Abgelegt) -> str:
    """Der Satz, der eine abgelegte Angabe erklaert.

    Er sagt dreierlei, weil der Anwender dreierlei wissen muss: was in
    seiner Datei steht, was das Programm damit gemacht hat und was
    heute an diese Stelle gehoert.
    """
    return u(
        "{0}: Die Angabe „{1}“ {2} gibt es seit Fassung {3} nicht mehr; "
        "sie wurde beim Lesen übergangen. An ihrer Stelle steht heute {4}. "
        "Auffrischen lässt sich die Datei unter Tools ▸ Blattvorlage prüfen…"
    ).format(
        herkunft, abgelegt.name, u(abgelegt.stelle), abgelegt.seit,
        u(abgelegt.ersatz),
    )


def blattvorlage_auffrischen(inhalt: dict) -> tuple[dict, list[str]]:
    """Macht aus einer alten Datei eine heutige - ohne sie zu deuten.

    Zurueck kommen der aufgefrischte Inhalt und was dabei geschah; eine
    leere Liste heisst: es war nichts aufzufrischen. Geaendert wird nur,
    was in ``ABGELEGT`` steht - ein unbekannter Schluessel bleibt stehen,
    denn er kann ein Tippfehler sein, und den soll niemand automatisch
    "berichtigt" bekommen.
    """
    neu = copy.deepcopy(inhalt)
    getan: list[str] = []

    # Die Sammelmarke: sie stand fuer *alle* eigenen Felder dieses Blocks.
    # Genau die traegt das Programm jetzt einzeln ein - der Block sieht
    # danach aus wie vorher, nur ausgeschrieben.
    eigene = [str(n).strip() for n in (neu.get("eigene_felder") or []) if str(n).strip()]
    bloecke = neu.get("schriftfeld")
    if isinstance(bloecke, list):
        for block in bloecke:
            if not isinstance(block, list):
                continue
            stelle = 0
            while stelle < len(block):
                eintrag = block[stelle]
                marke = (
                    eintrag.get("marke") if isinstance(eintrag, dict) else eintrag
                )
                if str(marke).strip() != SAMMELMARKE:
                    stelle += 1
                    continue
                block[stelle:stelle + 1] = list(eigene)
                stelle += len(eigene)
                getan.append(
                    u("„{0}“ im Schriftfeld durch {1} ersetzt").format(
                        SAMMELMARKE,
                        ", ".join(eigene) if eigene
                        else u("nichts — die Vorlage führt keine eigenen Felder"),
                    )
                )

    # zeilen_kabel stand kurz im Block "belegung" und gehoert aufs Blatt.
    belegung = neu.get("belegung")
    if isinstance(belegung, dict) and "zeilen_kabel" in belegung:
        wert = belegung.pop("zeilen_kabel")
        neu.setdefault("zeilen_kabel", wert)
        if not belegung:
            neu.pop("belegung")
        getan.append(
            u("zeilen_kabel aus dem Block „belegung“ auf die Blattebene geholt")
        )
    return neu, getan


def _eigene_aus_yaml(inhalt, wo: str, hinweise: list[str] | None) -> tuple[str, ...]:
    """Die Namen der eigenen Felder - eine Liste von Woertern.

    Leere Namen und Doppelte fallen weg: eine Zeile ohne Beschriftung
    waere keine, und zweimal derselbe Name liesse nicht erkennen, welcher
    Wert wohin gehoert.
    """
    if not inhalt:
        return ()
    if isinstance(inhalt, str) or not isinstance(inhalt, (list, tuple)):
        raise ModellFehler(
            u("{0}: eigene_felder ist eine Liste von Feldnamen").format(wo)
        )
    namen: list[str] = []
    for eintrag in inhalt:
        name = str(eintrag).strip()
        if not name:
            continue
        if name in namen:
            if hinweise is not None:
                hinweise.append(
                    u("{0}: das eigene Feld {1} steht zweimal - einmal genügt")
                    .format(wo, name)
                )
            continue
        namen.append(name)
    return tuple(namen)


def _blattarten_aus_yaml(
    inhalt, wo: str, hinweise: list[str] | None
) -> tuple[str, ...]:
    """Auf welchen Blattarten die eigenen Felder stehen.

    Fehlt die Angabe, stehen sie auf allen - so war es, bevor die Wahl in
    die Blattvorlage kam. Eine leere Liste heisst dagegen ausdruecklich:
    auf keiner.
    """
    if inhalt is None:
        return STANDARD.eigene_felder_auf
    if isinstance(inhalt, str) or not isinstance(inhalt, (list, tuple)):
        raise ModellFehler(
            u("{0}: eigene_felder_auf ist eine Liste von Blattarten").format(wo)
        )
    arten: list[str] = []
    for eintrag in inhalt:
        art = str(eintrag).strip()
        if art not in BLATTARTEN:
            if hinweise is not None:
                hinweise.append(
                    u("{0}: {1} ist keine Blattart - bekannt sind {2}").format(
                        wo, art, ", ".join(BLATTARTEN)
                    )
                )
            continue
        if art not in arten:
            arten.append(art)
    return tuple(arten)


def blattvorlage_als_yaml(vorlage: Blattvorlage) -> dict:
    """Die Vorlage als Inhalt einer Datei - nur, was vom Standard abweicht.

    Die Umkehrung von ``blattvorlage_aus_yaml``: eine Datei sagt, was sie
    anders will als die eingebaute Vorgabe, und bleibt so von Hand lesbar.
    """
    inhalt: dict = {"id": vorlage.id, "name": vorlage.name}
    if vorlage.beschreibung:
        inhalt["beschreibung"] = vorlage.beschreibung
    if vorlage.standard:
        inhalt["standard"] = True
    for feld in ("rand", "schriftfeld_hoehe", "kopfzeile_hoehe",
                 "zeilenhoehe_max", "zeilenhoehe_min"):
        _abweichung(inhalt, feld, getattr(vorlage, feld), getattr(STANDARD, feld))
    schrift: dict = {}
    for groesse in SCHRIFTSCHLUESSEL:
        _abweichung(schrift, groesse, getattr(vorlage, f"schrift_{groesse}"),
                    getattr(STANDARD, f"schrift_{groesse}"))
    if schrift:
        inhalt["schrift"] = schrift
    if vorlage.spalten != STANDARD.spalten:
        inhalt["spalten"] = [
            {"feld": s.feld, "ueberschrift": s.ueberschrift,
             "anteil": _zahlwert(s.anteil), "ausrichtung": s.ausrichtung}
            for s in vorlage.spalten
        ]
    if vorlage.schriftfeld != STANDARD.schriftfeld:
        # Kurzform, wo nichts abweicht: eine Marke fuer sich allein.
        inhalt["schriftfeld"] = [
            [
                eintrag.marke if eintrag.ausrichtung == LINKS
                else {"marke": eintrag.marke, "ausrichtung": eintrag.ausrichtung}
                for eintrag in spalte
            ]
            for spalte in vorlage.schriftfeld
        ]
    _abweichung(inhalt, "schriftfeld_art", vorlage.schriftfeld_art, STANDARD.schriftfeld_art)
    if vorlage.schriftfeld_anteile:
        inhalt["schriftfeld_anteile"] = [_zahlwert(a) for a in vorlage.schriftfeld_anteile]
    if vorlage.eigene_felder:
        inhalt["eigene_felder"] = list(vorlage.eigene_felder)
    if vorlage.eigene_felder_auf != STANDARD.eigene_felder_auf:
        inhalt["eigene_felder_auf"] = list(vorlage.eigene_felder_auf)
    for feld in ("buchten_je_blatt", "da_nummern", "kabel_gedreht",
                 "zeilen_kabel"):
        _abweichung(inhalt, feld, getattr(vorlage, feld), getattr(STANDARD, feld))
    belegung: dict = {}
    for feld in BELEGUNGSSCHLUESSEL:
        _abweichung(belegung, feld, getattr(vorlage, feld), getattr(STANDARD, feld))
    if belegung:
        inhalt["belegung"] = belegung
    return inhalt


def freie_kennung(name: str, vergeben, ordner: pathlib.Path) -> str:
    """Eine Kennung aus dem Namen, die weder vergeben ist noch als Datei liegt."""
    from .vorlagen import kennung_bilden

    grund = kennung_bilden(name)
    kennung, zaehler = grund, 2
    while kennung in vergeben or (pathlib.Path(ordner) / f"{kennung}.yaml").exists():
        kennung = f"{grund}-{zaehler}"
        zaehler += 1
    return kennung


def blattvorlage_speichern(
    vorlage: Blattvorlage, ordner: pathlib.Path, ueberschreiben: bool = False
) -> pathlib.Path:
    """Schreibt die Vorlage als Datei ``<kennung>.yaml`` in den Ordner.

    Ohne ``ueberschreiben`` wird die Datei **exklusiv** angelegt: eine
    vorhandene bleibt, wie sie ist - so kann eine neue Vorlage keine
    andere aus Versehen ersetzen. Wer eine vorhandene bearbeitet, will
    genau das Gegenteil und sagt es ausdruecklich.
    """
    ordner = pathlib.Path(ordner)
    ordner.mkdir(parents=True, exist_ok=True)
    ziel = ordner / f"{vorlage.id}.yaml"
    text = (
        "# Blattvorlage fuer Verteilerly, geschrieben vom Blattvorlagen-Editor.\n"
        "# Darin steht nur, was von der eingebauten Vorgabe abweicht.\n"
        + yaml.safe_dump(
            blattvorlage_als_yaml(vorlage), allow_unicode=True, sort_keys=False
        )
    )
    try:
        with open(ziel, "w" if ueberschreiben else "x", encoding="utf-8") as datei:
            datei.write(text)
    except FileExistsError:
        raise BlattvorlagenFehler(
            u("{0} gibt es schon - überschrieben wird nichts").format(ziel.name)
        ) from None
    return ziel


def _namenszeile(text: str, name: str) -> str:
    """Setzt ``name:`` in einer YAML-Datei neu - und laesst alles andere.

    Geschrieben wird nicht die ganze Vorlage: eine Datei sagt nur, was
    sie anders will, und ihre Kommentare gehoeren dem Anwender. Also
    wird die eine Zeile ersetzt und sonst nichts angefasst.
    """
    import re

    fertig = name.replace("\\", "\\\\").replace('"', '\\"')
    zeile = f'name: "{fertig}"'
    if re.search(r"^name:.*$", text, re.M):
        return re.sub(r"^name:.*$", zeile, text, count=1, flags=re.M)
    if re.search(r"^id:.*$", text, re.M):
        return re.sub(r"^(id:.*)$", r"\1\n" + zeile, text, count=1, flags=re.M)
    return zeile + "\n" + text


def blattvorlage_umbenennen(
    vorlage: Blattvorlage,
    name: str,
    ordner: pathlib.Path,
    quellen: list[pathlib.Path] | None = None,
) -> Blattvorlage:
    """Gibt einer Blattvorlage einen anderen Namen.

    Umbenannt wird der Name, nicht die Kennung - die ist der Dateiname
    und steht in der ``Verteilerly.conf``. Liegt die Datei nur unter den
    mitgelieferten, wird sie in den Arbeitsordner uebernommen: im Abbild
    laesst sich nichts schreiben, und dort gehoert sie auch nicht hin.
    """
    name = (name or "").strip()
    if not name:
        raise BlattvorlagenFehler(u("Eine Blattvorlage braucht einen Namen"))

    ordner = pathlib.Path(ordner)
    ziel = ordner / f"{vorlage.id}.yaml"
    text = ""
    if ziel.is_file():
        text = ziel.read_text(encoding="utf-8")
    else:
        for ort in quellen or []:
            kandidat = pathlib.Path(ort) / f"{vorlage.id}.yaml"
            if kandidat.is_file():
                text = kandidat.read_text(encoding="utf-8")
                break
    if not text:
        # Die eingebaute Vorgabe hat keine Datei - dann entsteht eine.
        text = f"id: {vorlage.id}\n"

    try:
        ordner.mkdir(parents=True, exist_ok=True)
        ziel.write_text(_namenszeile(text, name), encoding="utf-8")
    except OSError as fehler:
        raise BlattvorlagenFehler(
            u("Blattvorlage nicht umbenannt: {0}").format(fehler)
        ) from fehler
    return replace(vorlage, name=name)


def blattvorlage_loeschen(kennung: str, ordner: pathlib.Path) -> bool:
    """Loescht die Datei einer Blattvorlage.

    Gibt zurueck, ob eine Datei wegkam. Eine mitgelieferte liegt im
    Abbild weiter - dass sie nicht wieder ausgelegt wird, merkt sich
    ``pfade.loeschen_merken``.
    """
    ziel = pathlib.Path(ordner) / f"{kennung}.yaml"
    if not ziel.is_file():
        return False
    try:
        ziel.unlink()
    except OSError as fehler:
        raise BlattvorlagenFehler(
            u("Blattvorlage nicht gelöscht: {0}").format(fehler)
        ) from fehler
    return True


class Blattvorlagen:
    """Alle Blattvorlagen; die mitgelieferte Standardvorlage ist immer dabei."""

    def __init__(self, vorlagen: list[Blattvorlage] | None = None) -> None:
        self._vorlagen: dict[str, Blattvorlage] = {STANDARD.id: STANDARD}
        for vorlage in vorlagen or []:
            self._vorlagen[vorlage.id] = vorlage

    @classmethod
    def laden(cls, ordner: pathlib.Path) -> Blattvorlagen:
        gefunden: list[Blattvorlage] = []
        for datei in sorted(pathlib.Path(ordner).glob("*.yaml")):
            inhalt = yaml.safe_load(datei.read_text(encoding="utf-8")) or {}
            gefunden.append(blattvorlage_aus_yaml(inhalt, datei.name))
        return cls(gefunden)

    @classmethod
    def aus_ordnern(cls, ordner, ausgelassen=(), fehler=None) -> Blattvorlagen:
        """Aus mehreren Ordnern; bei gleicher Kennung gilt der letzte.

        ``ausgelassen`` nennt Marken wie ``blattvorlagen/knapp.yaml``,
        die weggeworfen wurden: eine geloeschte mitgelieferte Vorlage
        liegt im Abbild weiter und kaeme sonst durch die Hintertuer
        zurueck.

        **Eine unbrauchbare Datei nimmt nicht das Programm mit**: sie
        wird uebergangen, und was an ihr nicht stimmt, haengt diese
        Methode an die Liste ``fehler``. Wer eine Vorlage schreibt,
        vertippt sich - das darf den Start nicht verhindern.
        """
        weg = set(ausgelassen)
        gefunden: list[Blattvorlage] = []
        for ort in ordner:
            ort = pathlib.Path(ort)
            if not ort.is_dir():
                continue
            for datei in sorted(ort.glob("*.yaml")):
                try:
                    inhalt = yaml.safe_load(datei.read_text(encoding="utf-8")) or {}
                    vorlage = blattvorlage_aus_yaml(inhalt, datei.name, fehler)
                except BlattvorlagenFehler as wunde:
                    # Die Meldung nennt die Datei bereits.
                    if fehler is not None:
                        fehler.append(str(wunde))
                    continue
                except (yaml.YAMLError, OSError, ValueError, TypeError) as wunde:
                    if fehler is not None:
                        fehler.append(f"{datei.name}: {wunde}")
                    continue
                if f"{ort.name}/{vorlage.id}.yaml" in weg:
                    continue
                gefunden.append(vorlage)
        return cls(gefunden)

    def entfernen(self, kennung: str) -> None:
        """Nimmt eine Vorlage aus der Liste - die Datei ist schon weg.

        Die Kennung ``standard`` faellt dabei auf die eingebaute Vorgabe
        zurueck statt zu verschwinden: ohne sie gaebe es kein Blatt.
        """
        if kennung == STANDARD.id:
            self._vorlagen[STANDARD.id] = STANDARD
            return
        self._vorlagen.pop(kennung, None)

    def __len__(self) -> int:
        return len(self._vorlagen)

    def __contains__(self, kennung: object) -> bool:
        return kennung in self._vorlagen

    @property
    def alle(self) -> list[Blattvorlage]:
        return sorted(self._vorlagen.values(), key=lambda v: (not v.standard, v.name))

    def holen(self, kennung: str) -> Blattvorlage:
        try:
            return self._vorlagen[kennung]
        except KeyError:
            bekannt = ", ".join(sorted(self._vorlagen))
            raise BlattvorlagenFehler(
                u("Blattvorlage {0!r} gibt es nicht (bekannt: {1})").format(kennung, bekannt)
            ) from None

    def aufnehmen(self, vorlage: Blattvorlage) -> None:
        """Nimmt eine Vorlage auf oder ersetzt die gleicher Kennung."""
        self._vorlagen[vorlage.id] = vorlage

    def gewaehlt(self, kennung: str) -> Blattvorlage:
        """Die gemerkte Vorlage - oder die Standardvorlage.

        Was in der ``Verteilerly.conf`` steht, muss es nicht mehr geben:
        eine Vorlage laesst sich loeschen, und eine mitgelieferte kann in
        einer spaeteren Fassung fehlen. Dann faengt der Standard das auf,
        statt dass das Fenster gar nicht erst aufgeht.
        """
        if kennung in self._vorlagen:
            return self._vorlagen[kennung]
        return self.standard

    @property
    def standard(self) -> Blattvorlage:
        for vorlage in self.alle:
            if vorlage.standard:
                return vorlage
        return self.alle[0]
