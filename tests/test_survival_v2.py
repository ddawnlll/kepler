from datetime import date, timedelta

import pytest

from kepler.intelligence.survival import (
    build_survival_landmarks,
    fit_delayed_entry_censor_curve,
    ipcw_survival_scores,
)
from kepler.intelligence.validation import daily_close_time


def landmarks(states, *, start=date(2025, 1, 1), horizon=2):
    days = [start + timedelta(days=i) for i in range(len(states))]
    return build_survival_landmarks(
        "TEST", days, states, [daily_close_time(day) for day in days], horizon
    )


def test_spell_onset_age_exit_and_left_censor_are_explicit():
    rows = landmarks([-1, -1, 1, 1, 1, -1], horizon=2)
    by_day = {row.prediction_at.date(): row for row in rows}

    # Dataset-start history cannot identify the -1 spell's onset.
    assert by_day[date(2025, 1, 2)].left_censored
    assert by_day[date(2025, 1, 2)].elapsed_age is None
    # A new state after a directly observed different state has known age.
    assert by_day[date(2025, 1, 4)].elapsed_age == 1
    assert by_day[date(2025, 1, 5)].elapsed_age == 2
    # Jan 4 prediction survives the two closes; Jan 5 sees the Jan 6 exit.
    assert by_day[date(2025, 1, 4)].survives_horizon == 1
    assert by_day[date(2025, 1, 5)].survives_horizon == 0
    assert by_day[date(2025, 1, 5)].event_time_days == 2


def test_gap_censors_instead_of_becoming_a_survival_failure():
    rows = landmarks([-1, 1, 1, None, 1], horizon=2)
    jan3 = next(row for row in rows if row.prediction_at.date() == date(2025, 1, 3))
    assert jan3.status == "UNKNOWN_GAP"
    assert jan3.survives_horizon is None
    assert jan3.event_time_days is None
    # An observed state after a missing close does not inherit a known onset.
    jan5 = next(row for row in rows if row.prediction_at.date() == date(2025, 1, 5))
    assert jan5.left_censored
    assert jan5.elapsed_age is None


def test_censor_curve_requires_one_day_risk_rows_and_counts_gap_censoring():
    rows = landmarks([-1, 1, 1, None, 1], horizon=1)
    curve = fit_delayed_entry_censor_curve(rows, through_age=4)
    assert curve[1]["survival"] == 1.0
    # At duration 3, one known-onset spell is at risk and lost to a gap.
    assert curve[3]["risk"] == 1.0
    assert curve[3]["censors"] == 1.0
    assert curve[3]["survival"] == 0.0

    with pytest.raises(ValueError, match="one-day"):
        fit_delayed_entry_censor_curve(landmarks([-1, 1, 1], horizon=2), through_age=3)
    with pytest.raises(ValueError, match="positive whole number"):
        fit_delayed_entry_censor_curve(rows, through_age=2.5)


def test_ipcw_uses_observation_probability_before_event_day():
    rows = landmarks([-1, 1, 1, 1, -1, -1], horizon=2)
    target = next(row for row in rows if row.prediction_at.date() == date(2025, 1, 4))
    assert target.event_time_days == 2
    # G(age)=0.8; the observed state exit is weighted by G(T-) = G(age+1)=0.4.
    curve = {
        1: {"survival": 1.0},
        2: {"survival": 0.8},
        3: {"survival": 0.4},
        4: {"survival": 0.2},
    }
    result = ipcw_survival_scores([target], [0.75], curve)
    assert result["n_scored"] == 1
    assert result["max_ipcw_weight"] == pytest.approx(2.0)
    assert result["brier"] == pytest.approx((0.75 - 0.0) ** 2)


def test_landmarks_reject_bad_prediction_times_and_invalid_horizons():
    days = [date(2025, 1, 1), date(2025, 1, 2)]
    with pytest.raises(ValueError, match="positive whole number"):
        build_survival_landmarks("T", days, [0, 0], [daily_close_time(d) for d in days], 1.5)
    with pytest.raises(ValueError, match="matching UTC daily closes"):
        build_survival_landmarks("T", days, [0, 0], [daily_close_time(days[0])] * 2, 1)
