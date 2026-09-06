# Verteilerly

Dokumentation für LSA+-Verteiler in der Fernmeldetechnik: Deckblatt,
Verteilerbelegung und Leistenblätter aus einem Datenmodell statt aus
kopierten Tabellenblättern.

## Aufbau

```
verteilerly/        Programmpaket
  modell.py         Verteiler, Bucht, Leiste, Stift, Ader, Kabel, Rangierung
  farbcodes.py      Kabeltypen und Adernfarben
  vorlagen.py       Verteilervorlagen
  projektdatei.py   Projekt als JSON lesen und schreiben
  layout.py         Blätter als Zeichenanweisungen — Vorlage für Vorschau und PDF
  blattvorlagen.py  Wie ein Blatt aussieht: Spalten, Ränder, Schriftgrößen
  ausgabe/          PDF, Excel und CSV
    pdf.py          Zeichnet das Layoutmodell mit ReportLab
    tabellen.py     Belegungsdaten je Ader als xlsx und csv
  pfade.py          Wo die Daten liegen - entpackt wie gepackt
  gui/              Oberfläche
    hauptfenster.py Fenster, Menüs, Datei- und Kabelbefehle
    uebersicht.py   Verteilerübersicht, gezeichnet wie im Beispiel
    leistenansicht.py  Belegung einer Leiste als Tabelle
    vorschau.py     Zeichnet die Blätter neben der Eingabe
    dialoge.py      Neuer Verteiler, Kabel, Überlauf, Briefkopf
    thema.py        Farbsätze hell und dunkel
daten/              Liegt neben dem Programm und ist frei erweiterbar
  vorlagen/         Eine YAML-Datei je Verteilervorlage
  kabeltypen/       Farbfolgen der Kabeltypen
  blattvorlagen/    Wie die Ausgabe aussieht
werkzeuge/          Release und Verpacken
  bauen.py          Eine Datei je Plattform
  appimage.py       AppImage mit Python und Qt darin
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

Ein neuer Verteiler entsteht aus einer Vorlage oder aus eigenen Angaben;
die DA je Leiste stehen dort als 8, 10 und 20 DA zur Wahl, alles andere
wird eingetippt. Eine so gebaute Grundstruktur lässt sich als Vorlage
ablegen — im Dialog selbst oder später über *Bearbeiten ▸ Als Vorlage
speichern*. Sie landet als YAML-Datei im Arbeitsordner (siehe
*Verpacken ▸ Daten*) und steht sofort im Menü.

Der Editor zeigt links die Verteilerübersicht und rechts die Belegung der
gewählten Leiste. Ein Doppelklick auf eine freie Doppelader legt ein Kabel
auf, einer auf ein Kabel öffnet es; passt ein Kabel nicht mehr auf die
Leiste, fragt der Überlaufdialog nach der Fortsetzung. Rangierungen werden
in die Spalte getippt (`3 2a`, zwei durch Leerraum getrennt); die
Gegenstelle trägt sich selbst ein.

Die Blattfolge ist Deckblatt, Verteilerbelegung, dann je Leiste ein Blatt.
Bis zwei Buchten passt die Verteilerbelegung auf ein Blatt; ab der dritten
Bucht bekommt je zwei Buchten ein eigenes Blatt, benannt nach dem, was
darauf steht: **Buchten 1 und 2**, **Buchten 3 und 4**, bei einer
einzelnen **Bucht 5**. Ein Verteiler mit vier Buchten ergibt also zwei
Blätter — gequetscht wird nichts.

Was das Programm **Bucht** nennt, hieß bis zur Umbenennung *Reihe*. Ältere
Projektdateien und selbst geschriebene Vorlagen mit den alten Feldnamen
werden weiter gelesen; geschrieben wird immer die neue Fassung.

Wie das Blatt aussieht, sagt eine **Blattvorlage**; was darauf steht,
kommt aus dem Projekt. Drei liegen bei — *Standard* mit allen Spalten,
*Knapp* als reines Rangierblatt ohne Bezeichnung und Bemerkung, und
*Ausführlich* mit großer Schrift, hohen Zeilen und einer Bucht je Blatt.
Gewählt wird über der Vorschau; die Wahl gilt auch für die PDF-Ausgabe
und wird gemerkt. Eine eigene Blattvorlage ist eine YAML-Datei in
`blattvorlagen/`, die nur angibt, was sie anders will:

```yaml
id: eng
name: "Eng"
rand: 8
zeilenhoehe_max: 7
spalten: [stift, ader, farbe, rangierung]
```

Die Blätter entstehen in `layout.py` als Zeichenanweisungen in Millimetern
— ohne Qt und ohne PDF-Bibliothek. Die Vorschau zeichnet dieses Modell mit
QPainter, die PDF-Ausgabe mit ReportLab: eine einzige Quelle für das
Blattbild, Vorschau und Ausdruck können nicht auseinanderlaufen.
Excel und CSV geben nicht das Blatt aus, sondern die Belegungsdaten — eine
Zeile je Ader, filter- und sortierbar.

Zurückgestellt: Widerstandssymbol,
Pluginschnittstelle, Blatt „Änderungen“, Strichregel.

## Verpacken

```bash
.venv/bin/python3 werkzeuge/bauen.py    # Linux: AppImage, Windows: .exe
```

**Linux — AppImage.** `werkzeuge/appimage.py` baut ein AppImage, das seine
Abhängigkeiten selbst mitbringt: Python, Qt, ReportLab, openpyxl und
PyYAML stecken darin. Grundlage ist eine fertige Python-AppImage von
[python-appimage](https://github.com/niess/python-appimage) — ein auf
manylinux2014 gebautes Python. Auf dem Zielrechner muss weder Python noch
Qt installiert sein.

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

**Windows — `.exe`.** `werkzeuge/bauen.py` ruft dort PyInstaller mit
`--onefile` auf. Unter Linux geht das mit `--nur-exe` ebenfalls; dafür
werden `pip install pyinstaller` und die Python-Bibliothek als `.so`
gebraucht (`sudo apt install libpython3.14` unter Debian und Ubuntu).

**Daten.** Vorlagen und Kabeltypen sollen ohne Auspacken änderbar sein.
Beim ersten Start legt das Programm die mitgelieferten Dateien deshalb in
einem Arbeitsordner aus:

| Plattform | Arbeitsordner |
|---|---|
| Windows | `<Programmordner>/daten/` — eine Datei, ein Ordner, ein Stick |
| Linux | `~/.config/Verteilerly/` — dort liegt auch die `Verteilerly.conf` |

Kopiert wird nur, was dort noch nicht liegt: eigene Änderungen bleiben,
und eine spätere Fassung bringt ihre neuen Dateien nach. Dorthin wird
auch geschrieben, wenn eine Vorlage gesichert wird.

Gelesen wird darüber hinaus aus allen Orten, an denen Daten liegen
können — ein Ordner `daten/` **neben der AppImage-Datei** geht dabei vor,
damit ein vollständig portabler Stick möglich bleibt, dann der
Arbeitsordner, zuletzt das Mitgelieferte im Abbild. Eine eigene Vorlage
geht vor einer mitgelieferten gleicher Kennung, ohne dass die
mitgelieferte Datei angefasst wird.

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
