"""Was beim Anlegen mehrerer Verteiler entsteht - gerechnet, nicht geschrieben.

Ein Projekt besteht selten aus einem Verteiler: ein Haus hat einen HVt
und mehrere Etagenverteiler, und alle tragen dieselben Projektdaten.
Dieses Modul rechnet aus, was dabei auf die Platte soll, und schreibt es
auf Zuruf - **in zwei Schritten**, wie die Restleitungen: ``planen()``
aendert nichts und sagt zu jeder Zeile, was ihr im Weg steht, der Dialog
zeigt das, und erst ``anlegen()`` legt an. So laesst sich die Rechnung
ohne Qt pruefen.

Gearbeitet wird in **einem Projektordner**: darin bekommt jeder
Verteiler seinen eigenen Unterordner mit seiner Projektdatei, oder - mit
``eigener_ordner=False`` - liegen alle Projektdateien nebeneinander
darin. Die **Beilagen** gehoeren dem Projektordner und werden darum
**einmal** gelegt, nicht je Verteiler: vorgegebene Dateien und Ordner,
jede mit ihrem eigenen Unterordner, damit ein Projektordner von Anfang
an aussieht wie der vom letzten Mal (``Fotos/``,
``Messprotokolle/Vorlage.xlsx``).

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
    """Eine Datei - oder ein ganzer Ordner -, die in den Projektordner kommt.

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
    """Ein Verteiler, wie der Anwender ihn angibt - eine Zeile der Liste.

    Die **Geometrie steht dabei**: jede Zeile traegt ihren eigenen
    Bauplan, denn ein Projekt besteht nicht aus gleichen Verteilern -
    neben dem HVt mit vier Buchten haengt eine einzelne 10er-Leiste im
    Treppenhaus. Woher er kommt - aus einer Verteilervorlage oder aus
    eigenen Zahlen -, ist Sache des Dialogs; hier stehen nur die Zahlen,
    und zwar in der Form, die ``Verteiler.aus_buchten`` nimmt.
    """

    name: str = ""
    nummer: str = ""
    #: Wie Ordner und Datei heissen sollen; leer heisst: aus Name und Nummer.
    ablage: str = ""
    #: Je Bucht (Leisten, DA je Leiste). Leer heisst: keine Geometrie
    #: gewaehlt - daraus laesst sich kein Verteiler bauen, und der
    #: Aufrufer bekommt es beim Anlegen gesagt.
    bauplan: tuple[tuple[int, int], ...] = ()

    @property
    def leer(self) -> bool:
        return not (self.name.strip() or self.nummer.strip())

    @property
    def da_gesamt(self) -> int:
        return sum(leisten * da for leisten, da in self.bauplan)

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
    #: Der Ordner des Verteilers - der Projektordner selbst, wenn alle
    #: Projektdateien nebeneinander liegen sollen.
    ordner: pathlib.Path
    datei: pathlib.Path
    grund: str = ""

    @property
    def geht(self) -> bool:
        return not self.grund


@dataclass
class Plan:
    """Ein Projektordner, wie er entstehen soll - noch ist nichts geschrieben.

    Die Verteiler stehen in ``anlagen``, die **Beilagen** daneben: sie
    gehoeren dem Projektordner und werden einmal gelegt, ganz gleich wie
    viele Verteiler darin wohnen.
    """

    #: Der Projektordner.
    ordner: pathlib.Path
    anlagen: list[Anlage] = field(default_factory=list)
    #: Faecher der Beilagen, relativ zum Projektordner - auch leere.
    faecher: tuple[str, ...] = ()
    #: Die Beilagen: (Quelle, Zielpfad im Projektordner).
    dateien: tuple[tuple[pathlib.Path, str], ...] = ()

    @property
    def moegliche(self) -> list[Anlage]:
        """Die Zeilen, denen nichts im Weg steht."""
        return [anlage for anlage in self.anlagen if anlage.geht]


