"""V4 işçisi (Modal'de koşar): tam Turtle S1/S2 (reports/full_systems_protocol.md). Aşamalar:

  primary  12 ön kayıtlı deneme (S1/S2 x full, no_stop, fixed_size, no_pyramid, no_limits, g2_equiv): evaluate_book (denetim + defter), günlük net PnL
  robust   sağlamlık koşuları (maliyet ızgarası, gecikme, komşuluk, pencereler, başlangıç kaydırma, al-tut): run_book (deftersiz, N'ye girmez)
  null     K1 rotasyon null'ı: --null-from/--null-to ile bölünür (her çekiliş = rotasyon + yönetici + portföy hakemi)
  k7       çapraz varlık (kural: scripts/search.py replikasyon evreni)
Çıktı: --out altında JSON dosyaları; özet scripts/full_systems_report.py. Parametreler protokolde sabit; burada ayarlanmaz."""
import argparse
import json
import math
import time
from concurrent.futures import ProcessPoolExecutor
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

import g2
from kepler import evaluate as ev
from kepler import ledger, referee, report, robust, tape, turtle
from kepler import signals as sg

CAP, L_MAX = 10_000.0, 4.0
SYSTEMS = {"S1": (20, 10), "S2": (55, 20)}
VARIANTS = {"full": {}, "no_stop": dict(stop=False), "fixed_size": dict(fixed=0.25 * CAP), "no_pyramid": dict(pyramid=False), "no_limits": dict(limits=False),
            "g2_equiv": dict(stop=False, pyramid=False, limits=False, fixed=1000.0)}
GROUPS = {**{s: "major" for s in ("BTCUSDT", "ETHUSDT", "BNBUSDT")}, **{s: "l1" for s in ("SOLUSDT", "AVAXUSDT", "ADAUSDT")}, **{s: "other" for s in ("XRPUSDT", "DOGEUSDT", "LINKUSDT")}}
MAIN, K7_WINDOW = ("2022-03-01", "2026-04-01"), ("2023-07-01", "2026-04-01")
COSTS = [(4, 2, 0), (9, 2, 0), (10, 2, 0), (11, 2, 0), (16, 2, 0), (10, 6, 0), (16, 6, 0), (10, 2, 1)]  # (fee, slip, delay); K3 stresleri: (16,6) ve gecikme 1
WINDOWS, NB_LIMIT = g2.WINDOWS, None  # --smoke: kısa pencereler ve 2 komşu (yalnızca boru hattı denemesi; sonuçlar karar için kullanılmaz)
D: dict = {}  # sembol -> dict(kl, funding, mark, tick, step); fork ile paylaşılır


def load(root, syms):
    for s in syms:
        d = tape.load(root, s)
        kl = d["klines"][["open", "high", "low", "close", "volume"]]
        q = Decimal(10) ** (math.floor(math.log10(kl.close.min())) - 5)  # sembol kuralları UNKNOWN: sinyal-bağımsız çözünürlük (protokol)
        st = Decimal(10) ** (math.floor(math.log10(0.25 * CAP / kl.close.max())) - 3)
        D[s] = dict(kl=kl, funding=d["funding"], mark=d["mark"], tick=format(q, "f"), step=format(st, "f"))


def spec(fee=10.0, slip=2.0, delay=0, cap=L_MAX * CAP) -> referee.Spec:
    return referee.Spec(capital=CAP, leverage=10, liq=True, fee_rt_bps=fee, slip_rt_bps=slip, delay=delay, gross_cap=cap)


def make_book(entry, exit_, variant, groups, u=None):
    """Kitap fabrikası: u verilirse yön sinyalleri rotasyon null'ı için ortak ofsetle kaydırılır."""
    def book(kls):
        dirs = {s: (robust.rotate_signal(sg.turtle(entry, exit_), u) if u is not None else sg.turtle(entry, exit_)) for s in kls}
        return turtle.turtle_book(kls, dirs, CAP, groups, marks={s: D[s]["mark"] for s in kls}, ticks={s: float(D[s]["tick"]) for s in kls}, **variant)[0]
    return book


def daily(pnl: pd.Series) -> dict:
    return {str(k.date()): float(v) for k, v in pnl.resample("1D").sum().items()}


