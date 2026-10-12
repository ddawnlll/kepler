"""KEŞİF (ön kayıtsız; kullanıcı kararı 2026-10-05): stoplu, rejim filtreli saatlik mean reversion. Karar kanıtı DEĞİL: görülmüş veride, birkaç varyant yan yana (reports/edge_experts.md "Keşif eki").

Durum makinesi saatlik (stop bar içinde vurulursa hedef ffill edilip yeniden girişe yol açmasın diye hakemle aynı çözünürlük). Sözleşme: BACKTEST §4/§6.4 (`stop[t]` t kapanışında bilinir, t+1 açılışından geçerli).
  giriş   : z = (C - SMA_n) / std_n; z <= -k long, z >= +k short; yalnızca ADX(14) <= adx_max (rejim filtresi; None = filtre yok)
  stop    : giriş kapanışı -/+ s x ATR(14) (hakem stop-market; gap'te açılıştan). Stop sonrası z |z| < reset olana dek yeniden giriş yok
  çıkış   : z SMA'yı geçince (z >= 0 long, <= 0 short) ya da max_age bar sonra
  boyut   : stop mesafesine göre sabit risk: qty = risk x sermaye / (s x ATR); sembol notional tavanı cap x sermaye
Kullanım: python scripts/mr_explore.py --out /data/mr_explore [--smoke]   (varyantlar aşağıda sabit liste)"""
import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ensemble as E  # noqa: E402  (load, spec, utc, keep, daily, D)

from kepler import audit, indicators as ix, report, robust, tape  # noqa: E402
from kepler import evaluate as ev  # noqa: E402

BASE = dict(n=20, k=2.0, s=2.0, adx_max=25.0, exit_z=0.0, max_age=24, reset=1.0, risk=0.005, cap=0.5, stop=True, flip=False, regime=None, vol_max=None)
VARIANTS = {  # a priori listesi (sonuca bakılarak eklenmedi): filtre x stop, iki ölçek (n = 20 saat ~ saatlik Bollinger; n = 80 saat ~ 4 saatlik n = 20)
    "h20_filter_stop": {}, "h20_nofilter_stop": dict(adx_max=None), "h20_filter_nostop": dict(stop=False), "h20_nofilter_nostop": dict(adx_max=None, stop=False),
    "h80_filter_stop": dict(n=80, max_age=96), "h80_nofilter_stop": dict(n=80, max_age=96, adx_max=None),
    "h20_filter_stop_flip": dict(flip=True), "h20_nofilter_stop_flip": dict(adx_max=None, flip=True),  # yön testi: bandda trend takibi (aynı stop/boyut)
}


VARIANTS2 = {  # SONRADAN SEÇİLDİ (olay çalışmasından sonra: range rejimi + hacim şoku olmayan uç; reports/edge_experts.md "Keşif eki")
    "range_vol_stop": dict(adx_max=None, regime="range", vol_max=2.0), "range_vol_nostop": dict(adx_max=None, regime="range", vol_max=2.0, stop=False),
    "range_only_stop": dict(adx_max=None, regime="range"), "vol_only_stop": dict(adx_max=None, vol_max=2.0),
}
VARIANTS3 = {f"range_vol_stop{x}atr": dict(adx_max=None, regime="range", vol_max=2.0, s=float(x)) for x in (3, 4, 6)}  # stop genişliği taraması (kullanıcı: kâr stopla azalıyorsa sorun yönetimde); 2 ve stopsuz set 2'de
WINDOWS = {"tum": E.MAIN, "2020-21": ("2020-04-01", "2022-01-01"), "2022-26": ("2022-01-01", "2026-04-01")}


def trig(kl: pd.DataFrame, mark) -> tuple[np.ndarray, np.ndarray]:
    """Hakemle aynı tetik H/L: mark varsa mark; O/C aralığın içinde."""
    hi, lo = kl.high, kl.low
    if mark is not None and {"high", "low"} <= set(mark.columns):
        hi, lo = mark.high.reindex(kl.index).fillna(kl.high), mark.low.reindex(kl.index).fillna(kl.low)
    return pd.concat([hi, kl.open, kl.close], axis=1).max(axis=1).to_numpy(), pd.concat([lo, kl.open, kl.close], axis=1).min(axis=1).to_numpy()


