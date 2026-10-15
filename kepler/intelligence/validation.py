"""Shared point-in-time targets, validation contracts and deterministic receipts for PMI V2.

Legacy ERF-01 functions are intentionally untouched; these contracts describe new
observable outcomes rather than treating the legacy proxy as economic truth.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
import math
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

UTC = timezone.utc
TARGET_STATUSES = frozenset({"OBSERVED", "UNKNOWN_GAP", "UNKNOWN_INVALID_PRICE", "RIGHT_CENSORED"})
SCIENCE_STATUSES = frozenset({
    "IMPLEMENTED", "TESTED", "EXPLORATORY", "INCONCLUSIVE",
    "DATA_BLOCKED", "NOT_RUN", "INDEPENDENTLY_VALIDATED",
})


def utc(value: datetime) -> datetime:
    """Return an aware instant normalized to UTC; reject naive timestamps."""
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def daily_close_time(day: date) -> datetime:
    """UTC close instant for a daily candle keyed by its UTC opening date."""
    if isinstance(day, datetime) or not isinstance(day, date):
        raise TypeError("day must be datetime.date, not datetime")
    return datetime.combine(day + timedelta(days=1), time.min, UTC)


@dataclass(frozen=True)
class ForecastTarget:
    symbol: str
    prediction_at: datetime
    label_start: datetime
    label_end: datetime
    value: float | None
    status: str

    def __post_init__(self):
        pred, start, end = utc(self.prediction_at), utc(self.label_start), utc(self.label_end)
        if not self.symbol:
            raise ValueError("target symbol is required")
        if start < pred or end <= start:
            raise ValueError("target window must start at/after prediction and have positive order")
        if self.status not in TARGET_STATUSES:
            raise ValueError(f"unknown target status: {self.status}")
        if self.status == "OBSERVED":
            if self.value is None or not math.isfinite(float(self.value)) or float(self.value) < 0:
                raise ValueError("observed target must have a finite non-negative value")
        elif self.value is not None:
            raise ValueError("unknown or censored target must not carry a fabricated value")
        object.__setattr__(self, "prediction_at", pred)
        object.__setattr__(self, "label_start", start)
        object.__setattr__(self, "label_end", end)
        if self.value is not None:
            object.__setattr__(self, "value", float(self.value))


@dataclass(frozen=True)
class TemporalSplit:
    train: tuple[ForecastTarget, ...]
    test: tuple[ForecastTarget, ...]
    purged: int
    unknown_train: int
    unknown_test: int


def future_realized_risk(
    symbol: str, days: Sequence[date], closes: Sequence[float], horizon_days: int = 7,
) -> list[ForecastTarget]:
    """Build future RV targets from complete consecutive UTC daily closes.

    A gap or invalid close yields UNKNOWN; an unavailable right edge yields a
    right-censored target. Neither is silently converted into a zero event.
    """
    if horizon_days < 1 or len(days) != len(closes):
        raise ValueError("positive horizon and matching daily inputs are required")
    if any(isinstance(d, datetime) or not isinstance(d, date) for d in days):
        raise TypeError("days must contain UTC date keys")
    if any(days[i] >= days[i + 1] for i in range(len(days) - 1)):
        raise ValueError("daily dates must be strictly increasing")
    prices = np.asarray(closes, dtype=np.float64)
    out: list[ForecastTarget] = []
    if not days:
        return out
    available = {day: float(price) for day, price in zip(days, prices)}
    last_day = days[-1]
    for i, day in enumerate(days):
        prediction_at = daily_close_time(day)
        label_end = prediction_at + timedelta(days=horizon_days)
        expected = [day + timedelta(days=j) for j in range(horizon_days + 1)]
        if expected[-1] > last_day:
            # Distinguish a data gap before the observed right edge from a
            # genuinely incomplete right edge; neither becomes a zero label.
            observed_prefix = [d for d in days[i:] if d <= last_day]
            expected_prefix = [d for d in expected if d <= last_day]
            status = ("UNKNOWN_GAP" if observed_prefix != expected_prefix
                      else "RIGHT_CENSORED")
            out.append(ForecastTarget(symbol, prediction_at, prediction_at, label_end,
                                      None, status))
            continue
        window_days = expected
        if any(d not in available for d in window_days):
            out.append(ForecastTarget(symbol, prediction_at, prediction_at, label_end,
                                      None, "UNKNOWN_GAP"))
            continue
        window = np.asarray([available[d] for d in window_days], dtype=np.float64)
        if not np.isfinite(window).all() or np.any(window <= 0):
            out.append(ForecastTarget(symbol, prediction_at, prediction_at, label_end,
                                      None, "UNKNOWN_INVALID_PRICE"))
            continue
        returns = np.diff(np.log(window))
        value = float(np.sqrt(np.dot(returns, returns)))
        out.append(ForecastTarget(symbol, prediction_at, prediction_at, label_end,
                                  value, "OBSERVED"))
    return out


def temporal_split(
    targets: Sequence[ForecastTarget], test_start: datetime, test_end: datetime,
) -> TemporalSplit:
    """Chronological split with strict label-maturity purge at test start."""
    start, end = utc(test_start), utc(test_end)
    if end <= start:
        raise ValueError("test_end must be after test_start")
    train, test = [], []
    purged = unknown_train = unknown_test = 0
    for row in targets:
        pred, label_end = utc(row.prediction_at), utc(row.label_end)
        if pred < start:
            if row.status != "OBSERVED":
                unknown_train += 1
            elif label_end < start:
                train.append(row)
            else:
                purged += 1
        elif start <= pred < end:
            if row.status == "OBSERVED":
                test.append(row)
            else:
                unknown_test += 1
    return TemporalSplit(tuple(train), tuple(test), purged, unknown_train, unknown_test)


def fit_quantile_threshold(
    targets: Sequence[ForecastTarget], quantile: float, *, matured_before: datetime,
) -> float:
    """Fit a target threshold only from observed labels matured before cutoff."""
    cutoff = utc(matured_before)
    if not 0 < quantile < 1:
        raise ValueError("quantile must be between zero and one")
    rows = [x for x in targets if x.status == "OBSERVED"]
    if not rows:
        raise ValueError("no observed training targets")
    if any(utc(x.prediction_at) >= cutoff or utc(x.label_end) >= cutoff for x in rows):
        raise ValueError("threshold input contains a label not mature before cutoff")
    return float(np.quantile(np.asarray([x.value for x in rows], dtype=float),
                             quantile, method="linear"))


def event_labels(targets: Sequence[ForecastTarget], threshold: float) -> np.ndarray:
    """Map observed outcomes to a frozen threshold; unknown labels are rejected."""
    if not math.isfinite(threshold) or threshold < 0:
        raise ValueError("threshold must be finite and non-negative")
    if any(x.status != "OBSERVED" for x in targets):
        raise ValueError("unknown/censored targets cannot become event negatives")
    return np.asarray([int(float(x.value) >= threshold) for x in targets], dtype=np.int8)


def asof_latest(
    observations: Iterable[tuple[datetime, Any]], prediction_at: datetime,
) -> tuple[datetime, Any] | None:
    """Return the latest value by publication time that was available as of t."""
    cutoff = utc(prediction_at)
    eligible = [(utc(published_at), value) for published_at, value in observations
                if utc(published_at) <= cutoff]
    return max(eligible, key=lambda item: item[0]) if eligible else None


def validate_prediction_window(
    prediction_at: datetime,
    feature_published_at: Iterable[datetime],
    label_start: datetime,
    label_end: datetime,
) -> None:
    """Fail closed on future information, non-UTC instants or malformed labels."""
    pred, start, end = utc(prediction_at), utc(label_start), utc(label_end)
    if any(utc(published) > pred for published in feature_published_at):
        raise ValueError("feature was published after prediction time")
    if start < pred or end <= start:
        raise ValueError("label window must begin at/after prediction time")


def trailing_log_rv_features(log_returns: Sequence[float], end_index: int) -> dict[str, float] | None:
    """Causal log RV1/RV7/RV30 at an inclusive return index."""
    if end_index < 0 or end_index >= len(log_returns):
        raise IndexError("end_index is outside the return series")
    values = np.asarray(log_returns, dtype=np.float64)
    result = {}
    for window in (1, 7, 30):
        start = end_index - window + 1
        if start < 0:
            return None
        chunk = values[start:end_index + 1]
        if len(chunk) != window or not np.isfinite(chunk).all():
            return None
        rv = float(np.sqrt(np.dot(chunk, chunk)))
        result[f"log_rv{window}"] = math.log(max(rv, 1e-12))
    return result


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False)


def deterministic_receipt(
    *, protocol_sha: str, code_sha256: Mapping[str, str],
    data_sha256: Mapping[str, str], config: Mapping[str, Any], seed: int,
    run_url: str | None = None, science_status: str = "EXPLORATORY",
) -> dict[str, Any]:
    """Build stable identity from frozen inputs; volatile Actions URL stays outside hash."""
    if science_status not in SCIENCE_STATUSES:
        raise ValueError(f"invalid science status: {science_status}")
    config_value = dict(config)
    fixed = {
        "protocol_sha": protocol_sha,
        "code_sha256": dict(sorted(code_sha256.items())),
        "data_sha256": dict(sorted(data_sha256.items())),
        "config": config_value,
        "config_sha256": hashlib.sha256(_canonical_json(config_value).encode()).hexdigest(),
        "seed": int(seed),
        "science_status": science_status,
        "economic_success": "OUT_OF_SCOPE",
        "independent_validation": "NOT_RUN",
    }
    identity = hashlib.sha256(_canonical_json(fixed).encode()).hexdigest()
    return {
        **fixed,
        "receipt_id": identity,
        "execution": {"run_url": run_url},
    }
