"""Synthetic known-answer tests for the funding-only PMI-H4 ablation."""
from datetime import date, datetime, timedelta, timezone
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import numpy as np

from experiments.market_intelligence.h4 import _asset_fold_funding, run_h4
from kepler.intelligence.features import make_panel
from kepler.intelligence.validation import ForecastTarget, daily_close_time

UTC = timezone.utc


def _rows(n=1000):
    first = date(2020, 1, 1)
    rows = []
    for index in range(n):
        day = first + timedelta(days=index)
        prediction = daily_close_time(day)
        funding = np.sin(index / 13) + .4 * np.cos(index / 5)
        features = {"log_rv1": -3 + .3 * np.sin(index / 4),
                    "log_rv7": -2.4 + .45 * np.cos(index / 19),
                    "log_rv30": -1.9 + .25 * np.sin(index / 39),
                    "funding_stress90": float(funding)}
        log_rv = -2.0 + .12 * np.sin(index / 7) + .22 * (funding > .8) + .1 * np.cos(index / 3)
        target = ForecastTarget("SYN", prediction, prediction, prediction + timedelta(days=7),
                                float(np.exp(log_rv)), "OBSERVED")
        rows.append((target, features))
    return rows


def test_funding_ablation_is_matched_and_threshold_is_fit_only():
    rows = _rows()
    start, end = datetime(2022, 1, 1, tzinfo=UTC), datetime(2022, 4, 1, tzinfo=UTC)
    predictions, info = _asset_fold_funding(rows, start, end, symbol="SYN", fold="synthetic")
    assert info["status"] == "TESTED"
    assert info["matched_funding_test"] == len(predictions)
    assert info["price_ready_test"] == len(predictions)
    assert all(set(row["probabilities"]) == {"har", "har_plus_funding"} for row in predictions)
    assert all(0 <= p <= 1 for row in predictions for p in row["probabilities"].values())
    perturbed = [(ForecastTarget(target.symbol, target.prediction_at, target.label_start,
                                 target.label_end,
                                 1000.0 if target.prediction_at >= start else target.value,
                                 target.status), features)
                 for target, features in rows]
    _, changed = _asset_fold_funding(perturbed, start, end, symbol="SYN", fold="synthetic")
    assert changed["threshold_rv7_q75_fit_only"] == info["threshold_rv7_q75_fit_only"]


def test_missing_funding_feature_removes_rows_from_both_models():
    rows = _rows()
    start, end = datetime(2022, 1, 1, tzinfo=UTC), datetime(2022, 4, 1, tzinfo=UTC)
    changed = list(rows)
    for index, (target, features) in enumerate(changed):
        if target.prediction_at >= start and index % 5 == 0:
            changed[index] = (target, {**features, "funding_stress90": float("nan")})
    predictions, info = _asset_fold_funding(changed, start, end, symbol="SYN", fold="synthetic")
    assert info["price_ready_test"] > info["matched_funding_test"]
    assert len(predictions) == info["matched_funding_test"]


def test_funding_feature_excludes_events_at_and_after_prediction_close():
    first = date(2025, 1, 1)
    days = [first + timedelta(days=i) for i in range(120)]
    closes = [100 * np.exp(.003 * i + .025 * np.sin(i / 4)) for i in range(120)]
    prices = {"SYN": {day: (price, price * 1.01, price * .99, price, 100.0)
                       for day, price in zip(days, closes)}}
    events = []
    begin = datetime.combine(first - timedelta(days=100), datetime.min.time(), UTC)
    for index in range(220 * 3):
        at = begin + timedelta(hours=8 * index)
        events.append((int(at.timestamp() * 1000), .0001 + .0002 * np.sin(index / 9)))
    end = daily_close_time(days[100])
    base = {"SYN": sorted(events)}
    changed = {"SYN": sorted(events + [(int(end.timestamp() * 1000), 1000.0),
                                       (int((end + timedelta(hours=1)).timestamp() * 1000), -1000.0)])}
    kwargs = dict(symbols=["SYN"], day_bounds=(first, days[-1]),
                  m1_names=["ret7", "ret21", "ret63", "z20", "er20", "rv5", "rv20"],
                  m2_names=["rv5_rv20", "volume_surprise20", "breadth_dispersion7", "funding_stress90"])
    _, original = make_panel(prices, base, **kwargs)
    _, perturbed = make_panel(prices, changed, **kwargs)
    assert original["SYN"]["funding_stress90"][100] == perturbed["SYN"]["funding_stress90"][100]


def test_synthetic_runner_writes_matched_metrics_and_data_gate_provenance():
    first, last = date(2020, 1, 1), date(2021, 3, 31)
    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    prices = {"SYN": {day: (close, close * 1.01, close * .99, close, 100.0)
                       for index, day in enumerate(days)
                       for close in [100 * np.exp(.0007 * index + .035 * np.sin(index / 5))]}}
    funding = {"SYN": []}
    start = datetime.combine(first - timedelta(days=100), datetime.min.time(), UTC)
    for index in range(570 * 3):
        at = start + timedelta(hours=8 * index)
        funding["SYN"].append((int(at.timestamp() * 1000), .0001 + .0002 * np.sin(index / 9)))
    qc = {"SYN": {"qc_findings": []}}
    acquisition = {"records": [{"symbol": "SYN", "kind": kind, "sha256": "a" * 64}
                                for kind in ("klines", "markPriceKlines", "fundingRate")],
                   "source_bytes": 123}
    fake_pipeline = ModuleType("experiments.erf01.pipeline")
    fake_pipeline.DAYS = (first, last)
    fake_pipeline.FOLDS = [(date(2021, 1, 1), date(2021, 4, 1), "2021-Q1")]
    fake_pipeline.SYMS = ["SYN"]
    fake_pipeline.SEAL = date(2026, 4, 1)
    fake_pipeline.M1_NAMES = ["ret7", "ret21", "ret63", "z20", "er20", "rv5", "rv20"]
    fake_pipeline.M2_NAMES = ["rv5_rv20", "volume_surprise20", "breadth_dispersion7", "funding_stress90"]
    fake_adapter = ModuleType("experiments.erf01.tape_adapter")
    fake_adapter.load_development = lambda *args: (prices, funding, {}, qc, acquisition)
    with patch.dict(sys.modules, {"experiments.erf01.pipeline": fake_pipeline,
                                  "experiments.erf01.tape_adapter": fake_adapter}):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "h4-run"
            result = run_h4(Path(temp) / "staging", out, run_url="synthetic://run")
            assert result["status"] == "EXPLORATORY", result
            assert result["decision_rule_result"] == "INCONCLUSIVE"
            assert result["n_prediction_rows"] > 0
            assert result["funding_source_inventory"]["oi"] == "NOT_VERIFIED"
            metrics = json.loads((out / "metrics.json").read_text())
            manifest = json.loads((out / "manifest.json").read_text())
            predictions = [json.loads(line) for line in (out / "predictions.jsonl").read_text().splitlines()]
            assert len(predictions) == result["n_prediction_rows"]
            assert metrics["primary"]["n"] == len(predictions)
            assert manifest["protocol_sha"] == result["receipt"]["protocol_sha"]