def utc(w):
    return tuple(pd.Timestamp(x, tz="UTC") for x in w)


def keep(res, extra=None):
    s = res["summary"]
    return {k: float(s[k]) for k in ("net_pnl", "gross_pnl", "fee", "slippage", "funding", "exit_cost", "liq_fee", "n_fills", "n_liq", "n_stop", "n_rejected", "funding_missed")}


def primary(a):
    sysname, var, out, dh = a
    e, x = SYSTEMS[sysname]
    syms = list(g2.EXT)
    data = {s: D[s] for s in syms}
    book, sp = make_book(e, x, VARIANTS[var], GROUPS), spec()
    try:
        r = ev.evaluate_book(book, data, [sp], Path(out) / "ledger_run2.jsonl", f"V4 {sysname} {var}: tam Turtle (reports/full_systems_protocol.md)", dh, f"{sysname}_{var}", dict(sys=sysname, var=var, entry=e, exit=x), MAIN)[0]
        invalid = False
    except ValueError as err:  # ilk koşuda çöktü (S2 no_stop, S2 fixed_size: hesap sıfırlandı, marj reddi -> hakem kuralı deftere yazmaz). Denetim evaluate_book'ta zaten geçti; N=12'ye sayılır, geçersiz işaretlenir
        if "reddedilen" not in str(err):
            raise
        res, win, _ = ev.run_book(book({s: d["kl"] for s, d in data.items()}), data, sp, *utc(MAIN))
        r, invalid = dict(res=res, win=win, row=dict(trial=None)), True
    pnl = report.book_pnl(r["win"], r["res"], sp)
    info = turtle.turtle_book({s: D[s]["kl"] for s in syms}, {s: sg.turtle(e, x) for s in syms}, CAP, GROUPS, marks={s: D[s]["mark"] for s in syms}, ticks={s: float(D[s]["tick"]) for s in syms}, **VARIANTS[var])[1]
    sym_net = {s: float(report.hourly_pnl(r["win"][s]["kl"], r["win"][s].get("mark"), r["win"][s].get("funding"), r["res"]["fills"][r["res"]["fills"].sym == s], sp).sum()) for s in r["win"]}
    return f"{sysname}_{var}", dict(summary=keep(r["res"]), daily=daily(pnl), manager=info, sym_net=sym_net, recon=float(pnl.sum() - r["res"]["summary"]["net_pnl"]), row_trial=r["row"]["trial"], invalid=invalid)


def robust_task(a):
    kind, sysname, p = a
    e, x = SYSTEMS[sysname]
    syms = list(g2.EXT)
    data = {s: D[s] for s in syms}
    lo, hi = utc(MAIN)
    if kind == "bh":
        res, pnl = robust.buy_hold(data, spec(cap=None), CAP / len(syms), MAIN)
        return f"bh", dict(summary=keep(res), daily=daily(pnl))
    kls = {s: d["kl"] for s, d in data.items()}
    if kind == "cost":
        fee, slip, delay = p
        res, win, _ = ev.run_book(make_book(e, x, {}, GROUPS)(kls), data, spec(fee, slip, delay), lo, hi)
        return f"cost_{sysname}_{fee}_{slip}_{delay}", dict(summary=keep(res), daily=daily(report.book_pnl(win, res, spec(fee, slip, delay))))
    if kind == "nb":
        ne, nx = p
        res, win, _ = ev.run_book(make_book(ne, nx, {}, GROUPS)(kls), data, spec(), lo, hi)
        return f"nb_{sysname}_{ne}_{nx}", dict(summary=keep(res), daily=daily(report.book_pnl(win, res, spec())))
    if kind == "win":
        w = utc(p)
        res, win, _ = ev.run_book(make_book(e, x, {}, GROUPS)(kls), data, spec(), *w)
        return f"win_{sysname}_{p[0]}_{p[1]}", dict(summary=keep(res))


def null_draw(a):
    sysname, i = a
    e, x = SYSTEMS[sysname]
    u = float(np.random.default_rng([0, i]).uniform(0.05, 0.95))  # ortak ofset: tüm semboller aynı oranda kayar
    data = {s: D[s] for s in g2.EXT}
    lo, hi = utc(MAIN)
    out = make_book(e, x, {}, GROUPS, u)({s: d["kl"] for s, d in data.items()})
    res, _, _ = ev.run_book(out, data, spec(), lo, hi)
    return sysname, i, dict(keep(res), u=u)


