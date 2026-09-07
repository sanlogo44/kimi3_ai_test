#!/usr/bin/env python3
"""Warteschlange für LLM- und Werkzeug-Aufträge.

Die :class:`AuftragsWarteschlange` reiht Chat-Anfragen und Werkzeugaufrufe
in einer FIFO-Reihenfolge ein und verarbeitet sie nacheinander in einem
eigenen Hintergrund-Thread. So bleiben Oberfläche und Antwort-Streaming
flüssig, während langlaufende Modellaufrufe serialisiert werden – passend
zu Schwarm- und Ziel-Modus, die ebenfalls im Hintergrund laufen.

Typische Nutzung (in der GUI oder CLI)::

    from warteschlange import AuftragsWarteschlange

    queue = AuftragsWarteschlange()
    queue.starten()

    ergebnis = queue.einreihen(
        "chat",
        ausfuehren=lambda: llm.chat_with_tools(frage, client),
        fortschritt=lambda stueck: print(stueck, end="", flush=True),
    )

Die Warteschlange ist thread-sicher. ``einreihen`` blockiert nicht, sondern
gibt ein :class:`AuftragErgebnis` zurück, dessen Wert später abgerufen wird
(``ergebnis.warten()``) oder über einen Rückruf gemeldet.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

#: Statuswerte eines Auftrags
STATUS_OFFEN = "offen"
STATUS_IN_BEARBEITUNG = "in_bearbeitung"
STATUS_FERTIG = "fertig"
STATUS_FEHLER = "fehler"
STATUS_ABGEBROCHEN = "abgebrochen"


@dataclass
class Auftrag:
    """Ein einzelner Warteschlangen-Auftrag."""
    auftrags_id: int
    art: str
    ausfuehren: Callable[[], Any]
    fortschritt: Optional[Callable[[str], None]] = None
    status: str = STATUS_OFFEN
    fehler: Optional[str] = None
    ergebnis: Any = None
    abbruch: threading.Event = field(default_factory=threading.Event)
    fertig: threading.Event = field(default_factory=threading.Event)


class AuftragErgebnis:
    """Hält das Ergebnis eines eingereihten Auftrags bereit.

    Wird von ``einreihen`` zurückgegeben. ``warten()`` blockiert bis zur
    Fertigstellung; ``abholen()`` liefert das Ergebnis oder wirft den Fehler.
    """

    def __init__(self, auftrag: Auftrag):
        self._auftrag = auftrag

    def warten(self, zeitspanne: Optional[float] = None) -> bool:
        """Blockiert bis der Auftrag fertig ist (oder die Zeitspanne abläuft)."""
        return self._auftrag.fertig.wait(zeitspanne)

    @property
    def status(self) -> str:
        return self._auftrag.status

    @property
    def fehler(self) -> Optional[str]:
        return self._auftrag.fehler

    def abholen(self) -> Any:
        """Liefert das Ergebnis oder wirft, falls der Auftrag fehlschlug."""
        self.warten()
        if self._auftrag.fehler is not None:
            raise RuntimeError(self._auftrag.fehler)
        return self._auftrag.ergebnis

    def abbrechen(self) -> None:
        """Bricht den Auftrag ab (sofern er noch nicht fertig ist)."""
        self._auftrag.abbruch.set()


class AuftragsWarteschlange:
    """Thread-sichere FIFO-Warteschlange für LLM-/Tool-Aufträge.

    Ein Hintergrund-Thread (``_arbeite``) verarbeitet die Aufträge nacheinander.
    ``einreihen`` kann aus jedem Thread aufgerufen werden.
    """

    def __init__(self, max_groesse: int = 0):
        # queue.Queue ist thread-sicher; max_groesse=0 bedeutet unbegrenzt.
        import queue

        self._schlange: "queue.Queue[Auftrag]" = queue.Queue(maxsize=max_groesse)
        self._sperre = threading.Lock()
        self._naechste_id = 0
        self._worker: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._aktiv = False

    # ------------------------------------------------------------ Lebenszyklus
    def starten(self) -> None:
        """Startet den Hintergrund-Worker (idempotent)."""
        with self._sperre:
            if self._aktiv:
                return
            self._aktiv = True
            self._stop.clear()
            self._worker = threading.Thread(
                target=self._arbeite, name="warteschlange", daemon=True
            )
            self._worker.start()

    def stoppen(self, warten: bool = False) -> None:
        """Stoppt den Worker. Laufende Aufträge werden abgebrochen."""
        self._stop.set()
        with self._sperre:
            self._aktiv = False
        if warten and self._worker is not None:
            self._worker.join(timeout=5.0)

    @property
    def laeuft(self) -> bool:
        return self._aktiv and not self._stop.is_set()

    # ------------------------------------------------------------- Einreihen
    def einreihen(
        self,
        art: str,
        ausfuehren: Callable[[], Any],
        fortschritt: Optional[Callable[[str], None]] = None,
    ) -> AuftragErgebnis:
        """Reiht einen Auftrag ein und gibt sofort ein Ergebnis-Handle zurück.

        ``ausfuehren`` ist eine parameterlose Funktion, die den eigentlichen
        LLM- oder Werkzeugaufruf kapselt. ``fortschritt`` wird bei jedem
        Teilstück (Streaming-Ausgabe) aufgerufen. Das Abbruch-Event kann von
        ``ausfuehren`` respektiert werden, wenn der Auftrag ``abbruch``
        abfragt.
        """
        with self._sperre:
            self._naechste_id += 1
            auftrags_id = self._naechste_id
        auftrag = Auftrag(
            auftrags_id=auftrags_id,
            art=art,
            ausfuehren=ausfuehren,
            fortschritt=fortschritt,
        )
        self._schlange.put(auftrag)
        return AuftragErgebnis(auftrag)

    @property
    def groesse(self) -> int:
        """Anzahl der offenen Aufträge in der Warteschlange."""
        return self._schlange.qsize()

    # ------------------------------------------------------------- Verarbeitung
    def _arbeite(self) -> None:
        """Verarbeitet Aufträge nacheinander, bis die Warteschlange stoppt."""
        while not self._stop.is_set():
            try:
                auftrag = self._schlange.get(timeout=0.2)
            except Exception:
                # Queue-Timeout – erneut prüfen, ob Stop gesetzt ist.
                continue

            if auftrag.abbruch.is_set():
                auftrag.status = STATUS_ABGEBROCHEN
                auftrag.fertig.set()
                self._schlange.task_done()
                continue

            auftrag.status = STATUS_IN_BEARBEITUNG
            try:
                ergebnis = auftrag.ausfuehren()
                auftrag.ergebnis = ergebnis
                auftrag.status = STATUS_FERTIG
            except Exception as fehler:  # noqa: BLE001 - Fehler ans Ergebnis weiterreichen
                auftrag.fehler = str(fehler)
                auftrag.status = STATUS_FEHLER
            finally:
                auftrag.fertig.set()
                self._schlange.task_done()


# --- Bequemlichkeitsfunktion für die App-Integration -------------------------
def erstelle_warteschlange() -> AuftragsWarteschlange:
    """Erzeugt eine gestartete Warteschlange (Singleton pro Aufruf)."""
    queue = AuftragsWarteschlange()
    queue.starten()
    return queue


__all__ = [
    "STATUS_OFFEN",
    "STATUS_IN_BEARBEITUNG",
    "STATUS_FERTIG",
    "STATUS_FEHLER",
    "STATUS_ABGEBROCHEN",
    "Auftrag",
    "AuftragErgebnis",
    "AuftragsWarteschlange",
    "erstelle_warteschlange",
]
