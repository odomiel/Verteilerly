"""Verteilerübersicht: Leisten als Kästen aus DA-Zellen.

Eine Zelle entspricht einer Doppelader, ein Kabel einem zusammenhängenden
Block über die von ihm belegten Doppeladern - genau wie in den
Mustertabellen. Buchten stehen nebeneinander.
"""

from __future__ import annotations

from PySide6.QtCore import QMimeData, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QDrag,
    QFont,
    QFontMetrics,
    QKeySequence,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from ..modell import (
    LEISTEN_ZAHLEN,
    Kabel,
    Verteiler,
    leistenname,
    mehrzahl,
    platz_frei,
)
from .thema import HELL, Farben
from .zoom import rad_ist_zoom
from ..sprachen import u

#: Woran ein gezogenes Kabel zu erkennen ist. Ein eigener Typ: fremde
#: Fracht soll hier nichts ausloesen.
KABELFRACHT = "application/x-verteilerly-kabel"

# Eine DA-Zelle im Bearbeitungsfenster. Groesser als auf dem Blatt, und
# zwar mit Absicht: hier soll der Name auch eines Kabels zu lesen sein,
# das nur eine oder zwei Doppeladern belegt. Die Hoehe traegt dafuer zwei
# Zeilen - ein Name bricht um, bevor er abgeschnitten wird.
ZELLE_B = 38
ZELLE_H = 46
LABEL_B = 36
RAND = 14
ABSTAND_LEISTEN = 9
ABSTAND_BUCHTEN = 30
#: So klein und so gross laesst sich die Uebersicht ziehen.
ZOOM_KLEINSTENS = 0.5
ZOOM_GROESSTENS = 3.0
#: Ein Name darf **einmal** umbrechen. Reicht das nicht, wachsen die
#: Zellen - bis hierher, in diesen Schritten. Der Deckel muss sein:
#: ein langer Name auf einer einzigen Doppelader blaehte sonst den
#: ganzen Verteiler auf.
#: Wie der Name in seinem Block steht - und wie er umbricht.
LAGE = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
UMBRUCH = LAGE | Qt.TextFlag.TextWordWrap
ZEILEN_HOECHSTENS = 2
WACHSTUM_HOECHSTENS = 2.5
WACHSTUM_SCHRITT = 0.05


