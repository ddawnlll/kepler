"""2020–2021 replikasyon işçisi (Modal'de koşar): reports/pre2022_protocol.md. Mevcut işçi kodunu (full_systems, g2, search) yeni pencere/evrenle çağırır. Parametreler protokolde sabit; burada ayarlanmaz.

  --stage primary   Blok A: S1, S2, S1c, S2c (4 deneme, evaluate_book + deftere) + kontroller: 4 ablasyon (K8), ölçekli boyut (K4), betimleyici stres
  --stage robust    Blok A kontrolleri: maliyet ızgarası, pencereler, başlangıç kaydırma, komşuluk (24), al-tut, K7 (deftersiz; --shard i/n)
  --stage null      K1 rotasyon null'ı (--null-from/--null-to ile bölünür)
  --stage blockb    Blok B: 6 yapılandırma x 9 sembol x 6 maliyet (deftere; yalnız --null-from 0 parçasında) + rotasyon null'ı (B = 300, --null-from/--null-to ile bölünür)
Çıktı: --out altında JSON; özet scripts/pre2022_report.py."""
import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

import full_systems as fs
import g2
import search
from kepler import evaluate as ev
from kepler import audit, ledger, referee, report, robust, stress, tape, turtle
from kepler import signals as sg

CAP, END = fs.CAP, "2022-01-01"
MAIN = ("2020-03-01", END)
HALVES = [("2020-07-01", "2021-01-01"), ("2021-01-01", "2021-07-01"), ("2021-07-01", END)]
STRESS = {"covid": ("2020-03-09", "2020-03-16"), "2021-05": ("2021-05-17", "2021-05-24")}
SYSTEMS = {"S1": (20, 10, 20), "S2": (55, 20, 20), "S1c": (28, 14, 28), "S2c": (77, 28, 28)}  # giriş, çıkış, ATR penceresi (takvim düzeltmeli: 7/5)
RISK = {"S1": 0.0017, "S2": 0.0016, "S1c": 0.0017, "S2c": 0.0016}  # K4 planlanan boyut: backtest_completion.md madde 2 (S1c/S2c ayrıca türetilmez)
ABL = ("no_stop", "fixed_size", "no_pyramid", "no_limits")
COSTS = fs.COSTS
D, SYMS = fs.D, []


def utc(w):
    return fs.utc(w)


def book_for(sysname, var=None, u=None, risk=None, entry=None, exit_=None, groups=None):
    e, x, nd = SYSTEMS[sysname]
    variant = dict(nd=nd, **(fs.VARIANTS[var] if var else {}), **({} if risk is None else dict(risk=risk)))
    return fs.make_book(entry or e, exit_ or x, variant, groups or fs.GROUPS, u)


def run(sysname, spec, window=None, syms=None, **kw):
    window, syms = window or MAIN, syms or SYMS
    data = {s: D[s] for s in syms}
    out = book_for(sysname, **kw)({s: d["kl"] for s, d in data.items()})
    return ev.run_book(out, data, spec, *utc(window)), out


