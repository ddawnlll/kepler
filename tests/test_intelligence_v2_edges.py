from datetime import date, timedelta

import pytest

from kepler.intelligence.metrics_v2 import binary_probability_scores, paired_date_block_interval
from kepler.intelligence.validation import future_realized_risk


def test_block_bootstrap_does_not_bridge_missing_calendar_dates():
    rows = [(date(2025, 1, 1) + timedelta(days=2 * i), float(i)) for i in range(40)]
    interval = paired_date_block_interval(rows, block_days=7, replicates=30, seed=123)
    assert interval["n_dates"] == 40
    assert interval["replicates"] == 0
    assert interval["p025"] is None


@pytest.mark.parametrize("labels", ([.9], [256], [float("nan")]))
def test_binary_scores_reject_labels_before_integer_conversion(labels):
    with pytest.raises(ValueError, match="outcomes must be binary"):
        binary_probability_scores(labels, [.5])


def test_forward_risk_horizon_requires_an_integer_number_of_days():
    days = [date(2025, 1, 1) + timedelta(days=i) for i in range(3)]
    with pytest.raises(ValueError, match="positive horizon"):
        future_realized_risk("TEST", days, [100.0, 101.0, 102.0], horizon_days=1.5)
