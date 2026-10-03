"""kepler/indicators.py: TradingView teknik analiz sayfasındaki tüm osilatör, hareketli ortalama ve pivotlar.
Doğrulama dört katman: (1) elle hesaplı küçük örnekler ve literatürdeki bilinen cevap (Wilder RSI), (2) formüllerden bağımsız yazılmış saf-Python (döngü) oracle'lar, (3) nedensellik
(gelecek bozulunca/kesilince değişmez), (4) referans kütüphane (TA-Lib, ta) ile çapraz kontrol: kütüphane kurulu değilse atlanır (`uv run --with TA-Lib --with ta pytest tests/test_indicators.py`)."""
import math

import numpy as np
import pandas as pd
import pytest

from kepler import indicators as ind

NAN = float("nan")


def ohlcv(n=1500, seed=0, start="2022-01-01"):
    r = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(r.normal(0, 0.01, n)))
    o = np.r_[c[0], c[:-1]] * np.exp(r.normal(0, 0.002, n))
    h = np.maximum(o, c) * (1 + np.abs(r.normal(0, 0.004, n)))
    l = np.minimum(o, c) * (1 - np.abs(r.normal(0, 0.004, n)))
    v = r.uniform(10, 1000, n)
    return pd.DataFrame(dict(open=o, high=h, low=l, close=c, volume=v), index=pd.date_range(start, periods=n, freq="1h", tz="UTC"))


D = ohlcv()


def close_to(a, b, tol=1e-9):
    a, b = np.asarray(a, float), np.asarray(b, float)
    assert a.shape == b.shape
    assert np.array_equal(np.isnan(a), np.isnan(b)), f"NaN deseni farklı: {np.flatnonzero(np.isnan(a) != np.isnan(b))[:5]}"
    m = ~np.isnan(a)
    assert np.allclose(a[m], b[m], rtol=tol, atol=tol), np.abs(a[m] - b[m]).max()


# --- (1) elle hesaplı örnekler ---------------------------------------------
def test_sma_ema_wma_by_hand():
    x = pd.Series([1.0, 2, 3, 4, 5])
    close_to(ind.sma(x, 3), [NAN, NAN, 2, 3, 4])
    close_to(ind.ema(x, 3), [NAN, NAN, 2, 3, 4])  # tohum SMA(1,2,3)=2; alpha 0,5: 2+0,5(4-2)=3; 3+0,5(5-3)=4
    close_to(ind.rma(pd.Series([1.0, 2, 3, 6]), 3), [NAN, NAN, 2, (2 * 2 + 6) / 3])  # Wilder: (y(n-1) + x)/n
    close_to(ind.wma(x, 3), [NAN, NAN, (1 + 4 + 9) / 6, (2 + 6 + 12) / 6, (3 + 8 + 15) / 6])


def test_leading_nan_seed_starts_at_first_valid():
    x = pd.Series([NAN, NAN, 1.0, 2, 3, 4])
    close_to(ind.ema(x, 3), [NAN, NAN, NAN, NAN, 2, 3])


WILDER = [44.3389, 44.0902, 44.1497, 43.6124, 44.3278, 44.8264, 45.0955, 45.4245, 45.8433, 46.0826, 45.8931, 46.0328, 45.6140, 46.2820, 46.2820, 46.0028, 46.0328, 46.4116,
          46.2222, 45.6439, 46.2122, 46.2521, 45.7137, 46.4515, 45.7835, 45.3548, 44.0288, 44.1783, 44.2181, 44.5672, 43.4205, 42.6628, 43.1314]


def test_rsi_known_answer_wilder_spreadsheet():
    r = ind.rsi(pd.DataFrame(dict(close=WILDER)), 14)
    assert r.iloc[:14].isna().all()
    assert [round(v, 2) for v in r.iloc[14:19]] == [70.53, 66.32, 66.55, 69.41, 66.36]  # StockCharts/Wilder örnek tablosu


def test_rsi_edges():
    up = ind.rsi(pd.DataFrame(dict(close=np.arange(1.0, 30))), 14)
    assert (up.dropna() == 100).all() and len(up.dropna()) == 15  # hep yükseliş: kayıp 0 -> 100
    dn = ind.rsi(pd.DataFrame(dict(close=np.arange(30.0, 1, -1))), 14)
    assert np.allclose(dn.dropna(), 0)


