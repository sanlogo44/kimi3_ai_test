"""Zugriff auf den Rust-Kern ``kimi3_kern``.

Die Logik und Datenhaltung des Projekts – Konfiguration, Protokoll,
Einstellungen, Schalter, Metriken, Bewertungen, Konten, Checkpoints und der
Rechner – liegt in Rust (Ordner ``rust/``). Python nutzt sie über das
Erweiterungsmodul ``kimi3_kern``.

Dieses Modul kapselt den Import und gibt eine klare deutsche Meldung aus,
wenn das Modul noch nicht gebaut wurde.
"""
from __future__ import annotations

import os
import sys
from types import ModuleType

# Hinweis, der bei fehlendem Modul angezeigt wird.
BAUHINWEIS = (
    "Der Rust-Kern „kimi3_kern“ wurde nicht gefunden.\n"
    "Bitte einmal bauen:\n"
    "    bash rust/bauen.sh\n"
    "Dafür wird Rust benötigt (https://rustup.rs)."
)


class KernFehlt(ImportError):
    """Wird ausgelöst, wenn ``kimi3_kern`` nicht gebaut wurde."""


def _projektordner() -> str:
    """Gibt den Ordner dieser Datei zurück."""
    return os.path.dirname(os.path.abspath(__file__))


def lade_kern() -> ModuleType:
    """Lädt ``kimi3_kern`` und erklärt im Fehlerfall den nächsten Schritt."""
    ordner = _projektordner()
    if ordner not in sys.path:
        sys.path.insert(0, ordner)
    try:
        import kimi3_kern  # noqa: PLC0415  (bewusst erst hier importiert)
    except ImportError as fehler:  # pragma: no cover – hängt vom Bauzustand ab
        raise KernFehlt(f"{BAUHINWEIS}\n\nUrsprünglicher Fehler: {fehler}") from fehler
    return kimi3_kern


# Einmal geladen, überall genutzt.
kern = lade_kern()

__all__ = ["BAUHINWEIS", "KernFehlt", "kern", "lade_kern"]
