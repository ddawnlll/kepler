"""Trade denetimi düzeltmeleri, ANALİZ AŞAMASI (yerelde, hakemsiz): scripts/trade_audit.py (taban), scripts/audit_fix.py (Modal aşamaları) çıktılarından tabloları hesaplar,
`reports/trade_audit_data/fix/analysis.json` ve CSV'leri yazar. Rapor (scripts/trade_audit_report.py) yalnızca bu dosyaları okur: rakamı ELLE yazan yok.

  python scripts/audit_fix_analysis.py                  # varsayılan dizinler
Tanımlar `scripts/audit_metrics.py`'de (tek yer). Görülmüş veride yapılan her analiz örneklem içi / post-hoc'tur; OOS iddiası yoktur."""
import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import audit_metrics as am  # noqa: E402

from kepler import stats  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "reports" / "trade_audit_data" / "ev1_plus_new"
FIX = ROOT / "reports" / "trade_audit_data" / "fix"
OUT = FIX / "analysis"
SEED = 0


def load(src: Path = SRC) -> dict:
    meta = json.loads((src / "meta.json").read_text())
    d = dict(meta=meta, cap=float(meta["cap"]), names=list(meta["names"]), weights=list(meta["weights"]),
             daily=pd.read_csv(src / "daily.csv", index_col=0, parse_dates=True), trades=pd.read_csv(src / "trades.csv", parse_dates=["opened", "closed", "decision_day"]),
             fills=pd.read_csv(src / "fills.csv"), panels=pd.read_parquet(src / "panels.parquet"))
    d["hourly"] = pd.read_parquet(src / "hourly.parquet") if (src / "hourly.parquet").exists() else None
    d["syms"] = sorted({c.split(".")[0] for c in d["hourly"].columns}) if d["hourly"] is not None else sorted({c.split(".")[1] for c in d["panels"].columns if c.startswith("F.")})
    return d


def panel(P: pd.DataFrame, name: str) -> pd.DataFrame:
    cols = [c for c in P.columns if c.startswith(name + ".")]
    out = P[cols].copy()
    out.columns = [c.split(".", 1)[1] for c in cols]
    return out


# ================================================================ A. başlık metrikleri (0.2) ve alt dönemler
def headline(D: dict) -> dict:
    pnl, cap = D["daily"].net, D["cap"]
    eq = cap + pnl.cumsum()
    years = (pnl.index[-1] - pnl.index[0]).days / 365.25
    net = float(pnl.sum())
    rf, re = (pnl / cap), (pnl / eq.shift(1).fillna(cap))
    sortino = lambda r: float(r.mean() / np.sqrt((np.minimum(r, 0) ** 2).mean()) * np.sqrt(365))  # noqa: E731
    dd_fixed, dd_eq = am.max_dd_fixed(pnl, cap), am.max_dd_equity(pnl, cap)
    prim = dict(net=net, net_pct_cap=net / cap, annual_return_add=net / cap / years, sharpe=am.sharpe_fixed(pnl, cap), sortino=sortino(rf), vol=am.vol_fixed(pnl, cap),
                maxdd=dd_fixed, maxdd_usd=dd_fixed * cap, calmar=(net / cap / years) / dd_fixed)
    sec = dict(cagr=float((eq.iloc[-1] / cap) ** (1 / years) - 1), sharpe=am.sharpe_equity(pnl, cap), sortino=sortino(re), vol=am.vol_equity(pnl, cap), maxdd=dd_eq,
               maxdd_usd_peak=float((eq.cummax().clip(lower=cap) - eq).max()), calmar=float(((eq.iloc[-1] / cap) ** (1 / years) - 1) / dd_eq))
    tab = am.drawdown_table(eq, cap)
    return dict(primary=prim, secondary=sec, years=years, n_days=int(len(pnl)), longest_underwater_days=am.longest_underwater_days(eq, cap), drawdown_table=tab.assign(
        peak=tab.peak.dt.strftime("%Y-%m-%d"), trough=tab.trough.dt.strftime("%Y-%m-%d"), recovered=tab.recovered.dt.strftime("%Y-%m-%d").fillna("devam")).to_dict("records"),
        periods=am.period_table(pnl, cap).to_dict("records"), bootstrap=am.bootstrap_sharpe_ci(pnl, cap),
        period_bootstrap={k: am.bootstrap_sharpe_ci(pnl[(pnl.index >= pd.Timestamp(a, tz="UTC")) & (pnl.index <= pd.Timestamp(b, tz="UTC"))], cap, B=2000, seed=SEED)["sharpe_q"] for k, (a, b) in am.PERIODS.items()})


# ================================================================ B. DSR (1.1)
def trial_sharpes() -> dict:
    """Deneme düzeyinde günlük serisi bulunan set: EV1 ve 9 uzmanın birincil + ablasyon + komşu koşuları (reports/*_data/primary.json; sermaye 10 000). Ledger satırlarında Sharpe yok."""
    out = {}
    paths = [("ev1", ROOT / "reports" / "ensemble_data" / "primary.json")] + [(n, ROOT / "reports" / "edge_experts_data" / n / "primary.json") for n in
                                                                                   ("trend", "xs_momentum", "carry", "bollinger", "lowvol", "nearhigh", "fundcrowd", "volrev", "orderflow")]
    for name, p in paths:
        if not p.exists():
            continue
        j = json.loads(p.read_text())
        for k, v in j.items():
            if (k == "main" or k.startswith("abl_") or k.startswith("nb_")) and isinstance(v, dict) and "daily" in v:
                r = np.array(list(v["daily"].values()), float) / 10_000.0
                if r.std() > 0:
                    out[f"{name}/{k}"] = stats.moments(r)[0]
    return out


def dsr_table(D: dict) -> dict:
    pnl, cap = D["daily"].net, D["cap"]
    r = (pnl / cap).to_numpy(float)
    ts = json.loads((FIX / "trials" / "trials.json").read_text())["summary"]
    pool = trial_sharpes()
    sd_pool = float(np.std(list(pool.values()), ddof=1))  # günlük
    ns = {"6 (EV1 ön kayıt: birincil + 5 ablasyon)": 6, f"{len(pool)} (günlük serisi olan EV1 + uzman koşuları)": len(pool), "4 127 (TASKS.md: repo 4 119 + Modal edge 8)": 4127,
          f"{ts['repo_rows']} (repo defteri)": ts["repo_rows"], f"{ts['repo_rows'] + ts['volume_only_nonsmoke_rows']} (repo + Modal-yalnız gerçek; birincil)": ts["repo_rows"] + ts["volume_only_nonsmoke_rows"],
          f"{ts['repo_rows'] + ts['volume_only_rows']} (smoke dahil tüm defter)": ts["repo_rows"] + ts["volume_only_rows"]}
    sigmas = {"havuz": sd_pool, "0,25": 0.25 / math.sqrt(365), "0,5": 0.5 / math.sqrt(365), "1,0": 1.0 / math.sqrt(365)}  # günlük; etiketler yıllık
    rows = []
    for nlab, n in ns.items():
        row = dict(N=nlab, n=int(n))
        for slab, s in sigmas.items():
            sr0 = (s * ((1 - stats.EULER) * norm.ppf(1 - 1 / n) + stats.EULER * norm.ppf(1 - 1 / (n * math.e)))) if n > 1 else 0.0
            row[f"sr0_yillik[{slab}]"] = float(stats.annual(sr0))
            row[f"dsr[{slab}]"] = float(stats.psr(r, sr0))
        rows.append(row)
    sr_d, g3, g4, t = stats.moments(r)
    tj = json.loads((FIX / "trials" / "trials.json").read_text())["files"]
    repo_sha = {f["sha"] for f in tj if f["loc"] == "repo"}
    only = [f for f in tj if f["loc"] == "volume" and f["sha"] not in repo_sha and not f["smoke"]]
    detail = dict(pre2022_out=int(sum(f["n"] for f in only if f["path"].startswith("pre2022_out/"))), edge=int(sum(f["n"] for f in only if f["path"].startswith("edge/"))))
    return dict(detail=detail, rows=rows, psr0=float(stats.psr(r, 0.0)), sharpe_annual=float(stats.annual(sr_d)), skew=g3, kurt=g4, T=t, pool_n=len(pool), pool_sd_annual=float(stats.annual(sd_pool)),
                pool_sharpe_annual=dict(min=float(stats.annual(min(pool.values()))), median=float(stats.annual(np.median(list(pool.values())))), max=float(stats.annual(max(pool.values())))),
                trials=ts, min_trl_days=float(stats.min_trl(sr_d, g3, g4, 0.0)))


