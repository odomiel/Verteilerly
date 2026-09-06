# Windows-Build (portable .exe)

Verteilerly wird unter Windows als **portable One-File-.exe** gebaut — keine
Installation, kein Konsolenfenster, keine Registry-Einträge. PyInstaller cross-kompiliert nicht: der Build muss **auf
Windows** laufen. Unter Linux entsteht stattdessen ein AppImage
(`werkzeuge/appimage.py`).

## Voraussetzungen

- Windows 10/11 (x64)
- **Python 3** von python.org
- Paketabhängigkeiten:

```powershell
py -3 -m pip install --upgrade pip pyinstaller
py -3 -m pip install -r requirements.txt
```

`requirements.txt` bringt PySide6 (Oberfläche und Vorschau), ReportLab (PDF),
openpyxl (Excel) und PyYAML (Vorlagen, Kabeltypen). Alle vier liefern fertige
Wheels für Windows; nachzubauen ist nichts.

## Bauen

```powershell
powershell -ExecutionPolicy Bypass -File build_windows.ps1
powershell -ExecutionPolicy Bypass -File build_windows.ps1 -Bump   # Version vorher erhöhen

# oder direkt, ohne das Skript:
py -3 werkzeuge\symboldatei.py
py -3 werkzeuge\windowsangaben.py
py -3 -m PyInstaller --noconfirm --distpath auslieferung Verteilerly.spec
```

Ergebnis: `auslieferung\Verteilerly_<Version>.exe` (z. B.
`Verteilerly_2026.09.06b2.exe`) — eine eigenständige, portable Datei, die ohne
Installation gestartet werden kann. Die Version im Dateinamen kommt wie beim
AppImage aus `verteilerly/version.py`; die Spec liest sie selbst, ein direkter
PyInstaller-Aufruf benennt die Datei also genauso.

Nach dem Bauen startet das Skript die `.exe` einmal mit `--selbsttest` und
liest ihren Bericht — Fassung, Qt-Version, Arbeitsordner und die Zahl der
gefundenen Vorlagen, Blattvorlagen und Kabeltypen. Weil die Datei ohne Konsole
gebaut wird, schreibt sie den Bericht nach `bau\selbsttest.txt`.

## Hinweise

- Funktionsgleich zur Linux-AppImage-Variante: es wird dasselbe
  `verteilerly`-Paket gebündelt (`verteilerly\__main__.py` als Einstieg).
- **Der Arbeitsordner liegt neben der `.exe`.** Beim ersten Start legt das
  Programm die mitgelieferten Verteilervorlagen, Blattvorlagen und Kabeltypen
  in `daten\` neben der Datei ab, wo sie mit einem Texteditor änderbar sind.
  Kopiert wird nur, was dort noch nicht liegt — eigene Änderungen bleiben, eine
  spätere Fassung bringt ihre neuen Dateien nach. Unter Linux ist das
  `~/.config/Verteilerly`, weil im AppImage neben dem Programm nicht
  geschrieben werden kann.
- **Die Einstellungen liegen neben dem Programm** als `Verteilerly.conf`
  (Erscheinungsbild, gewählte Blattvorlage) — nicht in der Registry und nicht
  im Benutzerprofil. Zusammen mit `daten\` und der `.exe` ist damit alles in
  einem Ordner: ein Stick, ein Verzeichnis, nichts bleibt auf dem Rechner
  zurück. Lässt sich dort nicht schreiben — etwa unter `C:\Programme` —
  weicht die Datei nach `%APPDATA%\Verteilerly` aus.
- Das Symbol liegt als `assets\Verteilerly.ico` bei und wird aus der Zeichnung
  im Programm erzeugt (`werkzeuge\symboldatei.py`). Fehlt die Datei, baut
  PyInstaller ohne eigenes Icon.
- Bekannter Nebeneffekt von `--onefile`: Die Datei entpackt sich beim Start in
  das Temp-Verzeichnis, wodurch der erste Start ein bis zwei Sekunden braucht.
