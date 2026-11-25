"""Projektdaten in den Einstellungen merken.

Wie die Leisten heissen und ob die Verteilerbelegung umgekehrt ist, steht
**nicht** hier: beides gehoert dem Verteiler und steht in seiner
Projektdatei. Eine Vorgabe dafuer gab es bis 2026.10.04 - sie fuehrte
dazu, dass ein neuer Verteiler die Beschriftung des letzten erbte, ohne
dass jemand danach gefragt hatte.

Die Projektdaten sind bei einem Errichter meist dieselben: Firma, Kürzel,
Kunde wiederholen sich von Verteiler zu Verteiler. Er wird deshalb in der
Verteilerly.conf mitgeführt und in einen neuen Verteiler übernommen -
gespeichert bleibt er trotzdem im Projekt, denn dort gehört er hin.

Die Funktionen nehmen ein QSettings entgegen und kennen die Oberfläche
nicht; damit sind sie ohne Fenster prüfbar.
"""

from __future__ import annotations

from .modell import LEISTEN_SCHREIBWEISEN, LEISTEN_ZAHLEN, Projekt

GRUPPE_BRIEFKOPF = "briefkopf"
GRUPPE_BESCHRIFTUNGEN = "beschriftungen"
SCHLUESSEL_AUSGEBLENDET = "felder_ausgeblendet"
#: Wie die Leisten im naechsten neuen Verteiler heissen. Im Projekt steht
#: die Wahl mit; hier steht sie als Vorgabe, weil ein Errichter seine
#: Verteiler meist gleich beschriftet.


def _liste(wert) -> list[str]:
    """QSettings gibt eine einelementige Liste als Zeichenkette zurueck."""
    if wert is None:
        return []
    if isinstance(wert, str):
        return [wert] if wert else []
    return [str(eintrag) for eintrag in wert]


def _gruppe_schreiben(einstellungen, gruppe: str, werte: dict[str, str]) -> None:
    einstellungen.beginGroup(gruppe)
    einstellungen.remove("")          # alte Felder mitnehmen, nicht anhaeufen
    for name, wert in werte.items():
        if str(wert).strip():
            einstellungen.setValue(name, wert)
    einstellungen.endGroup()


def _gruppe_lesen(einstellungen, gruppe: str) -> dict[str, str]:
    einstellungen.beginGroup(gruppe)
    werte = {
        name: str(einstellungen.value(name, ""))
        for name in einstellungen.childKeys()
    }
    einstellungen.endGroup()
    return {name: wert for name, wert in werte.items() if wert}


def briefkopf_sichern(einstellungen, projekt: Projekt) -> None:
    """Schreibt Projektdaten und die Auswahl in die conf.

    Die **eigenen Felder** stehen nicht dabei: welche es gibt, sagt die
    Blattvorlage, und ihre Inhalte gehoeren dem einzelnen Projekt - eine
    Vorgabe dafuer gab es einmal und hat mehr verwirrt als geholfen.
    """
    _gruppe_schreiben(einstellungen, GRUPPE_BRIEFKOPF, projekt.briefkopf)
    _gruppe_schreiben(
        einstellungen, GRUPPE_BESCHRIFTUNGEN, projekt.eigene_beschriftungen()
    )
    einstellungen.setValue(SCHLUESSEL_AUSGEBLENDET, sorted(projekt.ausgeblendet))
    einstellungen.sync()


def briefkopf_laden(einstellungen) -> tuple[dict[str, str], set[str]]:
    """Was in der conf steht: Projektdaten und abgewaehlte Felder."""
    return (
        _gruppe_lesen(einstellungen, GRUPPE_BRIEFKOPF),
        set(_liste(einstellungen.value(SCHLUESSEL_AUSGEBLENDET))),
    )


