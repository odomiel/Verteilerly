"""CSV2Excel: den offenen Verteiler an Verteilerly_CSV2Excel uebergeben.

Verteilerly_CSV2Excel ist ein eigenes Werkzeug (nur fuer Windows), das
einen Verteiler in die passende Excel-Vorlage uebertraegt - aus der CSV
oder, seit seiner Fassung 1.2.0, aus der Projektdatei selbst. Die
Erweiterung schreibt den **Stand im Fenster** (auch ungespeichert) als
CSV wie *Datei ▸ Exportieren ▸ Als CSV* oder als ``.vtly`` in den
Temp-Ordner und startet das Werkzeug mit dieser Datei als
Aufrufparameter; welches von beiden, sagt die Einstellung ``format`` -
oder der Anwender bei jedem Druck. Die eigene Projektdatei wird dabei
nicht angefasst.

Von Haus aus **aus** (``von_haus_aus_an``): ohne das Werkzeug waere der
Knopf in der Werkzeugleiste nur im Weg. Eingeschaltet traegt sie zwei Dinge
ein - den Knopf *An CSV2Excel* in der Werkzeugleiste und *CSV2Excel
einrichten…* im Menue *Erweiterungen*, wo der Ort des Programms gewaehlt
wird. Der Ort gehoert dem Rechner und steht darum nicht in der
Uebernahmeliste fuer Pakete.
"""

from __future__ import annotations

import pathlib
import sys

from ...sprachen import u
from .. import Erweiterung

#: Die eigene Ecke in der Verteilerly.conf.
GRUPPE = "csv2excel"
SCHLUESSEL_PROGRAMM = f"{GRUPPE}/programm"
SCHLUESSEL_SOFORT = f"{GRUPPE}/sofort"
SCHLUESSEL_EXPORT = f"{GRUPPE}/export"
SCHLUESSEL_FORMAT = f"{GRUPPE}/format"


def _starten(programm: str, argumente: list[str], ordner: str) -> bool:
    """Startet das Werkzeug losgeloest - True, wenn es lief."""
    from PySide6.QtCore import QProcess

    ergebnis = QProcess.startDetached(programm, argumente, ordner)
    # PySide6 gibt (ok, pid) zurueck, aeltere Fassungen nur ok.
    return bool(ergebnis[0] if isinstance(ergebnis, tuple) else ergebnis)


