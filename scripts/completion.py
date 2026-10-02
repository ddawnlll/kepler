"""BACKTEST tamamlama işçisi (Modal'de koşar): reports/backtest_completion_protocol.md ve reports/nested_wf_protocol.md'deki araç uygulamaları. Parametreler protokolde sabit.

  --stage base       tam Turtle S1/S2 taban koşusu -> tarihsel stres (madde 1) + işlem sırası Monte Carlo (madde 2)
  --stage capacity   sermaye 500 / 10k / 100k + karekök etki (madde 3)
  --stage risk       equity_scale + portföy kill switch, 6 deneme (deftere; madde 4)
  --stage misc       risk.vol_target duman testi (BTC, 3 deneme) + tape.aggregate kontrolü (madde 4b)
  --stage pbo        PBO/CSCV + SPA, 88 yapılandırma (madde 5)
  --stage nested     --family <aile>: nested WF için sürekli koşu 2022-01-01 -> 2026-04-01 (deftere; ön kayıt reports/nested_wf_protocol.md)
  --stage nested_report   nested WF analizi (6 ailenin çıktısından)
Çıktı: --out altında JSON + MD."""
import argparse
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

import full_systems as fs
import g2
import search
from kepler import capacity, ledger, nested, referee, report, robust, stats, stress, tape, turtle
from kepler import evaluate as ev
from kepler import signals as sg

EXT, MAIN, SYSTEMS = g2.EXT, fs.MAIN, fs.SYSTEMS
CAP = 10_000.0
QV: dict = {}  # sembol -> kline close + quote_volume
NAMED = {"LUNA": ("2022-05-05", "2022-05-16"), "FTX": ("2022-11-06", "2022-11-15"), "2024-08": ("2024-08-01", "2024-08-12")}
SEARCH_WIN, NESTED_WIN = search.SEARCH, ("2022-01-01", "2026-04-01")
TOTAL_CAP = 9 * g2.CAP  # arama/nested getirisi = 9 sembol toplamı / 18 000


def utc(w):
    return tuple(pd.Timestamp(x, tz="UTC") for x in w)


def load(root):
    fs.load(root, EXT)
    for s in EXT:
        k = tape.load(root, s)["klines"]
        QV[s] = k[["close", "quote_volume"]]


def step_for(C: float, s: str) -> str:
    return format(Decimal(10) ** (math.floor(math.log10(0.25 * C / fs.D[s]["kl"].close.max())) - 3), "f")  # protokol (madde 3): 10^(⌊log10(0,25·C / en yüksek kapanış)⌋ − 3)


def spec_c(C=CAP, fee=10.0, slip=2.0, **kw) -> referee.Spec:
    return referee.Spec(capital=C, leverage=10, liq=True, fee_rt_bps=fee, slip_rt_bps=slip, gross_cap=4 * C, **kw)


def data_c(C=CAP) -> dict:
    return {s: dict(fs.D[s], step=step_for(C, s)) if C != CAP else fs.D[s] for s in EXT}


def book_c(sysname, C=CAP, **variant):
    e, x = SYSTEMS[sysname]
    return lambda kls: turtle.turtle_book(kls, {s: sg.turtle(e, x) for s in kls}, C, fs.GROUPS, marks={s: fs.D[s]["mark"] for s in kls}, ticks={s: float(fs.D[s]["tick"]) for s in kls}, **variant)[0]


def run_base(sysname, C=CAP, spec=None, variant=None):
    data = data_c(C)
    out = book_c(sysname, C, **(variant or {}))({s: d["kl"] for s, d in data.items()})
    sp = spec or spec_c(C)
    res, win, _ = ev.run_book(out, data, sp, *utc(MAIN))
    return out, res, win, sp


def annual_sharpe(pnl_daily: pd.Series, capital: float) -> float:
    return stats.annual(stats.moments(stats.sharpe_series(pnl_daily, capital).to_numpy())[0])


