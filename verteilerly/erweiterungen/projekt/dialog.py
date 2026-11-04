"""Der Dialog zum Anlegen eines Projekts: die Liste links, die Daten rechts.

Links steht, **was** entsteht: der Zielordner, die Geometrie (einmal
fuer alle - ein Projekt besteht meist aus gleichen Verteilern), die
Liste der Verteiler und die Beilagen. Rechts stehen die
**Projektdaten**, und zwar dieselben Felder wie im Dialog *Neuer
Verteiler*: dasselbe Bauteil (``ProjektdatenFelder``), damit beide
Wege nicht auseinanderlaufen. Gezeigt wird, was die gerade gewaehlte
Blattvorlage fuehrt; was sie nicht fuehrt, geht als **abgewaehlt** in
jedes Projekt - genau wie beim neuen Verteiler.

**Die Spalte Ordner folgt dem Namen, bis jemand sie anfasst** - dasselbe
Muster wie bei den Adernfarben: was die Automatik gesetzt hat, darf sie
auch wieder aendern, was von Hand kommt, bleibt stehen.

Der Plan wird bei jeder Aenderung neu gerechnet (``anlage.planen()``,
ohne Qt) und steht in der letzten Spalte: dort steht der Ordner, der
entstehen soll - oder der Grund, warum diese Zeile nicht geht.
Angelegt wird erst auf *Anlegen*.
"""

from __future__ import annotations

import pathlib

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ... import einstellungen as einstellungsspeicher
from ...layout import briefkopffelder
from ...modell import BRIEFKOPF_FELDER, Projekt, Verteiler
from ...sprachen import u
from ...vorlagen import Vorlagen
from ...gui.dialoge import ProjektdatenFelder
from ...gui.passform import PassenderDialog
from . import ProjektAnlegen
from .anlage import Angabe, Beilage, ablagename, anlegen, planen

#: Die Spalten der Verteilerliste.
NAME, NUMMER, ABLAGE, STAND = range(4)
#: Die Spalten der Beilagenliste.
UNTERORDNER, QUELLE = range(2)

#: So viele leere Zeilen stehen am Anfang in der Liste.
ZEILEN_ANFANGS = 3
#: Hoehe einer Zeile in beiden Listen.
ZEILENHOEHE = 26