def primary(a):
    sysname, var, out_dir, dh = a
    e, x, nd = SYSTEMS[sysname]
    data = {s: D[s] for s in SYMS}
    sp = fs.spec()
    if var == "scaled":  # K4: planlanan boyut (deftersiz kontrol)
        (res, win, _), _ = run(sysname, sp, risk=RISK[sysname])
        pnl = report.book_pnl(win, res, sp)
        return f"{sysname}_scaled", dict(summary=fs.keep(res), daily=fs.daily(pnl))
    if var != "full":  # K8 ablasyonu (deftersiz kontrol)
        (res, win, _), _ = run(sysname, sp, var=var)
        return f"{sysname}_{var}", dict(summary=fs.keep(res), daily=fs.daily(report.book_pnl(win, res, sp)))
    book, invalid = book_for(sysname), False
    try:
        r = ev.evaluate_book(book, data, [sp], Path(out_dir) / "ledger_a.jsonl", f"pre2022 Blok A {sysname}: tam Turtle (reports/pre2022_protocol.md)", dh, sysname, dict(sys=sysname, entry=e, exit=x, nd=nd), MAIN)[0]
    except ValueError as err:  # hesap sıfırlanıp marj reddi: hakem kuralı deftere yazmaz (full_systems_protocol.md koşu notundaki aynı davranış); geçersiz işaretlenir
        if "reddedilen" not in str(err):
            raise
        res, win, _ = ev.run_book(book({s: d["kl"] for s, d in data.items()}), data, sp, *utc(MAIN))
        r, invalid = dict(res=res, win=win, row=dict(trial=None)), True
    pnl = report.book_pnl(r["win"], r["res"], sp)
    dirs = {s: sg.turtle(e, x) for s in SYMS}
    outb, info = turtle.turtle_book({s: D[s]["kl"] for s in SYMS}, dirs, CAP, fs.GROUPS, marks={s: D[s]["mark"] for s in SYMS}, ticks={s: float(D[s]["tick"]) for s in SYMS}, nd=nd)
    close = {s: D[s]["kl"].close for s in SYMS}
    st = {}
    for k, w in STRESS.items():
        lo = pd.Timestamp(w[0], tz="UTC")
        st[k] = dict(stress.window_stats(pnl, r["res"]["fills"], *w, CAP, close, {s: outb[s].stop for s in SYMS}, {s: D[s]["kl"] for s in SYMS}),
                     basket=stress.basket_return({s: c for s, c in close.items() if (c.index < lo).any()}, *w))
    sym_net = {s: float(report.hourly_pnl(r["win"][s]["kl"], r["win"][s].get("mark"), r["win"][s].get("funding"), r["res"]["fills"][r["res"]["fills"].sym == s], sp).sum()) for s in r["win"]}
    return f"{sysname}_full", dict(summary=fs.keep(r["res"]), daily=fs.daily(pnl), manager=info, sym_net=sym_net, stress=st, recon=float(pnl.sum() - r["res"]["summary"]["net_pnl"]), row_trial=r["row"]["trial"], invalid=invalid)


def robust_task(a):
    kind, sysname, p = a
    if kind == "bh":
        res, pnl = robust.buy_hold({s: D[s] for s in SYMS}, fs.spec(cap=None), CAP / len(SYMS), MAIN)
        return "bh", dict(summary=fs.keep(res), daily=fs.daily(pnl))
    if kind == "cost":
        fee, slip, delay = p
        sp = fs.spec(fee, slip, delay)
        (res, win, _), _ = run(sysname, sp)
        return f"cost_{sysname}_{fee}_{slip}_{delay}", dict(summary=fs.keep(res), daily=fs.daily(report.book_pnl(win, res, sp)))
    if kind == "nb":
        sp = fs.spec()
        (res, win, _), _ = run(sysname, sp, entry=p[0], exit_=p[1])
        return f"nb_{sysname}_{p[0]}_{p[1]}", dict(summary=fs.keep(res), daily=fs.daily(report.book_pnl(win, res, sp)))
    if kind == "win":
        (res, win, _), _ = run(sysname, fs.spec(), window=p)
        return f"win_{sysname}_{p[0]}_{p[1]}", dict(summary=fs.keep(res))
    if kind == "k7":
        syms, sp = p, fs.spec(16, 2)
        (res, win, _), _ = run(sysname, sp, syms=syms, groups={s: s for s in syms})  # korele grup bilgisi önceden yok: her sembol kendi grubu
        return f"k7_{sysname}", dict(summary=fs.keep(res), syms=syms, sym_net={s: float(report.hourly_pnl(win[s]["kl"], win[s].get("mark"), win[s].get("funding"), res["fills"][res["fills"].sym == s], sp).sum()) for s in win})


def null_draw(a):
    sysname, i = a
    u = float(np.random.default_rng([0, i]).uniform(0.05, 0.95))  # ortak ofset: tüm semboller aynı oranda kayar
    (res, _, _), _ = run(sysname, fs.spec(), u=u)
    return sysname, i, dict(fs.keep(res), u=u)


def k7_universe(root, exclude):
    m = tape.membership(root).groupby("sym").month.nunique()  # sinyalden bağımsız kural (protokol, K7)
    cut, cand, dropped = tape._usable(root), [s for s, n in m.items() if n >= 8 and s not in exclude], []
    syms = []
    for s in sorted(cand):
        if s in cut:
            continue
        if not all((Path(root) / "tape" / k / f"{s}.parquet").exists() for k in tape.KINDS.values()):
            dropped.append(s)  # arşivde bir tür eksik: düşer ve sayılır
        elif tape.load(root, s, end=END)["klines"].index[0] <= pd.Timestamp("2020-07-01", tz="UTC"):
            syms.append(s)
    return syms, dropped


