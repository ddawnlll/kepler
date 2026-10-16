from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from kepler.intelligence.metrics_v2 import binary_probability_scores, paired_date_block_interval
from kepler.intelligence.validation import (
    ForecastTarget, asof_latest, daily_close_time, deterministic_receipt,
    event_labels, fit_quantile_threshold, future_realized_risk,
    temporal_split, trailing_log_rv_features, utc, validate_prediction_window,
)
from experiments.market_intelligence.h1 import _asset_fold
from experiments.market_intelligence.h7 import (
    _candidate_predictions, _state_transition, student_t_cdf,
    student_t_logpdf, student_t_sf,
)

UTC = timezone.utc


def target(day, value=1.0, *, horizon=7, status="OBSERVED"):
    prediction = datetime.combine(day + timedelta(days=1), datetime.min.time(), UTC)
    end = prediction + timedelta(days=horizon)
    return ForecastTarget("TEST", prediction, prediction, end,
                          value if status == "OBSERVED" else None, status)


def test_utc_and_daily_close_boundary_are_explicit():
    assert utc(datetime(2025, 1, 1, tzinfo=timezone(timedelta(hours=2)))) == datetime(
        2024, 12, 31, 22, tzinfo=UTC)
    assert daily_close_time(date(2025, 1, 1)) == datetime(2025, 1, 2, tzinfo=UTC)
    with pytest.raises(ValueError, match="timezone-aware"):
        utc(datetime(2025, 1, 1))
    with pytest.raises(TypeError):
        daily_close_time(datetime(2025, 1, 1, tzinfo=UTC))
    with pytest.raises(ValueError, match="positive order"):
        ForecastTarget("T", datetime(2025, 1, 1, tzinfo=UTC),
                       datetime(2025, 1, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC),
                       1.0, "OBSERVED")


def test_asof_publication_delay_excludes_late_observation():
    rows = [(datetime(2025, 1, 1, tzinfo=UTC), "old"),
            (datetime(2025, 1, 2, 0, 1, tzinfo=UTC), "late")]
    assert asof_latest(rows, datetime(2025, 1, 2, tzinfo=UTC)) == rows[0]
    assert asof_latest(rows, datetime(2024, 12, 31, tzinfo=UTC)) is None
    with pytest.raises(ValueError, match="published after"):
        validate_prediction_window(datetime(2025, 1, 2, tzinfo=UTC), [rows[1][0]],
                                   datetime(2025, 1, 2, tzinfo=UTC),
                                   datetime(2025, 1, 9, tzinfo=UTC))


def test_target_is_realized_from_known_future_returns():
    days = [date(2025, 1, 1) + timedelta(days=i) for i in range(4)]
    closes = [100.0, 110.0, 100.0, 100.0]
    rows = future_realized_risk("TEST", days, closes, horizon_days=2)
    expected = float(np.sqrt(np.log(1.1) ** 2 + np.log(100 / 110) ** 2))
    assert rows[0].value == pytest.approx(expected)
    assert rows[0].status == "OBSERVED"
    assert rows[-1].status == "RIGHT_CENSORED"
    assert rows[-1].value is None


def test_target_gap_is_unknown_even_near_right_edge():
    days = [date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 4)]
    rows = future_realized_risk("TEST", days, [100, 101, 105], horizon_days=2)
    assert rows[0].status == "UNKNOWN_GAP"
    assert rows[1].status == "UNKNOWN_GAP"
    assert rows[2].status == "RIGHT_CENSORED"
    with pytest.raises(ValueError, match="strictly increasing"):
        future_realized_risk("TEST", days[::-1], [100, 101, 105], horizon_days=2)


def test_invalid_close_and_unknown_event_labels_do_not_become_negatives():
    days = [date(2025, 1, 1) + timedelta(days=i) for i in range(4)]
    rows = future_realized_risk("TEST", days, [100, float("nan"), 102, 103], horizon_days=2)
    assert rows[0].status == "UNKNOWN_INVALID_PRICE"
    with pytest.raises(ValueError, match="cannot become event negatives"):
        event_labels(rows[:1], 0.5)


def test_temporal_split_purges_overlapping_and_equal_maturity_targets():
    rows = [target(date(2025, 1, 1)), target(date(2025, 1, 11)),
            target(date(2025, 1, 20))]
    split = temporal_split(rows, datetime(2025, 1, 19, tzinfo=UTC),
                           datetime(2025, 2, 1, tzinfo=UTC))
    assert len(split.train) == 1
    assert split.purged == 1
    assert len(split.test) == 1


def test_threshold_fit_rejects_test_or_unmatured_rows():
    rows = [target(date(2025, 1, i), value=float(i)) for i in range(1, 4)]
    assert fit_quantile_threshold(rows[:1], .75,
                                  matured_before=datetime(2025, 1, 20, tzinfo=UTC)) == 1.0
    with pytest.raises(ValueError, match="not mature"):
        fit_quantile_threshold(rows, .75, matured_before=datetime(2025, 1, 11, tzinfo=UTC))
    with pytest.raises(ValueError, match="quantile"):
        fit_quantile_threshold(rows[:1], 1.0,
                               matured_before=datetime(2025, 1, 20, tzinfo=UTC))


def test_trailing_features_are_future_perturbation_invariant():
    returns = np.linspace(-.03, .04, 40)
    original = trailing_log_rv_features(returns, 34)
    changed = returns.copy()
    changed[35:] = [10.0, -9.0, 4.0, 20.0, -30.0]
    assert trailing_log_rv_features(changed, 34) == original
    assert trailing_log_rv_features(returns, 28) is None


