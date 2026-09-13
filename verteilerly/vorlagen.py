"""Verteilervorlagen.

Eine Vorlage ist im Regelfall nichts weiter als die drei Kennzahlen
Buchten, Leisten je Bucht und DA je Leiste - dazu ein Name. Sie liegt als
YAML-Datei im Vorlagenordner neben dem Programm; eine neue Vorlage
entsteht durch Ablegen einer Datei, ohne dass am Programm etwas zu
aendern ist.

Ungleich besetzte Verteiler brauchen mehr als drei Zahlen. Dafuer traegt
``buchten`` statt einer Zahl eine Liste, eine Zeile je Bucht:

    buchten:
      - {leisten: 4, da: 10}
      - {leisten: 2, da: 20}

Beides steht im selben Feld, weil beides dasselbe meint: die Buchten.
Aeltere Dateien mit den drei Zahlen werden unveraendert weiter gelesen.
"""

from __future__ import annotations

import datetime
import pathlib
import re
import unicodedata
from dataclasses import dataclass, replace

import yaml

from .modell import ModellFehler, Verteiler


class VorlagenFehler(ModellFehler):
    """Eine Vorlagendatei ist unvollstaendig oder unbrauchbar."""


@dataclass(frozen=True)
class Vorlage:
    """Die Grundstruktur eines Verteilers."""

    id: str
    name: str
    buchten: int
    leisten_je_bucht: int
    da_je_leiste: int
    beschreibung: str = ""
    standard: bool = False
    # Je Bucht (Leisten, DA je Leiste) - nur bei ungleich besetzten
    # Verteilern gefuellt. Dann gilt er, und die drei Zahlen darueber
    # beschreiben die erste Bucht.
    bauplan: tuple[tuple[int, int], ...] = ()

    @property
    def gleichmaessig(self) -> bool:
        """Laesst sich diese Vorlage mit drei Zahlen beschreiben?"""
        return not self.bauplan or len(set(self.bauplan)) == 1

    @property
    def buchtenplan(self) -> tuple[tuple[int, int], ...]:
        """Je Bucht (Leisten, DA) - auch fuer die gleichmaessige Vorlage."""
        if self.bauplan:
            return self.bauplan
        return ((self.leisten_je_bucht, self.da_je_leiste),) * self.buchten

    @property
    def da_gesamt(self) -> int:
        return sum(leisten * da for leisten, da in self.buchtenplan)

    @property
    def leisten_gesamt(self) -> int:
        return sum(leisten for leisten, _ in self.buchtenplan)

    def verteiler(self, name: str = "", nummer: str = "") -> Verteiler:
        """Baut einen leeren Verteiler nach dieser Vorlage."""
        return Verteiler.aus_buchten(
            list(self.buchtenplan), name=name, nummer=nummer
        )

    def __str__(self) -> str:
        return f"{self.name} ({self.da_gesamt} DA)"

    @classmethod
    def aus_verteiler(
        cls,
        verteiler: Verteiler,
        name: str,
        kennung: str = "",
        beschreibung: str = "",
    ) -> Vorlage:
        """Nimmt die Geometrie eines vorhandenen Verteilers als Vorlage.

        Gleichmaessig besetzt, wird daraus die Vorlage aus drei Zahlen;
        sonst traegt sie den Bauplan je Bucht. Eine Bucht mit
        gemischten Leistengroessen laesst sich dagegen nicht abbilden -
        vorerst hat jede Bucht eine Leistengroesse.
        """
        if not verteiler.buchten:
            raise VorlagenFehler("Der Verteiler hat keine Buchten")

        plan: list[tuple[int, int]] = []
        for bucht in verteiler.buchten:
            groessen = {l.da_anzahl for l in bucht.leisten}
            if len(groessen) > 1:
                raise VorlagenFehler(
                    f"Bucht {bucht.nummer} trägt Leisten verschiedener Größe - "
                    "das lässt sich nicht als Vorlage ablegen"
                )
            plan.append((len(bucht.leisten), groessen.pop()))

        erste = plan[0]
        return cls(
            id=kennung or kennung_bilden(name),
            name=name,
            buchten=len(plan),
            leisten_je_bucht=erste[0],
            da_je_leiste=erste[1],
            beschreibung=beschreibung,
            bauplan=() if len(set(plan)) == 1 else tuple(plan),
        )


ORDNERNAME = "vorlagen"
ENDUNG = ".yaml"
PFLICHTFELDER = ("id", "name", "buchten", "leisten_je_bucht", "da_je_leiste")
# Vor der Umbenennung hiessen die Buchten Reihen - alte Dateien gelten weiter.
FRUEHERE_NAMEN = {"buchten": "reihen", "leisten_je_bucht": "leisten_je_reihe"}


def _feld(inhalt: dict, name: str):
    if name in inhalt:
        return inhalt[name]
    return inhalt.get(FRUEHERE_NAMEN.get(name, name))

