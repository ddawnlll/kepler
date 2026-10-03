"""TradingView "Teknik Analiz" sayfasının (BTCUSDT/technicals) tüm göstergeleri: 11 osilatör, 15 hareketli ortalama, 5 pivot türü. Tanımlar TradingView/Pine Script
yerleşikleridir (ta.rma/ta.ema tohumu ilk n değerin SMA'sı, Wilder düzleştirme, ta.dmi, ta.cci...). Saf ve nedensel: satır i yalnızca satır <= i'ye bakar (testte: gelecek
bozulunca/kesilince değişmez); tek istisna pivotlar: satır i bir önceki dönemin (i-1) HLC'sinden (Woodie: i. dönemin açılışından da) türer, i döneminde kullanılır.
Girdi: open/high/low/close/volume sütunlu DataFrame (herhangi bir zaman diliminin tamamlanmış barları); `on_tf` saatlik tape'i tf barlarına toplayıp karar anına nedensel hizalar.
Sıfıra bölme: Pine gibi NaN (RSI hariç: kayıp 0 ise 100; ADX paydası 0 ise 1). Nüanslar (HMA'da n/2 tabana yuvarlanır) TradingView ile birebir sayı karşılaştırması yapılamadı: doğrulanmadı."""
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as _win

from kepler.state import TF_HOURS, bars, ns

PERIODS = (10, 20, 30, 50, 100, 200)
PIVOTS = ("classic", "fibonacci", "camarilla", "woodie", "dm")


# --- ilkeller ---------------------------------------------------------------
def sma(x: pd.Series, n: int) -> pd.Series:
    return x.rolling(n, min_periods=n).mean()


def _seeded(x: pd.Series, alpha: float, n: int) -> pd.Series:
    """Pine ta.ema / ta.rma: ilk geçerli n değerin SMA'sı tohum (n-1. geçerli noktada), sonra y = y_önceki + alpha (x - y_önceki); tohumdan önce NaN. Girdide yalnızca baştaki NaN olur."""
    v = x.to_numpy(float)
    ok = np.flatnonzero(~np.isnan(v))
    out = np.full(len(v), np.nan)
    if len(ok) == 0 or ok[0] + n > len(v):
        return pd.Series(out, index=x.index)
    s = ok[0] + n - 1
    seed = np.full(len(v), np.nan)
    seed[s] = v[ok[0]:s + 1].mean()
    seed[s + 1:] = v[s + 1:]
    out = pd.Series(seed).ewm(alpha=alpha, adjust=False).mean().to_numpy().copy()  # pandas 3: salt okunur
    out[:s] = np.nan
    return pd.Series(out, index=x.index)


def ema(x: pd.Series, n: int) -> pd.Series:
    return _seeded(x, 2.0 / (n + 1), n)


def rma(x: pd.Series, n: int) -> pd.Series:
    return _seeded(x, 1.0 / n, n)


def wma(x: pd.Series, n: int) -> pd.Series:
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        w = np.arange(1, n + 1, dtype=float)
        out[n - 1:] = _win(x.to_numpy(float), n) @ w / w.sum()
    return pd.Series(out, index=x.index)


def _stoch(src: pd.Series, hi: pd.Series, lo: pd.Series, n: int) -> pd.Series:
    """Pine ta.stoch: 100 (src - min(lo, n)) / (max(hi, n) - min(lo, n)); aralık 0 ise NaN."""
    ll, hh = lo.rolling(n, min_periods=n).min(), hi.rolling(n, min_periods=n).max()
    return 100 * (src - ll) / (hh - ll).where(hh - ll != 0)


def _tr(d: pd.DataFrame) -> pd.Series:
    """Gerçek aralık; ilk bar NaN (Pine ta.tr(false))."""
    pc = d.close.shift(1)
    return pd.concat([d.high - d.low, (d.high - pc).abs(), (d.low - pc).abs()], axis=1).max(axis=1, skipna=False)


# --- osilatörler ------------------------------------------------------------
def rsi(d: pd.DataFrame, n: int = 14) -> pd.Series:
    ch = d.close.diff()
    up, dn = rma(ch.clip(lower=0), n), rma((-ch).clip(lower=0), n)
    r = 100 - 100 / (1 + up / dn)
    r = r.where(dn != 0, 100.0)  # Pine: kayıp 0 -> 100 (kazanç da 0 ise 100)
    return r.where(up.notna() & dn.notna())


