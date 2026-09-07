"""Test fuer den Ziel-Modus ohne echtes Sprachmodell.

Zwei Szenarien:

  1. Der Tester meldet beim dritten Versuch „ERREICHT" – die Schleife muss
     dann stoppen und ``ziel_erreicht=True`` mit ``versuche=3`` liefern.
  2. Der Tester meldet immer „NICHT_ERREICHT" – nach ``max_versuche=3`` muss
     ein Teilerfolg mit ``ziel_erreicht=False`` und ``versuche=3`` herauskommen.

Zusaetzlich wird geprueft, dass die echte ``py_compile``-Pruefung Vorrang vor
dem Tester hat: schlaegt sie fehl, gilt das Ziel als nicht erreicht, selbst
wenn der Tester „ERREICHT" sagen wuerde.
"""
from __future__ import annotations

import sys
import threading
import types
from typing import Any, Callable, List, Optional

# Stub fuer den Rust-Kern (wie in test_schwarm.py), damit der Test ohne
# gebautes Modul laeuft.
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
from ziel_modus import ZielModus, python_datei_pruefung


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
    """Nachahmung von ToolAugmentedLLM fuer den Ziel-Modus.

    Fuer Tester-Aufrufe (Systemprompt enthaelt „Tester") wird ein Zaehler
    verwendet: die ersten ``erfolge_ab``-mal „NICHT_ERREICHT", danach
    „ERREICHT". Fuer alle anderen (Schwarm-)Aufrufe gilt die Logik aus
    test_schwarm.py.
    """

    def __init__(self, erfolge_ab: int = 3) -> None:
        self.aufrufe = 0
        self.tester_aufrufe = 0
        self.erfolge_ab = erfolge_ab
        self.aktive = 0
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
            ist_tester = "Tester" in system_prompt

            if ist_tester:
                self.tester_aufrufe += 1
                if self.tester_aufrufe >= self.erfolge_ab:
                    text = "ERREICHT"
                else:
                    text = "NICHT_ERREICHT: Ergebnis noch nicht vollstaendig."
            else:
                # Schwarm-Rollen wie in test_schwarm.py.
                if "Planer" in system_prompt:
                    text = "1. Loese die Aufgabe.\n2. Pruefe sie.\n3. Antworte."
                elif "Kritiker" in system_prompt:
                    text = "OK"
                elif "Zusammenfasser" in system_prompt:
                    text = "Die Loesung ist 42."
                else:
                    text = f"Ergebnis fuer: {frage[:60]}"

            verlauf = list(conversation_history or [])
            verlauf.append({"role": "user", "content": frage})
            verlauf.append({"role": "assistant", "content": text})
            if teilstueck_rueckmeldung and "Zusammenfasser" in system_prompt:
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


def _scenario_erreicht() -> List[str]:
    """Szenario 1: Tester erreicht beim 3. Versuch das Ziel."""
    fehler: List[str] = []
    fake = FakeLLM(erfolge_ab=3)
    ziel_modus = ZielModus(llm=fake, server=dummy_server(), max_versuche=5)

    status_meldungen: List[str] = []
    teilstuecke: List[str] = []

    ergebnis = ziel_modus.arbeite_bis_ziel(
        "Finde die Antwort auf alles.",
        teilstueck_rueckmeldung=lambda t: teilstuecke.append(t),
        status_rueckmeldung=lambda m: status_meldungen.append(m),
    )

    if not ergebnis.get("ziel_erreicht"):
        fehler.append("Ziel sollte erreicht sein, ist es aber nicht.")
    if ergebnis.get("versuche") != 3:
        fehler.append(
            f"Falsche Versuchszahl: {ergebnis.get('versuche')}, erwartet 3."
        )
    if ergebnis.get("tester_aufrufe", 0):  # wird nicht gesetzt – Platzhalter
        pass
    if fake.tester_aufrufe != 3:
        fehler.append(
            f"Tester sollte 3-mal aufgerufen werden, war {fake.tester_aufrufe}."
        )
    if fake.max_ueberlappung > 1:
        fehler.append(
            f"Inferenz lief parallel (Ueberlappung={fake.max_ueberlappung})."
        )
    if not status_meldungen:
        fehler.append("Keine Statusmeldungen gesammelt.")

    print("[1] Erreicht bei Versuch 3:")
    print(f"    ziel_erreicht={ergebnis.get('ziel_erreicht')} "
          f"versuche={ergebnis.get('versuche')} "
          f"tester_aufrufe={fake.tester_aufrufe}")
    return fehler


