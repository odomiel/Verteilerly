"""Einen Verteiler mit Zufallsdaten fuellen - ohne Qt.

Gebraucht wird so etwas zum Vorfuehren und Ausprobieren: wie sieht die
Belegung aus, wenn sie voll ist, wie das Leistenblatt mit langen Namen,
wie die Mappe mit Rangierungen quer ueber den Verteiler? Von Hand
eingetippt dauert das eine halbe Stunde.

Gefuellt wird nur ueber die Wege, die auch die Bedienung nimmt
(``kabel_anlegen``, ``farben_eintragen``, ``rangierung_anlegen``) - so
entsteht nichts, was das Programm selbst nicht zuliesse, und die
Projektdatei besteht ihre Pruefung beim Lesen.

Was hier steht, ist der Inhalt des **Dokuments**, nicht die Oberflaeche:
die Woerter gehen darum nicht durch ``u()``.
"""

from __future__ import annotations

import datetime
import random
from dataclasses import dataclass

from ...farbcodes import Kabeltypen, farben_eintragen
from ...modell import (
    RANGIERVORLAGEN,
    Aderadresse,
    ModellFehler,
    Projekt,
    Verteiler,
)

#: Wie gross ein Kabel wird - in Doppeladern. Kleine kommen oefter vor.
GROESSEN = (2, 2, 2, 4, 4, 6, 10, 10, 20)
#: Wie oft hinter einem Kabel Doppeladern frei bleiben.
LUECKE = 0.2
#: Wie oft ein Kabel nicht ganz aufliegt (gekuerzt, mit Rest).
GEKUERZT = 0.08
#: Wie viele der belegten Doppeladern rangiert werden (Anteil).
RANGIERT = 0.15
#: Wie oft eine belegte Ader eine Bemerkung traegt.
BEMERKT = 0.1
#: Wie oft eine unrangierte Ader einen Vermerk traegt.
VERMERKT = 0.03

ORTE = (
    "Whg", "Büro", "Keller", "Dachgeschoss", "Hausmeister", "Aufzug",
    "Heizung", "Empfang", "Lager", "Werkstatt", "Labor", "Archiv",
    "Besprechung", "Serverraum", "Pforte", "Kantine",
)
ENDGERAETE = (
    "TAE", "Datendose", "Türsprechstelle", "Brandmelder", "Aufzugnotruf",
    "Fax", "Alarmanlage", "Zählerfernauslesung", "Zeiterfassung",
)
BEMERKUNGEN = (
    "geprüft", "Schirm aufgelegt", "Reserve", "nachmessen",
    "Dämpfung hoch", "neu verlegt", "alte Zuleitung",
)
FIRMEN = (
    "Elektro Brandt GmbH", "Fernmeldebau Kühn", "NetzWerk Süd KG",
    "Telekabel Lorenz", "Hausnetz Petersen",
)
KUNDEN = (
    "Wohnbau Lindenhof", "Stadtwerke Nord", "Klinikum am Park",
    "Schule Am Hang", "Bürohaus Kaiserstraße",
)


@dataclass
class Fuellstand:
    """Was beim Fuellen herauskam - fuer die Meldung."""

    kabel: int = 0
    belegt: int = 0
    rangierungen: int = 0


def zufallsprojekt(
    verteiler: Verteiler,
    kabeltypen: Kabeltypen | None = None,
    zufall: random.Random | None = None,
) -> Projekt:
    """Ein Projekt um diesen (leeren) Verteiler, mit Zufallsdaten gefuellt.

    ``zufall`` laesst sich vorgeben - mit festem Startwert kommt jedes Mal
    derselbe Verteiler heraus, darauf baut die Testreihe.
    """
    zufall = zufall or random.Random()
    if not verteiler.name:
        verteiler.name = f"{zufall.choice(KUNDEN)} {zufall.choice(ORTE)}"
    if not verteiler.nummer:
        verteiler.nummer = f"V{zufall.randint(1, 999):03d}"
    fuellen(verteiler, kabeltypen, zufall)
    heute = datetime.date.today().strftime("%d.%m.%Y")
    kuerzel = "".join(zufall.choice("ABCDEFGHKLMNPRSTW") for _ in range(2))
    return Projekt(
        verteiler=verteiler,
        briefkopf={
            "firma": zufall.choice(FIRMEN),
            "kunde": zufall.choice(KUNDEN),
            "anlagennummer": str(zufall.randint(10000, 99999)),
            "kundennummer": f"K-{zufall.randint(1000, 9999)}",
            "erstellt_am": heute,
            "erstellt_von": kuerzel,
            "kuerzel": kuerzel,
        },
    )


