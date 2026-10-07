# Verteilerly

Dokumentation für LSA+-Verteiler in der Fernmeldetechnik: Deckblatt,
Verteilerbelegung und Leistenblätter aus einem Datenmodell statt aus
kopierten Tabellenblättern.

## Aufbau

```
verteilerly/        Programmpaket
  modell.py         Verteiler, Bucht, Leiste, Stift, Ader, Kabel, Rangierung
  bestand.py        Welche Bausteine mit welcher Fassung drinstecken
  paket.py          Vorlagen und Einstellungen sichern und einspielen
  farbcodes.py      Kabeltypen und Adernfarben
  schreibweisen.py  Wie eine Rangierungsadresse geschrieben wird
  vorlagen.py       Verteilervorlagen
  projektdatei.py   Projekt als JSON lesen und schreiben
  einstellungen.py  Projektdaten als Vorgabe in der Verteilerly.conf
  layout.py         Blätter als Zeichenanweisungen — Vorlage für Vorschau und PDF
  blattvorlagen.py  Wie ein Blatt aussieht: Spalten, Ränder, Schriftgrößen
  ausgabe/          PDF, Excel und CSV
    pdf.py          Zeichnet das Layoutmodell mit ReportLab
    mappe.py        Excel-Mappe im Blattbild der Blattvorlage
    tabellen.py     Belegungsdaten je Ader als xlsx und csv
  suche.py          Fundstellen im Projekt - Adern, Kabel, Projektdaten
  sprachen.py       Deutsch oder Englisch - u("…") schlägt nach
  pfade.py          Wo die Daten liegen - entpackt wie gepackt
  erweiterungen/    Eingebaute Erweiterungen, Laden eigener aus dem Arbeitsordner
    blattvorlageneditor/  Der Blattvorlagen-Editor mit Vorschau
  gui/              Oberfläche
    hauptfenster.py Fenster, Menüs, Datei- und Kabelbefehle
    uebersicht.py   Verteilerübersicht, gezeichnet wie im Beispiel
    leistenansicht.py  Belegung einer Leiste als Tabelle
    vorschau.py     Zeichnet die Blätter neben der Eingabe
    dialoge.py      Neuer Verteiler, Kabel, Überlauf, Projektdaten
    passform.py     Dialoge bleiben auf dem Bildschirm
    thema.py        Farbsätze hell und dunkel
    sprache.py      Deutsche Beschriftung der Qt-Dialoge
    erweiterungen.py  Was eine Erweiterung vom Fenster sieht; Verwalten-Dialog
beispiele/          Hinweise zum Einspielen eigener Vorlagen
daten/              Liegt neben dem Programm und ist frei erweiterbar
  sprachen/         Wortlisten der Oberfläche (en.yaml)
  vorlagen/         Eine YAML-Datei je Verteilervorlage
  kabeltypen/       Farbfolgen der Kabeltypen
  blattvorlagen/    Wie die Ausgabe aussieht
build_windows.ps1   Windows: eine einzelne .exe
Verteilerly.spec    Das Rezept dafür — PyInstaller liest es
BUILD_WINDOWS.md    Voraussetzungen und Ablauf des Windows-Builds
assets/             Programmsymbol als .ico und .png
werkzeuge/          Release und Verpacken
  bauen.py          Ein Aufruf, zwei Plattformen
  appimage.py       Linux: AppImage mit Python und Qt darin
  symboldatei.py    Zeichnet das Symbol in assets/
  windowsangaben.py Was Windows unter Eigenschaften anzeigt
  release.py        Nächste Version aus den Git-Tags
tests/              unittest, offscreen - kein pytest, kein Linter
```

## Entwicklungsumgebung

```bash
python3 -m venv --without-pip .venv          # ensurepip fehlt unter Debian
curl -sS https://bootstrap.pypa.io/get-pip.py | .venv/bin/python3
.venv/bin/pip install -r requirements.txt
```

Tests:

```bash
.venv/bin/python3 -m unittest discover -s tests -t .
```

Programm starten:

```bash
.venv/bin/python3 -m verteilerly
```

## Stand

**Name und Nummer des Verteilers** stehen obenan im Dialog *Bearbeiten ▸
Projektdaten* (Strg+B) — im Schriftfeld stehen sie neben
Firma und Kunde, also werden sie auch dort gesucht. Bis dahin waren sie
nur beim Anlegen zu setzen. Abwählen lassen sie sich nicht: ein Blatt
ohne Verteilernamen wäre keines.

Im Projektdatendialog hat jedes Feld ein Häkchen — Standardfelder wie eigene
gleichermaßen. Ein abgewähltes Feld verschwindet vom Blatt **mitsamt seiner
Beschriftung** — eine Zeile „Kunde" ohne Kunden wäre schlimmer als gar
keine — und **behält seinen Inhalt**: wer die Anlagennummer nur für diesen Ausdruck
weglassen will, muss sie nicht löschen. Die Auswahl steht in der
Projektdatei.

**Die Beschriftungen selbst** sind änderbar: wo *Kunde* steht, darf
*Auftraggeber* stehen. Der Schalter *Erweitert: Beschriftungen auf dem Blatt
ändern* steht in der Auswahlzeile neben *Alle* und *Keine* und klappt die
Liste **neben** den Feldern auf — untereinander wäre der
Dialog höher als mancher Bildschirm; links das Wort der Vorgabe, rechts das eigene —, ein
Knopf schreibt überall wieder die Vorgabe hinein. Geändert wird nur das Wort:
Inhalt, Haken und Reihenfolge bleiben, und es gilt auf Deckblatt,
Verteilerbelegung und Leistenblättern gleichermaßen, auch in der Excel-Mappe.
Gemerkt wird nur, was abweicht — in der Projektdatei wie in den Vorgaben, so
dass ein umbenanntes Feld auch im nächsten neuen Verteiler so heißt.
Das Deckblatt hat mehr Platz und schreibt die Vorgabe aus (*Verteilernummer*
statt *Verteiler-Nr.*); ein selbst gesetztes Wort gilt überall unverändert.

**Eigene Felder** — frei benannte Zeilen wie *Standort: Keller* — erscheinen
im Schriftfeld, **jedes an seinem Platz**: der Feldname ist eine Marke des
Schriftfeldes, steht also in genau einem Block, und mehrere Felder lassen sich
unabhängig voneinander verteilen. **Angelegt werden sie in der Blattvorlage**,
im Blattvorlagen-Editor: dort stehen die `eigene_felder` (nur die Namen) und
`eigene_felder_auf` — auf welchen Blattarten sie erscheinen, Deckblatt,
Verteilerbelegung, Leistenblättern. Die Sammelmarke `eigene` für *alle* Felder
gab es bis 2026.09.30; in einer Datei wird sie mit Hinweis übergangen.
*Bearbeiten ▸ Projektdaten* **füllt** sie dann je Verteiler; der Name steht
fest, der Inhalt gehört dem Projekt. Ein Feld ohne Inhalt bleibt als leere
Zeile stehen — zum Ausfüllen von Hand —, und der Haken davor nimmt es wie
jedes andere Feld vom Blatt, ohne den Inhalt zu löschen. Was eine andere
Blattvorlage nicht führt, bleibt gespeichert und kommt mit ihr wieder.

Auf der **Verteilerbelegung** stehen sie an ihrem Platz wie auf jedem Blatt;
die Zeile „Leiste" fällt dort weg, weil dieses Blatt alle Leisten zeigt.

Was bei jedem Verteiler gleich ist — Firma, Kürzel, der Ersteller —,
wird als **Vorgabe** gesetzt: *Einstellungen ▸ Vorgaben für neue
Verteiler* führt dieselben Felder und schreibt sie in die
`Verteilerly.conf`; ein Knopf übernimmt sie aus dem offenen Verteiler.
Bearbeitete Projektdaten ändern die Vorgaben **nicht** von selbst —
sonst überschriebe der letzte Kunde sie ungefragt.

**Welche Felder die Dialoge *Neuer Verteiler* und *Bearbeiten ▸ Projektdaten*
zeigen, sagt die Blattvorlage**: `layout.briefkopffelder()` liest die Marken ihres
Schriftfeldes und löst die Paarmarken auf (`erstellt` → `erstellt_am`,
`erstellt_von`; `gezeichnet` zusätzlich `kuerzel`). Was zum Blatt gehört
(Verteiler, Leiste, Blatt), der Querstrich und die eigenen Felder zählen nicht
mit; der `dokumenttitel` gilt immer, denn er benennt das PDF und überschreibt
das Deckblatt. Beim **Anlegen** behält ein weggelassenes Feld seinen Wert, wird aber
**abgewählt** — sonst stünde ein Wert aus den Vorgaben auf dem Deckblatt, ohne
im Dialog zu stehen. In den **Projektdaten** eines offenen Verteilers wird
dagegen nichts abgewählt: dort stehen Werte, die niemand angefasst hat, und
sie still vom Blatt zu nehmen wäre eine Änderung, um die niemand gebeten hat.
In den **Vorgaben für neue Verteiler** stehen alle Felder — sie gelten für
jede Vorlage.

Beim Anlegen stehen sie schon in den Feldern; was im Projekt steht,
bleibt stehen, die Vorgabe überschreibt nie eine Eingabe. **Angehakt ist
dabei nur, was sie füllen** — ein leeres Feld gehört auf kein Blatt, bis
jemand es ausfüllt; wer in ein Feld schreibt, hakt es damit an. Ein
geöffneter Verteiler bleibt davon unberührt: dort gilt, was in der Datei
steht.

Der Dialog *Neuer Verteiler* trägt die **Projektdaten gleich mit** — rechts
neben den Verteilerangaben, damit der Dialog flach bleibt und beides auf
einen Blick zu sehen ist. Die in der `Verteilerly.conf` gemerkten Angaben
stehen schon in den Feldern und
sind dort für diesen Verteiler zu ändern, samt Haken. Getipptes gilt, die
Vorgabe ergänzt nur, was fehlt. Es sind dieselben Felder wie unter
*Bearbeiten ▸ Projektdaten* — ein Bauteil für beide
Dialoge, damit sie nicht auseinanderlaufen. Neben jedem **Datumsfeld**
(`DATUMSFELDER`, am Namen `*_am` erkennbar) steht ein Knopf **Heute**, der dort
das heutige Datum einträgt und das Feld anhakt — je Feld einer, denn erstellt
und geprüft sind selten derselbe Tag. In den *Vorgaben für neue Verteiler*
fehlen sie (`mit_datumsknoepfen=False`): ein Datum, das dort stehen bleibt,
wäre im nächsten Verteiler das von vorgestern. Geschrieben wird die deutsche
Schreibweise, denn das Datum landet auf dem Blatt und das Blatt folgt nicht der
Sprache der Oberfläche.

