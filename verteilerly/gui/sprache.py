"""Qts eigene Dialoge in der Sprache des Programms.

Qt beschriftet seine Knoepfe selbst - und zwar englisch, solange keine
Uebersetzung geladen ist. „Save", „Discard", „Cancel" mitten in einem
deutschen Programm sieht aus wie ein Fehler, und genau das ist es auch.

Zwei Wege fuehren hier zusammen: ``deutsch_einrichten`` laedt Qts eigene
Uebersetzung, damit auch die Datei- und Schriftdialoge deutsch sind, und
``frage`` beschriftet die Knoepfe unserer eigenen Rueckfragen zusaetzlich
von Hand. Fehlt die Uebersetzungsdatei einmal - sie liegt bei Qt, nicht
bei uns -, bleiben unsere Rueckfragen trotzdem deutsch.

Steht das Programm auf Englisch, unterbleibt beides: Qt spricht
von Haus aus englisch, und eine deutsche Beschriftung mitten in einem
englischen Programm waere derselbe Fehler, nur andersherum.
"""

from __future__ import annotations

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QMessageBox

from .. import sprachen

Knopf = QMessageBox.StandardButton

# Was auf den Knoepfen steht, die wir selbst anfordern.
KNOPFTEXTE = {
    Knopf.Ok: "OK",
    Knopf.Save: "Speichern",
    Knopf.Discard: "Verwerfen",
    Knopf.Cancel: "Abbrechen",
    Knopf.Close: "Schließen",
    Knopf.Yes: "Ja",
    Knopf.No: "Nein",
    Knopf.Apply: "Übernehmen",
    Knopf.Reset: "Zurücksetzen",
}


def deutsch_einrichten(anwendung) -> bool:
    """Laedt Qts deutsche Uebersetzung, wenn sie zu finden ist.

    Der Uebersetzer wird an der Anwendung festgehalten: gaebe man ihn
    frei, waere die Uebersetzung sofort wieder weg.
    """
    if sprachen.sprache() != "de":
        return False
    uebersetzer = QTranslator()
    ordner = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    for name in ("qtbase_de", "qt_de"):
        if uebersetzer.load(name, ordner):
            anwendung.installTranslator(uebersetzer)
            anwendung._uebersetzer = uebersetzer
            return True
    # Zweiter Versuch ueber das Gebietsschema - manche Auslieferungen
    # legen die Dateien anders ab.
    if uebersetzer.load(QLocale("de"), "qtbase", "_", ordner):
        anwendung.installTranslator(uebersetzer)
        anwendung._uebersetzer = uebersetzer
        return True
    return False


def fragekasten(
    eltern,
    titel: str,
    text: str,
    knoepfe: Knopf,
    vorgabe: Knopf | None = None,
) -> QMessageBox:
    """Baut die Rueckfrage - fertig beschriftet, aber noch ungezeigt."""
    kasten = QMessageBox(eltern)
    kasten.setIcon(QMessageBox.Icon.Question)
    kasten.setWindowTitle(titel)
    kasten.setText(text)
    kasten.setStandardButtons(knoepfe)
    if sprachen.sprache() == "de":
        for knopf, beschriftung in KNOPFTEXTE.items():
            vorhanden = kasten.button(knopf)
            if vorhanden is not None:
                vorhanden.setText(beschriftung)
    if vorgabe is not None:
        kasten.setDefaultButton(vorgabe)
    return kasten


def frage(
    eltern,
    titel: str,
    text: str,
    knoepfe: Knopf,
    vorgabe: Knopf | None = None,
) -> Knopf:
    """Eine Rueckfrage mit deutsch beschrifteten Knoepfen."""
    kasten = fragekasten(eltern, titel, text, knoepfe, vorgabe)
    kasten.exec()
    return kasten.standardButton(kasten.clickedButton())
