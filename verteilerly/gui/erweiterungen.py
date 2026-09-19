"""Was eine Erweiterung vom Fenster sieht - und wo man sie ein- und ausschaltet."""

from __future__ import annotations

import pathlib

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..erweiterungen import Fund, eingeschaltet
from ..sprachen import u
from .passform import PassenderDialog


class Schnittstelle:
    """Das Programm, wie eine Erweiterung es sieht.

    Mit Absicht schmal: was hier steht, bleibt, auch wenn sich das
    Hauptfenster aendert. Wer mehr braucht, kommt ueber ``fenster`` an
    alles - aber ohne Zusage, dass es morgen noch so heisst.
    """

    def __init__(self, fenster, menue, trenner, fund: Fund) -> None:
        self._fenster = fenster
        self._menue = menue
        self._trenner = trenner
        self._fund = fund

    @property
    def fenster(self):
        """Das Hauptfenster - als Eltern fuer Dialoge."""
        return self._fenster

    def menueeintrag(self, text: str, aufruf, hinweis: str = "", kuerzel: str = "") -> QAction:
        """Ein Eintrag im Menue *Erweiterungen*.

        Was der Aufruf an Fehlern wirft, faengt das Programm ab und zeigt
        es - eine Erweiterung soll das Fenster nicht mitnehmen.
        """
        handlung = QAction(text, self._fenster)
        handlung.triggered.connect(lambda _an=False: self._ausfuehren(aufruf))
        if kuerzel:
            handlung.setShortcut(QKeySequence(kuerzel))
        if hinweis:
            handlung.setStatusTip(hinweis)
        handlung.setProperty("erweiterung", self._fund.kennung)
        handlung.setProperty("fremd", not self._fund.eingebaut)
        self._menue.insertAction(self._trenner, handlung)
        return handlung

    def _ausfuehren(self, aufruf) -> None:
        try:
            aufruf()
        except Exception as fehler:  # noqa: BLE001 - Code einer Erweiterung
            QMessageBox.critical(
                self._fenster, u("Erweiterung"),
                u("{0} ist auf einen Fehler gelaufen:\n\n{1}").format(
                    u(self._fund.name), f"{type(fehler).__name__}: {fehler}"
                ),
            )

    def projekt(self):
        """Das offene Projekt - oder None."""
        return self._fenster.projekt

    def blattvorlagen(self):
        """Alle Blattvorlagen, wie sie gerade geladen sind."""
        return self._fenster.blattvorlagen

    def blattvorlage(self):
        """Die Blattvorlage, die Vorschau und Ausgabe gerade benutzen."""
        return self._fenster.vorschau.blattvorlage

    def blattvorlagen_neu_laden(self) -> None:
        """Liest die Blattvorlagen neu ein - nach dem Speichern einer neuen."""
        self._fenster.blattvorlagen_neu_laden()

    def blattvorlagenordner(self) -> pathlib.Path | None:
        """Wohin eigene Blattvorlagen geschrieben werden."""
        return self._fenster._blattvorlagenordner()

    def farben(self):
        """Der Farbsatz des Erscheinungsbilds - fuer eigene Zeichenflaechen."""
        from .thema import SAETZE

        return SAETZE.get(self._fenster.thema_name, SAETZE["hell"])

    def meldung(self, text: str, dauer: int = 8000) -> None:
        """Ein Satz in der Statuszeile."""
        self._fenster.statusBar().showMessage(text, dauer)


class ErweiterungenDialog(PassenderDialog):
    """Erweiterungen ein- und ausschalten.

    Je Erweiterung ein Haken, dazu woher sie kommt und was sie tut - oder
    warum sie nicht geladen werden konnte. Fremde laufen mit allen Rechten
    des Programms; eingeschaltet wird nur, was man kennt. Wirksam wird die
    Wahl beim naechsten Start: Code laesst sich laden, aber nicht sauber
    wieder entladen.
    """

    def __init__(
        self, funde: list[Fund], an, aus, ordner: pathlib.Path | None,
        ohne_fremde: bool = False, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(u("Erweiterungen verwalten"))
        self.funde = funde
        self.ordner = ordner

        hinweis = QLabel(u(
            "Eingebaute Erweiterungen sind eingeschaltet, eigene erst, wenn "
            "Sie sie einschalten. Eine eigene Erweiterung ist Programmcode "
            "und läuft mit allen Rechten von Verteilerly — schalten Sie nur "
            "ein, was Sie kennen. Die Wahl gilt ab dem nächsten Start."
        ))
        hinweis.setWordWrap(True)

        self.liste = QTreeWidget()
        self.liste.setColumnCount(3)
        self.liste.setHeaderLabels([u("Erweiterung"), u("Herkunft"), u("Beschreibung")])
        self.liste.setRootIsDecorated(False)
        self.eintraege: dict[str, QTreeWidgetItem] = {}
        for fund in funde:
            herkunft = u("eingebaut") if fund.eingebaut else fund.ort.name
            text = u(fund.beschreibung) if fund.beschreibung else ""
            if fund.fehler:
                text = u("Nicht geladen: {0}").format(fund.fehler)
            eintrag = QTreeWidgetItem([u(fund.name), herkunft, text])
            eintrag.setFlags(eintrag.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            eintrag.setCheckState(
                0, Qt.CheckState.Checked if eingeschaltet(fund, an, aus)
                else Qt.CheckState.Unchecked
            )
            eintrag.setToolTip(2, text)
            if fund.ort is not None:
                eintrag.setToolTip(1, str(fund.ort))
            self.liste.addTopLevelItem(eintrag)
            self.eintraege[fund.kennung] = eintrag
        for spalte in range(3):
            self.liste.resizeColumnToContents(spalte)

        ortzeile = QHBoxLayout()
        ortzeile.addWidget(QLabel(u("Eigene Erweiterungen liegen in:")))
        pfad = QLabel(str(ordner) if ordner else u("(kein beschreibbarer Ordner)"))
        pfad.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        ortzeile.addWidget(pfad, 1)
        self.ordnerknopf = QPushButton(u("Ordner öffnen"))
        self.ordnerknopf.setEnabled(ordner is not None)
        self.ordnerknopf.clicked.connect(self._ordner_oeffnen)
        ortzeile.addWidget(self.ordnerknopf)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(hinweis)
        if ohne_fremde:
            still = QLabel(u(
                "In diesem Lauf sind eigene Erweiterungen abgeschaltet "
                "(--ohne-fremde-erweiterungen)."
            ))
            still.setWordWrap(True)
            aufbau.addWidget(still)
        aufbau.addWidget(self.liste, 1)
        aufbau.addLayout(ortzeile)
        knoepfe = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        aufbau.addWidget(knoepfe)
        self.resize(720, 360)

    def _ordner_oeffnen(self) -> None:
        if self.ordner is None:
            return
        try:
            self.ordner.mkdir(parents=True, exist_ok=True)
        except OSError as fehler:
            QMessageBox.warning(self, u("Erweiterungen"), str(fehler))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.ordner)))

    def wahl(self) -> tuple[set[str], set[str]]:
        """(eingeschaltete fremde, ausgeschaltete eingebaute)."""
        an, aus = set(), set()
        for fund in self.funde:
            gesetzt = self.eintraege[fund.kennung].checkState(0) == Qt.CheckState.Checked
            if fund.eingebaut and not gesetzt:
                aus.add(fund.kennung)
            elif not fund.eingebaut and gesetzt:
                an.add(fund.kennung)
        return an, aus
