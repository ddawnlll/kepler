"""Synthetic-only checks for H2 residual-life intervals and score pooling."""
from datetime import date, timedelta

import numpy as np

from experiments.market_intelligence.h2 import (
    _residual_intervals,
    _score_collection,
    _sensitivity_states,
)
from kepler.intelligence.survival import build_survival_landmarks
from kepler.intelligence.validation import daily_close_time


def test_residual_life_central_intervals_and_nonestimable_tails():
    estimable = _residual_intervals([0.5] * 365)
    assert estimable["50"] == {"lower_days": 1, "upper_days": 2}
    assert estimable["80"] == {"lower_days": 1, "upper_days": 4}
    assert estimable["95"] == {"lower_days": 1, "upper_days": 6}
    assert _residual_intervals([0.001] * 365)["50"] is None


def test_h2_score_pooling_preserves_shared_date_clusters_and_ipcw_support():
    days = [date(2025, 1, 1) + timedelta(days=i) for i in range(16)]
    targets = build_survival_landmarks(
        "TEST", days, [-1, *([1] * 14), -1],
        [daily_close_time(day) for day in days], horizon_days=14
    )
    scored = [targets[1], targets[2]]
    curve = {age: {"survival": 1.0} for age in range(40)}
    curves = {("f1", "TEST"): curve, ("f2", "TEST"): curve}
    rows = []
    for fold, probabilities in (("f1", (0.8, 0.2)), ("f2", (0.6, 0.4))):
        for target, probability in zip(scored, probabilities):
            rows.append({
                "fold": fold, "symbol": "TEST", "targets": {14: target},
                "probabilities": {"market_only": {"14": probability}},
            })
    pooled = _score_collection(rows, 14, "market_only", curves)
    assert pooled["n_scored"] == 4
    assert pooled["n_exits"] == 4 and pooled["n_survivors"] == 0
    assert pooled["effective_n"] == 4
    assert pooled["date_brier"]["2025-01-03"] > 0


def test_label_sensitivity_keeps_missing_rolling_inputs_unknown():
    assert _sensitivity_states(
        np.array([2.0, 1.5, -1.5, 1.49, np.nan]),
        np.array([.4, .35, .35, .8, .8]),
    ) == [1, 1, -1, 0, None]