Ein neuer Verteiler entsteht aus einer Vorlage oder aus eigenen Angaben;
die DA je Leiste stehen dort als 8, 10 und 20 DA zur Wahl, alles andere
wird eingetippt. Der Haken **Erweiterte Verteiler** stellt an die Stelle der
beiden Zahlen eine Tabelle mit einer Zeile je Bucht — Leisten und Leistengröße
einzeln, für ungleich besetzte Verteiler; eine Leistengröße je Bucht. Auch so
einer lässt sich als **Vorlage** ablegen: die YAML-Datei trägt dann unter
`buchten` statt einer Zahl eine Liste mit einer Zeile je Bucht, während der
gleichmäßige Regelfall bei seinen drei Zahlen bleibt.

```yaml
buchten:
  - {leisten: 4, da: 10}
  - {leisten: 2, da: 20}
``` Eine so gebaute Grundstruktur lässt sich als Vorlage
ablegen — im Dialog selbst oder später über *Bearbeiten ▸ Als Vorlage
speichern*. Sie landet als YAML-Datei im Arbeitsordner (siehe
*Verpacken ▸ Daten*) und steht sofort im Menü.

Verwaltet werden die Vorlagen unter *Einstellungen ▸ Verteilervorlagen*
(Strg+Umschalt+V): umbenennen, löschen — auch die mitgelieferten. Gelöscht
wird die Datei im Arbeitsordner; damit der nächste Start eine mitgelieferte
nicht gleich wieder auslegt, merkt sich `.geloescht.json` daneben, was weg
soll. Der Knopf **Mitgelieferte wiederherstellen** hebt diese Vermerke auf
und legt die ausgelieferten Vorlagen erneut hin — geänderte eingeschlossen,
eigene bleiben unberührt.

Der Editor zeigt links die Verteilerübersicht und rechts die Belegung der
gewählten Leiste. Neben dem Aufklappmenü stehen zwei Pfeile, die Leiste
für Leiste weiterschalten (Alt+← und Alt+→); am ersten und letzten
Eintrag ist der jeweilige Pfeil aus. Daneben nehmen die Pfeile ↶ und ↷ die
letzte Änderung am Verteiler zurück und holen sie wieder her — dasselbe tun
*Bearbeiten ▸ Rückgängig* (Strg+Z) und *Wiederherstellen* (Strg+Y); gemerkt
werden die letzten fünfzig Schritte, und mit einem anderen Projekt fängt die
Reihe von vorn an. Neben der Leistenwahl stehen **Textoptionen** für die gewählte Zelle:
linksbündig, mittig, rechtsbündig, **F** und *K*. Nochmaliges Drücken einer
Ausrichtung nimmt sie zurück — dann gilt wieder, was die Blattvorlage für die
Spalte hält. Gestaltbar sind Farbe, Bezeichnung, Rangierung und Bemerkung;
Stift, Ader und Kabel nicht. Der Stil gehört der Ader, steht in der
Projektdatei und gilt in Leistenansicht, Blatt, PDF und Excel-Mappe
gleichermaßen.

Sind **mehrere Zellen markiert**, gilt ein Knopfdruck für alle auf einmal —
Ausrichtung, Schnitt, Teilung und Prozentwert; alle bekommen dasselbe, nicht
jede ihr eigenes Gegenteil, und was sich nicht gestalten lässt, bleibt
unberührt.

Daneben **teilt** ein Knopf die gewählte Zelle in **zwei
Beschriftungsfelder nebeneinander**; ein Prozentfeld sagt, wie breit das
rechte ist (10–90 %). Bearbeitet wird in zwei Eingabefeldern, Tabulator
springt vom linken ins rechte, Esc verwirft; ein Wechsel zwischen den Hälften
verlässt die Zelle nicht, und ein Klick woanders hin nimmt das Getippte nicht
mit. Auf dem Blatt steht zwischen beiden **kein
Strich** — dort sieht es aus wie eine Zelle mit zwei Angaben; nur die
Leistenansicht deutet es mit einem feinen Punktstrich an. Teilbar sind
Bezeichnung und Bemerkung. Wird die Teilung aufgehoben, bleibt der zweite Text
erhalten. In Excel und CSV stehen beide hintereinander in einer Zelle — ein
Raster hat keine halbe Spalte.

**Entf** leert die gewählten Zellen, ohne sie erst zu öffnen — auch mehrere auf
einmal; gelöscht wird der Inhalt, nicht die Form.

**Im Verteiler suchen** (*Bearbeiten ▸ Suchen…*, Strg+F): vierhundertachtzig
Adern lassen sich nicht durchblättern. Gesucht wird in allem, was von Hand
eingetragen wurde — Farbe, Bezeichnung, Rangierfeld (Ziele in der eingestellten
Schreibweise und Vermerke), Bemerkung, der zweite Text einer geteilten Zelle,
die Kabelbeschriftungen und die Projektdaten samt eigenen Feldern. Jede
Fundstelle nennt Ort (Bucht, Leiste, Stift), Feld und Inhalt; Doppelklick oder
Enter schaltet auf die Leiste und stellt die Marke auf die Zelle, ein Treffer
in den Projektdaten öffnet deren Dialog. Gesucht wird im Modell, nicht in der
Anzeige: `suche.py` kennt kein Qt und ist ohne Oberfläche prüfbar.

In der Leistenansicht schließt **Enter** die Eingabe und geht
**eine Zeile tiefer**, wie in einer Tabellenkalkulation — **auch ohne
Eingabe**: auf der blanken Tabelle fängt der Tastenfilter der Ansicht die
Taste ab und rückt die Marke weiter (`_zeile_weiter`), beim Bearbeiten tut es
der Editor über `weiter` → `_eine_zeile_tiefer`. Wurde eine Eingabe
nicht angenommen — eine unlesbare Rangierung etwa —, bleibt die Marke stehen.
**Ausschneiden, Kopieren, Einfügen** gibt es an beiden Stellen, an denen
gearbeitet wird. In der Leistenansicht über ein Rechtsklickmenü an der Tabelle
und die gewohnten Kürzel (`WidgetShortcut`, damit sie bei offenem Eingabefeld
dem Text gehören): kopiert wird der **Block** von der obersten linken bis zur
untersten rechten markierten Zelle samt allem dazwischen — sonst stünde das
Eingefügte eine Spalte daneben —, und zwar als Tabulatortext, wie ihn eine
Tabellenkalkulation versteht. Eingefügt wird ab der Marke; was sich nicht
beschreiben lässt, bleibt stehen. **Eine geteilte Zelle reist ganz**: neben dem
Text liegt eine eigene Fracht (`ZELLENFRACHT`, JSON) mit beiden Feldern und dem
Anteil — der schlichte Text kann sie nur hintereinander wiedergeben
(`layout.zellentext`, wie CSV und Mappe). Fremder Text lässt die Teilung am
Ziel darum in Ruhe, eigener setzt sie genau so, wie sie kopiert wurde. Ein Einfügen ist **ein** Schritt zum
Zurücknehmen: `LeistenModell.gesammelt()` hält die Meldung zurück, bis alles
steht. In der Verteilerübersicht gilt dasselbe für **Leitungen**: die
Übersicht meldet nur (`kabel_zwischenablage`), das Fenster hält die Ablage.
Kopieren legt ein zweites Kabel an (ohne Rangierungen), Ausschneiden nimmt es
nicht gleich weg — es **zieht beim Einfügen um**, mit Adern und Rangierungen,
denn `kabel_verschieben()` kann das, ein Entfernen-und-neu-Auflegen nicht.

Aus einer geteilten Zelle geht es ebenso geradewegs nach unten, auch
aus dem rechten Feld heraus — und ist die Zelle darunter ebenfalls geteilt,
steht die Eingabemarke dort gleich wieder im rechten Feld, sodass sich eine
Spalte von Nebenstellen ohne Klicken durchtippen lässt. Ein Doppelklick auf eine freie Doppelader legt ein Kabel
auf — vorbelegt mit **2 DA** und **J-Y(St)Y**, dem häufigsten Kabel im
Bestand —, einer auf ein aufgelegtes Kabel **bearbeitet** es: Beschriftung,
Kabeltyp, Kabelgröße und Länge lassen sich ändern, und der Dialog trägt auch
den Knopf zum Entfernen. *Davon auflegen* folgt der Kabelgröße — ganz
aufgelegt ist der Regelfall, gekürzt wird danach von Hand — und lässt sich
auch am liegenden Kabel ändern: es **wächst und schrumpft am Ende**, der
Anfang bleibt. Was frei wird, ist wieder frei, samt der Adernfarben, die die
Automatik dort gesetzt hat; reicht die Leiste nicht, fragt der Überlaufdialog
wie beim Auflegen. Leiste und Startpunkt stehen fest — wer die Lage
ändern will, zieht das Kabel in der Übersicht um oder schneidet es dort aus.

