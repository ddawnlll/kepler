"""ERF-01 five-year regime science: censoring, no lookahead and baseline checks."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from scripts import erf01_regime_atlas as ra


def sequence(values, first=date(2025, 1, 1)):
    return [first + timedelta(days=i) for i in range(len(values))]


def test_spells_do_not_turn_missing_days_into_confirmed_regime_endings():
    q = np.array([np.nan, 0, 0, 1, 1, np.nan, -1, -1, -1, 0], float)
    episodes = ra.spells(sequence(q), q)
    assert [(s["state"], s["duration"]) for s in episodes] == [
        (0, 2), (1, 2), (-1, 3), (0, 1)]
    assert episodes[0]["left_censored"] and not episodes[0]["right_censored"]
    assert episodes[1]["right_censored"] and not episodes[1]["left_censored"]
    assert episodes[2]["left_censored"] and not episodes[2]["right_censored"]
    assert episodes[3]["right_censored"]
    grouped = ra.spell_distribution(episodes)
    assert grouped["spells"] == 4
    assert grouped["completed"] == 0


def test_state_runs_with_known_exit_are_measured_not_marked_censored():
    q = np.asarray([-1, -1, -1, 0, 0, 1, 1, 1], float)
    episodes = ra.spells(sequence(q), q)
    assert [x["duration"] for x in episodes] == [3, 2, 3]
    assert not episodes[1]["left_censored"] and not episodes[1]["right_censored"]
    assert episodes[-1]["right_censored"]
    assert ra.spell_distribution(episodes)["median_completed_days"] == 2


def test_state_transition_prior_cannot_read_test_dates(monkeypatch):
    monkeypatch.setattr(ra.erf01, "SYMS", ["BTCUSDT"])
    days = sequence([0] * 8)
    first = np.array([0, 0, 0, 0, 0, 0, 1, 1], float)
    second = np.array([0, 0, 0, 0, 0, 1, -1, -1], float)
    cutoff = days[5]
    a = ra.transition_matrix({"BTCUSDT": {"q": first}}, days, cutoff)
    b = ra.transition_matrix({"BTCUSDT": {"q": second}}, days, cutoff)
    assert np.array_equal(a, b)
    assert np.allclose(a.sum(axis=1), 1)
    assert np.all(a > 0)


def test_censored_spell_never_becomes_a_fake_event():
    episodes = [
        {"state": 1, "duration": 3, "left_censored": False, "right_censored": False},
        {"state": 1, "duration": 10, "left_censored": False, "right_censored": True},
        {"state": 1, "duration": 1, "left_censored": True, "right_censored": False},
    ]
    observed, base = ra.survival_parameters(episodes, 1)
    assert len(observed) == 2
    assert 0 < base < 1
    one = ra.continuation_probability(episodes, 1, 3, 1)
    long = ra.continuation_probability(episodes, 1, 3, 14)
    assert 0 < long <= one < 1


def test_scored_brier_uses_correct_direction_and_rejects_no_observations():
    q = [{"date": date(2024, 1, 1) + timedelta(days=i),
          "true": 1 if i % 2 else 0,
          "f": 0.85 if i % 2 else 0.15,
          "b": 0.5} for i in range(32)]
    r = ra.summarise_forecast(q, "f", "b")
    assert r["n"] == 32 and r["brier"] < r["baseline_brier"]
    assert ra.summarise_forecast([], "f", "b")["status"] == "NOT_RUN"


def test_horizon_forecast_is_only_scored_with_future_state_and_purged_time(monkeypatch):
    monkeypatch.setattr(ra.erf01, "SYMS", ["BTCUSDT"])
    monkeypatch.setattr(ra.erf01, "FOLDS", [
        (date(2023, 1, 1), date(2023, 3, 1), "2023-01")])
    days = sequence([0] * 0, date(2020, 1, 1))
    end = date(2023, 4, 1)
    while not days or days[-1] < end - timedelta(days=1):
        days.append(date(2020, 1, 1) if not days else days[-1] + timedelta(days=1))
    q = np.asarray([0 if (i // 30) % 3 == 0 else
                    1 if (i // 30) % 3 == 1 else -1
                    for i in range(len(days))], dtype=float)
    age = np.zeros(len(q))
    for i, v in enumerate(q):
        age[i] = age[i - 1] + 1 if i and q[i - 1] == v else 1
    result = ra.analyse(days, {"BTCUSDT": {"q": q, "age": age}})
    assert result["trading_pnl"] == "OUT_OF_SCOPE"
    assert result["independent_unseen_validation"] == "NOT_RUN"
    assert result["forecast_oos_horizon_days"]["21"][
        "future_state_markov_vs_persistence"]["n"] > 0
    assert all(f["train_last_date"] < f["test_first_date"] for f in result["folds"])


def test_sealed_data_is_never_processed():
    with pytest.raises(RuntimeError, match="sealed"):
        ra.analyse([date(2020, 1, 1), date(2026, 4, 1)], {})
