"""Kapasite / karekök etki (BACKTEST §10). Beklenen değerler elle."""
import math

import numpy as np
import pandas as pd
import pytest

from kepler import capacity

A = pytest.approx


def test_participation_and_sqrt_impact_hand_values():
    h = pd.date_range("2024-01-01", periods=6, freq="1h", tz="UTC")
    kl = {"A": pd.DataFrame(dict(close=100.0 * 1.01 ** np.arange(6), quote_volume=[1e6, 1e6, 1e6, 1e6, 2e6, 0.0]), index=h)}
    ns = lambda i, d=0: int(h[i].value) + d  # noqa: E731
    fills = pd.DataFrame([dict(sym="A", ts=ns(3), qty=10.0, px=100.0),                        # bar 03:00, notional 1000, hacim 1e6 -> katılım 0,001
                          dict(sym="A", ts=ns(4, 3_599_999_999_999), qty=40.0, px=50.0),     # gövde dolumu, bar 04:00: notional 2000 / 2e6 -> 0,001
                          dict(sym="A", ts=ns(5), qty=1.0, px=100.0)])                       # hacmi 0 olan bar -> katılım 1
    t = capacity.fill_table(fills, kl, win=2)
    assert list(t.part) == [A(0.001), A(0.001), 1.0] and list(t.notional) == [1000, 2000, 100]
    # σ(03:00) = RMS(03:00 açılışında tamamlanmış son 2 saatlik log-getiri: 00-01, 01-02... = r1, r2) = ln(1,01) (sabit getiri); r3 (03:00 barının kendisi) kullanılmaz
    assert t.sigma[0] == A(math.log(1.01))
    # etki = Y σ √katılım notional = 0,00995033 × 0,0316228 × 1000 = 0,31466 (Y=1); Y=2 iki katı; hacimsiz barda tam saat: ln1,01 × 1 × 100
    c = capacity.impact_cost(t)
    assert c[0] == A(0.31466, abs=1e-5) and c[1] == A(0.00995033 * 0.0316228 * 2000, abs=1e-4) and c[2] == A(0.995033, abs=1e-5)
    assert capacity.impact_cost(t, 2.0)[0] == A(2 * c[0])
    hc = capacity.hourly_cost(t, c, h)
    assert hc.iloc[3] == A(c[0]) and hc.iloc[4] == A(c[1]) and hc.iloc[0] == 0 and hc.sum() == A(c.sum())
    s = capacity.summary(t, 0.0005)
    assert s["n"] == 3 and s["n_over"] == 3 and s["share_over"] == 1.0 and s["max"] == 1.0 and s["n_zero_volume"] == 1 and s["n_capped"] == 1
    assert capacity.summary(t, 0.002)["n_over"] == 1  # yalnızca katılımı 1 olan


def test_sigma_is_causal_future_bar_does_not_change_it():
    h = pd.date_range("2024-01-01", periods=6, freq="1h", tz="UTC")
    base = dict(close=100.0 * 1.01 ** np.arange(6), quote_volume=1e6)
    fills = pd.DataFrame([dict(sym="A", ts=int(h[3].value), qty=10.0, px=100.0)])
    c2 = base["close"].copy()
    c2[3:] *= 2  # 03:00 barının kendisi ve sonrası bozulur (r3 değişir); 03:00 açılışındaki σ aynı kalmalı
    a = capacity.fill_table(fills, {"A": pd.DataFrame(base, index=h)}, 2)
    b = capacity.fill_table(fills, {"A": pd.DataFrame(dict(base, close=c2), index=h)}, 2)
    assert a.sigma[0] == b.sigma[0] == A(math.log(1.01)) and a.sigma[0] > 0
