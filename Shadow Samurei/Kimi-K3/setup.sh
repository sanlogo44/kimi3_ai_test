#!/usr/bin/env bash
# =============================================================================
# setup.sh — Cross-platform environment setup for the Kimi-K3 repository
#   (https://github.com/MoonshotAI/Kimi-K3)
#
# What it does:
#   1. Detects the operating system (Linux / macOS / Windows-Git-Bash / WSL)
#      and hardware backend (Apple Silicon MPS, NVIDIA CUDA, AMD ROCm, CPU).
#   2. Creates an isolated Python virtual environment.
#   3. Installs the correct PyTorch build for the detected backend
#      (MPS ships inside the standard macOS wheels; CUDA/ROCm use dedicated
#      PyTorch wheel indexes).
#   4. Installs the repository's own dependencies (requirements.txt /
#      pyproject.toml) when present, otherwise a sensible default set of
#      inference packages (transformers, accelerate, safetensors, ...).
#   5. Optionally installs vLLM on Linux + CUDA/ROCm (the engine recommended
#      by the Kimi-K3 README for OpenAI-compatible local serving).
#   6. Runs a GPU-availability diagnostic.
#
# Configure behaviour with environment variables (all optional):
#   PYTHON_BIN         Python interpreter to use            (default: python3)
#   VENV_DIR           Virtual-env location                 (default: .venv)
#   TORCH_BACKEND      auto|cpu|cuda|rocm|mps               (default: auto)
#   CUDA_VERSION       cu121|cu124|cu126|cu128              (default: cu124)
#   ROCM_VERSION       rocm6.1|rocm6.2                      (default: rocm6.2)
#   INSTALL_VLLM       auto|yes|no                          (default: auto)
#   EXTRA_REQUIREMENTS extra pip spec(s), space-separated   (default: "")
#   REPO_DIR           repo root for requirements.txt lookup(default: cwd)
#   PYTHON_MIN         minimum Python major.minor           (default: 3.10)
#   SKIP_DRIVER_CHECK  1 to skip the pre-install driver check   (default: 0)
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh
#   # or e.g. TORCH_BACKEND=cuda CUDA_VERSION=cu126 ./setup.sh
# =============================================================================

set -uo pipefail

# ---------- Logging helpers --------------------------------------------------
if [[ -t 1 ]]; then
  C_RED=$'\033[1;31m'; C_GRN=$'\033[1;32m'; C_YEL=$'\033[1;33m'
  C_BLU=$'\033[1;34m'; C_DIM=$'\033[2m'; C_RST=$'\033[0m'
else
  C_RED=""; C_GRN=""; C_YEL=""; C_BLU=""; C_DIM=""; C_RST=""
fi

log()   { printf '%s▶%s %s\n' "$C_BLU" "$C_RST" "$*"; }
ok()    { printf '%s✓%s %s\n' "$C_GRN" "$C_RST" "$*"; }
warn()  { printf '%s!%s %s\n' "$C_YEL" "$C_RST" "$*" >&2; }
die()   { printf '%s✗%s %s\n' "$C_RED" "$C_RST" "$*" >&2; exit 1; }

# Compare dotted version strings. Returns 0 (true) iff $1 >= $2.
ver_ge() {
  [[ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | tail -n1)" == "$1" ]]
}

# ---------- Configuration ----------------------------------------------------
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
TORCH_BACKEND="${TORCH_BACKEND:-auto}"
CUDA_VERSION="${CUDA_VERSION:-cu124}"
ROCM_VERSION="${ROCM_VERSION:-rocm6.2}"
INSTALL_VLLM="${INSTALL_VLLM:-auto}"
EXTRA_REQUIREMENTS="${EXTRA_REQUIREMENTS:-}"
REPO_DIR="${REPO_DIR:-$(pwd)}"
PYTHON_MIN="${PYTHON_MIN:-3.10}"
SKIP_DRIVER_CHECK="${SKIP_DRIVER_CHECK:-0}"

# Resolve the in-venv python executable path (handles bin/ vs Scripts/)
venv_python() {
  if [[ -x "${VENV_DIR}/bin/python" ]]; then
    printf '%s' "${VENV_DIR}/bin/python"
  elif [[ -x "${VENV_DIR}/Scripts/python.exe" ]]; then
    printf '%s' "${VENV_DIR}/Scripts/python.exe"
  else
    printf '%s' "${VENV_DIR}/bin/python"
  fi
}

# ============================================================================
# 1. OS detection
# ============================================================================
log "Detecting operating system..."
OS_KERNEL="$(uname -s 2>/dev/null || echo unknown)"
ARCH="$(uname -m 2>/dev/null || echo unknown)"
case "${OS_KERNEL}" in
  Linux)     PLATFORM="linux";;
  Darwin)    PLATFORM="macos";;
  MINGW*|MSYS*|CYGWIN*) PLATFORM="windows";;
  *)         PLATFORM="unknown";;
