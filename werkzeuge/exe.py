#!/usr/bin/env python3
"""Verteilerly als eine einzelne Windows-.exe bauen.

Heraus kommt genau eine Datei: keine Installation, keine Laufzeitumgebung
daneben, keine Registry. Python, Qt und die mitgelieferten Vorlagen
stecken darin; beim ersten Start legt das Programm sie in einen
Datenordner neben der .exe, wo sie ohne Auspacken zu aendern sind.

    python werkzeuge\\exe.py             baut die .exe
    python werkzeuge\\exe.py --zeigen    zeigt nur den PyInstaller-Aufruf
    python werkzeuge\\exe.py --behalten  Bauordner nicht loeschen

Gebaut werden muss unter Windows: PyInstaller uebersetzt nicht ueber die
Plattform hinweg - es packt den Python, der es aufruft. Unter Linux baut
werkzeuge/appimage.py das Gegenstueck.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from verteilerly.version import VERSION, zerlegen  # noqa: E402

NAME = "Verteilerly"
BAUORDNER = WURZEL / "bau"
ZIELORDNER = WURZEL / "auslieferung"
DATEN = WURZEL / "daten"

# Alles, was die Oberflaeche nicht anfasst - sonst waechst die Datei um
# Hunderte Megabyte Qt, die niemand startet.
UNNOETIG = (
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
    "tkinter",
    "PIL",
    "numpy",
    "pytest",
    "pip",
    "setuptools",
)


def melden(text: str) -> None:
    print(f"· {text}", flush=True)


def voraussetzungen_pruefen(streng: bool = True) -> None:
    """Bricht mit einem verwertbaren Hinweis ab, statt in PyInstaller."""
    if streng and not sys.platform.startswith("win"):
        raise SystemExit(
            "Die .exe muss unter Windows gebaut werden - PyInstaller packt den\n"
            "Python, der es aufruft, und übersetzt nicht über die Plattform\n"
            "hinweg. Für Linux baut werkzeuge/appimage.py das Gegenstück.\n"
            "  (--zeigen führt den Aufruf hier trotzdem vor.)"
        )
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        raise SystemExit("PyInstaller fehlt:  pip install pyinstaller") from None


def symbol_schreiben(ordner: pathlib.Path) -> pathlib.Path:
    """Zeichnet das Programmsymbol als .ico fuer die Datei im Explorer."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from verteilerly.gui.symbol import symbol

    QApplication.instance() or QApplication([])
    ordner.mkdir(parents=True, exist_ok=True)
    ziel = ordner / f"{NAME}.ico"
    symbol(256).save(str(ziel))
    return ziel


def versionsdatei_schreiben(ordner: pathlib.Path) -> pathlib.Path:
    """Die Angaben, die Windows unter Eigenschaften anzeigt.

    Ohne sie steht dort nichts - bei einer Datei, die ohne Installation
    weitergegeben wird, ist das die einzige Stelle, an der die Fassung
    ablesbar ist.
    """
    teile = zerlegen(VERSION)
    datum = teile.datum
    vier = f"{datum.year}, {datum.month}, {datum.day}, {teile.build}"
    ordner.mkdir(parents=True, exist_ok=True)
    ziel = ordner / "version.txt"
    ziel.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({vier}), prodvers=({vier}),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040704B0', [
        StringStruct('FileDescription', 'Dokumentation für LSA+-Verteiler'),
        StringStruct('FileVersion', '{VERSION}'),
        StringStruct('InternalName', '{NAME}'),
        StringStruct('OriginalFilename', '{NAME}.exe'),
        StringStruct('ProductName', '{NAME}'),
        StringStruct('ProductVersion', '{VERSION}'),
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1031, 1200])])
  ]
)
""",
        encoding="utf-8",
    )
    return ziel


def befehl_bauen(symbol: pathlib.Path, versionsdatei: pathlib.Path) -> list[str]:
    """Der vollstaendige PyInstaller-Aufruf."""
    befehl = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",                       # genau eine Datei
        "--windowed",                      # kein Konsolenfenster daneben
        "--name", NAME,
        "--icon", str(symbol),
        "--version-file", str(versionsdatei),
        "--distpath", str(ZIELORDNER),
        "--workpath", str(BAUORDNER / "arbeit"),
        "--specpath", str(BAUORDNER),
        # Die Grundausstattung wandert in die Datei; das Programm legt sie
        # beim ersten Start daneben, damit sie aenderbar ist.
        "--add-data", f"{DATEN}{os.pathsep}daten",
        str(WURZEL / "verteilerly" / "__main__.py"),
    ]
    for modul in UNNOETIG:
        befehl += ["--exclude-module", modul]
    return befehl


def probelauf(programm: pathlib.Path) -> dict[str, str]:
    """Startet die fertige Datei einmal und liest ihren Selbstbericht.

    Die .exe hat keine Konsole - der Bericht kommt deshalb als Datei.
    """
    bericht = BAUORDNER / "selbsttest.txt"
    bericht.unlink(missing_ok=True)
    subprocess.run([str(programm), "--selbsttest", str(bericht)], check=False)
    if not bericht.exists():
        return {}
    werte = {}
    for zeile in bericht.read_text(encoding="utf-8").splitlines():
        if "=" in zeile:
            schluessel, wert = zeile.split("=", 1)
            werte[schluessel] = wert
    return werte


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--zeigen", action="store_true",
                          help="nur den PyInstaller-Aufruf ausgeben")
    zerleger.add_argument("--behalten", action="store_true",
                          help="Bauordner nach dem Bauen stehen lassen")
    zerleger.add_argument("--ohne-probelauf", action="store_true")
    argumente = zerleger.parse_args()

    voraussetzungen_pruefen(streng=not argumente.zeigen)
    symbol = symbol_schreiben(BAUORDNER)
    versionsdatei = versionsdatei_schreiben(BAUORDNER)
    befehl = befehl_bauen(symbol, versionsdatei)

    if argumente.zeigen:
        print(" ".join(befehl))
        return 0

    melden(f"baue {NAME} {VERSION} (dauert)")
    subprocess.run(befehl, check=True)

    programm = ZIELORDNER / f"{NAME}.exe"
    if not programm.exists():                     # pragma: no cover
        raise SystemExit(f"PyInstaller hat {programm} nicht angelegt")
    melden(f"fertig: {programm} ({programm.stat().st_size / 1024 / 1024:.0f} MB)")

    # Es soll wirklich nur eine Datei sein - PyInstaller legt sonst nichts
    # daneben, aber ein alter Bau koennte noch herumliegen.
    daneben = [d.name for d in ZIELORDNER.iterdir() if d.name != programm.name]
    if daneben:
        melden(f"daneben liegt noch: {', '.join(sorted(daneben))}")

    if not argumente.ohne_probelauf:
        werte = probelauf(programm)
        if not werte:
            print("Probelauf hat keinen Bericht geschrieben.", file=sys.stderr)
            return 1
        for schluessel in ("version", "python", "qt", "arbeitsordner",
                           "vorlagen", "blattvorlagen", "kabeltypen", "ergebnis"):
            if schluessel in werte:
                melden(f"  {schluessel}: {werte[schluessel]}")
        if werte.get("ergebnis") != "ok":
            return 1

    if not argumente.behalten:
        shutil.rmtree(BAUORDNER / "arbeit", ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