def stoch(d: pd.DataFrame, n: int = 14, k: int = 3, dd: int = 3) -> pd.DataFrame:
    """Stochastic %K (n, k, dd): K = SMA(ham %K, k); D = SMA(K, dd). Sayfadaki değer K."""
    kk = sma(_stoch(d.close, d.high, d.low, n), k)
    return pd.DataFrame(dict(k=kk, d=sma(kk, dd)))


def cci(d: pd.DataFrame, n: int = 20) -> pd.Series:
    """(tp - SMA(tp)) / (0,015 x ortalama mutlak sapma); tp = (H+L+C)/3; sapma 0 ise NaN."""
    tp = ((d.high + d.low + d.close) / 3).to_numpy(float)
    out = np.full(len(tp), np.nan)
    if len(tp) >= n:
        w = _win(tp, n)
        m = w.mean(axis=1)
        dev = np.abs(w - m[:, None]).mean(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            out[n - 1:] = np.where(dev != 0, (tp[n - 1:] - m) / (0.015 * dev), np.nan)
    return pd.Series(out, index=d.index)


def adx(d: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    """Pine ta.dmi(n, n): +DI, -DI, ADX (hepsi Wilder/RMA)."""
    up, dn = d.high.diff(), -d.low.diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=d.index).where(up.notna())
    mdm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=d.index).where(up.notna())
    tr = rma(_tr(d), n)
    plus, minus = 100 * rma(pdm, n) / tr, 100 * rma(mdm, n) / tr
    s = plus + minus
    dx = (plus - minus).abs() / s.where(s != 0, 1.0)
    return pd.DataFrame(dict(adx=100 * rma(dx, n), plus_di=plus, minus_di=minus))


def ao(d: pd.DataFrame, fast: int = 5, slow: int = 34) -> pd.Series:
    m = (d.high + d.low) / 2
    return sma(m, fast) - sma(m, slow)


def mom(d: pd.DataFrame, n: int = 10) -> pd.Series:
    return d.close.diff(n)


def macd(d: pd.DataFrame, fast: int = 12, slow: int = 26, sig: int = 9) -> pd.DataFrame:
    m = ema(d.close, fast) - ema(d.close, slow)
    s = ema(m, sig)
    return pd.DataFrame(dict(macd=m, signal=s, hist=m - s))


def stoch_rsi(d: pd.DataFrame, k: int = 3, dd: int = 3, rsi_n: int = 14, st_n: int = 14) -> pd.DataFrame:
    """Stochastic RSI (k, dd, rsi_n, st_n): K = SMA(stoch(RSI), k); D = SMA(K, dd). Sayfadaki "Fast" değer K."""
    r = rsi(d, rsi_n)
    kk = sma(_stoch(r, r, r, st_n), k)
    return pd.DataFrame(dict(k=kk, d=sma(kk, dd)))


def williams_r(d: pd.DataFrame, n: int = 14) -> pd.Series:
    hh, ll = d.high.rolling(n, min_periods=n).max(), d.low.rolling(n, min_periods=n).min()
    return -100 * (hh - d.close) / (hh - ll).where(hh - ll != 0)


def bbp(d: pd.DataFrame, n: int = 13) -> pd.DataFrame:
    """Elder Bull Bear Power: bull = H - EMA(C, n); bear = L - EMA(C, n); bbp = bull + bear."""
    e = ema(d.close, n)
    return pd.DataFrame(dict(bull=d.high - e, bear=d.low - e, bbp=d.high + d.low - 2 * e))


def uo(d: pd.DataFrame, a: int = 7, b: int = 14, c: int = 28) -> pd.Series:
    pc = d.close.shift(1)
    lo, hi = pd.concat([d.low, pc], axis=1).min(axis=1, skipna=False), pd.concat([d.high, pc], axis=1).max(axis=1, skipna=False)
    bp, tr = d.close - lo, hi - lo
    avg = lambda n: bp.rolling(n, min_periods=n).sum() / tr.rolling(n, min_periods=n).sum()  # noqa: E731
    return 100 * (4 * avg(a) + 2 * avg(b) + avg(c)) / 7


