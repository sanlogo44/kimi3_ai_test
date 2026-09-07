#!/usr/bin/env python3
"""kimi_k3.backend – Hardware-/Treibererkennung und PyTorch-Installation.

Dieses Modul ist das Herzstück der Integration von Kimi-K3 in die App.
Es ist reines Python (keine Shell-Abhängigkeit) und übernimmt:

  1. Erkennung von Betriebssystem, Architektur und Beschleuniger
     (Apple Silicon MPS, NVIDIA CUDA, AMD ROCm, CPU).
  2. Treiberkompatibilitätsprüfung VOR der Installation
     (NVIDIA-Mindesttreiber je CUDA-Release; amdgpu-/ROCm-Userspace-Check).
  3. Installation des passenden PyTorch-Wheels über den richtigen Index.

Die Mindesttreiber je CUDA-Release entsprechen den NVIDIA CUDA Toolkit
Release Notes. ROCm erlaubt +/-2 Releases Vorwärts-/Rückwärtskompatibilität
zwischen amdgpu-Kerneltreiber und Userspace (AMD ROCm-Dokumentation).
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Mindest-NVIDIA-Treiber je CUDA-Release (GA) laut NVIDIA Release Notes.
# Linux- und Windows-Werte getrennt.
MIN_NVIDIA_DRIVER = {
    "cu121": {"linux": "530.30.02", "windows": "531.14"},
    "cu124": {"linux": "550.54.14", "windows": "551.61"},
    "cu126": {"linux": "560.28.03", "windows": "560.76"},
    "cu128": {"linux": "570.26", "windows": "570.65"},
}

VALID_CUDA_VERSIONS = tuple(MIN_NVIDIA_DRIVER.keys())
VALID_ROCM_VERSIONS = ("rocm6.1", "rocm6.2")


@dataclass
class Backend:
    """Ergebnis der Backend-Erkennung."""
    name: str               # cpu | cuda | rocm | mps | xpu | npu | tpu
    platform: str           # linux | macos | windows
    arch: str               # z. B. arm64, x86_64
    is_wsl: bool = False
    nvidia_gpu: str = ""
    nvidia_driver: str = ""
    nvidia_max_cuda: str = ""
    rocm_installed: str = ""
    amdgpu_loaded: bool = False
    # Nur erkannt, wenn die passende Vendor-Runtime installiert ist.
    # Diese Geräte werden beim Training erst genutzt, wenn das zugehörige
    # PyTorch-Backend (torch_npu / torch_xla / intel_extension_for_pytorch)
    # importierbar ist. Die Installation dieser Wheels übernimmt Shadow nicht
    # automatisch – siehe Hinweise unten.
    has_xpu: bool = False
    has_npu: bool = False
    has_tpu: bool = False
    openvino_present: bool = False   # OpenVINO = Inferenz, kein Trainings-Backend


def detect_vendor_backends() -> tuple[bool, bool, bool, bool]:
    """Erkennt optionale Vendor-Backends: (xpu, npu, tpu, openvino).

    - xpu:  ``intel_extension_for_pytorch`` (Intel oneAPI-Grafik)
    - npu:  ``torch_npu`` (Huawei Ascend) – nicht OpenVINO
    - tpu:  ``torch_xla`` (Google Cloud TPU)
    - openvino: Intel OpenVINO – nur Inferenz, kein ``.to("npu")``-Training
    """
    xpu = npu = tpu = openvino = False
    try:
        import intel_extension_for_pytorch  # noqa: F401
        xpu = True
    except Exception:
        pass
    try:
        import torch_npu  # noqa: F401
        npu = True
    except Exception:
        pass
    try:
        import torch_xla  # noqa: F401
        tpu = True
    except Exception:
        pass
    try:
        import openvino  # noqa: F401
        openvino = True
    except Exception:
        pass
    return xpu, npu, tpu, openvino


def _ver_ge(a: str, b: str) -> bool:
    """True, wenn Version a >= b (punktgetrennte Zahlen)."""
    def key(v: str):
        parts = []
        for p in re.split(r"[.+-]", v):
            m = re.match(r"\d+", p)
            parts.append(int(m.group()) if m else 0)
        return parts
    try:
        return key(a) >= key(b)
    except Exception:
        return False


def _run(cmd, timeout: int = 8) -> str:
    """Führt einen Befehl aus und liefert stdout (leer bei Fehler)."""
    try:
        p = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=timeout,
        )
        return p.stdout
    except Exception:
        return ""


def detect_platform() -> tuple[str, str, bool]:
    """Liefert (platform, arch, is_wsl)."""
    s = platform.system()
    m = platform.machine().lower()
    plat = {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}.get(s, "unknown")
    if plat == "windows" and "cygwin" in sys.platform.lower():
        plat = "windows"
    is_wsl = False
    if plat == "linux":
        v = _run(["uname", "-r"]) + " " + Path("/proc/version").read_text(errors="ignore")
        is_wsl = "microsoft" in v.lower()
    return plat, m, is_wsl


def detect_nvidia() -> tuple[bool, str, str, str]:
    """Liefert (found, gpu_name, driver_version, max_cuda_from_driver)."""
    if not shutil.which("nvidia-smi"):
        return False, "", "", ""
    out = _run(["nvidia-smi", "--query-gpu=name,driver_version",
                "--format=csv,noheader"])
    if not out.strip():
        return False, "", "", ""
    parts = [p.strip() for p in out.splitlines()[0].split(",")]
    if len(parts) < 2:
        return False, "", "", ""
    name, driver = parts[0], parts[1]
    header = _run(["nvidia-smi"])
    m = re.search(r"CUDA Version:\s*([0-9.]+)", header)
    return True, name, driver, m.group(1) if m else ""


def detect_rocm(plat: str) -> tuple[bool, str, bool]:
    """Liefert (found, rocm_version, amdgpu_loaded) – nur Linux."""
    if plat != "linux":
        return False, "", False
    amdgpu = _run(["lsmod"])
    amdgpu_loaded = "amdgpu" in amdgpu
    if not amdgpu_loaded and Path("/dev/dri").is_dir():
        amdgpu_loaded = True
    rocm_ver = ""
    rv = Path("/opt/rocm/.rocm-version")
    if rv.is_file():
        m = re.search(r"\d+\.\d+\.\d+", rv.read_text(errors="ignore"))
        rocm_ver = m.group(0) if m else ""
    elif shutil.which("rocminfo"):
        info = _run(["rocminfo"])
        m = re.search(r"\d+\.\d+\.\d+", info)
        rocm_ver = m.group(0) if m else ""
    found = bool(rocm_ver) or Path("/opt/rocm").is_dir() or bool(shutil.which("rocminfo"))
    return found, rocm_ver, amdgpu_loaded


def detect_backend() -> Backend:
    """Erkennt Betriebssystem, Architektur und Beschleuniger."""
    plat, arch, is_wsl = detect_platform()
    nv_found, nv_name, nv_drv, nv_max = detect_nvidia()
    rocm_found, rocm_ver, amdgpu = detect_rocm(plat)
    xpu, npu, tpu, openvino = detect_vendor_backends()

    apple_silicon = (plat == "macos" and arch in ("arm64", "aarch64"))

    if apple_silicon:
        name = "mps"
    elif nv_found:
        name = "cuda"
    elif npu:
        name = "npu"
    elif tpu:
        name = "tpu"
    elif xpu:
        name = "xpu"
    elif rocm_found:
        name = "rocm"
    else:
        name = "cpu"

    return Backend(
        name=name, platform=plat, arch=arch, is_wsl=is_wsl,
        nvidia_gpu=nv_name, nvidia_driver=nv_drv, nvidia_max_cuda=nv_max,
        rocm_installed=rocm_ver, amdgpu_loaded=amdgpu,
        has_xpu=xpu, has_npu=npu, has_tpu=tpu, openvino_present=openvino,
    )


def check_driver_compat(backend: Backend, cuda_version: str,
                        rocm_version: str) -> list[str]:
    """Prüft Treiberkompatibilität. Liefert Liste von Warnungen (leer = ok).

    Löst RuntimeError aus, wenn der Treiber definitiv zu alt ist.
    """
    warnings: list[str] = []

    if backend.name == "cuda":
        if cuda_version not in MIN_NVIDIA_DRIVER:
            raise RuntimeError(
                f"Nicht unterstützte CUDA_VERSION='{cuda_version}'. "
                f"Erlaubt: {', '.join(VALID_CUDA_VERSIONS)}.")
        if backend.nvidia_driver:
            key = "windows" if backend.platform == "windows" else "linux"
            min_drv = MIN_NVIDIA_DRIVER[cuda_version][key]
            if not _ver_ge(backend.nvidia_driver, min_drv):
                raise RuntimeError(
                    f"NVIDIA-Treiber {backend.nvidia_driver} ist zu alt für "
                    f"{cuda_version} (benötigt >= {min_drv}). Treiber "
                    f"aktualisieren unter https://www.nvidia.com/drivers "
                    f"oder ältere CUDA_VERSION wählen.")
        else:
            warnings.append(
                "Kein NVIDIA-Treiber erkannt (nvidia-smi fehlt). CUDA-Wheels "
                "werden installiert, aber torch.cuda.is_available() ist False.")

    elif backend.name == "rocm":
        if backend.platform != "linux":
            raise RuntimeError("ROCm wird nur unter Linux unterstützt.")
        if not backend.amdgpu_loaded:
            warnings.append(
                "amdgpu-Kerneltreiber / /dev/dri nicht erkannt; ROCm-Wheels "
                "werden installiert, aber die GPU ist evtl. nicht nutzbar.")
        if backend.rocm_installed:
            req_major = rocm_version.replace("rocm", "").split(".")[0]
            inst_major = backend.rocm_installed.split(".")[0]
            if req_major != inst_major:
                warnings.append(
                    f"Installiertes ROCm major {inst_major} weicht von "
                    f"angefordertem {req_major} ab; das {rocm_version}-Wheel "
                    f"funktioniert evtl. nicht.")
        else:
            warnings.append(
                "Kein ROCm-Userspace erkannt (kein /opt/rocm oder rocminfo). "
                f"Das {rocm_version}-Wheel wird installiert, kann aber zur "
                f"Laufzeit scheitern.")
        if not shutil.which("rocm-smi"):
            warnings.append("rocm-smi nicht gefunden; vollständigen ROCm-Stack installieren.")
    return warnings


def torch_install_args(backend: Backend, cuda_version: str,
                       rocm_version: str) -> tuple[list[str], Optional[str]]:
    """Liefert (pip-specs, index-url) für das passende PyTorch-Wheel."""
    pkgs = ["torch", "torchvision", "torchaudio"]
    if backend.name in ("cpu", "mps"):
        # CPU-Wheels vom dedizierten Index (verhindert multi-GB CUDA-Bundle
        # auf Linux x86_64); macOS-arm64-Wheels enthalten MPS.
        return pkgs, "https://download.pytorch.org/whl/cpu"
    if backend.name == "cuda":
        return pkgs, f"https://download.pytorch.org/whl/{cuda_version}"
    if backend.name == "rocm":
        return pkgs, f"https://download.pytorch.org/whl/{rocm_version}"
    return pkgs, None


def install_pytorch(venv_python: Path, backend: Backend,
                    cuda_version: str = "cu124",
                    rocm_version: str = "rocm6.2",
                    skip_driver_check: bool = False) -> None:
    """Installiert das passende PyTorch in die venv (Treibercheck vorher)."""
    print(f"[kimi_k3] Backend: {backend.name} ({backend.platform}/{backend.arch})")
    if backend.nvidia_gpu:
        print(f"[kimi_k3] NVIDIA: {backend.nvidia_gpu}, Treiber "
              f"{backend.nvidia_driver}, max. CUDA {backend.nvidia_max_cuda}")
    if backend.rocm_installed:
        print(f"[kimi_k3] ROCm: {backend.rocm_installed}")
    if backend.has_xpu:
        print("[kimi_k3] Intel XPU erkannt (intel_extension_for_pytorch).")
    if backend.has_npu:
        print("[kimi_k3] Huawei-Ascend-NPU erkannt (torch_npu).")
    if backend.has_tpu:
        print("[kimi_k3] Google-TPU erkannt (torch_xla).")
    if backend.openvino_present:
        print("[kimi_k3] OpenVINO vorhanden – Inferenz möglich, kein Trainings-Backend.")

    # NPU/TPU/XPU benötigen spezielle Vendor-Wheels, die Shadow nicht
    # automatisch installiert. Stattdessen erfolgt ein Hinweis.
    if backend.name in ("npu", "tpu", "xpu"):
        vendor_pakete = {
            "npu": "torch_npu (Ascend/CANN)",
            "tpu": "torch_xla (Cloud TPU)",
            "xpu": "intel_extension_for_pytorch (oneAPI)",
        }[backend.name]
        print(f"[kimi_k3] Hinweis: {vendor_pakete} muss passend zur Hardware "
              f"installiert sein. Shadow installiert dieses Wheel nicht selbst.")
        if not skip_driver_check:
            # Treibercheck entfällt für Vendor-Geräte; nur CUDA/ROCm sind oben geprüft.
            pass

    if not skip_driver_check:
        warns = check_driver_compat(backend, cuda_version, rocm_version)
        for w in warns:
            print(f"[kimi_k3] ! {w}")
    else:
        print("[kimi_k3] Treibercheck übersprungen (SKIP_DRIVER_CHECK=1).")

    pkgs, index = torch_install_args(backend, cuda_version, rocm_version)
    cmd = [str(venv_python), "-m", "pip", "install", *pkgs]
    if index:
        cmd += ["--index-url", index]
    print(f"[kimi_k3] Installiere PyTorch: {' '.join(pkgs)}"
          + (f"  (Index: {index})" if index else ""))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise RuntimeError(
            f"PyTorch-Installation fehlgeschlagen (Backend={backend.name}). "
            f"Pip-Rückgabewert {r.returncode}.")
    print("[kimi_k3] PyTorch installiert.")
