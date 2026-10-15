# Kepler

Kepler is a quantitative research repository for causal crypto-market analysis and evidence-preserving strategy evaluation. Current scientific priority is understanding observable market regimes before optimizing trading decisions.

## Kepler M0: Smoke-Test Gates

1. **Gate 1 — Qlib Standalone**: Run official Qlib CSI300 Alpha158 LightGBM backtest baseline.
2. **Gate 2 — RD-Agent(Q)**: Run exactly one bounded quantitative research iteration on top of Qlib.

See [MISSION.md](MISSION.md) for core principles and constraints.

## Agent factory status

The repository includes an operator-installed broker, durable supervisor, Linux-isolated checks, human-reviewed branch promotion, Modal result spooling and a retrying status outbox. See [factory/README.md](factory/README.md) and [docs/factory.md §20](docs/factory.md) for the installation and acceptance sequence. Services are not started by the installer; research is disabled and paused until a human provisions separate DEV credentials and spending limits, runs the acceptance drill and resumes the dispatcher.

## Getting Started (default: train-free)

```bash
# Default: train-free modern backtest (refit yok, donuk model)
./scripts/backtest_only.sh
# config: configs/backtest_modern.yaml (2023-01-01 -> 2026-08-31)
# çıktı: reports/backtest_modern/metrics.yaml
```

## Archive: Kepler M0 Smoke-Test Gates (salt-okunur)

## Market intelligence research

The reusable causal feature and regime math lives in `kepler/intelligence/`.
Frozen ERF-01 experiment workflows live in `experiments/erf01/`; legacy CLI entry points under `scripts/` remain compatible.
Run `python -m kepler.intelligence atlas --staging /data/erf01/staging --out /data/erf01/regime_atlas_20261015` inside the pinned Modal environment. The run is scientific analysis, not a verified trading edge.
