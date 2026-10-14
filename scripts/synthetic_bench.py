"""Reproducible CPU throughput test. Synthetic results never certify real-data or Modal performance.
Run with PYTHONPATH=. python scripts/synthetic_bench.py --out /tmp/bench.json.
"""
import argparse
import hashlib
import json
import os
import platform
import resource
import statistics
import subprocess
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from kepler import referee, report


def timed(fn):
    start = time.perf_counter()
    result = fn()
    return result, time.perf_counter() - start


def fixture(hours, symbols, funding):
    ix = pd.date_range("2019-01-01", periods=hours, freq="1h", tz="UTC")
    x = np.arange(hours)
    data = {}
    for s in range(symbols):
        px = 100 + s * 10 + np.sin(x / 101 + s) * 2
        kl = pd.DataFrame(dict(open=px, high=px + .3, low=px - .3, close=px + .1, volume=1e6), index=ix)
        target = pd.Series(np.nan, index=ix)
        target.iloc[::24] = np.where((x[::24] // 24 + s) % 2, -100., 100.)
        f = pd.DataFrame(dict(last_funding_rate=.0001), index=ix[8::8]) if funding else None
        data[f"S{s:02}"] = dict(kl=kl, target=target, mark=kl, funding=f)
    return data


def parity(r):
    f = r["fills"]
    return dict(net=r["summary"]["net_pnl"], funding=r["summary"]["funding"], n_fills=len(f),
                fills_sha256=hashlib.sha256(pd.util.hash_pandas_object(f, index=False).values.tobytes()).hexdigest())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=52560)
    ap.add_argument("--symbols", type=int, default=9)
    ap.add_argument("--scenarios", type=int, default=64)
    ap.add_argument("--funding", action="store_true")
    ap.add_argument("--warm-reps", type=int, default=5)
    ap.add_argument("--single-only", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if min(a.hours, a.symbols, a.scenarios, a.warm_reps) < 1:
        raise SystemExit("positive dimensions required")
    data, prep_s = timed(lambda: fixture(a.hours, a.symbols, a.funding))
    sp = referee.Spec(capital=1000, liq=False, fee_rt_bps=10, slip_rt_bps=2)
    first, first_s = timed(lambda: referee.run_portfolio(data, sp))
    warm_runs = []
    for _ in range(a.warm_reps):
        warm, seconds = timed(lambda: referee.run_portfolio(data, sp))
        warm_runs.append(seconds)
        if parity(first) != parity(warm):
            raise RuntimeError("cold/warm fill parity failed")
    warm_s = statistics.median(warm_runs)
    if hasattr(report, "reconcile"):
        rc = report.reconcile(data, warm, sp)
    else:  # Historical Numba main: independent hourly reconstruction, no reconcile API yet.
        diff = float(report.book_pnl(data, warm, sp).sum()) - float(warm["summary"]["net_pnl"])
        rc = dict(ok=abs(diff) <= 1e-6, diff=diff, method="historical_hourly_reconstruction", tol=1e-6)
    if not rc["ok"]:
        raise RuntimeError(f"reconciliation failed: {rc}")
    grid = [replace(sp, fee_rt_bps=4 + i % 8, delay=i % 3) for i in range(a.scenarios)]
    out = dict(label="SYNTHETIC_CPU_ONLY", hours=a.hours, symbols=a.symbols, bars=a.hours * a.symbols,
               funding=a.funding, n_scenarios=0 if a.single_only else a.scenarios, fixture_s=prep_s, first_s=first_s, warm_s=warm_s, warm_runs=warm_runs,
               parity=parity(warm), reconcile=rc, cpu_count=os.cpu_count(), platform=platform.platform(),
               source_sha=subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip())
    if hasattr(referee, "run_many") and not a.single_only:
        serial, out["serial_summary_s"] = timed(lambda: referee.run_many(data, grid, workers=1, full=False))
        parallel, out["threads4_summary_s"] = timed(lambda: referee.run_many(data, grid, workers=4, full=False))
        if [r["summary"] for r in serial] != [r["summary"] for r in parallel]:
            raise RuntimeError("serial/thread economic parity failed")
        out["serial_thread_parity"] = True
    out["peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    out["dirty_diff_sha256"] = hashlib.sha256(subprocess.run(["git", "diff", "HEAD"], capture_output=True).stdout).hexdigest()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2, allow_nan=False))
    print(json.dumps(out, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
