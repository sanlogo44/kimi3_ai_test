"""Brücke zum Modellkern in Python.

Alles, was PyTorch braucht, bleibt Python. Die Weboberfläche startet dazu
einmalig den Prozess ``python3 kern_bruecke.py`` und tauscht mit ihm
zeilenweise JSON aus:

    Anfrage:  {"befehl": "<name>", "daten": {...}}
    Antwort:  {"ok": true, "daten": {...}}
              {"ok": false, "fehler": "...", "status": N}

Weil der Prozess läuft, solange der Server läuft, behält er sein Arbeitsmodell
und die Hintergrund-Benchmarks. Fehlt PyTorch, antwortet die Brücke mit
Status 503.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
from typing import Any

import kern


class BrueckenFehler(Exception):
    """Fehler mit einer deutschen Meldung und einem HTTP-Status."""

    def __init__(self, meldung: str, status: int = 500):
        super().__init__(meldung)
        self.meldung = meldung
        self.status = status


def _projektordner() -> str:
    """Gibt den Projektordner zurück."""
    return kern.pfade.projektordner()


class Bruecke:
    """Verbindung zum Modellkern in Python."""

    def __init__(self) -> None:
        self.programm = os.environ.get("PYTHON", "python3")
        self.skript = os.path.join(_projektordner(), "kern_bruecke.py")
        self.arbeitsordner = _projektordner()
        self._prozess: subprocess.Popen | None = None
        self._sperre = threading.Lock()
        self._kern_fehler: str | None = None

    def kern_fehler(self) -> str | None:
        """Gibt den zuletzt gemeldeten Grund für einen fehlenden Kern zurück."""
        with self._sperre:
            return self._kern_fehler

    def _starte(self) -> None:
        """Startet den Python-Prozess, falls er nicht läuft."""
        if self._prozess is not None and self._prozess.poll() is None:
            return
        # Alten Prozess aufräumen
        if self._prozess is not None:
            self._prozess = None
        if not os.path.isfile(self.skript):
            raise BrueckenFehler(
                f"Die Brücke zum Modellkern fehlt ({self.skript}).", 503
            )
        try:
            self._prozess = subprocess.Popen(
                [self.programm, self.skript],
                cwd=self.arbeitsordner,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=None,  # stderr erben
            )
        except OSError as fehler:
            raise BrueckenFehler(
                f"Python konnte nicht gestartet werden ({fehler}). "
                "Bitte „pip install -r requirements.txt“ ausführen.",
                503,
            )

    def rufe(self, befehl: str, daten: Any = None) -> Any:
        """Schickt einen Befehl und wartet auf die Antwort."""
        if daten is None:
            daten = {}
        with self._sperre:
            self._starte()
            ergebnis = self._rufe_intern(befehl, daten)
            if isinstance(ergebnis, BrueckenFehler):
                # Nach einem Abbruch der Verbindung den Prozess verwerfen
                if ergebnis.status == 503 and "antwortet nicht" in ergebnis.meldung:
                    self._beende_prozess()
                if ergebnis.status == 503:
                    self._kern_fehler = ergebnis.meldung
                raise ergebnis
            self._kern_fehler = None
            return ergebnis

    def _rufe_intern(self, befehl: str, daten: Any) -> Any:
        """Führt den Austausch einer Zeile durch."""
        if self._prozess is None or self._prozess.poll() is not None:
            return BrueckenFehler(
                "Die Brücke zum Modellkern antwortet nicht.", 503
            )
        anfrage = json.dumps(
            {"befehl": befehl, "daten": daten}, ensure_ascii=False
        )
        try:
            assert self._prozess.stdin is not None
            self._prozess.stdin.write((anfrage + "\n").encode("utf-8"))
            self._prozess.stdin.flush()
        except (BrokenPipeError, OSError):
            return BrueckenFehler(
                "Die Brücke zum Modellkern antwortet nicht.", 503
            )
        assert self._prozess.stdout is not None
        antwort = self._prozess.stdout.readline()
        if not antwort:
            return BrueckenFehler(
                "Die Brücke zum Modellkern antwortet nicht.", 503
            )
        return deute_antwort(antwort.decode("utf-8"))

    def _beende_prozess(self) -> None:
        """Beendet den Prozess, falls er läuft."""
        if self._prozess is not None:
            try:
                if self._prozess.stdin is not None:
                    self._prozess.stdin.close()
            except Exception:
                pass
            try:
                self._prozess.terminate()
                self._prozess.wait(timeout=2)
            except Exception:
                try:
                    self._prozess.kill()
                except Exception:
                    pass
            self._prozess = None

    def beende(self) -> None:
        """Beendet den Prozess, falls er läuft."""
        with self._sperre:
            self._beende_prozess()


def deute_antwort(zeile: str) -> Any:
    """Wertet eine Antwortzeile der Brücke aus."""
    zeile = zeile.strip()
    try:
        wert = json.loads(zeile)
    except (ValueError, TypeError):
        raise BrueckenFehler(
            "Die Brücke zum Modellkern hat unklar geantwortet.", 500
        )
    if not isinstance(wert, dict):
        raise BrueckenFehler(
            "Die Brücke zum Modellkern hat unklar geantwortet.", 500
        )
    if wert.get("ok") is True:
        return wert.get("daten", {})
    status = wert.get("status", 500)
    if not isinstance(status, int):
        status = 500
    meldung = wert.get("fehler", "Unbekannter Fehler im Modellkern.")
    if not isinstance(meldung, str):
        meldung = "Unbekannter Fehler im Modellkern."
    raise BrueckenFehler(meldung, status)
