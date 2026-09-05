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
daten/              Liegt neben dem Programm und ist frei erweiterbar
  vorlagen/         Eine YAML-Datei je Vorlage
  kabeltypen/       Farbfolgen der Kabeltypen
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

## Stand

Offen sind Editor, Layoutmodell und Vorschau,
PDF-Ausgabe, Excel und CSV sowie das Verpacken als
AppImage und `.exe`.

Zurückgestellt: Widerstandssymbol,
Pluginschnittstelle, Blatt „Änderungen“, Strichregel.

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