class Uebersicht(QWidget):
    """Zeigt den Verteiler und laesst Doppeladern auswaehlen."""

    auswahl_geaendert = Signal(object)      # (leiste, da) oder None
    stelle_aktiviert = Signal(int, int)     # Doppelklick auf freie Stelle
    kabel_aktiviert = Signal(object)        # Doppelklick auf ein Kabel
    #: Ein Kabel wurde woandershin gezogen: (Kabel, Leiste, Start-DA,
    #: kopieren). Das Fenster fuehrt es aus - die Uebersicht zeigt nur.
    kabel_umgelegt = Signal(object, int, int, bool)
    #: Ausschneiden, Kopieren, Einfuegen: (Handlung, Kabel oder None,
    #: Leiste, DA). Auch das fuehrt das Fenster aus - es haelt die
    #: Ablage, und es weiss, was ein Umzug am Verteiler bedeutet.
    kabel_zwischenablage = Signal(str, object, int, int)
    #: Der Rest dieser Leitung soll genau hier aufliegen (Kabel, Leiste,
    #: DA). Ausgefuehrt wird es im Fenster - die Uebersicht meldet nur.
    restleitung_hierher = Signal(object, int, int)
    #: Diese Leitung soll herunter: (Kabel, Abschnittsnummer). Die Nummer
    #: -1 heisst die ganze Leitung, sonst ist nur dieses Stueck gemeint.
    #: Gefragt und ausgefuehrt wird im Fenster.
    leitung_weg = Signal(object, int)
    #: Strg und Mausrad: eine Stufe hinauf oder hinab.
    zoom_gerollt = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.verteiler: Verteiler | None = None
        self.farben: Farben = HELL
        # Wie die Leisten heissen - nur fuer die Hinweistexte; gezeichnet
        # wird hier ohne Beschriftung.
        self.leisten_schreibweise: str = LEISTEN_ZAHLEN
        self.auswahl: tuple[int, int] | None = None
        self._kaesten: dict[int, QRect] = {}
        # Woher ein Ziehen kam: Druckpunkt, Kabel und an welcher seiner
        # Doppeladern es angefasst wurde.
        self._griff: tuple[QPoint, Kabel, int] | None = None
        #: Wohin es gerade zeigt - (Leiste, Start-DA, passt) fuer die Vorschau.
        self._ziel: tuple[int, int, bool] | None = None
        #: Das Kabel, das gerade am Zeiger haengt.
        self._gezogen: Kabel | None = None
        #: Schreibgeschuetzt: anschauen ja, umlegen und auflegen nein.
        self.schreibgeschuetzt = False
        #: Wie gross gezeichnet wird. Die Masse unten rechnen damit, die
        #: Schrift waechst mit - so bleibt das Bild in sich stimmig.
        self.zoom = 1.0
        #: Duerfen die Zellen wachsen, wenn ein Kabelname auch
        #: umgebrochen nicht hineingeht? Und um wie viel tun sie es
        #: gerade (1.0 = gar nicht).
        self.waechst = True
        self.wachstum = 1.0
        #: Woraus das Wachstum gerechnet wurde - Namen, Zoom, Schalter.
        self._wachstumsschluessel: tuple | None = None
        self._grundschrift = QFont(self.font())
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)
        #: Ob in der Ablage des Fensters etwas liegt - danach richtet
        #: sich, ob "Einfuegen" im Menue offen steht.
        self.ablage_voll = False
        self._menueaktionen()

    # -- Zustand -----------------------------------------------------------

    # -- Rechtsklickmenue ---------------------------------------------------

    def _menueaktionen(self) -> None:
        """Die Handlungen des Rechtsklickmenues, am Bild angemeldet."""
        self.aktion_ausschneiden = QAction(u("Leitung ausschneiden"), self)
        self.aktion_ausschneiden.setShortcut(QKeySequence.StandardKey.Cut)
        self.aktion_kopieren = QAction(u("Leitung kopieren"), self)
        self.aktion_kopieren.setShortcut(QKeySequence.StandardKey.Copy)
        self.aktion_einfuegen = QAction(u("Leitung einfügen"), self)
        self.aktion_einfuegen.setShortcut(QKeySequence.StandardKey.Paste)
        for handlung, was in (
            (self.aktion_ausschneiden, "ausschneiden"),
            (self.aktion_kopieren, "kopieren"),
            (self.aktion_einfuegen, "einfuegen"),
        ):
            handlung.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
            handlung.triggered.connect(
                lambda _an=False, handlung=was: self._ablage_melden(handlung)
            )
            self.addAction(handlung)


    def _ablage_melden(self, was: str, stelle=None) -> None:
        """Meldet die Handlung ans Fenster - mit Kabel und Platz."""
        stelle = stelle or self.auswahl
        if stelle is None or self.verteiler is None:
            return
        leiste, da = stelle
        kabel = self.verteiler.kabel_an(leiste, da)
        if was != "einfuegen" and kabel is None:
            return
        self.kabel_zwischenablage.emit(was, kabel, leiste, da)

    def menue_auffrischen(self, kabel) -> None:
        """Graut aus, was an dieser Stelle nicht geht.

        Steht neben dem Zeigen des Menues: ein offenes Menue haelt die
        Testreihe an, dieser Teil laesst sich ohne eines pruefen.
        """
        darf = not self.schreibgeschuetzt
        self.aktion_ausschneiden.setEnabled(darf and kabel is not None)
        self.aktion_kopieren.setEnabled(kabel is not None)
        self.aktion_einfuegen.setEnabled(darf and self.ablage_voll)

    @property
    def gekuerzte_leitungen(self) -> int:
        """Wie viele Leitungen weniger aufliegen, als sie haben."""
        if self.verteiler is None:
            return 0
        return sum(1 for kabel in self.verteiler.kabel if kabel.gekuerzt)

    def restleitungen_hier(self, leiste: int, da: int) -> list[tuple]:
        """Welche Restleitung an dieser Stelle aufliegen koennte.

        Eine Zeile je gekuerzter Leitung: (Kabel, Rest, passt). Was hier
        nicht hinpasst, faellt nicht weg, sondern kommt ausgegraut ins
        Menue - sonst raetselt man, wo eine Leitung geblieben ist.

        Steht **neben** dem Zeigen des Menues: ein offenes `QMenu.exec()`
        haelt die Testreihe an, diese Entscheidung laesst sich ohne eines
        pruefen.
        """
        if self.verteiler is None or self.schreibgeschuetzt:
            return []
        zeilen = []
        for kabel in self.verteiler.kabel:
            if not kabel.gekuerzt:
                continue
            rest = (kabel.da_gesamt or 0) - kabel.da_aufgelegt
            zeilen.append(
                (kabel, rest, platz_frei(self.verteiler, leiste, da, rest))
            )
        return zeilen

    def contextMenuEvent(self, ereignis) -> None:  # noqa: N802 - Qt-Name
        """Rechtsklick auf eine Doppelader: Ablage, Restleitungen, Entfernen.

        Angefasst wird, worauf geklickt wurde - nicht, was vorher
        markiert war: ein Rechtsklick waehlt die Stelle mit aus, wie
        ueberall.
        """
        stelle = self._zelle_bei(
            int(ereignis.pos().x()), int(ereignis.pos().y())
        )
        if stelle is None or self.verteiler is None:
            return
        self.auswahl = stelle
        self.auswahl_geaendert.emit(stelle)
        self.update()
        leiste, da = stelle
        self.menue_auffrischen(self.verteiler.kabel_an(leiste, da))
        menue = QMenu(self)
        menue.addAction(self.aktion_ausschneiden)
        menue.addAction(self.aktion_kopieren)
        menue.addSeparator()
        menue.addAction(self.aktion_einfuegen)
        menue.addSeparator()
        menue.addMenu(self._restleitungsmenue(menue, leiste, da))
        menue.addSeparator()
        menue.addMenu(self._entfernenmenue(menue, leiste, da))
        menue.exec(ereignis.globalPos())

    def _restleitungsmenue(self, eltern, leiste: int, da: int) -> QMenu:
        """Die gekuerzten Leitungen - ein Druck legt hier auf."""
        menue = QMenu(u("Restleitung auflegen"), eltern)
        zeilen = self.restleitungen_hier(leiste, da)
        menue.setEnabled(bool(zeilen))
        for kabel, rest, passt in zeilen:
            name = kabel.beschriftung or u("ohne Beschriftung")
            beschriftung = u("{0} ({1} übrig)").format(
                name, mehrzahl(rest, "DA", "DA")
            )
            if not passt:
                beschriftung += u(" — passt hier nicht")
            handlung = menue.addAction(beschriftung)
            handlung.setEnabled(passt)
            handlung.triggered.connect(
                lambda _an=False, k=kabel: self.restleitung_hierher.emit(
                    k, leiste, da
                )
            )
        return menue

    def entfernbar_hier(self, leiste: int, da: int) -> tuple:
        """Was ein Rechtsklick hier abnehmen kann: (Kabel, Nummer, geteilt).

        ``Nummer`` ist das Stueck unter dem Zeiger, ``geteilt`` sagt, ob
        die Leitung ueberhaupt in mehreren Stuecken liegt - nur dann ist
        das einzelne Stueck eine eigene Wahl.

        Steht **neben** dem Zeigen des Menues: ein offenes `QMenu.exec()`
        haelt die Testreihe an, diese Entscheidung laesst sich ohne eines
        pruefen.
        """
        if self.verteiler is None or self.schreibgeschuetzt:
            return (None, None, False)
        kabel = self.verteiler.kabel_an(leiste, da)
        if kabel is None:
            return (None, None, False)
        nummer = self.verteiler.kabel_abschnitt_an(kabel, leiste, da)
        return (kabel, nummer, len(kabel.abschnitte) > 1)

    def _entfernenmenue(self, eltern, leiste: int, da: int) -> QMenu:
        """Die Leitung herunternehmen - ganz oder nur dieses Stueck."""
        menue = QMenu(u("Leitung entfernen"), eltern)
        kabel, nummer, geteilt = self.entfernbar_hier(leiste, da)
        menue.setEnabled(kabel is not None)
        ganz = menue.addAction(u("Gesamte Leitung entfernen"))
        ganz.setEnabled(kabel is not None)
        ganz.triggered.connect(
            lambda _an=False, k=kabel: self.leitung_weg.emit(k, -1)
        )
        # Das einzelne Stueck steht auch bei einer Leitung in einem
        # Stueck da - ausgegraut mit dem Grund. Weggelassen waere es ein
        # Raetsel, warum die Wahl manchmal fehlt.
        beschriftung = u("Nur diesen Abschnitt entfernen")
        if nummer is not None and geteilt:
            abschnitt = kabel.abschnitte[nummer]
            beschriftung += u(" (Leiste {0}, DA {1}–{2})").format(
                leistenname(abschnitt.leiste, self.leisten_schreibweise),
                abschnitt.start_da,
                abschnitt.end_da,
            )
        elif kabel is not None:
            beschriftung += u(" — liegt in einem Stück")
        stueck = menue.addAction(beschriftung)
        stueck.setEnabled(geteilt and nummer is not None)
        stueck.triggered.connect(
            lambda _an=False, k=kabel, n=nummer: self.leitung_weg.emit(k, n)
        )
        return menue

    # -- Masse: sie wachsen mit dem Zoom -----------------------------------

    @property
    def zelle_b(self) -> int:
        return self._zellenbreite(self.wachstum)

    @property
    def zelle_h(self) -> int:
        return self._zellenhoehe(self.wachstum)

    def _zellenbreite(self, wachstum: float) -> int:
        return max(6, round(ZELLE_B * self.zoom * wachstum))

    def _zellenhoehe(self, wachstum: float) -> int:
        return max(8, round(ZELLE_H * self.zoom * wachstum))

    @property
    def label_b(self) -> int:
        return max(10, round(LABEL_B * self.zoom))

    @property
    def rand(self) -> int:
        return max(4, round(RAND * self.zoom))

    @property
    def abstand_leisten(self) -> int:
        return max(2, round(ABSTAND_LEISTEN * self.zoom))

    @property
    def abstand_buchten(self) -> int:
        return max(6, round(ABSTAND_BUCHTEN * self.zoom))

    def zoom_setzen(self, faktor: float) -> None:
        """Vergroessert die Uebersicht - Masse und Schrift zusammen.

        Die Flaeche waechst mit; sie steht in einem Rollbereich, der
        seine Balken von selbst zeigt, sobald sie nicht mehr hineingeht.
        """
        self.zoom = max(ZOOM_KLEINSTENS, min(ZOOM_GROESSTENS, float(faktor)))
        schrift = QFont(self._grundschrift)
        schrift.setPointSizeF(
            max(5.0, self._grundschrift.pointSizeF() * self.zoom)
        )
        self.setFont(schrift)
        self._neu_vermessen()

    def wheelEvent(self, ereignis) -> None:  # noqa: N802 - Qt-Name
        """Strg und Mausrad vergroessern, sonst rollt der Bereich."""
        richtung = rad_ist_zoom(ereignis)
        if richtung:
            self.zoom_gerollt.emit(richtung)
            ereignis.accept()
            return
        ereignis.ignore()

    def schreibschutz_setzen(self, an: bool) -> None:
        """Kein Auflegen per Doppelklick und kein Umlegen per Ziehen."""
        self.schreibgeschuetzt = bool(an)
        if an:
            self._griff = None
            self._ziel = None

    def verteiler_setzen(self, verteiler: Verteiler | None) -> None:
        self.verteiler = verteiler
        self.auswahl = None
        self._neu_vermessen()

    def leisten_schreibweise_setzen(self, schreibweise: str) -> None:
        """Wie die Leisten in den Hinweistexten heissen."""
        self.leisten_schreibweise = schreibweise

    def farben_setzen(self, farben: Farben) -> None:
        self.farben = farben
        self.update()

    def aktualisieren(self) -> None:
        self._neu_vermessen()

    def wachsen_setzen(self, an: bool) -> None:
        """Duerfen die Zellen fuer lange Kabelnamen wachsen?"""
        self.waechst = bool(an)
        self._neu_vermessen()

    # -- Wachsen: erst umbrechen, dann groessere Felder --------------------

    def _kabelnamen(self) -> list[tuple[str, int]]:
        """Je Kabelabschnitt: sein Name und wie viele Doppeladern er hat."""
        if self.verteiler is None:
            return []
        gefunden: list[tuple[str, int]] = []
        for kabel in self.verteiler.kabel:
            name = kabel.beschriftung.strip()
            if not name:
                continue
            for abschnitt in kabel.abschnitte:
                gefunden.append((name, abschnitt.anzahl_da))
        return gefunden

    def name_passt(self, name: str, da_zahl: int, wachstum: float) -> bool:
        """Geht der Name bei diesem Wachstum in seinen Block - mit **einem**
        Umbruch?

        Gefragt sind drei Dinge: nicht breiter als der Block, nicht hoeher
        als er, und hoechstens ``ZEILEN_HOECHSTENS`` Zeilen. Das dritte
        ist der eigentliche Massstab - ohne es waere jeder Name
        irgendwann untergebracht, nur eben siebenzeilig.
        """
        block = QRect(
            0, 0,
            self._zellenbreite(wachstum) * max(1, da_zahl),
            self._zellenhoehe(wachstum),
        )
        platz = block.adjusted(4, 2, -3, -2)
        masse = QFontMetrics(self.font())
        gebraucht = masse.boundingRect(platz, UMBRUCH, name)
        zeilen = max(1, round(gebraucht.height() / max(1, masse.lineSpacing())))
        return (
            zeilen <= ZEILEN_HOECHSTENS
            and gebraucht.width() <= platz.width()
            and gebraucht.height() <= platz.height()
        )

    def wachstum_suchen(self) -> float:
        """Der kleinste Faktor, mit dem jeder Kabelname hineingeht.

        Gesucht wird in Schritten von unten: der erste Faktor, bei dem
        alle Namen passen, gewinnt. Keiner tut es bis zum Deckel, bleibt
        es beim Deckel - was dann noch zu lang ist, bricht weiter um oder
        wird abgeschnitten, wie bisher.
        """
        if not self.waechst:
            return 1.0
        namen = self._kabelnamen()
        if not namen:
            return 1.0
        faktor = 1.0
        while faktor < WACHSTUM_HOECHSTENS:
            if all(self.name_passt(name, da, faktor) for name, da in namen):
                return faktor
            faktor = round(faktor + WACHSTUM_SCHRITT, 2)
        return WACHSTUM_HOECHSTENS

    def _neu_vermessen(self) -> None:
        # Gesucht wird nur, wenn sich etwas daran geaendert hat: beim
        # Tippen laeuft das hier nach jedem angenommenen Zeichen durch,
        # und die Namen stehen dabei meist still.
        schluessel = (tuple(self._kabelnamen()), self.zoom, self.waechst)
        if schluessel != self._wachstumsschluessel:
            self._wachstumsschluessel = schluessel
            self.wachstum = self.wachstum_suchen()
        self._kaesten = self._layout()
        self.updateGeometry()
        self.update()

    # -- Layout ------------------------------------------------------------

    def _layout(self) -> dict[int, QRect]:
        """Der Kasten jeder Leiste, ohne das Nummernfeld davor."""
        kaesten: dict[int, QRect] = {}
        if self.verteiler is None:
            return kaesten

        x = self.rand
        for bucht in self.verteiler.buchten:
            breiteste = max((l.da_anzahl for l in bucht.leisten), default=0)
            y = self.rand
            for leiste in bucht.leisten:
                kaesten[leiste.nummer] = QRect(
                    x + self.label_b, y, leiste.da_anzahl * self.zelle_b, self.zelle_h
                )
                y += self.zelle_h + self.abstand_leisten
            x += self.label_b + breiteste * self.zelle_b + self.abstand_buchten
        return kaesten

    def sizeHint(self) -> QSize:
        if not self._kaesten:
            return QSize(360, 180)
        rechts = max(k.right() for k in self._kaesten.values())
        unten = max(k.bottom() for k in self._kaesten.values())
        return QSize(rechts + self.rand, unten + self.rand)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def _zelle_bei(self, x: int, y: int) -> tuple[int, int] | None:
        for nummer, kasten in self._kaesten.items():
            if kasten.contains(x, y):
                return nummer, (x - kasten.left()) // self.zelle_b + 1
        return None

    def _zellrechteck(self, leiste: int, da: int) -> QRect:
        kasten = self._kaesten[leiste]
        return QRect(kasten.left() + (da - 1) * self.zelle_b, kasten.top(), self.zelle_b, self.zelle_h)

    # -- Maus --------------------------------------------------------------

    def mousePressEvent(self, ereignis) -> None:
        stelle = self._zelle_bei(int(ereignis.position().x()), int(ereignis.position().y()))
        self.auswahl = stelle
        self._griff = None
        if stelle is not None and self.verteiler is not None:
            kabel = self.verteiler.kabel_an(*stelle)
            if kabel is not None and ereignis.button() == Qt.MouseButton.LeftButton:
                # Gemerkt wird, an welcher Doppelader angefasst wurde: beim
                # Fallenlassen soll genau sie unter dem Zeiger liegen.
                self._griff = (
                    ereignis.position().toPoint(),
                    kabel,
                    self._versatz_im_kabel(kabel, stelle),
                )
        self.auswahl_geaendert.emit(stelle)
        self.update()

    @staticmethod
    def _versatz_im_kabel(kabel: Kabel, stelle: tuple[int, int]) -> int:
        """Die wievielte Doppelader des Kabels angefasst wurde - ab 0."""
        for versatz, (_kabel_da, leiste, da) in enumerate(kabel.positionen()):
            if (leiste, da) == stelle:
                return versatz
        return 0

    def mouseDoubleClickEvent(self, ereignis) -> None:
        stelle = self._zelle_bei(int(ereignis.position().x()), int(ereignis.position().y()))
        if stelle is None or self.verteiler is None or self.schreibgeschuetzt:
            return
        leiste, da = stelle
        kabel = self.verteiler.kabel_an(leiste, da)
        if kabel is not None:
            self.kabel_aktiviert.emit(kabel)
        else:
            self.stelle_aktiviert.emit(leiste, da)

    def mouseMoveEvent(self, ereignis) -> None:
        """Der Kabelname steht im Kasten oft gekuerzt - hier ganz.

        Und: wer ein Kabel weit genug zieht, nimmt es mit. Erst ab der
        Strecke, die das Erscheinungsbild als Ziehen versteht - sonst
        haette schon ein zittriger Klick das Kabel verschoben.
        """
        if self._griff is not None and not self.schreibgeschuetzt and (
            ereignis.buttons() & Qt.MouseButton.LeftButton
        ):
            druckpunkt, kabel, versatz = self._griff
            weite = (ereignis.position().toPoint() - druckpunkt).manhattanLength()
            if weite >= QApplication.startDragDistance():
                self._griff = None
                self._ziehen(kabel, versatz)
                return
        stelle = self._zelle_bei(int(ereignis.position().x()), int(ereignis.position().y()))
        self.setToolTip(self._hinweistext(stelle))

    def mouseReleaseEvent(self, ereignis) -> None:
        self._griff = None
        super().mouseReleaseEvent(ereignis)

    # -- Ziehen und Fallenlassen -------------------------------------------

    def _ziehen(self, kabel: Kabel, versatz: int) -> None:
        """Nimmt das Kabel an den Zeiger - verschieben, mit Strg kopieren."""
        fracht = QMimeData()
        fracht.setData(KABELFRACHT, str(versatz).encode("ascii"))
        zug = QDrag(self)
        zug.setMimeData(fracht)
        zug.setPixmap(self._kabelbild(kabel))
        # Das Kabel selbst reist nicht durch die Zwischenablage: fremde
        # Anwendungen sollen damit nichts anfangen koennen. Es steht so
        # lange hier.
        self._gezogen = kabel
        zug.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction,
                 Qt.DropAction.MoveAction)
        self._gezogen = None
        self._ziel = None
        self.update()

    def _kabelbild(self, kabel: Kabel):
        """Der Block des Kabels als Bild am Zeiger - so sieht man, was man traegt."""
        plaetze = [(leiste, da) for _kd, leiste, da in kabel.positionen()]
        erste = self._zellrechteck(*plaetze[0])
        letzte = self._zellrechteck(*plaetze[-1])
        return self.grab(erste.united(letzte))

    def _fracht_taugt(self, ereignis) -> bool:
        return (
            ereignis.mimeData().hasFormat(KABELFRACHT)
            and self._gezogen is not None
            and self.verteiler is not None
            and not self.schreibgeschuetzt
        )

    def _zielstelle(self, ereignis) -> tuple[int, int, bool] | None:
        """Wohin das Kabel fiele - und ob es dort ganz und frei liegt."""
        stelle = self._zelle_bei(
            int(ereignis.position().x()), int(ereignis.position().y())
        )
        if stelle is None:
            return None
        versatz = int(bytes(ereignis.mimeData().data(KABELFRACHT)).decode("ascii"))
        leiste, da = stelle
        start = da - versatz
        passt = True
        try:
            self.verteiler._platz_verlangen(
                leiste, start, self._gezogen.da_aufgelegt, ausser=self._gezogen
            )
        except Exception:      # noqa: BLE001 - hier wird nur gezeigt, nicht gehandelt
            passt = False
        return leiste, start, passt

    def dragEnterEvent(self, ereignis) -> None:  # noqa: N802 - Qt-Name
        if self._fracht_taugt(ereignis):
            ereignis.acceptProposedAction()

    def dragMoveEvent(self, ereignis) -> None:  # noqa: N802 - Qt-Name
        if not self._fracht_taugt(ereignis):
            return
        ziel = self._zielstelle(ereignis)
        if ziel != self._ziel:
            self._ziel = ziel
            self.update()
        if ziel is not None and ziel[2]:
            ereignis.acceptProposedAction()
        else:
            ereignis.ignore()

    def dragLeaveEvent(self, ereignis) -> None:  # noqa: N802 - Qt-Name
        self._ziel = None
        self.update()

    def dropEvent(self, ereignis) -> None:  # noqa: N802 - Qt-Name
        if not self._fracht_taugt(ereignis):
            return
        ziel = self._zielstelle(ereignis)
        self._ziel = None
        if ziel is None or not ziel[2]:
            ereignis.ignore()
            return
        leiste, start, _passt = ziel
        kopieren = ereignis.proposedAction() == Qt.DropAction.CopyAction
        ereignis.acceptProposedAction()
        self.kabel_umgelegt.emit(self._gezogen, leiste, start, kopieren)

    def _hinweistext(self, stelle: tuple[int, int] | None) -> str:
        if stelle is None or self.verteiler is None:
            return ""
        leiste, da = stelle
        name = leistenname(leiste, self.leisten_schreibweise)
        kabel = self.verteiler.kabel_an(leiste, da)
        if kabel is None:
            return u("Leiste {0}, DA {1} — frei").format(name, da)
        zeilen = [kabel.beschriftung, u("Leiste {0}, DA {1}").format(name, da)]
        if kabel.kabeltyp:
            zeilen.append(kabel.kabeltyp)
        if kabel.gekuerzt:
            zeilen.append(
                u("gekürzt: {0} von {1} DA").format(
                    kabel.da_aufgelegt, kabel.da_gesamt
                )
            )
        return "\n".join(zeilen)

    # -- Zeichnen ----------------------------------------------------------

    def paintEvent(self, ereignis) -> None:
        maler = QPainter(self)
        maler.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        maler.fillRect(self.rect(), self.farben.q("grund"))

        if self.verteiler is None or not self._kaesten:
            self._hinweis_zeichnen(maler)
            return

        self._raster_zeichnen(maler)
        for kabel in self.verteiler.kabel:
            self._kabel_zeichnen(maler, kabel)
        self._auswahl_zeichnen(maler)
        self._ziel_zeichnen(maler)

    def _ziel_zeichnen(self, maler: QPainter) -> None:
        """Zeigt beim Ziehen, wo das Kabel landen wuerde.

        Nur der Umriss, damit darunter sichtbar bleibt, was dort liegt -
        und in der Warnfarbe, wo es nicht hinpasst.
        """
        if self._ziel is None or self._gezogen is None:
            return
        leiste, start, passt = self._ziel
        if leiste not in self._kaesten:
            return
        anzahl = self._gezogen.da_aufgelegt
        kasten = self._kaesten[leiste]
        links = kasten.left() + (start - 1) * self.zelle_b
        umriss = QRect(links, kasten.top(), anzahl * self.zelle_b, self.zelle_h)
        maler.setPen(QPen(
            self.farben.q("akzent" if passt else "warnung"), 2,
            Qt.PenStyle.SolidLine if passt else Qt.PenStyle.DashLine,
        ))
        maler.setBrush(Qt.BrushStyle.NoBrush)
        maler.drawRect(umriss.adjusted(1, 1, -1, -1))

    def _hinweis_zeichnen(self, maler: QPainter) -> None:
        maler.setPen(self.farben.q("schrift_leise"))
        maler.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            u("Kein Verteiler geöffnet.\nDatei ▸ Neuer Verteiler"),
        )

    def _raster_zeichnen(self, maler: QPainter) -> None:
        nummernschrift = QFont(self.font())
        nummernschrift.setPointSizeF(self.font().pointSizeF() - 0.5)

        for nummer, kasten in self._kaesten.items():
            maler.setFont(nummernschrift)
            maler.setPen(self.farben.q("schrift_leise"))
            maler.drawText(
                QRect(kasten.left() - self.label_b, kasten.top(), self.label_b - 6, self.zelle_h),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                str(nummer),
            )

            maler.fillRect(kasten, self.farben.q("flaeche"))

            # Feine Linie je Doppelader, kraeftige Linie um die Leiste.
            maler.setPen(QPen(self.farben.q("linie"), 1))
            zellen = kasten.width() // self.zelle_b
            for i in range(1, zellen):
                x = kasten.left() + i * self.zelle_b
                maler.drawLine(x, kasten.top() + 1, x, kasten.bottom() - 1)
            maler.setPen(QPen(self.farben.q("linie_kraeftig"), 1))
            maler.drawRect(kasten)

    def _kabel_zeichnen(self, maler: QPainter, kabel: Kabel) -> None:
        for abschnitt in kabel.abschnitte:
            if abschnitt.leiste not in self._kaesten:
                continue
            anfang = self._zellrechteck(abschnitt.leiste, abschnitt.start_da)
            block = QRect(
                anfang.left(), anfang.top(), abschnitt.anzahl_da * self.zelle_b, self.zelle_h
            )
            maler.fillRect(block.adjusted(1, 1, 0, 0), self.farben.q("akzent_leise"))
            maler.setPen(QPen(self.farben.q("akzent"), 1))
            maler.drawRect(block)

            beschriftung = kabel.beschriftung
            if kabel.gekuerzt and abschnitt is kabel.abschnitte[-1]:
                beschriftung = u("{0} (gekürzt)").format(beschriftung)
            maler.setPen(self.farben.q("akzent"))
            self._namen_zeichnen(maler, block, beschriftung)

    def _namen_zeichnen(self, maler: QPainter, block: QRect, name: str) -> None:
        """Den Kabelnamen in seinen Block - umgebrochen, wenn es sein muss.

        Ein Kabel ueber eine Doppelader hat nur eine Zellbreite Platz; in
        einer Zeile blieben davon drei Buchstaben und ein Auslassungszeichen.
        Also wird umgebrochen, solange die Zeilen in die Hoehe passen, und
        erst wenn auch das nicht reicht, einzeilig abgeschnitten - lieber
        ein halber Name als keiner.
        """
        platz = block.adjusted(4, 2, -3, -2)
        text, flaggen = self.namenslage(name, platz)
        maler.drawText(platz, flaggen, text)

    def namenslage(self, name: str, platz: QRect):
        """Was von einem Namen zu sehen ist und wie - Text und Flaggen.

        Getrennt vom Zeichnen, damit die Entscheidung pruefbar bleibt:
        passt der umgebrochene Name in die Hoehe, wird umgebrochen; sonst
        bleibt es bei einer Zeile mit Auslassungszeichen.
        """
        masse = QFontMetrics(self.font())
        lage = LAGE
        umbruch = UMBRUCH
        if masse.boundingRect(platz, umbruch, name).height() <= platz.height():
            return name, umbruch
        return (
            masse.elidedText(name, Qt.TextElideMode.ElideRight, platz.width()),
            lage,
        )

    def _auswahl_zeichnen(self, maler: QPainter) -> None:
        if self.auswahl is None or self.auswahl[0] not in self._kaesten:
            return
        leiste, da = self.auswahl
        if da > self._kaesten[leiste].width() // self.zelle_b:
            return
        maler.setPen(QPen(self.farben.q("akzent"), 2))
        maler.setBrush(Qt.BrushStyle.NoBrush)
        maler.drawRect(self._zellrechteck(leiste, da).adjusted(1, 1, -1, -1))
