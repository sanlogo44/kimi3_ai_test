"""Metrikverfolgung für Trainings- und Benchmark-Läufe.

Gespeichert wird weiterhin als JSON-Liste in ``data/metriken.json``; die
Datenhaltung, die Auswertung und die Übernahme älterer Dateien übernimmt der
Rust-Kern (:class:`kimi3_kern.MetrikSpeicher`). Dieses Modul ist nur die dünne
Hülle darüber und stellt die Einträge wie bisher über die Datenklasse
:class:`MetricEntry` bereit.
"""
from __future__ import annotations

import csv
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from kern_modul import kern

PROJEKT_ORDNER = kern.projektordner()
DATEN_ORDNER = kern.datenordner()
METRIK_DATEI = kern.datendatei("metriken.json")

#: Dateien früherer Versionen, aus denen der Kern einmalig übernimmt
ALTE_DATEIEN = (
    os.path.join(DATEN_ORDNER, "metrics.json"),
    os.path.join(PROJEKT_ORDNER, "dev_tools", "metrics", "training_sessions.jsonl"),
)

#: Zuordnung alter englischer Feldnamen auf das deutsche Schema
FELD_ZUORDNUNG = {
    "timestamp": "zeitstempel",
    "ts": "zeitstempel",
    "model": "modell",
    "accuracy": "genauigkeit",
    "loss": "verlust",
    "tokens_used": "tokens",
    "train_time_sec": "trainingszeit",
    "train_time": "trainingszeit",
    "epochs": "epochen",
    "epoch": "epochen",
    "batch_size": "stapelgroesse",
    "notes": "notizen",
    "tags": "markierungen",
}


def _jetzt() -> str:
    """Gibt den aktuellen Zeitstempel als ISO-Text zurück."""
    return kern.jetzt_iso()


def _zahl(wert: Any, ersatz: float = 0.0) -> float:
    """Wandelt einen Wert robust in eine Fließkommazahl."""
    try:
        return float(wert)
    except (TypeError, ValueError):
        return ersatz


def _ganzzahl(wert: Any, ersatz: int = 0) -> int:
    """Wandelt einen Wert robust in eine Ganzzahl."""
    try:
        return int(float(wert))
    except (TypeError, ValueError):
        return ersatz


def _text(wert: Any) -> str:
    """Wandelt einen Wert in Text und erkennt leere Texte des Kerns.

    Der Kern gibt einen leeren gespeicherten Text beim Lesen als die zwei
    Anführungszeichen ``""`` zurück. Hier wird daraus wieder ein leerer Text,
    damit Oberfläche und Auswertung dasselbe sehen wie zuvor.
    """
    if wert is None:
        return ""
    text = str(wert)
    return "" if text == '""' else text


