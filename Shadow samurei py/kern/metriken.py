"""Metriken der Trainings- und Benchmark-Läufe.

Gespeichert wird als JSON-Liste in data/metriken.json. Alte Dateien
früherer Programmversionen (data/metrics.json,
dev_tools/metrics/training_sessions.jsonl) werden beim ersten Zugriff
einmalig übernommen, ebenso alte englische Feldnamen.
"""

import json
import math
import os

from .pfade import datendatei, schreibe_atomar, stelle_ordner_bereit
from .zeit import jetzt_iso, kurzzeit, lese, vor_tagen


def _deutscher_name(name):
    """Übersetzt alte englische Feldnamen in das deutsche Schema."""
    mapping = {
        "timestamp": "zeitstempel",
        "ts": "zeitstempel",
        "model": "modell",
        "accuracy": "genauigkeit",
        "loss": "verlust",
        "tokens_used": "tokens",
        "train_time_sec": "trainingszeit",
        "train_time": "trainingszeit",
        "epochs": "epochen",
        "epoch": "epochen",
        "batch_size": "stapelgroesse",
        "notes": "notizen",
        "tags": "markierungen",
    }
    return mapping.get(name, name)


def _zahl(wert, ersatz=0.0):
    """Liest eine Zahl robust aus einem JSON-Wert."""
    if isinstance(wert, (int, float)) and not isinstance(wert, bool):
        return float(wert)
    if isinstance(wert, str):
        try:
            return float(wert.strip())
        except ValueError:
            return ersatz
    return ersatz


def _ganzzahl(wert, ersatz=0):
    """Liest eine Ganzzahl robust aus einem JSON-Wert."""
    gelesen = _zahl(wert, float(ersatz))
    if math.isfinite(gelesen):
        return int(gelesen)
    return ersatz


def _text(wert, ersatz=""):
    """Liest einen Text robust aus einem JSON-Wert."""
    if isinstance(wert, str):
        return wert if wert else ersatz
    if wert is None:
        return ersatz
    text = str(wert)
    return text if text else ersatz


class Metrik:
    """Ein einzelner Metrikeintrag."""

    def __init__(
        self,
        modell="unbekannt",
        genauigkeit=0.0,
        verlust=0.0,
        tokens=0,
        trainingszeit=0.0,
        epochen=0,
        stapelgroesse=0,
        hardware="unbekannt",
        notizen="",
        markierungen=None,
        zeitstempel=None,
    ):
        self.modell = modell
        self.genauigkeit = genauigkeit
        self.verlust = verlust
        self.tokens = tokens
        self.trainingszeit = trainingszeit
        self.epochen = epochen
        self.stapelgroesse = stapelgroesse
        self.hardware = hardware
        self.notizen = notizen
        self.markierungen = markierungen if markierungen is not None else []
        self.zeitstempel = zeitstempel if zeitstempel else jetzt_iso()

    @classmethod
    def aus_wert(cls, rohdaten):
        """Erzeugt einen Eintrag aus – auch alten – JSON-Daten."""
        daten = {}
        if isinstance(rohdaten, dict):
            for schluessel, wert in rohdaten.items():
                daten[_deutscher_name(schluessel)] = wert

        markierungen = []
        if isinstance(daten.get("markierungen"), list):
            markierungen = [
                m if isinstance(m, str) else str(m)
                for m in daten["markierungen"]
            ]
        elif isinstance(daten.get("markierungen"), str) and daten["markierungen"]:
            markierungen = [daten["markierungen"]]

        zeitstempel = _text(daten.get("zeitstempel"), "")
        if not zeitstempel:
            zeitstempel = jetzt_iso()

        return cls(
            modell=_text(daten.get("modell"), "unbekannt"),
            genauigkeit=_zahl(daten.get("genauigkeit"), 0.0),
            verlust=_zahl(daten.get("verlust"), 0.0),
            tokens=_ganzzahl(daten.get("tokens"), 0),
            trainingszeit=_zahl(daten.get("trainingszeit"), 0.0),
            epochen=_ganzzahl(daten.get("epochen"), 0),
            stapelgroesse=_ganzzahl(daten.get("stapelgroesse"), 0),
            hardware=_text(daten.get("hardware"), "unbekannt"),
            notizen=_text(daten.get("notizen"), ""),
            markierungen=markierungen,
            zeitstempel=zeitstempel,
        )

    def als_wert(self):
        """Gibt den Eintrag als JSON-Wert zurück."""
        return {
            "modell": self.modell,
            "genauigkeit": self.genauigkeit,
            "verlust": self.verlust,
            "tokens": self.tokens,
            "trainingszeit": self.trainingszeit,
            "epochen": self.epochen,
            "stapelgroesse": self.stapelgroesse,
            "hardware": self.hardware,
            "notizen": self.notizen,
            "markierungen": self.markierungen,
            "zeitstempel": self.zeitstempel,
        }

    def kurzzeit(self):
        """Gibt eine kurze, lesbare Zeitangabe zurück."""
        return kurzzeit(self.zeitstempel)


