#!/usr/bin/env bash
# run_inference.sh – Bash-Einstieg für die lokale Kimi-K3-Inferenz.
# Dünner Wrapper um das integrierte Python-Modul kimi_k3.inference.
# Aktiviert die venv (falls vorhanden) und führt die Inferenz aus.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# venv suchen (app nutzt "venv", Fallback .venv)
if [[ -x venv/bin/python ]]; then PY=venv/bin/python
elif [[ -x .venv/bin/python ]]; then PY=.venv/bin/python
elif [[ -x venv/Scripts/python.exe ]]; then PY=venv/Scripts/python.exe
else PY=python3; fi

# Standard: lokale Inferenz. Mit --mode api gegen einen OpenAI-Endpunkt.
exec "${PY}" -m kimi_k3.inference "$@"
