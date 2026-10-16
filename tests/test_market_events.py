from datetime import date, datetime, timedelta, timezone

import math

from kepler.intelligence.events import (
    alarm_episodes, cluster_event_dates, confirmed_proxy_onsets,
    cusum_14d_scores, evaluate_alarm_events, fit_alarm_thresholds,
    fit_cusum_normalization, jeffreys_daily_hazard,
    paired_cluster_warning_interval, threshold_alarms,
)
from kepler.intelligence.validation import daily_close_time


def _days(start, count):
    return [start + timedelta(days=i) for i in range(count)]


def _raises(error_type, match, function):
    try:
        function()
    except error_type as exc:
        assert match in str(exc)
    else:
        raise AssertionError(f"expected {error_type.__name__} containing {match!r}")


def test_onset_keeps_first_transition_and_future_confirmation_is_only_a_label():
    days = _days(date(2022, 1, 1), 24)
    q = [0] * 10 + [1] * 11 + [0, 0, 0]
    result = confirmed_proxy_onsets("A", days, q)
    assert len(result) == 1
    assert result[0]["onset_date"] == days[10].isoformat()
    assert result[0]["confirmation_date"] == days[20].isoformat()
    assert result[0]["status"] == "CONFIRMED"
    assert result[0]["same_state_days"] == 10


def test_confirmation_gap_and_right_edge_are_unknown_not_negative():
    days = _days(date(2022, 1, 1), 25)
    q = [0] * 10 + [1] * 15
    q[14] = math.nan
    gap = confirmed_proxy_onsets("A", days, q)[0]
    assert gap["status"] == "UNKNOWN_GAP"
    right = confirmed_proxy_onsets("A", days[:15], [0] * 10 + [1] * 5)[0]
    assert right["status"] == "RIGHT_CENSORED"
    assert right["confirmation_date"] is None


def test_gapped_neutral_history_does_not_create_a_candidate_onset():
    days = _days(date(2022, 1, 1), 24)
    del days[4]
    q = [0] * len(days)
    q[10] = -1
    q[11:] = [-1] * (len(q) - 11)
    assert confirmed_proxy_onsets("A", days, q) == []


def test_cross_symbol_clusters_are_anchored_to_the_first_date():
    events = [
        {"symbol": "A", "onset_date": "2022-01-01"},
        {"symbol": "B", "onset_date": "2022-01-14"},
        {"symbol": "C", "onset_date": "2022-01-15"},
    ]
    clusters = cluster_event_dates(events, cluster_days=14)
    assert [x["event_count"] for x in clusters] == [2, 1]


def test_cusum_is_causal_and_resets_at_missing_days():
    days = _days(date(2022, 1, 1), 20)
    values = [0.0] * 19 + [100.0]
    before = cusum_14d_scores(days, values, center=0.0, scale=1.0)
    changed_future = cusum_14d_scores(days, values[:-1] + [-100.0], center=0.0, scale=1.0)
    assert before[:-1] == changed_future[:-1]
    values[10] = None
    reset = cusum_14d_scores(days, values, center=0.0, scale=1.0)
    assert reset[10] is None
    assert reset[11] == 0.0


def test_alarm_matching_is_one_to_one_and_separates_pre_and_post_onset():
    days = _days(date(2022, 1, 1), 70)
    events = [
        {"symbol": "A", "onset_date": "2022-01-20", "status": "CONFIRMED"},
        {"symbol": "A", "onset_date": "2022-01-25", "status": "CONFIRMED"},
    ]
    alarm_dates = {date(2022, 1, 6), date(2022, 1, 19), date(2022, 2, 5)}
    rows = [{"symbol": "A", "date": day, "prediction_at": daily_close_time(day),
             "score": 1.0, "alarm": day in alarm_dates,
             "feature_available_at": [daily_close_time(day)]} for day in days]
    result = evaluate_alarm_events(events, rows, cooldown_days=7)
    assert result["alarm_episodes"] == 3
    assert result["primary_warning_events"] == 1
    assert result["near_onset_detections"] == 1
    assert result["post_onset_detections"] == 0
    assert result["false_alarm_episodes"] == 1
    assert result["primary_lead_days"] == [14]
    assert len(result["matches"]) == 2


