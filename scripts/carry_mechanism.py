"""#17: carry_xs'in fiyat/funding mekanizması ve nötrlük iddiası. Teşhis; strateji, uzman ve boyutlama DEĞİŞMEZ (geliştirme verisi; mühürlü dönem yok; yeni grid/uzman yok).
  modal run --detach modal_app.py --cmd "python scripts/carry_mechanism.py --part real|perm --seeds 0,1,2 --out /data/carry_mech"; sonra --part merge
FALSİFİYE EDİLEBİLİR HİPOTEZ (koşudan önce): H_f: carry_xs funding'i kesitte 'kalabalık long'lara (en yüksek 7g funding) short, en düşüğe long olarak toplar; funding gelirini, o bacaklar taşınan fiyat
riskinin karşılığı olarak alır. Tahminler: (a) funding bileşeni yıl/rejim kırılımlarının çoğunluğunda pozitiftir; (b) funding bileşeni, aynı günlük kesit dağılımı + aynı boyutlama/maliyetle ama sembollere RASTGELE atanmış
tahminlerde (benchmark 'perm', 10 tohum) görülen dağılımın üstündedir; (c) fiyat bileşeni sistematik pozitif DEĞİLDİR (aksi halde funding dışı yön/beta kaynağı var). (a)-(c)'den biri tutmazsa mekanizma desteklenmez.
Benchmark ÖNCEDEN seçildi (maruziyet/maliyet eşlemeli): 'perm' = günlük kesitte tahminleri aktif semboller arasında permüte et (kesit dağılımı, aktiflik, boyutlama ve maliyet yapısı korunur). Beta ile dolar nötrlüğü karıştırılmaz:
beta ayrı raporlanır (BTC günlük getirisine regresyon), dolar nötrlüğü = |net$|/brüt$ olarak ayrıca ölçülür.
Mekanizma testi ≠ tradeable edge kararı: karar kartı (K1-K9, NO_EDGE) değişmez; bu çıktı o kararı kurtarmaz."""
import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from kepler import portfolio, report

NEUTRAL_LIMIT = 0.20  # ölçüt (önceden): |net$|/brüt$ ortalaması <= 0,20 ise 'yaklaşık dolar-nötr' denebilir


def stages(f: pd.DataFrame, st: dict, cap: float, p) -> dict[str, pd.DataFrame]:
    """forecast -> vol/risk/cap (tampon yok) -> tampon sonrası hedef; (lot sonrası gerçek pozisyon `realized` ile)."""
    return dict(forecast=f.fillna(0.0), sized=portfolio.size(f, st, cap, replace(p, buffer=0.0)), buffered=portfolio.size(f, st, cap, p))


def exposure(n: pd.DataFrame) -> dict:
    net, gross = n.sum(1), n.abs().sum(1)
    ok = gross > 0
    r = (net[ok] / gross[ok])
    return dict(days=int(ok.sum()), net_mean=float(net[ok].mean()), gross_mean=float(gross[ok].mean()), net_over_gross_mean=float(r.mean()), abs_net_over_gross_mean=float(r.abs().mean()),
                share_days_abs_gt_limit=float((r.abs() > NEUTRAL_LIMIT).mean()), neutral=bool(r.abs().mean() <= NEUTRAL_LIMIT))


def realized(fills: pd.DataFrame, closes: pd.DataFrame) -> pd.DataFrame:
    """Gün sonu fiili pozisyon notional'ı (gerçek lot sonrası): fills'ten kümülatif işaretli miktar x gün sonu kapanışı."""
    q = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    day = pd.to_datetime(fills.ts, unit="ns", utc=True).dt.floor("1D")
    for s, g in fills.groupby("sym"):
        sg = np.where(g.side == "BUY", g.qty, -g.qty)
        q[s] = pd.Series(sg, index=day[g.index].to_numpy()).groupby(level=0).sum().reindex(closes.index, fill_value=0.0).cumsum()
    return q * closes


def decompose(data: dict, res: dict, spec, regimes: pd.Series | None = None) -> dict:
    """Saatlik yeniden kurulumdan fiyat / funding / maliyet ayrımı, yıl ve rejim bazında. Isınma/etiketsiz dönem 'unclassified'; muhasebe residual'ı = yeniden kurulum toplamı − hakem net_pnl."""
    z = replace(spec, fee_rt_bps=0.0, slip_rt_bps=0.0)
    parts = {"price": [], "funding": [], "total": []}
    for s, d in data.items():
        f = res["fills"][res["fills"].sym == s]
        zf = f.assign(commission=0.0, liq=False)
        price = report.hourly_pnl(d["kl"], d.get("mark"), None, zf, z)
        withf = report.hourly_pnl(d["kl"], d.get("mark"), d.get("funding"), zf, z)
        parts["price"].append(price)
        parts["funding"].append(withf - price)
        parts["total"].append(report.hourly_pnl(d["kl"], d.get("mark"), d.get("funding"), f, spec))
    daily = {k: pd.concat(v, axis=1).fillna(0.0).sum(axis=1).resample("1D").sum() for k, v in parts.items()}
    daily["cost"] = daily["total"] - daily["price"] - daily["funding"]
    D = pd.DataFrame(daily)
    lab = (regimes.reindex(D.index) if regimes is not None else pd.Series(np.nan, index=D.index)).fillna("unclassified")
    by = lambda key: {str(k): {c: float(v) for c, v in g[["price", "funding", "cost", "total"]].sum().items()} | dict(n_days=int(len(g))) for k, g in D.groupby(key)}  # noqa: E731
    return dict(by_year=by(D.index.year), by_regime=by(lab.to_numpy()), totals={c: float(D[c].sum()) for c in ("price", "funding", "cost", "total")}, residual=float(D["total"].sum() - res["summary"]["net_pnl"]))