@dataclass
class MetricEntry:
    """Ein einzelner Metrikeintrag eines Trainings- oder Benchmark-Laufs."""

    modell: str = "unbekannt"
    genauigkeit: float = 0.0
    verlust: float = 0.0
    tokens: int = 0
    trainingszeit: float = 0.0
    epochen: int = 0
    stapelgroesse: int = 0
    hardware: str = "unbekannt"
    notizen: str = ""
    markierungen: list[str] = field(default_factory=list)
    zeitstempel: str = field(default_factory=_jetzt)

    # ------------------------------------------------------------- Umwandlung
    def to_dict(self) -> dict[str, Any]:
        """Gibt den Eintrag als Wörterbuch zurück."""
        return asdict(self)

    @classmethod
    def from_dict(cls, rohdaten: dict[str, Any]) -> "MetricEntry":
        """Erzeugt einen Eintrag aus einem – auch alten – Wörterbuch."""
        daten: dict[str, Any] = {}
        for schluessel, wert in (rohdaten or {}).items():
            daten[FELD_ZUORDNUNG.get(schluessel, schluessel)] = wert

        markierungen = daten.get("markierungen") or []
        if isinstance(markierungen, str):
            markierungen = [markierungen]

        return cls(
            modell=_text(daten.get("modell") or "unbekannt") or "unbekannt",
            genauigkeit=_zahl(daten.get("genauigkeit")),
            verlust=_zahl(daten.get("verlust")),
            tokens=_ganzzahl(daten.get("tokens")),
            trainingszeit=_zahl(daten.get("trainingszeit")),
            epochen=_ganzzahl(daten.get("epochen")),
            stapelgroesse=_ganzzahl(daten.get("stapelgroesse")),
            hardware=_text(daten.get("hardware") or "unbekannt") or "unbekannt",
            notizen=_text(daten.get("notizen") or ""),
            markierungen=[str(m) for m in markierungen],
            zeitstempel=_text(daten.get("zeitstempel") or "") or _jetzt(),
        )

    # --------------------------------------------------------------- Anzeige
    @property
    def zeitpunkt(self) -> datetime | None:
        """Gibt den Zeitstempel als ``datetime`` zurück, falls lesbar."""
        for muster in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
            try:
                return datetime.strptime(self.zeitstempel[:26], muster)
            except ValueError:
                continue
        return None

    @property
    def kurzzeit(self) -> str:
        """Gibt eine kurze, lesbare Zeitangabe zurück."""
        return kern.kurzzeit(self.zeitstempel)

    def __str__(self) -> str:  # pragma: no cover - nur Anzeige
        return (
            f"{self.kurzzeit} · {self.modell} · Genauigkeit {self.genauigkeit:.3f} "
            f"· Verlust {self.verlust:.4f}"
        )


