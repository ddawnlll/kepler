"""Hız benchmark'ı (Modal; issue #33). Deftere yazmaz, karar üretmez. Tek konteynerde ölçümleri SIRAYLA ve tekrarlı koşar (farklı konteynerler arası Modal gürültüsü 25–49 sn'ye varıyor),
her koşunun yanında pariteyi (net, dolum sayısı, dolum tablosu hash'i) yazar; paritesiz hız sonucu geçersizdir.
  modal run modal_app.py --cmd "python scripts/perf_bench.py ev1 --reps 3 --out /data/perf/ev1.json"        # EV1 tek hakem koşusu (+ --buffer0: abl_no_buffer)
  modal run modal_app.py --cmd "python scripts/perf_bench.py load --reps 3 --out /data/perf/load.json"      # carry_xs kartı veri hazırlığı: üyelik tablosu + sembol yükleme
  modal run modal_app.py --cmd "python scripts/perf_bench.py null --procs 1,2,4,8 --out /data/perf/null.json"  # null çekiliş ölçekleme
Her kayıt: wall_s, cpu_s (süreç), parite alanları. Özet medyan/min/maks."""
import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ensemble as E  # noqa: E402

from kepler import ensemble as en  # noqa: E402

ROOTS = [("/data/pre2022", None, E.SPLIT), ("/data", E.SPLIT, None)]


def timed(f):
    t0, c0 = time.perf_counter(), time.process_time()
    r = f()
    return r, dict(wall_s=round(time.perf_counter() - t0, 2), cpu_s=round(time.process_time() - c0, 2))


def parity(res) -> dict:
    f = res["fills"]
    return dict(net=repr(float(res["summary"]["net_pnl"])), n_fills=len(f), fills_hash=str(int(pd.util.hash_pandas_object(f, index=False).sum())), funding=repr(float(res["summary"]["funding"])))


def summarize(rows: list[dict]) -> dict:
    w = [r["wall_s"] for r in rows]
    out = dict(n=len(rows), wall_median=statistics.median(w), wall_min=min(w), wall_max=max(w), parity_unique=len({json.dumps({k: v for k, v in r.items() if k not in ("wall_s", "cpu_s", "rep")}, sort_keys=True) for r in rows}))
    return out


def bench_ev1(a):
    E.load(E.EXT, ROOTS)
    p = replace(en.Params(), buffer=0.0) if a.buffer0 else en.Params()
    rows = []
    for rep in range(a.reps):
        (res, _, _), t = timed(lambda: E.run(p, E.spec()))
        rows.append(dict(rep=rep, **t, **parity(res)))
        print(rows[-1], flush=True)
    return dict(kind="ev1", buffer0=a.buffer0, rows=rows, summary=summarize(rows))


def bench_load(a):
    """carry_xs kartı `setup()` aşamaları: üyelik tablosu (sd.members) ve sembol yükleme (AF.load_dynamic). Sıralı; tekrarlar soğuk/sıcak Volume farkını gösterir."""
    import audit_fix as AF
    import signal_diag as sd
    rows = []
    for rep in range(a.reps):
        E.D.clear()
        mem, t1 = timed(lambda: sd.members(20))
        syms = sorted(mem.sym.unique())
        _, t2 = timed(lambda: AF.load_dynamic(syms, cap=1000.0))
        rows.append(dict(rep=rep, n_syms=len(E.D), members_wall_s=t1["wall_s"], load_wall_s=t2["wall_s"], load_cpu_s=t2["cpu_s"]))
        print(rows[-1], flush=True)
    return dict(kind="load", rows=rows)


def bench_null(a):
    E.load(E.EXT, ROOTS)
    rows = []
    for n in [int(x) for x in a.procs.split(",")]:
        with ProcessPoolExecutor(n) as ex:
            r, t = timed(lambda: dict(ex.map(E.null_draw, range(100, 100 + n))))
        rows.append(dict(procs=n, draws=n, **t, draws_per_s=round(n / t["wall_s"], 3), net_sum=repr(sum(v["net_pnl"] for v in r.values()))))
        print(rows[-1], flush=True)
    return dict(kind="null", rows=rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["ev1", "load", "null"])
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--buffer0", action="store_true")
    ap.add_argument("--procs", default="1,2,4,8")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    res = {"ev1": bench_ev1, "load": bench_load, "null": bench_null}[a.kind](a)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1))
    print("BENCH", json.dumps(res.get("summary", {k: v for k, v in res.items() if k != "rows"})), flush=True)
