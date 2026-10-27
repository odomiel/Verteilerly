#!/usr/bin/env python3
"""Ein Release bei GitHub anlegen und die Dateien hochladen.

    python3 werkzeuge/github_release.py auslieferung/Verteilerly-*.AppImage \\
                                        auslieferung/Verteilerly_*.exe
    python3 werkzeuge/github_release.py --probe <dateien>    nur zeigen
    python3 werkzeuge/github_release.py --text notiz.md <dateien>

**Zweimal aufgerufen tut es nichts doppelt.** Gibt es das Release
schon, wird es genommen, gleichnamige Anhaenge werden ersetzt - und
der **Begleittext nachgezogen**, wenn er sich geaendert hat. Genau so
kommt die Windows-.exe spaeter ans selbe Release: sie entsteht auf
einem anderen Rechner, und ihre Pruefsumme gehoert in den Text. Wer
den Text drueben von Hand verbessert hat, schuetzt ihn mit
``--text-lassen``.

**Wozu.** Das Repo wird als Push-Mirror nach GitHub gespiegelt, und ein
Spiegel uebertraegt nur Zweige und Tags - **keine Releases und keine
Anhaenge**. Die legt dieses Werkzeug nach: warten, bis der Tag drueben
ist, Release anlegen (oder das vorhandene nehmen), Dateien hochladen und
jede per SHA-256 gegenpruefen.

**Was wohin gehoert.** Im Repo steht nichts, was auf ein Konto zeigt -
es wird oeffentlich gespiegelt. Repo-Kennung und Token stehen darum
daneben:

    Kennung: $VERTEILERLY_GITHUB_SLUG  oder  ~/.config/Verteilerly/github_repo
    Token  : $GITHUB_TOKEN             oder  ~/.config/Verteilerly/github_token

Beide Dateien liegen **neben** den Unterordnern des Arbeitsordners und
wandern darum in kein Sicherungspaket: ``paket.sichern()`` nimmt nur
``vorlagen/``, ``blattvorlagen/``, ``kabeltypen/`` und die Conf mit.

Der Token braucht genau ein Recht: **Contents: Read and write** auf dieses
eine Repo (fein eingestellt), oder beim klassischen Token den Bereich
``repo`` - bei einem oeffentlichen Repo reicht ``public_repo``.

Das Werkzeug kommt mit der Standardbibliothek aus und laeuft darum auch
ohne die virtuelle Umgebung.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

WURZEL = pathlib.Path(__file__).resolve().parent.parent
API = "https://api.github.com"
HOCHLADEN = "https://uploads.github.com"
# Derselbe Ort, an dem auch das Programm unter Linux seine Sachen
# haelt - samt XDG_CONFIG_HOME, damit beide dasselbe meinen.
CONFORDNER = pathlib.Path(
    os.environ.get("XDG_CONFIG_HOME") or pathlib.Path.home() / ".config"
) / "Verteilerly"
#: Wie lange auf den Tag gewartet wird, den der Spiegel hinueberschiebt.
WARTEN = 180


# -- Kennung und Token: nie im Repo ---------------------------------------

def _aus_umgebung_oder_datei(umgebung: str, datei: str) -> str:
    wert = os.environ.get(umgebung, "").strip()
    if wert:
        return wert
    try:
        return (CONFORDNER / datei).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def slug_finden() -> str:
    """``eigner/repo`` bei GitHub."""
    slug = _aus_umgebung_oder_datei("VERTEILERLY_GITHUB_SLUG", "github_repo")
    if not slug:
        raise SystemExit(
            "GitHub-Repo unbekannt. Setze VERTEILERLY_GITHUB_SLUG (eigner/repo) "
            f"oder lege {CONFORDNER / 'github_repo'} mit dieser einen Zeile an."
        )
    return slug


def token_finden() -> str:
    token = _aus_umgebung_oder_datei("GITHUB_TOKEN", "github_token")
    if not token:
        raise SystemExit(
            "GitHub-Token fehlt. Setze GITHUB_TOKEN oder lege "
            f"{CONFORDNER / 'github_token'} an (fein eingestellt, "
            "Contents: Read and write)."
        )
    return token


# -- Fassung und Begleittext ----------------------------------------------

def fassung_lesen() -> str:
    """Die Fassung aus ``verteilerly/version.py`` - ohne Import."""
    quelle = (WURZEL / "verteilerly" / "version.py").read_text(encoding="utf-8")
    treffer = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', quelle, re.M)
    if not treffer:
        raise SystemExit("VERSION in verteilerly/version.py nicht gefunden")
    return treffer.group(1)


def _git(*befehl: str) -> str:
    fertig = subprocess.run(
        ["git", *befehl], cwd=WURZEL, capture_output=True, text=True
    )
    return fertig.stdout.strip() if fertig.returncode == 0 else ""


def voriger_tag(tag: str) -> str:
    """Der Tag davor - wofuer der Begleittext die Aenderungen sammelt."""
    return _git("describe", "--tags", "--abbrev=0", f"{tag}^")


def pruefsumme(datei: pathlib.Path) -> str:
    return hashlib.sha256(pathlib.Path(datei).read_bytes()).hexdigest()


def notiz_bauen(tag: str, anhaenge: list[pathlib.Path]) -> str:
    """Begleittext aus den Commits seit dem vorigen Tag.

    Die Release-Commits bleiben draussen - sie sagen nur, dass eine
    Fassung gesetzt wurde. Darunter die Dateien mit ihrer Pruefsumme,
    wie es die Release-Seite auch sonst haelt.
    """
    teile: list[str] = []
    vorher = voriger_tag(tag)
    if vorher:
        zeilen = [
            f"* {zeile}"
            for zeile in _git("log", "--format=%s", f"{vorher}..{tag}").splitlines()
            if zeile and not zeile.startswith("Release ")
        ]
        if zeilen:
            teile.append("## Was neu ist\n\n" + "\n".join(zeilen))
    if anhaenge:
        tabelle = "\n".join(
            f"| `{datei.name}` | `{pruefsumme(datei)}` |" for datei in anhaenge
        )
        teile.append("## Dateien\n\n| Datei | SHA256 |\n|---|---|\n" + tabelle)
    return "\n\n".join(teile)


# -- HTTP ------------------------------------------------------------------

def _koepfe(token: str, dazu: dict | None = None) -> dict:
    koepfe = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "verteilerly-release",
    }
    if dazu:
        koepfe.update(dazu)
    return koepfe


def _anfrage(art: str, url: str, koepfe: dict, inhalt: bytes | None = None):
    bitte = urllib.request.Request(url, data=inhalt, method=art, headers=koepfe)
    try:
        with urllib.request.urlopen(bitte) as antwort:
            return antwort.status, antwort.read()
    except urllib.error.HTTPError as fehler:
        return fehler.code, fehler.read()


def auf_tag_warten(slug: str, tag: str, token: str, sekunden: int = WARTEN) -> bool:
    """Wartet, bis der Spiegel den Tag nach GitHub geschoben hat."""
    url = f"{API}/repos/{slug}/git/ref/tags/{tag}"
    ende = time.time() + sekunden
    while time.time() < ende:
        stand, _ = _anfrage("GET", url, _koepfe(token))
        if stand == 200:
            return True
        time.sleep(3)
    return False


def release_holen(slug: str, tag: str, token: str) -> dict | None:
    stand, inhalt = _anfrage(
        "GET", f"{API}/repos/{slug}/releases/tags/{tag}", _koepfe(token)
    )
    return json.loads(inhalt) if stand == 200 else None


def release_anlegen(slug: str, tag: str, notiz: str, token: str,
                    entwurf: bool = False, vorab: bool = False) -> dict:
    fracht = json.dumps({
        "tag_name": tag,
        "name": tag,
        "body": notiz,
        "draft": entwurf,
        "prerelease": vorab,
    }).encode()
    stand, inhalt = _anfrage(
        "POST", f"{API}/repos/{slug}/releases", _koepfe(token), fracht
    )
    if stand in (200, 201):
        return json.loads(inhalt)
    raise SystemExit(
        f"Release anlegen fehlgeschlagen (HTTP {stand}): "
        f"{inhalt[:400].decode(errors='replace')}"
    )


def text_nachziehen(slug: str, release: dict, notiz: str, token: str) -> bool:
    """Schreibt den Begleittext eines bestehenden Releases neu.

    Gebraucht wird das beim **Nachtrag**: die Windows-.exe entsteht auf
    einem anderen Rechner und kommt spaeter an dasselbe Release - dann
    muss ihre Pruefsumme in den Text, sonst steht dort eine Liste, in
    der sie fehlt.

    Geschrieben wird nur, was sich unterscheidet; zurueck kommt, ob
    etwas geschrieben wurde.
    """
    if (release.get("body") or "") == notiz:
        return False
    stand, inhalt = _anfrage(
        "PATCH", f"{API}/repos/{slug}/releases/{release['id']}",
        _koepfe(token), json.dumps({"body": notiz}).encode(),
    )
    if stand != 200:
        raise SystemExit(
            f"Begleittext nachziehen fehlgeschlagen (HTTP {stand}): "
            f"{inhalt[:400].decode(errors='replace')}"
        )
    release["body"] = notiz
    return True


def anhang_entfernen(slug: str, release: dict, name: str, token: str) -> None:
    """Raeumt einen gleichnamigen Anhang weg - sonst wird er umbenannt."""
    for anhang in release.get("assets") or []:
        if anhang.get("name") == name:
            _anfrage(
                "DELETE", f"{API}/repos/{slug}/releases/assets/{anhang['id']}",
                _koepfe(token),
            )


def anhang_hochladen(slug: str, release_id: int, datei: pathlib.Path,
                     token: str) -> dict:
    url = f"{HOCHLADEN}/repos/{slug}/releases/{release_id}/assets?name={datei.name}"
    koepfe = _koepfe(token, {"Content-Type": "application/octet-stream"})
    stand, inhalt = _anfrage("POST", url, koepfe, datei.read_bytes())
    if stand in (200, 201):
        return json.loads(inhalt)
    raise SystemExit(
        f"Hochladen fehlgeschlagen (HTTP {stand}): "
        f"{inhalt[:400].decode(errors='replace')}"
    )


def anhang_pruefen(url: str, datei: pathlib.Path) -> bool:
    """Laedt den Anhang zurueck und vergleicht die Pruefsumme.

    **Ohne Anmeldekopf**: die Adresse leitet auf den Auslieferungsdienst
    um, und der weist eine fremde Anmeldung ab.
    """
    bitte = urllib.request.Request(url, headers={"User-Agent": "verteilerly-release"})
    with urllib.request.urlopen(bitte) as antwort:
        geladen = hashlib.sha256(antwort.read()).hexdigest()
    return geladen == pruefsumme(datei)


# -- Ablauf ----------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    zerleger = argparse.ArgumentParser(
        description="Ein Release bei GitHub anlegen und die Dateien hochladen."
    )
    zerleger.add_argument("dateien", nargs="+", help="AppImage, .exe, PDF …")
    zerleger.add_argument("--fassung", help="Fassung (Vorgabe: aus version.py)")
    zerleger.add_argument(
        "--text", help="Datei mit dem Begleittext ('-' liest von der Eingabe)"
    )
    zerleger.add_argument("--entwurf", action="store_true", help="als Entwurf anlegen")
    zerleger.add_argument("--vorab", action="store_true", help="als Vorabfassung")
    zerleger.add_argument("--probe", action="store_true", help="nur zeigen, nichts senden")
    zerleger.add_argument(
        "--text-lassen", action="store_true",
        help="den Begleittext eines bestehenden Releases stehen lassen",
    )
    zerleger.add_argument(
        "--warten", type=int, default=WARTEN,
        help=f"Sekunden auf den Tag bei GitHub warten (Vorgabe {WARTEN})",
    )
    werte = zerleger.parse_args(argv)

    tag = werte.fassung or fassung_lesen()
    anhaenge = [pathlib.Path(name).resolve() for name in werte.dateien]
    for datei in anhaenge:
        if not datei.is_file():
            raise SystemExit(f"Datei nicht gefunden: {datei}")
        if tag not in datei.name:
            print(f"WARNUNG: {datei.name} traegt die Fassung {tag} nicht im Namen.",
                  file=sys.stderr)

    if werte.text == "-":
        notiz = sys.stdin.read()
    elif werte.text:
        notiz = pathlib.Path(werte.text).read_text(encoding="utf-8")
    else:
        notiz = notiz_bauen(tag, anhaenge)

    print(f"Release {tag}" + ("  [Entwurf]" if werte.entwurf else ""))
    for datei in anhaenge:
        print(f"  · {datei.name} ({datei.stat().st_size} Bytes)")
    if werte.probe:
        print("\n--- Begleittext ---\n" + notiz + "\n--- nichts gesendet (--probe) ---")
        return 0

    slug = slug_finden()
    token = token_finden()

    print(f"· warte auf den Tag {tag} bei {slug} (bis {werte.warten} s) …")
    if not auf_tag_warten(slug, tag, token, werte.warten):
        raise SystemExit(
            f"Der Tag {tag} ist nach {werte.warten} s nicht bei GitHub angekommen - "
            "hat der Spiegel schon gelaufen?"
        )

    vorhanden = release_holen(slug, tag, token)
    if vorhanden:
        print(f"· Release {tag} gibt es schon (id {vorhanden['id']}) - wird genommen.")
        release = vorhanden
        if werte.text_lassen:
            print("· Begleittext bleibt, wie er ist (--text-lassen).")
        elif text_nachziehen(slug, release, notiz, token):
            print("· Begleittext nachgezogen.")
        else:
            print("· Begleittext steht schon so da.")
    else:
        release = release_anlegen(
            slug, tag, notiz, token, werte.entwurf, werte.vorab
        )
        print(f"· Release angelegt: id {release['id']}")

    for datei in anhaenge:
        anhang_entfernen(slug, release, datei.name, token)
        oben = anhang_hochladen(slug, release["id"], datei, token)
        if not anhang_pruefen(oben.get("browser_download_url", ""), datei):
            raise SystemExit(f"Pruefsumme stimmt nicht: {oben.get('name')}")
        print(f"· hochgeladen und gegengeprueft: {oben.get('name')} "
              f"({oben.get('size')} Bytes)")
    print(f"Fertig: https://github.com/{slug}/releases/tag/{tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
