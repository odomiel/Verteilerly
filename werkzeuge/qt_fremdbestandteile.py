"""Die Fremdbestandteile von Qt samt ihren Lizenztexten zusammenstellen.

Qt baut Code anderer Projekte in seine Bibliotheken ein - PCRE2 in Qt Core,
HarfBuzz und libjpeg in Qt Gui, unter Windows auch FreeType und zlib. Deren
Lizenzen (BSD, MIT, FTL, IJG ...) verlangen, dass ihr Hinweis die gebaute
Weitergabe begleitet. Welche es sind, steht im Quelltext von Qt in den
Dateien qt_attribution.json.

Dieses Werkzeug holt qtbase und qtsvg in der Fassung, die PySide6 mitbringt,
und schreibt lizenzen/Qt-Fremdbestandteile.txt - nur fuer die Teile, die
in Core, Gui, Widgets, DBus, Svg, den Plattform-Steckmodulen und den
mitgenommenen Bildformaten stecken. Wayland, Android, macOS, SQL, Netzwerk
und die Testbibliothek kommen nicht mit und stehen darum nicht darin.

Nach einem Wechsel der Qt-Fassung neu aufrufen:

    .venv/bin/python3 werkzeuge/qt_fremdbestandteile.py
"""

from __future__ import annotations

import json
import pathlib
import sys
import tarfile
import urllib.request

WURZEL = pathlib.Path(__file__).resolve().parent.parent
ZIEL = WURZEL / "lizenzen" / "Qt-Fremdbestandteile.txt"
ZWISCHENLAGER = WURZEL / "bau" / "qt-quelltext"
MODULE = ("qtbase", "qtsvg")

# Ordner (unterhalb des Moduls), deren qt_attribution.json zum Programm
# gehoert. Gewaehlt nach dem Feld QtUsage.
MITGENOMMEN = {
    "src/3rdparty/blake2", "src/3rdparty/double-conversion",
    "src/3rdparty/easing", "src/3rdparty/emoji-segmenter",
    "src/3rdparty/forkfd", "src/3rdparty/freetype",
    "src/3rdparty/harfbuzz-ng", "src/3rdparty/icc", "src/3rdparty/libjpeg",
    "src/3rdparty/libpng", "src/3rdparty/md4", "src/3rdparty/md4c",
    "src/3rdparty/md5", "src/3rdparty/pcre2", "src/3rdparty/rfc6234",
    "src/3rdparty/sha1", "src/3rdparty/sha3", "src/3rdparty/siphash",
    "src/3rdparty/tinycbor", "src/3rdparty/wintab", "src/3rdparty/xcb",
    "src/3rdparty/zlib", "src/3rdparty/D3D12MemoryAllocator",
    "src/3rdparty/VulkanMemoryAllocator",
    "src/corelib/global", "src/corelib/mimetypes/3rdparty",
    "src/corelib/text", "src/dbus", "src/gui/opengl", "src/gui/painting",
    "src/gui/rhi", "src/gui/text", "src/gui/vulkan", "util/gradientgen",
    "src/svg",
}

TRENNER = "-" * 72


def qt_fassung() -> str:
    from PySide6.QtCore import qVersion

    return qVersion()


def _quelle_holen(modul: str, fassung: str) -> pathlib.Path:
    haupt = ".".join(fassung.split(".")[:2])
    name = f"{modul}-everywhere-src-{fassung}.tar.xz"
    ziel = ZWISCHENLAGER / name
    if not ziel.exists():
        ZWISCHENLAGER.mkdir(parents=True, exist_ok=True)
        url = f"https://download.qt.io/official_releases/qt/{haupt}/{fassung}/submodules/{name}"
        print(f"· hole {url}", flush=True)
        with urllib.request.urlopen(url, timeout=120) as antwort:
            ziel.write_bytes(antwort.read())
    return ziel


def _texte_lesen(archiv: pathlib.Path) -> dict[str, str]:
    """Alle kleinen Textdateien, die fuer Zuordnungen in Frage kommen."""
    texte: dict[str, str] = {}
    with tarfile.open(archiv, "r|xz") as tar:
        for eintrag in tar:
            if not eintrag.isfile() or eintrag.size > 400_000:
                continue
            pfad = eintrag.name.split("/", 1)[-1]
            ordner = pfad.rsplit("/", 1)[0] if "/" in pfad else ""
            if pfad.startswith("LICENSES/") or ordner in MITGENOMMEN or any(
                ordner.startswith(m + "/") for m in MITGENOMMEN
            ):
                inhalt = tar.extractfile(eintrag)
                if inhalt is not None:
                    texte[pfad] = inhalt.read().decode("utf-8", "replace")
    return texte


