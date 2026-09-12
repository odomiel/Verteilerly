"""Projektdaten und eigene Felder in den Einstellungen merken.

Die Projektdaten sind bei einem Errichter meist dieselben: Firma, Kürzel,
Kunde wiederholen sich von Verteiler zu Verteiler. Er wird deshalb in der
Verteilerly.conf mitgeführt und in einen neuen Verteiler übernommen -
gespeichert bleibt er trotzdem im Projekt, denn dort gehört er hin.

Die Funktionen nehmen ein QSettings entgegen und kennen die Oberfläche
nicht; damit sind sie ohne Fenster prüfbar.
"""

from __future__ import annotations

from .modell import Projekt

GRUPPE_BRIEFKOPF = "briefkopf"
GRUPPE_EIGENE = "eigene_felder"
SCHLUESSEL_AUSGEBLENDET = "felder_ausgeblendet"


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
    """Schreibt Projektdaten, eigene Felder und die Auswahl in die conf."""
    _gruppe_schreiben(einstellungen, GRUPPE_BRIEFKOPF, projekt.briefkopf)
    _gruppe_schreiben(einstellungen, GRUPPE_EIGENE, projekt.eigene_felder)
    einstellungen.setValue(SCHLUESSEL_AUSGEBLENDET, sorted(projekt.ausgeblendet))
    einstellungen.sync()


def briefkopf_laden(einstellungen) -> tuple[dict[str, str], dict[str, str], set[str]]:
    """Was in der conf steht: Projektdaten, eigene Felder, abgewaehlte Felder."""
    return (
        _gruppe_lesen(einstellungen, GRUPPE_BRIEFKOPF),
        _gruppe_lesen(einstellungen, GRUPPE_EIGENE),
        set(_liste(einstellungen.value(SCHLUESSEL_AUSGEBLENDET))),
    )


def briefkopf_uebernehmen(einstellungen, projekt: Projekt) -> Projekt:
    """Legt die gemerkten Angaben in ein frisches Projekt.

    Was im Projekt schon steht, bleibt stehen - uebernommen wird nur, was
    dort fehlt. Damit ueberschreibt die Vorgabe nie eine Eingabe.
    """
    briefkopf, eigene, ausgeblendet = briefkopf_laden(einstellungen)
    for name, wert in briefkopf.items():
        projekt.briefkopf.setdefault(name, wert)
    for name, wert in eigene.items():
        projekt.eigene_felder.setdefault(name, wert)
    projekt.ausgeblendet |= ausgeblendet
    return projekt
