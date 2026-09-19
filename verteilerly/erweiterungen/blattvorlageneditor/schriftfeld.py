"""Das Schriftfeld im Blattvorlagen-Editor - der Briefkopf am Blattfuss.

Die Bloecke stehen nebeneinander wie auf dem Blatt, darin die Angaben
untereinander. Eintraege lassen sich zwischen den Bloecken ziehen; ``+``
und ``−`` fuegen hinzu und nehmen weg. Die Breiten sind Anteile: ohne
Haken bei *Breiten selbst festlegen* teilt das Programm nach Augenmass.

Bei der Bauart ``beispiel`` (*Mit Anschriften*) ist die Aufteilung fest -
links Matrix und Verteiler, rechts die beiden Anschriften. Dann bleiben
nur die Breiten der beiden Haelften; die Bloecke werden aufgehoben, bis
wieder auf ``standard`` umgestellt wird.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ...blattvorlagen import SCHRIFTFELDMARKEN
from ...layout import schriftfeldanteile
from ...modell import BLATTBESCHRIFTUNG
from ...sprachen import u

#: Wie die Angaben im Editor heissen - wie auf dem Blatt, dazu "eigene".
MARKENNAMEN = {**BLATTBESCHRIFTUNG, "eigene": "Eigene Felder"}
HOECHSTENS_BLOECKE = 6


class SchriftfeldEditor(QWidget):
    """Bloecke nebeneinander, darin die Angaben untereinander."""

    geaendert = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.art = "standard"
        self._bloecke: list[list[str]] = [[]]
        self._breiten: list[float] = []
        self.listen: list[QListWidget] = []
        self.breiten: list[QDoubleSpinBox] = []

        self.hinweis = hinweis = QLabel(u(
            "Welche Angaben in welchem Block stehen. Einträge lassen sich "
            "zwischen den Blöcken ziehen."
        ))
        hinweis.setWordWrap(True)
        self.fest = QLabel(u(
            "Bei „Mit Anschriften“ ist die Aufteilung fest: links Matrix und "
            "Verteiler, rechts die beiden Anschriften."
        ))
        self.fest.setWordWrap(True)
        # Umbrechende Beschriftungen melden im Rollbereich nur eine Zeile
        # Hoehe an - die zweite laege sonst ueber den Bloecken.
        for beschriftung, zeilen in ((hinweis, 2), (self.fest, 3)):
            beschriftung.setMinimumHeight(beschriftung.fontMetrics().lineSpacing() * zeilen + 4)
        self.bloecke = QHBoxLayout()

        self.block_hinzu = QPushButton(u("Block hinzufügen"))
        self.block_hinzu.clicked.connect(self.block_hinzufuegen)
        self.block_weg = QPushButton(u("Letzten Block entfernen"))
        self.block_weg.clicked.connect(self.block_entfernen)
        knoepfe = QHBoxLayout()
        knoepfe.addWidget(self.block_hinzu)
        knoepfe.addWidget(self.block_weg)
        knoepfe.addStretch(1)

        self.eigene_breiten = QCheckBox(u("Breiten selbst festlegen"))
        self.eigene_breiten.toggled.connect(self._breiten_geschaltet)

        aufbau = QVBoxLayout(self)
        aufbau.setContentsMargins(0, 0, 0, 0)
        aufbau.addWidget(hinweis)
        aufbau.addWidget(self.fest)
        aufbau.addLayout(self.bloecke)
        aufbau.addLayout(knoepfe)
        aufbau.addWidget(self.eigene_breiten)
        self._aufbauen()

    # -- Zustand -------------------------------------------------------------

    def setzen(self, art: str, schriftfeld, anteile) -> None:
        """Uebernimmt Bauart, Bloecke und Breiten einer Vorlage - ohne Signal."""
        self.art = art
        self._bloecke = [list(block) for block in schriftfeld] or [[]]
        self._breiten = list(anteile)
        self.eigene_breiten.blockSignals(True)
        self.eigene_breiten.setChecked(bool(self._breiten))
        self.eigene_breiten.blockSignals(False)
        self._aufbauen()

    def art_setzen(self, art: str) -> None:
        if art == self.art:
            return
        self._bloecke = self._aus_listen()
        self.art = art
        # Die Breiten gehoeren zur Aufteilung - bei anderer Zahl von Teilen
        # passen sie nicht mehr.
        if len(self._breiten) != self._teile():
            self._breiten = []
            self.eigene_breiten.blockSignals(True)
            self.eigene_breiten.setChecked(False)
            self.eigene_breiten.blockSignals(False)
        self._aufbauen()
        self.geaendert.emit()

    def werte(self) -> tuple[tuple[tuple[str, ...], ...], tuple[float, ...]]:
        """(Bloecke, Breiten) - Breiten leer, wenn das Programm sie waehlt."""
        bloecke = tuple(tuple(block) for block in self._aus_listen())
        if not self.eigene_breiten.isChecked():
            return bloecke, ()
        return bloecke, tuple(round(feld.value(), 3) for feld in self.breiten)

    # -- Bearbeiten ----------------------------------------------------------

    def marke_hinzufuegen(self, block: int, marke: str) -> None:
        self._bloecke = self._aus_listen()
        self._bloecke[block].append(marke)
        self._aufbauen()
        self.geaendert.emit()

    def marke_entfernen(self, block: int, zeile: int) -> None:
        self._bloecke = self._aus_listen()
        if 0 <= zeile < len(self._bloecke[block]):
            del self._bloecke[block][zeile]
            self._aufbauen()
            self.geaendert.emit()

    def block_hinzufuegen(self) -> None:
        self._bloecke = self._aus_listen()
        if len(self._bloecke) >= HOECHSTENS_BLOECKE:
            return
        self._bloecke.append([])
        if self._breiten:
            self._breiten.append(sum(self._breiten) / len(self._breiten))
        self._aufbauen()
        self.geaendert.emit()

    def block_entfernen(self) -> None:
        """Nimmt den letzten Block samt seinen Angaben weg - einer bleibt."""
        self._bloecke = self._aus_listen()
        if len(self._bloecke) <= 1:
            return
        self._bloecke.pop()
        self._breiten = self._breiten[: len(self._bloecke)]
        self._aufbauen()
        self.geaendert.emit()

    # -- Aufbau --------------------------------------------------------------

    def _teile(self) -> int:
        return 2 if self.art == "beispiel" else len(self._bloecke)

    def _aus_listen(self) -> list[list[str]]:
        if self.art != "standard" or not self.listen:
            return [list(block) for block in self._bloecke]
        return [
            [liste.item(zeile).data(Qt.ItemDataRole.UserRole) for zeile in range(liste.count())]
            for liste in self.listen
        ]

    def _leeren(self) -> None:
        while self.bloecke.count():
            eintrag = self.bloecke.takeAt(0)
            alt = eintrag.widget()
            if alt is not None:
                # Sofort weg vom Bildschirm: deleteLater loescht erst, wenn
                # die Ereignisschleife wieder dran ist - bis dahin malte der
                # alte Block unter dem neuen weiter.
                alt.hide()
                alt.setParent(None)
                alt.deleteLater()
        self.listen, self.breiten = [], []

    def _aufbauen(self) -> None:
        self._leeren()
        standard = self.art == "standard"
        teile = self._teile()
        vorgabe = schriftfeldanteile(teile, tuple(self._breiten))
        titel = (
            [u("{0}. Block").format(i + 1) for i in range(teile)] if standard
            else [u("Links"), u("Rechts")]
        )
        for stelle in range(teile):
            spalte = QWidget()
            aufbau = QVBoxLayout(spalte)
            aufbau.setContentsMargins(0, 0, 0, 0)
            aufbau.addWidget(QLabel(titel[stelle]))
            if standard:
                aufbau.addWidget(self._liste(stelle), 1)
                aufbau.addLayout(self._listenknoepfe(stelle))
            breite = QDoubleSpinBox()
            breite.setRange(0.05, 10.0)
            breite.setSingleStep(0.05)
            breite.setDecimals(2)
            breite.setPrefix(u("Breite") + " ")
            breite.setValue(self._breiten[stelle] if len(self._breiten) == teile else vorgabe[stelle])
            breite.setEnabled(self.eigene_breiten.isChecked())
            breite.valueChanged.connect(self._breite_geaendert)
            aufbau.addWidget(breite)
            self.breiten.append(breite)
            self.bloecke.addWidget(spalte, 1)
        self.fest.setVisible(not standard)
        self.hinweis.setVisible(standard)
        self.block_hinzu.setVisible(standard)
        self.block_weg.setVisible(standard)
        self.block_hinzu.setEnabled(len(self._bloecke) < HOECHSTENS_BLOECKE)
        self.block_weg.setEnabled(len(self._bloecke) > 1)

    def _liste(self, block: int) -> QListWidget:
        liste = QListWidget()
        liste.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        liste.setDefaultDropAction(Qt.DropAction.MoveAction)
        liste.setMinimumHeight(110)
        for marke in self._bloecke[block]:
            eintrag = QListWidgetItem(u(MARKENNAMEN.get(marke, marke)))
            eintrag.setData(Qt.ItemDataRole.UserRole, marke)
            liste.addItem(eintrag)
        modell = liste.model()
        for signal in (modell.rowsInserted, modell.rowsRemoved, modell.rowsMoved):
            signal.connect(self._gezogen)
        self.listen.append(liste)
        return liste

    def _listenknoepfe(self, block: int) -> QHBoxLayout:
        dazu = QToolButton()
        dazu.setText("+")
        dazu.setToolTip(u("Eine Angabe hinzufügen"))
        auswahl = QMenu(dazu)
        for marke in SCHRIFTFELDMARKEN:
            handlung = auswahl.addAction(u(MARKENNAMEN.get(marke, marke)))
            handlung.triggered.connect(
                lambda _an=False, b=block, m=marke: self.marke_hinzufuegen(b, m)
            )
        dazu.setMenu(auswahl)
        dazu.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        weg = QToolButton()
        weg.setText("−")
        weg.setToolTip(u("Die gewählte Angabe entfernen"))
        weg.clicked.connect(
            lambda _an=False, b=block: self.marke_entfernen(b, self.listen[b].currentRow())
        )
        knoepfe = QHBoxLayout()
        knoepfe.addWidget(dazu)
        knoepfe.addWidget(weg)
        knoepfe.addStretch(1)
        return knoepfe

    def _gezogen(self, *_args) -> None:
        """Nach dem Ziehen: der Stand steht in den Listen."""
        self._bloecke = self._aus_listen()
        self.geaendert.emit()

    def _breiten_geschaltet(self, an: bool) -> None:
        for feld in self.breiten:
            feld.setEnabled(an)
        self._breiten = [feld.value() for feld in self.breiten] if an else []
        self.geaendert.emit()

    def _breite_geaendert(self, _wert: float) -> None:
        self._breiten = [feld.value() for feld in self.breiten]
        self.geaendert.emit()
