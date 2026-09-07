"""shadow.inference – Weiterleitung an kimi_k3.inference.

Aufruf bleibt gleich: ``python -m shadow.inference``.
"""
from __future__ import annotations

import runpy

if __name__ == "__main__":
    # Führt kimi_k3.inference als Skript aus – gleichbedeutend mit
    # ``python -m kimi_k3.inference``.
    runpy.run_module("kimi_k3.inference", run_name="__main__")
