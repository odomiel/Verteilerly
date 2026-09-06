"""Datenmodell eines LSA+-Verteilers.

Ein Verteiler besteht aus Buchten,
eine Bucht aus Leisten, eine Leiste aus Stiften, ein Stift aus den beiden
Adern a und b. Kabel und Rangierungen liegen quer dazu und haengen am
Verteiler, nicht an der einzelnen Ader.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SEITEN = ("a", "b")


class ModellFehler(Exception):
    """Fachlicher Fehler im Datenmodell."""


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

_ADRESSE = re.compile(r"^\s*(\d+)\s+(\d+)\s*([ab])\s*$", re.IGNORECASE)
_ADRESSE_IM_TEXT = re.compile(r"(\d+)\s+(\d+)\s*([ab])", re.IGNORECASE)

# Zwei Rangierungen stehen nebeneinander ohne Trennzeichen,
# allein durch Abstand getrennt.
RANGIERUNG_TRENNER = "   "


@dataclass(frozen=True, order=True)
class Aderadresse:
    """Zeigt auf genau eine Ader im Verteiler.

    Schreibweise: "<Leiste> <Stift><Ader>", also "3 2a".
    """

    leiste: int
    stift: int
    seite: str

    def __post_init__(self) -> None:
        if self.seite not in SEITEN:
            raise ModellFehler(f"Unbekannte Aderseite: {self.seite!r}")

    @classmethod
    def parse(cls, text: str) -> Aderadresse:
        treffer = _ADRESSE.match(text)
        if not treffer:
            raise ModellFehler(
                f"Rangierung {text!r} nicht lesbar - erwartet wird z.B. '3 2a'"
            )
        leiste, stift, seite = treffer.groups()
        return cls(int(leiste), int(stift), seite.lower())

    def __str__(self) -> str:
        return f"{self.leiste} {self.stift}{self.seite}"


# --------------------------------------------------------------------------
# Verteileraufbau
# --------------------------------------------------------------------------


@dataclass
class Ader:
    """Eine Ader mit ihren vier Feldern.

    Die Rangierung steht bewusst nicht hier: sie ist ein eigenes Objekt am
    Verteiler, damit beide Enden nicht auseinanderlaufen koennen.
    """

    seite: str
    farbe: str = ""
    bezeichnung: str = ""
    bemerkung: str = ""


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
        raise ModellFehler(f"Unbekannte Aderseite: {seite!r}")


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
                f"Leiste {self.nummer} hat {self.da_anzahl} DA, "
                f"Stift {nummer} gibt es dort nicht"
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
    """Ein zusammenhaengendes Stueck eines Kabels auf einer Leiste."""

    leiste: int
    start_da: int
    anzahl_da: int

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

    def positionen(self) -> list[tuple[int, int, int]]:
        """(Kabel-DA, Leiste, Leisten-DA) fuer jede aufgelegte Doppelader.

        Die Kabel-DA zaehlt ueber alle Abschnitte durch und bestimmt damit
        die Adernfarbe.
        """
        ergebnis: list[tuple[int, int, int]] = []
        kabel_da = 1
        for abschnitt in self.abschnitte:
            for versatz in range(abschnitt.anzahl_da):
                ergebnis.append(
                    (kabel_da, abschnitt.leiste, abschnitt.start_da + versatz)
                )
                kabel_da += 1
        return ergebnis


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
            raise ModellFehler("Buchten, Leisten und DA muessen mindestens 1 sein")

        aufbau: list[Bucht] = []
        naechste_leiste = 1
        for buchten_nr in range(1, buchten + 1):
            leisten = []
            for _ in range(leisten_je_bucht):
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
        raise ModellFehler(f"Leiste {nummer} gibt es in diesem Verteiler nicht")

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
            raise ModellFehler("Ein Kabel muss mindestens eine Doppelader haben")
        ziel = self.leiste(leiste)
        if not 1 <= start_da <= ziel.da_anzahl:
            raise ModellFehler(
                f"Start-DA {start_da} liegt ausserhalb von Leiste {leiste} "
                f"({ziel.da_anzahl} DA)"
            )

        passend = 0
        for versatz in range(anzahl_da):
            da = start_da + versatz
            if da > ziel.da_anzahl:
                break
            if self.kabel_an(leiste, da) is not None:
                raise ModellFehler(
                    f"Leiste {leiste} DA {da} ist bereits von einem Kabel belegt"
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
            raise ModellFehler("Ein Kabel braucht mindestens einen Abschnitt")

        for abschnitt in abschnitte:
            passend, rest = self.platz_pruefen(
                abschnitt.leiste, abschnitt.start_da, abschnitt.anzahl_da
            )
            if rest:
                raise ModellFehler(
                    f"Abschnitt auf Leiste {abschnitt.leiste} ab DA "
                    f"{abschnitt.start_da} passt nicht ({rest} DA zu viel)"
                )

        aufgelegt = sum(a.anzahl_da for a in abschnitte)
        if da_gesamt is not None and da_gesamt < aufgelegt:
            raise ModellFehler(
                f"Das Kabel hat {da_gesamt} DA, aufgelegt werden sollen {aufgelegt}"
            )

        kabel = Kabel(
            beschriftung=beschriftung,
            abschnitte=list(abschnitte),
            kabeltyp=kabeltyp,
            da_gesamt=da_gesamt if da_gesamt is not None else aufgelegt,
        )
        self.kabel.append(kabel)
        return kabel

    def kabel_entfernen(self, kabel: Kabel) -> None:
        self.kabel.remove(kabel)

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
            raise ModellFehler(f"Eine Rangierung kann nicht auf sich selbst zeigen ({von})")

        for adresse in (von, nach):
            if not self.kennt(adresse):
                raise ModellFehler(f"{adresse} gibt es in diesem Verteiler nicht")

        for bestehend in self.rangierungen:
            if bestehend.beruehrt(von) and bestehend.beruehrt(nach):
                raise ModellFehler(f"Die Rangierung {von} - {nach} besteht bereits")

        for adresse in (von, nach):
            belegt = len(self.rangierungen_an(adresse))
            if belegt >= MAX_RANGIERUNGEN_JE_ADER:
                raise ModellFehler(
                    f"{adresse} traegt bereits {belegt} Rangierungen - "
                    f"mehr als {MAX_RANGIERUNGEN_JE_ADER} sind nicht vorgesehen"
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
        raise ModellFehler(f"Die Rangierung {von} - {nach} gibt es nicht")


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
                f"{adresse} kann hoechstens {MAX_RANGIERUNGEN_JE_ADER} "
                f"Rangierungen tragen, angegeben sind {len(ziele)}"
            )
        if len(set(ziele)) != len(ziele):
            raise ModellFehler("Dieselbe Gegenstelle ist zweimal angegeben")

        bisher = self.ziele_von(adresse)

        # Vorpruefung auf einer Kopie, damit nichts halb angewandt wird.
        # Erst fliegen alle Rangierungen dieser Ader heraus, dann kommen
        # sie in der angegebenen Folge zurueck - so bleibt die Reihenfolge
        # die des Anwenders.
        probe = [r for r in self.rangierungen if not r.beruehrt(adresse)]
        for ziel in ziele:
            if ziel == adresse:
                raise ModellFehler(
                    f"Eine Rangierung kann nicht auf sich selbst zeigen ({ziel})"
                )
            if not self.kennt(ziel):
                raise ModellFehler(f"{ziel} gibt es in diesem Verteiler nicht")
            # Die eigenen sind oben herausgenommen und zaehlen nicht mit.
            belegt = sum(1 for r in probe if r.beruehrt(ziel))
            if belegt >= MAX_RANGIERUNGEN_JE_ADER:
                raise ModellFehler(
                    f"{ziel} traegt bereits {belegt} Rangierungen - "
                    f"mehr als {MAX_RANGIERUNGEN_JE_ADER} sind nicht vorgesehen"
                )
            probe.append(Rangierung(adresse, ziel))

        self.rangierungen = probe


# --------------------------------------------------------------------------
# Rangierungen als Text
# --------------------------------------------------------------------------


def adressen_lesen(text: str) -> list[Aderadresse]:
    """Liest ein Rangierungsfeld - eine oder zwei Adressen.

    Erlaubt ist, was der Anwender tippt: "3 2a" oder "3 2a   5 4a".
    """
    if not text or not text.strip():
        return []
    treffer = _ADRESSE_IM_TEXT.findall(text)
    if not treffer:
        raise ModellFehler(
            f"Rangierung {text.strip()!r} nicht lesbar - erwartet wird z.B. '3 2a'"
        )
    # Alles, was nicht zu einer Adresse gehoert, waere ein Tippfehler.
    rest = _ADRESSE_IM_TEXT.sub("", text).strip()
    if rest:
        raise ModellFehler(f"In der Rangierung steht ueberzaehliger Text: {rest!r}")
    return [
        Aderadresse(int(leiste), int(stift), seite.lower())
        for leiste, stift, seite in treffer
    ]


def adressen_schreiben(adressen: list[Aderadresse]) -> str:
    """Stellt Rangierungen fuer die Anzeige zusammen."""
    return RANGIERUNG_TRENNER.join(str(a) for a in adressen)


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


@dataclass
class Projekt:
    """Stammdaten und Verteiler einer Dokumentation.

    Der Briefkopf steht einmal zentral und wird auf jedem Blatt
    eingesetzt; eigene Felder ergaenzen ihn frei.
    """

    verteiler: Verteiler = field(default_factory=Verteiler)
    briefkopf: dict[str, str] = field(default_factory=dict)
    eigene_felder: dict[str, str] = field(default_factory=dict)
    # Felder, die auf den Blaettern nicht erscheinen sollen. Der Inhalt
    # bleibt erhalten - abwaehlen ist kein Loeschen.
    ausgeblendet: set[str] = field(default_factory=set)

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
