"""Startpunkt: python3 -m verteilerly"""

from __future__ import annotations

import pathlib
import sys


def selbsttest(ziel: pathlib.Path | None = None) -> int:
    """Meldet, was im gepackten Programm steckt, und beendet sich.

    Ein Fenster hat keine Ausgabe: die gepackte .exe wird ohne Konsole
    gebaut. Der Bericht geht deshalb in eine Datei, damit das Bauskript
    das fertige Programm einmal wirklich starten und nachsehen kann.
    """
    from verteilerly import pfade
    from verteilerly.blattvorlagen import Blattvorlagen
    from verteilerly.farbcodes import Kabeltypen
    from verteilerly.version import VERSION
    from verteilerly.vorlagen import Vorlagen

    zeilen = [f"version={VERSION}", f"python={sys.version.split()[0]}"]
    try:
        zeilen.append(f"paket={pathlib.Path(__file__).resolve().parent}")
        zeilen.append(f"gepackt={pfade.gepackt()}")
        pfade.grundausstattung_auslegen()
        zeilen.append(f"arbeitsordner={pfade.eigener_datenordner()}")
        zeilen.append(f"vorlagen={len(Vorlagen.laden(pfade.vorlagenordner()))}")
        zeilen.append(
            f"blattvorlagen={len(Blattvorlagen.laden(pfade.blattvorlagenordner()))}"
        )
        zeilen.append(
            f"kabeltypen={len(Kabeltypen.laden(pfade.kabeltypenordner()))}"
        )
        from PySide6 import QtCore

        zeilen.append(f"qt={QtCore.qVersion()}")
        zeilen.append("ergebnis=ok")
    except Exception as fehler:                      # noqa: BLE001
        zeilen.append(f"ergebnis=fehler: {type(fehler).__name__}: {fehler}")

    bericht = "\n".join(zeilen) + "\n"
    if ziel is None:
        sys.stdout.write(bericht)
    else:
        pathlib.Path(ziel).write_text(bericht, encoding="utf-8")
    return 0 if "ergebnis=ok" in bericht else 1


def main() -> int:
    if "--selbsttest" in sys.argv:
        stelle = sys.argv.index("--selbsttest")
        ziel = sys.argv[stelle + 1] if len(sys.argv) > stelle + 1 else None
        return selbsttest(pathlib.Path(ziel) if ziel else None)

    from PySide6.QtWidgets import QApplication

    from verteilerly.gui.hauptfenster import Hauptfenster
    from verteilerly.version import VERSION

    anwendung = QApplication(sys.argv)
    anwendung.setApplicationName("Verteilerly")
    anwendung.setApplicationVersion(VERSION)
    anwendung.setOrganizationName("Verteilerly")

    fenster = Hauptfenster()
    fenster.show()
    return anwendung.exec()


if __name__ == "__main__":
    raise SystemExit(main())
