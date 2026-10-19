"""Datenmodell eines LSA+-Verteilers.

Ein Verteiler besteht aus Buchten,
eine Bucht aus Leisten, eine Leiste aus Stiften, ein Stift aus den beiden
Adern a und b. Kabel und Rangierungen liegen quer dazu und haengen am
Verteiler, nicht an der einzelnen Ader.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field, replace

from . import schreibweisen
from .schreibweisen import Schreibweise
from .sprachen import u

SEITEN = ("a", "b")


class ModellFehler(Exception):
    """Fachlicher Fehler im Datenmodell."""


def unbekannte_schluessel(
    inhalt: dict, bekannt, herkunft: str, hinweise=None, wo: str = ""
) -> None:
    """Meldet Schluessel, die das Programm nicht kennt.

    Eine Vorlagendatei sagt nur, was sie anders will - was fehlt, kommt
    aus der Vorgabe. Genau deshalb faellt ein vertippter Schluessel sonst
    nirgends auf: ``zeilenhohe_max`` wird stillschweigend ueberlesen, und
    niemand weiss, warum die Vorlage aussieht wie immer. Abgewiesen wird
    die Datei nicht - sie kann aus einer neueren Fassung stammen.
    """
    if hinweise is None or not isinstance(inhalt, dict):
        return
    fremd = [str(name) for name in inhalt if str(name) not in set(bekannt)]
    for name in sorted(fremd):
        hinweise.append(
            u("{0}: {1} kennt das Programm nicht{2} - Tippfehler oder neuere "
              "Fassung?").format(herkunft, name, f" ({wo})" if wo else "")
        )


class UeberlaufFehler(ModellFehler):
    """Ein Kabel passt nicht vollstaendig auf die gewaehlte Leiste.

    Traegt mit, wie viele Doppeladern noch untergebracht werden muessen,
    damit die Oberflaeche fragen kann, wo fortgesetzt wird oder ob der
    Rest verfaellt.
    """

    def __init__(self, passend: int, rest: int) -> None:
        super().__init__(
            f"Kabel passt nicht vollstaendig: {passend} DA passen, {rest} DA bleiben uebrig"
        )
        self.passend = passend
        self.rest = rest


# --------------------------------------------------------------------------
# Adressierung
# --------------------------------------------------------------------------

#: Wie die Leisten heissen: gezaehlt (1, 2, 3) oder mit Buchstaben
#: (A, B, C). Eine reine Anzeigesache - gerechnet und gespeichert wird
#: immer mit der Nummer, wie bei den Rangierungen.
LEISTEN_ZAHLEN, LEISTEN_BUCHSTABEN = "zahlen", "buchstaben"
LEISTEN_SCHREIBWEISEN = (LEISTEN_ZAHLEN, LEISTEN_BUCHSTABEN)

#: Was im Rangierfeld statt eines Ziels stehen darf. Nicht jede Ader
#: fuehrt zu einer anderen: eine geht direkt weiter, eine ist defekt, an
#: einer sitzt der Abschlusswiderstand. Solche Vermerke sind wenige und
#: immer dieselben - darum eine Liste statt freiem Text: ein Tippfehler
#: im Ziel bleibt damit ein Tippfehler und wird nicht stillschweigend
#: zum Vermerk. Der Anwender aendert die Liste (Einstellungen oder das
#: Rechtsklickmenue der Leistenansicht); diese drei stehen am Anfang.
RANGIERVORLAGEN = ("direkt", "defekt", "12k")


def fremde_vermerke(projekt, vorlagen) -> list[str]:
    """Vermerke des Verteilers, die in keiner Vorlage stehen.

    Ein Verteiler aus der Zeit des freien Textes kann beliebige Vermerke
    tragen. Sie bleiben, wo sie sind - aber wer sie kennt, kann sie in
    die Vorlagen aufnehmen; dafuer sagt das Programm beim Oeffnen, dass
    es welche gibt. Jeder Text steht nur einmal in der Liste.
    """
    bekannt = {str(v).strip().casefold() for v in vorlagen}
    gefunden: list[str] = []
    for leiste in projekt.verteiler.alle_leisten:
        for stift in leiste.stifte:
            for seite in ("a", "b"):
                vermerk = stift.ader(seite).vermerk.strip()
                if vermerk and vermerk.casefold() not in bekannt:
                    if vermerk not in gefunden:
                        gefunden.append(vermerk)
    return gefunden


def leistenname(nummer: int, schreibweise: str = LEISTEN_ZAHLEN) -> str:
    """Wie die Leiste heisst: "3" oder "C" - ab der 27. dann "AA", "AB".

    Gezaehlt wird weiter ab 1; der Buchstabe ist nur ein anderer Name
    fuer dieselbe Leiste.
    """
    if schreibweise != LEISTEN_BUCHSTABEN or nummer < 1:
        return str(nummer)
    name, rest = "", int(nummer)
    while rest:
        rest, ziffer = divmod(rest - 1, 26)
        name = chr(ord("A") + ziffer) + name
    return name


def leistennummer(text: str) -> int:
    """Die Nummer hinter einem Leistennamen - "3" wie "C" ergeben 3.

    Gelesen wird beides, gleich welche Schreibweise eingestellt ist: wer
    umstellt, muss seine Rangierungen nicht neu tippen.
    """
    text = str(text).strip()
    if text.isdigit():
        return int(text)
    nummer = 0
    for zeichen in text.upper():
        if not "A" <= zeichen <= "Z":
            raise ModellFehler(u("{0!r} ist keine Leiste").format(text))
        nummer = nummer * 26 + (ord(zeichen) - ord("A") + 1)
    if not nummer:
        raise ModellFehler(u("{0!r} ist keine Leiste").format(text))
    return nummer


# Gelesen wird jede Schreibweise: "3 2a", "L3 2a" und "L3-2a"
# meinen dieselbe Ader. Das L ist ein Zierat, der Strich ein Trenner wie
# der Abstand. Die Leiste darf auch ihr Buchstabe sein ("C 2a"); steht
# dort ein einzelnes L, ist es die Leiste und kein Zierat - das regelt
# der Rueckzug des Musters von selbst.
_ADRESSMUSTER = r"[Ll]?\s*(\d+|[A-Za-z]+)\s*(?:-|\s+)\s*(\d+)\s*([ab])"
_ADRESSE = re.compile(rf"^\s*{_ADRESSMUSTER}\s*$", re.IGNORECASE)
_ADRESSE_IM_TEXT = re.compile(_ADRESSMUSTER, re.IGNORECASE)

# Zwei Rangierungen stehen nebeneinander ohne Trennzeichen,
# allein durch Abstand getrennt.
RANGIERUNG_TRENNER = "   "


@dataclass(frozen=True, order=True)
class Aderadresse:
    """Zeigt auf genau eine Ader im Verteiler.

    Schreibweise: "<Leiste> <Stift><Ader>", also "3 2a".
    So steht die Adresse auch in der Projektdatei. Wie sie dem Anwender
    gezeigt wird, sagt ``anzeige``.
    """

    leiste: int
    stift: int
    seite: str

    def __post_init__(self) -> None:
        if self.seite not in SEITEN:
            raise ModellFehler(u("Unbekannte Aderseite: {0!r}").format(self.seite))

    @classmethod
    def parse(cls, text: str) -> Aderadresse:
        treffer = _ADRESSE.match(text)
        if not treffer:
            raise ModellFehler(
                u("Rangierung {0!r} nicht lesbar - erwartet wird z.B. '3 2a', 'L3 2a' oder 'L3-2a'").format(text)
            )
        leiste, stift, seite = treffer.groups()
        return cls(leistennummer(leiste), int(stift), seite.lower())

    def __str__(self) -> str:
        return f"{self.leiste} {self.stift}{self.seite}"

    def anzeige(
        self,
        schreibweise: Schreibweise | None = None,
        leisten: str = LEISTEN_ZAHLEN,
    ) -> str:
        """Die Adresse in der eingestellten Schreibweise.

        ``leisten`` sagt, wie die Leiste dabei heisst - eine Rangierung
        zeigt auf dieselbe Leiste, die oben auf dem Blatt steht.
        """
        weise = schreibweise or schreibweisen.STANDARD
        return weise.schreiben(
            leistenname(self.leiste, leisten), self.stift, self.seite
        )


# --------------------------------------------------------------------------
# Verteileraufbau
# --------------------------------------------------------------------------


# Wie ein Text in seinem Feld steht. Dieselben Woerter wie in den
# Blattvorlagen - dort werden sie ebenfalls gebraucht, und zwei Listen
# derselben drei Woerter waeren eine zu viel.
LINKS, MITTE, RECHTS = "links", "mitte", "rechts"
AUSRICHTUNGEN = (LINKS, MITTE, RECHTS)

# Die Spalten, deren Text sich gestalten laesst. Stift und Ader
# stehen nicht darunter: sie sind Nummern, keine Eintraege. Die
# Kabelspalte auch nicht - dort steht ein Block ueber viele Zeilen, kein
# Zellentext.
STILFELDER = ("farbe", "bezeichnung", "rangierung", "bemerkung")


@dataclass(frozen=True)
class Textstil:
    """Wie der Text einer Zelle gesetzt ist.

    Eine leere ``ausrichtung`` heisst: so, wie die Blattvorlage es fuer
    diese Spalte haelt. Ein leerer Stil wird nicht gespeichert - die
    Projektdatei soll nur tragen, was jemand eingestellt hat.
    """

    ausrichtung: str = ""
    fett: bool = False
    kursiv: bool = False

    def __post_init__(self) -> None:
        if self.ausrichtung and self.ausrichtung not in AUSRICHTUNGEN:
            raise ModellFehler(u("Unbekannte Ausrichtung: {0!r}").format(self.ausrichtung))

    @property
    def leer(self) -> bool:
        return not (self.ausrichtung or self.fett or self.kursiv)

    def als_dict(self) -> dict:
        daten: dict[str, object] = {}
        if self.ausrichtung:
            daten["ausrichtung"] = self.ausrichtung
        if self.fett:
            daten["fett"] = True
        if self.kursiv:
            daten["kursiv"] = True
        return daten

    @classmethod
    def aus_dict(cls, daten: dict | None) -> Textstil:
        daten = daten or {}
        return cls(
            ausrichtung=str(daten.get("ausrichtung") or ""),
            fett=bool(daten.get("fett")),
            kursiv=bool(daten.get("kursiv")),
        )


LEERER_STIL = Textstil()


# Die Spalten, deren Zelle sich in zwei Beschriftungsfelder teilen
# laesst. Farbe und Rangierung nicht: dort steht ein Kuerzel
# beziehungsweise ein Ziel, kein freier Text.
TEILBARE_FELDER = ("bezeichnung", "bemerkung")
# Wie viel Prozent der Zellenbreite das rechte Feld bekommen darf. Unter
# einem Zehntel bliebe kein Platz fuer Text, ueber neun Zehnteln keiner
# fuer das linke Feld.
ANTEIL_MIN, ANTEIL_MAX, ANTEIL_VORGABE = 10, 90, 40


@dataclass(frozen=True)
class Zellenteilung:
    """Eine Zelle als zwei Beschriftungsfelder nebeneinander.

    ``anteil`` ist die Breite des rechten Feldes in Prozent. Auf dem
    Blatt steht zwischen beiden kein Strich - es soll aussehen wie eine
    Zelle, in der zwei Angaben stehen.

    Wird die Teilung aufgehoben, bleibt der Text des rechten Feldes
    erhalten: abwaehlen ist kein Loeschen. Er erscheint dann nur
    nirgends mehr.
    """

    anteil: int = ANTEIL_VORGABE
    text: str = ""
    geteilt: bool = True

    def __post_init__(self) -> None:
        if not ANTEIL_MIN <= self.anteil <= ANTEIL_MAX:
            raise ModellFehler(
                u("Der Anteil des zweiten Feldes muss zwischen {0} und {1} Prozent liegen, nicht {2}").format(ANTEIL_MIN, ANTEIL_MAX, self.anteil)
            )

    @property
    def leer(self) -> bool:
        return not self.geteilt and not self.text

    def als_dict(self) -> dict:
        daten: dict[str, object] = {"anteil": self.anteil}
        if self.text:
            daten["text"] = self.text
        if not self.geteilt:
            daten["geteilt"] = False
        return daten

    @classmethod
    def aus_dict(cls, daten: dict | None) -> Zellenteilung:
        daten = daten or {}
        anteil = int(daten.get("anteil") or ANTEIL_VORGABE)
        return cls(
            anteil=min(max(anteil, ANTEIL_MIN), ANTEIL_MAX),
            text=str(daten.get("text") or ""),
            geteilt=daten.get("geteilt", True) is not False,
        )


UNGETEILT = Zellenteilung(geteilt=False)


@dataclass
class Ader:
    """Eine Ader mit ihren vier Feldern.

    Die Rangierung steht bewusst nicht hier: sie ist ein eigenes Objekt am
    Verteiler, damit beide Enden nicht auseinanderlaufen koennen.
    Der ``vermerk`` dagegen gehoert der einzelnen Ader: er steht im
    Rangierfeld, meint aber kein Ziel im Verteiler und wird darum auch
    nicht gespiegelt.
    """

    seite: str
    farbe: str = ""
    bezeichnung: str = ""
    bemerkung: str = ""
    vermerk: str = ""
    # In welchem der beiden Rangierfelder der Vermerk steht. Sonst
    # spraenge er beim Eintragen eines Ziels ins erste Feld - die Eintraege
    # sollen ihre Plaetze behalten.
    vermerk_zuerst: bool = False
    # Textstil je Spalte - nur, was von der Blattvorlage abweicht.
    stile: dict[str, Textstil] = field(default_factory=dict)
    # Geteilte Zellen je Spalte.
    teilungen: dict[str, Zellenteilung] = field(default_factory=dict)

    def stil(self, feld: str) -> Textstil:
        """Wie der Text dieser Spalte steht - ohne Angabe wie die Vorlage."""
        return self.stile.get(feld, LEERER_STIL)

    def teilung(self, feld: str) -> Zellenteilung:
        """Ob und wie diese Zelle in zwei Felder geteilt ist."""
        return self.teilungen.get(feld, UNGETEILT)

    def teilung_setzen(self, feld: str, teilung: Zellenteilung) -> None:
        """Setzt die Teilung einer Zelle; eine leere wird geloescht."""
        if feld not in TEILBARE_FELDER:
            raise ModellFehler(u("{0!r} laesst sich nicht teilen").format(feld))
        if teilung.leer:
            self.teilungen.pop(feld, None)
        else:
            self.teilungen[feld] = teilung

    def stil_setzen(self, feld: str, stil: Textstil) -> None:
        """Setzt den Stil einer Spalte; ein leerer wird geloescht."""
        if feld not in STILFELDER:
            raise ModellFehler(u("Fuer {0!r} gibt es keinen Textstil").format(feld))
        if stil.leer:
            self.stile.pop(feld, None)
        else:
            self.stile[feld] = stil


@dataclass
class Stift:
    """Eine Doppelader mit den Adern a und b."""

    nummer: int
    a: Ader = field(default_factory=lambda: Ader("a"))
    b: Ader = field(default_factory=lambda: Ader("b"))

    def ader(self, seite: str) -> Ader:
        if seite == "a":
            return self.a
        if seite == "b":
            return self.b
        raise ModellFehler(u("Unbekannte Aderseite: {0!r}").format(seite))


@dataclass
class Leiste:
    """Eine LSA-Leiste. Die Nummer laeuft ueber alle Buchten durch."""

    nummer: int
    stifte: list[Stift]

    @property
    def da_anzahl(self) -> int:
        return len(self.stifte)

    def stift(self, nummer: int) -> Stift:
        if not 1 <= nummer <= self.da_anzahl:
            raise ModellFehler(
                u("Leiste {0} hat {1} DA, Stift {2} gibt es dort nicht").format(self.nummer, self.da_anzahl, nummer)
            )
        return self.stifte[nummer - 1]

    @classmethod
    def neu(cls, nummer: int, da_anzahl: int) -> Leiste:
        return cls(nummer, [Stift(i) for i in range(1, da_anzahl + 1)])


@dataclass
class Bucht:
    """Eine Montagebucht im Verteiler; ordnet nur an."""

    nummer: int
    leisten: list[Leiste]


# --------------------------------------------------------------------------
# Kabel
# --------------------------------------------------------------------------


@dataclass
class Kabelabschnitt:
    """Ein zusammenhaengendes Stueck eines Kabels auf einer Leiste.

    ``ab_kabel_da`` ist die Nummer der Doppelader **im Kabel**, mit der
    dieses Stueck anfaengt - daran haengt die Adernfarbe. ``None`` heisst:
    es folgt dem vorigen Stueck, und das ist der Regelfall. Festgehalten
    wird die Nummer erst, wenn die Reihenfolge der Abschnitte sie nicht
    mehr hergibt: nimmt man von einer geteilt aufgelegten Leitung ein
    Stueck ab, bleiben die uebrigen auf ihrer Stelle im Kabel stehen,
    denn in der Leiste stehen noch ihre Farben.
    """

    leiste: int
    start_da: int
    anzahl_da: int
    ab_kabel_da: int | None = None

    @property
    def end_da(self) -> int:
        return self.start_da + self.anzahl_da - 1

    def belegt(self, leiste: int, da: int) -> bool:
        return leiste == self.leiste and self.start_da <= da <= self.end_da


@dataclass
class Kabel:
    """Ein Kabel mit einem oder mehreren Abschnitten.

    ``da_gesamt`` ist die Nenngroesse des Kabels. Sie darf groesser sein als
    die Summe der aufgelegten Doppeladern - das ist der Sonderfall Kuerzen, etwa ein 6-DA-Kabel, von dem nur 5 DA aufgelegt werden.
    """

    beschriftung: str
    abschnitte: list[Kabelabschnitt] = field(default_factory=list)
    kabeltyp: str | None = None
    da_gesamt: int | None = None

    @property
    def da_aufgelegt(self) -> int:
        return sum(a.anzahl_da for a in self.abschnitte)

    @property
    def gekuerzt(self) -> bool:
        return self.da_gesamt is not None and self.da_gesamt > self.da_aufgelegt

    def erste_da(self, leiste: int) -> int | None:
        """Die kleinste Doppelader, die das Kabel auf dieser Leiste belegt.

        Ein Kabel kann ueber mehrere Leisten laufen und auf einer Leiste
        auch in mehreren Abschnitten liegen; gefragt ist, wo es dort
        anfaengt. Liegt es gar nicht auf der Leiste, kommt None.
        """
        starts = [a.start_da for a in self.abschnitte if a.leiste == leiste]
        return min(starts) if starts else None

    def positionen(self) -> list[tuple[int, int, int]]:
        """(Kabel-DA, Leiste, Leisten-DA) fuer jede aufgelegte Doppelader.

        Die Kabel-DA zaehlt ueber alle Abschnitte durch und bestimmt damit
        die Adernfarbe.
        """
        ergebnis: list[tuple[int, int, int]] = []
        kabel_da = 1
        for abschnitt in self.abschnitte:
            if abschnitt.ab_kabel_da is not None:
                kabel_da = abschnitt.ab_kabel_da
            for versatz in range(abschnitt.anzahl_da):
                ergebnis.append(
                    (kabel_da, abschnitt.leiste, abschnitt.start_da + versatz)
                )
                kabel_da += 1
        return ergebnis

    def belegte_kabel_da(self) -> set[int]:
        """Welche Doppeladern des Kabels aufliegen - gezaehlt im Kabel."""
        return {kabel_da for kabel_da, _leiste, _da in self.positionen()}

    @property
    def hoechste_kabel_da(self) -> int:
        """Die groesste aufliegende Kabel-DA - mit Luecke mehr als die Zahl."""
        belegt = self.belegte_kabel_da()
        return max(belegt) if belegt else 0

    @property
    def lueckenlos(self) -> bool:
        """Zaehlen die aufliegenden Doppeladern ohne Luecke von 1 durch?

        Nur dann darf am Ende einfach weitergezaehlt werden. Nach einem
        abgenommenen Abschnitt fehlt mitten im Kabel ein Stueck, und was
        neu dazukommt, gehoert in diese Luecke - sonst bekaeme es Farben,
        die im Kabel schon woanders liegen.
        """
        belegt = self.belegte_kabel_da()
        return belegt == set(range(1, len(belegt) + 1))

    def freie_kabel_da(self, anzahl: int) -> int | None:
        """Die erste Stelle, an der ``anzahl`` freie Kabel-DA zusammenliegen.

        Gesucht wird innerhalb der Nenngroesse: mehr Doppeladern als das
        Kabel hat, gibt es nicht. Passt nirgends ein Stueck dieser Laenge,
        kommt None - dann zaehlt der Aufrufer wie bisher am Ende weiter.
        """
        if anzahl < 1:
            return None
        belegt = self.belegte_kabel_da()
        grenze = self.da_gesamt or (len(belegt) + anzahl)
        for start in range(1, max(0, grenze - anzahl) + 2):
            if all(start + i not in belegt for i in range(anzahl)):
                return start
        return None


# --------------------------------------------------------------------------
# Rangierung
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Rangierung:
    """Eine Verbindung zwischen zwei Adern desselben Verteilers.

    Sie wird als ein Objekt gehalten. Dass auf beiden Leistenblaettern ein
    Eintrag erscheint, ist eine Frage der Darstellung, nicht der
    Speicherung - damit kann keine halbe Rangierung entstehen.
    """

    von: Aderadresse
    nach: Aderadresse

    def partner(self, adresse: Aderadresse) -> Aderadresse | None:
        if adresse == self.von:
            return self.nach
        if adresse == self.nach:
            return self.von
        return None

    def beruehrt(self, adresse: Aderadresse) -> bool:
        return adresse in (self.von, self.nach)


MAX_RANGIERUNGEN_JE_ADER = 2


# --------------------------------------------------------------------------
# Verteiler
# --------------------------------------------------------------------------


@dataclass
class Verteiler:
    """Ein vollstaendiger Verteiler samt Kabeln und Rangierungen."""

    name: str = ""
    nummer: str = ""
    buchten: list[Bucht] = field(default_factory=list)
    kabel: list[Kabel] = field(default_factory=list)
    rangierungen: list[Rangierung] = field(default_factory=list)

    # -- Aufbau ------------------------------------------------------------

    @classmethod
    def aus_geometrie(
        cls,
        buchten: int,
        leisten_je_bucht: int,
        da_je_leiste: int,
        name: str = "",
        nummer: str = "",
    ) -> Verteiler:
        """Baut einen Verteiler aus den drei Kennzahlen.

        Die Leisten werden ueber alle Buchten hinweg durchlaufend
        nummeriert: bei 2 Buchten zu 6 Leisten traegt Bucht 1 die
        Leisten 1 bis 6 und Bucht 2 die Leisten 7 bis 12.
        """
        if min(buchten, leisten_je_bucht, da_je_leiste) < 1:
            raise ModellFehler(u("Buchten, Leisten und DA muessen mindestens 1 sein"))
        return cls.aus_buchten(
            [(leisten_je_bucht, da_je_leiste)] * buchten, name, nummer
        )

    @classmethod
    def aus_buchten(
        cls,
        bauplan: list[tuple[int, int]],
        name: str = "",
        nummer: str = "",
    ) -> Verteiler:
        """Baut einen Verteiler aus ungleich besetzten Buchten.

        ``bauplan`` nennt je Bucht, wie viele Leisten sie traegt und wie
        viele Doppeladern jede dieser Leisten hat. Nicht jeder Verteiler
        ist gleichmaessig gewachsen; vorerst hat aber jede Bucht **eine**
        Leistenlaenge - alles Weitere hat bisher niemand gebraucht.

        Die Leisten werden ueber alle Buchten hinweg durchlaufend
        nummeriert.
        """
        if not bauplan:
            raise ModellFehler(u("Ein Verteiler braucht mindestens eine Bucht"))

        aufbau: list[Bucht] = []
        naechste_leiste = 1
        for buchten_nr, (leisten_anzahl, da_je_leiste) in enumerate(bauplan, 1):
            if min(leisten_anzahl, da_je_leiste) < 1:
                raise ModellFehler(
                    u("Bucht {0}: Leisten und DA muessen mindestens 1 sein").format(buchten_nr)
                )
            leisten = []
            for _ in range(leisten_anzahl):
                leisten.append(Leiste.neu(naechste_leiste, da_je_leiste))
                naechste_leiste += 1
            aufbau.append(Bucht(buchten_nr, leisten))
        return cls(name=name, nummer=nummer, buchten=aufbau)

    # -- Zugriff -----------------------------------------------------------

    @property
    def alle_leisten(self) -> list[Leiste]:
        return [leiste for bucht in self.buchten for leiste in bucht.leisten]

    @property
    def da_gesamt(self) -> int:
        return sum(leiste.da_anzahl for leiste in self.alle_leisten)

    def leiste(self, nummer: int) -> Leiste:
        for leiste in self.alle_leisten:
            if leiste.nummer == nummer:
                return leiste
        raise ModellFehler(u("Leiste {0} gibt es in diesem Verteiler nicht").format(nummer))

    def stift(self, adresse: Aderadresse) -> Stift:
        return self.leiste(adresse.leiste).stift(adresse.stift)

    def ader(self, adresse: Aderadresse) -> Ader:
        return self.stift(adresse).ader(adresse.seite)

    def kennt(self, adresse: Aderadresse) -> bool:
        try:
            self.ader(adresse)
        except ModellFehler:
            return False
        return True

    # -- Kabel --------------------------------------------

    def kabel_an(self, leiste: int, da: int) -> Kabel | None:
        """Das Kabel, das diese Doppelader belegt - oder None."""
        for kabel in self.kabel:
            if any(a.belegt(leiste, da) for a in kabel.abschnitte):
                return kabel
        return None

    def platz_pruefen(self, leiste: int, start_da: int, anzahl_da: int) -> tuple[int, int]:
        """Wie viele DA passen ab ``start_da`` auf die Leiste, wie viele nicht.

        Prueft Leistenende und bereits belegte Doppeladern. Gibt
        (passend, rest) zurueck, ohne etwas zu veraendern.
        """
        if anzahl_da < 1:
            raise ModellFehler(u("Ein Kabel muss mindestens eine Doppelader haben"))
        ziel = self.leiste(leiste)
        if not 1 <= start_da <= ziel.da_anzahl:
            raise ModellFehler(
                u("Start-DA {0} liegt ausserhalb von Leiste {1} ({2} DA)").format(start_da, leiste, ziel.da_anzahl)
            )

        passend = 0
        for versatz in range(anzahl_da):
            da = start_da + versatz
            if da > ziel.da_anzahl:
                break
            if self.kabel_an(leiste, da) is not None:
                raise ModellFehler(
                    u("Leiste {0} DA {1} ist bereits von einem Kabel belegt").format(leiste, da)
                )
            passend += 1
        return passend, anzahl_da - passend

    def kabel_anlegen(
        self,
        beschriftung: str,
        leiste: int,
        start_da: int,
        anzahl_da: int,
        kabeltyp: str | None = None,
        da_gesamt: int | None = None,
    ) -> Kabel:
        """Legt ein Kabel auf einer Leiste auf.

        Passt es nicht vollstaendig, wird ``UeberlaufFehler`` ausgeloest.
        Die Oberflaeche fragt dann, ob fortgesetzt wird oder der
        Rest verfaellt, und ruft danach ``kabel_anlegen_mehrteilig`` oder
        legt nur den passenden Teil auf.
        """
        passend, rest = self.platz_pruefen(leiste, start_da, anzahl_da)
        if rest:
            raise UeberlaufFehler(passend, rest)
        return self.kabel_anlegen_mehrteilig(
            beschriftung,
            [Kabelabschnitt(leiste, start_da, anzahl_da)],
            kabeltyp=kabeltyp,
            da_gesamt=da_gesamt,
        )

    def kabel_anlegen_mehrteilig(
        self,
        beschriftung: str,
        abschnitte: list[Kabelabschnitt],
        kabeltyp: str | None = None,
        da_gesamt: int | None = None,
    ) -> Kabel:
        """Legt ein Kabel mit fertig aufgeteilten Abschnitten auf.

        Damit wird sowohl die Fortsetzung nach einem Ueberlauf als
        auch das Kuerzen abgebildet: ``da_gesamt`` ist die
        Nenngroesse des Kabels und darf groesser sein als die Summe der
        Abschnitte.
        """
        if not abschnitte:
            raise ModellFehler(u("Ein Kabel braucht mindestens einen Abschnitt"))

        for abschnitt in abschnitte:
            passend, rest = self.platz_pruefen(
                abschnitt.leiste, abschnitt.start_da, abschnitt.anzahl_da
            )
            if rest:
                raise ModellFehler(
                    u("Abschnitt auf Leiste {0} ab DA {1} passt nicht ({2} DA zu viel)").format(abschnitt.leiste, abschnitt.start_da, rest)
                )

        aufgelegt = sum(a.anzahl_da for a in abschnitte)
        if da_gesamt is not None and da_gesamt < aufgelegt:
            raise ModellFehler(
                u("Das Kabel hat {0} DA, aufgelegt werden sollen {1}").format(da_gesamt, aufgelegt)
            )

        kabel = Kabel(
            beschriftung=beschriftung,
            abschnitte=list(abschnitte),
            kabeltyp=kabeltyp,
            da_gesamt=da_gesamt if da_gesamt is not None else aufgelegt,
        )
        self.kabel.append(kabel)
        return kabel

    def kabel_auflegen_aendern(self, kabel: Kabel, anzahl_da: int) -> None:
        """Aendert, wie viele Doppeladern eines Kabels aufliegen.

        Gewachsen und geschrumpft wird am Ende: der Anfang bleibt, wo er
        ist, denn dort haengt das Kabel. Passt die Verlaengerung nicht auf
        die Leiste, wird ``UeberlaufFehler`` ausgeloest - die Oberflaeche
        fragt dann wie beim Auflegen, ob fortgesetzt wird oder der Rest
        verfaellt.
        """
        if anzahl_da < 1:
            raise ModellFehler(u("Ein Kabel muss mindestens eine Doppelader haben"))
        jetzt = kabel.da_aufgelegt
        if anzahl_da == jetzt:
            return

        if anzahl_da < jetzt:
            self._kabel_kuerzen(kabel, jetzt - anzahl_da)
            return

        zusatz = anzahl_da - jetzt
        letzter = kabel.abschnitte[-1]
        weiter = letzter.start_da + letzter.anzahl_da
        if weiter > self.leiste(letzter.leiste).da_anzahl:
            # Das Kabel endet schon am Leistenende - hier waechst nichts
            # mehr, ohne dass jemand eine Fortsetzung waehlt.
            raise UeberlaufFehler(jetzt, zusatz)
        passend, rest = self.platz_pruefen(letzter.leiste, weiter, zusatz)
        if rest:
            raise UeberlaufFehler(jetzt + passend, rest)
        if kabel.lueckenlos:
            letzter.anzahl_da += zusatz
        else:
            # Mit Luecke waere Weiterzaehlen falsch: die neuen
            # Doppeladern gehoeren in die Luecke, und eine eigene Stelle
            # im Kabel hat nur ein eigener Abschnitt.
            kabel.abschnitte.append(
                Kabelabschnitt(
                    letzter.leiste,
                    weiter,
                    zusatz,
                    ab_kabel_da=kabel.freie_kabel_da(zusatz),
                )
            )
        if (
            kabel.da_gesamt is not None
            and kabel.da_gesamt < kabel.hoechste_kabel_da
        ):
            kabel.da_gesamt = kabel.hoechste_kabel_da

    def _kabel_kuerzen(self, kabel: Kabel, weniger: int) -> None:
        """Nimmt Doppeladern vom Ende weg; leere Abschnitte fallen fort."""
        while weniger:
            letzter = kabel.abschnitte[-1]
            weg = min(weniger, letzter.anzahl_da)
            letzter.anzahl_da -= weg
            weniger -= weg
            if letzter.anzahl_da == 0:
                kabel.abschnitte.pop()

    def kabel_verlaengern(
        self, kabel: Kabel, leiste: int, start_da: int, anzahl_da: int
    ) -> None:
        """Haengt einen weiteren Abschnitt an ein Kabel an.

        So geht es nach einem Ueberlauf weiter, wenn ein aufgelegtes Kabel
        groesser wird, als auf seiner Leiste noch Platz ist.
        """
        passend, rest = self.platz_pruefen(leiste, start_da, anzahl_da)
        if rest:
            raise ModellFehler(
                u("Auf Leiste {0} ab DA {1} passen nur {2} von {3} DA").format(leiste, start_da, passend, anzahl_da)
            )
        # Hat die Leitung eine Luecke in ihrer Zaehlung - etwa weil ein
        # Abschnitt abgenommen wurde -, gehoert das neue Stueck dorthin
        # und nicht hinter das letzte: so bekommt es die Farben, die im
        # Kabel noch frei sind.
        stelle = None if kabel.lueckenlos else kabel.freie_kabel_da(anzahl_da)
        kabel.abschnitte.append(
            Kabelabschnitt(leiste, start_da, anzahl_da, ab_kabel_da=stelle)
        )
        if (
            kabel.da_gesamt is not None
            and kabel.da_gesamt < kabel.hoechste_kabel_da
        ):
            kabel.da_gesamt = kabel.hoechste_kabel_da

    def kabel_entfernen(self, kabel: Kabel) -> None:
        self.kabel.remove(kabel)

    def kabel_abschnitt_an(self, kabel: Kabel, leiste: int, da: int) -> int | None:
        """Das wievielte Stueck der Leitung liegt auf dieser Doppelader?"""
        for nummer, abschnitt in enumerate(kabel.abschnitte):
            if abschnitt.belegt(leiste, da):
                return nummer
        return None

    def kabel_abschnitt_entfernen(self, kabel: Kabel, nummer: int) -> Kabelabschnitt:
        """Nimmt ein einzelnes Stueck einer geteilt aufgelegten Leitung ab.

        Die Leitung bleibt liegen und ist danach **gekuerzt**: was
        herunterkommt, zaehlt als ihr Rest und laesst sich an anderer
        Stelle wieder auflegen. ``da_gesamt`` bleibt darum stehen - die
        Nenngroesse des Kabels aendert sich nicht dadurch, dass ein
        Stueck abgenommen wird; stand sie noch offen, wird sie hier
        festgehalten, sonst waere der Rest nicht mehr zu sehen.

        Das letzte Stueck bleibt liegen: eine Leitung ohne Doppelader
        waere keine. Wer sie ganz weg will, nimmt `kabel_entfernen`.
        """
        if not 0 <= nummer < len(kabel.abschnitte):
            raise ModellFehler(
                u("Diesen Abschnitt hat die Leitung nicht")
            )
        if len(kabel.abschnitte) < 2:
            raise ModellFehler(
                u("Die Leitung liegt nur in einem Stück — dann wird sie ganz entfernt")
            )
        if kabel.da_gesamt is None:
            kabel.da_gesamt = kabel.da_aufgelegt
        self._stellen_festhalten(kabel)
        return kabel.abschnitte.pop(nummer)

    @staticmethod
    def _stellen_festhalten(kabel: Kabel) -> None:
        """Schreibt jedem Abschnitt seine Stelle im Kabel fest.

        Gleich danach fehlt ein Stueck, und die Reihenfolge gibt die
        Stellen nicht mehr her: die uebrigen Abschnitte wuerden nach vorn
        rutschen und andere Farben vorsehen, als in der Leiste stehen.
        """
        stelle = 1
        for abschnitt in kabel.abschnitte:
            if abschnitt.ab_kabel_da is None:
                abschnitt.ab_kabel_da = stelle
            stelle = abschnitt.ab_kabel_da + abschnitt.anzahl_da

    # -- Umlegen und kopieren ----------------------------------------

    def _platz_verlangen(
        self, leiste: int, start_da: int, anzahl_da: int, ausser: Kabel | None = None
    ) -> None:
        """Wirft, wenn das Kabel dort nicht ganz und frei liegen kann.

        ``ausser`` ist das Kabel, das gerade umzieht: seine eigenen
        Doppeladern stehen ihm nicht im Weg.
        """
        if anzahl_da < 1:
            raise ModellFehler(u("Ein Kabel muss mindestens eine Doppelader haben"))
        ziel = self.leiste(leiste)
        if not 1 <= start_da <= ziel.da_anzahl:
            raise ModellFehler(
                u("Start-DA {0} liegt ausserhalb von Leiste {1} ({2} DA)").format(start_da, leiste, ziel.da_anzahl)
            )
        if start_da + anzahl_da - 1 > ziel.da_anzahl:
            raise ModellFehler(
                u("Auf Leiste {0} ab DA {1} ist für {2} DA kein Platz").format(leiste, start_da, anzahl_da)
            )
        for versatz in range(anzahl_da):
            da = start_da + versatz
            belegt = self.kabel_an(leiste, da)
            if belegt is not None and belegt is not ausser:
                raise ModellFehler(
                    u("Leiste {0} DA {1} ist bereits von einem Kabel belegt").format(leiste, da)
                )

    @staticmethod
    def _plaetze(kabel: Kabel) -> list[tuple[int, int]]:
        """Leiste und DA jeder aufgelegten Doppelader - in der Folge des Kabels."""
        return [(leiste, da) for _kabel_da, leiste, da in kabel.positionen()]

    def kabel_verschieben(self, kabel: Kabel, leiste: int, start_da: int) -> Kabel:
        """Legt ein aufgelegtes Kabel an eine andere Stelle.

        **Es zieht mit allem um, was daran haengt**: die Adern nehmen
        Farbe, Bezeichnung, Bemerkung, Vermerk, Textstil und geteilte
        Zellen mit, und die Rangierungen folgen - sie zeigen auf die
        Ader, nicht auf den Platz. Was das Kabel verlaesst, ist danach
        leer wie vor dem Auflegen.

        Ein mehrteiliges Kabel wird dabei wieder zu einem Stueck: wer es
        umlegt, sucht sich einen Platz, an dem es ganz liegt.
        """
        anzahl = kabel.da_aufgelegt
        self._platz_verlangen(leiste, start_da, anzahl, ausser=kabel)
        alt = self._plaetze(kabel)
        kabel.abschnitte = [Kabelabschnitt(leiste, start_da, anzahl)]
        self._adern_umziehen(alt, self._plaetze(kabel))
        return kabel

    def kabel_kopieren(
        self, kabel: Kabel, leiste: int, start_da: int, beschriftung: str | None = None
    ) -> Kabel:
        """Legt ein zweites Kabel derselben Art an eine freie Stelle.

        Kopiert werden Beschriftung, Typ, Groesse und die Adern samt
        ihren Texten - **nicht die Rangierungen**: eine Rangierung ist
        eine Verbindung, die es genau einmal gibt.
        """
        anzahl = kabel.da_aufgelegt
        self._platz_verlangen(leiste, start_da, anzahl)
        zwilling = self.kabel_anlegen_mehrteilig(
            kabel.beschriftung if beschriftung is None else beschriftung,
            [Kabelabschnitt(leiste, start_da, anzahl)],
            kabeltyp=kabel.kabeltyp,
            da_gesamt=kabel.da_gesamt,
        )
        self._adern_kopieren(self._plaetze(kabel), self._plaetze(zwilling))
        return zwilling

    def _adern_lesen(self, plaetze: list[tuple[int, int]]) -> list[tuple[Ader, Ader]]:
        return [
            (
                copy.deepcopy(self.leiste(leiste).stift(da).a),
                copy.deepcopy(self.leiste(leiste).stift(da).b),
            )
            for leiste, da in plaetze
        ]

    def _adern_setzen(
        self, plaetze: list[tuple[int, int]], inhalt: list[tuple[Ader, Ader]]
    ) -> None:
        for (leiste, da), (a, b) in zip(plaetze, inhalt):
            stift = self.leiste(leiste).stift(da)
            stift.a, stift.b = a, b

    def _adern_umziehen(
        self, alt: list[tuple[int, int]], neu: list[tuple[int, int]]
    ) -> None:
        """Traegt die Adern von alten auf neue Plaetze um, samt Rangierungen.

        Erst gelesen, dann geleert, dann gesetzt: alter und neuer Platz
        duerfen sich ueberschneiden, wenn ein Kabel auf seiner Leiste
        nur verrutscht.
        """
        inhalt = self._adern_lesen(alt)
        for leiste, da in alt:
            stift = self.leiste(leiste).stift(da)
            stift.a, stift.b = Ader("a"), Ader("b")
        self._adern_setzen(neu, inhalt)
        self._rangierungen_umhaengen(alt, neu)

    def _adern_kopieren(
        self, quelle: list[tuple[int, int]], ziel: list[tuple[int, int]]
    ) -> None:
        """Legt die Adern noch einmal an - die Quelle bleibt, wie sie ist."""
        self._adern_setzen(ziel, self._adern_lesen(quelle))

    def _rangierungen_umhaengen(
        self, alt: list[tuple[int, int]], neu: list[tuple[int, int]]
    ) -> None:
        """Laesst die Rangierungen der Adern folgen.

        Eine Rangierung meint die Ader, nicht den Platz: zieht die Ader
        um, zeigt die Verbindung danach auf den neuen Platz. Faellt dabei
        eine Rangierung mit einer bestehenden zusammen, bleibt eine.
        """
        umzug = {
            Aderadresse(alte_leiste, altes_da, seite):
                Aderadresse(neue_leiste, neues_da, seite)
            for (alte_leiste, altes_da), (neue_leiste, neues_da) in zip(alt, neu)
            for seite in SEITEN
        }
        gesehen: set[frozenset] = set()
        geblieben = []
        for rangierung in self.rangierungen:
            gewandert = replace(
                rangierung,
                von=umzug.get(rangierung.von, rangierung.von),
                nach=umzug.get(rangierung.nach, rangierung.nach),
            )
            marke = frozenset((gewandert.von, gewandert.nach))
            if len(marke) < 2 or marke in gesehen:
                continue
            gesehen.add(marke)
            geblieben.append(gewandert)
        self.rangierungen = geblieben

    # -- Rangierungen -------------------------------------

    def rangierungen_an(self, adresse: Aderadresse) -> list[Rangierung]:
        return [r for r in self.rangierungen if r.beruehrt(adresse)]

    def ziele_von(self, adresse: Aderadresse) -> list[Aderadresse]:
        """Die Gegenstellen dieser Ader - bis zu zwei.

        Genau das erzeugt den automatischen Eintrag am anderen Ende,
        ohne dass ein zweiter Datensatz gepflegt werden muesste.
        """
        ziele = []
        for rangierung in self.rangierungen_an(adresse):
            partner = rangierung.partner(adresse)
            if partner is not None:
                ziele.append(partner)
        return ziele

    def rangierung_anlegen(self, von: Aderadresse, nach: Aderadresse) -> Rangierung:
        """Legt eine Rangierung an und prueft sie."""
        if von == nach:
            raise ModellFehler(u("Eine Rangierung kann nicht auf sich selbst zeigen ({0})").format(von))

        for adresse in (von, nach):
            if not self.kennt(adresse):
                raise ModellFehler(u("{0} gibt es in diesem Verteiler nicht").format(adresse))

        for bestehend in self.rangierungen:
            if bestehend.beruehrt(von) and bestehend.beruehrt(nach):
                raise ModellFehler(u("Die Rangierung {0} - {1} besteht bereits").format(von, nach))

        for adresse in (von, nach):
            belegt = len(self.rangierungen_an(adresse))
            if belegt >= MAX_RANGIERUNGEN_JE_ADER:
                raise ModellFehler(
                    u("{0} traegt bereits {1} Rangierungen - mehr als {2} sind nicht vorgesehen").format(adresse, belegt, MAX_RANGIERUNGEN_JE_ADER)
                )

        rangierung = Rangierung(von, nach)
        self.rangierungen.append(rangierung)
        return rangierung

    def rangierung_entfernen(self, von: Aderadresse, nach: Aderadresse) -> None:
        """Entfernt eine Rangierung - und damit immer beide Enden."""
        for rangierung in self.rangierungen:
            if rangierung.beruehrt(von) and rangierung.beruehrt(nach):
                self.rangierungen.remove(rangierung)
                return
        raise ModellFehler(u("Die Rangierung {0} - {1} gibt es nicht").format(von, nach))


    def rangierungen_setzen(
        self, adresse: Aderadresse, ziele: list[Aderadresse]
    ) -> None:
        """Setzt die Rangierungen einer Ader auf genau ``ziele``.

        Das ist die Form, in der die Oberflaeche arbeitet: der Anwender
        tippt den Inhalt des Feldes, das Modell gleicht ab. Wegfallende
        Rangierungen verschwinden dabei an beiden Enden.

        Es wird erst geprueft und dann geaendert - schlaegt eine Pruefung
        fehl, bleibt der bisherige Stand unangetastet.

        Die angegebene Folge ist auch die Anzeigefolge: wer im ersten
        Feld etwas anderes eintraegt, findet es hinterher wieder im
        ersten Feld und nicht im zweiten.
        """
        if len(ziele) > MAX_RANGIERUNGEN_JE_ADER:
            raise ModellFehler(
                u("{0} kann hoechstens {1} Rangierungen tragen, angegeben sind {2}").format(adresse, MAX_RANGIERUNGEN_JE_ADER, len(ziele))
            )
        if len(set(ziele)) != len(ziele):
            raise ModellFehler(u("Dieselbe Gegenstelle ist zweimal angegeben"))

        bisher = self.ziele_von(adresse)

        # Vorpruefung auf einer Kopie, damit nichts halb angewandt wird.
        # Erst fliegen alle Rangierungen dieser Ader heraus, dann kommen
        # sie in der angegebenen Folge zurueck - so bleibt die Reihenfolge
        # die des Anwenders.
        probe = [r for r in self.rangierungen if not r.beruehrt(adresse)]
        for ziel in ziele:
            if ziel == adresse:
                raise ModellFehler(
                    u("Eine Rangierung kann nicht auf sich selbst zeigen ({0})").format(ziel)
                )
            if not self.kennt(ziel):
                raise ModellFehler(u("{0} gibt es in diesem Verteiler nicht").format(ziel))
            # Die eigenen sind oben herausgenommen und zaehlen nicht mit.
            belegt = sum(1 for r in probe if r.beruehrt(ziel))
            if belegt >= MAX_RANGIERUNGEN_JE_ADER:
                raise ModellFehler(
                    u("{0} traegt bereits {1} Rangierungen - mehr als {2} sind nicht vorgesehen").format(ziel, belegt, MAX_RANGIERUNGEN_JE_ADER)
                )
            probe.append(Rangierung(adresse, ziel))

        self.rangierungen = probe

    # -- Vermerke im Rangierfeld -----------------------------------

    def vermerk_setzen(
        self, adresse: Aderadresse, text: str, zuerst: bool = False
    ) -> None:
        """Setzt den Freitext dieser Ader - oder loescht ihn.

        Ein Vermerk belegt eines der beiden Rangierfelder. Traegt die Ader
        schon zwei Rangierungen, ist kein Feld mehr frei; dann wird
        abgewiesen, statt den Vermerk stillschweigend zu verschlucken.
        ``zuerst`` haelt fest, ob er vor oder hinter den Zielen steht.
        """
        text = text.strip()
        if text and len(self.ziele_von(adresse)) >= MAX_RANGIERUNGEN_JE_ADER:
            raise ModellFehler(
                u("{0} traegt bereits {1} Rangierungen - fuer einen Vermerk ist kein Feld frei").format(adresse, MAX_RANGIERUNGEN_JE_ADER)
            )
        ader = self.ader(adresse)
        ader.vermerk = text
        ader.vermerk_zuerst = bool(text) and zuerst

    def rangiereintraege(
        self,
        adresse: Aderadresse,
        schreibweise: Schreibweise | None = None,
        leisten: str = LEISTEN_ZAHLEN,
    ) -> list[str]:
        """Was im Rangierfeld dieser Ader steht: Ziele und Vermerk.

        In der Folge, in der es eingetragen wurde - die Felder tauschen
        die Plaetze nicht.
        """
        eintraege = [
            ziel.anzeige(schreibweise, leisten) for ziel in self.ziele_von(adresse)
        ]
        ader = self.ader(adresse)
        if ader.vermerk:
            eintraege.insert(0 if ader.vermerk_zuerst else len(eintraege), ader.vermerk)
        return eintraege

    def rangierfeld(
        self,
        adresse: Aderadresse,
        schreibweise: Schreibweise | None = None,
        leisten: str = LEISTEN_ZAHLEN,
    ) -> str:
        """Der ganze Inhalt des Rangierfeldes als eine Zeile."""
        return RANGIERUNG_TRENNER.join(
            self.rangiereintraege(adresse, schreibweise, leisten)
        )


# --------------------------------------------------------------------------
# Restleitungen
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Restplatz:
    """Wohin der Rest einer gekuerzten Leitung kommen soll.

    ``leiste`` und ``start_da`` sind ``None``, wenn kein Stueck freier
    Leiste mehr gross genug ist. Der Eintrag bleibt dann in der Liste -
    wer den Verteiler vor sich hat, soll sehen, was uebrig bleibt, und
    nicht raten, warum eine Leitung fehlt.
    """

    kabel: Kabel
    rest: int
    leiste: int | None = None
    start_da: int | None = None

    @property
    def passt(self) -> bool:
        return self.leiste is not None

    @property
    def fortsetzung(self) -> bool:
        """Schliesst der Platz unmittelbar an die Leitung an?

        Dann waechst ihr letzter Abschnitt, statt dass ein zweiter
        daneben entsteht - zwei aneinanderliegende Abschnitte waeren
        derselbe Strang, wuerden aber als zwei Bloecke gezeichnet.
        """
        if not self.passt or not self.kabel.abschnitte:
            return False
        # Mit einer Luecke in der Zaehlung des Kabels waere das Wachsen
        # falsch: die neuen Doppeladern gehoeren in die Luecke, nicht
        # hinter die letzte - auch wenn die Stelle in der Leiste anschliesst.
        if not self.kabel.lueckenlos:
            return False
        letzter = self.kabel.abschnitte[-1]
        return (
            self.leiste == letzter.leiste
            and self.start_da == letzter.end_da + 1
        )


def platz_frei(
    verteiler: Verteiler,
    leiste: int,
    start_da: int,
    anzahl: int,
    vergeben: set[tuple[int, int]] | None = None,
) -> bool:
    """Liegt dieses Stueck Leiste ganz frei?

    ``vergeben`` sind Plaetze, die noch kein Kabel belegt, die aber
    schon einem Rest zugedacht sind - beim Planen die der vorigen
    Zeilen, im Dialog die der anderen. Ohne sie schickte ein Plan zwei
    Reste auf dieselben Doppeladern.

    Dieselbe Regel gilt fuer den Vorschlag des Programms und fuer eine
    von Hand gewaehlte Stelle: sonst lehnte der Dialog ab, was das
    Auflegen hinnimmt, oder umgekehrt.
    """
    if anzahl < 1 or start_da < 1:
        return False
    try:
        laenge = verteiler.leiste(leiste).da_anzahl
    except ModellFehler:
        return False
    if start_da + anzahl - 1 > laenge:
        return False
    schon = vergeben or set()
    return all(
        verteiler.kabel_an(leiste, start_da + i) is None
        and (leiste, start_da + i) not in schon
        for i in range(anzahl)
    )


def restleitungen_planen(verteiler: Verteiler) -> list[Restplatz]:
    """Sagt fuer jede gekuerzte Leitung, wo ihr Rest aufliegen koennte.

    Geplant wird in der Reihenfolge, in der die Leitungen am Verteiler
    liegen, und **ohne etwas zu aendern**: erst wenn der Plan angenommen
    ist, wird aufgelegt. Jeder vergebene Platz gilt dabei als besetzt,
    sonst schickte der Plan zwei Reste auf dieselben Doppeladern.

    Gesucht wird in **zwei Durchgaengen**: erst bekommt jede Leitung den
    Platz unmittelbar hinter sich, falls er frei ist - dort gehoert ihre
    Fortsetzung hin -, und nur was so nicht unterkommt, nimmt danach das
    erste freie Stueck. Andernfalls nahm die erste Leitung der zweiten
    ihre eigene Fortsetzung weg, bloss weil sie weiter vorne liegt.
    Zerteilt wird ein Rest nicht: ein Strang, der ueber drei Leisten
    verstreut liegt, ist auf dem Blatt nicht mehr zu verfolgen.
    """
    vergeben: set[tuple[int, int]] = set()

    def passt_ab(leiste: int, start_da: int, anzahl: int) -> bool:
        return platz_frei(verteiler, leiste, start_da, anzahl, vergeben)

    def belegen(leiste: int, start_da: int, anzahl: int) -> None:
        vergeben.update((leiste, start_da + i) for i in range(anzahl))

    def hinter(kabel: Kabel) -> tuple[int, int] | None:
        """Der Platz gleich hinter der Leitung - oder nichts."""
        if not kabel.abschnitte:
            return None
        letzter = kabel.abschnitte[-1]
        return letzter.leiste, letzter.end_da + 1

    gekuerzte = [
        (kabel, (kabel.da_gesamt or 0) - kabel.da_aufgelegt)
        for kabel in sorted(verteiler.kabel, key=_kabellage)
        if kabel.gekuerzt
    ]

    # Erster Durchgang: die eigene Fortsetzung.
    gefunden: dict[int, tuple[int, int]] = {}
    for kabel, rest in gekuerzte:
        anschluss = hinter(kabel)
        if anschluss and passt_ab(anschluss[0], anschluss[1], rest):
            gefunden[id(kabel)] = anschluss
            belegen(anschluss[0], anschluss[1], rest)

    # Zweiter Durchgang: das erste freie Stueck, das den Rest ganz traegt.
    for kabel, rest in gekuerzte:
        if id(kabel) in gefunden:
            continue
        for leiste in verteiler.alle_leisten:
            for start_da in range(1, leiste.da_anzahl + 1):
                if passt_ab(leiste.nummer, start_da, rest):
                    gefunden[id(kabel)] = (leiste.nummer, start_da)
                    belegen(leiste.nummer, start_da, rest)
                    break
            if id(kabel) in gefunden:
                break

    return [
        Restplatz(kabel, rest, *gefunden.get(id(kabel), (None, None)))
        for kabel, rest in gekuerzte
    ]


def _kabellage(kabel: Kabel) -> tuple[int, int]:
    """Wo eine Leitung am Verteiler anfaengt - zum Sortieren."""
    if not kabel.abschnitte:
        return (0, 0)
    erster = kabel.abschnitte[0]
    return (erster.leiste, erster.start_da)


def restplaetze_auflegen(
    verteiler: Verteiler, plan: list[Restplatz]
) -> list[Restplatz]:
    """Legt die geplanten Reste auf; gibt zurueck, was aufgelegt wurde.

    Uebergangen wird, was keinen Platz hat und was inzwischen nicht mehr
    gekuerzt ist. Ein Platz, der sich zwischen Planen und Auflegen
    belegt hat, wird gemeldet (``ModellFehler``) - stillschweigend
    daneben zu legen waere schlimmer.
    """
    aufgelegt: list[Restplatz] = []
    for platz in plan:
        if not platz.passt or not platz.kabel.gekuerzt:
            continue
        if platz.fortsetzung:
            verteiler.kabel_auflegen_aendern(
                platz.kabel, platz.kabel.da_aufgelegt + platz.rest
            )
        else:
            verteiler.kabel_verlaengern(
                platz.kabel, platz.leiste, platz.start_da, platz.rest
            )
        aufgelegt.append(platz)
    return aufgelegt


# --------------------------------------------------------------------------
# Rangierungen als Text
# --------------------------------------------------------------------------


def adressen_lesen(text: str) -> list[Aderadresse]:
    """Liest ein Rangierungsfeld - eine oder zwei Adressen.

    Erlaubt ist, was der Anwender tippt: "3 2a" oder "3 2a   5 4a",
    in jeder Schreibweise - "L3-2a" meint dieselbe Ader.
    """
    if not text or not text.strip():
        return []
    treffer = _ADRESSE_IM_TEXT.findall(text)
    if not treffer:
        raise ModellFehler(
            u("Rangierung {0!r} nicht lesbar - erwartet wird z.B. '3 2a', 'L3 2a' oder 'L3-2a'").format(text.strip())
        )
    # Alles, was nicht zu einer Adresse gehoert, waere ein Tippfehler.
    rest = _ADRESSE_IM_TEXT.sub("", text).strip()
    if rest:
        raise ModellFehler(u("In der Rangierung steht ueberzaehliger Text: {0!r}").format(rest))
    return [
        Aderadresse(leistennummer(leiste), int(stift), seite.lower())
        for leiste, stift, seite in treffer
    ]


def mehrzahl(zahl: int, eins: str, viele: str) -> str:
    """Zahl mit dem passenden Hauptwort: "1 Bucht", aber "2 Buchten".

    Ein Verteiler mit einer einzigen Bucht las sich sonst als "1 Buchten"
    - richtig gerechnet, falsch geschrieben.

    Beide Woerter gehen durch die Uebersetzung: so muss keine der
    vielen Aufrufstellen etwas davon wissen, und im Katalog stehen die
    Woerter einzeln - "Leiste" und "Leisten", nicht jeder Satz, in dem
    sie vorkommen.
    """
    return f"{zahl} {u(eins) if zahl == 1 else u(viele)}"


def adressen_schreiben(
    adressen: list[Aderadresse],
    schreibweise: Schreibweise | None = None,
    leisten: str = LEISTEN_ZAHLEN,
) -> str:
    """Stellt Rangierungen fuer die Anzeige zusammen."""
    return RANGIERUNG_TRENNER.join(
        a.anzeige(schreibweise, leisten) for a in adressen
    )


# --------------------------------------------------------------------------
# Projekt
# --------------------------------------------------------------------------

BRIEFKOPF_FELDER = (
    "firma",
    "kunde",
    "anlagennummer",
    "kundennummer",
    "gezeichnet_am",
    "gezeichnet_von",
    "kuerzel",
    "erstellt_am",
    "erstellt_von",
    "stand_am",
    "stand_von",
    "geprueft_am",
    "geprueft_von",
    "dokumenttitel",
)

#: Die Felder, in denen ein Datum steht - am Namen zu erkennen. Wer ein
#: weiteres Datumsfeld einfuehrt, nennt es ebenso ``*_am``.
DATUMSFELDER = tuple(name for name in BRIEFKOPF_FELDER if name.endswith("_am"))

BRIEFKOPF_BESCHRIFTUNG = {
    "dokumenttitel": "Dokumenttitel",
    "firma": "Firma",
    "kunde": "Kunde",
    "anlagennummer": "Anlagennummer",
    "kundennummer": "Kundennummer",
    "gezeichnet_am": "Gezeichnet am",
    "gezeichnet_von": "Gezeichnet von",
    "kuerzel": "Kürzel",
    "erstellt_am": "Erstellt am",
    "erstellt_von": "Erstellt von",
    "stand_am": "Stand am",
    "stand_von": "Stand von",
    "geprueft_am": "Geprüft am",
    "geprueft_von": "Geprüft von",
}


# Wie die Zeilen des Schriftfeldes auf dem Blatt heissen.
# Anders als BRIEFKOPF_BESCHRIFTUNG, das die Felder im Dialog benennt:
# auf dem Blatt ist es enger, dort steht "Anlage" statt "Anlagennummer"
# und ein Paar aus Datum und Name teilt sich eine Beschriftung. Wem die
# Woerter nicht passen, der aendert sie im Projektdatendialog; die
# Vorgabe steht hier.
BLATTBESCHRIFTUNG = {
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


# Die drei Blattarten - auf jeder koennen die eigenen Felder stehen
# oder eben nicht.
BLATTARTEN = ("deckblatt", "belegung", "leisten")
BLATTART_BESCHRIFTUNG = {
    "deckblatt": "Deckblatt",
    "belegung": "Verteilerbelegung",
    "leisten": "Leistenblättern",
}
# Dieselben Blattarten, wie sie fuer sich heissen - die Beschriftung oben
# steht im Dativ ("eigene Felder auf Leistenblaettern").
BLATTART_NAMEN = {
    "deckblatt": "Deckblatt",
    "belegung": "Verteilerbelegung",
    "leisten": "Leistenblätter",
}


@dataclass
class Projekt:
    """Stammdaten und Verteiler einer Dokumentation.

    Die Projektdaten stehen einmal zentral und werden auf jedem Blatt
    eingesetzt; eigene Felder ergaenzen ihn frei.
    """

    verteiler: Verteiler = field(default_factory=Verteiler)
    briefkopf: dict[str, str] = field(default_factory=dict)
    # Die Inhalte der eigenen Felder. **Welche** es gibt und auf welchen
    # Blattarten sie stehen, sagt die Blattvorlage - hier steht nur, was
    # darin steht. Ein Wert zu einem Namen, den keine Vorlage mehr kennt,
    # bleibt erhalten: eine andere Vorlage kann ihn wieder brauchen.
    eigene_felder: dict[str, str] = field(default_factory=dict)
    # Felder, die auf den Blaettern nicht erscheinen sollen. Der Inhalt
    # bleibt erhalten - abwaehlen ist kein Loeschen.
    ausgeblendet: set[str] = field(default_factory=set)
    # Eigene Woerter fuer die Zeilen des Schriftfeldes. Nur was
    # abweicht, steht drin - der Rest kommt aus BLATTBESCHRIFTUNG.
    beschriftungen: dict[str, str] = field(default_factory=dict)
    # Wie Rangierungen geschrieben werden. Eine Anzeigesache: die
    # Projektdatei haelt Adressen immer in der Grundform fest.
    rangierung_schreibweise: str = schreibweisen.STANDARD.id
    # Ob am gekuerzten Kabel steht, wie viel von ihm aufliegt. Ebenfalls
    # eine Anzeigesache - dass es gekuerzt ist, steht am Kabel selbst
    # (da_gesamt), und die Datenlisten fuehren es weiter.
    kuerzung_zeigen: bool = True
    # Wie die Leisten heissen - gezaehlt oder mit Buchstaben. Ebenfalls
    # eine Anzeigesache; im Modell traegt jede Leiste ihre Nummer.
    leisten_schreibweise: str = LEISTEN_ZAHLEN
    # Ob die Verteilerbelegung von rechts nach links zu lesen ist. Eine
    # Eigenschaft der Anlage: an manchem Verteiler wird von rechts
    # aufgelegt, und das Blatt soll aussehen wie das Gerät davor. Nur das
    # Blattbild der Belegung dreht sich - DA 1 bleibt DA 1 und steht in
    # Leistenblatt, Datenliste und Adresse unveraendert.
    belegung_umgekehrt: bool = False

    def beschriftung(self, marke: str) -> str:
        """Wie eine Zeile des Schriftfeldes ueberschrieben ist."""
        eigen = self.beschriftungen.get(marke, "").strip()
        return eigen or BLATTBESCHRIFTUNG.get(marke, marke)

    def eigene_beschriftungen(self) -> dict[str, str]:
        """Nur die Woerter, die von der Vorgabe abweichen."""
        return {
            marke: wert.strip()
            for marke, wert in self.beschriftungen.items()
            if wert.strip() and wert.strip() != BLATTBESCHRIFTUNG.get(marke, marke)
        }

    @property
    def schreibweise(self) -> Schreibweise:
        return schreibweisen.holen(self.rangierung_schreibweise)

    def leistenname(self, nummer: int) -> str:
        """Wie diese Leiste in diesem Projekt heisst: "3" oder "C"."""
        return leistenname(nummer, self.leisten_schreibweise)

    def feld(self, name: str, vorgabe: str = "") -> str:
        if name in self.briefkopf:
            return self.briefkopf[name]
        return self.eigene_felder.get(name, vorgabe)

    def sichtbar(self, name: str) -> bool:
        """Soll dieses Feld auf den Blaettern erscheinen?"""
        return name not in self.ausgeblendet

    def sichtbarkeit_setzen(self, name: str, an: bool) -> None:
        if an:
            self.ausgeblendet.discard(name)
        else:
            self.ausgeblendet.add(name)

    def anzeigewert(self, name: str, vorgabe: str = "") -> str:
        """Der Wert, sofern das Feld sichtbar ist - sonst nichts."""
        return self.feld(name, vorgabe) if self.sichtbar(name) else ""

    def sichtbare_eigene_felder(self) -> dict[str, str]:
        return {
            name: wert
            for name, wert in self.eigene_felder.items()
            if self.sichtbar(name)
        }

    def eigene_felder_hier(
        self, blattart: str, vorlage=None
    ) -> list[tuple[str, str]]:
        """Die eigenen Felder dieses Blattes - Namen aus der Blattvorlage.

        Die Vorlage sagt, welche Zeilen es gibt und in welcher Reihenfolge;
        gezeigt wird auch eine **leere** Zeile, denn ein Schriftfeld darf
        zum Ausfuellen von Hand danebenstehen. Ohne Vorlage - etwa in einer
        Datenliste, die kein Blatt zeichnet - steht, was das Projekt hat.
        """
        if vorlage is None:
            return list(self.sichtbare_eigene_felder().items())
        if blattart not in tuple(vorlage.eigene_felder_auf):
            return []
        return [
            (name, self.eigene_felder.get(name, ""))
            for name in vorlage.eigene_felder
            if self.sichtbar(name)
        ]
