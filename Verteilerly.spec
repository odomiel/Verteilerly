# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller-Spec fuer Verteilerly (Windows-.exe).
# Erzeugt ein eigenstaendiges One-File-Programm:
#   auslieferung\Verteilerly_<Version>.exe   - GUI (ohne Konsolenfenster)
#
# Bauen (auf Windows):
#   powershell -ExecutionPolicy Bypass -File build_windows.ps1
#   py -3 -m PyInstaller --noconfirm --distpath auslieferung Verteilerly.spec
#
# Funktionsgleich zur Linux-Version: dasselbe verteilerly-Paket wird
# gebuendelt. Unter Linux entsteht stattdessen ein AppImage ueber
# werkzeuge/appimage.py - der Name traegt dort ebenso die Version.

import os
import re
import shutil
import sys

from PyInstaller.utils.hooks import collect_submodules

# Version aus verteilerly/version.py lesen (einzige Quelle der Wahrheit) - per
# Regex statt per Import, damit die Spec nicht vom Suchpfad des bauenden
# Interpreters abhaengt. SPECPATH setzt PyInstaller auf das Verzeichnis dieser
# Datei; damit stimmt der Pfad auch aus einem anderen Arbeitsverzeichnis heraus.
_wurzel = globals().get("SPECPATH", os.path.dirname(os.path.abspath("__file__")))
with open(os.path.join(_wurzel, "verteilerly", "version.py"), encoding="utf-8") as datei:
    _treffer = re.search(r'VERSION\s*=\s*"([^"]+)"', datei.read())
VERSION = _treffer.group(1) if _treffer else "0"

# Die Grundausstattung wandert mit in die Datei. Beim ersten Start legt das
# Programm sie in einen Ordner "daten" neben der .exe, wo sie ohne Auspacken
# aenderbar ist.
datas = []
for ordner in ("vorlagen", "kabeltypen", "blattvorlagen"):
    quelle = os.path.join(_wurzel, "daten", ordner)
    for name in sorted(os.listdir(quelle)):
        if name.endswith(".yaml"):
            datas.append((os.path.join(quelle, name), os.path.join("daten", ordner)))

# Die Dokumentation, die "Hilfe > Dokumentation" anzeigt. Sie liegt
# im Datenordner, wird aber nicht ausgelegt - sie gehoert zum Programm.
_hilfe = os.path.join(_wurzel, "daten", "hilfe")
if os.path.isdir(_hilfe):
    for name in sorted(os.listdir(_hilfe)):
        if name.endswith(".html"):
            datas.append((os.path.join(_hilfe, name), os.path.join("daten", "hilfe")))

# Die Wortlisten der Oberflaeche - denselben Weg wie die
# Dokumentation: sie gehoeren zum Programm, nicht zum Bestand des Anwenders.
_sprachen = os.path.join(_wurzel, "daten", "sprachen")
if os.path.isdir(_sprachen):
    for name in sorted(os.listdir(_sprachen)):
        if name.endswith(".yaml"):
            datas.append(
                (os.path.join(_sprachen, name), os.path.join("daten", "sprachen"))
            )

# README und Lizenzen mit hinein - eine weitergegebene .exe soll sagen koennen,
# was sie ist und unter welchen Bedingungen sie weitergegeben werden darf.
for beigabe in ("README.md", "LICENSE"):
    pfad = os.path.join(_wurzel, beigabe)
    if os.path.exists(pfad):
        datas.append((pfad, "."))

# Die Lizenztexte der Bestandteile und das Quelltextangebot.
_lizenzen = os.path.join(_wurzel, "lizenzen")
if os.path.isdir(_lizenzen):
    for name in sorted(os.listdir(_lizenzen)):
        if name.endswith(".txt"):
            datas.append((os.path.join(_lizenzen, name), "lizenzen"))

# Dazu die Lizenzen der Python-Pakete und von Python selbst: MIT und BSD
# verlangen ihren Hinweis auch in der gebauten Weitergabe, und PyInstaller
# nimmt die dist-info-Ordner nicht mit. Sie heissen alle LICENSE - darum
# werden sie unter eindeutigem Namen in bau/ zwischengelegt.
sys.path.insert(0, os.path.join(_wurzel, "werkzeuge"))
from lizenztexte import pakettexte, python_lizenz  # noqa: E402

_texte = os.path.join(_wurzel, "bau", "lizenztexte")
os.makedirs(_texte, exist_ok=True)
_fremd = list(pakettexte())
_python = python_lizenz([os.path.join(sys.base_prefix, "LICENSE.txt")])
if _python:
    _fremd.append(("Python-LICENSE.txt", _python))
for name, quelle in _fremd:
    ziel = os.path.join(_texte, name)
    shutil.copyfile(quelle, ziel)
    datas.append((ziel, "lizenzen"))

