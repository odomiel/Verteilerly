"""Hauptfenster von Verteilerly."""

from __future__ import annotations

import os
import pathlib
import shutil
import tempfile

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import einstellungen as einstellungsspeicher
from .. import (
    bestand,
    erweiterungen,
    paket,
    pfade,
    projektdatei,
    pruefung,
    schreibweisen,
    sprachen,
    suche,
    verknuepfung,
)
from ..ausgabe import AusgabeFehler, csv_schreiben, pdf_schreiben, xlsx_schreiben
from ..blattvorlagen import Blattvorlagen
from ..farbcodes import (
    Kabeltypen,
    farben_eintragen,
    farben_loeschen,
    farben_verwaist_loeschen,
    farbplan,
)
from ..layout import verteilerbelegungen
from ..modell import (
    BLATTARTEN,
    BRIEFKOPF_FELDER,
    LEISTEN_BUCHSTABEN,
    LEISTEN_ZAHLEN,
    Kabelabschnitt,
    ModellFehler,
    Projekt,
    UeberlaufFehler,
    Verteiler,
    leistenname,
    mehrzahl,
)
from .. import URHEBER
from ..version import VERSION
from ..vorlagen import Vorlagen

#: Wie die Leisten heissen koennen - Kennung, Beispiel und Erklaerung.
#: Die Woerter gehen beim Anzeigen durch die Uebersetzung.
LEISTENWEISEN = (
    (LEISTEN_ZAHLEN, "1, 2, 3", "Die Leisten werden gezählt"),
    (LEISTEN_BUCHSTABEN, "A, B, C", "Die Leisten tragen Buchstaben"),
)
from .dialoge import (
    BlattvorlagenDialog,
    BlattwahlDialog,
    SuchDialog,
    VerteilervorlagenDialog,
    ProjektdatenDialog,
    KabelDialog,
    NeuerVerteilerDialog,
    PaketDialog,
    PruefberichtDialog,
    UeberlaufDialog,
    als_vorlage_speichern,
)
from .erweiterungen import ErweiterungenDialog, Schnittstelle
from .leistenansicht import LeistenAnsicht
from .sprache import frage
from .symbol import symbol_icon
from .thema import SAETZE, anwenden
from .uebersicht import Uebersicht
from .vorschau import Vorschau
from ..sprachen import u

# Wohin das Über-Fenster für die Lizenztexte verweist. Das Programm
# braucht das Netz nicht - die Texte liegen auch im Arbeitsordner;
# im Netz stehen sie in jeder Sprache und immer vollständig.
LIZENZVERWEISE = (
    ("GNU GPL v3", "https://www.gnu.org/licenses/gpl-3.0.html"),
    ("GNU LGPL v3", "https://www.gnu.org/licenses/lgpl-3.0.html"),
    ("Qt-Quelltext", "https://download.qt.io/official_releases/qt/"),
)

VORLAGENORDNER = "vorlagen"
BLATTVORLAGENORDNER = "blattvorlagen"

# Die drei Ausgabewege: Kennung, Name auf dem Knopf, Methode.
EXPORTFORMATE = (
    ("pdf", "PDF", "pdf_ausgeben"),
    ("xlsx", "XLSX", "xlsx_ausgeben"),
    ("csv", "CSV", "csv_ausgeben"),
)

#: Gespeichert wird als `.vtly` - eine einzige Endung, sonst haengt
#: Windows die Datei an `.json` und damit an jedes andere Programm.
#: Gelesen wird weiter auch die alte Schreibweise.
DATEIENDUNG = ".vtly"
DATEIFILTER = (
    "Verteilerly-Projekt (*.vtly *.vtly.json);;Alle Dateien (*)"
)
PDFFILTER = "PDF (*.pdf)"
XLSXFILTER = "Excel-Arbeitsmappe (*.xlsx)"
CSVFILTER = "CSV, Semikolon getrennt (*.csv)"
PAKETFILTER = "Verteilerly-Paket (*.zip)"
#: Welche Erweiterungen laufen, entscheidet dieser Rechner. Ein Paket
#: bringt diese Einstellungen darum nicht mit - sonst koennte eines aus
#: fremder Hand eine eigene Erweiterung einschalten, die hier liegt.
ERWEITERUNGSWAHL = (
    "erweiterungen_an",
    "erweiterungen_aus",
    "erweiterungen_nur_eingebaute",
)
VORSCHAU_VERZUG = 250  # ms, damit das Tippen nicht stockt

#: Wie viele Schritte sich zurücknehmen lassen. Ein Stand ist das
#: Projekt als Dict - klein genug, dass fünfzig davon nicht auffallen.
RUECKGAENGIG_SCHRITTE = 50