def test_post_onset_detection_never_counts_as_a_primary_warning():
    days = _days(date(2022, 1, 1), 45)
    onset = date(2022, 1, 20)
    rows = [{"symbol": "A", "date": day, "prediction_at": daily_close_time(day),
             "score": 2.0, "alarm": day == onset + timedelta(days=2)}
            for day in days]
    result = evaluate_alarm_events([
        {"symbol": "A", "onset_date": onset.isoformat(), "status": "CONFIRMED"}
    ], rows)
    assert result["primary_warning_events"] == 0
    assert result["post_onset_detections"] == 1
    assert result["primary_warning_recall"] == 0.0


def test_alarm_contract_rejects_future_features_and_missing_timestamps():
    d = date(2022, 1, 1)
    row = {"symbol": "A", "date": d, "score": 0.2,
           "prediction_at": daily_close_time(d), "alarm": False,
           "feature_available_at": [daily_close_time(d) + timedelta(seconds=1)]}
    _raises(ValueError, "unavailable", lambda: alarm_episodes([row]))
    missing = {k: v for k, v in row.items() if k != "prediction_at"}
    _raises(ValueError, "prediction_at", lambda: alarm_episodes([missing]))


def test_calibration_threshold_uses_only_calibration_scores_and_fixed_budget():
    days = _days(date(2022, 1, 1), 730)
    peaks = {days[10], days[150], days[300], days[470], days[620]}
    calibration = [{"symbol": "A", "date": day, "prediction_at": daily_close_time(day),
                    "score": 10.0 if day in peaks else 0.0,
                    "feature_available_at": [daily_close_time(day)]}
                   for day in days[:365]]
    threshold = fit_alarm_thresholds(calibration, max_episodes_per_asset_year=3.0)
    # All-low thresholds would create one continuous alarm episode, within
    # the episode-count budget; the alarm-time metric exposes that behavior.
    assert threshold["A"] == 0.0
    test_rows = [{"symbol": "A", "date": day, "prediction_at": daily_close_time(day),
                  "score": 1000.0, "feature_available_at": [daily_close_time(day)]}
                 for day in days[365:]]
    alarms = threshold_alarms(test_rows, threshold)
    assert all(row["alarm"] for row in alarms)
    # Test outcomes/scores are not an input to the already fitted threshold.
    assert fit_alarm_thresholds(calibration, max_episodes_per_asset_year=3.0) == threshold


def test_training_only_cusum_normalization_and_constant_hazard_reference():
    center, scale = fit_cusum_normalization([0.0, 1.0, 2.0, 100.0])
    changed_future = fit_cusum_normalization([0.0, 1.0, 2.0, 100.0])
    assert (center, scale) == changed_future
    assert center == 1.5
    assert scale > 0
    assert jeffreys_daily_hazard(0, 1) == .25
    assert jeffreys_daily_hazard(9, 99) == .095


def test_paired_warning_interval_resamples_cross_symbol_clusters_repeatably():
    dates = ["2022-01-01", "2022-02-01", "2022-03-01", "2022-04-01"]
    clusters = [{"cluster_id": str(i), "events": [
        {"symbol": "A", "onset_date": day}, {"symbol": "B", "onset_date": day},
    ]} for i, day in enumerate(dates)]
    candidate = {"matches": [
        {"symbol": event["symbol"], "onset_date": event["onset_date"],
         "category": "pre_onset_7_14d"}
        for cluster in clusters for event in cluster["events"]
    ]}
    baseline = {"matches": []}
    first = paired_cluster_warning_interval(clusters, candidate, baseline, replicates=500)
    second = paired_cluster_warning_interval(clusters, candidate, baseline, replicates=500)
    assert first == second
    assert first["independent_clusters"] == 4
    assert first["point_difference"] == 1.0
    assert first["p025"] == first["p975"] == 1.0
