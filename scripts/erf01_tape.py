"""Canonical Kepler tape-to-ERF-01 development input adapter (no G3/network).

The caller controls persistence; this adapter only returns validated data. It
does not declare a historical/prospective edge or write into the core ledger.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np


def load_development(root: Path, symbols: list[str], first_day, last_day, seal):
    from kepler import tape, qc

    if qc.SEAL_START.date() != seal:
        raise RuntimeError("ERF-01 frozen seal disagrees with Kepler QC")
    prices, funding, funding_records = {s: {} for s in symbols}, {s: [] for s in symbols}, []
    metadata, source_records = {}, []

    for symbol in symbols:
        for kind in ("klines", "markPriceKlines", "fundingRate"):
            path = root / "tape" / kind / f"{symbol}.parquet"
            if not path.is_file():
                raise FileNotFoundError(f"Missing canonical tape source: {path}")
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            source_records.append({"symbol": symbol, "kind": kind, "path": str(path),
                                   "sha256": digest.hexdigest(), "bytes": path.stat().st_size})
        frame = tape.load(root, symbol, start=first_day.isoformat(), end=seal.isoformat())
        errors, issues, inputs = [], [], {}
        for stream, kind in (("klines", "klines"), ("mark", "markPriceKlines"),
                             ("funding", "fundingRate")):
            if frame[stream].empty:
                raise RuntimeError(f"{symbol}/{stream}: empty canonical tape input")
            df = frame[stream].reset_index().rename(columns={"index": "ts"})
            if "ts" not in df.columns:
                raise RuntimeError(f"{symbol}/{stream}: missing UTC timestamp")
            inputs[stream] = df
            issues.extend(qc.check_frame(df, kind))
        issues.extend(qc.check_mark_vs_kline(inputs["klines"], inputs["mark"]))
        errors = [item for item in issues if item["severity"] == "ERROR"]
        if errors:
            raise RuntimeError(f"{symbol}: canonical QC errors: {errors}")
        if qc.divergence_cutoff(inputs["klines"], inputs["mark"]) is not None:
            raise RuntimeError(f"{symbol}: 24h sustained price/mark divergence; run Kepler QC")

        hourly = frame["klines"]
        counts = hourly["close"].resample("1D").count()
        daily = hourly.resample("1D").agg({"open": "first", "high": "max",
                                            "low": "min", "close": "last", "volume": "sum"})
        cols = ("open", "high", "low", "close", "volume")
        for ts in daily.index[counts == 24]:
            day = ts.date()
            if day < first_day or day > last_day:
                continue
            values = [float(daily.at[ts, c]) for c in cols]
            if not np.isfinite(values).all() or min(values[:4]) <= 0 or values[4] < 0:
                raise RuntimeError(f"{symbol}/{day}: invalid derived daily candle")
            prices[symbol][day] = (*values, int(ts.timestamp() * 1000), math.nan)

        frows = []
        for ts, item in frame["funding"].iterrows():
            if ts.date() >= seal:
                raise RuntimeError("sealed funding boundary crossed")
            interval, rate = float(item["funding_interval_hours"]), float(item["last_funding_rate"])
            ts_ms = int(ts.timestamp() * 1000)
            frows.append((ts_ms, rate * 8 / interval))
            funding_records.append((symbol, ts_ms, interval, rate, rate * 8 / interval))
        funding[symbol] = sorted(frows)
        metadata[symbol] = {"klines_archives": 0, "funding_archives": 0,
                            "daily_rows": len(prices[symbol]), "funding_rows": len(frows),
                            "bad_ohlc": 0, "duplicate_days": 0,
                            "funding_extreme_abs_gt_1pct": sum(
                                abs(r[3]) > .01 for r in funding_records if r[0] == symbol),
                            "dropped_incomplete_days": int(((counts > 0) & (counts < 24)).sum()),
                            "qc_findings": issues}

    acquisition = {"source": "kepler_tape", "complete": True, "records": source_records,
                   "errors": [], "record_count": len(source_records),
                   "expected_archives": len(source_records), "workers": 0,
                   "raw_root": str(root / "tape"), "downloaded_bytes": 0,
                   "source_bytes": sum(r["bytes"] for r in source_records),
                   "seal_start": seal.isoformat(), "symbols": symbols}
    return prices, funding, funding_records, metadata, acquisition
