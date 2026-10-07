"""Der Dialog des Blattvorlagen-Editors: links die Werte, rechts das Blatt.

Gezeichnet wird mit demselben Modell wie Vorschau und PDF (``layout``),
also sieht man, was herauskommt. Jede Aenderung baut die Vorlage neu und
prueft sie mit denselben Regeln wie beim Lesen einer Datei - was dort
abgewiesen wuerde, zeigt der Editor als Satz unter dem Blatt und laesst
sich nicht speichern.

Gespeichert wird auf zwei Wegen: **Speichern** schreibt die geladene
Vorlage in ihre eigene Datei zurueck - das geht nur, wenn sie eine im
Arbeitsordner hat -, **Als neue Vorlage speichern** legt eine neue an und
laesst jede vorhandene, wie sie ist. In der Datei steht nur, was von der
Vorgabe abweicht.
"""

from __future__ import annotations

import dataclasses
import pathlib

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ...blattvorlagen import (
    SPALTENFELDER,
    Blattvorlage,
    Spalte,
    blattvorlage_als_yaml,
    blattvorlage_aus_yaml,
    blattvorlage_speichern,
    freie_kennung,
)
from ...gui.passform import PassenderDialog
from ...gui.sprache import Knopf, frage
from ...gui.vorschau import Blattflaeche
from ...layout import blaetter
from ...modell import BLATTART_BESCHRIFTUNG, BLATTARTEN, Projekt, Verteiler
from ...sprachen import u
from .schriftfeld import AUSRICHTUNGSNAMEN, SchriftfeldEditor

# Was sich als Zahl einstellen laesst: Feld der Blattvorlage, Beschriftung,
# Einheit, kleinster und groesster Wert, Schrittweite. Die Beschriftungen
# werden beim Anzeigen uebersetzt, nicht beim Laden des Moduls.
ZAHLEN = (
    ("Blatt", (
        ("rand", "Rand", "mm", 0.0, 40.0, 0.5),
        ("kopfzeile_hoehe", "Kopfzeile", "mm", 3.0, 20.0, 0.5),
        ("zeilenhoehe_max", "Zeilenhöhe höchstens", "mm", 1.0, 20.0, 0.1),
        ("zeilenhoehe_min", "Zeilenhöhe mindestens", "mm", 1.0, 20.0, 0.1),
        ("zeilen_kabel", "Zeilen des Kabelnamens", "", 1.0, 6.0, 1.0),
    )),
    ("Schriftgrößen", (
        ("schrift_gross", "Groß", "pt", 4.0, 40.0, 0.5),
        ("schrift_mittel", "Mittel", "pt", 4.0, 30.0, 0.5),
        ("schrift_normal", "Normal", "pt", 3.0, 20.0, 0.5),
        ("schrift_klein", "Klein", "pt", 3.0, 20.0, 0.5),
        ("schrift_leiste", "Leiste", "pt", 0.0, 40.0, 0.5),
    )),
    ("Verteilerbelegung", (
        ("zelle_breite", "Zellenbreite", "mm", 2.0, 30.0, 0.5),
        ("zelle_hoehe", "Zellenhöhe", "mm", 2.0, 30.0, 0.5),
        ("leistenlabel", "Leistenbeschriftung", "mm", 4.0, 40.0, 0.5),
        ("abstand_leisten", "Abstand der Leisten", "mm", 0.0, 20.0, 0.5),
        ("abstand_buchten", "Abstand der Buchten", "mm", 0.0, 40.0, 0.5),
        ("fuellgrad_kabel", "Füllgrad des Kabelnamens", "", 0.1, 1.0, 0.02),
        ("polster_kabel", "Polster um den Kabelnamen", "mm", 0.0, 5.0, 0.1),
    )),
)
#: Felder, bei denen die Null etwas anderes heisst als "null Millimeter".
SONDERWERT = {"schrift_leiste": "automatisch"}

