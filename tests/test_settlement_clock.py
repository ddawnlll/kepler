"""Shared funding clock regressions; expectations are independent hand calculations."""
import numpy as np
import pandas as pd
import pytest

from kepler import report
from kepler import referee, referee_core
from kepler.referee import Spec, run_portfolio


def bars(n=6):
    ix = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame(dict(open=100., high=100., low=100., close=100., volume=1e6), index=ix)


def item(kl, target, hour=2, rate=.02, mark=None):
    t = pd.Series(np.nan, index=kl.index)
    t.iloc[0] = target
    f = pd.DataFrame({"last_funding_rate": [rate]}, index=[kl.index[0] + pd.Timedelta(hours=hour)])
    return dict(kl=kl, target=t, funding=f, mark=mark if mark is not None else kl)


def test_same_timestamp_funding_uses_all_positions_before_any_liquidation():
    k = bars()
    a, b = item(k, 900), item(k, -900)
    sp = Spec(capital=110, fee_rt_bps=0, slip_rt_bps=0)
    x, y = (run_portfolio(d, sp) for d in ({"A": a, "B": b}, {"B": b, "A": a}))
    for r in (x, y):
        assert r["summary"]["funding"] == 0
        assert r["summary"]["n_liq"] == 0
        assert r["summary"]["net_pnl"] == pytest.approx(0)


def test_gap_in_funded_symbol_cannot_delay_other_symbols_equity_sizing():
    k = bars()
    a = item(k.drop(k.index[[2, 3]]), 900, hour=3, rate=.1, mark=k)
    t = pd.Series(np.nan, index=k.index)
    t.iloc[2] = 100
    b = dict(kl=k, target=t, mark=k)
    r = run_portfolio({"A": a, "B": b}, Spec(capital=1000, fee_rt_bps=0, slip_rt_bps=0, liq=False, equity_scale=True))
    assert r["summary"]["funding"] == pytest.approx(-90)
    assert r["fills"].loc[r["fills"].sym == "B", "qty"].iloc[0] == pytest.approx(.91)
    assert report.reconcile({"A": a, "B": b}, r, Spec(capital=1000, fee_rt_bps=0, slip_rt_bps=0, liq=False, equity_scale=True))["ok"]


def test_terminal_funding_liquidation_is_in_hourly_accounting():
    k = bars(4)
    d = {"A": item(k, 900, hour=4, rate=.12)}
    sp = Spec(capital=100, fee_rt_bps=10, slip_rt_bps=2)
    r = run_portfolio(d, sp)
    assert r["summary"]["net_pnl"] == pytest.approx(-113.04)
    assert report.reconcile(d, r, sp)["ok"]
    assert report.book_pnl(d, r, sp).index.max() == k.index[-1]


@pytest.mark.parametrize("step,qty", [("0.005", .01), ("0.025", 0)])
def test_quantity_is_a_multiple_of_effective_step(step, qty):
    k = bars()
    d = {"A": dict(item(k, 1.23, rate=0), step=step)}
    r = run_portfolio(d, Spec(capital=1000, fee_rt_bps=0, min_notional=0, liq=False))
    assert r["summary"]["end_position"] == pytest.approx(qty)


def test_custom_tick_is_respected():
    k = bars()
    k.loc[:, ["open", "high", "low", "close"]] = 100.2
    r = run_portfolio({"A": dict(item(k, 100, rate=0), tick="0.5")}, Spec(capital=1000, fee_rt_bps=0, liq=False))
    assert list(r["fills"].px) == [100.]


