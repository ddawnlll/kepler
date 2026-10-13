"""Ensemble v1 işçisi (Modal'de koşar): reports/ensemble_protocol.md. Parametreler protokolde sabit; burada ayarlanmaz.

  --stage primary  birincil EV1 (evaluate_book: denetim + defter) + kontroller: 5 ablasyon (K8), 6 komşu (K5), maliyet/gecikme (K3), pencere/kaydırma (K6), al-tut (K2), 500 USD (bilgi)
  --stage k7       çapraz varlık (dev K7 kuralı, 2023-07 -> 2026-04, fee 16 + slip 2)
  --stage null     K1 rotasyon null'u (--null-from/--null-to ile bölünür)
  --stage decay_real | decay_null [--rot window|full]   EV1 sönme testi, W2 = 2022-01 -> 2026-04 (reports/ensemble_decay_protocol.md)
  --stage daily    ledger'sız tek koşu (fee 10 + slip 2): günlük PnL (EV1 regresyon karşılaştırması)
  --expert AD   (primary/k7/null/daily) tek uzman kipi: reports/edge_experts_protocol.md (EV1 zinciri, ağırlık 1; indirgenmiş kontrol listesi). Boş = EV1.
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
from kepler.experts._interface import scale

EXT = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT"]
CAP, SPLIT = 10_000.0, "2022-01-01"
MAIN, K7_WINDOW = ("2020-04-01", "2026-04-01"), ("2023-07-01", "2026-04-01")
W2 = ("2022-01-01", "2026-04-01")  # sönme testi alt dönemi (reports/ensemble_decay_protocol.md)
HALVES = [(f"{y}-{m}-01", f"{y + (m == '07')}-{'01' if m == '07' else '07'}-01") for y in range(2020, 2026) for m in ("01", "07")][1:] + [("2026-01-01", "2026-04-01")]
SHIFTS = [(f"2020-{m:02d}-01", MAIN[1]) for m in (4, 5, 6, 7)]
STRESS = {"2021-05": ("2021-05-17", "2021-05-24"), "LUNA": ("2022-05-05", "2022-05-16"), "FTX": ("2022-11-06", "2022-11-15")}
ABL = {"trend_only": dict(weights=(1.0, 0.0, 0.0)), "no_xs": dict(weights=(0.75, 0.0, 0.25)), "no_carry": dict(weights=(0.75, 0.25, 0.0)), "no_risk": dict(risk=False), "no_buffer": dict(buffer=0.0)}
NB = {**{f"scale_{s}": s for s in (0.8, 0.9, 1.1, 1.2)}, "w_50_25_25": (0.5, 0.25, 0.25), "w_70_15_15": (0.7, 0.15, 0.15)}
COSTS = [(4, 2, 0), (16, 2, 0), (10, 6, 0), (16, 6, 0), (10, 2, 1)]
XABL = ("no_risk", "no_buffer")  # tek uzman kipi ablasyonları (K8); K5 komşuları: tüm parametreler x s
XSCALES = (0.8, 0.9, 1.1, 1.2)
P0 = en.Params()  # __main__'de --expert ile değişir (fork ile işçilere geçer)
D: dict = {}  # sembol -> dict(kl [OHLCV + fund_hr], funding, mark, tick, step); fork ile paylaşılır


def load(syms, roots, cap=CAP):
    for s in syms:
        parts = [tape.load(r, s, start=lo, end=hi) for r, lo, hi in roots]
        parts = [p for p in parts if len(p["klines"])]
        d = {k: pd.concat([p[k] for p in parts]).sort_index() for k in ("klines", "mark", "funding")}
        for k in d:
            d[k] = d[k][~d[k].index.duplicated()]
        kl = sg.with_funding(d["klines"][["open", "high", "low", "close", "volume", "quote_volume", "taker_buy_quote_volume"]], d["funding"])  # son ikisi yalnızca tek uzman girdisi (dvol/tbr)
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


def neighbor(p, s):
    """K5 komşusu: EV1 uzmanları için Params.scaled; yeni uzmanlar için yalnızca uzman parametreleri x s (σ, ρ, τ sabit)."""
    m = en.REG.get(p.expert)
    return replace(p, xp=scale(m.DEFAULT, s)) if hasattr(m, "DEFAULT") else p.scaled(s)


def data_of(syms, d=None):
    d = d or D
    return {s: d[s] for s in syms}


def run(p, sp, window=None, syms=EXT, u=None, out=None, rot_from=None):
    window, data = window or MAIN, data_of(syms)  # varsayılan çağrı anında (--smoke MAIN'i değiştirir)
    out = out or en.make_book(sp.capital, p, u, rot_from)({s: x["kl"] for s, x in data.items()})
    res, win, _ = ev.run_book(out, data, sp, *utc(window))
    return res, win, out


def task(a):
    kind, name, out_dir, dh = a
    p = P0
    if kind == "main":
        data, sp = data_of(EXT), spec()
        ex, invalid = p.expert, None
        try:  # hesap batarsa (likidasyon + reddedilen emir) defter yazmaz (ledger kuralı); sonuç yine hakemden, "geçersiz" bayrağıyla raporlanır (full_systems emsali)
            r = ev.evaluate_book(en.make_book(CAP, p), data, [sp], Path(out_dir) / f"ledger_{ex or 'ev1'}.jsonl", f"Edge uzmanı {ex} tek başına (reports/edge_experts_protocol.md)" if ex else
                                 "Ensemble v1: piyasa durumu -> uzmanlar -> aday -> risk motoru (reports/ensemble_protocol.md)", dh, ex or "EV1", asdict(p), MAIN)[0]
        except ValueError as e:
            if "reddedilen" not in str(e):
                raise
            res_, win_, _ = run(p, sp)
            r, invalid = dict(res=res_, win=win_, row=dict(trial=None)), str(e)
        pnl = report.book_pnl(r["win"], r["res"], sp)
        out = en.make_book(CAP, p)({s: x["kl"] for s, x in data.items()})
        fills = r["res"]["fills"]
        close = {s: D[s]["kl"].close for s in EXT}
        st = {k: stress.window_stats(pnl, fills, *w, CAP, close, {s: out[s].stop for s in EXT}, {s: D[s]["kl"] for s in EXT}) for k, w in STRESS.items()}
        sym_net = {s: float(report.hourly_pnl(r["win"][s]["kl"], r["win"][s].get("mark"), r["win"][s].get("funding"), fills[fills.sym == s], sp).sum()) for s in r["win"]}
        gross_notional = pd.DataFrame({s: out[s].target.ffill().fillna(0.0).abs().resample("1D").last() for s in EXT}).fillna(0.0).sum(axis=1)
        f, _ = en.forecasts({s: x["kl"] for s, x in data.items()}, p)
        return "main", dict(summary=keep(r["res"]), daily=daily(pnl), sym_net=sym_net, stress=st, recon=float(pnl.sum() - r["res"]["summary"]["net_pnl"]), row_trial=r["row"]["trial"], invalid=invalid,
                            traded=float((fills.qty * fills.px).sum()), gross_notional_mean=float(gross_notional[gross_notional.index >= MAIN[0]].mean()),
                            forecast_abs_mean=float(f.abs().stack().mean()), forecast_long_share=float((f.stack() > 0).mean()))
    if kind == "abl":
        res, win, _ = run(replace(p, **ABL[name]), spec())
        return f"abl_{name}", dict(summary=keep(res), daily=daily(report.book_pnl(win, res, spec())))
    if kind == "flip":
        res, win, _ = run(replace(p, flip=True), spec())
        return "flip", dict(summary=keep(res), daily=daily(report.book_pnl(win, res, spec())))
    if kind == "nb":
        q = neighbor(p, NB[name]) if name.startswith("scale") else replace(p, weights=NB[name])
        res, win, _ = run(q, spec())
        return f"nb_{name}", dict(summary=keep(res), daily=daily(report.book_pnl(win, res, spec())), params=asdict(q))
    if kind == "cost":
        fee, slip, delay = name
        res, win, _ = run(p, spec(fee, slip, delay))
        return f"cost_{fee}_{slip}_{delay}", dict(summary=keep(res), daily=daily(report.book_pnl(win, res, spec(fee, slip, delay))))
    if kind == "win":
        res, win, _ = run(p, spec(), window=name)
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
    res, _, _ = run(P0, spec(), u=u)
    return i, dict(keep(res), u=u)


def decay_real(out_dir, dh):
    """Gerçek EV1, yalnızca W2'de (evaluate_book: denetim + defter; N + 1)."""
    p, data, sp = en.Params(), data_of(EXT), spec()
    r = ev.evaluate_book(en.make_book(CAP, p), data, [sp], Path(out_dir) / "ledger_ev1_w2.jsonl", "EV1 sönme testi: W2 = 2022-01 -> 2026-04 (reports/ensemble_decay_protocol.md)", dh, "EV1_W2", asdict(p), W2)[0]
    return dict(summary=keep(r["res"]), daily=daily(report.book_pnl(r["win"], r["res"], sp)), row_trial=r["row"]["trial"])


