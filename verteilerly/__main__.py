"""Startpunkt: python3 -m verteilerly"""

from __future__ import annotations

import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from .gui.hauptfenster import Hauptfenster
    from .version import VERSION

    anwendung = QApplication(sys.argv)
    anwendung.setApplicationName("Verteilerly")
    anwendung.setApplicationVersion(VERSION)
    anwendung.setOrganizationName("Verteilerly")

    fenster = Hauptfenster()
    fenster.show()
    return anwendung.exec()


if __name__ == "__main__":
    raise SystemExit(main())
