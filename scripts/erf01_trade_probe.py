#!/usr/bin/env python3
"""Bounded, resumable DEV economic *exploration*, never an edge certificate.

Consumes immutable ERF-01 OOS prediction probabilities; NOT future labels.
Executes genuine Kepler Numba portfolio referee with marks, funding and costs.
One predeclared candidate per invocation, stored idempotently in Modal Volume.
No G3/sealed/live access; no parameter optimization based on prior outcomes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

from kepler import qc, referee, report, tape

SYMS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT",
        "DOGEUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT")
SEAL = date(2026, 4, 1)
CAPITAL = 10_000.0
NOTIONAL = 1_000.0
# Frozen *before first economic result*. All eight are exploratory trials.
CANDIDATES = (
    ("m1_moderate_7d", "M1", 1.5, 0.015, 7),
    ("m1_moderate_21d", "M1", 1.5, 0.015, 21),
    ("m1_strict_7d", "M1", 3.0, 0.03, 7),
    ("m1_strict_21d", "M1", 3.0, 0.03, 21),
    ("m2_moderate_7d", "M2", 1.5, 0.015, 7),
    ("m2_moderate_21d", "M2", 1.5, 0.015, 21),
    ("m2_strict_7d", "M2", 3.0, 0.03, 7),
    ("m2_strict_21d", "M2", 3.0, 0.03, 21),
)


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_predictions(path: Path, model: str) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Frozen canonical OOS predictions missing: {path}")
    seen = set()
    out = {symbol: {} for symbol in SYMS}
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["model"] != model:
                continue
            sym, ds = row["symbol"], row["date"]
            d = date.fromisoformat(ds)
            if sym not in SYMS or not (date(2023, 1, 1) <= d < SEAL):
                raise ValueError(f"non-DEV or unregistered prediction: {sym}/{ds}")
            key = (sym, ds)
            if key in seen:
                raise ValueError(f"duplicate OOS prediction: {key}")
            seen.add(key)
            pu, pdn, pn = (float(row[n]) for n in ("p_up", "p_down", "p_none"))
            if (not all(math.isfinite(v) and 0 <= v <= 1 for v in (pu, pdn, pn))
                    or abs(pu + pdn + pn - 1) > 1e-6):
                raise ValueError(f"invalid probabilities: {key}")
            # Deliberately do not read row['y']: no knowledge of future labels.
            out[sym][ds] = (pu, pdn)
    if len(seen) < 5000 or any(not out[sym] for sym in SYMS):
        raise RuntimeError(f"insufficient original OOS predictions for {model}: {len(seen)}")
    return out


def signal_for_day(prob, ratio: float, min_prob: float) -> int:
    if prob is None:
        return 0
    up, down = prob
    if up >= min_prob and up > ratio * down:
        return 1
    if down >= min_prob and down > ratio * up:
        return -1
    return 0


def targets(kl: pd.DataFrame, probabilities: dict[str, tuple[float, float]],
            ratio: float, min_prob: float, days: int,
            *, invert: bool = False) -> tuple[pd.Series, dict]:
    """Close-of-UTC-day decision on hour-23 bar; next open fills in referee."""
    if days < 1 or days > 21 or not kl.index.is_monotonic_increasing:
        raise ValueError("invalid holding horizon or bar order")
    if kl.index.tz is None or str(kl.index.tz) != "UTC":
        raise ValueError("UTC input required")
    decisions = {}
    side, opened, entrances, exits = 0, None, 0, 0
    raw_held_days = []
    for ts in kl.index[kl.index.hour == 23]:
        d = ts.date()
        if d >= SEAL:
            raise RuntimeError("sealed data must never reach economic exploration")
        if side and (d - opened).days >= days:
            raw_held_days.append((d - opened).days)
            side, opened = 0, None
            exits += 1
            # Do not reverse/reenter on this same closing candle.
        elif not side:
            proposed = signal_for_day(probabilities.get(d.isoformat()), ratio, min_prob)
            if proposed:
                side = -proposed if invert else proposed
                opened = d
                entrances += 1
        decisions[ts] = float(side * NOTIONAL)
    result = pd.Series(np.nan, index=kl.index, dtype=float)
    if decisions:
        result.loc[list(decisions)] = list(decisions.values())
    result = result.ffill().fillna(0.0)
    if raw_held_days and max(raw_held_days) > days + 1:
        raise RuntimeError("data gap allowed holding horizon violation")
    return result, {"entries": entrances, "exits": exits,
                    "max_planned_closed_days": max(raw_held_days, default=0),
                    "open_at_last_bar": bool(side)}


def preflight(staging: Path) -> dict:
    if not staging.is_dir():
        raise FileNotFoundError(f"isolated real DEV staging missing: {staging}")
    if qc.SEAL_START.date() != SEAL:
        raise RuntimeError("Kepler QC seal date drift")
    receipts = {}
    for s in SYMS:
        p = staging / "erf01_qc" / f"{s}.json"
        record = json.loads(p.read_text(encoding="utf-8"))
        if (record.get("symbol") != s
                or record.get("status") != "STAGED_NOT_ACCEPTED"
                or any(x["severity"] == "ERROR" for x in record.get("findings", []))):
            raise RuntimeError(f"canonical source QC not eligible: {s}")
        for kind in ("klines", "markPriceKlines", "fundingRate"):
            if not (staging / "tape" / kind / f"{s}.parquet").is_file():
                raise FileNotFoundError(f"canonical tape missing: {s}/{kind}")
        receipts[s] = sha_file(p)
    return receipts


def load_data(staging: Path) -> dict:
    data = {}
    for sym in SYMS:
        frame = tape.load(staging, sym, start="2023-01-01", end=SEAL.isoformat())
        kl = frame["klines"][["open", "high", "low", "close", "volume"]]
        if len(kl) < 5000 or kl.index[-1].date() >= SEAL:
            raise RuntimeError(f"unusable or sealed hourly series: {sym}")
        if not kl.index.is_unique:
            raise RuntimeError(f"duplicate candle timestamps: {sym}")
        tick = Decimal(10) ** (math.floor(math.log10(float(kl.close.min()))) - 5)
        step = Decimal(10) ** (math.floor(math.log10(0.25 * CAPITAL / float(kl.close.max()))) - 3)
        data[sym] = {"kl": kl, "mark": frame["mark"],
                     "funding": frame["funding"],
                     "tick": format(tick, "f"), "step": format(step, "f")}
    return data


def spec(fee: float, slip: float) -> referee.Spec:
    return referee.Spec(capital=CAPITAL, leverage=10, liq=True, close_out=True,
                        fill="next_open", fee_rt_bps=fee, slip_rt_bps=slip,
                        gross_cap=CAPITAL)


def simulate(data: dict, predictions: dict, ratio: float, minimum: float,
             horizon: int, fee: float, slip: float,
             *, invert: bool = False) -> dict:
    sp = spec(fee, slip)
    book = {}
    counts = {}
    for sym, source in data.items():
        target, count = targets(source["kl"], predictions[sym], ratio, minimum,
                                horizon, invert=invert)
        book[sym] = dict(source, target=target)
        counts[sym] = count
    res = referee.run_portfolio(book, sp)
    summary = res["summary"]
    invalid = int(summary["n_rejected"]) > 0 or int(summary["funding_missed"]) > 0
    values = ("net_pnl", "gross_pnl", "fee", "slippage", "funding",
              "exit_cost", "liq_fee", "n_fills", "n_liq", "n_rejected",
              "funding_missed")
    stats = {field: float(summary[field]) for field in values}
    stats["fee_rt_bps"], stats["slip_rt_bps"] = fee, slip
    stats["signal_counts"] = counts
    stats["trade_entries_requested"] = sum(z["entries"] for z in counts.values())
    stats["valid"] = not invalid and stats["trade_entries_requested"] > 0
    if not invalid and stats["trade_entries_requested"] > 0:
        recon = report.reconcile(book, res, sp)
        stats["reconciliation"] = recon
        if not recon["ok"]:
            stats["valid"] = False
        pnl = report.book_pnl(book, res, sp)
        stats["calendar_year_net"] = {str(k.year): float(v)
                                     for k, v in pnl.resample("YS").sum().items()}
    return stats


def run_one(staging: Path, out: Path, *, candidate: str | None = None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    options = [c for c in CANDIDATES if candidate is None or c[0] == candidate]
    if not options:
        raise ValueError("unknown candidate")
    chosen = next((c for c in options if not (out / (c[0] + ".json")).exists()), None)
    if chosen is None:
        return {"status": "EXHAUSTED", "scope": "eight registered exploratory candidates",
                "completed": sum((out / (c[0] + ".json")).exists() for c in CANDIDATES)}
    ident, model, ratio, minimum, horizon = chosen
    # Compute all provenance gates BEFORE executing Numba or modifying trial files.
    receipt_hashes = preflight(staging)
    prediction_path = staging.parent / "canonical_20261015" / "results" / "oos_predictions.csv"
    # staging is /data/erf01/staging, sibling /data/erf01/canonical_20261015
    pred_hash = sha_file(prediction_path)
    predictions = load_predictions(prediction_path, model)
    data = load_data(staging)
    main = simulate(data, predictions, ratio, minimum, horizon, 10.0, 2.0)
    stress = simulate(data, predictions, ratio, minimum, horizon, 16.0, 6.0)
    invert = simulate(data, predictions, ratio, minimum, horizon, 10.0, 2.0, invert=True)
    result = {
        "trial_id": ident,
        "status": "EXPLORATORY_ONLY_NOT_AN_EDGE_CERTIFICATE",
        "code_sha256": sha_file(Path(__file__)),
        "canonical_oos_predictions_sha256": pred_hash,
        "staging_qc_receipt_sha256": receipt_hashes,
        "config": {"model": model, "ratio": ratio, "minimum_probability": minimum,
                   "max_holding_days": horizon, "universe": SYMS,
                   "initial_capital": CAPITAL, "per_symbol_notional": NOTIONAL},
        "main": main, "stress": stress, "inverted_direction_control": invert,
        "independent_confirmation": "NOT_RUN",
        "multiple_testing": "eight exploratory trials; no independent selection",
        "verdict": "INVALID" if not (main["valid"] and stress["valid"] and invert["valid"])
                   else "ECONOMIC_EXPLORATION_ONLY",
        "real_money": False,
        "g3_seal_opened": False,
        "decision_rule": "never certify edge on previously examined DEV data",
    }
    destination = out / (ident + ".json")
    tmp = out / (ident + ".json.tmp")
    tmp.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    if destination.exists():
        raise RuntimeError("concurrent trial writer detected")
    tmp.replace(destination)
    return {"status": result["status"], "id": ident, "main": main["net_pnl"],
            "stress": stress["net_pnl"], "inverted": invert["net_pnl"],
            "valid": result["verdict"], "n_trials_finished":
            sum((out / (c[0] + ".json")).exists() for c in CANDIDATES)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--staging", type=Path, default=Path("/data/erf01/staging"))
    p.add_argument("--out", type=Path, default=Path("/data/erf01/research/erf01_economic_v1"))
    p.add_argument("--candidate", choices=[c[0] for c in CANDIDATES])
    args = p.parse_args()
    result = run_one(args.staging, args.out, candidate=args.candidate)
    print("ERF01_RESEARCH_RESULT=" + json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