# --- hareketli ortalamalar --------------------------------------------------
def ichimoku(d: pd.DataFrame, conv: int = 9, base: int = 26, span_b: int = 52, disp: int = 26) -> pd.DataFrame:
    """tenkan (conv), kijun = Ichimoku Base Line (base), span_a / span_b bulutu `disp` bar ileri çizilir: t anındaki değer t-disp hesabıdır (nedensel). Geri çizilen chikou yok (gelecekten gelir)."""
    mid = lambda n: (d.high.rolling(n, min_periods=n).max() + d.low.rolling(n, min_periods=n).min()) / 2  # noqa: E731
    t, k = mid(conv), mid(base)
    return pd.DataFrame(dict(tenkan=t, kijun=k, span_a=((t + k) / 2).shift(disp), span_b=mid(span_b).shift(disp)))


def vwma(d: pd.DataFrame, n: int = 20) -> pd.Series:
    return (d.close * d.volume).rolling(n, min_periods=n).sum() / d.volume.rolling(n, min_periods=n).sum().where(lambda s: s != 0)


def hma(d: pd.DataFrame, n: int = 9) -> pd.Series:
    """wma(2 wma(C, ⌊n/2⌋) - wma(C, n), round(√n))."""
    return wma(2 * wma(d.close, n // 2) - wma(d.close, n), int(round(np.sqrt(n))))


# --- pivotlar ---------------------------------------------------------------
def pivots(d: pd.DataFrame, kind: str = "classic") -> pd.DataFrame:
    """Pivot seviyeleri; d pivot zaman diliminin (gün/hafta/ay) tamamlanmış barları. Satır i: bir önceki bar (i-1) H/L/C (+DM: O; Woodie: i. barın açılışı) ile hesaplanır ve i. barda geçerlidir.
    Sütunlar P, S1..S3, R1..R3 (camarilla ayrıca S4/R4; dm yalnızca P, S1, R1; diğerleri NaN)."""
    H, L, C, O = d.high.shift(1), d.low.shift(1), d.close.shift(1), d.open.shift(1)
    rg, nan = H - L, pd.Series(np.nan, index=d.index)
    cols = dict.fromkeys(["P", "S1", "S2", "S3", "S4", "R1", "R2", "R3", "R4"], nan)
    if kind == "classic":  # TradingView (BTCUSDT teknik analiz, doğrulandı): R3/S3 = P ± 2 (H - L)
        P = (H + L + C) / 3
        cols.update(P=P, R1=2 * P - L, S1=2 * P - H, R2=P + rg, S2=P - rg, R3=P + 2 * rg, S3=P - 2 * rg)
    elif kind == "woodie":  # R3/S3 = H + 2 (P - L) / L - 2 (H - P) (TradingView ile doğrulandı)
        P = (H + L + 2 * d.open) / 4
        cols.update(P=P, R1=2 * P - L, S1=2 * P - H, R2=P + rg, S2=P - rg, R3=H + 2 * (P - L), S3=L - 2 * (H - P))
    elif kind == "fibonacci":
        P = (H + L + C) / 3
        cols.update(P=P, R1=P + 0.382 * rg, S1=P - 0.382 * rg, R2=P + 0.618 * rg, S2=P - 0.618 * rg, R3=P + rg, S3=P - rg)
    elif kind == "camarilla":
        cols.update(P=(H + L + C) / 3, **{f"R{i}": C + 1.1 * rg / f for i, f in ((1, 12), (2, 6), (3, 4), (4, 2))}, **{f"S{i}": C - 1.1 * rg / f for i, f in ((1, 12), (2, 6), (3, 4), (4, 2))})
    elif kind == "dm":
        X = pd.Series(np.where(C < O, H + 2 * L + C, np.where(C > O, 2 * H + L + C, H + L + 2 * C)), index=d.index).where(H.notna() & O.notna())
        cols.update(P=X / 4, R1=X / 2 - L, S1=X / 2 - H)
    else:
        raise ValueError(f"bilinmeyen pivot türü: {kind}")
    return pd.DataFrame(cols)[["P", "S1", "S2", "S3", "S4", "R1", "R2", "R3", "R4"]]


# --- sayfa: tüm değerler ve zaman dilimi hizalama ---------------------------
def technicals(d: pd.DataFrame) -> pd.DataFrame:
    """TradingView teknik analiz sayfasındaki 26 sayısal satır (her bar için): 11 osilatör + 12 SMA/EMA + Ichimoku taban + VWMA + HMA. Pivotlar `pivots` ile."""
    c = d.close
    out = {"RSI14": rsi(d), "StochK_14_3_3": stoch(d).k, "CCI20": cci(d), "ADX14": adx(d).adx, "AO": ao(d), "Mom10": mom(d), "MACD_12_26": macd(d).macd,
           "StochRSI_K_3_3_14_14": stoch_rsi(d).k, "WilliamsR14": williams_r(d), "BBP": bbp(d).bbp, "UO_7_14_28": uo(d)}
    for n in PERIODS:
        out[f"EMA{n}"], out[f"SMA{n}"] = ema(c, n), sma(c, n)
    out.update(IchimokuBase=ichimoku(d).kijun, VWMA20=vwma(d), HMA9=hma(d))
    return pd.DataFrame(out)


def on_tf(kl: pd.DataFrame, tf: str, fn) -> pd.DataFrame:
    """Saatlik tape -> `fn(tf barları)` -> saatlik indekse nedensel hizalama. Yalnızca TAMAMLANMIŞ tf barları kullanılır (son bar tamamlanmadıysa girmez); saatlik bar h'nin karar anı h+1s'de
    kapanışı <= karar anı olan son tf barının değeri geçerlidir (state.py ile aynı kural). Eksik saatli takvim barı NaN satırı olur (göstergelere NaN yayılır)."""
    b = bars(kl[["open", "high", "low", "close", "volume"]].astype(float), tf)
    end = kl.index[-1] + pd.Timedelta("1h")
    b = b[b.index + pd.Timedelta(hours=TF_HOURS[tf]) <= end]
    v = fn(b[["open", "high", "low", "close", "volume"]])
    v = v.to_frame() if isinstance(v, pd.Series) else v
    closes = ns(b.index + pd.Timedelta(hours=TF_HOURS[tf]))
    j = np.searchsorted(closes, ns(kl.index + pd.Timedelta("1h")), side="right") - 1
    vals = v.to_numpy(float)
    out = np.where((j >= 0)[:, None], vals[np.maximum(j, 0)], np.nan)
    return pd.DataFrame(out, index=kl.index, columns=v.columns)


TV_PIVOT_TF = {"1h": "1w", "4h": "1w", "1d": "1M"}  # TradingView: grafik zaman dilimine göre pivotun türediği önceki dönem (1h/4h grafikte haftalık, 1d grafikte aylık; 1w grafik doğrulanmadı)


def _period_start(index: pd.DatetimeIndex, tf: str) -> pd.DatetimeIndex:
    """tf döneminin başlangıcı (UTC, tz'siz): 1w = pazartesi 00:00, 1M = ayın 1'i; diğerleri takvim çıpalı saat grupları."""
    t = index.tz_convert("UTC").tz_localize(None)
    if tf == "1M":
        return t.to_period("M").to_timestamp()
    if tf == "1w":
        return (t.normalize() - pd.to_timedelta(t.weekday, unit="D"))
    h = TF_HOURS[tf]
    return pd.DatetimeIndex(pd.Timestamp("1970-01-01") + ((t - pd.Timestamp("1970-01-01")) // pd.Timedelta(hours=h)) * pd.Timedelta(hours=h))


def on_tf_pivots(kl: pd.DataFrame, tf: str, kind: str) -> pd.DataFrame:
    """Pivot seviyeleri saatlik indekste: saat h, içinde bulunduğu tf döneminin (bir önceki dönemden türeyen) seviyelerini görür (dönem açılışında bilinir; Woodie dönem açılışını da kullanır).
    tf: 1h/4h/1d/3d (takvim çıpalı) veya 1w (pazartesi) / 1M (takvim ayı). TradingView eşlemesi için `TV_PIVOT_TF`."""
    kl = kl[["open", "high", "low", "close", "volume"]].astype(float)
    start = _period_start(kl.index, tf)
    g = kl.groupby(start)
    b = pd.DataFrame(dict(open=g.open.first(), high=g.high.max(), low=g.low.min(), close=g.close.last(), volume=g.volume.sum()))
    if tf == "1M":
        full = pd.date_range(b.index[0], b.index[-1], freq="MS")
    elif tf == "1w":
        full = pd.date_range(b.index[0], b.index[-1], freq="7D")
    else:
        full = pd.date_range(b.index[0], b.index[-1], freq=pd.Timedelta(hours=TF_HOURS[tf]))
    b = b.reindex(full)  # eksik dönem NaN satırı
    p = pivots(b, kind)
    return pd.DataFrame(p.reindex(start).to_numpy(float), index=kl.index, columns=p.columns)
