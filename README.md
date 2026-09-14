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
  pfade.py          Wo die Daten liegen - entpackt wie gepackt
  gui/              Oberfläche
    hauptfenster.py Fenster, Menüs, Datei- und Kabelbefehle
    uebersicht.py   Verteilerübersicht, gezeichnet wie im Beispiel
    leistenansicht.py  Belegung einer Leiste als Tabelle
    vorschau.py     Zeichnet die Blätter neben der Eingabe
    dialoge.py      Neuer Verteiler, Kabel, Überlauf, Projektdaten
    passform.py     Dialoge bleiben auf dem Bildschirm
    thema.py        Farbsätze hell und dunkel
    sprache.py      Deutsche Beschriftung der Qt-Dialoge
daten/              Liegt neben dem Programm und ist frei erweiterbar
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

**Eigene Felder** — frei benannte Paare wie *Standort: Keller* — erscheinen
im Schriftfeld. Eine Häkchenzeile *Anzeigen auf* sagt, auf welchen
Blattarten: Deckblatt, Verteilerbelegung, Leistenblättern. Eine abgewählte
Blattart lässt den Inhalt unberührt, sie zeigt ihn nur nicht.

Auf der **Verteilerbelegung** stehen sie am Platz der Leiste: dieses Blatt
zeigt alle Leisten, also keine einzelne — eine Zeile „Leiste" bliebe dort
leer. In allen mitgelieferten Blattvorlagen ist das so.

Was bei jedem Verteiler gleich ist — Firma, Kürzel, der Ersteller —,
wird als **Vorgabe** gesetzt: *Einstellungen ▸ Vorgaben für neue
Verteiler* führt dieselben Felder und schreibt sie in die
`Verteilerly.conf`; ein Knopf übernimmt sie aus dem offenen Verteiler.
Bearbeitete Projektdaten ändern die Vorgaben **nicht** von selbst —
sonst überschriebe der letzte Kunde sie ungefragt.

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
Dialoge, damit sie nicht auseinanderlaufen.

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
Eintrag ist der jeweilige Pfeil aus. Neben der Leistenwahl stehen **Textoptionen** für die gewählte Zelle:
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
**eine Zeile tiefer**, wie in einer Tabellenkalkulation; wurde die Eingabe
nicht angenommen — eine unlesbare Rangierung etwa —, bleibt die Marke stehen.
Aus einer geteilten Zelle geht es ebenso geradewegs nach unten, auch
aus dem rechten Feld heraus — und ist die Zelle darunter ebenfalls geteilt,
steht die Eingabemarke dort gleich wieder im rechten Feld, sodass sich eine
Spalte von Nebenstellen ohne Klicken durchtippen lässt. Ein Doppelklick auf eine freie Doppelader legt ein Kabel
auf, einer auf ein aufgelegtes Kabel **bearbeitet** es: Beschriftung,
Kabeltyp, Kabelgröße und Länge lassen sich ändern, und der Dialog trägt auch
den Knopf zum Entfernen. *Davon auflegen* folgt der Kabelgröße — ganz
aufgelegt ist der Regelfall, gekürzt wird danach von Hand — und lässt sich
auch am liegenden Kabel ändern: es **wächst und schrumpft am Ende**, der
Anfang bleibt. Was frei wird, ist wieder frei, samt der Adernfarben, die die
Automatik dort gesetzt hat; reicht die Leiste nicht, fragt der Überlaufdialog
wie beim Auflegen. Leiste und Startpunkt stehen fest — wer die Lage
ändern will, nimmt das Kabel ab und legt es neu auf. Die Farbfolge gehört dem Kabel: ändert sich Kabeltyp
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

Menüeinträge, die gerade nichts bewirken können, sind ausgegraut: ohne
Verteiler die ganze Ausgabe, *Kabel entfernen* nur dort, wo wirklich ein
Kabel liegt, *Speichern* nur, wenn es etwas zu speichern gibt. Jeder
Eintrag trägt einen Statushinweis, der auch im ausgegrauten Zustand
erscheint und sagt, wofür er da ist.

In der **Verteilerbelegung** steht kein Raster: gezeichnet wird allein das
Kabel. Was frei bleibt — links davon, rechts davon oder beides —, ist eine
durchgehende Fläche; wie viele Doppeladern ein Kabel belegt, zeigt die
Breite seines Blocks. Die DA-Nummern in den Zellen führt keine
mitgelieferte Vorlage mehr; wer sie will, setzt `da_nummern: true` in
seiner Blattvorlage. Im Bearbeitungsmodus bleibt jede Leiste unterteilt:
dort wird auf die einzelne Doppelader geklickt.

