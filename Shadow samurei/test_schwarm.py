"""Test für den Schwarm ohne echtes Sprachmodell.

Ein Fake-LLM ahmt ``chat_with_tools`` nach und gibt je nach Rolle passende
Antworten. So lässt sich prüfen, ob der Schwarm Planer, Bearbeiter, Kritiker
und Zusammenfasser korrekt durchlaeuft und die Sperre die Inferenz
serialisiert.
"""
from __future__ import annotations

import threading
import sys
import types
from typing import Any, Callable, List, Optional

# Stub fuer den Rust-Kern, damit der Test ohne gebautes Modul laeuft.
# logger.py und kern_modul.py greifen darauf zu; hier wird nur protokolliert.
if "kimi3_kern" not in sys.modules:
    _stub = types.ModuleType("kimi3_kern")
    _stub.richte_protokoll_ein = lambda *a, **k: None
    _stub.setze_protokollstufe = lambda *a, **k: None
    _stub.protokolliere = lambda stufe, meldung: print(f"[{stufe}] {meldung}")
    _stub.berechne = lambda a: float(eval(a, {"__builtins__": {}}, {}))  # noqa: S307
    _stub.ergebnis_text = lambda w: str(w)
    _stub.lade_konfiguration = lambda path="config.yaml": {
        "logging": {"level": "INFO", "colored": False, "log_file": None},
    }
    sys.modules["kimi3_kern"] = _stub

from mcp_protocol import MCPServer, ToolDefinition, ToolParameter
from schwarm import SchwarmOrchester


def dummy_server() -> MCPServer:
    """Ein MCP-Server ohne Rust-Kern, nur fuer den Test."""
    server = MCPServer()
    server.register_tool(
        ToolDefinition(
            "echo", "Gibt den Text zurueck.",
            [ToolParameter("text", "string", "Eingabe")],
        ),
        lambda text: {"text": text},
    )
    return server


class FakeLLM:
    """Nachahmung von ToolAugmentedLLM mit Zaehler und Sperren-Pruefung."""

    def __init__(self) -> None:
        self.aufrufe = 0
        self.aktive = 0  # sollte nie ueber 1 steigen (serialisierte Inferenz)
        self.max_ueberlappung = 0
        self._sperre = threading.Lock()

    def chat_with_tools(
        self,
        frage: str,
        client: Any,
        conversation_history: Optional[List[dict]] = None,
        teilstueck_rueckmeldung: Optional[Callable[[str], None]] = None,
        abbruch: Optional[threading.Event] = None,
        status_rueckmeldung: Optional[Callable[[str], None]] = None,
    ) -> dict[str, Any]:
        with self._sperre:
            self.aufrufe += 1
            self.aktive += 1
            self.max_ueberlappung = max(self.max_ueberlappung, self.aktive)

        try:
            system_prompt = client.get_system_prompt_with_tools()
            ist_planer = "Planer" in system_prompt
            ist_kritiker = "Kritiker" in system_prompt
            ist_zusammenfasser = "Zusammenfasser" in system_prompt
            ist_bearbeiter = "Bearbeiter" in system_prompt
            ist_subagent = "Unteragent" in system_prompt

            if ist_planer:
                text = (
                    "1. Berechne das Ergebnis.\n"
                    "2. Pruefe die Loesung.\n"
                    "3. Formuliere die Antwort."
                )
            elif ist_kritiker:
                text = "OK"
            elif ist_zusammenfasser:
                text = "Die Loesung ist 42."
            elif ist_subagent:
                text = "Tiefere Pruefung: 42 ist korrekt."
            elif ist_bearbeiter:
                text = f"Ergebnis fuer: {frage[:60]}"
            else:
                text = "Unbekannt."

            verlauf = list(conversation_history or [])
            verlauf.append({"role": "user", "content": frage})
            verlauf.append({"role": "assistant", "content": text})
            if teilstueck_rueckmeldung and ist_zusammenfasser:
                teilstueck_rueckmeldung(text)

            return {
                "response": text,
                "tool_calls": [],
                "tool_results": [],
                "conversation": verlauf[-20:],
                "abgebrochen": False,
            }
        finally:
            with self._sperre:
                self.aktive -= 1


def main() -> int:
    server: MCPServer = dummy_server()
    fake = FakeLLM()
    schwarm = SchwarmOrchester(llm=fake, server=server)

    status_meldungen: List[str] = []
    teilstuecke: List[str] = []

    ergebnis = schwarm.beantworte(
        "Was ist die Antwort auf alles?",
        verlauf=[],
        teilstueck_rueckmeldung=lambda t: teilstuecke.append(t),
        status_rueckmeldung=lambda m: status_meldungen.append(m),
    )

    fehler: List[str] = []

    if not ergebnis.get("response"):
        fehler.append("Keine Antwort erhalten.")
    if not ergebnis.get("schwarm"):
        fehler.append("Ergebnis ist nicht als Schwarm-Ergebnis markiert.")
    if ergebnis.get("teilaufgaben", 0) < 2:
        fehler.append(f"Zu wenige Teilaufgaben: {ergebnis.get('teilaufgaben')}")
    if fake.max_ueberlappung > 1:
        fehler.append(
            f"Inferenz lief parallel (Ueberlappung={fake.max_ueberlappung})."
        )
    if fake.aufrufe < 4:
        fehler.append(f"Zu wenige Agenten-Aufrufe: {fake.aufrufe}")
    if not teilstuecke:
        fehler.append("Zusammenfasser hat nicht gestreamt.")
    if not status_meldungen:
        fehler.append("Keine Statusmeldungen gesammelt.")

    print(f"Aufrufe gesamt: {fake.aufrufe}")
    print(f"Max. Ueberlappung: {fake.max_ueberlappung}")
    print(f"Teilaufgaben: {ergebnis.get('teilaufgaben')}")
    print(f"Antwort: {ergebnis.get('response')!r}")
    print(f"Statusmeldungen: {len(status_meldungen)}")
    print(f"Teilstuecke: {teilstuecke}")

    if fehler:
        print("\nFEHLER:")
        for f in fehler:
            print(f"  - {f}")
        return 1

    print("\nSchwarm-Test OK.")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