def test_simple_oscillators_by_hand():
    d = pd.DataFrame(dict(open=[1.0] * 6, high=[10.0, 12, 11, 13, 15, 14], low=[8.0, 9, 9, 10, 12, 11], close=[9.0, 11, 10, 12, 14, 13], volume=[1.0, 2, 3, 4, 5, 6]))
    close_to(ind.mom(d, 2), [NAN, NAN, 1, 1, 4, 1])
    # Williams %R (3): son bar: hh = 15, ll = 10, C = 13 -> -100 (15-13)/(15-10) = -40
    assert ind.williams_r(d, 3).iloc[-1] == pytest.approx(-40.0)
    # ham %K (3) son bar: 100 (13-10)/(15-10) = 60; bir önceki: hh 15, ll 9 (H3=13? pencere 2..4: low 9,10,12 -> 9; high 11,13,15 -> 15; C=14) -> 100 (14-9)/(15-9)
    assert ind._stoch(d.close, d.high, d.low, 3).iloc[-2:].tolist() == pytest.approx([100 * 5 / 6, 60.0])
    # AO(2, 3) son bar: hl2 = 9, 10, 10, 11.5, 13.5, 12.5 -> SMA2 = 13, SMA3 = 12.5 + ... (11.5 + 13.5 + 12.5)/3 = 12.5 -> 0,5
    assert ind.ao(d, 2, 3).iloc[-1] == pytest.approx(13.0 - 12.5)
    # VWMA(3) son bar: (12*4 + 14*5 + 13*6) / 15
    assert ind.vwma(d, 3).iloc[-1] == pytest.approx((48 + 70 + 78) / 15)
    # Elder: bull = H - EMA, bear = L - EMA, toplam = H + L - 2 EMA
    b = ind.bbp(d, 3).iloc[-1]
    assert b.bbp == pytest.approx(b.bull + b.bear) and b.bull - b.bear == pytest.approx(14 - 11)
    # CCI(3) son bar: tp = (11,12.? ...) elle: tp = (H+L+C)/3
    tp = ((d.high + d.low + d.close) / 3).to_numpy()[-3:]
    assert ind.cci(d, 3).iloc[-1] == pytest.approx((tp[-1] - tp.mean()) / (0.015 * np.abs(tp - tp.mean()).mean()))


def test_hma_by_hand():
    x = pd.Series(np.arange(1.0, 13))  # doğrusal seri: HMA gecikmesiz, değer = kendisi (wma(9) ilk 8. bar, dış wma(3) 2 bar sonra = bar 10, 11)
    h = ind.hma(pd.DataFrame(dict(close=x)), 9)
    assert h.iloc[:10].isna().all()
    close_to(h.iloc[10:], x.iloc[10:])


def test_uo_by_hand():
    d = pd.DataFrame(dict(high=[10.0, 12, 11], low=[8.0, 9, 9], close=[9.0, 11, 10]))
    # (1, 1, 1) periyot: bp = C - min(L, PC), tr = max(H, PC) - min(L, PC); bar2: bp = 10 - 9 = 1, tr = 11 - 9 = 2 -> 100 (4+2+1)/7 x 0,5 = 50
    assert ind.uo(d, 1, 1, 1).iloc[-1] == pytest.approx(50.0)
    assert ind.uo(d, 1, 1, 1).iloc[0] != ind.uo(d, 1, 1, 1).iloc[0]  # ilk bar NaN (önceki kapanış yok)


def test_ichimoku_by_hand():
    d = pd.DataFrame(dict(high=[5.0, 7, 6, 9, 8], low=[1.0, 2, 0, 3, 4]))
    k = ind.ichimoku(d, conv=2, base=3, span_b=4, disp=1)
    # tenkan(2) son: (max(9,8) + min(3,4))/2 = 6; kijun(3) son: (max(6,9,8) + min(0,3,4))/2 = 4,5
    assert k.tenkan.iloc[-1] == pytest.approx(6.0) and k.kijun.iloc[-1] == pytest.approx(4.5)
    assert k.span_a.iloc[-1] == pytest.approx((k.tenkan.iloc[-2] + k.kijun.iloc[-2]) / 2)  # 1 bar ileri çizim: t'deki bulut t-1'den
    assert k.span_b.iloc[-1] == pytest.approx((max(5, 7, 6, 9) + min(1, 2, 0, 3)) / 2)  # span_b(4) bir bar önceki: bar 0..3


