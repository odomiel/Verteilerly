"""Ausgabe der Dokumentation.

PDF ist das Pflichtformat, Excel und CSV kommen dazu. Alle drei
gehen vom selben Projekt aus; das Blattbild stammt aus layout.py, die
Tabellen aus den Belegungsdaten.
"""

from __future__ import annotations


class AusgabeFehler(Exception):
    """Eine Ausgabedatei konnte nicht geschrieben werden."""


from .pdf import pdf_schreiben  # noqa: E402  - braucht AusgabeFehler
from .tabellen import (  # noqa: E402
    belegungszeilen,
    csv_schreiben,
    kabelzeilen,
    xlsx_schreiben,
)

__all__ = [
    "AusgabeFehler",
    "belegungszeilen",
    "csv_schreiben",
    "kabelzeilen",
    "pdf_schreiben",
    "xlsx_schreiben",
]
