"""G2 sinyalleri: kurallar ve parametreler reports/book_signals.md'de veriye bakmadan sabitlendi (sonuca göre ayarlanmaz).
Sözleşme: signal(kl) -> birim pozisyon serisi (+1/-1/0), kl ile aynı indeks; karar günlük mumun kapanışında (saat-23 barı), diğer barlar NaN (tut)."""
import numpy as np
import pandas as pd


def _daily(kl: pd.DataFrame) -> pd.DataFrame:
    return kl.resample("1D").agg(dict(open="first", high="max", low="min", close="last"))


def _put(kl: pd.DataFrame, s: pd.Series, monthly: bool = False) -> pd.Series:
    """Günlük seriyi (indeks = gün) saatlik hedefe koyar: yalnızca günün 23:00 barına (kapanış 00:00); aylıkta yalnızca ay sonu günü."""
    out, last = pd.Series(np.nan, index=kl.index), kl.index[kl.index.hour == 23]
    if monthly:
        last = last[last.normalize().is_month_end]
    out.loc[last] = s.reindex(last.normalize()).to_numpy()
    return out


def turtle(entry: int, exit_: int, trend: bool = False):
    """Donchian kırılımı (Faith, Way of the Turtle). trend=True: yalnız 25/350 gün EMA yönünde giriş (Donchian Trend)."""
    def sig(kl):
        d = _daily(kl)
        hi_e, lo_e = d.high.rolling(entry).max().shift(1), d.low.rolling(entry).min().shift(1)
        hi_x, lo_x = d.high.rolling(exit_).max().shift(1), d.low.rolling(exit_).min().shift(1)
        fast, slow = d.close.ewm(span=25, adjust=False).mean(), d.close.ewm(span=350, min_periods=350, adjust=False).mean()
        up, dn = (fast > slow) | (not trend), (fast < slow) | (not trend)
        pos, out = 0, []
        for c, he, le, hx, lx, u, v in zip(d.close, hi_e, lo_e, hi_x, lo_x, up, dn):  # NaN karşılaştırması False: ısınmada işlem yok
            if c > he and u:
                pos = 1
            elif c < le and v:
                pos = -1
            elif (pos > 0 and c < lx) or (pos < 0 and c > hx):
                pos = 0
            out.append(float(pos))
        return _put(kl, pd.Series(out, index=d.index))
    return sig


def tsmom(days: int = 365):
    """Mutlak momentum (Antonacci): 12 aylık getiri > 0 long, < 0 short; aylık."""
    return lambda kl: _put(kl, np.sign(_daily(kl).close.pct_change(days)), monthly=True)


def dual_mom(panel: pd.DataFrame, sym: str, days: int = 365):
    """Çift momentum: mutlak (getiri işareti) + göreli (evren medyanına göre); aylık. panel = evrenin günlük kapanışları (sütun = sembol)."""
    def sig(kl):
        r = panel.pct_change(days)
        med = r.median(axis=1)
        s = pd.Series(0.0, index=r.index).where(~r[sym].isna())
        s[(r[sym] > 0) & (r[sym] > med)], s[(r[sym] < 0) & (r[sym] < med)] = 1.0, -1.0
        return _put(kl, s, monthly=True)
    return sig


def with_funding(kl: pd.DataFrame, funding: pd.DataFrame) -> pd.DataFrame:
    """kl'e fund_hr ekler: bar kapanışında bilinen son funding oranı / aralık saati (saatlik oran). Nedensel: ts <= bar kapanışı."""
    f = (funding.last_funding_rate / funding.funding_interval_hours).sort_index()
    f.index = f.index.round("1min")
    f = f[~f.index.duplicated()]
    t = kl.index + pd.Timedelta("1h")
    return kl.assign(fund_hr=f.reindex(f.index.union(t)).ffill().reindex(t).to_numpy())


def carry_funding(days: int = 30):
    """Carry (forex carry'nin perp karşılığı): son 30 günün ortalama funding'i > 0 -> short (funding alır), < 0 -> long; aylık."""
    return lambda kl: _put(kl, -np.sign(kl.fund_hr.resample("1D").mean().rolling(days).mean()), monthly=True)
