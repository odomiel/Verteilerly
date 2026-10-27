# Baut die portable Windows-.exe von Verteilerly.
# Muss AUF Windows laufen - PyInstaller cross-kompiliert nicht, es packt den
# Python, der es aufruft. Unter Linux entsteht stattdessen ein AppImage
# (werkzeuge/appimage.py).
#
#   powershell -ExecutionPolicy Bypass -File build_windows.ps1
#   powershell -ExecutionPolicy Bypass -File build_windows.ps1 -Bump   # Version vorher erhoehen
#   powershell -ExecutionPolicy Bypass -File build_windows.ps1 -Python 3.15
#
# Ergebnis ist genau eine Datei, ohne Installation startbar:
#   auslieferung\Verteilerly_<Version>.exe
#
# Die Grundausstattung (Verteilervorlagen, Blattvorlagen, Kabeltypen) steckt in
# der .exe. Beim ersten Start legt das Programm sie in einen Ordner "daten"
# neben der Datei, wo sie ohne Auspacken aenderbar ist.
#
# Python wird fest gewaehlt statt "py -3": das nimmt die neueste installierte
# Fassung, und fuer eine frisch erschienene gibt es oft noch keine fertigen
# Pakete (PyYAML fuer 3.15 etwa nur als Quelltext - ohne C++-Compiler scheitert
# die Installation, und die .exe kommt ohne yaml heraus).
param([switch]$Bump, [switch]$OhneProbelauf, [string]$Python = "3.14")

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# Ruft den gewaehlten Python auf und bricht ab, wenn er scheitert -
# $ErrorActionPreference wirkt auf externe Programme nicht.
function Invoke-Py {
    & py "-$Python" @args
    if ($LASTEXITCODE -ne 0) {
        throw "Fehlgeschlagen (Exitcode $LASTEXITCODE): py -$Python $args"
    }
}

& py "-$Python" -c "import sys" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Python $Python nicht gefunden (py -0p zeigt die installierten; Auswahl mit -Python)."
}

if ($Bump) {
    Write-Host "==== Version erhoehen ===="
    Invoke-Py werkzeuge\release.py --setzen
}
# Einzige Quelle der Wahrheit: verteilerly/version.py (dieselbe, die auch die
# Spec liest - ein direkter PyInstaller-Aufruf benennt die Datei also genauso).
$Version = [regex]::Match(
    (Get-Content -Raw -Path "verteilerly/version.py"),
    'VERSION\s*=\s*"([^"]+)"'
).Groups[1].Value
if (-not $Version) { throw "Keine VERSION in verteilerly/version.py gefunden." }

Write-Host "==== Abhaengigkeiten sicherstellen (Python $Python) ===="
Invoke-Py -m pip install --upgrade pip pyinstaller
Invoke-Py -m pip install -r requirements.txt

Write-Host "==== Symbol und Versionsangaben ($Version) ===="
Invoke-Py werkzeuge\symboldatei.py
Invoke-Py werkzeuge\windowsangaben.py

Write-Host "==== PyInstaller-Build ($Version) ===="
Invoke-Py -m PyInstaller --noconfirm --distpath auslieferung --workpath bau\arbeit Verteilerly.spec

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
