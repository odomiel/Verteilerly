@echo off
rem Verteilerly als einzelne .exe bauen.
rem Doppelklick genuegt; Python muss installiert sein und PyInstaller
rem sowie die Abhaengigkeiten aus requirements.txt bereitstehen:
rem     py -m pip install -r requirements.txt pyinstaller

setlocal
cd /d "%~dp0\.."
py -3 werkzeuge\exe.py %*
if errorlevel 1 (
    echo.
    echo Der Bau ist fehlgeschlagen.
    pause
    exit /b 1
)
echo.
echo Fertig: auslieferung\Verteilerly.exe
pause