PV = pd.DataFrame(dict(open=[105.0, 108.0], high=[120.0, 125.0], low=[100.0, 104.0], close=[110.0, 118.0]))


def row(kind, d=PV):
    return ind.pivots(d, kind).iloc[1]


def test_pivots_by_hand_prev_bar_H120_L100_C110():
    c = row("classic")
    assert [c.P, c.S1, c.S2, c.S3, c.R1, c.R2, c.R3] == pytest.approx([110, 100, 90, 70, 120, 130, 150])  # TradingView Classic: R3/S3 = P ± 2 (H - L)
    f = row("fibonacci")
    assert [f.P, f.S1, f.S2, f.S3, f.R1, f.R2, f.R3] == pytest.approx([110, 110 - 7.64, 110 - 12.36, 90, 110 + 7.64, 110 + 12.36, 130])
    m = row("camarilla")
    assert [m.R1, m.R2, m.R3, m.R4] == pytest.approx([110 + 22 / 12, 110 + 22 / 6, 110 + 22 / 4, 110 + 22 / 2])
    assert [m.S1, m.S2, m.S3, m.S4] == pytest.approx([110 - 22 / 12, 110 - 22 / 6, 110 - 22 / 4, 110 - 22 / 2]) and m.P == pytest.approx(110)
    w = row("woodie")  # P = (H + L + 2 x bugünün açılışı 108) / 4 = 109
    assert [w.P, w.R1, w.S1, w.R2, w.S2, w.R3, w.S3] == pytest.approx([109, 118, 98, 129, 89, 138, 78])


def test_pivot_dm_three_cases():
    base = dict(high=[120.0, 0.0], low=[100.0, 0.0])
    up = row("dm", pd.DataFrame(dict(open=[105.0, 0], close=[110.0, 0], **base)))  # C > O: X = 2H + L + C = 450
    assert [up.P, up.R1, up.S1] == pytest.approx([112.5, 125, 105])
    dn = row("dm", pd.DataFrame(dict(open=[115.0, 0], close=[110.0, 0], **base)))  # C < O: X = H + 2L + C = 430
    assert [dn.P, dn.R1, dn.S1] == pytest.approx([107.5, 115, 95])
    eq = row("dm", pd.DataFrame(dict(open=[110.0, 0], close=[110.0, 0], **base)))  # C = O: X = H + L + 2C = 440
    assert [eq.P, eq.R1, eq.S1] == pytest.approx([110, 120, 100])
    assert np.isnan(up.S2) and np.isnan(up.R3)  # DM yalnızca P, S1, R1


def test_pivot_first_row_nan_and_unknown_kind():
    assert ind.pivots(PV, "classic").iloc[0].isna().all()
    with pytest.raises(ValueError):
        ind.pivots(PV, "zigzag")


# --- (2) bağımsız saf-Python oracle'lar -------------------------------------
def o_sma(x, n):
    return [NAN if i < n - 1 or any(map(math.isnan, x[i - n + 1:i + 1])) else sum(x[i - n + 1:i + 1]) / n for i in range(len(x))]


def o_rma(x, n, alpha_form=False):
    """Wilder: tohum = ilk n geçerli değerin ortalaması, sonra (y (n-1) + x) / n (alpha_form: ema, y + a (x - y))."""
    out = [NAN] * len(x)
    f = next((i for i, v in enumerate(x) if not math.isnan(v)), None)
    if f is None or f + n > len(x):
        return out
    y = sum(x[f:f + n]) / n
    out[f + n - 1] = y
    for i in range(f + n, len(x)):
        y = y + (2 / (n + 1)) * (x[i] - y) if alpha_form else (y * (n - 1) + x[i]) / n
        out[i] = y
    return out


def o_ema(x, n):
    return o_rma(x, n, True)


def o_rsi(c, n):
    ch = [NAN] + [c[i] - c[i - 1] for i in range(1, len(c))]
    up, dn = o_rma([NAN if math.isnan(v) else max(v, 0) for v in ch], n), o_rma([NAN if math.isnan(v) else max(-v, 0) for v in ch], n)
    return [NAN if math.isnan(u) else (100.0 if d == 0 else 100 - 100 / (1 + u / d)) for u, d in zip(up, dn)]