# Qts deutsche Uebersetzung mitnehmen: sie beschriftet die Datei- und
# Rueckfragedialoge, die Qt selbst zeichnet. Ohne sie stuenden dort
# "Save" und "Cancel" mitten im deutschen Programm.
try:
    from PySide6.QtCore import QLibraryInfo

    _uebersetzungen = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    _deutsch = os.path.join(_uebersetzungen, "qtbase_de.qm")
    if os.path.exists(_deutsch):
        datas.append((_deutsch, os.path.join("PySide6", "Qt", "translations")))
except Exception:  # noqa: BLE001 - ohne Qt wird eben nichts mitgenommen
    pass

# Das eigene Paket vollstaendig einsammeln - die Oberflaeche laedt Teile erst
# beim Aufruf (gui.dialoge, ausgabe.pdf), die eine Analyse sonst uebersieht.
hiddenimports = collect_submodules("verteilerly")

# Alles, was die Oberflaeche nicht anfasst - sonst waechst die Datei um
# Hunderte Megabyte Qt, die niemand startet.
excludes = [
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtQuick",
    "PySide6.QtQml",
    "PySide6.Qt3DCore",
    "PySide6.QtMultimedia",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtBluetooth",
    "PySide6.QtDesigner",
    "PySide6.QtNetwork",
    "PySide6.QtSql",
    "PySide6.QtTest",
    # Gezeichnet wird mit QPainter; auf libQt6OpenGL verweist sonst
    # niemand - im AppImage nachgemessen, hier gilt dasselbe.
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtDBus",
    "tkinter",
    # Pillows Codecs fuer Formate, die hier niemand oeffnet. Der Kern
    # (PIL._imaging) bleibt - ohne ihn laesst sich reportlab nicht
    # importieren.
    "PIL._avif",
    "PIL._webp",
    "PIL._imagingtk",
    "PIL._imagingcms",
    "PIL.AvifImagePlugin",
    "PIL.WebPImagePlugin",
    "sqlite3",
    # Das Programm geht nie ins Netz - ohne _ssl und _hashlib bleiben auch
    # OpenSSLs DLLs draussen. hashlib rechnet mit Pythons eigenen Modulen.
    "_ssl",
    "_hashlib",
    # PIL/Pillow NICHT ausschliessen: reportlab.lib.utils importiert es beim
    # Laden von reportlab.lib.colors - ohne Pillow bricht die .exe beim ersten
    # Import des Hauptfensters ab (ModuleNotFoundError: No module named 'PIL').
    "numpy",
    "pytest",
    "pip",
    "setuptools",
]

# Optionales Symbol; fehlt es, baut PyInstaller ohne eigenes Icon.
# Neu zeichnen laesst es sich mit werkzeuge/symboldatei.py.
_symbol = os.path.join(_wurzel, "assets", "Verteilerly.ico")
icon = _symbol if os.path.exists(_symbol) else None

# Angaben, die Windows unter Eigenschaften anzeigt. Bei einer Datei, die ohne
# Installation weitergereicht wird, ist das die einzige Stelle, an der der
# Stand ablesbar ist. build_windows.ps1 schreibt die Datei vor dem Bauen.
_versionsangaben = os.path.join(_wurzel, "bau", "version.txt")
version_datei = _versionsangaben if os.path.exists(_versionsangaben) else None

a = Analysis(
    ["verteilerly/__main__.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
# Was PySides Hooks mitziehen, ohne dass die Oberflaeche es anfasst. Qt
# Virtual Keyboard steht nur unter der GPL-3, nicht unter der LGPL, und kaeme
# ueber sein Eingabe-Steckmodul herein - samt Qt Quick, Qml und Network, die
# nur es braucht. opengl32sw ist Mesa als OpenGL-Ersatz fuer Rechner ohne
# Treiber; gezeichnet wird mit QPainter. Die Bildformate liest das Programm nie.
WEG_AUS_DER_EXE = (
    "qt6virtualkeyboard", "qtvirtualkeyboardplugin", "qt6quick", "qt6qml",
    "qt6network", "qtuiotouchplugin", "qt6pdf", "qpdf", "opengl32sw",
    "qtiff", "qwebp", "qicns", "qtga", "qwbmp",
)


def mitnehmen(eintrag) -> bool:
    name = os.path.basename(str(eintrag[0]).replace("\\", "/")).lower()
    return not name.startswith(WEG_AUS_DER_EXE)


a.binaries = [eintrag for eintrag in a.binaries if mitnehmen(eintrag)]
a.datas = [eintrag for eintrag in a.datas if mitnehmen(eintrag)]

pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name=f"Verteilerly_{VERSION}",
    console=False,
    icon=icon,
    version=version_datei,
    upx=False,
    bootloader_ignore_signals=False,
    debug=False,
    strip=False,
    runtime_tmpdir=None,
    disable_windowed_traceback=False,
)
