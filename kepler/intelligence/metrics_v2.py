"""Small, deterministic scores for new observable-target experiments."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
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
    y = np.asarray(list(outcomes), dtype=np.int8)
    p = np.asarray(list(probabilities), dtype=np.float64)
    if y.ndim != 1 or p.ndim != 1 or len(y) != len(p) or not len(y):
        raise ValueError("non-empty one-dimensional outcomes and probabilities must align")
    if not np.isin(y, (0, 1)).all():
        raise ValueError("outcomes must be binary")
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
    per_date: dict[str, list[float]] = defaultdict(list)
    for when, value in dated_differences:
        day = when.date().isoformat() if isinstance(when, datetime) else str(when)
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
    rng = np.random.default_rng(seed)
    samples = np.empty(replicates, dtype=np.float64)
    n = len(x)
    # Non-circular moving blocks preserve observed adjacency and avoid wraparound.
    starts = n - block_days + 1
    for b in range(replicates):
        pieces = []
        while sum(len(piece) for piece in pieces) < n:
            start = int(rng.integers(starts))
            pieces.append(x[start:start + block_days])
        samples[b] = np.concatenate(pieces)[:n].mean()
    return {"n_dates": n, "mean": float(x.mean()),
            "p025": float(np.quantile(samples, .025)),
            "p975": float(np.quantile(samples, .975)),
            "replicates": replicates, "block_days": block_days, "seed": seed}

