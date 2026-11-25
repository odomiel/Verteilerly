"""Was an Verteilerly_CSV2Excel geht - ohne Qt.

Das Werkzeug nimmt CSV-Dateien als Aufrufparameter an und zeigt sie dann
als *Uebergebene CSV-Dateien*; ``--start`` verarbeitet sofort,
``--export ORDNER`` setzt den Zielordner nur fuer diesen Aufruf. Hier
steht, wie die Datei heisst, wo sie liegt und wie der Aufruf aussieht -
gestartet wird in ``__init__``.
"""

from __future__ import annotations

import pathlib
import tempfile

from ...sprachen import u
from ..projekt.anlage import sicherer_name

#: So heisst das Werkzeug, wie es ausgeliefert wird.
PROGRAMMNAME = "Verteilerly_CSV2Excel.exe"
#: Unterordner im Temp-Ordner, in den die CSV fuer die Uebergabe kommt.
ABLAGE = "Verteilerly-CSV2Excel"


def ablageordner() -> pathlib.Path:
    """Wohin die CSV fuer die Uebergabe geschrieben wird.

    In den Temp-Ordner des Rechners, nicht neben die Projektdatei: die
    Datei ist nur der Weg zum Werkzeug, das Ergebnis ist die Mappe, die
    es schreibt. Eine CSV desselben Namens wird beim naechsten Mal
    ueberschrieben.
    """
    return pathlib.Path(tempfile.gettempdir()) / ABLAGE


def csv_name(projekt, pfad: pathlib.Path | None) -> str:
    """Der Dateiname der CSV - wie beim Export vorgeschlagen.

    Erst der Name der Projektdatei, dann der des Verteilers. Das Werkzeug
    benennt seine Mappe nach Verteiler und Verteilernummer und nimmt den
    Namen der CSV nur, wenn der Verteiler keinen hat.
    """
    stamm = pfad.name.split(".")[0] if pfad else ""
    stamm = sicherer_name(stamm or projekt.verteiler.name)
    return f"{stamm or 'verteiler'}.csv"


def argumente(csv: pathlib.Path, export: str = "", sofort: bool = False) -> list[str]:
    """Die Aufrufparameter fuer das Werkzeug.

    Ohne ``--beenden``: das Fenster bleibt offen, damit man sieht, was
    entstanden ist - oder warum nicht.
    """
    teile = [str(csv)]
    if export:
        teile += ["--export", export]
    if sofort:
        teile.append("--start")
    return teile


def programm_grund(pfad: str) -> str:
    """Warum sich mit diesem Pfad nichts starten laesst - oder ""."""
    if not str(pfad or "").strip():
        return u("Es ist noch nicht eingestellt, wo Verteilerly_CSV2Excel liegt.")
    ort = pathlib.Path(pfad)
    if not ort.exists():
        return u("Verteilerly_CSV2Excel liegt nicht mehr unter {0}.").format(ort)
    if not ort.is_file():
        return u("{0} ist keine Programmdatei.").format(ort)
    return ""
