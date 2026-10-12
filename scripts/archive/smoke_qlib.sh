#!/usr/bin/env bash
set -euo pipefail

# Activate isolated environment if present
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

CONFIG_PATH="${HOME}/.qlib/workflow_config_lightgbm_Alpha158.yaml"
if [ ! -f "$CONFIG_PATH" ]; then
    mkdir -p "${HOME}/.qlib"
    python3 -c '
import urllib.request
url = "https://raw.githubusercontent.com/microsoft/qlib/main/examples/benchmarks/LightGBM/workflow_config_lightgbm_Alpha158.yaml"
urllib.request.urlretrieve(url, "'"${CONFIG_PATH}"'")
'
fi

export MLFLOW_ALLOW_FILE_STORE=true
qrun "$CONFIG_PATH"