Auf dem **Leistenblatt** gilt dasselbe für die Kabelspalte: die
Zeilenstriche enden davor. Das Kabel steht dort als ein Block über seine
Zeilen, und was frei bleibt, ist eine durchgehende Fläche.

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
*Knapp* hat eine breite Kabelspalte und lässt den Namen waagerecht.

**Firma und Kunde tragen eine Anschrift, keine Zeile.** Im
Projektdatendialog sind beide Felder mehrzeilig; Name, Straße und Ort stehen auf dem
Blatt untereinander, die Beschriftung nur an der ersten Zeile. So halten
es die Mustertabellen — und so kommt es auch nach Excel.

Wie das Blatt aussieht, sagt eine **Blattvorlage**; was darauf steht,
kommt aus dem Projekt. Vier liegen bei — *Standard* mit allen Spalten,
*Knapp* als reines Rangierblatt ohne Bezeichnung und Bemerkung,
*Ausführlich* mit großer Schrift, hohen Zeilen und einer Bucht je Blatt,
und *Mit Anschriften*. Deren Schriftfeld ist Feld für Feld das
der Mustertabellen (`schriftfeld_art: beispiel`):

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

Die Kabelspalte hat sie schmal und quer wie die Standardvorlage; in den
Mustertabellen gibt es sie nicht, dort stand das Kabel nur in der
Verteilerbelegung. Wie breit die drei Blöcke sind, sagt dort
`schriftfeld_anteile`.
Gewählt wird sie beim Anlegen eines Verteilers und später unter
*Einstellungen ▸ Blattvorlage* (Strg+Umschalt+B); über der Vorschau steht
nur noch, welche gerade gilt. Die Wahl gehört zum Arbeitsplatz, nicht zum
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
Die **Excel-Mappe trägt beides**: vorn die Blätter im Blattbild —
Deckblatt, Verteilerbelegung und je Leiste eines, gesetzt nach der
gewählten Blattvorlage —, dahinter dieselben Daten als Tabelle (*Daten je
Ader*, *Kabel je Leiste*, *Projektdaten*), filter- und sortierbar.
Übernommen werden Spaltenfolge und -breite, Schriftgrößen, Zeilenhöhen,
der verbundene Kabelblock samt Drehung und die Einrichtung auf A4 —
gedruckt kommt das Blatt aus Excel dem PDF nahe. Nachbilden lässt sich ein
PDF damit nicht: Excel ist ein Raster, das Blatt eine Zeichnung; das
Schriftfeld steht darum unter der Tabelle statt am Blattfuß.
Die CSV bleibt reine Daten — eine Zeile je Ader.

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

*Hilfe ▸ Über Verteilerly* führt jeden Baustein mit Fassung, Lizenz und
Aufgabe auf — Python, PySide6, Qt, ReportLab, openpyxl, PyYAML —, dazu
System, Arbeitsordner und Einstellungsdatei. Die Fassungen liest
`bestand.py` aus dem laufenden Programm, nicht aus einer gepflegten
Liste; ein fehlender Baustein steht als *nicht vorhanden* darin, statt
den Bericht abbrechen zu lassen.

Zurückgestellt: Widerstandssymbol,
Pluginschnittstelle, Blatt „Änderungen“, Strichregel.

## Lizenz

Verteilerly steht unter der **GNU General Public License, Version 3 oder
später** (`LICENSE`). Weitergeben und ändern ist erlaubt, auch gewerblich; wer
weitergibt, gibt den Quelltext mit oder bietet ihn an. Ohne jede
Gewährleistung.

Die Bausteine bleiben bei ihren eigenen Lizenzen: Qt und PySide6 unter der
LGPLv3 — dynamisch gebunden und im Abbild austauschbar, wie die LGPL es
verlangt —, ReportLab unter BSD, openpyxl, PyYAML und Pillow unter MIT, Python
unter der PSF-Lizenz. `lizenzen/` trägt die vollständigen Texte und
`QUELLEN.txt`, das für jeden Bestandteil Lizenz und Quelltextadresse nennt;
beides wandert ins AppImage und neben die `.exe`.

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
andere bleibt stehen.

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
