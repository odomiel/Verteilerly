"""Gemeinsames fuer die Testreihen."""

import atexit
import os
import pathlib
import shutil
import tempfile

# Die Testreihe bekommt einen eigenen Einstellungs- und Arbeitsordner.
# Unter Linux haengen beide an XDG_CONFIG_HOME (pfade.einstellungsordner):
# so schreibt kein Test in die echte Verteilerly.conf und keiner legt
# etwas in ~/.config/Verteilerly ab - auch nicht das Programm, das
# TestSelbstbericht als Unterprozess startet, denn es erbt die Umgebung.
# Gesetzt wird das hier, vor jedem Import aus verteilerly.
_TESTHEIM = tempfile.mkdtemp(prefix="verteilerly-tests-")
os.environ["XDG_CONFIG_HOME"] = _TESTHEIM
# Und XDG_DATA_HOME dazu: daran haengen Dateityp und Desktop-Eintrag der
# Verknuepfung. Ohne das liest die Testreihe die **echte** Anmeldung des
# Benutzers - zeigte die auf ein anderes Verteilerly, lief ein GUI-Test in
# eine ungepatchte Rueckfrage und die ganze Reihe blieb an dem Dialog stehen.
os.environ["XDG_DATA_HOME"] = str(pathlib.Path(_TESTHEIM) / "share")
atexit.register(shutil.rmtree, _TESTHEIM, True)

# Eigene Erweiterungen haben in der Testreihe nichts zu suchen - geprueft
# wird das Laden fremder Erweiterungen an eigenen Ordnern.
os.environ.setdefault("VERTEILERLY_OHNE_FREMDE_ERWEITERUNGEN", "1")

# Und die Testreihe geht nicht ins Netz: die taegliche Nachfrage nach
# einer neueren Fassung bleibt aus. Eine Reihe, die an einer fremden
# Antwort haengt, prueft das Wetter und nicht das Programm.
os.environ.setdefault("VERTEILERLY_OHNE_UPDATEPRUEFUNG", "1")


def bauteil_zurueckgeben(test, bauteil) -> None:
    """Gibt ein Fenster oder Bauteil nach dem Test an Qt zurueck.

    Python allein raeumt es **nicht** ab: seine Lambdas haengen in
    Qt-Verbindungen, der Kreis laeuft durch C++ und ist fuer den Sammler
    nicht zu sehen. Gemessen an fuenf Hauptfenstern: ohne bleiben fuenf
    liegen, mit `deleteLater()` keines.

    Und `deleteLater()` allein **stellt** die Loeschung nur ein - ohne
    Ereignisschleife arbeitet sie niemand ab. Die Reihe hat keine, also
    wird hier gleich abgearbeitet.
    """
    def zurueck():
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QApplication

        bauteil.close()
        bauteil.deleteLater()
        anwendung = QApplication.instance()
        if anwendung is not None:
            anwendung.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    test.addCleanup(zurueck)


def einstellung_bewahren(test, einstellungen, schluessel: str) -> None:
    """Stellt nach dem Test den Wert zurueck, der vorher in der Conf stand.

    Die GUI-Tests teilen sich die Verteilerly.conf der Testreihe. Wer dort
    nur loescht, aendert, was der naechste Test vorfindet - zurueckgestellt
    wird darum, was vorher dastand, und geloescht nur, was vorher fehlte.
    """
    vorher = einstellungen.value(schluessel)

    def zurueck():
        if vorher is None:
            einstellungen.remove(schluessel)
        else:
            einstellungen.setValue(schluessel, vorher)

    test.addCleanup(zurueck)

from verteilerly.blattvorlagen import Blattvorlage

#: Eine Blattvorlage mit dem Schriftfeld der Bauart "beispiel": links die
#: Matrix und der Verteiler, rechts Firma und Kunde mit ihren Anschriften.
#: Sie steht hier im Quelltext, nicht als Datei im Repo - geprueft wird
#: die Bauart, die das Programm kann, nicht eine mitgelieferte Vorlage.
BEISPIELVORLAGE = Blattvorlage(
    id="beispiel",
    name="Mit Anschriften",
    beschreibung="Schriftfeld mit Matrix, Verteiler und zwei Anschriften.",
    schriftfeld_hoehe=38.0,
    schriftfeld_art="beispiel",
    schriftfeld_anteile=(0.42, 0.58),
    schriftfeld=(
        ("verteiler", "verteilernummer", "leiste"),
        ("erstellt", "stand", "geprueft"),
        ("firma", "kunde"),
    ),
)