def trade_nets(res, sp) -> pd.DataFrame:
    """Protokol madde 2: işlem başına net = fiyat PnL'si − toplam maliyet × notional payı + toplam funding × (notional × saat) payı."""
    end = int(pd.Timestamp(utc(MAIN)[1]).value)  # sonda açık bacaklar pencere sonu kapanışından değerlenir (inceleme bulgusu 1: aksi halde Σ işlem ≠ hakem net)
    tr = pd.concat([report.trades(res["fills"][res["fills"].sym == s], fs.D[s]["kl"].close.iloc[-1], end).assign(sym=s) for s in res["fills"].sym.unique()], ignore_index=True)
    tr = tr.sort_values(["closed", "sym"], kind="stable").reset_index(drop=True)
    s = res["summary"]
    cost = s["fee"] + s["slippage"] + s["liq_fee"] + s["exit_cost"]
    tr["net"] = tr.pnl - cost * tr.notional / tr.notional.sum() + s["funding"] * (tr.notional * tr.hours) / (tr.notional * tr.hours).sum()
    return tr


def base_stage(a):
    out, rows, md = Path(a.out), {}, ["# Tarihsel stres + işlem sırası Monte Carlo (otomatik; reports/backtest_completion_protocol.md madde 1-2)", ""]
    kl = {s: fs.D[s]["kl"] for s in EXT}
    lo, hi = utc(MAIN)
    close = {s: kl[s].close for s in EXT}
    dclose = pd.DataFrame({s: close[s].resample("1D").last() for s in EXT})
    dclose = dclose[(dclose.index >= lo) & (dclose.index < hi)]
    top = stress.drop_days(dclose, 3, 7, exclude=tuple(NAMED.values()))
    abs5 = stress.drop_days(dclose, 5, 1)
    wins = dict(NAMED, **{f"düşüş {d.date()}": (str((d - pd.Timedelta(days=2)).date()), str((d + pd.Timedelta(days=3)).date())) for d, _ in top})
    md += ["Seçilen en büyük günlük sepet düşüşleri (adlı pencereler dışı, ≥7 gün ara): " + ", ".join(f"{d.date()} ({100 * v:.1f}%)" for d, v in top),
           "Mutlak en kötü 5 gün (dışlama yok): " + ", ".join(f"{d.date()} ({100 * v:.1f}%)" for d, v in abs5), ""]
    res_all = {"top": [(str(d.date()), v) for d, v in top], "abs5": [(str(d.date()), v) for d, v in abs5], "stress": {}, "mc": {}}
    for sysname in SYSTEMS:
        for var, kw in (("full", {}), ("no_stop", dict(stop=False))):
            outb, res, win, sp = run_base(sysname, variant=kw)
            pnl = report.book_pnl(win, res, sp)
            s = res["summary"]
            print(sysname, var, "net", round(s["net_pnl"], 2), "n_stop", s["n_stop"], "rej", s["n_rejected"], flush=True)
            res_all["stress"][f"{sysname}_{var}"] = dict(net=s["net_pnl"], n_rejected=int(s["n_rejected"]), recon=float(pnl.sum() - s["net_pnl"]),
                                                         windows={w: dict(stress.window_stats(pnl, res["fills"], *wins[w], CAP, close, {k: outb[k].stop for k in EXT}, kl), basket=stress.basket_return(close, *wins[w])) for w in wins})
            if var == "full":
                tr = trade_nets(res, sp)
                nets = tr.net.to_numpy() / CAP
                paths = stats.trade_mc(nets, 5000, 0)
                dd, streak, worst = stats.path_stats(paths)
                a_dd, a_streak, a_worst = (float(v[0]) for v in stats.path_stats(nets[None, :]))
                q = lambda v: {k: float(np.quantile(v, p)) for k, p in (("p05", .05), ("p50", .5), ("p95", .95), ("p99", .99))}  # noqa: E731
                dd95 = float(np.quantile(dd, .95))
                s_star = 0.25 / dd95
                dd99_s = float(np.quantile(dd, .99)) * s_star
                rec = min(dd99_s, 0.30)
                ths = (0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)
                res_all["mc"][sysname] = dict(n_trades=len(tr), recon=float(tr.net.sum() - s["net_pnl"]), net_trades=float(tr.net.sum()), dd=q(dd), streak=q(streak), worst_run=q(worst), actual=dict(dd=a_dd, streak=a_streak, worst_run=a_worst),
                                              actual_dd_pctile=float((dd <= a_dd).mean()), dd95=dd95, s_star=s_star, dd99_scaled=dd99_s, rec_kill=rec, win_rate=float((tr.net > 0).mean()),
                                              kill_table={str(t): dict(scaled=stats.kill_stats(paths * s_star, t), unscaled=stats.kill_stats(paths, t)) for t in ths})
    Path(out, "base.json").write_text(json.dumps(res_all, indent=1, default=float))
    print("base bitti", flush=True)