esac

# Detect WSL (Linux running under Windows) — treat as linux but note it
IS_WSL=0
if [[ "${PLATFORM}" == "linux" ]] && grep -qi microsoft /proc/version 2>/dev/null; then
  IS_WSL=1
fi

ok "OS: ${PLATFORM} (${OS_KERNEL}), arch: ${ARCH}$([[ ${IS_WSL} -eq 1 ]] && echo ', WSL')"

# ============================================================================
# 2. Python interpreter + version check
# ============================================================================
log "Locating Python interpreter..."
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  die "Python interpreter '${PYTHON_BIN}' not found on PATH. Install Python >=${PYTHON_MIN} or set PYTHON_BIN."
fi
PY_VERSION="$("${PYTHON_BIN}" -c 'import sys;print("%d.%d.%d"%sys.version_info[:3])' 2>/dev/null || echo 0.0.0)"
PY_MAJOR_MINOR="$("${PYTHON_BIN}" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo 0.0)"

if [[ "$(printf '%s\n' "${PYTHON_MIN}" "${PY_MAJOR_MINOR}" | sort -V | head -n1)" != "${PYTHON_MIN}" ]]; then
  die "Python ${PY_VERSION} is older than the required ${PYTHON_MIN}. Upgrade Python."
fi
ok "Python: ${PY_VERSION} (${PYTHON_BIN})"

# ============================================================================
# 3. Hardware / accelerator detection
# ============================================================================
log "Detecting hardware backend..."

HAVE_NVIDIA=0; HAVE_ROCM=0; HAVE_APPLE_SILICON=0
NVIDIA_GPU_NAME=""; CUDA_DRIVER_VERSION=""; NSMI_MAX_CUDA=""

if [[ "${PLATFORM}" == "macos" ]] && [[ "${ARCH}" == "arm64" ]]; then
  HAVE_APPLE_SILICON=1
fi

# NVIDIA — works on linux, windows, WSL
if command -v nvidia-smi >/dev/null 2>&1; then
  if nvidia-smi --query-gpu=name,driver_version --format=csv,noheader >/dev/null 2>&1; then
    HAVE_NVIDIA=1
    NVIDIA_GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n1)"
    CUDA_DRIVER_VERSION="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -n1)"
    # The header line advertises the maximum CUDA version the installed driver supports.
    NSMI_MAX_CUDA="$(nvidia-smi 2>/dev/null | grep -oiE 'CUDA Version: [0-9.]+' | grep -oE '[0-9.]+' | head -n1)"
  fi
fi

# ROCm — Linux only
if [[ "${PLATFORM}" == "linux" ]]; then
  if command -v rocminfo >/dev/null 2>&1 && rocminfo >/dev/null 2>&1; then
    HAVE_ROCM=1
  elif [[ -d /opt/rocm ]]; then
    HAVE_ROCM=1
  fi
fi

# Resolve backend
if [[ "${TORCH_BACKEND}" == "auto" ]]; then
  if [[ ${HAVE_APPLE_SILICON} -eq 1 ]]; then TORCH_BACKEND="mps"
  elif [[ ${HAVE_NVIDIA} -eq 1 ]]; then TORCH_BACKEND="cuda"
  elif [[ ${HAVE_ROCM} -eq 1 ]]; then TORCH_BACKEND="rocm"
  else TORCH_BACKEND="cpu"
  fi
fi

# Validate backend against platform constraints
case "${TORCH_BACKEND}" in
  mps)
    if [[ "${PLATFORM}" != "macos" ]]; then die "MPS backend requested but this is not macOS."; fi
    ok "Backend: Apple Silicon MPS";;
  cuda)
    if [[ ${HAVE_NVIDIA} -eq 0 ]]; then warn "CUDA backend selected but no NVIDIA GPU detected via nvidia-smi; installing CUDA wheels anyway."; fi
    ok "Backend: NVIDIA CUDA${NVIDIA_GPU_NAME:+ (${NVIDIA_GPU_NAME})}${CUDA_DRIVER_VERSION:+, driver ${CUDA_DRIVER_VERSION}}";;
  rocm)
    if [[ "${PLATFORM}" != "linux" ]]; then die "ROCm is only supported on Linux (not macOS / native Windows)."; fi
    ok "Backend: AMD ROCm";;
  cpu)
    ok "Backend: CPU";;
  *)
    die "Unknown TORCH_BACKEND='${TORCH_BACKEND}'. Use auto|cpu|cuda|rocm|mps.";;