def fuellen(
    verteiler: Verteiler,
    kabeltypen: Kabeltypen | None = None,
    zufall: random.Random | None = None,
) -> Fuellstand:
    """Legt Kabel auf, beschriftet die Adern und rangiert einige davon."""
    zufall = zufall or random.Random()
    typen = [typ.id for typ in kabeltypen.alle] if kabeltypen else []
    stand = Fuellstand()
    belegt: list[tuple[int, int]] = []

    for leiste in verteiler.alle_leisten:
        stift = 1
        while stift <= leiste.da_anzahl:
            if zufall.random() < LUECKE:
                stift += zufall.randint(1, 3)
                continue
            frei = leiste.da_anzahl - stift + 1
            anzahl = min(zufall.choice(GROESSEN), frei)
            stand.kabel += 1
            ort = zufall.choice(ORTE)
            name = f"K{stand.kabel:02d} {ort} {zufall.randint(1, 30)}"
            gesamt = anzahl
            if zufall.random() < GEKUERZT:
                gesamt += zufall.choice((2, 4))
            kabel = verteiler.kabel_anlegen(
                name, leiste.nummer, stift, anzahl,
                kabeltyp=zufall.choice(typen) if typen else None,
                da_gesamt=gesamt,
            )
            if kabeltypen and kabel.kabeltyp:
                farben_eintragen(verteiler, kabel, kabeltypen)
            for da in range(stift, stift + anzahl):
                ader = leiste.stift(da).a
                ader.bezeichnung = (
                    f"{ort} {zufall.randint(1, 30)} {zufall.choice(ENDGERAETE)}"
                )
                if zufall.random() < BEMERKT:
                    ader.bemerkung = zufall.choice(BEMERKUNGEN)
                belegt.append((leiste.nummer, da))
            stand.belegt += anzahl
            stift += anzahl

    stand.rangierungen = _rangieren(verteiler, belegt, zufall)
    _vermerken(verteiler, belegt, zufall)
    return stand


def _rangieren(verteiler: Verteiler, belegt, zufall: random.Random) -> int:
    """Verbindet Doppeladern auf verschiedenen Leisten, a mit a und b mit b.

    Was das Modell ablehnt (schon verbunden, schon zwei Rangierungen an
    der Ader), wird uebergangen - der Zufall darf daneben greifen.
    """
    if len({leiste for leiste, _ in belegt}) < 2:
        return 0
    gezogen = 0
    for _ in range(int(len(belegt) * RANGIERT)):
        (l1, d1), (l2, d2) = zufall.sample(belegt, 2)
        if l1 == l2:
            continue
        try:
            for seite in ("a", "b"):
                verteiler.rangierung_anlegen(
                    Aderadresse(l1, d1, seite), Aderadresse(l2, d2, seite)
                )
        except ModellFehler:
            continue
        gezogen += 1
    return gezogen


def _vermerken(verteiler: Verteiler, belegt, zufall: random.Random) -> None:
    """Ein paar Vermerke (``defekt``, ``direkt`` …) an unrangierten Adern."""
    for leiste_nr, da in belegt:
        adresse = Aderadresse(leiste_nr, da, "a")
        if zufall.random() >= VERMERKT or verteiler.rangierungen_an(adresse):
            continue
        verteiler.ader(adresse).vermerk = zufall.choice(RANGIERVORLAGEN)