def o_stoch(src, hi, lo, n):
    out = []
    for i in range(len(src)):
        if i < n - 1 or any(math.isnan(v) for v in src[i - n + 1:i + 1]):
            out.append(NAN)
            continue
        hh, ll = max(hi[i - n + 1:i + 1]), min(lo[i - n + 1:i + 1])
        out.append(NAN if hh == ll else 100 * (src[i] - ll) / (hh - ll))
    return out


def lists(d):
    return {k: d[k].tolist() for k in ("open", "high", "low", "close", "volume")}


def test_oracle_rsi_stoch_stochrsi():
    L = lists(D)
    close_to(ind.rsi(D, 14), o_rsi(L["close"], 14))
    k = o_sma(o_stoch(L["close"], L["high"], L["low"], 14), 3)
    close_to(ind.stoch(D, 14, 3, 3).k, k)
    close_to(ind.stoch(D, 14, 3, 3).d, o_sma(k, 3))
    r = o_rsi(L["close"], 14)
    sk = o_sma(o_stoch(r, r, r, 14), 3)
    close_to(ind.stoch_rsi(D, 3, 3, 14, 14).k, sk)
    close_to(ind.stoch_rsi(D, 3, 3, 14, 14).d, o_sma(sk, 3))


def test_oracle_cci_willr_ao_mom_uo():
    L = lists(D)
    tp = [(h + l + c) / 3 for h, l, c in zip(L["high"], L["low"], L["close"])]
    cc = [NAN if i < 19 else (tp[i] - np.mean(tp[i - 19:i + 1])) / (0.015 * np.mean(np.abs(np.array(tp[i - 19:i + 1]) - np.mean(tp[i - 19:i + 1])))) for i in range(len(tp))]
    close_to(ind.cci(D, 20), cc)
    wr = [NAN if i < 13 else -100 * (max(L["high"][i - 13:i + 1]) - L["close"][i]) / (max(L["high"][i - 13:i + 1]) - min(L["low"][i - 13:i + 1])) for i in range(len(tp))]
    close_to(ind.williams_r(D, 14), wr)
    hl = [(h + l) / 2 for h, l in zip(L["high"], L["low"])]
    close_to(ind.ao(D), np.array(o_sma(hl, 5)) - np.array(o_sma(hl, 34)))
    close_to(ind.mom(D, 10), [NAN if i < 10 else L["close"][i] - L["close"][i - 10] for i in range(len(tp))])
    u = [NAN] * len(tp)
    bp, tr = [NAN] * len(tp), [NAN] * len(tp)
    for i in range(1, len(tp)):
        lo, hi = min(L["low"][i], L["close"][i - 1]), max(L["high"][i], L["close"][i - 1])
        bp[i], tr[i] = L["close"][i] - lo, hi - lo
    for i in range(28, len(tp)):
        a = lambda n: sum(bp[i - n + 1:i + 1]) / sum(tr[i - n + 1:i + 1])  # noqa: E731
        u[i] = 100 * (4 * a(7) + 2 * a(14) + a(28)) / 7
    close_to(ind.uo(D), u)


def test_oracle_macd_bbp_ema_sma():
    c = D.close.tolist()
    e12, e26 = o_ema(c, 12), o_ema(c, 26)
    m = [a - b for a, b in zip(e12, e26)]
    close_to(ind.macd(D).macd, m)
    close_to(ind.macd(D).signal, o_ema(m, 9))
    e13 = o_ema(c, 13)
    close_to(ind.bbp(D).bbp, [h + l - 2 * e for h, l, e in zip(D.high, D.low, e13)])
    for n in ind.PERIODS:
        close_to(ind.ema(D.close, n), o_ema(c, n))
        close_to(ind.sma(D.close, n), o_sma(c, n))


