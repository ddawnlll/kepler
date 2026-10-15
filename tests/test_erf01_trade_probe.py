"""Causal/day-boundary and idempotent safety checks for ERF01 economic exploration."""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts import erf01_trade_probe as probe


def klines(start="2025-01-01", days=5):
    ix = pd.date_range(start, periods=24 * days, freq="h", tz="UTC")
    p = np.full(len(ix), 100.0)
    return pd.DataFrame({"open": p, "high": p + 1,
                         "low": p - 1, "close": p, "volume": p}, index=ix)


def test_no_future_hourly_decision_and_one_day_exit():
    kl = klines(days=4)
    p = {"2025-01-01": (0.2, 0.01), "2025-01-02": (0.4, 0.01),
         "2025-01-03": (0.3, 0.01), "2025-01-04": (0.2, 0.01)}
    target, counts = probe.targets(kl, p, 1.5, 0.015, 1)
    assert (target.loc["2025-01-01 00:00":"2025-01-01 22:00"] == 0).all()
    assert target.loc["2025-01-01 23:00"] == 1000
    assert target.loc["2025-01-02 00:00"] == 1000
    assert target.loc["2025-01-02 23:00"] == 0
    assert target.loc["2025-01-03 23:00"] == 1000
    assert target.loc["2025-01-04 23:00"] == 0
    assert counts["entries"] == counts["exits"] == 2
    assert counts["max_planned_closed_days"] == 1


def test_reverse_reference_preserves_schedule_not_labels():
    kl = klines(days=3)
    p = {"2025-01-01": (0.2, 0.01), "2025-01-02": (0.05, 0.4)}
    normal, _ = probe.targets(kl, p, 1.5, 0.015, 1)
    reverse, _ = probe.targets(kl, p, 1.5, 0.015, 1, invert=True)
    assert (reverse == -normal).all()


def test_predictor_cannot_ingest_sealed_rows(tmp_path):
    f = tmp_path / "prediction.csv"
    with f.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "model", "symbol", "date", "p_up", "p_down", "p_none", "y"])
        writer.writeheader()
        writer.writerow({"model": "M1", "symbol": "BTCUSDT",
                         "date": "2026-04-01", "p_up": 0.1,
                         "p_down": 0.1, "p_none": 0.8, "y": 1})
    with pytest.raises(ValueError, match="non-DEV"):
        probe.load_predictions(f, "M1")


def test_research_exhaustion_does_not_retest_same_data(tmp_path):
    for candidate in probe.CANDIDATES:
        (tmp_path / (candidate[0] + ".json")).write_text("{}")
    response = probe.run_one(Path("/canonical/missing"), tmp_path)
    assert response == {"status": "EXHAUSTED", "scope": "eight registered exploratory candidates",
                        "completed": len(probe.CANDIDATES)}


def test_preflight_missing_canonical_data_fails_closed(tmp_path):
    with pytest.raises((FileNotFoundError, RuntimeError)):
        probe.preflight(tmp_path)


def test_never_exceed_21_day_horizon_or_touch_seal():
    with pytest.raises(ValueError, match="holding"):
        probe.targets(klines(), {}, 1.5, 0.015, 22)
    with pytest.raises(RuntimeError, match="sealed"):
        probe.targets(klines("2026-04-01", 2), {}, 1.5, 0.015, 7)
