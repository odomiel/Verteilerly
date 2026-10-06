"""Leistenansicht: die Belegung einer Leiste bearbeiten.

Die Spalten folgen den Mustertabellen: Stift, Farbe, Bezeichnung,
Rangierung, Bemerkung - je Stift zwei Zeilen für die Adern a und b. Die
Kabelspalte rechts zeigt, welches Kabel die Doppelader belegt.
"""

from __future__ import annotations

import json
from contextlib import contextmanager

from dataclasses import replace

from PySide6.QtCore import (
    QAbstractTableModel,
    QMimeData,
    QEvent,
    QModelIndex,
    QPersistentModelIndex,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QApplication,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QLineEdit,
    QSpinBox,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import schreibweisen
from ..layout import zellentext
from ..modell import (
    ANTEIL_MAX,
    ANTEIL_MIN,
    ANTEIL_VORGABE,
    AUSRICHTUNGEN,
    LEERER_STIL,
    LEISTEN_ZAHLEN,
    TEILBARE_FELDER,
    UNGETEILT,
    LINKS,
    MITTE,
    RECHTS,
    Aderadresse,
    ModellFehler,
    Textstil,
    Verteiler,
    Zellenteilung,
    adressen_lesen,
    leistenname,
)
from ..schreibweisen import Schreibweise
from .thema import HELL, Farben
from ..sprachen import u

SPALTE_STIFT = 0
SPALTE_ADER = 1
SPALTE_FARBE = 2
SPALTE_BEZEICHNUNG = 3
# Je Rangierung ein Feld: getippt wird in zwei getrennte Zellen,
# auf dem Blatt stehen beide nebeneinander in einer.
SPALTE_RANGIERUNG = 4
SPALTE_RANGIERUNG_2 = 5
SPALTE_BEMERKUNG = 6
SPALTE_KABEL = 7

#: Wie schmal sich die Leistenansicht ziehen laesst, wenn ihre
#: Kopfleiste weniger braucht. Genug fuer Leistenwahl und Knoepfe; die
#: Tabelle rollt, und die Vorschau behaelt ihren Platz.
SCHMALSTENS = 480

RANGIERSPALTEN = (SPALTE_RANGIERUNG, SPALTE_RANGIERUNG_2)

# Welches Feld einer Fundstelle in welcher Spalte steht.
SUCHSPALTEN = {
    "farbe": SPALTE_FARBE,
    "bezeichnung": SPALTE_BEZEICHNUNG,
    "rangierung": SPALTE_RANGIERUNG,
    "bemerkung": SPALTE_BEMERKUNG,
    "kabel": SPALTE_KABEL,
}

# Welche Spalten sich in zwei Beschriftungsfelder teilen lassen.
TEILSPALTEN = {
    SPALTE_BEZEICHNUNG: "bezeichnung",
    SPALTE_BEMERKUNG: "bemerkung",
}

# Welche Tabellenspalte welches Feld auf dem Blatt gestaltet.
# Beide Rangierfelder gehoeren zu derselben Zelle des Blattes - dort
# stehen sie nebeneinander in einer.
STILSPALTEN = {
    SPALTE_FARBE: "farbe",
    SPALTE_BEZEICHNUNG: "bezeichnung",
    SPALTE_RANGIERUNG: "rangierung",
    SPALTE_RANGIERUNG_2: "rangierung",
    SPALTE_BEMERKUNG: "bemerkung",
}
WAAGERECHT = {
    LINKS: Qt.AlignmentFlag.AlignLeft,
    MITTE: Qt.AlignmentFlag.AlignHCenter,
    RECHTS: Qt.AlignmentFlag.AlignRight,
}
# „Stift“ steht über der Nummer und über a und b, wie auf dem Blatt.
STIFTSPALTEN = (SPALTE_STIFT, SPALTE_ADER)

# Uebersetzt wird beim Anzeigen (headerData), nicht hier: das Modul wird
# geladen, bevor die Sprache feststeht.
UEBERSCHRIFTEN = [
    "Stift",
    "",
    "Farbe",
    "Bezeichnung",
    # Eine Überschrift über beiden Feldern - die zweite bleibt leer.
    "Rangierung",
    "",
    "Bemerkung",
    "Kabel",
]
AENDERBAR = {
    SPALTE_FARBE,
    SPALTE_BEZEICHNUNG,
    SPALTE_RANGIERUNG,
    SPALTE_RANGIERUNG_2,
    SPALTE_BEMERKUNG,
    # Nur an der ersten Zeile eines Kabelblocks - dort, wo die
    # Beschriftung steht. Das prueft flags() Zelle fuer Zelle.
    SPALTE_KABEL,
}


#: Woran die eigene Fracht in der Zwischenablage zu erkennen ist.
#: Daneben steht immer der schlichte Text - fuer Excel und fuer alle
#: anderen; die eigene Fracht traegt zusaetzlich die geteilten Zellen.
ZELLENFRACHT = "application/x-verteilerly-zellen"


class LeistenModell(QAbstractTableModel):
    """Die Belegung einer Leiste als Tabelle."""

    fehler_gemeldet = Signal(str)
    belegung_geaendert = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.verteiler: Verteiler | None = None
        self.leiste_nr: int | None = None
        self.farben: Farben = HELL
        self.schreibweise: Schreibweise = schreibweisen.STANDARD
        # Wie die Leisten heissen - Rangierungen zeigen auf dieselben.
        self.leisten_schreibweise: str = LEISTEN_ZAHLEN
        # Freitext im Rangierfeld ist abschaltbar: wer nur Ziele
        # eintraegt, will einen Tippfehler als Fehler gemeldet bekommen
        # und nicht als Vermerk stehen haben.
        self.freitext_erlaubt = False
        # Schreibgeschuetzt: zu sehen, aber nicht zu aendern.
        self.schreibgeschuetzt = False
        # Waehrend eines Sammelvorgangs (Einfuegen, Leeren) wird nicht
        # einzeln gemeldet: sonst entstuende je Zelle ein eigener Schritt
        # zum Zuruecknehmen, und ein Einfuegen waere zwanzigmal zurueck.
        self._sammelt = False
        # Ob die letzte Eingabe angenommen wurde - danach richtet sich,
        # ob Enter eine Zeile weiterspringt.
        self.eingabe_angenommen = True

    def melden(self) -> None:
        """Sagt, dass sich am Verteiler etwas geaendert hat.

        Waehrend eines Sammelvorgangs schweigt sie: dort meldet der
        Aufrufer einmal, wenn er fertig ist.
        """
        if not self._sammelt:
            self.belegung_geaendert.emit()

    @contextmanager
    def gesammelt(self):
        """Mehrere Aenderungen, eine Meldung.

        Wer zwanzig Zellen auf einmal fuellt, will sie auch mit einem
        Griff zuruecknehmen - gemeldet wird darum erst danach, und nur
        vom Aufrufer, wenn wirklich etwas geschehen ist.
        """
        vorher, self._sammelt = self._sammelt, True
        try:
            yield
        finally:
            self._sammelt = vorher

    def freitext_erlauben(self, an: bool) -> None:
        """Darf ins Rangierfeld auch etwas anderes als ein Ziel?"""
        self.freitext_erlaubt = an

    def schreibweise_setzen(self, schreibweise: Schreibweise) -> None:
        """Wie Rangierungen in den beiden Feldern stehen."""
        self.schreibweise = schreibweise
        self._rangierfelder_auffrischen()

    def leisten_schreibweise_setzen(self, schreibweise: str) -> None:
        """Wie die Leiste in einer Rangierung heisst: 3 oder C."""
        self.leisten_schreibweise = schreibweise
        self._rangierfelder_auffrischen()

    def _rangierfelder_auffrischen(self) -> None:
        if self.rowCount():
            self.dataChanged.emit(
                self.index(0, RANGIERSPALTEN[0]),
                self.index(self.rowCount() - 1, RANGIERSPALTEN[-1]),
            )

    def setzen(self, verteiler: Verteiler | None, leiste_nr: int | None) -> None:
        self.beginResetModel()
        self.verteiler = verteiler
        self.leiste_nr = leiste_nr
        self.endResetModel()

    def schreibschutz_setzen(self, an: bool) -> None:
        """Keine Zelle mehr beschreibbar - oder wieder alle."""
        self.schreibgeschuetzt = bool(an)
        if self.rowCount():
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(self.rowCount() - 1, self.columnCount() - 1),
            )

    def farben_setzen(self, farben: Farben) -> None:
        self.farben = farben
        if self.rowCount():
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(self.rowCount() - 1, self.columnCount() - 1),
            )

    # -- Aufbau ------------------------------------------------------------

    @property
    def _leiste(self):
        if self.verteiler is None or self.leiste_nr is None:
            return None
        try:
            return self.verteiler.leiste(self.leiste_nr)
        except ModellFehler:
            return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        leiste = self._leiste
        return leiste.da_anzahl * 2 if leiste else 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(UEBERSCHRIFTEN)

    def _stelle(self, zeile: int) -> tuple[int, str]:
        return zeile // 2 + 1, ("a" if zeile % 2 == 0 else "b")

    def adresse(self, zeile: int) -> Aderadresse:
        stift, seite = self._stelle(zeile)
        return Aderadresse(self.leiste_nr, stift, seite)

    # -- Textstil je Zelle -----------------------------------------

    def stilfeld(self, spalte: int) -> str | None:
        """Welches Feld des Blattes diese Spalte gestaltet - oder keines."""
        return STILSPALTEN.get(spalte)

    def stil(self, index: QModelIndex) -> Textstil | None:
        """Der Stil dieser Zelle; None, wo sich nichts gestalten laesst."""
        feld = self.stilfeld(index.column())
        if feld is None or not index.isValid() or self._leiste is None:
            return None
        stift_nr, seite = self._stelle(index.row())
        return self._leiste.stift(stift_nr).ader(seite).stil(feld)

    def stil_setzen(self, index: QModelIndex, stil: Textstil) -> bool:
        feld = self.stilfeld(index.column())
        if (feld is None or not index.isValid() or self._leiste is None
                or self.schreibgeschuetzt):
            return False
        stift_nr, seite = self._stelle(index.row())
        self._leiste.stift(stift_nr).ader(seite).stil_setzen(feld, stil)
        # Beide Rangierfelder zeigen dieselbe Zelle des Blattes.
        links = self.index(index.row(), 0)
        rechts = self.index(index.row(), self.columnCount() - 1)
        self.dataChanged.emit(links, rechts)
        self.melden()
        return True

    # -- Geteilte Zellen -------------------------------------------

    def teilfeld(self, spalte: int) -> str | None:
        """Welches Feld sich in dieser Spalte teilen laesst - oder keines."""
        return TEILSPALTEN.get(spalte)

    def _ader_zu(self, index: QModelIndex):
        if not index.isValid() or self._leiste is None:
            return None
        stift_nr, seite = self._stelle(index.row())
        return self._leiste.stift(stift_nr).ader(seite)

    def teilung(self, index: QModelIndex) -> Zellenteilung | None:
        """Die Teilung dieser Zelle; None, wo sich nichts teilen laesst."""
        feld = self.teilfeld(index.column())
        ader = self._ader_zu(index)
        if feld is None or ader is None:
            return None
        return ader.teilung(feld)

    def teilung_setzen(self, index: QModelIndex, teilung: Zellenteilung) -> bool:
        feld = self.teilfeld(index.column())
        ader = self._ader_zu(index)
        if feld is None or ader is None or self.schreibgeschuetzt:
            return False
        ader.teilung_setzen(feld, teilung)
        self.dataChanged.emit(index, index)
        self.melden()
        return True

    def zweittext_setzen(self, index: QModelIndex, text: str) -> bool:
        """Was im rechten Feld einer geteilten Zelle steht."""
        teilung = self.teilung(index)
        if teilung is None:
            return False
        return self.teilung_setzen(index, replace(teilung, text=text.strip()))

    def headerData(self, abschnitt, ausrichtung, rolle=Qt.ItemDataRole.DisplayRole):
        if ausrichtung == Qt.Orientation.Horizontal:
            if rolle == Qt.ItemDataRole.DisplayRole:
                return u(UEBERSCHRIFTEN[abschnitt])
        return None

    def flags(self, index: QModelIndex):
        grund = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        # Schreibgeschuetzt ist keine Zelle beschreibbar: damit ist jeder
        # Weg zu - Doppelklick, Eingabetaste, Lostippen und das Leeren
        # mit Entf, das die Flagge selbst abfragt. Lesen und Markieren
        # bleiben, man soll ja etwas sehen koennen.
        if self.schreibgeschuetzt:
            return grund
        if index.column() == SPALTE_KABEL:
            stift_nr, seite = self._stelle(index.row())
            # Beschreibbar ist, wo ein Kabel anfaengt - auch eines ohne
            # Beschriftung, sonst liesse sich keine nachtragen.
            if self._kabelanfang(stift_nr, seite) is None:
                return grund
        if index.column() in AENDERBAR:
            return grund | Qt.ItemFlag.ItemIsEditable
        return grund

    # -- Inhalte -----------------------------------------------------------

    def data(self, index: QModelIndex, rolle=Qt.ItemDataRole.DisplayRole):
        leiste = self._leiste
        if not index.isValid() or leiste is None:
            return None

        zeile, spalte = index.row(), index.column()
        stift_nr, seite = self._stelle(zeile)
        stift = leiste.stift(stift_nr)
        ader = stift.ader(seite)

        if rolle in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if spalte == SPALTE_STIFT:
                # Wie in den Vorlagen: die Nummer steht nur in der a-Zeile.
                return str(stift_nr) if seite == "a" else ""
            if spalte == SPALTE_ADER:
                return seite
            if spalte == SPALTE_FARBE:
                return ader.farbe
            if spalte == SPALTE_BEZEICHNUNG:
                return ader.bezeichnung
            if spalte in RANGIERSPALTEN:
                eintraege = self.verteiler.rangiereintraege(
                    self.adresse(zeile), self.schreibweise,
                    self.leisten_schreibweise,
                )
                stelle = RANGIERSPALTEN.index(spalte)
                return eintraege[stelle] if stelle < len(eintraege) else ""
            if spalte == SPALTE_BEMERKUNG:
                return ader.bemerkung
            if spalte == SPALTE_KABEL:
                kabel = self._kabelanfang(stift_nr, seite)
                if rolle == Qt.ItemDataRole.EditRole and kabel is not None:
                    # Getippt wird die Beschriftung, nicht der Zusatz
                    # „(gekürzt)“, den die Anzeige anhaengt.
                    return kabel.beschriftung
                return self._kabeltext(stift_nr, seite)

        feldstil = ader.stil(STILSPALTEN[spalte]) if spalte in STILSPALTEN else LEERER_STIL

        if rolle == Qt.ItemDataRole.TextAlignmentRole:
            if feldstil.ausrichtung:
                return int(
                    WAAGERECHT[feldstil.ausrichtung] | Qt.AlignmentFlag.AlignVCenter
                )
            if spalte in (SPALTE_STIFT, SPALTE_ADER):
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        if rolle == Qt.ItemDataRole.FontRole:
            schrift = QFont()
            eigen = False
            if spalte in (SPALTE_STIFT, SPALTE_ADER, SPALTE_FARBE, *RANGIERSPALTEN):
                schrift.setStyleHint(QFont.StyleHint.Monospace)
                schrift.setFamilies(["IBM Plex Mono", "DejaVu Sans Mono", "monospace"])
                eigen = True
            if feldstil.fett:
                schrift.setBold(True)
                eigen = True
            if feldstil.kursiv:
                schrift.setItalic(True)
                eigen = True
            if eigen:
                return schrift

        if rolle == Qt.ItemDataRole.ForegroundRole:
            if spalte in RANGIERSPALTEN:
                return QColor(self.farben.akzent)
            if spalte in (SPALTE_ADER, SPALTE_KABEL):
                return QColor(self.farben.schrift_leise)

        if rolle == Qt.ItemDataRole.BackgroundRole:
            if spalte == SPALTE_KABEL and self.verteiler.kabel_an(self.leiste_nr, stift_nr):
                return QColor(self.farben.akzent_leise)

        return None

    def _kabel_beschriften(self, stift_nr: int, seite: str, text: str) -> bool:
        """Beschriftet das Kabel, das an dieser Zeile anfaengt."""
        kabel = self._kabelanfang(stift_nr, seite)
        if kabel is None or kabel.beschriftung == text:
            return False
        kabel.beschriftung = text
        # Das Kabel kann ueber mehrere Leisten laufen - die Spalte ist
        # als Ganzes zu erneuern, nicht nur diese eine Zelle.
        self.dataChanged.emit(
            self.index(0, SPALTE_KABEL),
            self.index(self.rowCount() - 1, SPALTE_KABEL),
        )
        self.melden()
        return True

    def _belegung(self, adresse: Aderadresse) -> list[tuple[str, object]]:
        """Was in den beiden Feldern steht - Ziele zuerst, dann der Vermerk."""
        belegung: list[tuple[str, object]] = [
            ("ziel", ziel) for ziel in self.verteiler.ziele_von(adresse)
        ]
        ader = self.verteiler.ader(adresse)
        if ader.vermerk:
            stelle = 0 if ader.vermerk_zuerst else len(belegung)
            belegung.insert(stelle, ("vermerk", ader.vermerk))
        return belegung

    def _kabelanfang(self, stift_nr: int, seite: str):
        """Das Kabel, dessen Block in dieser Zeile beginnt - sonst nichts.

        Massgeblich ist die Lage des Kabels, nicht seine Beschriftung: ein
        Kabel ohne Text soll hier einen bekommen koennen.
        """
        if seite != "a":
            return None
        kabel = self.verteiler.kabel_an(self.leiste_nr, stift_nr)
        if kabel is None:
            return None
        beginnt_hier = any(
            a.leiste == self.leiste_nr and a.start_da == stift_nr
            for a in kabel.abschnitte
        )
        return kabel if beginnt_hier else None

    def _kabeltext(self, stift_nr: int, seite: str) -> str:
        """Die Beschriftung steht nur an der ersten Zeile des Kabelblocks."""
        kabel = self._kabelanfang(stift_nr, seite)
        if kabel is None:
            return ""
        text = kabel.beschriftung
        return u("{0} (gekürzt)").format(text) if kabel.gekuerzt else text

    def setData(self, index: QModelIndex, wert, rolle=Qt.ItemDataRole.EditRole) -> bool:
        # Ob die Eingabe angenommen wurde, merkt sich das Modell: die
        # Ansicht springt danach nur weiter, wenn sie es wurde.
        self.eingabe_angenommen = self._eintragen(index, wert, rolle)
        return self.eingabe_angenommen

    def _eintragen(self, index: QModelIndex, wert, rolle) -> bool:
        # Der Schutz sitzt hier, nicht nur an den Flaggen: wer das Modell
        # von Hand beschriebe, umginge ihn sonst.
        if (rolle != Qt.ItemDataRole.EditRole or self._leiste is None
                or self.schreibgeschuetzt):
            return False

        zeile, spalte = index.row(), index.column()
        stift_nr, seite = self._stelle(zeile)
        ader = self._leiste.stift(stift_nr).ader(seite)
        text = str(wert).strip()

        if spalte in RANGIERSPALTEN:
            return self._rangierung_setzen(zeile, spalte, text)

        if spalte == SPALTE_KABEL:
            return self._kabel_beschriften(stift_nr, seite, text)

        if spalte == SPALTE_FARBE:
            ader.farbe = text
        elif spalte == SPALTE_BEZEICHNUNG:
            ader.bezeichnung = text
        elif spalte == SPALTE_BEMERKUNG:
            ader.bemerkung = text
        else:
            return False

        self.dataChanged.emit(index, index)
        self.melden()
        return True

    def _rangierung_setzen(self, zeile: int, spalte: int, text: str) -> bool:
        """Setzt eines der beiden Rangierfelder; das andere bleibt stehen.

        Wer zwei Ziele in ein Feld tippt, bekommt sie auf beide verteilt -
        die alte Schreibweise „3 2a   5 4a“ funktioniert also weiter. Was
        sich nicht als Ziel lesen laesst, wird bei erlaubtem Freitext zum
        Vermerk der Ader, sonst bleibt es ein Fehler.
        """
        adresse = self.adresse(zeile)
        stelle = RANGIERSPALTEN.index(spalte)
        belegung = self._belegung(adresse)

        try:
            neue = adressen_lesen(text)
        except ModellFehler as fehler:
            if not (self.freitext_erlaubt and text.strip()):
                self.fehler_gemeldet.emit(str(fehler))
                return False
            neue = None                       # kein Ziel, sondern Vermerk

        if neue is not None and len(neue) > 1 and stelle == 0:
            belegung = [("ziel", ziel) for ziel in neue]   # beide auf einmal
        else:
            if neue is None:
                eintrag = ("vermerk", text.strip())
            elif neue:
                eintrag = ("ziel", neue[0])
            else:
                eintrag = None
            belegung += [None] * (len(RANGIERSPALTEN) - len(belegung))
            belegung[stelle] = eintrag
            belegung = [teil for teil in belegung if teil is not None]

        ziele = [wert for art, wert in belegung if art == "ziel"]
        vermerke = [wert for art, wert in belegung if art == "vermerk"]
        if len(vermerke) > 1:
            self.fehler_gemeldet.emit(
                u("Je Ader ist ein Vermerk vorgesehen, nicht zwei")
            )
            return False

        try:
            # Erst der Vermerk, denn er kann am Platz scheitern - und ein
            # halb gesetztes Feld waere schlimmer als eine Meldung.
            self.verteiler.rangierungen_setzen(adresse, ziele)
            self.verteiler.vermerk_setzen(
                adresse,
                vermerke[0] if vermerke else "",
                zuerst=bool(belegung) and belegung[0][0] == "vermerk",
            )
        except ModellFehler as fehler:
            self.fehler_gemeldet.emit(str(fehler))
            return False

        # Die Gegenstelle steht auf einer anderen Leiste - beide Spalten
        # koennen sich geaendert haben.
        self.dataChanged.emit(
            self.index(0, RANGIERSPALTEN[0]),
            self.index(self.rowCount() - 1, RANGIERSPALTEN[-1]),
        )
        self.melden()
        return True


