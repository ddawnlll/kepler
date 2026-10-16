"""Frozen PMI-H3 linked fast/slow observable-risk density comparison."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
import time

import numpy as np

from experiments.market_intelligence.h1 import _fit_ols, _predict_ols, _target_rows
from experiments.market_intelligence.h7 import _logsumexp, student_t_cdf, student_t_logpdf
from kepler.intelligence.metrics_v2 import paired_date_block_interval
from kepler.intelligence.validation import (
    deterministic_receipt, temporal_split, validate_prediction_window,
)

UTC = timezone.utc
PROTOCOL_SHA = "72af5363ec89482d904c0c0a80e4867a1f122369"
PROTOCOL_FILE_SHA256 = "2e743677de963b5203d28a394eca40223820991c1ba8ba19424437381f411c09"
DF = 5
PRIMARY_HORIZON_DAYS = 7
MINIMUM_MEAN_GAIN = 0.01
FAST_STATE_QUANTILE = 0.75
BOOTSTRAP_BLOCK_DAYS = 28
BOOTSTRAP_REPLICATES = 2000
EXPERIMENT_SEED = 20261016
MODEL_NAMES = ("unlinked_mixture", "flat_cells", "linked_hierarchical", "continuous_har")
FEATURE_NAMES = ("log_rv1", "log_rv7", "log_rv30")
SLOW_STATES = (-1, 0, 1)


def _features_ok(row: tuple) -> bool:
    return all(name in row[1] and np.isfinite(row[1][name]) for name in FEATURE_NAMES)


def _fast_high_threshold(fit_rows: list[tuple]) -> float:
    """Fit high/low cutoff from current RV7 on matured fit targets only."""
    if not fit_rows or any(not _features_ok(row) for row in fit_rows):
        raise ValueError("fast-state threshold requires finite fit-row features")
    return float(np.quantile([math.exp(row[1]["log_rv7"]) for row in fit_rows],
                             FAST_STATE_QUANTILE, method="linear"))


def _ridge_location(x: np.ndarray, y: np.ndarray, penalties: np.ndarray) -> np.ndarray:
    """Solve fixed-penalty ridge with an explicitly unpenalized intercept."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    penalties = np.asarray(penalties, float)
    if x.ndim != 2 or len(x) != len(y) or x.shape[1] != len(penalties):
        raise ValueError("ridge design, labels and penalties must align")
    return np.linalg.solve(x.T @ x + np.diag(penalties), x.T @ y)


def _linked_design(q_values: np.ndarray, fast_values: np.ndarray) -> np.ndarray:
    """Reference-coded slow main effects, fast main effect and interactions."""
    q_values = np.asarray(q_values, dtype=int)
    fast_values = np.asarray(fast_values, dtype=float)
    q0, q1 = (q_values == 0).astype(float), (q_values == 1).astype(float)
    return np.column_stack((np.ones(len(q_values)), q0, q1, fast_values,
                            q0 * fast_values, q1 * fast_values))