# ================================================================ C. rotasyon null'u (1.2)
def null_table(D: dict) -> dict | None:
    fs = sorted((FIX / "null").glob("null_*.csv"))
    if not fs:
        return None
    df = pd.concat([pd.read_csv(f) for f in fs]).drop_duplicates("i")
    real = df[df.i < 0].iloc[0]
    nul = df[df.i >= 0]
    B = len(nul)
    p = lambda col: float(stats.rotation_p(real[col], nul[col].to_numpy()))  # noqa: E731
    q = lambda col: {k: float(nul[col].quantile(v)) for k, v in dict(p5=.05, p50=.5, p95=.95, p99=.99).items()}
    return dict(B=int(B), real=dict(net=float(real.net), gross=float(real.gross), sharpe=float(real.sharpe_fixed)), p_gross=p("gross"), p_net=p("net"), p_sharpe=p("sharpe_fixed"),
                null=dict(gross=dict(mean=float(nul.gross.mean()), sd=float(nul.gross.std()), **q("gross")), net=dict(mean=float(nul.net.mean()), sd=float(nul.net.std()), **q("net")),
                          sharpe=dict(mean=float(nul.sharpe_fixed.mean()), sd=float(nul.sharpe_fixed.std()), **q("sharpe_fixed"))), n_ge=dict(gross=int((nul.gross >= real.gross).sum()), net=int((nul.net >= real.net).sum()), sharpe=int((nul.sharpe_fixed >= real.sharpe_fixed).sum())),
                bonferroni_threshold_note="K1 eşiği p ≤ 0,05/N; N = deneme sayısı (DSR tablosundaki N); p, 1/(B+1) = %.4f altına inemez" % (1 / (B + 1)))


def dsr_nmax(D: dict, level: float = 0.95) -> dict:
    """DSR ≥ level için izin verilen en büyük N (σ_SR havuz / 0,5 / 0,25 yıllık). N = 1..6000 taranır (tarama ölçüm içindir, strateji parametresi değil)."""
    r = (D["daily"].net / D["cap"]).to_numpy(float)
    pool = trial_sharpes()
    sig = {"havuz": float(np.std(list(pool.values()), ddof=1)), "0,5": 0.5 / math.sqrt(365), "0,25": 0.25 / math.sqrt(365)}
    out = {}
    for k, s in sig.items():
        best = 0
        for n in range(2, 6001):
            sr0 = s * ((1 - stats.EULER) * norm.ppf(1 - 1 / n) + stats.EULER * norm.ppf(1 - 1 / (n * math.e)))
            if stats.psr(r, sr0) >= level:
                best = n
            else:
                break
        out[k] = best
    return out


# ================================================================ D. uzman atfı (2.1)
def _decision_to_pnl_day(df: pd.DataFrame) -> pd.DataFrame:
    """Karar günü t -> PnL günü t+1 (pozisyon sonraki günün açılışında kurulur ve o gün tutulur)."""
    return df.shift(1)


def attribution(D: dict) -> dict:
    """Doğrusal uzman atfı: günlük fiyat PnL'i = Σ_i (w_i x F_i x ölçek_t x r_t) + artık; ölçek_t = unit x 0,5 / m_t (risk motorunun tam-tahmin pozisyonu x tahmin ölçeği).
    Artık, aşamaların telesko farkıdır (tam kimlik): F kırpma/ısınma, oynaklık-sembol-brüt tavanları, tampon, yuvarlama/zamanlama. Sonra maliyet (devir payı), funding ve çıkış maliyeti ayrı satır.
    r_t = karar günü t için: açılış(t+2) / açılış(t+1) - 1 (dolum t+1 açılışında, pozisyon t+2 açılışına kadar); son gün için son kapanış."""
    P, H, names, w, cap = D["panels"], D["hourly"], D["names"], D["weights"], D["cap"]
    syms = D["syms"]
    unit, m, F = panel(P, "unit")[syms], panel(P, "m")[syms], panel(P, "F")[syms]
    opn, cls = panel(P, "open")[syms], panel(P, "close")[syms]
    o1 = opn.shift(-1)
    o2 = opn.shift(-2)
    o2.iloc[-2] = cls.iloc[-1]  # karar günü D-1: pozisyon son güne kadar; değerleme son kapanışta
    r = (o2 / o1 - 1).fillna(0.0)
    lin = {}
    for n, wi in zip(names, w):
        e = panel(P, f"E_{n}")[syms].fillna(0.0)
        lin[n] = (unit * (0.5 / m) * wi * e).fillna(0.0)
    L0 = sum(lin.values())
    act = panel(P, "active")[syms]
    warm = (act.any(axis=1).cumsum() >= 30).to_numpy()  # ensemble.combine: ilk 30 aktif günde F = 0 (pozisyon yok)
    L0w = L0.mul(warm, axis=0)  # ısınma maskesi uygulanmış doğrusal toplam
    L1, L2, L3 = panel(P, "n0")[syms].fillna(0.0), panel(P, "n2")[syms].fillna(0.0), panel(P, "out")[syms].fillna(0.0)
    # gerçek pozisyon: karar günü t'nin ertesi günü 00:00 barı sonundaki pozisyon (qty) x fiyat farkı
    hs = lambda metric: pd.DataFrame({s_: H[f"{s_}.{metric}"] for s_ in syms}).sum(axis=1).groupby(H.index.normalize()).sum()  # noqa: E731  (eksik saatlik bar = 0, NaN toplamı bozmasın)
    pos_day0 = pd.DataFrame({s_: H[f"{s_}.pos"].ffill().groupby(H.index.normalize()).first() for s_ in syms})  # günün ilk barı sonu (dolum sonrası) pozisyon
    qty = pos_day0.reindex(P.index.shift(1, freq="D")).set_axis(P.index)  # karar günü t -> t+1'in pozisyonu
    L4_pnl = (qty * (o2 - o1)).fillna(0.0).sum(axis=1)
    pnl_of = lambda L: (L * r).sum(axis=1)  # noqa: E731
    day = lambda s_: s_.shift(1)  # karar günü -> PnL günü  # noqa: E731
    comp = {n: day(pnl_of(l_)) for n, l_ in lin.items()}
    P0, P0w, P1, P2, P3, P4 = *(day(pnl_of(L)) for L in (L0, L0w, L1, L2, L3)), day(L4_pnl)
    price_actual = hs("price")
    idx = price_actual.index
    g = lambda s_: s_.reindex(idx).fillna(0.0)  # noqa: E731
    comp = {n: g(v) for n, v in comp.items()}
    P0, P0w, P1, P2, P3, P4 = g(P0), g(P0w), g(P1), g(P2), g(P3), g(P4)
    eff = dict(warmup=P0w - P0, f_clip=P1 - P0w, caps=P2 - P1, buffer=P3 - P2, drift_rounding=P4 - P3, residual=price_actual - P4)
    comm_h, fund_h, exit_h = hs("commission"), hs("funding"), hs("exit")
    # maliyetin devir payına göre dağılımı: her (sembol, karar günü) dolumunun komisyonu, o sembolde son dolumdan beri uzman bileşenlerinin |Δ| payına göre
    fl = D["fills"].copy()
    fl["day"] = pd.to_datetime(fl.ts, unit="ns", utc=True).dt.normalize() - pd.Timedelta("1D")
    ev = fl.groupby(["sym", "day"]).commission.sum().reset_index().sort_values(["sym", "day"])
    cost_share = {n: 0.0 for n in names}
    unalloc = 0.0
    last_n = {s: {n: 0.0 for n in names} for s in syms}
    for row in ev.itertuples():
        if row.day not in P.index:
            unalloc += row.commission
            continue
        cur = {n: float(lin[n].at[row.day, row.sym]) for n in names}
        dlt = {n: abs(cur[n] - last_n[row.sym][n]) for n in names}
        tot = sum(dlt.values())
        if tot <= 0:
            tot, dlt = (sum(abs(v) for v in cur.values()), {n: abs(cur[n]) for n in names})
        if tot <= 0:
            unalloc += row.commission
        else:
            for n in names:
                cost_share[n] += row.commission * dlt[n] / tot
        last_n[row.sym] = cur
    exp_rows = []
    for n, wi in zip(names, w):
        pn = float(comp[n].sum())
        exp_rows.append(dict(expert=n, weight=wi, price_pnl=pn, cost=-cost_share[n], net_attr=pn - cost_share[n]))
    lin_total = sum(comp.values())
    day_resid = price_actual - lin_total
    r2 = float(np.corrcoef(lin_total.to_numpy(), price_actual.to_numpy())[0, 1] ** 2)
    totals = dict(price_actual=float(price_actual.sum()), linear_experts=float(lin_total.sum()), **{k: float(v.sum()) for k, v in eff.items()}, commission=float(comm_h.sum()), funding=float(fund_h.sum()),
                  exit=float(exit_h.sum()), unallocated_commission=float(unalloc))
    totals["net"] = totals["price_actual"] - totals["commission"] + totals["funding"] - totals["exit"]
    totals["identity_check"] = totals["linear_experts"] + sum(totals[k] for k in eff) - totals["price_actual"]
    return dict(experts=exp_rows, totals=totals, r2_daily_linear_vs_actual=r2, resid_total_abs_share_of_net=float(abs(day_resid.sum()) / abs(totals["net"])),
                resid_gross_daily_rms=float(np.sqrt((day_resid ** 2).mean())), actual_daily_rms=float(np.sqrt((price_actual ** 2).mean())),
                nonlinear_sum=float(sum(totals[k] for k in eff)), nonlinear_abs_daily_sum=float(sum(v.abs().sum() for v in eff.values())))


