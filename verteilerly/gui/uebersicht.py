"""Verteilerübersicht: Leisten als Kästen aus DA-Zellen.

Eine Zelle entspricht einer Doppelader, ein Kabel einem zusammenhängenden
Block über die von ihm belegten Doppeladern - genau wie in den
Mustertabellen. Buchten stehen nebeneinander.
"""

from __future__ import annotations

from PySide6.QtCore import QMimeData, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QDrag, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from ..modell import LEISTEN_ZAHLEN, Kabel, Verteiler, leistenname
from .thema import HELL, Farben
from ..sprachen import u

#: Woran ein gezogenes Kabel zu erkennen ist. Ein eigener Typ: fremde
#: Fracht soll hier nichts ausloesen.
KABELFRACHT = "application/x-verteilerly-kabel"

# Eine DA-Zelle im Bearbeitungsfenster. Groesser als auf dem Blatt, und
# zwar mit Absicht: hier soll der Name auch eines Kabels zu lesen sein,
# das nur eine oder zwei Doppeladern belegt. Die Hoehe traegt dafuer zwei
# Zeilen - ein Name bricht um, bevor er abgeschnitten wird.
ZELLE_B = 38
ZELLE_H = 46
LABEL_B = 36
RAND = 14
ABSTAND_LEISTEN = 9
ABSTAND_BUCHTEN = 30


