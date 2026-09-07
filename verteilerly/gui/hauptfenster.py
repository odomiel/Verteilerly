"""Hauptfenster von Verteilerly."""

from __future__ import annotations

import pathlib

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
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

from .. import einstellungen as einstellungsspeicher
from .. import pfade, projektdatei, schreibweisen
from ..ausgabe import AusgabeFehler, csv_schreiben, pdf_schreiben, xlsx_schreiben
from ..blattvorlagen import Blattvorlagen
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
from .sprache import frage
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
        # Als Datei an einem bekannten Ort, nicht in der Registry:
        # unter Windows liegt sie neben dem Programm.
        self.einstellungen = QSettings(
            str(pfade.einstellungsdatei()), QSettings.Format.IniFormat
        )
        self._grundausstattung_sichern()
        self.vorlagen = self._vorlagen_laden()
        self.blattvorlagen = self._blattvorlagen_laden()
        self.kabeltypen = Kabeltypen.laden(pfade.kabeltypenordner())

        self.projekt: Projekt | None = None
        self.pfad: pathlib.Path | None = None
        self.veraendert = False
        self.thema_name = str(self.einstellungen.value("thema", "hell"))
        # Wie Rangierungen geschrieben werden - eine Anzeigesache,
        # darum in der Einstellungsdatei und nicht in der Projektdatei.
        self.schreibweise = schreibweisen.holen(
            self.einstellungen.value("schreibweise", schreibweisen.STANDARD.id)
        )
        # Freitext im Rangierfeld - aus, bis er gebraucht wird.
        self.freitext = self.einstellungen.value("freitext", False, type=bool)

        self.setWindowIcon(symbol_icon())
        self._oberflaeche_bauen()
        self._aktionen_bauen()
        self.thema_anwenden(self.thema_name)
        self._projekt_setzen(None, None)
        if self.ausgelegt:
            self.statusBar().showMessage(
                f"{len(self.ausgelegt)} Dateien nach {pfade.eigener_datenordner()} "
                "gelegt — dort sind sie änderbar",
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
        self.vorschau.blattvorlagen_setzen(
            self.blattvorlagen, str(self.einstellungen.value("blattvorlage", ""))
        )
        self.vorschau.blattvorlage_gewechselt.connect(self._blattvorlage_gemerkt)
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

        def aktion(text, ausloeser, kuerzel=None, in_leiste=False, menue=datei,
                   hinweis=""):
            handlung = QAction(text, self)
            handlung.triggered.connect(ausloeser)
            if kuerzel:
                handlung.setShortcut(QKeySequence(kuerzel))
            if hinweis:
                # Steht in der Statuszeile, sobald der Eintrag berührt wird -
                # auch wenn er ausgegraut ist. So ist ablesbar, was fehlt.
                handlung.setStatusTip(hinweis)
            menue.addAction(handlung)
            if in_leiste:
                werkzeuge.addAction(handlung)
            return handlung

        aktion("&Neuer Verteiler…", self.neuer_verteiler, "Ctrl+N", True,
               hinweis="Einen Verteiler aus einer Vorlage oder eigenen Maßen anlegen")
        aktion("Ö&ffnen…", self.oeffnen, "Ctrl+O", True,
               hinweis="Eine gespeicherte Verteilerdatei öffnen")
        self.aktion_speichern = aktion(
            "&Speichern", self.speichern, "Ctrl+S", True,
            hinweis="Den Verteiler speichern",
        )
        self.aktion_speichern_unter = aktion(
            "Speichern &unter…", self.speichern_unter, "Ctrl+Shift+S",
            hinweis="Den Verteiler unter einem anderen Namen speichern",
        )
        datei.addSeparator()
        self.aktion_pdf = aktion("Als &PDF…", self.pdf_ausgeben, "Ctrl+E", True,
                                 hinweis="Deckblatt, Verteilerbelegung und Leistenblätter")
        self.aktion_xlsx = aktion("Als &Excel-Mappe…", self.xlsx_ausgeben,
                                  hinweis="Die Belegungsdaten je Ader als xlsx")
        self.aktion_csv = aktion("Als &CSV…", self.csv_ausgeben,
                                 hinweis="Die Belegungsdaten je Ader als CSV")
        datei.addSeparator()
        aktion("&Beenden", self.close, "Ctrl+Q")

        bearbeiten = self.menuBar().addMenu("&Bearbeiten")
        werkzeuge.addSeparator()
        self.aktion_kabel = aktion(
            "&Kabel auflegen…", self.kabel_auflegen, "Ctrl+K", True, bearbeiten,
            hinweis="Ein Kabel auf eine Leiste legen",
        )
        self.aktion_kabel_weg = aktion(
            "Kabel &entfernen", self.kabel_entfernen, "Ctrl+Shift+K", True, bearbeiten,
            hinweis="Erst eine Doppelader mit Kabel auswählen",
        )
        self.aktion_vorlage = aktion(
            "Als &Vorlage speichern…", self.vorlage_ablegen, menue=bearbeiten,
            hinweis="Die Maße dieses Verteilers als Vorlage ablegen",
        )
        bearbeiten.addSeparator()
        self.aktion_briefkopf = aktion(
            "&Briefkopf und eigene Felder…",
            self.briefkopf_bearbeiten,
            "Ctrl+B",
            True,
            bearbeiten,
            hinweis="Stammdaten, die auf jedem Blatt stehen",
        )

        bearbeiten.addSeparator()
        self.aktion_freitext = QAction("&Freitext im Rangierfeld zulassen", self)
        self.aktion_freitext.setCheckable(True)
        self.aktion_freitext.setChecked(self.freitext)
        self.aktion_freitext.setStatusTip(
            "Erlaubt im Rangierfeld auch einen Vermerk statt eines Ziels — "
            "etwa „extern“ oder „zur Klemmleiste“"
        )
        self.aktion_freitext.triggered.connect(self.freitext_erlauben)
        bearbeiten.addAction(self.aktion_freitext)

        ansicht = self.menuBar().addMenu("&Ansicht")
        self.aktion_thema = QAction("&Dunkles Erscheinungsbild", self)
        self.aktion_thema.setCheckable(True)
        self.aktion_thema.setChecked(self.thema_name == "dunkel")
        self.aktion_thema.setShortcut(QKeySequence("Ctrl+D"))
        self.aktion_thema.triggered.connect(
            lambda an: self.thema_anwenden("dunkel" if an else "hell")
        )
        ansicht.addAction(self.aktion_thema)

        rangierungen = ansicht.addMenu("Schreibweise der &Rangierungen")
        rangierungen.setToolTipsVisible(True)
        self.schreibweisen_gruppe = QActionGroup(self)
        self.schreibweisen_gruppe.setExclusive(True)
        for weise in schreibweisen.SCHREIBWEISEN:
            handlung = QAction(weise.beispiel, self)
            handlung.setCheckable(True)
            handlung.setChecked(weise.id == self.schreibweise.id)
            handlung.setData(weise.id)
            handlung.setStatusTip(weise.beschreibung)
            handlung.setToolTip(weise.beschreibung)
            handlung.triggered.connect(
                lambda _an=False, kennung=weise.id: self.schreibweise_waehlen(kennung)
            )
            self.schreibweisen_gruppe.addAction(handlung)
            rangierungen.addAction(handlung)

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

    def schreibweise_waehlen(self, kennung: str) -> None:
        """Stellt um, wie Rangierungen geschrieben werden.

        Getippt werden darf weiter jede Form; nur die Anzeige folgt der
        Wahl - im Editor, auf dem Blatt und in Excel und CSV.
        """
        self.schreibweise = schreibweisen.holen(kennung)
        self.einstellungen.setValue("schreibweise", self.schreibweise.id)
        self._schreibweise_anwenden()
        self.statusBar().showMessage(
            f"Rangierungen werden als {self.schreibweise.beispiel} geschrieben", 6000
        )

    def freitext_erlauben(self, an: bool) -> None:
        """Schaltet den Vermerk im Rangierfeld frei.

        Ausgeschaltet meldet ein unlesbares Ziel wieder einen Fehler -
        wer nur Ziele eintraegt, will den Tippfehler sehen.
        """
        self.freitext = bool(an)
        self.einstellungen.setValue("freitext", self.freitext)
        self.leistenansicht.freitext_erlauben(self.freitext)
        self.aktion_freitext.setChecked(self.freitext)
        self.statusBar().showMessage(
            "Freitext im Rangierfeld ist zugelassen"
            if self.freitext
            else "Im Rangierfeld sind nur Ziele zugelassen",
            6000,
        )

    def _schreibweise_anwenden(self) -> None:
        # Der Haken folgt dem Zustand, nicht dem Klick: so stimmt das
        # Menue auch, wenn die Schreibweise von anderswo gesetzt wird.
        for handlung in self.schreibweisen_gruppe.actions():
            handlung.setChecked(handlung.data() == self.schreibweise.id)
        self.leistenansicht.schreibweise_setzen(self.schreibweise)
        if self.projekt is not None:
            self.projekt.rangierung_schreibweise = self.schreibweise.id
        self._vorschau_anstossen()

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
        # Auch das Abwählen zählt: „Kabel entfernen“ muss dann wieder aus.
        self.aktionen_auffrischen()
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
        self.aktionen_auffrischen()
        self._vorschau_anstossen()

    def _blattvorlage_gemerkt(self, kennung: str) -> None:
        self.einstellungen.setValue("blattvorlage", kennung)
        self.statusBar().showMessage(
            f"Blattvorlage: {self.blattvorlagen.holen(kennung).name}", 6000
        )

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
        if projekt is not None:
            projekt.rangierung_schreibweise = self.schreibweise.id
        self.uebersicht.verteiler_setzen(verteiler)
        self.leistenansicht.verteiler_setzen(verteiler)
        self.leistenansicht.schreibweise_setzen(self.schreibweise)
        self.leistenansicht.freitext_erlauben(self.freitext)
        self.vorschau.projekt_setzen(projekt)
        self.aktionen_auffrischen()
        self._titel_setzen()

    def aktionen_auffrischen(self) -> None:
        """Graut aus, was gerade nicht geht.

        Ein Menüeintrag, der nichts tun kann, soll das zeigen, statt beim
        Anklicken eine Meldung zu bringen. Der Statushinweis am Eintrag
        sagt, was fehlt - er erscheint auch bei ausgegrauten Einträgen.
        """
        offen = self.projekt is not None
        for handlung in (
            self.aktion_speichern_unter,
            self.aktion_pdf,
            self.aktion_xlsx,
            self.aktion_csv,
            self.aktion_kabel,
            self.aktion_vorlage,
            self.aktion_briefkopf,
        ):
            handlung.setEnabled(offen)

        # Speichern nur, wenn es etwas zu speichern gibt: ungesicherte
        # Änderungen oder eine Datei, die es noch nicht gibt.
        self.aktion_speichern.setEnabled(
            offen and (self.veraendert or self.pfad is None)
        )
        self.aktion_kabel_weg.setEnabled(self._kabel_der_auswahl() is not None)

    def _kabel_der_auswahl(self):
        """Das Kabel an der ausgewählten Doppelader, wenn dort eines liegt."""
        if self.projekt is None or self.uebersicht.auswahl is None:
            return None
        leiste, da = self.uebersicht.auswahl
        return self.projekt.verteiler.kabel_an(leiste, da)

    def _darf_verwerfen(self) -> bool:
        if not self.veraendert:
            return True
        antwort = frage(
            self,
            "Änderungen verwerfen?",
            "Der Verteiler wurde geändert und noch nicht gespeichert.",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
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
        projekt = self.neues_projekt(dialog.verteiler())
        self._projekt_setzen(projekt, None)
        uebernommen = len(projekt.briefkopf) + len(projekt.eigene_felder)
        self.statusBar().showMessage(
            f"Neuer Verteiler: {self.projekt.verteiler.da_gesamt} DA auf "
            f"{len(self.projekt.verteiler.alle_leisten)} Leisten"
            + (f", Briefkopf mit {uebernommen} Feldern übernommen" if uebernommen else "")
        )

    def neues_projekt(self, verteiler: Verteiler) -> Projekt:
        """Ein frisches Projekt mit dem gemerkten Briefkopf."""
        return einstellungsspeicher.briefkopf_uebernehmen(
            self.einstellungen, Projekt(verteiler=verteiler)
        )

    def briefkopf_merken(self) -> None:
        """Die Angaben wiederholen sich von Verteiler zu Verteiler."""
        if self.projekt is not None:
            einstellungsspeicher.briefkopf_sichern(self.einstellungen, self.projekt)

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
        self.aktionen_auffrischen()
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
        self._ausgeben(
            lambda: pdf_schreiben(self.projekt, ziel, self.vorschau.blattvorlage), ziel
        )

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

        meldung = f"Kabel aufgelegt: {kabel.da_aufgelegt} DA"
        if gefuellt:
            meldung += f", {gefuellt} Adernfarben eingetragen"
        meldung += self._lagenhinweis(kabel)
        self.statusBar().showMessage(meldung, 12000)

    def _lagenhinweis(self, kabel) -> str:
        """Warnt, wenn die Lagenaufteilung dieser Kabelgröße fehlt.

        Sonst bliebe unbemerkt, dass ab der zweiten Lage keine rote a-Ader
        gesetzt wurde - eine falsche Farbe fällt auf dem Blatt niemandem auf.
        """
        if not kabel.kabeltyp:
            return ""
        try:
            typ = self.kabeltypen.holen(kabel.kabeltyp)
        except ModellFehler:
            return ""
        if typ.lagen_bekannt(kabel.da_gesamt):
            return ""
        return (
            f" — Achtung: für {kabel.da_gesamt or kabel.da_aufgelegt} DA ist keine "
            "Lagenaufteilung hinterlegt, nur die erste Doppelader ist rot"
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
        antwort = frage(
            self,
            "Kabel entfernen?",
            f"Das Kabel „{kabel.beschriftung}“ von der Leiste nehmen?\n"
            "Die Adernfarben bleiben stehen.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if antwort == QMessageBox.StandardButton.Yes:
            self.projekt.verteiler.kabel_entfernen(kabel)
            self._belegung_geaendert()
            self.leistenansicht.aktualisieren()
            self.aktionen_auffrischen()

    def kabel_entfernen(self) -> None:
        """Der Eintrag ist nur da anklickbar, wo wirklich ein Kabel liegt."""
        kabel = self._kabel_der_auswahl()
        if kabel is not None:
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

    def _blattvorlagen_laden(self) -> Blattvorlagen:
        """Alle Blattvorlagen; eigene gehen vor mitgelieferten."""
        try:
            orte = list(reversed(pfade.blattvorlagenordner_alle()))
        except OSError:
            orte = []
        return Blattvorlagen.aus_ordnern(orte)

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
            # Die Angaben wiederholen sich von Verteiler zu Verteiler -
            # sie werden deshalb in der Verteilerly.conf gemerkt.
            self.briefkopf_merken()
            self._belegung_geaendert()
            self.statusBar().showMessage(
                "Briefkopf übernommen und als Vorgabe gemerkt"
            )

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
