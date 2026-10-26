# Verteilerly

*English version: [README.en.md](README.en.md)*

Dokumentation für **LSA+-Verteiler** in der Fernmeldetechnik: Deckblatt,
Verteilerbelegung und Leistenblätter entstehen aus **einem Datenmodell** statt
aus kopierten Tabellenblättern.

Wer einen Verteiler mit einer Tabellenkalkulation dokumentiert, pflegt dieselbe
Angabe an mehreren Stellen: das Kabel steht in der Belegung und auf dem
Leistenblatt, die Rangierung an beiden Enden, der Verteilername in jedem
Schriftfeld. Verteilerly hält den Verteiler als Datenmodell — Bucht, Leiste,
Doppelader, Kabel, Rangierung — und zeichnet daraus jedes Blatt neu. Eine
Rangierung ist dort **ein** Eintrag, der an beiden Enden erscheint; ein
umgelegtes Kabel nimmt seine Adern und Rangierungen mit.

Das Programm läuft unter **Linux und Windows ohne Installation**, speichert in
eine einzelne Projektdatei und gibt **PDF**, **Excel-Mappe** und **CSV** aus.
Das Programm ist auf Deutsch und English verfügbar. Lizenz:
**GPL-3.0-or-later**.

## Was es kann

**Verteiler anlegen.** Buchten, Leisten je Bucht und Doppeladern je Leiste —
oder aus einer **Verteilervorlage**, die eine wiederkehrende Bauform festhält
(zwei sind dabei, eigene legt *Bearbeiten ▸ Als Vorlage speichern* an).
Leisten werden gezählt oder tragen Buchstaben; die Verteilerbelegung lässt sich
umkehren, wenn von rechts aufgelegt wird.

**Kabel auflegen.** Ein Kabel liegt mit einem oder mehreren Abschnitten auf den
Leisten, darf über beliebig viele Leisten hinauslaufen — gefragt wird so oft,
wie der Rest Leisten braucht — und **gekürzt** aufliegen (z.b. ein
6-DA-Kabel mit fünf aufgelegten Adern). Aus dem **Kabeltyp** kommen die
Adernfarben gleich mit — mitgeliefert sind die üblichen Farbfolgen, eigene
Typen sind eine YAML-Datei. In der Verteilerübersicht lässt sich ein Kabel mit
der Maus **umlegen** (mit Strg kopieren), ausschneiden und einfügen; es nimmt
Farben, Bezeichnungen, Bemerkungen und Rangierungen mit. *Restleitungen
auflegen* nimmt sich alle gekürzten Leitungen auf einmal vor — wohin ihr Rest
kommt, steht je Zeile zur Wahl, mit einem Vorschlag vorbelegt; der Rechtsklick
legt eine einzelne Leitung an genau der angeklickten Stelle auf. Entfernt wird
eine Leitung ganz oder — wenn sie in mehreren Abschnitten liegt — nur das
angeklickte Stück; sie ist danach gekürzt und ihr Rest wieder auflegbar. Liegt
eine Leitung in mehreren Stücken, trägt jedes seine Nummer: *Halle Ost (1)*,
*Halle Ost (2)*.

**Leisten beschriften.** Die Leistenansicht ist die Arbeitsfläche: Farbe,
Bezeichnung, Rangierung und Bemerkung je Ader. Eine Zelle lässt sich in **zwei
Beschriftungsfelder teilen** (mit Prozentangabe), einzeln ausrichten, fett oder
kursiv setzen. Enter springt eine Zeile tiefer, Strg+C/X/V arbeiten mit Zellen
und Blöcken, und ein Klick auf ein Kabel in der Belegung springt an seinen
Anfang.

**Rangieren.** Ziele werden in der eingestellten Schreibweise getippt
(`3 2a`, `L3 2a`, `L3-2a`) und an **beiden** Enden geführt. Neben Zielen nimmt
das Feld **Vorlagen** an — mitgeliefert *direkt*, *defekt*, *12k*, die Liste
ist änderbar. Alles andere bleibt ein Fehler: ein vertipptes Ziel soll
auffallen.

