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

from .blattvorlagen import blattvorlage_auffrischen, blattvorlage_aus_yaml
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
    #: Was sich auffrischen liesse - eine Zeile je Angabe, die es nicht
    #: mehr gibt. Leer heisst: die Datei ist auf dem heutigen Stand.
    aufzufrischen: list[str] = field(default_factory=list)

    @property
    def urteil(self) -> str:
        """Ein Satz, der oben im Bericht steht."""
        if not self.gut:
            return u("Diese Datei kann das Programm nicht lesen.")
        if self.aufzufrischen:
            return u("Die Datei ist brauchbar, stammt aber aus einer älteren Fassung.")
        if self.hinweise:
            return u("Die Datei ist brauchbar, mit Anmerkungen.")
        return u("Die Datei ist in Ordnung.")


@dataclass
class Auffrischung:
    """Was das Auffrischen einer Vorlagendatei ergab."""

    datei: pathlib.Path
    #: Wohin die alte Fassung gelegt wurde - None, wenn nichts geschah.
    sicherung: pathlib.Path | None = None
    #: Was geaendert wurde, Zeile fuer Zeile.
    aenderungen: list[str] = field(default_factory=list)
    fehler: str = ""

    @property
    def gelungen(self) -> bool:
        return not self.fehler

    @property
    def urteil(self) -> str:
        if self.fehler:
            return u("Aufgefrischt wurde nichts: {0}").format(self.fehler)
        if not self.aenderungen:
            return u("Es war nichts aufzufrischen.")
        return mehrzahl(len(self.aenderungen), "Angabe", "Angaben") + u(" aufgefrischt")


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
    inhalt = _inhalt(pfad)
    # Trockenlauf: was das Auffrischen aendern wuerde, ohne es zu tun.
    bericht.aufzufrischen = blattvorlage_auffrischen(inhalt)[1]
    vorlage = blattvorlage_aus_yaml(inhalt, pfad.name, bericht.hinweise)
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


#: Was sich auffrischen laesst. Fuer die anderen Arten gibt es nichts
#: abzulegen - sie haben noch nie etwas verloren.
AUFFRISCHBAR = {"blattvorlage": blattvorlage_auffrischen}

#: Die alte Fassung bleibt daneben liegen, mit dieser Endung.
SICHERUNG = ".alt"


def auffrischen(pfad, art: str) -> Auffrischung:
    """Schreibt die Datei auf den heutigen Stand um.

    Geaendert wird nur, was das Programm als abgelegt kennt; alles
    andere bleibt, wie es ist. **Kommentare gehen dabei verloren** - die
    Datei wird aus den gelesenen Angaben neu geschrieben, und YAML
    behaelt keine Kommentare. Darum bleibt die alte Fassung als
    ``<name>.yaml.alt`` daneben liegen.

    Vor dem Schreiben wird das Ergebnis gelesen wie im Betrieb: was
    dabei durchfaellt, wird nicht geschrieben.
    """
    pfad = pathlib.Path(pfad)
    ergebnis = Auffrischung(datei=pfad)
    auffrischer = AUFFRISCHBAR.get(art)
    if auffrischer is None:
        ergebnis.fehler = u("Für diese Art gibt es nichts aufzufrischen.")
        return ergebnis
    try:
        inhalt = _inhalt(pfad)
        neu, getan = auffrischer(inhalt)
        if not getan:
            return ergebnis
        # Erst lesen, dann schreiben: eine Datei, die danach nicht mehr
        # taugt, waere schlimmer als eine veraltete.
        pruefer = PRUEFER[art]
        probe = Bericht(art=art, datei=pfad)
        text = yaml.safe_dump(neu, allow_unicode=True, sort_keys=False)
        with tempfile.TemporaryDirectory() as ordner:
            vorab = pathlib.Path(ordner) / pfad.name
            vorab.write_text(text, encoding="utf-8")
            pruefer(vorab, probe)
        sicherung = pfad.with_suffix(pfad.suffix + SICHERUNG)
        shutil.copyfile(pfad, sicherung)
        pfad.write_text(text, encoding="utf-8")
        ergebnis.sicherung = sicherung
        ergebnis.aenderungen = getan
    except (ModellFehler, yaml.YAMLError, OSError) as fehler:
        ergebnis.fehler = str(fehler)
    except (ValueError, TypeError, KeyError, AttributeError) as fehler:
        ergebnis.fehler = u("Nicht lesbar: {0}").format(fehler)
    return ergebnis


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