class ProjektDialog(PassenderDialog):
    """Mehrere Verteiler mit denselben Projektdaten anlegen."""

    def __init__(self, programm, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(u("Projekt anlegen"))
        self.programm = programm
        self.einstellungen = programm.einstellungen()
        self.vorlagen = programm.vorlagen() or Vorlagen([])
        #: Waehrend der Dialog selbst in die Listen schreibt, hoert er
        #: nicht auf ``itemChanged`` - sonst rechnete er sich im Kreis.
        self._fuellt = False

        self.ziel = QLineEdit(ProjektAnlegen.zielordner(self.einstellungen))
        self.ziel.setPlaceholderText(u("Ordner, in dem das Projekt entsteht"))
        self.ziel.textChanged.connect(self._vorschau_auffrischen)
        self.zielknopf = QPushButton(u("Durchsuchen…"))
        self.zielknopf.clicked.connect(self._ziel_waehlen)
        self.ordnerknopf = QPushButton(u("Ordner öffnen"))
        self.ordnerknopf.clicked.connect(self._ziel_oeffnen)
        zielzeile = QHBoxLayout()
        zielzeile.addWidget(self.ziel, 1)
        zielzeile.addWidget(self.zielknopf)
        zielzeile.addWidget(self.ordnerknopf)

        # Die Geometrie gilt fuer alle Zeilen: ein Projekt besteht in der
        # Regel aus gleichen Verteilern. Wer einen anderen braucht, legt
        # ihn hinterher einzeln an.
        self.vorlagenwahl = QComboBox()
        for vorlage in self.vorlagen.alle:
            self.vorlagenwahl.addItem(str(vorlage), vorlage.id)
        self.vorlagenwahl.addItem(u("Benutzerdefiniert"), "")
        if len(self.vorlagen):
            stelle = self.vorlagenwahl.findData(self.vorlagen.standard.id)
            self.vorlagenwahl.setCurrentIndex(max(stelle, 0))
        self.vorlagenwahl.currentIndexChanged.connect(self._geometrie_umschalten)

        self.buchten = QSpinBox()
        self.buchten.setRange(1, 20)
        self.leisten = QSpinBox()
        self.leisten.setRange(1, 60)
        self.leisten.setValue(4)
        self.da = QSpinBox()
        self.da.setRange(1, 100)
        self.da.setValue(10)
        self.da.setSuffix(u(" DA"))
        eigenform = QFormLayout()
        eigenform.setContentsMargins(0, 0, 0, 0)
        eigenform.addRow(u("Buchten:"), self.buchten)
        eigenform.addRow(u("Leisten je Bucht:"), self.leisten)
        eigenform.addRow(u("DA je Leiste:"), self.da)
        self.eigenblock = QWidget()
        self.eigenblock.setLayout(eigenform)

        geometrie = QVBoxLayout()
        geometrie.addWidget(self.vorlagenwahl)
        geometrie.addWidget(self.eigenblock)
        geometriekasten = QGroupBox(u("Geometrie — für jeden Verteiler dieselbe"))
        geometriekasten.setLayout(geometrie)
        self._geometrie_umschalten()

        self.tabelle = QTableWidget(0, 4)
        self.tabelle.setHorizontalHeaderLabels(
            [u("Verteilername"), u("Verteilernummer"), u("Ordner"), u("Wird angelegt")]
        )
        self.tabelle.verticalHeader().setDefaultSectionSize(ZEILENHOEHE)
        self.tabelle.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.tabelle.setToolTip(
            u("Je Zeile ein Verteiler. Die Spalte Ordner folgt Name und "
              "Nummer, solange niemand sie ändert.")
        )
        self.tabelle.itemChanged.connect(self._zelle_geaendert)
        for _ in range(ZEILEN_ANFANGS):
            self.zeile_anhaengen()

        zeilenknopf = QPushButton(u("Zeile hinzufügen"))
        zeilenknopf.clicked.connect(lambda: self.zeile_anhaengen())
        self.zeileweg = QPushButton(u("Zeile entfernen"))
        self.zeileweg.clicked.connect(self._zeile_entfernen)
        zeilenknoepfe = QHBoxLayout()
        zeilenknoepfe.addWidget(zeilenknopf)
        zeilenknoepfe.addWidget(self.zeileweg)
        zeilenknoepfe.addStretch(1)

        self.eigener_ordner_haken = QCheckBox(
            u("Für jeden Verteiler einen eigenen Ordner")
        )
        self.eigener_ordner_haken.setToolTip(
            u("Ohne Haken liegen alle Projektdateien nebeneinander im "
              "Zielordner, und die Beilagen kommen einmal dazu.")
        )
        self.eigener_ordner_haken.setChecked(
            ProjektAnlegen.eigener_ordner(self.einstellungen)
        )
        self.eigener_ordner_haken.toggled.connect(self._vorschau_auffrischen)

        verteilerblock = QVBoxLayout()
        verteilerblock.addWidget(self.tabelle, 1)
        verteilerblock.addLayout(zeilenknoepfe)
        verteilerblock.addWidget(self.eigener_ordner_haken)
        verteilerkasten = QGroupBox(u("Verteiler"))
        verteilerkasten.setLayout(verteilerblock)

        # Die Beilagen: was in jedem Projektordner liegen soll. Der
        # Bestand steht in der Conf und gilt beim naechsten Mal wieder.
        self.beilagentabelle = QTableWidget(0, 2)
        self.beilagentabelle.setHorizontalHeaderLabels(
            [u("Unterordner"), u("Datei oder Ordner")]
        )
        self.beilagentabelle.verticalHeader().setDefaultSectionSize(ZEILENHOEHE)
        self.beilagentabelle.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.beilagentabelle.setToolTip(
            u("Unterordner leer heißt: unmittelbar in den Projektordner. "
              "Von einem Ordner wandert sein Inhalt mit.")
        )
        self.beilagentabelle.itemChanged.connect(self._zelle_geaendert)
        for beilage in ProjektAnlegen.beilagen(self.einstellungen):
            self.beilage_anhaengen(beilage)

        dateiknopf = QPushButton(u("Dateien hinzufügen…"))
        dateiknopf.clicked.connect(self._dateien_waehlen)
        ordnerwahl = QPushButton(u("Ordner hinzufügen…"))
        ordnerwahl.clicked.connect(self._beilagenordner_waehlen)
        self.beilageweg = QPushButton(u("Entfernen"))
        self.beilageweg.clicked.connect(self._beilage_entfernen)
        beilagenknoepfe = QHBoxLayout()
        beilagenknoepfe.addWidget(dateiknopf)
        beilagenknoepfe.addWidget(ordnerwahl)
        beilagenknoepfe.addWidget(self.beilageweg)
        beilagenknoepfe.addStretch(1)

        self.beilagenhinweis = QLabel()
        self.beilagenhinweis.setWordWrap(True)
        warnfarbe = getattr(programm.farben(), "warnung", "")
        if warnfarbe:
            self.beilagenhinweis.setStyleSheet(f"color: {warnfarbe}")
        beilagenblock = QVBoxLayout()
        beilagenblock.addWidget(self.beilagentabelle, 1)
        beilagenblock.addLayout(beilagenknoepfe)
        beilagenblock.addWidget(self.beilagenhinweis)
        beilagenkasten = QGroupBox(u("Beilagen — kommen in jeden Projektordner"))
        beilagenkasten.setLayout(beilagenblock)

        # Die Projektdaten: dasselbe Bauteil wie im Dialog Neuer
        # Verteiler, vorbelegt mit den gemerkten Vorgaben.
        gemerkt, ausgeblendet = einstellungsspeicher.briefkopf_laden(
            self.einstellungen
        )
        ausgeblendet = set(ausgeblendet) | {
            name for name in BRIEFKOPF_FELDER if not gemerkt.get(name)
        }
        self.projektdaten = ProjektdatenFelder(
            gemerkt, ausgeblendet,
            u("Projektdaten — für jeden Verteiler dieselben"),
        )
        self.blattvorlage = programm.blattvorlage()
        if self.blattvorlage is not None:
            self.projektdaten.nur_diese_zeigen(briefkopffelder(self.blattvorlage))

        # Die eigenen Felder der Blattvorlage: die Namen stehen dort, hier
        # werden sie gefuellt - fuer alle Verteiler gleich.
        self.eigene_namen = tuple(
            getattr(self.blattvorlage, "eigene_felder", ()) or ()
        )
        self.eigene = QTableWidget(0, 2)
        self.eigene.setHorizontalHeaderLabels([u("Feldname"), u("Inhalt")])
        self.eigene.verticalHeader().setVisible(False)
        self.eigene.horizontalHeader().setStretchLastSection(True)
        self.eigene.verticalHeader().setDefaultSectionSize(ZEILENHOEHE)
        for name in self.eigene_namen:
            zeile = self.eigene.rowCount()
            self.eigene.insertRow(zeile)
            feldname = QTableWidgetItem(name)
            feldname.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.eigene.setItem(zeile, 0, feldname)
            self.eigene.setItem(zeile, 1, QTableWidgetItem(""))
        eigenekasten = QGroupBox(u("Eigene Felder"))
        eigeneblock = QVBoxLayout()
        eigeneblock.addWidget(self.eigene)
        eigenekasten.setLayout(eigeneblock)
        eigenekasten.setVisible(bool(self.eigene_namen))

        rechts = QWidget()
        rechtsblock = QVBoxLayout(rechts)
        rechtsblock.setContentsMargins(0, 0, 0, 0)
        rechtsblock.addWidget(self.projektdaten)
        rechtsblock.addWidget(eigenekasten)
        rechtsblock.addStretch(1)
        rollbereich = QScrollArea()
        rollbereich.setWidget(rechts)
        rollbereich.setWidgetResizable(True)
        rollbereich.setFrameShape(QScrollArea.Shape.NoFrame)
        rollbereich.setMinimumHeight(240)

        self.summe = QLabel()
        self.summe.setWordWrap(True)

        zielform = QFormLayout()
        zielform.addRow(u("Zielordner:"), zielzeile)
        links = QVBoxLayout()
        links.setContentsMargins(0, 0, 0, 0)
        links.addLayout(zielform)
        links.addWidget(geometriekasten)
        links.addWidget(verteilerkasten, 1)
        links.addWidget(beilagenkasten, 1)
        links.addWidget(self.summe)

        nebeneinander = QHBoxLayout()
        nebeneinander.setContentsMargins(0, 0, 0, 0)
        nebeneinander.addLayout(links, 5)
        nebeneinander.addWidget(rollbereich, 4)

        self.knoepfe = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.anlegenknopf = self.knoepfe.button(QDialogButtonBox.StandardButton.Ok)
        self.anlegenknopf.setText(u("Anlegen"))
        self.knoepfe.button(QDialogButtonBox.StandardButton.Cancel).setText(
            u("Abbrechen")
        )
        self.knoepfe.accepted.connect(self.accept)
        self.knoepfe.rejected.connect(self.reject)

        inhalt = QWidget()
        aufbau = QVBoxLayout(inhalt)
        aufbau.addLayout(nebeneinander, 1)
        self.resize(1060, 680)
        self.inhalt_rollbar(inhalt, self.knoepfe)
        self._vorschau_auffrischen()

    # -- Zielordner ----------------------------------------------------------

    def zielordner(self) -> pathlib.Path | None:
        text = self.ziel.text().strip()
        return pathlib.Path(text).expanduser() if text else None

    def _ziel_waehlen(self) -> None:
        name = QFileDialog.getExistingDirectory(
            self, u("Zielordner wählen"), self.ziel.text().strip()
        )
        if name:
            self.ziel.setText(name)

    def _ziel_oeffnen(self) -> None:
        """Zeigt den Zielordner im Dateiverwalter - vorher und nachher."""
        ordner = self.zielordner()
        if ordner is not None and ordner.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(ordner)))

    # -- Geometrie -----------------------------------------------------------

    def _geometrie_umschalten(self, *_args) -> None:
        self.eigenblock.setVisible(not self.vorlagenwahl.currentData())

    def verteiler(self, angabe: Angabe) -> Verteiler:
        """Der Verteiler zu einer Zeile - aus Vorlage oder eigener Geometrie."""
        name, nummer = angabe.name.strip(), angabe.nummer.strip()
        kennung = self.vorlagenwahl.currentData()
        if kennung:
            return self.vorlagen.holen(kennung).verteiler(name, nummer)
        return Verteiler.aus_geometrie(
            self.buchten.value(), self.leisten.value(), self.da.value(),
            name, nummer,
        )

    # -- Die Verteilerliste --------------------------------------------------

    def zeile_anhaengen(self, name: str = "", nummer: str = "") -> int:
        zeile = self.tabelle.rowCount()
        self._fuellt = True
        self.tabelle.insertRow(zeile)
        for spalte, wert in ((NAME, name), (NUMMER, nummer), (ABLAGE, "")):
            self.tabelle.setItem(zeile, spalte, QTableWidgetItem(wert))
        stand = QTableWidgetItem("")
        stand.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self.tabelle.setItem(zeile, STAND, stand)
        self._fuellt = False
        self._ablage_nachziehen(zeile)
        return zeile

    def _zeile_entfernen(self) -> None:
        zeile = self.tabelle.currentRow()
        if zeile < 0:
            zeile = self.tabelle.rowCount() - 1
        if zeile >= 0:
            self.tabelle.removeRow(zeile)
            self._vorschau_auffrischen()

    def _text(self, tabelle: QTableWidget, zeile: int, spalte: int) -> str:
        eintrag = tabelle.item(zeile, spalte)
        return eintrag.text().strip() if eintrag is not None else ""

    def angabe(self, zeile: int) -> Angabe:
        return Angabe(
            self._text(self.tabelle, zeile, NAME),
            self._text(self.tabelle, zeile, NUMMER),
            self._text(self.tabelle, zeile, ABLAGE),
        )

    def angaben(self) -> list[Angabe]:
        return [self.angabe(zeile) for zeile in range(self.tabelle.rowCount())]

    def _ablage_nachziehen(self, zeile: int) -> None:
        """Der Ordnername folgt Name und Nummer - bis jemand ihn anfasst.

        Massstab ist der eigene Vorschlag von vorhin: steht er noch so da,
        gehoert die Zelle der Automatik; steht etwas anderes, war jemand
        von Hand da, und das bleibt.
        """
        feld = self.tabelle.item(zeile, ABLAGE)
        if feld is None:
            return
        voriger = feld.data(Qt.ItemDataRole.UserRole) or ""
        if feld.text().strip() and feld.text().strip() != voriger:
            return
        angabe = self.angabe(zeile)
        neu = ablagename(Angabe(angabe.name, angabe.nummer))
        self._fuellt = True
        feld.setText(neu)
        feld.setData(Qt.ItemDataRole.UserRole, neu)
        self._fuellt = False

    # -- Die Beilagen --------------------------------------------------------

    def beilage_anhaengen(self, beilage: Beilage) -> int:
        zeile = self.beilagentabelle.rowCount()
        self._fuellt = True
        self.beilagentabelle.insertRow(zeile)
        self.beilagentabelle.setItem(
            zeile, UNTERORDNER, QTableWidgetItem(beilage.unterordner)
        )
        quelle = QTableWidgetItem(str(beilage.quelle))
        # Die Quelle wird gewaehlt, nicht getippt - ein vertippter Pfad
        # waere ein stiller Fehler.
        quelle.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        quelle.setToolTip(str(beilage.quelle))
        self.beilagentabelle.setItem(zeile, QUELLE, quelle)
        self._fuellt = False
        return zeile

    def beilagen(self) -> list[Beilage]:
        return [
            Beilage(
                pathlib.Path(self._text(self.beilagentabelle, zeile, QUELLE)),
                self._text(self.beilagentabelle, zeile, UNTERORDNER),
            )
            for zeile in range(self.beilagentabelle.rowCount())
            if self._text(self.beilagentabelle, zeile, QUELLE)
        ]

    def _dateien_waehlen(self) -> None:
        namen, _ = QFileDialog.getOpenFileNames(
            self, u("Dateien für jeden Projektordner"), self.ziel.text().strip()
        )
        for name in namen:
            self.beilage_anhaengen(Beilage(pathlib.Path(name), self._fach()))
        if namen:
            self._vorschau_auffrischen()

    def _beilagenordner_waehlen(self) -> None:
        name = QFileDialog.getExistingDirectory(
            self, u("Ordner, dessen Inhalt mitwandert"), self.ziel.text().strip()
        )
        if not name:
            return
        # Der Name des Ordners ist der naheliegende Unterordner: wer
        # „Fotos" waehlt, will sie meist in „Fotos" wiederfinden.
        self.beilage_anhaengen(
            Beilage(pathlib.Path(name), self._fach() or pathlib.Path(name).name)
        )
        self._vorschau_auffrischen()

    def _fach(self) -> str:
        """Der Unterordner der markierten Zeile - als Vorgabe fuer die neue."""
        zeile = self.beilagentabelle.currentRow()
        if zeile < 0:
            return ""
        return self._text(self.beilagentabelle, zeile, UNTERORDNER)

    def _beilage_entfernen(self) -> None:
        zeile = self.beilagentabelle.currentRow()
        if zeile < 0:
            zeile = self.beilagentabelle.rowCount() - 1
        if zeile >= 0:
            self.beilagentabelle.removeRow(zeile)
            self._vorschau_auffrischen()

    # -- Der Plan ------------------------------------------------------------

    def plan(self):
        """Was angelegt werden soll - gerechnet, nicht geschrieben."""
        return planen(
            self.angaben(),
            self.zielordner() or pathlib.Path(),
            self.beilagen(),
            self.eigener_ordner_haken.isChecked(),
        )

    def _zelle_geaendert(self, eintrag: QTableWidgetItem) -> None:
        if self._fuellt:
            return
        if eintrag.tableWidget() is self.tabelle and eintrag.column() in (NAME, NUMMER):
            self._ablage_nachziehen(eintrag.row())
        self._vorschau_auffrischen()

    def _vorschau_auffrischen(self, *_args) -> None:
        """Schreibt in die letzte Spalte, was aus jeder Zeile wird."""
        ziel = self.zielordner()
        angaben = self.angaben()
        plan = self.plan()
        # ``planen`` geht die Angaben in dieser Reihenfolge durch und
        # laesst nur die leeren Zeilen weg - so findet jede Zeile ihre.
        lauf = 0
        self._fuellt = True
        for zeile, angabe in enumerate(angaben):
            stand = self.tabelle.item(zeile, STAND)
            if stand is None:
                continue
            if angabe.leer:
                stand.setText("")
                stand.setToolTip("")
                continue
            anlage = plan[lauf]
            lauf += 1
            text = anlage.grund if not anlage.geht else self._wohin(anlage, ziel)
            stand.setText(text)
            stand.setToolTip(str(anlage.datei))
        self._fuellt = False

        fehlende = [beilage for beilage in self.beilagen() if beilage.fehlt]
        self.beilagenhinweis.setText(
            u("Nicht zu finden: {0}").format(
                ", ".join(str(beilage.quelle) for beilage in fehlende)
            )
            if fehlende else ""
        )

        geht = [anlage for anlage in plan if anlage.geht]
        dateien = sum(len(anlage.dateien) for anlage in geht)
        if ziel is None:
            self.summe.setText(u("Erst einen Zielordner wählen."))
        elif not plan:
            self.summe.setText(u("Noch kein Verteiler eingetragen."))
        elif not geht:
            self.summe.setText(u("Keine Zeile geht — die Gründe stehen rechts."))
        else:
            self.summe.setText(
                u("Angelegt werden {0} Verteiler und {1} Dateien dazu.").format(
                    len(geht), dateien
                )
            )
        self.anlegenknopf.setEnabled(ziel is not None and bool(geht))

    def _wohin(self, anlage, ziel) -> str:
        """Wo die Projektdatei landet - kurz, vom Zielordner aus gesehen.

        Ohne Zielordner und bei einem eigenen Pfad in der Spalte steht
        der ganze Weg da: lieber lang als falsch.
        """
        if ziel is None:
            return str(anlage.datei)
        try:
            return str(anlage.datei.relative_to(ziel))
        except ValueError:
            return str(anlage.datei)

    # -- Projektdaten und Ausfuehren -----------------------------------------

    def eigene_werte(self) -> dict[str, str]:
        """Die Inhalte der eigenen Felder - leere bleiben weg."""
        werte = {}
        for zeile in range(self.eigene.rowCount()):
            name = self._text(self.eigene, zeile, 0)
            wert = self._text(self.eigene, zeile, 1)
            if name and wert:
                werte[name] = wert
        return werte

    def projekt_fuer(self, angabe: Angabe) -> Projekt:
        """Ein Projekt zu dieser Zeile: eigener Verteiler, dieselben Daten.

        Jedes bekommt seine **eigenen** Sammlungen - zwei Projekte, die
        sich einen Briefkopf teilen, waeren eine Falle fuer den
        naechsten, der hier etwas aendert. Was diese Blattvorlage nicht
        fuehrt, ist abgewaehlt: das Feld stand nicht zur Eingabe, also
        soll es auf keinem Blatt stehen - wie beim neuen Verteiler.
        """
        return Projekt(
            verteiler=self.verteiler(angabe),
            briefkopf=dict(self.projektdaten.werte()),
            eigene_felder=dict(self.eigene_werte()),
            ausgeblendet=set(self.projektdaten.ausgeblendet())
            | set(self.projektdaten.verborgene()),
        )

    def ausfuehren(self):
        """Legt an, was der Plan sagt - und gibt den Bericht zurueck."""
        return anlegen(self.plan(), self.projekt_fuer)