def _fit_density_candidates(fit_rows: list[tuple], q_by_day: dict[date, int]):
    """Fit all four fixed models on identical matured observable targets."""
    selected = [row for row in fit_rows
                if _features_ok(row) and (row[0].prediction_at.date() - timedelta(days=1)) in q_by_day]
    if len(selected) < 60:
        raise ValueError("fewer than 60 matured fit rows have finite inputs and slow state")
    q = np.asarray([q_by_day[row[0].prediction_at.date() - timedelta(days=1)] for row in selected], int)
    fast_threshold = _fast_high_threshold(selected)
    fast = np.asarray([int(math.exp(row[1]["log_rv7"]) >= fast_threshold) for row in selected], int)
    y = np.log(np.maximum([float(row[0].value) for row in selected], 1e-12))
    pooled = float(np.mean(y))

    fast_means = {state: float(np.mean(y[fast == state])) if np.any(fast == state) else pooled
                  for state in (0, 1)}
    slow_means = {state: float(np.mean(y[q == state])) if np.any(q == state) else pooled
                  for state in SLOW_STATES}
    cell_means = {(slow, quick): float(np.mean(y[(q == slow) & (fast == quick)]))
                  for slow in SLOW_STATES for quick in (0, 1)
                  if np.any((q == slow) & (fast == quick))}

    linked_x = _linked_design(q, fast)
    linked_beta = _ridge_location(linked_x, y, np.asarray([0.0, 1.0, 1.0, 1.0, 10.0, 10.0]))
    continuous_x = np.asarray([[row[1][name] for name in FEATURE_NAMES] for row in selected], float)
    continuous_model = _fit_ols(continuous_x, y)

    # A common within-component scale is fit only on the training rows. For the
    # mixture it is the equal-weight average of the two component residual MSEs.
    mixture_residual = .5 * (np.mean((y - np.asarray([fast_means[v] for v in fast])) ** 2)
                             + np.mean((y - np.asarray([slow_means[v] for v in q])) ** 2))
    flat_location = np.asarray([cell_means.get((int(s), int(f)), pooled)
                                for s, f in zip(q, fast)], float)
    t_scale_factor = math.sqrt((DF - 2) / DF)
    scales = {
        "unlinked_mixture": max(math.sqrt(float(mixture_residual)) * t_scale_factor, 1e-6),
        "flat_cells": max(float(np.sqrt(np.mean((y - flat_location) ** 2))) * t_scale_factor, 1e-6),
        "linked_hierarchical": max(float(np.sqrt(np.mean((y - linked_x @ linked_beta) ** 2)))
                                   * t_scale_factor, 1e-6),
    }
    continuous_residual = y - _predict_ols(continuous_model, continuous_x)
    scales["continuous_har"] = max(float(np.sqrt(np.mean(continuous_residual ** 2)))
                                   * t_scale_factor, 1e-6)
    diagnostics = {
        "n_matured_fit_rows": len(selected), "fast_rv7_q75_threshold_fit_only": fast_threshold,
        "slow_state_fit_support": {str(state): int(np.sum(q == state)) for state in SLOW_STATES},
        "fast_state_fit_support": {str(state): int(np.sum(fast == state)) for state in (0, 1)},
        "slow_fast_cell_fit_support": {f"{slow}:{quick}": int(np.sum((q == slow) & (fast == quick)))
                                       for slow in SLOW_STATES for quick in (0, 1)},
        "parameters": {"unlinked_mixture": 6, "flat_cells": len(cell_means) + 2,
                       "linked_hierarchical": 7, "continuous_har": 5},
        "student_t_scales_fit_only": scales,
        "linked_penalties": {"intercept": 0.0, "slow_main": 1.0, "fast_main": 1.0,
                             "slow_fast_interaction": 10.0},
        "fit_rows": len(selected),
        "pooled_location": pooled,
    }
    model = {"fast_threshold": fast_threshold, "fast_means": fast_means,
             "slow_means": slow_means, "cell_means": cell_means,
             "linked_beta": linked_beta, "continuous": continuous_model,
             "scales": scales, "diagnostics": diagnostics}
    return model


def _forecast_locations(model: dict, feature: dict, slow_state: int) -> dict[str, tuple[float, float]]:
    """Return candidate location/scale distributions for one test row."""
    if slow_state not in SLOW_STATES or not _features_ok((None, feature)):
        raise ValueError("forecast requires a supported slow state and finite causal features")
    fast_state = int(math.exp(feature["log_rv7"]) >= model["fast_threshold"])
    linked_x = _linked_design(np.asarray([slow_state]), np.asarray([fast_state]))
    continuous_x = np.asarray([[feature[name] for name in FEATURE_NAMES]], float)
    continuous_location = float(_predict_ols(model["continuous"], continuous_x)[0])
    return {
        "unlinked_mixture": (model["fast_means"][fast_state], model["slow_means"][slow_state],
                             model["scales"]["unlinked_mixture"]),
        "flat_cells": (model["cell_means"].get((slow_state, fast_state), model["diagnostics"]["pooled_location"]),
                       model["scales"]["flat_cells"]),
        "linked_hierarchical": (float(linked_x @ model["linked_beta"]),
                                model["scales"]["linked_hierarchical"]),
        "continuous_har": (continuous_location, model["scales"]["continuous_har"]),
    }


