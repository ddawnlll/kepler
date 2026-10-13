"""EV1 kitabında fee x slip x gecikme ızgarası taraması (CPU, Modal; isteğe bağlı container'lara dağıtım). Aşama süreleri ve toplam yazılır.
  modal run modal_app.py --shards 4 --cmd "python scripts/referee_sweep.py --n 256 --out /data/vbt_val/sweep"   (shard i: ızgaradan grid[i::N], ortam KEPLER_SHARD=i/N)
Çıktı: <out>.shard<i>.json (senaryo özetleri + aşama süreleri)."""
import argparse
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

T_START = time.perf_counter()
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ensemble as E  # noqa: E402

from kepler import ensemble as en  # noqa: E402
from kepler import evaluate as ev  # noqa: E402
from kepler import referee  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=256)
    ap.add_argument("--out", default="/data/vbt_val/sweep")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    i, n_sh = map(int, os.environ.get("KEPLER_SHARD", "0/1").split("/"))
    st = {"python_import_s": time.perf_counter() - T_START}
    t = time.perf_counter()
    E.load(E.EXT, [("/data/pre2022", None, E.SPLIT), ("/data", E.SPLIT, None)], cap=1000.0)
    data, sp = E.data_of(E.EXT), E.spec(cap=1000.0)
    book = en.make_book(1000.0, en.Params(**en.PRESETS["ev1"]))({s: d["kl"] for s, d in data.items()})
    win = ev.book_window(book, data, *E.utc(E.MAIN))
    st["load_book_s"] = time.perf_counter() - t
    grid = [replace(sp, fee_rt_bps=4.0 + 12.0 * k / a.n, slip_rt_bps=1.0 + (k % 5), delay=k % 3) for k in range(a.n)][i::n_sh]
    t = time.perf_counter()
    referee.run_many(win, grid[:1], workers=1, device="cpu", full=False)  # ilk çağrı: numba önbellekten yükleme (ya da derleme) süresi
    st["first_call_s"] = time.perf_counter() - t
    t = time.perf_counter()
    res = referee.run_many(win, grid, workers=a.workers, device="cpu", full=False)
    st["sweep_s"], st["scenarios"], st["shard"] = time.perf_counter() - t, len(grid), f"{i}/{n_sh}"
    st["total_in_process_s"] = time.perf_counter() - T_START
    st["sweep_ms_per_scenario"] = 1000 * st["sweep_s"] / len(grid)
    Path(f"{a.out}.shard{i}.json").write_text(json.dumps(dict(stages=st, net=[r["summary"]["net_pnl"] for r in res], fee=[g.fee_rt_bps for g in grid]), indent=1))
    print(json.dumps(st), flush=True)


if __name__ == "__main__":
    main()
