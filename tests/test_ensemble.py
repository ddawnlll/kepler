"""Ensemble v1 (kepler/ensemble.py; reports/ensemble_protocol.md): beklenen değerler elle (formül + sayı), çıktıyı kendisiyle karşılaştırma yok."""
import math

import numpy as np
import pandas as pd
import pytest

from kepler import audit
from kepler import ensemble as en

DAYS = pd.date_range("2024-01-01", periods=5, freq="1D", tz="UTC")


def st_of(sigma, active=None, ret=None, phi=None):
    sigma = pd.DataFrame(sigma, index=DAYS[: len(next(iter(sigma.values())))]) if not isinstance(sigma, pd.DataFrame) else sigma
    act = sigma.notna() if active is None else active
    return dict(sigma=sigma, active=act, ret=sigma * 0 if ret is None else ret, phi=sigma * np.nan if phi is None else phi)


def test_market_state_sigma_and_activity():
    kl = pd.DataFrame(dict(close=[100.0] * 24 + [110.0] * 24 + [99.0] * 24), index=pd.date_range("2024-01-01", periods=72, freq="1h", tz="UTC"))
    kls = {"A": kl}
    close, _ = en.panel(kls)
    st = en.market_state(close, kls, en.Params(vol_days=3, vol_floor=0.0, min_days=3))
    # r = ln(1,1) = 0,0953102, ln(0,9) = -0,1053605; std(ddof=1) = |a-b|/√2 = 0,2006707/1,4142136 = 0,1418956; x √365 = 2,710912
    assert st["sigma"]["A"].iloc[2] == pytest.approx(0.1418956 * math.sqrt(365), rel=1e-6)
    assert st["sigma"]["A"].iloc[2] == pytest.approx(2.710912, rel=1e-6)
    assert list(st["active"]["A"]) == [False, False, True]  # 3 kapanış + sigma gerekli
    st2 = en.market_state(close, kls, en.Params(vol_days=3, vol_floor=5.0, min_days=3))
    assert st2["sigma"]["A"].iloc[2] == 5.0  # taban


def test_trend_expert_zscore_and_clip():
    close = pd.DataFrame({"A": [100.0, 100.0, 100 * math.exp(0.1)], "B": [100.0, 100.0, 100 * math.exp(0.3)]}, index=DAYS[:3])
    sd = 0.05 * math.sqrt(365)  # günlük 0,05
    st = st_of({"A": [sd] * 3, "B": [sd] * 3})
    e1, _, _ = en.experts(close, st, en.Params(trend_L=(2,), xs_L=(2,)))
    # A: z = 0,1 / (0,05 √2) = 1,414214 -> f = z/2 = 0,707107; B: z = 4,2426 -> clip 1
    assert e1["A"].iloc[2] == pytest.approx(0.70710678, rel=1e-7)
    assert e1["B"].iloc[2] == 1.0
    assert np.isnan(e1["A"].iloc[1])  # L = 2 gün geri yok


def test_xs_expert_ranks():
    close = pd.DataFrame({"A": [100.0, 101.0], "B": [100.0, 103.0], "C": [100.0, 99.0], "D": [100.0, 102.0]}, index=DAYS[:2])
    st = st_of({s: [0.5, 0.5] for s in "ABCD"})
    _, e2, _ = en.experts(close, st, en.Params(trend_L=(1,), xs_L=(1,)))
    # sıra: C=1, A=2, D=3, B=4 -> q = 2(sıra-1)/3 - 1
    assert e2.iloc[1].to_dict() == pytest.approx({"A": -1 / 3, "B": 1.0, "C": -1.0, "D": 1 / 3})
    st3 = st_of({s: [0.5, 0.5] for s in "ABCD"}, active=pd.DataFrame({"A": [True] * 2, "B": [True] * 2, "C": [True] * 2, "D": [True, False]}, index=DAYS[:2]))
    _, e2b, _ = en.experts(close, st3, en.Params(trend_L=(1,), xs_L=(1,)))
    assert e2b.iloc[1][["A", "B", "C"]].tolist() == [0.0, 0.0, 0.0]  # n = 3 < 4 -> 0
    assert np.isnan(e2b.iloc[1]["D"])


def test_carry_expert():
    close = pd.DataFrame({"A": [100.0, 100.0], "B": [100.0, 100.0]}, index=DAYS[:2])
    phi = pd.DataFrame({"A": [np.nan, 0.1095 + 0.1], "B": [np.nan, 0.1095 - 0.5]}, index=DAYS[:2])
    st = st_of({"A": [0.5, 0.5], "B": [0.5, 0.5]}, phi=phi)
    _, _, e3 = en.experts(close, st, en.Params(trend_L=(1,), xs_L=(1,)))
    # A: c = -0,1/0,5 = -0,2 -> 2c = -0,4; B: c = +1 -> clip 1; funding yok -> 0
    assert e3["A"].iloc[1] == pytest.approx(-0.4)
    assert e3["B"].iloc[1] == 1.0
    assert e3["A"].iloc[0] == 0.0
    assert en.BASE_FUNDING == pytest.approx(0.1095)