def test_receipt_is_deterministic_and_excludes_volatile_run_url_from_identity():
    args = dict(protocol_sha="abc", code_sha256={"b": "2", "a": "1"},
                data_sha256={"input": "3"}, config={"seed": 4}, seed=4)
    a = deterministic_receipt(**args, run_url="https://actions/1")
    b = deterministic_receipt(**args, run_url="https://actions/2")
    assert a["receipt_id"] == b["receipt_id"]
    assert a["execution"]["run_url"] != b["execution"]["run_url"]
    assert a["economic_success"] == "OUT_OF_SCOPE"
    assert a["independent_validation"] == "NOT_RUN"


def test_probability_scores_match_known_answers_and_validate_support():
    scores = binary_probability_scores([0, 1], [0.0, 1.0])
    assert scores["n"] == 2
    assert scores["brier"] == pytest.approx(1e-12)
    assert scores["log_loss"] == pytest.approx(-np.log(1 - 1e-6))
    assert scores["reliability"][0]["n"] == 1
    assert scores["reliability"][-1]["n"] == 1
    with pytest.raises(ValueError, match="finite and in \\[0, 1\\]"):
        binary_probability_scores([0], [float("nan")])


def test_date_block_interval_averages_assets_by_date_and_is_repeatable():
    values = []
    for i in range(60):
        day = (date(2025, 1, 1) + timedelta(days=i)).isoformat()
        values.extend([(day, float(i)), (day, float(i + 2))])
    first = paired_date_block_interval(values, block_days=7, replicates=30, seed=123)
    second = paired_date_block_interval(values, block_days=7, replicates=30, seed=123)
    assert first == second
    assert first["n_dates"] == 60
    assert first["mean"] == pytest.approx(30.5)
    assert first["replicates"] == 30


def test_h1_synthetic_fold_fits_train_only_threshold_and_all_frozen_candidates():
    rows = []
    first = date(2020, 1, 1)
    for i in range(900):
        day = first + timedelta(days=i)
        value = 1.0 + .25 * np.sin(i / 11) + .15 * np.cos(i / 5)
        features = {"log_rv1": -2.0 + .2 * np.sin(i / 7),
                    "log_rv7": -1.0 + .3 * np.cos(i / 9),
                    "log_rv30": -.5 + .15 * np.sin(i / 17)}
        rows.append((target(day, float(value)), features))
    predictions, info = _asset_fold(
        rows, datetime(2022, 1, 1, tzinfo=UTC), datetime(2022, 4, 1, tzinfo=UTC))
    assert info["status"] == "TESTED"
    assert info["calibration_both_classes"] is True
    assert info["threshold_rv7_q75_fit_only"] < max(r[0].value for r in rows[:600])
    assert predictions
    assert all(set(r["probabilities"]) == {"prevalence", "last_risk", "AR1", "HAR"}
               for r in predictions)
    assert all(0 <= p <= 1 for r in predictions for p in r["probabilities"].values())


def test_student_t_density_and_tail_match_known_df5_values():
    assert student_t_logpdf(0, 0, 1, 5) == pytest.approx(-.9686195890547249)
    assert student_t_cdf(0, 0, 1, 5) == pytest.approx(.5)
    assert student_t_cdf(1, 0, 1, 5) == pytest.approx(.8183912661754386)
    assert student_t_cdf(-1, 0, 1, 5) == pytest.approx(.1816087338245614)
    assert student_t_sf(1, 0, 1, 5) == pytest.approx(.1816087338245614)
    with pytest.raises(ValueError, match="positive scale"):
        student_t_logpdf(0, 0, 0, 5)


def test_h7_transition_is_cut_off_before_calibration_and_density_candidates_match():
    rows = []
    q_by_day = {}
    first = date(2020, 1, 1)
    for i in range(700):
        day = first + timedelta(days=i)
        q_by_day[day] = (-1, 0, 1)[(i // 5) % 3]
        prediction = datetime.combine(day + timedelta(days=1), datetime.min.time(), UTC)
        value = 1.0 + .2 * np.sin(i / 8) + .12 * np.cos(i / 3)
        features = {"log_rv1": -2 + .2 * np.sin(i / 7),
                    "log_rv7": -1 + .3 * np.cos(i / 9),
                    "log_rv30": -.5 + .15 * np.sin(i / 17)}
        rows.append((ForecastTarget("TEST", prediction, prediction,
                                    prediction + timedelta(days=7), float(value), "OBSERVED"),
                     features))
    cutoff = rows[399][0].prediction_at
    transition = _state_transition(q_by_day, sorted(q_by_day), cutoff)
    mutated = dict(q_by_day)
    for day in list(mutated):
        if datetime.combine(day + timedelta(days=1), datetime.min.time(), UTC) > cutoff:
            mutated[day] = -mutated[day]
    np.testing.assert_array_equal(_state_transition(mutated, sorted(mutated), cutoff), transition)
    fit = [rows[i] for i in range(300)]
    test_rows = [(target_row, features, q_by_day[target_row.prediction_at.date() - timedelta(days=1)])
                 for target_row, features in rows[500:520]]
    forecasts, diagnostics = _candidate_predictions(fit, test_rows, q_by_day, threshold_rv7=1.2)
    assert len(forecasts) == len(test_rows)
    assert diagnostics["training_q_transition_counts"]
    assert sum(diagnostics["matured_target_future_q_counts"].values()) >= 60
    for forecast in forecasts:
        assert np.isfinite(forecast["discrete_logpdf"])
        assert np.isfinite(forecast["continuous_logpdf"])
        assert sum(forecast["forecast_state_probabilities"]) == pytest.approx(1)
        assert 0 <= forecast["discrete_tail_probability"] <= 1
        assert 0 <= forecast["continuous_tail_probability"] <= 1
