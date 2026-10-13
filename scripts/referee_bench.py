"""Hakem motoru kıyaslaması (Modal): aşama süreleri, tek koşu, N senaryolu tarama (seri / iş parçacığı), isteğe bağlı GPU. Çıktı JSON.
  modal run modal_app.py --cmd "python scripts/referee_bench.py --out /data/vbt_val/bench.json"
Senaryo = (fee, slip, gecikme) ızgarası; veri = EV1 kitabı (9 sembol, 6 yıl, 473k saatlik bar)."""
import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ensemble as E  # noqa: E402

from kepler import ensemble as en  # noqa: E402
from kepler import evaluate as ev  # noqa: E402
from kepler import referee, referee_core  # noqa: E402


def timed(f, *a, **k):
    t = time.perf_counter()
    r = f(*a, **k)
    return r, time.perf_counter() - t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/data/vbt_val/bench.json")
    ap.add_argument("--n", type=int, default=64)
    a = ap.parse_args()
    t0 = time.perf_counter()
    E.load(E.EXT, [("/data/pre2022", None, E.SPLIT), ("/data", E.SPLIT, None)], cap=1000.0)
    data, sp = E.data_of(E.EXT), E.spec(cap=1000.0)
    kls = {s: d["kl"] for s, d in data.items()}
    book = en.make_book(1000.0, en.Params(**en.PRESETS["ev1"]))(kls)
    t_prep = time.perf_counter() - t0
    lo, hi = E.utc(E.MAIN)
    import os
    out = dict(cpus=os.cpu_count(), bars=int(sum(len(k) for k in kls.values())), t_load_book=t_prep)
    (_, out["t_first_cold_compile"]) = timed(ev.run_book, book, data, sp, lo, hi)
    runs = [timed(ev.run_book, book, data, sp, lo, hi)[1] for _ in range(5)]
    out["t_single_warm_s"] = float(np.median(runs))
    # aşama dökümü
    keep = {s: (d["kl"].index >= lo) & (d["kl"].index < hi) for s, d in data.items()}
    win = {s: dict(d, kl=d["kl"][keep[s]], target=book[s].target.ffill().fillna(0.0)[keep[s]], stop=book[s].stop[keep[s]], mark=None if d.get("mark") is None else d["mark"].loc[(d["mark"].index >= lo) & (d["mark"].index < hi)]) for s, d in data.items()}
    _, out["t_prep_inputs_s"] = timed(lambda: [referee._prep(s, d, sp) for s, d in win.items()])
    grid = [replace(sp, fee_rt_bps=f, slip_rt_bps=s_, delay=d) for f in (4.0, 8.0, 10.0, 16.0) for s_ in (1.0, 2.0, 4.0, 6.0) for d in (0, 1, 2, 3)][: a.n]
    out["n_scenarios"] = len(grid)
    _, out["t_sweep_serial_s"] = timed(lambda: [referee.run_portfolio(win, g) for g in grid])
    pr = referee.prepare(win, sp)
    _, out["t_sweep_prepared_serial_s"] = timed(lambda: [referee.run_portfolio(win, g, pr) for g in grid])
    for w in (2, 4, 8):
        _, out[f"t_sweep_threads{w}_s"] = timed(lambda: referee.run_many(win, grid, w))
    out["t_sweep_threads_s"] = min(out[f"t_sweep_threads{w}_s"] for w in (2, 4, 8))
    out["sweep_throughput_per_s_threads"] = len(grid) / out["t_sweep_threads_s"]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
