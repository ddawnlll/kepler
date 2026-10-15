"""Independent ERF-01 *forecast* evidence audit; never certifies a trading edge.

This secondary gate is preregistered before any complete 2020-26 DEV run.
It adds minimum alarm support and fold/symbol diversity so one lucky alarm
cannot masquerade as useful regime forecasting. No G3 or real-money actions.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

MIN_TRUE_ALERTS = 20
MIN_PRECISION = 0.25
MIN_RECALL = 0.20
MIN_GOOD_FOLDS = 4
MIN_GOOD_SYMBOLS = 3


def assess(metrics: dict, alerts: list[dict]) -> dict:
    data = metrics.get("data", {})
    counts = metrics.get("counts", {})
    operational = metrics.get("operational_gate") or {}
    if data.get("source") != "kepler_tape" or not data.get("canonical_qc"):
        return {"status": "NOT_RUN", "reason": "canonical Kepler DEV tape + QC evidence missing"}
    if not metrics.get("forecast_gate_passed") or not operational.get("passed"):
        return {"status": "NO_EDGE_OR_INCONCLUSIVE", "reason": "frozen ERF-01 forecast gate not passed",
                "original_verdict": metrics.get("verdict")}
    expected = int(operational.get("alerts", -1))
    if len(alerts) != expected or len({(a["fold"], a["date"], a["symbol"]) for a in alerts}) != expected:
        return {"status": "INVALID", "reason": "missing/duplicated alerts; audit refuses to certify"}
    good = [r for r in alerts if str(r.get("true_alert")).lower() in ("true", "1")]
    precision = len(good) / len(alerts) if alerts else 0.0
    n_events = int(counts.get("confirmed_onsets_oos", 0))
    recall = len({(a["symbol"], a["matched_onset"]) for a in good}) / n_events if n_events > 0 else 0
    folds, symbols = Counter(a["fold"] for a in good), Counter(a["symbol"] for a in good)
    checks = {
        "confirmed_alerts": len(good) >= MIN_TRUE_ALERTS,
        "alert_precision": precision >= MIN_PRECISION,
        "onset_recall": recall >= MIN_RECALL,
        "distinct_good_folds": len(folds) >= MIN_GOOD_FOLDS,
        "distinct_good_symbols": len(symbols) >= MIN_GOOD_SYMBOLS,
    }
    return {
        "status": "FORECAST_CANDIDATE_ONLY" if all(checks.values()) else "INSUFFICIENT_OPERATIONAL_EVIDENCE",
        "checks": checks, "confirmed_alerts": len(good), "precision": precision, "recall": recall,
        "good_folds": len(folds), "good_symbols": len(symbols),
        "economic_edge": "NOT_RUN", "independent_confirmation": "NOT_RUN",
        "note": "This DEV screen cannot become a proven trading edge without locked "
                "economic referee, dependence-aware tests and independent confirmation.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("metrics", type=Path)
    parser.add_argument("alerts", type=Path)
    args = parser.parse_args()
    import csv
    with args.alerts.open(newline="", encoding="utf-8") as handle:
        alerts = list(csv.DictReader(handle))
    print(json.dumps(assess(json.loads(args.metrics.read_text(encoding="utf-8")), alerts), indent=2))


if __name__ == "__main__":
    main()
