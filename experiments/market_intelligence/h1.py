"""Frozen PMI-H1 seven-day risk-event evaluation on canonical DEV tape."""
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
    ForecastTarget, daily_close_time, deterministic_receipt, event_labels,
    fit_quantile_threshold, future_realized_risk, temporal_split,
    trailing_log_rv_features, utc,
)

UTC = timezone.utc
PROTOCOL_SHA = "d89003c7c956ff25a3b1602fdffdaf5cb81028c0"
PROTOCOL_FILE_SHA256 = "fa2f9abfd6ea24631b7fe31089290d6fa82547f37effba938d0b8579f85d8708"
SEAL = datetime(2026, 4, 1, tzinfo=UTC)
PRIMARY_HORIZON_DAYS = 7
FEATURE_NAMES = {
    "AR1": ("log_rv7",),
    "HAR": ("log_rv1", "log_rv7", "log_rv30"),
}
MODEL_NAMES = ("prevalence", "last_risk", "AR1", "HAR")


def _fit_ols(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fit OLS with training-only standardization and a retained intercept."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[~np.isfinite(scale) | (scale == 0)] = 1.0
    z = (x - mean) / scale
    design = np.column_stack((np.ones(len(z)), z))
    coef = np.linalg.lstsq(design, y, rcond=None)[0]
    return coef, mean, scale


def _predict_ols(model: tuple[np.ndarray, np.ndarray, np.ndarray], x: np.ndarray) -> np.ndarray:
    coef, mean, scale = model
    return np.column_stack((np.ones(len(x)), (np.asarray(x, float) - mean) / scale)) @ coef


def _fit_platt(log_risk: np.ndarray, outcomes: np.ndarray, l2: float = 1.0) -> np.ndarray:
    """Two-parameter convex Platt fit; fixed L2 on intercept and slope."""
    x = np.column_stack((np.ones(len(log_risk)), np.asarray(log_risk, float)))
    y = np.asarray(outcomes, float)
    if len(np.unique(y)) < 2:
        raise ValueError("Platt calibration needs both event classes")
    theta = np.array([math.log(y.mean() / (1 - y.mean())), 0.0], dtype=float)
    penalty = np.eye(2) * float(l2)
    for _ in range(100):
        z = np.clip(x @ theta, -40, 40)
        p = 1.0 / (1.0 + np.exp(-z))
        grad = x.T @ (p - y) + penalty @ theta
        weight = p * (1 - p)
        hessian = (x.T * weight) @ x + penalty
        step = np.linalg.solve(hessian, grad)
        theta -= step
        if np.max(np.abs(step)) < 1e-9:
            break
    return theta


def _platt_predict(theta: np.ndarray, log_risk: np.ndarray) -> np.ndarray:
    z = np.clip(theta[0] + theta[1] * np.asarray(log_risk, float), -40, 40)
    return np.clip(1.0 / (1.0 + np.exp(-z)), 1e-6, 1 - 1e-6)


def _features_for_symbol(prices: dict[date, tuple], *, seal: datetime) -> dict[date, dict[str, float]]:
    # Daily OHLC rows are keyed by UTC candle opening date; their close is
    # available at the next UTC midnight. Drop the close at/after the seal.
    closes = {d: float(values[3]) for d, values in prices.items()
              if daily_close_time(d) < seal}
    if not closes:
        return {}
    first, last = min(closes), max(closes)
    full_days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    returns = np.full(len(full_days), np.nan, dtype=float)
    for i in range(1, len(full_days)):
        prev, curr = closes.get(full_days[i - 1]), closes.get(full_days[i])
        if prev is not None and curr is not None and prev > 0 and curr > 0:
            returns[i] = math.log(curr / prev)
    out = {}
    for i, day in enumerate(full_days):
        feat = trailing_log_rv_features(returns, i)
        if feat is not None and daily_close_time(day) < seal:
            out[day] = feat
    return out


def _target_rows(
    symbol: str, prices: dict[date, tuple], *, seal: datetime,
) -> list[tuple[ForecastTarget, dict[str, float]]]:
    # The terminal candle close is discarded above if its close instant meets
    # the seal. This keeps feature and label timestamps strictly pre-seal.
    closes = {d: float(values[3]) for d, values in prices.items()
              if daily_close_time(d) < seal}
    days = sorted(closes)
    targets = future_realized_risk(symbol, days, [closes[d] for d in days], PRIMARY_HORIZON_DAYS)
    features = _features_for_symbol(prices, seal=seal)
    out = []
    for target in targets:
        if target.prediction_at >= seal:
            continue
        if target.status == "OBSERVED" and target.label_end >= seal:
            raise RuntimeError("observed target reaches the exclusive development seal")
        day = target.prediction_at.date() - timedelta(days=1)
        out.append((target, features.get(day, {})))
    return out


def _asset_fold(
    rows: list[tuple[ForecastTarget, dict[str, float]]],
    test_start: datetime, test_end: datetime,
) -> tuple[list[dict], dict]:
    """Fit/calibrate one symbol-fold, applying the frozen chronological split."""
    split = temporal_split([r[0] for r in rows], test_start, test_end)
    outer_train_raw = [r for r in rows if r[0] in split.train]
    outer_test_raw = [r for r in rows if r[0] in split.test]
    usable = lambda r: all(name in r[1] and np.isfinite(r[1][name])
                           for name in ("log_rv1", "log_rv7", "log_rv30"))
    outer_train = [r for r in outer_train_raw if usable(r)]
    outer_test = [r for r in outer_test_raw if usable(r)]
    if len(outer_train) < 100 or len(outer_test) < 1:
        return [], {"status": "NOT_RUN", "reason": "insufficient_observed_outer_rows",
                    "train": len(outer_train), "test": len(outer_test), "purged": split.purged,
                    "unknown_train": split.unknown_train, "unknown_test": split.unknown_test,
                    "test_feature_unavailable": len(outer_test_raw) - len(outer_test)}
    split_at = int(math.floor(.8 * len(outer_train)))
    calibration_start = outer_train[split_at][0].prediction_at
    calibration = [r for r in outer_train[split_at:]
                   if all(np.isfinite(list(r[1].values())))]
    fit = [r for r in outer_train[:split_at]
           if r[0].label_end < calibration_start and all(np.isfinite(list(r[1].values())))]
    test = [r for r in outer_test if all(np.isfinite(list(r[1].values())))]
    if len(fit) < 60 or len(calibration) < 30 or not test:
        return [], {"status": "NOT_RUN", "reason": "insufficient_fit_calibration_or_test_rows",
                    "fit": len(fit), "calibration": len(calibration), "test": len(test),
                    "purged": split.purged + len(outer_train[:split_at]) - len(fit),
                    "unknown_train": split.unknown_train, "unknown_test": split.unknown_test,
                    "test_feature_unavailable": len(outer_test_raw) - len(outer_test)}
    threshold = fit_quantile_threshold([r[0] for r in fit], .75,
                                      matured_before=calibration_start)
    y_fit = event_labels([r[0] for r in fit], threshold)
    y_cal = event_labels([r[0] for r in calibration], threshold)
    if len(np.unique(y_cal)) < 2:
        return [], {"status": "NOT_RUN", "reason": "calibration_segment_lacks_both_event_classes",
                    "fit": len(fit), "calibration": len(calibration), "test": len(test),
                    "events_fit": int(y_fit.sum()), "events_calibration": int(y_cal.sum()),
                    "threshold": threshold, "purged": split.purged,
                    "unknown_train": split.unknown_train, "unknown_test": split.unknown_test,
                    "test_feature_unavailable": len(outer_test_raw) - len(outer_test)}

    def matrix(selected, names):
        return np.asarray([[r[1][name] for name in names] for r in selected], dtype=float)

    train_y = np.log(np.maximum([r[0].value for r in fit], 1e-12))
    cal_x = {name: None for name in MODEL_NAMES}
    test_x = {name: None for name in MODEL_NAMES}
    cal_x["last_risk"] = matrix(calibration, ("log_rv7",))[:, 0]
    test_x["last_risk"] = matrix(test, ("log_rv7",))[:, 0]
    models = {}
    for name, cols in FEATURE_NAMES.items():
        fitted = _fit_ols(matrix(fit, cols), train_y)
        models[name] = fitted
        cal_x[name] = _predict_ols(fitted, matrix(calibration, cols))
        test_x[name] = _predict_ols(fitted, matrix(test, cols))
    calibrators = {name: _fit_platt(cal_x[name], y_cal, 1.0)
                   for name in ("last_risk", "AR1", "HAR")}
    fit_prevalence = float(y_fit.mean())
    probs = {"prevalence": np.full(len(test), fit_prevalence)}
    for name, theta in calibrators.items():
        probs[name] = _platt_predict(theta, test_x[name])
    y_test = event_labels([r[0] for r in test], threshold)
    predictions = []
    for i, (target, _) in enumerate(test):
        predictions.append({
            "symbol": target.symbol, "prediction_at": target.prediction_at.isoformat(),
            "date": target.prediction_at.date().isoformat(), "fold": "",
            "truth": int(y_test[i]), "rv7": target.value, "threshold": threshold,
            "probabilities": {name: float(probs[name][i]) for name in MODEL_NAMES},
        })
    return predictions, {
        "status": "TESTED", "fit": len(fit), "calibration": len(calibration),
        "test": len(test), "purged_outer": split.purged,
        "purged_inner": int(len(outer_train[:split_at]) - len(fit)),
        "threshold_rv7_q75_fit_only": threshold,
        "events_fit": int(y_fit.sum()), "events_calibration": int(y_cal.sum()),
        "events_test": int(y_test.sum()), "calibration_both_classes": True,
        "unknown_train": split.unknown_train, "unknown_test": split.unknown_test,
        "test_feature_unavailable": len(outer_test_raw) - len(outer_test),
    }


def _group_scores(records: list[dict], group_key: str) -> dict:
    groups: dict[str, list[dict]] = {}
    for row in records:
        groups.setdefault(str(row[group_key]), []).append(row)
    result = {}
    for key, rows in sorted(groups.items()):
        result[key] = {name: binary_probability_scores(
            [r["truth"] for r in rows], [r["probabilities"][name] for r in rows])
            for name in MODEL_NAMES}
        result[key]["support"] = {
            "n_distinct_prediction_dates": len({r["date"] for r in rows}),
            "n_positive_event_dates": len({r["date"] for r in rows if r["truth"] == 1}),
        }
    return result


def run_h1(staging: Path, out_dir: Path, *, run_url: str | None = None) -> dict:
    """Load verified canonical DEV inputs and run the frozen H1 outer folds."""
    from experiments.erf01.pipeline import DAYS, FOLDS, SEAL, SYMS
    from experiments.erf01.tape_adapter import load_development

    protocol_file = Path(__file__).resolve().parents[2] / "reports" / "pmi_h1_protocol.md"
    # Modal images exclude .git; the source commit is checked in the Actions
    # preflight and the vendored protocol content is hash-checked here.
    current_hash = hashlib.sha256(protocol_file.read_bytes()).hexdigest()
    if current_hash != PROTOCOL_FILE_SHA256:
        raise RuntimeError("H1 protocol differs from its frozen protocol commit")
    if SEAL != date(2026, 4, 1):
        raise RuntimeError("pipeline seal does not match H1 protocol")
    if out_dir.exists():
        raise FileExistsError(f"experiment output already exists: {out_dir}")
    start_clock = time.monotonic()
    prices, _, _, qc_metadata, acquisition = load_development(
        staging, SYMS, DAYS[0], DAYS[1], SEAL)
    seal_time = datetime.combine(SEAL, datetime.min.time(), UTC)
    prepared_rows = {symbol: _target_rows(symbol, prices[symbol], seal=seal_time)
                     for symbol in SYMS}
    all_predictions: list[dict] = []
    fold_status: dict[str, dict] = {}
    for fold_start, fold_end, fold_name in FOLDS:
        fold_records = []
        fold_symbols = {}
        for symbol in SYMS:
            records, info = _asset_fold(
                prepared_rows[symbol], datetime.combine(fold_start, datetime.min.time(), UTC),
                datetime.combine(fold_end, datetime.min.time(), UTC))
            fold_symbols[symbol] = info
            for r in records:
                r["fold"] = fold_name
            fold_records.extend(records)
        # Protocol requires a shared four-model matched-date set.
        all_predictions.extend(fold_records)
        fold_status[fold_name] = {"symbols": fold_symbols,
                                  "matched_rows": len(fold_records),
                                  "symbols_tested": sum(x["status"] == "TESTED" for x in fold_symbols.values())}

    if not all_predictions:
        raise RuntimeError("no complete H1 folds produced scored predictions")
    scores = {name: binary_probability_scores(
        [r["truth"] for r in all_predictions], [r["probabilities"][name] for r in all_predictions])
        for name in MODEL_NAMES}
    paired = [(r["date"], (r["probabilities"]["last_risk"] - r["truth"]) ** 2 -
               (r["probabilities"]["HAR"] - r["truth"]) ** 2) for r in all_predictions]
    interval = paired_date_block_interval(paired, block_days=28, replicates=2000, seed=20261016)
    positive_folds = {r["fold"] for r in all_predictions if r["truth"] == 1}
    relative_brier_improvement = (
        (scores["last_risk"]["brier"] - scores["HAR"]["brier"]) / scores["last_risk"]["brier"]
        if scores["last_risk"]["brier"] > 0 else None)
    if len(positive_folds) < 2 or interval["p025"] is None:
        decision = "INCONCLUSIVE"
    elif (relative_brier_improvement is not None and relative_brier_improvement >= .01
          and interval["p025"] > 0):
        decision = "SUPPORTED_ON_SEEN_DEV"
    elif (interval["p025"] <= 0 and interval["p975"] is not None
          and interval["p975"] >= .01):
        decision = "INCONCLUSIVE"
    else:
        decision = "NOT_SUPPORTED_ON_SEEN_DEV"
    code_paths = [Path(__file__), Path(__file__).parents[2] / "kepler/intelligence/validation.py",
                  Path(__file__).parents[2] / "kepler/intelligence/metrics_v2.py",
                  Path(__file__).parents[1] / "erf01/tape_adapter.py"]
    code_hashes = {str(p.relative_to(Path(__file__).parents[2])): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in code_paths}
    data_hashes = {f"{r['symbol']}/{r['kind']}": r["sha256"] for r in acquisition["records"]}
    config = {
        "experiment": "PMI-H1", "primary_horizon_days": 7,
        "symbols": list(SYMS), "folds": [{"start": a.isoformat(), "end": b.isoformat(), "name": n}
                                           for a, b, n in FOLDS],
        "event_quantile": .75, "inner_fit_fraction": .8, "platt_l2": 1.0,
        "bootstrap_block_days": 28, "bootstrap_replicates": 2000, "bootstrap_seed": 20261016,
        "canonical_seal_exclusive": SEAL.isoformat(),
    }
    receipt = deterministic_receipt(protocol_sha=PROTOCOL_SHA, code_sha256=code_hashes,
                                    data_sha256=data_hashes, config=config, seed=20261016,
                                    run_url=run_url, science_status="EXPLORATORY")
    qc_findings = [finding for symbol in SYMS for finding in qc_metadata[symbol]["qc_findings"]]
    qc_counts = {severity: sum(f["severity"] == severity for f in qc_findings)
                 for severity in ("ERROR", "WARN", "INFO")}
    result = {
        "experiment": "PMI-H1", "status": "EXPLORATORY",
        "decision_rule_result": decision,
        "interpretation": "Seen-development evaluation only; no independent or prospective validation.",
        "primary": {"target": "training-only q75 of future RV7", "horizon_days": 7,
                    "comparator": "calibrated last-risk persistence", "candidate": "calibrated HAR",
                    "minimum_relative_brier_improvement": .01,
                    "relative_brier_improvement": relative_brier_improvement,
                    "paired_date_block_bootstrap": interval,
                    "positive_event_folds": sorted(positive_folds)},
        "scores": scores,
        "by_fold": _group_scores(all_predictions, "fold"),
        "by_year": _group_scores([{**r, "year": r["date"][:4]} for r in all_predictions], "year"),
        "by_symbol": _group_scores(all_predictions, "symbol"),
        "fold_status": fold_status,
        "n_prediction_rows": len(all_predictions),
        "n_distinct_prediction_dates": len({r["date"] for r in all_predictions}),
        "n_positive_event_dates": len({r["date"] for r in all_predictions if r["truth"] == 1}),
        "source_validation": {"status": "ERROR_FREE_WITH_FINDINGS_PRESERVED", "seal_start": SEAL.isoformat(),
                              "source_file_count": len(acquisition["records"]),
                              "source_bytes": acquisition["source_bytes"],
                              "symbols": SYMS, "qc_severity_counts": qc_counts,
                              "per_symbol": qc_metadata},
        "receipt": receipt,
        "runtime_seconds": None,
    }
    result["runtime_seconds"] = round(time.monotonic() - start_clock, 3)
    out_dir.mkdir(parents=True)
    (out_dir / "metrics.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    with (out_dir / "predictions.jsonl").open("w", encoding="utf-8") as handle:
        for record in all_predictions:
            handle.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
    (out_dir / "manifest.json").write_text(json.dumps({
        "experiment": "PMI-H1", "receipt_id": receipt["receipt_id"],
        "protocol_sha": PROTOCOL_SHA, "code_sha256": code_hashes,
        "data_sha256": data_hashes, "configuration": config,
        "run_url": run_url, "runtime_seconds": result["runtime_seconds"],
    }, indent=2, sort_keys=True) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-url")
    args = parser.parse_args(argv)
    result = run_h1(args.staging, args.out, run_url=args.run_url)
    print("PMI_H1_RESULT=" + json.dumps({
        "status": result["status"], "decision_rule_result": result["decision_rule_result"],
        "rows": result["n_prediction_rows"], "runtime_seconds": result["runtime_seconds"],
        "receipt_id": result["receipt"]["receipt_id"],
        "scores": {k: {"brier": v["brier"], "log_loss": v["log_loss"]}
                   for k, v in result["scores"].items()},
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
