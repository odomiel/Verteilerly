# Verteilerly

Dokumentation für LSA+-Verteiler in der Fernmeldetechnik: Deckblatt,
Verteilerbelegung und Leistenblätter aus einem Datenmodell statt aus
kopierten Tabellenblättern.

## Aufbau

```
verteilerly/        Programmpaket
  modell.py         Verteiler, Reihe, Leiste, Stift, Ader, Kabel, Rangierung
  farbcodes.py      Kabeltypen und Adernfarben
  vorlagen.py       Verteilervorlagen
  projektdatei.py   Projekt als JSON lesen und schreiben
  layout.py         Blätter als Zeichenanweisungen — Vorlage für Vorschau und PDF
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
  vorlagen/         Eine YAML-Datei je Vorlage
  kabeltypen/       Farbfolgen der Kabeltypen
werkzeuge/          Release und Verpacken
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

Der Editor zeigt links die Verteilerübersicht und rechts die Belegung der
gewählten Leiste. Ein Doppelklick auf eine freie Doppelader legt ein Kabel
auf, einer auf ein Kabel öffnet es; passt ein Kabel nicht mehr auf die
Leiste, fragt der Überlaufdialog nach der Fortsetzung. Rangierungen werden
in die Spalte getippt (`3 2a`, zwei durch Leerraum getrennt); die
Gegenstelle trägt sich selbst ein.

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
.venv/bin/python3 werkzeuge/bauen.py            # für die laufende Plattform
.venv/bin/python3 werkzeuge/bauen.py --nur-exe  # ohne AppImage
```

Heraus kommt eine einzelne ausführbare Datei in `auslieferung/`, daneben
der Ordner `daten/` — Vorlagen und Kabeltypen bleiben so ohne Auspacken
änderbar. Eine Kopie steckt zusätzlich im Programm, damit eine
allein weitergegebene Datei lauffähig bleibt.

Voraussetzungen unter Linux: `pip install pyinstaller` und die Python-
Bibliothek als `.so` (`sudo apt install libpython3.14` unter Debian und
Ubuntu — ohne sie bricht PyInstaller ab). Für das AppImage muss
`appimagetool` im `PATH` liegen; fehlt es, bleibt das fertige AppDir unter
`bau/` liegen. Die Windows-`.exe` entsteht mit demselben Aufruf unter
Windows.

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

Eine Datei in `daten/kabeltypen/` anlegen oder erweitern — am Programm ist
nichts zu ändern. Drei Regeln stehen zur Verfügung: `lagen` (J-Y(St)Y),
`sternvierer` (Fernmeldekabel mit Ringmarkierung) und `liste` (DIN 47100).
