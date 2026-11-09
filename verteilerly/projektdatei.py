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
    LEISTEN_SCHREIBWEISEN,
    LEISTEN_ZAHLEN,
    MAX_RANGIERUNGEN_JE_ADER,
    SEITEN,
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
FORMATVERSION = 11
# Fassung 1 nannte die Buchten noch Reihen, Fassung 2 kannte noch keine
# abgewaehlten Felder, Fassung 3 noch keinen Vermerk im Rangierfeld,
# Fassung 4 noch keine Wahl der Blattarten fuer die eigenen Felder,
# Fassung 5 noch keine eigenen Beschriftungen, Fassung 6 noch keinen
# Textstil je Zelle, Fassung 7 noch keine geteilten Zellen, Fassung 8
# noch keine Leisten mit Buchstaben, und bis Fassung 9 stand die Wahl der
# Blattarten fuer die eigenen Felder am Projekt - seither in der
# Blattvorlage, und ``eigene_felder_auf`` wird beim Lesen uebergangen.
# Fassung 10 kannte noch keine umgekehrte Verteilerbelegung.
# Solche Dateien werden weiter gelesen; geschrieben wird immer die neue
# Fassung.
LESBARE_VERSIONEN = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)


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
                    # Die Stelle im Kabel steht nur dabei, wenn sie
                    # festgehalten ist: sonst ergibt sie sich aus der
                    # Reihenfolge, und die Datei bleibt, wie sie war.
                    {
                        "leiste": a.leiste,
                        "start_da": a.start_da,
                        "anzahl_da": a.anzahl_da,
                        **(
                            {"ab_kabel_da": a.ab_kabel_da}
                            if a.ab_kabel_da is not None
                            else {}
                        ),
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
    # Ebenso die Leserichtung der Belegung: geschrieben nur, wenn sie
    # umgekehrt ist - die Normalform braucht keinen Eintrag.
    if projekt.belegung_umgekehrt:
        daten["belegung_umgekehrt"] = True
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
                Kabelabschnitt(
                    a["leiste"],
                    a["start_da"],
                    a["anzahl_da"],
                    a.get("ab_kabel_da"),
                )
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


def _ganzzahl(wert, was: str) -> int:
    """Eine ganze Zahl aus der Datei - sonst eine Meldung statt eines Absturzes."""
    if isinstance(wert, bool) or not isinstance(wert, int):
        raise ProjektdateiFehler(u("{0} muss eine ganze Zahl sein").format(was))
    return wert


def _pruefen(verteiler: Verteiler) -> None:
    """Weist eine in sich widerspruechliche Projektdatei ab (Audit 4).

    Der Verteiler wird aus dem Dict direkt gebaut, nicht ueber
    ``aus_buchten()`` - keine der Pruefungen des Modells greift also. Eine
    Datei aus fremder Hand koennte darum Unsinn enthalten, der erst beim
    Zeichnen auffiele: ein Stift mit der Nummer ``"eins"`` (TypeError),
    eine Leiste ohne Stifte (Division durch null), ein Kabel oder eine
    Rangierung auf eine Stelle, die es nicht gibt. Hier faellt das als
    Meldung auf, nicht spaeter als Absturz im Fenster.
    """
    if not isinstance(verteiler.name, str) or not isinstance(verteiler.nummer, str):
        raise ProjektdateiFehler(u("Name und Nummer des Verteilers muessen Text sein"))
    if not verteiler.buchten:
        raise ProjektdateiFehler(u("Der Verteiler hat keine Buchten"))

    leisten: dict[int, Leiste] = {}
    for bucht in verteiler.buchten:
        _ganzzahl(bucht.nummer, u("Die Buchtnummer"))
        if not bucht.leisten:
            raise ProjektdateiFehler(u("Bucht {0} hat keine Leisten").format(bucht.nummer))
        for leiste in bucht.leisten:
            nr = _ganzzahl(leiste.nummer, u("Die Leistennummer"))
            if nr in leisten:
                raise ProjektdateiFehler(
                    u("Die Leistennummer {0} kommt mehrfach vor").format(nr)
                )
            if not leiste.stifte:
                raise ProjektdateiFehler(u("Leiste {0} hat keine Stifte").format(nr))
            for stift in leiste.stifte:
                _ganzzahl(stift.nummer, u("Die Stiftnummer"))
                for seite in (stift.a.seite, stift.b.seite):
                    if seite not in SEITEN:
                        raise ProjektdateiFehler(
                            u("Leiste {0} Stift {1}: unbekannte Aderseite {2!r}").format(
                                nr, stift.nummer, seite)
                        )
            leisten[nr] = leiste

    for k in verteiler.kabel:
        for a in k.abschnitte:
            _ganzzahl(a.leiste, u("Die Leiste eines Kabelabschnitts"))
            start = _ganzzahl(a.start_da, u("Der Startstift eines Kabelabschnitts"))
            anzahl = _ganzzahl(a.anzahl_da, u("Die DA-Zahl eines Kabelabschnitts"))
            leiste = leisten.get(a.leiste)
            if leiste is None:
                raise ProjektdateiFehler(
                    u("Ein Kabel liegt auf Leiste {0}, die es nicht gibt").format(a.leiste)
                )
            if start < 1 or anzahl < 1 or start + anzahl - 1 > leiste.da_anzahl:
                raise ProjektdateiFehler(
                    u("Ein Kabel liegt auf Leiste {0} DA {1}–{2}, die es dort nicht gibt").format(
                        a.leiste, start, start + anzahl - 1)
                )

    belegt: dict[tuple, int] = {}
    for r in verteiler.rangierungen:
        enden = (r.von, r.nach)
        for ende in enden:
            leiste = leisten.get(ende.leiste)
            if leiste is None or not 1 <= ende.stift <= leiste.da_anzahl:
                raise ProjektdateiFehler(
                    u("Eine Rangierung zeigt auf {0}, die es nicht gibt").format(ende)
                )
        if (r.von.leiste, r.von.stift, r.von.seite) == (r.nach.leiste, r.nach.stift, r.nach.seite):
            raise ProjektdateiFehler(
                u("Eine Rangierung verbindet eine Ader mit sich selbst")
            )
        for ende in enden:
            schluessel = (ende.leiste, ende.stift, ende.seite)
            belegt[schluessel] = belegt.get(schluessel, 0) + 1
            if belegt[schluessel] > MAX_RANGIERUNGEN_JE_ADER:
                raise ProjektdateiFehler(
                    u("{0} traegt mehr als {1} Rangierungen").format(
                        ende, MAX_RANGIERUNGEN_JE_ADER)
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
    verteiler = _verteiler_rein(daten.get("verteiler", {}))
    _pruefen(verteiler)
    # ``ausgeblendet`` ist eine Liste von Feldnamen. Ein einzelner String
    # wuerde sonst in seine Buchstaben zerfallen ({'f','i',...}) - darum
    # erst den Typ pruefen (Audit 10).
    ausgeblendet = daten.get("ausgeblendet") or []
    if not isinstance(ausgeblendet, (list, tuple)):
        raise ProjektdateiFehler(u("„ausgeblendet“ muss eine Liste von Feldern sein"))
    return Projekt(
        verteiler=verteiler,
        briefkopf=dict(daten.get("briefkopf") or {}),
        eigene_felder=dict(daten.get("eigene_felder") or {}),
        ausgeblendet=set(str(feld) for feld in ausgeblendet),
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
        # Aeltere Dateien kannten nur die Normalform: von links nach rechts.
        belegung_umgekehrt=bool(daten.get("belegung_umgekehrt", False)),
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
