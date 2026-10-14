"""Numba trim_flat preserves fills/PnL and original funding valuation; the engine is silent."""
import numpy as np
import pandas as pd
import pytest

from kepler import evaluate as ev  # noqa: E402
from kepler import referee, report  # noqa: E402

N = 240
IDX = pd.date_range("2024-01-01", periods=N, freq="1h", tz="UTC")


def kl_of(seed):
    c = 100 + np.cumsum(np.random.default_rng(seed).normal(0, 0.4, N))
    return pd.DataFrame(dict(open=c, high=c + 0.3, low=c - 0.3, close=c, volume=1e6), index=IDX)


def book(target, stop=None):
    t = pd.Series(np.nan, index=IDX)
    for k, v in target.items():
        t.iloc[k] = v
    s = pd.Series(np.nan, index=IDX)
    for k, v in (stop or {}).items():
        s.iloc[k] = v
    return pd.DataFrame(dict(target=t, stop=s))


def setup():
    data = {s: dict(kl=kl_of(i)) for i, s in enumerate("ABCD")}
    out = {"A": book({20: 500.0, 60: 0.0, 150: -400.0, 170: 0.0}),
           "B": book({100: 300.0, 130: 0.0}, stop={100: 90.0, 101: 90.0}),
           "C": book({5: 0.0}),                      # hep düz
           "D": book({0: 0.0, 200: 250.0})}          # sonda açılır, pencere sonunda açık
    return out, data


@pytest.mark.parametrize("delay", [0, 1])
def test_trim_flat_is_result_neutral(delay):
    out, data = setup()
    sp = referee.Spec(tick="0.01", step="0.001", capital=10000.0, liq=True, fee_rt_bps=10.0, slip_rt_bps=2.0, delay=delay, gross_cap=30000.0)
    lo, hi = IDX[0], IDX[-1] + pd.Timedelta("1h")
    r0, w0, _ = ev.run_book(out, data, sp, lo, hi)
    r1, w1, _ = ev.run_book(out, data, sp, lo, hi, trim_flat=True)
    assert "C" not in w1 and len(w1["A"]["kl"]) < N          # kırpma gerçekten oldu
    pd.testing.assert_frame_equal(r0["fills"].reset_index(drop=True), r1["fills"].reset_index(drop=True))
    for k in ("net_pnl", "gross_pnl", "fee", "slippage", "funding", "exit_cost", "n_fills"):
        assert r0["summary"][k] == r1["summary"][k], k
    p0, p1 = report.book_pnl(w0, r0, sp), report.book_pnl(w1, r1, sp)
    assert p1.reindex(p0.index).fillna(0.0).round(9).equals(p0.round(9))
    assert p0.sum() == pytest.approx(r0["summary"]["net_pnl"], abs=1e-6) and p1.sum() == pytest.approx(r1["summary"]["net_pnl"], abs=1e-6)


def test_trim_flat_rejects_kill_dd():
    out, data = setup()
    with pytest.raises(ValueError):
        ev.run_book(out, data, referee.Spec(capital=10000.0), IDX[0], IDX[-1], kill_dd=0.1, trim_flat=True)


@pytest.mark.parametrize("partial_mark", [False, True])
def test_trimming_keeps_original_funding_fallback_prices(partial_mark):
    out, data = setup()
    for d in data.values():
        d["funding"] = pd.DataFrame(dict(last_funding_rate=.0001), index=IDX[8::8])
        if partial_mark:
            d["mark"] = d["kl"].drop(IDX[79])  # inactive funding T80 needs original kline fallback
    sp = referee.Spec(tick=".01", capital=10000., fee_rt_bps=10., slip_rt_bps=2.)
    r0, _, _ = ev.run_book(out, data, sp, IDX[0], IDX[-1] + pd.Timedelta("1h"))
    r1, w1, _ = ev.run_book(out, data, sp, IDX[0], IDX[-1] + pd.Timedelta("1h"), trim_flat=True)
    assert r0["summary"]["funding_missed"] == r1["summary"]["funding_missed"] == 0
    assert r0["summary"]["funding"] == pytest.approx(r1["summary"]["funding"], abs=1e-12)
    pd.testing.assert_frame_equal(r0["fills"], r1["fills"])
    assert report.reconcile(w1, r1, sp)["ok"]
    if partial_mark:
        assert r1["summary"]["funding_mark_fallback"] > 0


def test_referee_is_silent(capfd):
    data = {"A": dict(kl=kl_of(0), target=book({3: 500.0, 20: 0.0}).target.ffill().fillna(0.0))}
    referee.run_portfolio(data, referee.Spec(tick="0.01", step="0.001", capital=10000.0))
    cap = capfd.readouterr()
    assert "[INFO]" not in cap.out + cap.err and cap.out.strip() == ""


def test_entirely_flat_book_remains_a_valid_zero_trade_account():
    out = {"C": book({0: 0.})}
    data = {"C": dict(kl=kl_of(0))}
    sp = referee.Spec(capital=1000., liq=True, fee_rt_bps=10., slip_rt_bps=2.)
    r0, _, _ = ev.run_book(out, data, sp, IDX[0], IDX[-1] + pd.Timedelta("1h"))
    r1, _, _ = ev.run_book(out, data, sp, IDX[0], IDX[-1] + pd.Timedelta("1h"), trim_flat=True)
    assert r1["summary"] == r0["summary"] and r1["summary"]["n_fills"] == 0
