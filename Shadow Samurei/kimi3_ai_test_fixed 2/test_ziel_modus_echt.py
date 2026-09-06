"""Echte Python-Tests fuer den Ziel-Modus.

Im Gegensatz zu ``test_ziel_modus.py`` laufen hier **echte** Prüfungen auf
echten Dateien und echtem Code-Ausfuehrung:

  A. ``python_datei_pruefung`` gegen reale Dateien auf der Festplatte
     (gueltig, Syntaxfehler, Einrueckungsfehler, ungueltiges Modul).
  B. Eine echte Code-Ausfuehrungs-Pruefung: der Code wird nach ``py_compile``
     in einem Unterprozess ausgefuehrt und die tatsaechliche Ausgabe
     (stdout) mit dem erwarteten Wert verglichen.
  C. Ein vollstaendiger Ziel-Modus-Lauf mit Fake-LLM, bei dem die *echte*
     Pruefung den Ausschlag gibt: Versuch 1 liefert falschen Code (Ausgabe 5),
     Versuch 2 liefert korrekten Code (Ausgabe 4). Die echte Pruefung muss
     den ersten Versuch ablehnen und den zweiten akzeptieren.

Diese Tests brauchen kein echtes Sprachmodell und keinen gebauten Rust-Kern,
fuehren aber echten Python-Code aus (``py_compile`` + ``subprocess``).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import threading
import types
from typing import Any, Callable, List, Optional, Tuple

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


# ------------------------------------------------------------------ Hilfs-LLM
class CodeFakeLLM:
    """Fake-LLM, der aufeinander folgende Code-Antworten liefert.

    Der Schwarm produziert pro Versuch eine Zusammenfassung. Diese enthaelt
    (simuliert) einen Python-Code-Block. Im ersten Versuch ist das Ergebnis
    falsch (5), im zweiten korrekt (4).
    """

    def __init__(self, antworten: List[str]) -> None:
        self.antworten = list(antworten)
        self._index = 0
        self.aufrufe = 0

    def chat_with_tools(
        self,
        frage: str,
        client: Any,
        conversation_history: Optional[List[dict]] = None,
        teilstueck_rueckmeldung: Optional[Callable[[str], None]] = None,
        abbruch: Optional[threading.Event] = None,
        status_rueckmeldung: Optional[Callable[[str], None]] = None,
    ) -> dict[str, Any]:
        self.aufrufe += 1
        system_prompt = client.get_system_prompt_with_tools()
        if "Zusammenfasser" in system_prompt:
            text = self.antworten[min(self._index, len(self.antworten) - 1)]
            self._index += 1
        elif "Planer" in system_prompt:
            text = "1. Schreibe Code.\n2. Pruefe die Ausgabe."
        elif "Kritiker" in system_prompt:
            text = "OK"
        elif "Tester" in system_prompt:
            # Der Tester bewertet das Ergebnis objektiv: korrekter Code
            # (Ausgabe 4) -> ERREICHT, sonst NICHT_ERREICHT.
            if "print(2 + 2)" in frage or "print(2+2)" in frage:
                text = "ERREICHT"
            else:
                text = "NICHT_ERREICHT: Ausgabe ist nicht 4."
        else:
            text = "Arbeite ..."
        verlauf = list(conversation_history or [])
        verlauf.append({"role": "user", "content": frage})
        verlauf.append({"role": "assistant", "content": text})
        return {
            "response": text,
            "tool_calls": [],
            "tool_results": [],
            "conversation": verlauf[-20:],
            "abgebrochen": False,
        }


# ------------------------------------------------------- A: echte Datei-Pruefung
def scenario_a() -> List[str]:
    """Prueft python_datei_pruefung gegen reale Dateien."""
    fehler: List[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        gut = os.path.join(tmp, "gut.py")
        syntax = os.path.join(tmp, "syntax.py")
        einrueck = os.path.join(tmp, "einrueck.py")
        with open(gut, "w", encoding="utf-8") as f:
            f.write("def add(a, b):\n    return a + b\nprint(add(2, 2))\n")
        with open(syntax, "w", encoding="utf-8") as f:
            f.write("def add(a, b)\n    return a + b\n")  # fehlender Doppelpunkt
        with open(einrueck, "w", encoding="utf-8") as f:
            f.write("def add(a, b):\n   return a + b\n  print(add(2,2))\n")

        ok, meldung = python_datei_pruefung([gut], basis=tmp)("", {})
        if not ok:
            fehler.append(f"Gueltige Datei abgelehnt: {meldung}")

        ok, meldung = python_datei_pruefung([syntax], basis=tmp)("", {})
        if ok or "Syntaxfehler" not in meldung and "Syntax" not in meldung:
            fehler.append(
                f"Syntaxfehler nicht erkannt (ok={ok}, meldung={meldung!r})"
            )

        ok, meldung = python_datei_pruefung([einrueck], basis=tmp)("", {})
        if ok:
            fehler.append("Einrueckungsfehler nicht erkannt.")

        # Alle zusammen: eine fehlerhafte Datei reicht zum Durchfallen.
        ok, meldung = python_datei_pruefung([gut, syntax], basis=tmp)("", {})
        if ok:
            fehler.append("Bei einer fehlerhaften Datei muss die Pruefung scheitern.")

        # Nicht existierende Datei: wird von py_compile als Fehler gemeldet.
        ok, meldung = python_datei_pruefung([os.path.join(tmp, "gibt_es_nicht.py")], basis=tmp)("", {})
        if ok:
            fehler.append("Nicht existierende Datei sollte abgelehnt werden.")

    print("[A] python_datei_pruefung auf echten Dateien: OK")
    return fehler


# ------------------------------------------------ B: echte Code-Ausfuehrung
def code_ausfuehrungs_pruefung(
    erwartung: str,
    projekt: str,
) -> Callable[[str, dict], Tuple[bool, str]]:
    """Erzeugt eine echte Pruefung, die Code ausfuehrt und stdout vergleicht.

    Der Code wird aus dem Ergebnis (als ```python-Block oder direkt) gelesen,
    in eine temporaere Datei geschrieben, kompiliert und ausgefuehrt.
    """

    def extrahiere_code(text: str) -> str:
        match = re.search(r"```python\s*(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r"```\s*(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

    def pruefe(_ziel: str, ergebnis: dict) -> Tuple[bool, str]:
        text = ergebnis.get("response", "")
        code = extrahiere_code(text)
        if not code:
            return False, "Kein Code gefunden."
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            pfad = f.name
        try:
            # 1) echte Kompilierung
            import py_compile
            try:
                py_compile.compile(pfad, doraise=True)
            except py_compile.PyCompileError as e:
                return False, f"Code kompiliert nicht: {e}"
            # 2) echte Ausfuehrung im Unterprozess
            ergebnis_proc = subprocess.run(
                [sys.executable, pfad],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=projekt,
            )
            ausgabe = ergebnis_proc.stdout.strip()
            if ergebnis_proc.returncode != 0:
                return False, (
                    f"Code bricht ab (Returncode {ergebnis_proc.returncode}): "
                    f"{ergebnis_proc.stderr.strip()}"
                )
            if ausgabe != erwartung:
                return False, (
                    f"Falsche Ausgabe: {ausgabe!r}, erwartet {erwartung!r}."
                )
            return True, "Ausgabe stimmt."
        except subprocess.TimeoutExpired:
            return False, "Code laeuft zu lange (Endlosschleife?)."
        finally:
            try:
                os.unlink(pfad)
            except OSError:
                pass

    return pruefe


def scenario_b() -> List[str]:
    """Prueft die echte Code-Ausfuehrung direkt."""
    fehler: List[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        pruefe = code_ausfuehrungs_pruefung("4", tmp)

        ok, meldung = pruefe("", {"response": "```python\nprint(2 + 2)\n```"})
        if not ok:
            fehler.append(f"Korrekter Code abgelehnt: {meldung}")

        ok, meldung = pruefe("", {"response": "```python\nprint(2 + 3)\n```"})
        if ok:
            fehler.append("Falsche Ausgabe (5) sollte abgelehnt werden.")

        ok, meldung = pruefe("", {"response": "```python\nprint(2 +\n```"})
        if ok:
            fehler.append("Syntaxfehler sollte abgelehnt werden.")

        ok, meldung = pruefe("", {"response": "```python\nwhile True:\n    pass\n```"})
        if ok:
            fehler.append("Endlosschleife sollte abgelehnt werden (Timeout).")

        ok, meldung = pruefe("", {"response": "kein code hier"})
        if ok:
            fehler.append("Ohne Code sollte die Pruefung scheitern.")

    print("[B] echte Code-Ausfuehrung (compile + subprocess): OK")
    return fehler


# ------------------------------------------- C: vollstaendiger Ziel-Modus-Lauf
def scenario_c() -> List[str]:
    """Vollstaendiger Lauf: echte Pruefung treibt die Schleife.

    Versuch 1: Code gibt 5 aus (falsch) -> Pruefung schlaegt fehl.
    Versuch 2: Code gibt 4 aus (korrekt) -> Pruefung bestanden -> ERREICHT.
    Da die echte Pruefung Vorrang hat, darf der Tester gar nicht erst
    aufgerufen werden; das Ziel wird ueber die echte Pruefung erreicht.
    """
    fehler: List[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        antworten = [
            "```python\nprint(2 + 3)\n```",   # falsch: 5
            "```python\nprint(2 + 2)\n```",   # korrekt: 4
        ]
        fake = CodeFakeLLM(antworten)
        pruefe = code_ausfuehrungs_pruefung("4", tmp)

        ziel_modus = ZielModus(
            llm=fake,
            server=dummy_server(),
            max_versuche=3,
            pruefungen=[pruefe],
        )

        ergebnis = ziel_modus.arbeite_bis_ziel(
            "Schreibe Python-Code, der 2+2 berechnet und ausgibt.",
            status_rueckmeldung=lambda m: None,
        )

        if not ergebnis.get("ziel_erreicht"):
            fehler.append(
                f"Ziel sollte erreicht sein (ist {ergebnis.get('ziel_erreicht')})."
            )
        if ergebnis.get("versuche") != 2:
            fehler.append(
                f"Erwartet 2 Versuche, war {ergebnis.get('versuche')}."
            )

    print("[C] vollstaendiger Lauf mit echter Pruefung: OK "
          f"(ziel_erreicht={ergebnis.get('ziel_erreicht')}, "
          f"versuche={ergebnis.get('versuche')})")
    return fehler


def main() -> int:
    fehler: List[str] = []
    fehler.extend(scenario_a())
    fehler.extend(scenario_b())
    fehler.extend(scenario_c())

    if fehler:
        print("\nFEHLER:")
        for f in fehler:
            print(f"  - {f}")
        return 1

    print("\nEchte Ziel-Modus-Tests OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
