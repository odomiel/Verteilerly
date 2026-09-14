# Beispiele zum Einspielen

Was hier liegt, gehört **nicht** zur Grundausstattung des Programms und
**nicht ins Repo**: `blattvorlagen/` steht in der `.gitignore`. Der Ordner ist
Arbeitsmaterial — was darin liegt, ist die Sache des
Arbeitsplatzes, nicht des Programms.

## Eine eigene Blattvorlage einspielen

**Der kurze Weg: die Datei kopieren.** Die YAML-Datei in den Unterordner
`blattvorlagen/` des Arbeitsordners legen —

* Windows: `<Programmordner>\daten\blattvorlagen\`
* Linux: `~/.config/Verteilerly/blattvorlagen/`

— und das Programm neu starten. Danach steht sie unter *Einstellungen ▸
Blattvorlage* zur Wahl. Das Programm fasst die Datei nicht wieder an:
aufgefrischt wird nur, was es selbst ausgelegt hat.

**Der andere Weg: als Paket.** *Einstellungen ▸ Vorlagen und Einstellungen
einspielen…* liest nur echte Verteilerly-Pakete — die ZIP-Datei braucht den
Merkzettel `paket.json`, sonst kommt „Das ist kein Verteilerly-Paket". Wer
diesen Weg gehen will, erzeugt mit *…sichern…* einmal ein Paket, legt die
Datei hinein und spielt es wieder ein. Für eine einzelne Datei ist der erste
Weg der kürzere.

## Das Schriftfeld der Mustertabellen

Die **Bauart** bleibt im Programm: jede eigene Blattvorlage kann
`schriftfeld_art: beispiel` setzen und bekommt dieselbe Aufteilung — links
oben die Matrix aus Datum und Name mit Erstellt, Stand und Geprüft, links
unten Verteiler, Nummer und Leiste, rechts zwei Kästen mit den Anschriften von
Firma und Kunde. Wie breit sich das Feld teilt, sagt `schriftfeld_anteile`.
