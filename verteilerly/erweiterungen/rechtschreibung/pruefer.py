"""Die Texte des Verteilers von LanguageTool pruefen lassen.

Hier steht kein Qt: welche Texte es gibt, wie sie zu einer Anfrage
werden und was aus der Antwort zu lesen ist, laesst sich damit ohne
Fenster und ohne Netz pruefen - die Testreihe gibt eine fertige Antwort
herein (``abrufen=``).

**Welche Texte.** Die des Anwenders, also Bezeichnung und Bemerkung der
Adern, die Kabelbeschriftungen und die Projektdaten; der Rundgang ist
der der Suche (``suche.textstellen``). Farbe und Rangierfeld bleiben
draussen: ``rt/bl`` und ``L3-2a`` sind keine Woerter, und eine
Rechtschreibpruefung, die jede Aderfarbe anstreicht, liest niemand zu
Ende. Aus demselben Grund bleibt ein Text ohne ein einziges Wort von
drei Buchstaben draussen (``V-01``, ``12k``).

**Eine Anfrage je Buendel, nicht je Zelle.** Ein Verteiler hat hunderte
kurzer Texte; hunderte Anfragen waeren langsam und brennten jedes
Anfragekontingent nieder. Die Texte gehen darum durch Leerzeilen
getrennt zusammen ueber die Leitung, und ``befunde_aus()`` rechnet die
Stellen der Antwort wieder in die einzelne Zelle zurueck. Was ueber eine
Grenze hinweg beanstandet wird, faellt weg - es gehoert keiner Zelle.

**Wohin die Texte gehen, entscheidet der Anwender.** ``SERVER`` ist der
oeffentliche Dienst; wer seine Verteiler nicht aus dem Haus geben will,
traegt einen eigenen LanguageTool-Server ein. ``oeffentlich()`` sagt,
welcher Fall vorliegt - die Oberflaeche fragt danach, bevor zum ersten
Mal etwas hinausgeht.
"""

from __future__ import annotations

import bisect
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from ... import suche
from ...aktualisierung import umgebung
from ...modell import Projekt
from ...schreibweisen import Schreibweise
from ...sprachen import u
from ...suche import Fundstelle
from ...version import VERSION

#: Der oeffentliche Dienst. Ein eigener Server steht etwa unter
#: ``http://localhost:8081/v2/check``.
SERVER = "https://api.languagetool.org/v2/check"

#: Die Sprache der Texte. ``auto`` laesst LanguageTool raten - bei
#: kurzen Zellen raet es oft daneben, darum ist Deutsch die Vorgabe.
SPRACHE = "de-DE"
SPRACHEN = ("de-DE", "de-AT", "de-CH", "en-GB", "en-US", "auto")

#: Lieber eine Anfrage mehr als eine, die der Dienst ablehnt: der
#: oeffentliche nimmt 20 000 Zeichen je Anfrage.
ZEICHEN_JE_ANFRAGE = 8000
#: Was zwischen zwei Zellen steht. Eine Leerzeile ist fuer LanguageTool
#: das Ende eines Absatzes - so wird aus zwei Zellen kein Satz.
TRENNER = "\n\n"
#: Pruefen dauert laenger als eine Fassung nachzuschlagen.
WARTEZEIT = 30.0
#: Mehr Vorschlaege als diese traegt keine Liste.
VORSCHLAEGE = 5

#: Welche Felder der Ader gelesen werden - die mit Worten darin.
PRUEFFELDER = ("bezeichnung", "bemerkung")

#: Ein Wort, an dem sich etwas pruefen laesst: drei Buchstaben am Stueck.
_WORT = re.compile(r"[^\W\d_]{3,}")


class PruefFehler(Exception):
    """Der Server war nicht zu erreichen oder antwortete unverstaendlich."""


@dataclass(frozen=True)
class Befund:
    """Eine Beanstandung an einer Stelle des Projekts.

    ``von`` und ``laenge`` zeigen in den Text **der Zelle**, nicht in
    den, der ueber die Leitung ging - sonst liesse sich nichts
    uebernehmen.
    """

    stelle: Fundstelle
    von: int
    laenge: int
    meldung: str
    vorschlaege: tuple[str, ...] = ()
    regel: str = ""
    art: str = ""

    @property
    def wort(self) -> str:
        """Was beanstandet wird - wie es in der Zelle steht."""
        return self.stelle.text[self.von:self.von + self.laenge]

    def __str__(self) -> str:
        return f"{self.stelle.ort} · {self.wort}: {self.meldung}"


def pruefenswert(text: str) -> bool:
    """Steht in diesem Text ueberhaupt ein Wort?"""
    return bool(_WORT.search(text or ""))


def zu_pruefen(
    projekt: Projekt, schreibweise: Schreibweise | None = None
) -> list[Fundstelle]:
    """Die Stellen, deren Text eine Rechtschreibpruefung verdient."""
    return [
        stelle for stelle in suche.textstellen(projekt, schreibweise)
        if _gehoert_dazu(stelle) and pruefenswert(stelle.text)
    ]