def test_oracle_adx():
    L = lists(D)
    n, N = 14, len(D)
    tr, pdm, mdm = [NAN] * N, [NAN] * N, [NAN] * N
    for i in range(1, N):
        tr[i] = max(L["high"][i] - L["low"][i], abs(L["high"][i] - L["close"][i - 1]), abs(L["low"][i] - L["close"][i - 1]))
        up, dn = L["high"][i] - L["high"][i - 1], L["low"][i - 1] - L["low"][i]
        pdm[i], mdm[i] = (up if up > dn and up > 0 else 0.0), (dn if dn > up and dn > 0 else 0.0)
    atr, ps, ms = o_rma(tr, n), o_rma(pdm, n), o_rma(mdm, n)
    plus = [100 * p / a for p, a in zip(ps, atr)]
    minus = [100 * q / a for q, a in zip(ms, atr)]
    dx = [NAN if math.isnan(p) else abs(p - q) / ((p + q) or 1) for p, q in zip(plus, minus)]
    a = ind.adx(D, n)
    close_to(a.plus_di, plus)
    close_to(a.minus_di, minus)
    close_to(a.adx, [100 * v for v in o_rma(dx, n)])


def test_oracle_ichimoku_vwma_hma():
    L = lists(D)
    N = len(D)
    mid = lambda n: [NAN if i < n - 1 else (max(L["high"][i - n + 1:i + 1]) + min(L["low"][i - n + 1:i + 1])) / 2 for i in range(N)]  # noqa: E731
    k = ind.ichimoku(D)
    close_to(k.tenkan, mid(9))
    close_to(k.kijun, mid(26))
    close_to(k.span_b, [NAN] * 26 + mid(52)[:N - 26])
    sa = [(a + b) / 2 for a, b in zip(mid(9), mid(26))]
    close_to(k.span_a, [NAN] * 26 + sa[:N - 26])
    close_to(ind.vwma(D), [NAN if i < 19 else sum(c * v for c, v in zip(L["close"][i - 19:i + 1], L["volume"][i - 19:i + 1])) / sum(L["volume"][i - 19:i + 1]) for i in range(N)])

    def o_wma(x, n):
        w = list(range(1, n + 1))
        return [NAN if i < n - 1 or any(map(math.isnan, x[i - n + 1:i + 1])) else sum(a * b for a, b in zip(x[i - n + 1:i + 1], w)) / sum(w) for i in range(len(x))]
    w4, w9 = o_wma(L["close"], 4), o_wma(L["close"], 9)
    close_to(ind.hma(D, 9), o_wma([2 * a - b for a, b in zip(w4, w9)], 3))


# --- (3) nedensellik ---------------------------------------------------------
def everything(d):
    t = ind.technicals(d)
    parts = {f"{k}_{c}": v[c] for k, v in dict(stoch=ind.stoch(d), adx=ind.adx(d), macd=ind.macd(d), srsi=ind.stoch_rsi(d), bbp=ind.bbp(d), ich=ind.ichimoku(d)).items() for c in v}
    parts.update({f"piv_{k}_{c}": p[c] for k in ind.PIVOTS for p in [ind.pivots(d, k)] for c in p})
    return pd.concat([t, pd.DataFrame(parts)], axis=1)


def test_causal_prefix_and_future_perturbation():
    full = everything(D)
    r = np.random.default_rng(1)
    for k in (400, 777, 1200):
        close_to(everything(D.iloc[:k]).to_numpy(), full.iloc[:k].to_numpy())  # kesilince aynı
        d2 = D.copy()
        junk = r.uniform(1, 1000, (len(D) - k, 5))
        d2.iloc[k:] = junk  # gelecek (ve high/low tutarsızlığı) bozulunca da aynı
        close_to(everything(d2).iloc[:k].to_numpy(), full.iloc[:k].to_numpy())


def test_technicals_has_every_tradingview_row_and_warmup():
    t = ind.technicals(D)
    assert list(t.columns[:11]) == ["RSI14", "StochK_14_3_3", "CCI20", "ADX14", "AO", "Mom10", "MACD_12_26", "StochRSI_K_3_3_14_14", "WilliamsR14", "BBP", "UO_7_14_28"]
    assert all(f"{m}{n}" in t for m in ("EMA", "SMA") for n in (10, 20, 30, 50, 100, 200)) and {"IchimokuBase", "VWMA20", "HMA9"} <= set(t.columns) and t.shape[1] == 26
    assert t.iloc[-1].notna().all()
    first = {c: int(t[c].notna().to_numpy().argmax()) for c in t}
    assert first["SMA200"] == 199 and first["EMA200"] == 199 and first["Mom10"] == 10 and first["RSI14"] == 14 and first["WilliamsR14"] == 13 and first["AO"] == 33
    assert first["MACD_12_26"] == 25 and first["IchimokuBase"] == 25 and first["VWMA20"] == 19 and first["UO_7_14_28"] == 28 and first["HMA9"] == 8 + 2