esac

# ============================================================================
# 3b. Driver compatibility verification (before installing PyTorch)
# ============================================================================
# PyTorch CUDA/ROCm wheels bundle the userspace runtime, but the host GPU
# *driver* must still be new enough. Verify that here so we fail fast with a
# clear message instead of at `import torch` time.
#
# Minimum NVIDIA driver versions per CUDA release (NVIDIA CUDA Toolkit
# Release Notes). ROCm gives forward/backward compatibility of +/-2 releases
# between the amdgpu kernel driver (KMD) and ROCm userspace (AMD ROCm docs).
if [[ "${SKIP_DRIVER_CHECK}" == "1" ]]; then
  warn "SKIP_DRIVER_CHECK=1: driver compatibility check bypassed."
else
  log "Verifying GPU driver compatibility..."

  if [[ "${TORCH_BACKEND}" == "cuda" ]]; then
    case "${CUDA_VERSION}" in
      cu121) MIN_DRV_LINUX="530.30.02"; MIN_DRV_WIN="531.14" ;;
      cu124) MIN_DRV_LINUX="550.54.14"; MIN_DRV_WIN="551.61" ;;
      cu126) MIN_DRV_LINUX="560.28.03"; MIN_DRV_WIN="560.76" ;;
      cu128) MIN_DRV_LINUX="570.26";    MIN_DRV_WIN="570.65" ;;
      *) die "Unsupported CUDA_VERSION='${CUDA_VERSION}'. Use cu121|cu124|cu126|cu128." ;;
    esac
    if [[ ${HAVE_NVIDIA} -eq 1 ]]; then
      if [[ "${PLATFORM}" == "windows" ]]; then MIN_DRV="${MIN_DRV_WIN}"; else MIN_DRV="${MIN_DRV_LINUX}"; fi
      if ver_ge "${CUDA_DRIVER_VERSION}" "${MIN_DRV}"; then
        ok "NVIDIA driver ${CUDA_DRIVER_VERSION} >= required ${MIN_DRV} for ${CUDA_VERSION}."
      else
        die "NVIDIA driver ${CUDA_DRIVER_VERSION} is too old for ${CUDA_VERSION} (needs >= ${MIN_DRV}). Update the driver at https://www.nvidia.com/drivers, or set CUDA_VERSION to an older release (e.g. CUDA_VERSION=cu121)."
      fi
      if [[ -n "${NSMI_MAX_CUDA}" ]]; then
        ok "Driver advertises max CUDA ${NSMI_MAX_CUDA} support."
      fi
    else
      warn "No NVIDIA driver detected (nvidia-smi missing). CUDA wheels will install, but torch.cuda.is_available() will be False."
    fi
  fi

  if [[ "${TORCH_BACKEND}" == "rocm" ]]; then
    # amdgpu kernel driver loaded? (render nodes imply the driver is present)
    AMDGPU_LOADED=0
    if lsmod >/dev/null 2>&1 && lsmod | grep -qw amdgpu; then AMDGPU_LOADED=1; fi
    if [[ ${AMDGPU_LOADED} -eq 0 ]] && [[ -d /dev/dri ]]; then AMDGPU_LOADED=1; fi
    if [[ ${AMDGPU_LOADED} -eq 0 ]]; then
      warn "amdgpu kernel module / /dev/dri not detected; ROCm wheels will install but the GPU may be unusable."
    else
      ok "amdgpu kernel driver present."
    fi
    # Detect installed ROCm userspace version.
    ROCM_INSTALLED=""
    if [[ -f /opt/rocm/.rocm-version ]]; then
      ROCM_INSTALLED="$(grep -oE '[0-9]+\.[0-9]+\.[0-9]+' /opt/rocm/.rocm-version 2>/dev/null | head -n1)"
    elif command -v rocminfo >/dev/null 2>&1; then
      ROCM_INSTALLED="$(rocminfo 2>/dev/null | grep -iE 'version' | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1)"
    fi
    ROCM_REQ_MM="${ROCM_VERSION#rocm}"   # e.g. 6.2
    if [[ -n "${ROCM_INSTALLED}" ]]; then
      ok "Installed ROCm userspace: ${ROCM_INSTALLED}; requested wheel: ${ROCM_VERSION}."
      ROCM_INST_MAJOR="${ROCM_INSTALLED%%.*}"
      ROCM_REQ_MAJOR="${ROCM_REQ_MM%%.*}"
      if [[ "${ROCM_INST_MAJOR}" != "${ROCM_REQ_MAJOR}" ]]; then
        warn "Installed ROCm major ${ROCM_INST_MAJOR} differs from requested ${ROCM_REQ_MAJOR}; the ${ROCM_VERSION} wheel may not work."
      fi
    else
      warn "No ROCm userspace detected (no /opt/rocm or rocminfo). The ${ROCM_VERSION} wheel will install but may fail at runtime."
    fi
    if ! command -v rocm-smi >/dev/null 2>&1; then
      warn "rocm-smi not found; install the full ROCm stack for monitoring/verification."
    fi
  fi
