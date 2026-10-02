"""Kapasite ve hacme bağlı slippage (BACKTEST.md §10): dolum başına katılım (dolum notional'ı / aynı saatin quote hacmi) ve hakem dışı karekök etki maliyeti bindirmesi.
Etki = Y × σ_h × √katılım × notional (σ_h: önceki `win` tamamlanmış saatlik log-getirinin RMS'i, nedensel); mevcut sabit slippage'a EK. Yol bağımlılığı (etkinin stop/likidasyon yolunu değiştirmesi) yok sayılır."""
import numpy as np
import pandas as pd


def fill_table(fills: pd.DataFrame, kl: dict, win: int = 24) -> pd.DataFrame:
    """Dolum başına (sym, bar, notional, part, sigma). kl[sym]: close ve quote_volume sütunlu saatlik. Hacmi 0 olan barda katılım 1 (tüm saat) sayılır."""
    ts = pd.DatetimeIndex(pd.to_datetime(fills.ts, unit="ns", utc=True)).floor("1h")
    rows = []
    for s, g in fills.assign(bar=ts).groupby("sym"):
        k = kl[s]
        sig = np.sqrt((np.log(k.close).diff() ** 2).rolling(win).mean().shift(1))
        v = k.quote_volume.reindex(g.bar).to_numpy()
        n = (g.qty * g.px).to_numpy()
        rows.append(pd.DataFrame(dict(sym=s, bar=g.bar.to_numpy(), notional=n, part=np.where(v > 0, n / np.where(v > 0, v, 1.0), 1.0), sigma=sig.reindex(g.bar).fillna(0.0).to_numpy())))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["sym", "bar", "notional", "part", "sigma"])


def impact_cost(tab: pd.DataFrame, y: float = 1.0) -> pd.Series:
    """Dolum başına karekök etki maliyeti (USDT): y × σ × √min(katılım, 1) × notional."""
    return y * tab.sigma * np.sqrt(tab.part.clip(upper=1.0)) * tab.notional


def hourly_cost(tab: pd.DataFrame, cost: pd.Series, index) -> pd.Series:
    return cost.groupby(pd.DatetimeIndex(tab.bar)).sum().reindex(index, fill_value=0.0)


def summary(tab: pd.DataFrame, thr: float = 0.001) -> dict:
    """Katılım dağılımı ve eşiği (varsayılan %0,1, BACKTEST §10) aşan dolum sayısı/payı."""
    p = tab.part
    return dict(n=len(p), n_over=int((p > thr).sum()), share_over=float((p > thr).mean()) if len(p) else 0.0, p50=float(p.quantile(0.5)), p95=float(p.quantile(0.95)),
                p99=float(p.quantile(0.99)), max=float(p.max()), n_zero_volume=int(((p == 1.0) & (tab.notional > 0)).sum()))