# --- tf hizalama -------------------------------------------------------------
def test_on_tf_alignment_no_peeking():
    d = ohlcv(24 * 5 + 7, seed=3)  # 5 tam gün + 7 saat (6. gün tamamlanmadı)
    dc = d.close.resample("1D").last()  # gün 0..5 son kapanışları (gün 5 eksik: 7 saatlik)
    v = ind.on_tf(d, "1d", lambda b: ind.sma(b.close, 2)).iloc[:, 0]
    t = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731
    # gün 1'in son saatinin (23:00) karar anı gün 2 00:00 = gün 1 kapanışı: SMA(2) gün 0 ve gün 1'i içerir
    assert v[t("2022-01-02 23:00")] == pytest.approx((dc.iloc[0] + dc.iloc[1]) / 2)
    # gün 1'in içindeki saatlerde yalnızca gün 0 tamamlanmış: SMA(2) için yetmez
    assert v["2022-01-02 00:00":"2022-01-02 22:00"].isna().all() and v["2022-01-01 00:00":"2022-01-01 23:00"].isna().all()
    # gün 2 boyunca değer sabit ve gün 0-1'den (gün 2'nin içinden hiçbir şey sızmaz); gün 2 kapanınca (gün 2 23:00) gün 2 girer
    day2 = v["2022-01-03 00:00":"2022-01-03 22:00"]
    assert day2.nunique() == 1 and day2.iloc[0] == pytest.approx((dc.iloc[0] + dc.iloc[1]) / 2)
    assert v[t("2022-01-03 23:00")] == pytest.approx((dc.iloc[1] + dc.iloc[2]) / 2)
    # tamamlanmamış son gün (gün 5) yeni değer üretmez: son 7 saat gün 4'ün kapanışındaki değeri taşır
    assert v.iloc[-7:].nunique() == 1 and v.iloc[-7] == pytest.approx((dc.iloc[3] + dc.iloc[4]) / 2)


def test_on_tf_future_perturbation_hourly_alignment():
    d = ohlcv(24 * 20 + 5, seed=4)
    f = lambda b: pd.concat([ind.rsi(b, 5), ind.sma(b.close, 3)], axis=1)  # noqa: E731
    full = ind.on_tf(d, "1d", f)
    k = 24 * 12 + 6
    d2 = d.copy()
    d2.iloc[k:] = np.random.default_rng(2).uniform(1, 500, (len(d) - k, 5))
    close_to(ind.on_tf(d2, "1d", f).iloc[:k].to_numpy(), full.iloc[:k].to_numpy())
    close_to(ind.on_tf(d.iloc[:k], "1d", f).to_numpy(), full.iloc[:k].to_numpy())


def test_on_tf_pivots_match_previous_period():
    d = ohlcv(24 * 6, seed=5)
    p = ind.on_tf_pivots(d, "1d", "classic")
    day = d.groupby(d.index.normalize()).agg(h=("high", "max"), l=("low", "min"), c=("close", "last"))
    for i in range(1, 6):
        e = (day.h.iloc[i - 1] + day.l.iloc[i - 1] + day.c.iloc[i - 1]) / 3
        assert np.allclose(p.loc[day.index[i]:day.index[i] + pd.Timedelta("23h"), "P"], e)
    assert p.iloc[:24].isna().all().all()  # ilk gün: önceki dönem yok
    w = ind.on_tf_pivots(d, "1d", "woodie")  # Woodie: dönem açılışı = o günün ilk saatlik açılışı
    o1 = d.open.iloc[24]
    assert w.P.iloc[30] == pytest.approx((day.h.iloc[0] + day.l.iloc[0] + 2 * o1) / 4)


