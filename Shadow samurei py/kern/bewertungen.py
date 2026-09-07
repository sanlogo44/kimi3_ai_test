"""Bewertungen einzelner Antworten in data/bewertungen.json.

Eine Bewertung ist 1 (hilfreich), -1 (nicht hilfreich) oder 0
(ohne Bewertung). Alte Dateien (data/feedback.json) und alte
englische Feldnamen werden weiterhin gelesen.
"""

import json
import os

from .pfade import datendatei, schreibe_atomar
from .zeit import jetzt_iso, kurzzeit

#: Längste gespeicherte Textlänge für Frage und Antwort.
HOECHSTLAENGE_TEXT = 1000


def bewertungstext(bewertung):
    """Gibt den Anzeigetext einer Bewertung zurück."""
    if bewertung == 1:
        return "Hilfreich"
    elif bewertung == -1:
        return "Nicht hilfreich"
    else:
        return "Ohne Bewertung"


def _kuerze(text):
    """Kürzt einen Text auf die Höchstlänge."""
    if len(text) <= HOECHSTLAENGE_TEXT:
        return text
    return text[:HOECHSTLAENGE_TEXT]


class BewertungsEintrag:
    """Eine einzelne Bewertung."""

    def __init__(
        self,
        zeitstempel=None,
        modell="unbekannt",
        frage="",
        antwort="",
        bewertung=0,
        markierungen=None,
    ):
        self.zeitstempel = zeitstempel if zeitstempel else jetzt_iso()
        self.modell = modell
        self.frage = frage
        self.antwort = antwort
        self.bewertung = bewertung
        self.markierungen = markierungen if markierungen is not None else []

    @classmethod
    def neu(cls, modell, frage, antwort, bewertung):
        """Erzeugt einen Eintrag; die Texte werden gekürzt."""
        return cls(
            zeitstempel=jetzt_iso(),
            modell="unbekannt" if not modell else modell,
            frage=_kuerze(frage),
            antwort=_kuerze(antwort),
            bewertung=max(-1, min(1, bewertung)),
            markierungen=[],
        )

    @classmethod
    def aus_wert(cls, daten):
        """Liest einen Eintrag aus – auch alten – JSON-Daten."""
        def text(deutsch, englisch, ersatz=""):
            wert = daten.get(deutsch, daten.get(englisch)) if isinstance(daten, dict) else None
            if isinstance(wert, str) and wert:
                return wert
            if wert is None:
                return ersatz
            return str(wert)

        bewertung = 0
        bewertung_wert = daten.get("bewertung", daten.get("rating")) if isinstance(daten, dict) else None
        if isinstance(bewertung_wert, bool) and bewertung_wert:
            bewertung = 1
        elif isinstance(bewertung_wert, (int, float)) and not isinstance(bewertung_wert, bool):
            bewertung = int(bewertung_wert)
        elif isinstance(bewertung_wert, str):
            try:
                bewertung = int(bewertung_wert.strip())
            except ValueError:
                pass

        markierungen = []
        mark_wert = daten.get("markierungen", daten.get("tags")) if isinstance(daten, dict) else None
        if isinstance(mark_wert, list):
            markierungen = [
                m if isinstance(m, str) else str(m) for m in mark_wert
            ]
        elif isinstance(mark_wert, str) and mark_wert:
            markierungen = [mark_wert]

        zeitstempel = text("zeitstempel", "ts", "")
        if not zeitstempel:
            zeitstempel = jetzt_iso()

        return cls(
            zeitstempel=zeitstempel,
            modell=text("modell", "model", "unbekannt"),
            frage=_kuerze(text("frage", "prompt", "")),
            antwort=_kuerze(text("antwort", "response", "")),
            bewertung=max(-1, min(1, bewertung)),
            markierungen=markierungen,
        )

    def als_wert(self):
        """Gibt den Eintrag als JSON-Wert zurück."""
        return {
            "zeitstempel": self.zeitstempel,
            "modell": self.modell,
            "frage": self.frage,
            "antwort": self.antwort,
            "bewertung": self.bewertung,
            "markierungen": self.markierungen,
        }

    def text(self):
        """Gibt den Anzeigetext der Bewertung zurück."""
        return bewertungstext(self.bewertung)

    def kurzzeit(self):
        """Gibt eine kurze, lesbare Zeitangabe zurück."""
        return kurzzeit(self.zeitstempel)


