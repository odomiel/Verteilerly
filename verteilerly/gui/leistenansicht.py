"""Leistenansicht: die Belegung einer Leiste bearbeiten.

Die Spalten folgen den Mustertabellen: Stift, Farbe, Bezeichnung,
Rangierung, Bemerkung - je Stift zwei Zeilen für die Adern a und b. Die
Kabelspalte rechts zeigt, welches Kabel die Doppelader belegt.
"""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..modell import Aderadresse, ModellFehler, Verteiler, adressen_lesen
from .thema import HELL, Farben

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

RANGIERSPALTEN = (SPALTE_RANGIERUNG, SPALTE_RANGIERUNG_2)

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
}


class LeistenModell(QAbstractTableModel):
    """Die Belegung einer Leiste als Tabelle."""

    fehler_gemeldet = Signal(str)
    belegung_geaendert = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.verteiler: Verteiler | None = None
        self.leiste_nr: int | None = None
        self.farben: Farben = HELL

    def setzen(self, verteiler: Verteiler | None, leiste_nr: int | None) -> None:
        self.beginResetModel()
        self.verteiler = verteiler
        self.leiste_nr = leiste_nr
        self.endResetModel()

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

    def headerData(self, abschnitt, ausrichtung, rolle=Qt.ItemDataRole.DisplayRole):
        if ausrichtung == Qt.Orientation.Horizontal:
            if rolle == Qt.ItemDataRole.DisplayRole:
                return UEBERSCHRIFTEN[abschnitt]
        return None

    def flags(self, index: QModelIndex):
        grund = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
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
                ziele = self.verteiler.ziele_von(self.adresse(zeile))
                stelle = RANGIERSPALTEN.index(spalte)
                return str(ziele[stelle]) if stelle < len(ziele) else ""
            if spalte == SPALTE_BEMERKUNG:
                return ader.bemerkung
            if spalte == SPALTE_KABEL:
                return self._kabeltext(stift_nr, seite)

        if rolle == Qt.ItemDataRole.TextAlignmentRole:
            if spalte in (SPALTE_STIFT, SPALTE_ADER):
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        if rolle == Qt.ItemDataRole.FontRole:
            if spalte in (SPALTE_STIFT, SPALTE_ADER, SPALTE_FARBE, *RANGIERSPALTEN):
                schrift = QFont()
                schrift.setStyleHint(QFont.StyleHint.Monospace)
                schrift.setFamilies(["IBM Plex Mono", "DejaVu Sans Mono", "monospace"])
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

    def _kabeltext(self, stift_nr: int, seite: str) -> str:
        """Die Beschriftung steht nur an der ersten Zeile des Kabelblocks."""
        kabel = self.verteiler.kabel_an(self.leiste_nr, stift_nr)
        if kabel is None:
            return ""
        if seite != "a":
            return ""
        beginnt_hier = any(
            a.leiste == self.leiste_nr and a.start_da == stift_nr
            for a in kabel.abschnitte
        )
        if not beginnt_hier:
            return ""
        text = kabel.beschriftung
        return f"{text} (gekürzt)" if kabel.gekuerzt else text

    def setData(self, index: QModelIndex, wert, rolle=Qt.ItemDataRole.EditRole) -> bool:
        if rolle != Qt.ItemDataRole.EditRole or self._leiste is None:
            return False

        zeile, spalte = index.row(), index.column()
        stift_nr, seite = self._stelle(zeile)
        ader = self._leiste.stift(stift_nr).ader(seite)
        text = str(wert).strip()

        if spalte in RANGIERSPALTEN:
            return self._rangierung_setzen(zeile, spalte, text)

        if spalte == SPALTE_FARBE:
            ader.farbe = text
        elif spalte == SPALTE_BEZEICHNUNG:
            ader.bezeichnung = text
        elif spalte == SPALTE_BEMERKUNG:
            ader.bemerkung = text
        else:
            return False

        self.dataChanged.emit(index, index)
        self.belegung_geaendert.emit()
        return True

    def _rangierung_setzen(self, zeile: int, spalte: int, text: str) -> bool:
        """Setzt eine der beiden Rangierungen; die andere bleibt stehen.

        Wer zwei Ziele in ein Feld tippt, bekommt sie auf beide verteilt -
        die alte Schreibweise „3 2a   5 4a“ funktioniert also weiter.
        """
        adresse = self.adresse(zeile)
        bisher = self.verteiler.ziele_von(adresse)
        stelle = RANGIERSPALTEN.index(spalte)

        try:
            neue = adressen_lesen(text)
        except ModellFehler as fehler:
            self.fehler_gemeldet.emit(str(fehler))
            return False

        if len(neue) > 1 and stelle == 0:
            ziele = neue                      # beide Felder auf einmal
        else:
            ziele = list(bisher) + [None] * (len(RANGIERSPALTEN) - len(bisher))
            ziele[stelle] = neue[0] if neue else None
            ziele = [ziel for ziel in ziele if ziel is not None]

        try:
            self.verteiler.rangierungen_setzen(adresse, ziele)
        except ModellFehler as fehler:
            self.fehler_gemeldet.emit(str(fehler))
            return False

        # Die Gegenstelle steht auf einer anderen Leiste - beide Spalten
        # koennen sich geaendert haben.
        self.dataChanged.emit(
            self.index(0, RANGIERSPALTEN[0]),
            self.index(self.rowCount() - 1, RANGIERSPALTEN[-1]),
        )
        self.belegung_geaendert.emit()
        return True


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
        self.hinweis = QLabel("")

        kopf = QHBoxLayout()
        kopf.setContentsMargins(0, 0, 0, 6)
        kopf.addWidget(QLabel("Leiste:"))
        kopf.addWidget(self.auswahl)
        kopf.addSpacing(12)
        kopf.addWidget(self.hinweis, 1)

        self.modell = LeistenModell(self)
        self.modell.belegung_geaendert.connect(self.belegung_geaendert)
        self.modell.fehler_gemeldet.connect(self.fehler_gemeldet)

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

        # „Rangierung“ steht über beiden Rangierfeldern.
        self.tabelle.setHorizontalHeader(
            ZusammengefassteKopfzeile((RANGIERSPALTEN,), self.tabelle)
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

    def farben_setzen(self, farben) -> None:
        self.modell.farben_setzen(farben)

    def verteiler_setzen(self, verteiler: Verteiler | None) -> None:
        self.verteiler = verteiler
        self.auswahl.blockSignals(True)
        self.auswahl.clear()
        if verteiler is not None:
            for leiste in verteiler.alle_leisten:
                self.auswahl.addItem(
                    f"Leiste {leiste.nummer}  ({leiste.da_anzahl} DA)", leiste.nummer
                )
        self.auswahl.blockSignals(False)
        self.auswahl.setCurrentIndex(0 if self.auswahl.count() else -1)
        # Ohne Verteiler gibt es nichts zu wählen - dann bleibt das Feld aus.
        self.auswahl.setEnabled(bool(self.auswahl.count()))
        self._leiste_gewechselt()

    def leiste_zeigen(self, nummer: int) -> None:
        stelle = self.auswahl.findData(nummer)
        if stelle >= 0:
            self.auswahl.setCurrentIndex(stelle)

    def aktualisieren(self) -> None:
        self.modell.setzen(self.verteiler, self.modell.leiste_nr)
        self._hinweis_setzen()

    def _leiste_gewechselt(self) -> None:
        nummer = self.auswahl.currentData()
        self.modell.setzen(self.verteiler, nummer)
        self._hinweis_setzen()
        if nummer is not None:
            self.leiste_gewechselt.emit(nummer)

    def _hinweis_setzen(self) -> None:
        nummer = self.auswahl.currentData()
        if self.verteiler is None or nummer is None:
            self.hinweis.setText("")
            return
        kabel = [
            k
            for k in self.verteiler.kabel
            if any(a.leiste == nummer for a in k.abschnitte)
        ]
        if not kabel:
            self.hinweis.setText("kein Kabel aufgelegt")
        else:
            self.hinweis.setText(
                "Kabel: " + ", ".join(k.beschriftung or "ohne Beschriftung" for k in kabel)
            )
