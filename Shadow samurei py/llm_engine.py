"""Sprachmodell mit Werkzeugaufrufen über das MCP-Protokoll.

Das LLM kann aus drei Quellen kommen (Priorität in dieser Reihenfolge):

1. **Lokal trainiertes Modell** – wenn unter ``model.local_path``
   (Standard ``./tool_model``) ein trainiertes Modell liegt, wird dieses
   geladen. Es wird *nichts* von Hugging Face heruntergeladen – ideal für
   das selbst trainierte eigene LLM.
2. **OpenAI-kompatibler API-Server** – wenn ``model.api_key`` gesetzt ist,
   werden Anfragen an ``model.api_base`` (z. B. LM Studio, Ollama, vLLM)
   geroutet. Keine lokalen Modellbibliotheken nötig.
3. **Hugging Face-Modell** – sonst wird ``model.name`` geladen (Achtung:
   ``meta-llama/...`` ist ein gated Repo und braucht einen ``HF_TOKEN``).

PyTorch und Transformers werden erst beim Erzeugen von
:class:`ToolAugmentedLLM` importiert – und nur, wenn Quelle 1 oder 3
gewählt ist. So lassen sich Oberfläche und Werkzeuge auch starten, wenn
keine Modellbibliotheken installiert sind.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any, Callable

from logger import get_logger
from mcp_protocol import MCPClient, ToolCall, ToolResult

#: Textmarken, an denen die Generierung abgebrochen wird
STOPP_MARKEN = ("[/TOOL]", "[TOOL_RESULT]", "<|eot_id|>")

#: Standardordner für das lokal trainierte Modell
STANDARD_LOKALER_PFAD = "./tool_model"


class ModellNichtVerfuegbar(RuntimeError):
    """Wird ausgelöst, wenn keine LLM-Quelle verfügbar ist."""


def _lokal_trainiertes_modell(pfad: str) -> str | None:
    """Prüft, ob unter ``pfad`` ein ladbares lokales Modell liegt.

    Gibt den Pfad zurück, wenn ja – sonst ``None``.
    """
    if not pfad or not os.path.isdir(pfad):
        return None
    if not os.path.isfile(os.path.join(pfad, "config.json")):
        return None
    # Mindestens eine Gewichte-Datei muss vorhanden sein.
    for datei in os.listdir(pfad):
        if datei.endswith((".safetensors", ".bin", ".pt", ".gguf")):
            return pfad
    return None


def _lade_bibliotheken():
    """Importiert PyTorch und Transformers oder erklärt, was fehlt."""
    try:
        import torch
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            StoppingCriteria,
            StoppingCriteriaList,
            TextIteratorStreamer,
        )
    except ImportError as fehler:  # pragma: no cover - abhängig von der Umgebung
        raise ModellNichtVerfuegbar(
            "PyTorch und Transformers sind nicht installiert. "
            "Chat aktivieren mit: python start.py --mit-torch "
            "(oder: pip install -r requirements-ai.txt)"
        ) from fehler
    return (
        torch,
        AutoModelForCausalLM,
        AutoTokenizer,
        StoppingCriteria,
        StoppingCriteriaList,
        TextIteratorStreamer,
    )


class ToolAugmentedLLM:
    """Sprachmodell, das während der Antwort Werkzeuge aufrufen kann."""

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        load_in_4bit: bool | None = None,
        max_tool_iterations: int | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        config = config or {}
        hardware = config.get("hardware", {})
        modell_cfg = config.get("model", {})
        self.log = get_logger(config)
        self.max_tool_iterations = int(
            max_tool_iterations or modell_cfg.get("max_tool_iterations", 5)
        )

        # ------------------------------------------------------------- Quelle
        # 1. Lokal trainiertes Modell (kein Download, kein API-Key nötig).
        lokaler_pfad = modell_cfg.get("local_path", STANDARD_LOKALER_PFAD)
        gefunden = _lokal_trainiertes_modell(lokaler_pfad)

        # 2. OpenAI-kompatibler API-Server.
        self.api_key = modell_cfg.get("api_key") or os.environ.get("LLM_API_KEY", "")
        self.api_base = (
            modell_cfg.get("api_base")
            or os.environ.get("LLM_API_BASE", "http://localhost:1234/v1")
        )
        self.api_modell = modell_cfg.get("api_model") or "local-model"

        if gefunden and modell_cfg.get("source", "auto") in ("auto", "local"):
            self.modus = "transformers"
            self.model_name = gefunden
            self.log.info(f"Lokal trainiertes Modell verwendet: {gefunden}")
        elif self.api_key and modell_cfg.get("source", "auto") in ("auto", "api"):
            # API-Modus – keine Modellbibliotheken nötig.
            self.modus = "api"
            self.model_name = self.api_modell
            self.log.info(f"API-Modus: {self.api_base} (Modell: {self.api_modell})")
        else:
            # 3. Fallback auf Hugging Face-Modellname (ggf. gated).
            self.modus = "transformers"
            self.model_name = model_name or modell_cfg.get(
                "name", "meta-llama/Meta-Llama-3-8B-Instruct"
            )

        # Ab hier nur für den transformers-Modus nötig.
        if self.modus != "transformers":
            self._torch = None
            return

        (
            torch,
            AutoModelForCausalLM,
            AutoTokenizer,
            StoppingCriteria,
            StoppingCriteriaList,
            TextIteratorStreamer,
        ) = _lade_bibliotheken()
        self._torch = torch
        self._streamer_klasse = TextIteratorStreamer

        gewuenscht = (device or hardware.get("device", "auto")).lower()
        cuda_da = torch.cuda.is_available()
        if gewuenscht == "auto":
            self.device = "cuda" if cuda_da else "cpu"
        else:
            self.device = gewuenscht
        if self.device == "cuda" and not cuda_da:
            raise RuntimeError("CUDA wurde angefordert, ist aber nicht verfügbar.")

        gewichte = str(hardware.get("weights_dtype", "auto")).lower()
        if gewichte == "fp32" or self.device == "cpu":
            self.dtype, self.use_4bit = torch.float32, False
            self.log.info("Modus: float32 (CPU oder fp32 erzwungen)")
        else:
            self.use_4bit = (
                load_in_4bit if load_in_4bit is not None else hardware.get("use_4bit", True)
            )
            self.dtype = torch.float16 if hardware.get("use_fp16", True) else torch.float32
            self.log.info(
                f"GPU-Modus | 4-Bit: {self.use_4bit} | Datentyp: {self.dtype}"
            )

        self.log.info(f"Lade {self.model_name} auf {self.device.upper()}")
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name, trust_remote_code=True, padding_side="left"
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        argumente: dict[str, Any] = {
            "device_map": "cpu" if self.device == "cpu" else "auto",
            # „torch_dtype“ ist veraltet – aktuelle Transformers-Versionen
            # erwarten „dtype“.
            "dtype": self.dtype,
            "trust_remote_code": True,
        }
        if self.use_4bit:
            from transformers import BitsAndBytesConfig

            argumente["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
            )
        self.model = AutoModelForCausalLM.from_pretrained(self.model_name, **argumente)
        self.model.eval()

        class _StoppKriterium(StoppingCriteria):
            """Stoppt bei Werkzeugmarken oder auf Wunsch des Benutzers."""

            def __init__(self, tokenizer, marken, abbruch: threading.Event | None):
                self.tokenizer = tokenizer
                self.marken = marken
                self.abbruch = abbruch

            def __call__(self, input_ids, scores, **kwargs):
                if self.abbruch is not None and self.abbruch.is_set():
                    return torch.ones(
                        input_ids.shape[0], dtype=torch.bool, device=input_ids.device
                    )
                text = self.tokenizer.decode(
                    input_ids[0][-60:], skip_special_tokens=True
                )
                treffer = any(marke in text for marke in self.marken)
                return torch.full(
                    (input_ids.shape[0],), treffer, dtype=torch.bool,
                    device=input_ids.device,
                )

        self._stopp_klasse = _StoppKriterium
        self._stopp_liste_klasse = StoppingCriteriaList
        self.log.info("Modell geladen.")

    def load_model(self) -> "ToolAugmentedLLM":
        """Rückwärtskompatibler Haken – das Modell wird im Konstruktor geladen."""
        return self

    # ------------------------------------------------------------ Prompt-Bau
    def _build_chat_prompt(
        self, messages: list[dict[str, str]], system_prompt: str | None = None
    ) -> str:
        """Baut einen Llama-3-kompatiblen Chat-Prompt."""
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        teile = []
        for nachricht in messages:
            rolle = nachricht.get("role", "user")
            inhalt = nachricht.get("content", "")
            if rolle not in ("system", "user", "assistant"):
                rolle = "user"
            teile.append(
                f"<|start_header_id|>{rolle}<|end_header_id|>\n{inhalt}<|eot_id|>"
            )
        teile.append("<|start_header_id|>assistant<|end_header_id|>\n")
        return "\n".join(teile)

    # ------------------------------------------------------------ Generieren
    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop_on_tool: bool = True,
        abbruch: threading.Event | None = None,
        teilstueck_rueckmeldung: Callable[[str], None] | None = None,
    ) -> str:
        """Erzeugt Text und meldet bei Bedarf jedes Teilstück einzeln."""
        if self.modus == "api":
            return self._generate_api(
                prompt,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                abbruch=abbruch,
                teilstueck_rueckmeldung=teilstueck_rueckmeldung,
            )
        return self._generate_transformers(
            prompt,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            stop_on_tool=stop_on_tool,
            abbruch=abbruch,
            teilstueck_rueckmeldung=teilstueck_rueckmeldung,
        )

    def _generate_transformers(
        self,
        prompt: str,
        max_new_tokens: int,
        temperature: float,
        top_p: float,
        stop_on_tool: bool,
        abbruch: threading.Event | None,
        teilstueck_rueckmeldung: Callable[[str], None] | None,
    ) -> str:
        """Lokale Generierung über PyTorch/Transformers."""
        torch = self._torch
        eingabe = self.tokenizer(prompt, return_tensors="pt")
        if self.device != "cpu":
            eingabe = {name: wert.to(self.model.device) for name, wert in eingabe.items()}

        kriterien = None
        if stop_on_tool or abbruch is not None:
            kriterien = self._stopp_liste_klasse(
                [self._stopp_klasse(self.tokenizer, STOPP_MARKEN, abbruch)]
            )

        argumente: dict[str, Any] = {
            **eingabe,
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "do_sample": temperature > 0,
            "pad_token_id": self.tokenizer.pad_token_id,
        }
        if kriterien is not None:
            argumente["stopping_criteria"] = kriterien

        # Ohne Rückmeldung genügt ein einfacher Durchlauf.
        if teilstueck_rueckmeldung is None:
            with torch.no_grad():
                ausgabe = self.model.generate(**argumente)
            return self.tokenizer.decode(
                ausgabe[0][eingabe["input_ids"].shape[1]:], skip_special_tokens=True
            )

        # Mit Rückmeldung: Generierung in einem Faden, Text stückweise lesen.
        streamer = self._streamer_klasse(
            self.tokenizer, skip_prompt=True, skip_special_tokens=True
        )
        argumente["streamer"] = streamer
        fehler: list[BaseException] = []

        def erzeugen() -> None:
            try:
                with torch.no_grad():
                    self.model.generate(**argumente)
            except BaseException as ausnahme:  # pragma: no cover - Laufzeitschutz
                fehler.append(ausnahme)

        faden = threading.Thread(target=erzeugen, daemon=True)
        faden.start()

        gesamt = []
        for teilstueck in streamer:
            gesamt.append(teilstueck)
            teilstueck_rueckmeldung(teilstueck)
            if abbruch is not None and abbruch.is_set():
                break
        faden.join(timeout=1.0)
        if fehler:
            raise fehler[0]
        return "".join(gesamt)

    def _generate_api(
        self,
        prompt: str,
        max_new_tokens: int,
        temperature: float,
        top_p: float,
        abbruch: threading.Event | None,
        teilstueck_rueckmeldung: Callable[[str], None] | None,
    ) -> str:
        """Generierung über einen OpenAI-kompatiblen API-Server (Streaming)."""
        try:
            import requests
        except ImportError as fehler:  # pragma: no cover
            raise ModellNichtVerfuegbar(
                "Für den API-Modus wird 'requests' benötigt."
            ) from fehler

        url = f"{self.api_base.rstrip('/')}/chat/completions"
        nutzlast = {
            "model": self.api_modell,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_new_tokens,
            "stream": teilstueck_rueckmeldung is not None,
        }
        header = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Ohne Streaming: einfache Anfrage, ganze Antwort zurückgeben.
        if teilstueck_rueckmeldung is None:
            antwort = requests.post(url, headers=header, json=nutzlast, timeout=120)
            antwort.raise_for_status()
            daten = antwort.json()
            return daten["choices"][0]["message"]["content"]

        # Mit Streaming: Server-Sent-Events stückweise auswerten.
        gesamt = []
        with requests.post(
            url, headers=header, json=nutzlast, stream=True, timeout=120
        ) as antwort:
            antwort.raise_for_status()
            for zeile in antwort.iter_lines(decode_unicode=True):
                if abbruch is not None and abbruch.is_set():
                    break
                if not zeile or not zeile.startswith("data:"):
                    continue
                daten_block = zeile[5:].strip()
                if daten_block == "[DONE]":
                    break
                try:
                    ereignis = json.loads(daten_block)
                except json.JSONDecodeError:
                    continue
                delta = (
                    ereignis.get("choices", [{}])[0]
                    .get("delta", {})
                    .get("content", "")
                )
                if delta:
                    gesamt.append(delta)
                    teilstueck_rueckmeldung(delta)
        return "".join(gesamt)

    # -------------------------------------------------------- Werkzeugaufruf
    def _execute_tool_sync(self, mcp_client: MCPClient, aufruf: ToolCall) -> ToolResult:
        """Führt ein Werkzeug synchron aus – auch aus einem Faden heraus."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(mcp_client.server.execute(aufruf))

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ausfuehrer:
            zukunft = ausfuehrer.submit(
                lambda: asyncio.run(mcp_client.server.execute(aufruf))
            )
            return zukunft.result()

    # ------------------------------------------------------------------ Chat
    def chat_with_tools(
        self,
        user_message: str,
        mcp_client: MCPClient,
        conversation_history: list[dict[str, str]] | None = None,
        teilstueck_rueckmeldung: Callable[[str], None] | None = None,
        abbruch: threading.Event | None = None,
        status_rueckmeldung: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Beantwortet eine Frage und ruft dabei Werkzeuge auf.

        Gibt ein Wörterbuch mit ``response`` (Antworttext),
        ``tool_calls`` (Liste der Aufrufe), ``tool_results`` und
        ``conversation`` (fortgeschriebener Verlauf) zurück.
        """
        verlauf = list(conversation_history or [])
        system = mcp_client.get_system_prompt_with_tools()
        nachrichten = verlauf + [{"role": "user", "content": user_message}]
        aufrufe: list[ToolCall] = []
        ergebnisse: list[ToolResult] = []
        antwort = ""

        for runde in range(self.max_tool_iterations):
            if abbruch is not None and abbruch.is_set():
                return {
                    "response": "Die Antwort wurde abgebrochen.",
                    "tool_calls": aufrufe,
                    "tool_results": ergebnisse,
                    "conversation": nachrichten,
                    "abgebrochen": True,
                }

            prompt = self._build_chat_prompt(nachrichten, system)
            # Während der Werkzeugsuche wird nicht gestreamt, weil der Text
            # ein JSON-Aufruf sein kann.
            rohtext = self.generate(prompt, stop_on_tool=True, abbruch=abbruch)
            aufruf = mcp_client.parse_tool_call(rohtext)

            if aufruf is None:
                antwort = rohtext.strip()
                nachrichten.append({"role": "assistant", "content": antwort})
                if teilstueck_rueckmeldung and antwort:
                    teilstueck_rueckmeldung(antwort)
                break

            self.log.info(f"Werkzeug-Aufruf: {aufruf.tool_name}({aufruf.arguments})")
            if status_rueckmeldung:
                status_rueckmeldung(f"Werkzeug „{aufruf.tool_name}“ wird ausgeführt ...")
            aufrufe.append(aufruf)
            ergebnis = self._execute_tool_sync(mcp_client, aufruf)
            ergebnisse.append(ergebnis)
            formatiert = mcp_client.formatiere_werkzeugergebnis(ergebnis)

            nachrichten.append(
                {
                    "role": "assistant",
                    "content": mcp_client.formatiere_werkzeugaufruf(aufruf),
                }
            )
            nachrichten.append({"role": "user", "content": formatiert})
        else:
            # Die Schleife lief ohne abschließende Antwort aus. Statt eines
            # leeren Textes wird eine letzte Antwort ohne Werkzeuge erzeugt.
            self.log.warning(
                "Höchstzahl der Werkzeug-Runden erreicht – erzeuge Schlussantwort."
            )
            if status_rueckmeldung:
                status_rueckmeldung("Schlussantwort wird erzeugt ...")
            nachrichten.append(
                {
                    "role": "user",
                    "content": "Fasse die Werkzeug-Ergebnisse jetzt in einer "
                    "abschließenden Antwort zusammen und rufe kein weiteres "
                    "Werkzeug auf.",
                }
            )
            prompt = self._build_chat_prompt(nachrichten, system)
            antwort = self.generate(
                prompt,
                stop_on_tool=False,
                abbruch=abbruch,
                teilstueck_rueckmeldung=teilstueck_rueckmeldung,
            ).strip()
            nachrichten.append({"role": "assistant", "content": antwort})

        if not antwort:
            antwort = (
                "Ich konnte keine Antwort erzeugen. Bitte formuliere die Frage neu "
                "oder prüfe die Modelleinstellungen."
            )

        return {
            "response": antwort,
            "tool_calls": aufrufe,
            "tool_results": ergebnisse,
            "conversation": nachrichten,
            "abgebrochen": False,
        }

    # Deutscher Aliasname
    frage = chat_with_tools
