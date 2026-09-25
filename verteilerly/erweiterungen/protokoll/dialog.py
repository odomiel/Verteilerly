"""Das Protokoll ansehen - lesen, leeren, den Ordner oeffnen.

Der Dialog zeigt die Datei, wie sie ist: nur Text, das Neueste unten.
Geaendert wird daran nichts; wer aufraeumen will, leert sie ganz.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...gui.passform import PassenderDialog
from ...gui.sprache import Knopf, frage
from ...sprachen import u


class ProtokollDialog(PassenderDialog):
    """Was das Programm zuletzt gemeldet hat."""

    def __init__(self, protokoll, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.protokoll = protokoll
        self.setWindowTitle(u("Protokoll"))

        self.ort = QLabel(str(protokoll.datei()))
        # Der Pfad laesst sich herauskopieren - wer nachsehen will, muss
        # ihn nicht abtippen.
        self.ort.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.auffrischen_knopf = QPushButton(u("Auffrischen"))
        self.auffrischen_knopf.clicked.connect(self.auffrischen)
        self.ordner_knopf = QPushButton(u("Ordner öffnen"))
        self.ordner_knopf.clicked.connect(self._ordner_oeffnen)
        self.leeren_knopf = QPushButton(u("Protokoll leeren"))
        self.leeren_knopf.clicked.connect(self._leeren)

        knoepfe = QHBoxLayout()
        knoepfe.addWidget(self.auffrischen_knopf)
        knoepfe.addWidget(self.ordner_knopf)
        knoepfe.addWidget(self.leeren_knopf)
        knoepfe.addStretch(1)

        schliessen = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        schliessen.rejected.connect(self.reject)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(self.ort)
        aufbau.addWidget(self.text, 1)
        aufbau.addLayout(knoepfe)
        aufbau.addWidget(schliessen)
        self.resize(900, 520)
        self.auffrischen()

    def auffrischen(self) -> None:
        """Liest die Datei neu - sie waechst, waehrend der Dialog offen ist."""
        inhalt = self.protokoll.schreiber.lesen() if self.protokoll.schreiber else ""
        if not inhalt.strip():
            inhalt = u("Noch nichts protokolliert.")
        fehler = getattr(self.protokoll.schreiber, "letzter_fehler", "")
        if fehler:
            # Ein Protokoll, das sich nicht schreiben laesst, darf nicht
            # stumm bleiben - sonst wartet jemand auf Zeilen, die nie kommen.
            inhalt += "\n" + u("Zuletzt nicht geschrieben: {0}").format(fehler)
        self.text.setPlainText(inhalt)
        self.text.moveCursor(self.text.textCursor().MoveOperation.End)

    def _ordner_oeffnen(self) -> None:
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.protokoll.datei().parent))
        )

    def _leeren(self) -> None:
        antwort = frage(
            self, u("Protokoll"),
            u("Das bisherige Protokoll wird weggeworfen. Fortfahren?"),
            Knopf.Discard | Knopf.Cancel, Knopf.Cancel,
        )
        if antwort != Knopf.Discard:
            return
        if self.protokoll.schreiber is not None:
            self.protokoll.schreiber.leeren()
        self.auffrischen()
