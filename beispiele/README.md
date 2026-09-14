# Beispiele zum Einspielen

Was hier liegt, gehört **nicht** zur Grundausstattung des Programms: es wird
nicht ausgeliefert und beim ersten Start nicht in den Arbeitsordner gelegt.
Wer es braucht, holt es sich von hier.

## `blattvorlagen/beispiel.yaml` — „Mit Anschriften"

Das Schriftfeld der Mustertabellen, Feld für Feld nachgebaut: links oben die
Matrix aus Datum und Name mit Erstellt, Stand und Geprüft, links unten
Verteiler, Nummer und Leiste, rechts zwei Kästen mit den Anschriften von Firma
und Kunde (`schriftfeld_art: beispiel`). Dazu eine schmale Kabelspalte mit
gedrehtem Namen.

### Einspielen

**Der kurze Weg: die Datei kopieren.** `beispiel.yaml` in den Unterordner
`blattvorlagen/` des Arbeitsordners legen —

* Windows: `<Programmordner>\daten\blattvorlagen\`
* Linux: `~/.config/Verteilerly/blattvorlagen/`

— und das Programm neu starten. Danach steht *Mit Anschriften* unter
*Einstellungen ▸ Blattvorlage* zur Wahl. Das Programm fasst die Datei nicht
wieder an: aufgefrischt wird nur, was es selbst ausgelegt hat.

**Der andere Weg: als Paket.** *Einstellungen ▸ Vorlagen und Einstellungen
einspielen…* liest nur echte Verteilerly-Pakete — die ZIP-Datei braucht den
Merkzettel `paket.json`, sonst kommt „Das ist kein Verteilerly-Paket". Wer
diesen Weg gehen will, erzeugt mit *…sichern…* einmal ein Paket, legt
`blattvorlagen/beispiel.yaml` hinein und spielt es wieder ein. Für eine
einzelne Datei ist der erste Weg der kürzere.

## Warum liegt sie hier und nicht im Programm?

Sie war eine Nachbildung der Mustertabellen und hat
ihren Zweck erfüllt. Die **Bauart** ihres Schriftfeldes bleibt im Programm:
jede eigene Blattvorlage kann `schriftfeld_art: beispiel` setzen und bekommt
dieselbe Aufteilung. Nur die fertige Datei wird nicht mehr mitgeliefert.
