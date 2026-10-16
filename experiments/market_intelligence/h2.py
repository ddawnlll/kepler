"""Frozen PMI-H2 duration comparison on canonical pre-seal DEV tape."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np

from kepler.intelligence.metrics_v2 import paired_date_block_interval
from kepler.intelligence.survival import (
    HAZARD_FAMILIES,
    build_survival_landmarks,
    fit_delayed_entry_censor_curve,
    fit_discrete_hazard,
    forecast_remaining_survival,
    ipcw_survival_scores,
)
from kepler.intelligence.validation import daily_close_time, deterministic_receipt

UTC = timezone.utc
HORIZONS = (3, 7, 14, 21)
PRIMARY_HORIZON = 14
RESIDUAL_LIFE_MAX_DAYS = 365
BOOTSTRAP_BLOCK_DAYS = 28
BOOTSTRAP_REPLICATES = 2000
BOOTSTRAP_SEED = 20261016
MINIMUM_EFFECTIVE_N = 100.0
MAXIMUM_IPCW_WEIGHT = 20.0
MAXIMUM_ABS_CALIBRATION = 0.05
MINIMUM_MEANINGFUL_BRIER_IMPROVEMENT = 0.005
PROTOCOL_SHA = "97db1f8ea813d101e3cd69008ee63e1b3add5a4a"
PROTOCOL_FILE_SHA256 = "77fd4d1ee2f91de627063d3d184cfec9bb0cb4e737b6ed379d7a27b91dab06d1"


def _market_features_by_day(prices: dict[date, tuple], seal: datetime) -> dict[date, dict[str, float]]:
    from experiments.market_intelligence.h1 import _features_for_symbol
    return _features_for_symbol(prices, seal=seal)


def _sensitivity_states(z20: np.ndarray, er20: np.ndarray) -> list[int | None]:
    """One frozen secondary q sensitivity; unavailable inputs stay unknown."""
    z20, er20 = np.asarray(z20, dtype=np.float64), np.asarray(er20, dtype=np.float64)
    if z20.ndim != 1 or er20.shape != z20.shape:
        raise ValueError("z20 and er20 sensitivity inputs must be aligned vectors")
    out: list[int | None] = []
    for z, efficiency in zip(z20, er20):
        if not (np.isfinite(z) and np.isfinite(efficiency)):
            out.append(None)
        elif z >= 1.50 and efficiency >= .35:
            out.append(1)
        elif z <= -1.50 and efficiency >= .35:
            out.append(-1)
        else:
            out.append(0)
    return out


def _interval_quantile(survival_path: np.ndarray, probability: float) -> int | None:
    event_cdf = 1.0 - np.asarray(survival_path, dtype=np.float64)
    found = np.flatnonzero(event_cdf >= probability)
    return int(found[0] + 1) if len(found) else None


def _residual_intervals(daily_hazards: list[float]) -> dict[str, dict | None]:
    survival = np.cumprod(1.0 - np.asarray(daily_hazards, dtype=np.float64))
    result = {}
    for name, coverage in (("50", .50), ("80", .80), ("95", .95)):
        lower = _interval_quantile(survival, (1.0 - coverage) / 2.0)
        upper = _interval_quantile(survival, (1.0 + coverage) / 2.0)
        result[name] = ({"lower_days": lower, "upper_days": upper}
                        if lower is not None and upper is not None else None)
    return result


def _score_collection(
    rows: list[dict], horizon: int, family: str,
    censor_curves: dict[tuple[str, str], dict[int, dict[str, float]]],
) -> dict:
    """Score rows with their own symbol-fold training censor curve, then pool."""
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        grouped[(row["fold"], row["symbol"])].append(row)
    partial = []
    for key, selected in sorted(grouped.items()):
        partial.append(ipcw_survival_scores(
            [row["targets"][horizon] for row in selected],
            [row["probabilities"][family][str(horizon)] for row in selected],
            censor_curves[key], bins=5, minimum_effective_n=MINIMUM_EFFECTIVE_N,
        ))
    return _pool_ipcw_scores(partial)


def _pool_ipcw_scores(scores: list[dict]) -> dict:
    n = sum(score["n_scored"] for score in scores)
    weight_sum = sum(score["weight_sum"] for score in scores)
    weight_square_sum = sum(score["weight_square_sum"] for score in scores)
    weighted_brier = sum((score["brier"] or 0.0) * score["weight_sum"] for score in scores)
    weighted_calibration = sum((score["calibration_in_the_large"] or 0.0)
                               * score["weight_sum"] for score in scores)
    date_loss: dict[str, float] = defaultdict(float)
    date_weights: dict[str, float] = defaultdict(float)
    for score in scores:
        for day, brier in score["date_brier"].items():
            weight = score["date_weight_sum"][day]
            date_loss[day] += brier * weight
            date_weights[day] += weight
    reliability = []
    for index in range(5):
        selected = [item for score in scores for item in score["reliability"]
                    if item["lower"] == index / 5]
        bin_weight = sum(item["weight_sum"] for item in selected)
        probability_sum = sum((item["mean_probability"] or 0.0) * item["weight_sum"]
                              for item in selected)
        survival_sum = sum((item["survival_rate"] or 0.0) * item["weight_sum"]
                           for item in selected)
        reliability.append({
            "lower": index / 5, "upper": (index + 1) / 5,
            "n": sum(item["n"] for item in selected), "weight_sum": bin_weight,
            "mean_probability": probability_sum / bin_weight if bin_weight else None,
            "survival_rate": survival_sum / bin_weight if bin_weight else None,
        })
    effective_n = weight_sum ** 2 / weight_square_sum if weight_square_sum else 0.0
    max_weights = [score["max_ipcw_weight"] for score in scores
                   if score["max_ipcw_weight"] is not None]
    return {
        "n_scored": n,
        "n_exits": sum(score["n_exits"] for score in scores),
        "n_survivors": sum(score["n_survivors"] for score in scores),
        "n_left_censored": sum(score["n_left_censored"] for score in scores),
        "n_censored_before_horizon": sum(score["n_censored_before_horizon"] for score in scores),
        "n_zero_weight": sum(score["n_zero_weight"] for score in scores),
        "brier": weighted_brier / weight_sum if weight_sum else None,
        "effective_n": effective_n,
        "minimum_effective_n": MINIMUM_EFFECTIVE_N,
        "support_adequate": effective_n >= MINIMUM_EFFECTIVE_N,
        "weight_sum": weight_sum,
        "weight_square_sum": weight_square_sum,
        "max_ipcw_weight": max(max_weights) if max_weights else None,
        "calibration_in_the_large": weighted_calibration / weight_sum if weight_sum else None,
        "reliability": reliability,
        "date_brier": {day: date_loss[day] / date_weights[day] for day in sorted(date_loss)},
        "date_weight_sum": dict(sorted(date_weights.items())),
    }


def _serializable_prediction(row: dict) -> dict:
    primary = row["targets"][PRIMARY_HORIZON]
    result = {key: value for key, value in row.items() if key != "targets"}
    result["targets"] = {
        str(horizon): {
            "label_end": target.label_end.isoformat(), "status": target.status,
            "followup_days": int(target.followup_days),
            "survives_horizon": target.survives_horizon,
            "event_time_days": target.event_time_days,
        }
        for horizon, target in row["targets"].items()
    }
    result["primary_target"] = {
        "status": primary.status, "survives_horizon": primary.survives_horizon,
        "event_time_days": primary.event_time_days,
    }
    return result


def _unique_test_events(rows: list[dict]) -> dict:
    events = {}
    for row in rows:
        target = row["targets"][PRIMARY_HORIZON]
        if target.status != "OBSERVED" or target.survives_horizon != 0:
            continue
        event_day = row["prediction_at"].date() + timedelta(days=target.event_time_days)
        event_key = (row["symbol"], event_day.isoformat())
        current = events.get(event_key)
        if current is None or row["prediction_at"] < current["prediction_at"]:
            events[event_key] = {"symbol": row["symbol"], "event_date": event_day.isoformat(),
                                 "fold": row["fold"], "first_test_prediction_at": row["prediction_at"].isoformat()}
    by_fold = defaultdict(int)
    for event in events.values():
        by_fold[event["fold"]] += 1
    return {"n_unique_symbol_exit_events": len(events),
            "n_distinct_exit_dates": len({event["event_date"] for event in events.values()}),
            "by_fold": dict(sorted(by_fold.items())),
            "events": [events[key] for key in sorted(events)]}


def _interval_coverage(rows: list[dict]) -> dict:
    result = {}
    for family in sorted(HAZARD_FAMILIES):
        result[family] = {}
        for level in ("50", "80", "95"):
            eligible = [row for row in rows
                        if row["targets"][PRIMARY_HORIZON].status == "OBSERVED"
                        and row["targets"][PRIMARY_HORIZON].survives_horizon == 0]
            estimable = [row for row in eligible
                         if row["residual_life_intervals"][family][level] is not None]
            covered = sum(
                row["residual_life_intervals"][family][level]["lower_days"]
                <= row["targets"][PRIMARY_HORIZON].event_time_days
                <= row["residual_life_intervals"][family][level]["upper_days"]
                for row in estimable
            )
            result[family][level] = {
                "status": "TESTED" if estimable else "INCONCLUSIVE",
                "n_primary_observed_exits": len(eligible),
                "n_estimable_intervals": len(estimable),
                "n_covered": covered,
                "empirical_coverage": covered / len(estimable) if estimable else None,
            }
    return result


def _grouped_scores(rows: list[dict], key: str, censor_curves) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[str(row[key])].append(row)
    result = {}
    for group, selected in sorted(groups.items()):
        result[group] = {}
        for horizon in HORIZONS:
            result[group][str(horizon)] = {
                family: _score_collection(selected, horizon, family, censor_curves)
                for family in sorted(HAZARD_FAMILIES)
            }
    return result


def _evaluate_ontology(
    *, states_by_symbol: dict[str, list[int | None]], days: list[date],
    prediction_times: list[datetime], features_by_symbol: dict[str, dict],
    symbols: list[str], folds: list[tuple], residual_forecast: bool,
) -> tuple[list[dict], dict, dict, int]:
    targets_by_symbol = {
        symbol: {
            horizon: build_survival_landmarks(
                symbol, days, states_by_symbol[symbol], prediction_times, horizon)
            for horizon in (1, *HORIZONS)
        }
        for symbol in symbols
    }
    all_predictions: list[dict] = []
    fold_status: dict = {}
    censor_curves: dict = {}
    left_censored_total = 0
    max_forecast_days = RESIDUAL_LIFE_MAX_DAYS if residual_forecast else max(HORIZONS)
    for fold_start, fold_end, fold_name in folds:
        start = datetime.combine(fold_start, datetime.min.time(), UTC)
        end = datetime.combine(fold_end, datetime.min.time(), UTC)
        symbol_status = {}
        fold_predictions = []
        for symbol in symbols:
            one_day = targets_by_symbol[symbol][1]
            features = features_by_symbol[symbol]
            train_risk = [target for target in one_day
                          if target.prediction_at < start and target.label_end < start]
            train_censor = [target for target in train_risk if target.elapsed_age is not None]
            finite_train = []
            for target in train_risk:
                day = target.prediction_at.date() - timedelta(days=1)
                values = features.get(day)
                if values is not None and all(np.isfinite(values.get(name, np.nan))
                                              for name in ("log_rv1", "log_rv7", "log_rv30")):
                    finite_train.append((target, values))
            h14_targets = targets_by_symbol[symbol][PRIMARY_HORIZON]
            test_state_targets = [target for target in h14_targets
                                  if start <= target.prediction_at < end]
            left_censored_test = sum(target.elapsed_age is None for target in test_state_targets)
            observed_episode_onsets = sum(target.elapsed_age == 1 for target in test_state_targets)
            left_censored_total += left_censored_test
            test_targets = []
            for target in test_state_targets:
                if target.elapsed_age is None:
                    continue
                day = target.prediction_at.date() - timedelta(days=1)
                values = features.get(day)
                if values is None or not all(np.isfinite(values.get(name, np.nan))
                                             for name in ("log_rv1", "log_rv7", "log_rv30")):
                    continue
                test_targets.append((target, values))
            if not finite_train or not test_targets:
                symbol_status[symbol] = {
                    "status": "NOT_RUN", "reason": "insufficient_feature_complete_training_or_test_rows",
                    "training_risk_rows": len(train_risk), "training_known_onset_rows": len(train_censor),
                    "training_feature_complete_rows": len(finite_train),
                    "test_state_rows": len(test_state_targets), "test_feature_complete_rows": len(test_targets),
                    "test_left_censored_landmarks": left_censored_test,
                    "test_observed_episode_onsets": observed_episode_onsets,
                }
                continue
            try:
                through_age = max(int(target.elapsed_age) for target, _ in test_targets) + max_forecast_days
                censor_curve = fit_delayed_entry_censor_curve(
                    train_censor, through_age=through_age, matured_before=start)
                models = {
                    family: fit_discrete_hazard(
                        [target for target, _ in finite_train],
                        [[values[name] for name in ("log_rv1", "log_rv7", "log_rv30")]
                         for _, values in finite_train],
                        family=family, matured_before=start,
                        feature_available_times=[target.prediction_at for target, _ in finite_train],
                    )
                    for family in sorted(HAZARD_FAMILIES)
                }
            except (ValueError, ArithmeticError, np.linalg.LinAlgError) as exc:
                symbol_status[symbol] = {
                    "status": "NOT_RUN", "reason": str(exc),
                    "training_risk_rows": len(train_risk), "training_feature_complete_rows": len(finite_train),
                    "test_feature_complete_rows": len(test_targets),
                    "test_left_censored_landmarks": left_censored_test,
                    "test_observed_episode_onsets": observed_episode_onsets,
                }
                continue
            censor_curves[(fold_name, symbol)] = censor_curve
            model_support = {family: {"n_fit": model.n_fit, "n_exits": model.n_exits,
                                      "n_censored": model.n_censored,
                                      "n_left_censored": model.n_left_censored}
                             for family, model in models.items()}
            target_maps = {
                horizon: {target.prediction_at: target
                          for target in targets_by_symbol[symbol][horizon]}
                for horizon in HORIZONS
            }
            for primary_target, values in test_targets:
                market = [values[name] for name in ("log_rv1", "log_rv7", "log_rv30")]
                forecasts = {}
                residual_intervals = {}
                for family, model in models.items():
                    forecast = forecast_remaining_survival(
                        model, state=primary_target.state, elapsed_age=primary_target.elapsed_age,
                        market_conditions=market, prediction_at=primary_target.prediction_at,
                        feature_available_at=primary_target.prediction_at,
                        horizon_days=max_forecast_days,
                    )
                    survival_path = np.cumprod(1.0 - np.asarray(forecast["daily_exit_hazards"]))
                    forecasts[family] = {
                        str(horizon): float(survival_path[horizon - 1]) for horizon in HORIZONS
                    }
                    if residual_forecast:
                        residual_intervals[family] = _residual_intervals(forecast["daily_exit_hazards"])
                horizon_targets = {horizon: target_maps[horizon][primary_target.prediction_at]
                                   for horizon in HORIZONS}
                fold_predictions.append({
                    "symbol": symbol, "fold": fold_name,
                    "year": str(primary_target.prediction_at.year),
                    "prediction_at": primary_target.prediction_at,
                    "state": primary_target.state, "elapsed_age": primary_target.elapsed_age,
                    "market_features": dict(zip(("log_rv1", "log_rv7", "log_rv30"), market)),
                    "targets": horizon_targets, "probabilities": forecasts,
                    "residual_life_intervals": residual_intervals,
                })
            symbol_status[symbol] = {
                "status": "TESTED", "training_risk_rows": len(train_risk),
                "training_known_onset_rows": len(train_censor),
                "training_feature_complete_rows": len(finite_train),
                "training_censor_curve_max_age": through_age,
                "test_state_rows": len(test_state_targets),
                "test_feature_complete_rows": len(test_targets),
                "test_left_censored_landmarks": left_censored_test,
                "test_observed_episode_onsets": observed_episode_onsets,
                "models": model_support,
            }
        all_predictions.extend(fold_predictions)
        fold_status[fold_name] = {
            "symbols": symbol_status, "scored_landmarks": len(fold_predictions),
            "symbols_tested": sum(x["status"] == "TESTED" for x in symbol_status.values()),
        }
    return all_predictions, fold_status, censor_curves, left_censored_total


def run_h2(staging: Path, out_dir: Path, *, run_url: str | None = None) -> dict:
    """Run H2's fixed age/market hazard comparison on canonical DEV tape."""
    if out_dir.exists():
        raise FileExistsError(f"experiment output already exists: {out_dir}")
    out_dir.mkdir(parents=True)
    started = time.monotonic()
    from experiments.erf01.pipeline import DAYS, FOLDS, M1_NAMES, M2_NAMES, SEAL, SYMS
    from experiments.erf01.tape_adapter import load_development
    from kepler.intelligence.features import make_panel

    root = Path(__file__).resolve().parents[2]
    seal_time = datetime.combine(SEAL, datetime.min.time(), UTC)
    protocol_path = root / "reports" / "pmi_h2_protocol.md"
    if not PROTOCOL_SHA or not PROTOCOL_FILE_SHA256:
        raise RuntimeError("H2 frozen protocol commit/hash constants are missing")
    if hashlib.sha256(protocol_path.read_bytes()).hexdigest() != PROTOCOL_FILE_SHA256:
        raise RuntimeError("H2 protocol differs from its frozen pre-run commit")
    if SEAL != date(2026, 4, 1):
        raise RuntimeError("ERF-01 seal differs from the H2 protocol")

    try:
        prices, _funding, _funding_records, qc_metadata, acquisition = load_development(
            staging, SYMS, DAYS[0], DAYS[1], SEAL)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        result = {
            "experiment": "PMI-H2", "status": "DATA_BLOCKED", "decision_rule_result": "NOT_RUN",
            "scored": False, "failure": {"type": type(exc).__name__, "reason": str(exc)},
            "protocol_sha": PROTOCOL_SHA, "run_url": run_url,
        }
        _write_outputs(out_dir, result, [], {}, {}, {}, run_url)
        return result

    prices_preseal = {
        symbol: {day: values for day, values in prices[symbol].items()
                 if daily_close_time(day) < seal_time}
        for symbol in SYMS
    }
    days, panel = make_panel(
        prices_preseal, {symbol: [] for symbol in SYMS}, symbols=SYMS,
        day_bounds=DAYS, m1_names=M1_NAMES, m2_names=M2_NAMES,
    )
    prediction_times = [daily_close_time(day) for day in days]
    features_by_symbol = {}
    primary_states = {}
    sensitivity_states = {}
    for symbol in SYMS:
        primary_states[symbol] = [int(panel[symbol]["q"][i])
                                  if np.isfinite(panel[symbol]["q"][i]) else None
                                  for i in range(len(days))]
        sensitivity_states[symbol] = _sensitivity_states(
            panel[symbol]["z20"], panel[symbol]["er20"])
        features_by_symbol[symbol] = _market_features_by_day(prices_preseal[symbol], seal_time)
    all_predictions, fold_status, censor_curves, left_censored_count = _evaluate_ontology(
        states_by_symbol=primary_states, days=days, prediction_times=prediction_times,
        features_by_symbol=features_by_symbol, symbols=SYMS, folds=FOLDS,
        residual_forecast=True,
    )
    sensitivity_predictions, sensitivity_fold_status, sensitivity_censor_curves, _ = _evaluate_ontology(
        states_by_symbol=sensitivity_states, days=days, prediction_times=prediction_times,
        features_by_symbol=features_by_symbol, symbols=SYMS, folds=FOLDS,
        residual_forecast=False,
    )

    horizon_scores = {
        str(horizon): {
            family: _score_collection(all_predictions, horizon, family, censor_curves)
            for family in sorted(HAZARD_FAMILIES)
        }
        for horizon in HORIZONS
    }
    baseline = horizon_scores[str(PRIMARY_HORIZON)]["market_only"]
    candidate = horizon_scores[str(PRIMARY_HORIZON)]["market_plus_age"]
    date_differences = [
        (day, baseline["date_brier"][day] - candidate["date_brier"][day])
        for day in sorted(set(baseline["date_brier"]) & set(candidate["date_brier"]))
    ]
    interval = paired_date_block_interval(
        date_differences, block_days=BOOTSTRAP_BLOCK_DAYS,
        replicates=BOOTSTRAP_REPLICATES, seed=BOOTSTRAP_SEED,
    ) if date_differences else {
        "n_dates": 0, "mean": None, "p025": None, "p975": None,
        "replicates": 0, "block_days": BOOTSTRAP_BLOCK_DAYS, "seed": BOOTSTRAP_SEED,
    }
    event_support = _unique_test_events(all_predictions)
    sensitivity_horizon_scores = {
        family: _score_collection(sensitivity_predictions, PRIMARY_HORIZON, family,
                                  sensitivity_censor_curves)
        for family in sorted(HAZARD_FAMILIES)
    }
    sensitivity_baseline = sensitivity_horizon_scores["market_only"]
    sensitivity_candidate = sensitivity_horizon_scores["market_plus_age"]
    sensitivity_improvement = (
        sensitivity_baseline["brier"] - sensitivity_candidate["brier"]
        if sensitivity_baseline["brier"] is not None and sensitivity_candidate["brier"] is not None
        else None
    )
    sensitivity_differences = [
        (day, sensitivity_baseline["date_brier"][day] - sensitivity_candidate["date_brier"][day])
        for day in sorted(set(sensitivity_baseline["date_brier"])
                          & set(sensitivity_candidate["date_brier"]))
    ]
    sensitivity_interval = paired_date_block_interval(
        sensitivity_differences, block_days=BOOTSTRAP_BLOCK_DAYS,
        replicates=BOOTSTRAP_REPLICATES, seed=BOOTSTRAP_SEED,
    ) if sensitivity_differences else {
        "n_dates": 0, "mean": None, "p025": None, "p975": None,
        "replicates": 0, "block_days": BOOTSTRAP_BLOCK_DAYS, "seed": BOOTSTRAP_SEED,
    }
    support_conditions = {
        "baseline_effective_n_at_least_100": baseline["effective_n"] >= MINIMUM_EFFECTIVE_N,
        "candidate_effective_n_at_least_100": candidate["effective_n"] >= MINIMUM_EFFECTIVE_N,
        "candidate_max_weight_at_most_20": (candidate["max_ipcw_weight"] is not None
                                              and candidate["max_ipcw_weight"] <= MAXIMUM_IPCW_WEIGHT),
        "candidate_abs_calibration_at_most_0_05": (candidate["calibration_in_the_large"] is not None
                                                      and abs(candidate["calibration_in_the_large"])
                                                      <= MAXIMUM_ABS_CALIBRATION),
        "observed_exits_in_at_least_two_test_folds": sum(
            count > 0 for count in event_support["by_fold"].values()) >= 2,
        "continuous_28_day_interval_available": interval["p025"] is not None,
        "primary_scores_available": baseline["brier"] is not None and candidate["brier"] is not None,
    }
    improvement = (baseline["brier"] - candidate["brier"]
                   if baseline["brier"] is not None and candidate["brier"] is not None else None)
    if not all(support_conditions.values()):
        decision = "INCONCLUSIVE"
    elif improvement >= MINIMUM_MEANINGFUL_BRIER_IMPROVEMENT and interval["p025"] > 0:
        decision = "SUPPORTED_ON_SEEN_DEV"
    elif (interval["p025"] <= 0 and interval["p975"] is not None
          and interval["p975"] >= MINIMUM_MEANINGFUL_BRIER_IMPROVEMENT):
        decision = "INCONCLUSIVE"
    else:
        decision = "NOT_SUPPORTED_ON_SEEN_DEV"

    year_rows = [row for row in all_predictions]
    by_fold = _grouped_scores(all_predictions, "fold", censor_curves)
    by_year = _grouped_scores(year_rows, "year", censor_curves)
    by_symbol = _grouped_scores(all_predictions, "symbol", censor_curves)
    source_records = [{key: row[key] for key in ("symbol", "kind", "sha256", "bytes")}
                      for row in acquisition["records"]]
    qc_findings = [item for symbol in SYMS for item in qc_metadata[symbol]["qc_findings"]]
    qc_counts = {severity: sum(item["severity"] == severity for item in qc_findings)
                 for severity in ("ERROR", "WARN", "INFO")}
    data_hashes = {f"{item['symbol']}/{item['kind']}": item["sha256"] for item in source_records}
    code_paths = (
        Path(__file__), root / "kepler/intelligence/survival.py",
        root / "kepler/intelligence/validation.py", root / "kepler/intelligence/metrics_v2.py",
        root / "kepler/intelligence/features.py", root / "experiments/market_intelligence/h1.py",
        root / "experiments/erf01/tape_adapter.py", root / "experiments/erf01/pipeline.py",
        root / "kepler/tape.py", root / "kepler/qc.py",
    )
    code_hashes = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in code_paths}
    config = {
        "experiment": "PMI-H2", "target": "q_v1_proxy uninterrupted observed state episode",
        "primary_horizon_days": PRIMARY_HORIZON, "secondary_horizon_days": [3, 7, 21],
        "symbols": list(SYMS), "folds": [{"start": a.isoformat(), "end": b.isoformat(), "name": n}
                                            for a, b, n in FOLDS],
        "candidates": sorted(HAZARD_FAMILIES), "logistic_l2": 1.0,
        "minimum_meaningful_brier_improvement": MINIMUM_MEANINGFUL_BRIER_IMPROVEMENT,
        "minimum_effective_n": MINIMUM_EFFECTIVE_N,
        "maximum_ipcw_weight": MAXIMUM_IPCW_WEIGHT,
        "maximum_abs_candidate_calibration": MAXIMUM_ABS_CALIBRATION,
        "residual_life_max_days": RESIDUAL_LIFE_MAX_DAYS,
        "bootstrap_block_days": BOOTSTRAP_BLOCK_DAYS,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "canonical_seal_exclusive": SEAL.isoformat(),
        "secondary_label_sensitivity": {
            "name": "q_z20_pm1_50_er20_0_35", "directional_z20_threshold": 1.50,
            "efficiency_ratio_minimum": .35,
        },
    }
    receipt = deterministic_receipt(
        protocol_sha=PROTOCOL_SHA, code_sha256=code_hashes, data_sha256=data_hashes,
        config=config, seed=BOOTSTRAP_SEED, run_url=run_url, science_status="EXPLORATORY",
    )
    status = "EXPLORATORY" if all_predictions else "NOT_RUN"
    result = {
        "experiment": "PMI-H2", "status": status,
        "decision_rule_result": decision if all_predictions else "NOT_RUN",
        "interpretation": "Previously examined DEV only; q_v1_proxy is an observable technical label, not a latent economic regime.",
        "primary": {
            "target": "14-day uninterrupted observed q_v1_proxy episode survival",
            "baseline": "market_conditions_only", "candidate": "market_conditions_plus_elapsed_age",
            "minimum_meaningful_brier_improvement": MINIMUM_MEANINGFUL_BRIER_IMPROVEMENT,
            "absolute_ipcw_brier_improvement": improvement,
            "paired_28_calendar_day_block_interval_baseline_minus_candidate": interval,
            "baseline_scores": baseline, "candidate_scores": candidate,
            "support_conditions": support_conditions,
        },
        "horizon_scores": horizon_scores,
        "by_fold": by_fold, "by_year": by_year, "by_symbol": by_symbol,
        "residual_life_interval_coverage": _interval_coverage(all_predictions),
        "event_support": event_support,
        "fold_status": fold_status,
        "n_prediction_rows": len(all_predictions),
        "n_distinct_prediction_dates": len({row["prediction_at"].date().isoformat() for row in all_predictions}),
        "test_left_censored_landmarks": sum(
            item.get("test_left_censored_landmarks", 0)
            for fold in fold_status.values() for item in fold["symbols"].values()),
        "test_observed_episode_onsets": sum(
            item.get("test_observed_episode_onsets", 0)
            for fold in fold_status.values() for item in fold["symbols"].values()),
        "label_sensitivity": {
            "status": "EXPLORATORY" if sensitivity_predictions else "NOT_RUN",
            "ontology": "q_z20_pm1_50_er20_0_35",
            "primary_horizon_days": PRIMARY_HORIZON,
            "market_only_scores": sensitivity_baseline,
            "market_plus_age_scores": sensitivity_candidate,
            "absolute_ipcw_brier_improvement": sensitivity_improvement,
            "paired_28_calendar_day_block_interval": sensitivity_interval,
            "event_support": _unique_test_events(sensitivity_predictions),
            "fold_status": sensitivity_fold_status,
        },
        "source_validation": {
            "status": "ERROR_FREE_WITH_FINDINGS_PRESERVED", "seal_start": SEAL.isoformat(),
            "source_file_count": acquisition["record_count"], "source_bytes": acquisition["source_bytes"],
            "symbols": SYMS, "qc_severity_counts": qc_counts,
            "qc_findings": qc_findings, "sources": source_records,
        },
        "receipt": receipt, "runtime_seconds": round(time.monotonic() - started, 3),
    }
    _write_outputs(out_dir, result, all_predictions, code_hashes, data_hashes, config, run_url,
                   sensitivity_predictions=sensitivity_predictions)
    return result


