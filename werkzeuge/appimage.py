#!/usr/bin/env python3
"""Verteilerly als AppImage bauen, das alles selbst mitbringt.

Grundlage ist eine fertige Python-AppImage von python-appimage: ein auf
manylinux2014 gebautes Python, also gegen glibc 2.17 gelinkt. Da hinein
kommen die Bibliotheken aus requirements.txt, das Programm selbst und die
Systembibliotheken, die Qt braucht und die nicht auf jedem Rechner liegen.

Wie alt das Zielsystem sein darf, sagt der Bau am Ende: die Untergrenze
setzen das Qt-Rad und die mitgenommenen Bibliotheken des Baurechners, nicht
das Python. Wer aeltere Systeme bedienen will, baut auf einer aelteren
Verteilung.

    python3 werkzeuge/appimage.py               laedt, baut, prueft
    python3 werkzeuge/appimage.py --behalten    AppDir stehen lassen
    python3 werkzeuge/appimage.py --basis DATEI  eigene Python-AppImage

Ergebnis ist eine einzelne Datei in auslieferung/. Python, Qt, ReportLab,
openpyxl und PyYAML stecken darin; vom Zielrechner erwartet das Programm
nur die X11-Grundausstattung, die jede Arbeitsumgebung mitbringt.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from verteilerly.version import VERSION  # noqa: E402

import lizenztexte  # noqa: E402

NAME = "verteilerly"
ANZEIGENAME = "Verteilerly"
# Der Dateityp der Projektdatei - dasselbe Wort wie in verknuepfung.py,
# das sich im Programm selbst bei der Dateiverwaltung anmeldet.
MIMETYP = "application/x-verteilerly-projekt"
PYTHONFASSUNG = "3.14"
BASIS_URL = (
    "https://github.com/niess/python-appimage/releases/download/python3.14/"
    "python3.14.8-cp314-cp314-manylinux2014_x86_64.AppImage"
)
WERKZEUG_URL = (
    "https://github.com/AppImage/appimagetool/releases/download/continuous/"
    "appimagetool-x86_64.AppImage"
)

# Die mitgenommenen Systembibliotheken kommen nicht vom Baurechner,
# sondern aus einer aelteren Verteilung: sonst verlangte das fertige
# AppImage die glibc des Rechners, auf dem gebaut wurde.
DEBIAN = "bookworm"          # Debian 12, glibc 2.36
DEBIAN_SPIEGEL = "https://deb.debian.org/debian/"
DEBIAN_INDEX = (
    f"{DEBIAN_SPIEGEL}dists/{DEBIAN}/main/binary-amd64/Packages.gz"
)
# Welche Bibliothek in welchem Debian-Paket steckt.
DEBIAN_PAKETE = {
    "libX11-xcb.so.1": "libx11-xcb1",
    "libXau.so.6": "libxau6",
    "libXcursor.so.1": "libxcursor1",
    "libXdmcp.so.6": "libxdmcp6",
    "libXext.so.6": "libxext6",
    "libXfixes.so.3": "libxfixes3",
    "libXi.so.6": "libxi6",
    "libXrandr.so.2": "libxrandr2",
    "libatomic.so.1": "libatomic1",
    "libb2.so.1": "libb2-1",
    "libbrotlicommon.so.1": "libbrotli1",
    "libbrotlidec.so.1": "libbrotli1",
    "libbz2.so.1.0": "libbz2-1.0",
    "libdouble-conversion.so.3": "libdouble-conversion3",
    "libgraphite2.so.3": "libgraphite2-3",
    "libgthread-2.0.so.0": "libglib2.0-0",
    "libmd4c.so.0": "libmd4c0",
    "libpcre2-16.so.0": "libpcre2-16-0",
    "libpcre2-8.so.0": "libpcre2-8-0",
    "libpng16.so.16": "libpng16-16",
    "libxcb-cursor.so.0": "libxcb-cursor0",
    "libxcb-glx.so.0": "libxcb-glx0",
    "libxcb-icccm.so.4": "libxcb-icccm4",
    "libxcb-image.so.0": "libxcb-image0",
    "libxcb-keysyms.so.1": "libxcb-keysyms1",
    "libxcb-randr.so.0": "libxcb-randr0",
    "libxcb-render-util.so.0": "libxcb-render-util0",
    "libxcb-render.so.0": "libxcb-render0",
    "libxcb-shape.so.0": "libxcb-shape0",
    "libxcb-shm.so.0": "libxcb-shm0",
    "libxcb-sync.so.1": "libxcb-sync1",
    "libxcb-util.so.1": "libxcb-util1",
    "libxcb-xfixes.so.0": "libxcb-xfixes0",
    "libxcb-xkb.so.1": "libxcb-xkb1",
    "libxkbcommon-x11.so.0": "libxkbcommon-x11-0",
    "libxkbcommon.so.0": "libxkbcommon0",
    "libzstd.so.1": "libzstd1",
}

BAUORDNER = WURZEL / "bau"
BASISORDNER = BAUORDNER / "basis"
DEBIANORDNER = BASISORDNER / DEBIAN
APPDIR = BAUORDNER / f"{ANZEIGENAME}.AppDir"
ZIELORDNER = WURZEL / "auslieferung"
DATEN = WURZEL / "daten"
LIZENZEN = WURZEL / "lizenzen"

# Qt-Module, die die Oberflaeche braucht. Alles andere fliegt raus - der
# Rest von Qt ist ein Vielfaches des Programms gross.
# OpenGL steht bewusst nicht dabei: nachgesehen mit readelf verweist auf
# libQt6OpenGL nur seine eigene Bindung und das glx-Steckmodul, sonst
# niemand. Gezeichnet wird mit QPainter.
QT_BEHALTEN = {"Core", "Gui", "Widgets", "DBus", "XcbQpa", "Svg"}
# Steckmodule, die die Oberflaeche laedt. Der Rest zieht Fremdes nach:
# das GTK-Thema die halbe GTK-Welt, das Drucksteckmodul CUPS - und
# gedruckt wird hier ohnehin über das PDF.
# imageformats fehlt mit Absicht: das Programm liest keine Bilddateien,
# sein Symbol zeichnet es selbst (gui/symbol.py).
PLUGINS_BEHALTEN = {
    "platforms", "iconengines", "platforminputcontexts", "styles",
}
PLATTFORMEN_BEHALTEN = {"libqxcb", "libqminimal", "libqoffscreen"}
# Von Qts Uebersetzungen bleibt die deutsche - sie beschriftet die
# Datei- und Rueckfragedialoge. Der Rest waere Ballast.
UEBERSETZUNGEN_BEHALTEN = {"qtbase_de.qm"}
# Qts Entwicklerwerkzeuge liegen in der PySide6-Auslieferung mit. Sie
# gehoeren an den Arbeitsplatz des Entwicklers, nicht in ein fertiges
# Programm - aufgerufen werden sie dort nie.
QT_WERKZEUGE = (
    "assistant", "designer", "linguist", "lrelease", "lupdate",
    "qmlformat", "qmllint", "qmlls", "svgtoqml", "qmltyperegistrar",
    "qmlimportscanner", "qmlcachegen", "rcc", "uic", "balsam",
    "qsb", "shiboken6", "pyside6-*",
)
# Pillow kommt mit ReportLab mit und bringt Bildcodecs fuer Formate mit,
# die hier niemand oeffnet - gezeichnet wird mit ReportLab, nicht mit
# Pillow. Der Kern (_imaging samt libjpeg, libtiff, libopenjp2, zlib)
# bleibt: ohne ihn laesst sich reportlab nicht einmal importieren.
PILLOW_WEG = (
    "PIL/_avif.*.so", "PIL/_webp.*.so", "PIL/_imagingtk.*.so",
    "PIL/_imagingft.*.so", "PIL/_imagingcms.*.so",
    "pillow.libs/libavif-*.so*", "pillow.libs/libwebp*-*.so*",
    "pillow.libs/libsharpyuv-*.so*", "pillow.libs/libfreetype-*.so*",
    "pillow.libs/libharfbuzz-*.so*", "pillow.libs/liblcms2-*.so*",
    "pillow.libs/libbrotli*-*.so*",
)

# Ordner in der PySide6-Auslieferung, die die Oberflaeche nicht anfasst.
PYSIDE_WEG = (
    "Qt/qml",
    "Qt/resources",
    "Qt/libexec",
    "Qt/plugins/multimedia",
    "Qt/plugins/webview",
    "Qt/plugins/position",
    "Qt/plugins/sqldrivers",
    "Qt/plugins/renderers",
    "Qt/plugins/geometryloaders",
    "examples",
    "glue",
    "typesystems",
    "include",
    "scripts",
    "support",
)

# Was ein AppImage nie mitbringen darf, weil es zum Kern des Zielsystems
# gehoert. Gekuerzte Fassung der Liste von AppImage/pkg2appimage.
NIE_MITNEHMEN = {
    "ld-linux-x86-64.so.2", "libc.so.6", "libm.so.6", "libdl.so.2",
    "libpthread.so.0", "librt.so.1", "libresolv.so.2", "libutil.so.1",
    "libstdc++.so.6", "libgcc_s.so.1", "libGL.so.1", "libGLX.so.0",
    "libEGL.so.1", "libGLdispatch.so.0", "libOpenGL.so.0", "libdrm.so.2",
    "libglapi.so.0", "libX11.so.6", "libxcb.so.1", "libXext.so.6",
    "libgio-2.0.so.0", "libglib-2.0.so.0", "libgobject-2.0.so.0",
    "libgmodule-2.0.so.0", "libfontconfig.so.1", "libfreetype.so.6",
    "libharfbuzz.so.0", "libz.so.1", "libselinux.so.1", "libexpat.so.1",
    "libp11-kit.so.0", "libgcrypt.so.20", "libsystemd.so.0", "libdbus-1.so.3",
}


def melden(text: str) -> None:
    print(f"· {text}", flush=True)


WARTEZEIT = 30.0          # Sekunden je Versuch
VERSUCHE = 3


def holen(url: str, ziel: pathlib.Path) -> pathlib.Path:
    """Laedt eine Datei, wenn sie noch nicht daliegt.

    Mit Wartezeit und zweitem Anlauf: ein haengender Spiegel hielt den
    Bau sonst endlos auf, ohne ein Wort zu sagen. Eine halb geladene
    Datei wird weggeraeumt - sonst gaelte sie beim naechsten Mal als
    "schon vorhanden".
    """
    ziel.parent.mkdir(parents=True, exist_ok=True)
    if ziel.exists() and ziel.stat().st_size > 0:
        melden(f"schon vorhanden: {ziel.name}")
        return ziel
    melden(f"lade {url.rsplit('/', 1)[-1]} …")
    for versuch in range(1, VERSUCHE + 1):
        try:
            with urllib.request.urlopen(url, timeout=WARTEZEIT) as quelle:
                with ziel.open("wb") as datei:
                    shutil.copyfileobj(quelle, datei)
            break
        except (urllib.error.URLError, TimeoutError, OSError) as fehler:
            ziel.unlink(missing_ok=True)
            if versuch == VERSUCHE:
                raise SystemExit(
                    f"{ziel.name} liess sich nicht laden ({fehler}). "
                    "Spiegel nicht erreichbar?"
                ) from None
            melden(f"  Versuch {versuch} fehlgeschlagen ({fehler}) - noch einmal")
    ziel.chmod(0o755)
    return ziel


def basis_auspacken(basis: pathlib.Path) -> pathlib.Path:
    """Entpackt die Python-AppImage zum AppDir."""
    if APPDIR.exists():
        shutil.rmtree(APPDIR)
    arbeit = BAUORDNER / "auspacken"
    shutil.rmtree(arbeit, ignore_errors=True)
    arbeit.mkdir(parents=True)

    melden(f"packe {basis.name} aus")
    subprocess.run([str(basis), "--appimage-extract"], cwd=arbeit, check=True,
                   stdout=subprocess.DEVNULL)
    (arbeit / "squashfs-root").rename(APPDIR)
    shutil.rmtree(arbeit, ignore_errors=True)
    return APPDIR


def _python() -> pathlib.Path:
    return APPDIR / "opt" / f"python{PYTHONFASSUNG}" / "bin" / f"python{PYTHONFASSUNG}"


def _site_packages() -> pathlib.Path:
    return (
        APPDIR / "opt" / f"python{PYTHONFASSUNG}" / "lib"
        / f"python{PYTHONFASSUNG}" / "site-packages"
    )


def abhaengigkeiten_einbauen() -> None:
    """PySide6, ReportLab, openpyxl und PyYAML in das AppDir installieren."""
    melden("installiere die Bibliotheken in das AppDir (dauert)")
    subprocess.run(
        [str(_python()), "-m", "pip", "install", "--no-warn-script-location",
         "--disable-pip-version-check", "--upgrade",
         "PySide6-Essentials", "reportlab", "openpyxl", "PyYAML"],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def programm_einbauen() -> None:
    """Das Paket selbst und die Daten daneben."""
    ziel = _site_packages() / "verteilerly"
    shutil.rmtree(ziel, ignore_errors=True)
    shutil.copytree(
        WURZEL / "verteilerly", ziel,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    datenziel = APPDIR / DATEN.name
    shutil.rmtree(datenziel, ignore_errors=True)
    shutil.copytree(DATEN, datenziel)

    # Wer ein Abbild weitergibt, gibt die Lizenzen mit: die GPL fuer das
    # Programm, die LGPL fuer Qt, und QUELLEN.txt sagt, wo der Quelltext
    # jedes Bestandteils zu holen ist.
    lizenzziel = APPDIR / LIZENZEN.name
    shutil.rmtree(lizenzziel, ignore_errors=True)
    shutil.copytree(LIZENZEN, lizenzziel)
    # Die GPL liegt im Quellbaum als LICENSE, wo sie jedes Werkzeug sucht;
    # im Abbild heisst sie wie die uebrigen Lizenztexte.
    shutil.copy2(WURZEL / "LICENSE", lizenzziel / "GPL-3.0.txt")
    # Die Lizenzen der Pakete liegen in ihren dist-info-Ordnern, die im
    # Einhaengepunkt stecken - ausgelegt wird nur lizenzen/.
    for name, quelle in lizenztexte.pakettexte([_site_packages()]):
        shutil.copy2(quelle, lizenzziel / name)
    python = lizenztexte.python_lizenz([_site_packages().parent / "LICENSE.txt"])
    if python:
        shutil.copy2(python, lizenzziel / "Python-LICENSE.txt")
    melden(
        f"Programm, Daten und Lizenzen eingebaut "
        f"({ziel.name}, {datenziel.name}, {lizenzziel.name})"
    )


# Module der Standardbibliothek, die ein fertiges Programm nie aufruft -
# und dazu die Bibliotheken, an denen sie haengen. readline und gdbm
# stehen unter der GPL-3: sie hier zu lassen hiesse, ihren Quelltext
# mit anbieten zu muessen, und das Programm ruft sie nie auf. Tcl/Tk
# geht mit tkinter denselben Weg, nur aus Platzgruenden. _sqlite3
# braucht hier niemand: ein Verteiler ist eine Datei, keine Datenbank.
#
# **_ssl und _hashlib bleiben drin** (mit libssl und libcrypto, rund
# 7 MB roh): seit 2026.10.12 sieht das Programm einmal am Tag nach, ob
# es eine neuere Fassung gibt, und das geht nur ueber HTTPS. OpenSSL
# steht unter der Apache-2.0 - vertraeglich mit der GPL-3 -, der Text
# liegt als OpenSSL.txt bei. Zertifikate bringt es keine mit: die holt
# `aktualisierung.zertifikatsspeicher()` vom Rechner.
UNNOETIGE_MODULE = ("_gdbm", "_dbm", "readline", "_tkinter",
                    "_sqlite3", "_curses", "_curses_panel")
UNNOETIGE_BIBLIOTHEKEN = ("libgdbm", "libgdbm_compat", "libreadline",
                          "libtcl", "libtk",
                          "libsqlite3", "libncursesw", "libpanelw", "libtinfo",
                          "libXft", "libXrender")
# Was die Python-AppImage selbst mitbringt und das Programm nie aufruft:
# pip samt seinen Bauwerkzeugen, certifi (MPL-2.0) fuer Netzzugriffe, die
# es nicht gibt, und der Haken, der pip-Installationen umbiegt. Was nicht
# mitkommt, braucht auch keinen Lizenzhinweis.
BASIS_WEG = ("pip", "setuptools", "wheel", "pkg_resources", "build",
             "certifi", "packaging", "pyproject_hooks", "sitecustomize")
# ReportLab bringt Schriften mit - DarkGarden unter der GPL-2, Bitstream
# Vera und Type-1-Nachbildungen der Standardschriften. Das Programm setzt
# nur die vierzehn Standardschriften, die jeder PDF-Betrachter selbst hat:
# eingebettet und gelesen wird davon nichts. Die .exe kommt ohnehin ohne.
REPORTLAB_WEG = ("reportlab/fonts",)


def python_abspecken() -> None:
    """Was in einem fertigen Programm niemand aufruft."""
    opt = APPDIR / "opt" / f"python{PYTHONFASSUNG}"
    stdlib = opt / "lib" / f"python{PYTHONFASSUNG}"
    for teil in ("test", "idlelib", "tkinter", "ensurepip", "lib2to3",
                 "distutils", "turtledemo", "config-*"):
        for ordner in stdlib.glob(teil):
            shutil.rmtree(ordner, ignore_errors=True) if ordner.is_dir() else ordner.unlink()

    for name in UNNOETIGE_MODULE:
        for datei in (stdlib / "lib-dynload").glob(f"{name}.*.so"):
            datei.unlink()
    for name in UNNOETIGE_BIBLIOTHEKEN:
        for ordner in (APPDIR / "usr" / "lib", opt / "lib"):
            # "libtcl8.6.so" traegt die Fassung im Namen, "libgdbm.so.4"
            # dahinter - das Muster muss beides fangen.
            for datei in ordner.glob(f"{name}*.so*") if ordner.is_dir() else ():
                datei.unlink()

    # Tcl/Tk ist mit tkinter draussen; seine Skripte lagen noch daneben.
    shutil.rmtree(APPDIR / "usr" / "share" / "tcltk", ignore_errors=True)
    for teil in REPORTLAB_WEG:
        shutil.rmtree(_site_packages() / teil, ignore_errors=True)

    for ordner in APPDIR.rglob("__pycache__"):
        shutil.rmtree(ordner, ignore_errors=True)


def qt_abspecken() -> int:
    """Wirft heraus, was die Oberflaeche nicht anfasst."""
    pyside = _site_packages() / "PySide6"
    if not pyside.is_dir():
        return 0
    vorher = _groesse(APPDIR)

    for teil in PYSIDE_WEG:
        shutil.rmtree(pyside / teil, ignore_errors=True)

    uebersetzungen = pyside / "Qt" / "translations"
    for datei in list(uebersetzungen.glob("*")):
        if datei.name not in UEBERSETZUNGEN_BEHALTEN:
            shutil.rmtree(datei, ignore_errors=True) if datei.is_dir() else datei.unlink()

    for datei in list((pyside / "Qt" / "lib").glob("libQt6*.so*")):
        modul = datei.name.split(".")[0].removeprefix("libQt6")
        if modul not in QT_BEHALTEN:
            datei.unlink()
    for datei in list(pyside.glob("Qt*.abi3.so")):
        if datei.name.removeprefix("Qt").removesuffix(".abi3.so") not in QT_BEHALTEN:
            datei.unlink()
    for datei in list(pyside.glob("Qt*.pyi")) + list(pyside.glob("*.debug")):
        datei.unlink()

    # pip und Konsorten braucht das fertige Programm nicht mehr.
    for name in BASIS_WEG:
        for ordner in _site_packages().glob(f"{name}*"):
            shutil.rmtree(ordner, ignore_errors=True) if ordner.is_dir() else ordner.unlink()

    gespart = vorher - _groesse(APPDIR)
    melden(f"abgespeckt: {gespart / 1024 / 1024:.0f} MB")
    return gespart


def werkzeuge_entfernen() -> int:
    """Qts Entwicklerwerkzeuge aus der PySide6-Auslieferung."""
    pyside = _site_packages() / "PySide6"
    if not pyside.is_dir():
        return 0
    weg = 0
    for muster in QT_WERKZEUGE:
        for datei in pyside.glob(muster):
            if datei.is_file():
                weg += datei.stat().st_size
                datei.unlink()
            elif datei.is_dir():
                weg += _groesse(datei)
                shutil.rmtree(datei, ignore_errors=True)
    return weg


def bildcodecs_entfernen() -> int:
    """Pillows Codecs fuer Formate, die hier niemand oeffnet."""
    pakete = _site_packages()
    weg = 0
    for muster in PILLOW_WEG:
        for datei in pakete.glob(muster):
            weg += datei.stat().st_size
            datei.unlink()
    return weg


def symbole_strippen() -> int:
    """Nimmt den Bibliotheken ihre Symboltabellen.

    Qt liefert schon gestrippt aus, die Raeder von Pillow und PyYAML
    nicht: dort steckt ein Vielfaches der eigentlichen Bibliothek in
    Symbolen, die zur Laufzeit niemand liest. Fehlt ``strip``, wird das
    gesagt und weitergebaut - ein Abbild muss sich auch ohne binutils
    bauen lassen.
    """
    werkzeug = shutil.which("strip")
    if werkzeug is None:
        melden("strip nicht vorhanden - Symboltabellen bleiben drin")
        return 0
    vorher = _groesse(APPDIR)
    dateien = [
        str(datei)
        for datei in APPDIR.rglob("*.so*")
        if datei.is_file() and not datei.is_symlink()
    ]
    for anfang in range(0, len(dateien), 200):      # nicht eine Zeile je Datei
        subprocess.run(
            [werkzeug, "--strip-unneeded", *dateien[anfang:anfang + 200]],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
    return vorher - _groesse(APPDIR)


def plugins_abspecken() -> None:
    """Wirft die Steckmodule heraus, die das Programm nie laedt."""
    plugins = _site_packages() / "PySide6" / "Qt" / "plugins"
    if not plugins.is_dir():
        return
    for ordner in plugins.iterdir():
        if ordner.is_dir() and ordner.name not in PLUGINS_BEHALTEN:
            shutil.rmtree(ordner, ignore_errors=True)
    for datei in (plugins / "platforms").glob("*.so"):
        if datei.stem not in PLATTFORMEN_BEHALTEN:
            datei.unlink()


def verwaiste_entfernen() -> list[str]:
    """Loescht, was auf ein herausgeworfenes Qt-Modul zeigt.

    Sonst holte ldd das fehlende Modul spaeter vom Rechner, auf dem
    gebaut wird - und im AppImage steckte fremdes Qt.
    """
    pyside = _site_packages() / "PySide6"
    entfernt: list[str] = []
    while True:
        offen = []
        for datei in list((pyside / "Qt" / "plugins").rglob("*.so")) + list(
            (pyside / "Qt" / "lib").glob("libQt6*.so*")
        ):
            fehlend = [n for n, ort in _ldd(datei) if ort is None and n.startswith("libQt6")]
            if fehlend:
                offen.append(datei)
        if not offen:
            return entfernt
        for datei in offen:
            datei.unlink(missing_ok=True)
            entfernt.append(datei.name)


def systembibliotheken_mitnehmen() -> list[str]:
    """Nimmt die Bibliotheken mit, die Qt braucht und die oft fehlen.

    Der Kern des Zielsystems bleibt draussen (glibc, libGL, X11) - den
    bringt jede Arbeitsumgebung mit, und eine mitgelieferte Fassung
    wuerde sich mit dem Treiber des Rechners beissen.

    Geholt wird aus Debian und nicht vom Baurechner: eine Bibliothek
    dieses Rechners verlangte die glibc dieses Rechners und schnitte
    damit alles Aeltere ab.
    """
    lib = APPDIR / "usr" / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    pyside = _site_packages() / "PySide6"
    kandidaten = list((pyside / "Qt" / "lib").glob("libQt6*.so*"))
    kandidaten += list((pyside / "Qt" / "plugins").rglob("*.so"))

    gebraucht: dict[str, pathlib.Path] = {}
    for datei in kandidaten:
        for name, ort in _ldd(datei):
            if name in NIE_MITNEHMEN or not ort:
                continue
            if (lib / name).exists() or (pyside / "Qt" / "lib" / name).exists():
                continue
            if str(ort).startswith(str(APPDIR)):
                continue
            gebraucht.setdefault(name, ort)

    aus_debian, vom_rechner = [], []
    for name, ort in sorted(gebraucht.items()):
        fremd = _aus_debian(name)
        if fremd:
            shutil.copy2(fremd, lib / name)
            aus_debian.append(name)
        else:
            shutil.copy2(ort, lib / name)
            vom_rechner.append(name)

    for name in aus_debian:
        _copyright_mitnehmen(DEBIAN_PAKETE[name])
    if aus_debian:
        melden(f"aus Debian {DEBIAN}: {', '.join(aus_debian)}")
    if vom_rechner:
        melden(f"vom Baurechner (setzt die glibc-Untergrenze): "
               f"{', '.join(vom_rechner)}")
    return sorted(gebraucht)


def _copyright_mitnehmen(paket: str) -> None:
    """Legt die Copyright-Datei eines Debian-Pakets zu den Lizenzen.

    Die X11-, xcb- und Kompressionsbibliotheken stehen unter MIT- und
    BSD-artigen Lizenzen, die ihren Hinweis bei jeder Weitergabe
    verlangen. Wo Debian das Verzeichnis nur verlinkt (libatomic1 auf
    gcc-12-base), gelten GPL-3.0.txt und GCC-Laufzeitausnahme-3.1.txt.
    """
    for datei in (DEBIANORDNER / paket).glob("usr/share/doc/*/copyright"):
        if datei.is_file():
            shutil.copy2(datei, APPDIR / LIZENZEN.name / f"Debian-{paket}.txt")
            return


def _debian_index() -> dict[str, str]:
    """Paketname zum Ort im Debian-Archiv."""
    import gzip

    datei = holen(DEBIAN_INDEX, DEBIANORDNER / "Packages.gz")
    gesucht = set(DEBIAN_PAKETE.values())
    orte: dict[str, str] = {}
    paket = ""
    with gzip.open(datei, "rt", encoding="utf-8", errors="replace") as index:
        for zeile in index:
            if zeile.startswith("Package: "):
                paket = zeile[9:].strip()
            elif zeile.startswith("Filename: ") and paket in gesucht:
                orte[paket] = zeile[10:].strip()
    return orte


_INDEX: dict[str, str] | None = None


def _aus_debian(name: str) -> pathlib.Path | None:
    """Holt eine Bibliothek aus dem Debian-Paket und gibt die Datei zurueck."""
    global _INDEX

    paket = DEBIAN_PAKETE.get(name)
    if not paket:
        return None
    ausgepackt = DEBIANORDNER / paket
    treffer = _bibliothek_finden(ausgepackt, name)
    if treffer:
        return treffer

    if _INDEX is None:
        _INDEX = _debian_index()
    ort = _INDEX.get(paket)
    if not ort:
        return None

    deb = holen(DEBIAN_SPIEGEL + ort, DEBIANORDNER / ort.rsplit("/", 1)[-1])
    ausgepackt.mkdir(parents=True, exist_ok=True)
    subprocess.run(["dpkg-deb", "-x", str(deb), str(ausgepackt)], check=True)
    return _bibliothek_finden(ausgepackt, name)


def _bibliothek_finden(ordner: pathlib.Path, name: str) -> pathlib.Path | None:
    """Die echte Datei hinter dem Namen - Debian legt Verweise an."""
    if not ordner.is_dir():
        return None
    for datei in ordner.rglob(name):
        return datei.resolve()
    return None


def _ldd(datei: pathlib.Path) -> list[tuple[str, pathlib.Path | None]]:
    """Abhaengigkeiten einer Datei, zuerst im AppDir gesucht."""
    innen = os.pathsep.join(
        str(o) for o in (
            _site_packages() / "PySide6" / "Qt" / "lib",
            APPDIR / "usr" / "lib",
            datei.parent,
        )
    )
    ergebnis = subprocess.run(
        ["ldd", str(datei)], capture_output=True, text=True,
        env=dict(os.environ, LD_LIBRARY_PATH=innen),
    )
    gefunden = []
    for zeile in ergebnis.stdout.splitlines():
        teile = zeile.split(" => ")
        if len(teile) != 2:
            continue
        name = teile[0].strip()
        ort = teile[1].split(" (")[0].strip()
        gefunden.append((name, pathlib.Path(ort) if ort.startswith("/") else None))
    return gefunden


def glibc_bedarf() -> tuple[str, list[str]]:
    """Hoechste glibc-Fassung, die das fertige AppDir verlangt, und woher.

    Der Wert entscheidet, wie alt das Zielsystem sein darf. Gesetzt wird
    er von den mitgenommenen Systembibliotheken - wer aeltere Systeme
    bedienen will, baut auf einer aelteren Verteilung.
    """
    hoechste = (2, 0)
    schuldige: list[str] = []
    for datei in list(APPDIR.rglob("*.so")) + list(APPDIR.rglob("*.so.*")):
        ergebnis = subprocess.run(
            ["objdump", "-T", str(datei)], capture_output=True, text=True
        )
        bedarf = (2, 0)
        for zeile in ergebnis.stdout.splitlines():
            if "GLIBC_2." not in zeile:
                continue
            teil = zeile.split("GLIBC_2.")[1].split(")")[0].split()[0].strip()
            try:
                bedarf = max(bedarf, (2, int(teil.split(".")[0])))
            except ValueError:
                continue
        if bedarf > hoechste:
            hoechste, schuldige = bedarf, [datei.name]
        elif bedarf == hoechste and datei.name not in schuldige:
            schuldige.append(datei.name)
    return f"{hoechste[0]}.{hoechste[1]}", sorted(schuldige)


def _groesse(ordner: pathlib.Path) -> int:
    return sum(d.stat().st_size for d in ordner.rglob("*") if d.is_file())


def huelle_schreiben() -> None:
    """AppRun, Desktop-Eintrag und Symbol - die Vorgaben von Python raus."""
    for muster in ("python*.desktop", "python*.png", "*.desktop", "*.png", ".DirIcon"):
        for datei in APPDIR.glob(muster):
            datei.unlink()
    shutil.rmtree(APPDIR / "usr" / "share" / "applications", ignore_errors=True)
    shutil.rmtree(APPDIR / "usr" / "share" / "icons", ignore_errors=True)

    apprun = APPDIR / "AppRun"
    # In der Python-AppImage ist AppRun ein Verweis auf usr/bin/python -
    # ohne Loeschen schriebe man den Python-Aufruf selbst kaputt.
    apprun.unlink(missing_ok=True)
    apprun.write_text(
        "#!/bin/sh\n"
        "# Verteilerly bringt Python und Qt selbst mit.\n"
        'HIER="$(dirname "$(readlink -f "$0")")"\n'
        'export APPDIR="${APPDIR:-$HIER}"\n'
        f'export PYTHONHOME="$HIER/opt/python{PYTHONFASSUNG}"\n'
        'export PYTHONNOUSERSITE=1\n'
        'export LD_LIBRARY_PATH="$HIER/usr/lib:$LD_LIBRARY_PATH"\n'
        f'PYTHON="$HIER/opt/python{PYTHONFASSUNG}/bin/python{PYTHONFASSUNG}"\n'
        '# Erste Hilfe bei Fragen: --python startet den eingebauten Python.\n'
        'if [ "$1" = "--python" ]; then shift; exec "$PYTHON" "$@"; fi\n'
        'exec "$PYTHON" -m verteilerly "$@"\n',
        encoding="utf-8",
    )
    apprun.chmod(0o755)

    symbol_schreiben(APPDIR / f"{NAME}.png")
    shutil.copy2(APPDIR / f"{NAME}.png", APPDIR / ".DirIcon")
    # %f und MimeType: wer das Abbild in seine Arbeitsflaeche einhaengt,
    # kann damit eine Projektdatei per Doppelklick oeffnen. Angemeldet
    # wird der Typ im Programm selbst (Tools), hier steht nur, dass es
    # ihn oeffnen kann.
    (APPDIR / f"{NAME}.desktop").write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={ANZEIGENAME}\n"
        "Comment=Dokumentation für LSA+-Verteiler\n"
        f"Exec={NAME} %f\n"
        f"Icon={NAME}\n"
        "Categories=Office;Engineering;\n"
        f"MimeType={MIMETYP};\n"
        "Terminal=false\n",
        encoding="utf-8",
    )
    melden("AppRun, Desktop-Eintrag und Symbol geschrieben")


def symbol_schreiben(ziel: pathlib.Path) -> pathlib.Path:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from verteilerly.gui.symbol import symbol

    QApplication.instance() or QApplication([])
    symbol(256).save(str(ziel))
    return ziel


def appimage_bauen(werkzeug: pathlib.Path) -> pathlib.Path:
    ZIELORDNER.mkdir(parents=True, exist_ok=True)
    ziel = ZIELORDNER / f"{ANZEIGENAME}-{VERSION}-x86_64.AppImage"
    ziel.unlink(missing_ok=True)
    melden("packe das AppImage")
    subprocess.run(
        [str(werkzeug), "--appimage-extract-and-run", str(APPDIR), str(ziel)],
        check=True,
        env=dict(os.environ, ARCH=os.uname().machine, VERSION=VERSION),
    )
    ziel.chmod(0o755)
    return ziel


def probelauf(programm: pathlib.Path) -> bool:
    """Startet das fertige AppImage ohne Bildschirm und laesst es arbeiten.

    Gearbeitet wird in einem leeren Ordner, damit nicht versehentlich der
    Quellbaum geprueft wird: aus dem Arbeitsverzeichnis heraus faende
    Python sonst das Paket daneben statt das eingebaute.
    """
    pruefung = (
        "import ctypes, pathlib, tempfile, sys, verteilerly;"
        # Die mitgenommenen Bibliotheken muessen sich mit der glibc des
        # Rechners vertragen, auf dem gestartet wird.
        "[ctypes.CDLL(n) for n in "
        "('libxcb-cursor.so.0','libxkbcommon-x11.so.0','libxcb-icccm.so.4')];"
        "from verteilerly.ausgabe import pdf_schreiben;"
        "from verteilerly.modell import Projekt, Verteiler;"
        "from verteilerly.pfade import datenordner, vorlagenordner_alle;"
        "from verteilerly.vorlagen import Vorlagen;"
        "from verteilerly.gui.hauptfenster import Hauptfenster;"
        "from PySide6.QtWidgets import QApplication;"
        "a=QApplication([]);f=Hauptfenster();"
        # Wie das Programm selbst laden - aus allen Ordnern zusammen.
        "v=Vorlagen.aus_ordnern(reversed(vorlagenordner_alle())).standard"
        ".verteiler(name='Probe');"
        "z=pathlib.Path(tempfile.mkdtemp())/'p.pdf';"
        "pdf_schreiben(Projekt(verteiler=v), z);"
        "eingebaut = verteilerly.__file__.startswith(sys.prefix);"
        "print('PYTHON', sys.version.split()[0]);"
        "print('PAKET', verteilerly.__file__);"
        "print('DATEN', datenordner());"
        "print('PDF', z.stat().st_size);"
        "sys.exit(0 if eingebaut else 'Es wurde nicht das eingebaute Paket geladen')"
    )
    mit = tempfile.mkdtemp(prefix="verteilerly-probe-")
    umgebung = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    umgebung.pop("PYTHONPATH", None)
    ergebnis = subprocess.run(
        [str(programm), "--python", "-c", pruefung],
        capture_output=True, text=True, cwd=mit, env=umgebung,
    )
    shutil.rmtree(mit, ignore_errors=True)
    print(ergebnis.stdout.strip())
    if ergebnis.returncode != 0:
        print(ergebnis.stderr.strip(), file=sys.stderr)
    return ergebnis.returncode == 0


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--basis", type=pathlib.Path,
                          help="schon geladene Python-AppImage")
    zerleger.add_argument("--behalten", action="store_true",
                          help="AppDir nach dem Bauen stehen lassen")
    zerleger.add_argument("--ohne-probelauf", action="store_true")
    argumente = zerleger.parse_args()

    basis = argumente.basis or holen(
        BASIS_URL, BASISORDNER / BASIS_URL.rsplit("/", 1)[-1]
    )
    werkzeug = holen(WERKZEUG_URL, BASISORDNER / "appimagetool-x86_64.AppImage")

    basis_auspacken(basis)
    abhaengigkeiten_einbauen()
    programm_einbauen()
    qt_abspecken()
    plugins_abspecken()
    python_abspecken()
    ballast = werkzeuge_entfernen() + bildcodecs_entfernen()
    if ballast:
        melden(f"Werkzeuge und Bildcodecs heraus: {ballast // 1048576} MB")
    verwaist = verwaiste_entfernen()
    if verwaist:
        melden(f"verwaist und entfernt: {', '.join(sorted(set(verwaist)))}")
    systembibliotheken_mitnehmen()
    huelle_schreiben()

    # Zuletzt, wenn nichts mehr dazukommt: die Symboltabellen.
    gestrippt = symbole_strippen()
    if gestrippt:
        melden(f"gestrippt: {gestrippt // 1048576} MB")

    fassung, wegen = glibc_bedarf()
    melden(f"AppDir: {_groesse(APPDIR) / 1024 / 1024:.0f} MB, "
           f"verlangt glibc {fassung} oder neuer")
    melden(f"  gesetzt von: {', '.join(wegen[:6])}")
    programm = appimage_bauen(werkzeug)
    melden(f"fertig: {programm} ({programm.stat().st_size / 1024 / 1024:.0f} MB)")

    if not argumente.ohne_probelauf and not probelauf(programm):
        print("Probelauf fehlgeschlagen.", file=sys.stderr)
        return 1
    if not argumente.behalten:
        shutil.rmtree(APPDIR, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
