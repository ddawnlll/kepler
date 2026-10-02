"""Ensemble v1 işçisi (Modal'de koşar): reports/ensemble_protocol.md. Parametreler protokolde sabit; burada ayarlanmaz.

  --stage primary  birincil EV1 (evaluate_book: denetim + defter) + kontroller: 5 ablasyon (K8), 6 komşu (K5), maliyet/gecikme (K3), pencere/kaydırma (K6), al-tut (K2), 500 USD (bilgi)
  --stage k7       çapraz varlık (dev K7 kuralı, 2023-07 -> 2026-04, fee 16 + slip 2)
  --stage null     K1 rotasyon null'u (--null-from/--null-to ile bölünür)
Veri: /data/pre2022 (2020-01 -> 2021-12) + /data (2022-01 -> 2026-03) sembol başına birleştirilir. Çıktı --out altında JSON; özet scripts/ensemble_report.py."""
import argparse
import json
import math
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

from kepler import ensemble as en
from kepler import evaluate as ev
from kepler import ledger, referee, report, robust, stress, tape
from kepler import signals as sg

EXT = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT"]
CAP, SPLIT = 10_000.0, "2022-01-01"
MAIN, K7_WINDOW = ("2020-04-01", "2026-04-01"), ("2023-07-01", "2026-04-01")
HALVES = [(f"{y}-{m}-01", f"{y + (m == '07')}-{'01' if m == '07' else '07'}-01") for y in range(2020, 2026) for m in ("01", "07")][1:] + [("2026-01-01", "2026-04-01")]
SHIFTS = [(f"2020-{m:02d}-01", MAIN[1]) for m in (4, 5, 6, 7)]
STRESS = {"2021-05": ("2021-05-17", "2021-05-24"), "LUNA": ("2022-05-05", "2022-05-16"), "FTX": ("2022-11-06", "2022-11-15")}
ABL = {"trend_only": dict(weights=(1.0, 0.0, 0.0)), "no_xs": dict(weights=(0.75, 0.0, 0.25)), "no_carry": dict(weights=(0.75, 0.25, 0.0)), "no_risk": dict(risk=False), "no_buffer": dict(buffer=0.0)}
NB = {**{f"scale_{s}": s for s in (0.8, 0.9, 1.1, 1.2)}, "w_50_25_25": (0.5, 0.25, 0.25), "w_70_15_15": (0.7, 0.15, 0.15)}
COSTS = [(4, 2, 0), (16, 2, 0), (10, 6, 0), (16, 6, 0), (10, 2, 1)]
D: dict = {}  # sembol -> dict(kl [OHLCV + fund_hr], funding, mark, tick, step); fork ile paylaşılır


def load(syms, roots, cap=CAP):
    for s in syms:
        parts = [tape.load(r, s, start=lo, end=hi) for r, lo, hi in roots]
        parts = [p for p in parts if len(p["klines"])]
        d = {k: pd.concat([p[k] for p in parts]).sort_index() for k in ("klines", "mark", "funding")}
        for k in d:
            d[k] = d[k][~d[k].index.duplicated()]
        kl = sg.with_funding(d["klines"][["open", "high", "low", "close", "volume"]], d["funding"])
        q = Decimal(10) ** (math.floor(math.log10(kl.close.min())) - 5)  # sembol kuralları UNKNOWN: sinyal-bağımsız çözünürlük (full_systems ile aynı kural)
        st = Decimal(10) ** (math.floor(math.log10(0.25 * cap / kl.close.max())) - 3)
        D[s] = dict(kl=kl, funding=d["funding"], mark=d["mark"], tick=format(q, "f"), step=format(st, "f"))


def spec(fee=10.0, slip=2.0, delay=0, cap=CAP) -> referee.Spec:
    return referee.Spec(capital=cap, leverage=10, liq=True, fee_rt_bps=fee, slip_rt_bps=slip, delay=delay, gross_cap=3 * cap)


def utc(w):
    return tuple(pd.Timestamp(x, tz="UTC") for x in w)


def keep(res):
    s = res["summary"]
    return {k: float(s[k]) for k in ("net_pnl", "gross_pnl", "fee", "slippage", "funding", "exit_cost", "liq_fee", "n_fills", "n_liq", "n_rejected", "funding_missed")}


