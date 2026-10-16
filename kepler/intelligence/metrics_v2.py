"""Small, deterministic scores for new observable-target experiments."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
import math
from typing import Iterable, Mapping

import numpy as np


def binary_probability_scores(
    outcomes: Iterable[int], probabilities: Iterable[float], *, bins: int = 5,
) -> dict:
    """Return proper scores and fixed-width reliability summaries.

    Probabilities are clipped only at the scoring boundary. Inputs with invalid
    labels, mismatched lengths or non-finite/out-of-range probabilities fail
    closed instead of being silently dropped.
    """
    raw_y = np.asarray(list(outcomes))
    p = np.asarray(list(probabilities), dtype=np.float64)
    if raw_y.ndim != 1 or p.ndim != 1 or len(raw_y) != len(p) or not len(raw_y):
        raise ValueError("non-empty one-dimensional outcomes and probabilities must align")
    try:
        finite_y = np.isfinite(raw_y).all()
    except TypeError as exc:
        raise ValueError("outcomes must be numeric binary values") from exc
    if not finite_y or not np.isin(raw_y, (0, 1)).all():
        raise ValueError("outcomes must be binary")
    y = raw_y.astype(np.int8)
    if not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError("probabilities must be finite and in [0, 1]")
    if bins < 1:
        raise ValueError("bins must be positive")
    p = np.clip(p, 1e-6, 1 - 1e-6)
    loss = -(y * np.log(p) + (1 - y) * np.log1p(-p))
    reliability = []
    edges = np.linspace(0.0, 1.0, bins + 1)
    for i in range(bins):
        mask = (p >= edges[i]) & ((p < edges[i + 1]) if i < bins - 1 else (p <= edges[i + 1]))
        reliability.append({
            "lower": float(edges[i]), "upper": float(edges[i + 1]),
            "n": int(mask.sum()),
            "mean_probability": float(p[mask].mean()) if mask.any() else None,
            "event_rate": float(y[mask].mean()) if mask.any() else None,
        })
    event = y == 1
    predicted_event = p >= 0.5
    return {
        "n": int(len(y)), "events": int(event.sum()), "non_events": int((~event).sum()),
        "brier": float(np.mean((p - y) ** 2)), "log_loss": float(np.mean(loss)),
        "calibration_in_the_large": float(p.mean() - y.mean()),
        "precision_at_0_5": (float((event & predicted_event).sum() / predicted_event.sum())
                              if predicted_event.any() else None),
        "recall_at_0_5": (float((event & predicted_event).sum() / event.sum()) if event.any() else None),
        "reliability": reliability,
    }


def paired_date_block_interval(
    dated_differences: Iterable[tuple[date | datetime | str, float]], *,
    block_days: int = 28, replicates: int = 2000, seed: int = 20261016,
) -> dict:
    """Date-clustered moving-block interval; multiple assets share one date unit."""
    if block_days < 1 or replicates < 1:
        raise ValueError("block_days and replicates must be positive")
    per_date: dict[date, list[float]] = defaultdict(list)
    for when, value in dated_differences:
        if isinstance(when, datetime):
            day = when.date()
        elif isinstance(when, date):
            day = when
        else:
            day = date.fromisoformat(str(when))
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("paired differences must be finite")
        per_date[day].append(value)
    dates = sorted(per_date)
    x = np.asarray([np.mean(per_date[d]) for d in dates], dtype=np.float64)
    if not len(x):
        return {"n_dates": 0, "mean": None, "p025": None, "p975": None,
                "replicates": 0, "block_days": block_days, "seed": seed}
    if len(x) < block_days:
        return {"n_dates": len(x), "mean": float(x.mean()), "p025": None, "p975": None,
                "replicates": 0, "block_days": block_days, "seed": seed}
    # A block means adjacent UTC calendar days. Never bridge missing dates by
    # treating neighboring rows as adjacent observations.
    valid_starts = []
    run_start = 0
    for i in range(1, len(dates) + 1):
        if i == len(dates) or dates[i] - dates[i - 1] != timedelta(days=1):
            run_end = i
            if run_end - run_start >= block_days:
                valid_starts.extend(range(run_start, run_end - block_days + 1))
            run_start = i
    if not valid_starts:
        return {"n_dates": len(x), "mean": float(x.mean()), "p025": None, "p975": None,
                "replicates": 0, "block_days": block_days, "seed": seed}
    rng = np.random.default_rng(seed)
    samples = np.empty(replicates, dtype=np.float64)
    n = len(x)
    # Non-circular moving blocks preserve calendar adjacency and avoid wraparound.
    for b in range(replicates):
        pieces = []
        while sum(len(piece) for piece in pieces) < n:
            start = valid_starts[int(rng.integers(len(valid_starts)))]
            pieces.append(x[start:start + block_days])
        samples[b] = np.concatenate(pieces)[:n].mean()
    return {"n_dates": n, "mean": float(x.mean()),
            "p025": float(np.quantile(samples, .025)),
            "p975": float(np.quantile(samples, .975)),
            "replicates": replicates, "block_days": block_days, "seed": seed}

