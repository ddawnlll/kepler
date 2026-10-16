"""Frozen PMI-H7 comparison: causal discrete states vs continuous Student-t."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np

from kepler.intelligence.metrics_v2 import binary_probability_scores, paired_date_block_interval
from kepler.intelligence.validation import (
    deterministic_receipt, fit_quantile_threshold,
    temporal_split,
)
from experiments.market_intelligence.h1 import (
    _fit_ols, _predict_ols, _target_rows,
)

UTC = timezone.utc
PROTOCOL_SHA = "6e6008088e55d670a55378c64ea9ac48f77d0ce9"
PROTOCOL_FILE_SHA256 = "e1db4266091929a0b590e7f079700a26264c1f33f37ab88866b5b74cd081860f"
DF = 5
PSEUDO_OBSERVATIONS = 20.0
STATES = (-1, 0, 1)
FEATURES = ("log_rv1", "log_rv7", "log_rv30")
EXPERIMENT_SEED = 20261016


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta, Numerical Recipes form."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    tiny, eps = 1e-300, 3e-14
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, 201):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        change = d * c
        h *= change
        if abs(change - 1.0) < eps:
            return h
    raise ArithmeticError("Student-t CDF incomplete-beta continued fraction did not converge")


def _regularized_beta(a: float, b: float, x: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    log_front = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                 + a * math.log(x) + b * math.log1p(-x))
    front = math.exp(log_front)
    if x < (a + 1) / (a + b + 2):
        return front * _beta_continued_fraction(a, b, x) / a
    return 1.0 - front * _beta_continued_fraction(b, a, 1.0 - x) / b


def student_t_logpdf(value: float, location: float, scale: float, df: int = DF) -> float:
    """Log density of a location-scale Student-t random variable."""
    if not all(math.isfinite(x) for x in (value, location, scale)) or scale <= 0 or df <= 0:
        raise ValueError("Student-t inputs must be finite with positive scale and df")
    z = (value - location) / scale
    return (math.lgamma((df + 1) / 2) - math.lgamma(df / 2)
            - .5 * math.log(df * math.pi) - math.log(scale)
            - (df + 1) / 2 * math.log1p(z * z / df))


def student_t_cdf(value: float, location: float, scale: float, df: int = DF) -> float:
    if not all(math.isfinite(x) for x in (value, location, scale)) or scale <= 0 or df <= 0:
        raise ValueError("Student-t inputs must be finite with positive scale and df")
    t = (value - location) / scale
    x = df / (df + t * t)
    ibeta = _regularized_beta(df / 2, .5, x)
    result = 1 - .5 * ibeta if t >= 0 else .5 * ibeta
    return min(max(result, 0.0), 1.0)


def student_t_sf(value: float, location: float, scale: float, df: int = DF) -> float:
    return 1.0 - student_t_cdf(value, location, scale, df)


def _logsumexp(values: np.ndarray) -> float:
    maximum = float(np.max(values))
    return maximum + math.log(float(np.exp(values - maximum).sum()))


def _state_transition(q_by_day: dict[date, int], days: list[date], cutoff: datetime) -> np.ndarray:
    """Add-one transitions, using only consecutive q observations available by cutoff."""
    counts = np.ones((3, 3), dtype=np.float64)
    for day in days:
        next_day = day + timedelta(days=1)
        if datetime.combine(next_day + timedelta(days=1), datetime.min.time(), UTC) > cutoff:
            continue
        if next_day not in q_by_day or day not in q_by_day:
            continue
        counts[q_by_day[day] + 1, q_by_day[next_day] + 1] += 1.0
    return counts / counts.sum(axis=1, keepdims=True)


def _transition_diagnostics(
    q_by_day: dict[date, int], days: list[date], cutoff: datetime,
) -> tuple[list[list[int]], dict[str, int]]:
    counts = np.zeros((3, 3), dtype=np.int64)
    occupancy = {str(state): 0 for state in STATES}
    for day in days:
        available_at = datetime.combine(day + timedelta(days=1), datetime.min.time(), UTC)
        if available_at <= cutoff:
            occupancy[str(q_by_day[day])] += 1
        next_day = day + timedelta(days=1)
        next_available_at = datetime.combine(next_day + timedelta(days=1), datetime.min.time(), UTC)
        if next_available_at <= cutoff:
            if next_day not in q_by_day or day not in q_by_day:
                continue
            counts[q_by_day[day] + 1, q_by_day[next_day] + 1] += 1
    return counts.tolist(), occupancy


def _conditional_state_densities(fit_rows: list[tuple], q_by_day: dict[date, int]) -> dict[int, tuple[float, float]]:
    """Shrink state means and residual variances toward pooled training values."""
    observations: list[tuple[float, int]] = []
    for target, _features in fit_rows:
        future_day = target.label_end.date() - timedelta(days=1)
        state = q_by_day.get(future_day)
        if state in STATES:
            observations.append((math.log(max(float(target.value), 1e-12)), state))
    if not observations:
        raise ValueError("no matured training targets have an observable future q-state")
    values = np.asarray([x[0] for x in observations], dtype=float)
    pooled_mean = float(values.mean())
    pooled_variance = max(float(np.mean((values - pooled_mean) ** 2)), 1e-8)
    result = {}
    for state in STATES:
        selected = np.asarray([v for v, s in observations if s == state], dtype=float)
        n = len(selected)
        state_mean = float(selected.mean()) if n else pooled_mean
        residual_ss = float(np.sum((selected - state_mean) ** 2)) if n else 0.0
        location = (n * state_mean + PSEUDO_OBSERVATIONS * pooled_mean) / (n + PSEUDO_OBSERVATIONS)
        variance = max((residual_ss + PSEUDO_OBSERVATIONS * pooled_variance) /
                       (n + PSEUDO_OBSERVATIONS), 1e-8)
        scale = math.sqrt(variance * (DF - 2) / DF)
        result[state] = (location, max(scale, 1e-6))
    return result


def _candidate_predictions(
    fit_rows: list[tuple], test_rows: list[tuple], q_by_day: dict[date, int],
    threshold_rv7: float,
) -> tuple[list[dict], dict]:
    """Return matched Student-t density and high-risk probability forecasts."""
    density_rows = [(target, feat) for target, feat in fit_rows
                    if target.label_end.date() - timedelta(days=1) in q_by_day]
    if len(density_rows) < 60:
        raise ValueError("fewer than 60 matured fit targets have an observable future q-state")
    y_fit = np.log(np.maximum([r[0].value for r in density_rows], 1e-12))
    x_fit = np.asarray([[r[1][name] for name in FEATURES] for r in density_rows], dtype=float)
    continuous = _fit_ols(x_fit, y_fit)
    continuous_location_fit = _predict_ols(continuous, x_fit)
    residual_rms = float(np.sqrt(np.mean((y_fit - continuous_location_fit) ** 2)))
    continuous_scale = max(residual_rms * math.sqrt((DF - 2) / DF), 1e-6)
    state_densities = _conditional_state_densities(density_rows, q_by_day)

    latest_fit_prediction = fit_rows[-1][0].prediction_at
    q_days = sorted(q_by_day)
    transition = _state_transition(q_by_day, q_days, latest_fit_prediction)
    seven_day_transition = np.linalg.matrix_power(transition, 7)
    transition_counts, occupancy = _transition_diagnostics(q_by_day, q_days, latest_fit_prediction)
    future_q_counts = {str(s): 0 for s in STATES}
    for target, _features in density_rows:
        future_state = q_by_day[target.label_end.date() - timedelta(days=1)]
        future_q_counts[str(future_state)] += 1
    threshold_y = math.log(max(float(threshold_rv7), 1e-12))
    predictions = []
    for target, features, q_today in test_rows:
        y = math.log(max(float(target.value), 1e-12))
        x = np.asarray([[features[name] for name in FEATURES]], dtype=float)
        continuous_location = float(_predict_ols(continuous, x)[0])
        continuous_logpdf = student_t_logpdf(y, continuous_location, continuous_scale)
        state_p = seven_day_transition[int(q_today) + 1]
        log_components, tail_components = [], []
        for state in STATES:
            location, scale = state_densities[state]
            log_components.append(math.log(float(state_p[state + 1])) +
                                  student_t_logpdf(y, location, scale))
            tail_components.append(float(state_p[state + 1]) *
                                   student_t_sf(threshold_y, location, scale))
        discrete_logpdf = _logsumexp(np.asarray(log_components, dtype=float))
        predictions.append({
            "symbol": target.symbol, "date": target.prediction_at.date().isoformat(),
            "prediction_at": target.prediction_at.isoformat(), "truth_log_rv7": y,
            "discrete_logpdf": discrete_logpdf, "continuous_logpdf": continuous_logpdf,
            "continuous_tail_probability": student_t_sf(threshold_y, continuous_location,
                                                        continuous_scale),
            "discrete_tail_probability": float(sum(tail_components)),
            "state_today": int(q_today),
            "forecast_state_probabilities": [float(p) for p in state_p],
        })
    diagnostics = {
        "training_q_state_occupancy": occupancy,
        "training_q_transition_counts": transition_counts,
        "matured_target_future_q_counts": future_q_counts,
        "state_conditional_log_rv7": {
            str(state): {"location": state_densities[state][0], "student_t_scale": state_densities[state][1]}
            for state in STATES
        },
        "transition_cutoff": latest_fit_prediction.isoformat(),
    }
    return predictions, diagnostics


def _score_rows(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0, "mean_log_density_gain": None, "tail_brier_discrete": None,
                "tail_brier_continuous": None}
    difference = [r["discrete_logpdf"] - r["continuous_logpdf"] for r in rows]
    discrete_tail = binary_probability_scores(
        [r["tail_event"] for r in rows], [r["discrete_tail_probability"] for r in rows])
    continuous_tail = binary_probability_scores(
        [r["tail_event"] for r in rows], [r["continuous_tail_probability"] for r in rows])
    return {
        "n": len(rows), "n_dates": len({r["date"] for r in rows}),
        "mean_log_density_discrete": float(np.mean([r["discrete_logpdf"] for r in rows])),
        "mean_log_density_continuous": float(np.mean([r["continuous_logpdf"] for r in rows])),
        "mean_log_density_gain": float(np.mean(difference)),
        "tail_brier_discrete": discrete_tail["brier"],
        "tail_brier_continuous": continuous_tail["brier"],
        "tail_probability_metrics": {"discrete": discrete_tail, "continuous": continuous_tail},
    }


def _grouped(rows: list[dict], key: str) -> dict:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(str(row[key]), []).append(row)
    return {name: _score_rows(group) for name, group in sorted(groups.items())}


def run_h7(staging: Path, out_dir: Path, *, run_url: str | None = None) -> dict:
    """Run the frozen discrete-vs-heavy-tail comparison on canonical DEV tape."""
    from experiments.erf01.pipeline import DAYS, FOLDS, M1_NAMES, M2_NAMES, SEAL, SYMS
    from experiments.erf01.tape_adapter import load_development
    from kepler.intelligence.features import make_panel

    root = Path(__file__).resolve().parents[2]
    protocol_path = root / "reports" / "pmi_h7_protocol.md"
    if hashlib.sha256(protocol_path.read_bytes()).hexdigest() != PROTOCOL_FILE_SHA256:
        raise RuntimeError("H7 protocol differs from its frozen protocol commit")
    if SEAL != date(2026, 4, 1):
        raise RuntimeError("pipeline seal does not match H7 protocol")
    if out_dir.exists():
        raise FileExistsError(f"experiment output already exists: {out_dir}")
    started = time.monotonic()
    prices, _, _, qc_metadata, acquisition = load_development(staging, SYMS, DAYS[0], DAYS[1], SEAL)
    seal_time = datetime.combine(SEAL, datetime.min.time(), UTC)
    prices_preseal = {s: {d: row for d, row in prices[s].items()
                          if datetime.combine(d + timedelta(days=1), datetime.min.time(), UTC) < seal_time}
                      for s in SYMS}
    days, panel = make_panel(prices_preseal, {s: [] for s in SYMS}, symbols=SYMS,
                             day_bounds=DAYS, m1_names=M1_NAMES, m2_names=M2_NAMES)
    q_by_symbol = {}
    for symbol in SYMS:
        q_by_symbol[symbol] = {day: int(panel[symbol]["q"][i]) for i, day in enumerate(days)
                                if np.isfinite(panel[symbol]["q"][i])}
    prepared_rows = {s: _target_rows(s, prices[s], seal=seal_time) for s in SYMS}
    all_predictions = []
    fold_status = {}
    for fold_start, fold_end, fold_name in FOLDS:
        fold_rows = []
        symbol_status = {}
        for symbol in SYMS:
            rows = prepared_rows[symbol]
            q = q_by_symbol[symbol]
            start, end = (datetime.combine(fold_start, datetime.min.time(), UTC),
                          datetime.combine(fold_end, datetime.min.time(), UTC))
            split = temporal_split([r[0] for r in rows], start, end)
            feature_ok = lambda r: all(name in r[1] and np.isfinite(r[1][name]) for name in FEATURES)
            outer_train = [r for r in rows if r[0] in split.train and feature_ok(r)]
            outer_test = [r for r in rows if r[0] in split.test and feature_ok(r)]
            outer_test = [r for r in outer_test
                          if (r[0].prediction_at.date() - timedelta(days=1)) in q]
            if len(outer_train) < 100 or len(outer_test) < 1:
                symbol_status[symbol] = {"status": "NOT_RUN", "reason": "insufficient_observed_rows",
                                         "train": len(outer_train), "test": len(outer_test),
                                         "unknown_train": split.unknown_train,
                                         "unknown_test": split.unknown_test}
                continue
            cal_start_index = int(math.floor(.8 * len(outer_train)))
            calibration_start = outer_train[cal_start_index][0].prediction_at
            calibration = outer_train[cal_start_index:]
            fit = [r for r in outer_train[:cal_start_index]
                   if r[0].label_end < calibration_start]
            if len(fit) < 60:
                symbol_status[symbol] = {"status": "NOT_RUN", "reason": "insufficient_matured_fit_rows",
                                         "fit": len(fit), "calibration": len(calibration),
                                         "test": len(outer_test), "unknown_test": split.unknown_test}
                continue
            threshold = fit_quantile_threshold([r[0] for r in fit], .75,
                                               matured_before=calibration_start)
            qtest = [(r[0], r[1], q[r[0].prediction_at.date() - timedelta(days=1)])
                     for r in outer_test]
            try:
                rows_out, model_diagnostics = _candidate_predictions(fit, qtest, q, threshold)
            except (ValueError, ArithmeticError, np.linalg.LinAlgError) as exc:
                symbol_status[symbol] = {"status": "NOT_RUN", "reason": str(exc),
                                         "fit": len(fit), "calibration": len(calibration),
                                         "test": len(qtest), "unknown_test": split.unknown_test}
                continue
            for prediction, (target, _feature, _q) in zip(rows_out, qtest):
                prediction.update({"fold": fold_name, "threshold_rv7_q75_fit_only": threshold,
                                   "tail_event": int(float(target.value) >= threshold)})
            fold_rows.extend(rows_out)
            symbol_status[symbol] = {"status": "TESTED", "fit": len(fit),
                                     "calibration_reserved": len(calibration),
                                     "test": len(rows_out), "threshold_rv7_q75_fit_only": threshold,
                                     "unknown_train": split.unknown_train,
                                     "unknown_test": split.unknown_test,
                                     **model_diagnostics}
        all_predictions.extend(fold_rows)
        fold_status[fold_name] = {"symbols": symbol_status, "matched_rows": len(fold_rows),
                                  "symbols_tested": sum(v["status"] == "TESTED" for v in symbol_status.values())}
    if not all_predictions:
        raise RuntimeError("no matched finite H7 density forecasts were produced")
    primary = _score_rows(all_predictions)
    difference = [(r["date"], r["discrete_logpdf"] - r["continuous_logpdf"])
                  for r in all_predictions]
    interval = paired_date_block_interval(difference, block_days=28,
                                          replicates=2000, seed=EXPERIMENT_SEED)
    tested_folds = {r["fold"] for r in all_predictions}
    if len(tested_folds) < 2 or interval["p025"] is None:
        decision = "INCONCLUSIVE"
    elif primary["mean_log_density_gain"] >= .01 and interval["p025"] > 0:
        decision = "SUPPORTED_ON_SEEN_DEV"
    elif (interval["p025"] <= 0 and interval["p975"] is not None
          and interval["p975"] >= .01):
        decision = "INCONCLUSIVE"
    else:
        decision = "NOT_SUPPORTED_ON_SEEN_DEV"
    tail_conflict = primary["tail_brier_discrete"] - primary["tail_brier_continuous"] > .01
    code_paths = [Path(__file__), Path(__file__).with_name("h1.py"),
                  root / "kepler/intelligence/validation.py", root / "kepler/intelligence/metrics_v2.py",
                  root / "kepler/intelligence/features.py", root / "experiments/erf01/tape_adapter.py"]
    code_hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in code_paths}
    data_hashes = {f"{r['symbol']}/{r['kind']}": r["sha256"] for r in acquisition["records"]}
    config = {"experiment": "PMI-H7", "primary_horizon_days": 7, "df": DF,
              "pseudo_observations": PSEUDO_OBSERVATIONS, "transition_prior": "add_one",
              "symbols": list(SYMS), "folds": [{"start": a.isoformat(), "end": b.isoformat(), "name": n}
                                                  for a, b, n in FOLDS],
              "event_quantile": .75, "inner_fit_fraction": .8,
              "bootstrap_block_days": 28, "bootstrap_replicates": 2000,
              "bootstrap_seed": EXPERIMENT_SEED, "canonical_seal_exclusive": SEAL.isoformat()}
    receipt = deterministic_receipt(protocol_sha=PROTOCOL_SHA, code_sha256=code_hashes,
                                    data_sha256=data_hashes, config=config, seed=EXPERIMENT_SEED,
                                    run_url=run_url, science_status="EXPLORATORY")
    qc_findings = [f for s in SYMS for f in qc_metadata[s]["qc_findings"]]
    result = {
        "experiment": "PMI-H7", "status": "EXPLORATORY",
        "decision_rule_result": decision,
        "tail_brier_conflict_over_0_01": tail_conflict,
        "interpretation": "Seen-development evaluation only; discrete state is a predictor, not economic ground truth.",
        "primary": {**primary, "minimum_mean_density_gain_nats": .01,
                    "paired_date_block_bootstrap": interval, "tested_folds": sorted(tested_folds)},
        "by_fold": _grouped(all_predictions, "fold"),
        "by_year": _grouped([{**r, "year": r["date"][:4]} for r in all_predictions], "year"),
        "by_symbol": _grouped(all_predictions, "symbol"),
        "fold_status": fold_status,
        "n_prediction_rows": len(all_predictions),
        "n_distinct_prediction_dates": len({r["date"] for r in all_predictions}),
        "n_positive_tail_dates": len({r["date"] for r in all_predictions if r["tail_event"] == 1}),
        "source_validation": {"status": "ERROR_FREE_WITH_FINDINGS_PRESERVED",
                              "seal_start": SEAL.isoformat(), "source_file_count": len(acquisition["records"]),
                              "source_bytes": acquisition["source_bytes"],
                              "qc_severity_counts": {sev: sum(x["severity"] == sev for x in qc_findings)
                                                     for sev in ("ERROR", "WARN", "INFO")}},
        "receipt": receipt, "runtime_seconds": round(time.monotonic() - started, 3),
    }
    out_dir.mkdir(parents=True)
    (out_dir / "metrics.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    with (out_dir / "predictions.jsonl").open("w", encoding="utf-8") as handle:
        for row in all_predictions:
            handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
    (out_dir / "manifest.json").write_text(json.dumps({
        "experiment": "PMI-H7", "receipt_id": receipt["receipt_id"],
        "protocol_sha": PROTOCOL_SHA, "code_sha256": code_hashes,
        "data_sha256": data_hashes, "configuration": config,
        "run_url": run_url, "runtime_seconds": result["runtime_seconds"],
        "status": result["status"],
    }, indent=2, sort_keys=True) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-url")
    args = parser.parse_args(argv)
    result = run_h7(args.staging, args.out, run_url=args.run_url)
    print("PMI_H7_RESULT=" + json.dumps({
        "status": result["status"], "decision_rule_result": result["decision_rule_result"],
        "rows": result["n_prediction_rows"], "runtime_seconds": result["runtime_seconds"],
        "receipt_id": result["receipt"]["receipt_id"], "primary": result["primary"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
