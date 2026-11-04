"""Was beim Anlegen mehrerer Verteiler entsteht - gerechnet, nicht geschrieben.

Ein Projekt besteht selten aus einem Verteiler: ein Haus hat einen HVt
und mehrere Etagenverteiler, und alle tragen dieselben Projektdaten.
Dieses Modul rechnet aus, was dabei auf die Platte soll, und schreibt es
auf Zuruf - **in zwei Schritten**, wie die Restleitungen: ``planen()``
aendert nichts und sagt zu jeder Zeile, was ihr im Weg steht, der Dialog
zeigt das, und erst ``anlegen()`` legt an. So laesst sich die Rechnung
ohne Qt pruefen.

Je Verteiler entsteht ein **Projektordner** mit der Projektdatei darin;
``eigener_ordner=False`` legt stattdessen alle Dateien in **einen**
Ordner. Dazu kommen die **Beilagen**: vorgegebene Dateien und Ordner,
die in jeden Projektordner mitwandern - jede mit ihrem eigenen
Unterordner, damit ein Projektordner von Anfang an aussieht wie die
anderen (``Fotos/``, ``Messprotokolle/Vorlage.xlsx``).

**Ueberschrieben wird nichts.** Eine Projektdatei, die es schon gibt,
ist ein Grund, die Zeile stehen zu lassen; eine Beilage, die am Ziel
schon liegt, wird uebergangen und gezaehlt. Und **ein Fehler haelt den
Rest nicht auf**: ein gesperrter Ordner soll nicht die anderen neun
Verteiler kosten.
"""

from __future__ import annotations

import pathlib
import re
import shutil
from dataclasses import dataclass, field

from ... import projektdatei
from ...modell import ModellFehler, Projekt
from ...sprachen import u
from ...verknuepfung import ENDUNGEN

#: Wie eine Projektdatei heisst - dieselbe Endung, die auch verknuepft wird.
ENDUNG = ENDUNGEN[0]

#: Zeichen, die in keinem Datei- oder Ordnernamen stehen duerfen. Die
#: Windows-Liste gilt hier ueberall: ein Projektordner wandert auf einen
#: Stick und soll auch dort heissen, wie er heisst.
VERBOTEN = '<>:"/\\|?*'

#: Laenger wird kein Ordnername. Lange Pfade sind unter Windows eine
#: Falle, und niemand liest einen Ordner mit zweihundert Zeichen.
NAME_HOECHSTENS = 80

#: Womit Unterordner und Quelle einer Beilage in der Conf getrennt stehen.
TRENNER = "\t"


def sicherer_name(text: str) -> str:
    """Aus einer Eingabe einen Namen, den jedes Dateisystem annimmt.

    Verbotene Zeichen werden zu Leerzeichen, nicht entfernt: aus
    ``HVt/UVt`` wird ``HVt UVt`` und nicht ``HVtUVt``. Ein Punkt am Ende
    muss weg - Windows laesst ihn stillschweigend fallen, und dann
    heisst der Ordner anders als die Datei darin.
    """
    name = "".join(
        " " if zeichen in VERBOTEN or not zeichen.isprintable() else zeichen
        for zeichen in str(text or "")
    )
    name = re.sub(r"\s+", " ", name).strip()
    return name[:NAME_HOECHSTENS].strip().rstrip(". ").strip()


def sicherer_unterordner(text: str) -> str:
    """Ein Unterordner darf tief sein, aber nicht aus dem Projektordner heraus.

    Nicht anders als beim Einspielen eines Pakets: ``..`` und ein
    absoluter Pfad sind keine Angabe, sondern ein Ausbruchsversuch. Was
    davon uebrig bleibt, steht hier mit ``/`` als Trenner - ganz gleich,
    wie es eingetippt wurde.
    """
    teile = [sicherer_name(teil) for teil in re.split(r"[\\/]+", str(text or ""))]
    return "/".join(teil for teil in teile if teil)


@dataclass(frozen=True)
class Beilage:
    """Eine Datei - oder ein ganzer Ordner -, die in jeden Projektordner kommt.

    Bei einem Ordner wandert sein **Inhalt** in den Unterordner, nicht er
    selbst: wer ``Muster`` nach ``Fotos`` legt, will die Bilder in
    ``Fotos`` haben und nicht in ``Fotos/Muster``. Ein leerer Ordner
    bringt wenigstens sich selbst mit - so laesst sich ein leeres Fach
    vorgeben.
    """

    quelle: pathlib.Path
    #: Wohin im Projektordner; leer heisst: unmittelbar hinein.
    unterordner: str = ""

    @property
    def ziel(self) -> str:
        return sicherer_unterordner(self.unterordner)

    @property
    def fehlt(self) -> bool:
        """Die Quelle ist weg - verschoben, umbenannt, Stick abgezogen."""
        return not self.quelle.exists()


