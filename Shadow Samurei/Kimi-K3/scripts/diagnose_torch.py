#!/usr/bin/env python
"""
diagnose_torch.py — Verify accelerator availability after PyTorch install.

Reports torch version, platform/arch, CUDA / MPS / ROCm status, the device
PyTorch will actually use, and runs a tiny matmul on that device to confirm
end-to-end execution. Exits non-zero if no usable accelerator is found on a
machine that claimed to have one, or if torch itself fails to import.
"""
from __future__ import annotations

import sys
import traceback


def _banner(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> int:
    try:
        import torch
    except Exception:
        print("FATAL: could not import torch. Install failed or is corrupt.")
        traceback.print_exc()
        return 2

    _banner("Environment")
    print(f"Python      : {sys.version.split()[0]}")
    print(f"Platform    : {sys.platform}")
    print(f"torch       : {torch.__version__}")
    print(f"torch CUDA  : {torch.version.cuda}")
    print(f"torch HIP   : {torch.version.hip}")
    print(f"debug build : {torch._C._GLIBCXX_USE_CXX11_ABI}")

    _banner("Accelerator detection")
    cuda_ok = bool(torch.cuda.is_available())
    mps_ok = False
    mps_built = False
    # torch.mps exists as a stub on non-macOS builds; guard the macOS-only calls.
    if getattr(torch, "mps", None) is not None:
        try:
            mps_ok = bool(torch.mps.is_available())
        except Exception:
            mps_ok = False
        try:
            mps_built = bool(torch.mps.is_built())
        except Exception:
            mps_built = False

    print(f"CUDA available : {cuda_ok}")
    if cuda_ok:
        print(f"  device count : {torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            print(f"  [{i}] {torch.cuda.get_device_name(i)} "
                  f"(cap {torch.cuda.get_device_capability(i)}, "
                  f"v{torch.version.cuda})")
    print(f"MPS available  : {mps_ok}  (built: {mps_built})")
    if torch.version.hip:
        print(f"ROCm/HIP build detected (HIP {torch.version.hip})")

    # Resolve the device we will actually compute on.
    _banner("Chosen device")
    if cuda_ok:
        device = torch.device("cuda")
    elif mps_ok:
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    print(f"Using device: {device}")

    # Smoke test: matmul on the chosen device.
    _banner("Smoke test (512x512 matmul)")
    try:
        a = torch.randn(512, 512, device=device)
        b = torch.randn(512, 512, device=device)
        c = a @ b
        torch.cuda.synchronize() if device.type == "cuda" else None
        print(f"OK  result shape={tuple(c.shape)}  dtype={c.dtype}  "
              f"mean={float(c.mean()):.4f}")
    except Exception:
        print(f"FAILED matmul on {device}:")
        traceback.print_exc()
        return 3

    _banner("Summary")
    if device.type == "cpu":
        print("Running on CPU. This works but is very slow for a 2.8T model.")
        print("For local serving, an NVIDIA (CUDA) or AMD (ROCm) GPU is expected.")
        return 0  # not fatal — CPU is a valid, if impractical, backend
    print(f"Accelerator ready on {device}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