def test_combine_expanding_scale():
    act = pd.DataFrame(True, index=DAYS[:2], columns=["A", "B"])
    e1 = pd.DataFrame({"A": [0.5, 1.0], "B": [-0.5 / 3, 1 / 3]}, index=DAYS[:2])
    zero = e1 * 0
    f = en.combine((e1, zero, zero), dict(active=act), en.Params(weights=(0.6, 0.2, 0.2), warm=1))
    # raw = 0,6 e1: gün 0 (0,3, -0,1), m0 = 0,2 -> F = raw * 0,5/0,2 = (0,75, -0,25); gün 1 raw (0,6, 0,2), m1 = (0,4+0,8)/4 = 0,3 -> (1,0 [clip], 0,3333)
    assert f.iloc[0].tolist() == pytest.approx([0.75, -0.25])
    assert f.iloc[1].tolist() == pytest.approx([1.0, 1 / 3])
    f2 = en.combine((e1, zero, zero), dict(active=act), en.Params(warm=2))
    assert f2.iloc[0].tolist() == [0.0, 0.0]  # ısınma


def test_rotate_shift_and_mask():
    f = pd.DataFrame({"A": [1.0, 2.0, 3.0, 4.0], "B": [np.nan, np.nan, 0.5, 0.6]}, index=DAYS[:4])
    act = f.notna()
    r = en.rotate(f, act, 0.5)  # k = 2
    assert r["A"].tolist() == [3.0, 4.0, 1.0, 2.0]
    assert np.isnan(r["B"].iloc[0]) and np.isnan(r["B"].iloc[1]) and r["B"].iloc[2:].tolist() == [0.0, 0.0]  # B'nin kaydırılmış değerleri aktif olmayan günlere düştü