def daily(pnl):
    return {str(k.date()): float(v) for k, v in pnl.resample("1D").sum().items()}


def data_of(syms, d=None):
    d = d or D
    return {s: d[s] for s in syms}


def run(p, sp, window=MAIN, syms=EXT, u=None, out=None):
    data = data_of(syms)
    out = out or en.make_book(sp.capital, p, u)({s: x["kl"] for s, x in data.items()})
    res, win, _ = ev.run_book(out, data, sp, *utc(window))
    return res, win, out


def task(a):
    kind, name, out_dir, dh = a
    p = en.Params()
    if kind == "main":
        data, sp = data_of(EXT), spec()
        r = ev.evaluate_book(en.make_book(CAP, p), data, [sp], Path(out_dir) / "ledger_ev1.jsonl", "Ensemble v1: piyasa durumu -> uzmanlar -> aday -> risk motoru (reports/ensemble_protocol.md)",
                             dh, "EV1", asdict(p), MAIN)[0]
        pnl = report.book_pnl(r["win"], r["res"], sp)
        out = en.make_book(CAP, p)({s: x["kl"] for s, x in data.items()})
        fills = r["res"]["fills"]
        close = {s: D[s]["kl"].close for s in EXT}
        st = {k: stress.window_stats(pnl, fills, *w, CAP, close, {s: out[s].stop for s in EXT}, {s: D[s]["kl"] for s in EXT}) for k, w in STRESS.items()}
        sym_net = {s: float(report.hourly_pnl(r["win"][s]["kl"], r["win"][s].get("mark"), r["win"][s].get("funding"), fills[fills.sym == s], sp).sum()) for s in r["win"]}
        gross_notional = pd.DataFrame({s: out[s].target.ffill().fillna(0.0).abs().resample("1D").last() for s in EXT}).fillna(0.0).sum(axis=1)
        f, _ = en.forecasts({s: x["kl"] for s, x in data.items()}, p)
        return "main", dict(summary=keep(r["res"]), daily=daily(pnl), sym_net=sym_net, stress=st, recon=float(pnl.sum() - r["res"]["summary"]["net_pnl"]), row_trial=r["row"]["trial"],
                            traded=float((fills.qty * fills.px).sum()), gross_notional_mean=float(gross_notional[gross_notional.index >= MAIN[0]].mean()),
                            forecast_abs_mean=float(f.abs().stack().mean()), forecast_long_share=float((f.stack() > 0).mean()))
    if kind == "abl":
        res, win, _ = run(replace(p, **ABL[name]), spec())
        return f"abl_{name}", dict(summary=keep(res), daily=daily(report.book_pnl(win, res, spec())))
    if kind == "nb":
        q = p.scaled(NB[name]) if name.startswith("scale") else replace(p, weights=NB[name])
        res, win, _ = run(q, spec())
        return f"nb_{name}", dict(summary=keep(res), daily=daily(report.book_pnl(win, res, spec())), params=asdict(q))
    if kind == "cost":
        fee, slip, delay = name
        res, win, _ = run(p, spec(fee, slip, delay))
        return f"cost_{fee}_{slip}_{delay}", dict(summary=keep(res), daily=daily(report.book_pnl(win, res, spec(fee, slip, delay))))
    if kind == "win":
        out = None
        res, win, _ = run(p, spec(), window=name, out=out)
        return f"win_{name[0]}_{name[1]}", dict(summary=keep(res))
    if kind == "bh":
        res, pnl = robust.buy_hold(data_of(EXT), replace(spec(), gross_cap=None), CAP / len(EXT), MAIN)
        return "bh", dict(summary=keep(res), daily=daily(pnl))
    if kind == "cap500":
        d500 = {s: dict(D[s], step=format(Decimal(10) ** (math.floor(math.log10(0.25 * 500 / D[s]["kl"].close.max())) - 3), "f")) for s in EXT}
        sp = spec(cap=500.0)
        out = en.make_book(500.0, p)({s: x["kl"] for s, x in d500.items()})
        res, win, _ = ev.run_book(out, d500, sp, *utc(MAIN))
        return "cap500", dict(summary=keep(res), daily=daily(report.book_pnl(win, res, sp)), n_targets=int(sum((out[s].target.dropna().diff().abs() > 0).sum() for s in EXT)))