def _mixture_cdf(value: float, locations: tuple[float, float], scale: float) -> float:
    return .5 * (student_t_cdf(value, locations[0], scale, DF)
                 + student_t_cdf(value, locations[1], scale, DF))


def _quantile(cdf, probability: float, center: float, scale: float) -> float:
    lo, hi = center - 100 * scale, center + 100 * scale
    for _ in range(70):
        mid = (lo + hi) / 2
        if cdf(mid) < probability:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


@lru_cache(maxsize=8)
def _student_t_standard_quantile(probability: float) -> float:
    return _quantile(lambda value: student_t_cdf(value, 0.0, 1.0, DF), probability, 0.0, 1.0)


@lru_cache(maxsize=256)
def _mixture_standard_quantile(separation: float, probability: float) -> float:
    cdf = lambda value: .5 * (student_t_cdf(value, -separation, 1.0, DF)
                               + student_t_cdf(value, separation, 1.0, DF))
    return _quantile(cdf, probability, 0.0, 1.0)


def _density_summary(y: float, spec: tuple[str, tuple, float]) -> dict:
    kind, locations, scale = spec
    if kind == "mixture":
        logpdf = _logsumexp(np.asarray([
            math.log(.5) + student_t_logpdf(y, locations[0], scale, DF),
            math.log(.5) + student_t_logpdf(y, locations[1], scale, DF)], float))
        cdf = lambda z: _mixture_cdf(z, locations, scale)
        center = .5 * (locations[0] + locations[1])
        separation = abs(locations[0] - locations[1]) / (2 * scale)
        quantile = lambda probability: center + scale * _mixture_standard_quantile(separation, probability)
    else:
        logpdf = student_t_logpdf(y, locations, scale, DF)
        cdf = lambda z: student_t_cdf(z, locations, scale, DF)
        center = locations
        quantile = lambda probability: center + scale * _student_t_standard_quantile(probability)
    pit = cdf(y)
    intervals = {}
    for coverage in (.50, .80, .95):
        tail = (1 - coverage) / 2
        low = quantile(tail)
        high = quantile(1 - tail)
        intervals[str(int(coverage * 100))] = [low, high]
    return {"log_density": float(logpdf), "pit": float(pit), "intervals": intervals}


def _score_predictions(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0, "mean_log_density": None, "pit_histogram_10": [0] * 10,
                "central_interval_coverage": {"50": None, "80": None, "95": None}}
    scores = {}
    for model_name in MODEL_NAMES:
        pits = np.asarray([row["forecasts"][model_name]["pit"] for row in rows], float)
        score_values = [row["forecasts"][model_name]["log_density"] for row in rows]
        coverage = {}
        for level in ("50", "80", "95"):
            coverage[level] = float(np.mean([
                row["truth_log_rv7"] >= row["forecasts"][model_name]["intervals"][level][0]
                and row["truth_log_rv7"] <= row["forecasts"][model_name]["intervals"][level][1]
                for row in rows]))
        scores[model_name] = {"n": len(rows), "mean_log_density": float(np.mean(score_values)),
                              "pit_histogram_10": np.histogram(pits, bins=np.linspace(0, 1, 11))[0].astype(int).tolist(),
                              "central_interval_coverage": coverage}
    scores["primary_mean_gain_linked_vs_unlinked_nats"] = float(np.mean([
        row["forecasts"]["linked_hierarchical"]["log_density"]
        - row["forecasts"]["unlinked_mixture"]["log_density"] for row in rows]))
    scores["matched_rows"] = len(rows)
    scores["distinct_prediction_dates"] = len({row["date"] for row in rows})
    return scores


