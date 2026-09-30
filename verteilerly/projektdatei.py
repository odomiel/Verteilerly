"""Projektdatei lesen und schreiben.

Ein Verteiler ist eine JSON-Datei: lesbar, versionierbar und auch ohne das
Programm auswertbar. Bewusst kein Binaerformat und kein Fremdformat.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

from .modell import (
    Ader,
    BLATTARTEN,
    LEISTEN_SCHREIBWEISEN,
    LEISTEN_ZAHLEN,
    STILFELDER,
    TEILBARE_FELDER,
    Textstil,
    Zellenteilung,
    Aderadresse,
    Kabel,
    Kabelabschnitt,
    ModellFehler,
    Projekt,
    Rangierung,
    Bucht,
    Leiste,
    Stift,
    Verteiler,
)
from .sprachen import u

DATEIKENNUNG = "verteilerly-projekt"
FORMATVERSION = 10
# Fassung 1 nannte die Buchten noch Reihen, Fassung 2 kannte noch keine
# abgewaehlten Felder, Fassung 3 noch keinen Vermerk im Rangierfeld,
# Fassung 4 noch keine Wahl der Blattarten fuer die eigenen Felder,
# Fassung 5 noch keine eigenen Beschriftungen, Fassung 6 noch keinen
# Textstil je Zelle, Fassung 7 noch keine geteilten Zellen, Fassung 8
# noch keine Leisten mit Buchstaben, und bis Fassung 9 stand die Wahl der
# Blattarten fuer die eigenen Felder am Projekt - seither in der
# Blattvorlage, und ``eigene_felder_auf`` wird beim Lesen uebergangen.
# Solche Dateien werden weiter gelesen; geschrieben wird immer die neue
# Fassung.
LESBARE_VERSIONEN = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)


class ProjektdateiFehler(ModellFehler):
    """Die Datei ist keine lesbare Verteilerly-Projektdatei."""


# --------------------------------------------------------------------------
# Schreiben
# --------------------------------------------------------------------------


def _ader_raus(ader: Ader) -> dict[str, Any]:
    daten = {"seite": ader.seite}
    # Leere Felder werden weggelassen, damit die Datei lesbar bleibt.
    for feld in ("farbe", "bezeichnung", "bemerkung", "vermerk"):
        wert = getattr(ader, feld)
        if wert:
            daten[feld] = wert
    if ader.vermerk and ader.vermerk_zuerst:
        daten["vermerk_zuerst"] = True
    # Nur eingestellte Stile, und nur die von Hand gesetzten Angaben darin.
    stile = {
        feld: stil.als_dict()
        for feld, stil in sorted(ader.stile.items())
        if not stil.leer
    }
    if stile:
        daten["stile"] = stile
    teilungen = {
        feld: teilung.als_dict()
        for feld, teilung in sorted(ader.teilungen.items())
        if not teilung.leer
    }
    if teilungen:
        daten["teilungen"] = teilungen
    return daten


def _verteiler_raus(verteiler: Verteiler) -> dict[str, Any]:
    return {
        "name": verteiler.name,
        "nummer": verteiler.nummer,
        "buchten": [
            {
                "nummer": bucht.nummer,
                "leisten": [
                    {
                        "nummer": leiste.nummer,
                        "stifte": [
                            {
                                "nummer": stift.nummer,
                                "a": _ader_raus(stift.a),
                                "b": _ader_raus(stift.b),
                            }
                            for stift in leiste.stifte
                        ],
                    }
                    for leiste in bucht.leisten
                ],
            }
            for bucht in verteiler.buchten
        ],
        "kabel": [
            {
                "beschriftung": kabel.beschriftung,
                "kabeltyp": kabel.kabeltyp,
                "da_gesamt": kabel.da_gesamt,
                "abschnitte": [
                    {
                        "leiste": a.leiste,
                        "start_da": a.start_da,
                        "anzahl_da": a.anzahl_da,
                    }
                    for a in kabel.abschnitte
                ],
            }
            for kabel in verteiler.kabel
        ],
        "rangierungen": [
            {"von": str(r.von), "nach": str(r.nach)} for r in verteiler.rangierungen
        ],
    }


def als_dict(projekt: Projekt) -> dict[str, Any]:
    daten: dict[str, Any] = {
        "dateikennung": DATEIKENNUNG,
        "formatversion": FORMATVERSION,
        "briefkopf": dict(projekt.briefkopf),
        "eigene_felder": dict(projekt.eigene_felder),
        # Abgewaehlte Felder behalten ihren Inhalt - nur die Auswahl wird
        # vermerkt.
        "ausgeblendet": sorted(projekt.ausgeblendet),
        # Auf welchen Blattarten die eigenen Felder erscheinen.
        # Nur die Woerter, die von der Vorgabe abweichen.
        "beschriftungen": projekt.eigene_beschriftungen(),
        "verteiler": _verteiler_raus(projekt.verteiler),
    }
    # Wie die Leisten heissen, gehoert zum Verteiler: seine Leisten sind
    # am Gerät selbst so beschriftet. Geschrieben wird es nur, wenn es von
    # der Vorgabe abweicht - eine gezaehlte Leiste braucht keinen Eintrag.
    if projekt.leisten_schreibweise != LEISTEN_ZAHLEN:
        daten["leisten_schreibweise"] = projekt.leisten_schreibweise
    return daten


def speichern(projekt: Projekt, pfad: pathlib.Path) -> None:
    """Schreibt das Projekt als JSON.

    Es wird erst in eine Nebendatei geschrieben und dann umbenannt, damit
    bei einem Abbruch nicht die bestehende Datei halb ueberschrieben ist.
    """
    pfad = pathlib.Path(pfad)
    text = json.dumps(als_dict(projekt), indent=2, ensure_ascii=False) + "\n"
    neben = pfad.with_suffix(pfad.suffix + ".neu")
    neben.write_text(text, encoding="utf-8")
    neben.replace(pfad)


# --------------------------------------------------------------------------
# Lesen
# --------------------------------------------------------------------------


def _ader_rein(daten: dict[str, Any], seite: str) -> Ader:
    return Ader(
        seite=daten.get("seite", seite),
        farbe=daten.get("farbe", ""),
        bezeichnung=daten.get("bezeichnung", ""),
        bemerkung=daten.get("bemerkung", ""),
        vermerk=daten.get("vermerk", ""),
        vermerk_zuerst=bool(daten.get("vermerk_zuerst")),
        stile={
            feld: Textstil.aus_dict(wert)
            for feld, wert in (daten.get("stile") or {}).items()
            if feld in STILFELDER
        },
        teilungen={
            feld: Zellenteilung.aus_dict(wert)
            for feld, wert in (daten.get("teilungen") or {}).items()
            if feld in TEILBARE_FELDER
        },
    )


def _verteiler_rein(daten: dict[str, Any]) -> Verteiler:
    buchten = []
    for bucht in daten.get("buchten") or daten.get("reihen") or []:
        leisten = []
        for leiste in bucht.get("leisten", []):
            stifte = [
                Stift(
                    nummer=stift["nummer"],
                    a=_ader_rein(stift.get("a", {}), "a"),
                    b=_ader_rein(stift.get("b", {}), "b"),
                )
                for stift in leiste.get("stifte", [])
            ]
            leisten.append(Leiste(nummer=leiste["nummer"], stifte=stifte))
        buchten.append(Bucht(nummer=bucht["nummer"], leisten=leisten))

    kabel = [
        Kabel(
            beschriftung=eintrag.get("beschriftung", ""),
            abschnitte=[
                Kabelabschnitt(a["leiste"], a["start_da"], a["anzahl_da"])
                for a in eintrag.get("abschnitte", [])
            ],
            kabeltyp=eintrag.get("kabeltyp"),
            da_gesamt=eintrag.get("da_gesamt"),
        )
        for eintrag in daten.get("kabel", [])
    ]

    rangierungen = [
        Rangierung(Aderadresse.parse(r["von"]), Aderadresse.parse(r["nach"]))
        for r in daten.get("rangierungen", [])
    ]

    return Verteiler(
        name=daten.get("name", ""),
        nummer=daten.get("nummer", ""),
        buchten=buchten,
        kabel=kabel,
        rangierungen=rangierungen,
    )


def aus_dict(daten: dict[str, Any]) -> Projekt:
    if daten.get("dateikennung") != DATEIKENNUNG:
        raise ProjektdateiFehler(u("Das ist keine Verteilerly-Projektdatei"))
    version = daten.get("formatversion")
    if version not in LESBARE_VERSIONEN:
        lesbar = ", ".join(str(v) for v in LESBARE_VERSIONEN)
        raise ProjektdateiFehler(
            u("Formatversion {0} wird nicht unterstuetzt (lesbar: {1})").format(version, lesbar)
        )
    return Projekt(
        verteiler=_verteiler_rein(daten.get("verteiler", {})),
        briefkopf=dict(daten.get("briefkopf") or {}),
        eigene_felder=dict(daten.get("eigene_felder") or {}),
        ausgeblendet=set(daten.get("ausgeblendet") or ()),
        # ``eigene_felder_auf`` stand bis Fassung 9 hier; heute sagt die
        # Blattvorlage, auf welchen Blattarten die eigenen Felder stehen.
        # Der alte Schluessel wird ueberlesen, nicht beanstandet.
        beschriftungen=dict(daten.get("beschriftungen") or {}),
        # Aeltere Dateien kannten nur gezaehlte Leisten; eine Angabe, die
        # das Programm nicht kennt, wird ebenfalls zur Zahl.
        leisten_schreibweise=(
            daten.get("leisten_schreibweise")
            if daten.get("leisten_schreibweise") in LEISTEN_SCHREIBWEISEN
            else LEISTEN_ZAHLEN
        ),
    )


def laden(pfad: pathlib.Path) -> Projekt:
    """Liest eine Projektdatei.

    Was an der Datei nicht stimmt, kommt als ``ProjektdateiFehler`` heraus -
    auch dann, wenn sie gueltiges JSON ist, aber nicht so gebaut wie ein
    Projekt: eine Datei aus fremder Hand soll eine Meldung ergeben, keinen
    Absturz.
    """
    pfad = pathlib.Path(pfad)
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        raise ProjektdateiFehler(u("{0} ist keine Textdatei").format(pfad.name)) from None
    except json.JSONDecodeError as fehler:
        raise ProjektdateiFehler(u("{0} ist kein gueltiges JSON - {1}").format(pfad.name, fehler)) from None
    except RecursionError:
        raise ProjektdateiFehler(u("{0} ist zu tief verschachtelt").format(pfad.name)) from None
    if not isinstance(daten, dict):
        raise ProjektdateiFehler(u("{0} enthaelt kein Projekt").format(pfad.name))
    try:
        return aus_dict(daten)
    except ModellFehler:
        raise
    except (KeyError, TypeError, AttributeError, ValueError, IndexError, RecursionError) as fehler:
        raise ProjektdateiFehler(
            u("{0} ist unvollstaendig - {1}").format(pfad.name, f"{type(fehler).__name__}: {fehler}")
        ) from None
