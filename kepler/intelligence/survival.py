"""Censor-aware observable-spell landmark targets and IPCW survival scores."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import math
from typing import Iterable, Sequence

import numpy as np

from kepler.intelligence.validation import daily_close_time, utc

UTC = timezone.utc
STATES = (-1, 0, 1)
SURVIVAL_STATUSES = frozenset({"OBSERVED", "UNKNOWN_GAP", "RIGHT_CENSORED"})


def _state(raw) -> int | None:
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    state = int(value)
    if state not in STATES or float(state) != value:
        raise ValueError(f"unknown observable spell state: {raw}")
    return state


@dataclass(frozen=True)
class SurvivalLandmark:
    symbol: str
    prediction_at: datetime
    label_end: datetime
    state: int
    elapsed_age: int | None
    horizon_days: int
    followup_days: int
    event_time_days: int | None
    survives_horizon: int | None
    status: str
    left_censored: bool

    def __post_init__(self):
        prediction, end = utc(self.prediction_at), utc(self.label_end)
        if not self.symbol:
            raise ValueError("survival target symbol is required")
        if self.state not in STATES:
            raise ValueError("survival target state must be -1, 0 or 1")
        if self.horizon_days < 1 or not 0 <= self.followup_days <= self.horizon_days:
            raise ValueError("invalid survival horizon/follow-up")
        if end < prediction or self.status not in SURVIVAL_STATUSES:
            raise ValueError("invalid survival label window or status")
        if self.elapsed_age is not None and self.elapsed_age < 1:
            raise ValueError("elapsed age must be positive when observed")
        if (self.elapsed_age is None) != bool(self.left_censored):
            raise ValueError("unknown elapsed age must be marked left-censored")
        if self.status == "OBSERVED":
            if self.survives_horizon not in (0, 1):
                raise ValueError("observed survival target must be binary")
            if self.survives_horizon == 0:
                if self.event_time_days is None or not 1 <= self.event_time_days <= self.horizon_days:
                    raise ValueError("observed exit needs an in-horizon event time")
                if self.followup_days != self.event_time_days:
                    raise ValueError("exit follow-up must end at its observed event")
            elif self.event_time_days is not None or self.followup_days != self.horizon_days:
                raise ValueError("observed survivor must complete the horizon without an exit")
        elif self.survives_horizon is not None or self.event_time_days is not None:
            raise ValueError("unknown/censored survival target cannot carry a fabricated outcome")
        object.__setattr__(self, "prediction_at", prediction)
        object.__setattr__(self, "label_end", end)


def build_survival_landmarks(
    symbol: str,
    days: Sequence[date],
    states: Sequence[int | float | None],
    prediction_times: Sequence[datetime],
    horizon_days: int = 14,
) -> list[SurvivalLandmark]:
    """Build causal survival landmarks; gaps censor instead of ending a spell."""
    if (isinstance(horizon_days, bool) or not isinstance(horizon_days, (int, np.integer))
            or horizon_days < 1):
        raise ValueError("survival horizon must be a positive whole number of days")
    horizon_days = int(horizon_days)
    if not symbol or len(days) != len(states) or len(days) != len(prediction_times):
        raise ValueError("symbol and matching daily state/timestamp inputs are required")
    if any(isinstance(day, datetime) or not isinstance(day, date) for day in days):
        raise TypeError("days must contain UTC date keys")
    if any(days[i] >= days[i + 1] for i in range(len(days) - 1)):
        raise ValueError("daily dates must be strictly increasing")
    timestamps = [utc(t) for t in prediction_times]
    if any(timestamps[i] != daily_close_time(days[i]) for i in range(len(days))):
        raise ValueError("prediction timestamps must be the matching UTC daily closes")
    q = [_state(raw) for raw in states]

    ages: list[int | None] = [None] * len(days)
    left_censored = [True] * len(days)
    for i, state in enumerate(q):
        if state is None:
            continue
        contiguous = i > 0 and days[i] == days[i - 1] + timedelta(days=1)
        if not contiguous or q[i - 1] is None:
            continue
        if state != q[i - 1]:
            ages[i], left_censored[i] = 1, False
        elif ages[i - 1] is not None:
            ages[i], left_censored[i] = ages[i - 1] + 1, False

    index_by_day = {day: i for i, day in enumerate(days)}
    targets = []
    for i, state in enumerate(q):
        if state is None:
            continue
        prediction = timestamps[i]
        followup, event_time, survives, status = 0, None, None, "RIGHT_CENSORED"
        label_end = prediction
        for offset in range(1, horizon_days + 1):
            future_day = days[i] + timedelta(days=offset)
            j = index_by_day.get(future_day)
            if j is None or q[j] is None:
                # The state is known only through the last consecutive close.
                followup = offset - 1
                label_end = prediction + timedelta(days=followup)
                status = "UNKNOWN_GAP" if j is not None or future_day <= days[-1] else "RIGHT_CENSORED"
                break
            if q[j] != state:
                followup, event_time, survives, status = offset, offset, 0, "OBSERVED"
                label_end = timestamps[j]
                break
            followup = offset
            label_end = timestamps[j]
            if offset == horizon_days:
                survives, status = 1, "OBSERVED"
        targets.append(SurvivalLandmark(
            symbol=symbol, prediction_at=prediction, label_end=label_end, state=state,
            elapsed_age=ages[i], horizon_days=horizon_days, followup_days=followup,
            event_time_days=event_time, survives_horizon=survives, status=status,
            left_censored=left_censored[i],
        ))
    return targets


def fit_delayed_entry_censor_curve(
    training: Iterable[SurvivalLandmark], *, through_age: int,
) -> dict[int, dict[str, float]]:
    """Fit a reverse-KM observation-censor curve with left-truncated risk sets.

    State exits are treated as competing observed endpoints, not losses to
    observation. Only gaps and the right edge reduce the observation-survival
    function. Inputs must be one-day risk rows: passing multi-day landmarks
    would count the same spell repeatedly in the censor risk set. The caller
    must pass training-fold records only.
    """
    if (isinstance(through_age, bool) or not isinstance(through_age, (int, np.integer))
            or through_age < 1):
        raise ValueError("through_age must be a positive whole number of days")
    rows = list(training)
    if any(r.horizon_days != 1 for r in rows):
        raise ValueError("censor curve requires one-day training risk rows")
    rows = [r for r in rows if r.elapsed_age is not None]
    g = 1.0
    curve = {0: {"survival": 1.0, "risk": 0.0, "censors": 0.0}}
    for age in range(1, through_age + 1):
        at_risk = [r for r in rows
                   if r.elapsed_age < age <= r.elapsed_age + max(1, r.followup_days)]
        censored = [r for r in at_risk if r.status in {"UNKNOWN_GAP", "RIGHT_CENSORED"}
                    and r.elapsed_age + max(1, r.followup_days) == age]
        if at_risk:
            g *= 1.0 - len(censored) / len(at_risk)
        curve[age] = {"survival": float(max(g, 0.0)), "risk": float(len(at_risk)),
                      "censors": float(len(censored))}
    return curve


def ipcw_survival_scores(
    targets: Sequence[SurvivalLandmark],
    survival_probabilities: Sequence[float],
    censor_curve: dict[int, dict[str, float]],
    *,
    bins: int = 5,
    minimum_effective_n: float = 0.0,
) -> dict:
    """IPCW Brier/calibration on observed-onset landmarks with delayed entry."""
    p = np.asarray(survival_probabilities, dtype=np.float64)
    if p.ndim != 1 or len(p) != len(targets) or not len(p):
        raise ValueError("non-empty survival probabilities must align with targets")
    if not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError("survival probabilities must be finite and in [0, 1]")
    if bins < 1 or minimum_effective_n < 0:
        raise ValueError("invalid reliability bins or effective support threshold")
    contributions = []
    censored_before_horizon = left_censored = zero_weight = 0
    max_weight = 0.0
    for target, probability in zip(targets, p):
        if target.elapsed_age is None or target.left_censored:
            left_censored += 1
            continue
        if target.status != "OBSERVED":
            if target.followup_days < target.horizon_days:
                censored_before_horizon += 1
            continue
        # For an observed exit, use G(T-) because the exit was observed at T;
        # for a survivor, observation is required through the horizon close.
        elapsed_end = target.elapsed_age + (
            target.event_time_days - 1 if target.survives_horizon == 0
            else target.horizon_days)
        g_entry = censor_curve.get(target.elapsed_age, {}).get("survival", 0.0)
        g_end = censor_curve.get(elapsed_end, {}).get("survival", 0.0)
        ratio = g_end / g_entry if g_entry > 0 else 0.0
        if not math.isfinite(ratio) or ratio <= 0:
            zero_weight += 1
            continue
        weight = 1.0 / ratio
        max_weight = max(max_weight, weight)
        contributions.append((float(probability), int(target.survives_horizon), weight,
                              target.prediction_at.date().isoformat()))
    if not contributions:
        return {"n_scored": 0, "brier": None, "effective_n": 0.0,
                "minimum_effective_n": float(minimum_effective_n), "support_adequate": False,
                "n_left_censored": left_censored,
                "n_censored_before_horizon": censored_before_horizon,
                "n_zero_weight": zero_weight, "max_ipcw_weight": None,
                "calibration_in_the_large": None, "reliability": []}
    weights = np.asarray([r[2] for r in contributions], dtype=np.float64)
    probabilities = np.asarray([r[0] for r in contributions], dtype=np.float64)
    outcomes = np.asarray([r[1] for r in contributions], dtype=np.float64)
    effective_n = float(weights.sum() ** 2 / np.square(weights).sum())
    edges = np.linspace(0, 1, bins + 1)
    reliability = []
    for i in range(bins):
        mask = ((probabilities >= edges[i]) &
                ((probabilities < edges[i + 1]) if i < bins - 1 else
                 (probabilities <= edges[i + 1])))
        selected_weight = weights[mask]
        total = float(selected_weight.sum())
        reliability.append({
            "lower": float(edges[i]), "upper": float(edges[i + 1]),
            "n": int(mask.sum()), "weight_sum": total,
            "mean_probability": (float(np.dot(selected_weight, probabilities[mask]) / total)
                                 if total else None),
            "survival_rate": (float(np.dot(selected_weight, outcomes[mask]) / total)
                              if total else None),
        })
    return {
        "n_scored": len(contributions),
        "brier": float(np.dot(weights, np.square(probabilities - outcomes)) / weights.sum()),
        "effective_n": effective_n,
        "minimum_effective_n": float(minimum_effective_n),
        "support_adequate": effective_n >= minimum_effective_n,
        "n_left_censored": left_censored,
        "n_censored_before_horizon": censored_before_horizon,
        "n_zero_weight": zero_weight,
        "max_ipcw_weight": max_weight,
        "calibration_in_the_large": float(np.dot(weights, probabilities - outcomes) / weights.sum()),
        "reliability": reliability,
    }