def _fit_fold_symbol(rows: list[tuple], q_by_day: dict[date, int], start: datetime, end: datetime,
                     fold: str, symbol: str) -> tuple[list[dict], dict]:
    split = temporal_split([row[0] for row in rows], start, end)
    train = [row for row in rows if row[0] in split.train and _features_ok(row)
             and (row[0].prediction_at.date() - timedelta(days=1)) in q_by_day]
    test = [row for row in rows if row[0] in split.test and _features_ok(row)
            and (row[0].prediction_at.date() - timedelta(days=1)) in q_by_day]
    if len(train) < 60 or not test:
        return [], {"status": "NOT_RUN", "reason": "insufficient_matured_train_or_matched_test",
                    "fit_rows": len(train), "test_rows": len(test), "purged": split.purged,
                    "unknown_train": split.unknown_train, "unknown_test": split.unknown_test,
                    "test_rows_without_features_or_slow_state": len(split.test) - len(test)}
    try:
        model = _fit_density_candidates(train, q_by_day)
    except (ValueError, ArithmeticError, np.linalg.LinAlgError) as exc:
        return [], {"status": "NOT_RUN", "reason": str(exc), "fit_rows": len(train),
                    "test_rows": len(test), "purged": split.purged}
    predictions = []
    for target, feature in test:
        state_day = target.prediction_at.date() - timedelta(days=1)
        q = q_by_day[state_day]
        if target.status != "OBSERVED" or target.value is None:
            raise RuntimeError("temporal target split admitted a non-observed test label")
        validate_prediction_window(target.prediction_at, [target.prediction_at],
                                   target.label_start, target.label_end)
        locations = _forecast_locations(model, feature, q)
        fast_state = int(math.exp(feature["log_rv7"]) >= model["fast_threshold"])
        y = math.log(max(float(target.value), 1e-12))
        forecasts = {
            "unlinked_mixture": _density_summary(y, ("mixture", locations["unlinked_mixture"][:2],
                                                       locations["unlinked_mixture"][2])),
            "flat_cells": _density_summary(y, ("single", locations["flat_cells"][0], locations["flat_cells"][1])),
            "linked_hierarchical": _density_summary(y, ("single", locations["linked_hierarchical"][0],
                                                            locations["linked_hierarchical"][1])),
            "continuous_har": _density_summary(y, ("single", locations["continuous_har"][0],
                                                       locations["continuous_har"][1])),
        }
        predictions.append({"symbol": symbol, "fold": fold, "date": target.prediction_at.date().isoformat(),
                            "prediction_at": target.prediction_at.isoformat(), "target_log_start": target.label_start.isoformat(),
                            "target_log_end": target.label_end.isoformat(), "truth_log_rv7": y,
                            "feature_available_at": target.prediction_at.isoformat(),
                            "slow_q_v1_proxy": int(q),
                            "fast_rv7_high": fast_state, "joint_state": f"{int(q)}:{fast_state}",
                            "forecasts": forecasts})
    info = {"status": "TESTED", "fit_rows": len(train), "test_rows": len(test),
            "purged": split.purged, "unknown_train": split.unknown_train,
            "unknown_test": split.unknown_test,
            "test_rows_without_features_or_slow_state": len(split.test) - len(test),
            **model["diagnostics"]}
    return predictions, info


def _group_scores(rows: list[dict], key: str) -> dict:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(str(row[key]), []).append(row)
    return {group: _score_predictions(group_rows) for group, group_rows in sorted(groups.items())}


def _model_complexity(fold_status: dict) -> dict:
    counts = {name: [] for name in MODEL_NAMES}
    for fold, summary in fold_status.items():
        for symbol, info in summary["symbols"].items():
            if info.get("status") != "TESTED":
                continue
            for name in MODEL_NAMES:
                counts[name].append({"fold": fold, "symbol": symbol,
                                     "parameters": info["parameters"][name]})
    return {name: {
        "n_symbol_folds": len(rows), "min": min((row["parameters"] for row in rows), default=None),
        "median": (float(np.median([row["parameters"] for row in rows])) if rows else None),
        "max": max((row["parameters"] for row in rows), default=None),
        "by_symbol_fold": rows,
    } for name, rows in counts.items()}