fi

# Decide whether vLLM is appropriate (Linux + CUDA/ROCm only; not macOS/Windows)
WANT_VLLM=0
if [[ "${INSTALL_VLLM}" == "yes" ]]; then
  WANT_VLLM=1
elif [[ "${INSTALL_VLLM}" == "auto" ]]; then
  if [[ "${PLATFORM}" == "linux" ]] && { [[ ${HAVE_NVIDIA} -eq 1 ]] || [[ ${HAVE_ROCM} -eq 1 ]]; }; then
    WANT_VLLM=1
  fi
fi
if [[ ${WANT_VLLM} -eq 1 ]] && [[ "${PLATFORM}" != "linux" ]]; then
  warn "vLLM requested but is not supported on ${PLATFORM}; skipping."
  WANT_VLLM=0
fi
if [[ ${WANT_VLLM} -eq 1 ]] && [[ "${TORCH_BACKEND}" == "mps" || "${TORCH_BACKEND}" == "cpu" ]]; then
  warn "vLLM not available for ${TORCH_BACKEND}; skipping."
  WANT_VLLM=0
fi

# ============================================================================
# 4. Virtual environment
# ============================================================================
log "Creating virtual environment at '${VENV_DIR}'..."
if [[ -d "${VENV_DIR}" ]]; then
  warn "Virtual env already exists at '${VENV_DIR}'. Reusing (delete it to rebuild)."
else
  if "${PYTHON_BIN}" -m venv "${VENV_DIR}"; then
    ok "Virtual environment created."
  else
    die "Failed to create virtual environment with '${PYTHON_BIN}'."
  fi
fi

VENV_PY="$(venv_python)"
[[ -x "${VENV_PY}" ]] || die "Virtual-env python not found at expected location."
ok "Venv python: ${VENV_PY}"

# Upgrade pip tooling
log "Upgrading pip / setuptools / wheel inside the venv..."
"${VENV_PY}" -m pip install --upgrade pip setuptools wheel >/dev/null 2>&1 || warn "pip self-upgrade reported a non-fatal issue; continuing."

# ============================================================================
# 5. Install PyTorch for the detected backend
# ============================================================================
log "Installing PyTorch for backend '${TORCH_BACKEND}'..."
PIP_TORCH_ARGS=(torch torchvision torchaudio)

case "${TORCH_BACKEND}" in
  cpu)
    # CPU-only wheels come from the dedicated CPU index. This is important on
    # Linux x86_64, where the default PyPI 'torch' wheel bundles multi-GB of
    # CUDA libraries. The CPU index serves small CPU-only wheels on every
    # platform (including macOS arm64, which still exposes MPS from these).
    "${VENV_PY}" -m pip install "${PIP_TORCH_ARGS[@]}" \
      --index-url https://download.pytorch.org/whl/cpu \
      || die "PyTorch CPU install failed."
    ;;
  mps)
    # macOS arm64: MPS is built into the standard PyPI wheels (recommended path).
    "${VENV_PY}" -m pip install "${PIP_TORCH_ARGS[@]}" || die "PyTorch install failed (mps)."
    ;;
  cuda)
    TORCH_INDEX="https://download.pytorch.org/whl/${CUDA_VERSION}"
    warn "Installing CUDA PyTorch wheels (${CUDA_VERSION}). These bundle the CUDA runtime; an NVIDIA driver is still required."
    "${VENV_PY}" -m pip install "${PIP_TORCH_ARGS[@]}" --index-url "${TORCH_INDEX}" \
      || die "PyTorch CUDA install failed. Try a different CUDA_VERSION (cu121|cu124|cu126|cu128)."
    ;;
  rocm)
    TORCH_INDEX="https://download.pytorch.org/whl/${ROCM_VERSION}"
    warn "Installing ROCm PyTorch wheels (${ROCM_VERSION}). ROCm is Linux-only."
    "${VENV_PY}" -m pip install "${PIP_TORCH_ARGS[@]}" --index-url "${TORCH_INDEX}" \
      || die "PyTorch ROCm install failed. Try a different ROCM_VERSION (rocm6.1|rocm6.2)."
    ;;
