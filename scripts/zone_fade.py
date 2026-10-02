"""Zone Fade v1 işçisi: reports/zone_fade_protocol.md. Parametreler protokolde sabit; burada ayarlanmaz.

  --stage primary  birincil (evaluate_book: denetim + defter, N = 1) + kontroller: 4 ablasyon (K8), 8 komşu (K5), maliyet/gecikme (K3), pencere/kaydırma (K6), al-tut (K2)
  --stage second   2020-07 -> 2022-01 ikinci pencere (bilgi; deftersiz): birincil kural + al-tut
  --stage k7       çapraz varlık (K7: kullanılmamış 14 sembol, 2023-07 -> 2026-04, fee 16 + slip 2)
  --stage null     K1 rotasyon null'u (--null-from/--null-to ile bölünür; --null-mode rel (birincil) | abs (protokol lafzı, bilgi))
Veri: --root (birincil: <root>/tape, 2022-01 -> 2026-03) ve <root>/pre2022 (2020-01 -> 2021-12). Çıktı --out altında JSON; özet scripts/zone_fade_report.py."""
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

from kepler import evaluate as ev
from kepler import ledger, referee, report, robust, tape
from kepler import signals as sg
from kepler.experts import zone_fade as zf

REPO = Path(__file__).resolve().parent.parent
EXT = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT"]
CAP = 10_000.0
MAIN, PRE, K7_WINDOW = ("2022-07-01", "2026-04-01"), ("2020-07-01", "2022-01-01"), ("2023-07-01", "2026-04-01")
EDGES = ["2022-07-01", "2023-01-01", "2023-07-01", "2024-01-01", "2024-07-01", "2025-01-01", "2025-07-01", "2026-01-01", "2026-04-01"]
HALVES = list(zip(EDGES[:-1], EDGES[1:]))
SHIFTS = [(a, b) for a, b in robust.shift_windows(*MAIN)]
COSTS = [(4, 2, 0), (16, 2, 0), (10, 6, 0), (16, 6, 0), (10, 2, 1)]
ABL = ("no_impulse", "no_trigger", "no_poc", "no_rr")
NB = [(w, i) for w in (0.75, 1.0, 1.25) for i in (3.0, 4.0, 5.0) if (w, i) != (1.0, 4.0)]
HYP = "Zone Fade v1: arz/talep bölgesinden dönüş, hacim profili (POC) hedefli (reports/zone_fade_protocol.md)"
D: dict = {}  # sembol -> dict(kl [OHLCV + fund_hr], funding, mark, tick, step); fork ile paylaşılır
OUT0: dict = {}  # birincil kitap çıktısı (fork ile paylaşılır; null, maliyet ve pencere koşuları bunu kullanır)
NULL_REL = True


def load(syms, roots, cap=CAP):
    for s in syms:
        parts = [tape.load(r, s, start=lo, end=hi) for r, lo, hi in roots]
        parts = [p for p in parts if len(p["klines"])]
        d = {k: pd.concat([p[k] for p in parts]).sort_index() for k in ("klines", "mark", "funding")}
        for k in d:
            d[k] = d[k][~d[k].index.duplicated()]
        kl = sg.with_funding(d["klines"][["open", "high", "low", "close", "volume"]], d["funding"])
        q = Decimal(10) ** (math.floor(math.log10(kl.close.min())) - 5)  # sembol kuralları UNKNOWN: sinyal-bağımsız çözünürlük (ensemble/full_systems ile aynı kural)
        st = Decimal(10) ** (math.floor(math.log10(0.25 * cap / kl.close.max())) - 3)
        D[s] = dict(kl=kl, funding=d["funding"], mark=d["mark"], tick=format(q, "f"), step=format(st, "f"))


def spec(fee=10.0, slip=2.0, delay=0, cap=CAP) -> referee.Spec:
    return referee.Spec(capital=cap, leverage=10, liq=True, fee_rt_bps=fee, slip_rt_bps=slip, delay=delay, gross_cap=3 * cap, mmr=0.005)


def utc(w):
    return tuple(pd.Timestamp(x, tz="UTC") for x in w)


def keep(res):
    s = res["summary"]
    return {k: float(s[k]) for k in ("net_pnl", "gross_pnl", "fee", "slippage", "funding", "exit_cost", "liq_fee", "n_fills", "n_liq", "n_stop", "n_rejected", "funding_missed")}


def daily(pnl):
    return {str(k.date()): float(v) for k, v in pnl.resample("1D").sum().items()}


def data_of(syms):
    return {s: D[s] for s in syms}


