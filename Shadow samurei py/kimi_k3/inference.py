#!/usr/bin/env python3
"""kimi_k3.inference – Lokale Kimi-K3-Inferenz (transformers) + API-Client.

Zwei Modi:

    python -m kimi_k3.inference              # lokale Inferenz (transformers)
    python -m kimi_k3.inference --mode api   # OpenAI-kompatibler API-Aufruf

Lokal funktioniert auf allen Plattformen (MPS/CUDA/ROCm/CPU) mit
automatischer Geräte- und dtype-Auswahl. Der API-Modus spricht denselben
OpenAI-kompatiblen Endpunkt wie das offizielle Kimi-K3-Repo (lokal vLLM
oder gehostet auf platform.kimi.ai).
"""
from __future__ import annotations

import os
import sys
import traceback
from typing import Optional


def _pick_device():
    import torch
    choice = os.getenv("DEVICE", "auto").lower()
    if choice in ("cpu", "cuda", "mps"):
        return torch.device(choice)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch, "mps", None) is not None:
        try:
            if torch.mps.is_available():
                return torch.device("mps")
        except Exception:
            pass
    return torch.device("cpu")


def _pick_dtype(device):
    import torch
    raw = os.getenv("DTYPE", "auto").lower()
    mapping = {
        "float16": torch.float16, "fp16": torch.float16,
        "bfloat16": torch.bfloat16, "bf16": torch.bfloat16,
        "float32": torch.float32, "fp32": torch.float32,
    }
    if raw in mapping:
        return mapping[raw]
    if device.type == "cuda":
        return torch.bfloat16
    if device.type == "mps":
        return torch.float16
    return torch.float32


def run_local() -> int:
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception:
        print("FEHLER: torch/transformers fehlen. start.py ausführen?")
        traceback.print_exc()
        return 2

    model_id = os.getenv("MODEL_ID") or os.getenv("MODEL_PATH") or "moonshotai/Kimi-K3"
    prompt = os.getenv("PROMPT", "Sag Hallo und welches Modell du bist.")
    max_new = int(os.getenv("MAX_NEW_TOKENS", "128"))
    trust = os.getenv("TRUST_REMOTE_CODE", "1") == "1"

    device = _pick_device()
    dtype = _pick_dtype(device)
    print(f"[inference] model={model_id} device={device} dtype={dtype} "
          f"max_new_tokens={max_new}")
    print("[inference] lade Tokenizer ...")
    try:
        tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=trust)
    except Exception:
        print("FEHLER: Tokenizer konnte nicht geladen werden.")
        traceback.print_exc()
        return 3

    print("[inference] lade Modell (bei 1.5 TB sehr lange) ...")
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_id, torch_dtype=dtype,
            device_map="auto" if device.type == "cuda" else None,
            trust_remote_code=trust, low_cpu_mem_usage=True,
        )
    except Exception:
        print("FEHLER: Modellladung fehlgeschlagen. 2.8T-Modelle brauchen Multi-GPU.")
        traceback.print_exc()
        return 4

    if device.type != "cuda":
        model = model.to(device)
    model.eval()
    print(f"[inference] Prompt: {prompt}")
    print("-" * 60)
    inp = tok(prompt, return_tensors="pt").to(model.device)
    with torch.inference_mode():
        out = model.generate(**inp, max_new_tokens=max_new, do_sample=False)
    text = tok.decode(out[0][inp["input_ids"].shape[-1]:], skip_special_tokens=True)
    print(text)
    print("-" * 60)
    print("[inference] fertig.")
    return 0


def run_api() -> int:
    base_url = os.getenv("BASE_URL", "http://localhost:8000/v1")
    api_key = os.getenv("API_KEY", "EMPTY")
    model_id = os.getenv("MODEL_ID", "kimi-k3")
    prompt = os.getenv("PROMPT", "Sag Hallo und welches Modell du bist.")
    max_tokens = int(os.getenv("MAX_TOKENS", "512"))
    reasoning = os.getenv("REASONING_EFFORT", "max")
    try:
        from openai import OpenAI
    except Exception:
        print("FEHLER: 'openai' nicht installiert (pip install openai).")
        traceback.print_exc()
        return 2
    client = OpenAI(base_url=base_url, api_key=api_key)
    messages = [{"role": "user", "content": prompt}]
    print(f"[inference] endpoint={base_url} model={model_id} reasoning={reasoning}")
    print("-" * 60)
    kwargs = dict(model=model_id, messages=messages, max_tokens=max_tokens,
                  temperature=0.7, stream=False)
    try:
        try:
            resp = client.chat.completions.create(reasoning_effort=reasoning, **kwargs)
        except TypeError:
            resp = client.chat.completions.create(**kwargs)
        except Exception as e:
            if "reasoning" in str(e).lower():
                resp = client.chat.completions.create(**kwargs)
            else:
                raise
    except Exception:
        print(f"FEHLER: Aufruf an {base_url} fehlgeschlagen. Server läuft?")
        traceback.print_exc()
        return 3
    choice = resp.choices[0].message
    rc = getattr(choice, "reasoning_content", None) or ""
    if rc:
        print("[reasoning_content]"); print(rc); print("-" * 60)
    print(choice.content or "")
    print("-" * 60)
    print("[inference] fertig.")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    mode = "local"
    i = 0
    while i < len(args):
        if args[i] in ("--mode", "-m") and i + 1 < len(args):
            mode = args[i + 1]; i += 1
        i += 1
    if mode == "api":
        return run_api()
    return run_local()


if __name__ == "__main__":
    sys.exit(main())
