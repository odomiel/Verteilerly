"""Blattvorlagen-Editor: Werte einer Blattvorlage aendern und sofort sehen, was sich tut.

Die erste eingebaute Erweiterung. Sie traegt sich ins Menue
*Erweiterungen* ein; der Dialog selbst liegt in ``dialog`` und wird erst
geladen, wenn er gebraucht wird.
"""

from __future__ import annotations

from ...sprachen import u
from .. import Erweiterung


class BlattvorlagenEditor(Erweiterung):
    kennung = "blattvorlageneditor"
    name = "Blattvorlagen-Editor"
    beschreibung = (
        "Werte einer Blattvorlage ändern, die Wirkung sofort am Blatt sehen "
        "und als neue Vorlage speichern"
    )

    def einrichten(self, programm) -> None:
        programm.menueeintrag(
            u("&Blattvorlagen-Editor…"),
            lambda: self.oeffnen(programm),
            hinweis=u("Eine Blattvorlage anpassen und als neue speichern — "
                      "mit Vorschau am Blatt"),
        )

    def oeffnen(self, programm) -> None:
        from .dialog import EditorDialog

        EditorDialog(programm).exec()


erweiterung = BlattvorlagenEditor()
