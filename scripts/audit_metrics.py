"""Trade denetimi ölçü fonksiyonları (saf, hakemsiz; rapor ve testler ortak kullanır). TEK tanım yeri: aynı ölçü raporda iki farklı yoldan hesaplanmaz.

Tanımlar (BACKTEST §9, K4):
- BİRİNCİL: sabit sermaye bazlı. Günlük getiri r = günlük net PnL / BAŞLANGIÇ sermayesi (bileşik yok). Sharpe = ort(r) / std(r, ddof=1) x √365. DD = toplamsal equity'nin (başlangıç 0 dahil) tepe − equity en büyüğü,
  başlangıç sermayesinin oranı (`stats.max_drawdown`). Önceki rapor equity'ye normalize edilmiş değerleri başlığa koyuyordu (kâr büyüdükçe payda büyür: Sharpe/oynaklık/DD göreli olarak güzelleşir).
- İKİNCİL: equity'ye normalize: r = PnL / önceki gün equity; DD = tepe equity'nin yüzdesi.
- Suda kalma: tepe tarihinden toparlanma tarihine (equity ≥ tepe ilk gün) ya da veri sonuna TAKVİM günü; tek tanım (`drawdown_table`), rapordaki her yerde bu.
"""
import numpy as np
import pandas as pd

from kepler import stats

PERIODS = {"2020–21": ("2020-04-01", "2021-12-31"), "2022–24": ("2022-01-01", "2024-12-31"), "2025+": ("2025-01-01", "2026-03-31")}


def sharpe_fixed(pnl: pd.Series, cap: float) -> float:
    r = (pnl / cap).to_numpy(float)
    return float(r.mean() / r.std(ddof=1) * np.sqrt(365)) if len(r) > 2 and r.std(ddof=1) > 0 else float("nan")


def sharpe_equity(pnl: pd.Series, cap: float) -> float:
    eq = cap + pnl.cumsum()
    r = (pnl / eq.shift(1).fillna(cap)).to_numpy(float)
    return float(r.mean() / r.std(ddof=1) * np.sqrt(365)) if len(r) > 2 and r.std(ddof=1) > 0 else float("nan")


def vol_fixed(pnl: pd.Series, cap: float) -> float:
    return float((pnl / cap).std(ddof=1) * np.sqrt(365))


def vol_equity(pnl: pd.Series, cap: float) -> float:
    eq = cap + pnl.cumsum()
    return float((pnl / eq.shift(1).fillna(cap)).std(ddof=1) * np.sqrt(365))


def max_dd_fixed(pnl: pd.Series, cap: float) -> float:
    """K4: toplamsal equity (sabit sermaye = 1), tepe başlangıç dahil; başlangıç sermayesinin oranı."""
    return float(stats.max_drawdown((pnl / cap).to_numpy(float)))


def max_dd_equity(pnl: pd.Series, cap: float) -> float:
    eq = cap + pnl.cumsum()
    pk = np.maximum(eq.cummax(), cap)
    return float(((pk - eq) / pk).max())


def drawdown_table(eq: pd.Series, cap: float, top: int = 10) -> pd.DataFrame:
    """Equity tepeden-diplere: tepe, dip, toparlanma (equity ≥ tepe ilk gün; yoksa NaT), derinlik (tepe equity'nin oranı), USDT, süre = takvim günü (tepe → toparlanma ya da veri sonu).
    Başlangıç sermayesi de bir tepe sayılır (eq'nin ilk gününden önceki değer)."""
    pk, start, trough, depth_usd, rows = cap, eq.index[0] - pd.Timedelta("1D"), eq.index[0], 0.0, []
    for t, v in eq.items():
        if v >= pk:
            if depth_usd > 0:
                rows.append(dict(peak=start, trough=trough, recovered=t, depth=depth_usd / pk, usd=depth_usd, days=(t - start).days))
            pk, start, trough, depth_usd = v, t, t, 0.0
        elif pk - v > depth_usd:
            depth_usd, trough = pk - v, t
    if depth_usd > 0:
        rows.append(dict(peak=start, trough=trough, recovered=pd.NaT, depth=depth_usd / pk, usd=depth_usd, days=(eq.index[-1] - start).days))
    return pd.DataFrame(rows).sort_values("depth", ascending=False).head(top).reset_index(drop=True)


def longest_underwater_days(eq: pd.Series, cap: float) -> int:
    t = drawdown_table(eq, cap, top=10_000)
    return int(t.days.max()) if len(t) else 0


def period_table(pnl: pd.Series, cap: float) -> pd.DataFrame:
    """Yıllar (takvim) ve alt dönemler (2020–21, 2022–24, 2025+): net, sabit-sermaye Sharpe, oynaklık, DD, gün sayısı. Sharpe kısa dönemde gürültülü (gün sayısı yanında)."""
    rows = []
    spans = [(str(y), (f"{y}-01-01", f"{y}-12-31")) for y in sorted(set(pnl.index.year))] + list(PERIODS.items())
    for name, (a, b) in spans:
        x = pnl[(pnl.index >= pd.Timestamp(a, tz="UTC")) & (pnl.index <= pd.Timestamp(b, tz="UTC") + pd.Timedelta("23h"))]
        if len(x) < 3:
            continue
        rows.append(dict(period=name, days=len(x), net=float(x.sum()), sharpe=sharpe_fixed(x, cap), vol=vol_fixed(x, cap), maxdd=max_dd_fixed(x, cap)))
    return pd.DataFrame(rows)


def bootstrap_sharpe_ci(pnl: pd.Series, cap: float, mean_block: float = 20.0, B: int = 2000, seed: int = 0) -> dict:
    """Durağan blok bootstrap (Politis–Romano, ortalama blok 20 gün; BACKTEST §9.3): yıllık Sharpe %5/%50/%95 ve %2,5/%97,5, DD ve toplam getiri dilimleri. Sabit sermaye."""
    r = (pnl / cap).to_numpy(float)
    x = r[stats.stationary_bootstrap(len(r), mean_block, B, seed)]
    sh = x.mean(axis=1) / x.std(axis=1, ddof=1) * np.sqrt(365)
    q = lambda v, ps: [float(np.quantile(v, p)) for p in ps]  # noqa: E731
    return dict(sharpe_q=dict(zip(("p2.5", "p5", "p50", "p95", "p97.5"), q(sh, (.025, .05, .5, .95, .975)))), p_sharpe_le_0=float((sh <= 0).mean()), maxdd_q=dict(zip(("p50", "p95"), q(stats.max_drawdown(x), (.5, .95)))),
                total_q=dict(zip(("p5", "p50", "p95"), q(x.sum(axis=1), (.05, .5, .95)))), mean_block=mean_block, B=B, seed=seed, n_days=len(r))
