"""Frozen PMI-H4 funding-only conditional H7 risk-event ablation."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np

from experiments.market_intelligence.h1 import (
    _fit_ols, _fit_platt, _platt_predict, _predict_ols, _target_rows,
)
from kepler.intelligence.metrics_v2 import binary_probability_scores, paired_date_block_interval
from kepler.intelligence.validation import (
    deterministic_receipt, event_labels, fit_quantile_threshold, temporal_split,
)

UTC = timezone.utc
PROTOCOL_SHA = "d83a085c00688d30a4942e80a8888ea6656064be"
PROTOCOL_FILE_SHA256 = "1bafbc944ff42321b2eec4df3d1b079e92311ce6f64ea3c0e41dcfbeada3c029"
PRIMARY_HORIZON_DAYS = 7
EVENT_QUANTILE = 0.75
MINIMUM_RELATIVE_BRIER_REDUCTION = 0.01
MINIMUM_ABSOLUTE_CANDIDATE_CALIBRATION = 0.05
MINIMUM_POSITIVE_EVENT_DATES = 10
BOOTSTRAP_BLOCK_DAYS = 28
BOOTSTRAP_REPLICATES = 2000
EXPERIMENT_SEED = 20261016
PRICE_FEATURES = ("log_rv1", "log_rv7", "log_rv30")
FUNDING_FEATURE = "funding_stress90"
MODEL_NAMES = ("har", "har_plus_funding")


def _complete(row: tuple, *, with_funding: bool = True) -> bool:
    names = PRICE_FEATURES + ((FUNDING_FEATURE,) if with_funding else ())
    return all(name in row[1] and np.isfinite(row[1][name]) for name in names)


def _design(rows: list[tuple], *, with_funding: bool) -> np.ndarray:
    names = PRICE_FEATURES + ((FUNDING_FEATURE,) if with_funding else ())
    return np.asarray([[row[1][name] for name in names] for row in rows], dtype=float)


def _asset_fold_funding(
    rows: list[tuple], test_start: datetime, test_end: datetime, *, symbol: str, fold: str,
) -> tuple[list[dict], dict]:
    """Fit both fixed candidates on the identical funding-complete cohort."""
    split = temporal_split([row[0] for row in rows], test_start, test_end)
    price_ready_train = [row for row in rows if row[0] in split.train and _complete(row, with_funding=False)]
    price_ready_test = [row for row in rows if row[0] in split.test and _complete(row, with_funding=False)]
    train = [row for row in price_ready_train if _complete(row)]
    test = [row for row in price_ready_test if _complete(row)]
    coverage = {
        "price_ready_train": len(price_ready_train), "matched_funding_train": len(train),
        "price_ready_test": len(price_ready_test), "matched_funding_test": len(test),
        "test_funding_coverage": len(test) / len(price_ready_test) if price_ready_test else None,
        "unknown_train": split.unknown_train, "unknown_test": split.unknown_test,
        "purged_outer": split.purged,
    }
    if len(train) < 100 or not test:
        return [], {"status": "NOT_RUN", "reason": "insufficient_matched_price_funding_rows",
                    "fit_rows": len(train), "test_rows": len(test), **coverage}

    split_at = int(math.floor(.8 * len(train)))
    calibration_start = train[split_at][0].prediction_at
    calibration = train[split_at:]
    fit = [row for row in train[:split_at] if row[0].label_end < calibration_start]
    test = [row for row in test if _complete(row)]
    if len(fit) < 60 or len(calibration) < 30 or not test:
        return [], {"status": "NOT_RUN", "reason": "insufficient_fit_calibration_or_test_rows",
                    "fit_rows": len(fit), "calibration_rows": len(calibration),
                    "test_rows": len(test), **coverage}

    threshold = fit_quantile_threshold([row[0] for row in fit], EVENT_QUANTILE,
                                       matured_before=calibration_start)
    y_fit = event_labels([row[0] for row in fit], threshold)
    y_cal = event_labels([row[0] for row in calibration], threshold)
    if len(np.unique(y_cal)) < 2:
        return [], {"status": "NOT_RUN", "reason": "calibration_segment_lacks_both_event_classes",
                    "fit_rows": len(fit), "calibration_rows": len(calibration),
                    "threshold_rv7_q75_fit_only": threshold, **coverage}

    y_fit_log_rv = np.log(np.maximum([float(row[0].value) for row in fit], 1e-12))
    baseline_model = _fit_ols(_design(fit, with_funding=False), y_fit_log_rv)
    funding_model = _fit_ols(_design(fit, with_funding=True), y_fit_log_rv)
    cal_x = {
        "har": _predict_ols(baseline_model, _design(calibration, with_funding=False)),
        "har_plus_funding": _predict_ols(funding_model, _design(calibration, with_funding=True)),
    }
    test_x = {
        "har": _predict_ols(baseline_model, _design(test, with_funding=False)),
        "har_plus_funding": _predict_ols(funding_model, _design(test, with_funding=True)),
    }
    calibrators = {name: _fit_platt(cal_x[name], y_cal, l2=1.0) for name in MODEL_NAMES}
    probabilities = {name: _platt_predict(calibrators[name], test_x[name]) for name in MODEL_NAMES}
    y_test = event_labels([row[0] for row in test], threshold)
    predictions = []
    for index, (target, features) in enumerate(test):
        predictions.append({
            "symbol": symbol, "fold": fold, "date": target.prediction_at.date().isoformat(),
            "prediction_at": target.prediction_at.isoformat(),
            "label_start": target.label_start.isoformat(), "label_end": target.label_end.isoformat(),
            "truth": int(y_test[index]), "rv7": target.value, "event_threshold_fit_only": threshold,
            "funding_stress90": float(features[FUNDING_FEATURE]),
            "probabilities": {name: float(probabilities[name][index]) for name in MODEL_NAMES},
        })
    return predictions, {
        "status": "TESTED", "fit_rows": len(fit), "calibration_rows": len(calibration),
        "test_rows": len(test), "threshold_rv7_q75_fit_only": threshold,
        "positive_fit": int(y_fit.sum()), "positive_calibration": int(y_cal.sum()),
        "positive_test": int(y_test.sum()), "positive_test_dates": len({
            row["date"] for row in predictions if row["truth"] == 1}),
        "feature_count": {"har": len(PRICE_FEATURES) + 1, "har_plus_funding": len(PRICE_FEATURES) + 2},
        **coverage,
    }


def _score_rows(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0, "brier": {name: None for name in MODEL_NAMES},
                "log_loss": {name: None for name in MODEL_NAMES}}
    scores = {name: binary_probability_scores(
        [row["truth"] for row in rows], [row["probabilities"][name] for row in rows])
        for name in MODEL_NAMES}
    baseline_brier = scores["har"]["brier"]
    candidate_brier = scores["har_plus_funding"]["brier"]
    return {"n": len(rows), "n_dates": len({row["date"] for row in rows}),
            "n_positive_event_dates": len({row["date"] for row in rows if row["truth"] == 1}),
            "brier": {name: scores[name]["brier"] for name in MODEL_NAMES},
            "log_loss": {name: scores[name]["log_loss"] for name in MODEL_NAMES},
            "calibration_in_the_large": {name: scores[name]["calibration_in_the_large"]
                                         for name in MODEL_NAMES},
            "reliability": {name: scores[name]["reliability"] for name in MODEL_NAMES},
            "precision_at_0_5": {name: scores[name]["precision_at_0_5"] for name in MODEL_NAMES},
            "recall_at_0_5": {name: scores[name]["recall_at_0_5"] for name in MODEL_NAMES},
            "absolute_brier_reduction": baseline_brier - candidate_brier,
            "relative_brier_reduction": ((baseline_brier - candidate_brier) / baseline_brier
                                         if baseline_brier > 0 else None)}


def _group_scores(rows: list[dict], key: str) -> dict:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(str(row[key]), []).append(row)
    return {value: _score_rows(group) for value, group in sorted(groups.items())}


def _write_result(out_dir: Path, result: dict, predictions: list[dict], manifest: dict) -> dict:
    out_dir.mkdir(parents=True)
    (out_dir / "metrics.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    with (out_dir / "predictions.jsonl").open("w", encoding="utf-8") as handle:
        for row in predictions:
            handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return result


def run_h4(staging: Path, out_dir: Path, *, run_url: str | None = None) -> dict:
    """Run the fixed funding-only H4 comparison on canonical pre-seal DEV data."""
    from experiments.erf01.pipeline import DAYS, FOLDS, M1_NAMES, M2_NAMES, SEAL, SYMS
    from experiments.erf01.tape_adapter import load_development
    from kepler.intelligence.features import make_panel

    root = Path(__file__).resolve().parents[2]
    protocol_path = root / "reports" / "pmi_h4_protocol.md"
    if hashlib.sha256(protocol_path.read_bytes()).hexdigest() != PROTOCOL_FILE_SHA256:
        raise RuntimeError("H4 protocol differs from its frozen protocol commit")
    if SEAL != date(2026, 4, 1):
        raise RuntimeError("pipeline seal does not match H4 protocol")
    if out_dir.exists():
        raise FileExistsError(f"experiment output already exists: {out_dir}")
    started = time.monotonic()
    try:
        prices, funding, _, qc_metadata, acquisition = load_development(
            staging, SYMS, DAYS[0], DAYS[1], SEAL)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        elapsed = round(time.monotonic() - started, 3)
        code_paths = [Path(__file__), root / "kepler/intelligence/validation.py",
                      root / "kepler/intelligence/features.py", root / "kepler/intelligence/metrics_v2.py"]
        code_hashes = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in code_paths}
        config = {"experiment": "PMI-H4-funding-only", "primary_horizon_days": PRIMARY_HORIZON_DAYS,
                  "status": "DATA_BLOCKED", "reason": str(exc), "canonical_seal_exclusive": SEAL.isoformat()}
        receipt = deterministic_receipt(protocol_sha=PROTOCOL_SHA, code_sha256=code_hashes,
                                        data_sha256={}, config=config, seed=EXPERIMENT_SEED,
                                        run_url=run_url, science_status="DATA_BLOCKED")
        result = {"experiment": "PMI-H4-funding-only", "status": "DATA_BLOCKED",
                  "decision_rule_result": "DATA_BLOCKED", "blocker": str(exc),
                  "receipt": receipt, "runtime_seconds": elapsed, "n_prediction_rows": 0}
        manifest = {"experiment": "PMI-H4-funding-only", "protocol_sha": PROTOCOL_SHA,
                    "code_sha256": code_hashes, "data_sha256": {}, "configuration": config,
                    "run_url": run_url, "status": result["status"], "runtime_seconds": elapsed}
        return _write_result(out_dir, result, [], manifest)

    seal_time = datetime.combine(SEAL, datetime.min.time(), UTC)
    preseal_prices = {symbol: {day: row for day, row in prices[symbol].items()
                               if datetime.combine(day + timedelta(days=1), datetime.min.time(), UTC) < seal_time}
                      for symbol in SYMS}
    days, panel = make_panel(preseal_prices, funding, symbols=SYMS, day_bounds=DAYS,
                             m1_names=M1_NAMES, m2_names=M2_NAMES)
    funding_by_symbol = {symbol: {
        day: float(panel[symbol][FUNDING_FEATURE][index])
        for index, day in enumerate(days) if np.isfinite(panel[symbol][FUNDING_FEATURE][index])
    } for symbol in SYMS}
    prepared = {}
    for symbol in SYMS:
        prepared[symbol] = [(target, {**features, FUNDING_FEATURE: funding_by_symbol[symbol].get(
            target.prediction_at.date() - timedelta(days=1), math.nan)})
            for target, features in _target_rows(symbol, prices[symbol], seal=seal_time)]
    predictions: list[dict] = []
    fold_status = {}
    for fold_start, fold_end, fold_name in FOLDS:
        start = datetime.combine(fold_start, datetime.min.time(), UTC)
        end = datetime.combine(fold_end, datetime.min.time(), UTC)
        fold_rows, symbol_status = [], {}
        for symbol in SYMS:
            rows, info = _asset_fold_funding(prepared[symbol], start, end,
                                             symbol=symbol, fold=fold_name)
            symbol_status[symbol] = info
            fold_rows.extend(rows)
        predictions.extend(fold_rows)
        fold_status[fold_name] = {"symbols": symbol_status, "matched_rows": len(fold_rows),
                                  "symbols_tested": sum(x["status"] == "TESTED" for x in symbol_status.values())}

    if not predictions:
        statuses = [info for fold in fold_status.values() for info in fold["symbols"].values()]
        has_price_test_rows = any(info.get("price_ready_test", 0) > 0 for info in statuses)
        has_matched_funding_test_rows = any(info.get("matched_funding_test", 0) > 0 for info in statuses)
        status = ("DATA_BLOCKED" if has_price_test_rows and not has_matched_funding_test_rows
                  else "INCONCLUSIVE")
        decision = status
        primary, interval = _score_rows([]), {"n_dates": 0, "mean": None, "p025": None, "p975": None,
                                               "replicates": 0, "block_days": BOOTSTRAP_BLOCK_DAYS,
                                               "seed": EXPERIMENT_SEED}
    else:
        status = "EXPLORATORY"
        primary = _score_rows(predictions)
        paired = [(row["date"], (row["probabilities"]["har"] - row["truth"]) ** 2
                   - (row["probabilities"]["har_plus_funding"] - row["truth"]) ** 2)
                  for row in predictions]
        interval = paired_date_block_interval(paired, block_days=BOOTSTRAP_BLOCK_DAYS,
                                              replicates=BOOTSTRAP_REPLICATES, seed=EXPERIMENT_SEED)
        event_dates = primary["n_positive_event_dates"]
        positive_folds = len({row["fold"] for row in predictions if row["truth"] == 1})
        cal_in_large = abs(primary["calibration_in_the_large"]["har_plus_funding"])
        enough_support = event_dates >= MINIMUM_POSITIVE_EVENT_DATES and positive_folds >= 2
        effect = primary["relative_brier_reduction"]
        if not enough_support or interval["p025"] is None:
            decision = "INCONCLUSIVE"
        elif (effect is not None and effect >= MINIMUM_RELATIVE_BRIER_REDUCTION
              and interval["p025"] > 0 and cal_in_large <= MINIMUM_ABSOLUTE_CANDIDATE_CALIBRATION):
            decision = "SUPPORTED_ON_SEEN_DEV"
        elif interval["p025"] <= 0 and interval["p975"] is not None:
            decision = "INCONCLUSIVE"
        else:
            decision = "NOT_SUPPORTED_ON_SEEN_DEV"

    code_paths = [Path(__file__), Path(__file__).with_name("h1.py"),
                  root / "kepler/intelligence/validation.py", root / "kepler/intelligence/features.py",
                  root / "kepler/intelligence/metrics_v2.py", root / "experiments/erf01/tape_adapter.py"]
    code_hashes = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in code_paths}
    data_hashes = {f"{record['symbol']}/{record['kind']}": record["sha256"]
                   for record in acquisition["records"]}
    config = {"experiment": "PMI-H4-funding-only", "target": "future_RV7_q75_fit_only",
              "primary_horizon_days": PRIMARY_HORIZON_DAYS, "event_quantile": EVENT_QUANTILE,
              "models": list(MODEL_NAMES), "funding_feature": FUNDING_FEATURE,
              "funding_units": "8h_equivalent", "funding_available_at": "source_settlement_timestamp",
              "inner_fit_fraction": 0.8, "platt_l2": 1.0,
              "minimum_relative_brier_reduction": MINIMUM_RELATIVE_BRIER_REDUCTION,
              "minimum_candidate_abs_calibration_in_the_large": MINIMUM_ABSOLUTE_CANDIDATE_CALIBRATION,
              "minimum_positive_test_dates": MINIMUM_POSITIVE_EVENT_DATES,
              "bootstrap_block_days": BOOTSTRAP_BLOCK_DAYS,
              "bootstrap_replicates": BOOTSTRAP_REPLICATES, "bootstrap_seed": EXPERIMENT_SEED,
              "symbols": list(SYMS), "folds": [{"start": a.isoformat(), "end": b.isoformat(), "name": n}
                                                    for a, b, n in FOLDS],
              "canonical_seal_exclusive": SEAL.isoformat()}
    receipt = deterministic_receipt(protocol_sha=PROTOCOL_SHA, code_sha256=code_hashes,
                                    data_sha256=data_hashes, config=config, seed=EXPERIMENT_SEED,
                                    run_url=run_url, science_status=status)
    qc_findings = [finding for symbol in SYMS for finding in qc_metadata[symbol]["qc_findings"]]
    result = {"experiment": "PMI-H4-funding-only", "status": status,
              "decision_rule_result": decision,
              "interpretation": "Funding-only conditional risk ablation on previously examined DEV; not a global derivatives or independent-validation result.",
              "primary": {**primary, "minimum_relative_brier_reduction": MINIMUM_RELATIVE_BRIER_REDUCTION,
                          "paired_date_block_bootstrap": interval,
                          "tested_folds": sorted({row["fold"] for row in predictions})},
              "by_fold": _group_scores(predictions, "fold"),
              "by_year": _group_scores([{**row, "year": row["date"][:4]} for row in predictions], "year"),
              "by_symbol": _group_scores(predictions, "symbol"),
              "fold_status": fold_status, "n_prediction_rows": len(predictions),
              "funding_source_inventory": {"normalized_units": "8h_equivalent",
                                           "input_funding_rows": {s: len(funding[s]) for s in SYMS},
                                           "funding_feature_days": {s: len(funding_by_symbol[s]) for s in SYMS},
                                           "funding_feature_coverage": {
                                               s: len(funding_by_symbol[s]) / len(days) for s in SYMS},
                                           "oi": "NOT_VERIFIED", "spot_futures_basis": "NOT_VERIFIED",
                                           "liquidation_event_archive": "NOT_VERIFIED",
                                           "cross_exchange_provenance": "NOT_VERIFIED"},
              "source_validation": {"status": "ERROR_FREE_WITH_FINDINGS_PRESERVED",
                                    "seal_start": SEAL.isoformat(), "source_file_count": len(acquisition["records"]),
                                    "source_bytes": acquisition["source_bytes"],
                                    "qc_severity_counts": {severity: sum(f["severity"] == severity for f in qc_findings)
                                                           for severity in ("ERROR", "WARN", "INFO")}},
              "receipt": receipt, "runtime_seconds": round(time.monotonic() - started, 3)}
    manifest = {"experiment": result["experiment"], "receipt_id": receipt["receipt_id"],
                "protocol_sha": PROTOCOL_SHA, "code_sha256": code_hashes, "data_sha256": data_hashes,
                "configuration": config, "run_url": run_url, "status": status,
                "runtime_seconds": result["runtime_seconds"]}
    return _write_result(out_dir, result, predictions, manifest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-url")
    args = parser.parse_args(argv)
    result = run_h4(args.staging, args.out, run_url=args.run_url)
    print("PMI_H4_RESULT=" + json.dumps({"status": result["status"],
                                        "decision_rule_result": result["decision_rule_result"],
                                        "rows": result["n_prediction_rows"],
                                        "runtime_seconds": result["runtime_seconds"],
                                        "receipt_id": result["receipt"]["receipt_id"],
                                        "primary": result.get("primary")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