class Uebersicht(QWidget):
    """Zeigt den Verteiler und laesst Doppeladern auswaehlen."""

    auswahl_geaendert = Signal(object)      # (leiste, da) oder None
    stelle_aktiviert = Signal(int, int)     # Doppelklick auf freie Stelle
    kabel_aktiviert = Signal(object)        # Doppelklick auf ein Kabel
    #: Ein Kabel wurde woandershin gezogen: (Kabel, Leiste, Start-DA,
    #: kopieren). Das Fenster fuehrt es aus - die Uebersicht zeigt nur.
    kabel_umgelegt = Signal(object, int, int, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.verteiler: Verteiler | None = None
        self.farben: Farben = HELL
        # Wie die Leisten heissen - nur fuer die Hinweistexte; gezeichnet
        # wird hier ohne Beschriftung.
        self.leisten_schreibweise: str = LEISTEN_ZAHLEN
        self.auswahl: tuple[int, int] | None = None
        self._kaesten: dict[int, QRect] = {}
        # Woher ein Ziehen kam: Druckpunkt, Kabel und an welcher seiner
        # Doppeladern es angefasst wurde.
        self._griff: tuple[QPoint, Kabel, int] | None = None
        #: Wohin es gerade zeigt - (Leiste, Start-DA, passt) fuer die Vorschau.
        self._ziel: tuple[int, int, bool] | None = None
        #: Das Kabel, das gerade am Zeiger haengt.
        self._gezogen: Kabel | None = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)

    # -- Zustand -----------------------------------------------------------

    def verteiler_setzen(self, verteiler: Verteiler | None) -> None:
        self.verteiler = verteiler
        self.auswahl = None
        self._neu_vermessen()

    def leisten_schreibweise_setzen(self, schreibweise: str) -> None:
        """Wie die Leisten in den Hinweistexten heissen."""
        self.leisten_schreibweise = schreibweise

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
        self._griff = None
        if stelle is not None and self.verteiler is not None:
            kabel = self.verteiler.kabel_an(*stelle)
            if kabel is not None and ereignis.button() == Qt.MouseButton.LeftButton:
                # Gemerkt wird, an welcher Doppelader angefasst wurde: beim
                # Fallenlassen soll genau sie unter dem Zeiger liegen.
                self._griff = (
                    ereignis.position().toPoint(),
                    kabel,
                    self._versatz_im_kabel(kabel, stelle),
                )
        self.auswahl_geaendert.emit(stelle)
        self.update()

    @staticmethod
    def _versatz_im_kabel(kabel: Kabel, stelle: tuple[int, int]) -> int:
        """Die wievielte Doppelader des Kabels angefasst wurde - ab 0."""
        for versatz, (_kabel_da, leiste, da) in enumerate(kabel.positionen()):
            if (leiste, da) == stelle:
                return versatz
        return 0

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
        """Der Kabelname steht im Kasten oft gekuerzt - hier ganz.

        Und: wer ein Kabel weit genug zieht, nimmt es mit. Erst ab der
        Strecke, die das Erscheinungsbild als Ziehen versteht - sonst
        haette schon ein zittriger Klick das Kabel verschoben.
        """
        if self._griff is not None and (
            ereignis.buttons() & Qt.MouseButton.LeftButton
        ):
            druckpunkt, kabel, versatz = self._griff
            weite = (ereignis.position().toPoint() - druckpunkt).manhattanLength()
            if weite >= QApplication.startDragDistance():
                self._griff = None
                self._ziehen(kabel, versatz)
                return
        stelle = self._zelle_bei(int(ereignis.position().x()), int(ereignis.position().y()))
        self.setToolTip(self._hinweistext(stelle))

    def mouseReleaseEvent(self, ereignis) -> None:
        self._griff = None
        super().mouseReleaseEvent(ereignis)

    # -- Ziehen und Fallenlassen -------------------------------------------

    def _ziehen(self, kabel: Kabel, versatz: int) -> None:
        """Nimmt das Kabel an den Zeiger - verschieben, mit Strg kopieren."""
        fracht = QMimeData()
        fracht.setData(KABELFRACHT, str(versatz).encode("ascii"))
        zug = QDrag(self)
        zug.setMimeData(fracht)
        zug.setPixmap(self._kabelbild(kabel))
        # Das Kabel selbst reist nicht durch die Zwischenablage: fremde
        # Anwendungen sollen damit nichts anfangen koennen. Es steht so
        # lange hier.
        self._gezogen = kabel
        zug.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction,
                 Qt.DropAction.MoveAction)
        self._gezogen = None
        self._ziel = None
        self.update()

    def _kabelbild(self, kabel: Kabel):
        """Der Block des Kabels als Bild am Zeiger - so sieht man, was man traegt."""
        plaetze = [(leiste, da) for _kd, leiste, da in kabel.positionen()]
        erste = self._zellrechteck(*plaetze[0])
        letzte = self._zellrechteck(*plaetze[-1])
        return self.grab(erste.united(letzte))

    def _fracht_taugt(self, ereignis) -> bool:
        return (
            ereignis.mimeData().hasFormat(KABELFRACHT)
            and self._gezogen is not None
            and self.verteiler is not None
        )

    def _zielstelle(self, ereignis) -> tuple[int, int, bool] | None:
        """Wohin das Kabel fiele - und ob es dort ganz und frei liegt."""
        stelle = self._zelle_bei(
            int(ereignis.position().x()), int(ereignis.position().y())
        )
        if stelle is None:
            return None
        versatz = int(bytes(ereignis.mimeData().data(KABELFRACHT)).decode("ascii"))
        leiste, da = stelle
        start = da - versatz
        passt = True
        try:
            self.verteiler._platz_verlangen(
                leiste, start, self._gezogen.da_aufgelegt, ausser=self._gezogen
            )
        except Exception:      # noqa: BLE001 - hier wird nur gezeigt, nicht gehandelt
            passt = False
        return leiste, start, passt

    def dragEnterEvent(self, ereignis) -> None:  # noqa: N802 - Qt-Name
        if self._fracht_taugt(ereignis):
            ereignis.acceptProposedAction()

    def dragMoveEvent(self, ereignis) -> None:  # noqa: N802 - Qt-Name
        if not self._fracht_taugt(ereignis):
            return
        ziel = self._zielstelle(ereignis)
        if ziel != self._ziel:
            self._ziel = ziel
            self.update()
        if ziel is not None and ziel[2]:
            ereignis.acceptProposedAction()
        else:
            ereignis.ignore()

    def dragLeaveEvent(self, ereignis) -> None:  # noqa: N802 - Qt-Name
        self._ziel = None
        self.update()

    def dropEvent(self, ereignis) -> None:  # noqa: N802 - Qt-Name
        if not self._fracht_taugt(ereignis):
            return
        ziel = self._zielstelle(ereignis)
        self._ziel = None
        if ziel is None or not ziel[2]:
            ereignis.ignore()
            return
        leiste, start, _passt = ziel
        kopieren = ereignis.proposedAction() == Qt.DropAction.CopyAction
        ereignis.acceptProposedAction()
        self.kabel_umgelegt.emit(self._gezogen, leiste, start, kopieren)

    def _hinweistext(self, stelle: tuple[int, int] | None) -> str:
        if stelle is None or self.verteiler is None:
            return ""
        leiste, da = stelle
        name = leistenname(leiste, self.leisten_schreibweise)
        kabel = self.verteiler.kabel_an(leiste, da)
        if kabel is None:
            return u("Leiste {0}, DA {1} — frei").format(name, da)
        zeilen = [kabel.beschriftung, u("Leiste {0}, DA {1}").format(name, da)]
        if kabel.kabeltyp:
            zeilen.append(kabel.kabeltyp)
        if kabel.gekuerzt:
            zeilen.append(
                u("gekürzt: {0} von {1} DA").format(
                    kabel.da_aufgelegt, kabel.da_gesamt
                )
            )
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
        self._ziel_zeichnen(maler)

    def _ziel_zeichnen(self, maler: QPainter) -> None:
        """Zeigt beim Ziehen, wo das Kabel landen wuerde.

        Nur der Umriss, damit darunter sichtbar bleibt, was dort liegt -
        und in der Warnfarbe, wo es nicht hinpasst.
        """
        if self._ziel is None or self._gezogen is None:
            return
        leiste, start, passt = self._ziel
        if leiste not in self._kaesten:
            return
        anzahl = self._gezogen.da_aufgelegt
        kasten = self._kaesten[leiste]
        links = kasten.left() + (start - 1) * ZELLE_B
        umriss = QRect(links, kasten.top(), anzahl * ZELLE_B, ZELLE_H)
        maler.setPen(QPen(
            self.farben.q("akzent" if passt else "warnung"), 2,
            Qt.PenStyle.SolidLine if passt else Qt.PenStyle.DashLine,
        ))
        maler.setBrush(Qt.BrushStyle.NoBrush)
        maler.drawRect(umriss.adjusted(1, 1, -1, -1))

    def _hinweis_zeichnen(self, maler: QPainter) -> None:
        maler.setPen(self.farben.q("schrift_leise"))
        maler.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            u("Kein Verteiler geöffnet.\nDatei ▸ Neuer Verteiler"),
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
                beschriftung = u("{0} (gekürzt)").format(beschriftung)
            maler.setPen(self.farben.q("akzent"))
            self._namen_zeichnen(maler, block, beschriftung)

    def _namen_zeichnen(self, maler: QPainter, block: QRect, name: str) -> None:
        """Den Kabelnamen in seinen Block - umgebrochen, wenn es sein muss.

        Ein Kabel ueber eine Doppelader hat nur eine Zellbreite Platz; in
        einer Zeile blieben davon drei Buchstaben und ein Auslassungszeichen.
        Also wird umgebrochen, solange die Zeilen in die Hoehe passen, und
        erst wenn auch das nicht reicht, einzeilig abgeschnitten - lieber
        ein halber Name als keiner.
        """
        platz = block.adjusted(4, 2, -3, -2)
        text, flaggen = self.namenslage(name, platz)
        maler.drawText(platz, flaggen, text)

    def namenslage(self, name: str, platz: QRect):
        """Was von einem Namen zu sehen ist und wie - Text und Flaggen.

        Getrennt vom Zeichnen, damit die Entscheidung pruefbar bleibt:
        passt der umgebrochene Name in die Hoehe, wird umgebrochen; sonst
        bleibt es bei einer Zeile mit Auslassungszeichen.
        """
        masse = QFontMetrics(self.font())
        lage = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        umbruch = lage | Qt.TextFlag.TextWordWrap
        if masse.boundingRect(platz, umbruch, name).height() <= platz.height():
            return name, umbruch
        return (
            masse.elidedText(name, Qt.TextElideMode.ElideRight, platz.width()),
            lage,
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