def _write_outputs(out_dir: Path, result: dict, predictions: list[dict], code_hashes: dict,
                   data_hashes: dict, config: dict, run_url: str | None,
                   *, sensitivity_predictions: list[dict] | None = None) -> None:
    (out_dir / "metrics.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    with (out_dir / "predictions.jsonl").open("w", encoding="utf-8") as handle:
        for row in predictions:
            handle.write(json.dumps(_serializable_prediction(row), sort_keys=True, allow_nan=False) + "\n")
    if sensitivity_predictions is not None:
        with (out_dir / "sensitivity_predictions.jsonl").open("w", encoding="utf-8") as handle:
            for row in sensitivity_predictions:
                handle.write(json.dumps(_serializable_prediction(row), sort_keys=True, allow_nan=False) + "\n")
    (out_dir / "manifest.json").write_text(json.dumps({
        "experiment": "PMI-H2", "status": result["status"],
        "protocol_sha": PROTOCOL_SHA, "protocol_file_sha256": PROTOCOL_FILE_SHA256,
        "receipt_id": result.get("receipt", {}).get("receipt_id"),
        "code_sha256": code_hashes, "data_sha256": data_hashes,
        "configuration": config, "run_url": run_url,
        "runtime_seconds": result.get("runtime_seconds"),
    }, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-url")
    args = parser.parse_args(argv)
    result = run_h2(args.staging, args.out, run_url=args.run_url)
    print("PMI_H2_RESULT=" + json.dumps({
        "status": result["status"], "decision_rule_result": result["decision_rule_result"],
        "rows": result["n_prediction_rows"], "runtime_seconds": result.get("runtime_seconds"),
        "receipt_id": result.get("receipt", {}).get("receipt_id"),
        "primary_improvement": result.get("primary", {}).get("absolute_ipcw_brier_improvement"),
    }, sort_keys=True))
    return 0 if result["status"] in {"EXPLORATORY", "NOT_RUN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
