"""Tests zur Rechtschreibpruefung.

Ins Netz geht hier nichts: ``pruefen`` bekommt eine fertige Antwort
herein, wie sie ein LanguageTool-Server schickt. Geprueft wird damit,
was das Programm daraus macht - welche Texte ueberhaupt hinausgehen, wie
sie gebuendelt werden, wie die Stellen der Antwort in die einzelne Zelle
zurueckgerechnet werden und ob ein Vorschlag dort landet, wo der Text
herkommt.
"""

from __future__ import annotations

# Erst das Paket: es legt Einstellungs- und Arbeitsordner der
# Testreihe um, bevor etwas aus verteilerly Pfade liest.
from . import TESTHEIM  # noqa: F401

import unittest
from unittest import mock

from verteilerly import suche
from verteilerly.erweiterungen.rechtschreibung import pruefer
from verteilerly.modell import Aderadresse, Projekt, Verteiler, Zellenteilung


def _projekt() -> Projekt:
    v = Verteiler.aus_geometrie(1, 2, 4, name="Hauptverteiler", nummer="V-01")
    v.kabel_anlegen("Melderkreis Halle", 1, 1, 2)
    ader = v.ader(Aderadresse(1, 1, "a"))
    ader.farbe = "ws/bl"
    ader.bezeichnung = "Melder Werkstat"
    ader.bemerkung = "Kontakt prufen"
    v.rangierung_anlegen(Aderadresse(1, 1, "a"), Aderadresse(2, 2, "a"))
    return Projekt(
        verteiler=v,
        briefkopf={"firma": "Musterfirma", "kunde": "Stadtwerke"},
        eigene_felder={"Standort": "Keller"},
    )


def _treffer(offset: int, laenge: int, ersatz="Werkstatt", meldung="Tippfehler"):
    return {
        "offset": offset,
        "length": laenge,
        "message": meldung,
        "replacements": [{"value": ersatz}],
        "rule": {"id": "GERMAN_SPELLER_RULE", "issueType": "misspelling"},
    }


class TestWelcheTexte(unittest.TestCase):
    """Geprueft wird, was jemand geschrieben hat - nicht jede Zelle."""

    def setUp(self):
        self.projekt = _projekt()
        self.stellen = pruefer.zu_pruefen(self.projekt)

    def _felder(self):
        return {(stelle.bereich, stelle.feld) for stelle in self.stellen}

    def test_bezeichnung_und_bemerkung_gehen_mit(self):
        self.assertIn((suche.ADER, "bezeichnung"), self._felder())
        self.assertIn((suche.ADER, "bemerkung"), self._felder())

    def test_farbe_und_rangierung_bleiben_draussen(self):
        """„ws/bl" und „2 2a" sind keine Woerter."""
        self.assertNotIn((suche.ADER, "farbe"), self._felder())
        self.assertNotIn((suche.ADER, "rangierung"), self._felder())

    def test_kabel_und_projektdaten_gehen_mit(self):
        texte = [stelle.text for stelle in self.stellen]
        self.assertIn("Melderkreis Halle", texte)
        self.assertIn("Musterfirma", texte)
        self.assertIn("Keller", texte)

    def test_ein_text_ohne_wort_bleibt_draussen(self):
        """V-01 ist eine Nummer, keine Rechtschreibung."""
        self.assertNotIn("V-01", [stelle.text for stelle in self.stellen])
        self.assertFalse(pruefer.pruefenswert("V-01"))
        self.assertFalse(pruefer.pruefenswert("12k"))
        self.assertTrue(pruefer.pruefenswert("Amt 1"))


class TestBuendel(unittest.TestCase):
    """Eine Anfrage je Buendel - hundert Zellen sind nicht hundert Anfragen."""

    def _stellen(self, *texte):
        return [
            suche.Fundstelle(suche.ADER, "bezeichnung", "Bezeichnung", text, "hier")
            for text in texte
        ]

    def test_was_zusammen_passt_geht_zusammen(self):
        stellen = self._stellen("eins", "zwei", "drei")
        self.assertEqual(len(pruefer.buendel(stellen, 100)), 1)

    def test_voll_ist_voll(self):
        stellen = self._stellen("a" * 30, "b" * 30, "c" * 30)
        gebuendelt = pruefer.buendel(stellen, 70)
        self.assertEqual([len(teil) for teil in gebuendelt], [2, 1])

    def test_eine_lange_zelle_wird_nicht_zerteilt(self):
        stellen = self._stellen("a" * 500, "kurz")
        gebuendelt = pruefer.buendel(stellen, 100)
        self.assertEqual([len(teil) for teil in gebuendelt], [1, 1])

    def test_die_starts_zeigen_auf_den_anfang_jeder_zelle(self):
        stellen = self._stellen("eins", "zwei")
        text, starts = pruefer.zusammenlegen(stellen)
        self.assertEqual(text, "eins\n\nzwei")
        self.assertEqual(starts, [0, 6])
        self.assertEqual(text[starts[1]:starts[1] + 4], "zwei")