class MetricsTracker:
    """Speichert und wertet Metrikeinträge über den Kern aus."""

    def __init__(self, dateipfad: str | None = None, log_dir: str | None = None) -> None:
        # ``log_dir`` bleibt aus Rückwärtskompatibilität erhalten.
        if dateipfad is None and log_dir:
            dateipfad = os.path.join(log_dir, "metriken.json")
        self.dateipfad = dateipfad or METRIK_DATEI
        os.makedirs(os.path.dirname(os.path.abspath(self.dateipfad)), exist_ok=True)
        #: Datenhaltung im Rust-Kern (übernimmt auch alte Dateien)
        self.speicher = kern.MetrikSpeicher(self.dateipfad)

    # ------------------------------------------------------------ Persistenz
    def hole_alle(self) -> list[MetricEntry]:
        """Gibt alle Einträge in chronologischer Reihenfolge zurück."""
        return [MetricEntry.from_dict(daten) for daten in self.speicher.hole_alle()]

    # -------------------------------------------------------------- Schreiben
    def add(
        self,
        modell: str = "unbekannt",
        genauigkeit: float = 0.0,
        verlust: float = 0.0,
        tokens: int = 0,
        trainingszeit: float = 0.0,
        epochen: int = 0,
        stapelgroesse: int = 0,
        hardware: str = "unbekannt",
        notizen: str = "",
        markierungen: list[str] | None = None,
        **weitere: Any,
    ) -> MetricEntry:
        """Legt einen neuen Metrikeintrag an und speichert ihn.

        Englische Schlüsselwörter älterer Aufrufer (``model``, ``accuracy``,
        ``train_time``, ``epoch``, ``tags`` …) werden weiterhin akzeptiert.
        """
        rohdaten = {
            "modell": modell,
            "genauigkeit": genauigkeit,
            "verlust": verlust,
            "tokens": tokens,
            "trainingszeit": trainingszeit,
            "epochen": epochen,
            "stapelgroesse": stapelgroesse,
            "hardware": hardware,
            "notizen": notizen,
            "markierungen": list(markierungen or []),
        }
        for schluessel, wert in weitere.items():
            deutsch = FELD_ZUORDNUNG.get(schluessel)
            if deutsch:
                rohdaten[deutsch] = wert

        return MetricEntry.from_dict(self.speicher.fuege_hinzu(rohdaten))

    def log_session(
        self,
        model: str = "unbekannt",
        accuracy: float = 0.0,
        loss: float = 0.0,
        tokens_used: int = 0,
        train_time_sec: float = 0.0,
        epochs: int = 0,
        batch_size: int = 0,
        hardware: str = "unbekannt",
        notes: str = "",
    ) -> dict[str, Any]:
        """Rückwärtskompatible Variante von :meth:`add`."""
        eintrag = self.add(
            modell=model,
            genauigkeit=accuracy,
            verlust=loss,
            tokens=tokens_used,
            trainingszeit=train_time_sec,
            epochen=epochs,
            stapelgroesse=batch_size,
            hardware=hardware,
            notizen=notes,
        )
        return eintrag.to_dict()

    # ---------------------------------------------------------------- Abfragen
    def hole_letzte(self, anzahl: int = 10) -> list[MetricEntry]:
        """Gibt die letzten ``anzahl`` Einträge zurück."""
        if anzahl <= 0:
            return []
        return [
            MetricEntry.from_dict(daten) for daten in self.speicher.hole_letzte(anzahl)
        ]

    def filtere(
        self, modell: str | None = None, markierung: str | None = None
    ) -> list[MetricEntry]:
        """Filtert Einträge nach Modellname und/oder Markierung."""
        return [
            MetricEntry.from_dict(daten)
            for daten in self.speicher.filtere(modell, markierung)
        ]

    def modelle(self) -> list[str]:
        """Gibt alle vorkommenden Modellnamen zurück."""
        return list(self.speicher.modelle())

    def zusammenfassung(self) -> dict[str, Any]:
        """Berechnet Kennzahlen über alle Einträge."""
        return self.speicher.zusammenfassung()

    def vergleich_je_modell(self) -> dict[str, dict[str, float]]:
        """Berechnet Durchschnittswerte je Modell."""
        return self.speicher.vergleich_je_modell()

    # ----------------------------------------------------------------- Pflege
    def exportiere_csv(self, pfad: str) -> str:
        """Schreibt alle Einträge als CSV-Datei und gibt den Pfad zurück.

        Geschrieben wird aus den bereits gelesenen Einträgen, nicht über
        ``MetrikSpeicher.exportiere_csv``: Der Kern setzt für leere Notizen
        zwei Anführungszeichen in die Spalte und schreibt Fließkommazahlen
        ohne Nachkommastelle. Sobald das im Kern behoben ist, kann hier wieder
        direkt an den Kern übergeben werden.
        """
        eintraege = self.hole_alle()
        os.makedirs(os.path.dirname(os.path.abspath(pfad)), exist_ok=True)
        spalten = [
            "zeitstempel", "modell", "genauigkeit", "verlust", "tokens",
            "trainingszeit", "epochen", "stapelgroesse", "hardware",
            "markierungen", "notizen",
        ]
        with open(pfad, "w", newline="", encoding="utf-8") as datei:
            schreiber = csv.writer(datei, delimiter=";")
            schreiber.writerow(spalten)
            for eintrag in eintraege:
                daten = eintrag.to_dict()
                daten["markierungen"] = ", ".join(eintrag.markierungen)
                schreiber.writerow([daten[spalte] for spalte in spalten])
        return pfad

    def loesche_aelter_als(self, tage: int) -> int:
        """Löscht Einträge, die älter als ``tage`` Tage sind."""
        return int(self.speicher.loesche_aelter_als(max(0, tage)))

    def leere_verlauf(self) -> None:
        """Löscht alle gespeicherten Metriken."""
        self.speicher.leere()

    # ------------------------------------- Rückwärtskompatible Aliasnamen
    leere = leere_verlauf
    get_all = hole_alle
    get_all_sessions = hole_alle
    get_latest = hole_letzte
    filter_by = filtere
    summary = zusammenfassung
    export_csv = exportiere_csv
    delete_older_than = loesche_aelter_als
    clear_history = leere_verlauf


#: Gemeinsam genutzte Instanz für Weboberfläche, GUI und Dev-Werkzeuge
_verfolgung: MetricsTracker | None = None


def hole_verfolgung() -> MetricsTracker:
    """Gibt die gemeinsame Metrikverfolgung zurück."""
    global _verfolgung
    if _verfolgung is None:
        _verfolgung = MetricsTracker()
    return _verfolgung