def beilagen_lesen(text) -> list[Beilage]:
    """Je Zeile eine Beilage: ``Unterordner<Tab>Quelle``.

    Ohne Tabulator ist die ganze Zeile die Quelle; sie kommt dann
    unmittelbar in den Projektordner. So steht der Bestand in der
    ``Verteilerly.conf`` - wie die Vorlagen des Rangierfeldes als Text
    mit Zeilenumbruechen.
    """
    beilagen: list[Beilage] = []
    for zeile in str(text or "").splitlines():
        if not zeile.strip():
            continue
        unterordner, trenner, quelle = zeile.partition(TRENNER)
        if not trenner:
            unterordner, quelle = "", unterordner
        quelle = quelle.strip()
        if quelle:
            beilagen.append(Beilage(pathlib.Path(quelle), unterordner.strip()))
    return beilagen


def beilagen_schreiben(beilagen) -> str:
    return "\n".join(
        f"{beilage.unterordner}{TRENNER}{beilage.quelle}" for beilage in beilagen
    )


def beilagendateien(beilage: Beilage):
    """Welche Dateien und welche Faecher diese Beilage mitbringt.

    Zurueck kommen ``((Quelle, Zielpfad), …)`` und die Ordner, die es
    dafuer braucht - beides **relativ** zum Projektordner und mit ``/``
    als Trenner. Was es nicht gibt, bringt nichts mit; gemeldet wird das
    im Dialog, nicht hier.
    """
    ziel = beilage.ziel
    quelle = beilage.quelle

    def unter(pfad: str) -> str:
        return f"{ziel}/{pfad}" if ziel else pfad

    if quelle.is_dir():
        faecher = [ziel] if ziel else []
        dateien = []
        for ort in sorted(quelle.rglob("*")):
            innen = unter("/".join(ort.relative_to(quelle).parts))
            if ort.is_dir():
                faecher.append(innen)
            elif ort.is_file():
                dateien.append((ort, innen))
        return tuple(dateien), tuple(faecher)
    if quelle.is_file():
        return ((quelle, unter(quelle.name)),), ((ziel,) if ziel else ())
    return (), ()


def _mitbringsel(beilagen):
    """Alle Beilagen zusammengenommen: erst die Faecher, dann die Dateien."""
    faecher: list[str] = []
    dateien: list[tuple[pathlib.Path, str]] = []
    for beilage in beilagen:
        teile, eigene = beilagendateien(beilage)
        for fach in eigene:
            if fach and fach not in faecher:
                faecher.append(fach)
        dateien.extend(teile)
    return tuple(faecher), tuple(dateien)


@dataclass
class Angabe:
    """Ein Verteiler, wie der Anwender ihn angibt - eine Zeile der Liste."""

    name: str = ""
    nummer: str = ""
    #: Wie Ordner und Datei heissen sollen; leer heisst: aus Name und Nummer.
    ablage: str = ""

    @property
    def leer(self) -> bool:
        return not (self.name.strip() or self.nummer.strip())

    def bezeichnung(self) -> str:
        """Wie der Verteiler in Meldungen und als Ordner heisst.

        Die Nummer steht vorn: so liegen die Ordner in der
        Dateiverwaltung in der Reihenfolge der Anlage.
        """
        return " ".join(
            teil for teil in (self.nummer.strip(), self.name.strip()) if teil
        )


def ablagename(angabe: Angabe) -> str:
    """Wie Ordner und Datei dieser Zeile heissen.

    Eine eigene Angabe gilt, wie sie dasteht - nur von verbotenen Zeichen
    befreit: wer seinen Ordnern eine eigene Ordnung gibt, soll sie
    behalten.
    """
    return sicherer_name(angabe.ablage or angabe.bezeichnung())


@dataclass
class Anlage:
    """Ein Verteiler, wie er auf die Platte soll - noch ist nichts geschrieben.

    ``grund`` ist der Haken an der Sache: steht dort etwas, wird diese
    Zeile nicht angelegt, und der Dialog zeigt den Satz an ihrer Stelle.
    """

    angabe: Angabe
    ordner: pathlib.Path
    datei: pathlib.Path
    #: Faecher, die im Projektordner entstehen - auch leere.
    faecher: tuple[str, ...] = ()
    #: Die Beilagen: (Quelle, Zielpfad im Projektordner).
    dateien: tuple[tuple[pathlib.Path, str], ...] = ()
    grund: str = ""

    @property
    def geht(self) -> bool:
        return not self.grund