# ================================================================ E/J. trade kırılımları: bps (notional) ve ay-küme bootstrap güven aralığı (1.4, 2.2)
def prep_trades(D: dict) -> pd.DataFrame:
    tr = D["trades"].copy()
    tr["bps"] = tr.net / tr.avg_notional * 1e4  # trade düzeyi: net / zaman-ortalamalı notional (getiri/maruziyet). Not: ortalama notional çıkışta bilinir; boyut ANALİZİ (2.2) bu tanımı kullanmaz (karar-günü birimi, size_vol_f)
    tr["absf"] = tr.f_total.abs()
    tr["n_aligned"] = (tr[[f"c_{n}" for n in D["names"]]] > 0).sum(axis=1)
    tr["month"] = tr.opened.dt.tz_localize(None).dt.to_period("M").astype(str)
    return tr


def cluster_mean_ci(x: np.ndarray, cl: np.ndarray, B: int = 2000, seed: int = SEED, level: float = 0.95) -> tuple[float, float, float]:
    """Ortalamanın küme (ay) bootstrap güven aralığı: kümeler yerine koymayla yeniden örneklenir (aynı aydaki işlemler aynı piyasa koşuluna maruz; bağımsızlık varsayılmaz)."""
    x, cl = np.asarray(x, float), np.asarray(cl)
    if len(x) == 0:
        return (float("nan"),) * 3
    u, inv = np.unique(cl, return_inverse=True)
    s, n = np.bincount(inv, weights=x, minlength=len(u)), np.bincount(inv, minlength=len(u))
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(u), (B, len(u)))
    m = s[pick].sum(axis=1) / n[pick].sum(axis=1)
    a = (1 - level) / 2
    return float(x.mean()), float(np.quantile(m, a)), float(np.quantile(m, 1 - a))


def group_table(tr: pd.DataFrame, by, order=None, min_n: int = 30) -> list[dict]:
    g = tr.groupby(by, observed=True)
    rows = []
    for k, x in (g if order is None else ((o, g.get_group(o)) for o in order if o in g.groups)):
        mean, lo, hi = cluster_mean_ci(x.bps.to_numpy(), x.month.to_numpy())
        rows.append(dict(group=str(k) if not isinstance(k, tuple) else " / ".join(map(str, k)), n=int(len(x)), mean_bps=mean, ci_lo=lo, ci_hi=hi, median_bps=float(x.bps.median()), win=float((x.net > 0).mean()),
                         net_usd=float(x.net.sum()), usd_per_trade=float(x.net.mean()), small=bool(len(x) < min_n)))
    return rows


def calibration(D: dict) -> dict:
    """Giriş koşuluna göre trade sonucu (1.4): |F| çeyreği, aynı yönde uzman sayısı, rejim x yön; notional'a göre bps + ay-küme bootstrap %95 AA; n < 30 işaretli. Haftanın günü tabloları KALDIRILDI (örneklem içi gürültü)."""
    tr = prep_trades(D)
    tr["q_absf"] = pd.qcut(tr.absf, 4, labels=["1 (en zayıf)", "2", "3", "4 (en güçlü)"])
    tr["reg_side"] = tr.regime.fillna("etiketsiz") + " / " + tr.side
    overall = cluster_mean_ci(tr.bps.to_numpy(), tr.month.to_numpy())
    return dict(overall=dict(mean_bps=overall[0], ci_lo=overall[1], ci_hi=overall[2], n=int(len(tr)), n_months=int(tr.month.nunique())), absf=group_table(tr, "q_absf"),
                aligned=group_table(tr, "n_aligned"), regime=group_table(tr, "reg_side"),
                note="CI: giriş ayına göre küme bootstrap (B=2000, tohum 0); trade'ler zaman içinde örtüşür ve sembol arası korelidir, bu yüzden CI iyimser olabilir. n < 30: yetersiz.")


def cluster_ratio_ci(num: np.ndarray, den: np.ndarray, cl: np.ndarray, B: int = 2000, seed: int = SEED, level: float = 0.95) -> tuple[float, float, float]:
    """Σnum / Σden oranının küme bootstrap güven aralığı (notional-ağırlıklı bps için)."""
    num, den, cl = np.asarray(num, float), np.asarray(den, float), np.asarray(cl)
    u, inv = np.unique(cl, return_inverse=True)
    sn, sd = np.bincount(inv, weights=num, minlength=len(u)), np.bincount(inv, weights=den, minlength=len(u))
    pick = np.random.default_rng(seed).integers(0, len(u), (B, len(u)))
    m = sn[pick].sum(axis=1) / sd[pick].sum(axis=1)
    a = (1 - level) / 2
    return float(num.sum() / den.sum()), float(np.quantile(m, a)), float(np.quantile(m, 1 - a))


