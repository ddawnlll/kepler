from datetime import date, datetime, timedelta, timezone

import pytest

from kepler.intelligence.survival import (
    HAZARD_FAMILIES,
    build_survival_landmarks,
    fit_discrete_hazard,
    fit_delayed_entry_censor_curve,
    forecast_remaining_survival,
    ipcw_survival_scores,
    predict_one_day_exit_hazard,
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
    # A missing Jan 4 close is not knowable until its scheduled Jan 5 close;
    # this timestamp prevents a fold boundary from training on the future gap.
    assert jan3.label_end == daily_close_time(date(2025, 1, 4))
    # An observed state after a missing close does not inherit a known onset.
    jan5 = next(row for row in rows if row.prediction_at.date() == date(2025, 1, 5))
    assert jan5.left_censored
    assert jan5.elapsed_age is None


def test_censor_curve_requires_one_day_risk_rows_and_counts_gap_censoring():
    rows = landmarks([-1, 1, 1, None, 1], horizon=1)
    cutoff = datetime(2030, 1, 1, tzinfo=timezone.utc)
    curve = fit_delayed_entry_censor_curve(rows, through_age=4, matured_before=cutoff)
    assert curve[1]["survival"] == 1.0
    # At duration 3, one known-onset spell is at risk and lost to a gap.
    assert curve[3]["risk"] == 1.0
    assert curve[3]["censors"] == 1.0
    assert curve[3]["survival"] == 0.0

    with pytest.raises(ValueError, match="one-day"):
        fit_delayed_entry_censor_curve(
            landmarks([-1, 1, 1], horizon=2), through_age=3, matured_before=cutoff)
    with pytest.raises(ValueError, match="positive whole number"):
        fit_delayed_entry_censor_curve(rows, through_age=2.5, matured_before=cutoff)


def test_four_frozen_hazard_candidates_are_train_only_and_forecast_as_of():
    pattern = (-1, -1, -1, 0, 0, 1, 1, 1, 0)
    states = [pattern[i % len(pattern)] for i in range(90)]
    rows = landmarks(states, horizon=1)
    market = [[-4.0 + (i % 7) / 10, -3.5 + (i % 5) / 10, -3.0 + (i % 3) / 10]
              for i in range(len(rows))]
    feature_times = [row.prediction_at for row in rows]
    cutoff = datetime(2025, 6, 1, tzinfo=timezone.utc)
    target = next(row for row in rows if row.elapsed_age is not None)
    feature_time = target.prediction_at - timedelta(hours=1)

    assert HAZARD_FAMILIES == {
        "state_age_blind", "age_only", "market_only", "market_plus_age"
    }
    for family in sorted(HAZARD_FAMILIES):
        model = fit_discrete_hazard(
            rows, market, family=family, matured_before=cutoff,
            feature_available_times=feature_times,
        )
        assert model.n_fit > 0 and model.n_exits > 0
        result = forecast_remaining_survival(
            model, state=target.state, elapsed_age=target.elapsed_age,
            market_conditions=market[rows.index(target)],
            prediction_at=target.prediction_at, feature_available_at=feature_time,
            horizon_days=14,
        )
        assert result["family"] == family
        assert result["prediction_at"] == target.prediction_at.isoformat()
        assert 0 <= result["survival_probability"] <= 1
        assert len(result["daily_exit_hazards"]) == 14
        for offset, hazard in enumerate(result["daily_exit_hazards"]):
            assert hazard == pytest.approx(predict_one_day_exit_hazard(
                model, state=target.state, elapsed_age=target.elapsed_age + offset,
                market_conditions=market[rows.index(target)]))

    with pytest.raises(ValueError, match="strictly before the cutoff"):
        fit_discrete_hazard(rows, market, family="market_plus_age",
                            matured_before=rows[-2].label_end,
                            feature_available_times=feature_times)
    model = fit_discrete_hazard(rows, market, family="market_only", matured_before=cutoff,
                                feature_available_times=feature_times)
    future_times = list(feature_times)
    future_times[5] = rows[5].prediction_at + timedelta(seconds=1)
    with pytest.raises(ValueError, match="published after"):
        fit_discrete_hazard(rows, market, family="market_only", matured_before=cutoff,
                            feature_available_times=future_times)
    with pytest.raises(ValueError, match="published after"):
        forecast_remaining_survival(
            model, state=target.state, elapsed_age=target.elapsed_age,
            market_conditions=market[rows.index(target)],
            prediction_at=target.prediction_at,
            feature_available_at=target.prediction_at + timedelta(seconds=1), horizon_days=7,
        )


def test_fixed_hazard_hidden_subtypes_create_a_pooled_age_gradient():
    # Each latent subtype has a constant hazard. High-hazard spells leave the
    # risk set sooner, so the pooled observed hazard falls with elapsed age.
    subtype_hazards = (0.25, 0.05)

    def pooled_next_day_hazard(elapsed_age):
        survivor_mass = [0.5 * (1 - hazard) ** elapsed_age
                         for hazard in subtype_hazards]
        exit_mass = [mass * hazard for mass, hazard in zip(survivor_mass, subtype_hazards)]
        return sum(exit_mass) / sum(survivor_mass)

    assert pooled_next_day_hazard(0) == pytest.approx(0.15)
    assert pooled_next_day_hazard(1) < pooled_next_day_hazard(0)
    assert pooled_next_day_hazard(8) < pooled_next_day_hazard(1)


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
    assert result["date_brier"] == {"2025-01-04": pytest.approx((0.75 - 0.0) ** 2)}


def test_landmarks_reject_bad_prediction_times_and_invalid_horizons():
    days = [date(2025, 1, 1), date(2025, 1, 2)]
    with pytest.raises(ValueError, match="positive whole number"):
        build_survival_landmarks("T", days, [0, 0], [daily_close_time(d) for d in days], 1.5)
    with pytest.raises(ValueError, match="matching UTC daily closes"):
        build_survival_landmarks("T", days, [0, 0], [daily_close_time(days[0])] * 2, 1)
    with pytest.raises(ValueError, match="boolean values"):
        build_survival_landmarks("T", days, [True, 0], [daily_close_time(d) for d in days], 1)


def test_future_state_perturbation_does_not_change_prior_episode_age():
    days = [date(2025, 1, 1) + timedelta(days=i) for i in range(6)]
    times = [daily_close_time(day) for day in days]
    baseline = build_survival_landmarks("T", days, [-1, -1, 1, 1, 1, 1], times, 2)
    perturbed = build_survival_landmarks("T", days, [-1, -1, 1, -1, -1, -1], times, 2)
    for index in (0, 1, 2):
        assert baseline[index].state == perturbed[index].state
        assert baseline[index].elapsed_age == perturbed[index].elapsed_age
