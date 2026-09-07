"""Dauerhafte Anwendungseinstellungen in data/settings.json.

Format und Standardwerte entsprechen der bisherigen Python-Fassung
(settings_store.py), damit vorhandene Dateien weiter gelten.
"""

import json

from .pfade import datendatei, schreibe_atomar


def _standardwerte():
    """Standardwerte für alle Einstellungen."""
    return {
        "erscheinungsbild": "System",
        "farbschema": "blue",
        "fenstergroesse": "1180x860",
        "letzter_benutzer": "",
        "widget_skalierung": 1.0,
    }


class Einstellungen:
    """Kleiner Einstellungsspeicher auf JSON-Basis."""

    def __init__(self, pfad):
        self.pfad = pfad
        self._werte = _standardwerte()
        try:
            with open(pfad, "r", encoding="utf-8") as f:
                inhalt = f.read()
            gespeichert = json.loads(inhalt)
            if isinstance(gespeichert, dict):
                for schluessel, wert in gespeichert.items():
                    self._werte[schluessel] = wert
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    @classmethod
    def standardpfad(cls):
        """Öffnet den Speicher unter data/settings.json des Projekts."""
        return cls(datendatei("settings.json"))

    def _speichere(self):
        text = json.dumps(self._werte, indent=2, ensure_ascii=False)
        schreibe_atomar(self.pfad, text)

    def hole(self, schluessel):
        """Gibt einen Wert zurück; fehlt er, gilt der Standardwert."""
        if schluessel in self._werte:
            return self._werte[schluessel]
        standard = _standardwerte()
        if schluessel in standard:
            return standard[schluessel]
        return None

    def text(self, schluessel, ersatz=""):
        """Gibt einen Wert als Text zurück."""
        wert = self.hole(schluessel)
        if isinstance(wert, str):
            return wert if wert else ersatz
        if wert is None:
            return ersatz
        text = str(wert)
        return text if text else ersatz

    def setze(self, schluessel, wert):
        """Setzt einen Wert und speichert ihn sofort."""
        self._werte[schluessel] = wert
        self._speichere()

    def alle(self):
        """Gibt eine Kopie aller Einstellungen zurück."""
        return self._werte.copy()

    def fenstergroesse(self, breite, hoehe):
        """Liest die gespeicherte Fenstergröße als Zahlenpaar.

        Die Untergrenzen (900 × 620) entsprechen der Python-Fassung.
        """
        wert = self.text("fenstergroesse", f"{breite}x{hoehe}")
        vorne = wert.split("+")[0].lower()
        teile = vorne.split("x")
        try:
            b = int(teile[0].strip())
            h = int(teile[1].strip())
            return (max(b, 900), max(h, 620))
        except (ValueError, IndexError):
            return (breite, hoehe)

    def setze_fenstergroesse(self, breite, hoehe):
        """Speichert die aktuelle Fenstergröße."""
        if breite > 200 and hoehe > 200:
            self.setze("fenstergroesse", f"{breite}x{hoehe}")

    def zuruecksetzen(self):
        """Stellt alle Standardwerte wieder her."""
        self._werte = _standardwerte()
        self._speichere()
