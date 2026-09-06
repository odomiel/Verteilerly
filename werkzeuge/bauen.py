#!/usr/bin/env python3
"""Verteilerly verpacken.

Ein Aufruf fuer beide Plattformen; der Unterschied liegt nur im Verpacken:

    python3 werkzeuge/bauen.py              fuer die laufende Plattform
    python3 werkzeuge/bauen.py --nur-exe    auch unter Linux PyInstaller
    python3 werkzeuge/bauen.py --sauber     Bau- und Zielordner leeren

Unter Windows entsteht eine einzelne .exe mit PyInstaller. Unter Linux
uebernimmt werkzeuge/appimage.py: das AppImage bringt Python und Qt selbst
mit und braucht deshalb weder PyInstaller noch ein passendes Python auf
dem Zielrechner.

Der Datenordner wird nicht nur eingeschlossen, sondern auch neben das
Programm gelegt: Vorlagen und Kabeltypen sollen ohne Auspacken zu aendern
sein.
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

from verteilerly.version import VERSION  # noqa: E402

NAME = "verteilerly"
ANZEIGENAME = "Verteilerly"
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
    "tkinter",
    "PIL",
    "numpy",
    "pytest",
)


def voraussetzungen_pruefen() -> None:
    """Bricht mit einem verwertbaren Hinweis ab, statt in PyInstaller."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        raise SystemExit(
            "PyInstaller fehlt:  pip install pyinstaller"
        ) from None

    if not sys.platform.startswith("linux"):
        return

    # PyInstaller braucht die Python-Bibliothek als .so; bei Debian und
    # Ubuntu steckt die in einem eigenen Paket.
    import sysconfig

    name = sysconfig.get_config_var("LDLIBRARY") or ""
    if not name.endswith(".so"):
        return
    orte = [
        pathlib.Path(sysconfig.get_config_var("LIBDIR") or "/usr/lib"),
        pathlib.Path("/usr/lib") / (sysconfig.get_config_var("MULTIARCH") or ""),
    ]
    fassung = f"{name}.1.0"
    if any((ort / fassung).exists() or (ort / name).exists() for ort in orte):
        return
    kurz = f"{sys.version_info.major}.{sys.version_info.minor}"
    raise SystemExit(
        f"Die Python-Bibliothek {fassung} fehlt - ohne sie kann PyInstaller "
        "nichts packen.\n"
        f"  Debian/Ubuntu:  sudo apt install libpython{kurz}"
    )


def symbol_schreiben(ordner: pathlib.Path) -> dict[str, pathlib.Path]:
    """Zeichnet das Programmsymbol als PNG und, fuer Windows, als ICO."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from verteilerly.gui.symbol import symbol

    QApplication.instance() or QApplication([])
    ordner.mkdir(parents=True, exist_ok=True)
    png = ordner / f"{NAME}.png"
    symbol(256).save(str(png))
    ico = ordner / f"{NAME}.ico"
    symbol(256).save(str(ico))
    return {"png": png, "ico": ico}


def pyinstaller_aufrufen(symbole: dict[str, pathlib.Path]) -> pathlib.Path:
    """Baut die einzelne ausfuehrbare Datei."""
    icon = symbole["ico" if sys.platform.startswith("win") else "png"]
    befehl = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", NAME,
        "--icon", str(icon),
        "--distpath", str(ZIELORDNER),
        "--workpath", str(BAUORDNER / "arbeit"),
        "--specpath", str(BAUORDNER),
        "--add-data", f"{DATEN}{os.pathsep}daten",
        str(WURZEL / "verteilerly" / "__main__.py"),
    ]
    for modul in UNNOETIG:
        befehl += ["--exclude-module", modul]

    print("PyInstaller:", " ".join(befehl[:8]), "…")
    subprocess.run(befehl, check=True)

    endung = ".exe" if sys.platform.startswith("win") else ""
    return ZIELORDNER / f"{NAME}{endung}"


def daten_danebenlegen() -> None:
    """Vorlagen und Kabeltypen bleiben lesbar neben dem Programm."""
    ziel = ZIELORDNER / DATEN.name
    if ziel.exists():
        shutil.rmtree(ziel)
    shutil.copytree(DATEN, ziel)
    print(f"Datenordner: {ziel}")


def appimage_aufrufen(argumente: list[str]) -> int:
    """Reicht an das AppImage-Skript weiter, das alles selbst mitbringt."""
    return subprocess.run(
        [sys.executable, str(WURZEL / "werkzeuge" / "appimage.py"), *argumente]
    ).returncode


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--nur-exe", action="store_true",
                          help="auch unter Linux PyInstaller statt AppImage")
    zerleger.add_argument("--sauber", action="store_true",
                          help="Bau- und Zielordner vorher leeren")
    argumente = zerleger.parse_args()

    if argumente.sauber:
        for ordner in (BAUORDNER, ZIELORDNER):
            shutil.rmtree(ordner, ignore_errors=True)

    if sys.platform.startswith("linux") and not argumente.nur_exe:
        return appimage_aufrufen([])

    voraussetzungen_pruefen()
    symbole = symbol_schreiben(BAUORDNER)
    programm = pyinstaller_aufrufen(symbole)
    daten_danebenlegen()
    groesse = programm.stat().st_size / 1024 / 1024
    print(f"Programm: {programm} ({groesse:.0f} MB)")

    print(f"\nVerteilerly {VERSION} liegt in {ZIELORDNER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
