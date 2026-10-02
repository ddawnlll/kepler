"""Tarihsel stres araçları (BACKTEST §10). Beklenen değerler elle."""
import numpy as np
import pandas as pd
import pytest

from kepler import stress

A = pytest.approx


def test_drop_days_picks_worst_basket_days_with_separation_and_exclusion():
    idx = pd.date_range("2024-01-01", periods=20, freq="1D", tz="UTC")
    a = pd.Series(100.0, index=idx)
    b = pd.Series(100.0, index=idx)
    a.iloc[3:], b.iloc[3:] = 90.0, 98.0   # gün 3: a -10%, b -2% -> sepet -6%
    a.iloc[4:], b.iloc[4:] = 81.0, 78.4   # gün 4: a -10%, b -20% -> sepet -15% (en kötü)
    a.iloc[14:], b.iloc[14:] = 72.9, 70.56   # gün 14: -10%, -10% -> sepet -10%
    c = pd.DataFrame(dict(a=a, b=b))
    assert [(d.day, round(v, 4)) for d, v in stress.drop_days(c, 3, 7)] == [(5, -0.15), (15, -0.1)]  # indeks 4 = 5 Ocak; indeks 3 (-6%) 5 Ocak'a 1 gün uzak: atlanır; indeks 14 = 15 Ocak
    ex = (("2024-01-05", "2024-01-06"),)
    assert [d.day for d, _ in stress.drop_days(c, 3, 7, ex)] == [15, 4]  # 5 Ocak dışlandı; en kötüden: 15 Ocak (-10%), 4 Ocak (-6%); ikisi >= 7 gün uzak


def test_window_stats_hand_values():
    h = pd.date_range("2024-01-01", periods=6, freq="1h", tz="UTC")
    pnl = pd.Series([1.0, -3, -2, 4, -5, 1], index=h)
    close = {"A": pd.Series([105.0, 100, 100, 100, 100, 100], index=h)}
    stop = {"A": pd.Series([np.nan, np.nan, 95.0, np.nan, np.nan, np.nan], index=h)}
    ns = lambda i: int(h[i].value)  # noqa: E731
    fills = pd.DataFrame([dict(sym="A", ts=ns(0), side="BUY", qty=2.0, px=100.0, liq=False, stop=False),
                          dict(sym="A", ts=ns(3) + 3_599_999_999_999, side="SELL", qty=2.0, px=94.0, liq=False, stop=True)])
    bar = {"A": pd.DataFrame(dict(low=[100, 100, 100, 93.0, 100, 100], high=100.0), index=h)}
    s = stress.window_stats(pnl, fills, "2024-01-01 01:00", "2024-01-01 06:00", 100.0, close, stop, bar)
    # pencere [01:00, 06:00): -3,-2,4,-5,1 -> kümülatif -3,-5,-1,-6,-5; tepe 0 (başlangıç) -> maks DD 6; net -5; en kötü saat -5
    assert s["net"] == -5 and s["net_pct"] == A(-0.05) and s["max_dd"] == 6 and s["max_dd_pct"] == A(0.06) and s["worst_hour"] == -5 and s["worst_day"] == -5
    assert s["n_stop"] == 1 and s["n_liq"] == 0
    assert s["gross_start"] == 210 and s["net_start"] == 210  # pozisyon +2, 01:00 öncesi son kapanış 105
    # stop dolumu 03:00 barında (ts = 03:00 + 1sa - 1ns); yürürlükteki seviye = stop.shift(1)[03:00] = stop[02:00] = 95; satış 94'ten -> (95-94)/95 = 105,263 bps
    assert s["stop_slip_bps_mean"] == A(1 / 95 * 1e4) and s["n_stop_slip"] == 1
    assert s["overshoot_bps_mean"] == A((95 - 93) / 95 * 1e4)  # barın dibi 93, seviye 95 -> 210,526 bps aşma
    assert stress.basket_return(close, "2024-01-01 01:00", "2024-01-01 06:00") == A(100 / 105 - 1)
