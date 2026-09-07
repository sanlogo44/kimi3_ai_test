"""Zugriff auf den Python-Kern ``kern``.

Die Logik und Datenhaltung des Projekts – Konfiguration, Protokoll,
Einstellungen, Schalter, Metriken, Bewertungen, Konten, Checkpoints und der
Rechner – liegt im Python-Paket ``kern`` (Ordner ``kern/``). Dieses Modul
kapselt den Import und gibt eine klare deutsche Meldung aus, falls das Paket
nicht geladen werden kann.
"""
from __future__ import annotations

import os
import sys
from types import ModuleType


class KernFehlt(ImportError):
    """Wird ausgelöst, wenn das Paket ``kern`` nicht geladen werden kann."""


def _projektordner() -> str:
    """Gibt den Ordner dieser Datei zurück."""
    return os.path.dirname(os.path.abspath(__file__))


def lade_kern() -> ModuleType:
    """Lädt das Paket ``kern`` und erklärt im Fehlerfall den nächsten Schritt."""
    ordner = _projektordner()
    if ordner not in sys.path:
        sys.path.insert(0, ordner)
    try:
        import kern  # noqa: PLC0415  (bewusst erst hier importiert)
    except ImportError as fehler:  # pragma: no cover – hängt vom Zustand ab
        raise KernFehlt(
            f"Das Python-Paket „kern“ konnte nicht geladen werden.\n"
            f"Bitte sicherstellen, dass der Ordner „kern/“ im Projektordner liegt.\n\n"
            f"Ursprünglicher Fehler: {fehler}"
        ) from fehler
    return kern


# Einmal geladen, überall genutzt.
kern = lade_kern()

__all__ = ["KernFehlt", "kern", "lade_kern"]
