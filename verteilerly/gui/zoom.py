"""Eine Leiste zum Vergroessern - fuer jede Ansicht dieselbe.

Minus, eine Auswahl, Plus: so steht es ueber der Vorschau, und so steht
es auch an der Verteilerbelegung und an der Leiste. Wer eines bedienen
kann, kann alle drei.

Die Leiste selbst vergroessert nichts - sie sagt nur, was gewaehlt wurde;
was das fuer das Bild heisst, weiss die Ansicht.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QWidget

from ..sprachen import u

#: Die Stufen, die zur Wahl stehen. 1.0 ist die gewohnte Groesse.
STUFEN = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0)
VORGABE = 1.0


class Zoomleiste(QWidget):
    """Minus, eine Auswahl, Plus - und ein Signal mit dem Faktor."""

    gewaehlt = Signal(float)

    def __init__(
        self, parent: QWidget | None = None, stufen=STUFEN, vorgabe: float = VORGABE
    ) -> None:
        super().__init__(parent)
        self.stufen = list(stufen)

        self.kleiner = QPushButton("−")
        self.groesser = QPushButton("+")
        for knopf in (self.kleiner, self.groesser):
            knopf.setFixedWidth(26)
            # Das Stilblatt polstert Knoepfe breit; hier bliebe sonst
            # nichts vom Zeichen uebrig.
            knopf.setStyleSheet("padding: 3px 0;")
        self.kleiner.setToolTip(u("Kleiner (Strg und Mausrad)"))
        self.groesser.setToolTip(u("Größer (Strg und Mausrad)"))
        self.kleiner.clicked.connect(lambda: self.stufen_gehen(-1))
        self.groesser.clicked.connect(lambda: self.stufen_gehen(1))

        self.wahl = QComboBox()
        for stufe in self.stufen:
            self.wahl.addItem(u("{0} %").format(round(stufe * 100)), stufe)
        self.wahl.setCurrentIndex(self.stufen.index(vorgabe))
        self.wahl.currentIndexChanged.connect(self._gewaehlt)

        aufbau = QHBoxLayout(self)
        aufbau.setContentsMargins(0, 0, 0, 0)
        aufbau.setSpacing(4)
        aufbau.addWidget(self.kleiner)
        aufbau.addWidget(self.wahl)
        aufbau.addWidget(self.groesser)
        self._knoepfe_nachfuehren()

    # -- Zustand -----------------------------------------------------------

    def zoom(self) -> float:
        """Der gewaehlte Faktor."""
        daten = self.wahl.currentData()
        return VORGABE if daten is None else float(daten)

    def zoom_setzen(self, faktor: float) -> None:
        """Stellt auf die naechstgelegene Stufe."""
        naechste = min(self.stufen, key=lambda stufe: abs(stufe - faktor))
        self.wahl.setCurrentIndex(self.stufen.index(naechste))

    def stufen_gehen(self, richtung: int) -> None:
        """Eine Stufe hinauf oder hinab; an den Enden ist Schluss."""
        stelle = self.wahl.currentIndex() + richtung
        if 0 <= stelle < self.wahl.count():
            self.wahl.setCurrentIndex(stelle)

    def _gewaehlt(self, _index: int) -> None:
        self._knoepfe_nachfuehren()
        self.gewaehlt.emit(self.zoom())

    def _knoepfe_nachfuehren(self) -> None:
        self.kleiner.setEnabled(self.wahl.currentIndex() > 0)
        self.groesser.setEnabled(
            self.wahl.currentIndex() < self.wahl.count() - 1
        )


def rad_ist_zoom(ereignis) -> int:
    """Strg und Mausrad: 1 hinauf, -1 hinab, 0 fuer alles andere.

    Steht hier, weil jede Ansicht dieselbe Frage hat - und weil ohne
    Strg das Ereignis liegen bleiben muss, sonst rollt der Bereich
    darunter nicht mehr.
    """
    if not ereignis.modifiers() & Qt.KeyboardModifier.ControlModifier:
        return 0
    schritt = ereignis.angleDelta().y()
    return 1 if schritt > 0 else (-1 if schritt < 0 else 0)
