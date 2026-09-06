"""Schwarm-Orchestrierung für kimi3_ai_test.

Ein Schwarm besteht aus mehreren Agenten mit festen Rollen, die gemeinsam eine
Aufgabe bearbeiten:

  - **Planer**          zerlegt die Aufgabe in Teilaufgaben.
  - **Bearbeiter**      führen die Teilaufgaben aus (mit Werkzeugzugriff).
  - **Kritiker**        prüft die Zwischenergebnisse und kann Nachbesserung fordern.
  - **Zusammenfasser**  fasst alles zu einer endgültigen Antwort zusammen.

Alle Agenten nutzen dasselbe geladene Sprachmodell (``ToolAugmentedLLM``) und
denselben Werkzeug-Server. Da ein Transformers-Modell nicht nebenläufig
aufgerufen werden darf (GPU-Speicher, KV-Cache, Streamer), läuft jede
Modellanfrage über eine Sperre (``RLock``) sequenziell. Die logische Trennung
in mehrere Agenten bleibt trotzdem erhalten: jeder hat seinen eigenen
System-Prompt, seinen eigenen Gesprächsverlauf und kann Werkzeuge aufrufen.

Der Schwarm ist absichtlich begrenzt, damit er überschaubar und stabil bleibt:
höchstens ``max_bearbeiter`` Bearbeiter, eine Nachbesserungsrunde des Kritikers
und höchstens ``max_subagenten`` Unteragenten je Bearbeiter.
"""
from __future__ import annotations

import threading
from typing import Any, Callable, List, Optional

from logger import get_logger
from mcp_protocol import MCPClient, MCPServer, ToolCall


class RollenMCPClient(MCPClient):
    """MCP-Client, der die Systemanweisung um eine Agentenrolle ergänzt.

    Jeder Agent bekommt eine eigene Instanz, damit die Rollenbeschreibung nicht
    den gemeinsamen Zustand verändert. Die Werkzeug-Schemata bleiben identisch.
    """

    def __init__(self, server: MCPServer, rollen_zusatz: str) -> None:
        super().__init__(server)
        self._rollen_zusatz = rollen_zusatz.strip()

    def get_system_prompt_with_tools(self) -> str:
        """Basis-Systemanweisung plus rollenspezifischen Zusatz."""
        basis = super().get_system_prompt_with_tools()
        return f"{self._rollen_zusatz}\n\n{basis}"


class Agent:
    """Ein Agent im Schwarm mit Rolle, eigenem Verlauf und eigenem Client."""

    def __init__(
        self,
        name: str,
        rolle: str,
        beschreibung: str,
        server: MCPServer,
    ) -> None:
        self.name = name
        self.rolle = rolle
        self.beschreibung = beschreibung
        zusatz = (
            f"Du bist der Agent „{name}“ mit der Rolle „{rolle}“. "
            f"{beschreibung} "
            "Antworte immer auf Deutsch, kurz und sachlich. "
            "Wenn du eine Teilaufgabe gelöst hast, gib nur das Ergebnis zurück."
        )
        self.client = RollenMCPClient(server, zusatz)
        self.verlauf: List[dict[str, str]] = []
        self.log = get_logger()

    def frage(
        self,
        llm: Any,
        aufgabe: str,
        abbruch: Optional[threading.Event] = None,
        status: Optional[Callable[[str], None]] = None,
        teilstueck: Optional[Callable[[str], None]] = None,
    ) -> dict[str, Any]:
        """Stellt dem Agenten eine Aufgabe und gibt das vollständige Ergebnis zurück.

        Die Rückgabe ist das unveränderte Ergebnis von ``chat_with_tools`` und
        enthält ``response``, ``tool_calls`` und ``tool_results``.
        """
        if status:
            status(f"Agent „{self.name}“ arbeitet ...")
        ergebnis = llm.chat_with_tools(
            aufgabe,
            self.client,
            conversation_history=self.verlauf,
            teilstueck_rueckmeldung=teilstueck,
            abbruch=abbruch,
        )
        self.verlauf = ergebnis.get("conversation", self.verlauf)[-20:]
        return ergebnis


