"""Liest config.yaml (oder eine JSON-Datei) und ergänzt fehlende Werte.

Die Standardwerte entsprechen genau der bisherigen Python-Fassung
(config_loader.DEFAULT_CONFIG). Fehlt die Datei oder ist sie defekt,
gelten die Standardwerte und es erscheint ein deutscher Hinweis.
"""

import json
import os

try:
    import yaml
except ImportError:
    yaml = None

from .pfade import projektordner


def standardwerte():
    """Gibt die eingebauten Standardwerte zurück."""
    return {
        "logging": {"level": "INFO", "colored": True, "log_file": None},
        "hardware": {
            "device": "auto",
            "use_4bit": True,
            "use_fp16": True,
            "weights_dtype": "fp32",
        },
        "model": {
            "name": "meta-llama/Meta-Llama-3-8B-Instruct",
            "max_tool_iterations": 5,
        },
        "training": {
            "output_dir": "./tool_model",
            "batch_size": 1,
            "gradient_accumulation_steps": 8,
            "num_epochs": 3,
            "learning_rate": 2e-4,
            "max_length": 2048,
        },
        "auth": {
            "default_user": "Admin",
            "default_password": "1234",
            "force_password_change": True,
        },
        "oberflaeche": {"erscheinungsbild": "System", "farbschema": "kimi"},
    }


def tiefe_zusammenfuehrung(basis, ueberschreibung):
    """Führt zwei Wörterbücher tief zusammen; ueberschreibung gewinnt."""
    if not isinstance(basis, dict) or not isinstance(ueberschreibung, dict):
        return ueberschreibung
    for schluessel, wert in ueberschreibung.items():
        if (
            schluessel in basis
            and isinstance(basis[schluessel], dict)
            and isinstance(wert, dict)
        ):
            basis[schluessel] = tiefe_zusammenfuehrung(basis[schluessel], wert)
        else:
            basis[schluessel] = wert
    return basis


class Konfiguration:
    """Die Konfiguration des Programms."""

    def __init__(self, werte=None):
        if werte is None:
            self.werte = standardwerte()
        else:
            self.werte = werte

    @classmethod
    def lade(cls, pfad):
        """Lädt die Konfiguration aus einer Datei."""
        werte = standardwerte()
        if not os.path.exists(pfad):
            print(f"[INFO] {pfad} nicht gefunden, nutze Standardwerte.")
            return cls(werte)
        endung = os.path.splitext(pfad)[1].lower().lstrip(".")
        try:
            with open(pfad, "r", encoding="utf-8") as f:
                inhalt = f.read()
        except OSError as fehler:
            print(
                f"[WARNUNG] {pfad} konnte nicht gelesen werden ({fehler}), "
                f"nutze Standardwerte."
            )
            return cls(werte)
        if endung in ("yaml", "yml"):
            if yaml is None:
                print(
                    f"[WARNUNG] PyYAML ist nicht installiert, kann {pfad} "
                    f"nicht lesen, nutze Standardwerte."
                )
                return cls(werte)
            try:
                eigene = yaml.safe_load(inhalt)
                if eigene is None:
                    eigene = {}
            except Exception as fehler:
                print(
                    f"[WARNUNG] {pfad} konnte nicht gelesen werden ({fehler}), "
                    f"nutze Standardwerte."
                )
                return cls(werte)
        elif endung == "json":
            try:
                eigene = json.loads(inhalt)
            except Exception as fehler:
                print(
                    f"[WARNUNG] {pfad} konnte nicht gelesen werden ({fehler}), "
                    f"nutze Standardwerte."
                )
                return cls(werte)
        else:
            return cls(werte)
        tiefe_zusammenfuehrung(werte, eigene)
        return cls(werte)

    @classmethod
    def lade_standardpfad(cls):
        """Lädt die Konfiguration aus config.yaml des Projektordners."""
        return cls.lade(os.path.join(projektordner(), "config.yaml"))

    @classmethod
    def aus_wert(cls, eigene):
        """Erzeugt eine Konfiguration aus einem bereits gelesenen Wert."""
        werte = standardwerte()
        tiefe_zusammenfuehrung(werte, eigene)
        return cls(werte)

    def wert(self):
        """Gibt die gesamte Konfiguration zurück."""
        return self.werte

    def abschnitt(self, name):
        """Gibt einen Abschnitt zurück, zum Beispiel logging."""
        teil = self.werte.get(name)
        if isinstance(teil, dict):
            return teil.copy()
        return {}

    def hole(self, pfad):
        """Gibt einen Wert über seinen Pfad zurück, etwa ["auth", "default_user"]."""
        aktuell = self.werte
        for teil in pfad:
            if not isinstance(aktuell, dict) or teil not in aktuell:
                return None
            aktuell = aktuell[teil]
        return aktuell

    def text(self, pfad, ersatz=""):
        """Gibt einen Text zurück oder den Ersatzwert."""
        wert = self.hole(pfad)
        if isinstance(wert, str) and wert:
            return wert
        return ersatz

    def wahrheitswert(self, pfad, ersatz=False):
        """Gibt einen Wahrheitswert zurück oder den Ersatzwert."""
        wert = self.hole(pfad)
        if isinstance(wert, bool):
            return wert
        return ersatz

    def zahl(self, pfad, ersatz=0.0):
        """Gibt eine Zahl zurück oder den Ersatzwert."""
        wert = self.hole(pfad)
        if isinstance(wert, (int, float)) and not isinstance(wert, bool):
            return float(wert)
        return ersatz


def lade_konfiguration(pfad="config.yaml"):
    """Lädt YAML/JSON-Konfiguration mit Standardwerten. Gibt ein dict zurück."""
    return Konfiguration.lade(pfad).wert()