# Die Hoehe des Schriftfeldes steht bei seinen Bloecken, nicht beim Blatt.
SCHRIFTFELDHOEHE = ("schriftfeld_hoehe", "Höhe", "mm", 10.0, 80.0, 0.5)
SCHALTER = (
    ("da_nummern", "DA-Nummern in der Verteilerbelegung"),
    ("kabel_gedreht", "Kabelname quer in der Kabelspalte"),
)
FELDNAMEN = {
    "stift": "Stift",
    "ader": "Ader",
    "farbe": "Farbe",
    "bezeichnung": "Bezeichnung",
    "rangierung": "Rangierung",
    "bemerkung": "Bemerkung",
    "kabel": "Kabel",
}
VERZUG = 150  # ms - tippen, ohne dass das Blatt bei jeder Ziffer neu entsteht


def beispielprojekt() -> Projekt:
    """Ein kleiner Verteiler, an dem man etwas sieht - wenn keiner offen ist.

    Mit Projektdaten, damit im Schriftfeld nicht nur Beschriftungen stehen.
    """
    verteiler = Verteiler.aus_geometrie(2, 4, 10, name=u("Beispiel"), nummer="V-1")
    verteiler.kabel_anlegen(u("Musterleitung Obergeschoss"), 1, 1, 6)
    verteiler.kabel_anlegen("K2", 2, 3, 4)
    return Projekt(verteiler=verteiler, briefkopf={
        "firma": "Musterfirma GmbH\nHauptstraße 1\n12345 Musterstadt",
        "kunde": "Beispielkunde AG\nAm Markt 5\n54321 Beispielstadt",
        "anlagennummer": "A-4711",
        "kundennummer": "K-0815",
        "erstellt_am": "01.09.2026",
        "erstellt_von": "M. Muster",
        "stand_am": "15.09.2026",
        "stand_von": "M. Muster",
    })


