# Kimi-K3 — Cross-Platform Setup

A robust bash-based environment setup for the
[`MoonshotAI/Kimi-K3`](https://github.com/MoonshotAI/Kimi-K3) repository.

## What the official repo provides

The Kimi-K3 README ships **no local install instructions, no `requirements.txt`,
no `pyproject.toml`, and no local-inference code**. It recommends serving the
model via **vLLM / SGLang / TokenSpeed** and provides an **OpenAI-compatible
API example** ([README](https://github.com/MoonshotAI/Kimi-K3/blob/main/README.md)).
Kimi-K3 is a **2.8T-parameter MoE** model (~1.56 TB of MXFP4 weights) using
MXFP4 weights and MXFP8 activations ([Moonshot AI](https://www.moonshot.ai/)).

This setup matches that real-world pattern:

- Correct PyTorch per platform (Apple Silicon MPS, NVIDIA CUDA, AMD ROCm, CPU).
- vLLM serving path for Linux + CUDA/ROCm (the README's recommended engine).
- A HuggingFace `transformers` fallback so inference is still runnable on
  macOS MPS, ROCm, CPU, and native Windows — where vLLM is unavailable.

## Files

| File | Purpose |
|------|---------|
| `setup.sh` | OS/hardware detection, venv, correct PyTorch, repo deps, vLLM, diagnostic |
| `run_inference.sh` | Standardized runner (`vllm` / `api` / `local` modes, auto-detects) |
| `scripts/diagnose_torch.py` | Verifies CUDA/MPS/ROCm availability + a smoke-test matmul |
| `scripts/run_api.py` | Calls an OpenAI-compatible endpoint (local vLLM or hosted Kimi API) |
| `scripts/run_local.py` | Loads the model with `transformers` (cross-platform fallback) |

## Quick start

```bash
chmod +x setup.sh run_inference.sh
./setup.sh                       # creates .venv, installs PyTorch + deps, runs diagnostic
source .venv/bin/activate        # Windows Git Bash: source .venv/Scripts/activate
./run_inference.sh               # auto-picks vllm if installed, else transformers
```

## Configuration (env vars)

### setup.sh
| Variable | Default | Meaning |
|----------|---------|---------|
| `PYTHON_BIN` | `python3` | Interpreter to build the venv with |
| `VENV_DIR` | `.venv` | Virtual-env location |
| `TORCH_BACKEND` | `auto` | `auto\|cpu\|cuda\|rocm\|mps` |
| `CUDA_VERSION` | `cu124` | `cu121\|cu124\|cu126\|cu128` |
| `ROCM_VERSION` | `rocm6.2` | `rocm6.1\|rocm6.2` (Linux only) |
| `INSTALL_VLLM` | `auto` | `auto\|yes\|no` (vLLM only on Linux + CUDA/ROCm) |
| `EXTRA_REQUIREMENTS` | _empty_ | Extra pip specs, space-separated |
| `REPO_DIR` | cwd | Where to look for `requirements.txt` / `pyproject.toml` |
| `PYTHON_MIN` | `3.10` | Minimum Python major.minor |
| `SKIP_DRIVER_CHECK` | `0` | Set `1` to bypass the pre-install GPU driver compatibility check |

### run_inference.sh
| Variable | Default | Meaning |
|----------|---------|---------|
| `MODE` | `auto` | `vllm\|api\|local` (`auto` picks vLLM if installed, else local) |
| `MODEL_ID` | `moonshotai/Kimi-K3` | HF model id or local path |
| `PROMPT` | hello-world | User prompt |
| `MAX_NEW_TOKENS` | `128` | Generation length |
| `VLLM_PORT` | `8000` | vLLM server port (vllm mode) |
| `BASE_URL` / `API_KEY` | localhost / `EMPTY` | OpenAI-compatible endpoint (api mode) |

## Backend detection logic

| Platform | Arch | Detected backend | PyTorch source |
|----------|------|------------------|-----------------|
| macOS | arm64 | **MPS** | Default PyPI index (MPS is built into macOS wheels) |
| macOS | x86_64 | CPU | Default PyPI index |
| Linux / WSL | x86_64 + `nvidia-smi` | **CUDA** | `https://download.pytorch.org/whl/${CUDA_VERSION}` |
| Linux | + `rocminfo` or `/opt/rocm` | **ROCm** | `https://download.pytorch.org/whl/${ROCM_VERSION}` |
| Windows (Git Bash) | + `nvidia-smi` | **CUDA** | CUDA wheel index |
| otherwise | — | CPU | Default PyPI index |

Notes:
- **MPS** is part of the standard macOS PyTorch wheels — no special index is needed.
- **CUDA wheels bundle the CUDA runtime**; an NVIDIA driver is still required.
- **Driver compatibility is verified before install.** For CUDA, the installed NVIDIA driver is checked against the minimum required per CUDA release (e.g. cu124 needs Linux driver >= 550.54.14 / Windows >= 551.61; cu128 needs >= 570.26 / 570.65), per the [NVIDIA CUDA Toolkit Release Notes](https://docs.nvidia.com/cuda/cuda-toolkit-release-notes/index.html). For ROCm, the script checks the amdgpu kernel driver is loaded and compares the installed ROCm userspace version against the requested wheel, respecting AMD's ±2-release forward/backward compatibility. Set `SKIP_DRIVER_CHECK=1` to bypass (e.g. in containers where the driver is forwarded).
- **ROCm is Linux-only** — the script refuses on macOS / native Windows.
- **vLLM on ROCm is more conditional than on CUDA.** The installer attempts it on Linux + ROCm, but if the vLLM install or serving fails, the runner falls back to the `transformers` path. If a wheel is unavailable for your `CUDA_VERSION` / `ROCM_VERSION`, check the [PyTorch install selector](https://pytorch.org/get-started/locally/) for a compatible value.
- On Windows the venv python lives at `.venv/Scripts/python.exe`; the scripts handle this automatically.

## Running against the hosted Kimi API

```bash
MODE=api \
  BASE_URL=https://api.moonshot.ai/v1 \
  API_KEY=$KIMI_API_KEY \
  MODEL_ID=kimi-k3 \
  ./run_inference.sh
```

## Reality check

Kimi-K3 is ~1.56 TB of weights. Full local inference is a multi-GPU data-center
task, not a laptop task. These scripts give you a correct, reproducible stack on
every platform and the right entrypoints; for serious local serving use vLLM on a
CUDA cluster with tensor parallelism, or call the hosted API.
