#!/usr/bin/env python
"""
run_api.py — Run Kimi-K3 inference against an OpenAI-compatible endpoint.

The official Kimi-K3 README recommends serving via vLLM / SGLang / TokenSpeed
and exposes an OpenAI/Anthropic-compatible API. This script speaks that API, so
it works identically against:

  * a locally served vLLM instance (BASE_URL=http://localhost:8000/v1)
  * the hosted Kimi platform      (BASE_URL=https://api.moonshot.ai/v1)

Env vars:
  BASE_URL          API base URL                  (default: http://localhost:8000/v1)
  API_KEY           API key                        (default: "EMPTY" for local vLLM)
  MODEL_ID          Model name / id                (default: kimi-k3)
  PROMPT            User prompt                    (default: a hello-world prompt)
  SYSTEM_PROMPT     Optional system prompt        (default: none)
  MAX_TOKENS        Max tokens to generate         (default: 512)
  TEMPERATURE       Sampling temperature          (default: 0.7)
  REASONING_EFFORT low|high|max                    (default: max) — Kimi-K3 thinking
"""
from __future__ import annotations

import os
import sys
import traceback


def main() -> int:
    base_url = os.getenv("BASE_URL", "http://localhost:8000/v1")
    api_key = os.getenv("API_KEY", "EMPTY")
    model_id = os.getenv("MODEL_ID", "kimi-k3")
    prompt = os.getenv("PROMPT", "Say hello and tell me what model you are.")
    system_prompt = os.getenv("SYSTEM_PROMPT", "")
    max_tokens = int(os.getenv("MAX_TOKENS", "512"))
    temperature = float(os.getenv("TEMPERATURE", "0.7"))
    reasoning_effort = os.getenv("REASONING_EFFORT", "max")

    try:
        from openai import OpenAI
    except Exception:
        print("FATAL: 'openai' package not installed. Run: pip install openai")
        traceback.print_exc()
        return 2

    client = OpenAI(base_url=base_url, api_key=api_key)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    print(f"[run_api] endpoint={base_url} model={model_id} "
          f"reasoning={reasoning_effort} max_tokens={max_tokens}")
    print("[run_api] prompt:", prompt)
    print("-" * 60)

    try:
        kwargs = dict(
            model=model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=False,
        )
        # reasoning_effort is Kimi-specific; pass it if supported by the server.
        try:
            resp = client.chat.completions.create(reasoning_effort=reasoning_effort, **kwargs)
        except TypeError:
            resp = client.chat.completions.create(**kwargs)
        except Exception as e:
            # Some servers reject unknown params; retry without reasoning_effort.
            if "reasoning" in str(e).lower():
                resp = client.chat.completions.create(**kwargs)
            else:
                raise
    except Exception:
        print(f"FATAL: request to {base_url} failed. Is the server running?")
        traceback.print_exc()
        return 3

    choice = resp.choices[0].message
    reasoning = getattr(choice, "reasoning_content", None) or ""
    content = choice.content or ""

    if reasoning:
        print("[reasoning_content]")
        print(reasoning)
        print("-" * 60)
    print("[response]")
    print(content)
    print("-" * 60)
    print("[run_api] done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
