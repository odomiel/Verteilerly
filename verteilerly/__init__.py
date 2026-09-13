"""Verteilerly - Dokumentation fuer LSA+-Verteiler.

Copyright (C) 2026 Mirik

Dieses Programm ist freie Software: Sie koennen es weitergeben und
aendern unter den Bedingungen der GNU General Public License, Version 3
oder (nach Ihrer Wahl) jeder spaeteren Version, wie von der Free
Software Foundation veroeffentlicht.

Weitergegeben wird es in der Hoffnung, dass es nuetzlich ist, aber OHNE
JEDE GEWAEHRLEISTUNG - sogar ohne die stillschweigende Gewaehrleistung
der MARKTGAENGIGKEIT oder EIGNUNG FUER EINEN BESTIMMTEN ZWECK. Naeheres
in der GNU General Public License, die als LICENSE beiliegt und unter
<https://www.gnu.org/licenses/> nachzulesen ist.
"""

from .version import VERSION

LIZENZ = "GPL-3.0-or-later"
URHEBER = "Mirik"

__version__ = VERSION

__all__ = ["LIZENZ", "URHEBER", "VERSION", "__version__"]