def decay_null(a):
    """W2 null'u: rot = "window" (birincil: yalnızca W2 satırları kaydırılır) ya da "full" (bilgi: tüm seri kaydırılır, W2'de hakem). u tohumları K1 ile aynı."""
    i, rot = a
    u = float(np.random.default_rng([0, i]).uniform(0.05, 0.95))
    res, _, _ = run(en.Params(), spec(), window=W2, u=u, rot_from=utc(W2)[0] if rot == "window" else None)
    return i, dict(keep(res), u=u)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["primary", "k7", "null", "decay_real", "decay_null", "daily"])
    ap.add_argument("--preset", default="", choices=[""] + list(en.PRESETS), help="adlandırılmış bileşim (ensemble.PRESETS); --expert ile birlikte kullanılmaz")
    ap.add_argument("--expert", default="", choices=[""] + list(en.REG), help="tek uzman kipi (reports/edge_experts_protocol.md); boş = EV1")
    ap.add_argument("--rot", default="window", choices=["window", "full"], help="decay_null: W2 içinde mi (birincil) tüm seride mi (bilgi) kaydırılır")
    ap.add_argument("--out", default="/data/ensemble")
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--drop", default="", help="keşif: bileşimden bu üyeyi çıkar (leave-one-out marjinal katkı; --preset ile)")
    ap.add_argument("--cap", type=float, default=None, help="keşif: başlangıç sermayesi (varsayılan 10 000); daily aşaması + veri yüklemesi (lot çözünürlüğü sermayeye bağlı); pozisyon notional dağılımı da yazılır")
    ap.add_argument("--tau", type=float, default=None, help="keşif: yıllık hedef portföy oynaklığı (varsayılan 0,20); kaldıraç taraması için (yalnızca daily aşaması için gözden geçirilmiş)")
    ap.add_argument("--b", type=int, default=300)
    ap.add_argument("--null-from", type=int, default=0)
    ap.add_argument("--null-to", type=int, default=None)
    ap.add_argument("--only", default=None, help="primary: yalnızca bu tür görevler (virgüllü; main,abl,nb,cost,win,bh,cap500)")
    ap.add_argument("--smoke", action="store_true", help="boru hattı denemesi: kısa pencere; --out ayrı olmalı; sonuçlar karar için kullanılmaz")
    a = ap.parse_args()
    if a.smoke:
        MAIN, K7_WINDOW, HALVES, SHIFTS = ("2021-11-01", "2022-02-01"), ("2025-01-01", "2025-02-01"), [("2021-11-01", "2021-12-15")], [("2021-12-01", "2022-02-01")]
        W2 = ("2021-12-01", "2022-02-01")
    P0 = en.Params(**(en.PRESETS[a.preset] if a.preset else {}), expert=a.expert, **({"tau": a.tau} if a.tau else {}))
    if a.drop:
        keep_ = [i for i, n in enumerate(P0.names) if n != a.drop]
        P0 = replace(P0, names=tuple(P0.names[i] for i in keep_), weights=tuple(P0.weights[i] for i in keep_))
    Path(a.out).mkdir(parents=True, exist_ok=True)
    dh, t0 = ledger.sha(Path("/repo/data_manifest/manifest.json").read_text() + Path("/repo/data_manifest/manifest_pre2022.json").read_text()), time.time()
    roots = [("/data/pre2022", None, SPLIT), ("/data", SPLIT, None)]
    if a.stage == "k7":
        m = tape.membership("/data").groupby("sym").month.nunique()  # sinyalden bağımsız kural (full_systems / search replikasyon K7)
        syms = sorted(s for s, n in m.items() if n >= 8 and s not in EXT and s not in tape._usable("/data") and tape.load("/data", s)["klines"].index[0] <= pd.Timestamp("2023-07-01", tz="UTC"))
        print("K7 evreni:", syms, flush=True)
        load(syms, [("/data", None, None)])
        sp = spec(16, 2)
        res, win, _ = run(P0, sp, window=K7_WINDOW, syms=syms)
        sym_net = {s: float(report.hourly_pnl(win[s]["kl"], win[s].get("mark"), win[s].get("funding"), res["fills"][res["fills"].sym == s], sp).sum()) for s in win}
        Path(a.out, "k7.json").write_text(json.dumps(dict(summary=keep(res), daily=daily(report.book_pnl(win, res, sp)), syms=syms, sym_net=sym_net)))
        print(f"k7 bitti {time.time() - t0:.0f}s", keep(res), flush=True)
        raise SystemExit(0)
    load(EXT, roots, cap=a.cap or CAP)
    print("veri:", {s: (str(D[s]["kl"].index[0]), str(D[s]["kl"].index[-1]), len(D[s]["kl"])) for s in EXT}, flush=True)
    with ProcessPoolExecutor(a.procs) as ex:
        if a.stage == "primary":
            btc = D["BTCUSDT"]["kl"].close.resample("1D").last()
            Path(a.out, "btc_close.json").write_text(json.dumps({str(k.date()): float(v) for k, v in btc.items()}))
            tasks = [("abl", "no_buffer"), ("main", None), ("bh", None), ("cap500", None)] + [("abl", k) for k in ABL if k != "no_buffer"] + [("nb", k) for k in NB] + [("cost", c) for c in COSTS] + [("win", w) for w in HALVES + SHIFTS]  # en uzun iş (≈200–280 sn, dolum başına bakiye sorgusu) ilk başlar: duvar süresi onunla belirlenir (issue #28/#34)
            if a.expert:  # indirgenmiş liste: bh/cap500 EV1 çıktısından, ablasyonlar yalnızca no_risk/no_buffer, 4 komşu (protokol "Denetimler"), yalnızca K3 maliyetleri, + yön testi
                NB.clear()
                NB.update({f"scale_{x}": x for x in XSCALES})
                tasks = [("main", None)] + [("abl", k) for k in XABL] + [("nb", k) for k in NB] + [("cost", c) for c in COSTS if c in ((16, 6, 0), (10, 2, 1))] + [("win", w) for w in HALVES + SHIFTS] + [("flip", None)]
            if a.only:
                tasks = [t for t in tasks if t[0] in a.only.split(",")]
            res = {}
            for k, v in ex.map(task, [(kind, name, a.out, dh) for kind, name in tasks], chunksize=1):
                res[k] = v
                print(f"{k} {time.time() - t0:.0f}s net={v['summary']['net_pnl']:.0f}", flush=True)
            tag = "" if not a.only else "_" + a.only.replace(",", "_")
            Path(a.out, f"primary{tag}.json").write_text(json.dumps(res))
        elif a.stage == "daily":
            cap = a.cap or CAP
            sp = spec(cap=cap)
            out = en.make_book(cap, P0)({s: D[s]["kl"] for s in EXT})
            res, win, _ = run(P0, sp, out=out)
            nz = {s: out[s].target.dropna().abs()[lambda t: t > 0] for s in EXT}  # tutulan/açılan hedef notional dağılımı (USDT)
            size = {s: dict(n=int(len(t)), median=float(t.median()), p10=float(t.quantile(0.1)), below5=float((t < 5).mean()), below20=float((t < 20).mean()), below100=float((t < 100).mean())) for s, t in nz.items()}
            Path(a.out, "daily.json").write_text(json.dumps(dict(summary=keep(res), daily=daily(report.book_pnl(win, res, sp)), cap=cap, target_size=size)))
        elif a.stage == "decay_real":
            Path(a.out, "decay_real.json").write_text(json.dumps(decay_real(a.out, dh)))
        elif a.stage == "decay_null":
            hi = a.b if a.null_to is None else a.null_to
            res = dict(ex.map(decay_null, [(i, a.rot) for i in range(a.null_from, hi)], chunksize=1))
            Path(a.out, f"decay_null_{a.rot}_{a.null_from}_{hi}.json").write_text(json.dumps(res))
        else:
            hi = a.b if a.null_to is None else a.null_to
            res = dict(ex.map(null_draw, range(a.null_from, hi), chunksize=1))
            Path(a.out, f"null_{a.null_from}_{hi}.json").write_text(json.dumps(res))
    print(f"{a.stage} bitti {time.time() - t0:.0f}s", flush=True)
