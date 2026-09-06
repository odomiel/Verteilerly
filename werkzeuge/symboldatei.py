#!/usr/bin/env python3
"""Das Programmsymbol als Datei ablegen.

Gezeichnet wird es im Programm (verteilerly/gui/symbol.py); PyInstaller
und appimagetool brauchen es aber als Datei. Dieses Skript schreibt sie
neu, wenn sich die Zeichnung aendert:

    python3 werkzeuge/symboldatei.py
"""

from __future__ import annotations

import os
import pathlib
import sys

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

ZIEL = WURZEL / "assets"


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from verteilerly.gui.symbol import symbol

    QApplication.instance() or QApplication([])
    ZIEL.mkdir(parents=True, exist_ok=True)
    for endung in ("ico", "png"):
        datei = ZIEL / f"Verteilerly.{endung}"
        symbol(256).save(str(datei))
        print(f"· {datei} ({datei.stat().st_size // 1024} kB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
