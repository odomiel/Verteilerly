"""Einstellungen der Erweiterung: wo das Werkzeug liegt und wie es laeuft."""

from __future__ import annotations

import pathlib
import sys

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...gui.passform import PassenderDialog
from ...sprachen import u
from .uebergabe import CSV, FRAGEN, PROGRAMMNAME, VTLY, format_lesen, programm_grund

#: Die Wahl im Feld *Übergeben als*, in dieser Reihenfolge.
FORMATWAHL = (
    (CSV, "CSV"),
    (VTLY, "Projektdatei (.vtly)"),
    (FRAGEN, "Jedes Mal fragen"),
)


class EinrichtenDialog(PassenderDialog):
    """Programmort, Format, sofort verarbeiten, eigener Exportordner."""

    def __init__(
        self, programm: str = "", sofort: bool = False, export: str = "",
        parent: QWidget | None = None, art: str = CSV,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(u("CSV2Excel einrichten"))

        hinweis = QLabel(u(
            "Verteilerly_CSV2Excel überträgt einen Verteiler in die passende "
            "Excel-Vorlage. Der Knopf „An CSV2Excel“ in der Werkzeugleiste "
            "schreibt den offenen Verteiler als CSV oder als Projektdatei und "
            "übergibt ihn dem Programm; Projektdateien liest es ab Version "
            "1.2.0. Das Programm gibt es nur für Windows."
        ))
        hinweis.setWordWrap(True)

        self.programmfeld = QLineEdit(programm)
        self.programmfeld.setPlaceholderText(PROGRAMMNAME)
        programmknopf = QPushButton(u("Durchsuchen…"))
        programmknopf.clicked.connect(self._programm_waehlen)
        programmzeile = QHBoxLayout()
        programmzeile.addWidget(self.programmfeld, 1)
        programmzeile.addWidget(programmknopf)

        self.exportfeld = QLineEdit(export)
        self.exportfeld.setPlaceholderText(u("wie in Verteilerly_CSV2Excel eingestellt"))
        exportknopf = QPushButton(u("Durchsuchen…"))
        exportknopf.clicked.connect(self._export_waehlen)
        exportzeile = QHBoxLayout()
        exportzeile.addWidget(self.exportfeld, 1)
        exportzeile.addWidget(exportknopf)

        self.formatwahl = QComboBox()
        for kennung, text in FORMATWAHL:
            self.formatwahl.addItem(u(text), kennung)
        self.formatwahl.setCurrentIndex(
            self.formatwahl.findData(format_lesen(art))
        )

        self.sofort_haken = QCheckBox(u("Gleich verarbeiten, ohne auf „Start“ zu warten"))
        self.sofort_haken.setChecked(sofort)

        formular = QFormLayout()
        formular.addRow(u("Programm:"), programmzeile)
        formular.addRow(u("Übergeben als:"), self.formatwahl)
        formular.addRow(u("Exportordner:"), exportzeile)
        formular.addRow("", self.sofort_haken)

        knoepfe = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        knoepfe.accepted.connect(self._annehmen)
        knoepfe.rejected.connect(self.reject)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(hinweis)
        aufbau.addLayout(formular)
        aufbau.addStretch(1)
        aufbau.addWidget(knoepfe)
        self.resize(560, 220)

    @staticmethod
    def _startordner(text: str) -> str:
        ort = pathlib.Path(text) if text else None
        if ort is not None and ort.exists():
            return str(ort if ort.is_dir() else ort.parent)
        return str(pathlib.Path.home())

    def _programm_waehlen(self) -> None:
        filter_ = u("Programme (*.exe)") if sys.platform == "win32" else u(
            "Programme (*.exe);;Alle Dateien (*)"
        )
        name, _ = QFileDialog.getOpenFileName(
            self, u("Verteilerly_CSV2Excel wählen"),
            self._startordner(self.programmfeld.text()), filter_,
        )
        if name:
            self.programmfeld.setText(str(pathlib.Path(name)))

    def _export_waehlen(self) -> None:
        name = QFileDialog.getExistingDirectory(
            self, u("Exportordner wählen"), self._startordner(self.exportfeld.text())
        )
        if name:
            self.exportfeld.setText(str(pathlib.Path(name)))

    def _annehmen(self) -> None:
        # Leer darf es bleiben - dann fragt der Knopf beim ersten Druck.
        grund = programm_grund(self.programm()) if self.programm() else ""
        if grund:
            QMessageBox.warning(self, u("CSV2Excel einrichten"), grund)
            return
        self.accept()

    def programm(self) -> str:
        return self.programmfeld.text().strip()

    def export(self) -> str:
        return self.exportfeld.text().strip()

    def format(self) -> str:
        return self.formatwahl.currentData()

    def sofort(self) -> bool:
        return self.sofort_haken.isChecked()
