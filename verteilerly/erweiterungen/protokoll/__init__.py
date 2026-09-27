"""Protokoll: Ereignisse und unerwartete Fehler in eine Datei schreiben.

Das Programm meldet alles dem Anwender - in der Statuszeile, als
Hinweis beim Start, als Meldungsfenster. Nichts davon ueberlebt das
Beenden, und ein Fehler, den niemand gefangen hat, verschwindet in der
gepackten .exe ganz: sie hat keine Konsole. Diese Erweiterung haengt
sich darum an zwei Stellen:

* an die **Statuszeile** - was dort erscheint, ist der Ereignisstrom des
  Programms und wandert als Zeile ins Protokoll;
* an ``sys.excepthook`` - ein **unerwarteter Fehler** kommt samt Bericht
  in die Datei, und der Anwender erfaehrt, wo er steht.

Geschrieben wird nach ``Verteilerly.log`` im Arbeitsordner; ``schreiber``
haelt die Datei in Grenzen. Das Protokoll ist eine Beigabe, kein
Bestandteil des Betriebs: laesst es sich nicht schreiben, arbeitet das
Programm weiter, als gaebe es die Erweiterung nicht.
"""

from __future__ import annotations

import pathlib
import sys
import traceback

from ... import pfade
from ...sprachen import u
from ...version import VERSION
from .. import Erweiterung
from .schreiber import EREIGNIS, FEHLER, START, Schreiber

#: Wie die Datei im Arbeitsordner heisst.
DATEINAME = "Verteilerly.log"