def ausrichtungssymbol(art: str, farbe: str = "#000000") -> QIcon:
    """Ein Sinnbild fuer links-, mittig- oder rechtsbuendig.

    Vier Striche, zwei davon kurz und an der gemeinten Seite - so zeigen
    es Textprogramme seit jeher. Gezeichnet statt geladen: das Programm
    bringt keine Symboldateien mit, und die Farbe folgt dem Farbsatz.
    """
    kante = 16
    bild = QPixmap(kante, kante)
    bild.fill(Qt.GlobalColor.transparent)
    maler = QPainter(bild)
    maler.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    maler.setPen(QPen(QColor(farbe), 2))
    rand, lang, kurz = 2, kante - 4, int((kante - 4) * 0.6)
    for i, y in enumerate((3, 7, 11, 15)):
        breite = lang if i % 2 == 0 else kurz
        if art == RECHTS:
            x = rand + lang - breite
        elif art == MITTE:
            x = rand + (lang - breite) // 2
        else:
            x = rand
        maler.drawLine(x, y - 1, x + breite, y - 1)
    maler.end()
    return QIcon(bild)


LUFT_ZWISCHEN_FELDERN = 4          # Bildpunkte, wie der Fingerbreit auf dem Blatt


def teilungssymbol(farbe: str = "#000000", anteil: int = ANTEIL_VORGABE) -> QIcon:
    """Ein Kasten mit einem Strich darin - die geteilte Zelle."""
    kante = 16
    bild = QPixmap(kante, kante)
    bild.fill(Qt.GlobalColor.transparent)
    maler = QPainter(bild)
    maler.setPen(QPen(QColor(farbe), 1))
    rahmen = QRect(2, 4, kante - 5, kante - 9)
    maler.drawRect(rahmen)
    trenner = rahmen.right() - int(rahmen.width() * anteil / 100)
    maler.setPen(QPen(QColor(farbe), 1, Qt.PenStyle.DotLine))
    maler.drawLine(trenner, rahmen.top() + 1, trenner, rahmen.bottom() - 1)
    maler.end()
    return QIcon(bild)


