"""Observable proxy regimes, censor-aware episodes and fitted duration hazards.

No trading or experiment imports. The historical smoothing constant is frozen.
"""
import numpy as np
from datetime import timedelta

STATES = (-1, 0, 1)
SMOOTHING = 10.0

def observed_state(value) -> int | None:
    if not np.isfinite(value):
        return None
    state = int(value)
    if state not in STATES or float(value) != state:
        raise ValueError(f"unknown regime proxy state: {value}")
    return state


def spells(days, q):
    """A state changes only on observable consecutive days; gaps censor spells."""
    if len(days) != len(q):
        raise ValueError("dates and state lengths disagree")
    if any(days[i] >= days[i + 1] for i in range(len(days) - 1)):
        raise ValueError("days not strictly increasing")
    out, current, last, gap_before = [], None, None, True
    for d, raw in zip(days, q):
        state = observed_state(raw)
        contiguous = last is not None and d == last + timedelta(days=1)
        if current is not None and (state != current["state"] or not contiguous):
            # A missing day is NOT proof that a regime ended.
            current["right_censored"] = state is None or not contiguous
            out.append(current)
            current = None
        if state is not None and current is None:
            left = gap_before or not contiguous
            current = {"state": state, "start": d, "end": d,
                       "duration": 1, "left_censored": left,
                       "right_censored": False}
        elif state is not None:
            current["end"] = d
            current["duration"] += 1
        gap_before = state is None
        last = d
    if current is not None:
        current["right_censored"] = True
        out.append(current)
    return out


def spell_distribution(episodes):
    """Report uncensored distribution; never silently treat boundary spells as finished."""
    fully = np.asarray([e["duration"] for e in episodes
                        if not e["left_censored"] and not e["right_censored"]], dtype=float)
    summary = {"spells": len(episodes), "completed": int(len(fully)),
               "left_censored": sum(bool(e["left_censored"]) for e in episodes),
               "right_censored": sum(bool(e["right_censored"]) for e in episodes),
               "average_completed_days": float(fully.mean()) if len(fully) else None,
               "median_completed_days": float(np.median(fully)) if len(fully) else None,
               "p25_completed_days": float(np.quantile(fully, .25)) if len(fully) else None,
               "p75_completed_days": float(np.quantile(fully, .75)) if len(fully) else None,
               "p90_completed_days": float(np.quantile(fully, .90)) if len(fully) else None}
    return summary


def transition_matrix(panels, days, cutoff):
    """Add-one smoothed daily q transitions, strictly earlier than cutoff."""
    counts = np.ones((3, 3), dtype=float)
    for sym in panels:
        q = panels[sym]["q"]
        for i in range(len(days) - 1):
            if days[i + 1] >= cutoff:
                break
            if days[i + 1] != days[i] + timedelta(days=1):
                continue
            a, b = observed_state(q[i]), observed_state(q[i + 1])
            if a is not None and b is not None:
                counts[a + 1, b + 1] += 1
    return counts / counts.sum(axis=1, keepdims=True)


def survival_parameters(train_spells, state):
    """Discrete event hazards; right-censored episodes do not create fake exits."""
    observed = [s for s in train_spells if s["state"] == state
                and not s["left_censored"]]
    complete = [s for s in observed if not s["right_censored"]]
    # Exit at age a is observable for complete spells of length a.
    # A right-censored spell of length a has UNKNOWN next day, not failure.
    exposure = sum(s["duration"] - 1 + (not s["right_censored"])
                   for s in observed)
    base_hazard = (len(complete) + 1) / (exposure + 2)
    return observed, min(max(base_hazard, 1e-6), 1 - 1e-6)


def continuation_probability(episodes, state, age, horizon):
    """P(this exact spell persists next h days | survived age days), fitted ex ante."""
    prior_spells, prior = survival_parameters(episodes, state)
    p = 1.0
    for a in range(age, age + horizon):
        at_risk = sum(s["duration"] > a or (
            s["duration"] == a and not s["right_censored"]) for s in prior_spells)
        exits = sum(s["duration"] == a and not s["right_censored"]
                    for s in prior_spells)
        hazard = (exits + SMOOTHING * prior) / (at_risk + SMOOTHING)
        p *= 1.0 - hazard
    return float(np.clip(p, 0.0, 1.0))


