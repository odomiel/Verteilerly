"""Gemeinsames fuer die Testreihen."""

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
