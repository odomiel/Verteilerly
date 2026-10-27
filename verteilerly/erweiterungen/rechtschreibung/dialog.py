"""Der Dialog der Rechtschreibpruefung: pruefen, lesen, uebernehmen.

Oben stehen die **beiden Pruefer**, jeder fuer sich zuzuschalten:

* das **Woerterbuch** liest auf diesem Rechner und schickt nichts
  hinaus - es findet Tippfehler, mehr nicht;
* **LanguageTool** findet auch Grammatik und Zeichensetzung, dafuer
  gehen die Texte an einen Server.

Darum ist das Woerterbuch die Vorgabe und LanguageTool ausgeschaltet:
wer Texte aus dem Haus gibt, soll das selbst entschieden haben. Beide
zusammen gehen auch; ``pruefer.zusammenfuehren()`` wirft dann heraus,
was beide an derselben Stelle beanstanden.

Gefragt wird in einem **eigenen Faden**: eine Anfrage ueber das Netz
dauert, und ein Fenster, das derweil steht, sieht aus wie ein
abgestuerztes. Das Ergebnis kommt als Signal zurueck - gezeichnet wird
also dort, wo Qt es erwartet. **Vorschlaege des Woerterbuchs kosten
auch Zeit** (gemessen zweieinhalb Sekunden je Wort, Nachschlagen
dagegen nichts), sie werden darum erst geholt, wenn jemand die Zeile
anklickt - ebenfalls im Faden, ebenfalls ueber ein Signal.

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
    QCheckBox,
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
from . import (
    SCHLUESSEL_LANGUAGETOOL,
    SCHLUESSEL_SERVER,
    SCHLUESSEL_SPRACHE,
    SCHLUESSEL_WOERTERBUCH,
    SCHLUESSEL_ZUGESTIMMT,
    pruefer,
    woerterbuch,
)
from .pruefer import PruefFehler

#: Die Spalten der Liste.
ORT, FELD, WORT, HINWEIS, VORSCHLAG, QUELLE = range(6)


class RechtschreibDialog(PassenderDialog):
    """Was an den Texten des Verteilers auszusetzen ist."""

    #: (Befunde oder None, Grund) - aus dem Faden der Pruefung.
    geprueft = Signal(object, str)
    #: (Wort, Vorschlaege) - aus dem Faden des Woerterbuchs.
    vorgeschlagen = Signal(str, object)

    def __init__(self, programm, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.programm = programm
        self.einstellungen = programm.einstellungen()
        self.befunde: list[pruefer.Befund] = []
        #: Vorschlaege des Woerterbuchs, Wort fuer Wort - einmal geholt,
        #: dann gehalten; dasselbe Wort steht oft mehrfach im Verteiler.
        self._vorschlaege: dict[str, tuple[str, ...]] = {}
        self._unterwegs: set[str] = set()
        #: Gesetzt, wenn der Dialog zum Springen geschlossen wird.
        self.gewaehlt = None
        self.setWindowTitle(u("Rechtschreibung"))

        self.wb_haken = QCheckBox(u("Wörterbuch (auf diesem Rechner)"))
        self.wb_haken.setChecked(
            self.einstellungen.value(SCHLUESSEL_WOERTERBUCH, True, type=bool)
        )
        self.wb_haken.setToolTip(u(
            "Findet Tippfehler, ohne dass etwas den Rechner verlässt."
        ))
        self.wb_hinweis = QLabel()
        self.wb_hinweis.setWordWrap(True)

        self.lt_haken = QCheckBox(u("LanguageTool (Server)"))
        self.lt_haken.setChecked(
            self.einstellungen.value(SCHLUESSEL_LANGUAGETOOL, False, type=bool)
        )
        self.lt_haken.setToolTip(u(
            "Findet auch Grammatik und Zeichensetzung — die Texte gehen "
            "dafür an einen Server."
        ))

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
        self.sprachfeld.currentTextChanged.connect(lambda *_: self._wb_hinweis_setzen())
        self.lt_haken.toggled.connect(lambda *_: self._knoepfe_auffrischen())
        self.wb_haken.toggled.connect(lambda *_: self._knoepfe_auffrischen())

        formular = QFormLayout()
        formular.addRow(self.wb_haken, self.wb_hinweis)
        formular.addRow(self.lt_haken, QLabel(""))
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
            u("Quelle"),
        ])
        self.liste.setRootIsDecorated(False)
        self.liste.setAlternatingRowColors(True)
        self.liste.currentItemChanged.connect(lambda *_: self._zeile_gewechselt())
        self.liste.itemDoubleClicked.connect(lambda *_: self.springen())

        self.uebernehmen_knopf = QPushButton(u("Vorschlag übernehmen"))
        self.uebernehmen_knopf.clicked.connect(self.uebernehmen)
        self.aufnehmen_knopf = QPushButton(u("Wort aufnehmen"))
        self.aufnehmen_knopf.setToolTip(u(
            "Trägt das Wort in die eigene Wortliste ein — das Wörterbuch "
            "beanstandet es dann nicht mehr."
        ))
        self.aufnehmen_knopf.clicked.connect(self.wort_aufnehmen)
        self.springen_knopf = QPushButton(u("Zur Stelle springen"))
        self.springen_knopf.clicked.connect(self.springen)

        knoepfe = QHBoxLayout()
        knoepfe.addWidget(self.uebernehmen_knopf)
        knoepfe.addWidget(self.aufnehmen_knopf)
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
        self.resize(1040, 580)

        self.geprueft.connect(self._ergebnis)
        self.vorgeschlagen.connect(self._vorschlaege_eingetroffen)
        self._wb_hinweis_setzen()
        self._knoepfe_auffrischen()

    # -- Was eingestellt ist -------------------------------------------------

    def _sprache(self) -> str:
        return self.sprachfeld.currentText().strip() or pruefer.SPRACHE

    def _woerterbuch(self):
        """Das Woerterbuch zur eingestellten Sprache - oder nichts."""
        if not woerterbuch.verfuegbar():
            return None
        return woerterbuch.passendes(self._sprache())

    def _wb_hinweis_setzen(self) -> None:
        if not woerterbuch.verfuegbar():
            self.wb_hinweis.setText(u("Dafür fehlt spylls."))
            self.wb_haken.setEnabled(False)
            return
        fund = self._woerterbuch()
        self.wb_haken.setEnabled(True)
        self.wb_hinweis.setText(
            u("{0} aus {1}").format(fund.kennung, fund.ort.parent)
            if fund else u("Für diese Sprache liegt kein Wörterbuch bereit.")
        )

    # -- Pruefen -------------------------------------------------------------

    def pruefen(self) -> None:
        """Laesst pruefen - nach Rueckfrage, wenn Texte hinausgehen."""
        projekt = self.programm.projekt()
        if projekt is None:
            return
        fund = self._woerterbuch()
        mit_wb = self.wb_haken.isChecked() and fund is not None
        mit_lt = self.lt_haken.isChecked()
        if not mit_wb and not mit_lt:
            self.stand.setText(u("Kein Prüfer gewählt."))
            return
        server = self.serverfeld.text().strip() or pruefer.SERVER
        sprache = self._sprache()
        stellen = pruefer.zu_pruefen(projekt, getattr(projekt, "schreibweise", None))
        if not stellen:
            self.liste.clear()
            self.befunde = []
            self.stand.setText(u("Hier steht kein Text, der zu prüfen wäre."))
            self._knoepfe_auffrischen()
            return
        if mit_lt and not self._zustimmung(server, len(stellen)):
            return

        self.einstellungen.setValue(SCHLUESSEL_SERVER, server)
        self.einstellungen.setValue(SCHLUESSEL_SPRACHE, sprache)
        self.einstellungen.setValue(SCHLUESSEL_LANGUAGETOOL, mit_lt)
        self.einstellungen.setValue(SCHLUESSEL_WOERTERBUCH, self.wb_haken.isChecked())
        self.pruefknopf.setEnabled(False)
        self.stand.setText(
            u("{0} Texte gehen zur Prüfung an {1} …").format(len(stellen), server)
            if mit_lt else u("{0} Texte werden geprüft …").format(len(stellen))
        )
        eigene = woerterbuch.eigene_lesen() if mit_wb else frozenset()

        def arbeiten() -> None:
            befunde: list[pruefer.Befund] = []
            gruende: list[str] = []
            # LanguageTool zuerst: seine Befunde sagen mehr und bringen
            # Vorschlaege mit - bei gleicher Stelle bleibt der erste.
            if mit_lt:
                try:
                    befunde += pruefer.pruefen(stellen, server, sprache)
                except PruefFehler as fehler:
                    gruende.append(str(fehler))
                except Exception as fehler:      # noqa: BLE001
                    gruende.append(f"{type(fehler).__name__}: {fehler}")
            if mit_wb:
                try:
                    befunde += woerterbuch.pruefen(stellen, fund, eigene)
                except Exception as fehler:      # noqa: BLE001
                    gruende.append(f"{type(fehler).__name__}: {fehler}")
            # Nur wenn gar nichts gelaufen ist, ist es ein Fehlschlag -
            # sonst stehen die Befunde des anderen Pruefers da.
            wege = int(mit_lt) + int(mit_wb)
            ergebnis = (
                None if len(gruende) == wege
                else pruefer.zusammenfuehren(befunde, stellen)
            )
            try:
                self.geprueft.emit(ergebnis, "  ".join(gruende))
            except RuntimeError:
                pass        # Dialog ist inzwischen zu - dann eben nicht

        threading.Thread(target=arbeiten, daemon=True).start()

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
              "trägt einen eigenen LanguageTool-Server ein oder prüft nur "
              "mit dem Wörterbuch.\n\nSenden?")
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
        self.stand.setText(" ".join(teil for teil in (
            u("Nichts zu beanstanden.") if not self.befunde
            else u("{0} Stellen beanstandet.").format(len(self.befunde)),
            grund,
        ) if teil))

    def _liste_fuellen(self) -> None:
        self.liste.clear()
        for befund in self.befunde:
            eintrag = QTreeWidgetItem([
                befund.stelle.ort,
                befund.stelle.beschriftung,
                befund.wort,
                befund.meldung,
                ", ".join(self._zu(befund)),
                u(pruefer.QUELLEN.get(befund.quelle, befund.quelle)),
            ])
            eintrag.setData(0, Qt.ItemDataRole.UserRole, befund)
            self.liste.addTopLevelItem(eintrag)
        for spalte in range(self.liste.columnCount()):
            self.liste.resizeColumnToContents(spalte)
        if self.liste.topLevelItemCount():
            self.liste.setCurrentItem(self.liste.topLevelItem(0))
        self._knoepfe_auffrischen()

    # -- Vorschlaege des Woerterbuchs ---------------------------------------

    def _zu(self, befund) -> tuple[str, ...]:
        """Die Vorschlaege zu einem Befund - geholte wie mitgelieferte."""
        if befund.vorschlaege:
            return befund.vorschlaege
        return self._vorschlaege.get(befund.wort, ())

    def _zeile_gewechselt(self) -> None:
        self._knoepfe_auffrischen()
        befund = self._befund()
        if befund is None or befund.quelle != pruefer.WOERTERBUCH:
            return
        wort = befund.wort
        if wort in self._vorschlaege or wort in self._unterwegs:
            return
        fund = self._woerterbuch()
        if fund is None:
            return
        self._unterwegs.add(wort)

        def suchen() -> None:
            gefunden = woerterbuch.vorschlaege(fund, wort)
            try:
                self.vorgeschlagen.emit(wort, gefunden)
            except RuntimeError:
                pass

        threading.Thread(target=suchen, daemon=True).start()

    def _vorschlaege_eingetroffen(self, wort: str, gefunden) -> None:
        self._vorschlaege[wort] = tuple(gefunden)
        self._unterwegs.discard(wort)
        for nummer in range(self.liste.topLevelItemCount()):
            eintrag = self.liste.topLevelItem(nummer)
            befund = eintrag.data(0, Qt.ItemDataRole.UserRole)
            if befund is not None and befund.wort == wort and not befund.vorschlaege:
                eintrag.setText(VORSCHLAG, ", ".join(self._vorschlaege[wort]))
        self._knoepfe_auffrischen()

    # -- Der gewaehlte Befund ------------------------------------------------

    def _befund(self):
        eintrag = self.liste.currentItem()
        return eintrag.data(0, Qt.ItemDataRole.UserRole) if eintrag else None

    def _knoepfe_auffrischen(self) -> None:
        befund = self._befund()
        self.serverfeld.setEnabled(self.lt_haken.isChecked())
        self.sprachfeld.setEnabled(True)
        self.springen_knopf.setEnabled(befund is not None)
        self.uebernehmen_knopf.setEnabled(
            befund is not None and bool(self._zu(befund))
            and not self.programm.schreibgeschuetzt()
        )
        self.aufnehmen_knopf.setEnabled(
            befund is not None and befund.quelle == pruefer.WOERTERBUCH
        )

    def springen(self) -> None:
        """Schliesst den Dialog und zeigt die Stelle - wie die Suche."""
        befund = self._befund()
        if befund is None:
            return
        self.gewaehlt = befund
        self.accept()
        self.programm.zur_fundstelle(befund.stelle)

    def wort_aufnehmen(self) -> None:
        """Nimmt das Wort in die eigene Liste - und aus der Anzeige."""
        befund = self._befund()
        if befund is None:
            return
        wort = befund.wort
        if not woerterbuch.eigenes_wort_aufnehmen(wort):
            self.stand.setText(u("Die eigene Wortliste ist nicht zu schreiben."))
            return
        self.befunde = [
            uebrig for uebrig in self.befunde
            if not (uebrig.quelle == pruefer.WOERTERBUCH and uebrig.wort == wort)
        ]
        self._liste_fuellen()
        self.stand.setText(
            u("„{0}“ steht jetzt in der eigenen Wortliste.").format(wort)
        )

    def uebernehmen(self) -> None:
        """Traegt den ersten Vorschlag ein und meldet die Aenderung."""
        befund = self._befund()
        vorschlaege = self._zu(befund) if befund is not None else ()
        if not vorschlaege:
            return
        projekt = self.programm.projekt()
        if projekt is None or self.programm.schreibgeschuetzt():
            return
        ersatz = vorschlaege[0]
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
