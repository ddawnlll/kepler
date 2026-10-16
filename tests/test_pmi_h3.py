"""Synthetic known-answer and leakage checks for the frozen H3 benchmark."""
from datetime import date, datetime, timedelta, timezone
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import numpy as np

from experiments.market_intelligence.h3 import (
    _density_summary,
    _fast_high_threshold,
    _fit_density_candidates,
    _fit_fold_symbol,
    _group_scores,
    _model_complexity,
    _score_predictions,
    run_h3,
)
from kepler.intelligence.features import make_panel
from kepler.intelligence.validation import ForecastTarget, daily_close_time, temporal_split

UTC = timezone.utc


def _synthetic_rows(n=1000):
    first = date(2020, 1, 1)
    rows, q_by_day = [], {}
    for index in range(n):
        day = first + timedelta(days=index)
        prediction = daily_close_time(day)
        q = (-1, 0, 1)[(index // 17) % 3]
        log_rv7 = -2.6 + .45 * np.sin(index / 23) + .18 * np.cos(index / 7)
        features = {"log_rv1": -3.1 + .4 * np.sin(index / 5),
                    "log_rv7": float(log_rv7),
                    "log_rv30": -2.2 + .3 * np.cos(index / 41)}
        noise = .16 * np.sin(index * 1.73) + .07 * np.cos(index * .37)
        log_future_rv = -2.0 + .28 * q + .22 * int(log_rv7 > -2.6) + noise
        target = ForecastTarget("SYN", prediction, prediction,
                                prediction + timedelta(days=7), float(np.exp(log_future_rv)), "OBSERVED")
        rows.append((target, features))
        q_by_day[day] = q
    return rows, q_by_day


def test_fast_state_threshold_uses_only_training_rows():
    rows, _ = _synthetic_rows(200)
    fit = rows[:120]
    expected = float(np.quantile([np.exp(row[1]["log_rv7"]) for row in fit], .75))
    assert _fast_high_threshold(fit) == expected
    assert expected < np.exp(8.0)


def test_current_slow_proxy_does_not_use_future_bars():
    first = date(2025, 1, 1)
    days = [first + timedelta(days=i) for i in range(120)]
    closes = [100 * np.exp(.004 * i + .03 * np.sin(i / 4)) for i in range(120)]
    candles = {"SYN": {day: (price, price * 1.01, price * .99, price, 100.0)
                       for day, price in zip(days, closes)}}
    common = dict(symbols=["SYN"], day_bounds=(first, days[-1]),
                  m1_names=["ret7", "ret21", "ret63", "z20", "er20", "rv5", "rv20"],
                  m2_names=["rv5_rv20", "volume_surprise20", "breadth_dispersion7", "funding_stress90"])
    _, original = make_panel(candles, {"SYN": []}, **common)
    changed_candles = {"SYN": dict(candles["SYN"])}
    for index in range(80, 120):
        day = days[index]
        price = closes[index] * (100 if index % 2 else .01)
        changed_candles["SYN"][day] = (price, price * 1.01, price * .99, price, 100.0)
    _, changed = make_panel(changed_candles, {"SYN": []}, **common)
    assert original["SYN"]["q"][75] == changed["SYN"]["q"][75]


def test_fixed_student_t_and_mixture_intervals_are_centered_and_repeatable():
    single = _density_summary(2.0, ("single", 2.0, .4))
    mixture = _density_summary(1.0, ("mixture", (0.0, 2.0), .4))
    assert single == _density_summary(2.0, ("single", 2.0, .4))
    assert mixture == _density_summary(1.0, ("mixture", (0.0, 2.0), .4))
    assert abs(sum(single["intervals"]["80"]) / 2 - 2.0) < 1e-10
    assert abs(sum(mixture["intervals"]["80"]) / 2 - 1.0) < 1e-10


def test_synthetic_runner_writes_inconclusive_receipt_and_matched_artifacts():
    first, last = date(2020, 1, 1), date(2021, 3, 31)
    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    prices = {"SYN": {day: (close, close * 1.01, close * .99, close, 100.0)
                       for i, day in enumerate(days)
                       for close in [100 * np.exp(.0007 * i + .04 * np.sin(i / 6) + .01 * np.cos(i / 15))]}}
    qc = {"SYN": {"qc_findings": []}}
    acquisition = {"records": [{"symbol": "SYN", "kind": "klines", "sha256": "synthetic"}],
                   "source_bytes": 0}
    fake_fold = [(date(2021, 1, 1), date(2021, 4, 1), "2021-Q1")]
    fake_pipeline = ModuleType("experiments.erf01.pipeline")
    fake_pipeline.DAYS = (first, last)
    fake_pipeline.FOLDS = fake_fold
    fake_pipeline.SYMS = ["SYN"]
    fake_pipeline.SEAL = date(2026, 4, 1)
    fake_pipeline.M1_NAMES = ["ret7", "ret21", "ret63", "z20", "er20", "rv5", "rv20"]
    fake_pipeline.M2_NAMES = ["rv5_rv20", "volume_surprise20", "breadth_dispersion7", "funding_stress90"]
    fake_adapter = ModuleType("experiments.erf01.tape_adapter")
    fake_adapter.load_development = lambda *args: (prices, {}, {}, qc, acquisition)
    fake_modules = {"experiments.erf01.pipeline": fake_pipeline,
                    "experiments.erf01.tape_adapter": fake_adapter}
    with patch.dict(sys.modules, fake_modules):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "h3-run"
            result = run_h3(Path(temp) / "staging", out, run_url="synthetic://run")
            assert result["decision_rule_result"] == "INCONCLUSIVE"
            assert result["n_prediction_rows"] > 0
            assert result["primary"]["scores"]["matched_rows"] == result["n_prediction_rows"]
            metrics = json.loads((out / "metrics.json").read_text())
            manifest = json.loads((out / "manifest.json").read_text())
            stored = [json.loads(line) for line in (out / "predictions.jsonl").read_text().splitlines()]
            assert len(stored) == result["n_prediction_rows"]
            assert manifest["protocol_sha"] == result["receipt"]["protocol_sha"]
            assert metrics["joint_state_scores"]
            assert metrics["model_complexity"]["linked_hierarchical"]["n_symbol_folds"] == 1


def test_fit_parameters_are_invariant_to_future_q_perturbations():
    rows, q_by_day = _synthetic_rows(800)
    fit = rows[:700]
    before = _fit_density_candidates(fit, q_by_day)
    altered = dict(q_by_day)
    cutoff = max(row[0].prediction_at.date() - timedelta(days=1) for row in fit)
    for day in altered:
        if day > cutoff:
            altered[day] = -altered[day]
    after = _fit_density_candidates(fit, altered)
    assert before["fast_threshold"] == after["fast_threshold"]
    assert np.array_equal(before["linked_beta"], after["linked_beta"])
    assert before["scales"] == after["scales"]
    assert before["diagnostics"]["slow_state_fit_support"] == after["diagnostics"]["slow_state_fit_support"]


def test_all_fixed_models_score_same_rows_with_finite_density_and_calibration_outputs():
    rows, q_by_day = _synthetic_rows()
    start = datetime(2022, 1, 1, tzinfo=UTC)
    end = datetime(2022, 3, 1, tzinfo=UTC)
    predictions, info = _fit_fold_symbol(rows, q_by_day, start, end, "synthetic", "SYN")
    assert info["status"] == "TESTED"
    assert info["fit_rows"] >= 60 and len(predictions) > 0
    train_targets = temporal_split([row[0] for row in rows], start, end).train
    expected_threshold = float(np.quantile([
        np.exp(feature["log_rv7"]) for target, feature in rows
        if target in train_targets and target.label_end < start
    ], .75))
    assert info["fast_rv7_q75_threshold_fit_only"] == expected_threshold
    held_out_extreme = [(target, {**feature, "log_rv7": 8.0})
                        if target.prediction_at >= start else (target, feature)
                        for target, feature in rows]
    _, perturbed_info = _fit_fold_symbol(held_out_extreme, q_by_day, start, end,
                                         "synthetic", "SYN")
    assert perturbed_info["fast_rv7_q75_threshold_fit_only"] == expected_threshold
    assert all(set(row["forecasts"]) == {
        "unlinked_mixture", "flat_cells", "linked_hierarchical", "continuous_har"
    } for row in predictions)
    assert all(row["joint_state"] == f"{row['slow_q_v1_proxy']}:{row['fast_rv7_high']}"
               for row in predictions)
    assert all(row["feature_available_at"] <= row["prediction_at"] for row in predictions)
    assert all(np.isfinite(forecast["log_density"]) and 0 <= forecast["pit"] <= 1
               for row in predictions for forecast in row["forecasts"].values())
    repeated, repeated_info = _fit_fold_symbol(rows, q_by_day, start, end, "synthetic", "SYN")
    assert repeated == predictions and repeated_info == info
    zero_rows = list(rows)
    zero_index = next(i for i, row in enumerate(zero_rows) if row[0].prediction_at >= start)
    original_target, feature = zero_rows[zero_index]
    zero_rows[zero_index] = (ForecastTarget(
        original_target.symbol, original_target.prediction_at, original_target.label_start,
        original_target.label_end, 0.0, "OBSERVED"), feature)
    zero_predictions, _ = _fit_fold_symbol(zero_rows, q_by_day, start, end, "synthetic", "SYN")
    zero_prediction = next(row for row in zero_predictions
                           if row["prediction_at"] == original_target.prediction_at.isoformat())
    assert zero_prediction["truth_log_rv7"] == np.log(1e-12)
    assert all(np.isfinite(value["log_density"])
               for value in zero_prediction["forecasts"].values())
    score = _score_predictions(predictions)
    assert score["matched_rows"] == len(predictions)
    assert score["primary_mean_gain_linked_vs_unlinked_nats"] == np.mean([
        row["forecasts"]["linked_hierarchical"]["log_density"]
        - row["forecasts"]["unlinked_mixture"]["log_density"] for row in predictions])
    for name in ("unlinked_mixture", "flat_cells", "linked_hierarchical", "continuous_har"):
        assert sum(score[name]["pit_histogram_10"]) == len(predictions)
        assert set(score[name]["central_interval_coverage"]) == {"50", "80", "95"}
    joint_scores = _group_scores(predictions, "joint_state")
    assert set(joint_scores) == {row["joint_state"] for row in predictions}
    complexity = _model_complexity({"synthetic": {"symbols": {"SYN": info}}})
    assert all(complexity[name]["n_symbol_folds"] == 1 for name in complexity)