def _lizenzkennungen(kennung: str) -> list[str]:
    teile = kennung.replace("(", " ").replace(")", " ").split()
    return [t for t in teile if t not in ("AND", "OR", "WITH")]


def eintraege(texte: dict[str, str]) -> tuple[list[str], set[str]]:
    """Die Abschnitte je Bestandteil und die allgemeinen Lizenztexte dazu."""
    abschnitte: list[str] = []
    allgemein: set[str] = set()
    for pfad in sorted(p for p in texte if p.endswith("qt_attribution.json")):
        ordner = pfad.rsplit("/", 1)[0]
        if ordner not in MITGENOMMEN:
            continue
        inhalt = json.loads(texte[pfad], strict=False)
        for teil in inhalt if isinstance(inhalt, list) else [inhalt]:
            kopf = [f"{teil['Name']} {teil.get('Version', '')}".rstrip()]
            kopf.append(f"Verwendung: {teil.get('QtUsage', '').strip()}")
            kopf.append(f"Lizenz: {teil.get('License', '')} ({teil.get('LicenseId', '')})")
            if teil.get("Homepage"):
                kopf.append(f"Homepage: {teil['Homepage']}")
            urheber = teil.get("Copyright", [])
            if isinstance(urheber, str):
                urheber = urheber.splitlines()
            kopf.extend(z for z in urheber if z.strip())

            eigene = teil.get("LicenseFiles") or (
                [teil["LicenseFile"]] if teil.get("LicenseFile") else []
            )
            koerper = []
            for datei in eigene:
                text = texte.get(f"{ordner}/{datei}")
                if text:
                    koerper.append(text.strip())
            # Der allgemeine Text kommt immer mit: eine eigene Lizenzdatei
            # verweist mitunter nur weiter (libjpeg-turbo auf README.ijg).
            kennungen = _lizenzkennungen(teil.get("LicenseId", ""))
            allgemein.update(kennungen)
            if not koerper:
                koerper.append("Lizenztext: " + ", ".join(kennungen)
                               + " - siehe \"Allgemeine Lizenztexte\" am Ende.")
            abschnitte.append("\n".join(kopf) + "\n\n" + "\n\n".join(koerper))
    return abschnitte, allgemein


def schreiben(fassung: str) -> pathlib.Path:
    abschnitte: list[str] = []
    allgemein: set[str] = set()
    lizenztexte: dict[str, str] = {}
    for modul in MODULE:
        texte = _texte_lesen(_quelle_holen(modul, fassung))
        teile, kennungen = eintraege(texte)
        abschnitte += teile
        allgemein |= kennungen
        for pfad, text in texte.items():
            if pfad.startswith("LICENSES/"):
                lizenztexte.setdefault(pfad.removeprefix("LICENSES/").removesuffix(".txt"), text)

    kopf = (
        f"Qt {fassung} - Fremdbestandteile\n"
        f"{'=' * (len(fassung) + 21)}\n\n"
        f"Qt-Fassung: {fassung}\n\n"
        "Qt selbst steht unter der LGPL-3.0 (LGPL-3.0.txt, GPL-3.0.txt). Die\n"
        "folgenden Bestandteile anderer Projekte sind in die mitgelieferten\n"
        "Qt-Bibliotheken eingebaut und stehen unter ihren eigenen Lizenzen.\n"
        "Zusammengestellt aus den Dateien qt_attribution.json des Quelltextes\n"
        f"(qtbase und qtsvg {fassung}) mit werkzeuge/qt_fremdbestandteile.py.\n"
    )
    anhang = [f"Allgemeine Lizenztexte\n{'=' * 22}"]
    for kennung in sorted(allgemein):
        text = lizenztexte.get(kennung)
        if text:
            anhang.append(f"{kennung}\n\n{text.strip()}")
    ZIEL.write_text(
        kopf + "\n" + "\n\n".join(f"{TRENNER}\n{a}" for a in abschnitte)
        + "\n\n" + "\n\n".join(f"{TRENNER}\n{a}" for a in anhang) + "\n",
        encoding="utf-8",
    )
    return ZIEL


def main() -> int:
    fassung = sys.argv[1] if len(sys.argv) > 1 else qt_fassung()
    ziel = schreiben(fassung)
    print(f"· geschrieben: {ziel.relative_to(WURZEL)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
