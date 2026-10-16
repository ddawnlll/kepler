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
HAZARD_FAMILIES = frozenset({"state_age_blind", "age_only", "market_only", "market_plus_age"})
MARKET_FEATURES = ("log_rv1", "log_rv7", "log_rv30")


def _state(raw) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, (bool, np.bool_)):
        raise ValueError("boolean values are not observable spell states")
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
        if isinstance(self.state, bool) or not isinstance(self.state, (int, np.integer)) or self.state not in STATES:
            raise ValueError("survival target state must be -1, 0 or 1")
        if (isinstance(self.horizon_days, bool)
                or not isinstance(self.horizon_days, (int, np.integer))
                or isinstance(self.followup_days, bool)
                or not isinstance(self.followup_days, (int, np.integer))
                or self.horizon_days < 1 or not 0 <= self.followup_days <= self.horizon_days):
            raise ValueError("invalid survival horizon/follow-up")
        if end < prediction or self.status not in SURVIVAL_STATUSES:
            raise ValueError("invalid survival label window or status")
        if (self.elapsed_age is not None and (isinstance(self.elapsed_age, bool)
                or not isinstance(self.elapsed_age, (int, np.integer)) or self.elapsed_age < 1)):
            raise ValueError("elapsed age must be positive when observed")
        if (self.elapsed_age is None) != bool(self.left_censored):
            raise ValueError("unknown elapsed age must be marked left-censored")
        if self.status == "OBSERVED":
            if (isinstance(self.survives_horizon, bool)
                    or not isinstance(self.survives_horizon, (int, np.integer))
                    or self.survives_horizon not in (0, 1)):
                raise ValueError("observed survival target must be binary")
            if self.survives_horizon == 0:
                if (self.event_time_days is None or isinstance(self.event_time_days, bool)
                        or not isinstance(self.event_time_days, (int, np.integer))
                        or not 1 <= self.event_time_days <= self.horizon_days):
                    raise ValueError("observed exit needs an in-horizon event time")
                if self.followup_days != self.event_time_days:
                    raise ValueError("exit follow-up must end at its observed event")
            elif self.event_time_days is not None or self.followup_days != self.horizon_days:
                raise ValueError("observed survivor must complete the horizon without an exit")
        elif self.survives_horizon is not None or self.event_time_days is not None:
            raise ValueError("unknown/censored survival target cannot carry a fabricated outcome")
        object.__setattr__(self, "prediction_at", prediction)
        object.__setattr__(self, "label_end", end)


