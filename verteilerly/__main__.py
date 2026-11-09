"""Startpunkt: python3 -m verteilerly"""

from __future__ import annotations

import os
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


def zu_oeffnen(argumente) -> pathlib.Path | None:
    """Die Projektdatei aus der Kommandozeile - oder None.

    So kommt der **Doppelklick in der Dateiverwaltung** herein: sie ruft
    das Programm mit dem Pfad auf. Schalter beginnen mit einem
    Bindestrich und zaehlen nicht; genommen wird die erste Datei, die es
    gibt.
    """
    for wert in argumente:
        if wert.startswith("-"):
            continue
        pfad = pathlib.Path(wert)
        if pfad.is_file():
            return pfad
    return None


def _letzte_rettung(art, wert, spur) -> None:
    """Faengt einen unerwarteten Fehler, statt ihn verschwinden zu lassen.

    Der Bericht geht immer auf stderr - ein Start aus dem Terminal soll
    ihn sehen. Ist ``zeigt`` gesetzt (keine Erweiterung uebernimmt),
    kommt zusaetzlich ein Fenster; das Programm laeuft danach weiter.
    """
    import traceback

    if issubclass(art, KeyboardInterrupt):
        sys.__excepthook__(art, wert, spur)
        return
    traceback.print_exception(art, wert, spur)
    if getattr(_letzte_rettung, "zeigt", False):
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None,
                    "Unerwarteter Fehler",
                    f"Etwas ist schiefgelaufen:\n\n{type(wert).__name__}: {wert}"
                    "\n\nDas Programm läuft weiter.",
                )
        except Exception:      # noqa: BLE001 - im Fehlerfall nicht noch einmal
            pass


def _letzte_rettung_einrichten() -> None:
    _letzte_rettung.zeigt = False
    sys.excepthook = _letzte_rettung


def main() -> int:
    if "--selbsttest" in sys.argv:
        stelle = sys.argv.index("--selbsttest")
        ziel = sys.argv[stelle + 1] if len(sys.argv) > stelle + 1 else None
        return selbsttest(pathlib.Path(ziel) if ziel else None)
    if "--ohne-fremde-erweiterungen" in sys.argv:
        # Falls eine eigene Erweiterung den Start verhindert: so kommt man
        # ins Programm und kann sie unter Erweiterungen ausschalten.
        from verteilerly.erweiterungen import OHNE_FREMDE

        os.environ[OHNE_FREMDE] = "1"

    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from verteilerly import pfade, sprachen
    from verteilerly.gui.hauptfenster import Hauptfenster
    from verteilerly.gui.passform import dialoge_freistellen
    from verteilerly.gui.sprache import deutsch_einrichten
    from verteilerly.version import VERSION

    # Die Sprache steht fest, bevor das erste Fenster gebaut wird: die
    # Menues werden einmal beschriftet und nicht wieder.
    sprachen.sprache_setzen(
        str(
            QSettings(str(pfade.einstellungsdatei()), QSettings.Format.IniFormat)
            .value("sprache", sprachen.VORGABE)
        )
    )

    anwendung = QApplication(sys.argv)
    anwendung.setApplicationName("Verteilerly")
    anwendung.setApplicationVersion(VERSION)
    anwendung.setOrganizationName("Verteilerly")
    # Damit auch Qts eigene Dialoge deutsch sprechen.
    deutsch_einrichten(anwendung)
    # Unter X11 heftet GNOME modale Dialoge ans Hauptfenster - sie liessen
    # sich nicht mehr verschieben. Gilt auch fuer Qts eigene Dialoge.
    dialoge_freistellen(anwendung)

    # Letzte Rettung: ein unerwarteter Fehler in einem Slot ginge sonst nur
    # auf stderr - ohne Konsole unsichtbar -, und das Fenster liefe in
    # unklarem Zustand weiter (Audit 4). Gesetzt wird der Haken vor dem
    # Bauen des Fensters; die Erweiterung *Protokoll* haengt sich davor und
    # zeigt dann selbst. Damit kein zweites Fenster aufgeht, meldet die
    # Rettung nur noch, wenn niemand den Haken uebernommen hat.
    _letzte_rettung_einrichten()

    fenster = Hauptfenster()
    if sys.excepthook is _letzte_rettung:
        # Keine Erweiterung hat uebernommen - dann zeigt die Rettung.
        _letzte_rettung.zeigt = True
    fenster.show()
    datei = zu_oeffnen(sys.argv[1:])
    if datei is not None:
        # Erst zeigen, dann laden: eine Meldung ueber eine kaputte Datei
        # braucht ein Fenster, hinter dem sie stehen kann.
        fenster.datei_oeffnen(datei)
    return anwendung.exec()


if __name__ == "__main__":
    raise SystemExit(main())
