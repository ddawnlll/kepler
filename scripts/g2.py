"""G2 işçisi (Modal'de koşar): bir sinyal için tüm semboller x maliyet ızgarası + yarıyıl pencereleri + rotasyon null'ı. Doğrudan hakem (eleme yok).

  python scripts/g2.py --job turtle_s1 --b 200 --out /data/g2
Her sonuç yalnızca `evaluate` üzerinden deftere girer (nedensellik denetimi dahil); null çekilişleri kontrol sayılır (deftere değil `<job>.json`a)."""
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

from kepler import evaluate as ev
from kepler import ledger, referee, tape
from kepler import signals as sg

CORE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]
EXT = CORE + ["DOGEUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT"]
FEES, SLIP, SLIP_HI, NOTIONAL, CAP = (4, 9, 10, 11, 16), 2.0, 6.0, 1000.0, 2000.0  # sermaye = 2x notional: 0.5x kaldıraç, likidasyon yalnız uç olayda
WINDOWS = [("2023-01-01", "2023-07-01"), ("2023-07-01", "2024-01-01"), ("2024-01-01", "2024-07-01"), ("2024-07-01", "2025-01-01"),
           ("2025-01-01", "2025-07-01"), ("2025-07-01", "2026-01-01"), ("2026-01-01", "2026-04-01")]
JOBS = {"turtle_s1": 9, "turtle_s2": 9, "donchian_trend": 9, "tsmom": 9, "carry_funding": 9, "dual_mom_5": 5, "dual_mom_9": 9}
D: dict = {}  # sembol -> (kl, mark, funding); fork ile işçilere paylaşılır


def spec_for(kl, fee, slip) -> referee.Spec:
    """Sembol kuralları UNKNOWN: fiyat/miktar çözünürlüğü sinyal-bağımsız (5 anlamlı basamak fiyat, ~1e-3 lot), min notional 5; kısıt değil fikir ölçülür."""
    q = Decimal(10) ** (math.floor(math.log10(kl.close.min())) - 5)
    s = Decimal(10) ** (math.floor(math.log10(NOTIONAL / kl.close.max())) - 3)
    return referee.Spec(tick=format(q, "f"), step=format(s, "f"), min_notional=5.0, fee_rt_bps=fee, slip_rt_bps=slip, capital=CAP, leverage=10, liq=True)


def load(root, syms):
    for s in syms:
        d = tape.load(root, s)
        D[s] = (sg.with_funding(d["klines"][["open", "high", "low", "close", "volume"]], d["funding"]), d["mark"], d["funding"])


def make_signal(job, sym):
    if job.startswith("dual_mom"):
        uni = CORE if job.endswith("_5") else EXT
        return sg.dual_mom(pd.DataFrame({s: sg._daily(D[s][0]).close for s in uni}), sym)
    return {"turtle_s1": lambda: sg.turtle(20, 10), "turtle_s2": lambda: sg.turtle(55, 20), "donchian_trend": lambda: sg.turtle(20, 10, trend=True),
            "tsmom": sg.tsmom, "carry_funding": sg.carry_funding}[job]()


def daily_pnl(kl, mark, funding, fills, spec) -> pd.Series:
    """Günlük net PnL'yi hakem dolumlarından yeniden kurar (Sharpe/DSR için); toplamı hakem net'ine eşit olmalı (çapraz kontrol: run_symbol)."""
    t = pd.to_datetime(fills.ts, unit="ns", utc=True)
    pos = pd.Series(np.where(fills.side == "BUY", fills.qty, -fills.qty), index=t).groupby(level=0).sum().reindex(kl.index, fill_value=0.0).cumsum()
    nxt = kl.open.shift(-1).fillna(kl.close.iloc[-1])
    pnl = pos * (nxt - kl.open) - pd.Series(fills.commission.to_numpy(), index=t).groupby(level=0).sum().reindex(kl.index, fill_value=0.0)
    rate = funding.last_funding_rate.copy()
    rate.index = rate.index.round("1min")
    for T, r in rate.items():
        b = T - pd.Timedelta("1h")
        if b in pos.index:
            pnl[b] += -pos[b] * (mark.close.get(b, kl.close[b])) * r  # T öncesi tutulan pozisyon x mark kapanışı (hakemle aynı kural)
    pnl.iloc[-1] -= abs(pos.iloc[-1]) * kl.close.iloc[-1] * (spec.fee_rt_bps + spec.slip_rt_bps) / 2 / 1e4  # çıkış maliyeti
    return pnl.resample("1D").sum()