def capacity_stage(a):
    res_all = {}
    for sysname in SYSTEMS:
        for C in (500.0, 10_000.0, 100_000.0):
            outb, res, win, sp = run_base(sysname, C)
            pnl = report.book_pnl(win, res, sp)
            tab = capacity.fill_table(res["fills"], QV)
            s = res["summary"]
            d = dict(net=s["net_pnl"], gross=s["gross_pnl"], n_fills=int(s["n_fills"]), n_rejected=int(s["n_rejected"]), n_liq=int(s["n_liq"]), traded=float(tab.notional.sum()), part=capacity.summary(tab), sharpe_base=annual_sharpe(pnl.resample("1D").sum(), C), y={})
            for y in (0.5, 1.0, 2.0):
                cost = capacity.impact_cost(tab, y)
                adj = pnl - capacity.hourly_cost(tab, cost, pnl.index)
                d["y"][str(y)] = dict(cost=float(cost.sum()), net_after=float(s["net_pnl"] - cost.sum()), sharpe_after=annual_sharpe(adj.resample("1D").sum(), C), cost_over_gross=float(cost.sum() / s["gross_pnl"]) if s["gross_pnl"] > 0 else None)
            res_all[f"{sysname}_{int(C)}"] = d
            print(sysname, C, round(s["net_pnl"], 1), d["part"]["share_over"], flush=True)
    Path(a.out, "capacity.json").write_text(json.dumps(res_all, indent=1, default=float))


def risk_stage(a):
    dh, res_all = ledger.sha(Path("/repo/data_manifest/manifest.json").read_text()), {}
    led = Path(a.out) / "ledger_risk.jsonl"
    for sysname in SYSTEMS:
        e, x = SYSTEMS[sysname]
        base_out, base_res, base_win, base_sp = run_base(sysname)
        variants = {"base": (None, False), "eq_scale": (None, True), "fixed_kill25": (0.25, False), "eq_scale_kill25": (0.25, True)}
        for name, (kill, eq) in variants.items():
            sp = spec_c(equity_scale=eq)
            data = data_c()
            book = book_c(sysname)
            if name == "base":
                res, win, tripped, trial = base_res, base_win, None, None
            else:
                try:
                    r = ev.evaluate_book(book, data, [sp], led, f"risk motoru {sysname} {name} (reports/backtest_completion_protocol.md madde 4)", dh, f"{sysname}_{name}", dict(sys=sysname, var=name), MAIN, kill)[0]
                    res, win, tripped, trial = r["res"], r["win"], r["row"]["config"]["kill_at"], r["row"]["trial"]
                except ValueError as err:  # hesap sıfırlandı, marj reddi: hakem kuralı deftere yazmaz (full_systems ile aynı kural); N'ye sayılır, geçersiz işaretlenir
                    if "reddedilen" not in str(err):
                        raise
                    res, win, tr_ = ev.run_book(book({s: d["kl"] for s, d in data.items()}), data, sp, *utc(MAIN), kill)
                    tripped, trial = str(tr_), None
            pnl = report.book_pnl(win, res, sp)
            eq_h = sp.capital + pnl.cumsum()
            dd_h = float(((eq_h.cummax().clip(lower=sp.capital) - eq_h) / eq_h.cummax().clip(lower=sp.capital)).max())
            dpnl = pnl.resample("1D").sum()
            eq_d = sp.capital + dpnl.cumsum()
            ret = dpnl / eq_d.shift(1).fillna(sp.capital)
            dd_d = float(((eq_d.cummax().clip(lower=sp.capital) - eq_d) / eq_d.cummax().clip(lower=sp.capital)).max())
            s = res["summary"]
            res_all[f"{sysname}_{name}"] = dict(net=s["net_pnl"], final_equity=float(eq_h.iloc[-1]), sharpe=stats.annual(stats.moments(ret.to_numpy())[0]), sharpe_fixed_capital=annual_sharpe(dpnl, sp.capital), dd_hourly=dd_h, dd_daily=dd_d,
                                                n_fills=int(s["n_fills"]), n_stop=int(s["n_stop"]), n_liq=int(s["n_liq"]), n_rejected=int(s["n_rejected"]), kill_at=tripped, trial=trial, boot=stats.bootstrap_summary(ret.to_numpy()) if name != "base" else None,
                                                invalid=bool(s["n_rejected"] > 0))
            print(sysname, name, round(s["net_pnl"], 1), dd_h, tripped, flush=True)
    Path(a.out, "risk.json").write_text(json.dumps(res_all, indent=1, default=float))


