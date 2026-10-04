"""Edge uzmanları (reports/edge_experts_protocol.md): beklenen değerler elle (formül + sayı), çıktıyı kendisiyle karşılaştırma yok. Gelecek-bozma: bozulan/kesilen gelecek geçmiş tahmini değiştirmez."""
import math

import numpy as np
import pandas as pd
import pytest

from kepler import audit
from kepler import ensemble as en
from kepler.experts import bollinger, fundcrowd, lowvol, nearhigh, orderflow, volrev
from kepler.experts._interface import scale, xrank


def days(n):
    return pd.date_range("2024-01-01", periods=n, freq="1D", tz="UTC")


def st_of(index, cols, **kw):
    """Küçük elle kurulan piyasa durumu: yalnızca uzmanın okuduğu anahtarlar doldurulur, aktiflik hepsi True."""
    z = pd.DataFrame(np.nan, index=index, columns=cols)
    return dict(active=z.notna() | True, sigma=z, ret=z, phi=z, dvol=z, tbr=z, **kw)


def test_bollinger_hand_values():
    close = pd.DataFrame({"A": np.arange(1.0, 21.0), "B": [5.0] * 20}, index=days(20))
    f = bollinger.forecast(close, st_of(close.index, close.columns), en.Params()).iloc[-1]
    # A: SMA = 10,5; std(ddof 0) = √((20² − 1)/12) = √33,25 = 5,766281; z = 9,5 / 5,766281 = 1,647509; F = −z/2 = −0,8237545
    assert f["A"] == pytest.approx(-0.8237545, rel=1e-6)
    assert f["B"] == 0.0  # std = 0
    c3 = pd.DataFrame({"A": [1.0, 1.0, 10.0]}, index=days(3))
    f3 = bollinger.forecast(c3, st_of(c3.index, c3.columns), en.Params(xp=(("n", 3), ("k", 2.0)))).iloc[-1]
    # n = 3: SMA = 4; sapmalar −3, −3, 6 -> var = 54/3 = 18, std = 4,242641; z = 6 / 4,242641 = 1,414214; F = −0,7071068
    assert f3["A"] == pytest.approx(-0.70710678, rel=1e-7)
    f3k = bollinger.forecast(c3, st_of(c3.index, c3.columns), en.Params(xp=(("n", 3), ("k", 1.0)))).iloc[-1]
    assert f3k["A"] == -1.0  # z/k = 1,414214 > 1 -> clip


def test_lowvol_rank_and_min_symbols():
    d = days(3)
    ret = pd.DataFrame({"A": [0.0, 0.0, 0.0], "B": [0.01, -0.01, 0.01], "C": [0.02, -0.02, 0.02], "D": [0.03, -0.03, 0.03]}, index=d)
    st = st_of(d, ret.columns)
    st["ret"] = ret
    f = lowvol.forecast(ret, st, en.Params(xp=(("L", 3),))).iloc[-1]
    # std(ddof 1): A 0; B: sapmalar 0,006667, −0,013333, 0,006667 -> var 1,3333e-4 -> 0,011547; C 2x, D 3x. Sıra (−oynaklık): A 4, B 3, C 2, D 1; q = 2(sıra − 1)/3 − 1
    assert [f[k] for k in "ABCD"] == pytest.approx([1.0, 1 / 3, -1 / 3, -1.0], abs=1e-12)
    three = ret[["A", "B", "C"]]
    st3 = st_of(d, three.columns)
    st3["ret"] = three
    assert (lowvol.forecast(three, st3, en.Params(xp=(("L", 3),))).iloc[-1] == 0).all()  # n < 4 -> 0


def test_nearhigh_rank():
    d = days(3)
    close = pd.DataFrame({"A": [10.0, 10, 10], "B": [10.0, 20, 15], "C": [10.0, 20, 10], "D": [20.0, 20, 5]}, index=d)
    f = nearhigh.forecast(close, st_of(d, close.columns), en.Params(xp=(("L", 3),))).iloc[-1]
    # x = C / max: A 1,0; B 0,75; C 0,5; D 0,25 -> sıra 4, 3, 2, 1 -> q = 1, 1/3, −1/3, −1
    assert [f[k] for k in "ABCD"] == pytest.approx([1.0, 1 / 3, -1 / 3, -1.0], abs=1e-12)