TAG = "pre2022r2"  # ilk Blok B koşusu defter reddinde çöktü (ledger_pre2022_*.jsonl = o koşunun kısmi satırları, kümülatif sayıma girer); yeniden koşu bu etiketle yazar


def one_safe(a):
    """search.one, spec başına: defter bir koşuyu n_rejected/funding_missed > 0 diye reddederse (veri boşluğunda funding olayı: ham veri gerçeği, kod hatası değil) aynı nedensellik denetimi + hakemle
    deftersiz koşulur ve satır ledger=False işaretlenir (full_systems_protocol.md koşu notundaki 'defter dışı, N'ye sayılır' davranışı); hakem/defter koduna dokunulmaz."""
    family, name, p, sym, window, specs, out, dh, tag = a
    rows = []
    for sp in specs:
        try:
            rows.append(search.one((family, name, p, sym, window, [sp], out, dh, tag))[2][0])
            continue
        except ValueError as err:
            if "reddedilen" not in str(err):
                raise
        kl, mark, funding = g2.D[sym]
        sig = search.make(family, p, sym)
        audit.assert_causal(sig, kl)
        unit = tape.check_target(kl, sig(kl).astype(float)).ffill()
        keep = (kl.index >= window[0]) & (kl.index < window[1])
        k = kl[keep]
        res = referee.run(k, (unit * g2.NOTIONAL)[keep], sp, funding, mark.loc[(mark.index >= pd.Timestamp(window[0], tz="UTC")) & (mark.index < pd.Timestamp(window[1], tz="UTC"))])
        s = dict(res["summary"], fee_bps=sp.fee_rt_bps, slip_bps=sp.slip_rt_bps, traded=float((res["fills"].qty * res["fills"].px).sum()), ledger=False)
        base = (sp.fee_rt_bps, sp.slip_rt_bps) == (10, g2.SLIP)
        s["daily"] = {str(i.date()): float(v) for i, v in report.hourly_pnl(k, mark.loc[k.index.intersection(mark.index)], funding, res["fills"], sp).resample("1D").sum().items()} if base else None
        rows.append(s)
    return name, sym, rows


