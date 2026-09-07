"""Persistente Verwaltung der Chat-Gespräche.

Alle Gespräche werden gesammelt in ``data/gespraeche.json`` gespeichert,
sodass der Chatverlauf einen Neustart der Anwendung übersteht.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

DATEN_ORDNER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
GESPRAECHE_DATEI = os.path.join(DATEN_ORDNER, "gespraeche.json")

ZEITFORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass
class Nachricht:
    """Eine einzelne Chat-Nachricht."""

    rolle: str            # "benutzer" | "assistent" | "system"
    inhalt: str
    zeitpunkt: str = field(default_factory=lambda: time.strftime(ZEITFORMAT))
    werkzeuge: List[str] = field(default_factory=list)

    def als_dict(self) -> Dict:
        """Gibt die Nachricht als serialisierbares Dictionary zurück."""
        return asdict(self)

    @classmethod
    def aus_dict(cls, daten: Dict) -> "Nachricht":
        """Erzeugt eine Nachricht aus gespeicherten Daten."""
        return cls(
            rolle=daten.get("rolle", "benutzer"),
            inhalt=daten.get("inhalt", ""),
            zeitpunkt=daten.get("zeitpunkt", time.strftime(ZEITFORMAT)),
            werkzeuge=list(daten.get("werkzeuge", [])),
        )


@dataclass
class Gespraech:
    """Ein Gespräch mit Titel und zugehörigen Nachrichten."""

    kennung: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    titel: str = "Neues Gespräch"
    erstellt: str = field(default_factory=lambda: time.strftime(ZEITFORMAT))
    geaendert: str = field(default_factory=lambda: time.strftime(ZEITFORMAT))
    nachrichten: List[Nachricht] = field(default_factory=list)

    def fuege_hinzu(self, rolle: str, inhalt: str, werkzeuge: Optional[List[str]] = None) -> Nachricht:
        """Fügt eine Nachricht an und aktualisiert Titel und Zeitstempel."""
        nachricht = Nachricht(rolle=rolle, inhalt=inhalt, werkzeuge=list(werkzeuge or []))
        self.nachrichten.append(nachricht)
        self.geaendert = nachricht.zeitpunkt
        if rolle == "benutzer" and self.titel == "Neues Gespräch":
            self.titel = self._titel_aus_text(inhalt)
        return nachricht

    @staticmethod
    def _titel_aus_text(text: str) -> str:
        """Leitet einen kurzen Gesprächstitel aus der ersten Frage ab."""
        einzeilig = " ".join(text.split())
        return (einzeilig[:38] + "...") if len(einzeilig) > 38 else (einzeilig or "Neues Gespräch")

    @property
    def vorschau(self) -> str:
        """Kurze Vorschau der letzten Nachricht."""
        if not self.nachrichten:
            return "Noch keine Nachrichten"
        einzeilig = " ".join(self.nachrichten[-1].inhalt.split())
        return (einzeilig[:44] + "...") if len(einzeilig) > 44 else einzeilig

    def verlauf_fuer_modell(self, grenze: int = 20) -> List[Dict[str, str]]:
        """Wandelt den Verlauf in das Rollenformat des Sprachmodells um."""
        zuordnung = {"benutzer": "user", "assistent": "assistant", "system": "system"}
        verlauf = [
            {"role": zuordnung.get(n.rolle, "user"), "content": n.inhalt}
            for n in self.nachrichten
            if n.inhalt.strip()
        ]
        return verlauf[-grenze:]

    def als_dict(self) -> Dict:
        """Gibt das Gespräch als serialisierbares Dictionary zurück."""
        return {
            "kennung": self.kennung,
            "titel": self.titel,
            "erstellt": self.erstellt,
            "geaendert": self.geaendert,
            "nachrichten": [n.als_dict() for n in self.nachrichten],
        }

    @classmethod
    def aus_dict(cls, daten: Dict) -> "Gespraech":
        """Erzeugt ein Gespräch aus gespeicherten Daten."""
        return cls(
            kennung=daten.get("kennung", uuid.uuid4().hex[:10]),
            titel=daten.get("titel", "Neues Gespräch"),
            erstellt=daten.get("erstellt", time.strftime(ZEITFORMAT)),
            geaendert=daten.get("geaendert", time.strftime(ZEITFORMAT)),
            nachrichten=[Nachricht.aus_dict(n) for n in daten.get("nachrichten", [])],
        )


class GespraechSpeicher:
    """Lädt und speichert alle Gespräche als JSON-Datei."""

    def __init__(self, pfad: str = GESPRAECHE_DATEI):
        self._pfad = pfad
        self._gespraeche: List[Gespraech] = []
        self._laden()

    # ------------------------------------------------------------------ intern
    def _laden(self) -> None:
        """Liest gespeicherte Gespräche ein."""
        if not os.path.exists(self._pfad):
            return
        try:
            with open(self._pfad, "r", encoding="utf-8") as datei:
                rohdaten = json.load(datei)
            self._gespraeche = [Gespraech.aus_dict(d) for d in rohdaten]
        except (OSError, json.JSONDecodeError, TypeError):
            self._gespraeche = []

    def speichern(self) -> None:
        """Schreibt alle Gespräche auf die Festplatte."""
        os.makedirs(os.path.dirname(self._pfad), exist_ok=True)
        temp_pfad = self._pfad + ".tmp"
        with open(temp_pfad, "w", encoding="utf-8") as datei:
            json.dump([g.als_dict() for g in self._gespraeche], datei, indent=2, ensure_ascii=False)
        os.replace(temp_pfad, self._pfad)

    # ------------------------------------------------------------- öffentlich
    def alle(self) -> List[Gespraech]:
        """Gibt alle Gespräche, neueste zuerst, zurück."""
        return sorted(self._gespraeche, key=lambda g: g.geaendert, reverse=True)

    def neues(self) -> Gespraech:
        """Erstellt ein neues, leeres Gespräch."""
        gespraech = Gespraech()
        self._gespraeche.append(gespraech)
        self.speichern()
        return gespraech

    def hole(self, kennung: str) -> Optional[Gespraech]:
        """Sucht ein Gespräch anhand seiner Kennung."""
        for gespraech in self._gespraeche:
            if gespraech.kennung == kennung:
                return gespraech
        return None

    def loesche(self, kennung: str) -> bool:
        """Löscht ein Gespräch."""
        vorher = len(self._gespraeche)
        self._gespraeche = [g for g in self._gespraeche if g.kennung != kennung]
        if len(self._gespraeche) != vorher:
            self.speichern()
            return True
        return False

    def benenne_um(self, kennung: str, titel: str) -> bool:
        """Ändert den Titel eines Gesprächs."""
        gespraech = self.hole(kennung)
        if not gespraech or not titel.strip():
            return False
        gespraech.titel = titel.strip()[:60]
        self.speichern()
        return True

    def leeren(self) -> None:
        """Löscht alle Gespräche."""
        self._gespraeche = []
        self.speichern()
