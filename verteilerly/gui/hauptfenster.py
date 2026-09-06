"""Hauptfenster von Verteilerly."""

from __future__ import annotations

import pathlib

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .. import pfade, projektdatei
from ..ausgabe import AusgabeFehler, csv_schreiben, pdf_schreiben, xlsx_schreiben
from ..farbcodes import Kabeltypen, farben_eintragen
from ..modell import Kabelabschnitt, ModellFehler, Projekt, UeberlaufFehler, Verteiler
from ..version import VERSION
from ..vorlagen import Vorlagen
from .dialoge import (
    BriefkopfDialog,
    KabelDialog,
    NeuerVerteilerDialog,
    UeberlaufDialog,
    als_vorlage_speichern,
)
from .leistenansicht import LeistenAnsicht
from .symbol import symbol_icon
from .thema import SAETZE, anwenden
from .uebersicht import Uebersicht
from .vorschau import Vorschau

DATEIFILTER = "Verteilerly-Projekt (*.vtly.json);;Alle Dateien (*)"
PDFFILTER = "PDF (*.pdf)"
XLSXFILTER = "Excel-Arbeitsmappe (*.xlsx)"
CSVFILTER = "CSV, Semikolon getrennt (*.csv)"
VORSCHAU_VERZUG = 250  # ms, damit das Tippen nicht stockt