def planen(angaben, ordner, beilagen=(), eigener_ordner: bool = True) -> Plan:
    """Was im Projektordner entstehen soll - und was dem im Weg steht.

    Leere Zeilen fallen weg, der Rest bekommt seinen Ordner und seine
    Datei. Geprueft wird **von oben nach unten**, jede Zeile gegen die
    darueber: zwei gleiche Namen sind ein Fehler, und die obere Zeile
    bekommt den Namen zuerst.

    Die **Beilagen** haengen am Plan, nicht an der einzelnen Zeile: sie
    gehoeren dem Projektordner und werden darum einmal gelegt.
    """
    ordner = pathlib.Path(ordner)
    faecher, dateien = _mitbringsel(beilagen)
    plan = Plan(ordner, [], faecher, dateien)
    vergeben: set[str] = set()
    for angabe in angaben:
        if angabe.leer:
            continue
        name = ablagename(angabe)
        eigen = ordner / name if eigener_ordner else ordner
        datei = eigen / f"{name}{ENDUNG}"
        grund = ""
        if not name:
            grund = u("kein Name, der als Ordnername taugt")
        elif name.casefold() in vergeben:
            grund = u("steht in dieser Liste zweimal")
        elif datei.exists():
            grund = u("diese Datei gibt es schon")
        elif eigen.exists() and not eigen.is_dir():
            grund = u("dort liegt eine Datei dieses Namens")
        vergeben.add(name.casefold())
        plan.anlagen.append(Anlage(angabe, eigen, datei, grund=grund))
    return plan


@dataclass
class Bericht:
    """Was angelegt wurde - und was nicht."""

    #: Der Projektordner - gesetzt, sobald er dasteht.
    ordner: pathlib.Path | None = None
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


def _beilegen(plan: Plan, bericht: Bericht) -> None:
    """Legt die Beilagen **einmal** in den Projektordner.

    Die Faecher zuerst, und zwar alle - ein vorgegebenes leeres Fach
    (``Fotos/``) soll auch dann dastehen, wenn keine Datei hineingehoert.
    **Ueberschrieben wird nichts**: was am Ziel schon liegt, wird gezaehlt
    und bleibt, wie es ist.
    """
    for fach in plan.faecher:
        try:
            (plan.ordner / fach).mkdir(parents=True, exist_ok=True)
        except OSError as fehler:
            bericht.gruende.append(f"{fach}: {fehler}")
    for quelle, pfad in plan.dateien:
        ziel = plan.ordner / pfad
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


def anlegen(plan: Plan, projekt_fuer) -> Bericht:
    """Schreibt, was geht, und sagt, was nicht ging.

    ``projekt_fuer(angabe)`` baut das Projekt zu einer Zeile: Geometrie
    und Projektdaten kommen von dort, hier wird nur geschrieben. Jede
    Zeile steht fuer sich - **scheitert eine, bleiben die anderen
    stehen**; der Grund kommt in den Bericht.

    **Ohne einen einzigen Verteiler entsteht nichts**, auch kein
    Projektordner und keine Beilage: ein Projekt aus lauter Gruenden ist
    keines. Laesst sich der Projektordner nicht anlegen, ist alles
    Weitere ohnehin vergebens.
    """
    bericht = Bericht()
    for anlage in plan.anlagen:
        if not anlage.geht:
            bericht.gruende.append(_grundsatz(anlage.angabe, anlage.grund))
    moegliche = plan.moegliche
    if not moegliche:
        return bericht
    try:
        plan.ordner.mkdir(parents=True, exist_ok=True)
    except OSError as fehler:
        bericht.gruende.append(f"{plan.ordner}: {fehler}")
        return bericht
    bericht.ordner = plan.ordner
    _beilegen(plan, bericht)
    for anlage in moegliche:
        try:
            anlage.ordner.mkdir(parents=True, exist_ok=True)
            projekt = projekt_fuer(anlage.angabe)
            if not isinstance(projekt, Projekt):
                raise ModellFehler(u("kein Projekt zu dieser Zeile"))
            projektdatei.speichern(projekt, anlage.datei)
        except (OSError, ModellFehler) as fehler:
            bericht.gruende.append(_grundsatz(anlage.angabe, str(fehler)))
            continue
        bericht.dateien.append(anlage.datei)
    return bericht
