"""Im Projekt suchen.

Ein Verteiler mit zwoelf Leisten zu zwanzig Doppeladern traegt
vierhundertachtzig Adern mit vier Feldern - wer eine Nebenstelle sucht,
soll nicht Leiste fuer Leiste durchblaettern. Gesucht wird in allem, was
jemand von Hand eingetragen hat:

* die Felder der Ader (Farbe, Bezeichnung, Bemerkung), samt dem zweiten
  Text einer geteilten Zelle,
* was im Rangierfeld steht - Ziele in der eingestellten Schreibweise und
  der Vermerk,
* die Beschriftung der Kabel,
* die Projektdaten und die eigenen Felder.

Hier steht nur das Suchen: kein Qt, keine Anzeige. Die Oberflaeche macht
aus einer Fundstelle einen Eintrag in der Liste und springt hin
(``gui/dialoge.py``, ``gui/hauptfenster.py``).
"""

from __future__ import annotations

from dataclasses import dataclass

from .modell import (
    BRIEFKOPF_BESCHRIFTUNG,
    LEISTEN_ZAHLEN,
    Aderadresse,
    Projekt,
    leistenname,
    mehrzahl,
)
from .schreibweisen import Schreibweise
from .sprachen import u

# Die Felder einer Ader, in der Reihenfolge der Leistenansicht, mit der
# Beschriftung, unter der sie dort steht.
ADERFELDER = (
    ("farbe", "Farbe"),
    ("bezeichnung", "Bezeichnung"),
    ("rangierung", "Rangierung"),
    ("bemerkung", "Bemerkung"),
)

# Wo eine Fundstelle liegt.
ADER = "ader"
KABEL = "kabel"
PROJEKTDATEN = "projektdaten"


@dataclass(frozen=True)
class Fundstelle:
    """Eine Stelle, an der das gesuchte Wort steht.

    ``feld`` ist die Marke des Feldes ("bezeichnung", "rangierung", bei
    den Projektdaten der Feldname); ``beschriftung`` dasselbe in Worten.
    ``text`` ist der ganze Inhalt der Zelle, nicht nur das Wort - in der
    Liste soll zu lesen sein, was dort steht.
    """

    bereich: str
    feld: str
    beschriftung: str
    text: str
    ort: str
    adresse: Aderadresse | None = None
    leiste: int = 0

    def __str__(self) -> str:
        return f"{self.ort} · {self.beschriftung}: {self.text}"


def _passt(text: str, wort: str) -> bool:
    """Gross- und Kleinschreibung ist einerlei - wie in der Hilfe."""
    return bool(text) and wort in text.casefold()


def _ort(bucht: int, adresse: Aderadresse, leisten: str = LEISTEN_ZAHLEN) -> str:
    return u("Bucht {0} · Leiste {1} · Stift {2}{3}").format(
        bucht, leistenname(adresse.leiste, leisten), adresse.stift, adresse.seite
    )


def suchen(
    projekt: Projekt,
    wort: str,
    schreibweise: Schreibweise | None = None,
) -> list[Fundstelle]:
    """Alle Fundstellen zu diesem Wort, in der Reihenfolge des Verteilers.

    Ein leeres oder einbuchstabiges Wort findet nichts: bei einem
    einzelnen Buchstaben stuende der halbe Verteiler in der Liste.
    """
    gesucht = (wort or "").strip().casefold()
    if len(gesucht) < 2:
        return []

    verteiler = projekt.verteiler
    gefunden: list[Fundstelle] = []

    for bucht in verteiler.buchten:
        for leiste in bucht.leisten:
            for stift in leiste.stifte:
                for seite in ("a", "b"):
                    adresse = Aderadresse(leiste.nummer, stift.nummer, seite)
                    gefunden.extend(
                        _in_der_ader(
                            projekt, bucht.nummer, adresse, gesucht, schreibweise
                        )
                    )

    for kabel in verteiler.kabel:
        if not _passt(kabel.beschriftung, gesucht):
            continue
        anfang = kabel.abschnitte[0] if kabel.abschnitte else None
        leisten = sorted({teil.leiste for teil in kabel.abschnitte})
        ort = (
            u("Leiste {0}").format(", ".join(
                projekt.leistenname(nummer) for nummer in leisten
            ))
            if leisten
            else u("ohne Leiste")
        )
        gefunden.append(
            Fundstelle(
                bereich=KABEL,
                feld="kabel",
                beschriftung=u("Kabel"),
                text=kabel.beschriftung,
                ort=f"{ort} · {mehrzahl(kabel.da_aufgelegt, 'DA', 'DA')}",
                adresse=(
                    Aderadresse(anfang.leiste, anfang.start_da, "a")
                    if anfang
                    else None
                ),
                leiste=anfang.leiste if anfang else 0,
            )
        )

    gefunden.extend(_in_den_projektdaten(projekt, gesucht))
    return gefunden


def _in_der_ader(
    projekt: Projekt,
    bucht: int,
    adresse: Aderadresse,
    gesucht: str,
    schreibweise: Schreibweise | None,
) -> list[Fundstelle]:
    """Die vier Felder einer Ader - die geteilte Zelle mit beiden Texten."""
    verteiler = projekt.verteiler
    ader = verteiler.ader(adresse)
    gefunden = []
    for feld, beschriftung in ADERFELDER:
        if feld == "rangierung":
            text = verteiler.rangierfeld(
                adresse, schreibweise, projekt.leisten_schreibweise
            )
        else:
            text = getattr(ader, feld, "")
            zweiter = ader.teilung(feld).text
            if zweiter:
                # Beide Texte gehoeren zur Zelle - gesucht wird in beiden,
                # und in der Liste stehen sie so, wie sie auf dem Blatt
                # nebeneinander stuenden.
                text = f"{text} {zweiter}".strip()
        if _passt(text, gesucht):
            gefunden.append(
                Fundstelle(
                    bereich=ADER,
                    feld=feld,
                    beschriftung=u(beschriftung),
                    text=text,
                    ort=_ort(bucht, adresse, projekt.leisten_schreibweise),
                    adresse=adresse,
                    leiste=adresse.leiste,
                )
            )
    return gefunden


def _in_den_projektdaten(projekt: Projekt, gesucht: str) -> list[Fundstelle]:
    """Briefkopf und eigene Felder - dort steht der Kunde, nicht in der Leiste."""
    gefunden = []
    for feld, beschriftung, wert in (
        ("verteilername", u("Verteilername"), projekt.verteiler.name),
        ("verteilernummer", u("Verteilernummer"), projekt.verteiler.nummer),
    ):
        if _passt(wert, gesucht):
            gefunden.append(
                Fundstelle(
                    bereich=PROJEKTDATEN,
                    feld=feld,
                    beschriftung=beschriftung,
                    text=wert,
                    ort=u("Projektdaten"),
                )
            )
    for name, wert in projekt.briefkopf.items():
        if _passt(wert, gesucht):
            gefunden.append(
                Fundstelle(
                    bereich=PROJEKTDATEN,
                    feld=name,
                    beschriftung=u(BRIEFKOPF_BESCHRIFTUNG.get(name, name)),
                    text=wert,
                    ort=u("Projektdaten"),
                )
            )
    for name, wert in projekt.eigene_felder.items():
        if _passt(wert, gesucht):
            gefunden.append(
                Fundstelle(
                    bereich=PROJEKTDATEN,
                    feld=name,
                    beschriftung=name,
                    text=wert,
                    ort=u("Projektdaten · eigenes Feld"),
                )
            )
    return gefunden
