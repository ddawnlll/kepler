#!/usr/bin/env bash
# Kepler default: train-free modern backtest.
# Train yok; model smoke run'undaki donuk params.pkl'dan yüklenir.
# smoke_qlib.sh M0 arşivi olarak değişmeden kalır.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

export MLFLOW_ALLOW_FILE_STORE=true

CONFIG="${1:-configs/backtest_modern.yaml}"
MODEL="${2:-mlruns/461983874136587276/0414105956094a979bdd0f1a8a008066/artifacts/params.pkl}"
OUT="${3:-reports/backtest_modern}"

python scripts/backtest_only.py --config "$CONFIG" --model "$MODEL" --out "$OUT"
