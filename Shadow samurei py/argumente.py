"""Kleine Hilfen für deutschsprachige Kommandozeilen-Hilfetexte.

``argparse`` gibt „usage“ und „options“ standardmäßig auf Englisch aus.
Diese Funktion setzt beide Überschriften auf deutsche Begriffe.
"""
from __future__ import annotations

import argparse


def deutscher_zerleger(**angaben) -> argparse.ArgumentParser:
    """Erzeugt einen Argument-Zerleger mit deutschen Überschriften."""
    angaben.setdefault("add_help", False)
    zerleger = argparse.ArgumentParser(**angaben)
    zerleger._optionals.title = "Optionen"
    if zerleger._positionals is not None:
        zerleger._positionals.title = "Argumente"
    zerleger.add_argument(
        "-h", "--hilfe", "--help",
        action="help",
        help="Diese Hilfe anzeigen und beenden",
    )
    return zerleger


class _DeutscheHilfe(argparse.HelpFormatter):
    """Ersetzt die Überschrift „usage“ durch „Aufruf“."""

    def add_usage(self, usage, actions, groups, prefix=None):
        super().add_usage(usage, actions, groups, prefix or "Aufruf: ")
