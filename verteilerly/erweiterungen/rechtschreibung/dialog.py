"""Der Dialog der Rechtschreibpruefung: pruefen, lesen, uebernehmen.

Oben steht, **wohin** gefragt wird - Server und Sprache; beides wird
gemerkt. Die Liste darunter zeigt je Beanstandung, wo sie steht, was
beanstandet wird und was LanguageTool vorschlaegt.

Gefragt wird in einem **eigenen Faden**: eine Anfrage ueber das Netz
dauert, und ein Fenster, das derweil steht, sieht aus wie ein
abgestuerztes. Das Ergebnis kommt als Signal zurueck - gezeichnet wird
also dort, wo Qt es erwartet.

**Uebernehmen aendert das Projekt** und laeuft darum durch
``programm.geaendert()``: nur so kommen Vorschau, Uebersicht und das
Zuruecknehmen mit. Danach sind die uebrigen Beanstandungen derselben
Zelle ueberholt - ihre Stellen haben sich verschoben -, also fallen sie
aus der Liste; ein neuer Lauf findet sie wieder.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...gui.passform import PassenderDialog
from ...gui.sprache import Knopf, frage
from ...sprachen import u
from . import SCHLUESSEL_SERVER, SCHLUESSEL_SPRACHE, SCHLUESSEL_ZUGESTIMMT
from . import pruefer
from .pruefer import PruefFehler

#: Die Spalten der Liste.
ORT, FELD, WORT, HINWEIS, VORSCHLAG = range(5)


class RechtschreibDialog(PassenderDialog):
    """Was LanguageTool an den Texten des Verteilers auszusetzen hat."""

    #: (Befunde oder None, Grund) - aus dem Faden der Anfrage.
    geprueft = Signal(object, str)

    def __init__(self, programm, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.programm = programm
        self.einstellungen = programm.einstellungen()
        self.befunde: list[pruefer.Befund] = []
        #: Gesetzt, wenn der Dialog zum Springen geschlossen wird.
        self.gewaehlt = None
        self.setWindowTitle(u("Rechtschreibung"))

        self.serverfeld = QLineEdit(
            str(self.einstellungen.value(SCHLUESSEL_SERVER, pruefer.SERVER)
                or pruefer.SERVER)
        )
        self.serverfeld.setToolTip(u(
            "Ein eigener LanguageTool-Server, etwa "
            "http://localhost:8081/v2/check, hält die Texte im Haus."
        ))
        self.sprachfeld = QComboBox()
        self.sprachfeld.setEditable(True)
        self.sprachfeld.addItems(list(pruefer.SPRACHEN))
        self.sprachfeld.setCurrentText(
            str(self.einstellungen.value(SCHLUESSEL_SPRACHE, pruefer.SPRACHE)
                or pruefer.SPRACHE)
        )

        formular = QFormLayout()
        formular.addRow(u("Server:"), self.serverfeld)
        formular.addRow(u("Sprache:"), self.sprachfeld)

        self.pruefknopf = QPushButton(u("Prüfen"))
        self.pruefknopf.clicked.connect(self.pruefen)
        self.stand = QLabel(u("Geprüft wird erst auf Knopfdruck."))
        self.stand.setWordWrap(True)

        oben = QHBoxLayout()
        oben.addWidget(self.pruefknopf)
        oben.addWidget(self.stand, 1)

        self.liste = QTreeWidget()
        self.liste.setHeaderLabels([
            u("Ort"), u("Feld"), u("Beanstandet"), u("Hinweis"), u("Vorschlag"),
        ])
        self.liste.setRootIsDecorated(False)
        self.liste.setAlternatingRowColors(True)
        self.liste.currentItemChanged.connect(lambda *_: self._knoepfe_auffrischen())
        self.liste.itemDoubleClicked.connect(lambda *_: self.springen())

        self.uebernehmen_knopf = QPushButton(u("Vorschlag übernehmen"))
        self.uebernehmen_knopf.clicked.connect(self.uebernehmen)
        self.springen_knopf = QPushButton(u("Zur Stelle springen"))
        self.springen_knopf.clicked.connect(self.springen)

        knoepfe = QHBoxLayout()
        knoepfe.addWidget(self.uebernehmen_knopf)
        knoepfe.addWidget(self.springen_knopf)
        knoepfe.addStretch(1)

        schliessen = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        schliessen.rejected.connect(self.reject)

        aufbau = QVBoxLayout(self)
        aufbau.addLayout(formular)
        aufbau.addLayout(oben)
        aufbau.addWidget(self.liste, 1)
        aufbau.addLayout(knoepfe)
        aufbau.addWidget(schliessen)
        self.resize(980, 560)

        self.geprueft.connect(self._ergebnis)
        self._knoepfe_auffrischen()

    # -- Pruefen -------------------------------------------------------------

    def pruefen(self) -> None:
        """Fragt den Server - nach Rueckfrage, wenn er auswaerts steht."""
        projekt = self.programm.projekt()
        if projekt is None:
            return
        server = self.serverfeld.text().strip() or pruefer.SERVER
        sprache = self.sprachfeld.currentText().strip() or pruefer.SPRACHE
        stellen = pruefer.zu_pruefen(projekt, getattr(projekt, "schreibweise", None))
        if not stellen:
            self.liste.clear()
            self.befunde = []
            self.stand.setText(u("Hier steht kein Text, der zu prüfen wäre."))
            self._knoepfe_auffrischen()
            return
        if not self._zustimmung(server, len(stellen)):
            return

        self.einstellungen.setValue(SCHLUESSEL_SERVER, server)
        self.einstellungen.setValue(SCHLUESSEL_SPRACHE, sprache)
        self.pruefknopf.setEnabled(False)
        self.stand.setText(
            u("{0} Texte gehen zur Prüfung an {1} …").format(len(stellen), server)
        )

        def fragen() -> None:
            try:
                befunde = pruefer.pruefen(stellen, server, sprache)
            except PruefFehler as fehler:
                ergebnis, grund = None, str(fehler)
            except Exception as fehler:      # noqa: BLE001 - nichts reisst das Fenster mit
                ergebnis, grund = None, f"{type(fehler).__name__}: {fehler}"
            else:
                ergebnis, grund = befunde, ""
            try:
                self.geprueft.emit(ergebnis, grund)
            except RuntimeError:
                pass        # Dialog ist inzwischen zu - dann eben nicht

        threading.Thread(target=fragen, daemon=True).start()

    def _zustimmung(self, server: str, anzahl: int) -> bool:
        """Fragt, bevor zum ersten Mal Text an eine fremde Adresse geht."""
        if not pruefer.oeffentlich(server):
            return True
        if str(self.einstellungen.value(SCHLUESSEL_ZUGESTIMMT, "") or "") == server:
            return True
        antwort = frage(
            self,
            u("Texte senden?"),
            u("Zum Prüfen gehen {0} Texte dieses Verteilers an\n{1}\n\n"
              "Sie verlassen damit diesen Rechner. Wer das nicht möchte, "
              "trägt einen eigenen LanguageTool-Server ein.\n\nSenden?")
            .format(anzahl, server),
            Knopf.Yes | Knopf.No,
            Knopf.No,
        )
        if antwort != Knopf.Yes:
            self.stand.setText(u("Es wurde nichts gesendet."))
            return False
        self.einstellungen.setValue(SCHLUESSEL_ZUGESTIMMT, server)
        return True

    def _ergebnis(self, befunde, grund: str) -> None:
        self.pruefknopf.setEnabled(True)
        if befunde is None:
            self.stand.setText(grund)
            return
        self.befunde = list(befunde)
        self._liste_fuellen()
        self.stand.setText(
            u("Nichts zu beanstanden.") if not self.befunde
            else u("{0} Stellen beanstandet.").format(len(self.befunde))
        )

    def _liste_fuellen(self) -> None:
        self.liste.clear()
        for befund in self.befunde:
            eintrag = QTreeWidgetItem([
                befund.stelle.ort,
                befund.stelle.beschriftung,
                befund.wort,
                befund.meldung,
                ", ".join(befund.vorschlaege),
            ])
            eintrag.setData(0, Qt.ItemDataRole.UserRole, befund)
            self.liste.addTopLevelItem(eintrag)
        for spalte in range(self.liste.columnCount()):
            self.liste.resizeColumnToContents(spalte)
        if self.liste.topLevelItemCount():
            self.liste.setCurrentItem(self.liste.topLevelItem(0))
        self._knoepfe_auffrischen()

    # -- Der gewaehlte Befund ------------------------------------------------

    def _befund(self):
        eintrag = self.liste.currentItem()
        return eintrag.data(0, Qt.ItemDataRole.UserRole) if eintrag else None

    def _knoepfe_auffrischen(self) -> None:
        befund = self._befund()
        self.springen_knopf.setEnabled(befund is not None)
        self.uebernehmen_knopf.setEnabled(
            befund is not None and bool(befund.vorschlaege)
            and not self.programm.schreibgeschuetzt()
        )

    def springen(self) -> None:
        """Schliesst den Dialog und zeigt die Stelle - wie die Suche."""
        befund = self._befund()
        if befund is None:
            return
        self.gewaehlt = befund
        self.accept()
        self.programm.zur_fundstelle(befund.stelle)

    def uebernehmen(self) -> None:
        """Traegt den ersten Vorschlag ein und meldet die Aenderung."""
        befund = self._befund()
        if befund is None or not befund.vorschlaege:
            return
        projekt = self.programm.projekt()
        if projekt is None or self.programm.schreibgeschuetzt():
            return
        ersatz = befund.vorschlaege[0]
        if not pruefer.anwenden(projekt, befund, ersatz):
            self.stand.setText(u(
                "Diese Stelle liegt über zwei Beschriftungsfeldern — "
                "bitte von Hand ändern."
            ))
            return
        self.programm.geaendert()
        # Die uebrigen Beanstandungen derselben Zelle zeigen jetzt
        # daneben - ihr Text ist ein anderer geworden.
        self.befunde = [
            uebrig for uebrig in self.befunde if uebrig.stelle is not befund.stelle
        ]
        self._liste_fuellen()
        self.stand.setText(u("„{0}“ wurde übernommen.").format(ersatz))
