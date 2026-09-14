"""Farben fuer helle und dunkle Darstellung.

Der Dunkelmodus ist eine eigene, durchgezeichnete Fassung und keine
Umkehrung der hellen - beide Saetze sind vollstaendig angegeben.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap, QPolygonF
from PySide6.QtWidgets import QApplication, QProxyStyle, QStyle, QStyleFactory


@dataclass(frozen=True)
class Farben:
    """Ein vollstaendiger Farbsatz."""

    name: str
    grund: str          # Fensterhintergrund
    flaeche: str        # Eingabefelder, Tabellen
    flaeche_2: str = ""     # Kopfzeilen, abgesetzte Flaechen
    schrift: str = ""
    schrift_leise: str = ""
    linie: str = ""
    linie_kraeftig: str = ""
    akzent: str = ""
    akzent_leise: str = ""
    warnung: str = ""

    def q(self, name: str) -> QColor:
        return QColor(getattr(self, name))


HELL = Farben(
    name="hell",
    grund="#F2F5F5",
    flaeche="#FFFFFF",
    flaeche_2="#E8EDED",
    schrift="#14181A",
    schrift_leise="#56666A",
    linie="#C9D4D4",
    linie_kraeftig="#9BAAAA",
    akzent="#0E5A61",
    akzent_leise="#DCEAEA",
    warnung="#A8471C",
)

DUNKEL = Farben(
    name="dunkel",
    grund="#0E1214",
    flaeche="#161C1E",
    flaeche_2="#1E2629",
    schrift="#E2EAEA",
    schrift_leise="#93A2A5",
    linie="#2A3437",
    linie_kraeftig="#3E4B4F",
    akzent="#4FC2CB",
    akzent_leise="#17383B",
    warnung="#E08A5E",
)

SAETZE = {"hell": HELL, "dunkel": DUNKEL}


# Welche Standardbilder wir selbst malen und in welche Richtung sie
# zeigen. Qt bringt sie als feste Bilddateien mit - dunkle Pfeile, die
# im dunklen Satz auf dunklem Grund kaum zu sehen sind.
PFEILE = {
    QStyle.StandardPixmap.SP_ArrowBack: "links",
    QStyle.StandardPixmap.SP_ArrowForward: "rechts",
    QStyle.StandardPixmap.SP_ArrowLeft: "links",
    QStyle.StandardPixmap.SP_ArrowRight: "rechts",
    QStyle.StandardPixmap.SP_ArrowUp: "hoch",
    QStyle.StandardPixmap.SP_ArrowDown: "runter",
    QStyle.StandardPixmap.SP_FileDialogBack: "links",
    QStyle.StandardPixmap.SP_FileDialogToParent: "hoch",
}
PFEILGROESSEN = (16, 24, 32, 48)


def pfeilbild(farbe: QColor, richtung: str, kante: int) -> QPixmap:
    """Ein Pfeil als Bild - gezeichnet, nicht geladen.

    Gezeichnet in der Schriftfarbe des Satzes: damit folgt er dem
    Erscheinungsbild, statt als dunkler Fleck auf dunklem Grund zu
    liegen.
    """
    bild = QPixmap(kante, kante)
    bild.fill(Qt.GlobalColor.transparent)
    maler = QPainter(bild)
    maler.setRenderHint(QPainter.RenderHint.Antialiasing)
    maler.setPen(Qt.PenStyle.NoPen)
    maler.setBrush(farbe)
    # Ein gleichschenkliges Dreieck, mittig, mit Luft ringsum.
    rand = kante * 0.28
    mitte = kante / 2
    spitze = kante - rand
    punkte = {
        "links": [(rand, mitte), (spitze, rand), (spitze, kante - rand)],
        "rechts": [(spitze, mitte), (rand, rand), (rand, kante - rand)],
        "hoch": [(mitte, rand), (rand, spitze), (kante - rand, spitze)],
        "runter": [(mitte, spitze), (rand, rand), (kante - rand, rand)],
    }[richtung]
    maler.drawPolygon(QPolygonF([QPointF(x, y) for x, y in punkte]))
    maler.end()
    return bild


def pfeilsymbol(farbe: QColor, richtung: str) -> QIcon:
    """Derselbe Pfeil in mehreren Groessen - Qt sucht sich die passende."""
    symbol = QIcon()
    for kante in PFEILGROESSEN:
        symbol.addPixmap(pfeilbild(farbe, richtung, kante))
    return symbol


class PfeilStil(QProxyStyle):
    """Fusion, aber mit eigenen Pfeilen.

    Qts Standardbilder sind feste Dateien in dunklem Grau. Im dunklen
    Satz sind die Pfeile des Dateidialogs - zurueck, vor, eine Ebene
    hoeher - darauf kaum zu erkennen. Sie werden deshalb hier gemalt,
    in der Schriftfarbe des Satzes.
    """

    def __init__(self, farben: Farben) -> None:
        super().__init__(QStyleFactory.create("Fusion"))
        self.farben = farben

    def standardIcon(self, standardIcon, option=None, widget=None):  # noqa: N802
        richtung = PFEILE.get(standardIcon)
        if richtung is None:
            return super().standardIcon(standardIcon, option, widget)
        return pfeilsymbol(self.farben.q("schrift"), richtung)


def palette_bauen(farben: Farben) -> QPalette:
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, farben.q("grund"))
    p.setColor(QPalette.ColorRole.WindowText, farben.q("schrift"))
    p.setColor(QPalette.ColorRole.Base, farben.q("flaeche"))
    p.setColor(QPalette.ColorRole.AlternateBase, farben.q("flaeche_2"))
    p.setColor(QPalette.ColorRole.Text, farben.q("schrift"))
    p.setColor(QPalette.ColorRole.Button, farben.q("flaeche_2"))
    p.setColor(QPalette.ColorRole.ButtonText, farben.q("schrift"))
    p.setColor(QPalette.ColorRole.ToolTipBase, farben.q("flaeche"))
    p.setColor(QPalette.ColorRole.ToolTipText, farben.q("schrift"))
    p.setColor(QPalette.ColorRole.Highlight, farben.q("akzent"))
    p.setColor(QPalette.ColorRole.HighlightedText, farben.q("flaeche"))
    p.setColor(QPalette.ColorRole.PlaceholderText, farben.q("schrift_leise"))
    p.setColor(QPalette.ColorRole.Link, farben.q("akzent"))

    aus = QPalette.ColorGroup.Disabled
    p.setColor(aus, QPalette.ColorRole.Text, farben.q("schrift_leise"))
    p.setColor(aus, QPalette.ColorRole.ButtonText, farben.q("schrift_leise"))
    p.setColor(aus, QPalette.ColorRole.WindowText, farben.q("schrift_leise"))
    return p


def stilblatt(farben: Farben) -> str:
    """Das Stilblatt zum Farbsatz.

    Ankreuzfelder und Auswahlknoepfe bekommen eine eigene Regel: im
    dunklen Satz zeichnet Fusion sie sonst dunkel auf dunkel, und man
    sieht nicht einmal, dass dort etwas anzukreuzen ist. Offen tragen
    beide die Farbe eines Eingabefeldes; angekreuzt ist das Kaestchen
    gefuellt, und der Auswahlknopf bekommt Ring und Kugel in der
    Akzentfarbe - eine ganz gefuellte Scheibe saehe aus wie ein
    Ankreuzfeld mit runden Ecken.
    """
    return f"""