def run_symbol(a):
    job, sym, out, data_hash = a
    kl, mark, funding = D[sym]
    sig, led = make_signal(job, sym), Path(out) / f"ledger_{job}.jsonl"
    specs = [spec_for(kl, f, SLIP) for f in FEES] + [spec_for(kl, 10, SLIP_HI)]
    hyp = f"G2 {job}: kitap sinyali, sabit parametre (reports/book_signals.md)"
    res = ev.evaluate(sig, kl, specs, led, hyp, data_hash, funding, mark, NOTIONAL, job, dict(job=job), None)
    full = []
    for sp, r in zip(specs, res):
        s = dict(r["res"]["summary"], fee_bps=sp.fee_rt_bps, slip_bps=sp.slip_rt_bps, traded=float((r["res"]["fills"].qty * r["res"]["fills"].px).sum()))
        d = daily_pnl(kl, mark, funding, r["res"]["fills"], sp)
        s["recon_diff"] = float(d.sum() - r["res"]["summary"]["net_pnl"])
        s["daily"] = {str(k.date()): float(v) for k, v in d.items()} if (sp.fee_rt_bps, sp.slip_rt_bps) == (10, SLIP) else None  # günlük seri yalnız temel senaryoda (Sharpe/DSR)
        full.append(s)
    wins = []
    base = spec_for(kl, 10, SLIP)
    for w in WINDOWS:
        r = ev.evaluate(sig, kl, [base], led, hyp, data_hash, funding, mark, NOTIONAL, job, dict(job=job, window=w), w)[0]["res"]
        wins.append(dict(r["summary"], window=w[0], traded=float((r["fills"].qty * r["fills"].px).sum())))
    return sym, dict(full=full, windows=wins)


def null_draw(a):
    job, sym, i, seed, common = a
    kl, mark, funding = D[sym]
    unit = make_signal(job, sym)(kl).ffill().fillna(0.0).to_numpy()
    u = np.random.default_rng([seed, i] + ([] if common else [sum(map(ord, sym))])).uniform(0.05, 0.95)  # common: tüm semboller aynı oranda kayar (sembol-arası korelasyon korunur)
    off = int(u * len(unit))
    s = referee.run(kl, pd.Series(np.roll(unit, off) * NOTIONAL, index=kl.index), spec_for(kl, 10, SLIP), funding, mark)["summary"]
    return sym, i, {k: s[k] for k in ("gross_pnl", "net_pnl", "fee", "slippage", "funding", "exit_cost", "n_fills", "n_rejected")}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True, choices=list(JOBS))
    ap.add_argument("--b", type=int, default=200)
    ap.add_argument("--root", default="/data")
    ap.add_argument("--out", default="/data/g2")
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--syms", default="")
    ap.add_argument("--common", action="store_true", help="null: ortak ofset; yalnız null koşar, mevcut gerçek sonuçları kullanır, deftere yazmaz")
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    syms = a.syms.split(",") if a.syms else (CORE if a.job.endswith("_5") else EXT)
    load(a.root, EXT)  # dual_mom paneli için tüm evren; yalnız tape.load (mühür sınırı kodda)
    dh = ledger.sha(Path("/repo/data_manifest/manifest.json").read_text())
    t0 = time.time()
    with ProcessPoolExecutor(a.procs) as ex:
        real = json.loads(Path(a.out, f"{a.job}.json").read_text())["real"] if a.common else dict(ex.map(run_symbol, [(a.job, s, a.out, dh) for s in syms]))
        print(f"gerçek koşu {time.time() - t0:.0f}s", flush=True)
        null = {s: {} for s in syms}
        for s, i, r in ex.map(null_draw, [(a.job, s, i, 0, a.common) for i in range(a.b) for s in syms], chunksize=4):
            null[s][i] = r
    if a.common:
        Path(a.out, f"{a.job}_common.json").write_text(json.dumps(dict(job=a.job, syms=syms, null=null, b=a.b)))
        sys.exit(0)
    Path(a.out, f"{a.job}.json").write_text(json.dumps(dict(job=a.job, syms=syms, real=real, null=null, b=a.b, secs=time.time() - t0)))
    print(f"bitti {time.time() - t0:.0f}s", flush=True)
