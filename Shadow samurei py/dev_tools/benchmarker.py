"""Benchmark-Läufe für die Modellauswertung.

Unterstützt Einzelläufe, Vergleichsläufe mehrerer Modelle und
wiederkehrende Läufe im Hintergrund. PyTorch wird erst beim Ausführen
importiert, damit die Oberfläche auch ohne Installation startet.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable


class BenchmarkResult:
    """Ergebnis eines einzelnen Benchmark-Laufs."""

    def __init__(
        self,
        modellname: str,
        genauigkeit: float,
        dauer: float,
        zeitstempel: str | None = None,
        zusatz: dict[str, Any] | None = None,
    ) -> None:
        self.modellname = modellname
        self.genauigkeit = genauigkeit
        self.dauer = dauer
        self.zeitstempel = zeitstempel or time.strftime("%Y-%m-%d %H:%M:%S")
        self.zusatz = zusatz or {}

    def to_dict(self) -> dict[str, Any]:
        """Gibt das Ergebnis als Wörterbuch zurück."""
        return {
            "modellname": self.modellname,
            "genauigkeit": self.genauigkeit,
            "dauer": self.dauer,
            "zeitstempel": self.zeitstempel,
            "zusatz": self.zusatz,
        }

    def __str__(self) -> str:  # pragma: no cover - nur Anzeige
        return (
            f"{self.zeitstempel} · {self.modellname} · "
            f"Genauigkeit {self.genauigkeit:.3f} · {self.dauer:.2f}s"
        )


class Benchmarker:
    """Führt Benchmarks aus und schreibt sie in die Metrikverfolgung."""

    def __init__(
        self,
        modellfabrik: Callable[[], Any],
        datenfabrik: Callable[[], tuple],
        metrikverfolgung: Any = None,
        geraet: str = "cpu",
    ) -> None:
        self.modellfabrik = modellfabrik
        self.datenfabrik = datenfabrik
        self.metrikverfolgung = metrikverfolgung
        self.geraet = geraet
        self._laeuft = False
        self._faden: threading.Thread | None = None
        self._intervall = 30
        self._rueckmeldung: Callable[[BenchmarkResult], None] | None = None
        self._ergebnisse: list[BenchmarkResult] = []

    # ---------------------------------------------------------------- Läufe
    def _bewerte(self, modell) -> tuple[float, float]:
        """Wertet ein Modell auf den Testdaten aus und misst die Dauer."""
        import torch

        merkmale, ziele = self.datenfabrik()
        modell.eval()
        merkmale, ziele = merkmale.to(self.geraet), ziele.to(self.geraet)
        beginn = time.time()
        with torch.no_grad():
            vorhersage = modell(merkmale).argmax(1)
            genauigkeit = (vorhersage == ziele).float().mean().item()
        return genauigkeit, time.time() - beginn

    def fuehre_einzeln_aus(self, modellname: str = "benchmark") -> BenchmarkResult:
        """Führt einen einzelnen Benchmark durch."""
        genauigkeit, dauer = self._bewerte(self.modellfabrik())
        ergebnis = BenchmarkResult(modellname, genauigkeit, dauer)
        self._ergebnisse.append(ergebnis)

        if self.metrikverfolgung is not None:
            self.metrikverfolgung.add(
                modell=modellname,
                genauigkeit=genauigkeit,
                trainingszeit=dauer,
                tokens=0,
                epochen=0,
                hardware=self.geraet,
                markierungen=["benchmark"],
            )
        return ergebnis

    def fuehre_vergleich_aus(
        self, modellfabriken: dict[str, Callable[[], Any]]
    ) -> dict[str, BenchmarkResult]:
        """Vergleicht mehrere Modelle auf denselben Daten."""
        ergebnisse: dict[str, BenchmarkResult] = {}
        for name, fabrik in modellfabriken.items():
            genauigkeit, dauer = self._bewerte(fabrik())
            ergebnis = BenchmarkResult(name, genauigkeit, dauer)
            ergebnisse[name] = ergebnis
            self._ergebnisse.append(ergebnis)
            if self.metrikverfolgung is not None:
                self.metrikverfolgung.add(
                    modell=name,
                    genauigkeit=genauigkeit,
                    trainingszeit=dauer,
                    hardware=self.geraet,
                    markierungen=["benchmark", "vergleich"],
                )
        return ergebnisse

    # ---------------------------------------------------------- Hintergrund
    def starte_wiederkehrend(
        self,
        intervall: int = 30,
        rueckmeldung: Callable[[BenchmarkResult], None] | None = None,
    ) -> None:
        """Startet wiederkehrende Benchmarks in einem Hintergrundfaden."""
        if self._laeuft:
            return
        self._laeuft = True
        self._intervall = max(1, int(intervall))
        self._rueckmeldung = rueckmeldung
        self._faden = threading.Thread(target=self._schleife, daemon=True)
        self._faden.start()

    def _schleife(self) -> None:
        """Hintergrundschleife der wiederkehrenden Benchmarks."""
        while self._laeuft:
            # In kleinen Schritten warten, damit ein Stopp sofort greift.
            for _ in range(self._intervall):
                if not self._laeuft:
                    return
                time.sleep(1)
            try:
                ergebnis = self.fuehre_einzeln_aus()
                if self._rueckmeldung:
                    self._rueckmeldung(ergebnis)
            except Exception as fehler:  # pragma: no cover - Laufzeitschutz
                print(f"[Benchmark] Fehler: {fehler}")

    def stoppe(self) -> None:
        """Stoppt die wiederkehrenden Benchmarks."""
        self._laeuft = False

    def laeuft(self) -> bool:
        """Prüft, ob wiederkehrende Benchmarks laufen."""
        return self._laeuft

    # -------------------------------------------------------------- Ergebnisse
    def hole_ergebnisse(self) -> list[BenchmarkResult]:
        """Gibt alle Ergebnisse dieser Sitzung zurück."""
        return list(self._ergebnisse)

    def leere_ergebnisse(self) -> None:
        """Löscht die gesammelten Ergebnisse."""
        self._ergebnisse = []

    # ------------------------------------- Rückwärtskompatible Aliasnamen
    run_single = fuehre_einzeln_aus
    run_comparison = fuehre_vergleich_aus
    start_recurring = starte_wiederkehrend
    stop = stoppe
    is_running = laeuft
    get_results = hole_ergebnisse
    clear_results = leere_ergebnisse
