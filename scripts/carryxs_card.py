"""`carry_xs` K1–K9 kartı işçisi (reports/preregistration/carry_xs_card.md): dinamik evren, mevcut hakem. Ana koşu = Faz 2 C1 (yeniden koşulmaz). Kontroller deftere girmez.

  modal run modal_app.py --cmd "python scripts/carryxs_card.py --stage null --null-from 0 --null-to 20 --out /data/signal_diag/carry_xs_card"
  Aşamalar: null (K1, çekiliş aralığı) | fixed (K3 maliyet/gecikme, K5 komşular, K8 ablasyonlar) | windows (K6) | bench (K2 benchmark getirisi)."""
import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_fix as AF  # noqa: E402
import ensemble as E  # noqa: E402
import signal_diag as sd  # noqa: E402
import signal_phase2 as P2  # noqa: E402

from kepler import ensemble as en  # noqa: E402
from kepler import evaluate as ev  # noqa: E402
from kepler import report  # noqa: E402

CAPR = P2.CAPR
P0 = en.Params(names=("carry_xs",), weights=(1.0,))
G: dict = {}  # fork ile işçilere paylaşılır


def setup():
    mem = sd.members(20)
    syms = sorted(mem.sym.unique())
    E.D.clear()
    AF.load_dynamic(syms, cap=CAPR)
    syms = [s for s in syms if s in E.D]
    G.update(mem=mem, syms=syms, data=E.data_of(syms), kls={s: E.D[s]["kl"] for s in syms})


def one(p: en.Params, sp, u=None, window=None, out=None):
    out = out if out is not None else P2.make_book(p, G["mem"], False, CAPR, u)(G["kls"])
    lo, hi = E.utc(window or E.MAIN)
    res, win, _ = ev.run_book(out, G["data"], sp, lo, hi, trim_flat=True)
    pnl = report.book_pnl(win, res, sp)
    return dict(summary=E.keep(res), daily=E.daily(pnl))


def task(a):
    kind, arg = a
    if kind == "null":
        u = float(np.random.default_rng([0, arg]).uniform(0.05, 0.95))
        r = one(P0, E.spec(cap=CAPR), u=u)
        return f"null_{arg}", dict(summary=r["summary"], u=u)
    if kind == "cost":
        fee, slip, delay = arg
        return f"cost_{fee}_{slip}_{delay}", one(P0, E.spec(fee, slip, delay, cap=CAPR))
    if kind == "nb":
        q = P0.scaled(arg)
        return f"nb_{arg}", dict(one(q, E.spec(cap=CAPR)), params=asdict(q))
    if kind == "abl":
        q = {"no_risk": dict(risk=False), "no_buffer": dict(buffer=0.0)}[arg]
        from dataclasses import replace
        return f"abl_{arg}", one(replace(P0, **q), E.spec(cap=CAPR))
    if kind == "win":
        r = one(P0, E.spec(cap=CAPR), window=arg, out=G["out_main"])
        return f"win_{arg[0]}_{arg[1]}", dict(summary=r["summary"])
    raise ValueError(kind)


def bench(out: Path):
    """K2 benchmark: o gün (karar günü d−1'de) aktif üyelerin eşit ağırlıklı günlük basit fiyat getirisi (kapanış → kapanış), indeks = getiri günü."""
    close, st, _ = sd.forecasts(G["kls"], G["mem"])
    act = st["active"].shift(1, fill_value=False)  # d−1'de aktif olan semboller d günü getirisini taşır
    r = (close / close.shift(1) - 1.0).where(act)
    ew = r.mean(axis=1)
    ew[act.sum(axis=1) == 0] = np.nan
    ew.loc[ew.index >= pd.Timestamp("2020-04-01", tz="UTC")].to_csv(out / "bench_ew.csv", header=["ret"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["null", "fixed", "windows", "bench"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--null-from", type=int, default=0)
    ap.add_argument("--null-to", type=int, default=20)
    ap.add_argument("--procs", type=int, default=4)
    a = ap.parse_args()
    out, t0 = Path(a.out), time.time()
    out.mkdir(parents=True, exist_ok=True)
    setup()
    print("veri hazır", len(G["syms"]), f"{time.time() - t0:.0f}s", flush=True)
    if a.stage == "bench":
        bench(out)
        return
    if a.stage == "null":
        tasks = [("null", i) for i in range(a.null_from, a.null_to)]
        name = f"null_{a.null_from}_{a.null_to}"
    elif a.stage == "fixed":
        tasks = [("cost", (16, 6, 0)), ("cost", (10, 2, 1))] + [("nb", s) for s in (0.8, 0.9, 1.1, 1.2)] + [("abl", "no_risk"), ("abl", "no_buffer")]
        name = "fixed"
    else:
        G["out_main"] = P2.make_book(P0, G["mem"], False, CAPR)(G["kls"])
        tasks = [("win", w) for w in E.HALVES + E.SHIFTS]
        name = "windows"
    res = {}
    with ProcessPoolExecutor(a.procs) as ex:
        for k, v in ex.map(task, tasks, chunksize=1):
            res[k] = v
            print(k, f"{time.time() - t0:.0f}s", "net", round(v["summary"]["net_pnl"], 1), flush=True)
    shard = out / f"{name}.json"
    shard.write_text(json.dumps(res, allow_nan=False))
    if a.stage == "null":
        import null_merge as NM
        from kepler import receipt
        identity = receipt.make(dict(script="carryxs_card", params=asdict(P0), spec=E.spec(cap=CAPR).__dict__, window=E.MAIN,
                                     membership_sha=receipt.fingerprint(G["mem"])), G["data"], cut=E.utc(E.MAIN), extra_files=[__file__, P2.__file__])
        NM.publish_identity(shard, identity["economic_id"])
    print(a.stage, "bitti", f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