class Csv2Excel(Erweiterung):
    kennung = "csv2excel"
    name = "CSV2Excel"
    beschreibung = (
        "Den offenen Verteiler an Verteilerly_CSV2Excel übergeben, als CSV "
        "oder Projektdatei (nur unter Windows)"
    )
    von_haus_aus_an = False

    #: Auswechselbar, damit die Testreihe nichts startet.
    starten = staticmethod(_starten)

    def einrichten(self, programm) -> None:
        self.knopf = programm.werkzeugknopf(
            u("An CSV2Excel"), lambda: self.uebergeben(programm),
            hinweis=u("Den offenen Verteiler an Verteilerly_CSV2Excel übergeben"),
        )
        programm.menueeintrag(
            u("CSV2Excel &einrichten…"), lambda: self.einstellen(programm),
            hinweis=u("Wählen, wo Verteilerly_CSV2Excel liegt"),
        )

    # -- Einstellungen ------------------------------------------------------

    @staticmethod
    def werte(programm) -> tuple[str, bool, str, str]:
        """(Programm, sofort, Exportordner, Format) aus der Conf."""
        from .uebergabe import format_lesen

        conf = programm.einstellungen()
        return (
            str(conf.value(SCHLUESSEL_PROGRAMM, "") or ""),
            conf.value(SCHLUESSEL_SOFORT, False, type=bool),
            str(conf.value(SCHLUESSEL_EXPORT, "") or ""),
            format_lesen(conf.value(SCHLUESSEL_FORMAT, "")),
        )

    def einstellen(self, programm) -> bool:
        """Der Dialog *CSV2Excel einrichten* - True, wenn bestaetigt."""
        from .dialog import EinrichtenDialog

        pfad, sofort, export, art = self.werte(programm)
        dialog = EinrichtenDialog(pfad, sofort, export, programm.fenster, art=art)
        if dialog.exec() != EinrichtenDialog.DialogCode.Accepted:
            return False
        conf = programm.einstellungen()
        conf.setValue(SCHLUESSEL_PROGRAMM, dialog.programm())
        conf.setValue(SCHLUESSEL_SOFORT, dialog.sofort())
        conf.setValue(SCHLUESSEL_EXPORT, dialog.export())
        conf.setValue(SCHLUESSEL_FORMAT, dialog.format())
        return True

    @staticmethod
    def format_erfragen(programm) -> str | None:
        """Fragt, ob CSV oder Projektdatei - None heisst abgebrochen."""
        from PySide6.QtWidgets import QMessageBox

        from .uebergabe import CSV, VTLY

        kasten = QMessageBox(programm.fenster)
        kasten.setWindowTitle(u("An CSV2Excel"))
        kasten.setIcon(QMessageBox.Icon.Question)
        kasten.setText(u("Wie soll der Verteiler übergeben werden?"))
        csv = kasten.addButton(u("Als CSV"), QMessageBox.ButtonRole.AcceptRole)
        vtly = kasten.addButton(u("Als Projektdatei (.vtly)"), QMessageBox.ButtonRole.AcceptRole)
        kasten.addButton(QMessageBox.StandardButton.Cancel)
        kasten.setDefaultButton(csv)
        kasten.exec()
        gewaehlt = kasten.clickedButton()
        if gewaehlt is csv:
            return CSV
        if gewaehlt is vtly:
            return VTLY
        return None

    # -- Uebergeben ---------------------------------------------------------

    def uebergeben(self, programm) -> bool:
        """Schreibt CSV oder Projektdatei und startet das Werkzeug.

        True, wenn es lief.
        """
        from PySide6.QtWidgets import QMessageBox

        from ... import projektdatei
        from ...ausgabe import AusgabeFehler, csv_schreiben
        from ...modell import ModellFehler
        from .uebergabe import (
            FRAGEN, VTLY, ablageordner, argumente, dateiname, programm_grund,
        )

        titel = u("An CSV2Excel")
        projekt = programm.projekt()
        if projekt is None:
            QMessageBox.information(programm.fenster, titel, u("Es ist kein Verteiler offen."))
            return False

        pfad, sofort, export, art = self.werte(programm)
        grund = programm_grund(pfad)
        if grund:
            # Erst einrichten, dann weiter - wer abbricht, hat nichts verloren.
            QMessageBox.information(
                programm.fenster, titel,
                u("{0}\n\nBitte wählen Sie das Programm aus.").format(grund),
            )
            if not self.einstellen(programm):
                return False
            pfad, sofort, export, art = self.werte(programm)
            if programm_grund(pfad):
                return False
        if art == FRAGEN:
            art = self.format_erfragen(programm)
            if art is None:
                return False

        ziel = ablageordner() / dateiname(
            projekt, getattr(programm.fenster, "pfad", None), art
        )
        try:
            ziel.parent.mkdir(parents=True, exist_ok=True)
            if art == VTLY:
                # Der Stand im Fenster, nicht die Datei auf der Platte -
                # wie bei der CSV zaehlt, was gerade zu sehen ist.
                projektdatei.speichern(projekt, ziel)
            else:
                csv_schreiben(projekt, ziel)
        except (AusgabeFehler, ModellFehler, OSError) as fehler:
            QMessageBox.warning(
                programm.fenster, titel,
                u("{0} ließ sich nicht schreiben:\n\n{1}").format(ziel.name, fehler),
            )
            return False

        werkzeug = pathlib.Path(pfad)
        if not self.starten(str(werkzeug), argumente(ziel, export, sofort), str(werkzeug.parent)):
            text = u("Verteilerly_CSV2Excel ließ sich nicht starten:\n{0}").format(werkzeug)
            if sys.platform != "win32":
                text += "\n\n" + u("Das Programm gibt es nur für Windows.")
            QMessageBox.warning(programm.fenster, titel, text)
            return False
        programm.meldung(
            u("An Verteilerly_CSV2Excel übergeben: {0}").format(ziel.name)
        )
        return True


erweiterung = Csv2Excel()