def test_fundcrowd_extreme_only_and_sign():
    d = days(5)
    phi = pd.DataFrame({"A": [0.0, 0, 0, 0, 10.0], "B": [0.0, 0, 0, 0, -10.0], "C": [0.0, 1, 0, 1, 0.5]}, index=d)
    st = st_of(d, phi.columns)
    st["phi"] = phi
    f = fundcrowd.forecast(phi, st, en.Params(xp=(("L", 5), ("thr", 1.5))))
    # A son gün: pencere [0,0,0,0,10]: ort 2, var = (4·4 + 64)/4 = 20, std 4,472136; z = 8 / 4,472136 = 1,788854 > 1,5 -> F = −z/3 = −0,5962848 (aşırı pozitif funding -> short)
    assert f["A"].iloc[-1] == pytest.approx(-0.5962848, rel=1e-6)
    assert f["B"].iloc[-1] == pytest.approx(0.5962848, rel=1e-6)
    assert f["C"].iloc[-1] == 0.0  # C: pencere [0, 1, 0, 1, 0,5]: ort 0,5, son değer ortada -> z = 0 (eşik altı)
    assert (f["A"].iloc[:4] == 0).all()  # std 0 / NaN -> 0


def test_volrev_only_on_volume_spike():
    d = days(4)
    cols = ["A", "B"]
    st = st_of(d, cols)
    st["dvol"] = pd.DataFrame({"A": [100.0, 100, 100, 300], "B": [100.0, 100, 100, 100]}, index=d)
    st["ret"] = pd.DataFrame({"A": [np.nan, 0.0, 0.0, -0.05], "B": [np.nan, 0.0, 0.0, -0.05]}, index=d)
    st["sigma"] = pd.DataFrame(0.05 * math.sqrt(365), index=d, columns=cols)  # günlük sd = 0,05
    f = volrev.forecast(st["ret"], st, en.Params(xp=(("L", 3), ("thr", 1.5))))
    # A son gün: v = 300 / ort(100,100,100) = 3 > 1,5; F = −(−0,05)/(2·0,05) = +0,5; B: v = 1 -> 0
    assert f["A"].iloc[-1] == pytest.approx(0.5, abs=1e-12) and f["B"].iloc[-1] == 0.0
    st["ret"]["A"] = [np.nan, 0.0, 0.0, 0.2]
    assert volrev.forecast(st["ret"], st, en.Params(xp=(("L", 3), ("thr", 1.5))))["A"].iloc[-1] == -1.0  # −0,2/0,1 = −2 -> clip
    assert f["A"].iloc[2] == 0.0  # önceki günlerde şok yok


def test_orderflow_zscore():
    d = days(5)
    st = st_of(d, ["A"])
    st["tbr"] = pd.DataFrame({"A": [0.5, 0.5, 0.5, 0.5, 0.9]}, index=d)
    f = orderflow.forecast(st["tbr"], st, en.Params(xp=(("L", 4), ("m", 2)))).iloc[-1]
    # imb = [0,0,0,0,0,8]; L = 4 pencere [0,0,0,0,8]: son 4 = [0,0,0,0,8][-4:] = [0,0,0,0.8]: ort 0,2, var = (3·0,04 + 0,36)/3 = 0,16, std 0,4; ort_2 = 0,4; z = 0,2/0,4 = 0,5; F = 0,25
    assert f["A"] == pytest.approx(0.25, abs=1e-12)


def test_xrank_and_scale_helpers():
    d = days(1)
    x = pd.DataFrame({"A": [3.0], "B": [1.0], "C": [2.0], "D": [4.0]}, index=d)
    assert list(xrank(x, x.notna()).iloc[0]) == pytest.approx([1 / 3, -1.0, -1 / 3, 1.0])
    assert dict(scale(dict(n=20, k=2.0), 1.1)) == {"n": 22, "k": pytest.approx(2.2)}
    assert dict(scale(dict(L=3), 0.8)) == {"L": 2}  # yuvarlama, en az 1


def kls_fixture(n_days=260, n_sym=6, seed=1):
    rng, idx = np.random.default_rng(seed), pd.date_range("2023-01-01", periods=24 * n_days, freq="1h", tz="UTC")
    out = {}
    for i in range(n_sym):
        c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx))))
        vol = rng.uniform(50, 150, len(idx))
        qv = vol * c
        out[f"S{i}"] = pd.DataFrame(dict(open=np.r_[c[0], c[:-1]], high=c * 1.002, low=c * 0.998, close=c, volume=vol, quote_volume=qv, taker_buy_quote_volume=qv * rng.uniform(0.3, 0.7, len(idx)),
                                         fund_hr=np.repeat(rng.normal(1e-5, 4e-5, n_days * 3), 8)), index=idx)
    return out


NAMES = ["bollinger", "lowvol", "nearhigh", "fundcrowd", "volrev", "orderflow"]


