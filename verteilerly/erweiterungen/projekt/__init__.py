"""Projekt: mehrere Verteiler auf einen Schlag anlegen.

Ein Projekt besteht selten aus einem Verteiler. Ein Haus hat einen HVt
und mehrere Etagenverteiler; alle tragen **dieselben Projektdaten** -
Firma, Kunde, Bauvorhaben, Datum -, und alle sollen am Ende
nebeneinander in einem Ordner liegen. Von Hand heisst das: neuen
Verteiler anlegen, Projektdaten eintippen, speichern, und das sechsmal.

Diese Erweiterung nimmt die Liste auf einmal: je Zeile Name und
Verteilernummer, darueber die Geometrie, daneben die Projektdaten. Alles
entsteht in **einem Projektordner** - darin je Verteiler ein
Unterordner mit seiner Projektdatei, oder, wenn der Haken fort ist, alle
Projektdateien nebeneinander.

Dazu die **Beilagen**: vorgegebene Dateien und ganze Ordner, jede mit
ihrem Unterordner. Sie gehoeren dem Projektordner und kommen darum
**einmal** hinein, nicht in jeden Verteilerordner - damit ein frischer
Projektordner aussieht wie der vom letzten Mal: ``Fotos/``,
``Messprotokolle/Vorlage.xlsx``, die Checkliste des Hauses. Der Bestand
steht in der ``Verteilerly.conf`` unter ``projekt/`` und gilt beim
naechsten Mal wieder.

**Am offenen Verteiler aendert sich nichts.** Die Erweiterung schreibt
Dateien und ruehrt das Projekt im Fenster nicht an; sie braucht darum
auch keines. Gerechnet wird in ``anlage.py`` ohne Qt - der Dialog zeigt
den Plan, angelegt wird erst nach Zustimmung.
"""

from __future__ import annotations

from ...sprachen import u
from .. import Erweiterung
from .anlage import beilagen_lesen, beilagen_schreiben

#: Die eigene Ecke in der Verteilerly.conf.
GRUPPE = "projekt"
#: Wohin zuletzt angelegt wurde - der naechste Griff geht meist daneben.
SCHLUESSEL_ORDNER = f"{GRUPPE}/projektordner"
#: Der Bestand an Beilagen, als Text mit Zeilenumbruechen.
SCHLUESSEL_BEILAGEN = f"{GRUPPE}/beilagen"
#: Bekommt jeder Verteiler seinen eigenen Ordner? Vorgabe: ja.
SCHLUESSEL_EIGENER_ORDNER = f"{GRUPPE}/eigener_ordner"


class ProjektAnlegen(Erweiterung):
    kennung = "projekt"
    name = "Projekt"
    beschreibung = (
        "Mehrere Verteiler mit denselben Projektdaten auf einmal anlegen — "
        "in einem Projektordner, mit vorgegebenen Dateien darin"
    )

    def einrichten(self, programm) -> None:
        programm.menueeintrag(
            u("Projekt &anlegen…"),
            lambda: self.oeffnen(programm),
            hinweis=u("Mehrere Verteiler mit denselben Projektdaten anlegen"),
        )

    def oeffnen(self, programm) -> None:
        from .dialog import ProjektDialog

        dialog = ProjektDialog(programm, programm.fenster)
        if dialog.exec() != ProjektDialog.DialogCode.Accepted:
            return
        self.merken(programm.einstellungen(), dialog)
        self.melden(programm, dialog.ausfuehren())

    # -- Was gemerkt wird ----------------------------------------------------

    @staticmethod
    def projektordner(einstellungen) -> str:
        return str(einstellungen.value(SCHLUESSEL_ORDNER, "") or "")

    @staticmethod
    def beilagen(einstellungen):
        return beilagen_lesen(einstellungen.value(SCHLUESSEL_BEILAGEN, ""))

    @staticmethod
    def eigener_ordner(einstellungen) -> bool:
        return bool(einstellungen.value(SCHLUESSEL_EIGENER_ORDNER, True, type=bool))

    @staticmethod
    def merken(einstellungen, dialog) -> None:
        """Projektordner, Beilagen und den Haken fuer das naechste Mal.

        Die Verteilerliste und die Projektdaten bleiben draussen: die
        gehoeren diesem Projekt, nicht dem Programm. Was an Projektdaten
        als Vorgabe stehen soll, merkt sich *Bearbeiten ▸ Vorgaben fuer
        neue Verteiler*.
        """
        einstellungen.setValue(SCHLUESSEL_ORDNER, str(dialog.projektordner()))
        einstellungen.setValue(
            SCHLUESSEL_BEILAGEN, beilagen_schreiben(dialog.beilagen())
        )
        einstellungen.setValue(
            SCHLUESSEL_EIGENER_ORDNER, dialog.eigener_ordner_haken.isChecked()
        )
        einstellungen.sync()

    # -- Was danach dasteht --------------------------------------------------

    @staticmethod
    def melden(programm, bericht) -> None:
        """Ein Satz in der Statuszeile - und ein Kasten, wenn etwas fehlt.

        Der gute Fall kommt ohne Fenster aus: wer eben zugestimmt hat,
        braucht keine zweite Rueckfrage. Was **nicht** ging, muss dagegen
        zu sehen sein, sonst sucht man einen Ordner, den es nicht gibt.
        """
        if bericht.angelegt:
            satz = u("{0} Verteiler angelegt, {1} Dateien beigelegt").format(
                bericht.angelegt, bericht.beigelegt
            )
            if bericht.uebergangen:
                satz += u(" ({0} lagen schon da)").format(bericht.uebergangen)
            programm.meldung(satz)
        elif not bericht.gruende:
            programm.meldung(u("Nichts angelegt"))
        if not bericht.gruende:
            return
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.warning(
            programm.fenster,
            u("Projekt anlegen"),
            u("Das ging nicht:\n\n{0}").format("\n".join(bericht.gruende)),
        )


erweiterung = ProjektAnlegen()