def position_days(D: dict) -> pd.DataFrame:
    """Karar-günü birimi (ex-ante): her (sembol, karar günü t) için risk motorunun tuttuğu hedef notional N = |out_t|, giriş koşulları |F_t|, σ_t ve boyut N / equity_t karar anında bilinir;
    sonuç = o pozisyonun ertesi günkü net PnL'i (fiyat + funding − komisyon, saatlik yoldan). Pozisyon sürdükçe her gün ayrı birimdir. Trade düzeyindeki tanımlar (ortalama notional, tutma süresi) çıkışta bilinir."""
    P, H, syms = D["panels"], D["hourly"], D["syms"]
    out, Fp, sig = panel(P, "out")[syms], panel(P, "F")[syms], panel(P, "sigma")[syms]
    net_day = pd.DataFrame({s: H[f"{s}.net"].groupby(H.index.normalize()).sum() for s in syms})
    eq = (D["cap"] + D["daily"].net.cumsum())
    rows = []
    nxt = net_day.shift(-1)  # karar günü t -> ertesi günün net'i
    m_ = (out.abs() > 1e-9) & nxt.reindex(out.index).notna()
    st = out.where(m_).stack()
    df = pd.DataFrame(dict(N=st.abs()))
    df["net_next"] = nxt.reindex(out.index).stack().reindex(df.index)
    df["absf"] = Fp.abs().stack().reindex(df.index)
    df["vol"] = sig.stack().reindex(df.index)
    df["equity"] = eq.reindex(df.index.get_level_values(0)).to_numpy()
    df["size"] = df.N / df.equity
    df["month"] = df.index.get_level_values(0).tz_localize(None).to_period("M").astype(str)
    df["side"] = np.where(st.reindex(df.index) > 0, "long", "short")
    df = df.dropna(subset=["N", "net_next", "absf", "vol", "equity"])
    df["bps"] = df.net_next / df.N * 1e4
    return df


def _pd_group(df: pd.DataFrame, col: str) -> list[dict]:
    rows = []
    for k, x in df.groupby(col, observed=True):
        wb, lo, hi = cluster_ratio_ci(x.net_next.to_numpy(), x.N.to_numpy(), x.month.to_numpy())
        rows.append(dict(group=str(k), n=int(len(x)), wbps=wb * 1e4, ci_lo=lo * 1e4, ci_hi=hi * 1e4, net_usd=float(x.net_next.sum()), notional_share=float(x.N.sum() / df.N.sum()),
                         expected_usd_equal_bps=float(df.net_next.sum() / df.N.sum() * x.N.sum()), small=bool(len(x) < 30)))
    return rows


def size_vol_f(D: dict) -> dict:
    """2.2: boyut, |F| ve oynaklık üçlükleri, notional'a göre bps (notional-ağırlıklı = Σnet/ΣN; ay-küme bootstrap AA), karar-günü birimi (ex-ante). Boyut = F/σ olduğundan boyut etkisi oynaklıktan ayrılır:
    oynaklık üçlüğü İÇİNDE boyut üçlükleri (3x3). 'Mekanik pay': bps üçlükler arası eşit olsaydı beklenen USDT (genel bps x üçlüğün notional'ı) ile gerçek USDT."""
    df = position_days(D)
    df["t_vol"] = pd.qcut(df.vol, 3, labels=["1 (en düşük)", "2", "3 (en yüksek)"])
    df["t_f"] = pd.qcut(df.absf, 3, labels=["1 (en zayıf)", "2", "3 (en güçlü)"])
    df["t_size"] = pd.qcut(df["size"], 3, labels=["1 (en küçük)", "2", "3 (en büyük)"])
    out = dict(vol=_pd_group(df, "t_vol"), absf=_pd_group(df, "t_f"), size=_pd_group(df, "t_size"), n_units=int(len(df)), n_months=int(df.month.nunique()),
               overall_wbps=float(df.net_next.sum() / df.N.sum() * 1e4), overall_net=float(df.net_next.sum()))
    cells = []
    for v, gv in df.groupby("t_vol", observed=True):
        gv = gv.assign(t_size_in=pd.qcut(gv["size"], 3, labels=["1 (küçük)", "2", "3 (büyük)"]))
        for sz, x in gv.groupby("t_size_in", observed=True):
            wb, lo, hi = cluster_ratio_ci(x.net_next.to_numpy(), x.N.to_numpy(), x.month.to_numpy())
            cells.append(dict(vol=str(v), size=str(sz), n=int(len(x)), wbps=wb * 1e4, ci_lo=lo * 1e4, ci_hi=hi * 1e4, net_usd=float(x.net_next.sum()), small=bool(len(x) < 30)))
    out["vol_x_size"] = cells
    top = out["size"][-1]
    out["top_size_mechanical_fraction"] = float(top["expected_usd_equal_bps"] / top["net_usd"]) if top["net_usd"] else float("nan")
    out["corr_spearman"] = dict(size_vs_absf=float(df["size"].corr(df.absf, method="spearman")), size_vs_vol=float(df["size"].corr(df.vol, method="spearman")), absf_vs_vol=float(df.absf.corr(df.vol, method="spearman")))
    # eski (trade düzeyi, ortalama notional) tanım: karşılaştırma için
    tr = prep_trades(D)
    tr["size_avg"] = tr.avg_notional / tr.eq_at_open
    t_old = pd.qcut(tr.size_avg, 3, labels=["1", "2", "3"])
    out["old_trade_level_avgnotional"] = [dict(group=str(k), n=int(len(x)), net_usd=float(x.net.sum())) for k, x in tr.groupby(t_old, observed=True)]
    return out


def holding_buckets(D: dict) -> list[dict]:
    """2.3: tutma süresi kovaları ÇIKIŞTA BİLİNİR (hindsight): giriş anında bilinmez; bu yüzden kazanma oranı/net bu tablodan çıkarılıp trade seçimi yapılamaz."""
    tr = prep_trades(D)
    tr["bucket"] = pd.cut(tr.hours / 24, [0, 7, 30, 1e9], labels=["≤ 7 gün", "7-30 gün", "> 30 gün"], right=True)
    return group_table(tr, "bucket")


# ================================================================ F. oynaklık kalibrasyonu ayrıştırması (2.8)
def apply_buffer(tgt: np.ndarray, unit: np.ndarray, active: np.ndarray, buffer: float) -> np.ndarray:
    """`portfolio.size` tampon kuralının birebir kopyası: |hedef − önceki| > buffer x unit ise hedef olur, değilse önceki korunur; aktif olmayan sembol 0."""
    prev, out = np.zeros(tgt.shape[1]), np.zeros(tgt.shape)
    for d in range(len(tgt)):
        a = active[d] & ~np.isnan(tgt[d])
        t = np.where(a, np.nan_to_num(tgt[d]), 0.0)
        u = np.where(a, np.nan_to_num(unit[d]), np.inf)
        move = np.abs(t - prev) > np.where(np.isinf(u), np.inf, buffer * np.where(np.isinf(u), 0.0, u))
        prev = np.where(~a, 0.0, np.where(move, t, prev))
        out[d] = prev
    return out