class TestAntwortLesen(unittest.TestCase):
    """Die Stellen der Antwort gehoeren in die Zelle zurueck."""

    def setUp(self):
        self.stellen = [
            suche.Fundstelle(suche.ADER, "bezeichnung", "Bezeichnung", t, "hier")
            for t in ("Melder Werkstat", "Kontakt prufen")
        ]
        self.text, self.starts = pruefer.zusammenlegen(self.stellen)

    def test_der_befund_zeigt_in_die_eigene_zelle(self):
        # „prufen" steht in der zweiten Zelle ab deren achtem Zeichen.
        offset = self.starts[1] + 8
        befunde = pruefer.befunde_aus(
            {"matches": [_treffer(offset, 6, "prüfen")]}, self.stellen, self.starts
        )
        self.assertEqual(len(befunde), 1)
        self.assertIs(befunde[0].stelle, self.stellen[1])
        self.assertEqual(befunde[0].wort, "prufen")
        self.assertEqual(befunde[0].vorschlaege, ("prüfen",))
        self.assertEqual(befunde[0].regel, "GERMAN_SPELLER_RULE")

    def test_was_ueber_die_grenze_geht_gehoert_keiner_zelle(self):
        befunde = pruefer.befunde_aus(
            {"matches": [_treffer(len(self.stellen[0].text) - 2, 20)]},
            self.stellen, self.starts,
        )
        self.assertEqual(befunde, [])

    def test_eine_antwort_ohne_treffer_ist_kein_fehler(self):
        self.assertEqual(pruefer.befunde_aus({}, self.stellen, self.starts), [])

    def test_pruefen_geht_durch_alle_buendel(self):
        gefragt = []

        def abrufen(server, text, sprache, wartezeit=0):
            gefragt.append((server, text, sprache))
            # Jedes Buendel faengt mit einem Befund an.
            return {"matches": [_treffer(0, 6, "Melder")]}

        befunde = pruefer.pruefen(
            self.stellen, "http://localhost:8081/v2/check", "de-DE",
            abrufen=abrufen, hoechstens=20,
        )
        self.assertEqual(len(gefragt), 2)       # zwei Buendel, zwei Anfragen
        self.assertEqual(len(befunde), 2)
        self.assertEqual({b.stelle for b in befunde}, set(self.stellen))


class TestWohin(unittest.TestCase):
    """Ob der Text den Rechner verlaesst, entscheidet die Adresse."""

    def test_der_eigene_rechner_ist_nicht_auswaerts(self):
        self.assertFalse(pruefer.oeffentlich("http://localhost:8081/v2/check"))
        self.assertFalse(pruefer.oeffentlich("http://127.0.0.1:8081/v2/check"))

    def test_alles_andere_schon(self):
        self.assertTrue(pruefer.oeffentlich(pruefer.SERVER))
        self.assertTrue(pruefer.oeffentlich("http://sprachserver.intern/v2/check"))


class TestAnfrage(unittest.TestCase):
    """Gesendet werden Text und Sprache - und sonst nichts."""

    def _antwort(self, inhalt=b'{"matches": []}'):
        antwort = mock.MagicMock()
        antwort.read.return_value = inhalt
        antwort.__enter__.return_value = antwort
        return antwort

    def test_text_und_sprache_stehen_im_leib(self):
        with mock.patch.object(pruefer.urllib.request, "urlopen") as geoeffnet:
            geoeffnet.return_value = self._antwort()
            pruefer.abrufen("http://localhost:8081/v2/check", "Melder", "de-DE")
        bitte = geoeffnet.call_args[0][0]
        leib = bitte.data.decode("utf-8")
        self.assertIn("text=Melder", leib)
        self.assertIn("language=de-DE", leib)
        self.assertNotIn("username", leib)

    def test_ohne_server_ein_lesbarer_grund(self):
        with mock.patch.object(
            pruefer.urllib.request, "urlopen", side_effect=OSError("kein Netz")
        ):
            with self.assertRaises(pruefer.PruefFehler) as gefangen:
                pruefer.abrufen("http://localhost:8081/v2/check", "Melder", "de-DE")
        self.assertIn("nicht zu erreichen", str(gefangen.exception))

    def test_eine_fremde_antwort_ist_kein_absturz(self):
        with mock.patch.object(pruefer.urllib.request, "urlopen") as geoeffnet:
            geoeffnet.return_value = self._antwort(b"<html>kein LanguageTool</html>")
            with self.assertRaises(pruefer.PruefFehler):
                pruefer.abrufen("http://localhost:8081/v2/check", "Melder", "de-DE")

    def test_ohne_wurzelzertifikate_wird_nicht_gesendet(self):
        with mock.patch.object(pruefer, "umgebung", lambda: None), \
                mock.patch.object(pruefer.urllib.request, "urlopen") as geoeffnet:
            with self.assertRaises(pruefer.PruefFehler):
                pruefer.abrufen(pruefer.SERVER, "Melder", "de-DE")
        self.assertFalse(geoeffnet.called)