def misc_stage(a):
    """Protokol madde 4b: BTCUSDT turtle(20,10) sabit notional / vol_target / vol_target + kill 0,25 (3 deneme) + tape.aggregate gerçek veri kontrolü."""
    from kepler import risk
    kl, mark, funding = g2.D["BTCUSDT"]
    sig, led, dh = sg.turtle(20, 10), Path(a.out) / "ledger_misc.jsonl", ledger.sha(Path("/repo/data_manifest/manifest.json").read_text())
    sp = g2.spec_for(kl, 10, g2.SLIP)
    out = {}
    for name, size, kill in (("fixed_1000", None, None), ("vol_target", lambda k, u, c: risk.vol_target(k, u, c), None), ("vol_target_kill25", lambda k, u, c: risk.vol_target(k, u, c), 0.25)):
        r = ev.evaluate(sig, kl, [sp], led, f"risk motoru duman testi BTC turtle(20,10) {name} (reports/backtest_completion_protocol.md madde 4b)", dh, funding, mark, g2.NOTIONAL, name, dict(name=name), None, size, kill)[0]
        pnl = report.hourly_pnl(kl, mark, funding, r["res"]["fills"], sp)
        eq = sp.capital + pnl.cumsum()
        peak = eq.cummax().clip(lower=sp.capital)
        s = r["res"]["summary"]
        pos = r["res"]["fills"].assign(n=lambda f: f.qty * f.px)
        out[name] = dict(net=s["net_pnl"], gross=s["gross_pnl"], fee=s["fee"], n_fills=int(s["n_fills"]), n_liq=int(s["n_liq"]), dd=float(((peak - eq) / peak).max()), kill_at=r["row"]["config"]["kill_at"], mean_fill_notional=float(pos.n.mean()), trial=r["row"]["trial"])
    ag = {}
    for f in ("4h", "1D"):
        g = tape.aggregate(kl, f)
        ag[f] = dict(n_bars=len(g), volume_conserved=bool(abs(g.volume.sum() - kl.volume.sum()) < 1e-6 * kl.volume.sum()), first_open_ok=bool(g.open.iloc[0] == kl.open.iloc[0]), last_close_ok=bool(g.close.iloc[-1] == kl.close.iloc[-1]),
                     n_sum=int(g.n.sum()), n_expected=len(kl), high_ok=bool(g.high.max() == kl.high.max()), low_ok=bool(g.low.min() == kl.low.min()))
    out["aggregate"] = ag
    Path(a.out, "misc.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, default=float), flush=True)


def pbo_stage(a):
    cols, fam = {}, {}
    for f in search.FAMILIES:
        d = json.loads(Path(a.search, f"search_{f}.json").read_text())
        for name in d["cfgs"]:
            cols[name] = pd.DataFrame({s: v["daily"] for s, v in d["res"][name].items()}).sum(axis=1)
            fam[name] = f
    R = pd.DataFrame(cols) / TOTAL_CAP
    R.index = pd.to_datetime(R.index)
    out = dict(shape=list(R.shape), cscv={}, spa={})
    for f in (None, *search.FAMILIES):
        c = [n for n in R.columns if f is None or fam[n] == f]
        r = stats.cscv(R[c].to_numpy(), 16)
        out["cscv"][f or "all"] = dict(n=len(c), pbo=r["pbo"], lam_median=r["lam_median"], loss=r["loss"], n_splits=r["n_splits"])
    load_syms = {s: fs.D[s] for s in EXT}
    bh_res, bh_pnl = robust.buy_hold(load_syms, referee.Spec(capital=TOTAL_CAP, leverage=10, liq=True, fee_rt_bps=10.0, slip_rt_bps=2.0), 1000.0, SEARCH_WIN)
    bh = (bh_pnl.resample("1D").sum() / TOTAL_CAP).rename(lambda t: t.tz_localize(None))
    bh = bh.reindex(R.index).fillna(0.0)
    names = list(R.columns)
    for label, bench in (("cash", 0.0), ("buy_hold", bh.to_numpy()[:, None])):
        sp = stats.spa(R.to_numpy() - bench, 20.0, 2000, 0, 20)
        out["spa"][label] = dict(stat=sp["stat"], best=names[sp["best"]], t_best=float(sp["t"][sp["best"]]), p_lower=sp["p_lower"], p_consistent=sp["p_consistent"], p_upper=sp["p_upper"], n=sp["n"], K=sp["K"])
    out["bh_sharpe"] = stats.annual(stats.moments(bh.to_numpy())[0])
    out["best_sharpe"] = {n: stats.annual(stats.moments(R[n].to_numpy())[0]) for n in sorted(names, key=lambda n: -stats.moments(R[n].to_numpy())[0])[:5]}
    Path(a.out, "pbo.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out["cscv"]["all"]), out["spa"], flush=True)


def nested_stage(a):
    search.P["close"] = pd.DataFrame({s: sg._daily(g2.D[s][0]).close for s in EXT})
    search.P["fund"] = pd.DataFrame({s: g2.D[s][0].fund_hr.resample("1D").mean() for s in EXT})
    dh = ledger.sha(Path("/repo/data_manifest/manifest.json").read_text())
    cfgs = search.configs(a.family)
    tasks = [(a.family, name, p, s, NESTED_WIN, [g2.spec_for(g2.D[s][0], 10, g2.SLIP)], a.out, dh, "nested") for name, p in cfgs for s in EXT]
    res = {}
    with ProcessPoolExecutor(a.procs) as ex:
        for name, sym, rows in ex.map(search.one, tasks, chunksize=2):
            res.setdefault(name, {})[sym] = dict(daily=rows[0]["daily"], net=rows[0]["net_pnl"], n_rejected=rows[0]["n_rejected"])
    Path(a.out, f"nested_{a.family}.json").write_text(json.dumps(dict(family=a.family, cfgs=dict(cfgs), res=res)))


def nested_report(a):
    cols = {}
    for f in search.FAMILIES:
        d = json.loads(Path(a.out, f"nested_{f}.json").read_text())
        for name, _ in search.configs(f):
            cols[name] = pd.DataFrame({s: v["daily"] for s, v in d["res"][name].items()}).sum(axis=1)
    R = pd.DataFrame(cols) / TOTAL_CAP
    R.index = pd.to_datetime(R.index)
    out = nested.run(R)
    oos = out["oos"]
    days = R.index[(R.index >= nested.FOLDS[0][0]) & (R.index < nested.FOLDS[-1][1])]
    trial_srs = [stats.moments(R[c].loc[days].to_numpy())[0] for c in R.columns]
    rnd = nested.random_sharpes(R, nested.FOLDS, 5000, 0)
    sr = stats.moments(oos.to_numpy())[0]
    res = dict(n_cfg=R.shape[1], steps=[dict(s, oos=list(s["oos"])) for s in out["steps"]], oos_net=float(oos.sum() * TOTAL_CAP), oos_sharpe=stats.annual(sr), psr0=stats.psr(oos.to_numpy()), dsr=stats.dsr(oos.to_numpy(), trial_srs),
               max_dd=float(stats.max_drawdown(oos.to_numpy())), p_random=stats.rotation_p(sr, rnd), random_median_sharpe=stats.annual(float(np.median(rnd))), random_p95_sharpe=stats.annual(float(np.quantile(rnd, .95))),
               mean_config_net=float(R.loc[days].sum().mean() * TOTAL_CAP), median_config_net=float(R.loc[days].sum().median() * TOTAL_CAP), best_config_oos=R.loc[days].sum().idxmax(), n_days=len(oos),
               invalid=sum(1 for f in search.FAMILIES for n in json.loads(Path(a.out, f"nested_{f}.json").read_text())["res"].values() for v in n.values() if v["n_rejected"] > 0))
    Path(a.out, "nested_report.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["base", "capacity", "risk", "misc", "pbo", "nested", "nested_report"])
    ap.add_argument("--root", default="/data")
    ap.add_argument("--out", default="/data/completion")
    ap.add_argument("--search", default="/data/search")
    ap.add_argument("--family", default="")
    ap.add_argument("--procs", type=int, default=4)
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if a.stage == "nested":
        g2.load(a.root, EXT)
    elif a.stage == "misc":
        g2.load(a.root, EXT)
    elif a.stage != "nested_report":
        load(a.root)
    {"base": base_stage, "capacity": capacity_stage, "risk": risk_stage, "misc": misc_stage, "pbo": pbo_stage, "nested": nested_stage, "nested_report": nested_report}[a.stage](a)
    print(f"{a.stage} bitti {time.time() - t0:.0f}s", flush=True)
    sys.exit(0)