def planen(angaben, ziel, beilagen=(), eigener_ordner: bool = True) -> list[Anlage]:
    """Was entstehen soll - und was dem im Weg steht.

    Leere Zeilen fallen weg, der Rest bekommt seinen Ordner und seine
    Datei. Geprueft wird **von oben nach unten**, jede Zeile gegen die
    darueber: zwei gleiche Namen sind ein Fehler, und die obere Zeile
    bekommt den Namen zuerst.

    **Die Beilagen gehoeren dem Projektordner.** Bekommt jeder Verteiler
    einen eigenen, bekommt jeder sie; liegen alle in einem Ordner, gibt
    es diesen Ordner einmal - dann traegt sie die erste Zeile, die
    durchgeht.
    """
    ziel = pathlib.Path(ziel)
    faecher, dateien = _mitbringsel(beilagen)
    vergeben: set[str] = set()
    anlagen: list[Anlage] = []
    for angabe in angaben:
        if angabe.leer:
            continue
        name = ablagename(angabe)
        ordner = ziel / name if eigener_ordner else ziel
        datei = ordner / f"{name}{ENDUNG}"
        grund = ""
        if not name:
            grund = u("kein Name, der als Ordnername taugt")
        elif name.casefold() in vergeben:
            grund = u("steht in dieser Liste zweimal")
        elif datei.exists():
            grund = u("diese Datei gibt es schon")
        elif ordner.exists() and not ordner.is_dir():
            grund = u("dort liegt eine Datei dieses Namens")
        vergeben.add(name.casefold())
        anlage = Anlage(angabe, ordner, datei, grund=grund)
        if not grund and (eigener_ordner or not any(x.geht for x in anlagen)):
            anlage.faecher, anlage.dateien = faecher, dateien
        anlagen.append(anlage)
    return anlagen


@dataclass
class Bericht:
    """Was angelegt wurde - und was nicht."""

    #: Die Projektordner, jeder einmal.
    ordner: list[pathlib.Path] = field(default_factory=list)
    #: Die geschriebenen Projektdateien.
    dateien: list[pathlib.Path] = field(default_factory=list)
    #: So viele Beilagen sind mitgewandert.
    beigelegt: int = 0
    #: So viele lagen am Ziel schon - ueberschrieben wird nichts.
    uebergangen: int = 0
    gruende: list[str] = field(default_factory=list)

    @property
    def angelegt(self) -> int:
        return len(self.dateien)


def _grundsatz(angabe: Angabe, grund: str) -> str:
    """Zeile und Grund in einem Satz - er traegt keine eigenen Woerter."""
    return f"{angabe.bezeichnung() or '?'}: {grund}"


def anlegen(anlagen, projekt_fuer) -> Bericht:
    """Schreibt, was geht, und sagt, was nicht ging.

    ``projekt_fuer(angabe)`` baut das Projekt zu einer Zeile: Geometrie
    und Projektdaten kommen von dort, hier wird nur geschrieben. Jede
    Zeile steht fuer sich - **scheitert eine, bleiben die anderen
    stehen**; der Grund kommt in den Bericht.
    """
    bericht = Bericht()
    for anlage in anlagen:
        if not anlage.geht:
            bericht.gruende.append(_grundsatz(anlage.angabe, anlage.grund))
            continue
        try:
            anlage.ordner.mkdir(parents=True, exist_ok=True)
            for fach in anlage.faecher:
                (anlage.ordner / fach).mkdir(parents=True, exist_ok=True)
            projekt = projekt_fuer(anlage.angabe)
            if not isinstance(projekt, Projekt):
                raise ModellFehler(u("kein Projekt zu dieser Zeile"))
            projektdatei.speichern(projekt, anlage.datei)
        except (OSError, ModellFehler) as fehler:
            bericht.gruende.append(_grundsatz(anlage.angabe, str(fehler)))
            continue
        if anlage.ordner not in bericht.ordner:
            bericht.ordner.append(anlage.ordner)
        bericht.dateien.append(anlage.datei)
        for quelle, pfad in anlage.dateien:
            ziel = anlage.ordner / pfad
            try:
                if ziel.exists():
                    bericht.uebergangen += 1
                    continue
                ziel.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(quelle, ziel)
            except OSError as fehler:
                bericht.gruende.append(f"{pfad}: {fehler}")
                continue
            bericht.beigelegt += 1
    return bericht