class Hauptfenster(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        # Was beim Lesen der Einstellungen und der Vorlagen auffiel, kommt
        # hier zusammen und wird einmal gezeigt - nicht dreimal
        # hintereinander.
        self.hinweise: list[str] = []
        # Als Datei an einem bekannten Ort, nicht in der Registry:
        # unter Windows liegt sie neben dem Programm.
        self.einstellungen = self._einstellungen_oeffnen()
        self._grundausstattung_sichern()
        self.vorlagen = self._vorlagen_laden(self.hinweise)
        self.blattvorlagen = self._blattvorlagen_laden(self.hinweise)
        try:
            self.kabeltypen = Kabeltypen.laden(
                pfade.kabeltypenordner(), self.hinweise
            )
        except (OSError, ModellFehler) as fehler:
            self.hinweise.append(str(fehler))
            self.kabeltypen = Kabeltypen({}, {})
        self._hinweise_zeigen()

        self.projekt: Projekt | None = None
        self.pfad: pathlib.Path | None = None
        self.veraendert = False
        # Die Staende fuer das Zuruecknehmen: was war, was rueckgaengig
        # gemacht wurde, und der Stand seit der letzten Aenderung.
        #: Soll die Vorschau beim naechsten Auffrischen die
        #: Verteilerbelegung zeigen? Das Umkehren sieht man nur dort.
        self._vorschau_belegung = False
        self._rueckgaengig: list[dict] = []
        self._wiederherstellen: list[dict] = []
        self._stand: dict | None = None
        self.thema_name = str(self.einstellungen.value("thema", "hell"))
        # Wie Rangierungen geschrieben werden - eine Anzeigesache,
        # darum in der Einstellungsdatei und nicht in der Projektdatei.
        self.schreibweise = schreibweisen.holen(
            self.einstellungen.value("schreibweise", schreibweisen.STANDARD.id)
        )
        # Freitext im Rangierfeld - aus, bis er gebraucht wird.
        self.freitext = self.einstellungen.value("freitext", False, type=bool)
        # Das zuletzt gesuchte Wort steht beim naechsten Aufruf wieder da;
        # es gehoert zur Sitzung, nicht in die Einstellungsdatei.
        self.zuletzt_gesucht = ""

        self.setWindowIcon(symbol_icon())
        self._oberflaeche_bauen()
        self._aktionen_bauen()
        # Erst jetzt gibt es beides: die Knoepfe in der Leistenansicht
        # bekommen die Handlungen des Fensters.
        self.leistenansicht.bearbeitungsaktionen_setzen(
            self.aktion_rueckgaengig, self.aktion_wiederherstellen
        )
        self.thema_anwenden(self.thema_name)
        self._projekt_setzen(None, None)
        if self.einstellungen_grund:
            QMessageBox.warning(
                self,
                u("Einstellungen"),
                u("Die Einstellungen in {0} ließen sich nicht lesen ({1}).\n\n"
                  "Die Datei bleibt unberührt — was Sie in diesem Lauf "
                  "einstellen, wird darum nicht gemerkt. Schließen Sie das "
                  "Programm, sehen Sie sich die Datei an, und legen Sie sie "
                  "notfalls beiseite: beim nächsten Start wird sie neu "
                  "angelegt.").format(pfade.einstellungsdatei(), self.einstellungen_grund),
            )
        if self.ausgelegt:
            self.statusBar().showMessage(
                u("{0} Dateien nach {1} gelegt — dort sind sie änderbar").format(len(self.ausgelegt), pfade.eigener_datenordner()),
                12000,
            )
        self._zuordnung_pruefen()

    def _zuordnung_pruefen(self) -> None:
        """Sagt es, wenn der Doppelklick ein anderes Verteilerly oeffnet.

        Eine portable Ausgabe liegt, wo der Anwender sie hinlegt, und
        heisst, wie sie heisst. Zieht sie um oder tritt eine andere Ausgabe
        daneben, oeffnet der Doppelklick weiter die eingetragene Datei -
        mit deren eigener Conf. Das sah bisher aus wie verlorene
        Einstellungen. Gefragt wird nur im **gepackten** Programm: aus dem
        Quellbaum wechselt der Aufruf mit jedem Python, das waere Laerm.
        Und nur gesagt, nicht getan - angemeldet wird auf Wunsch.
        """
        if not pfade.gepackt():
            return
        fremd = verknuepfung.anderes_programm()
        if fremd:
            self.statusBar().showMessage(
                u("Ein Doppelklick auf eine Projektdatei öffnet zurzeit {0} — "
                  "nachsehen unter Tools").format(fremd),
                15000,
            )
        elif verknuepfung.aufgehoben():
            # Angemeldet waren wir, aber der Doppelklick kommt nicht mehr
            # bei uns an - das sagt sonst niemand.
            self.statusBar().showMessage(
                u("Ein Doppelklick auf eine Projektdatei öffnet Verteilerly "
                  "nicht mehr — nachsehen unter Tools"),
                15000,
            )

    # -- Einstellungen oeffnen ---------------------------------------------

    def _einstellungen_oeffnen(self) -> QSettings:
        """Die Verteilerly.conf - und was ist, wenn sie sich nicht lesen laesst.

        Ein QSettings, das seine Datei nicht lesen kann, sagt das **nur**
        in ``status()``: danach verhaelt es sich wie ein frisches
        Programm, und das erste ``setValue`` schreibt die Vorgaben in die
        Datei - die Einstellungen des Anwenders waeren weg, ohne dass
        jemand etwas gemerkt haette. Liegt die Datei also da und gibt doch
        nichts her, wird in eine wegwerfbare Datei geschrieben: lieber ein
        Lauf ohne Gedaechtnis als eine ueberschriebene Conf. Gesagt wird
        es dem Anwender mit den anderen Hinweisen des Starts.
        """
        datei = pfade.einstellungsdatei()
        einstellungen = QSettings(str(datei), QSettings.Format.IniFormat)
        self.einstellungen_grund = self._conf_grund(einstellungen, datei)
        if not self.einstellungen_grund:
            return einstellungen
        ersatz = (
            pathlib.Path(tempfile.gettempdir())
            / f"Verteilerly-ungemerkt-{os.getpid()}.conf"
        )
        ersatz.unlink(missing_ok=True)
        return QSettings(str(ersatz), QSettings.Format.IniFormat)

    @staticmethod
    def _conf_grund(einstellungen: QSettings, datei: pathlib.Path) -> str:
        """Warum diese Conf nicht zu gebrauchen ist - oder ein leerer Satz.

        Eine Datei, die es nicht gibt, ist kein Fehler: so faengt jeder
        erste Start an. Verdaechtig ist eine Datei, die da ist und
        trotzdem keinen einzigen Wert hergibt - dann hat Qt sie entweder
        nicht gelesen oder nicht verstanden.
        """
        if einstellungen.status() == QSettings.Status.AccessError:
            return u("kein Zugriff")
        if einstellungen.status() == QSettings.Status.FormatError:
            return u("die Datei ist nicht lesbar")
        try:
            vorhanden = datei.is_file() and datei.stat().st_size > 0
        except OSError:
            return u("kein Zugriff")
        if vorhanden and not einstellungen.allKeys():
            return u("kein Wert darin gelesen")
        return ""

    # -- Aufbau ------------------------------------------------------------

    def _oberflaeche_bauen(self) -> None:
        self.uebersicht = Uebersicht()
        self.uebersicht.stelle_aktiviert.connect(self.kabel_auflegen)
        self.uebersicht.kabel_aktiviert.connect(self._kabel_angeklickt)
        self.uebersicht.auswahl_geaendert.connect(self._auswahl_gemeldet)
        self.uebersicht.kabel_umgelegt.connect(self._kabel_umlegen)

        rollbereich = QScrollArea()
        rollbereich.setWidget(self.uebersicht)
        rollbereich.setWidgetResizable(True)
        rollbereich.setFrameShape(QScrollArea.Shape.NoFrame)

        oben = QWidget()
        obenaufbau = QVBoxLayout(oben)
        obenaufbau.setContentsMargins(0, 0, 0, 0)
        obenaufbau.addWidget(rollbereich)
        self.uebersichtsbereich = oben

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
        # Keine Seite laesst sich ganz wegziehen: die Vorschau war sonst
        # mit einem Griff verschwunden, ohne dass man wusste, wohin. Wer
        # sie loswerden will, nimmt den Schalter dafuer (F9).
        self.hauptteiler.setChildrenCollapsible(False)

        self.setCentralWidget(self.hauptteiler)
        self.statusBar().showMessage(u("Bereit"))
        self.resize(1320, 820)

    def _aktionen_bauen(self) -> None:
        datei = self.menuBar().addMenu(u("&Datei"))
        werkzeuge = QToolBar(u("Werkzeuge"))
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

        aktion(u("&Neuer Verteiler…"), self.neuer_verteiler, "Ctrl+N", True,
               hinweis=u("Einen Verteiler aus einer Vorlage oder eigenen Maßen anlegen"))
        aktion(u("Ö&ffnen…"), self.oeffnen, "Ctrl+O", True,
               hinweis=u("Eine gespeicherte Verteilerdatei öffnen"))
        self.aktion_speichern = aktion(
            u("&Speichern"), self.speichern, "Ctrl+S", True,
            hinweis=u("Den Verteiler speichern"),
        )
        self.aktion_speichern_unter = aktion(
            u("Speichern &unter…"), self.speichern_unter, "Ctrl+Shift+S",
            hinweis=u("Den Verteiler unter einem anderen Namen speichern"),
        )
        datei.addSeparator()
        # Drei Wege aus dem Programm heraus - sie gehören zusammen und
        # stehen darum in einem eigenen Untermenü.
        self.exportmenue = datei.addMenu(u("&Exportieren"))
        self.exportmenue.setToolTipsVisible(True)
        self.aktion_pdf = aktion(
            u("Als &PDF…"), self.pdf_ausgeben, "Ctrl+E", menue=self.exportmenue,
            hinweis=u("Deckblatt, Verteilerbelegung und Leistenblätter"),
        )
        self.aktion_xlsx = aktion(
            u("Als &Excel-Mappe…"), self.xlsx_ausgeben, menue=self.exportmenue,
            hinweis=u("Die Blätter im Blattbild, dahinter die Daten je Ader"),
        )
        self.aktion_csv = aktion(
            u("Als &CSV…"), self.csv_ausgeben, menue=self.exportmenue,
            hinweis=u("Belegung, Kabel und Projektdaten als Textdatei"),
        )
        self._exportknopf_bauen(werkzeuge)
        datei.addSeparator()
        aktion(u("&Beenden"), self.close, "Ctrl+Q")

        bearbeiten = self.menuBar().addMenu(u("&Bearbeiten"))
        self.aktion_rueckgaengig = aktion(
            u("&Rückgängig"), self.rueckgaengig, "Ctrl+Z", False, bearbeiten,
            hinweis=u("Nimmt die letzte Änderung am Verteiler zurück"),
        )
        self.aktion_wiederherstellen = aktion(
            u("Wieder&herstellen"), self.wiederherstellen, "Ctrl+Y", False,
            bearbeiten,
            hinweis=u("Stellt wieder her, was zuletzt zurückgenommen wurde"),
        )
        bearbeiten.addSeparator()
        werkzeuge.addSeparator()
        self.aktion_kabel = aktion(
            u("&Kabel auflegen…"), self.kabel_auflegen, "Ctrl+K", True, bearbeiten,
            hinweis=u("Ein Kabel auf eine Leiste legen"),
        )
        self.aktion_kabel_aendern = aktion(
            u("Kabel &bearbeiten…"), self.kabel_bearbeiten, "Ctrl+Shift+E", True,
            bearbeiten,
            hinweis=u("Beschriftung, Kabeltyp und Größe eines aufgelegten Kabels ändern"),
        )
        self.aktion_kabel_weg = aktion(
            u("Kabel &entfernen"), self.kabel_entfernen, "Ctrl+Shift+K", True, bearbeiten,
            hinweis=u("Erst eine Doppelader mit Kabel auswählen"),
        )
        self.aktion_vorlage = aktion(
            u("Als &Vorlage speichern…"), self.vorlage_ablegen, menue=bearbeiten,
            hinweis=u("Die Maße dieses Verteilers als Vorlage ablegen"),
        )
        bearbeiten.addSeparator()
        self.aktion_suchen = aktion(
            u("S&uchen…"), self.suchen, "Ctrl+F", True, bearbeiten,
            hinweis=u("Bezeichnungen, Bemerkungen, Rangierungen, Kabel und "
                    "Projektdaten durchsuchen"),
        )
        self.aktion_projektdaten = aktion(
            u("&Projektdaten…"),
            self.projektdaten_bearbeiten,
            "Ctrl+B",
            True,
            bearbeiten,
            hinweis=u("Name und Nummer des Verteilers, Stammdaten und eigene Felder — "
                    "was im Schriftfeld jedes Blattes steht"),
        )

        self.aktion_freitext = QAction(u("&Freitext im Rangierfeld zulassen"), self)
        self.aktion_freitext.setCheckable(True)
        self.aktion_freitext.setChecked(self.freitext)
        self.aktion_freitext.setStatusTip(
            u("Erlaubt im Rangierfeld auch einen Vermerk statt eines Ziels — "
            "etwa „extern“ oder „zur Klemmleiste“")
        )
        self.aktion_freitext.triggered.connect(self.freitext_erlauben)

        einstellungen = self.menuBar().addMenu(u("&Einstellungen"))
        aktion(
            u("&Blattvorlage…"), self.blattvorlage_waehlen, "Ctrl+Shift+B",
            menue=einstellungen,
            hinweis=u("Wie die Blätter aussehen — Spalten, Schriftgrößen, Ränder"),
        )
        aktion(
            u("&Verteilervorlagen…"), self.vorlagen_verwalten, "Ctrl+Shift+V",
            menue=einstellungen,
            hinweis=u("Vorlagen umbenennen, löschen und die mitgelieferten "
                    "zurückholen"),
        )
        aktion(
            u("&Vorgaben für neue Verteiler…"), self.vorgaben_bearbeiten,
            menue=einstellungen,
            hinweis=u("Firma, Kürzel und was sonst bei jedem Verteiler gleich ist"),
        )
        einstellungen.addSeparator()
        aktion(
            u("Vorlagen und Einstellungen &sichern…"), self.paket_sichern,
            menue=einstellungen,
            hinweis=u("Vorlagen, Kabeltypen und Einstellungen in eine Datei packen"),
        )
        aktion(
            u("Vorlagen und Einstellungen &einspielen…"), self.paket_einspielen,
            menue=einstellungen,
            hinweis=u("Ein gesichertes Paket in den Arbeitsordner zurückholen"),
        )
        einstellungen.addSeparator()

        ansicht = self.menuBar().addMenu(u("&Ansicht"))
        self.aktion_thema = QAction(u("&Dunkles Erscheinungsbild"), self)
        self.aktion_thema.setCheckable(True)
        self.aktion_thema.setChecked(self.thema_name == "dunkel")
        self.aktion_thema.setShortcut(QKeySequence("Ctrl+D"))
        self.aktion_thema.triggered.connect(
            lambda an: self.thema_anwenden("dunkel" if an else "hell")
        )
        ansicht.addAction(self.aktion_thema)

        sprachmenue = einstellungen.addMenu(u("&Sprache"))
        sprachmenue.setToolTipsVisible(True)
        self.sprachen_gruppe = QActionGroup(self)
        self.sprachen_gruppe.setExclusive(True)
        for kennung, wie in sprachen.SPRACHEN:
            handlung = QAction(wie, self)
            handlung.setCheckable(True)
            handlung.setChecked(kennung == sprachen.sprache())
            handlung.setData(kennung)
            handlung.setStatusTip(
                u("Die Sprache der Oberfläche — sie gilt nach einem Neustart")
            )
            handlung.triggered.connect(
                lambda _an=False, kennung=kennung: self.sprache_waehlen(kennung)
            )
            self.sprachen_gruppe.addAction(handlung)
            sprachmenue.addAction(handlung)

        rangierungen = einstellungen.addMenu(u("Schreibweise der &Rangierungen"))
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

        leistennamen = einstellungen.addMenu(u("&Leisten beschriften"))
        leistennamen.setToolTipsVisible(True)
        self.leistennamen_menue = leistennamen.menuAction()
        self.leistenweisen_gruppe = QActionGroup(self)
        self.leistenweisen_gruppe.setExclusive(True)
        for kennung, beispiel, erklaerung in LEISTENWEISEN:
            handlung = QAction(beispiel, self)
            handlung.setCheckable(True)
            handlung.setChecked(kennung == LEISTEN_ZAHLEN)
            handlung.setData(kennung)
            handlung.setStatusTip(u(erklaerung))
            handlung.setToolTip(u(erklaerung))
            handlung.triggered.connect(
                lambda _an=False, kennung=kennung: self.leistenweise_waehlen(kennung)
            )
            self.leistenweisen_gruppe.addAction(handlung)
            leistennamen.addAction(handlung)
        self.aktion_belegung_umgekehrt = QAction(
            u("Verteilerbelegung &umkehren"), self
        )
        self.aktion_belegung_umgekehrt.setCheckable(True)
        self.aktion_belegung_umgekehrt.setStatusTip(
            u("Die Doppeladern stehen von rechts nach links — wie an einem "
              "Verteiler, der von rechts belegt wird")
        )
        self.aktion_belegung_umgekehrt.triggered.connect(self.belegung_umkehren)
        einstellungen.addAction(self.aktion_belegung_umgekehrt)
        einstellungen.addAction(self.aktion_freitext)

        # Wie die Vorschau lassen sich Verteileruebersicht und Leistenansicht
        # ausblenden: wer nur tippt, gibt der Leistenansicht die ganze Hoehe,
        # wer nur das Blatt sehen will, der Vorschau das ganze Fenster.
        self.aktion_uebersicht = QAction(u("Verteiler&übersicht anzeigen"), self)
        self.aktion_uebersicht.setCheckable(True)
        self.aktion_uebersicht.setShortcut(QKeySequence("F7"))
        self.aktion_uebersicht.setChecked(
            self.einstellungen.value("uebersicht", True, type=bool)
        )
        self.aktion_uebersicht.triggered.connect(self.uebersicht_zeigen)
        ansicht.addAction(self.aktion_uebersicht)

        self.aktion_leistenansicht = QAction(u("&Leistenansicht anzeigen"), self)
        self.aktion_leistenansicht.setCheckable(True)
        self.aktion_leistenansicht.setShortcut(QKeySequence("F8"))
        self.aktion_leistenansicht.setChecked(
            self.einstellungen.value("leistenansicht", True, type=bool)
        )
        self.aktion_leistenansicht.triggered.connect(self.leistenansicht_zeigen)
        ansicht.addAction(self.aktion_leistenansicht)
        self.uebersicht_zeigen(self.aktion_uebersicht.isChecked())
        self.leistenansicht_zeigen(self.aktion_leistenansicht.isChecked())

        self.aktion_vorschau = QAction(u("&Vorschau anzeigen"), self)
        self.aktion_vorschau.setCheckable(True)
        self.aktion_vorschau.setShortcut(QKeySequence("F9"))
        self.aktion_vorschau.setChecked(
            self.einstellungen.value("vorschau", True, type=bool)
        )
        self.aktion_vorschau.triggered.connect(self.vorschau_zeigen)
        ansicht.addAction(self.aktion_vorschau)
        werkzeuge.addSeparator()
        self._ansichtsknopf_bauen(werkzeuge)
        self.vorschau_zeigen(self.aktion_vorschau.isChecked())

        werkzeugmenue = self.menuBar().addMenu(u("&Tools"))
        werkzeugmenue.setToolTipsVisible(True)
        for art, wie in pruefung.ARTEN:
            aktion(
                u("{0} prüfen…").format(u(wie)),
                lambda _an=False, art=art: self.vorlage_pruefen(art),
                menue=werkzeugmenue,
                hinweis=u("Eine Vorlagendatei lesen und sagen, was darin steht "
                          "— bevor sie in den Arbeitsordner kommt"),
            )

        werkzeugmenue.addSeparator()
        self.aktion_verknuepfen = aktion(
            u("&Projektdateien verknüpfen…"),
            self.verknuepfung_zeigen,
            menue=werkzeugmenue,
            hinweis=u("Sagt, mit welcher Datei die Projektdateien zu "
                      "verknüpfen sind und ob sie es sind"),
        )
        self.aktion_verknuepfen.setEnabled(verknuepfung.moeglich())

        # Erweiterungen tragen sich oberhalb des Trenners ein; darunter
        # steht, womit man sie ein- und ausschaltet. "E&rweiterungen":
        # Alt+E gehoert schon den Einstellungen.
        self.erweiterungsmenue = self.menuBar().addMenu(u("E&rweiterungen"))
        self.erweiterungsmenue.setToolTipsVisible(True)
        self._erweiterungstrenner = self.erweiterungsmenue.addSeparator()
        aktion(u("Erweiterungen &verwalten…"), self.erweiterungen_verwalten,
               menue=self.erweiterungsmenue,
               hinweis=u("Eingebaute und eigene Erweiterungen ein- und ausschalten"))
        self._erweiterungen_einrichten()

        hilfe = self.menuBar().addMenu(u("&Hilfe"))
        aktion(u("&Dokumentation"), self.dokumentation, "F1", menue=hilfe,
               hinweis=u("Was das Programm kann und wie es bedient wird"))
        hilfe.addSeparator()
        aktion(u("Ü&ber Verteilerly"), self.ueber, menue=hilfe)

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

    def sprache_waehlen(self, kennung: str) -> None:
        """Die Sprache der Oberfläche merken.

        Gewechselt wird beim nächsten Start: die Menüs, Dialoge und
        Beschriftungen werden einmal beschriftet, wenn das Fenster
        entsteht. Sie hinterher umzuhängen hieße, jedes Widget zweimal zu
        bauen - für eine Einstellung, die selten geändert wird.
        """
        if kennung == sprachen.sprache():
            return
        self.einstellungen.setValue("sprache", kennung)
        self.einstellungen.sync()
        for handlung in self.sprachen_gruppe.actions():
            handlung.setChecked(handlung.data() == kennung)
        QMessageBox.information(
            self,
            u("Sprache"),
            u("Die Oberfläche steht beim nächsten Start auf {0}.").format(
                sprachen.name(kennung)
            ),
        )
        self.statusBar().showMessage(
            u("Sprache: {0} — gilt nach einem Neustart").format(
                sprachen.name(kennung)
            ),
            8000,
        )

    def schreibweise_waehlen(self, kennung: str) -> None:
        """Stellt um, wie Rangierungen geschrieben werden.

        Getippt werden darf weiter jede Form; nur die Anzeige folgt der
        Wahl - im Editor, auf dem Blatt und in Excel und CSV.
        """
        self.schreibweise = schreibweisen.holen(kennung)
        self.einstellungen.setValue("schreibweise", self.schreibweise.id)
        self._schreibweise_anwenden()
        self.statusBar().showMessage(
            u("Rangierungen werden als {0} geschrieben").format(self.schreibweise.beispiel), 6000
        )

    def blattvorlage_waehlen(self) -> None:
        """Auf eine andere Blattvorlage umstellen oder sie umbenennen."""
        dialog = BlattvorlagenDialog(
            self.blattvorlagen, self.vorschau.blattvorlage.id, self,
            ordner=self._blattvorlagenordner(),
            quellen=self._blattvorlagenquellen(),
        )
        genommen = dialog.exec() == BlattvorlagenDialog.DialogCode.Accepted

        for kennung in dialog.geloescht:
            # Eine mitgelieferte Vorlage liegt im Abbild weiter; ohne
            # Vermerk legte der nächste Start sie wieder aus.
            pfade.loeschen_merken(f"{BLATTVORLAGENORDNER}/{kennung}.yaml")
        if dialog.wiederhergestellt:
            self._mitgeliefertes_wiederherstellen(BLATTVORLAGENORDNER)

        if dialog.umbenannt or dialog.geloescht or dialog.wiederhergestellt:
            # Die Dateien liegen jetzt anders - neu einlesen, damit Dialog,
            # Vorschau und Ausgabe dasselbe führen.
            self.blattvorlagen = self._blattvorlagen_laden()
            self.vorschau.blattvorlagen_setzen(
                self.blattvorlagen, self.vorschau.blattvorlage.id
            )
            gesagt = []
            if dialog.umbenannt:
                gesagt.append(
                    mehrzahl(len(dialog.umbenannt), "Blattvorlage", "Blattvorlagen")
                    + u(" umbenannt")
                )
            if dialog.geloescht:
                gesagt.append(
                    mehrzahl(len(dialog.geloescht), "Blattvorlage", "Blattvorlagen")
                    + u(" gelöscht")
                )
            if dialog.wiederhergestellt:
                gesagt.append(u("mitgelieferte Blattvorlagen wiederhergestellt"))
            satz = ", ".join(gesagt)
            self.statusBar().showMessage(satz[:1].upper() + satz[1:], 8000)

        if genommen:
            self.vorschau.blattvorlage_setzen(dialog.gewaehlt())

    def _blattvorlagenordner(self):
        """Wohin eine umbenannte Blattvorlage geschrieben wird."""
        try:
            return pfade.eigener_datenordner() / BLATTVORLAGENORDNER
        except OSError:
            return None

    def _blattvorlagenquellen(self) -> list:
        """Woher ihre Datei kommen kann, wenn sie im Arbeitsordner fehlt."""
        try:
            return list(pfade.blattvorlagenordner_alle())
        except OSError:
            return []

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
            u("Freitext im Rangierfeld ist zugelassen")
            if self.freitext
            else u("Im Rangierfeld sind nur Ziele zugelassen"),
            6000,
        )

    def leistenweise_waehlen(self, kennung: str) -> None:
        """Stellt um, wie die Leisten dieses Verteilers heissen.

        Die Beschriftung gehoert zum **Verteiler** - sie steht in seiner
        Projektdatei, nicht in den Einstellungen des Programms. Eine
        Vorgabe fuer den naechsten neuen gibt es darum nicht; wie bei der
        umgekehrten Belegung faengt jeder neue gezaehlt an und bekommt
        seine Beschriftung im Dialog oder hier. Gezaehlt wird innen weiter
        ab 1, und getippt werden darf beides, gleich was eingestellt ist.
        """
        kennung = einstellungsspeicher.leistenweise(kennung)
        if self.projekt is not None and self.projekt.leisten_schreibweise != kennung:
            self._stand_merken()
            self.projekt.leisten_schreibweise = kennung
            self.veraendert = True
            self._titel_setzen()
            self.aktionen_auffrischen()
        self._leistenweise_anwenden()
        beispiel = dict((k, b) for k, b, _e in LEISTENWEISEN)[kennung]
        self.statusBar().showMessage(
            u("Die Leisten heißen {0}").format(beispiel), 6000
        )

    def belegung_umkehren(self, an: bool) -> None:
        """Dreht die Leserichtung der Verteilerbelegung des offenen Projekts.

        Eine Eigenschaft der Anlage, nicht des Programms: sie steht in der
        Projektdatei und laesst sich zuruecknehmen. Nur das Blattbild der
        Belegung dreht sich - DA 1 bleibt DA 1.
        """
        if self.projekt is None:
            self.aktion_belegung_umgekehrt.setChecked(False)
            return
        if self.projekt.belegung_umgekehrt == bool(an):
            return
        self._stand_merken()
        self.projekt.belegung_umgekehrt = bool(an)
        self.veraendert = True
        self._titel_setzen()
        self.aktionen_auffrischen()
        # Zu sehen ist die Aenderung nur auf der Belegung - also dorthin.
        self._vorschau_anstossen(belegung=True)
        self.statusBar().showMessage(
            u("Die Verteilerbelegung läuft von rechts nach links")
            if an
            else u("Die Verteilerbelegung läuft von links nach rechts"),
            6000,
        )

    @property
    def leisten_schreibweise(self) -> str:
        """Wie die Leisten des offenen Verteilers heissen.

        Ohne Projekt sind die Leisten gezaehlt - dann ist ohnehin nichts
        zu beschriften.
        """
        if self.projekt is not None:
            return einstellungsspeicher.leistenweise(
                self.projekt.leisten_schreibweise
            )
        return LEISTEN_ZAHLEN

    def _leistenname(self, nummer: int) -> str:
        """Wie diese Leiste gerade heisst - "3" oder "C"."""
        return leistenname(nummer, self.leisten_schreibweise)

    def _leistenweise_anwenden(self) -> None:
        """Traegt die Beschriftung in Menue, Ansichten und Vorschau."""
        weise = self.leisten_schreibweise
        for handlung in self.leistenweisen_gruppe.actions():
            handlung.setChecked(handlung.data() == weise)
        self.leistenansicht.leisten_schreibweise_setzen(weise)
        self.uebersicht.leisten_schreibweise_setzen(weise)
        self._vorschau_anstossen()

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
            name = self.projekt.verteiler.name or u("ohne Namen")
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
            self.statusBar().showMessage(u("Leiste {0}, DA {1} — {2}").format(
                self._leistenname(leiste), da, kabel.beschriftung))
        else:
            self.statusBar().showMessage(u("Leiste {0}, DA {1} — frei").format(
                self._leistenname(leiste), da))

    # -- Zurücknehmen ------------------------------------------------------

    def _stand_merken(self) -> None:
        """Legt den Stand *vor* dieser Änderung auf den Stapel.

        Gehalten wird das Projekt als Dict - dieselbe Gestalt, in der es
        auch in seiner Datei steht. Damit taugt ein Stand fuer alles, was
        sich am Verteiler aendern laesst, ohne dass jede Aenderung ihr
        eigenes Rueckwaerts braeuchte.
        """
        if self.projekt is None or self._stand is None:
            return
        self._rueckgaengig.append(self._stand)
        del self._rueckgaengig[:-RUECKGAENGIG_SCHRITTE]
        # Ein neuer Weg: was zurueckgenommen war, ist nicht mehr zu holen.
        self._wiederherstellen.clear()
        self._stand = projektdatei.als_dict(self.projekt)

    def _stand_zeigen(self, stand: dict) -> None:
        """Setzt das Projekt auf einen gemerkten Stand zurück.

        Die gewaehlte Leiste bleibt, wo sie war: wer einen Tippfehler
        zuruecknimmt, will nicht auf Leiste 1 landen.
        """
        leiste = self.leistenansicht.modell.leiste_nr
        projekt = projektdatei.aus_dict(stand)
        self._projekt_setzen(projekt, self.pfad, vorgeschichte=True)
        self.veraendert = True
        self._titel_setzen()
        if leiste is not None:
            self.leistenansicht.leiste_zeigen(leiste)

    def rueckgaengig(self) -> None:
        """Nimmt die letzte Änderung am Verteiler zurück."""
        if self.projekt is None or not self._rueckgaengig:
            return
        self._wiederherstellen.append(projektdatei.als_dict(self.projekt))
        self._stand_zeigen(self._rueckgaengig.pop())
        self.statusBar().showMessage(
            u("Rückgängig gemacht — noch {0} Schritte möglich").format(
                len(self._rueckgaengig)
            ),
            6000,
        )

    def wiederherstellen(self) -> None:
        """Stellt wieder her, was zuletzt zurückgenommen wurde."""
        if self.projekt is None or not self._wiederherstellen:
            return
        self._rueckgaengig.append(projektdatei.als_dict(self.projekt))
        self._stand_zeigen(self._wiederherstellen.pop())
        self.statusBar().showMessage(u("Wiederhergestellt"), 6000)

    def _belegung_geaendert(self) -> None:
        self._stand_merken()
        self.veraendert = True
        self.uebersicht.update()
        self._titel_setzen()
        self.aktionen_auffrischen()
        self._vorschau_anstossen()

    def _blattvorlage_gemerkt(self, kennung: str) -> None:
        self.einstellungen.setValue("blattvorlage", kennung)
        self.statusBar().showMessage(
            u("Blattvorlage: {0}").format(self.blattvorlagen.holen(kennung).name), 6000
        )

    def _leiste_gewechselt(self, nummer: int) -> None:
        """Die Vorschau folgt der bearbeiteten Leiste."""
        self.vorschau.blatt_zeigen(f"Leiste {self._leistenname(nummer)}")

    def vorschau_zeigen(self, an: bool) -> None:
        self.vorschau.setVisible(an)
        self.einstellungen.setValue("vorschau", bool(an))
        if an:
            self._vorschau_auffrischen()

    def uebersicht_zeigen(self, an: bool) -> None:
        """Blendet die Verteileruebersicht ein oder aus."""
        self.uebersichtsbereich.setVisible(an)
        self.einstellungen.setValue("uebersicht", bool(an))
        self._linke_seite_anpassen()

    def leistenansicht_zeigen(self, an: bool) -> None:
        """Blendet die Leistenansicht ein oder aus."""
        self.leistenansicht.setVisible(an)
        self.einstellungen.setValue("leistenansicht", bool(an))
        self._linke_seite_anpassen()

    def _linke_seite_anpassen(self) -> None:
        """Sind Uebersicht und Leistenansicht aus, gehoert der Platz der Vorschau."""
        self.teiler.setVisible(
            not (self.uebersichtsbereich.isHidden() and self.leistenansicht.isHidden())
        )

    def _vorschau_anstossen(self, belegung: bool = False) -> None:
        """Sammelt schnelle Aenderungen, statt bei jedem Tastendruck neu zu bauen.

        ``belegung`` laesst die Vorschau danach die Verteilerbelegung
        zeigen - fuer Aenderungen, die man nur dort sieht.
        """
        self._vorschau_belegung = self._vorschau_belegung or belegung
        if self.vorschau.isVisible():
            self.vorschau_takt.start()

    def _vorschau_auffrischen(self) -> None:
        self.vorschau.aktualisieren()
        # Wer eine Aenderung am Belegungsblatt angestossen hat, will sie
        # auch sehen: dieses Blatt geht dann dem der gewaehlten Leiste vor.
        if self._vorschau_belegung:
            self._vorschau_belegung = False
            if self.vorschau.belegung_zeigen():
                return
        nummer = self.leistenansicht.modell.leiste_nr
        if nummer is not None:
            self.vorschau.blatt_zeigen(f"Leiste {self._leistenname(nummer)}")

    # -- Projekt -----------------------------------------------------------

    def _projekt_setzen(
        self,
        projekt: Projekt | None,
        pfad: pathlib.Path | None,
        vorgeschichte: bool = False,
    ) -> None:
        """Zeigt ein Projekt - ein neues, ein geoeffnetes, ein zurueckgenommenes.

        ``vorgeschichte`` behaelt die Staende zum Zuruecknehmen. Nur das
        Zuruecknehmen selbst setzt es: ein anderes Projekt hat eine
        andere Vorgeschichte, und ein Stand von vorhin gehoerte zu einem
        anderen Verteiler.
        """
        self.projekt = projekt
        self.pfad = pfad
        self.veraendert = False
        if not vorgeschichte:
            self._rueckgaengig.clear()
            self._wiederherstellen.clear()
        self._stand = (
            projektdatei.als_dict(projekt) if projekt is not None else None
        )
        verteiler = projekt.verteiler if projekt else None
        if projekt is not None:
            projekt.rangierung_schreibweise = self.schreibweise.id
        self.uebersicht.verteiler_setzen(verteiler)
        self.leistenansicht.verteiler_setzen(verteiler)
        self.leistenansicht.schreibweise_setzen(self.schreibweise)
        self.leistenansicht.freitext_erlauben(self.freitext)
        # Wie die Leisten heissen, bringt das Projekt mit - Menue und
        # Ansichten folgen ihm, nicht umgekehrt.
        self._leistenweise_anwenden()
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
        # Der Haken zeigt, wie das offene Projekt dasteht - ohne Projekt
        # gibt es nichts zu umkehren.
        self.aktion_belegung_umgekehrt.setEnabled(offen)
        self.aktion_belegung_umgekehrt.setChecked(
            offen and self.projekt.belegung_umgekehrt
        )
        # Ebenso die Beschriftung: sie gehoert dem offenen Verteiler.
        self.leistennamen_menue.setEnabled(offen)
        for handlung in self.leistenweisen_gruppe.actions():
            handlung.setChecked(handlung.data() == self.leisten_schreibweise)
        self.aktion_rueckgaengig.setEnabled(offen and bool(self._rueckgaengig))
        self.aktion_wiederherstellen.setEnabled(
            offen and bool(self._wiederherstellen)
        )
        for handlung in (
            self.aktion_speichern_unter,
            self.aktion_pdf,
            self.aktion_xlsx,
            self.aktion_csv,
            self.aktion_kabel,
            self.aktion_vorlage,
            self.aktion_suchen,
            self.aktion_projektdaten,
            self.aktion_export,
        ):
            handlung.setEnabled(offen)
        self.export_knopf.setEnabled(offen)
        self.exportmenue.setEnabled(offen)

        # Speichern nur, wenn es etwas zu speichern gibt: ungesicherte
        # Änderungen oder eine Datei, die es noch nicht gibt.
        self.aktion_speichern.setEnabled(
            offen and (self.veraendert or self.pfad is None)
        )
        hat_kabel = self._kabel_der_auswahl() is not None
        self.aktion_kabel_weg.setEnabled(hat_kabel)
        self.aktion_kabel_aendern.setEnabled(hat_kabel)

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
            u("Änderungen verwerfen?"),
            u("Der Verteiler wurde geändert und noch nicht gespeichert."),
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
        # Die gemerkten Vorgaben stehen schon im Dialog und sind dort für
        # diesen Verteiler zu ändern.
        gemerkt, ausgeblendet = einstellungsspeicher.briefkopf_laden(
            self.einstellungen
        )
        # Angehakt ist, was die Vorgaben füllen - ein leeres Feld gehört
        # auf kein Blatt, bis jemand es ausfüllt.
        ausgeblendet = set(ausgeblendet) | {
            name for name in BRIEFKOPF_FELDER if not gemerkt.get(name)
        }
        dialog = NeuerVerteilerDialog(
            self.vorlagen, self, self._vorlagenordner(), gemerkt, ausgeblendet,
            self.blattvorlagen, self.vorschau.blattvorlage.id,
        )
        if dialog.exec() != NeuerVerteilerDialog.DialogCode.Accepted:
            return
        self.vorschau.blattvorlage_setzen(dialog.blattvorlage())
        # Was der Dialog trägt, gilt; die Vorgaben füllen nur auf.
        projekt = self.neues_projekt(dialog.projekt())
        self._projekt_setzen(projekt, None)
        uebernommen = len(projekt.briefkopf)
        self.statusBar().showMessage(
            u("Neuer Verteiler: {0} DA auf {1}").format(
                self.projekt.verteiler.da_gesamt,
                mehrzahl(len(self.projekt.verteiler.alle_leisten), "Leiste", "Leisten"),
            )
            + (
                u(", {0} Felder Projektdaten übernommen").format(uebernommen)
                if uebernommen
                else ""
            )
        )

    def neues_projekt(self, angaben) -> Projekt:
        """Ein frisches Projekt mit den gemerkten Vorgaben.

        ``angaben`` ist ein Verteiler oder ein fertiges Projekt; im
        zweiten Fall bleibt stehen, was schon eingetragen ist - ergaenzt
        wird nur, was fehlt.
        """
        if isinstance(angaben, Projekt):
            projekt = angaben
        else:
            # Kein Dialog, kein Haken: gezaehlte Leisten, Belegung von
            # links nach rechts - beides gehoert dem Verteiler und ist
            # unter Einstellungen zu aendern.
            projekt = Projekt(verteiler=angaben)
        return einstellungsspeicher.briefkopf_uebernehmen(
            self.einstellungen, projekt
        )

    def paket_sichern(self) -> None:
        """Vorlagen, Kabeltypen und Einstellungen in eine Datei packen."""
        vorhanden = paket.bestand(
            pfade.eigener_datenordner(), pfade.einstellungsdatei()
        )
        wahl = PaketDialog(
            "Vorlagen und Einstellungen sichern",
            vorhanden,
            self,
            u("Was soll in das Paket?"),
            u("Sichern…"),
        )
        if wahl.exec() != PaketDialog.DialogCode.Accepted:
            return
        teile = wahl.auswahl()

        vorschlag = pathlib.Path.home() / f"Verteilerly-{VERSION}.zip"
        name, _ = QFileDialog.getSaveFileName(
            self, u("Vorlagen und Einstellungen sichern"), str(vorschlag), PAKETFILTER
        )
        if not name:
            return
        # Was gleich eingepackt wird, soll auf der Platte stehen.
        self.einstellungen.sync()
        try:
            bericht = paket.sichern(
                pathlib.Path(name),
                pfade.eigener_datenordner(),
                pfade.einstellungsdatei(),
                teile,
            )
        except paket.PaketFehler as fehler:
            QMessageBox.critical(self, u("Nicht gesichert"), str(fehler))
            return
        self.statusBar().showMessage(
            u("Gesichert nach {0}: {1}").format(name, self._paketbericht(bericht)), 12000
        )

    def paket_einspielen(self) -> None:
        """Ein gesichertes Paket zurueckholen."""
        name, _ = QFileDialog.getOpenFileName(
            self, u("Vorlagen und Einstellungen einspielen"), "", PAKETFILTER
        )
        if not name:
            return
        try:
            vorschau = paket.inhalt(pathlib.Path(name))
        except paket.PaketFehler as fehler:
            QMessageBox.critical(self, u("Kein Paket"), str(fehler))
            return

        wahl = PaketDialog(
            u("Paket einspielen"),
            vorschau,
            self,
            u(
                "Erstellt am {0} mit Verteilerly {1}. Was soll eingespielt "
                "werden? Gleichnamige Dateien im Arbeitsordner werden "
                "ersetzt; alles andere bleibt stehen."
            ).format(
                vorschau.get("erstellt", u("unbekannt")),
                vorschau.get("version", "?"),
            ),
            u("Einspielen"),
        )
        if wahl.exec() != PaketDialog.DialogCode.Accepted:
            return
        teile = wahl.auswahl()

        # Die Einstellungen gehen nicht als Datei an ihren Platz, sondern
        # Wert fuer Wert durch die laufenden QSettings: ein Dateitausch
        # unter ihnen faellt ihnen nicht zuverlaessig auf.
        with tempfile.TemporaryDirectory() as ordner:
            zwischen = pathlib.Path(ordner) / paket.CONFNAME
            try:
                bericht = paket.einspielen(
                    pathlib.Path(name),
                    pfade.eigener_datenordner(),
                    zwischen,
                    teile,
                )
            except paket.PaketFehler as fehler:
                QMessageBox.critical(self, u("Nicht eingespielt"), str(fehler))
                return
            if bericht.get("einstellungen"):
                self._einstellungen_uebernehmen(zwischen)

        self._nach_dem_einspielen()
        self.statusBar().showMessage(
            u("Eingespielt: {0}").format(self._paketbericht(bericht)), 12000
        )

    def _paketbericht(self, bericht: dict) -> str:
        teile = [
            f"{bericht.get(name, 0)} {u(beschriftung)}"
            for name, beschriftung in (
                ("vorlagen", "Verteilervorlagen"),
                ("blattvorlagen", "Blattvorlagen"),
                ("kabeltypen", "Kabeltypen"),
            )
        ]
        if bericht.get("einstellungen"):
            teile.append(u("die Einstellungen"))
        return ", ".join(teile)

    def _einstellungen_uebernehmen(self, datei: pathlib.Path) -> None:
        """Traegt die Werte einer eingespielten Datei in die laufenden ein."""
        quelle = QSettings(str(datei), QSettings.Format.IniFormat)
        behalten = {
            schluessel: self.einstellungen.value(schluessel)
            for schluessel in ERWEITERUNGSWAHL
            if self.einstellungen.contains(schluessel)
        }
        self.einstellungen.clear()
        for schluessel in quelle.allKeys():
            if schluessel not in ERWEITERUNGSWAHL:
                self.einstellungen.setValue(schluessel, quelle.value(schluessel))
        for schluessel, wert in behalten.items():
            self.einstellungen.setValue(schluessel, wert)
        self.einstellungen.sync()

    def _nach_dem_einspielen(self) -> None:
        """Das Eingespielte gilt sofort - ohne Neustart."""
        self.vorlagen = self._vorlagen_laden()
        self.blattvorlagen = self._blattvorlagen_laden()
        self.kabeltypen = Kabeltypen.laden(pfade.kabeltypenordner())

        self.vorschau.blattvorlagen_setzen(
            self.blattvorlagen, str(self.einstellungen.value("blattvorlage", ""))
        )
        self.thema_anwenden(str(self.einstellungen.value("thema", self.thema_name)))
        self.schreibweise = schreibweisen.holen(
            self.einstellungen.value("schreibweise", self.schreibweise.id)
        )
        self.freitext = self.einstellungen.value("freitext", self.freitext, type=bool)
        self.aktion_freitext.setChecked(self.freitext)
        self._schreibweise_anwenden()
        self._leistenweise_anwenden()
        self.vorschau.aktualisieren()

    def vorgaben_bearbeiten(self) -> None:
        """Was bei jedem neuen Verteiler schon dastehen soll.

        Firma, Kürzel, Ersteller - was sich nicht von Verteiler zu
        Verteiler ändert. Gemerkt wird nur, was hier eingetragen ist;
        bearbeitete Projektdaten ändern die Vorgaben nicht mehr von
        selbst, sonst überschriebe der letzte Kunde sie ungefragt.
        """
        briefkopf, ausgeblendet = einstellungsspeicher.briefkopf_laden(
            self.einstellungen
        )
        muster = Projekt(
            briefkopf=briefkopf,
            ausgeblendet=ausgeblendet,
            beschriftungen=einstellungsspeicher.beschriftungen_laden(
                self.einstellungen
            ),
        )
        dialog = ProjektdatenDialog(muster, self, vorgaben=True, quelle=self.projekt)
        if dialog.exec() != ProjektdatenDialog.DialogCode.Accepted:
            return
        dialog.uebernehmen()
        einstellungsspeicher.briefkopf_sichern(self.einstellungen, muster)
        self.statusBar().showMessage(
            u("Vorgaben gemerkt: {0} Felder stehen im nächsten neuen Verteiler schon da").format(len(muster.briefkopf)),
            8000,
        )

    def oeffnen(self) -> None:
        if not self._darf_verwerfen():
            return
        name, _ = QFileDialog.getOpenFileName(self, u("Verteiler öffnen"), "", DATEIFILTER)
        if name:
            self.datei_oeffnen(pathlib.Path(name))

    def datei_oeffnen(self, pfad: pathlib.Path) -> bool:
        """Oeffnet diese Datei - aus dem Dialog wie vom Doppelklick.

        Der Weg ueber die Dateiverwaltung kommt ohne Dialog hierher; was
        schiefgeht, wird darum hier gemeldet und nicht weitergereicht.
        """
        pfad = pathlib.Path(pfad)
        try:
            projekt = projektdatei.laden(pfad)
        except (ModellFehler, OSError) as fehler:
            QMessageBox.critical(self, u("Öffnen fehlgeschlagen"), str(fehler))
            return False
        self._projekt_setzen(projekt, pfad)
        self.statusBar().showMessage(u("Geöffnet: {0}").format(pfad))
        return True

    def speichern(self) -> bool:
        if self.projekt is None:
            return False
        if self.pfad is None:
            return self.speichern_unter()
        try:
            projektdatei.speichern(self.projekt, self.pfad)
        except OSError as fehler:
            QMessageBox.critical(self, u("Speichern fehlgeschlagen"), str(fehler))
            return False
        self.veraendert = False
        self._titel_setzen()
        self.aktionen_auffrischen()
        self.statusBar().showMessage(u("Gespeichert: {0}").format(self.pfad))
        return True

    def speichern_unter(self) -> bool:
        if self.projekt is None:
            return False
        vorschlag = self.projekt.verteiler.name or "verteiler"
        name, _ = QFileDialog.getSaveFileName(
            self, u("Verteiler speichern"), f"{vorschlag}{DATEIENDUNG}", DATEIFILTER
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
            self, u("Ausgeben nach"), str(ordner / f"{stamm}{endung}"), filter_
        )
        return pathlib.Path(name) if name else None

    # -- Export ------------------------------------------------------------

    def _exportknopf_bauen(self, werkzeuge) -> None:
        """Ein Knopf mit Pfeil: links das gewählte Format, rechts die Wahl.

        Auf dem Knopf steht, was ein Druck bewirkt - "Export (PDF)". Der
        Pfeil öffnet dasselbe Menü, das auch unter *Datei ▸ Exportieren*
        steht; was dort gewählt wird, steht danach auf dem Knopf und
        bleibt bis zum nächsten Mal.
        """
        self.aktion_export = QAction(self)
        self.aktion_export.triggered.connect(self.exportieren)
        self.export_knopf = QToolButton(self)
        self.export_knopf.setDefaultAction(self.aktion_export)
        self.export_knopf.setMenu(self.exportmenue)
        self.export_knopf.setPopupMode(
            QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )
        self.export_knopf.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextOnly
        )
        werkzeuge.addWidget(self.export_knopf)
        self.exportformat_setzen(
            str(self.einstellungen.value("exportformat", "pdf")), ausgeben=False
        )

    def _ansichtsaktionen(self) -> dict[str, QAction]:
        """Die drei Bereiche des Fensters und ihre Schalter unter *Ansicht*."""
        return {
            "uebersicht": self.aktion_uebersicht,
            "leistenansicht": self.aktion_leistenansicht,
            "vorschau": self.aktion_vorschau,
        }

    def _ansichtsknopf_bauen(self, werkzeuge) -> None:
        """Ein Knopf mit Pfeil wie der Exportknopf: links der gewaehlte Bereich.

        Auf dem Knopf steht, welchen Bereich ein Druck ein- und ausblendet;
        eingedrueckt ist er, solange der Bereich zu sehen ist. Der Pfeil
        klappt die drei Bereiche auf - eine Wahl dort schaltet sofort und
        legt den Bereich auf den Knopf. Die Eintraege sind eigene Aktionen,
        deren Haken den Schaltern unter *Ansicht* folgen: haengten dort
        dieselben Aktionen, stellten auch F7/F8 den Knopf um.
        """
        self.ansichtsmenue = QMenu(self)
        self.ansichtswahl: dict[str, QAction] = {}
        for kennung, aktion in self._ansichtsaktionen().items():
            eintrag = QAction(aktion.text(), self.ansichtsmenue)
            eintrag.setCheckable(True)
            eintrag.setChecked(aktion.isChecked())
            aktion.toggled.connect(eintrag.setChecked)
            eintrag.triggered.connect(
                lambda _an=False, kennung=kennung: self._ansicht_gewaehlt(kennung)
            )
            self.ansichtsmenue.addAction(eintrag)
            self.ansichtswahl[kennung] = eintrag
        self.ansicht_knopf = QToolButton(self)
        self.ansicht_knopf.setMenu(self.ansichtsmenue)
        self.ansicht_knopf.setPopupMode(
            QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )
        self.ansicht_knopf.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextOnly
        )
        werkzeuge.addWidget(self.ansicht_knopf)
        self.ansichtsknopf_setzen(
            str(self.einstellungen.value("ansichtsknopf", "vorschau"))
        )

    def ansichtsknopf_setzen(self, kennung: str) -> None:
        """Legt fest, welchen Bereich ein Druck auf den Knopf schaltet."""
        aktionen = self._ansichtsaktionen()
        if kennung not in aktionen:
            kennung = "vorschau"
        self.ansicht_knopf.setDefaultAction(aktionen[kennung])
        self.ansichtsknopf = kennung
        self.einstellungen.setValue("ansichtsknopf", kennung)

    def _ansicht_gewaehlt(self, kennung: str) -> None:
        """Wie beim Export: die Wahl wirkt sofort und bleibt auf dem Knopf."""
        self.ansichtsknopf_setzen(kennung)
        self._ansichtsaktionen()[kennung].trigger()

    def exportformat_setzen(self, kennung: str, ausgeben: bool = True) -> None:
        """Merkt das Format, beschriftet den Knopf - und gibt aus."""
        bekannt = {k: (name, ruf) for k, name, ruf in EXPORTFORMATE}
        if kennung not in bekannt:
            kennung = "pdf"
        self.exportformat = kennung
        self.einstellungen.setValue("exportformat", kennung)
        name = bekannt[kennung][0]
        self.aktion_export.setText(u("Export ({0})").format(name))
        hinweis = u("Gibt den Verteiler als {0} aus; der Pfeil wählt das Format").format(
            name
        )
        self.aktion_export.setStatusTip(hinweis)
        self.aktion_export.setToolTip(hinweis)
        if ausgeben:
            getattr(self, bekannt[kennung][1])()

    def exportieren(self) -> None:
        """Der Knopf selbst: ausgeben, was daneben steht."""
        bekannt = {k: ruf for k, _, ruf in EXPORTFORMATE}
        getattr(self, bekannt.get(self.exportformat, "pdf_ausgeben"))()

    def pdf_ausgeben(self) -> None:
        """PDF ist das Pflichtformat - welche Blaetter hinein, fragt ein Dialog."""
        self._format_merken("pdf")
        if self.projekt is None:
            return
        blattarten = self._pdf_blaetter_waehlen()
        if not blattarten:
            return
        ziel = self._ausgabeziel(".pdf", PDFFILTER)
        if ziel is None:
            return
        vorlage = self.vorschau.blattvorlage
        self._ausgeben(
            lambda: pdf_schreiben(self.projekt, ziel, vorlage, blattarten), ziel
        )

    def _pdf_blaetter_waehlen(self) -> set[str] | None:
        """Fragt, welche Blattarten ins PDF kommen - die letzte Wahl steht vor.

        Gemerkt wird als Text mit Kommas: eine Liste gibt QSettings bei
        einem einzigen Eintrag als blossen Text zurueck.
        """
        gemerkt = str(self.einstellungen.value("pdf_blaetter", ",".join(BLATTARTEN)))
        gewaehlt = {art for art in gemerkt.split(",") if art in BLATTARTEN}
        anzahlen = {
            "deckblatt": 1,
            "belegung": len(verteilerbelegungen(self.projekt, self.vorschau.blattvorlage)),
            "leisten": len(self.projekt.verteiler.alle_leisten),
        }
        dialog = BlattwahlDialog(anzahlen, gewaehlt or set(BLATTARTEN), self)
        if dialog.exec() != BlattwahlDialog.DialogCode.Accepted:
            return None
        auswahl = dialog.auswahl()
        self.einstellungen.setValue(
            "pdf_blaetter", ",".join(art for art in BLATTARTEN if art in auswahl)
        )
        return auswahl

    def xlsx_ausgeben(self) -> None:
        self._format_merken("xlsx")
        ziel = self._ausgabeziel(".xlsx", XLSXFILTER)
        if ziel is None:
            return
        # Dieselbe Blattvorlage wie für die Vorschau und das PDF.
        self._ausgeben(
            lambda: xlsx_schreiben(self.projekt, ziel, self.vorschau.blattvorlage),
            ziel,
        )

    def csv_ausgeben(self) -> None:
        self._format_merken("csv")
        ziel = self._ausgabeziel(".csv", CSVFILTER)
        if ziel is None:
            return
        self._ausgeben(lambda: csv_schreiben(self.projekt, ziel), ziel)

    def _format_merken(self, kennung: str) -> None:
        """Was zuletzt gewählt wurde, steht danach auf dem Knopf."""
        if getattr(self, "exportformat", None) != kennung:
            self.exportformat_setzen(kennung, ausgeben=False)

    def _ausgeben(self, arbeit, ziel: pathlib.Path) -> None:
        try:
            arbeit()
        except (AusgabeFehler, OSError) as fehler:
            QMessageBox.critical(self, u("Ausgabe fehlgeschlagen"), str(fehler))
            return
        self.statusBar().showMessage(u("Geschrieben: {0}").format(ziel))

    # -- Kabel -------------------------------------------------------------

    def kabel_auflegen(self, leiste: int | None = None, start_da: int | None = None) -> None:
        """Kabel auflegen, samt Rückfrage bei Überlauf."""
        if self.projekt is None:
            return
        verteiler = self.projekt.verteiler
        if leiste is None or not isinstance(leiste, int):
            stelle = self.uebersicht.auswahl or (verteiler.alle_leisten[0].nummer, 1)
            leiste, start_da = stelle
        dialog = KabelDialog(
            verteiler, self.kabeltypen, leiste, start_da or 1, self,
            leisten=self.leisten_schreibweise,
        )
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
            QMessageBox.warning(self, u("Kabel nicht aufgelegt"), str(fehler))
            return

        gefuellt = farben_eintragen(verteiler, kabel, self.kabeltypen)
        self._belegung_geaendert()
        self.leistenansicht.aktualisieren()

        meldung = u("Kabel aufgelegt: {0} DA").format(kabel.da_aufgelegt)
        if gefuellt:
            meldung += u(", {0} Adernfarben eingetragen").format(gefuellt)
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
        dialog = UeberlaufDialog(
            verteiler, ueberlauf.passend, ueberlauf.rest, self,
            leisten=self.leisten_schreibweise,
        )
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
            QMessageBox.warning(self, u("Kabel nicht aufgelegt"), str(fehler))
            return None

    def _kabel_angeklickt(self, kabel) -> None:
        """Doppelklick auf ein Kabel: bearbeiten."""
        self.kabel_bearbeiten(kabel)

    def kabel_bearbeiten(self, kabel=None) -> None:
        """Beschriftung, Kabeltyp und Größe eines Kabels ändern.

        Leiste und Startpunkt bleiben, wie sie sind - dort hängt das
        Kabel. Wie viel davon aufliegt, wächst und schrumpft dagegen am
        Ende; passt die Verlängerung nicht mehr, fragt der Überlaufdialog
        wie beim Auflegen. Der Dialog trägt auch den Knopf zum
        Entfernen.
        """
        if self.projekt is None:
            return
        kabel = kabel if kabel is not None else self._kabel_der_auswahl()
        if kabel is None:
            return

        abschnitt = kabel.abschnitte[0]
        dialog = KabelDialog(
            self.projekt.verteiler, self.kabeltypen,
            abschnitt.leiste, abschnitt.start_da, self, kabel=kabel,
            leisten=self.leisten_schreibweise,
        )
        if dialog.exec() != KabelDialog.DialogCode.Accepted:
            return

        angaben = dialog.angaben()
        if angaben["entfernen"]:
            self._kabel_abnehmen(kabel)
            return

        # Der bisherige Farbplan ist der Massstab: was noch genau so
        # dasteht, hat die Automatik gesetzt und darf ihr folgen.
        vorher = farbplan(self.projekt.verteiler, kabel, self.kabeltypen)

        kabel.beschriftung = angaben["beschriftung"]
        kabel.kabeltyp = angaben["kabeltyp"]
        if not self._auflegen_aendern(kabel, angaben["anzahl_da"]):
            return
        kabel.da_gesamt = max(angaben["da_gesamt"], kabel.da_aufgelegt)

        gefuellt = farben_eintragen(
            self.projekt.verteiler, kabel, self.kabeltypen,
            ueberschreiben=angaben["farben_neu"], statt=vorher,
        )
        geleert = farben_verwaist_loeschen(
            self.projekt.verteiler, vorher,
            farbplan(self.projekt.verteiler, kabel, self.kabeltypen),
        )
        self._belegung_geaendert()
        self.leistenansicht.aktualisieren()

        meldung = u("Kabel geändert: {0}").format(kabel.beschriftung or u("ohne Beschriftung"))
        if gefuellt:
            meldung += u(", {0} Adernfarben nachgezogen").format(gefuellt)
            meldung += self._lagenhinweis(kabel)
        if geleert:
            meldung += u(", {0} Adernfarben freigeräumt").format(geleert)
        self.statusBar().showMessage(meldung, 8000)

    def _auflegen_aendern(self, kabel, anzahl_da: int) -> bool:
        """Legt mehr oder weniger Doppeladern auf.

        Gibt zurueck, ob es geklappt hat; bei einem Ueberlauf entscheidet
        der Anwender, ob fortgesetzt wird oder der Rest verfaellt.
        """
        verteiler = self.projekt.verteiler
        try:
            verteiler.kabel_auflegen_aendern(kabel, anzahl_da)
            return True
        except UeberlaufFehler as ueberlauf:
            return self._ueberlauf_beim_wachsen(kabel, ueberlauf)
        except ModellFehler as fehler:
            QMessageBox.warning(self, u("Kabel nicht geändert"), str(fehler))
            return False

    def _ueberlauf_beim_wachsen(self, kabel, ueberlauf: UeberlaufFehler) -> bool:
        """Das Kabel waechst ueber seine Leiste hinaus."""
        verteiler = self.projekt.verteiler
        dialog = UeberlaufDialog(
            verteiler, ueberlauf.passend, ueberlauf.rest, self,
            leisten=self.leisten_schreibweise,
        )
        if dialog.exec() != UeberlaufDialog.DialogCode.Accepted:
            return False

        wahl, leiste, start = dialog.entscheidung()
        try:
            # So weit es auf der eigenen Leiste geht, geht es zuerst.
            verteiler.kabel_auflegen_aendern(kabel, ueberlauf.passend)
            if wahl == UeberlaufDialog.FORTSETZEN:
                verteiler.kabel_verlaengern(kabel, leiste, start, ueberlauf.rest)
        except ModellFehler as fehler:
            QMessageBox.warning(self, u("Kabel nicht geändert"), str(fehler))
            return False
        return True

    def kabel_entfernen(self) -> None:
        """Der Eintrag ist nur da anklickbar, wo wirklich ein Kabel liegt."""
        kabel = self._kabel_der_auswahl()
        if kabel is None:
            return
        antwort = frage(
            self,
            u("Kabel entfernen?"),
            u("Das Kabel „{0}“ von der Leiste nehmen?\nSeine Adernfarben werden mit entfernt; von Hand eingetragene bleiben stehen.").format(kabel.beschriftung),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if antwort == QMessageBox.StandardButton.Yes:
            self._kabel_abnehmen(kabel)

    def _kabel_umlegen(self, kabel, leiste: int, start_da: int, kopieren: bool) -> None:
        """Ein Kabel wurde woandershin gezogen: verschieben oder kopieren.

        Gezogen wird in der Verteileruebersicht; mit Strg wird kopiert.
        Was nicht passt, sagt die Statuszeile - ein Fenster dafuer
        aufzumachen waere fuer eine Mausbewegung zu viel.
        """
        if self.projekt is None:
            return
        verteiler = self.projekt.verteiler
        name = kabel.beschriftung or u("ohne Beschriftung")
        try:
            if kopieren:
                verteiler.kabel_kopieren(
                    kabel, leiste, start_da,
                    u("{0} (Kopie)").format(kabel.beschriftung)
                    if kabel.beschriftung
                    else "",
                )
            else:
                verteiler.kabel_verschieben(kabel, leiste, start_da)
        except ModellFehler as fehler:
            self.statusBar().showMessage(str(fehler), 8000)
            return
        self._belegung_geaendert()
        self.leistenansicht.aktualisieren()
        self.aktionen_auffrischen()
        wohin = u("Leiste {0}, ab DA {1}").format(
            self._leistenname(leiste), start_da
        )
        self.statusBar().showMessage(
            (u("Kabel kopiert: {0} nach {1}") if kopieren
             else u("Kabel verschoben: {0} nach {1}")).format(name, wohin),
            8000,
        )

    def _kabel_abnehmen(self, kabel) -> None:
        # Die Farbfolge gehoert zum Kabel: ist es weg, gehoert sie nicht
        # mehr in die Leiste - sonst stuende sie noch da, wenn die
        # naechste Leitung mit einer anderen Folge aufliegt.
        geleert = farben_loeschen(self.projekt.verteiler, kabel, self.kabeltypen)
        self.projekt.verteiler.kabel_entfernen(kabel)
        self._belegung_geaendert()
        self.leistenansicht.aktualisieren()
        self.aktionen_auffrischen()
        meldung = u("Kabel entfernt: {0}").format(kabel.beschriftung or u("ohne Beschriftung"))
        if geleert:
            meldung += u(", {0} Adernfarben mit entfernt").format(geleert)
        self.statusBar().showMessage(meldung, 8000)

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

    def vorlage_pruefen(self, art: str) -> None:
        """Eine Vorlagendatei prüfen, bevor sie eingespielt wird.

        Gelesen wird sie mit denselben Funktionen wie im Betrieb; der
        Bericht sagt, ob sie taugt, was darin steht und was auffiel.
        """
        wie = dict(pruefung.ARTEN).get(art, art)
        name, _ = QFileDialog.getOpenFileName(
            self,
            u("{0} prüfen").format(u(wie)),
            str(self._pruefordner(art)),
            u("Vorlagendateien (*.yaml *.yml);;Alle Dateien (*)"),
        )
        if not name:
            return
        bericht = pruefung.pruefen(pathlib.Path(name), art)
        PruefberichtDialog(bericht, self).exec()
        self.statusBar().showMessage(
            f"{pathlib.Path(name).name}: {bericht.urteil}", 8000
        )

    def _pruefordner(self, art: str) -> pathlib.Path:
        """Wo der Dateidialog aufgeht - beim passenden Unterordner."""
        unterordner = {
            "vorlage": VORLAGENORDNER,
            "blattvorlage": BLATTVORLAGENORDNER,
            "kabeltypen": "kabeltypen",
        }.get(art, "")
        try:
            ordner = pfade.eigener_datenordner() / unterordner
            if ordner.is_dir():
                return ordner
        except OSError:
            pass
        return pathlib.Path.home()

    def _blattvorlagen_laden(self, hinweise=None) -> Blattvorlagen:
        """Alle Blattvorlagen; eigene gehen vor mitgelieferten.

        Eine selbst geschriebene Vorlage kann Fehler haben. Sie wird dann
        uebergangen, der Grund kommt auf den Zettel ``hinweise`` - das
        Programm laeuft mit den uebrigen weiter.
        """
        try:
            orte = list(reversed(pfade.blattvorlagenordner_alle()))
            weg = pfade.geloeschte()
        except OSError:
            orte, weg = [], set()
        eigener = hinweise if hinweise is not None else []
        vorher = len(eigener)
        vorlagen = Blattvorlagen.aus_ordnern(orte, weg, eigener)
        if hinweise is None and len(eigener) > vorher:
            self._hinweise_zeigen(eigener)
        return vorlagen

    # -- Erweiterungen ------------------------------------------------------

    def _erweiterungswahl(self) -> tuple[set[str], set[str]]:
        """(eingeschaltete fremde, ausgeschaltete eingebaute) aus der Conf."""
        return (
            erweiterungen.wahl_lesen(self.einstellungen.value("erweiterungen_an", "")),
            erweiterungen.wahl_lesen(self.einstellungen.value("erweiterungen_aus", "")),
        )

    def _ohne_fremde(self) -> bool:
        """Nur fuer diesen Lauf abgeschaltet - ``--ohne-fremde-erweiterungen``."""
        return bool(os.environ.get(erweiterungen.OHNE_FREMDE))

    def _nur_eingebaute(self) -> bool:
        """Auf Dauer abgeschaltet - der Haken in *Erweiterungen verwalten*.

        Von Haus aus gesetzt: wer eigene Erweiterungen will, nimmt ihn
        bewusst heraus.
        """
        return self.einstellungen.value(
            "erweiterungen_nur_eingebaute", True, type=bool
        )

    def _erweiterungen_einrichten(self) -> None:
        """Findet die Erweiterungen und laesst die eingeschalteten sich eintragen.

        Was dabei schiefgeht, nimmt das Programm nicht mit: die Erweiterung
        wird uebergangen, der Grund einmal gezeigt und im Dialog
        *Erweiterungen verwalten* festgehalten.
        """
        try:
            orte = pfade.erweiterungsordner_alle()
        except OSError:
            orte = []
        self.erweiterungen = erweiterungen.finden(orte)
        an, aus = self._erweiterungswahl()
        uebergangen = []
        for fund in self.erweiterungen:
            if not erweiterungen.eingeschaltet(fund, an, aus):
                continue
            if not fund.eingebaut and (self._ohne_fremde() or self._nur_eingebaute()):
                continue
            erweiterungen.laden(fund)
            if fund.erweiterung is not None and not fund.fehler:
                try:
                    fund.erweiterung.einrichten(Schnittstelle(
                        self, self.erweiterungsmenue, self._erweiterungstrenner, fund
                    ))
                except Exception as fehler:  # noqa: BLE001 - Code einer Erweiterung
                    fund.fehler = f"{type(fehler).__name__}: {fehler}"
            if fund.fehler:
                uebergangen.append(f"{u(fund.name)}: {fund.fehler}")
        if uebergangen:
            QMessageBox.warning(
                self, u("Erweiterungen übergangen"),
                u("Diese Erweiterungen wurden nicht geladen; das Programm läuft "
                  "ohne sie weiter.\n\n{0}").format("\n".join(uebergangen)),
            )

    def verknuepfung_zeigen(self) -> None:
        """Sagt, welche Datei zu verknuepfen ist und wer gerade oeffnet.

        Eingetragen wird **nichts**: die Wahl des Anwenders geht jeder
        Anmeldung vor, und eine Ausgabe mit Starter kann sich ohnehin nicht
        selbst eintragen. Also die Auskunft, die man braucht, um es in der
        Dateiverwaltung selbst zu tun - und der Weg dorthin.
        """
        if not verknuepfung.moeglich():
            return
        QMessageBox.information(
            self, u("Projektdateien verknüpfen"), self._verknuepfungstext()
        )

    def _verknuepfungstext(self) -> str:
        """Der ganze Auskunftstext - Datei, Zustand und der Weg dorthin."""
        ziel = verknuepfung.zu_verknuepfen()
        eingetragen = verknuepfung.angemeldeter_aufruf()
        teile = [
            u("Ein Doppelklick auf eine Projektdatei ({0}) öffnet Verteilerly, "
              "sobald die Dateiverwaltung sie mit der richtigen Datei "
              "verknüpft hat.").format(DATEIENDUNG)
        ]
        teile.append(
            u("Zu verknüpfen ist:\n{0}").format(ziel)
            if ziel is not None
            else u("Zu verknüpfen ist: nichts — dieses Verteilerly läuft aus "
                   "dem Quelltext, nicht als fertiges Programm.")
        )
        teile.append(
            u("Bei der PortableApps-Ausgabe ist das die "
              "VerteilerlyPortable.exe, nicht das Programm in "
              "App\\Verteilerly; als AppImage die Abbilddatei selbst.")
        )
        if verknuepfung.angemeldet():
            teile.append(u("Verknüpft: ja — Projektdateien öffnen Verteilerly."))
        elif eingetragen == verknuepfung.KEINE:
            teile.append(
                u("Verknüpft: nein — die Zuordnung ist ausdrücklich "
                  "weggenommen, es öffnet niemand.")
            )
        elif eingetragen:
            teile.append(
                u("Verknüpft: nein — geöffnet wird zurzeit:\n{0}").format(
                    eingetragen
                )
            )
        else:
            teile.append(u("Verknüpft: nein — es ist nichts eingetragen."))
        teile.append(
            u("So wird verknüpft: Rechtsklick auf eine Projektdatei ▸ Öffnen "
              "mit ▸ Andere App ▸ Immer diese App (Windows) oder ▸ Öffnen mit "
              "▸ Andere Anwendung (Linux) — und dort die Datei von oben "
              "wählen.")
        )
        return "\n\n".join(teile)

    def erweiterungen_verwalten(self) -> None:
        """Erweiterungen ein- und ausschalten - wirksam ab dem naechsten Start."""
        an, aus = self._erweiterungswahl()
        try:
            ordner = pfade.erweiterungsordner()
        except OSError:
            ordner = None
        nur_eingebaute = self._nur_eingebaute()
        dialog = ErweiterungenDialog(
            self.erweiterungen, an, aus, ordner, self._ohne_fremde(), self,
            nur_eingebaute=nur_eingebaute,
        )
        if dialog.exec() != ErweiterungenDialog.DialogCode.Accepted:
            return
        neu_an, neu_aus = dialog.wahl()
        neu_nur_eingebaute = dialog.nur_eingebaute()
        if (neu_an, neu_aus, neu_nur_eingebaute) == (an, aus, nur_eingebaute):
            return
        self.einstellungen.setValue("erweiterungen_an", erweiterungen.wahl_schreiben(neu_an))
        self.einstellungen.setValue("erweiterungen_aus", erweiterungen.wahl_schreiben(neu_aus))
        self.einstellungen.setValue("erweiterungen_nur_eingebaute", neu_nur_eingebaute)
        self.statusBar().showMessage(
            u("Die Wahl der Erweiterungen gilt ab dem nächsten Start"), 8000
        )

    def blattvorlagen_neu_laden(self) -> None:
        """Liest die Blattvorlagen neu ein - etwa nach dem Speichern einer neuen."""
        self.blattvorlagen = self._blattvorlagen_laden()
        self.vorschau.blattvorlagen_setzen(
            self.blattvorlagen, self.vorschau.blattvorlage.id
        )

    def _hinweise_zeigen(self, hinweise=None) -> None:
        """Zeigt einmal, was beim Lesen der Vorlagen auffiel."""
        gesammelt = self.hinweise if hinweise is None else hinweise
        if not gesammelt:
            return
        QMessageBox.warning(
            self,
            mehrzahl(len(gesammelt), "Vorlage", "Vorlagen") + u(" beanstandet"),
            u("Was nicht stimmt, steht dahinter. Die übrigen Vorlagen "
              "stehen weiter zur Wahl.\n\n{0}").format("\n".join(gesammelt)),
        )

    def _vorlagen_laden(self, hinweise=None) -> Vorlagen:
        """Alle Vorlagenordner zusammen; eigene gehen vor mitgelieferten.

        Was der Anwender geloescht hat, bleibt draussen - die
        mitgelieferte Datei liegt im Abbild weiter.
        """
        try:
            orte = list(reversed(pfade.vorlagenordner_alle()))
            weg = pfade.geloeschte()
        except OSError:
            orte, weg = [], set()
        return Vorlagen.aus_ordnern(orte, weg, hinweise)

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
            beschreibung=u("Nach dem Verteiler {0}.").format(verteiler.name) if verteiler.name else "",
        )

    def vorlagen_verwalten(self) -> None:
        """Verteilervorlagen umbenennen, löschen, zurückholen."""
        dialog = VerteilervorlagenDialog(
            self.vorlagen, self._vorlagenordner(), self
        )
        dialog.exec()

        for kennung in dialog.geloescht:
            # Eine mitgelieferte Vorlage liegt im Abbild weiter; ohne
            # Vermerk legte der nächste Start sie wieder aus.
            pfade.loeschen_merken(f"{VORLAGENORDNER}/{kennung}.yaml")
        if dialog.wiederhergestellt:
            self._vorlagen_wiederherstellen()

        self.vorlagen = self._vorlagen_laden()
        if dialog.geloescht or dialog.umbenannt or dialog.wiederhergestellt:
            gesagt = []
            if dialog.umbenannt:
                gesagt.append(mehrzahl(len(dialog.umbenannt), "Vorlage", "Vorlagen")
                              + u(" umbenannt"))
            if dialog.geloescht:
                gesagt.append(mehrzahl(len(dialog.geloescht), "Vorlage", "Vorlagen")
                              + u(" gelöscht"))
            if dialog.wiederhergestellt:
                gesagt.append(u("mitgelieferte Vorlagen wiederhergestellt"))
            satz = ", ".join(gesagt)
            self.statusBar().showMessage(satz[:1].upper() + satz[1:], 8000)

    def _vorlagen_wiederherstellen(self) -> None:
        """Holt die mitgelieferten Verteilervorlagen zurück."""
        self._mitgeliefertes_wiederherstellen(VORLAGENORDNER)

    def _mitgeliefertes_wiederherstellen(self, unterordner: str) -> None:
        """Legt einen Unterordner wieder so hin, wie er ausgeliefert wurde.

        Derselbe Weg für Verteiler- und Blattvorlagen: erst
        die Löschvermerke aufheben, dann die mitgelieferten Dateien
        zurückkopieren. Eigene bleiben liegen - sie heißen anders.
        """
        try:
            ordner = pfade.eigener_datenordner() / unterordner
        except OSError:
            return
        pfade.loeschvermerke_aufheben(unterordner)
        quelle = pfade.mitgeliefert()
        if quelle is None or not (quelle / unterordner).is_dir():
            return
        try:
            ordner.mkdir(parents=True, exist_ok=True)
            for datei in sorted((quelle / unterordner).glob("*.yaml")):
                shutil.copy2(datei, ordner / datei.name)
        except OSError as fehler:
            QMessageBox.warning(self, u("Nicht wiederhergestellt"), str(fehler))
            return
        # Der Merkzettel gilt danach wieder: die Dateien liegen so da,
        # wie sie ausgelegt wurden.
        self.ausgelegt = pfade.grundausstattung_auslegen()

    def suchen(self) -> None:
        """Im Verteiler suchen und zur Fundstelle springen."""
        if self.projekt is None:
            return
        dialog = SuchDialog(
            self.projekt, self.schreibweise, self.zuletzt_gesucht, self
        )
        if dialog.exec() != SuchDialog.DialogCode.Accepted:
            self.zuletzt_gesucht = dialog.suchfeld.text()
            return
        self.zuletzt_gesucht = dialog.suchfeld.text()
        self._zur_fundstelle(dialog.gewaehlt)

    def _zur_fundstelle(self, fund) -> None:
        """Zeigt, wo das Gesuchte steht - in der Leiste oder im Dialog."""
        if fund is None:
            return
        if fund.bereich == suche.PROJEKTDATEN:
            # Dort steht es nicht in einer Zelle, sondern in einem Feld:
            # der Dialog ist die Fundstelle.
            self.projektdaten_bearbeiten()
            return
        if fund.adresse is None:
            return
        if self.leistenansicht.stelle_zeigen(fund.adresse, fund.feld):
            self.statusBar().showMessage(
                u("{0} · {1}: {2}").format(fund.ort, fund.beschriftung, fund.text), 8000
            )

    def projektdaten_bearbeiten(self) -> None:
        if self.projekt is None:
            return
        dialog = ProjektdatenDialog(
            self.projekt, self, vorlage=self.vorschau.blattvorlage
        )
        if dialog.exec() == ProjektdatenDialog.DialogCode.Accepted:
            dialog.uebernehmen()
            self._belegung_geaendert()
            # Der Verteilername steht im Fenstertitel - er kann sich
            # gerade geändert haben.
            self._titel_setzen()
            self.leistenansicht.aktualisieren()
            self.statusBar().showMessage(
                u("Projektdaten übernommen"), 8000
            )

    def ueber(self) -> None:
        """Fassung, Bausteine und Lizenzen - alles auf einen Blick."""

        def tabelle(zeilen) -> str:
            # Ohne <br> zwischen den Zeilen: das Trennzeichen der Tabelle
            # ist die Zeile selbst, sonst klafft dazwischen eine Lücke.
            return (
                "<table cellpadding='3' cellspacing='0'>"
                + "".join(zeilen)
                + "</table>"
            )

        bausteine = tabelle(
            f"<tr><td>{teil.name}</td>"
            f"<td><b>{teil.fassung}</b></td>"
            f"<td>{teil.lizenz}</td>"
            f"<td>{teil.aufgabe}</td></tr>"
            for teil in bestand.abhaengigkeiten()
        )
        umgebung = tabelle(
            f"<tr><td>{name}</td><td>{wert}</td></tr>"
            for name, wert in bestand.umgebung()
        )

        # Die Lizenzen stehen als Verweis da: im Netz immer zu erreichen,
        # und ausgelegt im Arbeitsordner auch ohne Netz.
        ordner = bestand.lizenzordner()
        verweise = " · ".join(
            f'<a href="{ziel}">{name}</a>' for name, ziel in LIZENZVERWEISE
        )
        vor_ort = (
            "<br>"
            + u("Im Arbeitsordner:")
            + f' <a href="{pathlib.Path(ordner).as_uri()}">{ordner}</a>'
            if ordner
            else ""
        )

        kasten = QMessageBox(self)
        kasten.setIconPixmap(self.windowIcon().pixmap(64, 64))
        kasten.setWindowTitle(u("Über Verteilerly"))
        kasten.setTextFormat(Qt.TextFormat.RichText)
        # Ohne diese beiden Zeilen sind die Verweise nur blauer Text.
        kasten.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        kasten.setText(
            f"<b>Verteilerly {VERSION}</b><br>"
            + u("Dokumentation für LSA+-Verteiler in der Fernmeldetechnik.")
            + u(
                "<p>© 2026 {0} — freie Software unter der "
                "<b>GNU GPL, Version 3 oder später</b>. Ohne jede Gewährleistung.</p>"
            ).format(URHEBER)
            + u(
                "<p><i>Mit KI-Unterstützung entwickelt: Teile des Quelltextes "
                "sind mit Claude Code (Anthropic) erarbeitet.</i></p>"
            )
            + f"<p><b>{u('Bausteine')}</b></p>{bausteine}"
            + f"<p><b>{u('Lizenztexte')}</b><br>{verweise}{vor_ort}</p>"
            + f"<p><b>{u('Umgebung')}</b></p>{umgebung}"
        )
        for kind in kasten.findChildren(QLabel):
            kind.setOpenExternalLinks(True)
        kasten.exec()

    def dokumentation(self) -> None:
        """Die Dokumentation im Programm."""
        from .dialoge import DokumentationDialog

        DokumentationDialog(self).exec()

    def closeEvent(self, ereignis) -> None:
        if self._darf_verwerfen():
            ereignis.accept()
        else:
            ereignis.ignore()
