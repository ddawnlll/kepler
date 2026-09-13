# Kepler

Kepler is a minimal, reproducible quantitative research setup evaluating **Microsoft Qlib** and **Microsoft RD-Agent(Q)**.

## Kepler M0: Smoke-Test Gates

1. **Gate 1 — Qlib Standalone**: Run official Qlib CSI300 Alpha158 LightGBM backtest baseline.
2. **Gate 2 — RD-Agent(Q)**: Run exactly one bounded quantitative research iteration on top of Qlib.

See [MISSION.md](MISSION.md) for core principles and constraints.

## Getting Started

```bash
# 1. Environment Setup
./scripts/setup.sh

# 2. Gate 1: Qlib baseline
./scripts/smoke_qlib.sh

# 3. Gate 2: RD-Agent iteration (requires .env configuration)
./scripts/smoke_rdagent.sh
```
