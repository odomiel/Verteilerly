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

DATEIKENNUNG = "verteilerly-projekt"
FORMATVERSION = 3
# Fassung 1 nannte die Buchten noch Reihen, Fassung 2 kannte noch keine
# abgewaehlten Felder. Solche Dateien werden weiter gelesen; geschrieben
# wird immer die neue Fassung.
LESBARE_VERSIONEN = (1, 2, 3)


class ProjektdateiFehler(ModellFehler):
    """Die Datei ist keine lesbare Verteilerly-Projektdatei."""


# --------------------------------------------------------------------------
# Schreiben
# --------------------------------------------------------------------------


def _ader_raus(ader: Ader) -> dict[str, Any]:
    daten = {"seite": ader.seite}
    # Leere Felder werden weggelassen, damit die Datei lesbar bleibt.
    for feld in ("farbe", "bezeichnung", "bemerkung"):
        wert = getattr(ader, feld)
        if wert:
            daten[feld] = wert
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
    return {
        "dateikennung": DATEIKENNUNG,
        "formatversion": FORMATVERSION,
        "briefkopf": dict(projekt.briefkopf),
        "eigene_felder": dict(projekt.eigene_felder),
        # Abgewaehlte Felder behalten ihren Inhalt - nur die Auswahl wird
        # vermerkt.
        "ausgeblendet": sorted(projekt.ausgeblendet),
        "verteiler": _verteiler_raus(projekt.verteiler),
    }


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
        raise ProjektdateiFehler("Das ist keine Verteilerly-Projektdatei")
    version = daten.get("formatversion")
    if version not in LESBARE_VERSIONEN:
        lesbar = ", ".join(str(v) for v in LESBARE_VERSIONEN)
        raise ProjektdateiFehler(
            f"Formatversion {version} wird nicht unterstuetzt (lesbar: {lesbar})"
        )
    return Projekt(
        verteiler=_verteiler_rein(daten.get("verteiler", {})),
        briefkopf=dict(daten.get("briefkopf") or {}),
        eigene_felder=dict(daten.get("eigene_felder") or {}),
        ausgeblendet=set(daten.get("ausgeblendet") or ()),
    )


def laden(pfad: pathlib.Path) -> Projekt:
    pfad = pathlib.Path(pfad)
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except json.JSONDecodeError as fehler:
        raise ProjektdateiFehler(f"{pfad.name} ist kein gueltiges JSON - {fehler}") from None
    except (KeyError, TypeError) as fehler:
        raise ProjektdateiFehler(f"{pfad.name} ist unvollstaendig - {fehler}") from None
    if not isinstance(daten, dict):
        raise ProjektdateiFehler(f"{pfad.name} enthaelt kein Projekt")
    return aus_dict(daten)