class Protokoll(Erweiterung):
    kennung = "protokoll"
    name = "Protokoll"
    beschreibung = (
        "Ereignisse und unerwartete Fehler in eine Datei im Arbeitsordner "
        "schreiben, damit sie sich später nachlesen lassen"
    )

    def __init__(self) -> None:
        self.schreiber: Schreiber | None = None
        self._voriger_haken = None
        #: Waehrend die Meldung steht, wird keine zweite aufgemacht - ein
        #: Fehler beim Zeichnen wiederholt sich sonst endlos.
        self._meldet = False

    # -- Einrichten ----------------------------------------------------------

    def einrichten(self, programm) -> None:
        self.schreiber = Schreiber(self.datei())
        for zeile in self._startzeilen(programm):
            self.schreiber.schreiben(START, zeile)
        self._haken_setzen()
        self._an_die_statuszeile(programm)
        programm.menueeintrag(
            u("&Protokoll…"),
            lambda: self.oeffnen(programm),
            hinweis=u("Zeigt, was das Programm zuletzt gemeldet hat"),
        )

    def _startzeilen(self, programm=None) -> list[str]:
        """Womit jeder Lauf anfaengt.

        Wer spaeter einen Bericht liest, will zuerst wissen, welcher Stand
        ihn erzeugt hat - und dann, woher dieser Lauf seine Einstellungen
        nahm. Denn ein Programm laesst sich auf mehrere Weisen starten:
        von Hand, aus der Dateiverwaltung, aus einem anderen Ordner. Wenn
        zwei Starts verschiedene Orte oder verschieden viele Werte melden,
        steht der Grund dafuer hier schwarz auf weiss.
        """
        teile = [f"Verteilerly {VERSION}", f"Python {sys.version.split()[0]}"]
        try:
            from PySide6 import QtCore

            teile.append(f"Qt {QtCore.qVersion()}")
        except Exception:      # noqa: BLE001 - ohne Qt eben ohne Qt
            pass
        zeilen = [" · ".join(teile)]
        woher = "gepackt" if pfade.gepackt() else "aus dem Quelltext"
        zeilen.append(f"Programm: {sys.executable} ({woher})")
        zeilen.append(f"Einstellungen: {self._einstellungsvermerk(programm)}")
        aufruf = " ".join(sys.argv[1:]) or "ohne Argumente"
        zeilen.append(f"Aufruf: {aufruf} · Arbeitsverzeichnis {pathlib.Path.cwd()}")
        return zeilen

    @staticmethod
    def _einstellungsvermerk(programm=None) -> str:
        """Welche Conf gilt und wie viel darin stand.

        Gefragt wird das Fenster: es hat die Datei geoeffnet und weiss
        auch, wenn dabei etwas nicht stimmte. Ohne Fenster bleibt der Weg
        ueber ``pfade``.
        """
        fenster = getattr(programm, "fenster", None)
        einstellungen = getattr(fenster, "einstellungen", None)
        if einstellungen is None:
            return f"{pfade.einstellungsdatei()} — nicht geöffnet"
        stueck = f"{einstellungen.fileName()} — {len(einstellungen.allKeys())} Werte"
        grund = getattr(fenster, "einstellungen_grund", "")
        if grund:
            stueck += f"; die eigentliche Datei war nicht zu lesen ({grund})"
        return stueck

    def datei(self):
        """Wohin geschrieben wird - in den Arbeitsordner, wie alles andere."""
        return pfade.eigener_datenordner() / DATEINAME

    def oeffnen(self, programm) -> None:
        from .dialog import ProtokollDialog

        ProtokollDialog(self, programm.fenster).exec()

    # -- Ereignisse ----------------------------------------------------------

    def _an_die_statuszeile(self, programm) -> None:
        """Was in der Statuszeile steht, ist ein Ereignis.

        Ohne Fenster - in der Testreihe, im Selbstbericht - gibt es keine
        Statuszeile; dann protokolliert die Erweiterung nur Fehler.
        """
        fenster = getattr(programm, "fenster", None)
        if fenster is None:
            return
        try:
            fenster.statusBar().messageChanged.connect(self.ereignis)
        except Exception:      # noqa: BLE001 - eine Beigabe haelt nichts auf
            pass

    def ereignis(self, text: str) -> None:
        """Eine Zeile ins Protokoll - leere Meldungen sind nur das Loeschen."""
        text = (text or "").strip()
        if text and self.schreiber is not None:
            self.schreiber.schreiben(EREIGNIS, text)

    # -- Unerwartete Fehler --------------------------------------------------

    def _haken_setzen(self) -> None:
        """Haengt sich vor den bisherigen ``sys.excepthook``.

        Der bisherige wird danach aufgerufen: wer aus einem Terminal
        startet, soll seinen Bericht weiter auf der Konsole sehen.
        """
        if self._voriger_haken is not None:
            return
        self._voriger_haken = sys.excepthook
        sys.excepthook = self.unerwartet

    def unerwartet(self, art, wert, spur) -> None:
        """Schreibt den Bericht, zeigt, wo er steht, und reicht weiter."""
        if issubclass(art, KeyboardInterrupt):
            self._weiterreichen(art, wert, spur)
            return
        bericht = "".join(traceback.format_exception(art, wert, spur))
        if self.schreiber is not None:
            self.schreiber.schreiben(
                FEHLER, f"{art.__name__}: {wert}", bericht
            )
        self._zeigen(f"{art.__name__}: {wert}")
        self._weiterreichen(art, wert, spur)

    def _weiterreichen(self, art, wert, spur) -> None:
        if self._voriger_haken is not None:
            self._voriger_haken(art, wert, spur)

    def _zeigen(self, satz: str) -> None:
        """Sagt dem Anwender, dass etwas schieflief - und wo es nachzulesen ist."""
        if self._meldet:
            return
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is None:
                return
            self._meldet = True
            QMessageBox.critical(
                None,
                u("Unerwarteter Fehler"),
                u("Etwas ist schiefgelaufen:\n\n{0}\n\nDas Programm läuft "
                  "weiter. Was genau passiert ist, steht im Protokoll:\n{1}")
                .format(satz, self.datei()),
            )
        except Exception:      # noqa: BLE001 - im Fehlerfall nicht noch einmal
            pass
        finally:
            self._meldet = False


erweiterung = Protokoll()