def _scenario_limit() -> List[str]:
    """Szenario 2: Ziel wird nie erreicht – Limit greift."""
    fehler: List[str] = []
    fake = FakeLLM(erfolge_ab=99)  # nie erreicht
    ziel_modus = ZielModus(llm=fake, server=dummy_server(), max_versuche=3)

    ergebnis = ziel_modus.arbeite_bis_ziel("Unloesbares Ziel.")

    if ergebnis.get("ziel_erreicht"):
        fehler.append("Ziel sollte nicht erreicht sein, ist es aber.")
    if ergebnis.get("versuche") != 3:
        fehler.append(
            f"Falsche Versuchszahl: {ergebnis.get('versuche')}, erwartet 3."
        )
    if fake.tester_aufrufe != 3:
        fehler.append(
            f"Tester sollte 3-mal aufgerufen werden, war {fake.tester_aufrufe}."
        )
    if "nicht sicher erreicht" not in ergebnis.get("response", ""):
        fehler.append("Teilerfolg-Hinweis fehlt in der Antwort.")

    print("[2] Limit greift nach 3 Versuchen:")
    print(f"    ziel_erreicht={ergebnis.get('ziel_erreicht')} "
          f"versuche={ergebnis.get('versuche')} "
          f"tester_aufrufe={fake.tester_aufrufe}")
    return fehler


def _scenario_echte_pruefung() -> List[str]:
    """Szenario 3: Echte Pruefung schlaegt fehl – hat Vorrang vor dem Tester."""
    fehler: List[str] = []
    fake = FakeLLM(erfolge_ab=1)  # Tester wuerde sofort „ERREICHT" sagen

    def pruefung_fehler(_ziel: str, _erg: dict) -> tuple[bool, str]:
        return False, "Syntaxfehler in Beispiel.py."

    ziel_modus = ZielModus(
        llm=fake,
        server=dummy_server(),
        max_versuche=2,
        pruefungen=[pruefung_fehler],
    )

    ergebnis = ziel_modus.arbeite_bis_ziel("Schreibe sauberen Code.")

    if ergebnis.get("ziel_erreicht"):
        fehler.append(
            "Echte Pruefung schlug fehl – Ziel darf nicht erreicht sein."
        )
    if fake.tester_aufrufe != 0:
        fehler.append(
            "Bei fehlschlagender echter Pruefung darf der Tester gar nicht "
            f"erst fragen (war {fake.tester_aufrufe})."
        )

    print("[3] Echte Pruefung hat Vorrang:")
    print(f"    ziel_erreicht={ergebnis.get('ziel_erreicht')} "
          f"versuche={ergebnis.get('versuche')} "
          f"tester_aufrufe={fake.tester_aufrufe}")
    return fehler


def main() -> int:
    fehler: List[str] = []
    fehler.extend(_scenario_erreicht())
    fehler.extend(_scenario_limit())
    fehler.extend(_scenario_echte_pruefung())

    # py_compile-Helfer: Syntaxfehler wird erkannt, korrekter Code bestanden.
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        gut = os.path.join(tmp, "gut.py")
        schlecht = os.path.join(tmp, "schlecht.py")
        with open(gut, "w", encoding="utf-8") as f:
            f.write("x = 1 + 2\n")
        with open(schlecht, "w", encoding="utf-8") as f:
            f.write("def kaputt(\n")  # Syntaxfehler

        ok_gut, _ = python_datei_pruefung([gut], basis=tmp)("", {})
        if not ok_gut:
            fehler.append("py_compile sollte gueltige Datei akzeptieren.")
        ok_schlecht, _ = python_datei_pruefung([schlecht], basis=tmp)("", {})
        if ok_schlecht:
            fehler.append("py_compile sollte syntaktisch falsche Datei ablehnen.")

    print("[4] python_datei_pruefung: Syntaxfehler wird erkannt.")

    if fehler:
        print("\nFEHLER:")
        for f in fehler:
            print(f"  - {f}")
        return 1

    print("\nZiel-Modus-Test OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
