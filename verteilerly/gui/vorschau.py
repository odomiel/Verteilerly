"""Vorschau: zeichnet die Blaetter des Layoutmodells.

Gezeichnet wird dasselbe Modell, das spaeter ins PDF geht - hier nur mit
QPainter statt ReportLab. Ein Blatt bleibt Papier: weiss mit schwarzer
Schrift, auch im dunklen Farbsatz.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..layout import Blatt, Linie, Rechteck, Text, blaetter
from ..modell import Projekt
from .thema import HELL, Farben

PUNKT_IN_MM = 25.4 / 72.0
PAPIERRAND = 10  # Pixel um das Blatt herum


class Blattflaeche(QWidget):
    """Ein Blatt, in die verfuegbare Flaeche eingepasst."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.blatt: Blatt | None = None
        self.farben: Farben = HELL
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(240, 300)

    def blatt_setzen(self, blatt: Blatt | None) -> None:
        self.blatt = blatt
        self.update()

    def farben_setzen(self, farben: Farben) -> None:
        self.farben = farben
        self.update()

    def _skala(self, blatt: Blatt) -> float:
        breite = self.width() - 2 * PAPIERRAND
        hoehe = self.height() - 2 * PAPIERRAND
        return max(0.05, min(breite / blatt.breite, hoehe / blatt.hoehe))

    def paintEvent(self, ereignis) -> None:
        maler = QPainter(self)
        maler.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        maler.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        maler.fillRect(self.rect(), self.farben.q("grund"))

        if self.blatt is None:
            maler.setPen(self.farben.q("schrift_leise"))
            maler.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "Keine Vorschau."
            )
            return

        blatt = self.blatt
        skala = self._skala(blatt)
        breite = blatt.breite * skala
        hoehe = blatt.hoehe * skala
        links = (self.width() - breite) / 2
        oben = (self.height() - hoehe) / 2

        papier = QRectF(links, oben, breite, hoehe)
        maler.fillRect(papier.adjusted(2, 2, 2, 2), QColor(0, 0, 0, 40))  # Schatten
        maler.fillRect(papier, QColor("#FFFFFF"))
        maler.setPen(QPen(QColor("#9AA0A0"), 1))
        maler.drawRect(papier)

        maler.save()
        maler.translate(links, oben)
        maler.scale(skala, skala)
        for element in blatt.elemente:
            self._element_zeichnen(maler, element, skala)
        maler.restore()

    def _element_zeichnen(self, maler: QPainter, element, skala: float) -> None:
        if isinstance(element, Rechteck):
            rechteck = QRectF(element.x, element.y, element.breite, element.hoehe)
            if element.fuellung:
                maler.fillRect(rechteck, QColor(element.fuellung))
            if element.rand:
                maler.setPen(self._stift(element.rand, element.staerke, skala))
                maler.setBrush(Qt.BrushStyle.NoBrush)
                maler.drawRect(rechteck)
        elif isinstance(element, Linie):
            maler.setPen(self._stift(element.farbe, element.staerke, skala))
            maler.drawLine(
                QRectF(element.x1, element.y1, 0, 0).topLeft(),
                QRectF(element.x2, element.y2, 0, 0).topLeft(),
            )
        elif isinstance(element, Text):
            self._text_zeichnen(maler, element, skala)

    def _stift(self, farbe: str, staerke: float, skala: float) -> QPen:
        stift = QPen(QColor(farbe))
        # Unter einem Bildpunkt wird die Linie sonst unsichtbar.
        stift.setWidthF(max(staerke, 1.0 / skala))
        return stift

    def _text_zeichnen(self, maler: QPainter, element: Text, skala: float) -> None:
        schrift = QFont(self.font())
        schrift.setBold(element.fett)
        schrift.setPixelSize(max(1, round(element.groesse * PUNKT_IN_MM * skala)))
        # Der Text wird in Geraetekoordinaten gesetzt: so franst die Schrift
        # beim Skalieren nicht aus und bleibt bei kleiner Vorschau lesbar.
        umriss = maler.transform().mapRect(
            QRectF(element.x, element.y, element.breite, element.hoehe)
        )
        maler.save()
        maler.resetTransform()
        maler.setFont(schrift)
        maler.setPen(QColor(element.farbe))
        maler.drawText(umriss, self._flagge(element.ausrichtung), element.text)
        maler.restore()

    def _flagge(self, ausrichtung: str) -> int:
        waagerecht = {
            "links": Qt.AlignmentFlag.AlignLeft,
            "mitte": Qt.AlignmentFlag.AlignHCenter,
            "rechts": Qt.AlignmentFlag.AlignRight,
        }[ausrichtung]
        return int(waagerecht | Qt.AlignmentFlag.AlignVCenter)