def vol_decomp(D: dict, tau: float = 0.20, buffer: float = 0.20) -> dict:
    """Gerçekleşen oynaklık / hedef τ farkının dört bileşene Shapley ayrıştırması (log-oynaklık; fiyat-yalnız günlük PnL; 16 konfigürasyon):
    (1) yön karışımı = semboller arası çeşitlendirme (kapalı: hepsi long, açık: gerçek yönler), (2) |F| ölçeği (kapalı: |F| = 1), (3) tampon (kapalı: günlük hedefe tam uyum), (4) payda
    (kapalı: sabit başlangıç sermayesi, açık: önceki gün equity'si, yani equity_scale=False'ın sonucu). Taban (hepsi kapalı) = her aktif sembolde unit x 1 long: risk motorunun ham tam-tahmin kitabı.
    Kalan iki fark ayrı satır: taban/τ (σ ve ρ tahmin hatası, IDM) ve konfigürasyon-dışı (tavanlar, yuvarlama/sürüklenme, maliyet, funding)."""
    P, syms, cap = D["panels"], D["syms"], D["cap"]
    unit, F, act = panel(P, "unit")[syms], panel(P, "F")[syms], panel(P, "active")[syms]
    opn, cls = panel(P, "open")[syms], panel(P, "close")[syms]
    o1, o2 = opn.shift(-1), opn.shift(-2)
    o2.iloc[-2] = cls.iloc[-1]
    r = (o2 / o1 - 1).fillna(0.0)
    warm = (act.any(axis=1).cumsum() >= 30)
    on = (act.astype(bool) & warm.to_numpy()[:, None] & unit.notna()).to_numpy()
    U = unit.fillna(0.0).to_numpy()
    sgn, mag = np.sign(F.fillna(0.0).to_numpy()), np.abs(F.fillna(0.0).to_numpy())
    days = D["daily"].index
    eq_prev = (cap + D["daily"].net.cumsum()).shift(1).fillna(cap)
    r_np = r.to_numpy()

    def series(dir_, mag_, buf_, den_):
        tgt = U * (sgn if dir_ else 1.0) * (mag if mag_ else 1.0) * on
        pos = apply_buffer(np.where(on, tgt, np.nan), np.where(on, U, np.nan), on, buffer) if buf_ else tgt
        pnl = pd.Series((pos * r_np).sum(axis=1), index=P.index).shift(1).reindex(days).fillna(0.0)
        rr = pnl / (eq_prev if den_ else cap)
        return float(rr.std(ddof=1) * np.sqrt(365)), pos

    vol, full_pos = {}, None
    for k in itertools.product((0, 1), repeat=4):
        v, pos = series(*k)
        vol[k] = v
        if k == (1, 1, 1, 0):
            full_pos = pos
    # doğrulama: tüm-açık konfigürasyon (payda hariç) risk motorunun tampon sonrası hedefine eşit (tavanlar hiç bağlamıyor)
    out_ref = panel(P, "out")[syms].fillna(0.0).to_numpy()
    full_dev = float(np.abs(full_pos - out_ref).max())
    names = ["Yön karışımı (çeşitlendirme)", "|F| ölçeği", "Tampon", "Payda (equity)"]
    phi = np.zeros(4)
    for k in range(4):
        others = [j for j in range(4) if j != k]
        for m in range(4):
            for S in itertools.combinations(others, m):
                w = math.factorial(m) * math.factorial(3 - m) / math.factorial(4)
                a = [1 if j in S else 0 for j in range(4)]
                b = list(a)
                b[k] = 1
                phi[k] += w * (math.log(vol[tuple(b)]) - math.log(vol[tuple(a)]))
    sec_vol = am.vol_equity(D["daily"].net, cap)
    base = vol[(0, 0, 0, 0)]
    full_eq = vol[(1, 1, 1, 1)]
    comp_rows = [dict(component="Hedef τ", vol=tau, ratio=1.0, log=0.0),
                 dict(component="Taban: σ/ρ tahmin hatası + IDM (tam-tahmin, hepsi long)", vol=base, ratio=base / tau, log=math.log(base / tau))]
    for n, ph in zip(names, phi):
        comp_rows.append(dict(component=n, vol=None, ratio=math.exp(ph), log=float(ph)))
    comp_rows.append(dict(component="Konfigürasyon dışı: tavanlar, yuvarlama/sürüklenme, maliyet, funding", vol=sec_vol, ratio=sec_vol / full_eq, log=math.log(sec_vol / full_eq)))
    total_log = math.log(sec_vol / tau)
    for rw in comp_rows:
        rw["share_of_gap"] = rw["log"] / total_log if total_log else float("nan")
    return dict(tau=tau, vol_equity_actual=sec_vol, vol_fixed_actual=am.vol_fixed(D["daily"].net, cap), vol_base=base, vol_full_cfg_equity=full_eq, vol_full_cfg_fixed=vol[(1, 1, 1, 0)], total_log_gap=total_log, ratio_total=sec_vol / tau,
                rows=comp_rows, vols={"".join(map(str, k)): v for k, v in vol.items()}, check_full_vs_out_maxdiff=full_dev, avg_abs_F=float(np.nanmean(np.abs(F.where(on)))) if False else float(np.abs(F.where(pd.DataFrame(on, index=F.index, columns=F.columns))).stack().mean()),
                order_note="Shapley: faktörlerin tüm sıralamaları ortalanır (oynaklık toplamsal değil; sıra etkisi budur); satırlar log-oranlardır, çarpımları toplam oranı verir")


# ================================================================ G. funding'in yön x rejim dağılımı (2.6)
def funding_by_regime(D: dict) -> dict:
    """Funding PnL'i (saatlik yol; + = alınan) yöne ve FUNDING ANINDAKİ BTC rejimine göre (rejim etiketi nedensel: robust.regime). Önceki incelemede toplam short funding (+41,6) yanlışlıkla ayı rejimine
    atfedilmişti; burada saatlik pozisyon işaretiyle, o günün rejiminde ödenen/alınan funding ayrı toplanır. 'giriş rejimi' kolonu trade tablosundaki eski (giriş anı) atfın karşılaştırması."""
    H, P, syms = D["hourly"], D["panels"], D["syms"]
    reg = panel(P, "regime").iloc[:, 0].replace({1.0: "bull", 0.0: "range", -1.0: "bear"})
    rows = []
    day = H.index.normalize()
    lab = pd.Series(reg.reindex(day).to_numpy(), index=H.index).fillna("etiketsiz")
    for side, sg in (("long", 1), ("short", -1)):
        for rg in ("bull", "bear", "range", "etiketsiz"):
            tot, hours, notional = 0.0, 0, 0.0
            for s in syms:
                pos = H[f"{s}.pos"].ffill()
                m = ((np.sign(pos) == sg) & (lab == rg)).to_numpy()
                tot += float(H[f"{s}.funding"].fillna(0.0)[m].sum())
                hours += int(m.sum())
                notional += float((pos.abs() * H[f"{s}.close"].ffill())[m].sum())
            rows.append(dict(side=side, regime=rg, funding_usd=tot, position_hours=hours, avg_notional=notional / max(hours, 1), annualized_pct_of_notional=(tot / notional * 8760) if notional else float("nan")))
    tr = prep_trades(D)
    entry = tr.assign(regime=tr.regime.fillna("etiketsiz")).groupby(["side", "regime"]).funding.sum().reset_index().rename(columns={"funding": "funding_usd_entry_regime"})
    cur = pd.DataFrame(rows)
    out = cur.merge(entry, on=["side", "regime"], how="outer").fillna(0.0)
    tot = out.groupby("side")[["funding_usd", "funding_usd_entry_regime"]].sum()
    return dict(rows=out.to_dict("records"), totals=tot.reset_index().to_dict("records"), short_total=float(tot.loc["short", "funding_usd"]), long_total=float(tot.loc["long", "funding_usd"]),
                short_bear_share=float(out[(out.side == "short") & (out.regime == "bear")].funding_usd.sum() / tot.loc["short", "funding_usd"]) if tot.loc["short", "funding_usd"] else float("nan"),
                short_bull_share=float(out[(out.side == "short") & (out.regime == "bull")].funding_usd.sum() / tot.loc["short", "funding_usd"]) if tot.loc["short", "funding_usd"] else float("nan"),
                short_bear_usd=float(out[(out.side == "short") & (out.regime == "bear")].funding_usd.sum()))