_UMLAUTE = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}


def kennung_bilden(name: str) -> str:
    """Aus einem Namen einen brauchbaren Dateinamen machen."""
    text = name.strip().lower()
    for zeichen, ersatz in _UMLAUTE.items():
        text = text.replace(zeichen, ersatz)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(z for z in text if not unicodedata.combining(z))
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "vorlage"


def vorlage_als_yaml(vorlage: Vorlage) -> str:
    """Die Vorlage als Datei, wie sie ein Mensch auch von Hand schriebe."""
    heute = datetime.date.today().strftime("%d.%m.%Y")
    inhalt = {
        "id": vorlage.id,
        "name": vorlage.name,
        "beschreibung": vorlage.beschreibung,
    }
    if vorlage.bauplan:
        # Ungleich besetzt: eine Zeile je Bucht statt dreier Zahlen.
        inhalt["buchten"] = [
            {"leisten": leisten, "da": da} for leisten, da in vorlage.bauplan
        ]
    else:
        inhalt["buchten"] = vorlage.buchten
        inhalt["leisten_je_bucht"] = vorlage.leisten_je_bucht
        inhalt["da_je_leiste"] = vorlage.da_je_leiste
    if vorlage.standard:
        inhalt["standard"] = True
    kopf = (
        f"# Vorlage: {vorlage.leisten_gesamt} Leisten, {vorlage.da_gesamt} DA.\n"
        f"# Von Verteilerly angelegt am {heute}.\n"
    )
    return kopf + yaml.safe_dump(inhalt, allow_unicode=True, sort_keys=False)


def vorlage_speichern(
    vorlage: Vorlage, ordner: pathlib.Path, ueberschreiben: bool = False
) -> pathlib.Path:
    """Legt die Vorlage als YAML-Datei im Vorlagenordner ab."""
    ordner = pathlib.Path(ordner)
    ziel = ordner / f"{vorlage.id}.yaml"
    if ziel.exists() and not ueberschreiben:
        raise VorlagenFehler(f"Es gibt schon eine Vorlage {vorlage.id!r}")
    try:
        ordner.mkdir(parents=True, exist_ok=True)
        ziel.write_text(vorlage_als_yaml(vorlage), encoding="utf-8")
    except OSError as fehler:
        raise VorlagenFehler(f"Vorlage nicht gespeichert: {fehler}") from fehler
    return ziel


def _bauplan_lesen(buchten, wo: str) -> tuple[tuple[int, int], ...]:
    """Die Liste unter ``buchten`` - je Bucht Leisten und Leistengroesse."""
    plan: list[tuple[int, int]] = []
    for nr, eintrag in enumerate(buchten, 1):
        if not isinstance(eintrag, dict):
            raise VorlagenFehler(f"{wo}Bucht {nr}: erwartet wird leisten und da")
        try:
            leisten = int(eintrag.get("leisten"))
            da = int(eintrag.get("da"))
        except (TypeError, ValueError):
            raise VorlagenFehler(
                f"{wo}Bucht {nr}: leisten und da muessen Zahlen sein"
            ) from None
        if min(leisten, da) < 1:
            raise VorlagenFehler(
                f"{wo}Bucht {nr}: Leisten und DA muessen mindestens 1 sein"
            )
        plan.append((leisten, da))
    if not plan:
        raise VorlagenFehler(f"{wo}Vorlage ohne Buchten")
    return tuple(plan)


def vorlage_loeschen(kennung: str, ordner: pathlib.Path) -> bool:
    """Loescht die Datei einer Vorlage im Arbeitsordner.

    Zurueck kommt, ob dort eine lag: eine mitgelieferte Vorlage, die noch
    nie ausgelegt wurde, gibt es hier nicht - sie wird stattdessen
    vermerkt, damit der naechste Start sie nicht wieder auslegt.
    """
    ziel = pathlib.Path(ordner) / f"{kennung}{ENDUNG}"
    if not ziel.is_file():
        return False
    try:
        ziel.unlink()
    except OSError as fehler:
        raise VorlagenFehler(f"Vorlage nicht gelöscht: {fehler}") from fehler
    return True


def vorlage_umbenennen(
    vorlage: Vorlage, name: str, ordner: pathlib.Path
) -> Vorlage:
    """Schreibt die Vorlage unter neuem Namen - die Kennung bleibt.

    Die Kennung ist der Dateiname; sie zu aendern hiesse, die Vorlage zu
    ersetzen. Umbenannt wird, was der Anwender sieht.
    """
    name = name.strip()
    if not name:
        raise VorlagenFehler("Eine Vorlage braucht einen Namen")
    neu = replace(vorlage, name=name)
    vorlage_speichern(neu, ordner, ueberschreiben=True)
    return neu