def beschriftungen_laden(einstellungen) -> dict[str, str]:
    """Die gemerkten eigenen Woerter fuer das Schriftfeld.

    Eigener Zugriff, damit die Rueckgabewerte von ``briefkopf_laden``
    bleiben, wie sie sind.
    """
    return _gruppe_lesen(einstellungen, GRUPPE_BESCHRIFTUNGEN)


def leistenweise(wert) -> str:
    """Prueft eine Angabe; was das Programm nicht kennt, wird gezaehlt.

    Eine Einstellung aus einer neueren Fassung soll nichts aufhalten -
    dann heissen die Leisten eben wieder 1, 2, 3.
    """
    wert = str(wert or "")
    return wert if wert in LEISTEN_SCHREIBWEISEN else LEISTEN_ZAHLEN


def briefkopf_uebernehmen(einstellungen, projekt: Projekt) -> Projekt:
    """Legt die gemerkten Angaben in ein frisches Projekt.

    Was im Projekt schon steht, bleibt stehen - uebernommen wird nur, was
    dort fehlt. Damit ueberschreibt die Vorgabe nie eine Eingabe.
    """
    briefkopf, ausgeblendet = briefkopf_laden(einstellungen)
    for name, wert in briefkopf.items():
        projekt.briefkopf.setdefault(name, wert)
    for marke, wert in beschriftungen_laden(einstellungen).items():
        projekt.beschriftungen.setdefault(marke, wert)
    projekt.ausgeblendet |= ausgeblendet
    return projekt




# -- Zuletzt geoeffnet -------------------------------------------------------

#: Die zuletzt geoeffneten oder gespeicherten Projektdateien, neueste zuerst,
#: als JSON-Liste - ein QSettings gibt eine einelementige Liste sonst als
#: Zeichenkette zurueck. Sie gehoert dem Rechner und reist darum in keinem
#: Paket mit (nicht in ``UEBERNAHME_EINZELN``).
SCHLUESSEL_ZULETZT = "zuletzt_geoeffnet"
#: So viele stehen im Menue *Datei ▸ Zuletzt geöffnet*.
ZULETZT_HOECHSTENS = 5


def _gleicher_pfad(a: str, b: str) -> bool:
    """Unter Windows ist C:\\A dasselbe wie c:\\a - normcase weiss das."""
    import os

    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def zuletzt_geoeffnet(einstellungen) -> list[str]:
    """Die gemerkten Pfade, neueste zuerst - Unlesbares faellt weg."""
    import json

    try:
        werte = json.loads(str(einstellungen.value(SCHLUESSEL_ZULETZT, "") or "[]"))
    except ValueError:
        return []
    if not isinstance(werte, list):
        return []
    return [str(w) for w in werte if isinstance(w, str) and w][:ZULETZT_HOECHSTENS]


def _zuletzt_schreiben(einstellungen, pfade: list[str]) -> list[str]:
    import json

    pfade = pfade[:ZULETZT_HOECHSTENS]
    einstellungen.setValue(SCHLUESSEL_ZULETZT, json.dumps(pfade, ensure_ascii=False))
    return pfade


def zuletzt_merken(einstellungen, pfad) -> list[str]:
    """Stellt ``pfad`` nach vorn - ein schon gemerkter rueckt nur auf."""
    import pathlib

    neu = str(pathlib.Path(pfad).absolute())
    bisher = [p for p in zuletzt_geoeffnet(einstellungen) if not _gleicher_pfad(p, neu)]
    return _zuletzt_schreiben(einstellungen, [neu] + bisher)


def zuletzt_vergessen(einstellungen, pfad=None) -> list[str]:
    """Nimmt einen Pfad aus der Liste - ohne Angabe alle."""
    if pfad is None:
        return _zuletzt_schreiben(einstellungen, [])
    bisher = zuletzt_geoeffnet(einstellungen)
    return _zuletzt_schreiben(
        einstellungen, [p for p in bisher if not _gleicher_pfad(p, str(pfad))]
    )
