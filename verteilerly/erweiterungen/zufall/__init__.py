"""Zufallsverteiler: ein Verteiler nach Vorlage, mit Zufallsdaten gefuellt.

Zum Vorfuehren und Ausprobieren: gewaehlt wird nur die
**Verteilervorlage**, alles andere wuerfelt die Erweiterung - Kabel mit
Typ und Adernfarben, Luecken dazwischen, hin und wieder ein gekuerztes
Kabel, Bezeichnungen und Bemerkungen an den Adern, Rangierungen quer
ueber die Leisten, ein paar Vermerke und die Projektdaten.

Das Ergebnis ist ein **neuer, ungespeicherter Verteiler** wie nach
*Datei ▸ Neuer Verteiler*; ein geaenderter offener wird vorher wie dort
zum Speichern angeboten. Gewuerfelt wird in ``fuellung.py`` ohne Qt.
"""

from __future__ import annotations

from ...sprachen import u
from .. import Erweiterung

#: Die eigene Ecke in der Verteilerly.conf.
GRUPPE = "zufall"
#: Welche Vorlage zuletzt gewaehlt war.
SCHLUESSEL_VORLAGE = f"{GRUPPE}/vorlage"


class Zufallsverteiler(Erweiterung):
    kennung = "zufall"
    name = "Zufallsverteiler"
    beschreibung = (
        "Einen Verteiler nach Vorlage anlegen und mit Zufallsdaten füllen — "
        "zum Vorführen und Ausprobieren"
    )

    def einrichten(self, programm) -> None:
        programm.menueeintrag(
            u("&Zufallsverteiler…"),
            lambda: self.oeffnen(programm),
            hinweis=u("Einen Verteiler nach Vorlage mit Zufallsdaten füllen"),
        )

    def oeffnen(self, programm) -> None:
        vorlagen = programm.vorlagen()
        if not len(vorlagen):
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(
                programm.fenster, u("Zufallsverteiler"),
                u("Es ist keine Verteilervorlage geladen."),
            )
            return
        from .dialog import ZufallsDialog

        einstellungen = programm.einstellungen()
        dialog = ZufallsDialog(
            vorlagen, einstellungen.value(SCHLUESSEL_VORLAGE, "") or "",
            programm.fenster,
        )
        if dialog.exec() != ZufallsDialog.DialogCode.Accepted:
            return
        kennung = dialog.vorlage()
        einstellungen.setValue(SCHLUESSEL_VORLAGE, kennung)
        self.anlegen(programm, kennung)

    @staticmethod
    def anlegen(programm, kennung: str, zufall=None) -> bool:
        """Baut den Verteiler und zeigt ihn - False, wenn nichts entstand."""
        from .fuellung import zufallsprojekt

        vorlage = programm.vorlagen().holen(kennung)
        projekt = zufallsprojekt(vorlage.verteiler(), programm.kabeltypen(), zufall)
        if not programm.projekt_zeigen(projekt):
            return False
        verteiler = projekt.verteiler
        belegt = sum(len(k.positionen()) for k in verteiler.kabel)
        programm.meldung(
            u("Zufallsverteiler nach {0}: {1} Kabel, {2} von {3} DA belegt, {4} Rangierungen").format(
                vorlage.name, len(verteiler.kabel), belegt,
                verteiler.da_gesamt, len(verteiler.rangierungen),
            )
        )
        return True


erweiterung = Zufallsverteiler()
