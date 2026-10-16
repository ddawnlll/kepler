"""PMI-H5 preregistered support-only census for observable q-v1 onsets."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from kepler.intelligence.events import cluster_event_dates, confirmed_proxy_onsets
from kepler.intelligence.validation import daily_close_time, deterministic_receipt

UTC = timezone.utc
PROTOCOL_SHA = "2755a7709eb1e84814c9b99237a88e73c6ec549c"
PROTOCOL_FILE_SHA256 = "10c79bee4b0dd57a202d8ffa79133dd2439f59a1459da33b0747a66d7f5878a5"
MIN_INDEPENDENT_CLUSTERS = 30
MIN_FOLDS_WITH_EVENTS = 4


def _write_result(out_dir: Path, metrics: dict, events: list[dict], manifest: dict) -> dict:
    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    with (out_dir / "events.jsonl").open("w", encoding="utf-8") as handle:
        for row in events:
            handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return metrics


def _within_fold_support(event: dict, event_day: date, q_by_day: dict[date, float | None],
                         fold_start: date, fold_end: date, seal: date) -> bool:
    if not (fold_start <= event_day < fold_end):
        return False
    if event_day - timedelta(days=14) < fold_start:
        return False
    if event.get("status") != "CONFIRMED" or event.get("confirmation_date") is None:
        return False
    seal_at = datetime.combine(seal, datetime.min.time(), UTC)
    if daily_close_time(event_day) >= seal_at:
        return False
    confirmation = date.fromisoformat(event["confirmation_date"])
    if daily_close_time(confirmation) >= seal_at:
        return False
    # Require every primary-window origin to have a valid observable q-state.
    for lead in range(14, 6, -1):
        origin = event_day - timedelta(days=lead)
        value = q_by_day.get(origin)
        if value is None or not np.isfinite(value):
            return False
    return True


def run_support_census(staging: Path, out_dir: Path, *, run_url: str | None = None) -> dict:
    """Count frozen q-v1 onset support; deliberately do not score warning models."""
    protocol_file = Path(__file__).resolve().parents[2] / "reports" / "pmi_h5_protocol.md"
    if hashlib.sha256(protocol_file.read_bytes()).hexdigest() != PROTOCOL_FILE_SHA256:
        raise RuntimeError("H5 protocol differs from its frozen pre-census content")
    if out_dir.exists():
        raise FileExistsError(f"H5 output already exists: {out_dir}")
    from experiments.erf01.pipeline import DAYS, FOLDS, SEAL, SYMS, make_panel
    from experiments.erf01.tape_adapter import load_development
    from kepler.intelligence.validation import UTC as VALIDATION_UTC

    start_clock = time.monotonic()
    try:
        prices, funding, _, qc, acquisition = load_development(
            staging, SYMS, DAYS[0], DAYS[1], SEAL)
        days, panel = make_panel(prices, funding)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        result = {
            "experiment": "PMI-H5", "science_status": "DATA_BLOCKED",
            "support_gate": "NOT_RUN", "scored_status": "NOT_RUN",
            "reason": f"canonical source preflight failed: {type(exc).__name__}: {exc}",
            "warning_scores_emitted": False,
        }
        return _write_result(out_dir, result, [], {
            "experiment": "PMI-H5-support-census", "protocol_sha": PROTOCOL_SHA,
            "protocol_file_sha256": PROTOCOL_FILE_SHA256, "run_url": run_url,
        })
    if VALIDATION_UTC != timezone.utc:
        raise RuntimeError("validation UTC contract differs from H5 runner")
    if SEAL != date(2026, 4, 1):
        raise RuntimeError("H5 requires the frozen exclusive 2026-04-01 seal")

    event_rows: list[dict] = []
    fold_definitions = [{"start": a.isoformat(), "end_exclusive": b.isoformat(), "name": name}
                        for a, b, name in FOLDS]
    for symbol in SYMS:
        q = panel[symbol]["q"]
        seal_at = datetime.combine(SEAL, datetime.min.time(), UTC)
        states = [float(v) if np.isfinite(v) and daily_close_time(day) < seal_at else None
                  for day, v in zip(days, q)]
        candidates = confirmed_proxy_onsets(symbol, days, states)
        q_by_day = {d: (float(v) if state is not None else None)
                    for d, v, state in zip(days, q, states)}
        for row in candidates:
            onset = date.fromisoformat(row["onset_date"])
            fold = next((name for start, end, name in FOLDS if start <= onset < end), None)
            if fold is None:
                continue
            fold_start, fold_end, _ = next(x for x in FOLDS if x[2] == fold)
            record = {**row, "fold": fold,
                      "oos_event": row["status"] == "CONFIRMED",
                      "support_eligible": False}
            record["support_eligible"] = _within_fold_support(
                row, onset, q_by_day, fold_start, fold_end, SEAL)
            event_rows.append(record)

    eligible = [r for r in event_rows if r["support_eligible"]]
    clusters = cluster_event_dates(eligible, cluster_days=14)
    folds_with_events = sorted({str(e["fold"]) for c in clusters for e in c["events"]})
    counts_by_fold = {}
    for _, _, name in FOLDS:
        fold_rows = [r for r in event_rows if r["fold"] == name]
        fold_events = [r for r in eligible if r["fold"] == name]
        fold_clusters = [c for c in clusters if any(e["fold"] == name for e in c["events"])]
        counts_by_fold[name] = {
            "candidates": len(fold_rows),
            "confirmed": sum(r["status"] == "CONFIRMED" for r in fold_rows),
            "rejected": sum(r["status"] == "REJECTED" for r in fold_rows),
            "unknown_gap": sum(r["status"] == "UNKNOWN_GAP" for r in fold_rows),
            "right_censored": sum(r["status"] == "RIGHT_CENSORED" for r in fold_rows),
            "support_eligible_confirmed": len(fold_events),
            "support_eligible_by_direction": {
                direction: sum(r["direction"] == direction for r in fold_events)
                for direction in ("up", "down")},
            "independent_clusters_touching_fold": len(fold_clusters),
        }
    by_symbol = {}
    for symbol in SYMS:
        rows = [r for r in event_rows if r["symbol"] == symbol]
        by_symbol[symbol] = {
            "candidates": len(rows),
            "confirmed": sum(r["status"] == "CONFIRMED" for r in rows),
            "rejected": sum(r["status"] == "REJECTED" for r in rows),
            "unknown_gap": sum(r["status"] == "UNKNOWN_GAP" for r in rows),
            "right_censored": sum(r["status"] == "RIGHT_CENSORED" for r in rows),
            "support_eligible_confirmed": sum(r["support_eligible"] for r in rows),
            "support_eligible_by_direction": {
                direction: sum(r["support_eligible"] and r["direction"] == direction for r in rows)
                for direction in ("up", "down")},
        }
    by_year = {}
    for year in sorted({r["onset_date"][:4] for r in event_rows}):
        rows = [r for r in event_rows if r["onset_date"].startswith(year)]
        by_year[year] = {
            "candidates": len(rows),
            "confirmed": sum(r["status"] == "CONFIRMED" for r in rows),
            "rejected": sum(r["status"] == "REJECTED" for r in rows),
            "unknown_gap": sum(r["status"] == "UNKNOWN_GAP" for r in rows),
            "right_censored": sum(r["status"] == "RIGHT_CENSORED" for r in rows),
            "support_eligible_confirmed": sum(r["support_eligible"] for r in rows),
            "support_eligible_by_direction": {
                direction: sum(r["support_eligible"] and r["direction"] == direction for r in rows)
                for direction in ("up", "down")},
        }
    directional = {direction: sum(r["support_eligible"] and r["direction"] == direction
                                  for r in event_rows) for direction in ("up", "down")}
    gate_passed = len(clusters) >= MIN_INDEPENDENT_CLUSTERS and len(folds_with_events) >= MIN_FOLDS_WITH_EVENTS
    data_hashes = {f"{x['symbol']}/{x['kind']}": x["sha256"] for x in acquisition["records"]}
    root = Path(__file__).resolve().parents[2]
    code_paths = [Path(__file__), root / "kepler/intelligence/events.py",
                  root / "kepler/intelligence/features.py", root / "experiments/erf01/pipeline.py",
                  root / "experiments/erf01/tape_adapter.py"]
    code_hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in code_paths}
    config = {"experiment": "PMI-H5-support-only", "symbols": SYMS,
              "folds": fold_definitions, "neutral_days": 10,
              "confirmation_days": 10, "minimum_same_state": 8,
              "primary_lead_days_inclusive": [7, 14],
              "independent_cluster_days": 14,
              "minimum_independent_clusters": MIN_INDEPENDENT_CLUSTERS,
              "minimum_folds_with_events": MIN_FOLDS_WITH_EVENTS,
              "seal_exclusive": SEAL.isoformat(), "warning_scores_emitted": False}
    receipt = deterministic_receipt(
        protocol_sha=PROTOCOL_SHA, code_sha256=code_hashes,
        data_sha256=data_hashes, config=config, seed=20261016,
        run_url=run_url, science_status="EXPLORATORY")
    findings = [f for symbol in SYMS for f in qc[symbol]["qc_findings"]]
    result = {
        "experiment": "PMI-H5", "science_status": "EXPLORATORY",
        "support_gate": "ELIGIBLE_FOR_SCORED_PHASE" if gate_passed else "INCONCLUSIVE",
        "scored_status": "NOT_RUN", "warning_scores_emitted": False,
        "gate_definition": {"minimum_independent_clusters": MIN_INDEPENDENT_CLUSTERS,
                            "minimum_folds_with_events": MIN_FOLDS_WITH_EVENTS,
                            "observed_independent_clusters": len(clusters),
                            "observed_folds_with_events": folds_with_events},
        "ontology": "frozen observable q_v1_proxy; technical state, not latent economic regime",
        "candidate_counts": {
            "oos_candidates": len(event_rows),
            "confirmed": sum(r["status"] == "CONFIRMED" for r in event_rows),
            "rejected": sum(r["status"] == "REJECTED" for r in event_rows),
            "unknown_gap": sum(r["status"] == "UNKNOWN_GAP" for r in event_rows),
            "right_censored": sum(r["status"] == "RIGHT_CENSORED" for r in event_rows),
            "support_eligible_confirmed": len(eligible),
            "support_eligible_by_direction": directional,
            "support_eligible_independent_clusters": len(clusters),
        },
        "by_fold": counts_by_fold, "by_year": by_year, "by_symbol": by_symbol,
        "independent_clusters": clusters,
        "source_validation": {"status": "ERROR_FREE_WITH_FINDINGS_PRESERVED",
                              "seal_exclusive": SEAL.isoformat(),
                              "source_record_count": len(acquisition["records"]),
                              "source_bytes": acquisition["source_bytes"],
                              "qc_findings": {severity: sum(x["severity"] == severity for x in findings)
                                              for severity in ("ERROR", "WARN", "INFO")}},
        "receipt": receipt, "runtime_seconds": round(time.monotonic() - start_clock, 3),
        "interpretation": "Support census only. It makes no alarm-skill or event-prediction claim.",
    }
    manifest = {"experiment": "PMI-H5-support-only", "protocol_sha": PROTOCOL_SHA,
                "protocol_file_sha256": PROTOCOL_FILE_SHA256, "code_sha256": code_hashes,
                "data_sha256": data_hashes, "configuration": config,
                "receipt_id": receipt["receipt_id"], "run_url": run_url,
                "runtime_seconds": result["runtime_seconds"]}
    return _write_result(out_dir, result, event_rows, manifest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("support",), default="support")
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-url")
    args = parser.parse_args(argv)
    result = run_support_census(args.staging, args.out, run_url=args.run_url)
    print("PMI_H5_RESULT=" + json.dumps({
        "status": result["science_status"], "support_gate": result["support_gate"],
        "scored_status": result["scored_status"],
        "independent_clusters": result.get("candidate_counts", {}).get("support_eligible_independent_clusters"),
        "runtime_seconds": result.get("runtime_seconds"),
        "warning_scores_emitted": result.get("warning_scores_emitted", False),
        "reason": result.get("reason"),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
