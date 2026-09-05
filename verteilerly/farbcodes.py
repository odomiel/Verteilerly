"""Kabeltypen und Adernfarben.

Die Farbfolgen stehen in ``daten/kabeltypen/*.yaml`` und werden hier nur
ausgewertet. Wer einen eigenen Kabeltyp braucht, legt ihn dort ab - am
Programm ist dafuer nichts zu aendern.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field

import yaml

from .modell import Kabel, ModellFehler, Verteiler


class KabeltypFehler(ModellFehler):
    """Der Kabeltyp ist unbekannt oder seine Beschreibung ist unvollstaendig."""


@dataclass
class Kabeltyp:
    """Ein Kabeltyp mit der Regel, nach der seine Adernfarben entstehen."""

    id: str
    name: str
    regel: str
    beschreibung: str = ""
    daten: dict = field(default_factory=dict)

    def farben(self, kabel_da: int, da_gesamt: int | None = None) -> tuple[str, str]:
        """Die Farben der Adern a und b fuer die ``kabel_da``-te Doppelader.

        ``kabel_da`` zaehlt ab 1 ueber das ganze Kabel, also auch ueber eine
        Fortsetzung auf einer anderen Leiste hinweg.
        """
        if kabel_da < 1:
            raise KabeltypFehler("Die Doppelader wird ab 1 gezaehlt")
        if self.regel == "lagen":
            return self._lagen(kabel_da, da_gesamt)
        if self.regel == "sternvierer":
            return self._sternvierer(kabel_da)
        if self.regel == "liste":
            return self._liste(kabel_da)
        raise KabeltypFehler(f"Unbekannte Farbregel {self.regel!r} bei {self.id!r}")

    # -- Regeln ------------------------------------------------------------

    def _lagen(self, kabel_da: int, da_gesamt: int | None) -> tuple[str, str]:
        folge = self.daten["b_folge"]
        lagenlaenge = int(self.daten.get("lagenlaenge", len(folge)))
        stelle = (kabel_da - 1) % lagenlaenge

        a = self.daten["a_lagenbeginn"] if stelle == 0 else self.daten["a_sonst"]
        b = folge[stelle % len(folge)]

        # Sonderfall 2x2: die erste b-Ader ist schwarz statt blau.
        sonderfall = self.daten.get("b_erste_bei_2da")
        if sonderfall and da_gesamt == 2 and kabel_da == 1:
            b = sonderfall
        return a, b

    def _sternvierer(self, kabel_da: int) -> tuple[str, str]:
        grundfarben = self.daten["grundfarben"]
        ringe = self.daten["ringe"]
        vierer, stelle = divmod(kabel_da - 1, 2)
        grundfarbe = grundfarben[vierer % len(grundfarben)]
        a, b = (0, 1) if stelle == 0 else (2, 3)
        return grundfarbe + ringe[a], grundfarbe + ringe[b]

    def _liste(self, kabel_da: int) -> tuple[str, str]:
        adern = self.daten["adern"]
        erste = (kabel_da - 1) * 2
        return adern[erste % len(adern)], adern[(erste + 1) % len(adern)]


class Kabeltypen:
    """Alle geladenen Kabeltypen samt Farbkuerzel-Verzeichnis."""

    def __init__(self, typen: dict[str, Kabeltyp], kuerzel: dict[str, str]) -> None:
        self._typen = typen
        self.kuerzel = kuerzel

    @classmethod
    def laden(cls, ordner: pathlib.Path) -> Kabeltypen:
        typen: dict[str, Kabeltyp] = {}
        kuerzel: dict[str, str] = {}

        for datei in sorted(ordner.glob("*.yaml")):
            inhalt = yaml.safe_load(datei.read_text(encoding="utf-8")) or {}
            kuerzel.update(inhalt.get("kuerzel") or {})
            for eintrag in inhalt.get("kabeltypen") or []:
                eintrag = dict(eintrag)
                try:
                    kennung = eintrag.pop("id")
                    name = eintrag.pop("name")
                    regel = eintrag.pop("regel")
                except KeyError as fehlt:
                    raise KabeltypFehler(
                        f"{datei.name}: Kabeltyp ohne {fehlt.args[0]}"
                    ) from None
                typen[kennung] = Kabeltyp(
                    id=kennung,
                    name=name,
                    regel=regel,
                    beschreibung=eintrag.pop("beschreibung", ""),
                    daten=eintrag,
                )
        return cls(typen, kuerzel)

    def __contains__(self, kennung: object) -> bool:
        return kennung in self._typen

    def __len__(self) -> int:
        return len(self._typen)

    @property
    def alle(self) -> list[Kabeltyp]:
        return list(self._typen.values())

    def holen(self, kennung: str) -> Kabeltyp:
        try:
            return self._typen[kennung]
        except KeyError:
            bekannt = ", ".join(sorted(self._typen)) or "keine"
            raise KabeltypFehler(
                f"Kabeltyp {kennung!r} ist nicht hinterlegt (bekannt: {bekannt})"
            ) from None


def farben_eintragen(
    verteiler: Verteiler,
    kabel: Kabel,
    kabeltypen: Kabeltypen,
    ueberschreiben: bool = False,
) -> int:
    """Traegt die Adernfarben eines Kabels in die Leiste ein.

    Vorhandene Eintraege bleiben stehen, solange ``ueberschreiben`` nicht
    gesetzt ist - die Automatik ist Vorschlag, nicht Sperre.
    Gibt zurueck, wie viele Adern gefuellt wurden.

    Ohne Kabeltyp passiert nichts: dann bleibt die Farbspalte leer und
    wird von Hand ausgefuellt.
    """
    if not kabel.kabeltyp:
        return 0

    typ = kabeltypen.holen(kabel.kabeltyp)
    gefuellt = 0
    for kabel_da, leiste_nr, leisten_da in kabel.positionen():
        farbe_a, farbe_b = typ.farben(kabel_da, kabel.da_gesamt)
        stift = verteiler.leiste(leiste_nr).stift(leisten_da)
        for ader, farbe in ((stift.a, farbe_a), (stift.b, farbe_b)):
            if ader.farbe and not ueberschreiben:
                continue
            ader.farbe = farbe
            gefuellt += 1
    return gefuellt