**Der Zusatz am gekürzten Kabel ist abschaltbar** (*Einstellungen ▸ Kürzung am
Kabel anzeigen*, Conf-Schlüssel `kuerzung_zeigen`): eine Anzeigesache wie die
Schreibweise der Rangierungen, darum in der `Verteilerly.conf` und nicht in der
Projektdatei; das Fenster legt sie als `Projekt.kuerzung_zeigen` ans Projekt,
damit `layout` und `mappe` sie sehen. Ohne den Zusatz gehört dem Namen der ganze
Block. **Gesetzt wird er ohnehin so groß, wie der Block ihn trägt**
(`kabelbeschriftung_groesse()`, wie auf der Verteilerbelegung, höchstens
`schrift_mittel`) — vorher stand jeder Name in `schrift_klein` und damit klein
in viel Weiß. Steht der Zusatz dabei, bekommt er die letzten zwei Zeilen des
Blocks; passt er dort nicht mehr (ein Kabel über eine einzige Doppelader),
hängt er in Klammern am Namen, statt aus dem Block zu rutschen. Die Farbfolge gehört dem Kabel: ändert sich Kabeltyp
oder Größe, ziehen die Farben nach, und beim Abnehmen gehen sie mit — Maßstab
ist, was die Automatik gesetzt hat. Von Hand Eingetragenes bleibt stehen, nur
ein ausdrücklicher Haken überschreibt auch das. Die Beschriftung ist außerdem direkt in der Kabelspalte der
Leistenansicht überschreibbar, dort, wo sie steht; passt ein Kabel nicht mehr auf die
Leiste, fragt der Überlaufdialog nach der Fortsetzung. Rangierungen werden
in zwei Felder getippt — je Rangierung eines, mit einer Überschrift
darüber; die Gegenstelle trägt sich selbst ein. Wer beide in ein Feld
tippt (`3 2a   5 4a`), bekommt sie auf beide verteilt. Auf dem Blatt
stehen sie nebeneinander in einer Zelle — dort soll nicht zu sehen sein,
dass es zwei Felder sind.

**Wie eine Adresse geschrieben wird, ist Hausbrauch** — unter
*Einstellungen ▸ Schreibweise der Rangierungen* steht zur Wahl:

| Schreibweise | Beispiel |
|---|---|
| ohne Kürzel | `1 1a` |
| mit Bindestrich | `1-1a` |
| mit L vor der Leiste | `L1 1a` |
| mit L und Bindestrich | `L1-1a` |

Die Wahl gilt für den Editor, das Blatt und die Ausgabe nach Excel und
CSV; sie steht in der `Verteilerly.conf` und gilt damit für alle
Verteiler. **Gelesen wird immer alles**: getippt werden darf jede dieser
Formen, gleich welche gerade eingestellt ist, und in der
Projektdatei steht die Adresse unverändert als `1 1a`. Wer umstellt, muss
also weder seine Projekte noch seine Gewohnheiten anfassen.

**Die Oberfläche ist durchweg deutsch** — auch die Knöpfe, die Qt selbst
beschriftet. Beim Schließen mit ungesicherten Änderungen stehen dort
*Speichern*, *Verwerfen* und *Abbrechen* statt „Save", „Discard" und
„Cancel". Unsere eigenen Rückfragen beschriftet `gui/sprache.py` von Hand;
für die Dialoge, die Qt selbst zeichnet — Datei öffnen, Datei speichern —
wird beim Start Qts deutsche Übersetzung (`qtbase_de.qm`) geladen, die
darum mit ins AppImage und in die .exe wandert.

Ins Rangierfeld darf auf Wunsch auch ein **Vermerk** statt eines Ziels —
„extern", „zur Klemmleiste", „n.b.". Freigeschaltet wird das über
*Einstellungen ▸ Freitext im Rangierfeld zulassen* und ist zunächst aus:
wer nur Ziele einträgt, will einen Tippfehler als Fehler gemeldet
bekommen und nicht als Vermerk stehen haben. Ein Vermerk belegt eines
der beiden Felder, bleibt darin stehen und wird **nicht gespiegelt** —
er gehört der Ader und steht als deren Feld in der Projektdatei. Was
sich als Ziel lesen lässt, bleibt auch dann ein Ziel.

**Ein aufgelegtes Kabel lässt sich umlegen** — in der Verteilerübersicht mit
der Maus an eine andere Stelle ziehen. Es nimmt mit, was daran hängt: die
Adern samt Farben, Bezeichnungen, Bemerkungen, Vermerken und Textstilen, und
die **Rangierungen** (`kabel_verschieben`) — die zeigen auf die Ader, nicht
auf den Platz. Angefasst wird die Doppelader unter dem Zeiger; ein Rahmen
zeigt, wo das Kabel landet, gestrichelt, wo kein Platz ist. Mit **Strg**
entsteht stattdessen eine **Kopie** (`kabel_kopieren`): Typ, Größe und dieselben
Adern, aber keine Rangierungen — eine Verbindung gibt es genau einmal.

**Ein Doppelklick in der Dateiverwaltung** öffnet eine Projektdatei in
Verteilerly, sobald sie dort mit der richtigen ausführbaren Datei verknüpft ist.
Gespeichert wird als `.vtly` — eine einzige Endung, denn Windows verknüpft über
die letzte, und `.json` gehört nicht uns; ältere Dateien (`.vtly.json`) lassen
sich weiter öffnen. Denselben Weg geht die Kommandozeile:
`Verteilerly <datei>`.

**Schreibgeschützt öffnen** (*Datei ▸ Schreibgeschützt öffnen…*,
Strg+Umschalt+O) zeigt eine Datei zum Ansehen: **nichts lässt sich ändern**.
Gesperrt wird an jeder Stelle, an der geändert wird — `LeistenModell` gibt
keine beschreibbare Zelle mehr her (`flags()`) und nimmt auch von Hand nichts
an (`_eintragen()`, `stil_setzen()`, `teilung_setzen()`), die Tabelle öffnet
keinen Editor mehr (`NoEditTriggers`), die Zellenknöpfe sind aus, die
`Uebersicht` legt kein Kabel auf und keines um, und
`aktionen_auffrischen()` graut jeden Menüeintrag aus, der am Projekt
arbeitet. Lesen, markieren, suchen und ausgeben bleiben; `speichern()` leitet
auf *Speichern unter…* um — auch aus der Rückfrage beim Schließen heraus. Die
neue Datei gehört dann dem Anwender, der Schutz fällt weg. Dasselbe stellt
`datei_oeffnen()` selbst fest, wenn `os.access(pfad, os.W_OK)` nein sagt: sonst
fiele es erst beim Speichern auf. Zu sehen ist es in der Titelzeile und als
rotes *schreibgeschützt* neben dem Prozentfeld der geteilten Zelle
(`LeistenAnsicht.schreibschutz_setzen()`, Farbe `warnung` aus dem Farbsatz).
Ein zurückgenommener Stand gehört zu derselben Datei — `vorgeschichte=True`
lässt den Schutz darum stehen.