class TestUebernehmen(unittest.TestCase):
    """Der Vorschlag gehoert dorthin, wo der Text herkommt."""

    def setUp(self):
        self.projekt = _projekt()

    def _befund(self, feld: str, wort: str, ersatz: str, bereich=suche.ADER):
        stelle = next(
            s for s in pruefer.zu_pruefen(self.projekt)
            if s.bereich == bereich and s.feld == feld and wort in s.text
        )
        von = stelle.text.index(wort)
        return pruefer.Befund(stelle, von, len(wort), "Tippfehler", (ersatz,))

    def test_in_der_bezeichnung(self):
        befund = self._befund("bezeichnung", "Werkstat", "Werkstatt")
        self.assertTrue(pruefer.anwenden(self.projekt, befund, "Werkstatt"))
        self.assertEqual(
            self.projekt.verteiler.ader(Aderadresse(1, 1, "a")).bezeichnung,
            "Melder Werkstatt",
        )

    def test_im_kabelnamen(self):
        befund = self._befund("kabel", "Halle", "Haus", bereich=suche.KABEL)
        self.assertTrue(pruefer.anwenden(self.projekt, befund, "Haus"))
        self.assertEqual(
            self.projekt.verteiler.kabel[0].beschriftung, "Melderkreis Haus"
        )

    def test_in_den_projektdaten(self):
        befund = self._befund("firma", "Musterfirma", "Musterfabrik",
                              bereich=suche.PROJEKTDATEN)
        self.assertTrue(pruefer.anwenden(self.projekt, befund, "Musterfabrik"))
        self.assertEqual(self.projekt.briefkopf["firma"], "Musterfabrik")

    def test_in_einem_eigenen_feld(self):
        befund = self._befund("Standort", "Keller", "Kessel",
                              bereich=suche.PROJEKTDATEN)
        self.assertTrue(pruefer.anwenden(self.projekt, befund, "Kessel"))
        self.assertEqual(self.projekt.eigene_felder["Standort"], "Kessel")

    def test_in_der_rechten_haelfte_einer_geteilten_zelle(self):
        ader = self.projekt.verteiler.ader(Aderadresse(1, 2, "a"))
        ader.bezeichnung = "Amt 1"
        ader.teilung_setzen("bezeichnung", Zellenteilung(40, "Nst. zwolf"))
        befund = self._befund("bezeichnung", "zwolf", "zwölf")
        self.assertEqual(befund.stelle.text, "Amt 1 Nst. zwolf")
        self.assertTrue(pruefer.anwenden(self.projekt, befund, "zwölf"))
        self.assertEqual(ader.teilung("bezeichnung").text, "Nst. zwölf")
        self.assertEqual(ader.bezeichnung, "Amt 1")

    def test_ueber_die_fuge_hinweg_geht_es_nicht(self):
        """Zwei Felder, ein Text in der Liste - das muss die Hand richten."""
        ader = self.projekt.verteiler.ader(Aderadresse(1, 2, "a"))
        ader.bezeichnung = "Amt"
        ader.teilung_setzen("bezeichnung", Zellenteilung(40, "eins"))
        befund = self._befund("bezeichnung", "Amt eins", "Amt Eins")
        self.assertFalse(pruefer.anwenden(self.projekt, befund, "Amt Eins"))
        self.assertEqual(ader.bezeichnung, "Amt")
        self.assertEqual(ader.teilung("bezeichnung").text, "eins")


if __name__ == "__main__":
    unittest.main()