# ================================================================ H. benchmark'lar, beta ve alfa (2.5)
def benchmarks(D: dict) -> dict:
    """Aynı evren/aynı hakem: (a) tek lookback'li TSMOM (365g, aylık), (b) eşit notional al-tut, (c) BTC al-tut (hakem koşuları: reports/trade_audit_data/fix/bench). Beta/alfa regresyonları günlük getiriyle
    (strateji PnL / 1000): BTC, eşit ağırlık-9 (günlük dengelemeli fiyat getirisi), alt sepeti (8 alt, BTC hariç), TSMOM benchmark'ı (PnL/1000, brüt notional 1000). Al-tut'un DOLAR PnL Sharpe'ı, miktar sabit kaldığı için
    (pozisyon 1 000 → ~34 000) anlamsızdır: getiri/equity bazlı Sharpe de verilir."""
    bench = json.loads((FIX / "bench" / "bench.json").read_text())["summary"]
    cap = D["cap"]
    pnl = D["daily"].net
    rs = pnl / cap
    px = pd.read_csv(FIX / "bench" / "daily_price_returns.csv", index_col=0, parse_dates=True).reindex(pnl.index)
    series = {"BTC (günlük fiyat getirisi)": px["BTCUSDT"], "Eşit ağırlık-9 (günlük dengelemeli)": px.mean(axis=1), "Alt sepeti-8, BTC hariç (eşit ağırlık)": px.drop(columns="BTCUSDT").mean(axis=1)}
    ts = pd.read_csv(FIX / "bench" / "daily_tsmom365.csv", index_col=0, parse_dates=True).net.reindex(pnl.index).fillna(0.0)
    series["TSMOM-365 (hakem, PnL/1000)"] = ts / cap
    reg = []
    for k, b in series.items():
        x = pd.concat([rs, b], axis=1, keys=["s", "b"]).dropna()
        a, bt, t = stats.nw_alpha(x.s.to_numpy(), x.b.to_numpy(), 5)
        reg.append(dict(benchmark=k, beta=bt, alpha_annual=a * 365, t_alpha=t, corr=float(x.s.corr(x.b)), r2=float(x.s.corr(x.b) ** 2), n=int(len(x))))
    runs = {}
    for k, label in (("tsmom365", "TSMOM-365 (aylık, sembol başına 111 USDT)"), ("ew_long", "Eşit notional long al-tut (9 x 111 USDT)"), ("btc_hold", "BTC al-tut (1 000 USDT)")):
        d = pd.read_csv(FIX / "bench" / f"daily_{k}.csv", index_col=0, parse_dates=True).net.reindex(pnl.index).fillna(0.0)
        runs[k] = dict(label=label, net=bench[k]["net_pnl"], gross=bench[k]["gross_pnl"], funding=bench[k]["funding"], fee_slip=bench[k]["fee"] + bench[k]["slippage"], n_fills=bench[k]["n_fills"],
                       sharpe_fixed=am.sharpe_fixed(d, cap), sharpe_equity=am.sharpe_equity(d, cap), vol_equity=am.vol_equity(d, cap), maxdd_equity=am.max_dd_equity(d, cap),
                       maxdd_fixed=am.max_dd_fixed(d, cap), maxdd_usd=float(am.max_dd_fixed(d, cap) * cap), final_equity=float(cap + d.sum()))
    runs["strategy"] = dict(label="ev1_plus_new", net=float(pnl.sum()), sharpe_fixed=am.sharpe_fixed(pnl, cap), sharpe_equity=am.sharpe_equity(pnl, cap), vol_equity=am.vol_equity(pnl, cap),
                            maxdd_equity=am.max_dd_equity(pnl, cap), maxdd_fixed=am.max_dd_fixed(pnl, cap), maxdd_usd=float(am.max_dd_fixed(pnl, cap) * cap))
    # fiyat-getirisi Sharpe'ları (maliyet ve funding hariç; gösterge): günlük dengelemeli benchmark
    ps = {k: float(b.mean() / b.std(ddof=1) * np.sqrt(365)) for k, b in series.items() if "TSMOM" not in k}
    return dict(regressions=reg, runs=runs, price_return_sharpe=ps, note="Regresyon: r_strateji = a + b r_benchmark + e; a yıllıklaştırılmış (x365); t Newey–West (gecikme 5). Benchmark'ın maliyet/funding'i regresyonda yok (fiyat getirisi).")


# ================================================================ I. MEXC kuralları, yuvarlama (0.3)
def mexc_rounding(D: dict) -> dict:
    cap0 = D["cap"]
    runs = json.loads((FIX / "mexc" / "mexc_runs.json").read_text())["runs"]
    rules = json.loads((FIX / "mexc_rules.json").read_text())
    by = {(int(r["cap"]), r["mode"]): r for r in runs}
    rows = []
    for c in sorted({k[0] for k in by}):
        u, m = by[(c, "unrounded")], by[(c, "mexc")]
        du = pd.read_csv(FIX / "mexc" / f"daily_{c}_unrounded.csv", index_col=0, parse_dates=True).net
        dm = pd.read_csv(FIX / "mexc" / f"daily_{c}_mexc.csv", index_col=0, parse_dates=True).net
        rp = pd.read_csv(FIX / "mexc" / f"replay_{c}_mexc.csv", parse_dates=["ts"])
        sent = rp[rp.sent]
        blocked = rp[~rp.sent]
        rel = ((sent.want - (sent.pos_before + sent.ideal)).abs() * sent.px / sent.tgt.abs()).replace([np.inf], np.nan)  # emir sonrası pozisyon notional'ı hedefe göre göreli sapma
        rows.append(dict(cap=c, net_unrounded=u["net_pnl"], net_mexc=m["net_pnl"], net_diff_pct=m["net_pnl"] / u["net_pnl"] - 1, sharpe_unrounded=u["sharpe_fixed"], sharpe_mexc=m["sharpe_fixed"], sharpe_diff=m["sharpe_fixed"] - u["sharpe_fixed"],
                         intents=int(len(rp)), sent=int(len(sent)), blocked=int(len(blocked)), blocked_share=float(len(blocked) / len(rp)), blocked_zero_pos=int(((blocked.pos_before == 0) & (blocked.tgt != 0)).sum()),
                         n_fills_unrounded=int(u["n_fills"]), n_fills_mexc=int(m["n_fills"]), median_rel_pos_err=float(rel.median()), mean_rel_pos_err=float(rel.mean()), share_err_gt_10pct=float((rel > 0.10).mean()),
                         pnl_corr=float(du.corr(dm)), tracking_rmse_usd=float(np.sqrt(((du - dm) ** 2).mean())), tracking_rmse_pct_of_cap=float(np.sqrt(((du - dm) ** 2).mean()) / c),
                         fee_slip_unrounded=u["fee"] + u["slippage"], fee_slip_mexc=m["fee"] + m["slippage"], funding_unrounded=u["funding"], funding_mexc=m["funding"], gross_unrounded=u["gross_pnl"], gross_mexc=m["gross_pnl"]))
    tab = pd.DataFrame(rows)
    ok = (tab.net_diff_pct.abs() <= 0.05) & (tab.sharpe_diff.abs() <= 0.10) & (tab.blocked_share <= 0.05)  # koşu ÖNCESİ yazılan ölçüt (fix_progress.md)
    conv = [bool(all(ok.iloc[i:])) for i in range(len(ok))]
    first = next((int(tab.cap.iloc[i]) for i, c_ in enumerate(conv) if c_), None)
    # sembol bazında gönderilemeyen niyet ($1000)
    rp1 = pd.read_csv(FIX / "mexc" / "replay_1000_mexc.csv", parse_dates=["ts"])
    per_sym = rp1.groupby("sym").agg(intents=("sent", "size"), blocked=("sent", lambda x: int((~x).sum())), median_tgt_usd=("tgt", lambda x: float(x.abs().median()))).reset_index()
    per_sym["blocked_share"] = per_sym.blocked / per_sym.intents
    per_sym["contract_usd_median"] = [float(rp1[rp1.sym == s].px.median()) for s in per_sym.sym]  # 1 sözleşmenin medyan USDT değeri
    rl = {s.replace("USDT", ""): dict(contractSize=v["contractSize"], priceUnit=v["priceUnit"], volUnit=v["volUnit"], minVol=v["minVol"], takerFeeRate=v.get("takerFeeRate"), makerFeeRate=v.get("makerFeeRate")) for s, v in rules["symbols"].items()}
    return dict(rows=tab.to_dict("records"), converged=dict(zip(tab.cap.astype(int).astype(str), conv)), min_capital=first, per_symbol_1000=per_sym.to_dict("records"), rules=rl,
                rules_source=dict(url=rules["source"], fetched_utc=rules["fetched_utc"], doc=rules["doc"], note=rules["note"]),
                criterion="net farkı ≤ %5 ve |Sharpe farkı| ≤ 0,10 ve gönderilemeyen emir niyeti ≤ %5; asgari sermaye = ızgarada bu ölçütü ve tüm büyük noktaların sağladığı en küçük sermaye (koşu öncesi yazıldı)")