def vorlage_aus_yaml(inhalt: dict, herkunft: str = "") -> Vorlage:
    wo = f"{herkunft}: " if herkunft else ""
    buchten = _feld(inhalt, "buchten")
    # Eine Liste statt einer Zahl: der ungleich besetzte Verteiler.
    plan = _bauplan_lesen(buchten, wo) if isinstance(buchten, list) else ()

    pflicht = ("id", "name", "buchten") if plan else PFLICHTFELDER
    fehlend = [feld for feld in pflicht if _feld(inhalt, feld) is None]
    if fehlend:
        raise VorlagenFehler(f"{wo}Vorlage ohne {', '.join(fehlend)}")

    try:
        vorlage = Vorlage(
            id=str(_feld(inhalt, "id")),
            name=str(_feld(inhalt, "name")),
            buchten=len(plan) if plan else int(buchten),
            leisten_je_bucht=plan[0][0] if plan else int(
                _feld(inhalt, "leisten_je_bucht")
            ),
            da_je_leiste=plan[0][1] if plan else int(_feld(inhalt, "da_je_leiste")),
            beschreibung=str(inhalt.get("beschreibung", "")),
            standard=bool(inhalt.get("standard", False)),
            bauplan=plan,
        )
    except (TypeError, ValueError) as fehler:
        raise VorlagenFehler(f"{wo}Zahlenangabe nicht lesbar - {fehler}") from None

    if min(vorlage.buchten, vorlage.leisten_je_bucht, vorlage.da_je_leiste) < 1:
        raise VorlagenFehler(f"{wo}Buchten, Leisten und DA muessen mindestens 1 sein")
    return vorlage


class Vorlagen:
    """Alle Vorlagen aus einem Ordner."""

    def __init__(self, vorlagen: list[Vorlage]) -> None:
        self._vorlagen = {v.id: v for v in vorlagen}

    @classmethod
    def laden(cls, ordner: pathlib.Path) -> Vorlagen:
        gefunden: list[Vorlage] = []
        for datei in sorted(pathlib.Path(ordner).glob("*.yaml")):
            inhalt = yaml.safe_load(datei.read_text(encoding="utf-8")) or {}
            gefunden.append(vorlage_aus_yaml(inhalt, datei.name))
        return cls(gefunden)

    @classmethod
    def aus_ordnern(cls, ordner, ausgelassen=()) -> Vorlagen:
        """Aus mehreren Ordnern; bei gleicher Kennung gilt der letzte.

        So kann eine eigene Vorlage eine mitgelieferte ersetzen, ohne
        dass die mitgelieferte Datei angefasst wird.

        ``ausgelassen`` nennt Marken wie ``vorlagen/40da-4x10.yaml``, die
        der Anwender geloescht hat: die mitgelieferte Datei liegt im
        Abbild weiter, gezeigt wird sie nicht mehr.
        """
        weg = set(ausgelassen)
        gefunden: list[Vorlage] = []
        for ort in ordner:
            ort = pathlib.Path(ort)
            if not ort.is_dir():
                continue
            for datei in sorted(ort.glob("*.yaml")):
                if f"{ORDNERNAME}/{datei.name}" in weg:
                    continue
                inhalt = yaml.safe_load(datei.read_text(encoding="utf-8")) or {}
                gefunden.append(vorlage_aus_yaml(inhalt, datei.name))
        return cls(gefunden)

    def entfernen(self, kennung: str) -> None:
        """Nimmt eine Vorlage aus der laufenden Sitzung heraus."""
        self._vorlagen.pop(kennung, None)

    def aufnehmen(self, vorlage: Vorlage) -> None:
        """Nimmt eine Vorlage in die laufende Sitzung auf."""
        self._vorlagen[vorlage.id] = vorlage

    def __len__(self) -> int:
        return len(self._vorlagen)

    def __contains__(self, kennung: object) -> bool:
        return kennung in self._vorlagen

    @property
    def alle(self) -> list[Vorlage]:
        """Alle Vorlagen, aufsteigend nach Groesse - so stehen sie im Menue."""
        return sorted(self._vorlagen.values(), key=lambda v: (v.da_gesamt, v.name))

    def holen(self, kennung: str) -> Vorlage:
        try:
            return self._vorlagen[kennung]
        except KeyError:
            bekannt = ", ".join(sorted(self._vorlagen)) or "keine"
            raise VorlagenFehler(
                f"Vorlage {kennung!r} gibt es nicht (bekannt: {bekannt})"
            ) from None

    @property
    def standard(self) -> Vorlage:
        """Die Default-Vorlage.

        Ist keine als ``standard: true`` gekennzeichnet, gilt die kleinste.
        """
        for vorlage in self.alle:
            if vorlage.standard:
                return vorlage
        if not self._vorlagen:
            raise VorlagenFehler("Es ist keine einzige Vorlage vorhanden")
        return self.alle[0]
