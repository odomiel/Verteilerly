"""Vorlagendateien pruefen, bevor sie ins Programm kommen.

Wer eine Vorlage schreibt, will wissen, ob sie taugt, *bevor* er sie in
den Arbeitsordner legt und das Programm neu startet. Hier steht die
Pruefung dafuer - ohne Qt, damit sie sich ohne Fenster pruefen laesst.

Gepruefte Arten sind dieselben drei, die auch beim Start gelesen werden:
Verteilervorlagen, Blattvorlagen und Kabeltypen. Gelesen wird mit
denselben Funktionen wie im Betrieb; was dort auffaellt, faellt auch
hier auf - eine zweite Auslegung des Formats gaebe es sonst.
"""

from __future__ import annotations

import pathlib
import shutil
import tempfile
from dataclasses import dataclass, field

import yaml

from .blattvorlagen import blattvorlage_aus_yaml
from .farbcodes import Kabeltypen
from .modell import ModellFehler, mehrzahl
from .sprachen import u
from .vorlagen import vorlage_aus_yaml

#: Was sich pruefen laesst - Kennung und wie es heisst.
ARTEN = (
    ("vorlage", "Verteilervorlage"),
    ("blattvorlage", "Blattvorlage"),
    ("kabeltypen", "Kabeltypen"),
)


@dataclass
class Bericht:
    """Was bei der Pruefung einer Datei herauskam."""

    art: str
    datei: pathlib.Path
    gut: bool = True
    #: Warum die Datei unbrauchbar ist - leer, wenn sie taugt.
    fehler: str = ""
    #: Was das Programm darin gelesen hat, Zeile fuer Zeile.
    angaben: list[str] = field(default_factory=list)
    #: Was gilt, aber Fragen aufwirft - unbekannte Schluessel.
    hinweise: list[str] = field(default_factory=list)

    @property
    def urteil(self) -> str:
        """Ein Satz, der oben im Bericht steht."""
        if not self.gut:
            return u("Diese Datei kann das Programm nicht lesen.")
        if self.hinweise:
            return u("Die Datei ist brauchbar, mit Anmerkungen.")
        return u("Die Datei ist in Ordnung.")


def _inhalt(pfad: pathlib.Path) -> dict:
    inhalt = yaml.safe_load(pfad.read_text(encoding="utf-8")) or {}
    if not isinstance(inhalt, dict):
        raise ModellFehler(u("Die Datei enthält keine Vorlage, sondern {0}").format(
            type(inhalt).__name__
        ))
    return inhalt


def _vorlage(pfad: pathlib.Path, bericht: Bericht) -> None:
    vorlage = vorlage_aus_yaml(_inhalt(pfad), pfad.name, bericht.hinweise)
    bericht.angaben = [
        u("Kennung: {0}").format(vorlage.id),
        u("Name: {0}").format(vorlage.name),
        u("Aufbau: {0} × {1} Leisten zu {2} DA").format(
            vorlage.buchten, vorlage.leisten_je_bucht, vorlage.da_je_leiste
        ),
        mehrzahl(vorlage.leisten_gesamt, "Leiste", "Leisten")
        + u(", ") + mehrzahl(vorlage.da_gesamt, "Doppelader", "Doppeladern"),
    ]
    if vorlage.beschreibung:
        bericht.angaben.append(u("Beschreibung: {0}").format(vorlage.beschreibung))
    if vorlage.bauplan:
        bericht.angaben.append(u("Bauplan je Bucht: {0}").format(
            ", ".join(f"{leisten}×{da}" for leisten, da in vorlage.bauplan)
        ))
    if vorlage.standard:
        bericht.angaben.append(u("Vorauswahl für neue Verteiler"))


def _blattvorlage(pfad: pathlib.Path, bericht: Bericht) -> None:
    vorlage = blattvorlage_aus_yaml(_inhalt(pfad), pfad.name, bericht.hinweise)
    spalten = ", ".join(spalte.feld for spalte in vorlage.spalten)
    bloecke = " | ".join(
        ", ".join(eintrag.marke for eintrag in block)
        for block in vorlage.schriftfeld
    )
    bericht.angaben = [
        u("Kennung: {0}").format(vorlage.id),
        u("Name: {0}").format(vorlage.name),
        u("Spalten: {0}").format(spalten),
        u("Schriftfeld ({0}): {1}").format(vorlage.schriftfeld_art, bloecke),
        u("Ränder und Höhen: Rand {0} mm, Schriftfeld {1} mm, Zeile {2} bis {3} mm").format(
            _zahl(vorlage.rand), _zahl(vorlage.schriftfeld_hoehe),
            _zahl(vorlage.zeilenhoehe_min), _zahl(vorlage.zeilenhoehe_max),
        ),
        mehrzahl(vorlage.buchten_je_blatt, "Bucht", "Buchten") + u(" je Blatt"),
    ]
    if vorlage.beschreibung:
        bericht.angaben.append(u("Beschreibung: {0}").format(vorlage.beschreibung))
    # Der Dateiname ist die Kennung - sonst finden Umbenennen und
    # Loeschen die Datei spaeter nicht wieder.
    if pfad.stem != vorlage.id:
        bericht.hinweise.append(
            u("Der Dateiname sollte die Kennung tragen: {0}.yaml statt {1}").format(
                vorlage.id, pfad.name
            )
        )


def _kabeltypen(pfad: pathlib.Path, bericht: Bericht) -> None:
    # Kabeltypen kommen ordnerweise; geprueft wird aber genau eine Datei -
    # was danebenliegt, geht diesen Bericht nichts an.
    _inhalt(pfad)
    with tempfile.TemporaryDirectory() as ordner:
        allein = pathlib.Path(ordner) / pfad.name
        shutil.copyfile(pfad, allein)
        typen = Kabeltypen.laden(pathlib.Path(ordner), bericht.hinweise)
    bericht.angaben = [
        mehrzahl(len(typen.alle), "Kabeltyp", "Kabeltypen") + u(" in dieser Datei"),
        *[u("{0} ({1}), Regel {2}").format(t.name, t.id, t.regel) for t in typen.alle],
    ]
    kuerzel = _inhalt(pfad).get("kuerzel") or {}
    if kuerzel:
        bericht.angaben.append(
            mehrzahl(len(kuerzel), "Farbkürzel", "Farbkürzel") + u(" dazu")
        )


def _zahl(wert: float) -> str:
    """Eine Maßangabe ohne überflüssige Null."""
    return f"{wert:g}".replace(".", ",")


PRUEFER = {
    "vorlage": _vorlage,
    "blattvorlage": _blattvorlage,
    "kabeltypen": _kabeltypen,
}


def pruefen(pfad, art: str) -> Bericht:
    """Liest die Datei so, wie das Programm sie lesen wuerde.

    Der Bericht sagt, ob sie taugt, was darin gelesen wurde und was
    dabei auffiel. Geworfen wird nichts - ein Bericht kommt immer.
    """
    pfad = pathlib.Path(pfad)
    bericht = Bericht(art=art, datei=pfad)
    pruefer = PRUEFER.get(art)
    if pruefer is None:
        bericht.gut = False
        bericht.fehler = u("Unbekannte Art: {0}").format(art)
        return bericht
    try:
        pruefer(pfad, bericht)
    except (ModellFehler, yaml.YAMLError, OSError) as fehler:
        bericht.gut = False
        bericht.fehler = str(fehler)
    except (ValueError, TypeError, KeyError, AttributeError) as fehler:
        bericht.gut = False
        bericht.fehler = u("Nicht lesbar: {0}").format(fehler)
    return bericht
