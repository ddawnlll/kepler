"""Üretim hattı GPU doğrulaması + kesişim ölçümü (Modal GPU): referee.run_many(device='gpu') ile 'cpu' AYNI gerçek veride (EV1, 462 bin bar), tam hat (funding + özet dâhil).
  modal run modal_app.py --gpu --cmd "python scripts/referee_gpu_e2e.py --out /data/vbt_val/gpu_e2e.json"   (GPU: KEPLER_GPU ortam değişkeni, varsayılan T4)"""
import argparse
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ensemble as E  # noqa: E402

from kepler import ensemble as en  # noqa: E402
from kepler import evaluate as ev  # noqa: E402
from kepler import referee, referee_gpu  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/data/vbt_val/gpu_e2e.json")
    ap.add_argument("--ns", default="16,64,128,256,512")
    a = ap.parse_args()
    E.load(E.EXT, [("/data/pre2022", None, E.SPLIT), ("/data", E.SPLIT, None)], cap=1000.0)
    data, sp = E.data_of(E.EXT), E.spec(cap=1000.0)
    kls = {s: d["kl"] for s, d in data.items()}
    book = en.make_book(1000.0, en.Params(**en.PRESETS["ev1"]))(kls)
    win = ev.book_window(book, data, *E.utc(E.MAIN))
    out = dict(cuda=referee_gpu.available(), cpus=os.cpu_count(), gpu=os.environ.get("KEPLER_GPU", "T4"), rows=[])
    t = time.perf_counter()
    referee.run_many(win, [sp, replace(sp, fee_rt_bps=11.0)] * 2, device="gpu", full=False)  # derleme + ısınma
    out["gpu_compile_warm_s"] = time.perf_counter() - t
    for n in map(int, a.ns.split(",")):
        grid = [replace(sp, fee_rt_bps=4.0 + 12.0 * i / n, slip_rt_bps=1.0 + (i % 5), delay=i % 3) for i in range(n)]
        t = time.perf_counter()
        cpu = referee.run_many(win, grid, workers=8, device="cpu", full=False)
        tc = time.perf_counter() - t
        t = time.perf_counter()
        gpu = referee.run_many(win, grid, workers=8, device="gpu", full=False)
        tg = time.perf_counter() - t
        keys = ("n_fills", "n_liq", "n_stop", "n_rejected", "funding_missed", "funding_mark_fallback")
        row = dict(n=n, cpu_s=tc, gpu_s=tg, speedup=tc / tg, cpu_ms_per=1000 * tc / n, gpu_ms_per=1000 * tg / n,
                   counts_equal=all(c["summary"][k] == g["summary"][k] for c, g in zip(cpu, gpu) for k in keys),
                   max_abs_net_diff=max(abs(c["summary"]["net_pnl"] - g["summary"]["net_pnl"]) for c, g in zip(cpu, gpu)),
                   max_abs_funding_diff=max(abs(c["summary"]["funding"] - g["summary"]["funding"]) for c, g in zip(cpu, gpu)))
        out["rows"].append(row)
        print(json.dumps(row), flush=True)
    Path(args_out := a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args_out).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
