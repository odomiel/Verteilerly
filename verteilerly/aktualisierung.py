"""Einmal am Tag nachsehen, ob es eine neuere Fassung gibt.

Gefragt wird die oeffentliche Releaseliste des Projekts - **nur lesend,
ohne Anmeldung und ohne irgendetwas zu senden**, was ueber die Anfrage
hinausgeht. Heruntergeladen wird nichts: das Programm sagt, dass es eine
neuere Fassung gibt und wo sie liegt; holen muss sie der Anwender.

Hier steht kein Qt. Die Oberflaeche ruft `nachsehen()` in einem eigenen
Faden auf und bekommt das Ergebnis zurueck - oder ``None``.

**Ohne Netz ist kein Fehler.** Jede Stoerung - kein Netz, ein Zaun
davor, eine unerwartete Antwort, ein fehlendes ``ssl`` - endet still mit
``None``. Eine Fassungspruefung, die den Start aufhaelt oder mit einer
Meldung dazwischenfaehrt, waere schlimmer als gar keine.

**Die Zertifikate stehen auf dem Rechner, nicht im Abbild.** Das
mitgelieferte Python bringt OpenSSL mit, aber keinen Zertifikatsspeicher
(seine eingebauten Pfade zeigen ins Leere - ``/opt/_internal/…``). Gesucht
wird darum der Speicher des Systems; findet sich keiner, wird nicht
geprueft. Ein eigener Satz Wurzelzertifikate im Abbild veraltete und
muesste gepflegt werden.
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import urllib.request

from .version import VERSION, UngueltigeVersion, zerlegen

#: Wo die Fassungen liegen - das oeffentliche Spiegelrepo des Projekts.
PROJEKT = "odomiel/Verteilerly"
NEUESTE = f"https://api.github.com/repos/{PROJEKT}/releases/latest"
SEITE = f"https://github.com/{PROJEKT}/releases"

#: Lieber nichts erfahren als warten: der Start soll nicht daran haengen.
WARTEZEIT = 6.0

#: Steht diese Umgebungsvariable, wird nie nachgesehen. Die Testreihe
#: setzt sie: sie geht nicht ins Netz, und eine Reihe, die an einer
#: fremden Antwort haengt, prueft das Wetter und nicht das Programm.
OHNE_PRUEFUNG = "VERTEILERLY_OHNE_UPDATEPRUEFUNG"

#: Wo die Wurzelzertifikate ueblicherweise liegen - Datei vor Ordner.
ZERTIFIKATE = (
    "/etc/ssl/certs/ca-certificates.crt",      # Debian, Ubuntu, Arch
    "/etc/pki/tls/certs/ca-bundle.crt",        # Fedora, RHEL
    "/etc/ssl/ca-bundle.pem",                  # openSUSE
    "/etc/ssl/cert.pem",                       # Alpine, BSD
)
ZERTIFIKATSORDNER = ("/etc/ssl/certs", "/etc/pki/tls/certs")


def zertifikatsspeicher() -> tuple[str | None, str | None]:
    """Datei und Ordner mit den Wurzelzertifikaten des Rechners."""
    datei = next((ort for ort in ZERTIFIKATE if pathlib.Path(ort).is_file()), None)
    ordner = next(
        (ort for ort in ZERTIFIKATSORDNER if pathlib.Path(ort).is_dir()), None
    )
    return datei, ordner


def umgebung():
    """Ein TLS-Umfeld mit den Zertifikaten des Rechners - oder nichts.

    Unter Windows kennt Python den Speicher des Systems selbst; dort
    genuegt die Vorgabe. Jede Anfrage des Programms geht ueber diese
    eine Stelle - die Fassungspruefung wie die Rechtschreibpruefung.
    """
    import ssl

    if os.name == "nt":
        return ssl.create_default_context()
    datei, ordner = zertifikatsspeicher()
    if not datei and not ordner:
        return None
    return ssl.create_default_context(cafile=datei, capath=None if datei else ordner)


def erlaubt() -> bool:
    """Darf ueberhaupt nachgesehen werden?"""
    return not os.environ.get(OHNE_PRUEFUNG)


def neuer_als(fassung: str, als: str = VERSION) -> bool:
    """Ist ``fassung`` neuer als die laufende?"""
    try:
        return zerlegen(fassung) > zerlegen(als)
    except UngueltigeVersion:
        return False


def faellig(zuletzt: str, heute: datetime.date | None = None) -> bool:
    """Steht die taegliche Pruefung an?

    ``zuletzt`` ist das gemerkte Datum als ISO-Zeichenkette. Was sich
    nicht lesen laesst - leer, krumm, aus der Zukunft -, gilt als
    faellig: lieber einmal zu viel nachsehen als nie wieder.
    """
    heute = heute or datetime.date.today()
    try:
        return datetime.date.fromisoformat(zuletzt.strip()) != heute
    except (AttributeError, ValueError):
        return True


def nachsehen(wartezeit: float = WARTEZEIT) -> dict | None:
    """Die neueste veroeffentlichte Fassung - oder ``None``.

    Zurueck kommt ``{"fassung": "2026.10.12b3", "seite": "https://…"}``.
    Geprueft wird hier nicht, ob sie neuer ist; das tut ``neuer_als()``.
    """
    bitte = urllib.request.Request(
        NEUESTE,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": f"Verteilerly/{VERSION}",
        },
    )
    if not erlaubt():
        return None
    try:
        umfeld = umgebung()
        if umfeld is None:
            return None
        with urllib.request.urlopen(bitte, timeout=wartezeit, context=umfeld) as antwort:
            inhalt = json.loads(antwort.read())
    except Exception:       # noqa: BLE001 - offline, Zaun, krumme Antwort: still
        return None
    fassung = str(inhalt.get("tag_name") or "").strip().lstrip("vV")
    if not fassung:
        return None
    return {"fassung": fassung, "seite": inhalt.get("html_url") or SEITE}


#: Was beim Nachsehen herauskommen kann.
NEUER = "neuer"
AKTUELL = "aktuell"
UNERREICHBAR = "unerreichbar"


def stand(wartezeit: float = WARTEZEIT) -> tuple[str, dict | None]:
    """Fuer die Nachfrage von Hand: was ist, mit Begruendung.

    Die taegliche Nachfrage meldet nur einen Fund und schweigt sonst -
    wer dagegen selbst auf den Knopf drueckt, will auch hoeren, dass
    alles aktuell oder nichts zu erreichen ist. Darum drei Ausgaenge
    statt eines.
    """
    gefunden = nachsehen(wartezeit)
    if gefunden is None:
        return UNERREICHBAR, None
    return (NEUER if neuer_als(gefunden["fassung"]) else AKTUELL), gefunden


def neuere_fassung(wartezeit: float = WARTEZEIT) -> dict | None:
    """Nur melden, was wirklich neuer ist als das laufende Programm."""
    gefunden = nachsehen(wartezeit)
    if gefunden and neuer_als(gefunden["fassung"]):
        return gefunden
    return None