class EingabeDelegat(QStyledItemDelegate):
    """Die Zelle zeichnen und bearbeiten.

    Zweierlei steckt darin. Erstens: Enter schliesst die Eingabe und geht
    eine Zeile tiefer - Qt laesst die Eingabemarke sonst stehen, wo sie
    war, und wer eine Spalte von oben nach unten ausfuellt, tippt dann
    jedes Mal zweimal.

    Zweitens die geteilte Zelle: sie traegt zwei Beschriftungsfelder
    nebeneinander. Gezeichnet werden beide Texte in einer Zelle,
    bearbeitet wird in zwei Eingabefeldern. Der feine Strich dazwischen
    steht nur hier - auf dem Blatt soll nicht zu sehen sein, dass es
    zwei Felder sind.
    """

    #: Zeile, Spalte und Haelfte der Zelle, in der Enter gedrueckt wurde.
    #: Die Stelle kommt mit, weil die Marke zu diesem Zeitpunkt schon
    #: weitergewandert sein kann: schliesst der Editor aus dem rechten
    #: Feld heraus, reicht Qt den Fokus an die naechste Zelle weiter, und
    #: der Sprung landete eine Spalte zu weit rechts.
    weiter = Signal(int, int, int)

    #: Einmaliger Wunsch: in welcher Haelfte der naechste Editor aufgeht.
    haelfte_beim_oeffnen = 0

    # -- Zeichnen ----------------------------------------------------------

    def _teilung(self, index) -> Zellenteilung | None:
        modell = index.model()
        teilung = modell.teilung(index) if hasattr(modell, "teilung") else None
        return teilung if teilung is not None and teilung.geteilt else None

    def _haelften(self, kasten: QRect, anteil: int) -> tuple[QRect, QRect]:
        rechts_b = int(kasten.width() * anteil / 100)
        links = QRect(
            kasten.left(), kasten.top(),
            kasten.width() - rechts_b - LUFT_ZWISCHEN_FELDERN, kasten.height(),
        )
        rechts = QRect(
            kasten.right() - rechts_b, kasten.top(), rechts_b, kasten.height()
        )
        return links, rechts

    def paint(self, maler, option, index) -> None:
        teilung = self._teilung(index)
        if teilung is None:
            super().paint(maler, option, index)
            return

        lage = QStyleOptionViewItem(option)
        self.initStyleOption(lage, index)
        texte = (lage.text, teilung.text)
        # Den Hintergrund samt Auswahl zeichnet der Stil, den Text nicht:
        # den setzen wir selbst in die beiden Haelften.
        lage.text = ""
        stil = lage.widget.style() if lage.widget else None
        if stil is not None:
            stil.drawControl(
                QStyle.ControlElement.CE_ItemViewItem, lage, maler, lage.widget
            )

        maler.save()
        gewaehlt = bool(lage.state & QStyle.StateFlag.State_Selected)
        maler.setPen(
            lage.palette.color(
                QPalette.ColorGroup.Normal,
                QPalette.ColorRole.HighlightedText if gewaehlt
                else QPalette.ColorRole.Text,
            )
        )
        maler.setFont(lage.font)
        innen = lage.rect.adjusted(4, 0, -4, 0)
        links, rechts = self._haelften(innen, teilung.anteil)
        flaggen = int(lage.displayAlignment) or int(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        for kasten, text in zip((links, rechts), texte):
            if text:
                maler.drawText(
                    kasten, flaggen,
                    maler.fontMetrics().elidedText(
                        str(text), Qt.TextElideMode.ElideRight, kasten.width()
                    ),
                )
        # Nur im Editor: ein feiner Strich zeigt, dass hier zwei Felder
        # sind. Auf dem Blatt steht dort nichts.
        trenner = links.right() + LUFT_ZWISCHEN_FELDERN // 2
        stift = QPen(maler.pen().color(), 1, Qt.PenStyle.DotLine)
        stift.setColor(QColor(stift.color().red(), stift.color().green(),
                              stift.color().blue(), 90))
        maler.setPen(stift)
        maler.drawLine(trenner, links.top() + 3, trenner, links.bottom() - 3)
        maler.restore()

    # -- Bearbeiten --------------------------------------------------------

    def createEditor(self, eltern, option, index):
        teilung = self._teilung(index)
        if teilung is None:
            feld = super().createEditor(eltern, option, index)
            feld.stelle = QPersistentModelIndex(index)
            return feld

        kasten = QWidget(eltern)
        kasten.setAutoFillBackground(True)
        aufbau = QHBoxLayout(kasten)
        aufbau.setContentsMargins(0, 0, 0, 0)
        aufbau.setSpacing(LUFT_ZWISCHEN_FELDERN)
        kasten.felder = []
        for anteil in (100 - teilung.anteil, teilung.anteil):
            feld = QLineEdit(kasten)
            feld.behaelter = kasten
            feld.installEventFilter(self)
            aufbau.addWidget(feld, anteil)
            kasten.felder.append(feld)
        kasten.stelle = QPersistentModelIndex(index)
        # Wer aus einem rechten Feld heruntergesprungen ist, tippt dort
        # weiter: der Fokusstellvertreter entscheidet, welches
        # Feld die Eingabemarke bekommt.
        kasten.setFocusProxy(kasten.felder[self.haelfte_beim_oeffnen])
        self.haelfte_beim_oeffnen = 0
        return kasten

    def setEditorData(self, editor, index) -> None:
        felder = getattr(editor, "felder", None)
        if felder is None:
            super().setEditorData(editor, index)
            return
        teilung = index.model().teilung(index)
        felder[0].setText(str(index.data(Qt.ItemDataRole.EditRole) or ""))
        felder[1].setText(teilung.text if teilung else "")

    def setModelData(self, editor, modell, index) -> None:
        felder = getattr(editor, "felder", None)
        if felder is None:
            super().setModelData(editor, modell, index)
            return
        # Beide Texte vorher ablesen: das erste Schreiben meldet eine
        # Aenderung, worauf die Ansicht den Editor neu fuellt - das zweite
        # Feld stuende sonst wieder auf dem alten Wert.
        links, rechts = felder[0].text(), felder[1].text()
        modell.setData(index, links, Qt.ItemDataRole.EditRole)
        modell.zweittext_setzen(index, rechts)

    def eventFilter(self, editor, ereignis) -> bool:
        behaelter = getattr(editor, "behaelter", None)
        felder = getattr(behaelter, "felder", None)
        if ereignis.type() == QEvent.Type.FocusOut and felder:
            # Qt kennt nur das eine Feld, das es beobachtet, und wollte
            # bei jedem Fokuswechsel die Eingabe schliessen - mit einem
            # Editor, den die Ansicht nicht kennt. Also selber machen:
            # ein Wechsel zwischen den Haelften ist kein Verlassen der
            # Zelle, und wer sie verlaesst, schliesst den Behaelter.
            neu = QApplication.focusWidget()
            if neu is not None and (neu in felder or behaelter.isAncestorOf(neu)):
                return True
            # Ein Editor, den die Ansicht schon weggeraeumt hat, ist
            # unsichtbar - ihn zu schliessen haette sie nur zu meckern.
            if not getattr(behaelter, "geschlossen", False) and behaelter.isVisible():
                behaelter.geschlossen = True
                self.commitData.emit(behaelter)
                self.closeEditor.emit(
                    behaelter, QAbstractItemDelegate.EndEditHint.NoHint
                )
            return True
        if ereignis.type() == QEvent.Type.KeyPress:
            # Esc verwirft die Eingabe - auch hier mit dem Behaelter,
            # nicht mit der Haelfte.
            if felder and ereignis.key() == Qt.Key.Key_Escape:
                behaelter.geschlossen = True
                self.closeEditor.emit(
                    behaelter, QAbstractItemDelegate.EndEditHint.RevertModelCache
                )
                return True
            # Innerhalb einer geteilten Zelle springt Tab ins zweite Feld,
            # statt gleich in die naechste Zelle zu gehen.
            if felder and ereignis.key() == Qt.Key.Key_Tab and editor is felder[0]:
                felder[1].setFocus()
                return True
            if felder and ereignis.key() == Qt.Key.Key_Backtab and editor is felder[1]:
                felder[0].setFocus()
                return True
            if (
                ereignis.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and not ereignis.modifiers() & Qt.KeyboardModifier.AltModifier
            ):
                ziel = behaelter if behaelter is not None else editor
                haelfte = 1 if felder and editor is felder[1] else 0
                stelle = getattr(ziel, "stelle", None)
                ziel.geschlossen = True
                self.commitData.emit(ziel)
                self.closeEditor.emit(
                    ziel, QAbstractItemDelegate.EndEditHint.SubmitModelCache
                )
                if stelle is not None and stelle.isValid():
                    self.weiter.emit(stelle.row(), stelle.column(), haelfte)
                return True
        return super().eventFilter(editor, ereignis)


class ZusammengefassteKopfzeile(QHeaderView):
    """Kopfzeile, in der eine Ueberschrift ueber mehrere Spalten reicht.

    Qt kennt keine verbundenen Kopffelder. Die zusammengefassten Spalten
    werden deshalb selbst gezeichnet: die erste bekommt die Breite aller,
    die uebrigen zeichnen nichts - so steht „Rangierung“ mittig ueber
    beiden Feldern statt nur ueber dem ersten.
    """

    def __init__(self, gruppen: tuple[tuple[int, ...], ...], parent=None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.gruppen = gruppen
        self._erste = {gruppe[0]: gruppe for gruppe in gruppen}
        self._weitere = {
            spalte for gruppe in gruppen for spalte in gruppe[1:]
        }

    def paintSection(self, maler, rechteck, spalte: int) -> None:
        if spalte in self._weitere:
            return                      # gehoert zur Ueberschrift links davon
        gruppe = self._erste.get(spalte)
        if gruppe:
            breite = sum(self.sectionSize(teil) for teil in gruppe)
            rechteck = QRect(rechteck.x(), rechteck.y(), breite, rechteck.height())
        super().paintSection(maler, rechteck, spalte)


class LeistenAnsicht(QWidget):
    """Leistenauswahl und Tabelle."""

    belegung_geaendert = Signal()
    fehler_gemeldet = Signal(str)
    leiste_gewechselt = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.verteiler: Verteiler | None = None

        self.auswahl = QComboBox()
        self.auswahl.currentIndexChanged.connect(self._leiste_gewechselt)

        # Durchblättern ohne den Umweg über das Aufklappmenü - wie über
        # der Vorschau. Beim Abarbeiten einer Bucht geht es Leiste für
        # Leiste, da will niemand jedes Mal auswählen.
        self.zurueck = QPushButton("‹")
        self.zurueck.setShortcut(QKeySequence("Alt+Left"))
        self.zurueck.setToolTip(u("Eine Leiste zurück (Alt+←)"))
        self.vor = QPushButton("›")
        self.vor.setShortcut(QKeySequence("Alt+Right"))
        self.vor.setToolTip(u("Eine Leiste weiter (Alt+→)"))
        for knopf in (self.zurueck, self.vor):
            knopf.setFixedWidth(30)
            # Das Stilblatt polstert Knöpfe breit; hier bliebe sonst
            # nichts vom Pfeil übrig.
            knopf.setStyleSheet("padding: 4px 0;")
        self.zurueck.clicked.connect(lambda: self._schieben(-1))
        self.vor.clicked.connect(lambda: self._schieben(1))

        self.modell = LeistenModell(self)
        self.modell.belegung_geaendert.connect(self.belegung_geaendert)
        self.modell.fehler_gemeldet.connect(self.fehler_gemeldet)

        kopf = QHBoxLayout()
        kopf.setContentsMargins(0, 0, 0, 6)
        kopf.addWidget(QLabel(u("Leiste:")))
        kopf.addWidget(self.auswahl)
        kopf.addWidget(self.zurueck)
        kopf.addWidget(self.vor)
        kopf.addSpacing(16)
        # Zuruecknehmen steht bei den Bearbeitungsknoepfen, nicht nur im
        # Menue: geaendert wird hier, also wird hier auch zurueckgenommen.
        # Die Handlungen kommen vom Fenster - es weiss, was zurueckgeht.
        self.rueckgaengig_knopf = QToolButton()
        self.wiederherstellen_knopf = QToolButton()
        for knopf, zeichen in (
            (self.rueckgaengig_knopf, "↶"),
            (self.wiederherstellen_knopf, "↷"),
        ):
            knopf.setText(zeichen)
            knopf.setAutoRaise(True)
            knopf.setEnabled(False)
            kopf.addWidget(knopf)
        kopf.addSpacing(16)
        for knopf in self._textknoepfe():
            kopf.addWidget(knopf)
        # Der Schreibschutz steht dort, wo gearbeitet wird: neben den
        # Knoepfen, die die Zelle aendern. Leer nimmt er keinen Platz.
        self.schreibschutz = QLabel("")
        self.schreibschutz.setVisible(False)
        kopf.addSpacing(8)
        kopf.addWidget(self.schreibschutz)
        # Was hier steht, ist Chrom und waechst nicht mit dem Verteiler:
        # ein Text, der die Kabel der Leiste aufzaehlte, hat die Vorschau
        # aus dem Fenster geschoben (siehe minimumSizeHint).
        kopf.addStretch(1)
        self.kopfleiste = kopf

        self.tabelle = QTableView()
        self.tabelle.setModel(self.modell)
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.tabelle.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.tabelle.setAlternatingRowColors(False)
        # Entf leert die gewaehlten Zellen, ohne sie erst zu oeffnen.
        self.tabelle.installEventFilter(self)
        # Ausschneiden, Kopieren, Einfuegen - per Rechtsklick und mit den
        # gewohnten Kuerzeln. Sie haengen an der Tabelle selbst
        # (WidgetShortcut): liegt ein Editor offen, gehoert Strg+C dem
        # Eingabefeld und nicht der Tabelle.
        self.zellenmenue_aktionen = self._zwischenablage_aktionen()
        self.tabelle.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.tabelle.customContextMenuRequested.connect(self._zellenmenue_zeigen)

        self.delegat = EingabeDelegat(self.tabelle)
        self.tabelle.setItemDelegate(self.delegat)
        self.delegat.weiter.connect(self._eine_zeile_tiefer)
        # Auch die Auswahl anhoeren, nicht nur die Marke: beim Ziehen
        # ueber mehrere Zellen steht die Marke auf der ersten, und liegt
        # die in einer Spalte ohne Stil, waeren die Knoepfe sonst aus.
        for melder in (
            self.tabelle.selectionModel().currentChanged,
            self.tabelle.selectionModel().selectionChanged,
        ):
            melder.connect(lambda *_: self._knoepfe_auffrischen())

        # „Stift“ und „Rangierung“ reichen über je zwei Spalten.
        self.tabelle.setHorizontalHeader(
            ZusammengefassteKopfzeile((STIFTSPALTEN, RANGIERSPALTEN), self.tabelle)
        )
        kopfzeile = self.tabelle.horizontalHeader()
        for spalte, breite in (
            (SPALTE_STIFT, 46),
            (SPALTE_ADER, 32),
            (SPALTE_FARBE, 66),
            # Beide gleich breit; die Überschrift „Rangierung“ muss in
            # die erste hineinpassen, sonst wird sie beschnitten.
            (SPALTE_RANGIERUNG, 96),
            (SPALTE_RANGIERUNG_2, 96),
        ):
            kopfzeile.setSectionResizeMode(spalte, QHeaderView.ResizeMode.Fixed)
            self.tabelle.setColumnWidth(spalte, breite)
        kopfzeile.setSectionResizeMode(SPALTE_BEZEICHNUNG, QHeaderView.ResizeMode.Stretch)
        kopfzeile.setSectionResizeMode(SPALTE_BEMERKUNG, QHeaderView.ResizeMode.Stretch)
        kopfzeile.setSectionResizeMode(SPALTE_KABEL, QHeaderView.ResizeMode.Stretch)

        aufbau = QVBoxLayout(self)
        aufbau.setContentsMargins(10, 8, 10, 10)
        aufbau.addLayout(kopf)
        aufbau.addWidget(self.tabelle)

        self._knoepfe_auffrischen()

    def bearbeitungsaktionen_setzen(self, rueckgaengig, wiederherstellen) -> None:
        """Legt die Handlungen des Fensters auf die beiden Pfeilknoepfe.

        Nicht ueber ``setDefaultAction``: das schriebe den Namen der
        Handlung auf den Knopf, und dort soll der Pfeil stehen. Statt
        dessen folgt der Knopf ihr von Hand - gedrueckt loest er sie aus,
        ausgegraut ist er, wenn sie es ist.
        """
        for knopf, handlung in (
            (self.rueckgaengig_knopf, rueckgaengig),
            (self.wiederherstellen_knopf, wiederherstellen),
        ):
            knopf.clicked.connect(handlung.trigger)
            knopf.setEnabled(handlung.isEnabled())
            handlung.changed.connect(
                lambda knopf=knopf, handlung=handlung: knopf.setEnabled(
                    handlung.isEnabled()
                )
            )
            kuerzel = handlung.shortcut().toString(
                QKeySequence.SequenceFormat.NativeText
            )
            name = handlung.text().replace("&", "")
            knopf.setToolTip(f"{name} ({kuerzel})" if kuerzel else name)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt-Name
        """Wie schmal sich die Ansicht ziehen laesst.

        Von selbst nimmt Qt die Mindestbreite des breitesten Inhalts -
        und die waechst mit dem Verteiler: lange Kabelnamen in der
        Tabelle machten die Ansicht breiter als das Fenster, der Teiler
        schob die **Vorschau hinaus**, bis nichts mehr von ihr zu sehen
        war. Die Tabelle rollt aber ohnehin; noetig ist nur, was die
        Kopfleiste an Knoepfen braucht - und das haengt am Programm,
        nicht am Verteiler.
        """
        masse = super().minimumSizeHint()
        raender = self.layout().contentsMargins()
        noetig = (
            self.kopfleiste.minimumSize().width()
            + raender.left()
            + raender.right()
        )
        return QSize(min(masse.width(), max(noetig, SCHMALSTENS)), masse.height())

    def _textknoepfe(self) -> list[QToolButton]:
        """Ausrichtung, fett und kursiv fuer die gewaehlte Zelle.

        Sie stehen neben der Leistenwahl, weil sie dorthin gehoeren, wo
        gearbeitet wird. Nochmaliges Druecken nimmt die Einstellung
        zurueck: dann gilt wieder, was die Blattvorlage fuer die Spalte
        haelt.
        """
        self.ausrichtungsknoepfe: dict[str, QToolButton] = {}
        for art, hinweis in (
            (LINKS, "Linksbündig"),
            (MITTE, "Mittig"),
            (RECHTS, "Rechtsbündig"),
        ):
            knopf = QToolButton()
            knopf.setCheckable(True)
            knopf.setAutoRaise(True)
            knopf.setToolTip(u("{0} — nochmals drücken: wie die Blattvorlage").format(hinweis))
            knopf.clicked.connect(
                lambda _an=False, gewaehlt=art: self._ausrichten(gewaehlt)
            )
            self.ausrichtungsknoepfe[art] = knopf

        self.fett = QToolButton()
        self.fett.setText("F")
        self.fett.setToolTip(u("Fett"))
        self.kursiv = QToolButton()
        self.kursiv.setText("K")
        self.kursiv.setToolTip(u("Kursiv"))
        for knopf, schnitt in ((self.fett, "fett"), (self.kursiv, "kursiv")):
            knopf.setCheckable(True)
            knopf.setAutoRaise(True)
            schrift = knopf.font()
            schrift.setBold(schnitt == "fett")
            schrift.setItalic(schnitt == "kursiv")
            knopf.setFont(schrift)
            knopf.clicked.connect(
                lambda _an=False, was=schnitt: self._schnitt_umschalten(was)
            )

        # Die geteilte Zelle: Knopf und der Anteil des rechten Feldes.
        self.teilen = QToolButton()
        self.teilen.setCheckable(True)
        self.teilen.setAutoRaise(True)
        self.teilen.setToolTip(
            u("Zelle in zwei Beschriftungsfelder teilen — auf dem Blatt ohne "
            "Trennstrich")
        )
        self.teilen.clicked.connect(self._teilen_umschalten)

        self.anteil = QSpinBox()
        self.anteil.setRange(ANTEIL_MIN, ANTEIL_MAX)
        self.anteil.setValue(ANTEIL_VORGABE)
        self.anteil.setSuffix(" %")
        self.anteil.setFixedWidth(66)
        self.anteil.setToolTip(u("Wie breit das rechte Feld ist"))
        self.anteil.valueChanged.connect(self._anteil_gesetzt)

        self.textknoepfe = [
            *self.ausrichtungsknoepfe.values(), self.fett, self.kursiv,
            self.teilen,
        ]
        self._symbole_auffrischen()
        return [*self.textknoepfe, self.anteil]

    def _symbole_auffrischen(self) -> None:
        """Die gezeichneten Sinnbilder folgen dem Farbsatz."""
        farbe = self.modell.farben.schrift
        for art, knopf in getattr(self, "ausrichtungsknoepfe", {}).items():
            knopf.setIcon(ausrichtungssymbol(art, farbe))
        if hasattr(self, "teilen"):
            self.teilen.setIcon(teilungssymbol(farbe))

    def _gewaehlte(self, taugt) -> list:
        """Alle markierten Zellen, auf die der Knopf wirken kann.

        Ist mehr als eine Zelle markiert, gilt der Knopf fuer alle auf
        einmal - eine ganze Spalte mittig zu stellen soll nicht Zeile fuer
        Zeile gehen. Die Reihenfolge ist die des Blattes, damit die
        Aenderungen von oben nach unten laufen.
        """
        gewaehlt = list(self.tabelle.selectionModel().selectedIndexes())
        jetzt = self.tabelle.currentIndex()
        if jetzt.isValid() and not any(
            i.row() == jetzt.row() and i.column() == jetzt.column() for i in gewaehlt
        ):
            gewaehlt.append(jetzt)
        passend = [i for i in gewaehlt if i.isValid() and taugt(i.column()) is not None]
        return sorted(passend, key=lambda i: (i.row(), i.column()))

    def _stilzellen(self) -> list:
        """Die markierten Zellen, an denen sich etwas gestalten laesst."""
        return self._gewaehlte(self.modell.stilfeld)

    def _teilzellen(self) -> list:
        """Die markierten Zellen, die sich teilen lassen."""
        return self._gewaehlte(self.modell.teilfeld)

    def _stilzelle(self):
        """Die Zelle, nach der sich die Knoepfe zeigen - die aktuelle."""
        index = self.tabelle.currentIndex()
        if index.isValid() and self.modell.stilfeld(index.column()) is not None:
            return index
        zellen = self._stilzellen()
        return zellen[0] if zellen else None

    def _teilzelle(self):
        """Dasselbe fuer die Teilung."""
        index = self.tabelle.currentIndex()
        if index.isValid() and self.modell.teilfeld(index.column()) is not None:
            return index
        zellen = self._teilzellen()
        return zellen[0] if zellen else None

    def _knoepfe_auffrischen(self) -> None:
        """Zeigt am Knopf, was in der gewaehlten Zelle gilt.

        Angezeigt wird die aktuelle Zelle; gewirkt wird auf alle
        markierten.
        """
        index = self._stilzelle()
        stil = self.modell.stil(index) if index is not None else None
        darf = not self.modell.schreibgeschuetzt
        for knopf in (*self.ausrichtungsknoepfe.values(), self.fett, self.kursiv):
            knopf.setEnabled(darf and bool(self._stilzellen()))
        for art, knopf in self.ausrichtungsknoepfe.items():
            knopf.setChecked(bool(stil) and stil.ausrichtung == art)
        self.fett.setChecked(bool(stil) and stil.fett)
        self.kursiv.setChecked(bool(stil) and stil.kursiv)

        teilbar = self._teilzelle()
        teilung = self.modell.teilung(teilbar) if teilbar is not None else None
        self.teilen.setEnabled(darf and bool(self._teilzellen()))
        self.teilen.setChecked(bool(teilung) and teilung.geteilt)
        # Der Anteil laesst sich nur an einer geteilten Zelle einstellen.
        self.anteil.setEnabled(darf and bool(teilung) and teilung.geteilt)
        if teilung is not None:
            self.anteil.blockSignals(True)
            self.anteil.setValue(teilung.anteil)
            self.anteil.blockSignals(False)

    def _teilen_umschalten(self) -> None:
        zellen = self._teilzellen()
        if not zellen:
            return
        # Wohin es gehen soll, sagt die aktuelle Zelle; alle markierten
        # bekommen dasselbe - nicht jede ihr eigenes Gegenteil.
        jetzt = self._teilzelle()
        soll = not self.modell.teilung(jetzt).geteilt
        for index in zellen:
            teilung = self.modell.teilung(index)
            self.modell.teilung_setzen(
                index,
                replace(teilung, geteilt=soll, anteil=self.anteil.value()),
            )
        self._knoepfe_auffrischen()

    def _anteil_gesetzt(self, wert: int) -> None:
        for index in self._teilzellen():
            teilung = self.modell.teilung(index)
            if teilung.geteilt and teilung.anteil != wert:
                self.modell.teilung_setzen(index, replace(teilung, anteil=wert))

    def _ausrichten(self, art: str) -> None:
        zellen = self._stilzellen()
        if not zellen:
            return
        jetzt = self._stilzelle()
        # Nochmals derselbe Knopf: zurueck zur Blattvorlage.
        soll = "" if self.modell.stil(jetzt).ausrichtung == art else art
        for index in zellen:
            self.modell.stil_setzen(
                index, replace(self.modell.stil(index), ausrichtung=soll)
            )
        self._knoepfe_auffrischen()

    def _schnitt_umschalten(self, was: str) -> None:
        zellen = self._stilzellen()
        if not zellen:
            return
        jetzt = self._stilzelle()
        soll = not getattr(self.modell.stil(jetzt), was)
        for index in zellen:
            self.modell.stil_setzen(
                index, replace(self.modell.stil(index), **{was: soll})
            )
        self._knoepfe_auffrischen()

    def eventFilter(self, gegenstand, ereignis) -> bool:
        """Entf leert die gewaehlten Zellen.

        Wer einen Eintrag loswerden will, soll die Zelle nicht erst mit
        einem Doppelklick oeffnen und den Text markieren muessen. Beim
        Bearbeiten selbst greift das nicht: dann liegt die Taste beim
        Eingabefeld, und dort loescht sie Zeichen.
        """
        tastendruck = (
            gegenstand is self.tabelle
            and ereignis.type() == QEvent.Type.KeyPress
            and not self.tabelle.state() == QTableView.State.EditingState
        )
        if tastendruck and ereignis.key() == Qt.Key.Key_Delete:
            if self._zellen_leeren():
                return True
        # Enter geht eine Zeile tiefer, auch ohne dass etwas getippt
        # wurde: wer die Tabelle durchgeht, kommt so von Zeile zu Zeile -
        # wie in einer Tabellenkalkulation. Beim Bearbeiten greift das
        # nicht, dann liegt die Taste beim Editor; der uebernimmt die
        # Eingabe und springt selbst weiter.
        if (
            tastendruck
            and ereignis.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and not ereignis.modifiers() & Qt.KeyboardModifier.AltModifier
        ):
            marke = self.tabelle.currentIndex()
            if marke.isValid():
                self._zeile_weiter(marke.row(), marke.column())
                return True
        return super().eventFilter(gegenstand, ereignis)

    # -- Zwischenablage ----------------------------------------------------

    def _zwischenablage_aktionen(self) -> list:
        """Die drei Handlungen samt Kuerzeln, an der Tabelle angemeldet."""
        self.aktion_ausschneiden = QAction(u("Ausschneiden"), self)
        self.aktion_ausschneiden.setShortcut(QKeySequence.StandardKey.Cut)
        self.aktion_ausschneiden.triggered.connect(self.zellen_ausschneiden)
        self.aktion_kopieren = QAction(u("Kopieren"), self)
        self.aktion_kopieren.setShortcut(QKeySequence.StandardKey.Copy)
        self.aktion_kopieren.triggered.connect(self.zellen_kopieren)
        self.aktion_einfuegen = QAction(u("Einfügen"), self)
        self.aktion_einfuegen.setShortcut(QKeySequence.StandardKey.Paste)
        self.aktion_einfuegen.triggered.connect(self.zellen_einfuegen)
        handlungen = [
            self.aktion_ausschneiden, self.aktion_kopieren, self.aktion_einfuegen
        ]
        for handlung in handlungen:
            handlung.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
            self.tabelle.addAction(handlung)
        return handlungen

    def _zellenmenue_zeigen(self, stelle) -> None:
        """Das Rechtsklickmenue - was gerade geht, steht offen."""
        unter_der_maus = self.tabelle.indexAt(stelle)
        gewaehlt = self.tabelle.selectionModel().selectedIndexes()
        # Ein Rechtsklick neben die Markierung nimmt die Zelle unter der
        # Maus - wie ueberall. Innerhalb der Markierung bleibt sie.
        if unter_der_maus.isValid() and unter_der_maus not in gewaehlt:
            self.tabelle.setCurrentIndex(unter_der_maus)
        self.zellenmenue_auffrischen()
        menue = QMenu(self)
        menue.addActions(self.zellenmenue_aktionen)
        menue.exec(self.tabelle.viewport().mapToGlobal(stelle))

    def zellenmenue_auffrischen(self) -> None:
        """Graut aus, was gerade nicht geht.

        Steht neben dem Zeigen des Menues, nicht darin: so laesst es
        sich pruefen, ohne ein Menue aufzumachen - ein offenes Menue
        haelt die Testreihe an.
        """
        darf = not self.modell.schreibgeschuetzt
        self.aktion_ausschneiden.setEnabled(darf and bool(self._beschreibbare()))
        self.aktion_kopieren.setEnabled(
            bool(self._gewaehlte(lambda spalte: spalte))
        )
        self.aktion_einfuegen.setEnabled(
            darf and bool(QApplication.clipboard().text())
        )

    def _beschreibbare(self) -> list:
        """Die markierten Zellen, die sich beschreiben lassen."""
        return [
            index for index in self._gewaehlte(lambda spalte: spalte)
            if self.modell.flags(index) & Qt.ItemFlag.ItemIsEditable
        ]

    def zellentext(self) -> str:
        """Die markierten Zellen als Text - Spalten mit Tabulator getrennt.

        Genommen wird der **Block** von der obersten linken bis zur
        untersten rechten markierten Zelle, mitsamt dem, was
        dazwischenliegt. Nur so steht das Eingefuegte wieder in
        denselben Spalten: wer zwei Spalten mit einer Luecke markiert
        und das Kopierte zusammenschoebe, traefe beim Einfuegen die
        Nachbarspalte. Das Format ist das der Tabellenkalkulation -
        Tabulator zwischen den Spalten, Zeilenumbruch zwischen den
        Zeilen -, also laesst es sich auch dort einfuegen.
        """
        gewaehlt = self._gewaehlte(lambda spalte: spalte)
        if not gewaehlt:
            return ""
        zeilen = [index.row() for index in gewaehlt]
        spalten = [index.column() for index in gewaehlt]
        return "\n".join(
            "\t".join(
                self._text_von(self.modell.index(zeile, spalte))
                for spalte in range(min(spalten), max(spalten) + 1)
            )
            for zeile in range(min(zeilen), max(zeilen) + 1)
        )

    def _text_von(self, index) -> str:
        """Der Text einer Zelle - eine geteilte hintereinander.

        Dasselbe tun CSV und Mappe (``layout.zellentext``): ein Raster
        kennt keine halbe Spalte. Die eigene Fracht traegt die Teilung
        daneben, fuer das Einfuegen im Programm selbst.
        """
        wert = str(index.data(Qt.ItemDataRole.EditRole) or "")
        teilung = self.modell.teilung(index)
        return wert if teilung is None else zellentext(wert, teilung)

    def zellenfracht(self) -> list:
        """Die markierten Zellen als Liste von Zeilen - mit ihrer Teilung.

        Der schlichte Text kann eine geteilte Zelle nur hintereinander
        wiedergeben; wer sie *als* geteilte Zelle einfuegen will,
        braucht beide Felder und den Anteil. Darum reist beides: der
        Text fuer alle anderen, diese Fracht fuer uns selbst.
        """
        gewaehlt = self._gewaehlte(lambda spalte: spalte)
        if not gewaehlt:
            return []
        zeilen = [index.row() for index in gewaehlt]
        spalten = [index.column() for index in gewaehlt]
        fracht = []
        for zeile in range(min(zeilen), max(zeilen) + 1):
            stueck = []
            for spalte in range(min(spalten), max(spalten) + 1):
                index = self.modell.index(zeile, spalte)
                teilung = self.modell.teilung(index)
                stueck.append({
                    "text": str(index.data(Qt.ItemDataRole.EditRole) or ""),
                    "teilung": None if teilung is None else {
                        "geteilt": bool(teilung.geteilt),
                        "anteil": int(teilung.anteil),
                        "text": teilung.text,
                    },
                })
            fracht.append(stueck)
        return fracht

    def zellen_kopieren(self) -> None:
        """Legt die Zellen ab - als Text und als eigene Fracht.

        Auch eine leere Zelle wird abgelegt: wer sie einfuegt, leert
        damit die Zielzelle - genau wie in einer Tabellenkalkulation.
        """
        fracht = self.zellenfracht()
        if not fracht:
            return
        daten = QMimeData()
        daten.setText(self.zellentext())
        daten.setData(
            ZELLENFRACHT, json.dumps({"zeilen": fracht}).encode("utf-8")
        )
        QApplication.clipboard().setMimeData(daten)

    def zellen_ausschneiden(self) -> None:
        """Erst kopieren, dann leeren - beides auf einen Griff."""
        if self.modell.schreibgeschuetzt:
            return
        self.zellen_kopieren()
        self._zellen_leeren()

    def _abgelegte_zellen(self) -> list:
        """Was in der Ablage liegt, als Liste von Zeilen.

        Die eigene Fracht geht vor: sie traegt die geteilten Zellen.
        Liegt sie nicht da - etwa weil anderswo kopiert wurde -, wird
        der schlichte Text gelesen, Tabulator fuer Tabulator.
        """
        ablage = QApplication.clipboard().mimeData()
        if ablage is not None and ablage.hasFormat(ZELLENFRACHT):
            try:
                inhalt = json.loads(
                    bytes(ablage.data(ZELLENFRACHT)).decode("utf-8")
                )
                zeilen = inhalt["zeilen"]
            except (ValueError, KeyError, TypeError, UnicodeDecodeError):
                zeilen = None
            if isinstance(zeilen, list):
                return zeilen
        text = QApplication.clipboard().text()
        if not text:
            return []
        return [
            [{"text": wert, "teilung": None} for wert in stueck.split("\t")]
            for stueck in text.rstrip("\n").split("\n")
        ]

    def zellen_einfuegen(self) -> int:
        """Setzt ab der Marke ein, was in der Ablage liegt.

        Gefuellt wird nach unten und nach rechts, so weit die Ablage und
        die Tabelle reichen. Zellen, die sich nicht beschreiben lassen -
        Stift, Ader, eine Kabelspalte ohne Kabel -, werden dabei
        uebergangen; was daneben steht, rutscht deswegen nicht.

        Eine **geteilte Zelle** kommt ganz mit: beide Felder und der
        Anteil. War die kopierte Zelle ungeteilt, wird die Teilung am
        Ziel aufgehoben - eingefuegt wird, was kopiert wurde.
        """
        if self.modell.schreibgeschuetzt:
            return 0
        marke = self.tabelle.currentIndex()
        zeilen = self._abgelegte_zellen()
        if not zeilen or not marke.isValid():
            return 0
        gesetzt = 0
        with self.modell.gesammelt():
            for zeile, stueck in enumerate(zeilen):
                for spalte, zelle in enumerate(stueck):
                    index = self.modell.index(
                        marke.row() + zeile, marke.column() + spalte
                    )
                    if not index.isValid():
                        continue
                    if not self.modell.flags(index) & Qt.ItemFlag.ItemIsEditable:
                        continue
                    if self.modell.setData(
                        index, zelle.get("text", ""), Qt.ItemDataRole.EditRole
                    ):
                        gesetzt += 1
                    if self._teilung_einsetzen(index, zelle.get("teilung")):
                        gesetzt += 1
        if gesetzt:
            self.modell.melden()
        return gesetzt

    def _teilung_einsetzen(self, index, abgelegt) -> bool:
        """Setzt die Teilung der kopierten Zelle am Ziel.

        Nur dort, wo sich ueberhaupt teilen laesst; steht in der Ablage
        nichts dazu (fremder Text), bleibt die Teilung des Ziels, wie
        sie ist.
        """
        ziel = self.modell.teilung(index)
        if ziel is None or not isinstance(abgelegt, dict):
            return False
        neu = replace(
            ziel,
            geteilt=bool(abgelegt.get("geteilt", False)),
            anteil=int(abgelegt.get("anteil", ziel.anteil)),
            text=str(abgelegt.get("text", "")),
        )
        if neu == ziel:
            return False
        return self.modell.teilung_setzen(index, neu)

    def _zellen_leeren(self) -> int:
        """Leert jede gewaehlte Zelle, die sich beschreiben laesst."""
        geleert = 0
        for index in self._gewaehlte(lambda spalte: spalte):
            if not self.modell.flags(index) & Qt.ItemFlag.ItemIsEditable:
                continue
            # Eine geteilte Zelle traegt zwei Texte - beide gehoeren zu ihr.
            teilung = self.modell.teilung(index)
            if teilung is not None and teilung.text:
                self.modell.zweittext_setzen(index, "")
                geleert += 1
            if str(index.data(Qt.ItemDataRole.EditRole) or ""):
                if self.modell.setData(index, "", Qt.ItemDataRole.EditRole):
                    geleert += 1
        return geleert

    def _eine_zeile_tiefer(self, zeile: int, spalte: int, haelfte: int = 0) -> None:
        """Nach Enter eine Zeile weiter - wie in einer Tabellenkalkulation.

        Gesprungen wird von der Zelle aus, in der Enter gedrueckt wurde,
        nicht von der Marke: die steht beim Schliessen eines geteilten
        Editors schon eine Spalte weiter, und der Sprung ginge dann
        schraeg nach unten statt geradewegs.

        Wer im rechten Feld einer geteilten Zelle getippt hat, tippt
        unten im rechten Feld weiter, sofern die Zeile dort ebenfalls
        geteilt ist. Ist sie es nicht, bleibt es beim blossen
        Weiterruecken der Marke.

        Wurde die Eingabe nicht angenommen - eine unlesbare Rangierung
        etwa -, bleibt die Marke stehen: dort ist etwas zu richten.
        """
        if not self.modell.eingabe_angenommen:
            return
        self._zeile_weiter(zeile, spalte, haelfte)

    def _zeile_weiter(self, zeile: int, spalte: int, haelfte: int = 0) -> None:
        """Eine Zeile tiefer - ohne zu fragen, ob etwas eingetragen wurde.

        Diesen Weg geht Enter auf der blanken Tabelle: dort gibt es keine
        Eingabe, die angenommen oder abgelehnt werden koennte.
        """
        naechste = self.modell.index(zeile + 1, spalte)
        if not naechste.isValid():
            # Ans Ende gekommen: die Marke gehoert zurueck auf die Zelle,
            # in der getippt wurde - Qt hat sie moeglicherweise verschoben.
            self.tabelle.setCurrentIndex(self.modell.index(zeile, spalte))
            return
        self.tabelle.setCurrentIndex(naechste)
        teilung = self.modell.teilung(naechste)
        if haelfte and teilung is not None and teilung.geteilt:
            self.delegat.haelfte_beim_oeffnen = haelfte
            self.tabelle.edit(naechste)

    def farben_setzen(self, farben) -> None:
        self.modell.farben_setzen(farben)
        self._symbole_auffrischen()
        self._schreibschutz_faerben()

    def schreibschutz_setzen(self, an: bool, grund: str = "") -> None:
        """Nichts laesst sich mehr aendern - und es steht rot daneben.

        Nicht nur in der Titelzeile: wer hier tippt, soll hier sehen,
        warum nichts geschieht. Gesperrt wird an der Wurzel - das Modell
        gibt keine beschreibbare Zelle mehr her -, die Knoepfe und die
        Eingabeausloeser der Tabelle kommen dazu, damit es auch so
        aussieht.
        """
        self.modell.schreibschutz_setzen(an)
        self.tabelle.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers if an
            else (
                QAbstractItemView.EditTrigger.DoubleClicked
                | QAbstractItemView.EditTrigger.SelectedClicked
                | QAbstractItemView.EditTrigger.EditKeyPressed
                | QAbstractItemView.EditTrigger.AnyKeyPressed
            )
        )
        self.schreibschutz.setText(u("schreibgeschützt") if an else "")
        self.schreibschutz.setToolTip(grund)
        self.schreibschutz.setVisible(an)
        self._schreibschutz_faerben()
        self._knoepfe_auffrischen()

    def _schreibschutz_faerben(self) -> None:
        """Rot aus dem Farbsatz - im dunklen Satz ein helleres Rot."""
        if not hasattr(self, "schreibschutz"):
            return
        schrift = self.schreibschutz.font()
        schrift.setBold(True)
        self.schreibschutz.setFont(schrift)
        self.schreibschutz.setStyleSheet(
            f"color: {self.modell.farben.warnung};"
        )

    def schreibweise_setzen(self, schreibweise: Schreibweise) -> None:
        self.modell.schreibweise_setzen(schreibweise)

    def leisten_schreibweise_setzen(self, schreibweise: str) -> None:
        """Wie die Leisten heissen - in der Wahlliste wie im Rangierfeld."""
        self.modell.leisten_schreibweise_setzen(schreibweise)
        self._leistenliste_auffrischen()

    def freitext_erlauben(self, an: bool) -> None:
        self.modell.freitext_erlauben(an)

    def verteiler_setzen(self, verteiler: Verteiler | None) -> None:
        self.verteiler = verteiler
        self._leistenliste_auffrischen(erste=True)
        # Ohne Verteiler gibt es nichts zu wählen - dann bleibt das Feld aus.
        self.auswahl.setEnabled(bool(self.auswahl.count()))
        self._leiste_gewechselt()

    def _leistenliste_auffrischen(self, erste: bool = False) -> None:
        """Baut die Wahlliste neu - beim Verteiler wie beim Umbenennen.

        Die gewaehlte Leiste bleibt: umgestellt wird ihr Name, nicht,
        welche man gerade vor sich hat.
        """
        vorher = self.auswahl.currentData()
        self.auswahl.blockSignals(True)
        self.auswahl.clear()
        if self.verteiler is not None:
            for leiste in self.verteiler.alle_leisten:
                self.auswahl.addItem(
                    u("Leiste {0}  ({1} DA)").format(
                        leistenname(leiste.nummer, self.modell.leisten_schreibweise),
                        leiste.da_anzahl,
                    ),
                    leiste.nummer,
                )
        self.auswahl.blockSignals(False)
        stelle = -1 if erste or vorher is None else self.auswahl.findData(vorher)
        self.auswahl.setCurrentIndex(
            stelle if stelle >= 0 else (0 if self.auswahl.count() else -1)
        )

    def _schieben(self, richtung: int) -> None:
        """Eine Leiste weiter oder zurück - am Ende passiert nichts."""
        neu = self.auswahl.currentIndex() + richtung
        if 0 <= neu < self.auswahl.count():
            self.auswahl.setCurrentIndex(neu)

    def leiste_zeigen(self, nummer: int) -> None:
        stelle = self.auswahl.findData(nummer)
        if stelle >= 0:
            self.auswahl.setCurrentIndex(stelle)

    def stelle_zeigen(self, adresse: Aderadresse, feld: str = "") -> bool:
        """Schaltet auf die Leiste und stellt die Marke auf die Zelle.

        Gebraucht wird das von der Suche: eine Fundstelle ist erst dann
        gefunden, wenn sie auch vor Augen steht.
        """
        self.leiste_zeigen(adresse.leiste)
        if self.modell.leiste_nr != adresse.leiste:
            return False
        zeile = (adresse.stift - 1) * 2 + (0 if adresse.seite == "a" else 1)
        index = self.modell.index(zeile, SUCHSPALTEN.get(feld, SPALTE_BEZEICHNUNG))
        if not index.isValid():
            return False
        self.tabelle.setCurrentIndex(index)
        self.tabelle.scrollTo(index)
        self.tabelle.setFocus()
        return True

    def aktualisieren(self) -> None:
        self.modell.setzen(self.verteiler, self.modell.leiste_nr)

    def _leiste_gewechselt(self) -> None:
        nummer = self.auswahl.currentData()
        self.modell.setzen(self.verteiler, nummer)
        self._pfeile_auffrischen()
        if nummer is not None:
            self.leiste_gewechselt.emit(nummer)

    def _pfeile_auffrischen(self) -> None:
        """Am Anfang und am Ende ist der jeweilige Pfeil aus."""
        stelle = self.auswahl.currentIndex()
        self.zurueck.setEnabled(stelle > 0)
        self.vor.setEnabled(0 <= stelle < self.auswahl.count() - 1)