# ================================================================ K. leave-one-out marjinal katkı (2.7)
def loo_table(D: dict) -> dict:
    """Uzman bileşimden çıkarılıp (ağırlıklar yeniden normalize edilmez; `combine` ortalama |F| = 0,5 ölçeklemesi kalanları orantılı büyütür) hakemle yeniden koşuldu (scripts/ensemble.py --stage daily --drop).
    Δ = çıkarılmış − tam: Δnet > 0 ⇒ uzmanın katkısı NET'te negatif; Δnet < 0 ⇒ pozitif. Sharpe sabit-sermaye. Katkı işareti net ve Sharpe için ayrı verilir (ayrışabilir)."""
    cap, full = D["cap"], D["daily"].net
    rows = []
    for n in D["names"]:
        f = SRC / "loo" / n / "daily.json"
        if not f.exists():
            continue
        j = json.loads(f.read_text())
        d = pd.Series(j["daily"])
        d.index = pd.to_datetime(d.index, utc=True)
        rows.append(dict(expert=n, net=float(j["summary"]["net_pnl"]), d_net=float(j["summary"]["net_pnl"] - D["meta"]["summary"]["net_pnl"]), sharpe=am.sharpe_fixed(d, cap),
                         d_sharpe=am.sharpe_fixed(d, cap) - am.sharpe_fixed(full, cap), maxdd=am.max_dd_fixed(d, cap), d_maxdd=am.max_dd_fixed(d, cap) - am.max_dd_fixed(full, cap)))
    t = pd.DataFrame(rows)
    return dict(rows=t.to_dict("records"), net_negative_contributors=[r["expert"] for r in rows if r["d_net"] > 0], net_positive_contributors=[r["expert"] for r in rows if r["d_net"] < 0],
                sharpe_negative_contributors=[r["expert"] for r in rows if r["d_sharpe"] > 0], sharpe_positive_contributors=[r["expert"] for r in rows if r["d_sharpe"] < 0],
                full=dict(net=float(full.sum()), sharpe=am.sharpe_fixed(full, cap), maxdd=am.max_dd_fixed(full, cap)))


# ================================================================ I. stop karşı-olgusalı: eski (gap'siz, yeniden girişsiz), gap'e duyarlı, yeniden girişli (2.4)
SIDE_BPS = 6.0  # yan başına maliyet: (fee 10 + slip 2) / 2 bps
STOP_RULES = tuple((tr_, k) for tr_ in (True, False) for k in (1.0, 1.5, 2.0, 3.0, 4.0, 6.0))


def _prepare_trade_paths(D: dict, tr: pd.DataFrame) -> list:
    H, syms = D["hourly"], D["syms"]
    A = {}
    for s in syms:
        x = H[[f"{s}.pos", f"{s}.open", f"{s}.close", f"{s}.high", f"{s}.low"]].ffill()
        A[s] = dict(idx=x.index, pos=x.iloc[:, 0].to_numpy(), open=x.iloc[:, 1].to_numpy(), close=x.iloc[:, 2].to_numpy(), high=x.iloc[:, 3].to_numpy(), low=x.iloc[:, 4].to_numpy())
    prepared = []
    for r in tr.itertuples():
        a = A[r.sym]
        ob, cb = a["idx"].searchsorted(r.opened.floor("1h")), a["idx"].searchsorted(r.closed.floor("1h"))
        h = np.arange(ob, max(cb, ob + 1))
        pos_in = np.r_[a["pos"][ob], a["pos"][h[1:] - 1]]  # bar boyunca tutulan (bar başı) pozisyon: eski rapordaki yöntemle aynı (açılıştaki dolum bir sonraki barın PnL'ine yansır)
        entry0 = a["close"][ob - 1] if ob > 0 else r.vwap_in
        prev = np.r_[entry0, a["close"][h[:-1]]]
        prepared.append((r, a, h, pos_in, prev, entry0))
    return prepared


def _simulate(item, out: pd.DataFrame, k: float, trailing: bool, gap_aware: bool, reentry: bool):
    """Tek trade: (taban fiyat PnL, karşı-olgusal fiyat PnL, taban devir USDT, karşı-olgusal devir USDT, stop sayısı, yeniden giriş sayısı). Devir = Σ |işlem miktarı| x dolum fiyatı."""
    r, a, h, pos_in, prev, entry0 = item
    base = float((pos_in * (a["close"][h] - prev)).sum())
    last_px = a["close"][h[-1]]
    dq0 = np.abs(np.diff(np.r_[0.0, pos_in]))
    orig_turn = float((dq0 * prev).sum() + abs(pos_in[-1]) * last_px)
    d = k * (r.sigma / np.sqrt(365)) if np.isfinite(r.sigma) else np.nan
    if not np.isfinite(d):
        return base, base, orig_turn, orig_turn, 0, 0
    sd = 1 if r.side == "long" else -1
    ref, active, pnl, turn, hits, reent = entry0, True, 0.0, 0.0, 0, 0
    n = 0
    while n < len(h):
        hh = h[n]
        if active:
            if n == 0:
                turn += abs(pos_in[0]) * prev[0]
            elif pos_in[n] != pos_in[n - 1]:
                turn += abs(pos_in[n] - pos_in[n - 1]) * prev[n]  # orijinal ekleme/azaltma
            stop = ref * (1 - d) if sd > 0 else ref * (1 + d)
            if (sd > 0 and a["low"][hh] <= stop) or (sd < 0 and a["high"][hh] >= stop):
                fill = stop
                if gap_aware and ((sd > 0 and a["open"][hh] <= stop) or (sd < 0 and a["open"][hh] >= stop)):
                    fill = a["open"][hh]
                pnl += pos_in[n] * (fill - prev[n])
                turn += abs(pos_in[n]) * fill
                hits, active = hits + 1, False
                if reentry:
                    day = a["idx"][hh].normalize()
                    m_idx = a["idx"].searchsorted(day + pd.Timedelta("1D"))
                    m = int(np.searchsorted(h, m_idx))
                    if m < len(h) and h[m] == m_idx and day in out.index and np.sign(out.at[day, r.sym]) == sd:
                        q_new = a["pos"][m_idx]  # yeniden girişte orijinal profilin o barın sonundaki (açılış dolumu sonrası) pozisyonu
                        pnl += q_new * (a["close"][m_idx] - a["open"][m_idx])
                        turn += abs(q_new) * a["open"][m_idx]
                        ref = max(a["open"][m_idx], a["high"][m_idx]) if (trailing and sd > 0) else (min(a["open"][m_idx], a["low"][m_idx]) if trailing else a["open"][m_idx])
                        active, reent, n = True, reent + 1, m + 1
                        continue
                break
            pnl += pos_in[n] * (a["close"][hh] - prev[n])
            if trailing:
                ref = max(ref, a["high"][hh]) if sd > 0 else min(ref, a["low"][hh])
        n += 1
    if active:
        turn += abs(pos_in[-1]) * last_px  # trade sonu çıkışı (orijinalle aynı)
    return base, pnl, orig_turn, turn, hits, reent


