"""Benchmark-Schnittstelle der Weboberfläche.

Die eigentliche Logik liegt in :mod:`dev_tools.benchmarker`. Dieses Modul
stellt nur die einfachen Start-/Stopp-Funktionen bereit, die die Flask-App
verwendet, und schreibt die Ergebnisse in die gemeinsame Metrikverfolgung.
"""
from __future__ import annotations

from typing import Any

from dev_tools.metrics_tracker import hole_verfolgung

_benchmarker: Any = None


def starte(modellverwaltung, metrik_modul=None, intervall: int = 30) -> bool:
    """Startet wiederkehrende Benchmarks im Hintergrund.

    ``modellverwaltung`` ist das Modul :mod:`model_manager`; ``metrik_modul``
    bleibt aus Rückwärtskompatibilität erhalten und wird ignoriert, da die
    Ergebnisse ohnehin in der gemeinsamen Metrikverfolgung landen.
    """
    global _benchmarker
    if _benchmarker is not None and _benchmarker.laeuft():
        return False
    try:
        from dev_tools.benchmarker import Benchmarker
    except ImportError:
        return False

    _benchmarker = Benchmarker(
        modellfabrik=lambda: modellverwaltung.ToyModel().to(modellverwaltung.DEVICE),
        datenfabrik=modellverwaltung.synthetic_data,
        metrikverfolgung=hole_verfolgung(),
        geraet=modellverwaltung.DEVICE,
    )
    _benchmarker.starte_wiederkehrend(intervall=intervall)
    return True


def stoppe() -> None:
    """Stoppt die wiederkehrenden Benchmarks."""
    if _benchmarker is not None:
        _benchmarker.stoppe()


def laeuft() -> bool:
    """Prüft, ob wiederkehrende Benchmarks laufen."""
    return bool(_benchmarker is not None and _benchmarker.laeuft())


def ergebnisse() -> list[dict[str, Any]]:
    """Gibt die Ergebnisse der laufenden Sitzung zurück."""
    if _benchmarker is None:
        return []
    return [ergebnis.to_dict() for ergebnis in _benchmarker.hole_ergebnisse()]


# Rückwärtskompatible englische Aliasnamen
start = starte
stop = stoppe
is_running = laeuft