def _gehoert_dazu(stelle: Fundstelle) -> bool:
    if stelle.bereich == suche.ADER:
        return stelle.feld in PRUEFFELDER
    return stelle.bereich in (suche.KABEL, suche.PROJEKTDATEN)


def buendel(
    stellen: list[Fundstelle], hoechstens: int = ZEICHEN_JE_ANFRAGE
) -> list[list[Fundstelle]]:
    """Die Stellen in Haeppchen, die je in eine Anfrage passen.

    Eine Zelle wird nicht zerteilt: ist sie allein schon zu lang, geht
    sie allein hinaus - der Server soll entscheiden, nicht wir.
    """
    gebuendelt: list[list[Fundstelle]] = []
    laufend: list[Fundstelle] = []
    laenge = 0
    for stelle in stellen:
        braucht = len(stelle.text) + len(TRENNER)
        if laufend and laenge + braucht > hoechstens:
            gebuendelt.append(laufend)
            laufend, laenge = [], 0
        laufend.append(stelle)
        laenge += braucht
    if laufend:
        gebuendelt.append(laufend)
    return gebuendelt


def zusammenlegen(stellen: list[Fundstelle]) -> tuple[str, list[int]]:
    """Ein Text aus vielen Zellen - und wo jede darin anfaengt."""
    starts: list[int] = []
    stelle_im_text = 0
    for stelle in stellen:
        starts.append(stelle_im_text)
        stelle_im_text += len(stelle.text) + len(TRENNER)
    return TRENNER.join(stelle.text for stelle in stellen), starts


def befunde_aus(
    antwort: dict, stellen: list[Fundstelle], starts: list[int]
) -> list[Befund]:
    """Was LanguageTool gemeldet hat, auf die Zellen zurueckgerechnet."""
    gefunden: list[Befund] = []
    for treffer in antwort.get("matches") or []:
        try:
            von = int(treffer.get("offset"))
            laenge = int(treffer.get("length"))
        except (TypeError, ValueError):
            continue
        nummer = bisect.bisect_right(starts, von) - 1
        if nummer < 0:
            continue
        stelle = stellen[nummer]
        innen = von - starts[nummer]
        if innen < 0 or innen + laenge > len(stelle.text):
            # Ueber die Grenze hinaus - das gehoert keiner Zelle.
            continue
        regel = treffer.get("rule") or {}
        gefunden.append(Befund(
            stelle=stelle,
            von=innen,
            laenge=laenge,
            meldung=str(treffer.get("message") or "").strip(),
            vorschlaege=tuple(
                str(vorschlag.get("value", "")).strip()
                for vorschlag in (treffer.get("replacements") or [])[:VORSCHLAEGE]
                if str(vorschlag.get("value", "")).strip()
            ),
            regel=str(regel.get("id") or ""),
            art=str(regel.get("issueType") or ""),
        ))
    return gefunden


def abrufen(
    server: str, text: str, sprache: str, wartezeit: float = WARTEZEIT
) -> dict:
    """Eine Anfrage an LanguageTool - mehr geht nicht hinaus als der Text.

    Keine Kennung, kein Wortspeicher, keine Vorlieben: gesendet werden
    der Text und die Sprache.
    """
    daten = urllib.parse.urlencode({"text": text, "language": sprache})
    bitte = urllib.request.Request(
        server,
        data=daten.encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": f"Verteilerly/{VERSION}",
        },
    )
    umfeld = None
    if urllib.parse.urlparse(server).scheme == "https":
        umfeld = umgebung()
        if umfeld is None:
            raise PruefFehler(u(
                "Auf diesem Rechner sind keine Wurzelzertifikate zu finden — "
                "eine gesicherte Verbindung ist damit nicht zu prüfen."
            ))
    try:
        with urllib.request.urlopen(bitte, timeout=wartezeit, context=umfeld) as antwort:
            inhalt = antwort.read()
    except urllib.error.HTTPError as fehler:
        raise PruefFehler(u("Der Server antwortet mit {0}.").format(
            f"{fehler.code} {fehler.reason}"
        )) from fehler
    except Exception as fehler:      # noqa: BLE001 - offline, Zaun, Zeitablauf
        raise PruefFehler(u(
            "Der Server ist nicht zu erreichen ({0}). Bitte prüfen sie die "
            "Internetverbindung oder die Adresse."
        ).format(f"{type(fehler).__name__}: {fehler}")) from fehler
    try:
        return json.loads(inhalt.decode("utf-8"))
    except Exception as fehler:      # noqa: BLE001 - kein LanguageTool dahinter
        raise PruefFehler(u(
            "Die Antwort ist nicht zu lesen — steht unter dieser Adresse ein "
            "LanguageTool-Server?"
        )) from fehler


