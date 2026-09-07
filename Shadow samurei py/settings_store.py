"""Persistente Anwendungseinstellungen (Erscheinungsbild, Fenstergröße, Farbschema).

Gespeichert wird weiterhin als JSON unter ``data/settings.json``; die
Datenhaltung übernimmt der Rust-Kern (:class:`kimi3_kern.Einstellungen`).
Dieses Modul ist nur die dünne, thread-sichere Hülle darüber und liefert für
fehlende Schlüssel wie bisher sinnvolle Standardwerte.
"""
from __future__ import annotations

import os
from typing import Any, Dict

from kern_modul import kern

DATEN_ORDNER = kern.datenordner()
EINSTELLUNGEN_DATEI = kern.datendatei("settings.json")

#: Standardwerte des Kerns. Sie werden aus einem leeren Speicher gelesen,
#: damit es nur eine Quelle für diese Werte gibt.
STANDARD_EINSTELLUNGEN: Dict[str, Any] = kern.Einstellungen(os.devnull).alle()


class Einstellungen:
    """Kleiner, thread-sicherer JSON-Einstellungsspeicher des Kerns."""

    def __init__(self, pfad: str = EINSTELLUNGEN_DATEI):
        self._pfad = pfad
        self._speicher = kern.Einstellungen(pfad)

    # ------------------------------------------------------------------ intern
    @property
    def pfad(self) -> str:
        """Gibt den Pfad der Einstellungsdatei zurück."""
        return self._pfad

    # ------------------------------------------------------------- öffentlich
    def hole(self, schluessel: str, standard: Any = None) -> Any:
        """Gibt einen Einstellungswert zurück."""
        wert = self._speicher.hole(schluessel)
        if wert is None:
            return STANDARD_EINSTELLUNGEN.get(schluessel, standard)
        return wert

    def setze(self, schluessel: str, wert: Any) -> None:
        """Setzt einen Wert und speichert ihn sofort."""
        self._speicher.setze(schluessel, wert)

    def alle(self) -> Dict[str, Any]:
        """Gibt eine Kopie aller Einstellungen zurück."""
        return self._speicher.alle()

    def fenstergroesse(self, breite: int = 1180, hoehe: int = 860) -> tuple[int, int]:
        """Liest die gespeicherte Fenstergröße als Zahlenpaar."""
        gelesen = self._speicher.fenstergroesse(int(breite), int(hoehe))
        return int(gelesen[0]), int(gelesen[1])

    def setze_fenstergroesse(self, breite: int, hoehe: int) -> None:
        """Speichert die aktuelle Fenstergröße."""
        if breite > 200 and hoehe > 200:
            self._speicher.setze_fenstergroesse(int(breite), int(hoehe))

    def zuruecksetzen(self) -> None:
        """Stellt die Standardwerte wieder her."""
        self._speicher.zuruecksetzen()


_einstellungen: Einstellungen | None = None


def hole_einstellungen() -> Einstellungen:
    """Gibt die global genutzte Einstellungs-Instanz zurück."""
    global _einstellungen
    if _einstellungen is None:
        _einstellungen = Einstellungen()
    return _einstellungen