def permute_forecast(f: pd.DataFrame, act: pd.DataFrame, seed: int) -> pd.DataFrame:
    """'perm' benchmark: her gün aktif semboller arasında tahmin değerlerini permüte eder (kesit dağılımı ve aktiflik korunur)."""
    rng, x, a = np.random.default_rng([1, seed]), f.to_numpy(copy=True), act.to_numpy()
    for d in range(len(x)):
        i = np.flatnonzero(a[d] & ~np.isnan(x[d]))
        x[d, i] = x[d, rng.permutation(i)]
    return pd.DataFrame(x, index=f.index, columns=f.columns)


def beta(daily_net: pd.Series, btc_ret: pd.Series, cap: float) -> dict:
    r = (daily_net / cap).reindex(btc_ret.index).dropna()
    b = btc_ret.reindex(r.index)
    cov = np.cov(r, b)
    return dict(beta=float(cov[0, 1] / cov[1, 1]), corr=float(np.corrcoef(r, b)[0, 1]), n=int(len(r)))


def stage_all(out_dir: str, part: str = "real", seeds: str = "0"):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import audit_fix as AF  # noqa: E402
    import ensemble as E  # noqa: E402
    import signal_diag as sd  # noqa: E402
    import signal_phase2 as P2  # noqa: E402

    from kepler import ensemble as en  # noqa: E402
    from kepler import evaluate as ev  # noqa: E402
    from kepler import robust  # noqa: E402
    from kepler.experts import carry_xs  # noqa: E402
    cap = P2.CAPR
    p = en.Params(names=("carry_xs",), weights=(1.0,))
    mem = sd.members(20)
    syms = sorted(mem.sym.unique())
    E.D.clear()
    AF.load_dynamic(syms, cap=cap)
    syms = [s for s in syms if s in E.D]
    data, kls = E.data_of(syms), {s: E.D[s]["kl"] for s in syms}
    close, _ = en.panel(kls)
    st = en.market_state(close, kls, p)
    st = dict(st, active=st["active"] & sd.member_mask(close.index, close.columns, mem))
    f = en.combine((carry_xs.forecast(close, st, p),), st, p)
    sp = E.spec(cap=cap)

    def run(ff):
        n = portfolio.size(ff, st, cap, p)
        out = {s: pd.DataFrame(dict(target=en.place(kl, n[s]), stop=np.nan), index=kl.index) for s, kl in kls.items()}
        res, win, _ = ev.run_book(out, data, sp, *E.utc(E.MAIN))
        return res, win, n

    t0 = time.time()
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    if part == "real":
        res, win, _ = run(f)
        stg = stages(f, st, cap, p)
        rz = realized(res["fills"], close)
        btc = kls["BTCUSDT"].close.resample("1D").last()
        pnl = report.book_pnl(win, res, sp).resample("1D").sum()
        real = decompose(win, res, sp, robust.regime(btc))
        out = dict(capital=cap, window=E.MAIN, exposure={k: exposure(v) for k, v in stg.items()} | {"realized_lot": exposure(rz)}, forecast_sum_abs_mean=float(f.sum(1).abs().mean()), decomposition=real,
                   beta_btc=beta(pnl, btc.pct_change(), cap), net=float(res["summary"]["net_pnl"]), neutral_limit=NEUTRAL_LIMIT, seconds=time.time() - t0)
        (Path(out_dir) / "real.json").write_text(json.dumps(out, indent=1, default=str, allow_nan=False))
        print("real tamam", f"{time.time() - t0:.0f}s", json.dumps(dict(exposure=out["exposure"], totals=real["totals"], residual=real["residual"], beta=out["beta_btc"]))[:2500])
    else:  # perm: --seeds "0,1,2" (her tohum bir 'perm' benchmark koşusu)
        reg = robust.regime(kls["BTCUSDT"].close.resample("1D").last())
        for i in [int(x) for x in seeds.split(",")]:
            r_i, w_i, _ = run(permute_forecast(f, st["active"], i))
            d_i = decompose(w_i, r_i, sp, reg)
            (Path(out_dir) / f"perm_{i}.json").write_text(json.dumps(dict(seed=i, totals=d_i["totals"], by_year=d_i["by_year"], net=float(r_i["summary"]["net_pnl"]), seconds=time.time() - t0), default=str, allow_nan=False))
            print("perm", i, f"{time.time() - t0:.0f}s", d_i["totals"])


def merge(out_dir: str) -> dict:
    """Parça çıktılarını birleştirir: funding gerçek değerinin perm dağılımına göre sıra-p'si (1 + #{perm >= gerçek}) / (n + 1) (n küçük: çözünürlük 1/(n+1), sertifika değil)."""
    d = Path(out_dir)
    real = json.loads((d / "real.json").read_text())
    perm = [json.loads(f.read_text()) for f in sorted(d.glob("perm_*.json"))]
    fp = np.array([x["totals"]["funding"] for x in perm])
    f_real = real["decomposition"]["totals"]["funding"]
    return dict(real=real, n_perm=len(perm), perm_funding=fp.tolist(), perm_net=[x["net"] for x in perm], funding_rank_p=float((1 + (fp >= f_real).sum()) / (len(fp) + 1)) if len(fp) else None, min_p_resolution=1 / (len(fp) + 1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", required=True, choices=["real", "perm", "merge"])
    ap.add_argument("--out", default="/data/carry_mech")
    ap.add_argument("--seeds", default="0")
    a = ap.parse_args()
    if a.part == "merge":
        print(json.dumps(merge(a.out)))
    else:
        stage_all(a.out, a.part, a.seeds)