class Zusammenfassung:
    """Kennzahlen über alle Metrikeinträge."""

    def __init__(
        self,
        anzahl=0,
        beste_genauigkeit=0.0,
        durchschnitt_genauigkeit=0.0,
        durchschnitt_verlust=0.0,
        durchschnitt_zeit=0.0,
        tokens_gesamt=0,
        modelle=0,
        letzter_lauf="-",
    ):
        self.anzahl = anzahl
        self.beste_genauigkeit = beste_genauigkeit
        self.durchschnitt_genauigkeit = durchschnitt_genauigkeit
        self.durchschnitt_verlust = durchschnitt_verlust
        self.durchschnitt_zeit = durchschnitt_zeit
        self.tokens_gesamt = tokens_gesamt
        self.modelle = modelle
        self.letzter_lauf = letzter_lauf

    def als_wert(self):
        return {
            "anzahl": self.anzahl,
            "beste_genauigkeit": self.beste_genauigkeit,
            "durchschnitt_genauigkeit": self.durchschnitt_genauigkeit,
            "durchschnitt_verlust": self.durchschnitt_verlust,
            "durchschnitt_zeit": self.durchschnitt_zeit,
            "tokens_gesamt": self.tokens_gesamt,
            "modelle": self.modelle,
            "letzter_lauf": self.letzter_lauf,
        }


class ModellVergleich:
    """Durchschnittswerte eines einzelnen Modells."""

    def __init__(self, anzahl=0, genauigkeit=0.0, verlust=0.0, zeit=0.0, tokens=0):
        self.anzahl = anzahl
        self.genauigkeit = genauigkeit
        self.verlust = verlust
        self.zeit = zeit
        self.tokens = tokens

    def als_wert(self):
        return {
            "anzahl": self.anzahl,
            "genauigkeit": self.genauigkeit,
            "verlust": self.verlust,
            "zeit": self.zeit,
            "tokens": self.tokens,
        }