def test_all_observed_opening_prices_are_visible_to_equity_sizing():
    a, b = bars(), bars()
    b.loc[b.index[2]:, ["open", "high", "low", "close"]] = 200.
    at, bt = pd.Series(np.nan, index=a.index), pd.Series(np.nan, index=b.index)
    at.iloc[1], bt.iloc[0] = 100., 100.
    aa, bb = dict(kl=a, target=at), dict(kl=b, target=bt)
    sp = Spec(capital=1000, fee_rt_bps=0, slip_rt_bps=0, liq=False, equity_scale=True)
    for d in ({"A": aa, "B": bb}, {"B": bb, "A": aa}):
        r = run_portfolio(d, sp)
        assert r["fills"].loc[r["fills"].sym == "A", "qty"].iloc[0] == pytest.approx(1.1)


def kernel_with_capacity(data, sp, cap):
    pr = referee.prepare(data, sp)
    tg, st, p = referee._inputs(pr, sp)
    args = [pr[k] for k in ("ev_k", "ev_b", "ev_kind", "T0", "O", "H", "L", "C", "SZ")]
    arrays = [np.zeros((cap, 4), np.int64), np.zeros((cap, 3)), np.zeros((cap, 3), np.int64),
              np.zeros(cap), np.zeros((cap, 3), np.int64), np.zeros((cap, 3), np.int64), np.zeros((cap, 5))]
    return referee_core.simulate(*args, tg, st, pr["U"], p, cap, *[pr[k] for k in ("FK", "FT", "FC", "FR")], *arrays)[-1]


def test_all_symbol_liquidation_batch_reserves_space_before_writing():
    k = bars(4)
    data = {f"S{i:02}": dict(kl=k, target=pd.Series([100., np.nan, np.nan, np.nan], index=k.index)) for i in range(20)}
    data["S00"]["funding"] = item(k, 100, rate=100)["funding"]
    sp = Spec(capital=1000, fee_rt_bps=0, slip_rt_bps=0)
    assert kernel_with_capacity(data, sp, 32)[0] == -1
    assert kernel_with_capacity(data, sp, 512)[0] == 40


def test_many_settlement_times_inside_one_gap_reserve_rejection_capacity():
    mk = bars(52)
    mk.volume = .002
    mk.loc[mk.index[0], "volume"] = 1e6
    mk.loc[mk.index[1], ["high", "low"]] = [105., 95.]
    k = mk.iloc[[0, 1, 2, 50, 51]]
    data = {"A": dict(kl=k, mark=mk, target=pd.Series([100., np.nan, np.nan, np.nan, np.nan], index=k.index),
                      stop=pd.Series([np.nan, 98., 98., 98., 98.], index=k.index),
                      funding=pd.DataFrame(dict(last_funding_rate=.0001), index=mk.index[4:50]))}
    sp = Spec(capital=1000, liq=False, fee_rt_bps=0, slip_rt_bps=0)
    assert kernel_with_capacity(data, sp, 32)[0] == -1
    assert kernel_with_capacity(data, sp, 128)[2] == 47


def test_empty_mark_uses_original_kline_funding_price():
    k = bars(6)
    r = run_portfolio({"A": item(k, 100, hour=2, rate=.01, mark=k.iloc[:0])}, Spec(capital=1000, fee_rt_bps=0, liq=False))
    assert r["summary"]["funding"] == pytest.approx(-1.)
    assert r["summary"]["funding_mark_fallback"] == 1


@pytest.mark.parametrize("bad", ["0", 0, "-0.01", "inf"])
def test_invalid_quantity_rule_is_rejected(bad):
    k = bars()
    with pytest.raises(ValueError, match="tick/step"):
        run_portfolio({"A": dict(item(k, 100), step=bad)}, Spec(capital=1000))


def test_nonfinite_funding_rate_is_rejected():
    k = bars()
    with pytest.raises(ValueError, match="funding oranında"):
        run_portfolio({"A": item(k, 100, rate=np.inf)}, Spec(capital=1000))


def test_misaligned_protective_stop_is_rejected():
    k = bars()
    with pytest.raises(ValueError, match="aynı indekse"):
        run_portfolio({"A": dict(item(k, 100), stop=pd.Series(90., index=k.index + pd.Timedelta("1h")))}, Spec(capital=1000))
