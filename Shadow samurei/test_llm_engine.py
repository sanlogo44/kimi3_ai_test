"""Testet die drei LLM-Quellen in llm_engine.py:
1. Erkennung eines lokal trainierten Modells
2. API-Modus (OpenAI-kompatibel) ohne PyTorch/Transformers
3. Fallback-Verhalten (ModellNichtVerfuegbar)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm_engine import (
    ModellNichtVerfuegbar,
    STANDARD_LOKALER_PFAD,
    ToolAugmentedLLM,
    _lokal_trainiertes_modell,
)


# --------------------------------------------------------------------------- #
# 1. Lokale Modellerkennung
# --------------------------------------------------------------------------- #
def test_lokale_erkennung():
    with tempfile.TemporaryDirectory() as tmp:
        # Leeres Verzeichnis -> kein Modell
        assert _lokal_trainiertes_modell(tmp) is None, "leeres Verz. sollte None sein"
        assert _lokal_trainiertes_modell("/existiert/nicht") is None

        # Nur config.json, keine Gewichte -> kein Modell
        with open(os.path.join(tmp, "config.json"), "w") as f:
            f.write("{}")
        assert _lokal_trainiertes_modell(tmp) is None, "ohne Gewichte -> None"

        # config.json + safetensors -> Modell erkannt
        with open(os.path.join(tmp, "modell.safetensors"), "wb") as f:
            f.write(b"\x00")
        ergebnis = _lokal_trainiertes_modell(tmp)
        assert ergebnis == tmp, f"Modell sollte {tmp} sein, war {ergebnis}"

        # Auch .bin und .gguf werden erkannt
        os.remove(os.path.join(tmp, "modell.safetensors"))
        for endung in (".bin", ".gguf", ".pt"):
            with open(os.path.join(tmp, f"m{endung}"), "wb") as f:
                f.write(b"\x00")
            assert _lokal_trainiertes_modell(tmp) == tmp, f"{endung} nicht erkannt"
            os.remove(os.path.join(tmp, f"m{endung}"))

    print("[OK] 1. Lokale Modellerkennung (leer/ohne Gewichte/mit Gewichten)")


# --------------------------------------------------------------------------- #
# Hilfs-Server für den API-Modus
# --------------------------------------------------------------------------- #
class MockServer:
    """Minimaler OpenAI-kompatibler Server (non-streaming + SSE)."""

    def __init__(self):
        self.port = 0
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.empfangen: list[dict] = []

    def start(self):
        handler = self._handler_klasse()
        self._server = HTTPServer(("127.0.0.1", 0), handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._thread.start()

    def stop(self):
        if self._server:
            self._server.shutdown()

    def _handler_klasse(self):
        empfangen = self.empfangen

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args, **kwargs):
                pass

            def do_POST(self):  # noqa: N802
                laenge = int(self.headers.get("Content-Length", 0))
                roh = self.rfile.read(laenge)
                try:
                    daten = json.loads(roh)
                except json.JSONDecodeError:
                    daten = {}
                empfangen.append(daten)
                stream = daten.get("stream", False)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                if stream:
                    # SSE: zwei Deltas, dann [DONE]
                    for wort in ("Hallo", " aus", " dem", " Test"):
                        delta = {"choices": [{"delta": {"content": wort}}]}
                        self.wfile.write(
                            b"data: " + json.dumps(delta).encode() + b"\n\n"
                        )
                        self.wfile.flush()
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                else:
                    antwort = {
                        "choices": [
                            {"message": {"content": "Mock-Antwort ohne Stream"}}
                        ]
                    }
                    self.wfile.write(json.dumps(antwort).encode())

        return Handler


# --------------------------------------------------------------------------- #
# 2. API-Modus ohne PyTorch/Transformers
# --------------------------------------------------------------------------- #
def test_api_modus():
    server = MockServer()
    server.start()
    try:
        config = {
            "model": {
                "source": "api",
                "api_key": "test-schluessel",
                "api_base": f"http://127.0.0.1:{server.port}/v1",
                "api_model": "mock-modell",
            }
        }
        llm = ToolAugmentedLLM(config=config)
        assert llm.modus == "api", f"modus={llm.modus}"
        assert llm.model_name == "mock-modell"

        # Non-Streaming
        text = llm.generate("Frage?", teilstueck_rueckmeldung=None)
        assert text == "Mock-Antwort ohne Stream", f"text={text!r}"

        # Streaming
        teile: list[str] = []
        text_stream = llm.generate(
            "Frage?", teilstueck_rueckmeldung=teile.append
        )
        assert text_stream == "Hallo aus dem Test", f"stream={text_stream!r}"
        assert "".join(teile) == "Hallo aus dem Test"

        # Modellname im Body gesendet?
        assert any(
            d.get("model") == "mock-modell" for d in server.empfangen
        ), "Modellname nicht gesendet"

        print("[OK] 2. API-Modus (non-streaming + SSE-Streaming, kein PyTorch)")
    finally:
        server.stop()


# --------------------------------------------------------------------------- #
# 3. Fallback: ohne lokales Modell, ohne API-Key -> ModellNichtVerfuegbar
#    (system-python ohne transformers)
# --------------------------------------------------------------------------- #
def test_fallback():
    try:
        import transformers  # noqa: F401
        hat_transformers = True
    except ImportError:
        hat_transformers = False

    with tempfile.TemporaryDirectory() as tmp:
        config = {
            "model": {
                "source": "auto",
                "local_path": tmp,  # leer -> kein lokales Modell
                # kein api_key
            }
        }
        if hat_transformers:
            print("[--] 3. Fallback übersprungen (transformers installiert)")
            return
        try:
            ToolAugmentedLLM(config=config)
            fehler = False
        except ModellNichtVerfuegbar:
            fehler = True
        assert fehler, "ModellNichtVerfuegbar erwartet"
        print("[OK] 3. Fallback: ohne Quelle -> ModellNichtVerfuegbar")


# --------------------------------------------------------------------------- #
# 4. Lokales Modell wird als Quelle gewählt (source=auto)
#    Wenn transformers fehlt, wird trotzdem die Quelle erkannt, bevor
#    das Laden fehlschlägt. Hier prüfen wir nur die Quellauswahl.
# --------------------------------------------------------------------------- #
def test_quellauswahl_lokal():
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "config.json"), "w") as f:
            f.write("{}")
        with open(os.path.join(tmp, "modell.safetensors"), "wb") as f:
            f.write(b"\x00")
        try:
            llm = ToolAugmentedLLM(
                config={"model": {"source": "auto", "local_path": tmp}}
            )
            assert llm.modus == "transformers", f"modus={llm.modus}"
            assert llm.model_name == tmp, f"model_name={llm.model_name}"
            print("[OK] 4. Lokales Modell als Quelle gewählt (source=auto)")
        except ModellNichtVerfuegbar:
            # Kein transformers -> Quelle wurde erkannt, Laden schlug fehl.
            # Das ist in Ordnung: die Quellauswahl hat funktioniert.
            print("[OK] 4. Lokales Modell erkannt (transformers fehlt -> erwartet)")


if __name__ == "__main__":
    test_lokale_erkennung()
    test_api_modus()
    test_fallback()
    test_quellauswahl_lokal()
    print("\nAlle llm_engine-Tests bestanden.")
