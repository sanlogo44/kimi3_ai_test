"""shadow – öffentliche Paket-Oberfläche von Shadow.

Dieses Paket ist die nach außen sichtbare Oberfläche. Es leitet auf das
integrierte ``kimi_k3``-Subpaket weiter, in dem die eigentliche Logik liegt
(Hardware-/Treibererkennung, Diagnose, Inferenz). So sind beide Aufrufe
gleichwertig:

    python -m shadow.inference
    python -m kimi_k3.inference

Die internen Bezeichner (``kimi_k3``) bleiben erhalten, damit bestehende
Importe und der Rust-Kern unangetastet funktionieren.
"""
from __future__ import annotations

__all__ = ["backend", "diagnose", "inference"]