def book_of(p, syms):
    return zf.make_book(CAP, p, {s: D[s]["mark"] for s in syms}, {s: float(D[s]["tick"]) for s in syms})


def trades_of(res, win):
    """Hakem dolumlarından işlem tablosu (sembol başına report.trades; açık kalan bacak son kapanıştan)."""
    f, rows = res["fills"], []
    for s, d in win.items():
        t = report.trades(f[f.sym == s], float(d["kl"].close.iloc[-1]), int((d["kl"].index[-1] + pd.Timedelta("1h")).as_unit("ns").value))
        rows += [dict(sym=s, opened=str(r.opened), closed=str(r.closed), side=r.side, notional=r.notional, hours=r.hours, gross_bps=r.gross_bps, pnl=r.pnl) for r in t.itertuples()]
    return rows


def cands_of(book):
    return [dict(sym=c.sym, side=c.side, born=str(c.born), state=c.state, why=c.why, ref=c.ref, stop=c.stop, target=c.target, zone=list(c.zone), va=c.va, atr=c.atr,
                 t_entry=str(c.t_entry), t_exit=str(c.t_exit)) for c in book.log]


def run(p, sp, window=None, syms=EXT, out=None):
    window, data = window or MAIN, data_of(syms)  # varsayılan çağrı anında (--smoke MAIN'i değiştirir)
    out = out if out is not None else book_of(p, syms)({s: x["kl"] for s, x in data.items()})
    res, win, _ = ev.run_book(out, data, sp, *utc(window))
    return res, win


def pack(res, win, sp):
    return dict(summary=keep(res), daily=daily(report.book_pnl(win, res, sp)), n_trades=len(trades_of(res, win)))


def task(a):
    kind, name, out_dir, dh = a
    p = zf.Params()
    sp = spec()
    if kind == "main":
        data = data_of(EXT)
        book = book_of(p, EXT)
        r = ev.evaluate_book(book, data, [sp], Path(out_dir) / "ledger_zf1.jsonl", HYP, dh, "ZF1", asdict(p), MAIN)[0]
        book({s: x["kl"] for s, x in data.items()})  # son çağrı gerçek veriyle: book.log
        pnl = report.book_pnl(r["win"], r["res"], sp)
        fills = r["res"]["fills"]
        sym_net = {s: float(report.hourly_pnl(r["win"][s]["kl"], r["win"][s].get("mark"), r["win"][s].get("funding"), fills[fills.sym == s], sp).sum()) for s in r["win"]}
        return "main", dict(summary=keep(r["res"]), daily=daily(pnl), sym_net=sym_net, trades=trades_of(r["res"], r["win"]), cands=cands_of(book), recon=float(pnl.sum() - r["res"]["summary"]["net_pnl"]),
                            row_trial=r["row"]["trial"], traded=float((fills.qty * fills.px).sum()))
    if kind == "abl":
        q = replace(p, ablate=name)
        res, win = run(q, sp)
        return f"abl_{name}", pack(res, win, sp)
    if kind == "nb":
        w, i = name
        res, win = run(replace(p, width=w, impulse=i), sp)
        return f"nb_{w}_{i}", dict(pack(res, win, sp), params=dict(width=w, impulse=i))
    if kind == "cost":
        fee, slip, delay = name
        s2 = spec(fee, slip, delay)
        res, win = run(p, s2, out=OUT0)
        return f"cost_{fee}_{slip}_{delay}", pack(res, win, s2)
    if kind == "win":
        res, win = run(p, sp, window=name, out=OUT0)
        return f"win_{name[0]}_{name[1]}", dict(summary=keep(res))
    if kind == "bh":
        res, pnl = robust.buy_hold(data_of(EXT), replace(sp, gross_cap=None), CAP / len(EXT), MAIN)
        return "bh", dict(summary=keep(res), daily=daily(pnl))