class MetrikSpeicher:
    """Speichert und wertet Metrikeinträge aus."""

    def __init__(self, dateipfad):
        self.pfad = dateipfad
        stelle_ordner_bereit(self.pfad)
        if not os.path.exists(self.pfad):
            self._uebernimm_alte_dateien()

    @classmethod
    def standardpfad(cls):
        """Öffnet den Speicher unter data/metriken.json des Projekts."""
        return cls(datendatei("metriken.json"))

    def _uebernimm_alte_dateien(self):
        """Liest Metriken früherer Programmversionen ein."""
        datenordner = os.path.dirname(self.pfad)
        projektordner = os.path.dirname(datenordner)
        alte = [
            os.path.join(datenordner, "metrics.json"),
            os.path.join(projektordner, "dev_tools", "metrics", "training_sessions.jsonl"),
        ]
        eintraege = []
        for pfad in alte:
            try:
                with open(pfad, "r", encoding="utf-8") as f:
                    inhalt = f.read()
            except FileNotFoundError:
                continue
            if pfad.endswith(".jsonl"):
                for zeile in inhalt.splitlines():
                    if not zeile.strip():
                        continue
                    try:
                        wert = json.loads(zeile)
                        eintraege.append(Metrik.aus_wert(wert))
                    except json.JSONDecodeError:
                        pass
            else:
                try:
                    liste = json.loads(inhalt)
                    if isinstance(liste, list):
                        eintraege.extend(Metrik.aus_wert(w) for w in liste)
                except json.JSONDecodeError:
                    pass
        if eintraege:
            self._schreibe(eintraege)

    def _schreibe(self, eintraege):
        """Schreibt alle Einträge in die JSON-Datei."""
        liste = [
            e.als_wert() if isinstance(e, Metrik) else e for e in eintraege
        ]
        text = json.dumps(liste, indent=2, ensure_ascii=False)
        schreibe_atomar(self.pfad, text)

    def hole_alle(self):
        """Gibt alle Einträge in zeitlicher Reihenfolge zurück."""
        try:
            with open(self.pfad, "r", encoding="utf-8") as f:
                inhalt = f.read()
        except FileNotFoundError:
            return []
        try:
            liste = json.loads(inhalt)
        except json.JSONDecodeError:
            return []
        if not isinstance(liste, list):
            return []
        return [
            Metrik.aus_wert(w).als_wert() for w in liste if isinstance(w, dict)
        ]

    def fuege_hinzu(self, daten):
        """Legt einen neuen Eintrag an und speichert ihn."""
        if isinstance(daten, Metrik):
            eintrag = daten
        else:
            eintrag = Metrik.aus_wert(daten)
        eintraege = [Metrik.aus_wert(d) for d in self.hole_alle()]
        eintraege.append(eintrag)
        self._schreibe(eintraege)
        return eintrag.als_wert()

    def fuege_wert_hinzu(self, rohdaten):
        """Legt einen Eintrag aus JSON-Daten an – auch mit alten Feldnamen."""
        return self.fuege_hinzu(rohdaten)

    def hole_letzte(self, anzahl):
        """Gibt die letzten anzahl Einträge zurück."""
        if anzahl == 0:
            return []
        alle = self.hole_alle()
        return alle[-anzahl:]

    def filtere(self, modell=None, markierung=None):
        """Filtert Einträge nach Modellname und/oder Markierung."""
        alle = self.hole_alle()
        result = []
        for eintrag in alle:
            if modell is not None and eintrag.get("modell") != modell:
                continue
            if markierung is not None and markierung not in eintrag.get("markierungen", []):
                continue
            result.append(eintrag)
        return result

    def modelle(self):
        """Gibt alle vorkommenden Modellnamen in ihrer Reihenfolge zurück."""
        gesehen = []
        for eintrag in self.hole_alle():
            modell = eintrag.get("modell", "unbekannt")
            if modell not in gesehen:
                gesehen.append(modell)
        return gesehen

    def zusammenfassung(self):
        """Berechnet die Kennzahlen über alle Einträge."""
        eintraege = self.hole_alle()
        if not eintraege:
            return Zusammenfassung().als_wert()
        anzahl = len(eintraege)
        teiler = float(anzahl)
        modelle = []
        for e in eintraege:
            if e.get("modell") not in modelle:
                modelle.append(e.get("modell"))
        letzter = Metrik.aus_wert(eintraege[-1]).kurzzeit() if eintraege else "-"
        return Zusammenfassung(
            anzahl=anzahl,
            beste_genauigkeit=max(e.get("genauigkeit", 0.0) for e in eintraege),
            durchschnitt_genauigkeit=sum(e.get("genauigkeit", 0.0) for e in eintraege) / teiler,
            durchschnitt_verlust=sum(e.get("verlust", 0.0) for e in eintraege) / teiler,
            durchschnitt_zeit=sum(e.get("trainingszeit", 0.0) for e in eintraege) / teiler,
            tokens_gesamt=sum(e.get("tokens", 0) for e in eintraege),
            modelle=len(modelle),
            letzter_lauf=letzter,
        ).als_wert()

    def vergleich_je_modell(self):
        """Berechnet Durchschnittswerte je Modell."""
        gruppen = {}
        for eintrag in self.hole_alle():
            name = eintrag.get("modell", "unbekannt")
            if name not in gruppen:
                gruppen[name] = []
            gruppen[name].append(eintrag)
        result = {}
        for name, liste in gruppen.items():
            teiler = float(len(liste))
            result[name] = ModellVergleich(
                anzahl=len(liste),
                genauigkeit=sum(e.get("genauigkeit", 0.0) for e in liste) / teiler,
                verlust=sum(e.get("verlust", 0.0) for e in liste) / teiler,
                zeit=sum(e.get("trainingszeit", 0.0) for e in liste) / teiler,
                tokens=sum(e.get("tokens", 0) for e in liste),
            ).als_wert()
        return result

    def exportiere_csv(self, pfad):
        """Schreibt alle Einträge als CSV-Datei (Semikolon als Trennzeichen)."""
        stelle_ordner_bereit(pfad)
        inhalt = (
            "zeitstempel;modell;genauigkeit;verlust;tokens;trainingszeit;"
            "epochen;stapelgroesse;hardware;markierungen;notizen\n"
        )
        for eintrag in self.hole_alle():
            felder = [
                str(eintrag.get("zeitstempel", "")),
                str(eintrag.get("modell", "")),
                str(eintrag.get("genauigkeit", 0.0)),
                str(eintrag.get("verlust", 0.0)),
                str(eintrag.get("tokens", 0)),
                str(eintrag.get("trainingszeit", 0.0)),
                str(eintrag.get("epochen", 0)),
                str(eintrag.get("stapelgroesse", 0)),
                str(eintrag.get("hardware", "")),
                ", ".join(eintrag.get("markierungen", [])),
                str(eintrag.get("notizen", "")),
            ]
            zeile = []
            for feld in felder:
                if ";" in feld or '"' in feld or "\n" in feld:
                    zeile.append('"' + feld.replace('"', '""') + '"')
                else:
                    zeile.append(feld)
            inhalt += ";".join(zeile) + "\n"
        with open(pfad, "w", encoding="utf-8") as f:
            f.write(inhalt)
        return pfad

    def loesche_aelter_als(self, tage):
        """Löscht Einträge, die älter als tage Tage sind; gibt die Anzahl zurück."""
        grenze = vor_tagen(tage)
        eintraege = self.hole_alle()
        behalten = []
        for eintrag in eintraege:
            zeitpunkt = lese(eintrag.get("zeitstempel", ""))
            if zeitpunkt is None or zeitpunkt >= grenze:
                behalten.append(eintrag)
        entfernt = len(eintraege) - len(behalten)
        if entfernt > 0:
            self._schreibe([Metrik.aus_wert(e) for e in behalten])
        return entfernt

    def leere(self):
        """Löscht alle gespeicherten Metriken."""
        self._schreibe([])
