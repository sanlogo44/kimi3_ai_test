"""Gemeinsamer Zustand des Servers und Umwandlung der Kern-Datentypen."""
from __future__ import annotations

import threading
from typing import Any

import kern

from .bruecke import Bruecke
from .sitzung import geheimnis_aus_umgebung
from .vorlagen import (
    Adressen,
    Checkpoint as VorlagenCheckpoint,
    Metrik as VorlagenMetrik,
    Schalter as VorlagenSchalter,
    Zusammenfassung as VorlagenZusammenfassung,
)


def schalter_fuer_seite(schalter: kern.schalter.Schalter) -> VorlagenSchalter:
    """Wandelt die Schalter des Kerns in den Typ der Seitenvorlagen um."""
    return VorlagenSchalter(
        bewertungsmodus=schalter.bewertungsmodus,
        zeige_diagramm=schalter.zeige_diagramm,
        schicht_training=schalter.schicht_training,
        auto_benchmarks=schalter.auto_benchmarks,
    )


def checkpoint_fuer_seite(punkt: kern.checkpoints.Checkpoint) -> VorlagenCheckpoint:
    """Wandelt einen Checkpoint des Kerns in den Typ der Seitenvorlagen um."""
    return VorlagenCheckpoint(
        kennung=punkt.kennung,
        name=punkt.name,
        genauigkeit=punkt.genauigkeit,
        gespeichert_am=punkt.gespeichert_am,
    )


def metrik_fuer_seite(eintrag: kern.metriken.Metrik) -> VorlagenMetrik:
    """Wandelt eine Metrik des Kerns in den Typ der Seitenvorlagen um."""
    return VorlagenMetrik(
        zeitstempel=eintrag.zeitstempel,
        modell=eintrag.modell,
        genauigkeit=eintrag.genauigkeit,
        verlust=eintrag.verlust,
        trainingszeit=eintrag.trainingszeit,
        tokens=eintrag.tokens,
        epochen=eintrag.epochen,
    )


def zusammenfassung_fuer_seite(
    kennzahlen: kern.metriken.Zusammenfassung,
) -> VorlagenZusammenfassung:
    """Wandelt die Kennzahlen des Kerns in den Typ der Seitenvorlagen um."""
    return VorlagenZusammenfassung(
        anzahl=kennzahlen.anzahl,
        beste_genauigkeit=kennzahlen.beste_genauigkeit,
        tokens_gesamt=kennzahlen.tokens_gesamt,
    )


class Zustand:
    """Alles, was die Routen gemeinsam nutzen."""

    def __init__(self) -> None:
        konfiguration = kern.konfiguration.Konfiguration.lade_standardpfad()
        self.schalter_speicher = kern.schalter.SchalterSpeicher.standardpfad()
        self.schalter = self.schalter_speicher.lade()
        self.metriken = kern.metriken.MetrikSpeicher.standardpfad()
        self.bewertungen = kern.bewertungen.BewertungsSpeicher.standardpfad()
        self.standardbenutzer = konfiguration.text(["auth", "default_user"], "Admin")
        self.konten = kern.konten.Kontenverwaltung.aus_konfiguration(konfiguration)
        self.checkpoints = kern.checkpoints.CheckpointOrdner.standardpfad()
        self.bruecke = Bruecke()
        self.benchmarks_laeuft = False
        self.geheimnis = geheimnis_aus_umgebung()
        self._schalter_sperre = threading.Lock()
        self._benchmarks_sperre = threading.Lock()

    def schalter_lesen(self) -> kern.schalter.Schalter:
        """Gibt die aktuelle Schalterstellung zurück."""
        with self._schalter_sperre:
            return self.schalter

    def schalter_aktualisieren(self, daten: Any) -> None:
        """Aktualisiert die Schalterstellung und speichert sie."""
        with self._schalter_sperre:
            self.schalter.uebernimm(daten)
            self.schalter_speicher.speichere(self.schalter)

    def benchmarks_laeuft_lesen(self) -> bool:
        """Laufen die Vergleichsläufe im Hintergrund?"""
        with self._benchmarks_sperre:
            return self.benchmarks_laeuft

    def benchmarks_laeuft_setzen(self, wert: bool) -> None:
        """Setzt den Status der Hintergrund-Benchmarks."""
        with self._benchmarks_sperre:
            self.benchmarks_laeuft = wert

    def auto_benchmarks(self) -> bool:
        """Gibt zurück, ob automatische Benchmarks aktiviert sind."""
        with self._schalter_sperre:
            return self.schalter.auto_benchmarks
