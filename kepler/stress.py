"""Tarihsel stres araçları (BACKTEST.md §10): en büyük günlük düşüş günleri ve bir PnL/dolum yolunun belirli pencerede özeti (DD, stop, likidasyon, stop kayması, açık pozisyon)."""
import numpy as np
import pandas as pd


def drop_days(close: pd.DataFrame, k: int = 3, sep: int = 7, exclude: tuple = ()) -> list[tuple]:
    """close: günlük kapanışlar (sütun = sembol). Eşit ağırlıklı sepetin günlük basit getirisi; en negatif günler açgözlü seçilir: seçilenler birbirinden >= sep gün uzak ve
    exclude = ((lo, hi), ...) pencerelerinin [lo, hi) DIŞINDA. Dönüş [(gün, sepet getirisi)]."""
    r = close.pct_change(fill_method=None).mean(axis=1).dropna().sort_values()
    out = []
    for day, v in r.items():
        if any(pd.Timestamp(lo, tz="UTC") <= day < pd.Timestamp(hi, tz="UTC") for lo, hi in exclude) or any(abs((day - d).days) < sep for d, _ in out):
            continue
        out.append((day, float(v)))
        if len(out) == k:
            break
    return out


def window_stats(pnl: pd.Series, fills: pd.DataFrame, lo, hi, capital: float, close: dict, stop: dict) -> dict:
    """pnl: saatlik net PnL (UTC indeks); fills: hakem dolumları (sym, ts ns, side, qty, px, liq, stop); close[sym]: saatlik kapanış; stop[sym]: saatlik stop seviyesi (t kapanışında
    bilinen, t+1 açılışından geçerli; bar b dolumunda yürürlükteki seviye = stop.shift(1)[b]). [lo, hi) pencere: net, pencere başından saatlik maks DD (tepe başlangıç dahil), en kötü
    saat/gün, stop ve likidasyon dolum sayısı, pencere başındaki brüt/net notional (son tamamlanmış saatin kapanışıyla), stop dolumunun seviyeye göre aleyhte kayması (bps)."""
    lo, hi = pd.Timestamp(lo, tz="UTC"), pd.Timestamp(hi, tz="UTC")
    w = pnl[(pnl.index >= lo) & (pnl.index < hi)]
    cum = w.cumsum()
    ts = pd.DatetimeIndex(pd.to_datetime(fills.ts, unit="ns", utc=True))
    signed = fills.qty.where(fills.side == "BUY", -fills.qty)
    pos = signed[ts < lo].groupby(fills.sym[ts < lo]).sum()
    last = {s: close[s][close[s].index < lo].iloc[-1] for s in pos.index}
    inw = fills[(ts >= lo) & (ts < hi)]
    slips = []
    for r in inw[inw.stop].itertuples():
        b = pd.Timestamp(r.ts, unit="ns", tz="UTC").floor("1h")
        lvl = stop[r.sym].shift(1).get(b, np.nan)
        if not np.isnan(lvl):
            slips.append((lvl - r.px) / lvl * 1e4 if r.side == "SELL" else (r.px - lvl) / lvl * 1e4)
    return dict(net=float(w.sum()), net_pct=float(w.sum() / capital), max_dd=float((np.maximum(cum.cummax(), 0) - cum).max()), max_dd_pct=float((np.maximum(cum.cummax(), 0) - cum).max() / capital),
                worst_hour=float(w.min()), worst_day=float(w.resample("1D").sum().min()), n_stop=int(inw.stop.sum()), n_liq=int(inw.liq.sum()),
                gross_start=float(sum(abs(q) * last[s] for s, q in pos.items())), net_start=float(sum(q * last[s] for s, q in pos.items())),
                stop_slip_bps_mean=float(np.mean(slips)) if slips else None, stop_slip_bps_max=float(np.max(slips)) if slips else None, n_stop_slip=len(slips))


def basket_return(close: dict, lo, hi) -> float:
    """Eşit ağırlıklı sepet fiyat getirisi: pencerenin ilk barının açılışına yakın son tamamlanmış kapanıştan [hi - 1h] barının kapanışına, sembol ortalaması (al-tut bağlamı)."""
    lo, hi = pd.Timestamp(lo, tz="UTC"), pd.Timestamp(hi, tz="UTC")
    return float(np.mean([c[c.index < hi].iloc[-1] / c[c.index < lo].iloc[-1] - 1 for c in close.values()]))