def test_market_state_daily_volume_and_taker_share():
    idx = pd.date_range("2024-01-01", periods=48, freq="1h", tz="UTC")
    kl = pd.DataFrame(dict(close=100.0, quote_volume=[10.0] * 24 + [20.0] * 24, taker_buy_quote_volume=[5.0] * 24 + [15.0] * 24), index=idx)
    close, _ = en.panel({"A": kl})
    st = en.market_state(close, {"A": kl}, en.Params(vol_days=3, min_days=1))
    assert list(st["dvol"]["A"]) == [240.0, 480.0]  # 24·10, 24·20
    assert list(st["tbr"]["A"]) == [0.5, 0.75]  # 120/240, 360/480
    st2 = en.market_state(close, {"A": kl[["close"]]}, en.Params(vol_days=3, min_days=1))
    assert st2["dvol"]["A"].isna().all() and st2["tbr"]["A"].isna().all()  # sütun yoksa NaN


@pytest.mark.parametrize("name", NAMES)
def test_future_corruption_and_truncation_do_not_change_past(name):
    kls, p = kls_fixture(), en.Params(expert=name)
    f, _ = en.forecasts(kls, p)
    assert f.abs().to_numpy()[~np.isnan(f.to_numpy())].max() > 0  # sinyal gerçekten bir şey üretiyor
    cut = pd.Timestamp("2023-07-15", tz="UTC")
    rng, alt = np.random.default_rng(7), {}
    for s, kl in kls.items():
        m = kl.index >= cut
        alt[s] = kl.copy()
        for col in kl.columns:  # tüm sütunlar (taker/hacim/funding dahil) bozulur
            alt[s].loc[m, col] = kl.loc[m, col].to_numpy() * rng.uniform(0.2, 3.0, int(m.sum()))
    fp, _ = en.forecasts(alt, p)
    ft, _ = en.forecasts({s: kl[kl.index < cut] for s, kl in kls.items()}, p)
    past = f.index < cut
    pd.testing.assert_frame_equal(f[past], fp[past])
    pd.testing.assert_frame_equal(f[past], ft.reindex(f.index)[past])


@pytest.mark.parametrize("name", NAMES)
def test_book_is_causal_via_audit(name):
    kls = kls_fixture(n_days=200, n_sym=5)
    assert audit.check_causal_book(en.make_book(10_000.0, en.Params(expert=name)), kls, fracs=(0.5, 0.8)) == []


def test_expert_mode_flip_and_ev1_default_unchanged():
    kls = kls_fixture(n_days=200, n_sym=5)
    f, _ = en.forecasts(kls, en.Params(expert="bollinger"))
    g, _ = en.forecasts(kls, en.Params(expert="bollinger", flip=True))
    pd.testing.assert_frame_equal(f.fillna(0.0), -g.fillna(0.0))
    close, _ = en.panel(kls)
    st = en.market_state(close, kls, en.Params())
    ev1, _ = en.forecasts(kls, en.Params())
    pd.testing.assert_frame_equal(ev1, en.combine(en.experts(close, st, en.Params()), st, en.Params()))  # expert="" -> EV1 yolu (3 uzman, ağırlıklar 0,6/0,2/0,2)


def test_forecast_does_not_depend_on_not_yet_listed_columns():
    """Gerçek veri durumu: tam panel 9 sütun (2'si henüz listelenmemiş, NaN), kesik panelde bu 2 sütun hiç yok. Toplama sırası değişirse 1 ulp fark çıkar; audit bunu sızıntı sayar. Not: sentetik veri bu ulp farkını yeniden üretmiyor (düzeltmesiz de geçer); asıl kanıt gerçek veride audit koşusudur (reports/edge_experts.md)."""
    kls = kls_fixture(n_days=200, n_sym=9)
    late = ("S7", "S8")
    full = {s: (kl.where(pd.Series(kl.index >= kl.index[24 * 120], index=kl.index), axis=0) if s in late else kl) for s, kl in kls.items()}  # S7/S8, 120. günden önce NaN
    cut = pd.Timestamp("2023-04-20", tz="UTC")  # listelenmeden önce
    for name in NAMES:
        p = en.Params(expert=name)
        f, _ = en.forecasts(full, p)
        g, _ = en.forecasts({s: kl[kl.index < cut] for s, kl in kls.items() if s not in late}, p)
        pd.testing.assert_frame_equal(f[f.index < cut].drop(columns=list(late)).iloc[:-1], g[g.index < cut].iloc[:-1], obj=name)  # son gün kesik: hariç; geri kalan birebir
