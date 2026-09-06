#!/usr/bin/env bash
# =============================================================================
# run_inference.sh — Standardized Kimi-K3 runner (cross-platform)
#
# Modes (set MODE=...):
#   vllm   Serve via vLLM (Linux + CUDA/ROCm), then call the OpenAI-compatible
#          API locally. This matches the path recommended by the Kimi-K3 README.
#   api    Call a remote OpenAI-compatible endpoint (e.g. platform.kimi.ai).
#   local  Load the model with HuggingFace transformers (works on macOS MPS,
#          ROCm, CPU, native Windows). DEFAULT when vLLM is unavailable.
#
# Common env vars:
#   MODE            vllm|api|local                     (default: auto)
#   MODEL_ID        model id / HF path                  (default: moonshotai/Kimi-K3)
#   PROMPT          user prompt                         (default: hello-world)
#   MAX_NEW_TOKENS  generation length (local) / MAX_TOKENS (api)  (default: 128)
#   VENV_DIR        virtual-env location                (default: .venv)
#
# vllm mode extras:
#   VLLM_PORT       port for the OpenAI server          (default: 8000)
#   VLLM_EXTRA_ARGS extra args passed to `vllm serve`
# api mode extras:
#   BASE_URL        API base URL                        (default: http://localhost:8000/v1)
#   API_KEY         API key                             (default: EMPTY)
# =============================================================================
set -uo pipefail

if [[ -t 1 ]]; then
  C_GRN=$'\033[1;32m'; C_YEL=$'\033[1;33m'; C_BLU=$'\033[1;34m'; C_RED=$'\033[1;31m'; C_RST=$'\033[0m'
else
  C_GRN=""; C_YEL=""; C_BLU=""; C_RED=""; C_RST=""
fi
log()  { printf '%s▶%s %s\n' "$C_BLU" "$C_RST" "$*"; }
ok()   { printf '%s✓%s %s\n' "$C_GRN" "$C_RST" "$*"; }
warn() { printf '%s!%s %s\n' "$C_YEL" "$C_RST" "$*" >&2; }
die()  { printf '%s✗%s %s\n' "$C_RED" "$C_RST" "$*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-${SCRIPT_DIR}/.venv}"
MODEL_ID="${MODEL_ID:-moonshotai/Kimi-K3}"
PROMPT="${PROMPT:-Say hello and tell me what model you are.}"
MAX_NEW_TOKENS="${MAX_NEW_TOKENS:-128}"
MODE="${MODE:-auto}"

# Locate venv python (bin/ on unix, Scripts/ on Windows)
if [[ -x "${VENV_DIR}/bin/python" ]]; then VENV_PY="${VENV_DIR}/bin/python"
elif [[ -x "${VENV_DIR}/Scripts/python.exe" ]]; then VENV_PY="${VENV_DIR}/Scripts/python.exe"
else die "Virtual env not found at '${VENV_DIR}'. Run ./setup.sh first."; fi
ok "Using python: ${VENV_PY}"

# Resolve mode automatically if not set.
if [[ "${MODE}" == "auto" ]]; then
  if "${VENV_PY}" -c 'import vllm' >/dev/null 2>&1; then
    MODE="vllm"
  else
    MODE="local"
  fi
  warn "MODE=auto resolved to '${MODE}'."
fi

export MODEL_ID PROMPT MAX_NEW_TOKENS

case "${MODE}" in
  # ------------------------------------------------------------------ vllm
  vllm)
    VLLM_PORT="${VLLM_PORT:-8000}"
    VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:-}"
    log "Starting vLLM server on port ${VLLM_PORT} for '${MODEL_ID}'..."
    warn "Kimi-K3 is ~1.56TB; vLLM serving needs a multi-GPU cluster. Adjust VLLM_EXTRA_ARGS for tensor-parallel / quantization."

    # vLLM's entrypoint name changed across versions. Prefer the `vllm serve`
    # CLI when present, else fall back to the module path.
    VLLM_LAUNCH=("${VENV_PY}" -m vllm.entrypoints.openai.api_server)
    if "${VENV_PY}" -c 'import vllm' >/dev/null 2>&1 && "${VENV_PY}" -c 'import shutil,sys;sys.exit(0 if shutil.which("vllm") else 1)' >/dev/null 2>&1; then
      VLLM_LAUNCH=(vllm serve)
    fi

    "${VLLM_LAUNCH[@]}" \
      --model "${MODEL_ID}" \
      --port "${VLLM_PORT}" \
      --host 0.0.0.0 \
      ${VLLM_EXTRA_ARGS} &
    VLLM_PID=$!
    trap 'warn "Stopping vLLM (pid ${VLLM_PID})..."; kill ${VLLM_PID} 2>/dev/null || true' EXIT

    # Wait for readiness (max ~5 minutes for a huge model to load). Use the
    # venv Python instead of relying on curl, which minimal systems may lack.
    log "Waiting for server readiness..."
    for i in $(seq 1 300); do
      if "${VENV_PY}" - "${VLLM_PORT}" <<'PY' >/dev/null 2>&1
import sys, urllib.request
try:
    urllib.request.urlopen(f"http://localhost:{sys.argv[1]}/v1/models", timeout=1).read()
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
      then
        ok "vLLM server is ready."; break
      fi
      sleep 2
      [[ $i -eq 300 ]] && { die "vLLM server did not become ready in time."; }
    done

    BASE_URL="http://localhost:${VLLM_PORT}/v1" API_KEY="EMPTY" \
      MAX_TOKENS="${MAX_NEW_TOKENS}" \
      "${VENV_PY}" "${SCRIPT_DIR}/scripts/run_api.py" || die "API run failed."
    ok "Inference complete."
    ;;

  # ------------------------------------------------------------------- api
  api)
    BASE_URL="${BASE_URL:-http://localhost:8000/v1}"
    API_KEY="${API_KEY:-EMPTY}"
    MAX_TOKENS="${MAX_NEW_TOKENS}"
    export BASE_URL API_KEY MAX_TOKENS
    "${VENV_PY}" "${SCRIPT_DIR}/scripts/run_api.py" || die "API run failed."
    ok "Inference complete."
    ;;

  # ----------------------------------------------------------------- local
  local)
    "${VENV_PY}" "${SCRIPT_DIR}/scripts/run_local.py" || die "Local inference failed."
    ok "Inference complete."
    ;;

  *)
    die "Unknown MODE='${MODE}'. Use vllm|api|local.";;
esac
