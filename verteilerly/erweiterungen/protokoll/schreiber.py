"""Der Schreiber des Protokolls - eine Zeile je Ereignis, ohne Qt.

Das Protokoll ist eine gewoehnliche Textdatei im Arbeitsordner. Jede
Zeile beginnt mit Zeitpunkt und Art, dahinter steht der Satz; ein
Fehlerbericht haengt eingerueckt darunter, damit er als ein Stueck
lesbar bleibt.

**Ein Protokoll darf das Programm nie aufhalten.** Laesst sich nicht
schreiben - volle Platte, keine Rechte, Ordner weg -, merkt sich der
Schreiber den Grund und schweigt; gearbeitet wird weiter.
"""

from __future__ import annotations

import datetime as _datetime
import pathlib

#: Wie gross die Datei werden darf, bevor die aelteste Haelfte weicht.
#: Gross genug fuer die Vorgeschichte eines Fehlers, klein genug, dass
#: sie niemandem den Arbeitsordner vollschreibt.
HOECHSTENS = 200_000

#: Die Arten, die in der zweiten Spalte stehen koennen.
START, EREIGNIS, FEHLER = "START", "EREIGNIS", "FEHLER"


class Schreiber:
    """Schreibt Zeilen in die Protokolldatei und haelt sie in Grenzen."""

    def __init__(self, datei: pathlib.Path, hoechstens: int = HOECHSTENS) -> None:
        self.datei = pathlib.Path(datei)
        self.hoechstens = hoechstens
        #: Warum zuletzt nicht geschrieben werden konnte - der Dialog
        #: zeigt es, statt dass es niemand erfaehrt.
        self.letzter_fehler = ""

    # -- Schreiben -----------------------------------------------------------

    def schreiben(self, art: str, text: str, bericht: str = "") -> bool:
        """Haengt eine Zeile an; ``bericht`` kommt eingerueckt darunter.

        Zurueck kommt, ob es geklappt hat - geworfen wird nie.
        """
        zeile = f"{self._zeitpunkt()}  {art:<8}  {self._einzeilig(text)}\n"
        if bericht:
            zeile += "".join(
                f"    {stueck}\n" for stueck in bericht.rstrip().splitlines()
            )
        try:
            self.datei.parent.mkdir(parents=True, exist_ok=True)
            with open(self.datei, "a", encoding="utf-8") as offen:
                offen.write(zeile)
            self._stutzen()
        except OSError as fehler:
            self.letzter_fehler = f"{type(fehler).__name__}: {fehler}"
            return False
        self.letzter_fehler = ""
        return True

    def lesen(self) -> str:
        """Der ganze Inhalt - oder eine leere Zeichenkette."""
        try:
            return self.datei.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def leeren(self) -> bool:
        """Wirft das Bisherige weg und faengt neu an."""
        try:
            self.datei.unlink(missing_ok=True)
        except OSError as fehler:
            self.letzter_fehler = f"{type(fehler).__name__}: {fehler}"
            return False
        return True

    # -- Innen ---------------------------------------------------------------

    @staticmethod
    def _zeitpunkt() -> str:
        return _datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _einzeilig(text: str) -> str:
        """Ein Ereignis ist eine Zeile - Umbrueche wuerden die Spalten sprengen."""
        return " ".join(str(text).split())

    def _stutzen(self) -> None:
        """Haelt die Datei unter der Grenze: die juengere Haelfte bleibt.

        Geschnitten wird an einem Zeilenanfang, damit kein halber Satz
        oben steht; die erste Zeile sagt, dass etwas fehlt.
        """
        try:
            groesse = self.datei.stat().st_size
        except OSError:
            return
        if groesse <= self.hoechstens:
            return
        inhalt = self.datei.read_bytes()[-(self.hoechstens // 2):]
        stelle = inhalt.find(b"\n")
        if stelle >= 0:
            inhalt = inhalt[stelle + 1:]
        kopf = f"{self._zeitpunkt()}  {EREIGNIS:<8}  [Älteres gekürzt]\n"
        self.datei.write_bytes(kopf.encode("utf-8") + inhalt)
