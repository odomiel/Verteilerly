"""Dialoge: neuer Verteiler, Kabel anlegen, Überlauf, Briefkopf.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
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
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

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
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Neuer Verteiler")
        self.vorlagen = vorlagen
        self.vorlagenordner = vorlagenordner

        self.name = QLineEdit()
        self.name.setPlaceholderText("z. B. Verteiler Keller")
        self.nummer = QLineEdit()
        self.nummer.setPlaceholderText("z. B. 1.1")

        stammdaten = QFormLayout()
        stammdaten.addRow("Verteilername:", self.name)
        stammdaten.addRow("Verteilernummer:", self.nummer)

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

        aufbau = QVBoxLayout(self)
        aufbau.addLayout(stammdaten)
        aufbau.addSpacing(6)
        aufbau.addWidget(self.aus_vorlage)
        aufbau.addWidget(vorlagenkasten)
        aufbau.addWidget(self.eigen)
        aufbau.addWidget(eigenkasten)
        aufbau.addWidget(_knopfleiste(self))

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


class BriefkopfDialog(QDialog):
    """Briefkopf und eigene Felder zentral pflegen.

    Jedes Feld hat ein Haken davor: abgewaehlte Felder erscheinen auf
    keinem Blatt, behalten ihren Inhalt aber. Wer eine Anlagennummer nur
    fuer diesen Ausdruck weglassen will, muss sie nicht loeschen.
    """

    def __init__(self, projekt: Projekt, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Briefkopf und eigene Felder")
        self.resize(620, 700)
        self.projekt = projekt

        self.felder: dict[str, QLineEdit] = {}
        self.haken: dict[str, QCheckBox] = {}
        form = QFormLayout()
        for name in BRIEFKOPF_FELDER:
            feld = QLineEdit(projekt.briefkopf.get(name, ""))
            haken = QCheckBox(BRIEFKOPF_BESCHRIFTUNG.get(name, name) + ":")
            haken.setChecked(projekt.sichtbar(name))
            haken.setToolTip(
                "Ohne Haken bleibt der Inhalt erhalten, erscheint aber auf "
                "keinem Blatt."
            )
            # Der Haken ist zugleich die Beschriftung der Zeile.
            haken.toggled.connect(feld.setEnabled)
            feld.setEnabled(haken.isChecked())
            self.felder[name] = feld
            self.haken[name] = haken
            form.addRow(haken, feld)

        alle_an = QPushButton("Alle")
        alle_an.clicked.connect(lambda: self._alle_haken(True))
        alle_aus = QPushButton("Keine")
        alle_aus.clicked.connect(lambda: self._alle_haken(False))
        schnell = QHBoxLayout()
        schnell.addWidget(QLabel("Auswahl:"))
        schnell.addWidget(alle_an)
        schnell.addWidget(alle_aus)
        schnell.addStretch(1)

        briefkopfblock = QVBoxLayout()
        briefkopfblock.addLayout(form)
        briefkopfblock.addLayout(schnell)
        briefkopf = QGroupBox("Briefkopf — steht auf jedem Blatt")
        briefkopf.setLayout(briefkopfblock)

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
        aufbau.addWidget(briefkopf)
        aufbau.addWidget(eigene)
        aufbau.addWidget(_knopfleiste(self))

    def _alle_haken(self, an: bool) -> None:
        for haken in self.haken.values():
            haken.setChecked(an)

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

        self.projekt.briefkopf = {
            name: feld.text().strip()
            for name, feld in self.felder.items()
            if feld.text().strip()
        }
        for name, haken in self.haken.items():
            if not haken.isChecked():
                ausgeblendet.add(name)

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
