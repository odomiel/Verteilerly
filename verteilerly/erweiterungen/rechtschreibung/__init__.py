"""Rechtschreibpruefung: die Texte des Verteilers nachlesen lassen.

Ein Leistenblatt traegt hunderte kurzer Texte - Bezeichnungen,
Bemerkungen, Kabelnamen -, und ein Tippfehler darin wandert ungeprueft
ins PDF und von dort an die Wand des Verteilerraums. Diese Erweiterung
zeigt, was zu beanstanden ist; ein Vorschlag laesst sich uebernehmen,
ohne den Dialog zu verlassen, und jede Uebernahme ist ein Schritt zum
Zuruecknehmen wie jede andere Aenderung auch.

**Zwei Pruefer, einzeln zuzuschalten** - beide im Dialog, beide
gemerkt:

* das **Woerterbuch** (``woerterbuch.py``, Hunspell ueber spylls) liest
  auf diesem Rechner. Es findet Tippfehler, keine Grammatik, und
  schickt nichts hinaus. **Vorgabe: an.**
* **LanguageTool** (``pruefer.py``) findet auch Grammatik und
  Zeichensetzung, dafuer gehen die Texte an einen Server.
  **Vorgabe: aus** - wer Texte aus dem Haus gibt, soll das selbst
  entschieden haben.

**Die Texte gehen erst auf Knopfdruck hinaus.** Gefragt wird nie von
selbst - weder beim Start noch beim Speichern. Steht ein auswaertiger
Server in den Einstellungen, fragt das Programm vor der ersten Anfrage
dorthin nach, ob die Texte ihn sehen duerfen; wer das nicht will,
traegt einen eigenen Server ein (``http://localhost:8081/v2/check``)
oder laesst es beim Woerterbuch. Die Zustimmung gilt genau der
eingetragenen Adresse und steht in der ``Verteilerly.conf``.

Was die Erweiterung sich merkt, steht dort unter ``rechtschreibung/``:
die beiden Schalter, Server, Sprache und die Adresse, der zugestimmt
wurde. Die eigene Wortliste steht dagegen als ``woerterbuch.txt`` im
Arbeitsordner - sie gehoert dem Anwender, nicht den Einstellungen.
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
#: Welcher Pruefer laeuft. Das Woerterbuch bleibt hier, LanguageTool
#: schickt die Texte fort - darum das eine an, das andere aus.
SCHLUESSEL_WOERTERBUCH = f"{GRUPPE}/woerterbuch"
SCHLUESSEL_LANGUAGETOOL = f"{GRUPPE}/languagetool"


class Rechtschreibung(Erweiterung):
    kennung = "rechtschreibung"
    name = "Rechtschreibprüfung"
    beschreibung = (
        "Bezeichnungen, Bemerkungen, Kabelnamen und Projektdaten prüfen — "
        "mit einem Wörterbuch auf diesem Rechner oder über LanguageTool"
    )

    def einrichten(self, programm) -> None:
        programm.menueeintrag(
            u("&Rechtschreibung…"),
            lambda: self.oeffnen(programm),
            hinweis=u("Die Texte des Verteilers auf Rechtschreibung prüfen"),
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

    @staticmethod
    def mit_woerterbuch(einstellungen) -> bool:
        return bool(einstellungen.value(SCHLUESSEL_WOERTERBUCH, True, type=bool))

    @staticmethod
    def mit_languagetool(einstellungen) -> bool:
        return bool(einstellungen.value(SCHLUESSEL_LANGUAGETOOL, False, type=bool))


erweiterung = Rechtschreibung()