def null_draw(i):
    u = float(np.random.default_rng([0, i]).uniform(0.05, 0.95))  # ortak ofset: tüm semboller aynı kaydırma
    lo, hi = utc(MAIN)
    out = zf.rotate_book(OUT0, {s: D[s]["kl"] for s in EXT}, lo, hi, u, relative=NULL_REL)
    res, _ = run(zf.Params(), spec(), out=out)
    return i, dict(keep(res), u=u)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["primary", "second", "k7", "null"])
    ap.add_argument("--root", default="/data")
    ap.add_argument("--out", default="/data/zone_fade")
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--b", type=int, default=500)
    ap.add_argument("--null-from", type=int, default=0)
    ap.add_argument("--null-to", type=int, default=None)
    ap.add_argument("--null-mode", default="rel", choices=["rel", "abs"])
    ap.add_argument("--smoke", action="store_true", help="boru hattı denemesi: kısa pencereler; --out ayrı olmalı; sonuçlar karar için kullanılmaz")
    ap.add_argument("--only", default=None, help="primary: yalnızca bu tür görevler (virgüllü; main,abl,nb,cost,win,bh)")
    a = ap.parse_args()
    NULL_REL = a.null_mode == "rel"
    if a.smoke:
        MAIN, HALVES, SHIFTS, PRE, K7_WINDOW = ("2022-09-15", "2022-11-15"), [("2022-09-15", "2022-10-15")], [("2022-10-01", "2022-11-15")], ("2020-10-01", "2020-12-01"), ("2023-07-01", "2023-09-01")
    Path(a.out).mkdir(parents=True, exist_ok=True)
    man = REPO / "data_manifest"
    dh, t0 = ledger.sha((man / "manifest.json").read_text() + (man / "manifest_pre2022.json").read_text()), time.time()
    root, pre = a.root, str(Path(a.root) / "pre2022")
    if a.stage == "k7":
        m = tape.membership(root).groupby("sym").month.nunique()  # sinyalden bağımsız kural (search replikasyon K7)
        first = json.loads((man / "manifest.json").read_text())["symbols"]  # ilk bar manifestten (dosya yüklemeden)
        syms = sorted(s for s, n in m.items() if n >= 8 and s not in EXT and s not in tape._usable(root) and pd.Timestamp(first[s]["klines"]["first"]) <= pd.Timestamp("2023-07-01", tz="UTC"))
        print("K7 evreni:", len(syms), syms, flush=True)
        load(syms, [(root, None, None)])
        sp = spec(16, 2)
        res, win = run(zf.Params(), sp, window=K7_WINDOW, syms=syms)
        sym_net = {s: float(report.hourly_pnl(win[s]["kl"], win[s].get("mark"), win[s].get("funding"), res["fills"][res["fills"].sym == s], sp).sum()) for s in win}
        Path(a.out, "k7.json").write_text(json.dumps(dict(summary=keep(res), daily=daily(report.book_pnl(win, res, sp)), syms=syms, sym_net=sym_net, n_trades=len(trades_of(res, win)))))
        print(f"k7 bitti {time.time() - t0:.0f}s", keep(res), flush=True)
        raise SystemExit(0)
    if a.stage == "second":
        load(EXT, [(pre, None, None)])
        print("veri:", {s: (str(D[s]["kl"].index[0]), str(D[s]["kl"].index[-1])) for s in EXT}, flush=True)
        sp, p = spec(), zf.Params()
        book = book_of(p, EXT)
        out = book({s: D[s]["kl"] for s in EXT})
        res, win, _ = ev.run_book(out, data_of(EXT), sp, *utc(PRE))
        bres, bpnl = robust.buy_hold(data_of(EXT), replace(sp, gross_cap=None), CAP / len(EXT), PRE)
        pnl = report.book_pnl(win, res, sp)
        Path(a.out, "second.json").write_text(json.dumps(dict(summary=keep(res), daily=daily(pnl), trades=trades_of(res, win), cands=cands_of(book), bh=dict(summary=keep(bres), daily=daily(bpnl)))))
        print(f"second bitti {time.time() - t0:.0f}s", keep(res), flush=True)
        raise SystemExit(0)
    load(EXT, [(root, "2022-01-01", None)])
    print("veri:", {s: (str(D[s]["kl"].index[0]), str(D[s]["kl"].index[-1]), len(D[s]["kl"])) for s in EXT}, flush=True)
    OUT0.update(book_of(zf.Params(), EXT)({s: D[s]["kl"] for s in EXT}))  # fork'tan önce: state önbelleği ve profiller çocuk süreçlere geçer
    print(f"birincil kitap hazır {time.time() - t0:.0f}s", flush=True)
    with ProcessPoolExecutor(a.procs) as ex:
        if a.stage == "primary":
            btc = D["BTCUSDT"]["kl"].close.resample("1D").last()
            Path(a.out, "btc_close.json").write_text(json.dumps({str(k.date()): float(v) for k, v in btc.items()}))
            tasks = [("main", None), ("bh", None)] + [("abl", k) for k in ABL] + [("nb", k) for k in NB] + [("cost", c) for c in COSTS] + [("win", w) for w in HALVES + SHIFTS]
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
            Path(a.out, f"null_{a.null_mode}_{a.null_from}_{hi}.json").write_text(json.dumps(res))
    print(f"{a.stage} bitti {time.time() - t0:.0f}s", flush=True)
