"""Gemeinsames fuer die Testreihen."""

import os

# Die Testreihe baut das echte Hauptfenster. Eigene Erweiterungen aus dem
# echten Arbeitsordner haben darin nichts zu suchen - geprueft wird das
# Laden fremder Erweiterungen an eigenen Ordnern.
os.environ.setdefault("VERTEILERLY_OHNE_FREMDE_ERWEITERUNGEN", "1")


def einstellung_bewahren(test, einstellungen, schluessel: str) -> None:
    """Stellt nach dem Test den Wert zurueck, der vorher in der Conf stand.

    Die GUI-Tests schreiben in die echte Verteilerly.conf. Wer dort nur
    loescht, nimmt dem Anwender seine Wahl - zurueckgestellt wird darum,
    was vorher dastand, und geloescht nur, was vorher fehlte.
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
