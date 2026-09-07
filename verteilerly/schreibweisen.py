"""Schreibweisen der Rangierungsadressen.

Welche Adresse gemeint ist, steht fest: Leiste, Stift, Ader. Wie sie
geschrieben wird, ist Hausbrauch - der eine schreibt ``1 1a``, der
naechste ``L1 1a``, der dritte ``L1-1a``. Darum steht die Schreibweise
hier als eigene Sache und nicht im Datenmodell.

Gelesen wird immer alles: wer die Anzeige umstellt, muss seine alten
Projekte nicht anfassen, und getippt werden darf jede der drei Formen,
gleich welche gerade eingestellt ist.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Schreibweise:
    """Wie eine Adresse auf dem Blatt und im Editor aussieht."""

    id: str
    muster: str
    beschreibung: str

    def schreiben(self, leiste: int, stift: int, seite: str) -> str:
        return self.muster.format(leiste=leiste, stift=stift, seite=seite)

    @property
    def beispiel(self) -> str:
        """Leiste 1, Stift 1, Ader a - das Beispiel im Menue."""
        return self.schreiben(1, 1, "a")


EINFACH = Schreibweise(
    "einfach", "{leiste} {stift}{seite}", "Leiste und Stift, nur durch Abstand getrennt"
)
MIT_L = Schreibweise(
    "mit_l", "L{leiste} {stift}{seite}", "Die Leiste mit einem L davor"
)
MIT_STRICH = Schreibweise(
    "mit_strich", "L{leiste}-{stift}{seite}", "Die Leiste mit L, getrennt durch Strich"
)

SCHREIBWEISEN = (EINFACH, MIT_L, MIT_STRICH)
STANDARD = EINFACH


def holen(kennung: str | None) -> Schreibweise:
    """Die Schreibweise zu einer Kennung - Unbekanntes wird zum Standard.

    Eine Einstellung aus einer neueren Fassung soll das Programm nicht
    aufhalten; dann wird eben normal geschrieben.
    """
    for weise in SCHREIBWEISEN:
        if weise.id == kennung:
            return weise
    return STANDARD