class Hauptfenster(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.einstellungen = QSettings("Verteilerly", "Verteilerly")
        self._grundausstattung_sichern()
        self.vorlagen = self._vorlagen_laden()
        self.kabeltypen = Kabeltypen.laden(pfade.kabeltypenordner())

        self.projekt: Projekt | None = None
        self.pfad: pathlib.Path | None = None
        self.veraendert = False
        self.thema_name = str(self.einstellungen.value("thema", "hell"))

        self.setWindowIcon(symbol_icon())
        self._oberflaeche_bauen()
        self._aktionen_bauen()
        self.thema_anwenden(self.thema_name)
        self._projekt_setzen(None, None)
        if self.ausgelegt:
            self.statusBar().showMessage(
                f"{len(self.ausgelegt)} Dateien nach {pfade.eigener_datenordner()} "
                "ausgelegt — dort sind sie änderbar",
                12000,
            )

    # -- Aufbau ------------------------------------------------------------

    def _oberflaeche_bauen(self) -> None:
        self.uebersicht = Uebersicht()
        self.uebersicht.stelle_aktiviert.connect(self.kabel_auflegen)
        self.uebersicht.kabel_aktiviert.connect(self._kabel_angeklickt)
        self.uebersicht.auswahl_geaendert.connect(self._auswahl_gemeldet)

        rollbereich = QScrollArea()
        rollbereich.setWidget(self.uebersicht)
        rollbereich.setWidgetResizable(True)
        rollbereich.setFrameShape(QScrollArea.Shape.NoFrame)

        oben = QWidget()
        obenaufbau = QVBoxLayout(oben)
        obenaufbau.setContentsMargins(0, 0, 0, 0)
        obenaufbau.addWidget(rollbereich)

        self.leistenansicht = LeistenAnsicht()
        self.leistenansicht.belegung_geaendert.connect(self._belegung_geaendert)
        self.leistenansicht.fehler_gemeldet.connect(self._fehler_zeigen)
        self.leistenansicht.leiste_gewechselt.connect(self._leiste_gewechselt)

        self.teiler = QSplitter(Qt.Orientation.Vertical)
        self.teiler.addWidget(oben)
        self.teiler.addWidget(self.leistenansicht)
        self.teiler.setStretchFactor(0, 0)
        self.teiler.setStretchFactor(1, 1)
        self.teiler.setSizes([230, 470])

        # Die Vorschau steht neben der Eingabe, nicht hinter einem Export.
        self.vorschau = Vorschau()
        self.vorschau_takt = QTimer(self)
        self.vorschau_takt.setSingleShot(True)
        self.vorschau_takt.setInterval(VORSCHAU_VERZUG)
        self.vorschau_takt.timeout.connect(self._vorschau_auffrischen)

        self.hauptteiler = QSplitter(Qt.Orientation.Horizontal)
        self.hauptteiler.addWidget(self.teiler)
        self.hauptteiler.addWidget(self.vorschau)
        self.hauptteiler.setStretchFactor(0, 3)
        self.hauptteiler.setStretchFactor(1, 2)
        self.hauptteiler.setSizes([760, 520])

        self.setCentralWidget(self.hauptteiler)
        self.statusBar().showMessage("Bereit")
        self.resize(1320, 820)

    def _aktionen_bauen(self) -> None:
        datei = self.menuBar().addMenu("&Datei")
        werkzeuge = QToolBar("Werkzeuge")
        werkzeuge.setMovable(False)
        self.addToolBar(werkzeuge)

        def aktion(text, ausloeser, kuerzel=None, in_leiste=False, menue=datei):
            handlung = QAction(text, self)
            handlung.triggered.connect(ausloeser)
            if kuerzel:
                handlung.setShortcut(QKeySequence(kuerzel))
            menue.addAction(handlung)
            if in_leiste:
                werkzeuge.addAction(handlung)
            return handlung

        aktion("&Neuer Verteiler…", self.neuer_verteiler, "Ctrl+N", True)
        aktion("Ö&ffnen…", self.oeffnen, "Ctrl+O", True)
        aktion("&Speichern", self.speichern, "Ctrl+S", True)
        aktion("Speichern &unter…", self.speichern_unter, "Ctrl+Shift+S")
        datei.addSeparator()
        self.aktion_pdf = aktion("Als &PDF…", self.pdf_ausgeben, "Ctrl+E", True)
        self.aktion_xlsx = aktion("Als &Excel-Mappe…", self.xlsx_ausgeben)
        self.aktion_csv = aktion("Als &CSV…", self.csv_ausgeben)
        datei.addSeparator()
        aktion("&Beenden", self.close, "Ctrl+Q")

        bearbeiten = self.menuBar().addMenu("&Bearbeiten")
        werkzeuge.addSeparator()
        self.aktion_kabel = aktion(
            "&Kabel auflegen…", self.kabel_auflegen, "Ctrl+K", True, bearbeiten
        )
        self.aktion_kabel_weg = aktion(
            "Kabel &entfernen", self.kabel_entfernen, "Ctrl+Shift+K", True, bearbeiten
        )
        self.aktion_vorlage = aktion(
            "Als &Vorlage speichern…", self.vorlage_ablegen, menue=bearbeiten
        )
        bearbeiten.addSeparator()
        aktion(
            "&Briefkopf und eigene Felder…",
            self.briefkopf_bearbeiten,
            "Ctrl+B",
            True,
            bearbeiten,
        )

        ansicht = self.menuBar().addMenu("&Ansicht")
        self.aktion_thema = QAction("&Dunkles Erscheinungsbild", self)
        self.aktion_thema.setCheckable(True)
        self.aktion_thema.setChecked(self.thema_name == "dunkel")
        self.aktion_thema.setShortcut(QKeySequence("Ctrl+D"))
        self.aktion_thema.triggered.connect(
            lambda an: self.thema_anwenden("dunkel" if an else "hell")
        )
        ansicht.addAction(self.aktion_thema)

        self.aktion_vorschau = QAction("&Vorschau anzeigen", self)
        self.aktion_vorschau.setCheckable(True)
        self.aktion_vorschau.setShortcut(QKeySequence("F9"))
        self.aktion_vorschau.setChecked(
            self.einstellungen.value("vorschau", True, type=bool)
        )
        self.aktion_vorschau.triggered.connect(self.vorschau_zeigen)
        ansicht.addAction(self.aktion_vorschau)
        werkzeuge.addSeparator()
        werkzeuge.addAction(self.aktion_vorschau)
        self.vorschau_zeigen(self.aktion_vorschau.isChecked())

        hilfe = self.menuBar().addMenu("&Hilfe")
        aktion("Ü&ber Verteilerly", self.ueber, menue=hilfe)

    # -- Darstellung -------------------------------------------------------

    def thema_anwenden(self, name: str) -> None:
        """Umschalten zwischen hellem und dunklem Erscheinungsbild."""
        from PySide6.QtWidgets import QApplication

        farben = SAETZE.get(name, SAETZE["hell"])
        self.thema_name = farben.name
        anwenden(QApplication.instance(), farben)
        self.uebersicht.farben_setzen(farben)
        self.leistenansicht.farben_setzen(farben)
        self.vorschau.farben_setzen(farben)
        self.einstellungen.setValue("thema", self.thema_name)

    def _titel_setzen(self) -> None:
        teile = ["Verteilerly"]
        if self.projekt is not None:
            name = self.projekt.verteiler.name or "ohne Namen"
            teile.append(name if not self.pfad else f"{name} — {self.pfad.name}")
        if self.veraendert:
            teile.append("•")
        self.setWindowTitle("  ".join(teile))

    def _fehler_zeigen(self, text: str) -> None:
        self.statusBar().showMessage(text, 8000)

    def _auswahl_gemeldet(self, stelle) -> None:
        if stelle is None or self.projekt is None:
            return
        leiste, da = stelle
        self.leistenansicht.leiste_zeigen(leiste)
        kabel = self.projekt.verteiler.kabel_an(leiste, da)
        if kabel is not None:
            self.statusBar().showMessage(f"Leiste {leiste}, DA {da} — {kabel.beschriftung}")
        else:
            self.statusBar().showMessage(f"Leiste {leiste}, DA {da} — frei")

    def _belegung_geaendert(self) -> None:
        self.veraendert = True
        self.uebersicht.update()
        self._titel_setzen()
        self._vorschau_anstossen()

    def _leiste_gewechselt(self, nummer: int) -> None:
        """Die Vorschau folgt der bearbeiteten Leiste."""
        self.vorschau.blatt_zeigen(f"Leiste {nummer}")

    def vorschau_zeigen(self, an: bool) -> None:
        self.vorschau.setVisible(an)
        self.einstellungen.setValue("vorschau", bool(an))
        if an:
            self._vorschau_auffrischen()

    def _vorschau_anstossen(self) -> None:
        """Sammelt schnelle Aenderungen, statt bei jedem Tastendruck neu zu bauen."""
        if self.vorschau.isVisible():
            self.vorschau_takt.start()

    def _vorschau_auffrischen(self) -> None:
        self.vorschau.aktualisieren()
        nummer = self.leistenansicht.modell.leiste_nr
        if nummer is not None:
            self.vorschau.blatt_zeigen(f"Leiste {nummer}")

    # -- Projekt -----------------------------------------------------------

    def _projekt_setzen(self, projekt: Projekt | None, pfad: pathlib.Path | None) -> None:
        self.projekt = projekt
        self.pfad = pfad
        self.veraendert = False
        verteiler = projekt.verteiler if projekt else None
        self.uebersicht.verteiler_setzen(verteiler)
        self.leistenansicht.verteiler_setzen(verteiler)
        self.vorschau.projekt_setzen(projekt)
        for handlung in (
            self.aktion_kabel,
            self.aktion_kabel_weg,
            self.aktion_pdf,
            self.aktion_xlsx,
            self.aktion_csv,
            self.aktion_vorlage,
        ):
            handlung.setEnabled(projekt is not None)
        self._titel_setzen()

    def _darf_verwerfen(self) -> bool:
        if not self.veraendert:
            return True
        antwort = QMessageBox.question(
            self,
            "Änderungen verwerfen?",
            "Der Verteiler wurde geändert und noch nicht gespeichert.",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if antwort == QMessageBox.StandardButton.Save:
            return self.speichern()
        return antwort == QMessageBox.StandardButton.Discard

    def neuer_verteiler(self) -> None:
        if not self._darf_verwerfen():
            return
        dialog = NeuerVerteilerDialog(
            self.vorlagen, self, self._vorlagenordner()
        )
        if dialog.exec() != NeuerVerteilerDialog.DialogCode.Accepted:
            return
        self._projekt_setzen(Projekt(verteiler=dialog.verteiler()), None)
        self.statusBar().showMessage(
            f"Neuer Verteiler: {self.projekt.verteiler.da_gesamt} DA auf "
            f"{len(self.projekt.verteiler.alle_leisten)} Leisten"
        )

    def oeffnen(self) -> None:
        if not self._darf_verwerfen():
            return
        name, _ = QFileDialog.getOpenFileName(self, "Verteiler öffnen", "", DATEIFILTER)
        if not name:
            return
        try:
            projekt = projektdatei.laden(pathlib.Path(name))
        except (ModellFehler, OSError) as fehler:
            QMessageBox.critical(self, "Öffnen fehlgeschlagen", str(fehler))
            return
        self._projekt_setzen(projekt, pathlib.Path(name))
        self.statusBar().showMessage(f"Geöffnet: {name}")

    def speichern(self) -> bool:
        if self.projekt is None:
            return False
        if self.pfad is None:
            return self.speichern_unter()
        try:
            projektdatei.speichern(self.projekt, self.pfad)
        except OSError as fehler:
            QMessageBox.critical(self, "Speichern fehlgeschlagen", str(fehler))
            return False
        self.veraendert = False
        self._titel_setzen()
        self.statusBar().showMessage(f"Gespeichert: {self.pfad}")
        return True

    def speichern_unter(self) -> bool:
        if self.projekt is None:
            return False
        vorschlag = self.projekt.verteiler.name or "verteiler"
        name, _ = QFileDialog.getSaveFileName(
            self, "Verteiler speichern", f"{vorschlag}.vtly.json", DATEIFILTER
        )
        if not name:
            return False
        self.pfad = pathlib.Path(name)
        return self.speichern()

    # -- Ausgabe -----------------------------------------------------------

    def _ausgabeziel(self, endung: str, filter_: str) -> pathlib.Path | None:
        """Schlaegt den Projektnamen als Dateinamen vor."""
        if self.projekt is None:
            return None
        stamm = self.pfad.name.split(".")[0] if self.pfad else ""
        stamm = stamm or self.projekt.verteiler.name or "verteiler"
        ordner = self.pfad.parent if self.pfad else pathlib.Path.home()
        name, _ = QFileDialog.getSaveFileName(
            self, "Ausgeben nach", str(ordner / f"{stamm}{endung}"), filter_
        )
        return pathlib.Path(name) if name else None

    def pdf_ausgeben(self) -> None:
        """PDF ist das Pflichtformat."""
        ziel = self._ausgabeziel(".pdf", PDFFILTER)
        if ziel is None:
            return
        self._ausgeben(lambda: pdf_schreiben(self.projekt, ziel), ziel)

    def xlsx_ausgeben(self) -> None:
        ziel = self._ausgabeziel(".xlsx", XLSXFILTER)
        if ziel is None:
            return
        self._ausgeben(
            lambda: xlsx_schreiben(self.projekt, ziel), ziel
        )

    def csv_ausgeben(self) -> None:
        ziel = self._ausgabeziel(".csv", CSVFILTER)
        if ziel is None:
            return
        self._ausgeben(lambda: csv_schreiben(self.projekt, ziel), ziel)

    def _ausgeben(self, arbeit, ziel: pathlib.Path) -> None:
        try:
            arbeit()
        except (AusgabeFehler, OSError) as fehler:
            QMessageBox.critical(self, "Ausgabe fehlgeschlagen", str(fehler))
            return
        self.statusBar().showMessage(f"Geschrieben: {ziel}")

    # -- Kabel -------------------------------------------------------------

    def kabel_auflegen(self, leiste: int | None = None, start_da: int | None = None) -> None:
        """Kabel auflegen, samt Rückfrage bei Überlauf."""
        if self.projekt is None:
            return
        verteiler = self.projekt.verteiler
        if leiste is None or not isinstance(leiste, int):
            stelle = self.uebersicht.auswahl or (verteiler.alle_leisten[0].nummer, 1)
            leiste, start_da = stelle
        dialog = KabelDialog(verteiler, self.kabeltypen, leiste, start_da or 1, self)
        if dialog.exec() != KabelDialog.DialogCode.Accepted:
            return

        angaben = dialog.angaben()
        try:
            kabel = verteiler.kabel_anlegen(
                angaben["beschriftung"],
                angaben["leiste"],
                angaben["start_da"],
                angaben["anzahl_da"],
                kabeltyp=angaben["kabeltyp"],
                da_gesamt=angaben["da_gesamt"],
            )
        except UeberlaufFehler as ueberlauf:
            kabel = self._ueberlauf_klaeren(angaben, ueberlauf)
            if kabel is None:
                return
        except ModellFehler as fehler:
            QMessageBox.warning(self, "Kabel nicht aufgelegt", str(fehler))
            return

        gefuellt = farben_eintragen(verteiler, kabel, self.kabeltypen)
        self._belegung_geaendert()
        self.leistenansicht.aktualisieren()
        self.statusBar().showMessage(
            f"Kabel aufgelegt: {kabel.da_aufgelegt} DA"
            + (f", {gefuellt} Adernfarben eingetragen" if gefuellt else "")
        )

    def _ueberlauf_klaeren(self, angaben: dict, ueberlauf: UeberlaufFehler):
        """Fortsetzen oder Rest verfallen lassen."""
        verteiler = self.projekt.verteiler
        dialog = UeberlaufDialog(verteiler, ueberlauf.passend, ueberlauf.rest, self)
        if dialog.exec() != UeberlaufDialog.DialogCode.Accepted:
            return None

        wahl, leiste, start = dialog.entscheidung()
        abschnitte = [
            Kabelabschnitt(angaben["leiste"], angaben["start_da"], ueberlauf.passend)
        ]
        if wahl == UeberlaufDialog.FORTSETZEN:
            abschnitte.append(Kabelabschnitt(leiste, start, ueberlauf.rest))

        try:
            return verteiler.kabel_anlegen_mehrteilig(
                angaben["beschriftung"],
                abschnitte,
                kabeltyp=angaben["kabeltyp"],
                da_gesamt=angaben["da_gesamt"],
            )
        except ModellFehler as fehler:
            QMessageBox.warning(self, "Kabel nicht aufgelegt", str(fehler))
            return None

    def _kabel_angeklickt(self, kabel) -> None:
        antwort = QMessageBox.question(
            self,
            "Kabel entfernen?",
            f"Das Kabel „{kabel.beschriftung}“ von der Leiste nehmen?\n"
            "Die Adernfarben bleiben stehen.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if antwort == QMessageBox.StandardButton.Yes:
            self.projekt.verteiler.kabel_entfernen(kabel)
            self._belegung_geaendert()
            self.leistenansicht.aktualisieren()

    def kabel_entfernen(self) -> None:
        if self.projekt is None or self.uebersicht.auswahl is None:
            self.statusBar().showMessage("Erst eine Doppelader mit Kabel auswählen")
            return
        leiste, da = self.uebersicht.auswahl
        kabel = self.projekt.verteiler.kabel_an(leiste, da)
        if kabel is None:
            self.statusBar().showMessage(f"Auf Leiste {leiste} DA {da} liegt kein Kabel")
            return
        self._kabel_angeklickt(kabel)

    # -- Sonstiges ---------------------------------------------------------

    def _grundausstattung_sichern(self) -> None:
        """Beim ersten Start die mitgelieferten Dateien auslegen.

        Erst danach sind Vorlagen und Kabeltypen fuer den Anwender
        erreichbar - im AppImage liegen sie sonst im Nur-Lese-Abbild.
        """
        try:
            self.ausgelegt = pfade.grundausstattung_auslegen()
        except OSError:
            self.ausgelegt = []

    def _vorlagen_laden(self) -> Vorlagen:
        """Alle Vorlagenordner zusammen; eigene gehen vor mitgelieferten."""
        try:
            orte = list(reversed(pfade.vorlagenordner_alle()))
        except OSError:
            orte = []
        return Vorlagen.aus_ordnern(orte)

    def _vorlagenordner(self):
        """Wohin eigene Vorlagen kommen - None, wenn dort nichts geht."""
        try:
            return pfade.eigener_vorlagenordner()
        except OSError:
            return None

    def vorlage_ablegen(self) -> None:
        """Die Geometrie des offenen Verteilers als Vorlage sichern."""
        if self.projekt is None:
            return
        verteiler = self.projekt.verteiler
        als_vorlage_speichern(
            self,
            verteiler,
            self.vorlagen,
            self._vorlagenordner(),
            vorschlag=verteiler.name or f"{verteiler.da_gesamt} DA",
            beschreibung=f"Nach dem Verteiler {verteiler.name}." if verteiler.name else "",
        )

    def briefkopf_bearbeiten(self) -> None:
        if self.projekt is None:
            return
        dialog = BriefkopfDialog(self.projekt, self)
        if dialog.exec() == BriefkopfDialog.DialogCode.Accepted:
            dialog.uebernehmen()
            self._belegung_geaendert()
            self.statusBar().showMessage("Briefkopf übernommen")

    def ueber(self) -> None:
        QMessageBox.about(
            self,
            "Über Verteilerly",
            f"<b>Verteilerly {VERSION}</b><br><br>"
            "Dokumentation für LSA+-Verteiler in der Fernmeldetechnik.<br>"
            f"Daten: {pfade.datenordner()}",
        )

    def closeEvent(self, ereignis) -> None:
        if self._darf_verwerfen():
            ereignis.accept()
        else:
            ereignis.ignore()
