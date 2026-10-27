"""Rechtschreibpruefung: die Texte des Verteilers von LanguageTool lesen lassen.

Ein Leistenblatt traegt hunderte kurzer Texte - Bezeichnungen,
Bemerkungen, Kabelnamen -, und ein Tippfehler darin wandert ungeprueft
ins PDF und von dort an die Wand des Verteilerraums. Diese Erweiterung
schickt sie an einen **LanguageTool**-Server und zeigt, was er
beanstandet; ein Vorschlag laesst sich uebernehmen, ohne den Dialog zu
verlassen, und jede Uebernahme ist ein Schritt zum Zuruecknehmen wie
jede andere Aenderung auch.

**Die Texte gehen hinaus, und zwar erst auf Knopfdruck.** Gefragt wird
nie von selbst - weder beim Start noch beim Speichern. Steht ein
auswaertiger Server in den Einstellungen, fragt das Programm vor der
ersten Anfrage dorthin nach, ob die Texte ihn sehen duerfen; wer das
nicht will, traegt einen eigenen Server ein (``http://localhost:8081/
v2/check``) - dann verlaesst nichts den Rechner. Die Zustimmung gilt
genau der eingetragenen Adresse und steht in der ``Verteilerly.conf``.

Was die Erweiterung sich merkt, steht dort unter ``rechtschreibung/``:
Server, Sprache und die Adresse, der zugestimmt wurde.
"""

from __future__ import annotations

from ...sprachen import u
from .. import Erweiterung
from .pruefer import SERVER, SPRACHE

#: Die eigene Ecke in der Verteilerly.conf.
GRUPPE = "rechtschreibung"
SCHLUESSEL_SERVER = f"{GRUPPE}/server"
SCHLUESSEL_SPRACHE = f"{GRUPPE}/sprache"
#: Welcher auswaertigen Adresse der Anwender zugestimmt hat.
SCHLUESSEL_ZUGESTIMMT = f"{GRUPPE}/zugestimmt"


class Rechtschreibung(Erweiterung):
    kennung = "rechtschreibung"
    name = "Rechtschreibprüfung"
    beschreibung = (
        "Bezeichnungen, Bemerkungen, Kabelnamen und Projektdaten von einem "
        "LanguageTool-Server prüfen lassen — öffentlich oder im eigenen Netz"
    )

    def einrichten(self, programm) -> None:
        programm.menueeintrag(
            u("&Rechtschreibung…"),
            lambda: self.oeffnen(programm),
            hinweis=u("Die Texte des Verteilers von LanguageTool prüfen lassen"),
        )

    def oeffnen(self, programm) -> None:
        if programm.projekt() is None:
            programm.meldung(u("Kein Verteiler geöffnet"))
            return
        from .dialog import RechtschreibDialog

        RechtschreibDialog(programm, programm.fenster).exec()

    # -- Was gemerkt wird ----------------------------------------------------

    @staticmethod
    def server(einstellungen) -> str:
        return str(einstellungen.value(SCHLUESSEL_SERVER, SERVER) or SERVER)

    @staticmethod
    def sprache(einstellungen) -> str:
        return str(einstellungen.value(SCHLUESSEL_SPRACHE, SPRACHE) or SPRACHE)


erweiterung = Rechtschreibung()
