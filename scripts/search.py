"""Arama (reports/search_protocol.md): 88 yapılandırma, arama dönemi hakem+eleme, aile başına seçilen yapılandırma doğrulama döneminde null'a karşı.

  python scripts/search.py --stage search --family donchian --out /data/search
  python scripts/search.py --stage validate --b 300 --out /data/search"""
import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

import g2
from kepler import evaluate as ev
from kepler import ledger, referee, report, screen
from kepler import signals as sg

SEARCH, VAL = ("2022-01-01", "2025-01-01"), ("2025-01-01", "2026-04-01")
FAMILIES = ("donchian", "ema", "tsmom", "xs_mom", "xs_carry", "xs_rev")
P = {}  # panel'ler (fork ile paylaşılır)


def configs(family):
    c = []
    if family == "donchian":
        c = [(f"don_{e}_{x}", dict(entry=e, exit=x)) for e in (10, 20, 30, 40, 55, 80, 100, 120) for x in (5, 10, 20, 30, 40) if x < e]
    elif family == "ema":
        c = [(f"ema_{f}_{s}", dict(fast=f, slow=s)) for f in (5, 10, 20, 30, 50) for s in (50, 100, 150, 200, 350) if f < s]
    elif family == "tsmom":
        c = [(f"tsmom_{d}_{k}", dict(days=d, every=k)) for d in (7, 14, 30, 60, 90, 180, 365) for k in (1, 7, 30)]
    elif family == "xs_mom":
        c = [(f"xsmom_{d}", dict(kind="mom", days=d, every=7)) for d in (7, 14, 30, 60, 90, 180)]
    elif family == "xs_carry":
        c = [(f"xscarry_{d}", dict(kind="carry", days=d, every=7)) for d in (7, 14, 30)]
    elif family == "xs_rev":
        c = [(f"xsrev_{d}", dict(kind="rev", days=d, every=1)) for d in (1, 2, 3, 5)]
    return c


def make(family, p, sym):
    if family == "donchian":
        return sg.turtle(p["entry"], p["exit"])
    if family == "ema":
        return sg.ema_trend(p["fast"], p["slow"])
    if family == "tsmom":
        return sg.tsmom(p["days"], p["every"] if p["every"] > 1 else 1)
    return sg.xs_signal(P["fund" if p["kind"] == "carry" else "close"], sym, p["kind"], p["days"], p["every"])


def one(a):
    family, name, p, sym, window, specs, out, dh, tag = a
    kl, mark, funding = g2.D[sym]
    led = Path(out) / f"ledger_{tag}_{family}.jsonl"
    res = ev.evaluate(make(family, p, sym), kl, specs, led, f"{tag} {family}: {name}", dh, funding, mark, g2.NOTIONAL, name, dict(p, family=family), window)
    k, mk = kl[(kl.index >= window[0]) & (kl.index < window[1])], mark
    rows = []
    for sp, r in zip(specs, res):
        s = dict(r["res"]["summary"], fee_bps=sp.fee_rt_bps, slip_bps=sp.slip_rt_bps, traded=float((r["res"]["fills"].qty * r["res"]["fills"].px).sum()))
        base = (sp.fee_rt_bps, sp.slip_rt_bps) == (10, g2.SLIP)
        s["daily"] = {str(i.date()): float(v) for i, v in report.hourly_pnl(k, mk.loc[k.index.intersection(mk.index)], funding, r["res"]["fills"], sp).resample("1D").sum().items()} if base else None
        rows.append(s)
    return name, sym, rows


