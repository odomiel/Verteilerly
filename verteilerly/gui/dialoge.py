"""Dialoge: neuer Verteiler, Kabel anlegen, Überlauf, Projektdaten.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import paket
from ..blattvorlagen import Blattvorlagen
from ..farbcodes import Kabeltypen
from ..modell import (
    BRIEFKOPF_BESCHRIFTUNG,
    BRIEFKOPF_FELDER,
    Kabel,
    Projekt,
    Verteiler,
)
from ..vorlagen import Vorlage, VorlagenFehler, Vorlagen, vorlage_speichern
from .sprache import frage


# Die gebraeuchlichen Leistengroessen; alles andere wird eingetippt.
DA_VORGABEN = (8, 10, 20)

# Felder, in denen eine Anschrift steht - die gehoert untereinander, so
# wie in den Mustertabellen.
ADRESSFELDER = ("firma", "kunde")
# So viele Zeilen zeigt ein Adressfeld ohne Rollen: Name, Strasse, Ort.
ADRESSZEILEN = 3


def _knopfleiste(dialog: QDialog) -> QDialogButtonBox:
    knoepfe = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    knoepfe.button(QDialogButtonBox.StandardButton.Ok).setText("Übernehmen")
    knoepfe.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
    knoepfe.accepted.connect(dialog.accept)
    knoepfe.rejected.connect(dialog.reject)
    return knoepfe


def als_vorlage_speichern(
    parent: QWidget,
    verteiler: Verteiler,
    vorlagen: Vorlagen,
    ordner,
    vorschlag: str = "",
    beschreibung: str = "",
) -> Vorlage | None:
    """Fragt nach einem Namen und legt die Geometrie als Vorlage ab.

    Gibt die gespeicherte Vorlage zurueck oder None, wenn abgebrochen
    wurde oder etwas nicht ging.
    """
    if ordner is None:
        return None
    try:
        Vorlage.aus_verteiler(verteiler, "Probe")
    except VorlagenFehler as fehler:
        QMessageBox.warning(parent, "Nicht als Vorlage geeignet", str(fehler))
        return None

    name, gewaehlt = QInputDialog.getText(
        parent, "Als Vorlage speichern", "Name der Vorlage:", text=vorschlag
    )
    if not gewaehlt or not name.strip():
        return None

    vorlage = Vorlage.aus_verteiler(verteiler, name.strip(), beschreibung=beschreibung)
    ueberschreiben = False
    if vorlage.id in vorlagen:
        antwort = frage(
            parent,
            "Vorlage überschreiben?",
            f"Es gibt schon eine Vorlage „{vorlagen.holen(vorlage.id).name}“. "
            "Soll sie ersetzt werden?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if antwort != QMessageBox.StandardButton.Yes:
            return None
        ueberschreiben = True

    try:
        ziel = vorlage_speichern(vorlage, ordner, ueberschreiben)
    except VorlagenFehler as fehler:
        QMessageBox.warning(parent, "Vorlage nicht gespeichert", str(fehler))
        return None

    vorlagen.aufnehmen(vorlage)
    QMessageBox.information(parent, "Vorlage gespeichert", f"{vorlage.name}\n{ziel}")
    return vorlage


class NeuerVerteilerDialog(QDialog):
    """Vorlage wählen oder eigene Geometrie angeben."""

    def __init__(
        self,
        vorlagen: Vorlagen,
        parent: QWidget | None = None,
        vorlagenordner=None,
        briefkopf: dict[str, str] | None = None,
        ausgeblendet: set[str] | None = None,
        blattvorlagen: Blattvorlagen | None = None,
        blattvorlage: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Neuer Verteiler")
        self.vorlagen = vorlagen
        self.vorlagenordner = vorlagenordner

        self.name = QLineEdit()
        self.name.setPlaceholderText("z. B. Verteiler Keller")
        self.nummer = QLineEdit()
        self.nummer.setPlaceholderText("z. B. 1.1")

        # Wie das Blatt aussieht, wird gleich hier gewaehlt - und bleibt
        # unter Einstellungen aenderbar.
        self.blattvorlagen = blattvorlagen or Blattvorlagen()
        self.blattvorlagenwahl = QComboBox()
        self.blattvorlagenwahl.setToolTip(
            "Spalten, Schriftgrößen und Ränder der Blätter. "
            "Später unter Einstellungen ▸ Blattvorlage zu ändern."
        )
        for vorlage in self.blattvorlagen.alle:
            self.blattvorlagenwahl.addItem(vorlage.name, vorlage.id)
            if vorlage.beschreibung:
                self.blattvorlagenwahl.setItemData(
                    self.blattvorlagenwahl.count() - 1,
                    vorlage.beschreibung,
                    Qt.ItemDataRole.ToolTipRole,
                )
        stelle = self.blattvorlagenwahl.findData(
            blattvorlage or self.blattvorlagen.standard.id
        )
        self.blattvorlagenwahl.setCurrentIndex(max(stelle, 0))

        stammdaten = QFormLayout()
        stammdaten.addRow("Verteilername:", self.name)
        stammdaten.addRow("Verteilernummer:", self.nummer)
        stammdaten.addRow("Blattvorlage:", self.blattvorlagenwahl)

        # Vorlage
        self.aus_vorlage = QRadioButton("Aus Vorlage")
        self.aus_vorlage.setChecked(True)
        self.vorlagenwahl = QComboBox()
        for vorlage in vorlagen.alle:
            self.vorlagenwahl.addItem(str(vorlage), vorlage.id)
        stelle = self.vorlagenwahl.findData(vorlagen.standard.id)
        if stelle >= 0:
            self.vorlagenwahl.setCurrentIndex(stelle)
        self.vorlagenwahl.currentIndexChanged.connect(self._beschreibung_zeigen)
        self.beschreibung = QLabel()
        self.beschreibung.setWordWrap(True)

        vorlagenblock = QVBoxLayout()
        vorlagenblock.addWidget(self.vorlagenwahl)
        vorlagenblock.addWidget(self.beschreibung)
        vorlagenkasten = QGroupBox()
        vorlagenkasten.setLayout(vorlagenblock)

        # Eigene Geometrie
        self.eigen = QRadioButton("Benutzerdefiniert")
        self.buchten = QSpinBox()
        self.buchten.setRange(1, 20)
        self.leisten = QSpinBox()
        self.leisten.setRange(1, 60)
        self.leisten.setValue(4)
        self.dawahl = QComboBox()
        for anzahl in DA_VORGABEN:
            self.dawahl.addItem(f"{anzahl} DA", anzahl)
        self.dawahl.addItem("Benutzerdefiniert", 0)
        self.dawahl.setCurrentIndex(DA_VORGABEN.index(10))
        self.dawahl.currentIndexChanged.connect(self._da_wahl_gewechselt)

        self.da = QSpinBox()
        self.da.setRange(1, 100)
        self.da.setValue(10)
        self.da.setSuffix(" DA")
        self.da.setVisible(False)

        dazeile = QHBoxLayout()
        dazeile.setContentsMargins(0, 0, 0, 0)
        dazeile.addWidget(self.dawahl)
        dazeile.addWidget(self.da)
        dablock = QWidget()
        dablock.setLayout(dazeile)

        for feld in (self.buchten, self.leisten, self.da):
            feld.valueChanged.connect(self._summe_zeigen)
        self.summe = QLabel()

        self.als_vorlage = QPushButton("Als Vorlage speichern…")
        self.als_vorlage.setToolTip(
            "Legt diese Geometrie als Vorlage ab, damit sie beim nächsten "
            "Verteiler oben zur Wahl steht."
        )
        self.als_vorlage.clicked.connect(self.vorlage_ablegen)
        self.als_vorlage.setEnabled(vorlagenordner is not None)

        eigenform = QFormLayout()
        eigenform.addRow("Buchten:", self.buchten)
        eigenform.addRow("Leisten je Bucht:", self.leisten)
        eigenform.addRow("DA je Leiste:", dablock)
        eigenform.addRow("", self.summe)
        eigenform.addRow("", self.als_vorlage)
        eigenkasten = QGroupBox()
        eigenkasten.setLayout(eigenform)

        self.aus_vorlage.toggled.connect(vorlagenkasten.setEnabled)
        self.aus_vorlage.toggled.connect(lambda an: eigenkasten.setEnabled(not an))
        eigenkasten.setEnabled(False)

        # Die Projektdaten gleich mit: was in der Verteilerly.conf gemerkt
        # ist, steht schon drin und lässt sich hier für diesen Verteiler
        # ändern. Er sitzt in einem Rollbereich, sonst wäre der
        # Dialog höher als mancher Bildschirm.
        self.projektdaten = ProjektdatenFelder(
            briefkopf, ausgeblendet,
            "Projektdaten — stehen auf jedem Blatt, später änderbar",
        )
        rollbereich = QScrollArea()
        rollbereich.setWidget(self.projektdaten)
        rollbereich.setWidgetResizable(True)
        rollbereich.setFrameShape(QScrollArea.Shape.NoFrame)
        rollbereich.setMinimumHeight(220)

        # Die Projektdaten stehen neben dem Verteiler, nicht darunter: so
        # bleibt der Dialog flach genug für einen Bildschirm, und beides
        # ist auf einen Blick zu sehen.
        links = QVBoxLayout()
        links.setContentsMargins(0, 0, 0, 0)
        links.addLayout(stammdaten)
        links.addSpacing(6)
        links.addWidget(self.aus_vorlage)
        links.addWidget(vorlagenkasten)
        links.addWidget(self.eigen)
        links.addWidget(eigenkasten)
        links.addStretch(1)

        nebeneinander = QHBoxLayout()
        nebeneinander.setContentsMargins(0, 0, 0, 0)
        nebeneinander.addLayout(links, 4)
        nebeneinander.addWidget(rollbereich, 5)

        aufbau = QVBoxLayout(self)
        aufbau.addLayout(nebeneinander, 1)
        aufbau.addWidget(_knopfleiste(self))
        self.resize(1000, 620)

        self._beschreibung_zeigen()
        self._summe_zeigen()

    def _beschreibung_zeigen(self) -> None:
        kennung = self.vorlagenwahl.currentData()
        if kennung:
            vorlage = self.vorlagen.holen(kennung)
            self.beschreibung.setText(
                f"{vorlage.beschreibung}\n"
                f"{vorlage.leisten_gesamt} Leisten, {vorlage.da_gesamt} DA"
            )

    def _da_wahl_gewechselt(self) -> None:
        """„Benutzerdefiniert“ blendet das Zahlenfeld ein."""
        eigen = not self.dawahl.currentData()
        self.da.setVisible(eigen)
        if not eigen:
            self.da.setValue(self.dawahl.currentData())
        self._summe_zeigen()

    def da_je_leiste(self) -> int:
        return self.dawahl.currentData() or self.da.value()

    def _summe_zeigen(self) -> None:
        gesamt = self.buchten.value() * self.leisten.value() * self.da_je_leiste()
        leisten = self.buchten.value() * self.leisten.value()
        self.summe.setText(f"ergibt {leisten} Leisten, {gesamt} DA")

    def vorlage_ablegen(self) -> None:
        """Sichert die eingestellte Geometrie als Vorlage."""
        da = self.da_je_leiste()
        vorlage = als_vorlage_speichern(
            self,
            self.geometrie(),
            self.vorlagen,
            self.vorlagenordner,
            vorschlag=(
                f"{self.buchten.value() * self.leisten.value() * da} DA - "
                f"{self.leisten.value()} Leisten zu {da} DA"
            ),
            beschreibung=(
                f"{self.buchten.value()} Buchten zu je {self.leisten.value()} "
                f"Leisten mit {da} Doppeladern."
            ),
        )
        if vorlage is not None:
            self._vorlagenliste_auffrischen(vorlage.id)

    def _vorlagenliste_auffrischen(self, auswahl: str) -> None:
        self.vorlagenwahl.blockSignals(True)
        self.vorlagenwahl.clear()
        for vorlage in self.vorlagen.alle:
            self.vorlagenwahl.addItem(str(vorlage), vorlage.id)
        stelle = self.vorlagenwahl.findData(auswahl)
        if stelle >= 0:
            self.vorlagenwahl.setCurrentIndex(stelle)
        self.vorlagenwahl.blockSignals(False)
        self._beschreibung_zeigen()

    def geometrie(self, name: str = "", nummer: str = "") -> Verteiler:
        """Der Verteiler aus den eigenen Angaben, ohne Vorlage."""
        return Verteiler.aus_geometrie(
            self.buchten.value(), self.leisten.value(), self.da_je_leiste(),
            name, nummer,
        )

    def verteiler(self) -> Verteiler:
        name, nummer = self.name.text().strip(), self.nummer.text().strip()
        if self.aus_vorlage.isChecked():
            return self.vorlagen.holen(self.vorlagenwahl.currentData()).verteiler(
                name, nummer
            )
        return self.geometrie(name, nummer)

    def blattvorlage(self) -> str:
        """Die Kennung der gewaehlten Blattvorlage."""
        return self.blattvorlagenwahl.currentData() or ""

    def projekt(self) -> Projekt:
        """Der neue Verteiler samt den hier eingetippten Projektdaten."""
        return Projekt(
            verteiler=self.verteiler(),
            briefkopf=self.projektdaten.werte(),
            ausgeblendet=self.projektdaten.ausgeblendet(),
        )


class PaketDialog(QDialog):
    """Was gesichert oder eingespielt werden soll.

    Je Teil ein Haken mit der Zahl der Dateien dahinter. Was es nicht
    gibt, ist abgehakt und nicht anzuhaken - ein Paket ohne Kabeltypen
    kann keine mitbringen.
    """

    def __init__(
        self,
        titel: str,
        bestand: dict,
        parent: QWidget | None = None,
        hinweis: str = "",
        knopf: str = "Übernehmen",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(titel)

        self.haken: dict[str, QCheckBox] = {}
        felder = QVBoxLayout()
        for teil in paket.TEILE:
            anzahl = int(bestand.get(teil, 0))
            beschriftung = paket.BESCHRIFTUNG[teil]
            if teil != paket.EINSTELLUNGEN:
                beschriftung += f" ({anzahl})"
            haken = QCheckBox(beschriftung)
            haken.setChecked(bool(anzahl))
            haken.setEnabled(bool(anzahl))
            if not anzahl:
                haken.setToolTip("Ist nicht vorhanden")
            self.haken[teil] = haken
            felder.addWidget(haken)

        kasten = QGroupBox("Teile")
        kasten.setLayout(felder)

        aufbau = QVBoxLayout(self)
        if hinweis:
            zeile = QLabel(hinweis)
            zeile.setWordWrap(True)
            aufbau.addWidget(zeile)
        aufbau.addWidget(kasten)
        knoepfe = _knopfleiste(self)
        knoepfe.button(QDialogButtonBox.StandardButton.Ok).setText(knopf)
        self.knoepfe = knoepfe
        aufbau.addWidget(knoepfe)
        for haken in self.haken.values():
            haken.toggled.connect(self._knopf_auffrischen)
        self._knopf_auffrischen()
        self.resize(380, 260)

    def _knopf_auffrischen(self) -> None:
        """Ohne einen einzigen Haken gibt es nichts zu tun."""
        self.knoepfe.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            bool(self.auswahl())
        )

    def auswahl(self) -> set[str]:
        return {teil for teil, haken in self.haken.items() if haken.isChecked()}


class BlattvorlagenDialog(QDialog):
    """Welche Blattvorlage die Ausgabe benutzt.

    Die Wahl gehoert nicht zu einem einzelnen Verteiler, sondern zum
    Arbeitsplatz: sie steht in der Verteilerly.conf und gilt fuer
    Vorschau, PDF und die Excel-Mappe.
    """

    def __init__(
        self,
        vorlagen: Blattvorlagen,
        gewaehlt: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Blattvorlage")
        self.vorlagen = vorlagen

        self.liste = QListWidget()
        for vorlage in vorlagen.alle:
            eintrag = QListWidgetItem(vorlage.name)
            eintrag.setData(Qt.ItemDataRole.UserRole, vorlage.id)
            if vorlage.beschreibung:
                eintrag.setToolTip(vorlage.beschreibung)
            self.liste.addItem(eintrag)
        stelle = max(
            (i for i in range(self.liste.count())
             if self.liste.item(i).data(Qt.ItemDataRole.UserRole)
             == (gewaehlt or vorlagen.standard.id)),
            default=0,
        )
        self.liste.setCurrentRow(stelle)
        self.liste.currentRowChanged.connect(self._beschreibung_zeigen)
        self.liste.itemDoubleClicked.connect(lambda _: self.accept())

        self.beschreibung = QLabel()
        self.beschreibung.setWordWrap(True)
        self.beschreibung.setMinimumHeight(48)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(QLabel("Wie das Blatt aussieht — Spalten, Schriftgrößen, "
                                "Ränder:"))
        aufbau.addWidget(self.liste, 1)
        aufbau.addWidget(self.beschreibung)
        aufbau.addWidget(_knopfleiste(self))
        self.resize(420, 340)
        self._beschreibung_zeigen()

    def _beschreibung_zeigen(self) -> None:
        vorlage = self.vorlagen.holen(self.gewaehlt())
        teile = [vorlage.beschreibung] if vorlage.beschreibung else []
        teile.append(
            ", ".join(spalte.feld for spalte in vorlage.spalten)
        )
        self.beschreibung.setText("\n".join(teile))

    def gewaehlt(self) -> str:
        eintrag = self.liste.currentItem()
        return eintrag.data(Qt.ItemDataRole.UserRole) if eintrag else ""


class KabelDialog(QDialog):
    """Ein Kabel auflegen oder ein aufgelegtes bearbeiten.

    Beim Bearbeiten liegt das Kabel schon: Leiste, Startpunkt und die Zahl
    der aufgelegten Doppeladern stehen dann fest und werden nur gezeigt -
    wer daran etwas aendern will, nimmt das Kabel ab und legt es neu auf.
    Aenderbar ist, was keine Belegung verschiebt: Beschriftung, Kabeltyp
    und die Kabelgroesse, an der nur die Kuerzung haengt.
    """

    def __init__(
        self,
        verteiler: Verteiler,
        kabeltypen: Kabeltypen,
        leiste: int,
        start_da: int,
        parent: QWidget | None = None,
        kabel: Kabel | None = None,
    ) -> None:
        super().__init__(parent)
        self.bearbeitet = kabel
        self.entfernen = False
        self.setWindowTitle("Kabel bearbeiten" if kabel else "Kabel auflegen")
        self.verteiler = verteiler

        self.beschriftung = QLineEdit()
        self.beschriftung.setPlaceholderText("z. B. 4DA Leitung zu Wohnzimmer")

        self.leiste = QComboBox()
        for l in verteiler.alle_leisten:
            self.leiste.addItem(f"Leiste {l.nummer}  ({l.da_anzahl} DA)", l.nummer)
        stelle = self.leiste.findData(leiste)
        if stelle >= 0:
            self.leiste.setCurrentIndex(stelle)

        self.start = QSpinBox()
        self.start.setRange(1, 100)
        self.start.setValue(start_da)

        self.kabel_da = QSpinBox()
        self.kabel_da.setRange(1, 200)
        self.kabel_da.setValue(4)
        self.kabel_da.setSuffix(" DA")

        self.auflegen_da = QSpinBox()
        self.auflegen_da.setRange(1, 200)
        self.auflegen_da.setValue(4)
        self.auflegen_da.setSuffix(" DA")
        self.kabel_da.valueChanged.connect(self._kabelgroesse_geaendert)

        self.kabeltyp = QComboBox()
        self.kabeltyp.addItem("— ohne, Farben von Hand —", None)
        for typ in kabeltypen.alle:
            self.kabeltyp.addItem(typ.name, typ.id)

        self.kuerzungshinweis = QLabel()
        self.kuerzungshinweis.setWordWrap(True)
        self.auflegen_da.valueChanged.connect(self._kuerzung_zeigen)

        self.farben_neu = QCheckBox("Adernfarben nach diesem Kabeltyp neu eintragen")
        self.farben_neu.setToolTip(
            "Überschreibt auch von Hand gesetzte Farben dieses Kabels"
        )

        form = QFormLayout()
        form.addRow("Beschriftung:", self.beschriftung)
        form.addRow("Leiste:", self.leiste)
        form.addRow("Ab Doppelader:", self.start)
        form.addRow("Kabelgröße:", self.kabel_da)
        form.addRow("Davon auflegen:", self.auflegen_da)
        form.addRow("Kabeltyp:", self.kabeltyp)
        form.addRow("", self.farben_neu)
        form.addRow("", self.kuerzungshinweis)

        aufbau = QVBoxLayout(self)
        aufbau.addLayout(form)
        aufbau.addWidget(self._knoepfe())
        self.farben_neu.setVisible(kabel is not None)
        if kabel is not None:
            self._vorbelegen(kabel)
        self._kuerzung_zeigen()

    def _vorbelegen(self, kabel: Kabel) -> None:
        """Zeigt das aufgelegte Kabel; die Lage steht fest."""
        self.beschriftung.setText(kabel.beschriftung)
        abschnitt = kabel.abschnitte[0]
        stelle = self.leiste.findData(abschnitt.leiste)
        if stelle >= 0:
            self.leiste.setCurrentIndex(stelle)
        self.start.setValue(abschnitt.start_da)
        self.auflegen_da.setValue(kabel.da_aufgelegt)
        self.kabel_da.setMinimum(kabel.da_aufgelegt)
        self.kabel_da.setValue(kabel.da_gesamt)
        stelle = self.kabeltyp.findData(kabel.kabeltyp)
        self.kabeltyp.setCurrentIndex(max(stelle, 0))

        for feld in (self.leiste, self.start, self.auflegen_da):
            feld.setEnabled(False)
            feld.setToolTip(
                "Steht fest — für eine andere Lage das Kabel abnehmen "
                "und neu auflegen"
            )
        if len(kabel.abschnitte) > 1:
            self.leiste.setToolTip(
                f"Das Kabel läuft über {len(kabel.abschnitte)} Abschnitte"
            )

    def _knoepfe(self) -> QDialogButtonBox:
        knoepfe = _knopfleiste(self)
        if self.bearbeitet is not None:
            weg = knoepfe.addButton(
                "Kabel entfernen", QDialogButtonBox.ButtonRole.DestructiveRole
            )
            weg.clicked.connect(self._entfernen)
        return knoepfe

    def _entfernen(self) -> None:
        self.entfernen = True
        self.accept()

    def _kabelgroesse_geaendert(self, wert: int) -> None:
        if self.auflegen_da.value() > wert:
            self.auflegen_da.setValue(wert)
        self.auflegen_da.setMaximum(wert)
        self._kuerzung_zeigen()

    def _kuerzung_zeigen(self) -> None:
        rest = self.kabel_da.value() - self.auflegen_da.value()
        if rest > 0:
            self.kuerzungshinweis.setText(
                f"Das Kabel wird gekürzt: {rest} DA bleiben unaufgelegt."
            )
        else:
            self.kuerzungshinweis.setText("")

    def angaben(self) -> dict:
        return {
            "beschriftung": self.beschriftung.text().strip(),
            "leiste": self.leiste.currentData(),
            "start_da": self.start.value(),
            "anzahl_da": self.auflegen_da.value(),
            "da_gesamt": self.kabel_da.value(),
            "kabeltyp": self.kabeltyp.currentData(),
            "farben_neu": self.farben_neu.isChecked(),
            "entfernen": self.entfernen,
        }


class UeberlaufDialog(QDialog):
    """Was mit dem Rest geschieht, wenn ein Kabel nicht ganz passt."""

    FORTSETZEN = "fortsetzen"
    VERFAELLT = "verfaellt"

    def __init__(
        self,
        verteiler: Verteiler,
        passend: int,
        rest: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Kabel passt nicht vollständig")

        erklaerung = QLabel(
            f"Von diesem Kabel passen {passend} DA auf die gewählte Leiste, "
            f"{rest} DA bleiben übrig."
        )
        erklaerung.setWordWrap(True)

        self.fortsetzen = QRadioButton("Auf einer anderen Leiste fortsetzen")
        self.fortsetzen.setChecked(True)
        self.verfaellt = QRadioButton(f"Rest verfällt — nur {passend} DA auflegen")

        self.leiste = QComboBox()
        for l in verteiler.alle_leisten:
            self.leiste.addItem(f"Leiste {l.nummer}  ({l.da_anzahl} DA)", l.nummer)
        self.start = QSpinBox()
        self.start.setRange(1, 100)
        self.start.setValue(1)

        fortsetzung = QFormLayout()
        fortsetzung.addRow("Weiter auf:", self.leiste)
        fortsetzung.addRow("Ab Doppelader:", self.start)
        kasten = QGroupBox()
        kasten.setLayout(fortsetzung)
        self.fortsetzen.toggled.connect(kasten.setEnabled)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(erklaerung)
        aufbau.addSpacing(6)
        aufbau.addWidget(self.fortsetzen)
        aufbau.addWidget(kasten)
        aufbau.addWidget(self.verfaellt)
        aufbau.addWidget(_knopfleiste(self))

    def entscheidung(self) -> tuple[str, int, int]:
        if self.verfaellt.isChecked():
            return self.VERFAELLT, 0, 0
        return self.FORTSETZEN, self.leiste.currentData(), self.start.value()


class ProjektdatenFelder(QGroupBox):
    """Die Projektdatenfelder mit ihren Haken - in beiden Dialogen dasselbe.

    Jedes Feld traegt einen Haken davor: abgewaehlte Felder erscheinen
    auf keinem Blatt, behalten ihren Inhalt aber. Firma und Kunde
    sind mehrzeilig, denn dort steht eine Anschrift.
    """

    def __init__(
        self,
        briefkopf: dict[str, str] | None = None,
        ausgeblendet: set[str] | None = None,
        titel: str = "Projektdaten — stehen auf jedem Blatt",
        parent: QWidget | None = None,
        inhalt_hakt_an: bool = True,
    ) -> None:
        super().__init__(titel, parent)
        briefkopf = briefkopf or {}
        ausgeblendet = ausgeblendet or set()
        # Was ausgefuellt wird, erscheint auch: wer in ein Feld schreibt,
        # meint es auch. Abwaehlen bleibt moeglich - der Haken
        # folgt dem Tippen, nicht dem Loeschen.
        self.inhalt_hakt_an = inhalt_hakt_an

        self.felder: dict[str, QWidget] = {}
        self.haken: dict[str, QCheckBox] = {}
        form = QFormLayout()
        for name in BRIEFKOPF_FELDER:
            feld = self._feld_bauen(name, briefkopf.get(name, ""))
            haken = QCheckBox(BRIEFKOPF_BESCHRIFTUNG.get(name, name) + ":")
            haken.setChecked(name not in ausgeblendet)
            haken.setToolTip(
                "Ohne Haken bleibt der Inhalt erhalten, erscheint aber auf "
                "keinem Blatt."
            )
            # Der Haken ist zugleich die Beschriftung der Zeile. Er sperrt
            # das Feld nicht: seit leere Felder abgewaehlt sind, liesse
            # sich sonst gerade dort nichts eintragen, wo etwas fehlt.
            if inhalt_hakt_an:
                self._mithaken(feld, haken)
            self.felder[name] = feld
            self.haken[name] = haken
            form.addRow(haken, feld)

        alle_an = QPushButton("Alle")
        alle_an.clicked.connect(lambda: self.alle_haken(True))
        alle_aus = QPushButton("Keine")
        alle_aus.clicked.connect(lambda: self.alle_haken(False))
        schnell = QHBoxLayout()
        schnell.addWidget(QLabel("Auswahl:"))
        schnell.addWidget(alle_an)
        schnell.addWidget(alle_aus)
        schnell.addStretch(1)

        aufbau = QVBoxLayout()
        aufbau.addLayout(form)
        aufbau.addLayout(schnell)
        self.setLayout(aufbau)

    def _mithaken(self, feld: QWidget, haken: QCheckBox) -> None:
        """Was ausgefuellt wird, hakt sich selbst an - Leeren nicht ab.

        Sonst tippte man einen Kunden ein und faende ihn auf keinem Blatt
        wieder, weil der Haken davor noch aus war.
        """
        def gefuellt() -> None:
            if not haken.isChecked() and self._feldwert(feld):
                haken.setChecked(True)

        if isinstance(feld, QPlainTextEdit):
            feld.textChanged.connect(gefuellt)
        else:
            feld.textEdited.connect(lambda _text: gefuellt())

    def _feld_bauen(self, name: str, wert: str) -> QWidget:
        """Adressfelder brauchen mehrere Zeilen, alles andere eine."""
        if name not in ADRESSFELDER:
            return QLineEdit(wert)
        feld = QPlainTextEdit(wert)
        feld.setToolTip(
            "Mehrzeilig: Firma, Straße, Ort — so steht die Anschrift auch "
            "auf dem Blatt untereinander."
        )
        feld.setPlaceholderText("Firma Beliebig\nBeliebige Straße 7\n77777 Ort")
        # Drei Zeilen sind die uebliche Anschrift - und sie sollen ganz zu
        # sehen sein, ohne Rollbalken. Rahmen und Innenabstand zaehlen mit,
        # sonst wird die dritte Zeile angeschnitten.
        rahmen = 2 * feld.frameWidth()
        polster = 2 * int(feld.document().documentMargin())
        zeile = QFontMetrics(feld.font()).lineSpacing()
        feld.setFixedHeight(rahmen + polster + ADRESSZEILEN * zeile + 2)
        return feld

    def alle_haken(self, an: bool) -> None:
        for haken in self.haken.values():
            haken.setChecked(an)

    def werte(self) -> dict[str, str]:
        """Die ausgefuellten Felder - leere bleiben weg."""
        gefuellt = {name: self._feldwert(feld) for name, feld in self.felder.items()}
        return {name: wert for name, wert in gefuellt.items() if wert}

    def ausgeblendet(self) -> set[str]:
        return {name for name, haken in self.haken.items() if not haken.isChecked()}

    def _feldwert(self, feld: QWidget) -> str:
        if isinstance(feld, QPlainTextEdit):
            # Leerzeilen am Rand weg, die Zeilen selbst bleiben.
            return "\n".join(
                zeile.strip() for zeile in feld.toPlainText().strip().splitlines()
            )
        return feld.text().strip()


class ProjektdatenDialog(QDialog):
    """Projektdaten und eigene Felder pflegen.

    Jedes Feld hat einen Haken davor: abgewaehlte Felder
    erscheinen auf keinem Blatt, behalten ihren Inhalt aber. Wer eine
    Anlagennummer nur fuer diesen Ausdruck weglassen will, muss sie nicht
    loeschen.

    Name und Nummer des Verteilers stehen oben mit im Dialog: im
    Schriftfeld stehen sie neben Firma und Kunde, also werden sie auch
    hier gesucht. Sie gehoeren zum Verteiler und lassen sich nicht
    abwaehlen - ein Blatt ohne Verteilernamen waere keines.
    """

    def __init__(
        self,
        projekt: Projekt,
        parent: QWidget | None = None,
        vorgaben: bool = False,
        quelle: Projekt | None = None,
    ) -> None:
        super().__init__(parent)
        self.vorgaben = vorgaben
        self.quelle = quelle
        self.setWindowTitle(
            "Vorgaben für neue Verteiler" if vorgaben else "Projektdaten"
        )
        self.resize(620, 760)
        self.projekt = projekt

        self.verteilername = QLineEdit(projekt.verteiler.name)
        self.verteilername.setPlaceholderText("z. B. Verteiler Keller")
        self.verteilernummer = QLineEdit(projekt.verteiler.nummer)
        self.verteilernummer.setPlaceholderText("z. B. 1.1")
        verteilerform = QFormLayout()
        verteilerform.addRow("Verteilername:", self.verteilername)
        verteilerform.addRow("Verteilernummer:", self.verteilernummer)
        verteilerblock = QGroupBox("Verteiler — steht im Schriftfeld jedes Blattes")
        verteilerblock.setLayout(verteilerform)

        projektdaten = ProjektdatenFelder(
            projekt.briefkopf,
            {name for name in BRIEFKOPF_FELDER if not projekt.sichtbar(name)},
        )
        self.projektdaten = projektdaten
        # Die Tests und der Rest des Dialogs greifen weiter direkt zu.
        self.felder = projektdaten.felder
        self.haken = projektdaten.haken

        self.eigene = QTableWidget(0, 2)
        self.eigene.setHorizontalHeaderLabels(["Feldname", "Inhalt"])
        self.eigene.horizontalHeader().setStretchLastSection(True)
        self.eigene.setToolTip(
            "Das Häkchen am Feldnamen entscheidet, ob das Feld auf den "
            "Blättern erscheint."
        )
        self.eigene.verticalHeader().setVisible(False)
        self.eigene.setMinimumHeight(150)
        for name, wert in projekt.eigene_felder.items():
            self._zeile_anhaengen(name, wert, projekt.sichtbar(name))

        hinzu = QPushButton("Feld hinzufügen")
        hinzu.clicked.connect(lambda: self._zeile_anhaengen("", "", True))
        weg = QPushButton("Feld entfernen")
        weg.clicked.connect(self._zeile_entfernen)
        knoepfe = QHBoxLayout()
        knoepfe.addWidget(hinzu)
        knoepfe.addWidget(weg)
        knoepfe.addStretch(1)

        eigenblock = QVBoxLayout()
        eigenblock.addWidget(self.eigene)
        eigenblock.addLayout(knoepfe)
        eigene = QGroupBox("Eigene Felder")
        eigene.setLayout(eigenblock)

        aufbau = QVBoxLayout(self)
        if vorgaben:
            # Der Verteiler gehoert nicht in die Vorgaben - Name und
            # Nummer sind bei jedem ein anderer.
            verteilerblock.setVisible(False)
            hinweis = QLabel(
                "Diese Angaben stehen beim Anlegen eines neuen Verteilers schon "
                "in den Feldern. Was hier leer bleibt, ist dort abgewählt."
            )
            hinweis.setWordWrap(True)
            aufbau.addWidget(hinweis)
            if quelle is not None:
                uebernehmen = QPushButton("Aus dem offenen Verteiler übernehmen")
                uebernehmen.clicked.connect(self._aus_dem_verteiler)
                aufbau.addWidget(uebernehmen)
        else:
            aufbau.addWidget(verteilerblock)
        aufbau.addWidget(projektdaten)
        aufbau.addWidget(eigene)
        aufbau.addWidget(_knopfleiste(self))

    def _alle_haken(self, an: bool) -> None:
        self.projektdaten.alle_haken(an)

    def _aus_dem_verteiler(self) -> None:
        """Fuellt die Vorgaben aus dem offenen Verteiler."""
        if self.quelle is None:
            return
        for name, feld in self.projektdaten.felder.items():
            wert = self.quelle.briefkopf.get(name, "")
            if isinstance(feld, QPlainTextEdit):
                feld.setPlainText(wert)
            else:
                feld.setText(wert)
            self.projektdaten.haken[name].setChecked(self.quelle.sichtbar(name))
        self.eigene.setRowCount(0)
        for name, wert in self.quelle.eigene_felder.items():
            self._zeile_anhaengen(name, wert, self.quelle.sichtbar(name))

    def _zeile_anhaengen(self, name: str, wert: str, sichtbar: bool = True) -> None:
        zeile = self.eigene.rowCount()
        self.eigene.insertRow(zeile)
        feldname = QTableWidgetItem(name)
        feldname.setFlags(feldname.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        feldname.setCheckState(
            Qt.CheckState.Checked if sichtbar else Qt.CheckState.Unchecked
        )
        self.eigene.setItem(zeile, 0, feldname)
        self.eigene.setItem(zeile, 1, QTableWidgetItem(wert))

    def _zeile_entfernen(self) -> None:
        zeile = self.eigene.currentRow()
        if zeile >= 0:
            self.eigene.removeRow(zeile)

    def uebernehmen(self) -> None:
        """Schreibt die Eingaben ins Projekt - samt der Auswahl."""
        ausgeblendet: set[str] = set()

        if not self.vorgaben:
            self.projekt.verteiler.name = self.verteilername.text().strip()
            self.projekt.verteiler.nummer = self.verteilernummer.text().strip()

        self.projekt.briefkopf = self.projektdaten.werte()
        ausgeblendet |= self.projektdaten.ausgeblendet()

        eigene: dict[str, str] = {}
        for zeile in range(self.eigene.rowCount()):
            name = self.eigene.item(zeile, 0)
            wert = self.eigene.item(zeile, 1)
            if not name or not name.text().strip():
                continue
            schluessel = name.text().strip()
            eigene[schluessel] = wert.text().strip() if wert else ""
            if name.checkState() != Qt.CheckState.Checked:
                ausgeblendet.add(schluessel)
        self.projekt.eigene_felder = eigene
        self.projekt.ausgeblendet = ausgeblendet
