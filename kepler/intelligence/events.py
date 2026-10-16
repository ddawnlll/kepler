"""Causal observable-event support and alarm evaluation primitives.

Events are labels on a frozen observable proxy. This module does not infer or
validate a latent economic regime, and its matching utilities never move an
event date to a later confirmation date.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import hashlib
import math
from typing import Iterable, Mapping, Sequence

import numpy as np

from kepler.intelligence.validation import UTC, utc


def _state(value) -> int | None:
    if value is None:
        return None
    try:
        raw = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("proxy states must be -1, 0, +1 or missing") from exc
    if not math.isfinite(raw):
        return None
    if raw not in (-1.0, 0.0, 1.0):
        raise ValueError("proxy states must be -1, 0, +1 or missing")
    return int(raw)


def confirmed_proxy_onsets(
    symbol: str, days: Sequence[date], states: Sequence[float | int | None], *,
    neutral_days: int = 10, confirmation_days: int = 10, minimum_same_state: int = 8,
) -> list[dict]:
    """Find neutral-to-directional proxy onsets and retain unknown censoring.

    A candidate's onset is its first non-neutral day after the required
    consecutive neutral spell. Future confirmation is a label only. A gap in
    the confirmation path is unknown, never a failed event.
    """
    if not symbol:
        raise ValueError("symbol is required")
    if len(days) != len(states):
        raise ValueError("date and proxy-state lengths disagree")
    if (isinstance(neutral_days, bool) or isinstance(confirmation_days, bool)
            or isinstance(minimum_same_state, bool) or neutral_days < 1
            or confirmation_days < 1 or not 1 <= minimum_same_state <= confirmation_days):
        raise ValueError("invalid onset window parameters")
    if any(isinstance(d, datetime) or not isinstance(d, date) for d in days):
        raise TypeError("days must be date keys, not datetimes")
    if any(days[i] >= days[i + 1] for i in range(len(days) - 1)):
        raise ValueError("days must be strictly increasing")
    q = [_state(x) for x in states]
    out = []
    for i in range(neutral_days, len(days)):
        if q[i] not in (-1, 1):
            continue
        start = i - neutral_days
        if q[start:i] != [0] * neutral_days:
            continue
        if any(days[j] + timedelta(days=1) != days[j + 1] for j in range(start, i)):
            continue
        base = {"symbol": symbol, "onset_date": days[i].isoformat(),
                "direction": "up" if q[i] == 1 else "down",
                "onset_state": q[i]}
        end = i + confirmation_days
        if end >= len(days):
            out.append({**base, "status": "RIGHT_CENSORED", "confirmation_date": None,
                        "same_state_days": None})
            continue
        following = range(i + 1, end + 1)
        if any(days[j] + timedelta(days=1) != days[j + 1] for j in range(i, end)):
            out.append({**base, "status": "UNKNOWN_GAP", "confirmation_date": None,
                        "same_state_days": None})
            continue
        path = q[i + 1:end + 1]
        if any(v is None for v in path):
            out.append({**base, "status": "UNKNOWN_GAP", "confirmation_date": None,
                        "same_state_days": None})
            continue
        same = sum(v == q[i] for v in path)
        status = "CONFIRMED" if same >= minimum_same_state else "REJECTED"
        out.append({**base, "status": status,
                    "confirmation_date": days[end].isoformat(), "same_state_days": same})
    return out


def cluster_event_dates(events: Sequence[Mapping], *, cluster_days: int = 14) -> list[dict]:
    """Collapse cross-symbol events into fixed, anchored calendar-date clusters."""
    if isinstance(cluster_days, bool) or cluster_days < 1:
        raise ValueError("cluster_days must be a positive integer")
    ordered = sorted(events, key=lambda e: (date.fromisoformat(str(e["onset_date"])),
                                           str(e["symbol"]), str(e.get("direction", ""))))
    clusters: list[list[Mapping]] = []
    for event in ordered:
        onset = date.fromisoformat(str(event["onset_date"]))
        if not clusters:
            clusters.append([event])
            continue
        first = date.fromisoformat(str(clusters[-1][0]["onset_date"]))
        if 0 <= (onset - first).days < cluster_days:
            clusters[-1].append(event)
        else:
            clusters.append([event])
    return [{"cluster_id": f"{i + 1:04d}",
             "first_onset_date": str(group[0]["onset_date"]),
             "last_onset_date": str(group[-1]["onset_date"]),
             "event_count": len(group),
             "symbols": sorted({str(e["symbol"]) for e in group}),
             "events": [dict(e) for e in group]}
            for i, group in enumerate(clusters)]


def _score_row(row: Mapping) -> tuple[str, date, float]:
    symbol = str(row.get("symbol", ""))
    day = row.get("date")
    prediction_at = row.get("prediction_at")
    if not symbol or isinstance(day, datetime) or not isinstance(day, date):
        raise ValueError("alarm score row needs a symbol and UTC date key")
    if not isinstance(prediction_at, datetime):
        raise ValueError("alarm score row needs an explicit prediction_at timestamp")
    instant = utc(prediction_at)
    expected = datetime.combine(day + timedelta(days=1), datetime.min.time(), UTC)
    if instant != expected:
        raise ValueError("daily prediction_at must equal the completed UTC close for its date key")
    available = row.get("feature_available_at", ())
    if any(utc(ts) > instant for ts in available):
        raise ValueError("an alarm feature was unavailable at its prediction time")
    raw = row.get("score")
    try:
        score = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("alarm score must be finite") from exc
    if not math.isfinite(score):
        raise ValueError("alarm score must be finite")
    return symbol, day, score


def alarm_episodes(alarm_rows: Sequence[Mapping], *, cooldown_days: int = 7) -> list[dict]:
    """Collapse thresholded alarm days by symbol using the frozen cooldown."""
    if isinstance(cooldown_days, bool) or cooldown_days < 0:
        raise ValueError("cooldown_days must be a non-negative integer")
    parsed = []
    seen = set()
    for row in alarm_rows:
        symbol, day, _ = _score_row({**row, "score": row.get("score", 0.0)})
        key = (symbol, day)
        if key in seen:
            raise ValueError("duplicate alarm score date for a symbol")
        seen.add(key)
        if not isinstance(row.get("alarm"), bool):
            raise ValueError("alarm rows require a boolean alarm value")
        if row["alarm"]:
            parsed.append((symbol, day))
    parsed.sort()
    out = []
    for symbol, day in parsed:
        if (out and out[-1]["symbol"] == symbol
                and (day - date.fromisoformat(out[-1]["last_alarm_date"])).days <= cooldown_days):
            out[-1]["last_alarm_date"] = day.isoformat()
            out[-1]["alarm_days"] += 1
        else:
            out.append({"symbol": symbol, "start_date": day.isoformat(),
                        "last_alarm_date": day.isoformat(), "alarm_days": 1})
    return out


def fit_alarm_thresholds(
    calibration_rows: Sequence[Mapping], *, max_episodes_per_asset_year: float = 3.0,
    cooldown_days: int = 7,
) -> dict[str, float]:
    """Choose the most sensitive per-symbol threshold within the calibration alarm budget.

    Only calibration scores and their exposure enter this function. Outcome
    labels are neither accepted nor inspected.
    """
    if not math.isfinite(max_episodes_per_asset_year) or max_episodes_per_asset_year < 0:
        raise ValueError("alarm budget must be finite and non-negative")
    parsed = []
    by_symbol: dict[str, list[tuple[date, float, Mapping]]] = {}
    seen = set()
    for row in calibration_rows:
        symbol, day, score = _score_row(row)
        if (symbol, day) in seen:
            raise ValueError("duplicate calibration score date for a symbol")
        seen.add((symbol, day))
        by_symbol.setdefault(symbol, []).append((day, score, row))
    thresholds = {}
    for symbol, entries in sorted(by_symbol.items()):
        entries.sort(key=lambda x: x[0])
        exposure = len(entries) / 365.25
        max_episodes = math.floor(max_episodes_per_asset_year * exposure + 1e-12)
        scores = sorted({x[1] for x in entries})
        chosen = None
        for threshold in scores:
            rows = [{**entry[2], "score": entry[1], "alarm": entry[1] >= threshold}
                    for entry in entries]
            if len(alarm_episodes(rows, cooldown_days=cooldown_days)) <= max_episodes:
                chosen = threshold
                break
        if chosen is None:
            chosen = math.nextafter(scores[-1], math.inf)
        thresholds[symbol] = float(chosen)
    return thresholds


def threshold_alarms(score_rows: Sequence[Mapping], thresholds: Mapping[str, float]) -> list[dict]:
    """Apply frozen per-symbol thresholds without learning from the scored rows."""
    out = []
    for row in score_rows:
        symbol, day, score = _score_row(row)
        threshold = thresholds.get(symbol)
        out.append({**dict(row), "alarm": bool(threshold is not None and score >= threshold)})
    return out


def cusum_14d_scores(
    days: Sequence[date], values: Sequence[float | int | None], *, center: float,
    scale: float, allowance: float = 0.5,
) -> list[float | None]:
    """Compute the fixed 14-day one-sided absolute-z20 CUSUM score causally."""
    if len(days) != len(values):
        raise ValueError("date and value lengths disagree")
    if (any(isinstance(d, datetime) or not isinstance(d, date) for d in days)
            or any(days[i] >= days[i + 1] for i in range(len(days) - 1))):
        raise ValueError("CUSUM requires strictly increasing date keys")
    if not all(math.isfinite(x) for x in (center, scale, allowance)) or scale <= 0 or allowance < 0:
        raise ValueError("CUSUM center, positive scale and allowance must be finite")
    window: list[float] = []
    result: list[float | None] = []
    last: date | None = None
    for day, raw in zip(days, values):
        if last is not None and day != last + timedelta(days=1):
            window.clear()
        last = day
        if raw is None:
            window.clear()
            result.append(None)
            continue
        value = float(raw)
        if not math.isfinite(value):
            window.clear()
            result.append(None)
            continue
        window.append((abs(value) - center) / scale - allowance)
        if len(window) > 14:
            del window[0]
        result.append(max(0.0, float(sum(window))))
    return result


def fit_cusum_normalization(training_values: Sequence[float | int | None]) -> tuple[float, float]:
    """Fit the frozen absolute-z20 median/MAD normalization on training rows."""
    values = []
    for raw in training_values:
        if raw is None:
            continue
        value = float(raw)
        if math.isfinite(value):
            values.append(abs(value))
    if not values:
        raise ValueError("CUSUM normalization requires finite training observations")
    values.sort()

    def median(xs):
        n = len(xs)
        mid = n // 2
        return xs[mid] if n % 2 else (xs[mid - 1] + xs[mid]) / 2.0

    center = median(values)
    mad = median(sorted(abs(x - center) for x in values))
    return center, max(1.4826 * mad, 1e-6)


def jeffreys_daily_hazard(event_count: int, exposure_days: int) -> float:
    """Posterior mean daily event hazard under the fixed Beta(0.5, 0.5) prior."""
    if (isinstance(event_count, bool) or isinstance(exposure_days, bool)
            or not isinstance(event_count, int) or not isinstance(exposure_days, int)
            or event_count < 0 or exposure_days < 1 or event_count > exposure_days):
        raise ValueError("event count and positive exposure must be valid integers")
    return (event_count + 0.5) / (exposure_days + 1.0)


def constant_hazard_priority(symbol: str, day: date, *, seed: int = 20261016) -> float:
    """Stable calendar-only priority for a no-information hazard alarm schedule."""
    if not symbol or isinstance(day, datetime) or not isinstance(day, date):
        raise ValueError("symbol and UTC date key are required")
    payload = f"{seed}|{symbol}|{day.isoformat()}".encode("utf-8")
    integer = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return integer / 2**64


def _category(lead_days: int) -> str | None:
    if 7 <= lead_days <= 14:
        return "pre_onset_7_14d"
    if 1 <= lead_days <= 6:
        return "near_onset_1_6d"
    if -7 <= lead_days <= 0:
        return "post_onset_0_7d"
    return None


def _match_one_symbol(events: list[Mapping], episodes: list[Mapping]) -> list[dict]:
    """Chronological one-to-one matching; primary-window matches have priority."""
    n, m = len(events), len(episodes)
    # Each DP cell stores the primary count, total matches, timing preference,
    # and its deterministic non-crossing pair path.
    empty = (0, 0, 0, ())
    dp = [[empty for _ in range(m + 1)] for _ in range(n + 1)]

    def better(a, b):
        ka = (a[0], a[1], a[2], tuple((-i, -j) for i, j, _, _ in a[3]))
        kb = (b[0], b[1], b[2], tuple((-i, -j) for i, j, _, _ in b[3]))
        return a if ka >= kb else b

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            best = better(dp[i - 1][j], dp[i][j - 1])
            onset = date.fromisoformat(str(events[i - 1]["onset_date"]))
            alarm = date.fromisoformat(str(episodes[j - 1]["start_date"]))
            lead = (onset - alarm).days
            category = _category(lead)
            if category:
                prior = dp[i - 1][j - 1]
                center2 = {"pre_onset_7_14d": 21, "near_onset_1_6d": 7,
                           "post_onset_0_7d": -7}[category]
                distance2 = abs(2 * lead - center2)
                matched = (prior[0] + (category == "pre_onset_7_14d"), prior[1] + 1,
                           prior[2] - distance2,
                           prior[3] + ((i - 1, j - 1, category, lead),))
                best = better(best, matched)
            dp[i][j] = best
    return [{"symbol": str(events[i]["symbol"]), "onset_date": str(events[i]["onset_date"]),
             "alert_start_date": str(episodes[j]["start_date"]),
             "lead_days": int(lead), "category": category}
            for i, j, category, lead in dp[n][m][3]]


def evaluate_alarm_events(
    events: Sequence[Mapping], alarm_rows: Sequence[Mapping], *, cooldown_days: int = 7,
) -> dict:
    """Score event timing, false alarms and alarm exposure on valid observed days."""
    for event in events:
        if str(event.get("status", "CONFIRMED")) != "CONFIRMED":
            raise ValueError("only confirmed observable events can be scored")
        if not event.get("symbol") or not event.get("onset_date"):
            raise ValueError("confirmed event requires symbol and onset_date")
    episodes = alarm_episodes(alarm_rows, cooldown_days=cooldown_days)
    symbols = sorted({str(e["symbol"]) for e in events} | {str(r["symbol"]) for r in alarm_rows})
    matches = []
    for symbol in symbols:
        es = sorted((e for e in events if str(e["symbol"]) == symbol),
                    key=lambda e: str(e["onset_date"]))
        aps = sorted((a for a in episodes if a["symbol"] == symbol),
                     key=lambda a: a["start_date"])
        matches.extend(_match_one_symbol(es, aps))
    used = {(m["symbol"], m["alert_start_date"]) for m in matches}
    unmatched = [a for a in episodes if (a["symbol"], a["start_date"]) not in used]
    confirmed = len(events)
    pre = [m for m in matches if m["category"] == "pre_onset_7_14d"]
    near = [m for m in matches if m["category"] == "near_onset_1_6d"]
    post = [m for m in matches if m["category"] == "post_onset_0_7d"]
    covered = {(str(r["symbol"]), r["date"]) for r in alarm_rows}
    alarmed = {(str(r["symbol"]), r["date"]) for r in alarm_rows if r["alarm"]}
    years = len(covered) / 365.25
    return {
        "confirmed_events": confirmed,
        "alarm_episodes": len(episodes),
        "matched_events_any_window": len(matches),
        "primary_warning_events": len(pre),
        "primary_warning_recall": len(pre) / confirmed if confirmed else None,
        "primary_warning_precision": len(pre) / len(episodes) if episodes else 0.0,
        "near_onset_detections": len(near),
        "post_onset_detections": len(post),
        "false_alarm_episodes": len(unmatched),
        "covered_asset_years": years,
        "false_alarm_episodes_per_asset_year": len(unmatched) / years if years else None,
        "fraction_time_in_alarm": len(alarmed) / len(covered) if covered else None,
        "primary_lead_days": sorted(int(m["lead_days"]) for m in pre),
        "near_lead_days": sorted(int(m["lead_days"]) for m in near),
        "post_lead_days": sorted(int(m["lead_days"]) for m in post),
        "matches": sorted(matches, key=lambda x: (x["onset_date"], x["symbol"])),
        "unmatched_episodes": unmatched,
    }


def paired_cluster_warning_interval(
    clusters: Sequence[Mapping], candidate_result: Mapping, baseline_result: Mapping, *,
    replicates: int = 2000, seed: int = 20261016,
) -> dict:
    """Paired percentile interval for warning-recall difference by shock cluster.

    Each 14-day cross-symbol cluster has equal weight. Within-cluster event
    fractions preserve event-level recall while avoiding an independence
    assumption across symbols exposed to a shared shock.
    """
    if isinstance(replicates, bool) or replicates < 100:
        raise ValueError("at least 100 bootstrap replicates are required")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("bootstrap seed must be an integer")

    def primary_keys(result):
        return {(str(row["symbol"]), str(row["onset_date"]))
                for row in result.get("matches", [])
                if row.get("category") == "pre_onset_7_14d"}

    candidate, baseline = primary_keys(candidate_result), primary_keys(baseline_result)
    paired = []
    seen = set()
    for cluster in clusters:
        events = cluster.get("events", ())
        keys = [(str(event["symbol"]), str(event["onset_date"])) for event in events]
        if not keys:
            continue
        if seen.intersection(keys):
            raise ValueError("an event appears in more than one bootstrap cluster")
        seen.update(keys)
        c_recall = sum(key in candidate for key in keys) / len(keys)
        b_recall = sum(key in baseline for key in keys) / len(keys)
        paired.append(c_recall - b_recall)
    if not paired:
        return {"status": "INCONCLUSIVE", "independent_clusters": 0,
                "point_difference": None, "p025": None, "p975": None,
                "replicates": replicates, "seed": seed}
    values = np.asarray(paired, dtype=np.float64)
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(values), size=(replicates, len(values)))
    draws = values[indices].mean(axis=1)
    return {"status": "TESTED" if len(values) >= 2 else "INCONCLUSIVE",
            "independent_clusters": int(len(values)),
            "point_difference": float(values.mean()),
            "p025": float(np.quantile(draws, .025)),
            "p975": float(np.quantile(draws, .975)),
            "replicates": int(replicates), "seed": int(seed),
            "resampling_unit": "anchored_14_day_cross_symbol_onset_cluster"}
