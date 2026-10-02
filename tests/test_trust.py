"""C4: nedensellik, determinizm, pencere denkliği, negatif kontroller."""
import numpy as np
import pandas as pd
import pytest

from kepler import audit, referee

A = pytest.approx


def market(n=400, seed=1, drift=0.0, vol=0.01):
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    c = (100 * np.exp(np.cumsum(np.random.default_rng(seed).normal(drift, vol, n)))).round(2)
    return pd.DataFrame(dict(open=c, high=c, low=c, close=c, volume=1000.0), index=idx)


def mom(kl, n=24, size=1000.0):  # test fixture (sinyal değil): nedensel
    up = kl.close > kl.close.shift(n)
    return pd.Series(np.where(up, size, -size), index=kl.index).where(kl.close.shift(n).notna())


def leaky(kl):  # BİLEREK sızdırır: bir SONRAKİ barın kapanışına bakar
    return pd.Series(np.where(kl.close.shift(-1) > kl.close, 1000.0, -1000.0), index=kl.index)


SP = referee.Spec(tick="0.01", step="0.0001", capital=10000.0, liq=False, fill="close", close_out=False)


# ---- nedensellik
def test_causal_signal_passes():
    assert audit.check_causal(mom, market()) == []
    audit.assert_causal(mom, market())


def test_leaking_signal_is_caught():
    assert audit.check_causal(leaky, market()) != []
    with pytest.raises(AssertionError, match="geleceğe bakıyor"):  # sızdıran sinyal gerçekten kırmızıya düşüyor
        audit.assert_causal(leaky, market())


def test_length_dependent_signal_is_caught():
    def peek_total(kl):  # tüm serinin ortalamasına bakar (kesilince değişir)
        return pd.Series(np.where(kl.close > kl.close.mean(), 1000.0, -1000.0), index=kl.index)

    assert audit.check_causal(peek_total, market()) != []


# ---- determinizm
def test_same_input_same_hash():
    kl = market()
    t = mom(kl)
    h = {audit.result_hash(referee.run(kl, t, SP)) for _ in range(3)}
    assert len(h) == 1
    assert audit.result_hash(referee.run(kl, t.shift(1), SP)) not in h  # farklı girdi farklı hash (hash duyarlı)


# ---- tam/pencereli tape denkliği (funding sınırı 08:00 pencerenin içinde)
def test_windowed_tape_equals_full_tape_including_funding():
    kl = market(n=120, seed=3)
    mark = kl.assign(close=kl.close * 1.001)
    fund = pd.DataFrame({"last_funding_rate": [1e-4, -3e-4, 2e-4, 1e-4, -1e-4, 5e-5]},
                        index=pd.date_range("2024-01-01 00:00:00.003", periods=6, freq="8h", tz="UTC"))
    t = pd.Series(np.nan, index=kl.index)
    t.iloc[20], t.iloc[50] = 1000.0, 0.0  # 20. bar kapanışında aç, 50.'de kapat: 08:00/16:00/00:00 sınırlarını aşar
    full = referee.run(kl, t, SP, funding=fund, mark=mark)
    win = slice(10, 70)  # pozisyon pencerede başlar ve biter
    part = referee.run(kl.iloc[win], t.iloc[win], SP, funding=fund, mark=mark.iloc[win])
    assert full["summary"]["funding"] != 0  # sınır gerçekten aşılıyor
    for k in ("net_pnl", "gross_pnl", "fee", "funding"):
        assert part["summary"][k] == A(full["summary"][k], abs=1e-9)
    assert part["fills"][["ts", "side", "qty", "px"]].equals(full["fills"][["ts", "side", "qty", "px"]])


# ---- negatif kontroller
def test_flat_signal_is_exactly_zero():
    r = referee.run(market(), pd.Series(0.0, index=market().index), SP)
    assert r["fills"].empty and r["summary"]["net_pnl"] == 0 and r["summary"]["fee"] == 0


def test_random_signal_is_minus_cost_on_driftless_market():
    """Sıfır sürüklenmeli piyasada rastgele sinyal: brüt ~ 0 (3 SE içinde), net = brüt - maliyet < 0."""
    gross, fee = [], []
    for seed in range(30):
        kl = market(n=300, seed=seed)
        t = pd.Series(np.random.default_rng(1000 + seed).choice([-1000.0, 0.0, 1000.0], size=len(kl)), index=kl.index)
        s = referee.run(kl, t, referee.Spec(tick="0.01", step="0.0001", capital=10000.0, liq=False, fee_rt_bps=10, fill="close", close_out=False))["summary"]
        gross.append(s["gross_pnl"])
        fee.append(s["fee"])
    g, se = np.mean(gross), np.std(gross, ddof=1) / np.sqrt(len(gross))
    assert abs(g) < 3 * se, (g, se)
    assert np.mean(fee) > 0 and g - np.mean(fee) < 0
