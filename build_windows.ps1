# Baut die portable Windows-.exe von Verteilerly.
# Muss AUF Windows laufen - PyInstaller cross-kompiliert nicht, es packt den
# Python, der es aufruft. Unter Linux entsteht stattdessen ein AppImage
# (werkzeuge/appimage.py).
#
#   powershell -ExecutionPolicy Bypass -File build_windows.ps1
#   powershell -ExecutionPolicy Bypass -File build_windows.ps1 -Bump   # Version vorher erhoehen
#
# Ergebnis ist genau eine Datei, ohne Installation startbar:
#   auslieferung\Verteilerly_<Version>.exe
#
# Die Grundausstattung (Verteilervorlagen, Blattvorlagen, Kabeltypen) steckt in
# der .exe. Beim ersten Start legt das Programm sie in einen Ordner "daten"
# neben der Datei, wo sie ohne Auspacken aenderbar ist.
param([switch]$Bump, [switch]$OhneProbelauf)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if ($Bump) {
    Write-Host "==== Version erhoehen ===="
    py -3 werkzeuge\release.py --setzen
}
# Einzige Quelle der Wahrheit: verteilerly/version.py (dieselbe, die auch die
# Spec liest - ein direkter PyInstaller-Aufruf benennt die Datei also genauso).
$Version = (py -3 -c "import re,pathlib; print(re.search('VERSION = \"([^\"]+)\"', pathlib.Path('verteilerly/version.py').read_text()).group(1))").Trim()

Write-Host "==== Abhaengigkeiten sicherstellen ===="
py -3 -m pip install --upgrade pip pyinstaller
py -3 -m pip install -r requirements.txt

Write-Host "==== Symbol und Versionsangaben ($Version) ===="
py -3 werkzeuge\symboldatei.py
py -3 werkzeuge\windowsangaben.py

Write-Host "==== PyInstaller-Build ($Version) ===="
py -3 -m PyInstaller --noconfirm --distpath auslieferung --workpath bau\arbeit Verteilerly.spec

$Exe = "auslieferung\Verteilerly_$Version.exe"
if (-not (Test-Path $Exe)) { throw "Erwartete Datei fehlt: $Exe" }

$Groesse = [math]::Round((Get-Item $Exe).Length / 1MB)
Write-Host ">> Fertig: $Exe ($Groesse MB)"

if (-not $OhneProbelauf) {
    # Die .exe hat kein Konsolenfenster; ihr Selbstbericht kommt als Datei.
    Write-Host "==== Probelauf ===="
    $Bericht = "bau\selbsttest.txt"
    if (Test-Path $Bericht) { Remove-Item $Bericht }
    & ".\$Exe" --selbsttest $Bericht | Out-Null
    if (-not (Test-Path $Bericht)) { throw "Der Probelauf hat keinen Bericht geschrieben." }
    Get-Content $Bericht | ForEach-Object { Write-Host "   $_" }
    if (-not (Select-String -Path $Bericht -Pattern "^ergebnis=ok" -Quiet)) {
        throw "Der Probelauf ist fehlgeschlagen - siehe $Bericht"
    }
}
