"""CSV2Excel: die CSV des offenen Verteilers an Verteilerly_CSV2Excel uebergeben.

Verteilerly_CSV2Excel ist ein eigenes Werkzeug (nur fuer Windows), das
die CSV eines Verteilers in die passende Excel-Vorlage uebertraegt. Die
Erweiterung schreibt die CSV wie *Datei ▸ Exportieren ▸ Als CSV* in den
Temp-Ordner und startet das Werkzeug mit ihr als Aufrufparameter.

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
        "Die CSV des offenen Verteilers an Verteilerly_CSV2Excel übergeben "
        "(nur unter Windows)"
    )
    von_haus_aus_an = False

    #: Auswechselbar, damit die Testreihe nichts startet.
    starten = staticmethod(_starten)

    def einrichten(self, programm) -> None:
        self.knopf = programm.werkzeugknopf(
            u("An CSV2Excel"), lambda: self.uebergeben(programm),
            hinweis=u("Die CSV des offenen Verteilers an Verteilerly_CSV2Excel übergeben"),
        )
        programm.menueeintrag(
            u("CSV2Excel &einrichten…"), lambda: self.einstellen(programm),
            hinweis=u("Wählen, wo Verteilerly_CSV2Excel liegt"),
        )

    # -- Einstellungen ------------------------------------------------------

    @staticmethod
    def werte(programm) -> tuple[str, bool, str]:
        """(Programm, sofort, Exportordner) aus der Conf."""
        conf = programm.einstellungen()
        return (
            str(conf.value(SCHLUESSEL_PROGRAMM, "") or ""),
            conf.value(SCHLUESSEL_SOFORT, False, type=bool),
            str(conf.value(SCHLUESSEL_EXPORT, "") or ""),
        )

    def einstellen(self, programm) -> bool:
        """Der Dialog *CSV2Excel einrichten* - True, wenn bestaetigt."""
        from .dialog import EinrichtenDialog

        pfad, sofort, export = self.werte(programm)
        dialog = EinrichtenDialog(pfad, sofort, export, programm.fenster)
        if dialog.exec() != EinrichtenDialog.DialogCode.Accepted:
            return False
        conf = programm.einstellungen()
        conf.setValue(SCHLUESSEL_PROGRAMM, dialog.programm())
        conf.setValue(SCHLUESSEL_SOFORT, dialog.sofort())
        conf.setValue(SCHLUESSEL_EXPORT, dialog.export())
        return True

    # -- Uebergeben ---------------------------------------------------------

    def uebergeben(self, programm) -> bool:
        """Schreibt die CSV und startet das Werkzeug - True, wenn es lief."""
        from PySide6.QtWidgets import QMessageBox

        from ...ausgabe import AusgabeFehler, csv_schreiben
        from .uebergabe import ablageordner, argumente, csv_name, programm_grund

        titel = u("An CSV2Excel")
        projekt = programm.projekt()
        if projekt is None:
            QMessageBox.information(programm.fenster, titel, u("Es ist kein Verteiler offen."))
            return False

        pfad, sofort, export = self.werte(programm)
        grund = programm_grund(pfad)
        if grund:
            # Erst einrichten, dann weiter - wer abbricht, hat nichts verloren.
            QMessageBox.information(
                programm.fenster, titel,
                u("{0}\n\nBitte wählen Sie das Programm aus.").format(grund),
            )
            if not self.einstellen(programm):
                return False
            pfad, sofort, export = self.werte(programm)
            if programm_grund(pfad):
                return False

        ziel = ablageordner() / csv_name(projekt, getattr(programm.fenster, "pfad", None))
        try:
            ziel.parent.mkdir(parents=True, exist_ok=True)
            csv_schreiben(projekt, ziel)
        except (AusgabeFehler, OSError) as fehler:
            QMessageBox.warning(
                programm.fenster, titel,
                u("Die CSV ließ sich nicht schreiben:\n\n{0}").format(fehler),
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