@dataclass(frozen=True)
class DiscreteHazardModel:
    """Fixed-candidate one-day exit hazard fitted on a training risk set."""

    family: str
    feature_names: tuple[str, ...]
    coefficients: tuple[float, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    state_hazards: tuple[tuple[int, float], ...]
    n_fit: int
    n_exits: int
    n_censored: int
    n_left_censored: int
    l2: float = 1.0


def _hazard_row_features(state: int, age: int, market: Sequence[float], family: str) -> np.ndarray:
    if (isinstance(state, bool) or not isinstance(state, (int, np.integer))
            or state not in STATES or isinstance(age, bool)
            or not isinstance(age, (int, np.integer)) or age < 1):
        raise ValueError("hazard prediction needs a valid state and positive elapsed age")
    market = np.asarray(market, dtype=np.float64)
    if market.shape != (3,) or not np.isfinite(market).all():
        raise ValueError("market features must be finite logRV1/logRV7/logRV30 values")
    state_indicators = np.asarray([float(state == candidate) for candidate in STATES])
    parts = [np.asarray([1.0]), state_indicators]
    if family in {"age_only", "market_plus_age"}:
        parts.append(np.asarray([math.log1p(age)]))
    if family in {"market_only", "market_plus_age"}:
        parts.append(market)
    return np.concatenate(parts)


def fit_discrete_hazard(
    rows: Sequence[SurvivalLandmark],
    market_conditions: Sequence[Sequence[float]],
    *,
    family: str,
    matured_before: datetime,
    feature_available_times: Sequence[datetime],
) -> DiscreteHazardModel:
    """Fit one frozen H2 daily hazard candidate on known-onset training rows.

    The four candidate names and ridge strength match the H2 preregistration.
    Censored outcomes and unknown-onset spells are excluded, not imputed. The
    continuous features are standardized on the retained fit rows only.
    """
    if family not in HAZARD_FAMILIES:
        raise ValueError(f"unknown frozen hazard family: {family}")
    cutoff = utc(matured_before)
    if (len(rows) != len(market_conditions) or len(rows) != len(feature_available_times)
            or not rows):
        raise ValueError("market conditions and availability times must align with risk rows")
    if any(row.horizon_days != 1 for row in rows):
        raise ValueError("discrete hazard fitting requires one-day risk rows")
    if any(row.label_end >= cutoff for row in rows):
        raise ValueError("training risk rows must mature strictly before the cutoff")
    available_times = [utc(when) for when in feature_available_times]
    if any(available > row.prediction_at for row, available in zip(rows, available_times)):
        raise ValueError("training market features were published after their prediction time")
    market = np.asarray(market_conditions, dtype=np.float64)
    if market.shape != (len(rows), 3):
        raise ValueError("market conditions must have logRV1/logRV7/logRV30 columns")
    if not np.isfinite(market).all():
        raise ValueError("market conditions must be finite")

    retained = [i for i, row in enumerate(rows)
                if row.elapsed_age is not None and row.status == "OBSERVED"]
    if not retained:
        raise ValueError("no known-onset observed outcomes in training risk rows")
    selected = [rows[i] for i in retained]
    selected_market = market[retained]
    outcomes = np.asarray([1 - int(row.survives_horizon) for row in selected], dtype=np.float64)
    n_exits = int(outcomes.sum())
    n_left_censored = sum(row.elapsed_age is None for row in rows)
    n_censored = sum(row.elapsed_age is not None and row.status != "OBSERVED" for row in rows)

    if family == "state_age_blind":
        hazards = []
        for state in STATES:
            state_rows = [int(row.survives_horizon) for row in selected if row.state == state]
            # Jeffreys Beta(1/2, 1/2) smoothing keeps empty/small state cells finite.
            exits = len(state_rows) - sum(state_rows)
            hazard = (exits + 0.5) / (len(state_rows) + 1.0)
            hazards.append((state, float(hazard)))
        return DiscreteHazardModel(
            family, (), (), (), (), tuple(hazards), len(selected), n_exits,
            n_censored, n_left_censored, 1.0)

    feature_names = [f"state_{state}" for state in STATES]
    if family in {"age_only", "market_plus_age"}:
        feature_names.append("log1p_elapsed_age")
    if family in {"market_only", "market_plus_age"}:
        feature_names.extend(MARKET_FEATURES)

    raw = np.vstack([
        _hazard_row_features(row.state, row.elapsed_age, selected_market[i], family)[1:]
        for i, row in enumerate(selected)
    ])
    means = np.zeros(raw.shape[1], dtype=np.float64)
    scales = np.ones(raw.shape[1], dtype=np.float64)
    # State indicators are not standardized; only continuous covariates use fit-only moments.
    continuous_start = 3
    if family in {"age_only", "market_plus_age"}:
        continuous_start = 3
    for column in range(continuous_start, raw.shape[1]):
        means[column] = raw[:, column].mean()
        scale = raw[:, column].std()
        scales[column] = scale if np.isfinite(scale) and scale > 0 else 1.0
    design = np.column_stack((np.ones(len(raw)), (raw - means) / scales))

    # Convex ridge logistic loss, fixed L2=1 and fixed Newton solver.
    penalty = np.eye(design.shape[1], dtype=np.float64)
    theta = np.zeros(design.shape[1], dtype=np.float64)
    prevalence = float(np.clip(outcomes.mean(), 1e-6, 1 - 1e-6))
    theta[0] = math.log(prevalence / (1.0 - prevalence))
    for _ in range(100):
        logits = np.clip(design @ theta, -40.0, 40.0)
        probabilities = 1.0 / (1.0 + np.exp(-logits))
        gradient = design.T @ (probabilities - outcomes) + theta
        weights = probabilities * (1.0 - probabilities)
        hessian = (design.T * weights) @ design + penalty
        step = np.linalg.solve(hessian, gradient)
        theta -= step
        if np.max(np.abs(step)) < 1e-9:
            break
    return DiscreteHazardModel(
        family=family,
        feature_names=tuple(feature_names),
        coefficients=tuple(float(value) for value in theta),
        means=tuple(float(value) for value in means),
        scales=tuple(float(value) for value in scales),
        state_hazards=(), n_fit=len(selected), n_exits=n_exits,
        n_censored=n_censored, n_left_censored=n_left_censored, l2=1.0,
    )


def predict_one_day_exit_hazard(
    model: DiscreteHazardModel, *, state: int, elapsed_age: int,
    market_conditions: Sequence[float],
) -> float:
    """Predict a one-day state exit probability from an explicit model."""
    if model.family not in HAZARD_FAMILIES:
        raise ValueError(f"unknown fitted hazard family: {model.family}")
    if model.family == "state_age_blind":
        mapping = dict(model.state_hazards)
        if state not in mapping:
            raise ValueError("age-blind hazard model is missing the requested state")
        return mapping[state]
    raw = _hazard_row_features(state, elapsed_age, market_conditions, model.family)[1:]
    standardized = (raw - np.asarray(model.means)) / np.asarray(model.scales)
    design = np.concatenate(([1.0], standardized))
    logit = float(np.clip(design @ np.asarray(model.coefficients), -40.0, 40.0))
    return float(np.clip(1.0 / (1.0 + math.exp(-logit)), 1e-6, 1 - 1e-6))


def forecast_remaining_survival(
    model: DiscreteHazardModel,
    *,
    state: int,
    elapsed_age: int,
    market_conditions: Sequence[float],
    prediction_at: datetime,
    feature_available_at: datetime,
    horizon_days: int = 14,
) -> dict:
    """Forecast uninterrupted survival with explicit as-of timing.

    Current market conditions are held fixed over the forecast and elapsed age
    advances one day per hazard, matching the frozen H2 candidate definition.
    """
    prediction_at = utc(prediction_at)
    feature_available_at = utc(feature_available_at)
    if model.family not in HAZARD_FAMILIES:
        raise ValueError(f"unknown fitted hazard family: {model.family}")
    if feature_available_at > prediction_at:
        raise ValueError("market features were published after the prediction timestamp")
    if (isinstance(horizon_days, bool) or not isinstance(horizon_days, (int, np.integer))
            or horizon_days < 1):
        raise ValueError("survival forecast horizon must be a positive whole number of days")
    if (isinstance(elapsed_age, bool) or not isinstance(elapsed_age, (int, np.integer))
            or elapsed_age < 1 or isinstance(state, bool)
            or not isinstance(state, (int, np.integer)) or state not in STATES):
        raise ValueError("survival forecast needs a valid observable state and positive age")
    horizon_days = int(horizon_days)
    ages = np.arange(elapsed_age, elapsed_age + horizon_days, dtype=np.float64)
    if model.family == "state_age_blind":
        mapping = dict(model.state_hazards)
        if state not in mapping:
            raise ValueError("age-blind hazard model is missing the requested state")
        daily_hazards = np.full(horizon_days, mapping[state], dtype=np.float64)
    else:
        market = np.asarray(market_conditions, dtype=np.float64)
        if market.shape != (3,) or not np.isfinite(market).all():
            raise ValueError("market features must be finite logRV1/logRV7/logRV30 values")
        raw_columns = [np.full(horizon_days, float(state == candidate)) for candidate in STATES]
        if model.family in {"age_only", "market_plus_age"}:
            raw_columns.append(np.log1p(ages))
        if model.family in {"market_only", "market_plus_age"}:
            raw_columns.extend(np.full(horizon_days, value) for value in market)
        raw = np.column_stack(raw_columns)
        standardized = (raw - np.asarray(model.means)) / np.asarray(model.scales)
        design = np.column_stack((np.ones(horizon_days), standardized))
        logits = np.clip(design @ np.asarray(model.coefficients), -40.0, 40.0)
        daily_hazards = np.clip(1.0 / (1.0 + np.exp(-logits)), 1e-6, 1 - 1e-6)
    survival_path = np.cumprod(1.0 - daily_hazards)
    survival = float(survival_path[-1])
    return {
        "family": model.family,
        "prediction_at": prediction_at.isoformat(),
        "feature_available_at": feature_available_at.isoformat(),
        "state": int(state), "elapsed_age": int(elapsed_age),
        "horizon_days": int(horizon_days),
        "survival_probability": survival,
        "daily_exit_hazards": daily_hazards.tolist(),
    }


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
                status = "UNKNOWN_GAP" if j is not None or future_day <= days[-1] else "RIGHT_CENSORED"
                # The absence is only knowable at the scheduled future close;
                # do not let an adjacent fold train on the censoring outcome
                # before that timestamp.
                label_end = (prediction + timedelta(days=offset) if status == "UNKNOWN_GAP"
                             else prediction + timedelta(days=followup))
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
    training: Iterable[SurvivalLandmark], *, through_age: int, matured_before: datetime,
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
    cutoff = utc(matured_before)
    if any(r.horizon_days != 1 for r in rows):
        raise ValueError("censor curve requires one-day training risk rows")
    if any(r.label_end >= cutoff for r in rows):
        raise ValueError("censor risk rows must mature strictly before the cutoff")
    rows = [r for r in rows if r.elapsed_age is not None]
    risk_counts: dict[int, int] = defaultdict(int)
    censor_counts: dict[int, int] = defaultdict(int)
    for row in rows:
        # One-day intervals enter at attained age + 1, whether the next close
        # is observed or is the first missing close. This is the delayed-entry
        # reverse-KM risk set for the observation process.
        attained_age = int(row.elapsed_age) + 1
        risk_counts[attained_age] += 1
        if row.status in {"UNKNOWN_GAP", "RIGHT_CENSORED"}:
            censor_counts[attained_age] += 1
    g = 1.0
    curve = {0: {"survival": 1.0, "risk": 0.0, "censors": 0.0}}
    for age in range(1, through_age + 1):
        at_risk = risk_counts[age]
        censored = censor_counts[age]
        if at_risk:
            g *= 1.0 - censored / at_risk
        curve[age] = {"survival": float(max(g, 0.0)), "risk": float(at_risk),
                      "censors": float(censored)}
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
                "n_zero_weight": zero_weight, "n_exits": 0, "n_survivors": 0,
                "weight_sum": 0.0, "weight_square_sum": 0.0,
                "n_zero_weight": zero_weight, "max_ipcw_weight": None,
                "calibration_in_the_large": None, "reliability": [],
                "date_brier": {}, "date_weight_sum": {}}
    weights = np.asarray([r[2] for r in contributions], dtype=np.float64)
    probabilities = np.asarray([r[0] for r in contributions], dtype=np.float64)
    outcomes = np.asarray([r[1] for r in contributions], dtype=np.float64)
    effective_n = float(weights.sum() ** 2 / np.square(weights).sum())
    date_weighted_losses: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for probability, outcome, weight, day in contributions:
        date_weighted_losses[day][0] += weight * (probability - outcome) ** 2
        date_weighted_losses[day][1] += weight
    date_brier = {day: loss / weight for day, (loss, weight) in sorted(date_weighted_losses.items())}
    date_weight_sum = {day: weight for day, (_loss, weight) in sorted(date_weighted_losses.items())}
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
        "n_exits": int(np.sum(outcomes == 0.0)),
        "n_survivors": int(np.sum(outcomes == 1.0)),
        "brier": float(np.dot(weights, np.square(probabilities - outcomes)) / weights.sum()),
        "effective_n": effective_n,
        "weight_sum": float(weights.sum()),
        "weight_square_sum": float(np.square(weights).sum()),
        "minimum_effective_n": float(minimum_effective_n),
        "support_adequate": effective_n >= minimum_effective_n,
        "n_left_censored": left_censored,
        "n_censored_before_horizon": censored_before_horizon,
        "n_zero_weight": zero_weight,
        "max_ipcw_weight": max_weight,
        "calibration_in_the_large": float(np.dot(weights, probabilities - outcomes) / weights.sum()),
        "reliability": reliability, "date_brier": date_brier,
        "date_weight_sum": date_weight_sum,
    }

