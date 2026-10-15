"""Build staging canonical 1h kline/mark/funding DEV tape from published SHA ZIPs.

No G3, no data synthesis, no ledger writes. Never replaces production /data/tape:
outputs only under the caller's /data/erf01/staging root until independently QC'd.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from kepler import data, qc, tape

SEAL = pd.Timestamp("2026-04-01", tz="UTC")
FIRST_MONTH, LAST_MONTH = "2020-01", "2026-03"
KINDS = ("klines", "markPriceKlines", "fundingRate")


def month_iter(first: str, last: str):
    y, m = map(int, first.split("-"))
    ey, em = map(int, last.split("-"))
    while (y, m) <= (ey, em):
        yield f"{y:04d}-{m:02d}"
        y, m = (y + (m == 12), 1 if m == 12 else m + 1)


def _plans(repo: Path, symbol: str):
    old = json.loads((repo / "data_manifest" / "manifest_pre2022.json").read_text())
    recent = json.loads((repo / "data_manifest" / "manifest.json").read_text())
    shards = [d.get("symbols", {}).get(symbol, {}) for d in (old, recent)]
    plan = {}
    for kind in KINDS:
        chunks = [d[kind] for d in shards if kind in d and d[kind].get("first")]
        if not chunks:
            raise RuntimeError(f"missing source manifests {symbol}/{kind}")
        first, last = min(x["first"][:7] for x in chunks), max(x["last"][:7] for x in chunks)
        published = {}
        for c in chunks:
            for month, value in c.get("zip_sha256", {}).items():
                if month in published and published[month] != value:
                    raise RuntimeError(f"inconsistent frozen manifests: {symbol}/{kind}/{month}")
                published[month] = value
        plan[kind] = [(month, published.get(month))
                      for month in month_iter(max(first, FIRST_MONTH), min(last, LAST_MONTH))]
        if not plan[kind]:
            raise RuntimeError(f"empty DEV source plan {symbol}/{kind}")
    return plan


def _timestamp(raw: pd.Series) -> pd.Series:
    n = pd.to_numeric(raw, errors="raise")
    if n.isna().any():
        raise ValueError("missing event timestamp")
    # Binance archives can encode both milliseconds and microseconds.
    micro = n.abs() > 10**14
    output = pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns, UTC]")
    for mask, unit in ((~micro, "ms"), (micro, "us")):
        if mask.any():
            output.loc[mask] = pd.to_datetime(n.loc[mask], unit=unit, utc=True)
    return output


def _parse_month(path: Path, kind: str, month: str) -> pd.DataFrame:
    df = data.read_zip_csv(path)
    clock = "calc_time" if kind == "fundingRate" else "open_time"
    if clock not in df:
        raise RuntimeError(f"unknown {kind} source time column")
    df["ts"] = _timestamp(df[clock])
    if df.empty or (df["ts"].dt.strftime("%Y-%m") != month).any():
        raise RuntimeError(f"{kind}/{month}: source has missing or out-of-month records")
    columns = (("ts", "funding_interval_hours", "last_funding_rate") if kind == "fundingRate"
               else ("ts", "open", "high", "low", "close", "volume"))
    if any(k not in df for k in columns):
        raise RuntimeError(f"{kind}/{month}: incompatible Binance archive columns")
    df = df[list(columns)].copy()
    for column in columns[1:]:
        df[column] = pd.to_numeric(df[column], errors="raise")
    if df["ts"].duplicated().any() or not df["ts"].is_monotonic_increasing:
        raise RuntimeError(f"{kind}/{month}: duplicate/out-of-order event time")
    df["ts_unit"] = "ms"  # native timestamp normalised from original unit
    return df


def build_symbol(repo: Path, root: Path, staging: Path, symbol: str,
                 workers: int = 16) -> dict:
    """Download/verify first. Only publish parquet after every required input passes QC."""
    if qc.SEAL_START != SEAL:
        raise RuntimeError("Kepler seal date drift")
    plans = _plans(repo, symbol)
    source = []
    for kind, months in plans.items():
        for month, expected in months:
            key = data.key(kind, symbol, month, "1h")
            source.append((kind, month, expected, key))
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=workers) as pool:
        paths = list(pool.map(lambda item: data.fetch(item[3], root), source))
    kinds = {}
    digests = []
    for (kind, month, expected, key), path in zip(source, paths):
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        if expected is not None and checksum != expected:
            raise RuntimeError(f"frozen manifest/source SHA mismatch: {symbol}/{kind}/{month}")
        digests.append({"kind":kind, "month":month, "sha256":checksum, "source":key})
        kinds.setdefault(kind, []).append(_parse_month(path, kind, month))
    tables, findings = {}, []
    for kind, parts in kinds.items():
        df = pd.concat(parts, ignore_index=True)
        if df["ts"].duplicated().any() or not df["ts"].is_monotonic_increasing:
            raise RuntimeError(f"{symbol}/{kind}: duplicated/non-monotonic boundary")
        if df.ts.min() >= SEAL or df.ts.max() >= SEAL:
            raise RuntimeError("sealed data boundary crossed")
        errors = qc.check_frame(df, kind)
        findings.extend(errors)
        if any(e["severity"] == "ERROR" for e in errors):
            raise RuntimeError(f"{symbol}/{kind}: canonical QC ERROR {errors}")
        tables[kind] = df
    findings.extend(qc.check_mark_vs_kline(tables["klines"], tables["markPriceKlines"]))
    if any(x["severity"] == "ERROR" for x in findings):
        raise RuntimeError(f"{symbol}: mark-vs-kline QC ERROR {findings}")
    if qc.divergence_cutoff(tables["klines"], tables["markPriceKlines"]) is not None:
        raise RuntimeError(f"{symbol}: persistent mark/kline divergence; cannot publish")

    # Atomic staging only; downstream consumers must independently check all 9 symbols.
    for kind, frame in tables.items():
        target = staging / "tape" / kind / f"{symbol}.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".part")
        frame.to_parquet(tmp, index=False, compression="zstd")
        tmp.replace(target)
    sample = tape.load(staging, symbol, start="2025-01-01", end="2025-02-01")
    if sample["klines"].empty or sample["mark"].empty or sample["funding"].empty:
        raise RuntimeError(f"{symbol}: no real 2025-01 canonical tape readback")
    evidence = {"symbol":symbol, "sealed_boundary":str(SEAL), "archives":len(source),
                "counts":{kind:len(frame) for kind,frame in tables.items()},
                "findings":findings, "sources":digests, "status":"STAGED_NOT_ACCEPTED"}
    out = staging / "erf01_qc" / f"{symbol}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2)+"\n")
    return {"symbol":symbol, "archives":len(source),
            "counts":evidence["counts"],"qc_error_count":0,
            "findings":len(findings),"state":"STAGED_NOT_ACCEPTED"}
