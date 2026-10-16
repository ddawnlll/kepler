"""Bounded, unscored preflight for the canonical Modal development tape."""
from __future__ import annotations

import argparse
from datetime import date, datetime, time as datetime_time, timezone
import hashlib
import json
from pathlib import Path
import platform
import time

from experiments.erf01.tape_adapter import load_development

SYMBOL = "BTCUSDT"
FIRST_DAY = date(2026, 3, 1)
LAST_DAY = date(2026, 3, 31)
SEAL = date(2026, 4, 1)
MIN_COMPLETE_DAILY_ROWS = 7


def run_smoke(staging: Path, out_dir: Path, *, run_url: str | None = None) -> dict:
    """Verify one bounded pre-seal slice without computing forecast scores."""
    if out_dir.exists():
        raise FileExistsError(f"smoke output already exists: {out_dir}")
    out_dir.mkdir(parents=True)
    started = time.monotonic()
    result = {
        "experiment": "PMI-DATA-SMOKE",
        "status": "NOT_RUN",
        "scored": False,
        "interpretation": "Data and runtime preflight only; no forecast or hypothesis was scored.",
        "configuration": {
            "symbols": [SYMBOL],
            "first_day_inclusive": FIRST_DAY.isoformat(),
            "last_day_inclusive": LAST_DAY.isoformat(),
            "seal_exclusive": SEAL.isoformat(),
            "minimum_complete_daily_rows": MIN_COMPLETE_DAILY_ROWS,
        },
        "runtime": {"python": platform.python_version(), "seconds": None},
        "run_url": run_url,
    }
    try:
        prices, _funding, funding_records, metadata, acquisition = load_development(
            staging, [SYMBOL], FIRST_DAY, LAST_DAY, SEAL)
        symbol_prices = prices[SYMBOL]
        if any(day < FIRST_DAY or day > LAST_DAY for day in symbol_prices):
            raise RuntimeError("derived daily candles escaped the configured smoke window")
        seal_ms = int(datetime.combine(SEAL, datetime_time.min, timezone.utc).timestamp() * 1000)
        if any(row[1] >= seal_ms for row in funding_records):
            raise RuntimeError("funding observations reached the exclusive development seal")
        if len(symbol_prices) < MIN_COMPLETE_DAILY_ROWS:
            raise RuntimeError(
                f"only {len(symbol_prices)} complete daily candles in smoke window; "
                f"required {MIN_COMPLETE_DAILY_ROWS}"
            )

        qc_findings = metadata[SYMBOL]["qc_findings"]
        qc_counts = {severity: sum(row["severity"] == severity for row in qc_findings)
                     for severity in ("ERROR", "WARN", "INFO")}
        source_records = [
            {key: row[key] for key in ("symbol", "kind", "sha256", "bytes")}
            for row in acquisition["records"]
        ]
        result.update({
            "status": "DATA_READY",
            "source_validation": {
                "status": "ERROR_FREE_WITH_FINDINGS_PRESERVED",
                "canonical_adapter": "experiments.erf01.tape_adapter.load_development",
                "source_file_count": acquisition["record_count"],
                "source_bytes": acquisition["source_bytes"],
                "sources": source_records,
                "qc_severity_counts": qc_counts,
                "qc_findings": qc_findings,
                "complete_daily_rows_in_window": len(symbol_prices),
                "first_daily_date": min(symbol_prices).isoformat(),
                "last_daily_date": max(symbol_prices).isoformat(),
                "funding_rows_loaded_preseal": len(funding_records),
            },
        })
    except Exception as exc:
        result["status"] = "DATA_BLOCKED"
        result["failure"] = {"type": type(exc).__name__, "reason": str(exc)}
    result["runtime"]["seconds"] = round(time.monotonic() - started, 3)
    repo_root = Path(__file__).resolve().parents[2]
    code_paths = (
        Path(__file__), repo_root / "experiments/erf01/tape_adapter.py",
        repo_root / "kepler/tape.py", repo_root / "kepler/qc.py",
    )
    code_hashes = {str(path.relative_to(repo_root)): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in code_paths}
    result["code_sha256"] = code_hashes
    identity_input = {
        "experiment": result["experiment"], "configuration": result["configuration"],
        "code_sha256": code_hashes,
        "source_sha256": {f"{row['symbol']}/{row['kind']}": row["sha256"]
                          for row in result.get("source_validation", {}).get("sources", [])},
        "status": result["status"],
    }
    result["preflight_id"] = hashlib.sha256(
        json.dumps(identity_input, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    (out_dir / "metrics.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    (out_dir / "manifest.json").write_text(
        json.dumps({
            "experiment": result["experiment"],
            "status": result["status"],
            "scored": False,
            "preflight_id": result["preflight_id"],
            "code_sha256": result["code_sha256"],
            "configuration": result["configuration"],
            "source_sha256": {f"{row['symbol']}/{row['kind']}": row["sha256"]
                              for row in result.get("source_validation", {}).get("sources", [])},
            "run_url": run_url,
            "runtime_seconds": result["runtime"]["seconds"],
        }, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-url")
    args = parser.parse_args(argv)
    result = run_smoke(args.staging, args.out, run_url=args.run_url)
    print("PMI_SMOKE_RESULT=" + json.dumps({
        "status": result["status"], "scored": result["scored"],
        "runtime_seconds": result["runtime"]["seconds"],
        "source_file_count": result.get("source_validation", {}).get("source_file_count"),
        "failure": result.get("failure"),
    }, sort_keys=True))
    return 0 if result["status"] == "DATA_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
