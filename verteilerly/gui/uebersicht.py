"""Verteilerübersicht: Leisten als Kästen aus DA-Zellen.

Eine Zelle entspricht einer Doppelader, ein Kabel einem zusammenhängenden
Block über die von ihm belegten Doppeladern - genau wie in den
Mustertabellen. Buchten stehen nebeneinander.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..modell import Kabel, Verteiler
from .thema import HELL, Farben

ZELLE_B = 27
ZELLE_H = 32
LABEL_B = 32
RAND = 14
ABSTAND_LEISTEN = 9
ABSTAND_BUCHTEN = 30


class Uebersicht(QWidget):
    """Zeigt den Verteiler und laesst Doppeladern auswaehlen."""

    auswahl_geaendert = Signal(object)      # (leiste, da) oder None
    stelle_aktiviert = Signal(int, int)     # Doppelklick auf freie Stelle
    kabel_aktiviert = Signal(object)        # Doppelklick auf ein Kabel

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.verteiler: Verteiler | None = None
        self.farben: Farben = HELL
        self.auswahl: tuple[int, int] | None = None
        self._kaesten: dict[int, QRect] = {}
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # -- Zustand -----------------------------------------------------------

    def verteiler_setzen(self, verteiler: Verteiler | None) -> None:
        self.verteiler = verteiler
        self.auswahl = None
        self._neu_vermessen()

    def farben_setzen(self, farben: Farben) -> None:
        self.farben = farben
        self.update()

    def aktualisieren(self) -> None:
        self._neu_vermessen()

    def _neu_vermessen(self) -> None:
        self._kaesten = self._layout()
        self.updateGeometry()
        self.update()

    # -- Layout ------------------------------------------------------------

    def _layout(self) -> dict[int, QRect]:
        """Der Kasten jeder Leiste, ohne das Nummernfeld davor."""
        kaesten: dict[int, QRect] = {}
        if self.verteiler is None:
            return kaesten

        x = RAND
        for bucht in self.verteiler.buchten:
            breiteste = max((l.da_anzahl for l in bucht.leisten), default=0)
            y = RAND
            for leiste in bucht.leisten:
                kaesten[leiste.nummer] = QRect(
                    x + LABEL_B, y, leiste.da_anzahl * ZELLE_B, ZELLE_H
                )
                y += ZELLE_H + ABSTAND_LEISTEN
            x += LABEL_B + breiteste * ZELLE_B + ABSTAND_BUCHTEN
        return kaesten

    def sizeHint(self) -> QSize:
        if not self._kaesten:
            return QSize(360, 180)
        rechts = max(k.right() for k in self._kaesten.values())
        unten = max(k.bottom() for k in self._kaesten.values())
        return QSize(rechts + RAND, unten + RAND)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def _zelle_bei(self, x: int, y: int) -> tuple[int, int] | None:
        for nummer, kasten in self._kaesten.items():
            if kasten.contains(x, y):
                return nummer, (x - kasten.left()) // ZELLE_B + 1
        return None

    def _zellrechteck(self, leiste: int, da: int) -> QRect:
        kasten = self._kaesten[leiste]
        return QRect(kasten.left() + (da - 1) * ZELLE_B, kasten.top(), ZELLE_B, ZELLE_H)

    # -- Maus --------------------------------------------------------------

    def mousePressEvent(self, ereignis) -> None:
        stelle = self._zelle_bei(int(ereignis.position().x()), int(ereignis.position().y()))
        self.auswahl = stelle
        self.auswahl_geaendert.emit(stelle)
        self.update()

    def mouseDoubleClickEvent(self, ereignis) -> None:
        stelle = self._zelle_bei(int(ereignis.position().x()), int(ereignis.position().y()))
        if stelle is None or self.verteiler is None:
            return
        leiste, da = stelle
        kabel = self.verteiler.kabel_an(leiste, da)
        if kabel is not None:
            self.kabel_aktiviert.emit(kabel)
        else:
            self.stelle_aktiviert.emit(leiste, da)

    def mouseMoveEvent(self, ereignis) -> None:
        """Der Kabelname steht im Kasten oft gekuerzt - hier ganz."""
        stelle = self._zelle_bei(int(ereignis.position().x()), int(ereignis.position().y()))
        self.setToolTip(self._hinweistext(stelle))

    def _hinweistext(self, stelle: tuple[int, int] | None) -> str:
        if stelle is None or self.verteiler is None:
            return ""
        leiste, da = stelle
        kabel = self.verteiler.kabel_an(leiste, da)
        if kabel is None:
            return f"Leiste {leiste}, DA {da} - frei"
        zeilen = [kabel.beschriftung, f"Leiste {leiste}, DA {da}"]
        if kabel.kabeltyp:
            zeilen.append(kabel.kabeltyp)
        if kabel.gekuerzt:
            zeilen.append(f"gekürzt: {kabel.da_aufgelegt} von {kabel.da_gesamt} DA")
        return "\n".join(zeilen)

    # -- Zeichnen ----------------------------------------------------------

    def paintEvent(self, ereignis) -> None:
        maler = QPainter(self)
        maler.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        maler.fillRect(self.rect(), self.farben.q("grund"))

        if self.verteiler is None or not self._kaesten:
            self._hinweis_zeichnen(maler)
            return

        self._raster_zeichnen(maler)
        for kabel in self.verteiler.kabel:
            self._kabel_zeichnen(maler, kabel)
        self._auswahl_zeichnen(maler)

    def _hinweis_zeichnen(self, maler: QPainter) -> None:
        maler.setPen(self.farben.q("schrift_leise"))
        maler.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "Kein Verteiler geöffnet.\nDatei ▸ Neuer Verteiler",
        )

    def _raster_zeichnen(self, maler: QPainter) -> None:
        nummernschrift = QFont(self.font())
        nummernschrift.setPointSizeF(self.font().pointSizeF() - 0.5)

        for nummer, kasten in self._kaesten.items():
            maler.setFont(nummernschrift)
            maler.setPen(self.farben.q("schrift_leise"))
            maler.drawText(
                QRect(kasten.left() - LABEL_B, kasten.top(), LABEL_B - 6, ZELLE_H),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                str(nummer),
            )

            maler.fillRect(kasten, self.farben.q("flaeche"))

            # Feine Linie je Doppelader, kraeftige Linie um die Leiste.
            maler.setPen(QPen(self.farben.q("linie"), 1))
            zellen = kasten.width() // ZELLE_B
            for i in range(1, zellen):
                x = kasten.left() + i * ZELLE_B
                maler.drawLine(x, kasten.top() + 1, x, kasten.bottom() - 1)
            maler.setPen(QPen(self.farben.q("linie_kraeftig"), 1))
            maler.drawRect(kasten)

    def _kabel_zeichnen(self, maler: QPainter, kabel: Kabel) -> None:
        for abschnitt in kabel.abschnitte:
            if abschnitt.leiste not in self._kaesten:
                continue
            anfang = self._zellrechteck(abschnitt.leiste, abschnitt.start_da)
            block = QRect(
                anfang.left(), anfang.top(), abschnitt.anzahl_da * ZELLE_B, ZELLE_H
            )
            maler.fillRect(block.adjusted(1, 1, 0, 0), self.farben.q("akzent_leise"))
            maler.setPen(QPen(self.farben.q("akzent"), 1))
            maler.drawRect(block)

            beschriftung = kabel.beschriftung
            if kabel.gekuerzt and abschnitt is kabel.abschnitte[-1]:
                beschriftung = f"{beschriftung} (gekürzt)"
            masse = QFontMetrics(self.font())
            platz = block.adjusted(6, 0, -4, 0)
            maler.setPen(self.farben.q("akzent"))
            maler.drawText(
                platz,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                masse.elidedText(
                    beschriftung, Qt.TextElideMode.ElideRight, platz.width()
                ),
            )

    def _auswahl_zeichnen(self, maler: QPainter) -> None:
        if self.auswahl is None or self.auswahl[0] not in self._kaesten:
            return
        leiste, da = self.auswahl
        if da > self._kaesten[leiste].width() // ZELLE_B:
            return
        maler.setPen(QPen(self.farben.q("akzent"), 2))
        maler.setBrush(Qt.BrushStyle.NoBrush)
        maler.drawRect(self._zellrechteck(leiste, da).adjusted(1, 1, -1, -1))