esac
ok "PyTorch installed for '${TORCH_BACKEND}'."

# ============================================================================
# 6. Install repository dependencies (or a sensible default inference set)
# ============================================================================
log "Installing project dependencies..."

install_default_inference_deps() {
  warn "No requirements.txt / pyproject.toml found in '${REPO_DIR}'."
  log "Installing default inference stack (transformers, accelerate, safetensors, ...)."
  "${VENV_PY}" -m pip install \
    "transformers>=4.45" "accelerate>=1.0" "safetensors" "sentencepiece" \
    "einops" "huggingface_hub" "openai" "numpy" "pillow" "tiktoken" \
    || die "Default dependency install failed."
}

if [[ -f "${REPO_DIR}/requirements.txt" ]]; then
  ok "Found requirements.txt — installing it."
  "${VENV_PY}" -m pip install -r "${REPO_DIR}/requirements.txt" \
    || die "requirements.txt install failed."
elif [[ -f "${REPO_DIR}/pyproject.toml" ]]; then
  ok "Found pyproject.toml — installing project in editable mode."
  ( cd "${REPO_DIR}" && "${VENV_PY}" -m pip install -e . ) \
    || die "pyproject.toml editable install failed."
else
  install_default_inference_deps
fi

# Extra user-specified requirements
if [[ -n "${EXTRA_REQUIREMENTS}" ]]; then
  log "Installing EXTRA_REQUIREMENTS: ${EXTRA_REQUIREMENTS}"
  # shellcheck disable=SC2086
  "${VENV_PY}" -m pip install ${EXTRA_REQUIREMENTS} \
    || die "EXTRA_REQUIREMENTS install failed."
fi

# ============================================================================
# 7. Optional vLLM (Linux + CUDA/ROCm) — the engine recommended by Kimi-K3
# ============================================================================
if [[ ${WANT_VLLM} -eq 1 ]]; then
  log "Installing vLLM (recommended by the Kimi-K3 README for local serving)..."
  "${VENV_PY}" -m pip install "vllm" || {
    warn "vLLM install failed. Inference will fall back to the transformers path."
    warn "Kimi-K3 is a 2.8T-parameter MoE model; local vLLM serving needs multi-GPU clusters."
  }
else
  warn "Skipping vLLM (not supported on ${PLATFORM}/${TORCH_BACKEND}). The runner will use the transformers fallback."
fi

# ============================================================================
# 8. Diagnostic check — verify GPU / accelerator availability
# ============================================================================
log "Running GPU availability diagnostic..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIAG_SCRIPT="${SCRIPT_DIR}/scripts/diagnose_torch.py"
if [[ ! -f "${DIAG_SCRIPT}" ]]; then
  warn "Diagnostic script not found at ${DIAG_SCRIPT}; skipping."
else
  if "${VENV_PY}" "${DIAG_SCRIPT}"; then
    ok "Diagnostic completed."
  else
    warn "Diagnostic reported an issue. Review the output above before running inference."
  fi
fi

# ============================================================================
# 9. Done — print activation hint
# ============================================================================
cat <<EOF

${C_GRN}✓ Setup complete.${C_RST}

Backend : ${TORCH_BACKEND}
Venv    : ${VENV_DIR}
Python  : ${VENV_PY}

Activate the environment:
EOF
case "${PLATFORM}" in
  windows)
    echo "  source ${VENV_DIR}/Scripts/activate   # Git Bash / MSYS2"
    echo "  ${VENV_DIR}\\Scripts\\activate.bat    # cmd.exe"
    echo "  ${VENV_DIR}\\Scripts\\Activate.ps1   # PowerShell"
    ;;
  *)
    echo "  source ${VENV_DIR}/bin/activate"
    ;;
esac
cat <<EOF

Run inference:
  ./run_inference.sh

EOF