class BewertungsZusammenfassung:
    """Kennzahlen über alle Bewertungen."""

    def __init__(self, gesamt=0, positiv=0, negativ=0, neutral=0, anteil=0.0):
        self.gesamt = gesamt
        self.positiv = positiv
        self.negativ = negativ
        self.neutral = neutral
        self.anteil = anteil

    def als_wert(self):
        return {
            "gesamt": self.gesamt,
            "positiv": self.positiv,
            "negativ": self.negativ,
            "neutral": self.neutral,
            "anteil": self.anteil,
        }


class BewertungsSpeicher:
    """Speichert und wertet Bewertungen aus."""

    def __init__(self, pfad=None):
        if pfad is None:
            pfad = datendatei("bewertungen.json")
        self.pfad = pfad
        ordner = os.path.dirname(pfad)
        self._alter_pfad = (
            os.path.join(ordner, "feedback.json") if ordner else "feedback.json"
        )

    @classmethod
    def standardpfad(cls):
        """Öffnet den Speicher unter data/bewertungen.json des Projekts."""
        return cls(datendatei("bewertungen.json"))

    def hole_alle(self):
        """Gibt alle Bewertungen zurück."""
        quellen = [self.pfad, self._alter_pfad]
        for pfad in quellen:
            try:
                with open(pfad, "r", encoding="utf-8") as f:
                    inhalt = f.read()
            except FileNotFoundError:
                continue
            try:
                liste = json.loads(inhalt)
            except json.JSONDecodeError:
                return []
            if isinstance(liste, list):
                return [
                    BewertungsEintrag.aus_wert(w).als_wert()
                    for w in liste
                    if isinstance(w, dict)
                ]
            return []
        return []

    def _schreibe(self, eintraege):
        """Schreibt alle Bewertungen in die Datei."""
        liste = [
            e.als_wert() if isinstance(e, BewertungsEintrag) else e
            for e in eintraege
        ]
        text = json.dumps(liste, indent=2, ensure_ascii=False)
        schreibe_atomar(self.pfad, text)

    def fuege_hinzu(self, daten):
        """Legt eine Bewertung an und speichert sie."""
        if isinstance(daten, BewertungsEintrag):
            eintrag = daten
        else:
            eintrag = BewertungsEintrag.aus_wert(daten)
        eintraege = [BewertungsEintrag.aus_wert(e) for e in self.hole_alle()]
        eintraege.append(eintrag)
        self._schreibe(eintraege)
        return eintrag.als_wert()

    def fuege_wert_hinzu(self, rohdaten):
        """Legt eine Bewertung aus JSON-Daten an."""
        return self.fuege_hinzu(rohdaten)

    def hole_letzte(self, anzahl):
        """Gibt die letzten anzahl Bewertungen zurück."""
        if anzahl == 0:
            return []
        alle = self.hole_alle()
        return alle[-anzahl:]

    def zusammenfassung(self):
        """Berechnet die Kennzahlen über alle Bewertungen."""
        eintraege = self.hole_alle()
        positiv = sum(1 for e in eintraege if e.get("bewertung", 0) > 0)
        negativ = sum(1 for e in eintraege if e.get("bewertung", 0) < 0)
        neutral = len(eintraege) - positiv - negativ
        bewertet = positiv + negativ
        anteil = positiv / bewertet if bewertet > 0 else 0.0
        return BewertungsZusammenfassung(
            gesamt=len(eintraege),
            positiv=positiv,
            negativ=negativ,
            neutral=neutral,
            anteil=anteil,
        ).als_wert()

    def leere(self):
        """Löscht alle Bewertungen."""
        self._schreibe([])

    @staticmethod
    def bewertungstext(bewertung):
        """Gibt den Anzeigetext einer Bewertung zurück."""
        return bewertungstext(bewertung)