class SchwarmOrchester:
    """Orchestriert mehrere Agenten zur Lösung einer Aufgabe.

    Der Schwarm läuft in einem einzigen Aufruf sequenziell ab; die Sperre
    ``_sperre`` stellt sicher, dass nie zwei ``chat_with_tools``-Aufrufe das
    Modell gleichzeitig nutzen.
    """

    def __init__(
        self,
        llm: Any,
        server: MCPServer,
        max_bearbeiter: int = 3,
        max_subagenten: int = 1,
    ) -> None:
        self.llm = llm
        self.server = server
        self._sperre = threading.RLock()
        self.log = get_logger()

        self.max_bearbeiter = max(1, min(6, max_bearbeiter))
        self.max_subagenten = max(0, min(3, max_subagenten))

        # Festgelegte Rollen – bewusst klein gehalten.
        self.planer = Agent(
            "Planer",
            "Planer",
            "Du zerlegst eine Aufgabe in höchstens "
            f"{self.max_bearbeiter} eigenständige, klar abgegrenzte Teilaufgaben. "
            "Gib die Teilaufgaben als nummerierte Liste aus, eine je Zeile, "
            "ohne Einleitungstext.",
            server,
        )
        self.zusammenfasser = Agent(
            "Zusammenfasser",
            "Zusammenfasser",
            "Du fasst die Ergebnisse aller Bearbeiter zu einer klaren, "
            "zusammenhängenden Endantwort zusammen. Wiederhole nicht die "
            "einzelnen Schritte, sondern liefere das fertige Ergebnis.",
            server,
        )
        self.kritiker = Agent(
            "Kritiker",
            "Kritiker",
            "Du prüfst, ob die Bearbeitung die Aufgabe vollständig und "
            "korrekt gelöst hat. Wenn etwas fehlt, nenne genau einen "
            "Nachbesserungspunkt. Andernfalls antworte mit „OK“.",
            server,
        )
        # Bearbeiter werden je nach Plan dynamisch erzeugt, damit nicht
        # mehr Agenten laufen als Teilaufgaben vorhanden sind.
        self._bearbeiter_pool: List[Agent] = []

    def _bearbeiter(self, index: int) -> Agent:
        """Gibt den n-ten Bearbeiter zurück und legt ihn bei Bedarf an."""
        while len(self._bearbeiter_pool) <= index:
            self._bearbeiter_pool.append(
                Agent(
                    f"Bearbeiter {len(self._bearbeiter_pool) + 1}",
                    "Bearbeiter",
                    "Du bearbeitest genau eine Teilaufgabe mit den verfügbaren "
                    "Werkzeugen. Wenn du fertig bist, gib nur dein Ergebnis zurück.",
                    self.server,
                )
            )
        return self._bearbeiter_pool[index]

    # -------------------------------------------------------------- Hilfsformate
    @staticmethod
    def _teile_aufgabe(text: str) -> List[str]:
        """Zerlegt eine nummerierte Liste in einzelne Teilaufgaben."""
        teile: List[str] = []
        for zeile in text.splitlines():
            zeile = zeile.strip().lstrip("-").strip()
            if not zeile:
                continue
            # Führende Nummer wie „1." oder „1)" entfernen.
            if zeile[0:1].isdigit():
                punkt = zeile.find(".")
                klammer = zeile.find(")")
                treffer = [x for x in (punkt, klammer) if x != -1]
                schnitt = min(treffer) if treffer else -1
                if 0 < schnitt < 4:
                    zeile = zeile[schnitt + 1:].strip()
            if zeile:
                teile.append(zeile)
        return teile

    # ------------------------------------------------------------------ Ablauf
    def _gesperrt(self, funktion: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        """Führt eine Modellanfrage unter der Sperre aus."""
        with self._sperre:
            return funktion()

    def beantworte(
        self,
        frage: str,
        verlauf: Optional[List[dict[str, str]]] = None,
        teilstueck_rueckmeldung: Optional[Callable[[str], None]] = None,
        abbruch: Optional[threading.Event] = None,
        status_rueckmeldung: Optional[Callable[[str], None]] = None,
    ) -> dict[str, Any]:
        """Löst eine Aufgabe über den gesamten Schwarm und gibt das Ergebnis zurück.

        Die Rückgabe ist kompatibel zu ``ToolAugmentedLLM.chat_with_tools``:
        sie enthält ``response``, ``tool_calls``, ``tool_results``,
        ``conversation`` und ``abgebrochen``.
        """
        if status_rueckmeldung:
            status_rueckmeldung("Schwarm wird gestartet ...")

        aufrufe: List[ToolCall] = []
        ergebnisse: List[str] = []

        def verarbeite(agent: Agent, ergebnis: dict[str, Any]) -> str:
            """Nimmt das Ergebnis eines Agenten auf und sammelt Werkzeugaufrufe."""
            aufrufe.extend(ergebnis.get("tool_calls", []) or [])
            text = (ergebnis.get("response") or "").strip()
            if text:
                ergebnisse.append(f"[{agent.name}] {text}")
            return text

        # 1) Planung: Aufgabe in Teilaufgaben zerlegen.
        plan_ergebnis = self._gesperrt(
            lambda: self.planer.frage(
                self.llm,
                f"Aufgabe: {frage}\n\nZerlege sie in eigenständige Teilaufgaben.",
                abbruch=abbruch,
                status=status_rueckmeldung,
            )
        )
        plan_text = verarbeite(self.planer, plan_ergebnis)
        teilaufgaben = self._teile_aufgabe(plan_text)
        if not teilaufgaben:
            # Konnte nicht zerlegt werden – als eine Teilaufgabe behandeln.
            teilaufgaben = [frage]

        teilaufgaben = teilaufgaben[: self.max_bearbeiter]
        if status_rueckmeldung:
            status_rueckmeldung(
                f"{len(teilaufgaben)} Teilaufgabe(n) erkannt – Bearbeiter starten."
            )

        # 2) Bearbeitung: jede Teilaufgabe durch einen eigenen Bearbeiter.
        for nummer, aufgabe in enumerate(teilaufgaben):
            if abbruch is not None and abbruch.is_set():
                return self._abbruch(frage, verlauf, aufrufe, ergebnisse)

            bearbeiter = self._bearbeiter(nummer)
            b_ergebnis = self._gesperrt(
                lambda b=bearbeiter, a=aufgabe: b.frage(
                    self.llm,
                    f"Teilaufgabe {nummer + 1}: {a}",
                    abbruch=abbruch,
                    status=status_rueckmeldung,
                )
            )
            antwort = verarbeite(bearbeiter, b_ergebnis)

            # Optionaler Unteragent für eine vertiefte Teilfrage.
            if self.max_subagenten > 0 and antwort:
                self._führe_subagent_aus(
                    bearbeiter, antwort, aufrufe, ergebnisse, abbruch,
                    status_rueckmeldung,
                )

        # 3) Kritik: einmalige Prüfung, ob etwas fehlt.
        kritik_ergebnis = self._gesperrt(
            lambda: self.kritiker.frage(
                self.llm,
                "Prüfe diese Bearbeitung auf Vollständigkeit und Fehler:\n"
                + "\n".join(ergebnisse),
                abbruch=abbruch,
                status=status_rueckmeldung,
            )
        )
        kritik = verarbeite(self.kritiker, kritik_ergebnis)
        nachbesserung = kritik.strip().upper() != "OK" and not kritik.startswith("OK")
        if nachbesserung:
            if status_rueckmeldung:
                status_rueckmeldung("Kritiker fordert Nachbesserung – zweite Runde.")
            nach_ergebnis = self._gesperrt(
                lambda: self._bearbeiter(0).frage(
                    self.llm,
                    f"Bitte ergänze oder korrigiere: {kritik}",
                    abbruch=abbruch,
                    status=status_rueckmeldung,
                )
            )
            verarbeite(self._bearbeiter(0), nach_ergebnis)

        # 4) Zusammenfassung zur finalen Antwort.
        if status_rueckmeldung:
            status_rueckmeldung("Zusammenfasser erzeugt die Endantwort ...")
        einzelteile = "\n".join(ergebnisse)
        zusammen_ergebnis = self._gesperrt(
            lambda: self.zusammenfasser.frage(
                self.llm,
                f"Ursprüngliche Aufgabe: {frage}\n\n"
                f"Ergebnisse der Bearbeiter:\n{einzelteile}\n\n"
                "Fasse dies zu einer klaren Antwort zusammen.",
                abbruch=abbruch,
                status=status_rueckmeldung,
                teilstueck=teilstueck_rueckmeldung,
            )
        )
        endantwort = verarbeite(self.zusammenfasser, zusammen_ergebnis)

        if not endantwort:
            endantwort = einzelteile or "Der Schwarm hat keine Antwort erzeugt."

        # Gesprächsverlauf für die Oberfläche fortschreiben.
        neu_verlauf = list(verlauf or [])
        neu_verlauf.append({"role": "user", "content": frage})
        neu_verlauf.append({"role": "assistant", "content": endantwort})
        if len(neu_verlauf) > 20:
            neu_verlauf = neu_verlauf[-20:]

        return {
            "response": endantwort,
            "tool_calls": aufrufe,
            "tool_results": [],
            "conversation": neu_verlauf,
            "abgebrochen": False,
            "schwarm": True,
            "teilaufgaben": len(teilaufgaben),
        }

    def _führe_subagent_aus(
        self,
        eltern: Agent,
        kontext: str,
        aufrufe: List[ToolCall],
        ergebnisse: List[str],
        abbruch: Optional[threading.Event],
        status_rueckmeldung: Optional[Callable[[str], None]],
    ) -> None:
        """Startet einen begrenzten Unteragenten für eine vertiefte Teilfrage."""
        sub = Agent(
            f"Unteragent von {eltern.name}",
            "Unteragent",
            "Du vertiefst eine einzelne Frage für den übergeordneten Bearbeiter. "
            "Bleibe eng am Thema und gib nur dein Ergebnis zurück.",
            self.server,
        )
        ergebnis = self._gesperrt(
            lambda: sub.frage(
                self.llm,
                f"Vertiefte Frage zu: {kontext}",
                abbruch=abbruch,
                status=status_rueckmeldung,
            )
        )
        text = (ergebnis.get("response") or "").strip()
        aufrufe.extend(ergebnis.get("tool_calls", []) or [])
        if text:
            ergebnisse.append(f"[{sub.name}] {text}")

    def _abbruch(
        self,
        frage: str,
        verlauf: Optional[List[dict[str, str]]],
        aufrufe: List[ToolCall],
        ergebnisse: List[str],
    ) -> dict[str, Any]:
        """Gibt ein sauberes Abbruch-Ergebnis zurück."""
        antwort = "Der Schwarm wurde abgebrochen.\n" + "\n".join(ergebnisse)
        neu_verlauf = list(verlauf or [])
        neu_verlauf.append({"role": "user", "content": frage})
        neu_verlauf.append({"role": "assistant", "content": antwort})
        return {
            "response": antwort,
            "tool_calls": aufrufe,
            "tool_results": [],
            "conversation": neu_verlauf,
            "abgebrochen": True,
            "schwarm": True,
        }


#: Rückwärtskompatibler deutscher Name
Schwarm = SchwarmOrchester