**Blätter gestalten.** Was auf den Blättern steht, sagen die **Projektdaten**
(Firma, Kunde, Anlagen- und Kundennummer, gezeichnet, erstellt, Stand, geprüft
— dazu frei benannte eigene Felder); wie sie aussehen, die
**Blattvorlage**: Spalten, Ränder, Schriftgrößen und der Aufbau des
Schriftfeldes. Drei Vorlagen sind dabei, eigene sind eine YAML-Datei — oder
entstehen im mitgelieferten **Blattvorlagen-Editor** mit sofortiger Vorschau.
Vor dem Einspielen prüft *Tools* eine Vorlagendatei und frischt veraltete
Angaben auf.

**Ausgeben.** Die **Vorschau** zeigt jedes Blatt so, wie es gedruckt wird
(vergrößerbar bis zur wahren Größe). Daraus entstehen ein **PDF**, eine
**Excel-Mappe** im Blattbild samt Datenlisten und **CSV**-Listen für die
Weiterverarbeitung — einzeln oder mit *Komplett* alle drei auf einmal unter
einem Namen.

**Einmal am Tag nach Updates sehen** (*Einstellungen*, abschaltbar): das
Programm fragt die öffentliche Releaseliste und sagt in der Statuszeile
Bescheid, wenn eine neuere Fassung da ist. Heruntergeladen wird nichts,
gesendet nichts außer der Anfrage; abgeschaltet geht es **nie** ins Netz.
*Hilfe ▸ Nach Updates sehen…* fragt auf Knopfdruck und sagt in jedem Fall, was
herauskam.

**Dazu im Alltag.** Suchen über den ganzen Verteiler, Zurücknehmen und
Wiederherstellen der letzten fünfzig Schritte, **schreibgeschützt öffnen**,
helles und dunkles Erscheinungsbild, Sichern und Einspielen aller Vorlagen und
Einstellungen, und ein Protokoll, das sagt, was das Programm getan hat.
Erweitern lässt es sich mit eigenen Python-Modulen.

## Installieren

### Linux — AppImage

```bash
chmod +x Verteilerly-<version>-x86_64.AppImage
./Verteilerly-<version>-x86_64.AppImage
```

Das Abbild (etwa 40 MB) bringt **Python 3.14 und Qt selbst mit**; verlangt wird
nur eine glibc ab 2.34 (Debian 12, Ubuntu 22.04 und neuer). Nichts wird
installiert.

Seine Vorlagen und Einstellungen legt das Programm beim ersten Start in
`~/.config/Verteilerly` ab; dorthin schreibt es auch. Gelesen wird darüber
hinaus ein Ordner `daten` **neben der Abbilddatei**, und zwar zuerst — damit
lässt sich Verteilerly samt eigener Vorlagen auf einem Stick mitnehmen; ist
dort kein Benutzerordner beschreibbar, wird auch darin gespeichert.

```bash
./Verteilerly-<version>-x86_64.AppImage --selbsttest   # Kurzbericht: Fassung, Pfade, Probe-PDF
```

### Windows — .exe

Eine einzelne Datei, ohne Installation startbar:
`Verteilerly_<version>.exe`. Die Grundausstattung steckt darin; beim ersten
Start legt das Programm sie in einen Ordner `daten` **neben** der Datei, wo sie
änderbar ist. Für den Stick gibt es die PortableApps-Fassung mit ihrem
Starter.

Projektdateien (`.vtly`) verknüpft *Tools ▸ Projektdateien verknüpfen…* auf
Knopfdruck — nur für den angemeldeten Benutzer, ohne erhöhte Rechte.
Eingetragen wird der **Starter**, nicht das Programm dahinter: darum übersteht
die Verknüpfung ein Update. Die reine `.exe` trägt ihre Fassung im Namen —
ist die eingetragene Datei nach einem Update weg, zieht der Start die
Verknüpfung selbst nach; liegt sie noch da, meldet er es nur und der Dialog
bietet *Verknüpfung erneuern* an. Hat jemand „Öffnen mit ▸ Immer
diese App" gewählt, gilt weiter diese Wahl — sie lässt sich von außen nicht
setzen.

### Aus dem Quellbaum

```bash
python3 -m venv --without-pip .venv                 # Debian: ensurepip fehlt
curl -sS https://bootstrap.pypa.io/get-pip.py | .venv/bin/python3
.venv/bin/pip install -r requirements.txt
.venv/bin/python3 -m verteilerly
```

Gebraucht werden ein aktuelles Python 3 — entwickelt und gebaut wird mit
**3.14** — und die vier Pakete aus `requirements.txt`: PySide6 (Oberfläche),
ReportLab (PDF), openpyxl (Excel) und PyYAML (Vorlagen). Für die Tests kommt
pypdf dazu, zum Verpacken PyInstaller.

