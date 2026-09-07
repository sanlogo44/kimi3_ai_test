"""Metrikschnittstelle der Weboberfläche.

Das Modul ist eine dünne Hülle um :mod:`dev_tools.metrics_tracker` und damit
um die Metrikhaltung des Rust-Kerns (:class:`kimi3_kern.MetrikSpeicher`), damit
Weboberfläche, Desktop-GUI und Entwicklerwerkzeuge dieselben Daten nutzen.
"""
from __future__ import annotations

from typing import Any

from dev_tools.metrics_tracker import MetricEntry, hole_verfolgung


def erfasse(
    modell: str = "unbekannt",
    genauigkeit: float = 0.0,
    trainingszeit: float = 0.0,
    tokens: int = 0,
    epochen: int = 0,
    verlust: float = 0.0,
    markierungen: list[str] | None = None,
    **weitere: Any,
) -> dict[str, Any]:
    """Speichert einen Trainings- oder Auswertungseintrag.

    Englische Schlüsselwörter älterer Aufrufer werden weitergereicht.
    """
    eintrag = hole_verfolgung().add(
        modell=modell,
        genauigkeit=genauigkeit,
        trainingszeit=trainingszeit,
        tokens=tokens,
        epochen=epochen,
        verlust=verlust,
        markierungen=markierungen or ["training"],
        **weitere,
    )
    return eintrag.to_dict()


def alle_metriken() -> list[dict[str, Any]]:
    """Gibt alle gespeicherten Metriken als Wörterbücher zurück."""
    return [eintrag.to_dict() for eintrag in hole_verfolgung().hole_alle()]


def letzte_metriken(anzahl: int = 20) -> list[dict[str, Any]]:
    """Gibt die letzten Metriken als Wörterbücher zurück."""
    return [eintrag.to_dict() for eintrag in hole_verfolgung().hole_letzte(anzahl)]


def zusammenfassung() -> dict[str, Any]:
    """Gibt die Kennzahlen aller Metriken zurück."""
    return hole_verfolgung().zusammenfassung()


def eintraege() -> list[MetricEntry]:
    """Gibt alle Metriken als Datenklassen zurück."""
    return hole_verfolgung().hole_alle()


def leere() -> None:
    """Löscht alle gespeicherten Metriken."""
    hole_verfolgung().leere_verlauf()


# Rückwärtskompatible englische Aliasnamen
record = erfasse
all_metrics = alle_metriken