def null_one(a):
    family, name, p, sym, window, i = a
    kl, mark, funding = g2.D[sym]
    u = make(family, p, sym)(kl).ffill().fillna(0.0)
    keep = (kl.index >= window[0]) & (kl.index < window[1])
    u = u[keep].to_numpy()
    off = int(np.random.default_rng([0, i]).uniform(0.05, 0.95) * len(u))  # ortak ofset: tüm semboller aynı oranda kayar
    s = referee.run(kl[keep], pd.Series(np.roll(u, off) * g2.NOTIONAL, index=kl.index[keep]), g2.spec_for(kl, 10, g2.SLIP), funding, mark.loc[mark.index.intersection(kl.index[keep])])["summary"]
    return sym, i, {k: s[k] for k in ("gross_pnl", "net_pnl", "n_rejected")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["search", "validate"])
    ap.add_argument("--family", default="")
    ap.add_argument("--b", type=int, default=300)
    ap.add_argument("--root", default="/data")
    ap.add_argument("--out", default="/data/search")
    ap.add_argument("--procs", type=int, default=4)
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    g2.load(a.root, g2.EXT)
    P["close"] = pd.DataFrame({s: sg._daily(g2.D[s][0]).close for s in g2.EXT})
    P["fund"] = pd.DataFrame({s: g2.D[s][0].fund_hr.resample("1D").mean() for s in g2.EXT})
    dh, t0 = ledger.sha(Path("/repo/data_manifest/manifest.json").read_text()), time.time()
    S = lambda kl, fee, slip: g2.spec_for(kl, fee, slip)  # noqa: E731
    with ProcessPoolExecutor(a.procs) as ex:
        if a.stage == "search":
            cfgs, tasks = configs(a.family), []
            for name, p in cfgs:
                tasks += [(a.family, name, p, s, SEARCH, [S(g2.D[s][0], 10, g2.SLIP)], a.out, dh, "search") for s in g2.EXT]
            res = {}
            for name, sym, rows in ex.map(one, tasks, chunksize=2):
                res.setdefault(name, {})[sym] = rows[0]
            print(f"hakem {time.time() - t0:.0f}s", flush=True)
            scr = {}
            for sym in g2.EXT:  # eleme: aynı ızgara vectorbt ile (deftere eleme olarak yazılır, deneme sayacına girer)
                kl = g2.D[sym][0]
                keep = (kl.index >= SEARCH[0]) & (kl.index < SEARCH[1])
                tg = {n: (make(a.family, p, sym)(kl).ffill() * g2.NOTIONAL)[keep] for n, p in cfgs}
                sc = screen.screen(kl[keep], tg, 10, Path(a.out) / f"ledger_screen_{a.family}.jsonl", g2.SLIP, 1e6, f"eleme {a.family}", dh)
                for n, v in sc.items():
                    scr.setdefault(n, {})[sym] = float(v)
            Path(a.out, f"search_{a.family}.json").write_text(json.dumps(dict(family=a.family, cfgs=dict(cfgs), res=res, screen=scr)))
        else:
            best = {}
            for fam in FAMILIES:
                d = json.loads(Path(a.out, f"search_{fam}.json").read_text())
                nm = max(d["res"], key=lambda n: sum(v["net_pnl"] for v in d["res"][n].values()))
                best[fam] = (nm, d["cfgs"][nm])
            specs = lambda kl: [S(kl, f, g2.SLIP) for f in g2.FEES] + [S(kl, 10, 6.0)]  # noqa: E731
            tasks = [(fam, nm, p, s, VAL, specs(g2.D[s][0]), a.out, dh, "val") for fam, (nm, p) in best.items() for s in g2.EXT]
            real = {}
            for name, sym, rows in ex.map(one, tasks, chunksize=1):
                real.setdefault(name, {})[sym] = rows
            print(f"doğrulama hakem {time.time() - t0:.0f}s", flush=True)
            null = {nm: {s: {} for s in g2.EXT} for nm, _ in best.values()}
            for fam, (nm, p) in best.items():
                for sym, i, r in ex.map(null_one, [(fam, nm, p, s, VAL, i) for i in range(a.b) for s in g2.EXT], chunksize=4):
                    null[nm][sym][i] = r
            Path(a.out, "validate.json").write_text(json.dumps(dict(best={f: b[0] for f, b in best.items()}, real=real, null=null, b=a.b)))
    print(f"bitti {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    sys.exit(main())
