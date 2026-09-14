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
from .sprachen import u


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
            raise KabeltypFehler(u("Die Doppelader wird ab 1 gezaehlt"))
        if self.regel == "lagen":
            return self._lagen(kabel_da, da_gesamt)
        if self.regel == "sternvierer":
            return self._sternvierer(kabel_da)
        if self.regel == "liste":
            return self._liste(kabel_da)
        raise KabeltypFehler(u("Unbekannte Farbregel {0!r} bei {1!r}").format(self.regel, self.id))

    # -- Regeln ------------------------------------------------------------

    def _lagen(self, kabel_da: int, da_gesamt: int | None) -> tuple[str, str]:
        """Lagenverseilung: die b-Ader laeuft durch, die a-Ader markiert die Lage.

        Die b-Ader wiederholt ihre Folge endlos - bl, ge, gn, br, sw und
        wieder von vorn. Die a-Ader ist weiss, ausser bei der ersten
        Doppelader einer Lage; dort ist sie rot. Wo eine Lage beginnt,
        haengt an der Groesse des Kabels und steht in der Tabelle
        ``lagenbeginn``: beim 10x2 sind das die Doppeladern 1 und 9, beim
        16x2 die 1 und 12. Eine feste Lagenlaenge gibt es nicht.
        """
        folge = self.daten["b_folge"]
        b = folge[(kabel_da - 1) % len(folge)]
        a = self.daten.get("a_farbe") or self.daten.get("a_sonst", "")
        if kabel_da in self.lagenbeginn(da_gesamt):
            a = self.daten["a_lagenbeginn"]

        ausnahme = self._ausnahme(kabel_da, da_gesamt)
        if ausnahme:
            a, b = ausnahme[0] or a, ausnahme[1] or b
        return a, b

    def lagenbeginn(self, da_gesamt: int | None) -> set[int]:
        """Bei welchen Doppeladern dieses Kabels eine Lage beginnt."""
        tabelle = self.daten.get("lagenbeginn") or {}
        try:
            return set(tabelle[int(da_gesamt)])
        except (KeyError, TypeError, ValueError):
            return {1}

    def lagen_bekannt(self, da_gesamt: int | None) -> bool:
        """Ist die Lagenaufteilung fuer diese Kabelgroesse hinterlegt?

        Ist sie es nicht, bleibt nur die erste Doppelader rot - geraten
        wird nicht, denn eine falsche Farbe faellt niemandem auf.
        """
        if self.regel != "lagen":
            return True
        tabelle = self.daten.get("lagenbeginn") or {}
        try:
            return int(da_gesamt) in tabelle
        except (TypeError, ValueError):
            return False

    def _ausnahme(self, kabel_da: int, da_gesamt: int | None) -> list | None:
        """Einzelne Doppeladern, die aus der Regel fallen (etwa das 2x2)."""
        alle = self.daten.get("ausnahmen") or {}
        try:
            eintrag = alle[int(da_gesamt)][kabel_da]
        except (KeyError, TypeError, ValueError):
            return None
        return list(eintrag) if isinstance(eintrag, (list, tuple)) else None

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
                        u("{0}: Kabeltyp ohne {1}").format(datei.name, fehlt.args[0])
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
                u("Kabeltyp {0!r} ist nicht hinterlegt (bekannt: {1})").format(kennung, bekannt)
            ) from None


def farbplan(
    verteiler: Verteiler, kabel: Kabel, kabeltypen: Kabeltypen
) -> dict[tuple[int, int, str], str]:
    """Welche Farbe die Automatik fuer jede Ader dieses Kabels vorsieht.

    Der Plan ist der Massstab fuer alles Weitere: steht in einer Ader
    genau das, was hier steht, hat es die Automatik gesetzt und darf von
    ihr auch wieder geaendert werden. Steht etwas anderes, war es der
    Anwender - und das bleibt.
    """
    if not kabel.kabeltyp:
        return {}
    typ = kabeltypen.holen(kabel.kabeltyp)
    plan: dict[tuple[int, int, str], str] = {}
    for kabel_da, leiste_nr, leisten_da in kabel.positionen():
        farbe_a, farbe_b = typ.farben(kabel_da, kabel.da_gesamt)
        plan[(leiste_nr, leisten_da, "a")] = farbe_a
        plan[(leiste_nr, leisten_da, "b")] = farbe_b
    return plan


def farben_eintragen(
    verteiler: Verteiler,
    kabel: Kabel,
    kabeltypen: Kabeltypen,
    ueberschreiben: bool = False,
    statt: dict[tuple[int, int, str], str] | None = None,
) -> int:
    """Traegt die Adernfarben eines Kabels in die Leiste ein.

    Vorhandene Eintraege bleiben stehen, solange ``ueberschreiben`` nicht
    gesetzt ist - die Automatik ist Vorschlag, nicht Sperre.
    Gibt zurueck, wie viele Adern gefuellt wurden.

    ``statt`` ist der Farbplan von vorher: was noch genau so dasteht, hat
    die Automatik gesetzt und wird ersetzt. So folgen die Farben einem
    geaenderten Kabeltyp oder einer geaenderten Groesse, ohne dass von
    Hand Eingetragenes verlorenginge.

    Ohne Kabeltyp passiert nichts: dann bleibt die Farbspalte leer und
    wird von Hand ausgefuellt.
    """
    if not kabel.kabeltyp:
        return 0

    vorher = statt or {}
    gefuellt = 0
    for (leiste_nr, leisten_da, seite), farbe in farbplan(
        verteiler, kabel, kabeltypen
    ).items():
        ader = verteiler.leiste(leiste_nr).stift(leisten_da).ader(seite)
        von_der_automatik = ader.farbe == vorher.get((leiste_nr, leisten_da, seite))
        if ader.farbe and not ueberschreiben and not von_der_automatik:
            continue
        if ader.farbe == farbe:
            continue
        ader.farbe = farbe
        gefuellt += 1
    return gefuellt


def farben_verwaist_loeschen(
    verteiler: Verteiler,
    vorher: dict[tuple[int, int, str], str],
    jetzt: dict[tuple[int, int, str], str],
) -> int:
    """Raeumt die Farben der Adern, die das Kabel nicht mehr belegt.

    Wird ein Kabel kuerzer, gehoert seine Farbfolge dort nicht mehr hin.
    Massstab ist wie ueberall der Farbplan: nur was die Automatik gesetzt
    hat, nimmt sie auch wieder mit.
    """
    geleert = 0
    for stelle, farbe in vorher.items():
        if stelle in jetzt:
            continue
        leiste_nr, leisten_da, seite = stelle
        ader = verteiler.leiste(leiste_nr).stift(leisten_da).ader(seite)
        if ader.farbe and ader.farbe == farbe:
            ader.farbe = ""
            geleert += 1
    return geleert


def farben_loeschen(
    verteiler: Verteiler, kabel: Kabel, kabeltypen: Kabeltypen
) -> int:
    """Nimmt die Farben wieder heraus, die dieses Kabel gesetzt hat.

    Wird ein Kabel abgenommen, gehoert seine Farbfolge nicht mehr dorthin:
    die naechste Leitung hat eine eigene. Was jemand von Hand eingetragen
    hat, bleibt stehen - dafuer ist der Farbplan der Massstab.
    """
    geleert = 0
    for (leiste_nr, leisten_da, seite), farbe in farbplan(
        verteiler, kabel, kabeltypen
    ).items():
        ader = verteiler.leiste(leiste_nr).stift(leisten_da).ader(seite)
        if ader.farbe and ader.farbe == farbe:
            ader.farbe = ""
            geleert += 1
    return geleert
