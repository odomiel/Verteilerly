"""Das Schriftfeld im Blattvorlagen-Editor - der Briefkopf am Blattfuss.

Die Bloecke stehen nebeneinander wie auf dem Blatt, darin die Angaben
untereinander. Eintraege lassen sich zwischen den Bloecken ziehen; ``+``
und ``−`` fuegen hinzu und nehmen weg, ``✕`` loescht den ganzen Block.
Hinter jeder Angabe steht ein Knopf fuer ihre **Ausrichtung** - links,
mittig oder rechts; er gilt dem Wert, nicht der Beschriftung. Unter den
Angaben steht auch der **Querstrich**: keine Angabe, sondern ein Strich
quer durch den Block, der trennt, was darueber steht - er hat nichts
auszurichten und traegt darum keinen Knopf.

Die Breiten sind Anteile: ohne Haken bei *Breiten selbst festlegen*
teilt das Programm nach Augenmass.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QPainter, QPen, QPixmap
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

from ...blattvorlagen import SCHRIFTFELDMARKEN, Schriftfeldeintrag
from ...layout import schriftfeldanteile
from ...modell import BLATTBESCHRIFTUNG, LINKS, MITTE, RECHTS
from ...sprachen import u

#: Wie die Angaben im Editor heissen - wie auf dem Blatt. Ein eigenes
#: Feld heisst, wie es heisst, und steht darum nicht in dieser Tabelle.
MARKENNAMEN = {
    **BLATTBESCHRIFTUNG,
    "strich": "Querstrich",
}
#: Wie die Ausrichtungen heissen. Auch die Spaltentabelle des Dialogs
#: nimmt diese Tabelle - eine zweite liefe irgendwann auseinander.
AUSRICHTUNGSNAMEN = {LINKS: "links", MITTE: "mittig", RECHTS: "rechts"}
HOECHSTENS_BLOECKE = 6

#: Woran ein Listeneintrag seine Marke und seine Ausrichtung traegt.
#: Beides reist beim Ziehen mit - Qt gibt alle Rollen eines Eintrags
#: an den neuen Platz weiter.
MARKE = Qt.ItemDataRole.UserRole
AUSRICHTUNG = Qt.ItemDataRole.UserRole + 1


def ausrichtungssymbol(ausrichtung: str, farbe) -> QIcon:
    """Ein Sinnbild der Ausrichtung: vier Striche, so gelegt wie der Text.

    Gezeichnet statt geschrieben: ein Buchstabe waere in jeder Sprache
    ein anderer, das Bild ist ueberall dasselbe.
    """
    kante = 16
    bild = QPixmap(kante, kante)
    bild.fill(Qt.GlobalColor.transparent)
    maler = QPainter(bild)
    maler.setRenderHint(QPainter.RenderHint.Antialiasing)
    maler.setPen(QPen(farbe, 1.6))
    for i, laenge in enumerate((12, 8, 12, 8)):
        if ausrichtung == RECHTS:
            x = kante - 2 - laenge
        elif ausrichtung == MITTE:
            x = (kante - laenge) / 2
        else:
            x = 2
        y = 3.5 + i * 3.0
        maler.drawLine(QPointF(x, y), QPointF(x + laenge, y))
    maler.end()
    return QIcon(bild)


class SchriftfeldEditor(QWidget):
    """Bloecke nebeneinander, darin die Angaben untereinander."""

    geaendert = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bloecke: list[list[Schriftfeldeintrag]] = [[]]
        self._breiten: list[float] = []
        #: Die eigenen Felder dieser Vorlage - sie stehen im Auswahlmenue
        #: neben Firma und Kunde, jedes einzeln platzierbar.
        self._eigene: tuple[str, ...] = ()
        self._symbole: dict[tuple[str, str], QIcon] = {}
        self.listen: list[QListWidget] = []
        self.breiten: list[QDoubleSpinBox] = []

        self.hinweis = hinweis = QLabel(u(
            "Welche Angaben in welchem Block stehen. Einträge lassen sich "
            "zwischen den Blöcken ziehen; der Knopf dahinter richtet den "
            "Wert aus."
        ))
        hinweis.setWordWrap(True)
        # Eine umbrechende Beschriftung meldet im Rollbereich nur eine Zeile
        # Hoehe an - die zweite laege sonst ueber den Bloecken.
        hinweis.setMinimumHeight(hinweis.fontMetrics().lineSpacing() * 3 + 4)
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
        aufbau.addLayout(self.bloecke)
        aufbau.addLayout(knoepfe)
        aufbau.addWidget(self.eigene_breiten)
        self._aufbauen()

    # -- Zustand -------------------------------------------------------------

    def eigene_felder_setzen(self, namen) -> None:
        """Welche eigenen Felder zur Wahl stehen - und was mit den anderen wird.

        Wird ein Feld umbenannt oder entfernt, stehen seine Eintraege im
        Schriftfeld ins Leere: sie werden **mit entfernt**, sonst
        beanstandete die Pruefung eine Marke, die es nicht mehr gibt.
        """
        self._eigene = tuple(namen)
        bekannt = set(SCHRIFTFELDMARKEN) | set(self._eigene)
        vorher = [list(block) for block in self._bloecke]
        self._bloecke = [
            [eintrag for eintrag in block if eintrag.marke in bekannt]
            for block in self._bloecke
        ]
        self._aufbauen()
        if self._bloecke != vorher:
            self.geaendert.emit()

    def setzen(self, schriftfeld, anteile) -> None:
        """Uebernimmt Bloecke und Breiten einer Vorlage - ohne Signal.

        Breiten, die nicht zur Zahl der Bloecke passen, gelten als keine:
        genau so liest das Programm sie aus einer Datei - es teilt dann
        nach Augenmass.
        """
        self._bloecke = [list(block) for block in schriftfeld] or [[]]
        self._breiten = list(anteile) if len(anteile) == len(self._bloecke) else []
        self.eigene_breiten.blockSignals(True)
        self.eigene_breiten.setChecked(bool(self._breiten))
        self.eigene_breiten.blockSignals(False)
        self._aufbauen()

    def werte(self) -> tuple[tuple[tuple[Schriftfeldeintrag, ...], ...], tuple[float, ...]]:
        """(Bloecke, Breiten) - Breiten leer, wenn das Programm sie waehlt."""
        bloecke = tuple(tuple(block) for block in self._aus_listen())
        if not self.eigene_breiten.isChecked():
            return bloecke, ()
        return bloecke, tuple(round(feld.value(), 3) for feld in self.breiten)

    # -- Bearbeiten ----------------------------------------------------------

    def marke_hinzufuegen(self, block: int, marke: str) -> None:
        self._bloecke = self._aus_listen()
        self._bloecke[block].append(Schriftfeldeintrag(marke))
        self._aufbauen()
        self.geaendert.emit()

    def marke_entfernen(self, block: int, zeile: int) -> None:
        self._bloecke = self._aus_listen()
        if 0 <= zeile < len(self._bloecke[block]):
            del self._bloecke[block][zeile]
            self._aufbauen()
            self.geaendert.emit()

    def ausrichten(self, block: int, zeile: int, ausrichtung: str) -> None:
        """Legt fest, wie der Wert dieser Angabe im Block liegt."""
        self._bloecke = self._aus_listen()
        if not 0 <= zeile < len(self._bloecke[block]):
            return
        eintrag = self._bloecke[block][zeile]
        if eintrag.ausrichtung == ausrichtung:
            return
        self._bloecke[block][zeile] = Schriftfeldeintrag(eintrag.marke, ausrichtung)
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
        self.block_loeschen(len(self._aus_listen()) - 1)

    def block_loeschen(self, block: int) -> None:
        """Loescht genau diesen Block samt seinen Angaben - einer bleibt."""
        self._bloecke = self._aus_listen()
        if len(self._bloecke) <= 1 or not 0 <= block < len(self._bloecke):
            return
        del self._bloecke[block]
        if len(self._breiten) > block:
            del self._breiten[block]
        self._aufbauen()
        self.geaendert.emit()

    # -- Aufbau --------------------------------------------------------------

    def _teile(self) -> int:
        return len(self._bloecke)

    def _aus_listen(self) -> list[list[Schriftfeldeintrag]]:
        if not self.listen:
            return [list(block) for block in self._bloecke]
        return [
            [self._eintrag(liste.item(zeile)) for zeile in range(liste.count())]
            for liste in self.listen
        ]

    @staticmethod
    def _eintrag(zeile: QListWidgetItem) -> Schriftfeldeintrag:
        return Schriftfeldeintrag(
            zeile.data(MARKE), zeile.data(AUSRICHTUNG) or LINKS
        )

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
        teile = self._teile()
        vorgabe = schriftfeldanteile(teile, tuple(self._breiten))
        for stelle in range(teile):
            spalte = QWidget()
            aufbau = QVBoxLayout(spalte)
            aufbau.setContentsMargins(0, 0, 0, 0)
            aufbau.addWidget(QLabel(u("{0}. Block").format(stelle + 1)))
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
        self.block_hinzu.setEnabled(len(self._bloecke) < HOECHSTENS_BLOECKE)
        self.block_weg.setEnabled(len(self._bloecke) > 1)

    def _liste(self, block: int) -> QListWidget:
        liste = QListWidget()
        liste.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        liste.setDefaultDropAction(Qt.DropAction.MoveAction)
        liste.setMinimumHeight(110)
        self.listen.append(liste)
        for eintrag in self._bloecke[block]:
            zeile = QListWidgetItem(u(MARKENNAMEN.get(eintrag.marke, eintrag.marke)))
            zeile.setData(MARKE, eintrag.marke)
            zeile.setData(AUSRICHTUNG, eintrag.ausrichtung)
            liste.addItem(zeile)
        self._knoepfe_setzen(liste)
        modell = liste.model()
        for signal in (modell.rowsInserted, modell.rowsRemoved, modell.rowsMoved):
            signal.connect(self._gezogen)
        return liste

    def _symbol(self, ausrichtung: str) -> QIcon:
        farbe = self.palette().buttonText().color()
        schluessel = (ausrichtung, farbe.name())
        if schluessel not in self._symbole:
            self._symbole[schluessel] = ausrichtungssymbol(ausrichtung, farbe)
        return self._symbole[schluessel]

    def _knoepfe_setzen(self, liste: QListWidget) -> None:
        """Gibt jeder Angabe ihren Ausrichtungsknopf.

        Ein gezogener Eintrag ist am neuen Platz ein neuer Eintrag und
        kommt ohne Knopf an - darum wird jede Liste danach durchgesehen.
        """
        block = self.listen.index(liste)
        for stelle in range(liste.count()):
            zeile = liste.item(stelle)
            if zeile.data(MARKE) == "strich" or liste.itemWidget(zeile) is not None:
                continue
            liste.setItemWidget(zeile, self._ausrichtungsknopf(block, zeile))

    def _ausrichtungsknopf(self, block: int, zeile: QListWidgetItem) -> QWidget:
        knopf = QToolButton()
        knopf.setAutoRaise(True)
        knopf.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        knopf.setIcon(self._symbol(zeile.data(AUSRICHTUNG) or LINKS))
        knopf.setToolTip(u("Wie der Wert in seinem Block liegt"))
        auswahl = QMenu(knopf)
        for kennung, name in AUSRICHTUNGSNAMEN.items():
            handlung = auswahl.addAction(self._symbol(kennung), u(name))
            handlung.triggered.connect(
                lambda _an=False, b=block, z=zeile, k=kennung: self.ausrichten(
                    b, self.listen[b].row(z), k
                )
            )
        knopf.setMenu(auswahl)
        huelle = QWidget()
        # Ohne eigenen Hintergrund: der Name des Eintrags steht darunter
        # und soll sichtbar bleiben.
        lage = QHBoxLayout(huelle)
        lage.setContentsMargins(0, 0, 2, 0)
        lage.addStretch(1)
        lage.addWidget(knopf)
        hoehe = max(huelle.sizeHint().height(), knopf.sizeHint().height())
        zeile.setSizeHint(QSize(0, hoehe + 2))
        return huelle

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
        if self._eigene:
            # Die eigenen Felder darunter, mit einem Trenner davor: sie
            # gehoeren dieser Vorlage, nicht dem Programm.
            auswahl.addSeparator()
            for marke in self._eigene:
                handlung = auswahl.addAction(marke)
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
        block_weg = QToolButton()
        block_weg.setText("✕")
        block_weg.setToolTip(u("Diesen Block löschen"))
        block_weg.setEnabled(len(self._bloecke) > 1)
        block_weg.clicked.connect(lambda _an=False, b=block: self.block_loeschen(b))
        knoepfe = QHBoxLayout()
        knoepfe.addWidget(dazu)
        knoepfe.addWidget(weg)
        knoepfe.addStretch(1)
        knoepfe.addWidget(block_weg)
        return knoepfe

    def _gezogen(self, *_args) -> None:
        """Nach dem Ziehen: der Stand steht in den Listen.

        Die Knoepfe kommen erst danach dazu - mitten im Fallenlassen
        haengt Qt noch an seinen Zeilen.
        """
        self._bloecke = self._aus_listen()
        QTimer.singleShot(0, self.knoepfe_auffrischen)
        self.geaendert.emit()

    def knoepfe_auffrischen(self) -> None:
        """Jede Liste durchsehen und fehlende Ausrichtungsknoepfe nachtragen."""
        for liste in self.listen:
            self._knoepfe_setzen(liste)

    def _breiten_geschaltet(self, an: bool) -> None:
        for feld in self.breiten:
            feld.setEnabled(an)
        self._breiten = [feld.value() for feld in self.breiten] if an else []
        self.geaendert.emit()

    def _breite_geaendert(self, _wert: float) -> None:
        self._breiten = [feld.value() for feld in self.breiten]
        self.geaendert.emit()
