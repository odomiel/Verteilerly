"""Verteilervorlagen.

Eine Vorlage ist nichts weiter als die drei Kennzahlen Reihen, Leisten je
Reihe und DA je Leiste - dazu ein Name. Sie liegt als YAML-Datei im
Vorlagenordner neben dem Programm; eine neue Vorlage entsteht
durch Ablegen einer Datei, ohne dass am Programm etwas zu aendern ist.
"""

from __future__ import annotations

import pathlib
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
    reihen: int
    leisten_je_reihe: int
    da_je_leiste: int
    beschreibung: str = ""
    standard: bool = False

    @property
    def da_gesamt(self) -> int:
        return self.reihen * self.leisten_je_reihe * self.da_je_leiste

    @property
    def leisten_gesamt(self) -> int:
        return self.reihen * self.leisten_je_reihe

    def verteiler(self, name: str = "", nummer: str = "") -> Verteiler:
        """Baut einen leeren Verteiler nach dieser Vorlage."""
        return Verteiler.aus_geometrie(
            self.reihen,
            self.leisten_je_reihe,
            self.da_je_leiste,
            name=name,
            nummer=nummer,
        )

    def __str__(self) -> str:
        return f"{self.name} ({self.da_gesamt} DA)"


PFLICHTFELDER = ("id", "name", "reihen", "leisten_je_reihe", "da_je_leiste")


def vorlage_aus_yaml(inhalt: dict, herkunft: str = "") -> Vorlage:
    fehlend = [feld for feld in PFLICHTFELDER if feld not in inhalt]
    if fehlend:
        wo = f"{herkunft}: " if herkunft else ""
        raise VorlagenFehler(f"{wo}Vorlage ohne {', '.join(fehlend)}")

    try:
        vorlage = Vorlage(
            id=str(inhalt["id"]),
            name=str(inhalt["name"]),
            reihen=int(inhalt["reihen"]),
            leisten_je_reihe=int(inhalt["leisten_je_reihe"]),
            da_je_leiste=int(inhalt["da_je_leiste"]),
            beschreibung=str(inhalt.get("beschreibung", "")),
            standard=bool(inhalt.get("standard", False)),
        )
    except (TypeError, ValueError) as fehler:
        wo = f"{herkunft}: " if herkunft else ""
        raise VorlagenFehler(f"{wo}Zahlenangabe nicht lesbar - {fehler}") from None

    if min(vorlage.reihen, vorlage.leisten_je_reihe, vorlage.da_je_leiste) < 1:
        wo = f"{herkunft}: " if herkunft else ""
        raise VorlagenFehler(f"{wo}Reihen, Leisten und DA muessen mindestens 1 sein")
    return vorlage


class Vorlagen:
    """Alle Vorlagen aus einem Ordner."""

    def __init__(self, vorlagen: list[Vorlage]) -> None:
        self._vorlagen = {v.id: v for v in vorlagen}

    @classmethod
    def laden(cls, ordner: pathlib.Path) -> Vorlagen:
        gefunden: list[Vorlage] = []
        for datei in sorted(ordner.glob("*.yaml")):
            inhalt = yaml.safe_load(datei.read_text(encoding="utf-8")) or {}
            gefunden.append(vorlage_aus_yaml(inhalt, datei.name))
        return cls(gefunden)

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
