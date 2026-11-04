"""Der Dialog zum Anlegen eines Projekts: die Liste links, die Daten rechts.

Links steht, **was** entsteht: der Projektordner, die Liste der
Verteiler und die Beilagen, die einmal in den Projektordner kommen.

**Die Geometrie steht in der Zeile**, nicht ueber der Liste: ein Projekt
besteht nicht aus gleichen Verteilern. Je Zeile ein Auswahlfeld mit den
Verteilervorlagen und *Benutzerdefiniert…*, das nach drei Zahlen fragt
und sie als eigenen Eintrag in dieses Feld legt. Eine **neue Zeile erbt
die Wahl der letzten** - das Haeufige ist damit ein Griff, das
Abweichende einer mehr. Rechts stehen die
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
from ...modell import BRIEFKOPF_FELDER, Projekt, Verteiler, mehrzahl
from ...sprachen import u
from ...vorlagen import Vorlagen
from ...gui.dialoge import ProjektdatenFelder
from ...gui.passform import PassenderDialog
from . import ProjektAnlegen
from .anlage import Angabe, Beilage, ablagename, anlegen, planen

#: Die Spalten der Verteilerliste.
NAME, NUMMER, GEOMETRIE, ABLAGE, STAND = range(5)
#: Die Spalten der Beilagenliste.
UNTERORDNER, QUELLE = range(2)

#: So viele leere Zeilen stehen am Anfang in der Liste.
ZEILEN_ANFANGS = 3
#: Hoehe einer Zeile in beiden Listen - ein Auswahlfeld braucht Luft.
ZEILENHOEHE = 30

#: Was im Auswahlfeld der Geometrie steht: eine Verteilervorlage, ein
#: eigener Bauplan, oder die Aufforderung, nach Zahlen zu fragen.
VORLAGE, PLAN, EIGEN = "vorlage", "plan", "eigen"

#: Womit der Dialog fuer eine eigene Geometrie anfaengt.
BUCHTEN_VORGABE, LEISTEN_VORGABE, DA_VORGABE = 1, 4, 10


def bauplantext(bauplan) -> str:
    """Ein Bauplan in einer Zeile - gleichmaessig kurz, sonst aufgezaehlt."""
    gesamt = sum(leisten * da for leisten, da in bauplan)
    if len(set(bauplan)) == 1:
        leisten, da = bauplan[0]
        return u("{0} × {1} zu {2} DA ({3} DA)").format(
            mehrzahl(len(bauplan), "Bucht", "Buchten"),
            mehrzahl(leisten, "Leiste", "Leisten"), da, gesamt,
        )
    return u("{0}, {1} DA").format(
        mehrzahl(len(bauplan), "Bucht", "Buchten"), gesamt
    )


class GeometrieDialog(PassenderDialog):
    """Drei Zahlen fuer **eine** Zeile der Liste.

    Mehr als drei gibt es hier nicht: eine ungleich besetzte Anlage
    gehoert in eine Verteilervorlage (*Neuer Verteiler ▸ Als Vorlage
    speichern*), dann steht sie jedem Projekt zur Wahl.
    """

    def __init__(self, bauplan=(), parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(u("Eigene Geometrie"))
        buchten, leisten, da = BUCHTEN_VORGABE, LEISTEN_VORGABE, DA_VORGABE
        if bauplan and len(set(bauplan)) == 1:
            buchten, (leisten, da) = len(bauplan), bauplan[0]
        self.buchten = QSpinBox()
        self.buchten.setRange(1, 20)
        self.buchten.setValue(buchten)
        self.leisten = QSpinBox()
        self.leisten.setRange(1, 60)
        self.leisten.setValue(leisten)
        self.da = QSpinBox()
        self.da.setRange(1, 100)
        self.da.setValue(da)
        self.da.setSuffix(u(" DA"))
        self.summe = QLabel()
        for feld in (self.buchten, self.leisten, self.da):
            feld.valueChanged.connect(self._summe_zeigen)

        knoepfe = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        knoepfe.button(QDialogButtonBox.StandardButton.Ok).setText(u("Übernehmen"))
        knoepfe.button(QDialogButtonBox.StandardButton.Cancel).setText(
            u("Abbrechen")
        )
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)

        aufbau = QFormLayout(self)
        aufbau.addRow(u("Buchten:"), self.buchten)
        aufbau.addRow(u("Leisten je Bucht:"), self.leisten)
        aufbau.addRow(u("DA je Leiste:"), self.da)
        aufbau.addRow("", self.summe)
        aufbau.addRow(knoepfe)
        self._summe_zeigen()

    def _summe_zeigen(self) -> None:
        self.summe.setText(bauplantext(self.bauplan()))

    def bauplan(self) -> tuple[tuple[int, int], ...]:
        return ((self.leisten.value(), self.da.value()),) * self.buchten.value()


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

        self.ordnerfeld = QLineEdit(ProjektAnlegen.projektordner(self.einstellungen))
        self.ordnerfeld.setPlaceholderText(u("Ordner, in dem das Projekt entsteht"))
        self.ordnerfeld.textChanged.connect(self._vorschau_auffrischen)
        self.suchknopf = QPushButton(u("Durchsuchen…"))
        self.suchknopf.clicked.connect(self._ordner_waehlen)
        self.ordnerknopf = QPushButton(u("Ordner öffnen"))
        self.ordnerknopf.clicked.connect(self._ordner_oeffnen)
        ordnerzeile = QHBoxLayout()
        ordnerzeile.addWidget(self.ordnerfeld, 1)
        ordnerzeile.addWidget(self.suchknopf)
        ordnerzeile.addWidget(self.ordnerknopf)

        self.tabelle = QTableWidget(0, 5)
        self.tabelle.setHorizontalHeaderLabels(
            [u("Verteilername"), u("Verteilernummer"), u("Geometrie"),
             u("Ordner"), u("Wird angelegt")]
        )
        self.tabelle.verticalHeader().setDefaultSectionSize(ZEILENHOEHE)
        kopf = self.tabelle.horizontalHeader()
        kopf.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # Die Nummer ist kurz - der Platz gehoert den anderen.
        kopf.setSectionResizeMode(NUMMER, QHeaderView.ResizeMode.ResizeToContents)
        self.tabelle.setToolTip(
            u("Je Zeile ein Verteiler mit seiner eigenen Geometrie. Die "
              "Spalte Ordner folgt Name und Nummer, solange niemand sie "
              "ändert.")
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
              "Projektordner.")
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
        beilagenkasten = QGroupBox(u("Beilagen — kommen einmal in den Projektordner"))
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

        ordnerform = QFormLayout()
        ordnerform.addRow(u("Projektordner:"), ordnerzeile)
        links = QVBoxLayout()
        links.setContentsMargins(0, 0, 0, 0)
        links.addLayout(ordnerform)
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

    # -- Der Projektordner ---------------------------------------------------

    def projektordner(self) -> pathlib.Path | None:
        text = self.ordnerfeld.text().strip()
        return pathlib.Path(text).expanduser() if text else None

    def _ordner_waehlen(self) -> None:
        name = QFileDialog.getExistingDirectory(
            self, u("Projektordner wählen"), self.ordnerfeld.text().strip()
        )
        if name:
            self.ordnerfeld.setText(name)

    def _ordner_oeffnen(self) -> None:
        """Zeigt den Projektordner im Dateiverwalter - vorher und nachher."""
        ordner = self.projektordner()
        if ordner is not None and ordner.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(ordner)))

    # -- Geometrie je Zeile --------------------------------------------------

    def _geometriefeld(self, erben_von: int = -1) -> QComboBox:
        """Das Auswahlfeld einer Zeile: die Vorlagen und ein eigener Weg.

        ``erben_von`` ist die Zeile, deren Wahl die neue uebernimmt - in
        der Regel die letzte. Ein eigener Bauplan wird dabei
        mituebernommen: wer zwei gleiche Sonderlinge eintraegt, soll die
        Zahlen nicht zweimal tippen.
        """
        feld = QComboBox()
        for vorlage in self.vorlagen.alle:
            feld.addItem(str(vorlage), (VORLAGE, vorlage.id))
        vorbild = (
            self.tabelle.cellWidget(erben_von, GEOMETRIE)
            if erben_von >= 0 else None
        )
        geerbt = vorbild.currentData() if vorbild is not None else None
        if geerbt is not None and geerbt[0] == PLAN:
            feld.addItem(bauplantext(geerbt[1]), geerbt)
        feld.addItem(u("Benutzerdefiniert…"), (EIGEN, None))
        if geerbt is not None:
            stelle = feld.findData(geerbt)
            feld.setCurrentIndex(max(stelle, 0))
        elif len(self.vorlagen):
            stelle = feld.findData((VORLAGE, self.vorlagen.standard.id))
            feld.setCurrentIndex(max(stelle, 0))
        else:
            # Ohne eine einzige Vorlage bleibt nur der eigene Weg.
            feld.setCurrentIndex(feld.count() - 1)
        feld.setProperty("zuletzt", feld.currentIndex())
        feld.currentIndexChanged.connect(
            lambda _stelle, f=feld: self._geometrie_gewechselt(f)
        )
        return feld

    def _geometrie_gewechselt(self, feld: QComboBox) -> None:
        """*Benutzerdefiniert…* fragt nach Zahlen, alles andere gilt sofort.

        Der Eintrag ist eine **Aufforderung, kein Zustand**: angenommen
        wird der Bauplan als eigener Eintrag darueber, abgebrochen steht
        wieder da, was vorher dastand - sonst zeigte das Feld eine
        Geometrie, die niemand gewaehlt hat.
        """
        daten = feld.currentData()
        if daten is None or daten[0] != EIGEN:
            feld.setProperty("zuletzt", feld.currentIndex())
            self._vorschau_auffrischen()
            return
        vorher = feld.property("zuletzt")
        voriger = feld.itemData(vorher) if vorher is not None else None
        dialog = GeometrieDialog(
            voriger[1] if voriger is not None and voriger[0] == PLAN else (),
            self,
        )
        if dialog.exec() != GeometrieDialog.DialogCode.Accepted:
            feld.setCurrentIndex(vorher if vorher is not None else 0)
            return
        self._eigenen_plan_setzen(feld, dialog.bauplan())

    def _eigenen_plan_setzen(self, feld: QComboBox, bauplan) -> None:
        """Legt den Bauplan als Eintrag vor *Benutzerdefiniert…* und waehlt ihn.

        Je Feld gibt es nur **einen** eigenen Eintrag: ein zweiter waere
        die vorige Eingabe, die niemand mehr sucht.
        """
        daten = (PLAN, tuple(bauplan))
        feld.blockSignals(True)
        for stelle in range(feld.count() - 1, -1, -1):
            if (feld.itemData(stelle) or ("", None))[0] == PLAN:
                feld.removeItem(stelle)
        feld.insertItem(feld.count() - 1, bauplantext(daten[1]), daten)
        feld.setCurrentIndex(feld.count() - 2)
        feld.setProperty("zuletzt", feld.currentIndex())
        feld.blockSignals(False)
        # Die Zeile hat eine andere Geometrie - die Vorschau soll es zeigen.
        self._vorschau_auffrischen()

    def bauplan(self, zeile: int) -> tuple[tuple[int, int], ...]:
        """Die Geometrie dieser Zeile, als Bauplan je Bucht."""
        feld = self.tabelle.cellWidget(zeile, GEOMETRIE)
        daten = feld.currentData() if feld is not None else None
        if daten is None:
            return ()
        art, wert = daten
        if art == PLAN:
            return tuple(wert)
        if art == VORLAGE and wert in self.vorlagen:
            return self.vorlagen.holen(wert).buchtenplan
        return ()

    def verteiler(self, angabe: Angabe) -> Verteiler:
        """Der Verteiler zu einer Zeile - nach ihrem eigenen Bauplan.

        Ohne Bauplan wirft ``aus_buchten`` einen ``ModellFehler``, und
        ``anlegen()`` schreibt ihn als Grund zu dieser Zeile - genau
        richtig: die anderen Verteiler gehen davon nichts an.
        """
        return Verteiler.aus_buchten(
            list(angabe.bauplan), angabe.name.strip(), angabe.nummer.strip()
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
        # Die Geometrie erbt die neue Zeile von der letzten.
        self.tabelle.setCellWidget(
            zeile, GEOMETRIE, self._geometriefeld(zeile - 1)
        )
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
            self.bauplan(zeile),
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
            self, u("Dateien für den Projektordner"), self.ordnerfeld.text().strip()
        )
        for name in namen:
            self.beilage_anhaengen(Beilage(pathlib.Path(name), self._fach()))
        if namen:
            self._vorschau_auffrischen()

    def _beilagenordner_waehlen(self) -> None:
        name = QFileDialog.getExistingDirectory(
            self, u("Ordner, dessen Inhalt mitwandert"), self.ordnerfeld.text().strip()
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
            self.projektordner() or pathlib.Path(),
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
        ordner = self.projektordner()
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
            anlage = plan.anlagen[lauf]
            lauf += 1
            text = anlage.grund if not anlage.geht else self._wohin(anlage, ordner)
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

        geht = plan.moegliche
        if ordner is None:
            self.summe.setText(u("Erst einen Projektordner wählen."))
        elif not plan.anlagen:
            self.summe.setText(u("Noch kein Verteiler eingetragen."))
        elif not geht:
            self.summe.setText(u("Keine Zeile geht — die Gründe stehen rechts."))
        else:
            self.summe.setText(
                u("Angelegt werden {0} Verteiler mit {1} DA, dazu {2} Dateien "
                  "im Projektordner.").format(
                    len(geht),
                    sum(anlage.angabe.da_gesamt for anlage in geht),
                    len(plan.dateien),
                )
            )
        self.anlegenknopf.setEnabled(ordner is not None and bool(geht))

    def _wohin(self, anlage, ordner) -> str:
        """Wo die Projektdatei landet - kurz, vom Projektordner aus gesehen.

        Ohne Projektordner und bei einem eigenen Pfad in der Spalte steht
        der ganze Weg da: lieber lang als falsch.
        """
        if ordner is None:
            return str(anlage.datei)
        try:
            return str(anlage.datei.relative_to(ordner))
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