# --- (4) referans kütüphaneler (kuruluysa) ----------------------------------
def test_against_talib():
    talib = pytest.importorskip("talib")
    h, l, c, v = (D[k].to_numpy(float) for k in ("high", "low", "close", "volume"))
    close_to(ind.sma(D.close, 20), talib.SMA(c, 20), 1e-9)
    close_to(ind.ema(D.close, 20), talib.EMA(c, 20), 1e-9)  # TA-Lib de SMA tohumu
    close_to(ind.rsi(D, 14), talib.RSI(c, 14), 1e-9)
    close_to(ind.mom(D, 10), talib.MOM(c, 10), 1e-9)
    close_to(ind.williams_r(D, 14), talib.WILLR(h, l, c, 14), 1e-9)
    close_to(ind.cci(D, 20), talib.CCI(h, l, c, 20), 1e-9)
    close_to(ind.uo(D), talib.ULTOSC(h, l, c, 7, 14, 28), 1e-9)
    sk, sd = talib.STOCH(h, l, c, 14, 3, 0, 3, 0)
    ok = ~np.isnan(sk)  # TA-Lib slowk'yı slowd ile aynı indeksten (17) başlatır; bizim K 15'ten geçerli: ortak aralıkta eşit
    assert ok.sum() == len(D) - 17 and np.allclose(ind.stoch(D).k[ok], sk[ok], rtol=1e-9, atol=1e-9)
    close_to(ind.stoch(D).d, sd, 1e-9)
    ok = np.arange(len(D)) >= 400  # TA-Lib Wilder/EMA tohumunu farklı noktadan başlatır (DI: ilk n-1 terim; MACD hızlı EMA): ısınma sonrası aynı, öncesi bilinçli farklı
    a = ind.adx(D, 14)
    for mine, ref in ((a.plus_di, talib.PLUS_DI(h, l, c, 14)), (a.minus_di, talib.MINUS_DI(h, l, c, 14)), (a.adx, talib.ADX(h, l, c, 14))):
        assert np.allclose(mine[ok], ref[ok], rtol=1e-9, atol=1e-9)
    m = ind.macd(D)
    tm, ts, _ = talib.MACD(c, 12, 26, 9)
    assert np.allclose(m.macd[ok], tm[ok], rtol=1e-9, atol=1e-9) and np.allclose(m.signal[ok], ts[ok], rtol=1e-9, atol=1e-9)
    fk, fd = talib.STOCHRSI(c, 14, 14, 3, 0)[0:2]
    close_to(ind.stoch_rsi(D, 3, 3, 14, 14).k, fd, 1e-9)  # TA-Lib fastd = SMA(ham %K, 3) = TradingView K


def test_against_ta_library():
    ta = pytest.importorskip("ta")
    ao = ta.momentum.AwesomeOscillatorIndicator(D.high, D.low).awesome_oscillator()
    close_to(ind.ao(D), ao, 1e-9)
    ich = ta.trend.IchimokuIndicator(D.high, D.low, 9, 26, 52)
    close_to(ind.ichimoku(D).kijun, ich.ichimoku_base_line(), 1e-9)
    close_to(ind.ichimoku(D).tenkan, ich.ichimoku_conversion_line(), 1e-9)


def test_against_pandas_ta_classic():
    pta = pytest.importorskip("pandas_ta_classic")
    for mine, ref in ((ind.hma(D, 9), pta.hma(D.close, 9)), (ind.vwma(D, 20), pta.vwma(D.close, D.volume, 20))):
        close_to(mine, ref, 1e-9)


# --- (5) TradingView ile birebir: gerçek BTCUSDT (Binance spot) mumları + aynı anda TradingView tarama API'sinden alınan değerler -------------------------------------------------------
# tests/data/tradingview/: btcusdt_<tf>.csv.gz (son 1000 mum, oluşmakta olan bar dahil) ve tv_<tf>.json (TradingView'in aynı anki değerleri: RSI, Stoch.K, CCI20, ADX, AO, Mom, MACD.macd, Stoch.RSI.K,
# W.R, BBPower, UO, EMA/SMA 10-200, Ichimoku.BLine, VWMA, HullMA9, Pivot.M.*). Tek yakalama, 2026-10-03; ağ gerekmez.
import gzip
import json
from pathlib import Path

