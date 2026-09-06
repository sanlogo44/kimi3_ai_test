#!/usr/bin/env python
"""
run_local.py — Local Kimi-K3 inference via HuggingFace transformers.

This is the cross-platform fallback used when vLLM is not available
(macOS/Apple Silicon MPS, AMD ROCm without vLLM, CPU, native Windows).
It auto-detects the accelerator, picks a sensible dtype, and runs generate().

NOTE: Kimi-K3 is a 2.8T-parameter MoE model (~1.56 TB of MXFP4 weights). Full
local inference is not practical on a single workstation. This script is the
correct entrypoint for smaller / quantized checkpoints and for verifying the
PyTorch stack end-to-end on every platform.

Env vars:
  MODEL_ID        HuggingFace model id or local path (default: moonshotai/Kimi-K3)
  MODEL_PATH      Alias of MODEL_ID (MODEL_ID takes precedence)
  PROMPT          User prompt                       (default: hello-world)
  MAX_NEW_TOKENS  Tokens to generate               (default: 128)
  DEVICE          auto|cpu|cuda|mps                (default: auto)
  DTYPE           auto|float16|bfloat16|float32   (default: auto)
  TRUST_REMOTE_CODE 1|0  allow custom model code   (default: 1)
"""
from __future__ import annotations

import os
import sys
import traceback


def pick_device() -> "torch.device":
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


def pick_dtype(device) -> "torch.dtype":
    import torch
    raw = os.getenv("DTYPE", "auto").lower()
    mapping = {
        "float16": torch.float16,
        "fp16": torch.float16,
        "bfloat16": torch.bfloat16,
        "bf16": torch.bfloat16,
        "float32": torch.float32,
        "fp32": torch.float32,
    }
    if raw in mapping:
        return mapping[raw]
    # auto: prefer bf16 on CUDA, fp16 on MPS, fp32 on CPU.
    if device.type == "cuda":
        return torch.bfloat16
    if device.type == "mps":
        return torch.float16
    return torch.float32


def main() -> int:
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception:
        print("FATAL: torch/transformers not importable. Did setup.sh finish?")
        traceback.print_exc()
        return 2

    model_id = os.getenv("MODEL_ID") or os.getenv("MODEL_PATH") or "moonshotai/Kimi-K3"
    prompt = os.getenv("PROMPT", "Say hello and tell me what model you are.")
    max_new_tokens = int(os.getenv("MAX_NEW_TOKENS", "128"))
    trust_remote_code = os.getenv("TRUST_REMOTE_CODE", "1") == "1"

    device = pick_device()
    dtype = pick_dtype(device)

    print(f"[run_local] model={model_id} device={device} dtype={dtype} "
          f"max_new_tokens={max_new_tokens}")
    print("[run_local] loading tokenizer...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            model_id, trust_remote_code=trust_remote_code
        )
    except Exception:
        print("FATAL: could not load tokenizer. Check MODEL_ID / network / HF token.")
        traceback.print_exc()
        return 3

    print("[run_local] loading model (this can take a very long time for 1.5TB)...")
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=dtype,
            device_map="auto" if device.type == "cuda" else None,
            trust_remote_code=trust_remote_code,
            low_cpu_mem_usage=True,
        )
    except Exception:
        print("FATAL: model load failed. For a 2.8T model you need a multi-GPU "
              "cluster or a quantized checkpoint.")
        traceback.print_exc()
        return 4

    if device.type != "cuda":  # device_map=auto already placed tensors
        model = model.to(device)
    model.eval()

    print(f"[run_local] prompt: {prompt}")
    print("-" * 60)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.inference_mode():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
        )
    text = tokenizer.decode(out[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)
    print(text)
    print("-" * 60)
    print("[run_local] done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