**Verknüpft wird von Hand**, in der Dateiverwaltung — das Programm trägt nichts
ein. `verknuepfung.py` (ohne Qt) gibt nur Auskunft, und *Tools ▸ Projektdateien
verknüpfen…* zeigt sie: welche Datei zu verknüpfen ist (`zu_verknuepfen()` —
beim AppImage die Abbilddatei, unter Windows der **Starter**, den `starter()`
neben der laufenden .exe sucht, denn die PortableApps-Fassung lässt
`VerteilerlyPortable.exe` erst einrichten und dann
`App\Verteilerly\Verteilerly.exe` laufen), ob verknüpft ist (`angemeldet()`)
und, wenn nicht, welches Programm gerade öffnet (`anderes_programm()`). Gefragt
wird immer, was die Dateiverwaltung **tut**, nicht was irgendwo eingetragen
steht: unter Windows zählt zuerst `FileExts\.vtly\UserChoice` (das setzt
„Öffnen mit ▸ Immer"), unter Linux die `mimeapps.list` samt
`[Removed Associations]` — dafür steht die Marke `KEINE`. Das gepackte Programm
sagt es auch beim Start in der Statuszeile, wenn ein anderes Programm öffnet.

Das Eintragen hat das Programm eine Weile selbst gemacht und ist wieder
ausgebaut: die Wahl des Anwenders geht jeder Eintragung vor, und eine Ausgabe
mit Starter kann sich nicht selbst verknüpfen.

Menüeinträge, die gerade nichts bewirken können, sind ausgegraut: ohne
Verteiler die ganze Ausgabe, *Kabel entfernen* nur dort, wo wirklich ein
Kabel liegt, *Speichern* nur, wenn es etwas zu speichern gibt. Jeder
Eintrag trägt einen Statushinweis, der auch im ausgegrauten Zustand
erscheint und sagt, wofür er da ist.

**Die Verteilerbelegung lässt sich umkehren**: *Einstellungen ▸
Verteilerbelegung umkehren* stellt die Doppeladern von rechts nach links —
wie an einem Verteiler, der von rechts belegt wird. Gedreht wird allein das
Bild dieses Blattes, in Vorschau, PDF und Excel-Mappe gleichermaßen; DA 1
bleibt DA 1, und Leistenblätter, Datenlisten und Adressen rühren sich nicht.
`belegung_umgekehrt` gehört dem Verteiler (Projektdatei, Formatversion 11,
geschrieben nur wenn gesetzt), und der Haken lässt sich zurücknehmen; die
Vorschau springt dabei einmal auf die Belegung, weil man es nur dort sieht.
Im Dialog *Neuer Verteiler* steht derselbe Haken unter *Buchstaben statt
Zahlen* — beides gehört zum Verteiler.
Gerechnet wird an einer Stelle — `layout._belegungsplatz()` für das Blatt,
`mappe._belegungsspalte()` für das Raster.

In der **Verteilerbelegung** steht kein Raster: gezeichnet wird allein das
Kabel. Was frei bleibt — links davon, rechts davon oder beides —, ist eine
durchgehende Fläche; wie viele Doppeladern ein Kabel belegt, zeigt die
Breite seines Blocks. Die DA-Nummern in den Zellen führt keine
mitgelieferte Vorlage mehr; wer sie will, setzt `da_nummern: true` in
seiner Blattvorlage. Im Bearbeitungsmodus bleibt jede Leiste unterteilt:
dort wird auf die einzelne Doppelader geklickt. Die Zellen sind dort
**größer** als auf dem Blatt (38 × 46 statt 27 × 32 Bildpunkte), damit auch ein
Kabel über eine einzige Doppelader seinen Namen zeigt: `namenslage()` bricht
ihn um, solange die Zeilen in den Block passen, und schneidet erst dann ab.

**Die Beschriftung der Leisten** (*Leiste 1*, *Leiste 2* …) steht links neben
jedem Kasten, in einer Flucht mit dem Schriftfeld darunter. Ihre Größe folgt
`schrift.leiste` der Blattvorlage; **0** — die Vorgabe — heißt *wie die
übrigen*: dann gilt `klein`, und erst bei stark vergrößerter Belegung (Faktor
ab 1,4) `normal`. Wer sie für sich haben will, setzt eine Zahl, ohne
Tabellentext und Schriftfeld mitzuziehen. Die **Breite** ihrer Spalte ist
`leistenlabel` im Block `belegung`.

Der **Kabelname steht mitten im Block**, waagerecht wie senkrecht, und so
groß, wie dieser ihn trägt (höchstens `schrift_mittel` der Blattvorlage;
`kabelbeschriftung_groesse()` rechnet es aus, Blatt und Mappe fragen
dieselbe Stelle). Wie viel Platz er darin bekommt, sagt `kabelfeld()`: nicht den
ganzen Block, sondern `fuellgrad_kabel` davon (Vorgabe 0,82), und mindestens
`polster_kabel` bleibt am Rahmen frei — ein Name von Rand zu Rand ließe den
Block vollgestopft aussehen. Beides steht unter `belegung` in der
Blattvorlage, ist also je Vorlage einstellbar. Wird es eng, wird zuerst
**umgebrochen** und erst danach verkleinert — gesucht ist die größte Schrift,
mit der der Name auf so vielen Zeilen, wie der Block sie trägt, hineingeht.
Gedeckelt wird die Zahl der Zeilen hier nicht — der Block ist breit genug, und
was auch klein nicht passt, wird gekürzt:
`zeilen_umbrechen()` und `umbruch_einpassen()` in `layout.py`
brechen an Leerzeichen und an `/`, `-`, `_`. Muss ein Wort selbst
umbrechen, wird es **mit Trennstrich zwischen den Silben** getrennt:
`_trennstellen()` braucht dafür kein Wörterbuch, sondern die Regel, dass
von der Mitlautgruppe zwischen zwei Selbstlauten der längste deutsche
Anlaut mitwandert (`ANLAUTE`) — *Wohn-zim-mer*, *Licht-schacht*, *Zu-cker*.
Zwei Buchstaben bleiben stehen, zwei gehen mit, der Trennstrich zählt zur
Zeilenbreite, und in Zahlen wird gar nicht getrennt. Lieber eine Stufe kleiner als
ein Wort mitten durchgeschnitten; erst danach wird hart getrennt und zuletzt
gekürzt. Ein `Text` mit `umbruch=True` sagt, dass ein Feld diesen Weg geht.

**Gemessen wird dabei mit einem gemeinsamen Maß** (`geschaetzte_breite()`,
Zeichenbreiten einer gewöhnlichen Groteske plus Zuschlag): `textzeilen()`
und `umgebrochene_zeilen()` sagen allen drei Wegen dieselbe Größe und
dieselben Zeilen. Wer zeichnet, misst danach mit seiner eigenen Schrift nach
und setzt notfalls eine Stufe kleiner — größer nie. Die Schrift der
Oberfläche baut rund 6 % breiter als Helvetica; ohne dieses gemeinsame Maß
stünde derselbe Name in der Vorschau zweizeilig, im PDF einzeilig quer über
den Block und in der Mappe unverkleinert darüber hinaus.
Excel misst überhaupt nicht: die Mappe schreibt Größe und Zeilen so hinein,
wie sie gerechnet wurden.

Auf dem **Leistenblatt** gilt dasselbe für die Kabelspalte: die
Zeilenstriche enden davor. Das Kabel steht dort als ein Block über seine
Zeilen, und was frei bleibt, ist eine durchgehende Fläche. Der Name bricht
auch dort um, bevor er schrumpft — quer gedreht **nebeneinander**: für ein
gedrehtes Feld ist die Höhe des Kastens die Länge der Zeile und seine Breite
der Platz, auf dem die Zeilen sich stapeln (`textzeilen()` dreht beides mit,
`_zeilen_gedreht()` im PDF und der gedrehte Malrahmen der Vorschau setzen es
um).

Das **Deckblatt trägt kein Schriftfeld** — es ist selbst eines: Titel,
Verteiler, Aufbau, Kennzahlen und die Projektdaten stehen dort als Liste.
Ein zweiter Kasten am Blattfuß hätte nur wiederholt, was darüber schon
steht.

Die **Verteilerbelegung** richtet sich nach dem, was auf ihr steht: **eine
Bucht steht hochkant** — sie ist schmal und hoch, quer bliebe die halbe Seite
leer —, **ab zwei Buchten quer**. Das Blatt wird dabei ausgefüllt: die Kästen
wachsen, so weit die Seite es hergibt, bei vielen Leisten dürfen die Zellen
zusätzlich in die Breite wachsen (bis zum Doppelten ihrer Höhe), und was übrig
bleibt, wird als Luft zwischen die Buchten und die Leisten verteilt — höchstens
eine Zellenhöhe je Leiste, sonst wird die Bucht zur Leiter.
Die Leistenbeschriftung steht dabei **linksbündig** und beginnt damit auf
derselben Fluchtlinie wie Überschrift und Schriftfeld — vorher hing sie rechts
an ihrem Kasten und rückte mit der Spaltenbreite hin und her.

Die Blattfolge ist Deckblatt, Verteilerbelegung, dann je Leiste ein Blatt.
Zwei Buchten teilen sich ein Blatt und liegen quer. **Jede Bucht bekommt ein
eigenes Blatt im Hochformat**, sobald der Verteiler mehr als zwei Buchten hat
— zu zweit gruppiert bliebe für die letzte ein halbes Blatt — oder eine Bucht
mehr als dreizehn Leisten trägt; zwei solche nebeneinander wären nur noch
Striche. Jedes Blatt heißt nach dem, was darauf steht: **Bucht 3**, bei zweien
nebeneinander **Buchten 1 und 2**.

Was das Programm **Bucht** nennt, hieß bis zur Umbenennung *Reihe*. Ältere
Projektdateien und selbst geschriebene Vorlagen mit den alten Feldnamen
werden weiter gelesen; geschrieben wird immer die neue Fassung.

In der Standardvorlage ist die **Kabelspalte schmal**, und der Kabelname
steht **quer** darin — von unten nach oben zu lesen, wie in technischen
Zeichnungen üblich. Quer ist die Klammer so lang, wie das Kabel Zeilen
belegt: ein langer Name passt dort hinein, statt in einer breiten Spalte
Platz zu fressen, den Bezeichnung und Bemerkung besser brauchen können.
Steuern lässt sich das je Blattvorlage über `kabel_gedreht`; die Vorlage
*Knapp* hat eine breite Kabelspalte und lässt den Namen waagerecht. Weil die
Spalte schmal ist, bleibt es dort bei `zeilen_kabel` Zeilen (Vorgabe 2) —
darunter wird die Schrift kleiner. **Der Deckel gibt nach, bevor ein Name
verloren geht**: geht der Text auch bei kleinster Schrift nicht in zwei Zeilen,
erlaubt `ZEILEN_NOTFALLS` eine dritte; gekürzt wird erst danach. Auf der
Verteilerbelegung gilt der Deckel gar nicht, ihr Block ist breit.

**Firma und Kunde tragen eine Anschrift, keine Zeile.** Im
Projektdatendialog sind beide Felder mehrzeilig; Name, Straße und Ort stehen auf dem
Blatt untereinander, die Beschriftung nur an der ersten Zeile. So halten
es die Mustertabellen, nach denen gearbeitet wurde — und so kommt es auch
nach Excel.

**Leisten heißen 1, 2, 3 — oder A, B, C.** *Einstellungen ▸ Leisten
beschriften* stellt um; gezählt wird innen weiter ab 1, der Buchstabe ist nur
ein anderer Name (die 27. heißt `AA`). Die Wahl gilt überall, wo eine Leiste
genannt wird — Wahlliste, Blätter, Verteilerbelegung, PDF, Mappe, Datenlisten
— und in den Rangierungen, denn die zeigen auf dieselben Leisten. Getippt
werden darf beides: `C 2a` und `3 2a` meinen dieselbe Ader; die Adressen
stehen in der Projektdatei ohnehin als Nummern. Die Beschriftung **gehört dem
Verteiler** — seine Leisten sind am Gerät so beschriftet — und steht darum in
der Projektdatei — **nicht** in der `Verteilerly.conf`: eine Vorgabe gab es bis
2026.10.04, sie ließ den nächsten Verteiler die Beschriftung des letzten erben,
ohne dass jemand danach gefragt hatte. Jeder neue fängt darum gezählt an, wie
er auch mit der Belegung von links nach rechts anfängt. Im Dialog *Neuer
Verteiler* stehen beide Haken beieinander — **Buchstaben statt Zahlen** und
**Verteilerbelegung umkehren** —, leer vorbelegt und wirksam für die Vorlage
wie für den benutzerdefinierten Verteiler; das Menü *Einstellungen ▸ Leisten
beschriften* ist ausgegraut, solange kein Verteiler offen ist.

Wie das Blatt aussieht, sagt eine **Blattvorlage**; was darauf steht,
kommt aus dem Projekt. **Drei liegen bei** — *Standard* mit allen Spalten,
*Knapp* als reines Rangierblatt ohne Bezeichnung und Bemerkung und
*Ausführlich* mit großer Schrift, hohen Zeilen und einer Bucht je Blatt.

Das Schriftfeld lässt sich auch **anders bauen**, nur eben nicht mit einer
mitgelieferten Vorlage: wer es will, setzt `schriftfeld_art: beispiel` in
seiner eigenen Blattvorlage (siehe `beispiele/README.md`):

```
┌────────┬─────────┬─────────┬──────────────────────────────┐
│        │  Datum  │  Name   │        Firma Beliebig        │
│Erstellt│01.01.70 │John Doe │      Beliebige Straße 7      │
│Stand   │         │         │     77777 Beliebiger Ort     │
│Geprüft │         │         │                              │
├────────┴─────────┴─────────┼──────────────────────────────┤
│Verteiler:  Verteiler Name  │        Kunde Beliebig        │
│Verteiler Nr.     1.1       │      Beliebige Straße 7      │
│Leiste:            1        │     77777 Beliebiger Ort     │
└────────────────────────────┴──────────────────────────────┘
```

Wie sich die beiden Hälften teilen, sagt `schriftfeld_anteile` — die
Anschriften bekommen mit `[0.42, 0.58]` die größere.

Von der linken Hälfte bekommen die Beschriftungen **28 %** — *Erstellt*,
*Geprüft* und *Verteiler Nr.* sind kurze Wörter, ein Name wie *Max
Mustermann* braucht dagegen Platz. Beide Blöcke setzen ihre Werte auf
dieselbe Fluchtlinie.

Verteiler, Nummer und das freie Feld darunter stehen **mittig zwischen den
beiden Strichen**: die Zeilenhöhe richtet sich nach der Matrix darüber,
damit beide Hälften dieselbe Schrift tragen, und was an Platz übrig bleibt,
gehört oben und unten zu gleichen Teilen. Auf der Verteilerbelegung sind es
zwei Zeilen statt drei — dort fehlt die Leiste —, und mit genug
eigenen Feldern füllt der Block die Hälfte aus.

Die Kabelspalte steht dabei schmal und quer wie in der Standardvorlage —
in den Mustertabellen gab es sie nicht, dort stand das Kabel nur in der
Verteilerbelegung. Wie breit die drei Blöcke sind, sagt
`schriftfeld_anteile`.
Gewählt wird sie beim Anlegen eines Verteilers und später unter
*Einstellungen ▸ Blattvorlage* (Strg+Umschalt+B); über der Vorschau steht
nur noch, welche gerade gilt. Dort lässt sie sich auch **umbenennen**:
geändert wird der Name, nicht die Kennung — die ist der Dateiname und steht
in der `Verteilerly.conf`. `blattvorlage_umbenennen()` schreibt nur die eine
Zeile in die YAML-Datei und lässt Kommentare und alles andere stehen; war es
eine mitgelieferte Vorlage, entsteht dabei eine Kopie im Arbeitsordner.
**Löschen** geht ebenso — auch eine mitgelieferte: die Datei kommt weg, und
`pfade.loeschen_merken()` hält fest, dass sie nicht wieder ausgelegt wird.
*Mitgelieferte wiederherstellen* hebt die Vermerke auf und legt sie zurück,
wie sie ausgeliefert wurden; derselbe Weg wie bei den Verteilervorlagen.
Die eingebaute Standardvorlage bleibt in jedem Fall wählbar.
Die Wahl gehört zum Arbeitsplatz, nicht zum
einzelnen Verteiler: sie steht in der `Verteilerly.conf` und gilt für
Vorschau, PDF und Excel-Mappe. Eine eigene Blattvorlage ist eine YAML-Datei in
`blattvorlagen/`, die nur angibt, was sie anders will:

```yaml
id: eng
name: "Eng"
rand: 8
zeilenhoehe_max: 7
spalten: [stift, ader, farbe, rangierung]
```

Nötig sind nur `id` und `name`; **der Dateiname ist die Kennung**
(`eng.yaml`), sonst finden Umbenennen und Löschen die Datei nicht. Das
vollständige Format — alle Schlüssel mit Vorgaben, die erlaubten Werte für
`spalten`, `schriftfeld` und `ausrichtung`, dazu ein ganzes Beispiel — steht
in der Dokumentation im Programm, Abschnitt *Blattvorlagen*;
`tests/test_hilfe.py` hält beide Sprachfassungen gegen `Blattvorlage` und
liest das dortige Beispiel mit `blattvorlage_aus_yaml` ein, damit die
Anleitung nicht auseinanderläuft. **Eine fehlerhafte Datei übergeht
`Blattvorlagen.aus_ordnern()`** und hängt den Grund an seine `fehler`-Liste;
das Hauptfenster zeigt ihn beim Start. Vorher nahm ein Tippfehler in einer
eigenen Vorlage das ganze Programm mit.

**Prüfen, bevor die Datei ins Programm kommt** (`pruefung.py`):
das Menü *Tools* führt je Vorlagenart einen Eintrag. `pruefen(pfad, art)`
liest die Datei mit denselben Funktionen wie der Betrieb — eine zweite
Auslegung des Formats liefe auseinander — und gibt einen `Bericht`: taugt
sie, was wurde gelesen (Kennung, Spalten, Schriftfeld, Maße), was fiel auf.
Geworfen wird nichts, ein Bericht kommt immer. Die Oberfläche macht daraus
den `PruefberichtDialog`; `PruefberichtDialog.als_text()` setzt denselben
Text, den der Dialog zeigt.

**Was abgelegt ist, steht an einer Stelle** (`blattvorlagen.ABGELEGT`): Name,
Ort, die Fassung, mit der die Angabe wegfiel, und was heute an ihrer Stelle
steht. Daraus speisen sich beide Seiten — die Meldung beim Lesen
(`hinweis_abgelegt()`: was in der Datei steht, was das Programm damit tat, was
heute dorthin gehört) und das Auffrischen (`blattvorlage_auffrischen()`).
Sonst sagte das eine, was das andere nicht täte. Der Bericht führt es als
`aufzufrischen`, der Dialog bietet dann *Auffrischen…*: `pruefung.auffrischen()`
schreibt die Datei neu, legt die alte als `<name>.yaml.alt` daneben und liest
das Ergebnis **vorher** einmal wie im Betrieb — was durchfiele, wird nicht
geschrieben. Geändert wird nur, was in `ABGELEGT` steht; ein unbekannter
Schlüssel bleibt stehen, denn er kann ein Tippfehler sein.

**Eine Formatnummer wie in der Projektdatei gibt es hier weiter nicht** — aber
nicht mehr mit der Begründung, es gäbe nichts zu versionieren: die Sammelmarke
`eigene` fiel weg, `zeilen_kabel` wechselte den Block, beides sind keine
additiven Erweiterungen. Eine Nummer brächte für diese Fälle nichts, was die
Liste oben nicht besser kann: sie müsste von Hand gepflegt werden, in Dateien,
die von Hand geschrieben sind — eine falsche Nummer wäre schlimmer als keine,
weil sie eine Umschreibung auslöste oder unterschlüge. Die Liste dagegen
erkennt die Angabe an ihrem Namen, trifft also unabhängig davon zu, was in der
Datei behauptet wird. Was eine Nummer zusätzlich sagen könnte — „diese Datei
stammt aus einer **neueren** Fassung" —, sagt der Hinweis auf den unbekannten
Schlüssel bereits, wenn auch vorsichtiger. Der wunde Punkt bleibt derselbe wie
zuvor: ein vertippter Schlüssel fiele nirgends auf, weil die Vorgabe greift.
`modell.unbekannte_schluessel()` meldet ihn darum — für Verteilervorlagen,
Blattvorlagen und Kabeltypen.
Gültig bleibt die Datei: sie kann aus einer neueren Fassung
stammen. Das Hauptfenster sammelt alles in `self.hinweise` und zeigt es
einmal beim Start (`_hinweise_zeigen()`).

Über der Tabelle steht **keine Überschrift** — welche Leiste ein Blatt
zeigt und wie viele Doppeladern sie hat, sagt das Schriftfeld unten; die
Tabelle beginnt am Rand und hat den Platz.

Eine Spalte ohne eigene Überschrift gehört zur vorigen: **Stift** steht
über der Nummer *und* über der Spalte mit a und b, der Strich dazwischen
beginnt erst unter der Kopfzeile. Das gilt für jede Blattvorlage, für die
Leistenansicht und für die Excel-Mappe gleichermaßen.

Die Blätter entstehen in `layout.py` als Zeichenanweisungen in Millimetern
— ohne Qt und ohne PDF-Bibliothek. Die Vorschau zeichnet dieses Modell mit
QPainter, die PDF-Ausgabe mit ReportLab: eine einzige Quelle für das
Blattbild, Vorschau und Ausdruck können nicht auseinanderlaufen.

**Vergrößern gibt es in allen drei Ansichten**, mit demselben Bedienteil:
`gui/zoom.py` hält die `Zoomleiste` (−, Auswahl, +) und `rad_ist_zoom()` für
Strg mit dem Mausrad. Die **Verteilerübersicht** rechnet ihre Maße als
Eigenschaften (`zelle_b`, `zelle_h`, `label_b` …) aus den Konstanten mal
`zoom` und setzt die Schrift dazu; der Rollbereich um sie herum zeigt seine
Balken von selbst, weil `sizeHint()` mitwächst. Die **Leistenansicht** setzt
Schrift und `defaultSectionSize` der Zeilen — gesetzt, nicht gemessen: der
Delegat käme mit seinen Polstern unter seiner Mindesthöhe nicht herunter. Dass
auch `LeistenModell` den Zoom kennt, hat einen Grund: es gibt manchen Zellen
eine **eigene** Schrift (einfarbige Spalten, fett, kursiv), und die bliebe
sonst stehen, während alles andere wächst.

**Die Vorschau lässt sich vergrößern**: neben der Blattvorlage stehen `−`,
eine Auswahl und `+`. *Einpassen* legt das Blatt ins Fenster (so fängt sie an),
die Stufen von 50 % bis 400 % zeigen es in wahrer Größe — bei 100 % ist ein
Millimeter des Blattes einer auf dem Bildschirm, gerechnet aus
`physicalDotsPerInch` des Schirms. Dasselbe tut Strg mit dem Mausrad; ohne Strg
rollt es nur. Die Blattfläche steckt dafür in einem `QScrollArea` mit
`setWidgetResizable(True)`, und der Griff ist ihre **Mindestgröße**: eingepasst
ist sie klein (240 × 300), vergrößert genau so groß wie das Blatt — dann zeigt
der Rollbereich von selbst seine Balken.

Die drei Wege aus dem Programm heraus stehen unter *Datei ▸ Exportieren*
beieinander — PDF (Strg+E), Excel-Mappe und CSV. Vor dem PDF fragt ein kleiner Dialog, welche
Blattarten hineinkommen — Deckblatt, Verteilerbelegung, Leistenblätter;
die Blätter werden fortlaufend nummeriert, und die Wahl bleibt in der `Verteilerly.conf`.
In der Werkzeugleiste steht
dafür **ein** Knopf: links *Export (PDF)*, rechts ein Pfeil, der dasselbe Menü
öffnet; das zuletzt gewählte Format steht danach auf dem Knopf und in der
`Verteilerly.conf`. Daneben steht der Ansichtsknopf, gebaut wie der Exportknopf: auf ihm
steht der Bereich, den ein Druck ein- und ausblendet, sein Pfeil klappt die drei
Bereiche des Fensters auf — Verteilerübersicht (F7), Leistenansicht (F8) und
Vorschau (F9). Eine Wahl dort schaltet sofort und legt den Bereich auf den
Knopf. Sind Übersicht und Leistenansicht beide aus, füllt die Vorschau das
Fenster; gemerkt wird alles in der `Verteilerly.conf`.
Die **Excel-Mappe trägt beides**: vorn die Blätter im Blattbild —
Deckblatt, Verteilerbelegung und je Leiste eines, gesetzt nach der
gewählten Blattvorlage —, dahinter dieselben Daten als Tabelle (*Daten je
Ader*, *Kabel je Leiste*, *Projektdaten*), filter- und sortierbar.
Übernommen werden Spaltenfolge und -breite, Schriftgrößen, Zeilenhöhen,
der verbundene Kabelblock samt Drehung und die Einrichtung auf A4 —
gedruckt kommt das Blatt aus Excel dem PDF nahe. **Das Schriftfeld trägt
dieselbe Bauart wie das Blatt**: bei `schriftfeld_art: beispiel` links oben
die Matrix aus Datum und Name, links unten Verteiler, Nummer und Leiste,
rechts die beiden Anschriften in eigenen, verbundenen Kästen; sonst die
Blöcke nebeneinander, jeder gerahmt. Auch die Verteilerbelegung trägt es,
und das Deckblatt führt dieselben Zeilen wie das gezeichnete. Gefüllt wird
aus denselben Werten wie die Zeichnung (`layout.deckblattzeilen`,
`schriftfeldspalten`, `beispielschriftfeld`) — zwei Auslesungen liefen
sonst auseinander. **Die Seiten füllen das Blatt wie im PDF**: Zeilenhöhen, Zellengrößen und
die Luft dazwischen kommen aus dem Blattmodell (`zeilenhoehe_leiste`,
`belegungsmasse`), die Buchten der Verteilerbelegung stehen nebeneinander,
und die Aufteilung auf mehrere Blätter ist dieselbe (`belegungsgruppen`) —
ab drei Buchten eines je Bucht, benannt wie dort. Gedruckt wird auf eine
Seite in Breite *und* Höhe, und **das Schriftfeld sitzt am Blattfuß**: was
zwischen Tabelle und Fuß fehlt, legt `_bis_zum_blattfuss()` als Zeilenhöhe
ein, damit die freie Fläche darüber liegt und nicht darunter. Nachbilden
lässt sich ein PDF damit trotzdem nicht:
Excel ist ein Raster, das Blatt eine Zeichnung; das Schriftfeld steht darum
unter der Tabelle statt am Blattfuß.
Die **CSV trägt dieselben Angaben** wie die Mappe, nur ohne Blattbild:
oben die Belegung — eine Zeile je Ader, die erste Zeile ihre Kopfzeile, damit
sich die Datei einlesen lässt wie bisher —, darunter durch eine Leerzeile
getrennt die Blöcke *Kabel je Leiste* und *Projektdaten*, jeder mit Titel und
eigener Kopfzeile. Die Projektdaten stehen zuletzt, so wie das Schriftfeld am
Blattfuß; eine mehrzeilige Anschrift steht in einer Zeile, mit `·` getrennt.
Gefüllt wird aus denselben Zeilen wie das Projektdatenblatt der Mappe
(`projektdatenzeilen`).

**Kein Text läuft über sein Feld hinaus.** Passt eine Bezeichnung, eine
Bemerkung oder ein Kabelname nicht in seine Spalte, wird die Schrift dafür
verkleinert — nur für dieses eine Feld, der Rest des Blattes behält seine
Größe. Erst unterhalb von 5 pt hört das auf, denn kleiner liest es niemand
mehr; dann wird gekürzt und ein „…“ zeigt an, dass noch etwas folgt.
Vorschau und PDF rechnen dabei gleich, jedes mit den Maßen seiner eigenen
Schrift-Engine — was in der Vorschau passt, passt auch im Ausdruck.

*Hilfe ▸ Dokumentation* (F1) zeigt die **Dokumentation im Programm**: links
ein Verzeichnis der Abschnitte, rechts der Text — Überblick, Anlegen, Editor,
Kabel, Rangierungen, Projektdaten, Blattvorlagen, Blattregeln, Ausgabe,
Dateien, Menüs mit Tastenkürzeln. Darüber eine **Suche** (Strg+F): sie greift
beim Tippen, ab dem zweiten Zeichen, streicht jeden Treffer an — den
angesteuerten kräftig, die übrigen leise —, zählt sie und geht mit Enter, F3
oder den Pfeilen weiter, am Ende von vorn. Angefangen wird an der sichtbaren
Stelle, nicht am Textanfang; Esc räumt die Suche weg, erst das zweite schließt
das Fenster. Sie liegt als HTML in
`daten/hilfe/dokumentation.html`, wird über dieselbe Suchreihenfolge gefunden
wie die übrigen mitgelieferten Dateien und **nicht** in den Arbeitsordner
ausgelegt — sie gehört zum Programm. Eigene Farben bringt sie nicht mit, damit
sie im dunklen Erscheinungsbild lesbar bleibt. `tests/test_hilfe.py` hält sie in
Schritt: was im Menü steht, muss dort erklärt sein, und **die gedruckte
Kürzeltabelle wird gegen die Menüs geprüft** — ein Kürzel, das nichts auslöst,
wäre schlimmer als keines.

**Jeder Dialog passt auf den Bildschirm** (`gui/passform.py`). Ein
Fenster, das höher ist als die Anzeige, ist unbedienbar — die Knopfleiste
stünde unter dem unteren Rand. `PassenderDialog` ist darum die Grundlage aller
Dialoge: beim Zeigen wird gestutzt, was über die freie Bildschirmfläche
hinausragt, und hereingeschoben, was daneben steht. Wo der Inhalt nicht
schrumpfen kann — *Projektdaten* und *Vorgaben für neue Verteiler* sind lauter
Felder untereinander —, baut der Dialog ihn in ein eigenes Widget und reicht
es an `inhalt_rollbar()` weiter: der Inhalt rollt, die Knopfleiste bleibt
außerhalb des Rollbereichs stehen. Gerollt wird nur, wenn es sein muss.

**Jeder Dialog lässt sich frei verschieben** (`dialoge_freistellen()` in
`gui/passform.py`). GNOMEs Mutter heftet unter X11 ein Fenster an
sein Elternfenster, sobald es sich als modaler Dialog anmeldet
(`_NET_WM_WINDOW_TYPE_DIALOG` plus `_NET_WM_STATE_MODAL`, Einstellung
`attach-modal-dialogs`). Ein Ereignisfilter an der Anwendung meldet darum jeden
`QDialog` beim Zeigen als Werkzeugfenster (`Qt.Tool`) an — auch die, die Qt
selbst baut (`QMessageBox`, `QInputDialog`, Dateidialoge). Am Bildschirm
ausprobiert: Mutter sieht dann `UTILITY` statt `DIALOG`, lässt das Fenster
frei; Qt hält es modal und setzt `WM_TRANSIENT_FOR` weiter — es geht mittig
über dem Hauptfenster auf, bleibt davor, bekommt Fokus und keinen
Taskleisten-Eintrag. Die naheliegende Fensterart `Qt.Window` wäre auch frei,
verlöre aber die Transient-Angabe; `_q_xcb_wm_window_type` wirkt nicht mehr,
sobald das X-Fenster steht, und das steht schon vor dem ersten
`Polish`-Ereignis. Eingeschaltet wird der Filter in `__main__.main()`, nur
unter `xcb` (`FREISTELLEN_AUF`) — das AppImage bringt ohnehin nur diese
Plattform mit.

**Was Qt selbst mitbringt, folgt dem Erscheinungsbild** (`gui/thema.py`): Ankreuzfelder und Auswahlknöpfe bekommen eigene Regeln im Stilblatt,
weil Fusion sie im dunklen Satz dunkel auf dunkel zeichnet. Qts
**Standardbilder** sind feste Dateien in dunklem Grau — die Pfeile der Datei-
und Exportdialoge (zurück, vor, eine Ebene höher) wären darauf kaum zu
erkennen. `PfeilStil`, ein `QProxyStyle` um Fusion, malt sie deshalb selbst,
in der Schriftfarbe des Satzes.

**Deutsch oder Englisch** (`sprachen.py`). *Einstellungen ▸ Sprache*
stellt die Oberfläche um — Menüs, Dialoge, Knöpfe, Hinweise, Meldungen und
Spaltenköpfe. Die Wahl steht in der `Verteilerly.conf` und gilt **nach einem
Neustart**: die Menüs werden beim Aufbau des Fensters einmal beschriftet.

Die **Quellsprache bleibt Deutsch**. Im Quelltext steht der deutsche Satz und
ist zugleich der Schlüssel:

```python
self.setWindowTitle(u("Neuer Verteiler"))
u("Neuer Verteiler: {0} DA auf {1}").format(da, leisten)
```

Jede Stelle ist damit auch ohne Katalog zu lesen, und fehlt eine Übersetzung,
erscheint der deutsche Satz. Der Katalog liegt als YAML in `daten/sprachen/`
und wandert nicht in den Arbeitsordner — wer eine weitere Sprache beisteuern
will, legt eine Datei daneben. `mehrzahl()` übersetzt seine beiden Wörter
selbst, damit die vielen Aufrufstellen nichts davon wissen müssen.
`tests/test_sprachen.py` liest **jeden** übersetzten Satz aus dem Quelltext und
vergleicht ihn mit der Wortliste; umgekehrt darf die Liste nichts Überflüssiges
tragen, und die Platzhalter müssen auf beiden Seiten dieselben sein.

Die **Dokumentation im Programm wechselt mit**: je Sprache eine Datei
(`daten/hilfe/dokumentation.html`, `dokumentation_en.html`), und fehlt die
fremdsprachige, wird die deutsche gezeigt — eine halb übersetzte Hilfe wäre
schlimmer als eine ganz deutsche. Geprüft wird die englische gegen dieselben
Menüs wie die deutsche: jeder Eintrag muss vorkommen, und die gedruckte
Kürzeltabelle muss zu den Tastenkürzeln passen.

Übersetzt wird sonst das **Programm**, nicht das **Dokument**: die Blätter und
die Namen der mitgelieferten Vorlagen bleiben deutsch. Was auf dem Blatt steht,
ist die Arbeit des Anwenders — die Wörter des Schriftfeldes sind ohnehin je
Projekt änderbar.

**Eine unlesbare `Verteilerly.conf` wird nicht überschrieben.** Ein
QSettings, das seine Datei nicht lesen kann, meldet das nur in seinem
Status und verhält sich danach wie ein frisches Programm — der erste
gesetzte Wert schriebe die Vorgaben über die Einstellungen des Anwenders.
Liegt die Datei also da und gibt doch keinen Wert her, sagt das Programm es
beim Start und arbeitet für diesen Lauf mit einer wegwerfbaren Datei. Wo ein
Lauf seine Werte hernahm, hält die Protokoll-Erweiterung in ihren
Startzeilen fest: Programmpfad, benutzte Conf samt Zahl der Werte, Aufruf und
Arbeitsverzeichnis — damit lassen sich zwei Startwege vergleichen.

*Hilfe ▸ Über Verteilerly* führt jeden Baustein mit Fassung, Lizenz und
Aufgabe auf — Python, PySide6, Qt, ReportLab, openpyxl, PyYAML —, dazu
System, Arbeitsordner und Einstellungsdatei. Die Fassungen liest
`bestand.py` aus dem laufenden Programm, nicht aus einer gepflegten
Liste; ein fehlender Baustein steht als *nicht vorhanden* darin, statt
den Bericht abbrechen zu lassen.

Zurückgestellt: Widerstandssymbol, Blatt „Änderungen“, Strichregel.

## Erweiterungen

Das Menü **Erweiterungen** trägt, was über den Kern hinausgeht. Eine
Erweiterung ist ein Modul mit einem Objekt `erweiterung`, das von
`verteilerly.erweiterungen.Erweiterung` erbt und in `einrichten(programm)` seine
Menüeinträge anmeldet; `programm` ist eine bewusst schmale Schnittstelle
(`gui/erweiterungen.py`): Menüeintrag, offenes Projekt, Blattvorlagen,
Statuszeile, Farbsatz und — ohne Zusage — das Hauptfenster.

**Eingebaute** stehen in `EINGEBAUT` — eine feste Liste statt einer Suche, damit
AppImage und `.exe` sie wie der Quellbaum finden — und sind von Haus aus an.
**Eigene** sind Python-Dateien oder -Pakete im Ordner `erweiterungen` des
Arbeitsordners. Sie sind Programmcode mit allen Rechten und darum **aus**, bis
sie unter *Erweiterungen ▸ Erweiterungen verwalten…* eingeschaltet werden;
vorher liest das Programm nur die erste Zeile ihres Docstrings und ihre
Fassung, statt sie auszuführen. *Erweiterungen verwalten* zeigt eine Spalte
**Version**: eine eingebaute trägt die des Programms (`jahr.monat.tag`, sie
wird ja damit ausgeliefert), eine eigene zählt, wie sie will — oder gar nicht. Die Wahl steht in der `Verteilerly.conf` und gilt ab dem nächsten
Start. Was sich nicht laden oder einrichten lässt, wird übergangen und beim
Start genannt; ein Fehler in einem Menüaufruf wird angezeigt, statt das
Programm anzuhalten. Der Haken *Nur mitgelieferte Erweiterungen laden* im
selben Dialog hält alle eigenen dauerhaft aus, auch eingeschaltete; er ist von
Haus aus gesetzt und muss für eigene Erweiterungen erst heraus. Verhindert
eine eigene Erweiterung den Start, startet `--ohne-fremde-erweiterungen` ohne
sie. Die Hilfe (Abschnitt 11) zeigt ein
vollständiges Beispiel; ein Test lädt es.

Die erste eingebaute ist der **Blattvorlagen-Editor**: links alle Werte einer
Blattvorlage samt der Spalten des Leistenblatts und dem Schriftfeld (dem
Briefkopf: Blöcke, Angaben, ihre Ausrichtung, Breiten), rechts das Blatt, gezeichnet
mit demselben Modell wie Vorschau und PDF — am offenen Verteiler oder an einem
Beispiel. Jede Änderung wird mit denselben Regeln geprüft wie eine Datei beim
Lesen. Gespeichert wird auf zwei Wegen: *Speichern* schreibt die geladene
Vorlage in **ihre eigene Datei** zurück — so wird eine vorhandene bearbeitet —,
*Als neue Vorlage speichern* legt eine **neue** an und lässt jede vorhandene,
wie sie ist (`blattvorlage_speichern()` öffnet die Datei sonst exklusiv). In
der Datei steht nur, was von der Vorgabe abweicht (`blattvorlage_als_yaml()`,
die Umkehrung von `blattvorlage_aus_yaml()`).

Die zweite ist das **Protokoll**. Das Programm meldet alles dem Anwender und
nichts einer Datei: was in der Statuszeile steht, ist nach dem Beenden weg, und
ein Fehler, den niemand gefangen hat, verschwindet in der Windows-Fassung ganz
— sie hat keine Konsole. Die Erweiterung hängt sich darum an zwei Stellen: an
die **Statuszeile**, deren Meldungen der Ereignisstrom des Programms sind, und
an `sys.excepthook`, der den **unerwarteten Fehler** samt Bericht bekommt.
Beides geht als Zeile nach `Verteilerly.log` im Arbeitsordner; der bisherige
Haken läuft weiter, wer aus einem Terminal startet, sieht seinen Bericht also
wie immer. Der Dialog *Erweiterungen ▸ Protokoll…* zeigt die Datei, frischt
sie auf, öffnet den Ordner und leert sie. Sie bleibt klein (über 200 000
Zeichen fällt die ältere Hälfte weg) und ist eine **Beigabe**: lässt sie sich
nicht schreiben, arbeitet das Programm weiter, und der Grund steht im Dialog.
In ein Sicherungspaket kommt sie nicht mit.

## Lizenz

Verteilerly steht unter der **GNU General Public License, Version 3 oder
später** (`LICENSE`). Weitergeben und ändern ist erlaubt, auch gewerblich; wer
weitergibt, gibt den Quelltext mit oder bietet ihn an. Ohne jede
Gewährleistung.

Die Bausteine bleiben bei ihren eigenen Lizenzen: Qt und PySide6 unter der
LGPLv3 — dynamisch gebunden und austauschbar, wie die LGPL es verlangt —,
ReportLab unter BSD, openpyxl, PyYAML und Pillow unter MIT, Python unter der
PSF-Lizenz. `lizenzen/` trägt die vollständigen Texte, dazu die der
Fremdbestandteile, die Qt und Python in sich tragen (`Qt-Fremdbestandteile.txt`,
`Python-Fremdbestandteile.txt`), und `QUELLEN.txt`, das für jeden Bestandteil
Lizenz, Text und Quelltextadresse nennt. Beide Bauwege legen die
Lizenzdateien der Python-Pakete und von Python selbst dazu
(`werkzeuge/lizenztexte.py`), das AppImage außerdem die Copyright-Dateien der
Debian-Bibliotheken; das Programm legt den Ordner in seinen Arbeitsordner aus.
Nach einem Qt-Wechsel stellt `werkzeuge/qt_fremdbestandteile.py` die Qt-Liste
neu zusammen — ein Test vergleicht die Fassung.

Gelesen werden sie an zwei Stellen: das Über-Fenster **verweist** auf gnu.org
und auf den Qt-Quelltext, und `grundausstattung_auslegen()` legt die Texte beim
ersten Start in den Arbeitsordner — im AppImage stecken sie sonst im
Einhängepunkt unter `/tmp`, der beim Beenden verschwindet. Offline lesbar
bleiben sie damit auch.

Im Abbild steckt nichts, was das Programm nicht braucht: `readline` und `gdbm`
stehen unter der GPL-3 und werden nie aufgerufen, `python_abspecken()` wirft sie
samt ihrer Bibliotheken heraus.

## Verpacken

```bash
.venv/bin/python3 werkzeuge/bauen.py    # Linux: AppImage, Windows: .exe
```

**Linux — AppImage.** `werkzeuge/appimage.py` baut ein AppImage, das seine
Abhängigkeiten selbst mitbringt: Python, Qt, ReportLab, openpyxl und
PyYAML stecken darin. Grundlage ist eine fertige Python-AppImage von
[python-appimage](https://github.com/niess/python-appimage) — **Python 3.14**,
auf manylinux2014 gebaut. Auf dem Zielrechner muss weder Python noch
Qt installiert sein. Welche Fassung es ist, sagen `PYTHONFASSUNG` und
`BASIS_URL` in `werkzeuge/appimage.py`; beide gehören zusammen geändert.

Was das Programm dem Zielsystem überlässt, ist dessen eigener Unterbau:
glibc, `libGL`, `libX11`, `libxcb`, glib, fontconfig, freetype und dbus.
Diese Bibliotheken gehören zur Arbeitsumgebung und dürfen nicht
mitgeliefert werden — eine mitgebrachte Fassung würde sich mit dem
Grafiktreiber des Rechners beißen. Alles andere, was Qt braucht und was
oft fehlt (`libxcb-cursor`, `libxkbcommon` und die übrigen xcb-Helfer),
liegt im AppImage.

Diese Bibliotheken kommen **nicht vom Baurechner**, sondern aus Debian 12
(bookworm): eine Bibliothek dieses Rechners verlangte dessen glibc und
schnitte damit alles Ältere ab. Das Bauskript holt die Pakete selbst aus
dem Debian-Archiv und packt nur die benötigte `.so` ein.

**Mitgenommen wird nur, was das Programm anfasst.** Der Bau wirft heraus:
Qts Entwicklerwerkzeuge (`qmlls`, `designer`, `assistant`, `linguist`,
`lupdate`, `lrelease` — 13 MB, die nie aufgerufen werden), QtOpenGL samt
Bibliothek und glx-Steckmodul (gezeichnet wird mit QPainter; nachgesehen mit
`readelf`, dass sonst niemand darauf verweist), Qts Bildformat-Steckmodule,
Pillows Codecs für Formate, die hier niemand öffnet (AVIF allein 5 MB),
OpenSSL samt `_ssl` und `_hashlib` — das Programm geht nie ins Netz,
und `hashlib` rechnet ohne sie weiter —, SQLite sowie readline und gdbm.
Zuletzt nimmt `strip` den Bibliotheken die Symboltabellen: PyYAMLs `_yaml.so`
schrumpft dabei von 2,5 auf 0,35 MB.

Der Kern bleibt: ohne `PIL._imaging` ließe sich ReportLab nicht einmal
importieren. Fehlt `strip` auf dem Baurechner, wird das gemeldet und
weitergebaut. Zusammen macht das aus 179 MB entpackt 131 MB und aus 58,7 MB
Abbild **41,0 MB** — so gemessen mit Python 3.13. Mit Python 3.14 liegt das
fertige AppDir bei 132 MB und die Datei bei **41,5 MB**.

Damit verlangt das Ergebnis **glibc 2.34 oder neuer** — das ist die
Untergrenze des Qt-Rads selbst und deckt Ubuntu 22.04, Debian 12, RHEL 9
und Fedora 35 aufwärts ab. Der Bau meldet den Wert und nennt die
Bibliothek, die ihn setzt. Noch tiefer käme man nur mit einem älteren Qt
(PySide6 6.5 ist gegen glibc 2.17 gebaut).

Damit die Datei klein bleibt, fliegt heraus, was die Oberfläche nicht
anfasst — Qt Quick, QML, WebEngine, Multimedia, das GTK-Thema (es zöge die
halbe GTK-Welt nach), das Drucksteckmodul (gedruckt wird über das PDF) und
die ungenutzten Teile der Standardbibliothek. Aus gut 300 MB werden so
rund 57 MB.

Nach dem Bauen startet das fertige AppImage einmal ohne Bildschirm, lädt
die mitgenommenen Bibliotheken, legt ein PDF an und prüft, dass dabei
wirklich das eingebaute Paket und die mitgelieferten Daten benutzt werden
— nicht der Quellbaum daneben.

**Windows — eine einzelne `.exe`.** Gebaut wird über
`build_windows.ps1`, das Rezept steht in `Verteilerly.spec`:
`--onefile`, ohne Konsolenfenster, keine Installation, keine
Registry-Einträge. Ausführlich in **`BUILD_WINDOWS.md`**.

```powershell
powershell -ExecutionPolicy Bypass -File build_windows.ps1
powershell -ExecutionPolicy Bypass -File build_windows.ps1 -Bump   # Version vorher erhöhen
```

Heraus kommt `auslieferung\Verteilerly_<Version>.exe`. Die Version im
Namen liest die Spec selbst aus `verteilerly/version.py` — ein direkter
PyInstaller-Aufruf benennt die Datei also genauso. Symbol und
Versionsangaben sind eingebettet, sodass unter *Eigenschaften* ablesbar
ist, welcher Stand weitergegeben wurde. Nach dem Bauen startet das Skript
die `.exe` einmal mit `--selbsttest` und liest ihren Bericht.

Gebaut werden muss **unter Windows** — PyInstaller packt den Python, der
es aufruft, und übersetzt nicht über die Plattform hinweg.

**Daten.** Vorlagen und Kabeltypen sollen ohne Auspacken änderbar sein.
Beim ersten Start legt das Programm die mitgelieferten Dateien deshalb in
einem Arbeitsordner aus:

| Plattform | Arbeitsordner |
|---|---|
| Windows | `<Programmordner>/daten/` — eine Datei, ein Ordner, ein Stick |
| Linux | `~/.config/Verteilerly/` — dort liegt auch die `Verteilerly.conf` |

Die Einstellungen (Erscheinungsbild, gewählte Blattvorlage) stehen in
`Verteilerly.conf` — unter Windows **neben dem Programm**, sodass ein
Stick alles beisammen hat und nichts auf dem Rechner zurückbleibt; unter
Linux im Einstellungsordner. Eine Registry wird nie beschrieben.

Angelegt wird, was dort noch fehlt — eine spätere Fassung bringt ihre
neuen Dateien so nach. **Aufgefrischt** wird eine Datei nur dann, wenn
sie noch genau so daliegt, wie sie ausgelegt wurde: dann hat niemand sie
angefasst, und eine Verbesserung der mitgelieferten Vorlage darf
ankommen. Sobald jemand eine Zeile geändert hat, bleibt die Datei
unangetastet — eigene Änderungen wiegen schwerer als jede Vorgabe. Wer
was mitgebracht hat, steht im Merkzettel `.ausgelegt.json` daneben; ohne
ihn (Arbeitsordner aus einer älteren Fassung) wird nichts aufgefrischt.
Dorthin wird auch geschrieben, wenn eine Vorlage gesichert wird.

Wer eine mitgelieferte Datei **löscht**, will sie los sein und nicht beim
nächsten Start wiederhaben: `.geloescht.json` hält daneben fest, was
weggeworfen wurde, und das Auslegen geht darüber hinweg. Erst
*Mitgelieferte wiederherstellen* im Vorlagendialog hebt die Vermerke
wieder auf.

**Umziehen und sichern.** *Einstellungen ▸ Vorlagen und Einstellungen
sichern…* packt Verteilervorlagen, Blattvorlagen, Kabeltypen und die
`Verteilerly.conf` in eine ZIP-Datei; *…einspielen…* holt sie zurück —
auf demselben Rechner nach einem Fehlgriff oder auf einem zweiten. Das
Eingespielte gilt sofort, ohne Neustart: Vorlagen, Kabeltypen,
Blattvorlage, Schreibweise und Erscheinungsbild werden neu geladen.

**Was hinein- und herauskommt, ist wählbar:** Verteilervorlagen,
Blattvorlagen, Kabeltypen und Einstellungen tragen je einen Haken, mit
der Zahl der Dateien dahinter. Was es nicht gibt, ist nicht anzuhaken —
ein Paket ohne Kabeltypen kann keine mitbringen —, und ohne einen
einzigen Haken bleibt der Knopf aus.

Beim Einspielen wird nichts blind ausgepackt: übernommen werden nur die
bekannten Unterordner, nur `*.yaml` und die Einstellungsdatei, und nur
Namen ohne Pfadanteil — ein Paket aus fremder Hand darf nichts außerhalb
des Arbeitsordners anlegen. Gleichnamige Dateien werden ersetzt, alles
andere bleibt stehen. Die Wahl der Erweiterungen (`erweiterungen_an`,
`erweiterungen_aus`, `erweiterungen_nur_eingebaute`) bleibt beim Einspielen,
wie sie ist: sonst könnte ein Paket eine eigene Erweiterung einschalten, die
auf dem Rechner liegt.

Gelesen wird darüber hinaus aus allen Orten, an denen Daten liegen
können — ein Ordner `daten/` **neben der AppImage-Datei** geht dabei vor,
damit ein vollständig portabler Stick möglich bleibt, dann der
Arbeitsordner, zuletzt das Mitgelieferte im Abbild. Eine eigene Vorlage
geht vor einer mitgelieferten gleicher Kennung, ohne dass die
mitgelieferte Datei angefasst wird.

Der **erste Bau eines Tages** sieht nach, ob es neuere Fassungen der
Abhängigkeiten gibt: `werkzeuge/abhaengigkeiten.py` vergleicht, was installiert
ist, mit dem, was PyPI meldet — geprüft wird, was in `requirements.txt` steht, damit es keine zweite Liste
gibt, die veraltet. Gemeldet wird nur; ob eine
neuere Fassung taugt, entscheidet niemand nebenbei, und ohne Netz baut es
trotzdem weiter. `--ohne-pruefung` lässt den Blick aus, `abhaengigkeiten.py
--immer` erzwingt ihn.

Mitgeprüft wird der **Unterbau des AppImage**: die Python-AppImage von
python-appimage. Sie kommt nicht von PyPI und fiele sonst durch jedes Raster —
dabei ist sie der größte Baustein im Abbild. Welche gerade eingebaut ist, liest
die Prüfung aus `BASIS_URL` in `werkzeuge/appimage.py`; bei GitHub sucht sie
nur **dieselbe Bauart** (manylinux2014, x86_64, kein Free-threaded-Bau), damit
die glibc-Untergrenze bleibt und die Räder passen. Gemeldet wird getrennt, was
zwei verschiedene Entscheidungen sind:

```
  Python (Abbild)  3.14.7         neuer: 3.14.8
  Python (Abbild)  3.13.15        aktuell (neue Reihe: 3.14.7)
```

Die erste Zeile ist ein Austausch, die zweite will erst geprüft sein. Dabei
bleibt es: geändert wird von Hand, in `PYTHONFASSUNG` und `BASIS_URL`.

```
Abhängigkeiten (einmal täglich geprüft):
  PySide6        6.11.2         aktuell
  pyinstaller    6.22.2         neuer: 6.22.3
  → neuere Fassungen vorhanden. Aktualisieren mit:
      .venv/bin/pip install -U pyinstaller
```

## Versionen

Eine Version ist das Releasedatum im Format `jahr.monat.tag`. Wird an einem
Tag mehr als einmal gebaut, hängt an den folgenden Builds ein `b` mit der
Nummer des Builds:

| Version | Bedeutung |
|---|---|
| `2026.09.05` | erster Build des Tages |
| `2026.09.05b2` | zweiter Build desselben Tages |
| `2026.09.05b3` | dritter Build desselben Tages |

Der Stand ist damit direkt am Namen ablesbar — bei einem portablen Programm
ohne Installation nützlich, weil auf einem Stick mehrere Stände nebeneinander
liegen können.

Maßgeblich sind die Git-Tags; sie tragen die Version ohne Präfix. Die nächste
Version leitet sich daraus ab:

```bash
python3 werkzeuge/release.py            # nächste Version anzeigen
python3 werkzeuge/release.py --setzen   # version.py schreiben, committen, Tag setzen
```

## Kabeltyp ergänzen

Eine Datei in `kabeltypen/` im Arbeitsordner anlegen oder erweitern — am
Programm ist nichts zu ändern. Drei Regeln stehen zur Verfügung: `lagen`
(J-Y(St)Y), `sternvierer` (Fernmeldekabel mit Ringmarkierung) und `liste`
(DIN 47100).

Bei `lagen` läuft die b-Ader ihre Folge endlos durch; die a-Ader ist nur
zu Beginn einer Lage rot. **Eine Lage ist nicht fünf Doppeladern lang** —
wo sie beginnt, hängt an der Kabelgröße und steht als Tabelle in der
Datei (10×2: DA 1 und 9; 16×2: DA 1 und 12). Für eine nicht hinterlegte
Größe bleibt nur die erste Doppelader rot, und das Programm sagt es beim
Auflegen.
