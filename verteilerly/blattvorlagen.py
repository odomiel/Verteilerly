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

import pathlib
from dataclasses import dataclass, field, replace

import yaml

from .modell import ModellFehler

LINKS, MITTE, RECHTS = "links", "mitte", "rechts"
AUSRICHTUNGEN = (LINKS, MITTE, RECHTS)

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

# Was im Schriftfeld stehen kann. „eigene“ steht fuer alle eigenen Felder.
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
    "eigene",
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


STANDARDSPALTEN = (
    Spalte("stift", "Stift", 10.0, MITTE),
    Spalte("ader", "", 7.0, MITTE),
    Spalte("farbe", "Farbe", 16.0),
    Spalte("bezeichnung", "Bezeichnung", 46.0),
    Spalte("rangierung", "Rangierung", 30.0),
    Spalte("bemerkung", "Bemerkung", 44.0),
    Spalte("kabel", "Kabel", 33.0),
)

STANDARDSCHRIFTFELD = (
    ("firma", "kunde", "anlagennummer", "kundennummer"),
    ("verteiler", "verteilernummer", "leiste", "blatt"),
    ("erstellt", "stand", "geprueft", "gezeichnet", "eigene"),
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
    schriftfeld: tuple[tuple[str, ...], ...] = STANDARDSCHRIFTFELD

    buchten_je_blatt: int = 2
    da_nummern: bool = True
    # Die Rangierspalte in zwei gleich grosse Felder teilen - je eines
    # fuer eine Rangierung. Die Ueberschrift bleibt ganz.
    rangierung_geteilt: bool = True
    zelle_breite: float = 6.0
    zelle_hoehe: float = 9.0
    leistenlabel: float = 14.0
    abstand_leisten: float = 3.0
    abstand_buchten: float = 12.0

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
        raise BlattvorlagenFehler(f"{herkunft}: {name} ist keine Zahl") from None


def _spalten_aus_yaml(eintraege, herkunft: str) -> tuple[Spalte, ...]:
    spalten = []
    for eintrag in eintraege:
        if isinstance(eintrag, str):
            eintrag = {"feld": eintrag}
        feld = str(eintrag.get("feld", "")).strip()
        if feld not in SPALTENFELDER:
            bekannt = ", ".join(SPALTENFELDER)
            raise BlattvorlagenFehler(
                f"{herkunft}: Spalte {feld!r} gibt es nicht (bekannt: {bekannt})"
            )
        ausrichtung = str(eintrag.get("ausrichtung", LINKS))
        if ausrichtung not in AUSRICHTUNGEN:
            raise BlattvorlagenFehler(
                f"{herkunft}: Ausrichtung {ausrichtung!r} gibt es nicht"
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
        raise BlattvorlagenFehler(f"{herkunft}: kein einziges Feld im Leistenblatt")
    return tuple(spalten)


def _schriftfeld_aus_yaml(eintraege, herkunft: str) -> tuple[tuple[str, ...], ...]:
    spalten = []
    for spalte in eintraege:
        marken = []
        for marke in spalte:
            marke = str(marke).strip()
            if marke not in SCHRIFTFELDMARKEN:
                bekannt = ", ".join(SCHRIFTFELDMARKEN)
                raise BlattvorlagenFehler(
                    f"{herkunft}: {marke!r} gehört nicht ins Schriftfeld "
                    f"(bekannt: {bekannt})"
                )
            marken.append(marke)
        spalten.append(tuple(marken))
    if not spalten:
        raise BlattvorlagenFehler(f"{herkunft}: leeres Schriftfeld")
    return tuple(spalten)


def blattvorlage_aus_yaml(inhalt: dict, herkunft: str = "") -> Blattvorlage:
    """Liest eine Blattvorlage; alles Weggelassene bleibt beim Standard."""
    wo = herkunft or "Blattvorlage"
    for feld in ("id", "name"):
        if not str(inhalt.get(feld, "")).strip():
            raise BlattvorlagenFehler(f"{wo}: Blattvorlage ohne {feld}")

    schrift = inhalt.get("schrift") or {}
    belegung = inhalt.get("belegung") or {}

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
            _spalten_aus_yaml(inhalt["spalten"], wo)
            if inhalt.get("spalten")
            else STANDARD.spalten
        ),
        schriftfeld=(
            _schriftfeld_aus_yaml(inhalt["schriftfeld"], wo)
            if inhalt.get("schriftfeld")
            else STANDARD.schriftfeld
        ),
        buchten_je_blatt=int(
            _zahl(inhalt, "buchten_je_blatt", STANDARD.buchten_je_blatt, wo)
        ),
        da_nummern=bool(inhalt.get("da_nummern", STANDARD.da_nummern)),
        rangierung_geteilt=bool(
            inhalt.get("rangierung_geteilt", STANDARD.rangierung_geteilt)
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
    )
    if vorlage.buchten_je_blatt < 1:
        raise BlattvorlagenFehler(f"{wo}: buchten_je_blatt muss mindestens 1 sein")
    if vorlage.rand < 0 or vorlage.zeilenhoehe_min <= 0:
        raise BlattvorlagenFehler(f"{wo}: Rand und Zeilenhöhe müssen positiv sein")
    return vorlage


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
    def aus_ordnern(cls, ordner) -> Blattvorlagen:
        """Aus mehreren Ordnern; bei gleicher Kennung gilt der letzte."""
        gefunden: list[Blattvorlage] = []
        for ort in ordner:
            ort = pathlib.Path(ort)
            if ort.is_dir():
                gefunden += cls.laden(ort).alle
        return cls(gefunden)

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
                f"Blattvorlage {kennung!r} gibt es nicht (bekannt: {bekannt})"
            ) from None

    @property
    def standard(self) -> Blattvorlage:
        for vorlage in self.alle:
            if vorlage.standard:
                return vorlage
        return self.alle[0]