QToolBar {{
    background: {farben.flaeche_2};
    border: none;
    border-bottom: 1px solid {farben.linie};
    padding: 4px 6px;
    spacing: 4px;
}}
QToolBar QToolButton {{ padding: 4px 10px; border-radius: 3px; }}
QToolBar QToolButton:hover {{ background: {farben.akzent_leise}; }}
QStatusBar {{
    background: {farben.flaeche_2};
    border-top: 1px solid {farben.linie};
    color: {farben.schrift_leise};
}}
QHeaderView::section {{
    background: {farben.flaeche_2};
    color: {farben.schrift_leise};
    padding: 5px 7px;
    border: none;
    border-right: 1px solid {farben.linie};
    border-bottom: 1px solid {farben.linie_kraeftig};
    font-weight: 600;
}}
QTableView {{
    background: {farben.flaeche};
    gridline-color: {farben.linie};
    selection-background-color: {farben.akzent};
    selection-color: {farben.flaeche};
}}
QTableView::item {{ padding: 2px 4px; }}
QSplitter::handle {{ background: {farben.linie}; }}
QGroupBox {{
    border: 1px solid {farben.linie};
    border-radius: 3px;
    margin-top: 10px;
    padding-top: 8px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 9px;
    padding: 0 4px;
    color: {farben.schrift_leise};
}}
QLineEdit, QSpinBox, QComboBox, QPlainTextEdit {{
    background: {farben.flaeche};
    border: 1px solid {farben.linie_kraeftig};
    border-radius: 3px;
    padding: 4px 6px;
    selection-background-color: {farben.akzent};
    selection-color: {farben.flaeche};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {farben.akzent}; }}
QCheckBox {{ spacing: 7px; }}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {farben.linie_kraeftig};
    border-radius: 3px;
    background: {farben.flaeche};
}}
QCheckBox::indicator:hover {{ border-color: {farben.akzent}; }}
QCheckBox::indicator:checked {{
    background: {farben.akzent};
    border-color: {farben.akzent};
}}
QRadioButton {{ spacing: 7px; }}
QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {farben.linie_kraeftig};
    border-radius: 8px;
    background: {farben.flaeche};
}}
QRadioButton::indicator:hover {{ border-color: {farben.akzent}; }}
QRadioButton::indicator:checked {{
    border-color: {farben.akzent};
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 {farben.akzent}, stop:0.45 {farben.akzent},
        stop:0.5 {farben.flaeche}, stop:1 {farben.flaeche});
}}
QRadioButton::indicator:disabled {{ border-color: {farben.linie}; }}
QPushButton {{
    background: {farben.flaeche_2};
    border: 1px solid {farben.linie_kraeftig};
    border-radius: 3px;
    padding: 5px 14px;
}}
QPushButton:hover {{ border-color: {farben.akzent}; }}
QPushButton:default {{
    background: {farben.akzent};
    color: {farben.flaeche};
    border-color: {farben.akzent};
}}
"""


def anwenden(anwendung: QApplication, farben: Farben) -> None:
    """Legt Palette, Stilblatt und die eigenen Pfeile auf die Anwendung."""
    stil = PfeilStil(farben)
    # Qt uebernimmt den Stil, aber ein Verweis schadet nicht: ohne ihn
    # haengt er allein am C++-Objekt.
    anwendung._stil = stil
    anwendung.setStyle(stil)
    anwendung.setPalette(palette_bauen(farben))
    anwendung.setStyleSheet(stilblatt(farben))
