"""Dialoge: neuer Verteiler, Kabel anlegen, Überlauf, Projektdaten.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import (
    QColor,
    QFontMetrics,
    QKeySequence,
    QPalette,
    QShortcut,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
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
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .. import hilfe, paket, suche
from ..blattvorlagen import (
    Blattvorlagen,
    BlattvorlagenFehler,
    blattvorlage_loeschen,
    blattvorlage_umbenennen,
)
from ..farbcodes import Kabeltypen
from ..modell import (
    BLATTART_BESCHRIFTUNG,
    BLATTART_NAMEN,
    BLATTARTEN,
    BLATTBESCHRIFTUNG,
    BRIEFKOPF_BESCHRIFTUNG,
    BRIEFKOPF_FELDER,
    Kabel,
    Projekt,
    Verteiler,
    mehrzahl,
)
from ..vorlagen import (
    Vorlage,
    VorlagenFehler,
    Vorlagen,
    vorlage_loeschen,
    vorlage_speichern,
    vorlage_umbenennen,
)
from .passform import PassenderDialog
from .sprache import frage
from ..sprachen import u


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
    knoepfe.button(QDialogButtonBox.StandardButton.Ok).setText(u(u("Übernehmen")))
    knoepfe.button(QDialogButtonBox.StandardButton.Cancel).setText(u("Abbrechen"))
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
        QMessageBox.warning(parent, u("Nicht als Vorlage geeignet"), str(fehler))
        return None

    name, gewaehlt = QInputDialog.getText(
        parent, u("Als Vorlage speichern"), u("Name der Vorlage:"), text=vorschlag
    )
    if not gewaehlt or not name.strip():
        return None

    vorlage = Vorlage.aus_verteiler(verteiler, name.strip(), beschreibung=beschreibung)
    ueberschreiben = False
    if vorlage.id in vorlagen:
        antwort = frage(
            parent,
            u("Vorlage überschreiben?"),
            u("Es gibt schon eine Vorlage „{0}“. Soll sie ersetzt werden?").format(vorlagen.holen(vorlage.id).name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if antwort != QMessageBox.StandardButton.Yes:
            return None
        ueberschreiben = True

    try:
        ziel = vorlage_speichern(vorlage, ordner, ueberschreiben)
    except VorlagenFehler as fehler:
        QMessageBox.warning(parent, u("Vorlage nicht gespeichert"), str(fehler))
        return None

    vorlagen.aufnehmen(vorlage)
    QMessageBox.information(parent, u("Vorlage gespeichert"), u("{0}\n{1}").format(vorlage.name, ziel))
    return vorlage


class NeuerVerteilerDialog(PassenderDialog):
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
        self.setWindowTitle(u("Neuer Verteiler"))
        self.vorlagen = vorlagen
        self.vorlagenordner = vorlagenordner

        self.name = QLineEdit()
        self.name.setPlaceholderText(u("z. B. Verteiler Keller"))
        self.nummer = QLineEdit()
        self.nummer.setPlaceholderText(u("z. B. 1.1"))

        # Wie das Blatt aussieht, wird gleich hier gewaehlt - und bleibt
        # unter Einstellungen aenderbar.
        self.blattvorlagen = blattvorlagen or Blattvorlagen()
        self.blattvorlagenwahl = QComboBox()
        self.blattvorlagenwahl.setToolTip(
            u("Spalten, Schriftgrößen und Ränder der Blätter. "
            "Später unter Einstellungen ▸ Blattvorlage zu ändern.")
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
        stammdaten.addRow(u("Verteilername:"), self.name)
        stammdaten.addRow(u("Verteilernummer:"), self.nummer)
        stammdaten.addRow(u("Blattvorlage:"), self.blattvorlagenwahl)

        # Vorlage
        self.aus_vorlage = QRadioButton(u("Aus Vorlage"))
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
        self.eigen = QRadioButton(u("Benutzerdefiniert"))
        self.buchten = QSpinBox()
        self.buchten.setRange(1, 20)
        self.leisten = QSpinBox()
        self.leisten.setRange(1, 60)
        self.leisten.setValue(4)
        self.dawahl = QComboBox()
        for anzahl in DA_VORGABEN:
            self.dawahl.addItem(u("{0} DA").format(anzahl), anzahl)
        self.dawahl.addItem("Benutzerdefiniert", 0)
        self.dawahl.setCurrentIndex(DA_VORGABEN.index(10))
        self.dawahl.currentIndexChanged.connect(self._da_wahl_gewechselt)

        self.da = QSpinBox()
        self.da.setRange(1, 100)
        self.da.setValue(10)
        self.da.setSuffix(u(" DA"))
        self.da.setVisible(False)

        dazeile = QHBoxLayout()
        dazeile.setContentsMargins(0, 0, 0, 0)
        dazeile.addWidget(self.dawahl)
        dazeile.addWidget(self.da)
        dablock = QWidget()
        dablock.setLayout(dazeile)

        # Erweitert: jede Bucht einzeln. Nicht jeder Verteiler ist
        # gleichmaessig gewachsen - eine Bucht mit 20-DA-Leisten neben
        # zweien mit 10 DA ist im Bestand nichts Seltenes.
        self.erweitert = QCheckBox(u("Erweiterte Verteiler: Buchten einzeln festlegen"))
        self.erweitert.setToolTip(
            u("Jede Bucht bekommt ihre eigene Zahl an Leisten und ihre eigene "
            "Leistengröße. Eine Leistengröße je Bucht.")
        )
        self.erweitert.toggled.connect(self._erweitert_umgeschaltet)

        self.buchtentabelle = QTableWidget(0, 2)
        self.buchtentabelle.setHorizontalHeaderLabels(
            [u("Leisten je Bucht"), u("DA je Leiste")]
        )
        self.buchtentabelle.verticalHeader().setDefaultSectionSize(26)
        self.buchtentabelle.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.buchtentabelle.setVisible(False)

        for feld in (self.buchten, self.leisten, self.da):
            feld.valueChanged.connect(self._summe_zeigen)
        self.buchten.valueChanged.connect(self._buchtenzeilen_anpassen)
        self.summe = QLabel()

        self.als_vorlage = QPushButton(u("Als Vorlage speichern…"))
        self.als_vorlage.setToolTip(
            u("Legt diese Geometrie als Vorlage ab, damit sie beim nächsten "
            "Verteiler oben zur Wahl steht.")
        )
        self.als_vorlage.clicked.connect(self.vorlage_ablegen)
        self.als_vorlage.setEnabled(vorlagenordner is not None)

        eigenform = QFormLayout()
        eigenform.addRow(u("Buchten:"), self.buchten)
        self.leistenzeile = eigenform.rowCount()
        eigenform.addRow(u("Leisten je Bucht:"), self.leisten)
        eigenform.addRow(u("DA je Leiste:"), dablock)
        eigenform.addRow("", self.erweitert)
        eigenform.addRow("", self.buchtentabelle)
        eigenform.addRow("", self.summe)
        eigenform.addRow("", self.als_vorlage)
        self.eigenform = eigenform
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
            u("Projektdaten — stehen auf jedem Blatt, später änderbar"),
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

        # Der Inhalt steht in einem eigenen Widget: auf einem flachen
        # Bildschirm rollt er, die Knopfleiste bleibt stehen.
        inhalt = QWidget()
        aufbau = QVBoxLayout(inhalt)
        aufbau.addLayout(nebeneinander, 1)
        self.resize(1000, 620)
        self.inhalt_rollbar(inhalt, _knopfleiste(self))

        self._beschreibung_zeigen()
        self._summe_zeigen()

    def _beschreibung_zeigen(self) -> None:
        kennung = self.vorlagenwahl.currentData()
        if kennung:
            vorlage = self.vorlagen.holen(kennung)
            self.beschreibung.setText(
                u("{0}\n{1} Leisten, {2} DA").format(vorlage.beschreibung, vorlage.leisten_gesamt, vorlage.da_gesamt)
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
        bauplan = self.bauplan()
        leisten = sum(anzahl for anzahl, _ in bauplan)
        gesamt = sum(anzahl * da for anzahl, da in bauplan)
        self.summe.setText(
            u("ergibt {0}, {1} DA").format(mehrzahl(leisten, 'Leiste', 'Leisten'), gesamt)
        )

    def vorlage_ablegen(self) -> None:
        """Sichert die eingestellte Geometrie als Vorlage."""
        bauplan = self.bauplan()
        leisten = sum(anzahl for anzahl, _ in bauplan)
        gesamt = sum(anzahl * da for anzahl, da in bauplan)
        if len(set(bauplan)) == 1:
            da = bauplan[0][1]
            vorschlag = (
                u("{0} DA — {1} zu {2} DA").format(gesamt, mehrzahl(leisten, "Leiste", "Leisten"), da)
            )
            beschreibung = u("{0} zu je {1} mit {2}.").format(
                mehrzahl(len(bauplan), "Bucht", "Buchten"),
                mehrzahl(bauplan[0][0], "Leiste", "Leisten"),
                mehrzahl(da, "Doppelader", "Doppeladern"),
            )
        else:
            # Ungleich besetzt: die Beschreibung zaehlt die Buchten auf.
            vorschlag = u("{0} DA — {1}").format(gesamt, mehrzahl(leisten, "Leiste", "Leisten"))
            beschreibung = "; ".join(
                u("Bucht {0}: {1} zu {2} DA").format(nr, mehrzahl(anzahl, "Leiste", "Leisten"), da)
                for nr, (anzahl, da) in enumerate(bauplan, 1)
            )
        vorlage = als_vorlage_speichern(
            self,
            self.geometrie(),
            self.vorlagen,
            self.vorlagenordner,
            vorschlag=vorschlag,
            beschreibung=beschreibung,
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

    def _erweitert_umgeschaltet(self, an: bool) -> None:
        """Erweitert: die Tabelle tritt an die Stelle der beiden Zahlen."""
        self.buchtentabelle.setVisible(an)
        for zeile in (self.leistenzeile, self.leistenzeile + 1):
            beschriftung = self.eigenform.itemAt(
                zeile, QFormLayout.ItemRole.LabelRole
            )
            feld = self.eigenform.itemAt(zeile, QFormLayout.ItemRole.FieldRole)
            for teil in (beschriftung, feld):
                if teil is not None and teil.widget() is not None:
                    teil.widget().setVisible(not an)
        if an:
            self._buchtenzeilen_anpassen()
        self._summe_zeigen()

    def _buchtenzeilen_anpassen(self) -> None:
        """So viele Zeilen wie Buchten - neue erben die bisherigen Werte."""
        gewuenscht = self.buchten.value()
        while self.buchtentabelle.rowCount() > gewuenscht:
            self.buchtentabelle.removeRow(self.buchtentabelle.rowCount() - 1)
        while self.buchtentabelle.rowCount() < gewuenscht:
            zeile = self.buchtentabelle.rowCount()
            self.buchtentabelle.insertRow(zeile)
            leisten = QSpinBox()
            leisten.setRange(1, 60)
            leisten.setValue(self.leisten.value())
            da = QSpinBox()
            da.setRange(1, 100)
            da.setSuffix(u(" DA"))
            da.setValue(self.da_je_leiste())
            for feld in (leisten, da):
                feld.valueChanged.connect(self._summe_zeigen)
            self.buchtentabelle.setCellWidget(zeile, 0, leisten)
            self.buchtentabelle.setCellWidget(zeile, 1, da)
        self.buchtentabelle.setVerticalHeaderLabels(
            [u("Bucht {0}").format(nr) for nr in range(1, gewuenscht + 1)]
        )
        # Die Tabelle ist so hoch wie ihre Zeilen; leerer Platz darunter
        # sieht nach einem Fehler aus, den es nicht gibt.
        kopf = self.buchtentabelle.horizontalHeader().height()
        rahmen = 2 * self.buchtentabelle.frameWidth()
        self.buchtentabelle.setFixedHeight(
            min(kopf + rahmen + gewuenscht * 26 + 2, 260)
        )

    def bauplan(self) -> list[tuple[int, int]]:
        """Je Bucht (Leisten, DA je Leiste) - erweitert oder gleichmaessig."""
        if not self.erweitert.isChecked():
            return [
                (self.leisten.value(), self.da_je_leiste())
            ] * self.buchten.value()
        return [
            (
                self.buchtentabelle.cellWidget(zeile, 0).value(),
                self.buchtentabelle.cellWidget(zeile, 1).value(),
            )
            for zeile in range(self.buchtentabelle.rowCount())
        ]

    def geometrie(self, name: str = "", nummer: str = "") -> Verteiler:
        """Der Verteiler aus den eigenen Angaben, ohne Vorlage."""
        return Verteiler.aus_buchten(self.bauplan(), name, nummer)

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


class PaketDialog(PassenderDialog):
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
        knopf: str = u("Übernehmen"),
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(titel)

        self.haken: dict[str, QCheckBox] = {}
        felder = QVBoxLayout()
        for teil in paket.TEILE:
            anzahl = int(bestand.get(teil, 0))
            beschriftung = paket.BESCHRIFTUNG[teil]
            if teil != paket.EINSTELLUNGEN:
                beschriftung += u(" ({0})").format(anzahl)
            haken = QCheckBox(beschriftung)
            haken.setChecked(bool(anzahl))
            haken.setEnabled(bool(anzahl))
            if not anzahl:
                haken.setToolTip(u("Ist nicht vorhanden"))
            self.haken[teil] = haken
            felder.addWidget(haken)

        kasten = QGroupBox(u("Teile"))
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


class BlattwahlDialog(PassenderDialog):
    """Welche Blattarten ins PDF kommen.

    Je Blattart ein Haken mit der Zahl ihrer Blaetter dahinter. Ohne einen
    einzigen Haken gaebe es nichts auszugeben - dann ist der Knopf aus.
    """

    def __init__(
        self, anzahlen: dict, gewaehlt, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(u("PDF ausgeben"))

        self.haken: dict[str, QCheckBox] = {}
        felder = QVBoxLayout()
        for art in BLATTARTEN:
            anzahl = int(anzahlen.get(art, 0))
            haken = QCheckBox(u(BLATTART_NAMEN[art]) + u(" ({0})").format(anzahl))
            haken.setChecked(art in gewaehlt and anzahl > 0)
            haken.setEnabled(anzahl > 0)
            self.haken[art] = haken
            felder.addWidget(haken)
        kasten = QGroupBox(u("Blätter"))
        kasten.setLayout(felder)

        aufbau = QVBoxLayout(self)
        hinweis = QLabel(u(
            "Gezählt wird, was hineinkommt: ohne Deckblatt beginnt die "
            "Verteilerbelegung bei Blatt 1."
        ))
        hinweis.setWordWrap(True)
        aufbau.addWidget(hinweis)
        aufbau.addWidget(kasten)
        knoepfe = _knopfleiste(self)
        knoepfe.button(QDialogButtonBox.StandardButton.Ok).setText(u("Weiter…"))
        self.knoepfe = knoepfe
        aufbau.addWidget(knoepfe)
        for haken in self.haken.values():
            haken.toggled.connect(self._knopf_auffrischen)
        self._knopf_auffrischen()
        self.resize(360, 240)

    def _knopf_auffrischen(self) -> None:
        """Ohne einen einzigen Haken gibt es nichts auszugeben."""
        self.knoepfe.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            bool(self.auswahl())
        )

    def auswahl(self) -> set[str]:
        return {art for art, haken in self.haken.items() if haken.isChecked()}


class VerteilervorlagenDialog(PassenderDialog):
    """Verteilervorlagen verwalten: umbenennen, löschen, zurückholen.

    Auch die mitgelieferten lassen sich loeschen - wer sie nie braucht,
    soll sie nicht jedes Mal im Menue haben. Sie bleiben im Abbild
    liegen; ein Knopf holt sie zurueck.
    """

    def __init__(
        self,
        vorlagen: Vorlagen,
        ordner,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(u("Verteilervorlagen"))
        self.vorlagen = vorlagen
        self.ordner = ordner
        # Was der Dialog getan hat - das Hauptfenster liest es aus.
        self.geloescht: list[str] = []
        self.umbenannt: dict[str, str] = {}
        self.wiederhergestellt = False

        self.liste = QListWidget()
        self.liste.itemDoubleClicked.connect(lambda _: self.umbenennen())

        self.umbenennen_knopf = QPushButton(u("Umbenennen…"))
        self.umbenennen_knopf.clicked.connect(self.umbenennen)
        self.loeschen_knopf = QPushButton(u("Löschen"))
        self.loeschen_knopf.clicked.connect(self.loeschen)
        self.zurueck_knopf = QPushButton(u("Mitgelieferte wiederherstellen"))
        self.zurueck_knopf.setToolTip(
            u("Holt die mitgelieferten Vorlagen zurück, so wie sie ausgeliefert "
            "wurden. Eigene Vorlagen bleiben unberührt.")
        )
        self.zurueck_knopf.clicked.connect(self.wiederherstellen)

        knoepfe = QHBoxLayout()
        knoepfe.addWidget(self.umbenennen_knopf)
        knoepfe.addWidget(self.loeschen_knopf)
        knoepfe.addStretch(1)
        knoepfe.addWidget(self.zurueck_knopf)

        self.hinweis = QLabel()
        self.hinweis.setWordWrap(True)
        self.hinweis.setMinimumHeight(48)
        self.liste.currentRowChanged.connect(lambda _: self._hinweis_zeigen())

        schliessen = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        schliessen.rejected.connect(self.accept)
        schliessen.button(QDialogButtonBox.StandardButton.Close).setText(u("Schließen"))

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(QLabel(
            u("Grundstrukturen für neue Verteiler — Buchten, Leisten und "
            "Doppeladern:")
        ))
        aufbau.addWidget(self.liste, 1)
        aufbau.addLayout(knoepfe)
        aufbau.addWidget(self.hinweis)
        aufbau.addWidget(schliessen)
        self.resize(460, 380)
        self._liste_fuellen()

    # -- Anzeige -----------------------------------------------------------

    def _liste_fuellen(self, auswahl: str = "") -> None:
        self.liste.clear()
        for vorlage in self.vorlagen.alle:
            eintrag = QListWidgetItem(str(vorlage))
            eintrag.setData(Qt.ItemDataRole.UserRole, vorlage.id)
            if vorlage.beschreibung:
                eintrag.setToolTip(vorlage.beschreibung)
            self.liste.addItem(eintrag)
        stelle = max(
            (i for i in range(self.liste.count())
             if self.liste.item(i).data(Qt.ItemDataRole.UserRole) == auswahl),
            default=0,
        )
        self.liste.setCurrentRow(stelle)
        self._hinweis_zeigen()

    def _hinweis_zeigen(self) -> None:
        kennung = self.gewaehlt()
        if not kennung:
            self.hinweis.setText(u("Keine Vorlage vorhanden."))
            for knopf in (self.umbenennen_knopf, self.loeschen_knopf):
                knopf.setEnabled(False)
            return
        vorlage = self.vorlagen.holen(kennung)
        zeilen = [vorlage.beschreibung] if vorlage.beschreibung else []
        zeilen.append(
            u("{0}, {1}, {2} DA").format(
                mehrzahl(len(vorlage.buchtenplan), "Bucht", "Buchten"),
                mehrzahl(vorlage.leisten_gesamt, "Leiste", "Leisten"),
                vorlage.da_gesamt,
            )
        )
        self.hinweis.setText("\n".join(zeilen))
        for knopf in (self.umbenennen_knopf, self.loeschen_knopf):
            knopf.setEnabled(self.ordner is not None)

    def gewaehlt(self) -> str:
        eintrag = self.liste.currentItem()
        return eintrag.data(Qt.ItemDataRole.UserRole) if eintrag else ""

    # -- Tun ---------------------------------------------------------------

    def umbenennen(self) -> None:
        kennung = self.gewaehlt()
        if not kennung or self.ordner is None:
            return
        vorlage = self.vorlagen.holen(kennung)
        name, gewaehlt = QInputDialog.getText(
            self, u("Vorlage umbenennen"), u("Name der Vorlage:"), text=vorlage.name
        )
        if not gewaehlt or not name.strip() or name.strip() == vorlage.name:
            return
        try:
            neu = vorlage_umbenennen(vorlage, name, self.ordner)
        except VorlagenFehler as fehler:
            QMessageBox.warning(self, u("Nicht umbenannt"), str(fehler))
            return
        self.vorlagen.aufnehmen(neu)
        self.umbenannt[kennung] = neu.name
        self._liste_fuellen(kennung)

    def loeschen(self) -> None:
        kennung = self.gewaehlt()
        if not kennung or self.ordner is None:
            return
        vorlage = self.vorlagen.holen(kennung)
        antwort = frage(
            self,
            u("Vorlage löschen?"),
            u("Die Vorlage „{0}“ löschen?\nMitgelieferte Vorlagen holt der Knopf „Mitgelieferte wiederherstellen“ zurück.").format(vorlage.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if antwort != QMessageBox.StandardButton.Yes:
            return
        try:
            vorlage_loeschen(kennung, self.ordner)
        except VorlagenFehler as fehler:
            QMessageBox.warning(self, u("Nicht gelöscht"), str(fehler))
            return
        self.geloescht.append(kennung)
        self.vorlagen.entfernen(kennung)
        self._liste_fuellen()

    def wiederherstellen(self) -> None:
        antwort = frage(
            self,
            u("Mitgelieferte Vorlagen wiederherstellen?"),
            u("Die mitgelieferten Vorlagen kommen zurück, so wie sie "
            "ausgeliefert wurden — auch gelöschte und geänderte.\n"
            "Eigene Vorlagen bleiben unberührt."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if antwort != QMessageBox.StandardButton.Yes:
            return
        self.wiederhergestellt = True
        self.accept()


class BlattvorlagenDialog(PassenderDialog):
    """Welche Blattvorlage die Ausgabe benutzt.

    Die Wahl gehoert nicht zu einem einzelnen Verteiler, sondern zum
    Arbeitsplatz: sie steht in der Verteilerly.conf und gilt fuer
    Vorschau, PDF und die Excel-Mappe.

    Umbenennen laesst sich eine Vorlage hier ebenfalls: der Name ist,
    was im Menue steht, und "Knapp" sagt nicht jedem dasselbe. Geaendert
    wird nur der Name - die Kennung bleibt, denn sie ist der Dateiname
    und steht in der Verteilerly.conf.
    """

    def __init__(
        self,
        vorlagen: Blattvorlagen,
        gewaehlt: str = "",
        parent: QWidget | None = None,
        ordner=None,
        quellen=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(u("Blattvorlage"))
        self.vorlagen = vorlagen
        self.ordner = ordner
        self.quellen = list(quellen or [])
        #: Was der Dialog getan hat - das Hauptfenster liest es aus.
        self.umbenannt: dict[str, str] = {}
        self.geloescht: list[str] = []
        self.wiederhergestellt = False

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

        self.umbenennen_knopf = QPushButton(u("Umbenennen…"))
        self.umbenennen_knopf.setToolTip(
            u("Gibt der Vorlage einen anderen Namen; ihre Kennung bleibt")
        )
        self.umbenennen_knopf.clicked.connect(self.umbenennen)
        self.loeschen_knopf = QPushButton(u("Löschen"))
        self.loeschen_knopf.clicked.connect(self.loeschen)
        self.zurueck_knopf = QPushButton(u("Mitgelieferte wiederherstellen"))
        self.zurueck_knopf.setToolTip(
            u("Holt die mitgelieferten Blattvorlagen zurück, so wie sie "
              "ausgeliefert wurden. Eigene bleiben unberührt.")
        )
        self.zurueck_knopf.clicked.connect(self.wiederherstellen)
        for knopf in (self.umbenennen_knopf, self.loeschen_knopf,
                      self.zurueck_knopf):
            knopf.setEnabled(self.ordner is not None)
        knoepfe = QHBoxLayout()
        knoepfe.addWidget(self.umbenennen_knopf)
        knoepfe.addWidget(self.loeschen_knopf)
        knoepfe.addStretch(1)
        knoepfe.addWidget(self.zurueck_knopf)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(QLabel(u("Wie das Blatt aussieht — Spalten, Schriftgrößen, "
                                "Ränder:")))
        aufbau.addWidget(self.liste, 1)
        aufbau.addLayout(knoepfe)
        aufbau.addWidget(self.beschreibung)
        aufbau.addWidget(_knopfleiste(self))
        self.resize(420, 360)
        self._beschreibung_zeigen()

    def umbenennen(self) -> None:
        """Fragt nach einem Namen und schreibt ihn in die YAML-Datei."""
        kennung = self.gewaehlt()
        if not kennung or self.ordner is None:
            return
        vorlage = self.vorlagen.holen(kennung)
        name, gewaehlt = QInputDialog.getText(
            self, u("Blattvorlage umbenennen"), u("Name der Blattvorlage:"),
            text=vorlage.name,
        )
        if not gewaehlt or not name.strip() or name.strip() == vorlage.name:
            return
        try:
            neu = blattvorlage_umbenennen(vorlage, name, self.ordner, self.quellen)
        except BlattvorlagenFehler as fehler:
            QMessageBox.warning(self, u("Nicht umbenannt"), str(fehler))
            return
        self.vorlagen.aufnehmen(neu)
        self.umbenannt[kennung] = neu.name
        eintrag = self.liste.currentItem()
        if eintrag is not None:
            eintrag.setText(neu.name)
        self._beschreibung_zeigen()

    def loeschen(self) -> None:
        """Nimmt eine Blattvorlage weg - auch eine mitgelieferte."""
        kennung = self.gewaehlt()
        if not kennung or self.ordner is None:
            return
        vorlage = self.vorlagen.holen(kennung)
        antwort = frage(
            self,
            u("Blattvorlage löschen?"),
            u("Die Blattvorlage „{0}“ löschen?\nMitgelieferte holt der Knopf "
              "„Mitgelieferte wiederherstellen“ zurück.").format(vorlage.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if antwort != QMessageBox.StandardButton.Yes:
            return
        try:
            blattvorlage_loeschen(kennung, self.ordner)
        except BlattvorlagenFehler as fehler:
            QMessageBox.warning(self, u("Nicht gelöscht"), str(fehler))
            return
        self.geloescht.append(kennung)
        self.vorlagen.entfernen(kennung)
        self._liste_fuellen()

    def wiederherstellen(self) -> None:
        """Die mitgelieferten Blattvorlagen zurückholen."""
        antwort = frage(
            self,
            u("Mitgelieferte Blattvorlagen wiederherstellen?"),
            u("Die mitgelieferten Blattvorlagen kommen zurück, so wie sie "
              "ausgeliefert wurden — auch gelöschte und geänderte.\nEigene "
              "bleiben unberührt."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if antwort != QMessageBox.StandardButton.Yes:
            return
        self.wiederhergestellt = True
        self.accept()

    def _liste_fuellen(self, auswahl: str = "") -> None:
        """Baut die Liste neu auf - nach dem Löschen."""
        self.liste.blockSignals(True)
        self.liste.clear()
        for vorlage in self.vorlagen.alle:
            eintrag = QListWidgetItem(vorlage.name)
            eintrag.setData(Qt.ItemDataRole.UserRole, vorlage.id)
            if vorlage.beschreibung:
                eintrag.setToolTip(vorlage.beschreibung)
            self.liste.addItem(eintrag)
        stelle = max(
            (i for i in range(self.liste.count())
             if self.liste.item(i).data(Qt.ItemDataRole.UserRole) == auswahl),
            default=0,
        )
        self.liste.setCurrentRow(stelle)
        self.liste.blockSignals(False)
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


class KabelDialog(PassenderDialog):
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
        self.setWindowTitle(u("Kabel bearbeiten") if kabel else u("Kabel auflegen"))
        self.verteiler = verteiler

        self.beschriftung = QLineEdit()
        self.beschriftung.setPlaceholderText(u("z. B. 4DA Leitung zu Wohnzimmer"))

        self.leiste = QComboBox()
        for l in verteiler.alle_leisten:
            self.leiste.addItem(u("Leiste {0}  ({1} DA)").format(l.nummer, l.da_anzahl), l.nummer)
        stelle = self.leiste.findData(leiste)
        if stelle >= 0:
            self.leiste.setCurrentIndex(stelle)

        self.start = QSpinBox()
        self.start.setRange(1, 100)
        self.start.setValue(start_da)

        self.kabel_da = QSpinBox()
        self.kabel_da.setRange(1, 200)
        self.kabel_da.setValue(4)
        self.kabel_da.setSuffix(u(" DA"))

        self.auflegen_da = QSpinBox()
        self.auflegen_da.setRange(1, 200)
        self.auflegen_da.setValue(4)
        self.auflegen_da.setSuffix(u(" DA"))
        self.kabel_da.valueChanged.connect(self._kabelgroesse_geaendert)

        self.kabeltyp = QComboBox()
        self.kabeltyp.addItem(u("— ohne, Farben von Hand —"), None)
        for typ in kabeltypen.alle:
            self.kabeltyp.addItem(typ.name, typ.id)

        self.kuerzungshinweis = QLabel()
        self.kuerzungshinweis.setWordWrap(True)
        self.auflegen_da.valueChanged.connect(self._kuerzung_zeigen)

        self.farben_neu = QCheckBox(u("Auch von Hand geänderte Adernfarben ersetzen"))
        self.farben_neu.setToolTip(
            u("Die Farben folgen Kabeltyp und Größe ohnehin — solange sie "
            "noch so dastehen, wie die Automatik sie gesetzt hat. Mit "
            "diesem Haken werden auch von Hand geänderte überschrieben.")
        )

        form = QFormLayout()
        form.addRow(u("Beschriftung:"), self.beschriftung)
        form.addRow(u("Leiste:"), self.leiste)
        form.addRow(u("Ab Stift:"), self.start)
        form.addRow(u("Kabelgröße:"), self.kabel_da)
        form.addRow(u("Davon auflegen:"), self.auflegen_da)
        form.addRow(u("Kabeltyp:"), self.kabeltyp)
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
        # Erst die Groesse, dann das Aufgelegte: die Groesse zieht es mit,
        # und gekuerzt war es vielleicht schon.
        self.kabel_da.setValue(kabel.da_gesamt)
        self.auflegen_da.setValue(kabel.da_aufgelegt)
        stelle = self.kabeltyp.findData(kabel.kabeltyp)
        self.kabeltyp.setCurrentIndex(max(stelle, 0))

        # Leiste und Startpunkt stehen fest: dort haengt das Kabel. Wie
        # viel davon aufliegt, laesst sich dagegen aendern - gewachsen
        # und geschrumpft wird am Ende.
        for feld in (self.leiste, self.start):
            feld.setEnabled(False)
            feld.setToolTip(
                u("Steht fest — für eine andere Lage das Kabel abnehmen "
                "und neu auflegen")
            )
        self.auflegen_da.setToolTip(
            u("Wächst und schrumpft am Ende des Kabels; der Anfang bleibt, "
            "wo er ist")
        )
        if len(kabel.abschnitte) > 1:
            self.leiste.setToolTip(
                u("Das Kabel läuft über {0} Abschnitte").format(len(kabel.abschnitte))
            )

    def _knoepfe(self) -> QDialogButtonBox:
        knoepfe = _knopfleiste(self)
        if self.bearbeitet is not None:
            weg = knoepfe.addButton(
                u("Kabel entfernen"), QDialogButtonBox.ButtonRole.DestructiveRole
            )
            weg.clicked.connect(self._entfernen)
        return knoepfe

    def _entfernen(self) -> None:
        self.entfernen = True
        self.accept()

    def _kabelgroesse_geaendert(self, wert: int) -> None:
        """Die Kabelgroesse zieht "Davon auflegen" mit.

        Der Regelfall ist, dass ein Kabel ganz aufgelegt wird; wer kuerzen
        will, sagt es danach. Beim Bearbeiten liegt die Zahl fest - dort
        bleibt sie stehen, wie sie ist.
        """
        self.auflegen_da.setMaximum(wert)
        self.auflegen_da.setValue(wert)
        self._kuerzung_zeigen()

    def _kuerzung_zeigen(self) -> None:
        rest = self.kabel_da.value() - self.auflegen_da.value()
        if rest > 0:
            self.kuerzungshinweis.setText(
                u("Das Kabel wird gekürzt: {0} DA bleiben unaufgelegt.").format(rest)
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


class UeberlaufDialog(PassenderDialog):
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
        self.setWindowTitle(u("Kabel passt nicht vollständig"))

        erklaerung = QLabel(
            u("Von diesem Kabel passen {0} DA auf die gewählte Leiste, {1} DA bleiben übrig.").format(passend, rest)
        )
        erklaerung.setWordWrap(True)

        self.fortsetzen = QRadioButton(u("Auf einer anderen Leiste fortsetzen"))
        self.fortsetzen.setChecked(True)
        self.verfaellt = QRadioButton(u("Rest verfällt — nur {0} DA auflegen").format(passend))

        self.leiste = QComboBox()
        for l in verteiler.alle_leisten:
            self.leiste.addItem(u("Leiste {0}  ({1} DA)").format(l.nummer, l.da_anzahl), l.nummer)
        self.start = QSpinBox()
        self.start.setRange(1, 100)
        self.start.setValue(1)

        fortsetzung = QFormLayout()
        fortsetzung.addRow(u("Weiter auf:"), self.leiste)
        fortsetzung.addRow(u("Ab Stift:"), self.start)
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


class PruefberichtDialog(PassenderDialog):
    """Was die Pruefung einer Vorlagendatei ergab.

    Oben das Urteil in einem Satz, darunter die Datei, dann was das
    Programm darin gelesen hat - wer eine Vorlage schreibt, sieht daran,
    ob sie so verstanden wird, wie sie gemeint war.
    """

    def __init__(self, bericht, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bericht = bericht
        self.setWindowTitle(u("Vorlage geprüft"))

        urteil = QLabel(bericht.urteil)
        schrift = urteil.font()
        schrift.setBold(True)
        urteil.setFont(schrift)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlainText(self.als_text(bericht))
        self.text.setMinimumSize(520, 260)

        knoepfe = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        knoepfe.button(QDialogButtonBox.StandardButton.Close).setText(u("Schließen"))
        knoepfe.rejected.connect(self.reject)
        knoepfe.accepted.connect(self.accept)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(urteil)
        aufbau.addWidget(QLabel(str(bericht.datei)))
        aufbau.addWidget(self.text)
        aufbau.addWidget(knoepfe)

    @staticmethod
    def als_text(bericht) -> str:
        """Der Bericht als Text - dasselbe, was der Dialog zeigt."""
        zeilen: list[str] = []
        if bericht.fehler:
            zeilen += [u("Fehler"), f"  {bericht.fehler}"]
        if bericht.angaben:
            if zeilen:
                zeilen.append("")
            zeilen.append(u("Gelesen"))
            zeilen += [f"  {zeile}" for zeile in bericht.angaben]
        if bericht.hinweise:
            if zeilen:
                zeilen.append("")
            zeilen.append(u("Anmerkungen"))
            zeilen += [f"  {zeile}" for zeile in bericht.hinweise]
        return "\n".join(zeilen)


class DokumentationDialog(PassenderDialog):
    """Die Dokumentation im Programm.

    Links das Verzeichnis, rechts der Text. Die Seite bringt keine
    eigenen Farben mit: sie soll im hellen wie im dunklen
    Erscheinungsbild lesbar sein, und das entscheidet die Farbpalette
    des Fensters.

    Darueber die Suche: wer wissen will, was "Rangierung" bedeutet,
    soll nicht erst raten, in welchem der zwoelf Abschnitte es steht.
    Gesucht wird waehrend des Tippens, jeder Treffer wird angestrichen,
    und Enter geht zum naechsten.
    """

    #: Wie die Treffer angestrichen werden - kraeftig der laufende,
    #: leise die uebrigen. Die Farbe kommt aus der Palette, damit es in
    #: beiden Erscheinungsbildern stimmt.
    TRUEBUNG = 70            # Deckkraft der uebrigen Treffer (0-255)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(u("Dokumentation"))

        text = hilfe.dokumentation()
        self.text = QTextBrowser()
        self.text.setOpenExternalLinks(False)
        self.text.setHtml(text)
        self.text.document().setDefaultStyleSheet(
            "h1 { font-size: 17pt; }"
            "h2 { font-size: 12pt; margin-top: 18px; }"
            "p, li, td, th { line-height: 140%; }"
            "th { text-align: left; }"
            "pre { margin-left: 12px; }"
            ".anriss { font-size: 11pt; }"
        )

        # Suche: Feld, zwei Pfeile, Zaehler.
        self.treffer: list[QTextCursor] = []
        self.stelle = -1

        self.suchfeld = QLineEdit()
        self.suchfeld.setPlaceholderText(u("In der Dokumentation suchen (Strg+F)"))
        self.suchfeld.setClearButtonEnabled(True)
        self.suchfeld.textChanged.connect(self._suche_beginnen)
        self.suchfeld.returnPressed.connect(lambda: self.weiterspringen(1))

        self.zurueck = QPushButton("‹")
        self.zurueck.setToolTip(u("Vorheriger Treffer (Umschalt+F3)"))
        self.zurueck.clicked.connect(lambda: self.weiterspringen(-1))
        self.vor = QPushButton("›")
        self.vor.setToolTip(u("Nächster Treffer (F3 oder Enter)"))
        self.vor.clicked.connect(lambda: self.weiterspringen(1))
        for knopf in (self.zurueck, self.vor):
            knopf.setFixedWidth(32)
            knopf.setEnabled(False)

        self.zaehler = QLabel()
        self.zaehler.setMinimumWidth(110)

        suchzeile = QHBoxLayout()
        suchzeile.addWidget(QLabel(u("Suchen:")))
        suchzeile.addWidget(self.suchfeld, 1)
        suchzeile.addWidget(self.zurueck)
        suchzeile.addWidget(self.vor)
        suchzeile.addWidget(self.zaehler)

        for tasten, richtung in (
            (QKeySequence.StandardKey.FindNext, 1),
            (QKeySequence.StandardKey.FindPrevious, -1),
        ):
            QShortcut(tasten, self, lambda r=richtung: self.weiterspringen(r))
        QShortcut(
            QKeySequence.StandardKey.Find, self, self.suche_aufrufen
        )

        self.verzeichnis = QListWidget()
        self.verzeichnis.setMaximumWidth(260)
        for marke, titel in hilfe.abschnitte(text):
            eintrag = QListWidgetItem(titel)
            eintrag.setData(Qt.ItemDataRole.UserRole, marke)
            self.verzeichnis.addItem(eintrag)
        self.verzeichnis.currentItemChanged.connect(self._springen)

        teiler = QSplitter()
        teiler.addWidget(self.verzeichnis)
        teiler.addWidget(self.text)
        teiler.setStretchFactor(1, 1)

        schliessen = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        schliessen.rejected.connect(self.reject)
        schliessen.button(QDialogButtonBox.StandardButton.Close).setText(u("Schließen"))

        aufbau = QVBoxLayout(self)
        # Die Suchzeile bleibt so hoch, wie sie ist; der Platz gehoert
        # dem Text darunter.
        aufbau.addLayout(suchzeile, 0)
        aufbau.addWidget(teiler, 1)
        aufbau.addWidget(schliessen, 0)
        self.resize(940, 700)

    def _springen(self, eintrag: QListWidgetItem | None) -> None:
        if eintrag is None:
            return
        self.text.scrollToAnchor(eintrag.data(Qt.ItemDataRole.UserRole))

    # -- Suche -------------------------------------------------------------

    def suche_aufrufen(self) -> None:
        """Strg+F: ins Suchfeld, und was darin steht, ist gleich ersetzbar."""
        self.suchfeld.setFocus()
        self.suchfeld.selectAll()

    def _suche_beginnen(self) -> None:
        """Bei jedem getippten Zeichen: Treffer sammeln und hinspringen.

        Angefangen wird oben am sichtbaren Rand, nicht am Anfang des
        Textes: wer im Abschnitt ueber Kabel liest und dort sucht, meint
        den naechsten Treffer von dort - nicht den auf Seite eins.
        """
        wort = self.suchfeld.text()
        self.treffer = []
        if len(wort) >= 2:
            blatt = self.text.document()
            stelle = QTextCursor(blatt)
            while True:
                stelle = blatt.find(wort, stelle)
                if stelle.isNull():
                    break
                self.treffer.append(QTextCursor(stelle))
        oben = self.text.cursorForPosition(QPoint(0, 0)).position()
        naechster = next(
            (i for i, c in enumerate(self.treffer) if c.selectionStart() >= oben),
            0,
        )
        self._treffer_zeigen(naechster)

    def weiterspringen(self, richtung: int) -> None:
        """Einen Treffer vor oder zurueck, im Kreis."""
        if not self.treffer:
            return
        self._treffer_zeigen((self.stelle + richtung) % len(self.treffer))

    def _treffer_zeigen(self, nummer: int) -> None:
        """Streicht alle Treffer an und rueckt den gewaehlten ins Bild."""
        self.stelle = nummer if self.treffer else -1
        for knopf in (self.zurueck, self.vor):
            knopf.setEnabled(len(self.treffer) > 1)

        kraeftig = self.palette().color(QPalette.ColorRole.Highlight)
        leise = QColor(kraeftig)
        leise.setAlpha(self.TRUEBUNG)
        angestrichen = []
        for i, treffer in enumerate(self.treffer):
            anstrich = QTextEdit.ExtraSelection()
            anstrich.cursor = treffer
            anstrich.format.setBackground(kraeftig if i == nummer else leise)
            if i == nummer:
                anstrich.format.setForeground(
                    self.palette().color(QPalette.ColorRole.HighlightedText)
                )
            angestrichen.append(anstrich)
        self.text.setExtraSelections(angestrichen)

        if self.treffer:
            # Ohne Auswahl, sonst laege der Anstrich unter der Markierung
            # des Textfeldes; gebraucht wird der Zeiger nur zum Blaettern.
            zeiger = QTextCursor(self.treffer[nummer])
            zeiger.clearSelection()
            self.text.setTextCursor(zeiger)
            self.text.ensureCursorVisible()
        self._zaehler_zeigen()

    def _zaehler_zeigen(self) -> None:
        wort = self.suchfeld.text()
        if not wort:
            self.zaehler.setText("")
        elif len(wort) < 2:
            self.zaehler.setText(u("weiter tippen…"))
        elif not self.treffer:
            self.zaehler.setText(u("nicht gefunden"))
        else:
            self.zaehler.setText(
                u("{0} von {1}").format(self.stelle + 1, mehrzahl(len(self.treffer), 'Treffer', 'Treffern'))
            )

    def keyPressEvent(self, ereignis) -> None:  # noqa: N802 - Qt-Name
        """Esc raeumt erst die Suche weg, dann schliesst es den Dialog."""
        if (
            ereignis.key() == Qt.Key.Key_Escape
            and self.suchfeld.text()
        ):
            self.suchfeld.clear()
            return
        super().keyPressEvent(ereignis)


class SuchDialog(PassenderDialog):
    """Im Projekt suchen und hinspringen.

    Oben das Wort, darunter die Fundstellen mit Ort, Feld und Inhalt.
    Ein Doppelklick oder Enter waehlt eine aus; das Hauptfenster springt
    dann dorthin. Gesucht wird beim Tippen - ein Verteiler passt ohne
    Weiteres durchsucht zu werden, dafuer braucht es keinen Knopf.
    """

    def __init__(
        self,
        projekt: Projekt,
        schreibweise=None,
        wort: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(u("Im Verteiler suchen"))
        self.projekt = projekt
        self.schreibweise = schreibweise
        self.gewaehlt: suche.Fundstelle | None = None
        self.treffer: list[suche.Fundstelle] = []

        self.suchfeld = QLineEdit(wort)
        self.suchfeld.setPlaceholderText(
            u("Bezeichnung, Bemerkung, Rangierung, Kabel, Projektdaten…")
        )
        self.suchfeld.setClearButtonEnabled(True)
        self.suchfeld.textChanged.connect(self._suchen)
        self.suchfeld.returnPressed.connect(self._erste_waehlen)

        self.liste = QTableWidget(0, 3)
        self.liste.setHorizontalHeaderLabels([u("Wo"), u("Feld"), u("Inhalt")])
        self.liste.verticalHeader().setVisible(False)
        self.liste.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.liste.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.liste.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.liste.horizontalHeader().setStretchLastSection(True)
        self.liste.itemDoubleClicked.connect(lambda _: self.springen())
        self.liste.itemSelectionChanged.connect(self._zustand)

        self.zaehler = QLabel()

        self.springen_knopf = QPushButton(u("Hinspringen"))
        self.springen_knopf.setDefault(True)
        self.springen_knopf.clicked.connect(self.springen)
        schliessen = QPushButton(u("Schließen"))
        schliessen.clicked.connect(self.reject)

        knoepfe = QHBoxLayout()
        knoepfe.addWidget(self.zaehler)
        knoepfe.addStretch(1)
        knoepfe.addWidget(self.springen_knopf)
        knoepfe.addWidget(schliessen)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(QLabel(u("Suchen nach:")))
        aufbau.addWidget(self.suchfeld)
        aufbau.addWidget(self.liste, 1)
        aufbau.addLayout(knoepfe)
        self.resize(720, 460)
        self._suchen()

    # -- Suchen ------------------------------------------------------------

    def _suchen(self) -> None:
        self.treffer = suche.suchen(
            self.projekt, self.suchfeld.text(), self.schreibweise
        )
        self.liste.setRowCount(len(self.treffer))
        for zeile, fund in enumerate(self.treffer):
            for spalte, text in enumerate((fund.ort, fund.beschriftung, fund.text)):
                self.liste.setItem(zeile, spalte, QTableWidgetItem(text))
        self.liste.resizeColumnsToContents()
        if self.treffer:
            self.liste.selectRow(0)
        self._zaehler_zeigen()
        self._zustand()

    def _zaehler_zeigen(self) -> None:
        wort = self.suchfeld.text().strip()
        if len(wort) < 2:
            self.zaehler.setText(u("Mindestens zwei Zeichen eingeben."))
        elif not self.treffer:
            self.zaehler.setText(u("„{0}“ kommt im Verteiler nicht vor.").format(wort))
        else:
            self.zaehler.setText(
                mehrzahl(len(self.treffer), "Fundstelle", "Fundstellen")
            )

    def _zustand(self) -> None:
        self.springen_knopf.setEnabled(self.auswahl() is not None)

    def auswahl(self) -> suche.Fundstelle | None:
        zeile = self.liste.currentRow()
        if 0 <= zeile < len(self.treffer) and self.liste.selectionModel().hasSelection():
            return self.treffer[zeile]
        return None

    def _erste_waehlen(self) -> None:
        """Enter im Suchfeld nimmt die erste Fundstelle."""
        if self.treffer:
            self.liste.selectRow(max(self.liste.currentRow(), 0))
            self.springen()

    def springen(self) -> None:
        gewaehlt = self.auswahl()
        if gewaehlt is None:
            return
        self.gewaehlt = gewaehlt
        self.accept()


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
        super().__init__(u(titel), parent)
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
            haken = QCheckBox(u(BRIEFKOPF_BESCHRIFTUNG.get(name, name)) + ":")
            haken.setChecked(name not in ausgeblendet)
            haken.setToolTip(
                u("Ohne Haken bleibt der Inhalt erhalten, erscheint aber auf "
                "keinem Blatt.")
            )
            # Der Haken ist zugleich die Beschriftung der Zeile. Er sperrt
            # das Feld nicht: seit leere Felder abgewaehlt sind, liesse
            # sich sonst gerade dort nichts eintragen, wo etwas fehlt.
            if inhalt_hakt_an:
                self._mithaken(feld, haken)
            self.felder[name] = feld
            self.haken[name] = haken
            form.addRow(haken, feld)

        alle_an = QPushButton(u("Alle"))
        alle_an.clicked.connect(lambda: self.alle_haken(True))
        alle_aus = QPushButton(u("Keine"))
        alle_aus.clicked.connect(lambda: self.alle_haken(False))
        self.schnell = QHBoxLayout()
        self.schnell.addWidget(QLabel(u("Auswahl:")))
        self.schnell.addWidget(alle_an)
        self.schnell.addWidget(alle_aus)
        self.schnell.addStretch(1)

        aufbau = QVBoxLayout()
        aufbau.addLayout(form)
        aufbau.addLayout(self.schnell)
        self.setLayout(aufbau)

    def zusatz(self, feld: QWidget) -> None:
        """Haengt etwas rechts an die Auswahlzeile - dort ist Platz frei."""
        self.schnell.insertWidget(self.schnell.count() - 1, feld)

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
            u("Mehrzeilig: Firma, Straße, Ort — so steht die Anschrift auch "
            "auf dem Blatt untereinander.")
        )
        feld.setPlaceholderText(u("Firma Beliebig\nBeliebige Straße 7\n77777 Ort"))
        # Drei Zeilen sind die uebliche Anschrift - und sie sollen ganz zu
        # sehen sein, ohne Rollbalken. Rahmen und Innenabstand zaehlen mit,
        # sonst wird die dritte Zeile angeschnitten. Erst poliert stehen
        # sie fest: das Erscheinungsbild gibt dem Feld einen breiteren
        # Rahmen, und der zaehlt mit.
        feld.ensurePolished()
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


class BeschriftungsFelder(QWidget):
    """Eigene Woerter fuer die Zeilen des Schriftfeldes.

    Wem "Kunde" nicht passt, schreibt "Auftraggeber" hin. Die Woerter
    stehen hinter einem Schalter: die Vorgabe taugt fuer die meisten, und
    ein Dialog voller Textfelder, die niemand anfasst, hilft keinem.
    Zurueck zur Vorgabe geht mit einem Knopf.
    """

    def __init__(
        self,
        beschriftungen: dict[str, str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        beschriftungen = beschriftungen or {}

        # Der Schalter gehoert in die Auswahlzeile der Projektdaten; er
        # wird dort eingehaengt (ProjektdatenFelder.zusatz).
        self.schalter = QCheckBox(
            u("Erweitert: Beschriftungen auf dem Blatt ändern")
        )
        self.schalter.setToolTip(
            u("Zeigt die Wörter, mit denen das Schriftfeld seine Zeilen "
            "überschreibt. Der Schalter blendet sie nur ein und aus; "
            "geändert wird nichts, solange nichts eingetippt ist.")
        )

        self.felder: dict[str, QLineEdit] = {}
        form = QFormLayout()
        for marke, vorgabe in BLATTBESCHRIFTUNG.items():
            feld = QLineEdit(beschriftungen.get(marke, "").strip() or vorgabe)
            feld.setPlaceholderText(vorgabe)
            # So breit, dass auch "Verteiler-Nr." ganz hineinpasst.
            feld.setMinimumWidth(150)
            self.felder[marke] = feld
            # Links steht die Vorgabe: so ist die Zeile auch dann noch zu
            # erkennen, wenn rechts ein ganz anderes Wort steht.
            form.addRow(vorgabe, feld)

        inhalt = QWidget()
        inhalt.setLayout(form)
        rollen = QScrollArea()
        rollen.setWidget(inhalt)
        rollen.setWidgetResizable(True)
        # Neben den Feldern ist Hoehe da: die Liste bekommt so viel, wie
        # sie braucht, und der Rollbalken erscheint erst, wenn der Dialog
        # dafuer zu flach ist.
        rahmen = 2 * rollen.frameWidth()
        rollen.setMinimumHeight(inhalt.sizeHint().height() + rahmen)
        # Der Rollbereich gibt die Wuensche seines Inhalts nicht weiter -
        # er koennte ja rollen. Die Breite muss er trotzdem bekommen.
        rollen.setMinimumWidth(inhalt.sizeHint().width() + rahmen)

        zurueck = QPushButton(u("Auf Vorgabe zurücksetzen"))
        zurueck.setToolTip(u("Schreibt in jedes Feld wieder das Wort der Vorgabe."))
        zurueck.clicked.connect(self.zuruecksetzen)
        knoepfe = QHBoxLayout()
        knoepfe.addWidget(zurueck)
        knoepfe.addStretch(1)

        innen = QVBoxLayout()
        innen.setContentsMargins(0, 0, 0, 0)
        innen.addWidget(rollen)
        innen.addLayout(knoepfe)
        self.kasten = QWidget()
        self.kasten.setLayout(innen)

        # Wer schon eigene Woerter benutzt, soll sie gleich sehen.
        eigen = bool(self.werte())
        self.schalter.setChecked(eigen)
        self.kasten.setVisible(eigen)
        self.schalter.toggled.connect(self.kasten.setVisible)

        # Der Schalter steht nicht hier, sondern in der Auswahlzeile der
        # Projektdaten - dort ist er zu finden, wo man ihn sucht. Dieses
        # Bauteil traegt nur die Liste.
        aufbau = QVBoxLayout()
        aufbau.setContentsMargins(0, 0, 0, 0)
        aufbau.addWidget(self.kasten)
        self.setLayout(aufbau)

    def zuruecksetzen(self) -> None:
        """Jedes Feld zurueck auf das Wort der Vorgabe."""
        for marke, feld in self.felder.items():
            feld.setText(BLATTBESCHRIFTUNG[marke])

    def werte(self) -> dict[str, str]:
        """Nur die Woerter, die von der Vorgabe abweichen."""
        return {
            marke: feld.text().strip()
            for marke, feld in self.felder.items()
            if feld.text().strip() and feld.text().strip() != BLATTBESCHRIFTUNG[marke]
        }


class ProjektdatenDialog(PassenderDialog):
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
            u("Vorgaben für neue Verteiler") if vorgaben else u("Projektdaten")
        )
        self.resize(620, 760)
        self.projekt = projekt

        self.verteilername = QLineEdit(projekt.verteiler.name)
        self.verteilername.setPlaceholderText(u("z. B. Verteiler Keller"))
        self.verteilernummer = QLineEdit(projekt.verteiler.nummer)
        self.verteilernummer.setPlaceholderText(u("z. B. 1.1"))
        verteilerform = QFormLayout()
        verteilerform.addRow(u("Verteilername:"), self.verteilername)
        verteilerform.addRow(u("Verteilernummer:"), self.verteilernummer)
        verteilerblock = QGroupBox(u("Verteiler — steht im Schriftfeld jedes Blattes"))
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
        self.eigene.setHorizontalHeaderLabels([u("Feldname"), u("Inhalt")])
        self.eigene.horizontalHeader().setStretchLastSection(True)
        self.eigene.setToolTip(
            u("Das Häkchen am Feldnamen entscheidet, ob das Feld auf den "
            "Blättern erscheint.")
        )
        self.eigene.verticalHeader().setVisible(False)
        self.eigene.setMinimumHeight(150)
        for name, wert in projekt.eigene_felder.items():
            self._zeile_anhaengen(name, wert, projekt.sichtbar(name))

        # Auf welchen Blaettern die eigenen Felder erscheinen.
        self.blattarten: dict[str, QCheckBox] = {}
        blattzeile = QHBoxLayout()
        blattzeile.addWidget(QLabel(u("Anzeigen auf:")))
        for art in BLATTARTEN:
            haken = QCheckBox(u(BLATTART_BESCHRIFTUNG[art]))
            haken.setChecked(art in projekt.eigene_felder_auf)
            haken.setToolTip(
                u("Ohne Haken erscheinen die eigenen Felder auf dieser Blattart "
                "nicht; ihr Inhalt bleibt erhalten.")
            )
            self.blattarten[art] = haken
            blattzeile.addWidget(haken)
        blattzeile.addStretch(1)
        # In den Vorgaben hat die Zeile nichts zu suchen: sie gehoert zum
        # Projekt, nicht zu dem, was jeder neue Verteiler erbt.
        self.blattkasten = QWidget()
        self.blattkasten.setLayout(blattzeile)
        self.blattkasten.setVisible(not vorgaben)

        self.beschriftungen = BeschriftungsFelder(projekt.beschriftungen, self)
        projektdaten.zusatz(self.beschriftungen.schalter)

        hinzu = QPushButton(u("Feld hinzufügen"))
        hinzu.clicked.connect(lambda: self._zeile_anhaengen("", "", True))
        weg = QPushButton(u("Feld entfernen"))
        weg.clicked.connect(self._zeile_entfernen)
        knoepfe = QHBoxLayout()
        knoepfe.addWidget(hinzu)
        knoepfe.addWidget(weg)
        knoepfe.addStretch(1)

        eigenblock = QVBoxLayout()
        eigenblock.addWidget(self.eigene)
        eigenblock.addWidget(self.blattkasten)
        eigenblock.addLayout(knoepfe)
        eigene = QGroupBox(u("Eigene Felder"))
        eigene.setLayout(eigenblock)

        # Links die Felder, rechts die Beschriftungen: untereinander
        # waere der Dialog hoeher als mancher Bildschirm.
        links = QVBoxLayout()
        links.setContentsMargins(0, 0, 0, 0)
        inhalt = QWidget()
        aufbau = QVBoxLayout(inhalt)
        if vorgaben:
            # Der Verteiler gehoert nicht in die Vorgaben - Name und
            # Nummer sind bei jedem ein anderer.
            verteilerblock.setVisible(False)
            hinweis = QLabel(
                u("Diese Angaben stehen beim Anlegen eines neuen Verteilers schon "
                "in den Feldern. Was hier leer bleibt, ist dort abgewählt.")
            )
            hinweis.setWordWrap(True)
            links.addWidget(hinweis)
            if quelle is not None:
                uebernehmen = QPushButton(u("Aus dem offenen Verteiler übernehmen"))
                uebernehmen.clicked.connect(self._aus_dem_verteiler)
                links.addWidget(uebernehmen)
        else:
            links.addWidget(verteilerblock)
        links.addWidget(projektdaten)
        links.addWidget(eigene)

        rechts = QVBoxLayout()
        rechts.setContentsMargins(0, 0, 0, 0)
        rechts.addWidget(self.beschriftungen)
        rechts.addStretch(1)

        nebeneinander = QHBoxLayout()
        # Die Beschriftungen nehmen nur, was sie brauchen; zugeklappt ist
        # das eine Zeile, der Platz gehoert dann den Feldern.
        nebeneinander.addLayout(links, 1)
        nebeneinander.addLayout(rechts, 0)
        aufbau.addLayout(nebeneinander)
        # Lauter Felder untereinander - das schrumpft nicht. Auf einem
        # flachen Bildschirm rollt der Inhalt, Übernehmen und Abbrechen
        # stehen fest darunter.
        self.inhalt_rollbar(inhalt, _knopfleiste(self))

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
        for marke, feld in self.beschriftungen.felder.items():
            feld.setText(self.quelle.beschriftung(marke))

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
        self.projekt.eigene_felder_auf = {
            art for art, haken in self.blattarten.items() if haken.isChecked()
        }
        self.projekt.beschriftungen = self.beschriftungen.werte()
