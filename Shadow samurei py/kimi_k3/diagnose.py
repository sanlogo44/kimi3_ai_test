#!/usr/bin/env python3
"""kimi_k3.diagnose – GPU-Verfügbarkeitsdiagnose nach der Installation.

Importiert torch, meldet Version/Plattform/CUDA/MPS/HIP, das gewählte Gerät
und führt einen kleinen Matmul-Smoketest aus. Aufruf als Modul:

    python -m kimi_k3.diagnose
"""
from __future__ import annotations

import sys
import traceback


def run() -> int:
    try:
        import torch
    except Exception:
        print("FEHLER: torch konnte nicht importiert werden. Installation fehlgeschlagen?")
        traceback.print_exc()
        return 2

    print("\n=== Umgebung ===")
    print(f"Python      : {sys.version.split()[0]}")
    print(f"Plattform   : {sys.platform}")
    print(f"torch       : {torch.__version__}")
    print(f"torch CUDA  : {torch.version.cuda}")
    print(f"torch HIP   : {torch.version.hip}")

    print("\n=== Beschleuniger ===")
    cuda_ok = bool(torch.cuda.is_available())
    mps_ok = False
    mps_built = False
    if getattr(torch, "mps", None) is not None:
        try:
            mps_ok = bool(torch.mps.is_available())
        except Exception:
            mps_ok = False
        try:
            mps_built = bool(torch.mps.is_built())
        except Exception:
            mps_built = False
    print(f"CUDA verfügbar : {cuda_ok}")
    if cuda_ok:
        for i in range(torch.cuda.device_count()):
            print(f"  [{i}] {torch.cuda.get_device_name(i)} "
                  f"(cap {torch.cuda.get_device_capability(i)})")
    print(f"MPS verfügbar  : {mps_ok} (gebaut: {mps_built})")

    if cuda_ok:
        device = torch.device("cuda")
    elif mps_ok:
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    print(f"\n=== Gewähltes Gerät ===\n{device}")

    print("\n=== Smoketest (512x512 Matmul) ===")
    try:
        a = torch.randn(512, 512, device=device)
        b = torch.randn(512, 512, device=device)
        c = a @ b
        if device.type == "cuda":
            torch.cuda.synchronize()
        print(f"OK  shape={tuple(c.shape)} dtype={c.dtype} mean={float(c.mean()):.4f}")
    except Exception:
        print(f"FEHLER Matmul auf {device}:")
        traceback.print_exc()
        return 3

    print("\n=== Ergebnis ===")
    if device.type == "cpu":
        print("Läuft auf CPU – gültig, aber für ein 2.8T-Modell sehr langsam.")
    else:
        print(f"Beschleuniger einsatzbereit: {device}.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