def run_h3(staging: Path, out_dir: Path, *, run_url: str | None = None) -> dict:
    """Run fixed H3 comparisons on canonical pre-seal development data."""
    from experiments.erf01.pipeline import DAYS, FOLDS, M1_NAMES, M2_NAMES, SEAL, SYMS
    from experiments.erf01.tape_adapter import load_development
    from kepler.intelligence.features import make_panel

    root = Path(__file__).resolve().parents[2]
    protocol_file = root / "reports" / "pmi_h3_protocol.md"
    if hashlib.sha256(protocol_file.read_bytes()).hexdigest() != PROTOCOL_FILE_SHA256:
        raise RuntimeError("H3 protocol differs from its frozen protocol commit")
    if SEAL != date(2026, 4, 1):
        raise RuntimeError("pipeline seal does not match H3 protocol")
    if out_dir.exists():
        raise FileExistsError(f"experiment output already exists: {out_dir}")
    started = time.monotonic()
    prices, _, _, qc_metadata, acquisition = load_development(staging, SYMS, DAYS[0], DAYS[1], SEAL)
    seal_time = datetime.combine(SEAL, datetime.min.time(), UTC)
    prices_preseal = {symbol: {day: candle for day, candle in prices[symbol].items()
                               if datetime.combine(day + timedelta(days=1), datetime.min.time(), UTC) < seal_time}
                      for symbol in SYMS}
    days, panel = make_panel(prices_preseal, {symbol: [] for symbol in SYMS}, symbols=SYMS,
                             day_bounds=DAYS, m1_names=M1_NAMES, m2_names=M2_NAMES)
    q_by_symbol = {symbol: {day: int(panel[symbol]["q"][index]) for index, day in enumerate(days)
                            if np.isfinite(panel[symbol]["q"][index])}
                   for symbol in SYMS}
    prepared = {symbol: _target_rows(symbol, prices[symbol], seal=seal_time) for symbol in SYMS}
    predictions, fold_status = [], {}
    for fold_start, fold_end, fold_name in FOLDS:
        start = datetime.combine(fold_start, datetime.min.time(), UTC)
        end = datetime.combine(fold_end, datetime.min.time(), UTC)
        fold_rows, symbol_status = [], {}
        for symbol in SYMS:
            rows, info = _fit_fold_symbol(prepared[symbol], q_by_symbol[symbol], start, end,
                                          fold_name, symbol)
            symbol_status[symbol] = info
            fold_rows.extend(rows)
        predictions.extend(fold_rows)
        fold_status[fold_name] = {"symbols": symbol_status, "matched_rows": len(fold_rows),
                                  "symbols_tested": sum(x["status"] == "TESTED" for x in symbol_status.values())}
    scores = _score_predictions(predictions)
    differences = [(row["date"], row["forecasts"]["linked_hierarchical"]["log_density"]
                    - row["forecasts"]["unlinked_mixture"]["log_density"]) for row in predictions]
    interval = paired_date_block_interval(differences, block_days=BOOTSTRAP_BLOCK_DAYS,
                                          replicates=BOOTSTRAP_REPLICATES, seed=EXPERIMENT_SEED)
    tested_folds = sorted({row["fold"] for row in predictions})
    gain = scores.get("primary_mean_gain_linked_vs_unlinked_nats")
    if len(tested_folds) < 2 or interval["p025"] is None or gain is None:
        decision = "INCONCLUSIVE"
    elif gain >= MINIMUM_MEAN_GAIN and interval["p025"] > 0:
        decision = "SUPPORTED_ON_SEEN_DEV"
    elif interval["p025"] <= 0 and interval["p975"] is not None and interval["p975"] >= MINIMUM_MEAN_GAIN:
        decision = "INCONCLUSIVE"
    else:
        decision = "NOT_SUPPORTED_ON_SEEN_DEV"
    code_paths = [Path(__file__), Path(__file__).with_name("h1.py"), Path(__file__).with_name("h7.py"),
                  root / "kepler/intelligence/validation.py", root / "kepler/intelligence/metrics_v2.py",
                  root / "kepler/intelligence/features.py", root / "experiments/erf01/tape_adapter.py"]
    code_hashes = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in code_paths}
    data_hashes = {f"{record['symbol']}/{record['kind']}": record["sha256"]
                   for record in acquisition["records"]}
    config = {"experiment": "PMI-H3", "target": "future_observed_log_RV7",
              "primary_horizon_days": PRIMARY_HORIZON_DAYS, "slow_state": "q_v1_proxy",
              "fast_state": "current_RV7_fit_q75", "fast_state_quantile": FAST_STATE_QUANTILE,
              "df": DF, "unlinked_mixture_weights": [0.5, 0.5],
              "linked_ridge_penalties": {"intercept": 0.0, "main_effects": 1.0,
                                         "slow_fast_interactions": 10.0},
              "student_t_scale_conversion": "residual_RMS*sqrt((df-2)/df)",
              "models": list(MODEL_NAMES), "minimum_mean_gain_nats": MINIMUM_MEAN_GAIN,
              "bootstrap_block_days": BOOTSTRAP_BLOCK_DAYS,
              "bootstrap_replicates": BOOTSTRAP_REPLICATES, "bootstrap_seed": EXPERIMENT_SEED,
              "symbols": list(SYMS), "folds": [{"start": a.isoformat(), "end": b.isoformat(), "name": n}
                                                    for a, b, n in FOLDS],
              "canonical_seal_exclusive": SEAL.isoformat()}
    receipt = deterministic_receipt(protocol_sha=PROTOCOL_SHA, code_sha256=code_hashes,
                                    data_sha256=data_hashes, config=config, seed=EXPERIMENT_SEED,
                                    run_url=run_url, science_status="EXPLORATORY")
    qc_findings = [finding for symbol in SYMS for finding in qc_metadata[symbol]["qc_findings"]]
    result = {"experiment": "PMI-H3", "status": "EXPLORATORY",
              "decision_rule_result": decision,
              "interpretation": "Seen-development observable-risk forecast comparison only; q_v1 is a technical proxy, not economic ground truth. This lightweight benchmark is not a filtered HMM/HSMM.",
              "primary": {"target": "future observed log RV7", "horizon_days": PRIMARY_HORIZON_DAYS,
                          "candidate": "linked hierarchical ridge", "baseline": "unlinked fast/slow Student-t mixture",
                          "minimum_mean_gain_nats": MINIMUM_MEAN_GAIN, "scores": scores,
                          "paired_date_block_bootstrap": interval, "tested_folds": tested_folds},
              "by_fold": _group_scores(predictions, "fold"),
              "by_year": _group_scores([{**row, "year": row["date"][:4]} for row in predictions], "year"),
              "by_symbol": _group_scores(predictions, "symbol"),
              "joint_state_scores": _group_scores(predictions, "joint_state"),
              "model_complexity": _model_complexity(fold_status),
              "fold_status": fold_status, "n_prediction_rows": len(predictions),
              "n_distinct_prediction_dates": len({row["date"] for row in predictions}),
              "source_validation": {"status": "ERROR_FREE_WITH_FINDINGS_PRESERVED",
                                    "seal_start": SEAL.isoformat(), "source_file_count": len(acquisition["records"]),
                                    "source_bytes": acquisition["source_bytes"],
                                    "qc_severity_counts": {severity: sum(f["severity"] == severity for f in qc_findings)
                                                           for severity in ("ERROR", "WARN", "INFO")}},
              "receipt": receipt, "runtime_seconds": round(time.monotonic() - started, 3)}
    out_dir.mkdir(parents=True)
    (out_dir / "metrics.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    with (out_dir / "predictions.jsonl").open("w", encoding="utf-8") as handle:
        for row in predictions:
            handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
    (out_dir / "manifest.json").write_text(json.dumps({
        "experiment": "PMI-H3", "receipt_id": receipt["receipt_id"], "protocol_sha": PROTOCOL_SHA,
        "code_sha256": code_hashes, "data_sha256": data_hashes, "configuration": config,
        "run_url": run_url, "runtime_seconds": result["runtime_seconds"], "status": result["status"]},
        indent=2, sort_keys=True) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-url")
    args = parser.parse_args(argv)
    result = run_h3(args.staging, args.out, run_url=args.run_url)
    print("PMI_H3_RESULT=" + json.dumps({"status": result["status"],
                                        "decision_rule_result": result["decision_rule_result"],
                                        "rows": result["n_prediction_rows"],
                                        "runtime_seconds": result["runtime_seconds"],
                                        "receipt_id": result["receipt"]["receipt_id"],
                                        "primary": result["primary"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