TVDIR = Path(__file__).parent / "data" / "tradingview"
TV_MAP = {"RSI": "RSI14", "Stoch.K": "StochK_14_3_3", "CCI20": "CCI20", "ADX": "ADX14", "AO": "AO", "Mom": "Mom10", "MACD.macd": "MACD_12_26", "Stoch.RSI.K": "StochRSI_K_3_3_14_14",
          "W.R": "WilliamsR14", "BBPower": "BBP", "UO": "UO_7_14_28", "Ichimoku.BLine": "IchimokuBase", "VWMA": "VWMA20", "HullMA9": "HMA9",
          **{f"{m}{n}": f"{m}{n}" for m in ("EMA", "SMA") for n in ind.PERIODS}}
TV_PIVOT_KIND = {"Classic": "classic", "Fibonacci": "fibonacci", "Camarilla": "camarilla", "Woodie": "woodie", "Demark": "dm"}
TV_LEVEL = {"Middle": "P", "S1": "S1", "S2": "S2", "S3": "S3", "R1": "R1", "R2": "R2", "R3": "R3"}


def tv_case(tf):
    with gzip.open(TVDIR / f"btcusdt_{tf}.csv.gz", "rt") as f:
        k = pd.read_csv(f)
    k.index = pd.DatetimeIndex(pd.to_datetime(k.open_time, unit="ms", utc=True)).as_unit("ns")
    return k[["open", "high", "low", "close", "volume"]].astype(float), json.loads((TVDIR / f"tv_{tf}.json").read_text())["values"]


@pytest.mark.parametrize("tf", ["1d", "4h", "1h", "1w"])
def test_matches_tradingview_values(tf):
    d, tv = tv_case(tf)
    assert tv["close"] == pytest.approx(d.close.iloc[-1])  # aynı fiyatta yakalandı
    mine = ind.technicals(d).iloc[-1]
    # EMA'nın hafızası uzun: TradingView tarama API'si EMA100/200'ü sınırlı geçmişle hesaplıyor (1h/4h'de ~600 mum, aşağıda birebir gösteriliyor), biz 1000 mumla; formül aynı, tohum penceresi farklı.
    tol = {"EMA100": 1e-6, "EMA200": {"1d": 1e-5, "1w": 5e-3}.get(tf, 0), "RSI": 1e-5, "ADX": 5e-4, "MACD.macd": 5e-4}
    for name, col in TV_MAP.items():
        a, b = tv[name], mine[col]
        if name == "EMA200" and tf in ("4h", "1h"):
            continue  # aşağıda pencere eşlemesiyle
        t = tol.get(name, 1e-6)
        assert abs(a - b) <= t * max(abs(a), 1.0), f"{tf} {name}: TradingView {a} bizim {b}"


@pytest.mark.parametrize("tf", ["4h", "1h"])
def test_tradingview_scanner_ema_uses_about_600_bars(tf):
    """EMA(100/200) için TradingView değeri, son ~600 muma uygulanan AYNI formülle (SMA tohumu) birebir çıkar: tohum penceresi dışında fark yok."""
    d, tv = tv_case(tf)
    for n in (100, 200):
        best = min(abs(ind.ema(d.close.iloc[-w:], n).iloc[-1] - tv[f"EMA{n}"]) for w in range(550, 700))
        assert best < 1e-6, f"{tf} EMA{n}: en iyi fark {best}"


@pytest.mark.parametrize("tf,src,pivot_tf", [("1d", "1d", "1M"), ("4h", "1h", "1w"), ("1h", "1h", "1w")])
def test_pivots_match_tradingview(tf, src, pivot_tf):
    """TradingView pivot zaman dilimi grafiğe bağlı: 1d grafikte önceki AY, 1h/4h grafikte önceki HAFTA (gözlem; `TV_PIVOT_TF`). 1w grafik doğrulanmadı."""
    assert ind.TV_PIVOT_TF[tf] == pivot_tf
    d, _ = tv_case(src)
    _, tv = tv_case(tf)
    for tvk, kind in TV_PIVOT_KIND.items():
        p = ind.on_tf_pivots(d, pivot_tf, kind).iloc[-1]
        for lv, col in TV_LEVEL.items():
            a = tv.get(f"Pivot.M.{tvk}.{lv}")
            if a is not None and not np.isnan(p[col]):
                assert p[col] == pytest.approx(a, abs=0.01), f"{tf} {tvk} {lv}: TradingView {a} bizim {p[col]}"
