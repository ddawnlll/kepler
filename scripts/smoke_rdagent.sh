#!/usr/bin/env bash
set -euo pipefail

# Kepler RD-Agent Smoke Test
# Runs 1 iteration of the Qlib factor R&D evolving loop

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# 1. Activate virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# 2. Load environment variables
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# 3. Environment prerequisites
export CONDA_DEFAULT_ENV="${CONDA_DEFAULT_ENV:-base}"
export MLFLOW_ALLOW_FILE_STORE=true
export PATH="${ROOT_DIR}/.venv/bin:${HOME}/.local/bin:${PATH}"

# 4. Run single loop of RD-Agent fin_factor
rdagent fin_factor --loop-n 1
