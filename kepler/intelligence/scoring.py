"""Reproducible proper scoring and date-block bootstrap uncertainty.

A model's Brier and uncertainty are defined here; its experimental label ontology
and training protocol remain explicit caller inputs.
"""
from collections import defaultdict
from datetime import date
import numpy as np

def _moving_block_ci(by_date: dict[date, float], B=2000, block=28, seed=20261014):
    ds = sorted(by_date); x = np.asarray([by_date[d] for d in ds], dtype=float)
    if len(x) < block:
        return {"n_dates": len(x), "observed": float(x.mean()), "p05": None, "p025": None, "p975": None, "replicates": 0}
    rng = np.random.default_rng(seed); reps = np.empty(B)
    n = len(x)
    for b in range(B):
        sample = []
        while len(sample) < n:
            start = int(rng.integers(0, n - block + 1))
            sample.extend(x[start:start + block])
        reps[b] = np.mean(sample[:n])
    return {"n_dates": n, "observed": float(x.mean()), "p05": float(np.quantile(reps, .05)),
            "p025": float(np.quantile(reps, .025)), "p975": float(np.quantile(reps, .975)), "replicates": B,
            "block_days": block, "seed": seed}



def summarise_forecast(records, name, paired_baseline, *, state_names):
    if not records:
        return {"n": 0, "status": "NOT_RUN"}
    actual = np.asarray([r["true"] for r in records], dtype=int)
    prob = np.asarray([r[name] for r in records], dtype=float)
    base = np.asarray([r[paired_baseline] for r in records], dtype=float)
    if prob.ndim == 2:
        onehot = np.eye(3)[actual + 1]
        delta = np.sum((base - onehot) ** 2, axis=1) - np.sum((prob - onehot) ** 2, axis=1)
        brier = float(np.mean(np.sum((prob - onehot) ** 2, axis=1)))
        baseline_brier = float(np.mean(np.sum((base - onehot) ** 2, axis=1)))
        hit = np.argmax(prob, axis=1) - 1
        base_hit = np.argmax(base, axis=1) - 1
        accuracy = float(np.mean(hit == actual))
        accuracy_baseline = float(np.mean(base_hit == actual))
        recall = {state_names[k]: float(np.mean(hit[actual == k] == k))
                  if np.any(actual == k) else None for k in STATES}
        confusion = {state_names[k]: {state_names[j]:
                     int(np.sum((actual == k) & (hit == j))) for j in STATES}
                     for k in STATES}
    else:
        delta = (base - actual) ** 2 - (prob - actual) ** 2
        brier = float(np.mean((prob - actual) ** 2))
        baseline_brier = float(np.mean((base - actual) ** 2))
        accuracy = accuracy_baseline = None
        recall = confusion = None
    by_day = defaultdict(list)
    for r, d in zip(records, delta):
        by_day[r["date"]].append(float(d))
    bootstrap = _moving_block_ci({d: float(np.mean(x)) for d, x in by_day.items()},
                                        B=1000, block=28, seed=20261015)
    return {"n": len(records), "n_distinct_dates": len(by_day),
            "brier": brier, "baseline_brier": baseline_brier,
            "baseline_minus_model_brier": baseline_brier - brier,
            "paired_block_bootstrap": bootstrap, "accuracy": accuracy,
            "baseline_accuracy": accuracy_baseline, "class_recall": recall,
            "confusion": confusion}


