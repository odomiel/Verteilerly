"""Dialoge, die auf den Bildschirm passen.

Ein Dialog, der hoeher ist als der Bildschirm, ist unbedienbar: die
Knopfleiste steht dann unter dem unteren Rand, und wer keinen zweiten
Bildschirm hat, kommt nicht an sie heran. Auf kleinen Anzeigen - ein
Notebook mit 1366x768, ein Beamer, ein hochskalierter Bildschirm -
passiert das schnell.

Zwei Regeln darum:

* Kein Fenster wird groesser als die freie Flaeche des Bildschirms, auf
  dem es aufgeht; was darueber hinausragt, wird hereingeschoben.
* Wo der Inhalt nicht schrumpfen kann - lauter Eingabefelder
  untereinander -, sitzt er in einem Rollbereich, und die Knopfleiste
  bleibt darunter stehen. Gerollt wird nur, wenn es sein muss: passt
  alles, ist kein Balken zu sehen.

Geprueft wird beides beim Zeigen, nicht beim Bauen - erst dann steht
fest, auf welchem Bildschirm das Fenster aufgeht.
"""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

# Solange ein Fenster nicht gezeigt ist, weiss niemand, wie breit sein
# Rahmen wird. Diese Schaetzung ist die Untergrenze gaengiger
# Fensterverwaltungen - lieber etwas Luft zu viel als ein Knopf, der
# unter dem Bildschirmrand steht.
RAHMEN_GESCHAETZT = QSize(16, 48)

# Kleiner als das stutzt niemand ein Fenster, auch nicht auf eine
# Briefmarke von Bildschirm.
MINDESTMASS = QSize(320, 240)


def freie_flaeche(fenster: QWidget):
    """Der Teil des Bildschirms, den Leisten und Docks uebrig lassen."""
    bildschirm = fenster.screen() or QGuiApplication.primaryScreen()
    if bildschirm is None:  # ohne Bildschirm (Kopfloser Lauf) gilt nichts
        return None
    return bildschirm.availableGeometry()


def hoechstmass(fenster: QWidget) -> QSize | None:
    """Wie gross das Fenster hier hoechstens sein darf - Rahmen abgezogen."""
    flaeche = freie_flaeche(fenster)
    if flaeche is None:
        return None
    rahmen = fenster.frameGeometry().size() - fenster.size()
    breite = rahmen.width() if rahmen.width() > 0 else RAHMEN_GESCHAETZT.width()
    hoehe = rahmen.height() if rahmen.height() > 0 else RAHMEN_GESCHAETZT.height()
    return QSize(
        max(flaeche.width() - breite, MINDESTMASS.width()),
        max(flaeche.height() - hoehe, MINDESTMASS.height()),
    )


def einpassen(fenster: QWidget) -> bool:
    """Stutzt das Fenster auf den Bildschirm und schiebt es ganz darauf.

    Gibt zurueck, ob dabei etwas zu tun war - die Tests lesen es aus.
    """
    mass = hoechstmass(fenster)
    if mass is None:
        return False
    breite = min(fenster.width(), mass.width())
    hoehe = min(fenster.height(), mass.height())
    gestutzt = QSize(breite, hoehe) != fenster.size()
    if gestutzt:
        fenster.resize(breite, hoehe)

    flaeche = freie_flaeche(fenster)
    rahmen = fenster.frameGeometry()
    # move() setzt bei einem Fenster mit Rahmen dessen Ecke - darum wird
    # auch mit der Rahmengeometrie gerechnet.
    links = min(max(rahmen.x(), flaeche.x()), flaeche.right() - rahmen.width() + 1)
    oben = min(max(rahmen.y(), flaeche.y()), flaeche.bottom() - rahmen.height() + 1)
    geschoben = (links, oben) != (rahmen.x(), rahmen.y())
    if geschoben:
        fenster.move(max(links, flaeche.x()), max(oben, flaeche.y()))
    return gestutzt or geschoben


class PassenderDialog(QDialog):
    """Ein Dialog, der sich dem Bildschirm beugt.

    Erbt jeder Dialog des Programms: mehr als den Bildschirm bekommt
    keiner. Wer ausserdem einen Inhalt hat, der sich nicht zusammen-
    schieben laesst, baut ihn in ein eigenes Widget und reicht es an
    `inhalt_rollbar` weiter, statt ein Layout auf sich selbst zu setzen.
    """

    #: Gesetzt, sobald `inhalt_rollbar` gerufen wurde - sonst None.
    rollbereich: QScrollArea | None = None

    def inhalt_rollbar(
        self, inhalt: QWidget, knopfleiste: QWidget | None = None
    ) -> QScrollArea:
        """Baut den Dialog aus rollendem Inhalt und stehender Knopfleiste."""
        rollen = QScrollArea(self)
        rollen.setWidget(inhalt)
        rollen.setWidgetResizable(True)
        rollen.setFrameShape(QScrollArea.Shape.NoFrame)

        aufbau = QVBoxLayout(self)
        aufbau.setContentsMargins(0, 0, 0, 0)
        aufbau.addWidget(rollen, 1)
        if knopfleiste is not None:
            # Die Leiste steht ausserhalb des Rollbereichs: Übernehmen
            # und Abbrechen duerfen nie wegrollen.
            rand = inhalt.layout().contentsMargins() if inhalt.layout() else None
            if rand is not None:
                knopfleiste.setContentsMargins(
                    rand.left(), 0, rand.right(), rand.bottom()
                )
            aufbau.addWidget(knopfleiste, 0)
        self.rollbereich = rollen

        # Ohne Zutun wuerde der Rollbereich den Wunsch seines Inhalts
        # verschlucken - er koennte ja rollen. Der Dialog soll aber so
        # aufgehen, wie er ohne ihn aufginge, nur eben nicht groesser
        # als der Bildschirm.
        wunsch = inhalt.sizeHint()
        if knopfleiste is not None:
            wunsch.setHeight(wunsch.height() + knopfleiste.sizeHint().height())
        self.resize(wunsch.expandedTo(self.size()))
        einpassen(self)
        return rollen

    def showEvent(self, ereignis) -> None:  # noqa: N802 - Qt-Name
        super().showEvent(ereignis)
        einpassen(self)
