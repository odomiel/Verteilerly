"""Was in diesem Programm steckt.

Alle Bausteine stehen unter LGPL, BSD, MIT oder PSF. Damit das im
laufenden Programm nachzusehen ist, sammelt dieses Modul die Fassungen
zur Laufzeit ein: was tatsaechlich geladen ist, nicht was in einer Liste
steht.

Fehlt ein Baustein, wird das gesagt statt zu scheitern - ein Bericht, der
am ersten fehlenden Modul abbricht, hilft niemandem.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass

FEHLT = "nicht vorhanden"


@dataclass(frozen=True)
class Baustein:
    """Ein Baustein mit seiner Fassung und der Lizenz, unter der er steht."""

    name: str
    fassung: str
    lizenz: str
    aufgabe: str = ""

    @property
    def vorhanden(self) -> bool:
        return self.fassung != FEHLT


def _fassung(modul: str, feld: str = "__version__") -> str:
    """Die Fassung eines Moduls - ohne es zur Bedingung zu machen."""
    try:
        geladen = __import__(modul)
    except ImportError:
        return FEHLT
    wert = getattr(geladen, feld, None)
    return str(wert) if wert else "unbekannt"


def _qt() -> str:
    try:
        from PySide6 import QtCore
    except ImportError:
        return FEHLT
    return QtCore.qVersion()


def abhaengigkeiten() -> list[Baustein]:
    """Die Bausteine des Programms, in fester Reihenfolge."""
    return [
        Baustein("Python", sys.version.split()[0], "PSF", "Sprache"),
        Baustein("PySide6", _fassung("PySide6"), "LGPLv3", "Oberfläche"),
        Baustein("Qt", _qt(), "LGPLv3", "Oberfläche und Vorschau"),
        Baustein("ReportLab", _fassung("reportlab", "Version"), "BSD", "PDF"),
        Baustein("openpyxl", _fassung("openpyxl"), "MIT", "Excel-Mappe"),
        Baustein("PyYAML", _fassung("yaml"), "MIT", "Vorlagen und Kabeltypen"),
    ]


def umgebung() -> list[tuple[str, str]]:
    """Wo das Programm laeuft - fuer eine Rueckfrage aus dem Feld."""
    from . import pfade

    return [
        ("System", f"{platform.system()} {platform.release()}"),
        ("Gepackt", "ja" if pfade.gepackt() else "nein, aus dem Quelltext"),
        ("Arbeitsordner", str(pfade.eigener_datenordner())),
        ("Einstellungen", str(pfade.einstellungsdatei())),
    ]