def k7_task(a):
    sysname, syms = a
    e, x = SYSTEMS[sysname]
    data = {s: D[s] for s in syms}
    kls = {s: d["kl"] for s, d in data.items()}
    groups = {s: s for s in syms}  # korele grup bilgisi önceden yok: her sembol kendi grubu
    out = turtle.turtle_book(kls, {s: sg.turtle(e, x) for s in syms}, CAP, groups, marks={s: D[s]["mark"] for s in syms}, ticks={s: float(D[s]["tick"]) for s in syms})[0]
    res, win, _ = ev.run_book(out, data, spec(16, 2), *utc(K7_WINDOW))
    return f"k7_{sysname}", dict(summary=keep(res), syms=syms, sym_net={s: float(report.hourly_pnl(win[s]["kl"], win[s].get("mark"), win[s].get("funding"), res["fills"][res["fills"].sym == s], spec(16, 2)).sum()) for s in win})


def dump(path, items):
    Path(path).write_text(json.dumps(dict(items), indent=0))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["primary", "robust", "null", "k7"])
    ap.add_argument("--root", default="/data")
    ap.add_argument("--out", default="/data/full")
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--b", type=int, default=500)
    ap.add_argument("--null-from", type=int, default=0)
    ap.add_argument("--null-to", type=int, default=None)
    ap.add_argument("--smoke", action="store_true", help="boru hattı denemesi: kısa pencere, 2 komşu; --out ayrı olmalı")
    a = ap.parse_args()
    if a.smoke:
        MAIN, K7_WINDOW, WINDOWS, NB_LIMIT = ("2022-03-01", "2022-06-01"), ("2022-03-01", "2022-06-01"), [("2022-03-01", "2022-04-15"), ("2022-04-15", "2022-06-01")], 2
    Path(a.out).mkdir(parents=True, exist_ok=True)
    dh, t0 = ledger.sha(Path("/repo/data_manifest/manifest.json").read_text()), time.time()
    if a.stage == "k7":
        m = tape.membership(a.root).groupby("sym").month.nunique()  # sinyalden bağımsız kural (protokol, K7)
        syms = sorted(s for s, n in m.items() if n >= 8 and s not in g2.EXT and s not in tape._usable(a.root) and tape.load(a.root, s)["klines"].index[0] <= pd.Timestamp("2023-07-01", tz="UTC"))
        print("K7 evreni:", syms, flush=True)
        load(a.root, syms)
    else:
        load(a.root, g2.EXT)
    with ProcessPoolExecutor(a.procs) as ex:
        if a.stage == "primary":
            btc = D["BTCUSDT"]["kl"].close.resample("1D").last()
            Path(a.out, "btc_close.json").write_text(json.dumps({str(k.date()): float(v) for k, v in btc.items()}))
            dump(Path(a.out, "primary.json"), ex.map(primary, [(s, v, a.out, dh) for s in SYSTEMS for v in VARIANTS]))
        elif a.stage == "robust":
            tasks = [("bh", "S1", None)] + [("cost", s, c) for s in SYSTEMS for c in COSTS] + [("win", s, w) for s in SYSTEMS for w in WINDOWS + robust.shift_windows(*MAIN)]
            tasks += [("nb", s, (nb["entry"], nb["exit"])) for s, (e, x) in SYSTEMS.items() for nb in robust.neighbors(dict(entry=e, exit=x))[:NB_LIMIT]]
            dump(Path(a.out, "robust.json"), ex.map(robust_task, tasks, chunksize=1))
        elif a.stage == "null":
            hi = a.b if a.null_to is None else a.null_to
            res = {s: {} for s in SYSTEMS}
            for s, i, r in ex.map(null_draw, [(s, i) for i in range(a.null_from, hi) for s in SYSTEMS], chunksize=2):
                res[s][i] = r
            Path(a.out, f"null_{a.null_from}_{hi}.json").write_text(json.dumps(res))
        else:
            dump(Path(a.out, "k7.json"), ex.map(k7_task, [(s, syms) for s in SYSTEMS]))
    print(f"{a.stage} bitti {time.time() - t0:.0f}s", flush=True)