def blockb(ex, out, dh, universe, lo, hi):
    """Gerçek koşu (6 yapılandırma x semboller x 6 maliyet, deftere) yalnızca lo == 0 parçasında; null çekilişleri [lo, hi) aralığında."""
    best = {fam: next((n, p) for n, p in search.configs(fam) if n == nm) for fam, nm in dict(donchian="don_80_20", ema="ema_10_100", tsmom="tsmom_14_1", xs_carry="xscarry_7", xs_mom="xsmom_7", xs_rev="xsrev_3").items()}
    specs = lambda kl: [g2.spec_for(kl, f, g2.SLIP) for f in g2.FEES] + [g2.spec_for(kl, 10, 6.0)]  # noqa: E731
    if lo == 0:
        real = {}
        for name, sym, rows in ex.map(one_safe, [(fam, nm, p, s, MAIN, specs(g2.D[s][0]), out, dh, TAG) for fam, (nm, p) in best.items() for s in universe], chunksize=1):
            real.setdefault(name, {})[sym] = rows
        Path(out, "blockb_real.json").write_text(json.dumps(dict(best={f: b[0] for f, b in best.items()}, universe=universe, real=real)))
    null = {nm: {s: {} for s in universe} for nm, _ in best.values()}
    for fam, (nm, p) in best.items():
        for sym, i, r in ex.map(search.null_one, [(fam, nm, p, s, MAIN, i) for i in range(lo, hi) for s in universe], chunksize=4):
            null[nm][sym][i] = r
    Path(out, f"blockb_null_{lo}_{hi}.json").write_text(json.dumps(null))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["primary", "robust", "null", "blockb"])
    ap.add_argument("--root", default="/data/pre2022")
    ap.add_argument("--out", default="/data/pre2022_out")
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--b", type=int, default=500)
    ap.add_argument("--null-from", type=int, default=0)
    ap.add_argument("--null-to", type=int, default=None)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--smoke", action="store_true", help="boru hattı denemesi: kısa pencere, 2 komşu, B=3; --out ayrı olmalı; sonuçlar karar için kullanılmaz")
    a = ap.parse_args()
    nb_limit = None
    if a.smoke:
        MAIN, HALVES, STRESS, nb_limit = ("2020-04-01", "2020-05-01"), [("2020-04-01", "2020-04-15"), ("2020-04-15", "2020-05-01")], {"covid": ("2020-04-10", "2020-04-12")}, 2
    Path(a.out).mkdir(parents=True, exist_ok=True)
    dh, t0 = ledger.sha(Path("/repo/data_manifest/manifest_pre2022.json").read_text()), time.time()
    ext = list(g2.EXT)
    if a.stage == "blockb":
        g2.load(a.root, ext, END)
        SYMS[:] = [s for s in ext if g2.D[s][0].index[0] < pd.Timestamp(MAIN[1], tz="UTC") and g2.D[s][0].index[-1] >= pd.Timestamp(MAIN[0], tz="UTC")]  # pencerede verisi olanlar
        print("Blok B evreni:", SYMS, "düşen:", sorted(set(ext) - set(SYMS)), flush=True)
        search.P["close"] = pd.DataFrame({s: sg._daily(g2.D[s][0]).close for s in SYMS})
        search.P["fund"] = pd.DataFrame({s: g2.D[s][0].fund_hr.resample("1D").mean() for s in SYMS})
        with ProcessPoolExecutor(a.procs) as ex:
            blockb(ex, a.out, dh, list(SYMS), a.null_from, (3 if a.smoke else 300) if a.null_to is None else a.null_to)
        print(f"blockb bitti {time.time() - t0:.0f}s", flush=True)
        raise SystemExit(0)
    syms7, dropped7 = k7_universe(a.root, ext) if a.stage == "robust" else ([], [])
    fs.load(a.root, ext + syms7, END)
    SYMS[:] = [s for s in ext if D[s]["kl"].index[0] < pd.Timestamp(MAIN[1], tz="UTC") and D[s]["kl"].index[-1] >= pd.Timestamp(MAIN[0], tz="UTC")]
    print("Blok A evreni:", SYMS, "düşen:", sorted(set(ext) - set(SYMS)), flush=True)
    with ProcessPoolExecutor(a.procs) as ex:
        if a.stage == "primary":
            btc = D["BTCUSDT"]["kl"].close.resample("1D").last()
            Path(a.out, "btc_close.json").write_text(json.dumps({str(k.date()): float(v) for k, v in btc.items()}))
            Path(a.out, "universe.json").write_text(json.dumps(dict(syms=SYMS, dropped=sorted(set(ext) - set(SYMS)))))
            res = dict(ex.map(primary, [(s, v, a.out, dh) for s in SYSTEMS for v in ("full", *ABL, "scaled")]))
            Path(a.out, "primary.json").write_text(json.dumps(res, indent=0))
        elif a.stage == "robust":
            print("K7 evreni:", syms7, "arşivde türü eksik düşen:", dropped7, flush=True)
            tasks = [("bh", "S1", None)] + [("cost", s, c) for s in SYSTEMS for c in COSTS] + [("win", s, w) for s in SYSTEMS for w in HALVES + robust.shift_windows(*MAIN)]
            tasks += [("nb", s, (nb["entry"], nb["exit"])) for s, (e, x, _) in SYSTEMS.items() for nb in robust.neighbors(dict(entry=e, exit=x))[:nb_limit]]
            tasks += [("k7", s, syms7) for s in SYSTEMS]
            i, n = map(int, a.shard.split("/"))
            res = dict(ex.map(robust_task, tasks[i::n], chunksize=1))
            Path(a.out, f"robust_{i}_of_{n}.json").write_text(json.dumps(dict(res, _k7_dropped=dropped7), indent=0))
        else:
            hi = (3 if a.smoke else a.b) if a.null_to is None else a.null_to
            res = {s: {} for s in SYSTEMS}
            for s, i, r in ex.map(null_draw, [(s, i) for i in range(a.null_from, hi) for s in SYSTEMS], chunksize=2):
                res[s][i] = r
            Path(a.out, f"null_{a.null_from}_{hi}.json").write_text(json.dumps(res))
    print(f"{a.stage} bitti {time.time() - t0:.0f}s", flush=True)
