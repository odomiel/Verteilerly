"""Programmsymbol, gezeichnet statt mitgeliefert.

Ein gezeichnetes Symbol braucht keine Bilddatei im Paket, skaliert auf
jede Groesse und passt zum Farbsatz: eine Leiste mit Doppeladern, darauf
ein Kabelblock.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

from .thema import HELL, Farben


def symbol(groesse: int = 256, farben: Farben = HELL) -> QPixmap:
    bild = QPixmap(groesse, groesse)
    bild.fill(Qt.GlobalColor.transparent)

    maler = QPainter(bild)
    maler.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    e = groesse / 32.0  # eine Einheit

    maler.setBrush(QColor(farben.akzent))
    maler.setPen(Qt.PenStyle.NoPen)
    maler.drawRoundedRect(QRectF(0, 0, groesse, groesse), 6 * e, 6 * e)

    # Drei Leisten, in der obersten ein Kabel ueber vier Doppeladern.
    zellen = 8
    breite = 24 * e
    hoehe = 5 * e
    links = 4 * e
    for i, oben in enumerate((6 * e, 13.5 * e, 21 * e)):
        kasten = QRectF(links, oben, breite, hoehe)
        maler.setBrush(QColor(farben.flaeche))
        maler.setPen(QPen(QColor(farben.flaeche), 0))
        maler.drawRect(kasten)
        if i == 0:
            maler.setBrush(QColor(farben.akzent_leise))
            maler.drawRect(QRectF(links, oben, breite / 2, hoehe))
        maler.setPen(QPen(QColor(farben.akzent), max(1.0, e / 3)))
        for n in range(1, zellen):
            x = links + n * breite / zellen
            maler.drawLine(int(x), int(oben), int(x), int(oben + hoehe))
    maler.end()
    return bild


def symbol_icon(farben: Farben = HELL) -> QIcon:
    zeichen = QIcon()
    for groesse in (16, 24, 32, 48, 64, 128, 256):
        zeichen.addPixmap(symbol(groesse, farben))
    return zeichen
