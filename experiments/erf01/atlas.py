#!/usr/bin/env python3
"""ERF-01 Regime Atlas: observed regimes, spell durations and causal OOS forecasts.

Scientific target: market-state understanding, NOT trade returns or alpha.
Reuses the EXISTING causal 20-day q-state definition and audited canonical tape.
All descriptions are EX POST; every forecast is fit before its test fold.
2020 warms the state definition, 2021-04..2026-03 is the five-year atlas.
Never opens sealed 2026-04+ or uses PnL, referee, orders or trading positions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from experiments.erf01 import pipeline as erf01
from experiments.erf01.tape_adapter import load_development

STATES = (-1, 0, 1)
STATE_NAMES = {-1: "downtrend_proxy", 0: "neutral_proxy", 1: "uptrend_proxy"}
ATLAS_BEGIN = date(2021, 4, 1)
HORIZONS = (3, 7, 14, 21)
SEAL = date(2026, 4, 1)
SMOOTHING = 10.0  # frozen prior pseudo-observations, not fit to OOS outcomes


from kepler.intelligence.regimes import (
    observed_state, spells, spell_distribution, transition_matrix,
    survival_parameters, continuation_probability,
)


def summarise_forecast(records, name, paired_baseline):
    if not records:
        return {"n": 0, "status": "NOT_RUN"}
    actual = np.asarray([r["true"] for r in records], dtype=int)
    prob = np.asarray([r[name] for r in records], dtype=float)
    base = np.asarray([r[paired_baseline] for r in records], dtype=float)
    if prob.ndim == 2:
        onehot = np.eye(3)[actual + 1]
        delta = np.sum((base - onehot) ** 2, axis=1) - np.sum((prob - onehot) ** 2, axis=1)
        brier = float(np.mean(np.sum((prob - onehot) ** 2, axis=1)))
        baseline_brier = float(np.mean(np.sum((base - onehot) ** 2, axis=1)))
        hit = np.argmax(prob, axis=1) - 1
        base_hit = np.argmax(base, axis=1) - 1
        accuracy = float(np.mean(hit == actual))
        accuracy_baseline = float(np.mean(base_hit == actual))
        recall = {STATE_NAMES[k]: float(np.mean(hit[actual == k] == k))
                  if np.any(actual == k) else None for k in STATES}
        confusion = {STATE_NAMES[k]: {STATE_NAMES[j]:
                     int(np.sum((actual == k) & (hit == j))) for j in STATES}
                     for k in STATES}
    else:
        delta = (base - actual) ** 2 - (prob - actual) ** 2
        brier = float(np.mean((prob - actual) ** 2))
        baseline_brier = float(np.mean((base - actual) ** 2))
        accuracy = accuracy_baseline = None
        recall = confusion = None
    by_day = defaultdict(list)
    for r, d in zip(records, delta):
        by_day[r["date"]].append(float(d))
    bootstrap = erf01._moving_block_ci({d: float(np.mean(x)) for d, x in by_day.items()},
                                        B=1000, block=28, seed=20261015)
    return {"n": len(records), "n_distinct_dates": len(by_day),
            "brier": brier, "baseline_brier": baseline_brier,
            "baseline_minus_model_brier": baseline_brier - brier,
            "paired_block_bootstrap": bootstrap, "accuracy": accuracy,
            "baseline_accuracy": accuracy_baseline, "class_recall": recall,
            "confusion": confusion}


def analyse(days, panel):
    """No future target/episode may be used to train a test fold."""
    if days[0] > date(2020, 1, 1) or days[-1] >= SEAL:
        raise RuntimeError("expected causal warmup with no sealed dates")
    start_index = next(i for i, d in enumerate(days) if d >= ATLAS_BEGIN)
    episodes = {sym: spells(days[start_index:], panel[sym]["q"][start_index:])
                for sym in erf01.SYMS}
    all_spells = [s for batch in episodes.values() for s in batch]
    durations = {STATE_NAMES[state]: spell_distribution(
        [s for s in all_spells if s["state"] == state]) for state in STATES}
    by_sym = {sym: {STATE_NAMES[state]: spell_distribution(
        [s for s in episodes[sym] if s["state"] == state]) for state in STATES}
        for sym in erf01.SYMS}

    occupancy = {}
    annual = {}
    for year in range(ATLAS_BEGIN.year, SEAL.year + 1):
        bucket = Counter()
        for sym in erf01.SYMS:
            for d, x in zip(days[start_index:], panel[sym]["q"][start_index:]):
                if d.year == year:
                    state = observed_state(x)
                    if state is not None:
                        bucket[STATE_NAMES[state]] += 1
                    else:
                        bucket["unknown_days"] += 1
        if bucket:
            annual[str(year)] = dict(bucket)
    for state in STATES:
        occupancy[STATE_NAMES[state]] = sum(
            observed_state(x) == state for sym in erf01.SYMS
            for x in panel[sym]["q"][start_index:])
    missing = sum(not np.isfinite(x) for sym in erf01.SYMS
                  for x in panel[sym]["q"][start_index:])
    counts = {"finite_asset_days": int(sum(occupancy.values())),
              "missing_asset_days": int(missing), "occupancy": occupancy,
              "annual_occupancy": annual}
    episode_rows = [{**e, "symbol": sym} for sym, es in episodes.items() for e in es]
    fold_summary = []
    forecast_by_horizon = {h: {"states": [], "survival": []} for h in HORIZONS}
    for first, last, fold in erf01.FOLDS:
        test_start = next(i for i, d in enumerate(days) if d >= first)
        test_last = next((i for i, d in enumerate(days) if d >= last), len(days))
        trained = [sp for sym in erf01.SYMS
                   for sp in spells(days[:test_start], panel[sym]["q"][:test_start])]
        transition = transition_matrix(panel, days, first)
        state_prior = np.asarray([sum(observed_state(x) == state
                             for sym in erf01.SYMS
                             for x in panel[sym]["q"][:test_start])
                             for state in STATES], dtype=float)
        state_prior = (state_prior + 1) / (state_prior.sum() + 3)
        # Memoize (state, current-age, horizon) per fold; otherwise repeating
        # pooled spell scan for every asset/day turns a 5-year pass quadratic.
        survival_cache = {}
        state_exit_priors = {state: survival_parameters(trained, state)[1] for state in STATES}
        for h in HORIZONS:
            matrix_h = np.linalg.matrix_power(transition, h)
            for sym in erf01.SYMS:
                q = panel[sym]["q"]
                age_values = panel[sym]["age"]
                for i in range(test_start, min(test_last, len(days) - h)):
                    current, future = observed_state(q[i]), observed_state(q[i + h])
                    if current is None or future is None or not np.isfinite(age_values[i]):
                        continue
                    age = int(age_values[i])
                    forecast_by_horizon[h]["states"].append({
                        "date": days[i], "fold": fold, "symbol": sym,
                        "true": future,
                        "markov": matrix_h[current + 1].copy(),
                        "persistence": np.eye(3)[current + 1].copy(),
                        "climatology": state_prior.copy()})
                    future_path = q[i + 1:i + h + 1]
                    if not np.isfinite(future_path).all():
                        continue
                    surviving = int(np.all(future_path == current))
                    key = (current, age, h)
                    if key not in survival_cache:
                        survival_cache[key] = continuation_probability(trained, current, age, h)
                    predicted = survival_cache[key]
                    constant_exit = state_exit_priors[current]
                    forecast_by_horizon[h]["survival"].append({
                        "date": days[i], "fold": fold, "symbol": sym,
                        "state": current, "true": surviving,
                        "age_conditioned": predicted,
                        "age_agnostic": float((1 - constant_exit) ** h)})
        fold_summary.append({"fold": fold, "train_last_date": days[test_start - 1].isoformat(),
                             "test_first_date": first.isoformat(),
                             "test_last_exclusive": last.isoformat(),
                             "training_known_spells": len(trained)})
    metrics = {}
    for h in HORIZONS:
        f = forecast_by_horizon[h]
        metrics[str(h)] = {
            "future_state_markov_vs_persistence": summarise_forecast(
                f["states"], "markov", "persistence"),
            "future_state_markov_vs_climatology": summarise_forecast(
                f["states"], "markov", "climatology"),
            "remaining_spell_survival_vs_state_constant_hazard": summarise_forecast(
                f["survival"], "age_conditioned", "age_agnostic"),
            "observed_survival_rate": float(np.mean([x["true"] for x in f["survival"]]))
            if f["survival"] else None,
            "observed_transition_rate": float(np.mean([
                x["true"] != np.argmax(x["persistence"]) - 1
                for x in f["states"]])) if f["states"] else None,
        }
    return {"status": "EXPLORATORY_SEEN_DEV_NOT_INDEPENDENT_CONFIRMATION",
            "target": "state understanding, forecast and duration; NO PNL",
            "proxy_definition": "ERF01 q: trailing 20d z20 ±1.25 with efficiency ratio>=.35; 0 otherwise",
            "warning": "q=0 is neutral proxy, NOT proof of sideways consolidation; labels have 20d smoothing",
            "atlas_first": ATLAS_BEGIN.isoformat(), "atlas_last_inclusive": days[-1].isoformat(),
            "warmup_first": days[0].isoformat(), "universe": erf01.SYMS,
            "duration_days": durations, "per_symbol_durations": by_sym,
            "descriptive_counts": counts, "folds": fold_summary,
            "forecast_oos_horizon_days": metrics, "raw_episodes": episode_rows,
            "confirmed_onset_original": "Preserved unchanged; 34 up/20 down OOS and M2 worse than M1",
            "trading_pnl": "OUT_OF_SCOPE", "proof_of_predictability": "NOT_ESTABLISHED",
            "independent_unseen_validation": "NOT_RUN"}


def write_report(result, path):
    lines = ["# ERF-01 Regime Atlas — five-year observation & causal forecasting",
             "", "Scientific status: **EXPLORATORY**, not independent confirmation.",
             "Never interpret an observed 20-day q proxy as ground-truth economic regimes.",
             "No trading simulation, strategy PnL or financial edge claim.", "",
             "## How long do observed regimes last?",
             "", "| State | Complete spells | Mean days | Median days | p90 days | Censored spans |",
             "|---|---:|---:|---:|---:|---:|"]
    for key, d in result["duration_days"].items():
        show = lambda x: "n/a" if x is None else f"{x:.1f}"
        lines.append(f"| {key} | {d['completed']} | {show(d['average_completed_days'])} | "
                     f"{show(d['median_completed_days'])} | {show(d['p90_completed_days'])} | "
                     f"{d['left_censored'] + d['right_censored']} |")
    lines += ["", "Censoring: gaps or the analysis boundary never count as observed regime endings.",
              "The mean/percentiles above use **fully observed** spells only; censoring is reported.",
              "", "## Forecast checks (chronological 2023–2026 OOS)",
              "", "| Horizon | Multiclass Markov Brier | Persist-q Brier | "
              "Duration survival Brier | Age-blind survival Brier |",
              "|---|---:|---:|---:|---:|"]
    for horizon, m in result["forecast_oos_horizon_days"].items():
        a = m["future_state_markov_vs_persistence"]
        b = m["remaining_spell_survival_vs_state_constant_hazard"]
        lines.append(f"| {horizon}d | {a['brier']:.4f} | {a['baseline_brier']:.4f} "
                     f"| {b['brier']:.4f} | {b['baseline_brier']:.4f} |")
    lines += ["", "Brier lower is better. Markov, age-conditioned survival and baselines"
              " use only history before each 6-month test fold.",
              "Every forecast scored at time t predicts future state q(t+h), or whether the"
              " current uninterrupted q spell survives h days.",
              "Class-level recall/confusion, annual observations and moving-block confidence"
              " intervals are in metrics JSON.", "",
              "**Independence warning:** the same DEV panel has already been explored;"
              " statistical comparisons here diagnose behavior, not confirm new edge.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--staging", type=Path, default=Path("/data/erf01/staging"))
    ap.add_argument("--out", type=Path, default=Path("/data/erf01/regime_atlas_20261015"))
    args = ap.parse_args()
    if not (args.staging / "tape").is_dir():
        raise FileNotFoundError("verified 9-symbol canonical staging is missing")
    klines, funding, _, qc_meta, acquisition = load_development(
        args.staging, erf01.SYMS, erf01.DAYS[0], erf01.DAYS[1], erf01.SEAL)
    days, panel = erf01.make_panel(klines, funding)
    result = analyse(days, panel)
    result["input_sha256"] = {
        str(Path(x["path"]).relative_to(args.staging)): x["sha256"]
        for x in acquisition["records"]}
    result["source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["erf01_definition_sha256"] = hashlib.sha256(Path(erf01.__file__).read_bytes()).hexdigest()
    result["qc_warnings_by_symbol"] = {s: len(qc_meta[s]["qc_findings"]) for s in erf01.SYMS}
    # Episode dates cannot be dumped as native date objects.
    result["raw_episodes"] = [{k: v.isoformat() if isinstance(v, date) else v
                               for k, v in episode.items()}
                              for episode in result["raw_episodes"]]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "metrics.json").write_text(json.dumps(result, indent=2) + "\n")
    write_report(result, args.out / "report.md")
    summary = {"status": result["status"], "five_year_asset_days":
               result["descriptive_counts"]["finite_asset_days"],
               "duration_days": result["duration_days"],
               "oos": {k: {"state_brier": v["future_state_markov_vs_persistence"]["brier"],
                           "persist_brier": v["future_state_markov_vs_persistence"]["baseline_brier"],
                           "survival_brier": v["remaining_spell_survival_vs_state_constant_hazard"]["brier"],
                           "baseline_survival_brier": v["remaining_spell_survival_vs_state_constant_hazard"]["baseline_brier"]}
                       for k, v in result["forecast_oos_horizon_days"].items()}}
    print("ERF01_REGIME_ATLAS_RESULT=" + json.dumps(summary, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