def corr_panel(n, pattern):
    """Ortalama 0, eşit varyanslı periyot-4 diziler: s1 = [1,-1,1,-1], o = [1,1,-1,-1] (dik)."""
    s1, o = np.tile([1.0, -1, 1, -1], n // 4), np.tile([1.0, 1, -1, -1], n // 4)
    return s1, {"same": s1, "orth": o, "neg": -0.5 * s1 + math.sqrt(0.75) * o}[pattern]


def size_case(pattern, F, p=en.Params(corr_days=40), cap=10_000.0):
    n = 40
    idx = pd.date_range("2024-01-01", periods=n, freq="1D", tz="UTC")
    a, b = corr_panel(n, pattern)
    ret = pd.DataFrame({"A": a * 0.01, "B": b * 0.01}, index=idx)
    sig = pd.DataFrame(0.5, index=idx, columns=["A", "B"])
    act = pd.DataFrame(False, index=idx, columns=["A", "B"])
    act.iloc[-len(F):] = True
    f = pd.DataFrame(np.nan, index=idx, columns=["A", "B"])
    f.iloc[-len(F):] = F
    return en.size(f, dict(ret=ret, sigma=sig, active=act), cap, p)


def test_size_idm_correlated_and_uncorrelated():
    # ρ = 1: IDM = 1, birim = 10000·0,2·0,5/0,5 = 2000; V = 0,2 = τ (tavan bağlamaz)
    out = size_case("same", [[1.0, 0.5]])
    assert out.iloc[-1].tolist() == pytest.approx([2000.0, 1000.0])
    # ρ = 0: IDM = 1/√0,5 = √2 -> birim = 2828,427; F = (1, 1): V = √2·0,5·2828,427/10000 = 0,2
    out = size_case("orth", [[1.0, 1.0]])
    assert out.iloc[-1].tolist() == pytest.approx([2828.427125, 2828.427125])


def test_size_portfolio_vol_cap_binds_with_negative_correlation():
    # ρ = -0,5: IDM ρ⁺ = I ile √2; n = ±2828,427; nᵀΣn = 0,25·2828,427²·(1+1+2·0,5) = 6e6 -> V = 0,244949 > 0,2 -> x 0,816497 -> ±2309,401
    out = size_case("neg", [[1.0, -1.0]])
    assert out.iloc[-1].tolist() == pytest.approx([2309.401077, -2309.401077])


def test_size_buffer_caps_and_no_risk():
    out = size_case("same", [[1.0, 0.0], [0.9, 0.0], [0.7, 0.0]])
    # 2000 -> |1800-2000| = 200 <= 0,2·2000 = 400: tut; |1400-2000| = 600 > 400: 1400
    assert out["A"].iloc[-3:].tolist() == pytest.approx([2000.0, 2000.0, 1400.0])
    assert out["A"].iloc[:-3].abs().sum() == 0  # aktif değil -> 0
    out = size_case("same", [[1.0, 0.0]], en.Params(corr_days=40, sym_cap=0.1))
    assert out["A"].iloc[-1] == pytest.approx(1000.0)  # 0,1 x 10000
    out = size_case("same", [[1.0, -1.0]], en.Params(corr_days=40, gross_cap=0.3))
    assert out.iloc[-1].tolist() == pytest.approx([1500.0, -1500.0])  # brüt 4000 > 3000 -> x 0,75
    out = size_case("same", [[0.5, -1.0]], en.Params(corr_days=40, risk=False))
    assert out.iloc[-1].tolist() == pytest.approx([2500.0, -5000.0])  # n = K F / M


def test_place_last_bar_of_day_and_partial_day():
    idx = pd.date_range("2024-01-01", periods=24 * 3, freq="1h", tz="UTC").delete(list(range(24 + 20, 48)))  # 2. gün 19:00'da bitiyor (boşluk)
    idx = idx[:-3]  # son gün 20:00'de kesik
    kl = pd.DataFrame(dict(close=1.0), index=idx)
    daily = pd.Series([1.0, 2.0, 3.0], index=DAYS[:3])
    t = en.place(kl, daily)
    assert t.dropna().to_dict() == {pd.Timestamp("2024-01-01 23:00", tz="UTC"): 1.0, pd.Timestamp("2024-01-02 19:00", tz="UTC"): 2.0}


def synth(n_days=160, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=24 * n_days, freq="1h", tz="UTC")
    kls = {}
    for i, s in enumerate(("AAA", "BBB", "CCC", "DDD")):
        c = 100 * np.exp(np.cumsum(rng.normal(0.0002 * (i - 1.5), 0.01, len(idx))))
        o = np.r_[c[0], c[:-1]]
        start = 0 if s != "DDD" else 24 * 30  # geç listelenen sembol
        kls[s] = pd.DataFrame(dict(open=o, high=np.maximum(o, c) * 1.002, low=np.minimum(o, c) * 0.998, close=c, volume=1.0, fund_hr=rng.normal(1e-5, 2e-5, len(idx))), index=idx).iloc[start:]
    return kls


P_SMALL = en.Params(trend_L=(3, 6), xs_L=(3, 6), carry_days=3, vol_days=10, corr_days=40, min_days=45, warm=5)


def test_book_causal_and_deterministic():
    kls = synth()
    book = en.make_book(10_000.0, P_SMALL)
    assert audit.check_causal_book(book, kls) == []
    a, b = book(kls), book(kls)
    assert all(a[s].equals(b[s]) for s in kls)
    t = a["AAA"].target.dropna()
    assert (t.index.hour == 23).all() and a["AAA"].stop.isna().all()
    d = a["DDD"].target.dropna()
    assert (d[d != 0].index >= kls["DDD"].index[0] + pd.Timedelta(days=44)).all() and (d != 0).any()  # aktiflikten (45 kapanış) önce pozisyon yok
    assert t.abs().max() > 0


def test_book_funding_causal():
    """audit.check_causal_book yalnızca OHLCV'yi bozar; funding (fund_hr) nedenselliği burada: k sonrası funding bozulunca önceki hedefler değişmez, sonrası değişir."""
    kls = synth()
    book = en.make_book(10_000.0, P_SMALL)
    base = book(kls)
    k = kls["AAA"].index[24 * 100]
    alt = {s: kl.assign(fund_hr=kl.fund_hr.where(kl.index < k, 1e-3)) for s, kl in kls.items()}
    pert = book(alt)
    for s in kls:
        assert base[s].target[base[s].index < k].equals(pert[s].target[pert[s].index < k])
    assert not all(base[s].target.equals(pert[s].target) for s in kls)


def test_rotation_book_keeps_activity():
    kls = synth()
    f, st = en.forecasts(kls, P_SMALL)
    fr, _ = en.forecasts(kls, P_SMALL, u=0.3)
    assert (fr.notna() == st["active"]).all().all()
    k = int(0.3 * len(f))
    assert fr["AAA"].iloc[k + 50] == pytest.approx(f["AAA"].fillna(0.0).iloc[50])


def test_params_scaled():
    p = en.Params().scaled(1.2)
    assert (p.trend_L, p.xs_L, p.carry_days, p.vol_days, p.corr_days) == ((8, 17, 34, 67), (17, 34, 67), 8, 36, 108)
