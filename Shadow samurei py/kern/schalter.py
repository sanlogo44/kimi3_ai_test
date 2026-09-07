"""Die vier globalen Schalter der Weboberfläche.

1. bewertungsmodus  – Antworten dürfen bewertet werden
2. zeige_diagramm   – Metriken werden im Trainingsbereich gezeigt
3. schicht_training – einzelne Schichten gezielt trainieren
4. auto_benchmarks  – wiederkehrende Vergleichsläufe im Hintergrund

Gespeichert wird wie bisher in data/schalter.json. Ältere Dateien mit
englischen Schlüsseln (data/toggles.json) werden weiterhin gelesen.
"""

import json
import os

from .pfade import datendatei, schreibe_atomar


class Schalter:
    """Stellung der vier Schalter, mit Laden und Speichern."""

    _STANDARD = {
        "bewertungsmodus": False,
        "zeige_diagramm": True,
        "schicht_training": False,
        "auto_benchmarks": False,
    }

    _DEUTSCHE_NAMEN = {
        "rate_mode": "bewertungsmodus",
        "show_graph": "zeige_diagramm",
        "layer_training": "schicht_training",
    }

    def __init__(self, pfad):
        self.pfad = pfad
        ordner = os.path.dirname(pfad)
        self._alter_pfad = (
            os.path.join(ordner, "toggles.json") if ordner else "toggles.json"
        )
        self._werte = dict(self._STANDARD)
        self._lade()

    @staticmethod
    def deutscher_name(name):
        """Übersetzt alte englische Schlüssel in die deutschen Namen."""
        return Schalter._DEUTSCHE_NAMEN.get(name, name)

    @classmethod
    def standardpfad(cls):
        """Öffnet den Speicher unter data/schalter.json des Projekts."""
        return cls(datendatei("schalter.json"))

    def _lade(self):
        """Liest die Schalterstellungen; fehlende Werte bleiben auf Standard."""
        quellen = [self.pfad, self._alter_pfad]
        for pfad in quellen:
            try:
                with open(pfad, "r", encoding="utf-8") as f:
                    inhalt = f.read()
                daten = json.loads(inhalt)
                self._uebernimm(daten)
            except (FileNotFoundError, json.JSONDecodeError):
                continue
            break

    def _uebernimm(self, daten):
        """Übernimmt alle bekannten Schalter aus einem JSON-Wörterbuch."""
        if not isinstance(daten, dict):
            return
        for schluessel, wert in daten.items():
            name = self.deutscher_name(schluessel)
            if name not in self._STANDARD:
                continue
            if isinstance(wert, bool):
                wahrheit = wert
            elif isinstance(wert, (int, float)) and not isinstance(wert, bool):
                wahrheit = wert != 0.0
            elif isinstance(wert, str):
                wahrheit = bool(wert) and wert != "false" and wert != "0"
            elif wert is None:
                wahrheit = False
            else:
                wahrheit = True
            self._werte[name] = wahrheit

    def _speichere(self):
        """Schreibt die Schalterstellungen auf die Festplatte."""
        text = json.dumps(self._werte, indent=2, ensure_ascii=False)
        schreibe_atomar(self.pfad, text)

    def hole(self, name):
        """Gibt den Wert eines Schalters über seinen Namen zurück."""
        name = self.deutscher_name(name)
        if name in self._werte:
            return self._werte[name]
        return None

    def hole_alle(self):
        """Gibt alle Schalter als Wörterbuch zurück."""
        return self._werte.copy()

    def setze(self, name, wert):
        """Setzt einen Schalter über seinen Namen."""
        name = self.deutscher_name(name)
        if name in self._STANDARD:
            self._werte[name] = bool(wert)
            self._speichere()

    def zuruecksetzen(self):
        """Stellt die Standardstellung wieder her."""
        self._werte = dict(self._STANDARD)
        self._speichere()