class EditorDialog(PassenderDialog):
    """Eine Blattvorlage bearbeiten und die Wirkung sofort sehen."""

    def __init__(self, programm, parent: QWidget | None = None) -> None:
        super().__init__(parent or programm.fenster)
        self.setWindowTitle(u("Blattvorlagen-Editor"))
        # Der Editor ist eher ein Fenster als ein Dialog: Werte links, Blatt
        # rechts, und je groesser, desto besser. Als Dialog - und erst recht
        # als Werkzeugfenster, zu dem dialoge_freistellen() jeden Dialog
        # macht - haette er keinen Maximieren-Knopf. Als Fenster hat er ihn;
        # ueber dem Hauptfenster bleibt er, weil showEvent das Elternfenster
        # als transient anmeldet.
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinMaxButtonsHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.programm = programm
        self.projekt = programm.projekt() or beispielprojekt()
        self.blaetter = []
        self.geaendert = False
        self.gespeichert: list[str] = []
        self.takt = QTimer(self)
        self.takt.setSingleShot(True)
        self.takt.setInterval(VERZUG)
        self.takt.timeout.connect(self._neu_zeichnen)

        # -- links: die Werte ---------------------------------------------
        self.basiswahl = QComboBox()
        self.basiswahl.currentIndexChanged.connect(self._basis_gewaehlt)
        self.name = QLineEdit()
        self.name.textChanged.connect(self._geaendert)
        self.beschreibung = QLineEdit()
        self.beschreibung.textChanged.connect(self._geaendert)
        self.buchten = QSpinBox()
        self.buchten.setRange(1, 6)
        self.buchten.valueChanged.connect(self._geaendert)

        kopf = QFormLayout()
        kopf.addRow(u("Vorlage:"), self.basiswahl)
        kopf.addRow(u("Name:"), self.name)
        kopf.addRow(u("Beschreibung:"), self.beschreibung)
        kopf.addRow(u("Buchten je Blatt:"), self.buchten)

        links = QWidget()
        linksaufbau = QVBoxLayout(links)
        linksaufbau.addLayout(kopf)

        self.zahlen: dict[str, QDoubleSpinBox] = {}
        for gruppe, felder in ZAHLEN:
            formular = QFormLayout()
            for feld, beschriftung, einheit, unten, oben, schritt in felder:
                wert = QDoubleSpinBox()
                wert.setRange(unten, oben)
                wert.setSingleStep(schritt)
                # Eine Anzahl hat keine Nachkommastellen: „2,00 Zeilen"
                # liest sich wie ein Mass, und das ist es nicht.
                wert.setDecimals(0 if schritt >= 1 else 2)
                if einheit:
                    wert.setSuffix(f" {einheit}")
                # Wo die Null "wie die uebrigen" heisst, soll das auch
                # dastehen - "0,0 pt" liest sich wie eine Groesse.
                if feld in SONDERWERT:
                    wert.setSpecialValueText(u(SONDERWERT[feld]))
                wert.valueChanged.connect(self._geaendert)
                formular.addRow(u(beschriftung) + ":", wert)
                self.zahlen[feld] = wert
            kasten = QGroupBox(u(gruppe))
            kasten.setLayout(formular)
            linksaufbau.addWidget(kasten)

        self.schalter: dict[str, QCheckBox] = {}
        schalterkasten = QGroupBox(u("Schalter"))
        schalteraufbau = QVBoxLayout(schalterkasten)
        for feld, beschriftung in SCHALTER:
            haken = QCheckBox(u(beschriftung))
            haken.toggled.connect(self._geaendert)
            schalteraufbau.addWidget(haken)
            self.schalter[feld] = haken
        linksaufbau.addWidget(schalterkasten)

        linksaufbau.addWidget(self._spaltenkasten())
        linksaufbau.addWidget(self._schriftfeldkasten())
        linksaufbau.addWidget(self._eigenefelderkasten())
        linksaufbau.addStretch(1)

        rollbereich = QScrollArea()
        rollbereich.setWidget(links)
        rollbereich.setWidgetResizable(True)
        rollbereich.setMinimumWidth(420)

        # -- rechts: das Blatt --------------------------------------------
        self.blattwahl = QComboBox()
        self.blattwahl.currentIndexChanged.connect(self._blatt_zeigen)
        zurueck = QPushButton("‹")
        vor = QPushButton("›")
        for knopf, richtung in ((zurueck, -1), (vor, 1)):
            knopf.setFixedWidth(30)
            knopf.setStyleSheet("padding: 4px 0;")
            knopf.clicked.connect(lambda _an=False, r=richtung: self._schieben(r))
        blattkopf = QHBoxLayout()
        blattkopf.addWidget(QLabel(u("Blatt:")))
        blattkopf.addWidget(self.blattwahl, 1)
        blattkopf.addWidget(zurueck)
        blattkopf.addWidget(vor)

        self.flaeche = Blattflaeche()
        self.flaeche.farben_setzen(programm.farben())
        self.meldung = QLabel("")
        self.meldung.setWordWrap(True)
        self.meldung.setStyleSheet("color: #c0392b;")
        herkunft = QLabel(
            u("Gezeigt wird der offene Verteiler.") if programm.projekt()
            else u("Gezeigt wird ein Beispielverteiler — es ist keiner geöffnet.")
        )

        rechts = QWidget()
        rechtsaufbau = QVBoxLayout(rechts)
        rechtsaufbau.addLayout(blattkopf)
        rechtsaufbau.addWidget(self.flaeche, 1)
        rechtsaufbau.addWidget(self.meldung)
        rechtsaufbau.addWidget(herkunft)

        teiler = QSplitter(Qt.Orientation.Horizontal)
        teiler.addWidget(rollbereich)
        teiler.addWidget(rechts)
        teiler.setStretchFactor(0, 2)
        teiler.setStretchFactor(1, 3)

        self.ueberschreiben_knopf = QPushButton(u("Speichern"))
        self.ueberschreiben_knopf.setToolTip(
            u("Schreibt die Änderungen in die Datei der geladenen Vorlage")
        )
        self.ueberschreiben_knopf.clicked.connect(self.ueberschreiben)
        self.speichern_knopf = QPushButton(u("Als neue Vorlage speichern…"))
        self.speichern_knopf.clicked.connect(self.speichern)
        schliessen = QPushButton(u("Schließen"))
        schliessen.clicked.connect(self.reject)
        knoepfe = QHBoxLayout()
        knoepfe.addStretch(1)
        knoepfe.addWidget(self.ueberschreiben_knopf)
        knoepfe.addWidget(self.speichern_knopf)
        knoepfe.addWidget(schliessen)

        aufbau = QVBoxLayout(self)
        aufbau.addWidget(teiler, 1)
        aufbau.addLayout(knoepfe)

        self._basisliste_fuellen(programm.blattvorlage().id)
        self.resize(1240, 800)

    # -- Schriftfeld ---------------------------------------------------------

    def _schriftfeldkasten(self) -> QGroupBox:
        """Bauart, Hoehe und die Bloecke des Schriftfeldes - der Briefkopf."""
        feld, beschriftung, einheit, unten, oben, schritt = SCHRIFTFELDHOEHE
        hoehe = QDoubleSpinBox()
        hoehe.setRange(unten, oben)
        hoehe.setSingleStep(schritt)
        hoehe.setDecimals(2)
        hoehe.setSuffix(f" {einheit}")
        hoehe.valueChanged.connect(self._geaendert)
        self.zahlen[feld] = hoehe
        formular = QFormLayout()
        formular.addRow(u(beschriftung) + ":", hoehe)

        self.schriftfeld = SchriftfeldEditor()
        self.schriftfeld.geaendert.connect(self._geaendert)
        kasten = QGroupBox(u("Schriftfeld (Briefkopf)"))
        aufbau = QVBoxLayout(kasten)
        aufbau.addLayout(formular)
        aufbau.addWidget(self.schriftfeld)
        return kasten

    # -- Eigene Felder -------------------------------------------------------

    def _eigenefelderkasten(self) -> QGroupBox:
        """Die Namen der eigenen Felder - und auf welchen Blattarten sie stehen.

        Hier entstehen die Zeilen, die hinter der Marke *eigene* im
        Schriftfeld erscheinen; **gefuellt** werden sie am Verteiler
        (Bearbeiten ▸ Projektdaten). Die Vorlage sagt, welche Zeilen ein
        Blatt hat, das Projekt, was darin steht.
        """
        self.eigene = QListWidget()
        self.eigene.setMinimumHeight(120)
        self.eigene.setToolTip(
            u("Namen der eigenen Zeilen des Schriftfeldes. Gefüllt werden sie "
              "je Verteiler unter Bearbeiten ▸ Projektdaten.")
        )
        self.eigene.itemChanged.connect(self._eigene_geaendert)
        knoepfe = QHBoxLayout()
        for text, ruf in (
            (u("Hinzufügen"), self._eigenes_hinzu),
            (u("Entfernen"), self._eigenes_weg),
            (u("Nach oben"), lambda: self._eigenes_schieben(-1)),
            (u("Nach unten"), lambda: self._eigenes_schieben(1)),
        ):
            knopf = QPushButton(text)
            knopf.clicked.connect(ruf)
            knoepfe.addWidget(knopf)

        self.eigene_auf: dict[str, QCheckBox] = {}
        blattzeile = QHBoxLayout()
        blattzeile.addWidget(QLabel(u("Anzeigen auf:")))
        for art in BLATTARTEN:
            haken = QCheckBox(u(BLATTART_BESCHRIFTUNG[art]))
            haken.setToolTip(
                u("Ohne Haken erscheinen die eigenen Felder auf dieser "
                  "Blattart nicht.")
            )
            haken.toggled.connect(self._geaendert)
            self.eigene_auf[art] = haken
            blattzeile.addWidget(haken)
        blattzeile.addStretch(1)

        hinweis = QLabel(
            u("Sichtbar werden sie über die Marke „eigene“ im Schriftfeld.")
        )
        hinweis.setWordWrap(True)

        kasten = QGroupBox(u("Eigene Felder"))
        aufbau = QVBoxLayout(kasten)
        aufbau.addWidget(self.eigene)
        aufbau.addLayout(knoepfe)
        aufbau.addLayout(blattzeile)
        aufbau.addWidget(hinweis)
        return kasten

    def _eigene_geaendert(self, *_args) -> None:
        """Ein Name kam dazu, fiel weg oder heisst anders.

        Das Schriftfeld baut daraus sein Auswahlmenue - und verliert
        Eintraege, deren Feld es nicht mehr gibt.
        """
        self.schriftfeld.eigene_felder_setzen(self.eigenefelder())
        self._geaendert()

    def _eigenes_hinzu(self) -> None:
        eintrag = QListWidgetItem(u("Neues Feld"))
        eintrag.setFlags(eintrag.flags() | Qt.ItemFlag.ItemIsEditable)
        self.eigene.addItem(eintrag)
        self.eigene.setCurrentItem(eintrag)
        self.eigene.editItem(eintrag)
        self._eigene_geaendert()

    def _eigenes_weg(self) -> None:
        zeile = self.eigene.currentRow()
        if zeile >= 0:
            self.eigene.takeItem(zeile)
            self._eigene_geaendert()

    def _eigenes_schieben(self, richtung: int) -> None:
        zeile = self.eigene.currentRow()
        ziel = zeile + richtung
        if zeile < 0 or not 0 <= ziel < self.eigene.count():
            return
        eintrag = self.eigene.takeItem(zeile)
        self.eigene.insertItem(ziel, eintrag)
        self.eigene.setCurrentRow(ziel)
        self._eigene_geaendert()

    def eigenefelder(self) -> tuple[str, ...]:
        """Die Namen, wie sie in der Liste stehen - ohne Leere und Doppelte."""
        namen: list[str] = []
        for zeile in range(self.eigene.count()):
            name = self.eigene.item(zeile).text().strip()
            if name and name not in namen:
                namen.append(name)
        return tuple(namen)

    def _eigenefelder_setzen(self, namen, blattarten) -> None:
        self.eigene.blockSignals(True)
        self.eigene.clear()
        for name in namen:
            eintrag = QListWidgetItem(name)
            eintrag.setFlags(eintrag.flags() | Qt.ItemFlag.ItemIsEditable)
            self.eigene.addItem(eintrag)
        self.eigene.blockSignals(False)
        for art, haken in self.eigene_auf.items():
            haken.blockSignals(True)
            haken.setChecked(art in tuple(blattarten))
            haken.blockSignals(False)

    # -- Spalten -------------------------------------------------------------

    def _spaltenkasten(self) -> QGroupBox:
        self.spalten = QTableWidget(0, 4)
        self.spalten.setHorizontalHeaderLabels(
            [u("Feld"), u("Überschrift"), u("Anteil"), u("Ausrichtung")]
        )
        self.spalten.verticalHeader().setVisible(False)
        self.spalten.setMinimumHeight(230)
        knoepfe = QHBoxLayout()
        for text, ruf in (
            (u("Hinzufügen"), self._spalte_hinzu),
            (u("Entfernen"), self._spalte_weg),
            (u("Nach oben"), lambda: self._spalte_schieben(-1)),
            (u("Nach unten"), lambda: self._spalte_schieben(1)),
        ):
            knopf = QPushButton(text)
            knopf.clicked.connect(ruf)
            knoepfe.addWidget(knopf)
        kasten = QGroupBox(u("Spalten des Leistenblatts"))
        aufbau = QVBoxLayout(kasten)
        aufbau.addWidget(self.spalten)
        aufbau.addLayout(knoepfe)
        return kasten

    def _spalten_setzen(self, spalten) -> None:
        self.spalten.setRowCount(0)
        for spalte in spalten:
            zeile = self.spalten.rowCount()
            self.spalten.insertRow(zeile)
            feld = QComboBox()
            for kennung in SPALTENFELDER:
                feld.addItem(u(FELDNAMEN.get(kennung, kennung)), kennung)
            feld.setCurrentIndex(max(feld.findData(spalte.feld), 0))
            feld.currentIndexChanged.connect(self._geaendert)
            ueberschrift = QLineEdit(spalte.ueberschrift)
            ueberschrift.textChanged.connect(self._geaendert)
            anteil = QDoubleSpinBox()
            anteil.setRange(0.5, 200.0)
            anteil.setDecimals(1)
            anteil.setValue(spalte.anteil)
            anteil.valueChanged.connect(self._geaendert)
            ausrichtung = QComboBox()
            for kennung, name in AUSRICHTUNGSNAMEN.items():
                ausrichtung.addItem(u(name), kennung)
            ausrichtung.setCurrentIndex(max(ausrichtung.findData(spalte.ausrichtung), 0))
            ausrichtung.currentIndexChanged.connect(self._geaendert)
            for stelle, feldchen in enumerate((feld, ueberschrift, anteil, ausrichtung)):
                self.spalten.setCellWidget(zeile, stelle, feldchen)
        self.spalten.resizeColumnsToContents()

    def spaltenliste(self) -> list[Spalte]:
        liste = []
        for zeile in range(self.spalten.rowCount()):
            feld, ueberschrift, anteil, ausrichtung = (
                self.spalten.cellWidget(zeile, stelle) for stelle in range(4)
            )
            liste.append(Spalte(
                feld=feld.currentData(), ueberschrift=ueberschrift.text(),
                anteil=anteil.value(), ausrichtung=ausrichtung.currentData(),
            ))
        return liste

    def _spalte_hinzu(self) -> None:
        self._spalten_setzen(self.spaltenliste() + [Spalte("bemerkung", "", 10.0)])
        self.spalten.setCurrentCell(self.spalten.rowCount() - 1, 1)
        self._geaendert()

    def _spalte_weg(self) -> None:
        liste = self.spaltenliste()
        zeile = self.spalten.currentRow()
        # Ohne eine einzige Spalte gaebe es kein Leistenblatt.
        if len(liste) <= 1 or zeile < 0:
            return
        del liste[zeile]
        self._spalten_setzen(liste)
        self.spalten.setCurrentCell(min(zeile, len(liste) - 1), 0)
        self._geaendert()

    def _spalte_schieben(self, richtung: int) -> None:
        liste = self.spaltenliste()
        zeile = self.spalten.currentRow()
        ziel = zeile + richtung
        if zeile < 0 or not 0 <= ziel < len(liste):
            return
        liste[zeile], liste[ziel] = liste[ziel], liste[zeile]
        self._spalten_setzen(liste)
        self.spalten.setCurrentCell(ziel, 0)
        self._geaendert()

    # -- Vorlage -------------------------------------------------------------

    def _basisliste_fuellen(self, gewaehlt: str) -> None:
        self.basiswahl.blockSignals(True)
        self.basiswahl.clear()
        for vorlage in self.programm.blattvorlagen().alle:
            self.basiswahl.addItem(vorlage.name, vorlage.id)
        self.basiswahl.setCurrentIndex(max(self.basiswahl.findData(gewaehlt), 0))
        self.basiswahl.blockSignals(False)
        self.basis_uebernehmen(self.programm.blattvorlagen().holen(self.basiswahl.currentData()))

    def basis_uebernehmen(self, vorlage: Blattvorlage) -> None:
        """Stellt alle Felder auf eine vorhandene Vorlage."""
        self.basis = vorlage
        felder = [self.name, self.beschreibung, self.buchten,
                  *self.zahlen.values(), *self.schalter.values()]
        for feld in felder:
            feld.blockSignals(True)
        self.name.setText(vorlage.name)
        self.beschreibung.setText(vorlage.beschreibung)
        self.buchten.setValue(vorlage.buchten_je_blatt)
        for feld, wert in self.zahlen.items():
            wert.setValue(getattr(vorlage, feld))
        for feld, haken in self.schalter.items():
            haken.setChecked(getattr(vorlage, feld))
        for feld in felder:
            feld.blockSignals(False)
        self._spalten_setzen(vorlage.spalten)
        self._eigenefelder_setzen(vorlage.eigene_felder, vorlage.eigene_felder_auf)
        # Erst die Namen, dann das Schriftfeld: dessen Auswahlmenue baut
        # sich aus ihnen, und seine Eintraege zeigen auf sie.
        self.schriftfeld.eigene_felder_setzen(vorlage.eigene_felder)
        self.schriftfeld.setzen(vorlage.schriftfeld, vorlage.schriftfeld_anteile)
        self.geaendert = False
        self._neu_zeichnen()

    def _basis_gewaehlt(self, _index: int) -> None:
        kennung = self.basiswahl.currentData()
        if kennung is None or kennung == self.basis.id:
            return
        if self.geaendert and not self._verwerfen_erlaubt():
            self.basiswahl.blockSignals(True)
            self.basiswahl.setCurrentIndex(max(self.basiswahl.findData(self.basis.id), 0))
            self.basiswahl.blockSignals(False)
            return
        self.basis_uebernehmen(self.programm.blattvorlagen().holen(kennung))

    def vorlage(self) -> Blattvorlage:
        """Die Vorlage, wie sie gerade eingestellt ist."""
        schriftfeld, anteile = self.schriftfeld.werte()
        return dataclasses.replace(
            self.basis,
            standard=False,
            # Der Editor baut nur Schriftfelder in Bloecken - die feste
            # Aufteilung der Mustertabellen stellt er nicht ein.
            schriftfeld_art="standard",
            schriftfeld=schriftfeld,
            schriftfeld_anteile=anteile,
            name=self.name.text().strip(),
            beschreibung=self.beschreibung.text().strip(),
            buchten_je_blatt=self.buchten.value(),
            spalten=tuple(self.spaltenliste()),
            eigene_felder=self.eigenefelder(),
            eigene_felder_auf=tuple(
                art for art, haken in self.eigene_auf.items() if haken.isChecked()
            ),
            **{
                feld: (wert.value() if wert.decimals() else int(wert.value()))
                for feld, wert in self.zahlen.items()
            },
            **{feld: haken.isChecked() for feld, haken in self.schalter.items()},
        )

    def _geaendert(self, *_args) -> None:
        self.geaendert = True
        self.takt.start()

    def _neu_zeichnen(self) -> None:
        """Prueft die Vorlage wie eine Datei und zeichnet die Blaetter neu."""
        try:
            vorlage = self.vorlage()
            # Der Name geht mit durch die Pruefung: ein leerer faellt sonst
            # erst beim Speichern auf.
            probe = dataclasses.replace(vorlage, id="probe")
            blattvorlage_aus_yaml(blattvorlage_als_yaml(probe), u("Blattvorlagen-Editor"))
            self.blaetter = blaetter(self.projekt, vorlage)
        except Exception as fehler:  # noqa: BLE001 - beim Ausprobieren darf nichts abstuerzen
            self.meldung.setText(str(fehler))
            self._speicherknoepfe(False)
            return
        self.meldung.setText("")
        self._speicherknoepfe(True)
        stelle = self.blattwahl.currentIndex()
        self.blattwahl.blockSignals(True)
        self.blattwahl.clear()
        self.blattwahl.addItems([blatt.titel for blatt in self.blaetter])
        self.blattwahl.setCurrentIndex(min(max(stelle, 0), len(self.blaetter) - 1))
        self.blattwahl.blockSignals(False)
        self._blatt_zeigen(self.blattwahl.currentIndex())

    def _blatt_zeigen(self, index: int) -> None:
        self.flaeche.blatt_setzen(
            self.blaetter[index] if 0 <= index < len(self.blaetter) else None
        )

    def _schieben(self, richtung: int) -> None:
        neu = self.blattwahl.currentIndex() + richtung
        if 0 <= neu < self.blattwahl.count():
            self.blattwahl.setCurrentIndex(neu)

    # -- Speichern und Schliessen -------------------------------------------

    def vorlagendatei(self, kennung: str = "") -> pathlib.Path | None:
        """Die Datei dieser Vorlage im Arbeitsordner - oder None.

        Nur was dort liegt, laesst sich bearbeiten: die eingebaute Vorgabe
        steht im Programm, und in einen mitgelieferten Ordner neben dem
        Abbild wird nicht geschrieben.
        """
        ordner = self.programm.blattvorlagenordner()
        kennung = kennung or self.basis.id
        if ordner is None or not kennung:
            return None
        datei = pathlib.Path(ordner) / f"{kennung}.yaml"
        return datei if datei.is_file() else None

    def _speicherknoepfe(self, gueltig: bool) -> None:
        """Speichern geht nur, was auch als Datei taugt - und nur in eine eigene."""
        self.speichern_knopf.setEnabled(gueltig)
        self.ueberschreiben_knopf.setEnabled(
            gueltig and self.vorlagendatei() is not None
        )

    def ueberschreiben(self) -> str | None:
        """Schreibt die Aenderungen in die Datei der geladenen Vorlage."""
        datei = self.vorlagendatei()
        if datei is None:
            return None
        vorlage = dataclasses.replace(
            self.vorlage(),
            id=self.basis.id,
            # Welche Vorlage die Vorgabe ist, sagt die Datei weiter - der
            # Editor stellt das nicht um.
            standard=self.basis.standard,
        )
        try:
            ziel = blattvorlage_speichern(
                vorlage, datei.parent, ueberschreiben=True
            )
        except Exception as fehler:  # noqa: BLE001 - Platte voll, keine Rechte ...
            QMessageBox.critical(self, u("Speichern fehlgeschlagen"), str(fehler))
            return None
        self.programm.blattvorlagen_neu_laden()
        self.gespeichert.append(vorlage.id)
        self._basisliste_fuellen(vorlage.id)
        self.programm.meldung(
            u("Blattvorlage „{0}“ gespeichert ({1})").format(vorlage.name, ziel.name)
        )
        return vorlage.id

    def speichern(self, name: str | None = None) -> str | None:
        """Speichert als neue Vorlage und gibt ihre Kennung zurueck."""
        if name is None:
            name, genommen = QInputDialog.getText(
                self, u("Als neue Vorlage speichern"), u("Name der neuen Blattvorlage:"),
                text=self.name.text().strip() + " – " + u("angepasst"),
            )
            if not genommen:
                return None
        name = name.strip()
        ordner = self.programm.blattvorlagenordner()
        if not name or ordner is None:
            return None
        vergeben = {vorlage.id for vorlage in self.programm.blattvorlagen().alle}
        vorlage = dataclasses.replace(
            self.vorlage(), id=freie_kennung(name, vergeben, ordner), name=name
        )
        try:
            ziel = blattvorlage_speichern(vorlage, ordner)
        except Exception as fehler:  # noqa: BLE001 - Platte voll, keine Rechte ...
            QMessageBox.critical(self, u("Speichern fehlgeschlagen"), str(fehler))
            return None
        self.programm.blattvorlagen_neu_laden()
        self.gespeichert.append(vorlage.id)
        self._basisliste_fuellen(vorlage.id)
        self.programm.meldung(
            u("Blattvorlage „{0}“ gespeichert ({1}) — zu wählen unter "
              "Einstellungen ▸ Blattvorlage").format(name, ziel.name)
        )
        return vorlage.id

    def showEvent(self, ereignis) -> None:  # noqa: N802 - Qt-Name
        """Meldet das Hauptfenster als Eltern an - sonst faellt der Editor dahinter.

        Ein Fenster der Art ``Window`` traegt die Angabe nicht von selbst,
        anders als ein Dialog.
        """
        super().showEvent(ereignis)
        eltern = self.parentWidget()
        eigenes = self.windowHandle()
        if eltern is not None and eigenes is not None:
            eigenes.setTransientParent(eltern.window().windowHandle())

    def _verwerfen_erlaubt(self) -> bool:
        antwort = frage(
            self, u("Blattvorlagen-Editor"),
            u("Die Änderungen sind noch nicht gespeichert. Verwerfen?"),
            Knopf.Discard | Knopf.Cancel, Knopf.Cancel,
        )
        return antwort == Knopf.Discard

    def reject(self) -> None:
        if self.geaendert and not self._verwerfen_erlaubt():
            return
        super().reject()