def machine(kl: pd.DataFrame, mark, capital: float, P: dict, gate=None):
    """gate: saatlik bool dizisi (BTC rejimi); P["vol_max"]: giriş saatinin hacmi önceki 24 saat ortalamasının en çok bu katı (hacim şokunda fade yok)."""
    c = kl.close.to_numpy()
    vr = (kl.volume / kl.volume.rolling(24).mean().shift(1)).to_numpy()
    sd = kl.close.rolling(P["n"]).std(ddof=0)
    z = ((kl.close - kl.close.rolling(P["n"]).mean()) / sd.where(sd > 0)).to_numpy()
    atr = ix.rma(ix._tr(kl), 14).to_numpy()
    adx = ix.adx(kl)["adx"].to_numpy()
    hi, lo = trig(kl, mark)
    n = len(c)
    tgt, stp, info = np.full(n, np.nan), np.full(n, np.nan), dict(entries=0, stops=0, exits=0)
    pos, qty, stop, age, halt = 0, 0.0, np.nan, 0, False
    for t in range(n):
        zt = z[t]
        if pos and P["stop"] and ((pos > 0 and lo[t] <= stop) or (pos < 0 and hi[t] >= stop)):  # önceki kapanışta kurulan stop bu barda vuruldu: hakem kapattı
            pos, stop, halt = 0, np.nan, True
            tgt[t], info["stops"] = 0.0, info["stops"] + 1
        elif pos:
            age += 1
            if (pos > 0 and zt >= P["exit_z"]) or (pos < 0 and zt <= -P["exit_z"]) or age >= P["max_age"]:
                pos, stop = 0, np.nan
                tgt[t], info["exits"] = 0.0, info["exits"] + 1
            else:
                tgt[t], stp[t] = pos * qty * c[t], stop  # sabit miktar: hedef notional fiyatla birlikte (gereksiz yeniden dengeleme yok)
        if pos == 0:
            if halt and abs(zt) < P["reset"]:
                halt = False
            ok = (gate is None or bool(gate[t])) and (P["vol_max"] is None or (not np.isnan(vr[t]) and vr[t] <= P["vol_max"]))
            ok = ok and not halt and not np.isnan(zt) and not np.isnan(atr[t]) and atr[t] > 0 and (P["adx_max"] is None or (not np.isnan(adx[t]) and adx[t] <= P["adx_max"]))
            if ok and abs(zt) >= P["k"]:
                d = int(-np.sign(zt)) * (-1 if P["flip"] else 1)
                dist = P["s"] * atr[t]
                qty = min(P["risk"] * capital / dist, P["cap"] * capital / c[t])
                pos, age = d, 0
                stop = c[t] - d * dist if P["stop"] else np.nan
                tgt[t], stp[t] = d * qty * c[t], stop
                info["entries"] += 1
    return pd.DataFrame(dict(target=tgt, stop=stp), index=kl.index), info


def regime_gate(kls: dict, want: str | None) -> dict:
    """BTC günlük rejimi (robust.regime: nedensel, d-1 kapanışına kadar) saatlik indekse; want = istenen etiket. Kitap içinde hesaplanır (kesik/bozuk veride nedensellik denetimi geçerli)."""
    if want is None:
        return {s: None for s in kls}
    lab = robust.regime(kls["BTCUSDT"].close.resample("1D").last())
    return {s: (lab.reindex(kl.index.normalize()).to_numpy() == want) for s, kl in kls.items()}


def make_book(capital: float, P: dict, marks: dict):
    def book(kls):
        g = regime_gate(kls, P["regime"])
        return {s: machine(kl, marks.get(s), capital, P, g[s])[0] for s, kl in kls.items()}
    return book


def run_variant(a):
    name, over, window = a
    P, sp = {**BASE, **over}, E.spec()
    data = E.data_of(E.EXT)
    marks = {s: d["mark"] for s, d in data.items()}
    book = make_book(E.CAP, P, marks)
    out = book({s: d["kl"] for s, d in data.items()})
    res, win, _ = ev.run_book(out, data, sp, *E.utc(window))
    pnl = report.book_pnl(win, res, sp)
    daily = pnl.resample("1D").sum()
    close = data["BTCUSDT"]["kl"].close.resample("1D").last()
    reg = robust.by_regime(daily, robust.regime(close))
    g = regime_gate({s: d["kl"] for s, d in data.items()}, P["regime"])
    info = {s: machine(data[s]["kl"], marks.get(s), E.CAP, P, g[s])[1] for s in E.EXT}
    f = res["fills"]
    return name, dict(P=P, summary=E.keep(res), sharpe=float(daily.mean() / daily.std() * np.sqrt(365)) if daily.std() > 0 else None, regimes={k: v["total"] for k, v in reg.items()},
                      daily=E.daily(pnl), entries=sum(i["entries"] for i in info.values()), stops=sum(i["stops"] for i in info.values()), exits=sum(i["exits"] for i in info.values()),
                      n_stop_fills=int(f.stop.sum()) if len(f) else 0, traded=float((f.qty * f.px).sum()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/data/mr_explore")
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--only", default=None)
    ap.add_argument("--set", type=int, default=1, help="1: ilk 8 varyant; 2: sonradan seçilen range/hacim varyantları x 3 pencere")
    ap.add_argument("--causal", action="store_true", help="yalnızca nedensellik denetimi (audit.check_causal_book, 2 kesim)")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    window = ("2021-11-01", "2022-02-01") if a.smoke else E.MAIN
    Path(a.out).mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    E.load(E.EXT, [("/data/pre2022", None, E.SPLIT), ("/data", E.SPLIT, None)])
    if a.causal:
        kls = {s: E.D[s]["kl"] for s in E.EXT}
        bad = audit.check_causal_book(make_book(E.CAP, {**BASE, **VARIANTS2["range_vol_stop"]}, {s: E.D[s]["mark"] for s in E.EXT}), kls, fracs=(0.3, 0.7))
        print("nedensellik, bozuk kesimler:", bad, flush=True)
        Path(a.out, "causal.json").write_text(json.dumps(bad))
        raise SystemExit(0)
    if a.set in (2, 3):
        jobs = [(f"{k}|{w}", v, WINDOWS[w] if not a.smoke else window) for k, v in (VARIANTS2 if a.set == 2 else VARIANTS3).items() for w in WINDOWS]
    else:
        jobs = [(k, VARIANTS[k], window) for k in VARIANTS if not a.only or k in a.only.split(",")]
    with ProcessPoolExecutor(a.procs) as ex:
        res = dict(ex.map(run_variant, jobs, chunksize=1))
    Path(a.out, "smoke.json" if a.smoke else f"results{a.set}.json").write_text(json.dumps(res))
    for k, v in res.items():
        print(k, f"net={v['summary']['net_pnl']:.0f} gross={v['summary']['gross_pnl']:.0f} fills={v['summary']['n_fills']:.0f} rej={v['summary']['n_rejected']:.0f} liq={v['summary']['n_liq']:.0f}", flush=True)
    print(f"bitti {time.time() - t0:.0f}s", flush=True)
