"""Datenmodell eines LSA+-Verteilers.

Ein Verteiler besteht aus Buchten,
eine Bucht aus Leisten, eine Leiste aus Stiften, ein Stift aus den beiden
Adern a und b. Kabel und Rangierungen liegen quer dazu und haengen am
Verteiler, nicht an der einzelnen Ader.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import schreibweisen
from .schreibweisen import Schreibweise

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

# Gelesen wird jede Schreibweise: "3 2a", "L3 2a" und "L3-2a"
# meinen dieselbe Ader. Das L ist ein Zierat, der Strich ein Trenner wie
# der Abstand.
_ADRESSMUSTER = r"[Ll]?\s*(\d+)\s*(?:-|\s+)\s*(\d+)\s*([ab])"
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
            raise ModellFehler(f"Unbekannte Aderseite: {self.seite!r}")

    @classmethod
    def parse(cls, text: str) -> Aderadresse:
        treffer = _ADRESSE.match(text)
        if not treffer:
            raise ModellFehler(
                f"Rangierung {text!r} nicht lesbar - erwartet wird "
                "z.B. '3 2a', 'L3 2a' oder 'L3-2a'"
            )
        leiste, stift, seite = treffer.groups()
        return cls(int(leiste), int(stift), seite.lower())

    def __str__(self) -> str:
        return f"{self.leiste} {self.stift}{self.seite}"

    def anzeige(self, schreibweise: Schreibweise | None = None) -> str:
        """Die Adresse in der eingestellten Schreibweise."""
        weise = schreibweise or schreibweisen.STANDARD
        return weise.schreiben(self.leiste, self.stift, self.seite)


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
            raise ModellFehler(f"Unbekannte Ausrichtung: {self.ausrichtung!r}")

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
                f"Der Anteil des zweiten Feldes muss zwischen {ANTEIL_MIN} "
                f"und {ANTEIL_MAX} Prozent liegen, nicht {self.anteil}"
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
            raise ModellFehler(f"{feld!r} laesst sich nicht teilen")
        if teilung.leer:
            self.teilungen.pop(feld, None)
        else:
            self.teilungen[feld] = teilung

    def stil_setzen(self, feld: str, stil: Textstil) -> None:
        """Setzt den Stil einer Spalte; ein leerer wird geloescht."""
        if feld not in STILFELDER:
            raise ModellFehler(f"Fuer {feld!r} gibt es keinen Textstil")
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

    def kabel_auflegen_aendern(self, kabel: Kabel, anzahl_da: int) -> None:
        """Aendert, wie viele Doppeladern eines Kabels aufliegen.

        Gewachsen und geschrumpft wird am Ende: der Anfang bleibt, wo er
        ist, denn dort haengt das Kabel. Passt die Verlaengerung nicht auf
        die Leiste, wird ``UeberlaufFehler`` ausgeloest - die Oberflaeche
        fragt dann wie beim Auflegen, ob fortgesetzt wird oder der Rest
        verfaellt.
        """
        if anzahl_da < 1:
            raise ModellFehler("Ein Kabel muss mindestens eine Doppelader haben")
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
        letzter.anzahl_da += zusatz
        if kabel.da_gesamt is not None and kabel.da_gesamt < kabel.da_aufgelegt:
            kabel.da_gesamt = kabel.da_aufgelegt

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
                f"Auf Leiste {leiste} ab DA {start_da} passen nur {passend} "
                f"von {anzahl_da} DA"
            )
        kabel.abschnitte.append(Kabelabschnitt(leiste, start_da, anzahl_da))
        if kabel.da_gesamt is not None and kabel.da_gesamt < kabel.da_aufgelegt:
            kabel.da_gesamt = kabel.da_aufgelegt

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
                f"{adresse} traegt bereits {MAX_RANGIERUNGEN_JE_ADER} "
                "Rangierungen - fuer einen Vermerk ist kein Feld frei"
            )
        ader = self.ader(adresse)
        ader.vermerk = text
        ader.vermerk_zuerst = bool(text) and zuerst

    def rangiereintraege(
        self, adresse: Aderadresse, schreibweise: Schreibweise | None = None
    ) -> list[str]:
        """Was im Rangierfeld dieser Ader steht: Ziele und Vermerk.

        In der Folge, in der es eingetragen wurde - die Felder tauschen
        die Plaetze nicht.
        """
        eintraege = [ziel.anzeige(schreibweise) for ziel in self.ziele_von(adresse)]
        ader = self.ader(adresse)
        if ader.vermerk:
            eintraege.insert(0 if ader.vermerk_zuerst else len(eintraege), ader.vermerk)
        return eintraege

    def rangierfeld(
        self, adresse: Aderadresse, schreibweise: Schreibweise | None = None
    ) -> str:
        """Der ganze Inhalt des Rangierfeldes als eine Zeile."""
        return RANGIERUNG_TRENNER.join(self.rangiereintraege(adresse, schreibweise))


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
            f"Rangierung {text.strip()!r} nicht lesbar - erwartet wird "
            "z.B. '3 2a', 'L3 2a' oder 'L3-2a'"
        )
    # Alles, was nicht zu einer Adresse gehoert, waere ein Tippfehler.
    rest = _ADRESSE_IM_TEXT.sub("", text).strip()
    if rest:
        raise ModellFehler(f"In der Rangierung steht ueberzaehliger Text: {rest!r}")
    return [
        Aderadresse(int(leiste), int(stift), seite.lower())
        for leiste, stift, seite in treffer
    ]


def mehrzahl(zahl: int, eins: str, viele: str) -> str:
    """Zahl mit dem passenden Hauptwort: "1 Bucht", aber "2 Buchten".

    Ein Verteiler mit einer einzigen Bucht las sich sonst als "1 Buchten"
    - richtig gerechnet, falsch geschrieben.
    """
    return f"{zahl} {eins if zahl == 1 else viele}"


def adressen_schreiben(
    adressen: list[Aderadresse], schreibweise: Schreibweise | None = None
) -> str:
    """Stellt Rangierungen fuer die Anzeige zusammen."""
    return RANGIERUNG_TRENNER.join(a.anzeige(schreibweise) for a in adressen)


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


@dataclass
class Projekt:
    """Stammdaten und Verteiler einer Dokumentation.

    Die Projektdaten stehen einmal zentral und werden auf jedem Blatt
    eingesetzt; eigene Felder ergaenzen ihn frei.
    """

    verteiler: Verteiler = field(default_factory=Verteiler)
    briefkopf: dict[str, str] = field(default_factory=dict)
    eigene_felder: dict[str, str] = field(default_factory=dict)
    # Felder, die auf den Blaettern nicht erscheinen sollen. Der Inhalt
    # bleibt erhalten - abwaehlen ist kein Loeschen.
    ausgeblendet: set[str] = field(default_factory=set)
    # Auf welchen Blaettern die eigenen Felder erscheinen. Ohne
    # Angabe auf allen - wer eines nicht will, nimmt es heraus.
    eigene_felder_auf: set[str] = field(default_factory=lambda: set(BLATTARTEN))
    # Eigene Woerter fuer die Zeilen des Schriftfeldes. Nur was
    # abweicht, steht drin - der Rest kommt aus BLATTBESCHRIFTUNG.
    beschriftungen: dict[str, str] = field(default_factory=dict)
    # Wie Rangierungen geschrieben werden. Eine Anzeigesache: die
    # Projektdatei haelt Adressen immer in der Grundform fest.
    rangierung_schreibweise: str = schreibweisen.STANDARD.id

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

    def eigene_felder_hier(self, blattart: str) -> dict[str, str]:
        """Die eigenen Felder, sofern sie auf dieses Blatt gehoeren."""
        if blattart not in self.eigene_felder_auf:
            return {}
        return self.sichtbare_eigene_felder()
