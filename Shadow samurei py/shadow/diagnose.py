"""shadow.diagnose – Weiterleitung an kimi_k3.diagnose.

Aufruf bleibt gleich: ``python -m shadow.diagnose``.
"""
from __future__ import annotations

import runpy

if __name__ == "__main__":
    # Führt kimi_k3.diagnose als Skript aus – gleichbedeutend mit
    # ``python -m kimi_k3.diagnose``.
    runpy.run_module("kimi_k3.diagnose", run_name="__main__")
