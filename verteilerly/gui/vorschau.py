"""Vorschau: zeichnet die Blaetter des Layoutmodells.

Gezeichnet wird dasselbe Modell, das spaeter ins PDF geht - hier nur mit
QPainter statt ReportLab. Ein Blatt bleibt Papier: weiss mit schwarzer
Schrift, auch im dunklen Farbsatz.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..blattvorlagen import STANDARD, Blattvorlage, Blattvorlagen
from ..layout import (
    ZEILENABSTAND,
    Blatt,
    Linie,
    Rechteck,
    Text,
    blaetter,
    textzeilen,
)
from ..modell import Projekt
from .thema import HELL, Farben
from ..sprachen import u

PUNKT_IN_MM = 25.4 / 72.0
PAPIERRAND = 10  # Pixel um das Blatt herum
# Die Stufen der Vergroesserung: 1.0 ist das Blatt in seiner wahren
# Groesse, soweit der Bildschirm seine Masse kennt. 0 steht daneben fuer
# "ins Fenster einpassen" - damit faengt die Vorschau an.
EINPASSEN = 0.0
ZOOMSTUFEN = (0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0)
# Rechnet der Bildschirm Unsinn, bleibt es bei der ueblichen Dichte.
PUNKTE_JE_ZOLL = 96.0
# So weit darf die Schrift schrumpfen, damit ein Text in sein Feld passt -
# dieselbe Untergrenze wie im PDF (ausgabe/pdf.py).
KLEINSTE_SCHRIFT = 5.0


class Blattflaeche(QWidget):
    """Ein Blatt, in die verfuegbare Flaeche eingepasst."""

    #: Strg und Mausrad: eine Stufe hinauf oder hinab.
    zoom_gerollt = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.blatt: Blatt | None = None
        self.farben: Farben = HELL
        #: Bildpunkte je Millimeter, oder EINPASSEN fuer "ins Fenster".
        self.zoom: float = EINPASSEN
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(240, 300)

    def blatt_setzen(self, blatt: Blatt | None) -> None:
        self.blatt = blatt
        self._groesse_nachfuehren()
        self.update()

    def farben_setzen(self, farben: Farben) -> None:
        self.farben = farben
        self.update()

    def zoom_setzen(self, faktor: float) -> None:
        """Vergroessert das Blatt; ``EINPASSEN`` passt es ins Fenster.

        Gemessen wird in wahrer Groesse: bei 1.0 ist ein Millimeter des
        Blattes ein Millimeter auf dem Bildschirm, soweit der seine
        Masse kennt.
        """
        self.zoom = max(faktor, EINPASSEN)
        self._groesse_nachfuehren()
        self.update()

    def punkte_je_mm(self) -> float:
        """Wie viele Bildpunkte ein Millimeter auf diesem Schirm hat."""
        schirm = self.screen() or QApplication.primaryScreen()
        dichte = schirm.physicalDotsPerInch() if schirm else PUNKTE_JE_ZOLL
        # Manche Schirme melden gar nichts oder Unsinn.
        if not 30.0 <= dichte <= 600.0:
            dichte = PUNKTE_JE_ZOLL
        return dichte / 25.4

    def _groesse_nachfuehren(self) -> None:
        """Beim Vergroessern waechst die Flaeche - der Rollbereich merkt es.

        Die Mindestgroesse ist der Griff dafuer: ein ``QScrollArea`` mit
        ``setWidgetResizable`` macht seinen Inhalt so gross wie die
        Sichtflaeche, aber nie kleiner als dessen Mindestmass. Ist das
        Blatt groesser, erscheinen die Rollbalken von selbst.
        """
        if self.blatt is None or self.zoom == EINPASSEN:
            self.setMinimumSize(240, 300)
            return
        skala = self.zoom * self.punkte_je_mm()
        self.setMinimumSize(
            int(self.blatt.breite * skala) + 2 * PAPIERRAND,
            int(self.blatt.hoehe * skala) + 2 * PAPIERRAND,
        )

    def wheelEvent(self, ereignis) -> None:  # noqa: N802 - Qt-Name
        """Strg und Mausrad vergroessern, sonst rollt der Rollbereich."""
        if ereignis.modifiers() & Qt.KeyboardModifier.ControlModifier:
            schritt = ereignis.angleDelta().y()
            if schritt:
                self.zoom_gerollt.emit(1 if schritt > 0 else -1)
                ereignis.accept()
                return
        ereignis.ignore()

    def _skala(self, blatt: Blatt) -> float:
        if self.zoom != EINPASSEN:
            return self.zoom * self.punkte_je_mm()
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
                self.rect(), Qt.AlignmentFlag.AlignCenter, u("Keine Vorschau.")
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
        # Der Text wird in Geraetekoordinaten gesetzt: so franst die Schrift
        # beim Skalieren nicht aus und bleibt bei kleiner Vorschau lesbar.
        umriss = maler.transform().mapRect(
            QRectF(element.x, element.y, element.breite, element.hoehe)
        )
        # Quer gedreht ist die Hoehe des Kastens die Laenge der Zeile.
        laenge = umriss.height() if element.drehung else umriss.width()
        schrift = QFont(self.font())
        schrift.setBold(element.fett)
        schrift.setItalic(element.kursiv)
        if element.umbruch:
            self._text_umgebrochen(maler, element, umriss, schrift, skala)
            return
        schrift.setPixelSize(self._passende_pixel(element, laenge, skala))
        masse = QFontMetricsF(schrift)
        # Was auch bei kleinster Schrift nicht hineinpasst, wird gekuerzt -
        # sonst schnitte Qt mitten im Buchstaben ab. Genau wie im PDF.
        text = str(element.text)
        if masse.horizontalAdvance(text) > laenge:
            text = masse.elidedText(text, Qt.TextElideMode.ElideRight, laenge)

        maler.save()
        maler.resetTransform()
        maler.setFont(schrift)
        maler.setPen(QColor(element.farbe))
        if element.drehung:
            # Um die Mitte des Kastens drehen; Qt zaehlt den Winkel im
            # Uhrzeigersinn, das Layoutmodell dagegen.
            maler.translate(umriss.center())
            maler.rotate(-element.drehung)
            kasten = QRectF(
                -umriss.height() / 2, -umriss.width() / 2,
                umriss.height(), umriss.width(),
            )
            maler.drawText(kasten, self._flagge(element.ausrichtung), text)
        else:
            maler.drawText(umriss, self._flagge(element.ausrichtung), text)
        maler.restore()

    def _text_umgebrochen(
        self, maler: QPainter, element: Text, umriss, schrift: QFont, skala: float
    ) -> None:
        """Text auf mehreren Zeilen, mittig im Kasten.

        Wo umgebrochen wird, rechnet das Layoutmodell mit dem gemeinsamen
        Mass - so stehen im Ausdruck dieselben Zeilen wie hier.
        Nachgemessen wird mit der Schrift der Oberflaeche: baut sie
        breiter, wird eine Stufe kleiner gesetzt, nie groesser.

        Quer gedreht wird im gedrehten Koordinatensystem gezeichnet: dort
        steht der Kasten aufrecht, und die Zeilen stapeln sich wie
        gewohnt nach unten - auf dem Blatt nebeneinander.
        """
        punkt, zeilen = textzeilen(element)
        zeilen = [z for z in zeilen if z.strip()]
        if not zeilen:
            return

        laenge = umriss.height() if element.drehung else umriss.width()
        kleinste = max(1, int(KLEINSTE_SCHRIFT * PUNKT_IN_MM * skala))
        groesse = max(kleinste, round(punkt * PUNKT_IN_MM * skala))
        while groesse > kleinste:
            gemessen = QFont(schrift)
            gemessen.setPixelSize(int(groesse))
            masse = QFontMetricsF(gemessen)
            if all(masse.horizontalAdvance(z) <= laenge for z in zeilen):
                break
            groesse -= 1

        schrift.setPixelSize(max(1, int(groesse)))
        abstand = groesse * ZEILENABSTAND

        maler.save()
        maler.resetTransform()
        maler.setFont(schrift)
        maler.setPen(QColor(element.farbe))
        if element.drehung:
            maler.translate(umriss.center())
            maler.rotate(-element.drehung)
            platz = QRectF(
                -umriss.height() / 2, -umriss.width() / 2,
                umriss.height(), umriss.width(),
            )
        else:
            platz = umriss
        oben = platz.center().y() - abstand * len(zeilen) / 2
        for i, zeile in enumerate(zeilen):
            kasten = QRectF(
                platz.left(), oben + abstand * i, platz.width(), abstand
            )
            maler.drawText(kasten, self._flagge(element.ausrichtung), zeile)
        maler.restore()

    def _passende_pixel(self, element: Text, laenge_px: float, skala: float) -> int:
        """Die Pixelgroesse, mit der der Text in sein Feld passt.

        Dasselbe Vorgehen wie im PDF, nur mit den Massen von Qt: gemessen
        wird die Schrift so, wie sie gezeichnet wird - in Bildpunkten.
        Qt kennt nur ganze Pixel, darum wird abgerundet und nachgemessen;
        eine aufgerundete Groesse liefe sonst doch ueber den Rand.
        """
        gewuenscht = max(1, round(element.groesse * PUNKT_IN_MM * skala))
        kleinste = max(1, int(KLEINSTE_SCHRIFT * PUNKT_IN_MM * skala))
        text = str(element.text)
        if not text.strip() or laenge_px <= 0:
            return gewuenscht

        schrift = QFont(self.font())
        schrift.setBold(element.fett)
        schrift.setItalic(element.kursiv)
        groesse = gewuenscht
        while groesse > kleinste:
            schrift.setPixelSize(groesse)
            gebraucht = QFontMetricsF(schrift).horizontalAdvance(text)
            if gebraucht <= laenge_px or gebraucht <= 0:
                break
            # Der Dreisatz bringt uns in einem Schritt fast ans Ziel, das
            # -1 sorgt dafuer, dass die Schleife auf jeden Fall endet.
            geschaetzt = int(groesse * laenge_px / gebraucht)
            groesse = max(kleinste, min(groesse - 1, geschaetzt))
        return max(kleinste, groesse)

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
    blattvorlage_gewechselt = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.projekt: Projekt | None = None
        self.blaetter: list[Blatt] = []
        self.blattvorlagen = Blattvorlagen()
        self.blattvorlage: Blattvorlage = STANDARD

        # Gewaehlt wird die Blattvorlage nicht mehr hier, sondern beim
        # Anlegen und unter Einstellungen - hier steht nur noch,
        # welche gerade gilt.
        self.vorlagenname = QLabel("")
        self.vorlagenname.setToolTip(
            u("Wie das Blatt aussieht — Spalten, Schriftgrößen, Ränder. "
            "Zu ändern unter Einstellungen ▸ Blattvorlage.")
        )

        self.auswahl = QComboBox()
        self.auswahl.currentIndexChanged.connect(self._gewechselt)
        self.zurueck = QPushButton("‹")
        self.vor = QPushButton("›")
        for knopf in (self.zurueck, self.vor):
            knopf.setFixedWidth(30)
            # Das Stilblatt polstert Knöpfe breit; hier bliebe sonst nichts
            # vom Pfeil übrig.
            knopf.setStyleSheet("padding: 4px 0;")
        self.zurueck.clicked.connect(lambda: self._schieben(-1))
        self.vor.clicked.connect(lambda: self._schieben(1))
        self.zaehler = QLabel("")

        kopf = QHBoxLayout()
        kopf.setContentsMargins(0, 0, 0, 6)
        kopf.addWidget(QLabel(u("Blatt:")))
        kopf.addWidget(self.auswahl, 1)
        kopf.addWidget(self.zurueck)
        kopf.addWidget(self.vor)
        kopf.addWidget(self.zaehler)

        self.kleiner = QPushButton("−")
        self.groesser = QPushButton("+")
        for knopf in (self.kleiner, self.groesser):
            knopf.setFixedWidth(30)
            knopf.setStyleSheet("padding: 4px 0;")
        self.kleiner.setToolTip(u("Kleiner (Strg und Mausrad)"))
        self.groesser.setToolTip(u("Größer (Strg und Mausrad)"))
        self.kleiner.clicked.connect(lambda: self.zoom_stufen(-1))
        self.groesser.clicked.connect(lambda: self.zoom_stufen(1))

        self.zoomwahl = QComboBox()
        self.zoomwahl.addItem(u("Einpassen"), EINPASSEN)
        for stufe in ZOOMSTUFEN:
            self.zoomwahl.addItem(u("{0} %").format(round(stufe * 100)), stufe)
        self.zoomwahl.setToolTip(
            u("Wie groß das Blatt gezeigt wird. Passt es nicht mehr ins "
            "Fenster, erscheinen Rollbalken.")
        )
        self.zoomwahl.currentIndexChanged.connect(self._zoom_gewaehlt)

        zweite = QHBoxLayout()
        zweite.setContentsMargins(0, 0, 0, 6)
        zweite.addWidget(QLabel(u("Blattvorlage:")))
        zweite.addWidget(self.vorlagenname, 1)
        zweite.addWidget(self.kleiner)
        zweite.addWidget(self.zoomwahl)
        zweite.addWidget(self.groesser)

        self.flaeche = Blattflaeche()
        self.flaeche.zoom_gerollt.connect(self.zoom_stufen)
        # Der Rollbereich macht die Flaeche so gross wie seine Sicht -
        # und laesst ihr ihre Mindestgroesse, sobald vergroessert wird.
        self.rollbereich = QScrollArea()
        self.rollbereich.setWidgetResizable(True)
        self.rollbereich.setFrameShape(QScrollArea.Shape.NoFrame)
        self.rollbereich.setWidget(self.flaeche)

        gesamt = QVBoxLayout(self)
        gesamt.setContentsMargins(8, 8, 8, 8)
        gesamt.addLayout(kopf)
        gesamt.addLayout(zweite)
        gesamt.addWidget(self.rollbereich, 1)

    # -- Zustand -----------------------------------------------------------

    def blattvorlagen_setzen(self, vorlagen: Blattvorlagen, gewaehlt: str = "") -> None:
        """Die vorhandenen Blattvorlagen und die, die gerade gilt."""
        self.blattvorlagen = vorlagen
        self.blattvorlage = vorlagen.gewaehlt(gewaehlt or vorlagen.standard.id)
        self.vorlagenname.setText(self.blattvorlage.name)

    def blattvorlage_setzen(self, kennung: str) -> None:
        """Stellt auf eine andere Blattvorlage um und zeichnet neu."""
        if not kennung or kennung == self.blattvorlage.id:
            return
        self.blattvorlage = self.blattvorlagen.holen(kennung)
        self.vorlagenname.setText(self.blattvorlage.name)
        self.aktualisieren()
        self.blattvorlage_gewechselt.emit(kennung)

    def projekt_setzen(self, projekt: Projekt | None) -> None:
        self.projekt = projekt
        self.aktualisieren()

    def farben_setzen(self, farben: Farben) -> None:
        self.flaeche.farben_setzen(farben)

    def aktualisieren(self, blatt_index: int | None = None) -> None:
        """Baut die Blaetter neu und haelt dabei die Stelle."""
        merker = self.auswahl.currentIndex() if blatt_index is None else blatt_index
        self.blaetter = blaetter(self.projekt, self.blattvorlage) if self.projekt else []

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

    def belegung_zeigen(self) -> bool:
        """Springt zur Verteilerbelegung - zum ersten ihrer Blaetter.

        Nicht am Titel zu erkennen: bei mehreren Buchten heisst jedes
        Belegungsblatt nach seiner Bucht. Die Blattfolge ist dagegen
        fest - Deckblatt, Belegung(en), dann je Leiste ein Blatt -, also
        ist es das zweite Blatt. Zurueck kommt, ob es eines gab.
        """
        if len(self.blaetter) < 2:
            return False
        self.auswahl.setCurrentIndex(1)
        return True

    # -- Vergroessern ------------------------------------------------------

    def zoom_stufen(self, richtung: int) -> None:
        """Eine Stufe hinauf oder hinab - vom Einpassen aus ab 100 %.

        Wer einpasst und vergroessert, will das Blatt groesser sehen,
        nicht kleiner: darum beginnt der Weg nach oben bei der wahren
        Groesse, der nach unten bei der Stufe darunter.
        """
        stufen = list(ZOOMSTUFEN)
        jetzt = self.zoomwahl.currentData()
        if jetzt == EINPASSEN:
            ziel = 1.0 if richtung > 0 else stufen[0]
        else:
            stelle = stufen.index(jetzt) + richtung
            if not 0 <= stelle < len(stufen):
                return
            ziel = stufen[stelle]
        self.zoomwahl.setCurrentIndex(self.zoomwahl.findData(ziel))

    def _zoom_gewaehlt(self, _index: int) -> None:
        daten = self.zoomwahl.currentData()
        self.flaeche.zoom_setzen(EINPASSEN if daten is None else float(daten))
        stufen = list(ZOOMSTUFEN)
        self.kleiner.setEnabled(daten != stufen[0])
        self.groesser.setEnabled(daten != stufen[-1])

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
            self.zaehler.setText(u("{0} / {1}").format(index + 1, gesamt))
        self.zurueck.setEnabled(index > 0)
        self.vor.setEnabled(0 <= index < gesamt - 1)
        # Ohne Blätter gibt es nichts zu wählen.
        self.auswahl.setEnabled(bool(gesamt))
        self.blatt_gewechselt.emit(index)
