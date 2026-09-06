"""Verteilervorlagen.

Eine Vorlage ist nichts weiter als die drei Kennzahlen Buchten, Leisten je
Bucht und DA je Leiste - dazu ein Name. Sie liegt als YAML-Datei im
Vorlagenordner neben dem Programm; eine neue Vorlage entsteht
durch Ablegen einer Datei, ohne dass am Programm etwas zu aendern ist.
"""

from __future__ import annotations

import datetime
import pathlib
import re
import unicodedata
from dataclasses import dataclass

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

    @property
    def da_gesamt(self) -> int:
        return self.buchten * self.leisten_je_bucht * self.da_je_leiste

    @property
    def leisten_gesamt(self) -> int:
        return self.buchten * self.leisten_je_bucht

    def verteiler(self, name: str = "", nummer: str = "") -> Verteiler:
        """Baut einen leeren Verteiler nach dieser Vorlage."""
        return Verteiler.aus_geometrie(
            self.buchten,
            self.leisten_je_bucht,
            self.da_je_leiste,
            name=name,
            nummer=nummer,
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

        Eine Vorlage sind drei Zahlen - ein Verteiler mit ungleich
        besetzten Buchten laesst sich damit nicht beschreiben.
        """
        if not verteiler.buchten:
            raise VorlagenFehler("Der Verteiler hat keine Buchten")
        leisten = {len(r.leisten) for r in verteiler.buchten}
        da = {l.da_anzahl for l in verteiler.alle_leisten}
        if len(leisten) > 1 or len(da) > 1:
            raise VorlagenFehler(
                "Der Verteiler ist nicht gleichmäßig aufgebaut und taugt "
                "deshalb nicht als Vorlage"
            )
        return cls(
            id=kennung or kennung_bilden(name),
            name=name,
            buchten=len(verteiler.buchten),
            leisten_je_bucht=leisten.pop(),
            da_je_leiste=da.pop(),
            beschreibung=beschreibung,
        )


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
        "buchten": vorlage.buchten,
        "leisten_je_bucht": vorlage.leisten_je_bucht,
        "da_je_leiste": vorlage.da_je_leiste,
    }
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


def vorlage_aus_yaml(inhalt: dict, herkunft: str = "") -> Vorlage:
    fehlend = [feld for feld in PFLICHTFELDER if _feld(inhalt, feld) is None]
    if fehlend:
        wo = f"{herkunft}: " if herkunft else ""
        raise VorlagenFehler(f"{wo}Vorlage ohne {', '.join(fehlend)}")

    try:
        vorlage = Vorlage(
            id=str(_feld(inhalt, "id")),
            name=str(_feld(inhalt, "name")),
            buchten=int(_feld(inhalt, "buchten")),
            leisten_je_bucht=int(_feld(inhalt, "leisten_je_bucht")),
            da_je_leiste=int(_feld(inhalt, "da_je_leiste")),
            beschreibung=str(inhalt.get("beschreibung", "")),
            standard=bool(inhalt.get("standard", False)),
        )
    except (TypeError, ValueError) as fehler:
        wo = f"{herkunft}: " if herkunft else ""
        raise VorlagenFehler(f"{wo}Zahlenangabe nicht lesbar - {fehler}") from None

    if min(vorlage.buchten, vorlage.leisten_je_bucht, vorlage.da_je_leiste) < 1:
        wo = f"{herkunft}: " if herkunft else ""
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
    def aus_ordnern(cls, ordner) -> Vorlagen:
        """Aus mehreren Ordnern; bei gleicher Kennung gilt der letzte.

        So kann eine eigene Vorlage eine mitgelieferte ersetzen, ohne
        dass die mitgelieferte Datei angefasst wird.
        """
        gefunden: list[Vorlage] = []
        for ort in ordner:
            ort = pathlib.Path(ort)
            if ort.is_dir():
                gefunden += cls.laden(ort).alle
        return cls(gefunden)

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