def stop_counterfactual(D: dict) -> dict:
    """Trade başına stop kuralı karşı-olgusalı (ölçüm; strateji değil; kural/parametre ARANMAZ: önceki raporun 12 kuralı aynen). Saatlik gerçek pozisyon profiliyle.
    (A) eski: stop SEVİYESİNDE dolum (gap yok), yeniden giriş yok; (B) gap'e duyarlı: bar stop seviyesinin ötesinde AÇILDIYSA dolum açılış fiyatından; (C) B + yeniden giriş: stop sonrası bir sonraki karar
    zamanında (gün sonu; ertesi gün 00:00 açılışı) sistemin o günkü hedef işareti trade yönüyle aynıysa pozisyonun gerçek profiline yeniden katılır, stop referansı sıfırlanır.
    Net değişim = fiyat PnL değişimi − (karşı-olgusal devir − taban devir) x 6 bps. Tümü görülmüş veride (post-hoc)."""
    tr = prep_trades(D)
    for i_, r_ in tr[tr.gross_bps.isna()].iterrows():
        tr.at[i_, "gross_bps"] = 0.0
    tr["sigma"] = tr.sigma
    prepared = _prepare_trade_paths(D, tr)
    out = panel(D["panels"], "out")[D["syms"]]
    # birim test: stop hiç tetiklenmezse karşı-olgusal = taban ve devir = taban devir
    chk = [_simulate(it, out, 1e9, True, True, True) for it in prepared[:200]]
    assert all(abs(c[0] - c[1]) < 1e-9 and abs(c[2] - c[3]) < 1e-9 for c in chk), "stop simülasyonu k→∞ iken tabanı vermiyor"
    base_total = float(sum(it[3].dot(it[1]["close"][it[2]] - it[4]) for it in prepared))
    rows = []
    for trailing, k in STOP_RULES:
        rec = dict(rule="İzleyen stop" if trailing else "Sabit stop (girişten)", k=k)
        for tag, kw in (("A", dict(gap_aware=False, reentry=False)), ("B", dict(gap_aware=True, reentry=False)), ("C", dict(gap_aware=True, reentry=True))):
            res = [_simulate(it, out, k, trailing, **kw) for it in prepared]
            b, c, bt, ct, hit, re_ = (np.array([x[i] for x in res], float) for i in range(6))
            dl = c - b
            rec.update({f"{tag}_dprice": float(dl.sum()), f"{tag}_dnet": float(dl.sum() - SIDE_BPS * 1e-4 * (ct.sum() - bt.sum())), f"{tag}_hit_share": float((hit > 0).mean()), f"{tag}_n_reentries": int(re_.sum()),
                        f"{tag}_helped": int((dl > 1e-9).sum()), f"{tag}_hurt": int((dl < -1e-9).sum()), f"{tag}_cost": float(SIDE_BPS * 1e-4 * (ct.sum() - bt.sum()))})
        rows.append(rec)
    return dict(rows=rows, base_price_pnl=base_total, n_trades=len(prepared),
                note="Taban = saatlik profilden yeniden kurulan fiyat PnL'i (hakemin 838,1'ine yakın; fark eski rapordaki gibi 1 bar gecikmeli profil yaklaşıklığı). A = önceki rapordaki yöntem.")


# ================================================================ L. hayatta kalma yanlılığı (2.9) ve öncesi/sonrası
def survivorship() -> dict | None:
    out = {}
    for tag in ("top9", "top20"):
        f = FIX / "surv" / f"surv_{tag}.json"
        if not f.exists():
            continue
        j = json.loads(f.read_text())
        d = pd.read_csv(FIX / "surv" / f"daily_{tag}.csv", index_col=0, parse_dates=True).net
        out[tag] = dict(top_n=j["top_n"], n_symbols=j["n_symbols_loaded"], net=j["summary"]["net_pnl"], gross=j["summary"]["gross_pnl"], funding=j["summary"]["funding"], n_fills=j["summary"]["n_fills"],
                        n_rejected=j["summary"]["n_rejected"], n_liq=j["summary"]["n_liq"], sharpe=am.sharpe_fixed(d, 1000.0), maxdd=am.max_dd_fixed(d, 1000.0), periods=am.period_table(d, 1000.0).to_dict("records"),
                        per_symbol_top=sorted(j["per_symbol_net"].items(), key=lambda kv: kv[1])[:5] + sorted(j["per_symbol_net"].items(), key=lambda kv: kv[1])[-5:],
                        delisted={s: j["per_symbol_net"].get(s) for s in j["delisted_in_universe"]}, n_active_by_year=j["n_active_by_year"])
    return out or None


def cf_runs(D: dict) -> list[dict]:
    """Post-hoc karşı-olgusallar (hakem, $1 000): tam bileşim, long-only, short x0,5. Betimsel; seçim değil."""
    cap = D["cap"]
    j = json.loads((FIX / "cf" / "cf.json").read_text())["summary"]
    rows = [dict(label="Tam bileşim (ana koşu)", net=float(D["daily"].net.sum()), sharpe=am.sharpe_fixed(D["daily"].net, cap), maxdd=am.max_dd_fixed(D["daily"].net, cap), n_fills=float(D["meta"]["summary"]["n_fills"]), funding=float(D["meta"]["summary"]["funding"]))]
    for k, lab in (("long_only", "Long-only (short hedefleri 0)"), ("short_x0.5", "Short x 0,5")):
        d = pd.read_csv(FIX / "cf" / f"daily_{k}.csv", index_col=0, parse_dates=True).net
        rows.append(dict(label=lab + " [post-hoc]", net=float(j[k]["net_pnl"]), sharpe=am.sharpe_fixed(d, cap), maxdd=am.max_dd_fixed(d, cap), n_fills=float(j[k]["n_fills"]), funding=float(j[k]["funding"])))
    return rows


def universe_stats() -> dict | None:
    f = FIX / "universe" / "universe_stats.json"
    return json.loads(f.read_text()) if f.exists() else None


def before_after(D: dict) -> dict:
    """Önceki raporun başlık değerleri (git geçmişindeki ilk tabanlı çıktılar: fix/before/*) ile yeni tanımlar. Önceki: equity'ye normalize Sharpe/oynaklık/DD."""
    old_d = pd.read_csv(FIX / "before" / "daily.csv", index_col=0, parse_dates=True)
    old_m = json.loads((FIX / "before" / "meta.json").read_text())
    cap = D["cap"]
    eq_old = old_d.equity
    under = eq_old < eq_old.cummax()
    runs = (under != under.shift()).cumsum()
    return dict(old=dict(net=float(old_d.net.sum()), sharpe_equity=am.sharpe_equity(old_d.net, cap), vol_equity=am.vol_equity(old_d.net, cap), maxdd_equity=am.max_dd_equity(old_d.net, cap),
                         recon=float(old_m["recon_hourly_vs_referee"]), underwater_days_old_def=int(under.groupby(runs).sum().max())),
                new=dict(net=float(D["daily"].net.sum()), recon=float(D["meta"]["recon_hourly_vs_referee"])))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    D = load()
    res = dict(headline=headline(D), dsr=dsr_table(D), dsr_nmax=dsr_nmax(D), null=null_table(D), attribution=attribution(D), calibration=calibration(D), size_vol_f=size_vol_f(D), holding=holding_buckets(D),
               vol_decomp=vol_decomp(D), funding=funding_by_regime(D), benchmarks=benchmarks(D), mexc=mexc_rounding(D), loo=loo_table(D), stop_cf=stop_counterfactual(D), survivorship=survivorship(), cf_runs=cf_runs(D), universe=universe_stats(),
               before_after=before_after(D), causal=json.loads((FIX / "causal" / "causal.json").read_text()), recon=D["meta"]["recon"], rounding_note=None)

    def conv(o):
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        if isinstance(o, (pd.Timestamp,)):
            return str(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        raise TypeError(type(o))

    (OUT / "analysis.json").write_text(json.dumps(res, indent=1, default=conv, allow_nan=True))
    print("analysis.json yazıldı:", OUT / "analysis.json")


if __name__ == "__main__":
    main()