## Bauen

Ein Aufruf, zwei Plattformen — gebaut wird immer **auf** der Zielplattform,
PyInstaller packt den Python, der es aufruft:

```bash
.venv/bin/python3 werkzeuge/bauen.py                 # AppImage (Linux) bzw. .exe (Windows)
.venv/bin/python3 werkzeuge/bauen.py --sauber        # Bau- und Zielordner vorher leeren
.venv/bin/python3 werkzeuge/bauen.py --ohne-pruefung # ohne Blick auf PyPI
```

Das Ergebnis liegt in `auslieferung/`. Der erste Bau eines Tages sieht nach, ob
es neuere Fassungen der Abhängigkeiten oder der Python-Basis gibt, und meldet
das — abgebrochen wird deswegen nie, ohne Netz wird weitergebaut.

**Linux** (`werkzeuge/appimage.py`): Grundlage ist eine python-appimage mit
Python 3.14; die Systembibliotheken kommen aus Debian bookworm statt vom
Baurechner, damit die glibc-Untergrenze dieselbe bleibt. Qt wird auf das
beschnitten, was das Programm anfasst — so bleiben es 40 statt 60 MB.

**Windows** (`build_windows.ps1` mit `Verteilerly.spec`), auf einem
Windows-Rechner:

```powershell
powershell -ExecutionPolicy Bypass -File build_windows.ps1
```

Die Version ist das Releasedatum (`jahr.monat.tag`, weitere Bauten desselben
Tages mit `b2`, `b3` …). Gesetzt wird sie aus den Git-Tags:

```bash
.venv/bin/python3 werkzeuge/release.py            # nächste Version anzeigen
.venv/bin/python3 werkzeuge/release.py --setzen   # schreiben, committen, taggen
```

Ein **Release** entsteht aus den gebauten Dateien. Wo das Repo gespiegelt
wird, überträgt der Spiegel nur Zweige und Tags — Releases und ihre Anhänge
legt `werkzeuge/github_release.py` nach:

```bash
python3 werkzeuge/github_release.py --probe auslieferung/Verteilerly-*   # erst zeigen
python3 werkzeuge/github_release.py auslieferung/Verteilerly-*           # dann anlegen
```

Es wartet, bis der Tag drüben ist, legt das Release an (oder nimmt ein
vorhandenes), lädt die Dateien hoch und prüft jede per SHA256 gegen.
Repo-Kennung und Token stehen **außerhalb** des Repos — in
`$VERTEILERLY_GITHUB_SLUG` und `$GITHUB_TOKEN` oder als `github_repo` und
`github_token` im Arbeitsordner; der Token braucht nur *Contents: Read and
write*.

## Handbuch

Das Benutzerhandbuch ist die Dokumentation, die das Programm unter *Hilfe ▸
Dokumentation* zeigt. Als PDF gesetzt wird sie mit:

```bash
.venv/bin/python3 werkzeuge/handbuch.py              # deutsch und englisch
.venv/bin/python3 werkzeuge/handbuch.py --sprache en # nur eine Sprache
```

Die Dateien landen in `auslieferung/` — `Verteilerly-Handbuch-<version>.pdf`
und `Verteilerly-Manual-<version>.pdf`, mit Titelblatt, Inhaltsverzeichnis und
Seitenzahlen.

## Tests

Geprüft wird mit `unittest`, ohne Bildschirm (die GUI-Tests laufen offscreen).
Die ganze Reihe braucht etwa zwei Minuten:

```bash
.venv/bin/python3 -m unittest discover -s tests -t .   # alle Tests
.venv/bin/python3 -m unittest tests.test_layout        # eine Datei
```

## Lizenz

Große Teile des Projekts wurden mithilfe von KI (Claude Code) erstellt.

Verteilerly steht unter der **GPL-3.0-or-later** (`LICENSE`). Die
mitgelieferten Bestandteile stehen unter LGPL, BSD, MIT und PSF; ihre Texte
liegen in `lizenzen/`, jede Quelle samt Adresse in `lizenzen/QUELLEN.txt`.
*Hilfe ▸ Über Verteilerly* zeigt im Programm, was gerade geladen ist, mit
Fassung und Lizenz.