class Vorschau(QWidget):
    """Blattwahl und Blattflaeche."""

    blatt_gewechselt = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.projekt: Projekt | None = None
        self.blaetter: list[Blatt] = []

        self.auswahl = QComboBox()
        self.auswahl.currentIndexChanged.connect(self._gewechselt)
        self.zurueck = QPushButton("<")
        self.vor = QPushButton(">")
        for knopf in (self.zurueck, self.vor):
            knopf.setFixedWidth(28)
        self.zurueck.clicked.connect(lambda: self._schieben(-1))
        self.vor.clicked.connect(lambda: self._schieben(1))
        self.zaehler = QLabel("")

        kopf = QHBoxLayout()
        kopf.setContentsMargins(0, 0, 0, 6)
        kopf.addWidget(QLabel("Blatt:"))
        kopf.addWidget(self.auswahl, 1)
        kopf.addWidget(self.zurueck)
        kopf.addWidget(self.vor)
        kopf.addWidget(self.zaehler)

        self.flaeche = Blattflaeche()

        gesamt = QVBoxLayout(self)
        gesamt.setContentsMargins(8, 8, 8, 8)
        gesamt.addLayout(kopf)
        gesamt.addWidget(self.flaeche, 1)

    # -- Zustand -----------------------------------------------------------

    def projekt_setzen(self, projekt: Projekt | None) -> None:
        self.projekt = projekt
        self.aktualisieren()

    def farben_setzen(self, farben: Farben) -> None:
        self.flaeche.farben_setzen(farben)

    def aktualisieren(self, blatt_index: int | None = None) -> None:
        """Baut die Blaetter neu und haelt dabei die Stelle."""
        merker = self.auswahl.currentIndex() if blatt_index is None else blatt_index
        self.blaetter = blaetter(self.projekt) if self.projekt else []

        self.auswahl.blockSignals(True)
        self.auswahl.clear()
        self.auswahl.addItems([b.titel for b in self.blaetter])
        if self.blaetter:
            self.auswahl.setCurrentIndex(min(max(merker, 0), len(self.blaetter) - 1))
        self.auswahl.blockSignals(False)
        self._gewechselt(self.auswahl.currentIndex())

    def blatt_zeigen(self, titel: str) -> None:
        """Springt zu einem Blatt, etwa wenn die Leiste gewechselt wird."""
        for i, blatt in enumerate(self.blaetter):
            if blatt.titel == titel:
                self.auswahl.setCurrentIndex(i)
                return

    def _schieben(self, richtung: int) -> None:
        neu = self.auswahl.currentIndex() + richtung
        if 0 <= neu < self.auswahl.count():
            self.auswahl.setCurrentIndex(neu)

    def _gewechselt(self, index: int) -> None:
        gesamt = len(self.blaetter)
        if not gesamt or index < 0:
            self.flaeche.blatt_setzen(None)
            self.zaehler.setText("")
        else:
            self.flaeche.blatt_setzen(self.blaetter[index])
            self.zaehler.setText(f"{index + 1} / {gesamt}")
        self.zurueck.setEnabled(index > 0)
        self.vor.setEnabled(0 <= index < gesamt - 1)
        self.blatt_gewechselt.emit(index)