def null_draw(i):
    u = float(np.random.default_rng([0, i]).uniform(0.05, 0.95))  # ortak ofset: tüm semboller aynı k
    res, _, _ = run(en.Params(), spec(), u=u)
    return i, dict(keep(res), u=u)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["primary", "k7", "null"])
    ap.add_argument("--out", default="/data/ensemble")
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--b", type=int, default=300)
    ap.add_argument("--null-from", type=int, default=0)
    ap.add_argument("--null-to", type=int, default=None)
    ap.add_argument("--only", default=None, help="primary: yalnızca bu tür görevler (virgüllü; main,abl,nb,cost,win,bh,cap500)")
    ap.add_argument("--smoke", action="store_true", help="boru hattı denemesi: kısa pencere; --out ayrı olmalı; sonuçlar karar için kullanılmaz")
    a = ap.parse_args()
    if a.smoke:
        MAIN, K7_WINDOW, HALVES, SHIFTS = ("2021-11-01", "2022-02-01"), ("2025-01-01", "2025-02-01"), [("2021-11-01", "2021-12-15")], [("2021-12-01", "2022-02-01")]
    Path(a.out).mkdir(parents=True, exist_ok=True)
    dh, t0 = ledger.sha(Path("/repo/data_manifest/manifest.json").read_text() + Path("/repo/data_manifest/manifest_pre2022.json").read_text()), time.time()
    roots = [("/data/pre2022", None, SPLIT), ("/data", SPLIT, None)]
    if a.stage == "k7":
        m = tape.membership("/data").groupby("sym").month.nunique()  # sinyalden bağımsız kural (full_systems / search replikasyon K7)
        syms = sorted(s for s, n in m.items() if n >= 8 and s not in EXT and s not in tape._usable("/data") and tape.load("/data", s)["klines"].index[0] <= pd.Timestamp("2023-07-01", tz="UTC"))
        print("K7 evreni:", syms, flush=True)
        load(syms, [("/data", None, None)])
        sp = spec(16, 2)
        res, win, _ = run(en.Params(), sp, window=K7_WINDOW, syms=syms)
        sym_net = {s: float(report.hourly_pnl(win[s]["kl"], win[s].get("mark"), win[s].get("funding"), res["fills"][res["fills"].sym == s], sp).sum()) for s in win}
        Path(a.out, "k7.json").write_text(json.dumps(dict(summary=keep(res), daily=daily(report.book_pnl(win, res, sp)), syms=syms, sym_net=sym_net)))
        print(f"k7 bitti {time.time() - t0:.0f}s", keep(res), flush=True)
        raise SystemExit(0)
    load(EXT, roots)
    print("veri:", {s: (str(D[s]["kl"].index[0]), str(D[s]["kl"].index[-1]), len(D[s]["kl"])) for s in EXT}, flush=True)
    with ProcessPoolExecutor(a.procs) as ex:
        if a.stage == "primary":
            btc = D["BTCUSDT"]["kl"].close.resample("1D").last()
            Path(a.out, "btc_close.json").write_text(json.dumps({str(k.date()): float(v) for k, v in btc.items()}))
            tasks = [("main", None), ("bh", None), ("cap500", None)] + [("abl", k) for k in ABL] + [("nb", k) for k in NB] + [("cost", c) for c in COSTS] + [("win", w) for w in HALVES + SHIFTS]
            if a.only:
                tasks = [t for t in tasks if t[0] in a.only.split(",")]
            res = {}
            for k, v in ex.map(task, [(kind, name, a.out, dh) for kind, name in tasks], chunksize=1):
                res[k] = v
                print(f"{k} {time.time() - t0:.0f}s net={v['summary']['net_pnl']:.0f}", flush=True)
            tag = "" if not a.only else "_" + a.only.replace(",", "_")
            Path(a.out, f"primary{tag}.json").write_text(json.dumps(res))
        else:
            hi = a.b if a.null_to is None else a.null_to
            res = dict(ex.map(null_draw, range(a.null_from, hi), chunksize=1))
            Path(a.out, f"null_{a.null_from}_{hi}.json").write_text(json.dumps(res))
    print(f"{a.stage} bitti {time.time() - t0:.0f}s", flush=True)