def pruefen(
    stellen: list[Fundstelle],
    server: str = SERVER,
    sprache: str = SPRACHE,
    abrufen=abrufen,
    hoechstens: int = ZEICHEN_JE_ANFRAGE,
) -> list[Befund]:
    """Alle Stellen pruefen lassen, Buendel fuer Buendel.

    ``abrufen`` ist auswechselbar: die Testreihe gibt eine fertige
    Antwort herein und geht nicht ins Netz.
    """
    befunde: list[Befund] = []
    for teil in buendel(stellen, hoechstens):
        text, starts = zusammenlegen(teil)
        befunde.extend(befunde_aus(abrufen(server, text, sprache), teil, starts))
    return befunde


def oeffentlich(server: str) -> bool:
    """Verlaesst der Text diesen Rechner?

    Alles ausser dem eigenen Rechner gilt als auswaerts - ein Server im
    Hausnetz ebenso wie der oeffentliche Dienst. Wer ihn eingetragen
    hat, weiss, wohin er zeigt; gefragt wird trotzdem, denn die Texte
    stehen danach auf einem fremden Rechner.
    """
    ort = (urllib.parse.urlparse(server).hostname or "").lower()
    return ort not in ("localhost", "127.0.0.1", "::1", "")


# -- Uebernehmen -----------------------------------------------------------


def ersetzt(befund: Befund, ersatz: str) -> str:
    """Der Text der Zelle, mit dem Vorschlag an der beanstandeten Stelle."""
    text = befund.stelle.text
    return text[:befund.von] + ersatz + text[befund.von + befund.laenge:]


def anwenden(projekt: Projekt, befund: Befund, ersatz: str) -> bool:
    """Traegt den Vorschlag dort ein, wo der Text herkommt.

    Zurueck kommt, ob es gelungen ist. Nicht alles laesst sich
    uebernehmen: eine **geteilte Zelle** steht in der Liste als ein Text,
    liegt aber in zwei Feldern - was ueber die Fuge hinweg beanstandet
    wird, muss von Hand gerichtet werden.
    """
    stelle = befund.stelle
    if stelle.bereich == suche.ADER:
        return _in_der_ader(projekt, befund, ersatz)
    if stelle.bereich == suche.KABEL:
        kabel = _kabel_zu(projekt, stelle)
        if kabel is None:
            return False
        kabel.beschriftung = ersetzt(befund, ersatz)
        return True
    if stelle.bereich == suche.PROJEKTDATEN:
        return _in_den_projektdaten(projekt, befund, ersatz)
    return False


def _in_der_ader(projekt: Projekt, befund: Befund, ersatz: str) -> bool:
    stelle = befund.stelle
    if stelle.adresse is None or stelle.feld not in PRUEFFELDER:
        return False
    ader = projekt.verteiler.ader(stelle.adresse)
    vorne = getattr(ader, stelle.feld, "")
    teilung = ader.teilung(stelle.feld)
    if not teilung.text:
        setattr(ader, stelle.feld, ersetzt(befund, ersatz))
        return True

    # In der Liste steht die geteilte Zelle als „links rechts" - und zwar
    # ohne fuehrende Luft. Um welches Feld es geht, sagt die Stelle im
    # zusammengesetzten Text.
    roh = f"{vorne} {teilung.text}"
    versatz = len(roh) - len(roh.lstrip())
    von = befund.von + versatz
    if von + befund.laenge <= len(vorne):
        setattr(ader, stelle.feld, _ersetzt_in(vorne, von, befund.laenge, ersatz))
        return True
    fuge = len(vorne) + 1
    if von >= fuge:
        ader.teilung_setzen(stelle.feld, _teilung_mit(
            teilung, _ersetzt_in(teilung.text, von - fuge, befund.laenge, ersatz)
        ))
        return True
    return False


def _teilung_mit(teilung, text: str):
    from dataclasses import replace

    return replace(teilung, text=text)


def _ersetzt_in(text: str, von: int, laenge: int, ersatz: str) -> str:
    return text[:von] + ersatz + text[von + laenge:]


def _kabel_zu(projekt: Projekt, stelle: Fundstelle):
    """Das Kabel, dessen Beschriftung in der Liste steht."""
    if stelle.adresse is not None:
        kabel = projekt.verteiler.kabel_an(
            stelle.adresse.leiste, stelle.adresse.stift
        )
        if kabel is not None and kabel.beschriftung == stelle.text:
            return kabel
    # Ein Kabel ohne Abschnitt hat keine Adresse - dann hilft der Name.
    return next(
        (k for k in projekt.verteiler.kabel if k.beschriftung == stelle.text), None
    )


def _in_den_projektdaten(projekt: Projekt, befund: Befund, ersatz: str) -> bool:
    feld = befund.stelle.feld
    neu = ersetzt(befund, ersatz)
    if feld == "verteilername":
        projekt.verteiler.name = neu
        return True
    if feld == "verteilernummer":
        projekt.verteiler.nummer = neu
        return True
    if feld in projekt.briefkopf:
        projekt.briefkopf[feld] = neu
        return True
    if feld in projekt.eigene_felder:
        projekt.eigene_felder[feld] = neu
        return True
    return False
