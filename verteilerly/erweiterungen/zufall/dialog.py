"""Der Dialog des Zufallsverteilers: welche Verteilervorlage."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QWidget,
)

from ...gui.passform import PassenderDialog
from ...sprachen import u


class ZufallsDialog(PassenderDialog):
    """Nur die Vorlage ist zu waehlen - der Rest ist Zufall.

    Vorgewaehlt ist die zuletzt genommene, sonst die Standardvorlage.
    """

    def __init__(self, vorlagen, gewaehlt: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(u("Zufallsverteiler"))
        self.vorlagenwahl = QComboBox()
        standard = 0
        for vorlage in vorlagen.alle:
            self.vorlagenwahl.addItem(
                u("{0} ({1} DA)").format(vorlage.name, vorlage.da_gesamt), vorlage.id
            )
            if vorlage.beschreibung:
                self.vorlagenwahl.setItemData(
                    self.vorlagenwahl.count() - 1, vorlage.beschreibung,
                    Qt.ItemDataRole.ToolTipRole,
                )
            if vorlage.standard:
                standard = self.vorlagenwahl.count() - 1
        stelle = self.vorlagenwahl.findData(gewaehlt) if gewaehlt else -1
        self.vorlagenwahl.setCurrentIndex(stelle if stelle >= 0 else standard)

        erklaerung = QLabel(
            u("Kabel, Adernfarben, Bezeichnungen, Rangierungen und Projektdaten "
              "werden ausgewürfelt. Es entsteht ein neuer, ungespeicherter Verteiler.")
        )
        erklaerung.setWordWrap(True)

        knoepfe = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        knoepfe.button(QDialogButtonBox.StandardButton.Ok).setText(u("Würfeln"))
        knoepfe.button(QDialogButtonBox.StandardButton.Cancel).setText(
            u("Abbrechen")
        )
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)

        aufbau = QFormLayout(self)
        aufbau.addRow(erklaerung)
        aufbau.addRow(u("Verteilervorlage:"), self.vorlagenwahl)
        aufbau.addRow(knoepfe)

    def vorlage(self) -> str:
        """Die Kennung der gewaehlten Verteilervorlage."""
        return self.vorlagenwahl.currentData() or ""
