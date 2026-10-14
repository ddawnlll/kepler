"""#11: niyet → hedef → emir → dolum izi ve PnL mutabakatı. Beklenenler ELLE hesaplı."""
import numpy as np
import pandas as pd
import pytest

from kepler import report
from kepler.referee import Spec, run, run_portfolio

A = pytest.approx


def bars(n=12, px=100.0, drop=()):
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    c = np.full(n, px)
    kl = pd.DataFrame(dict(open=c, high=c, low=c, close=c, volume=1e6), index=idx)
    return kl.drop(kl.index[list(drop)]) if drop else kl


def tgt(kl, **at):
    s = pd.Series(np.nan, index=kl.index)
    for k, v in at.items():
        s.iloc[int(k[1:])] = v
    return s


SP = Spec(capital=10000.0, fee_rt_bps=10.0, tick="0.1", step="0.001", fill="next_open", liq=False)


def test_e04_blocked_minimum_is_recorded_not_silent():
    kl = bars()
    r = run(kl, tgt(kl, b0=100.0, b3=100.4), SP)  # 1 birim; hedef 100,4 -> delta 0,004 birim = 0,40 USDT < 5 minimum
    s, it = r["summary"], r["intents"]
    assert list(it.status) == ["sent", "blocked_minimum"] and s["n_rejected"] == 0 and s["n_fills"] == 1
    assert s["n_blocked_minimum"] == 1 and s["blocked_notional"] == A(0.4) and it.iloc[1].gap_notional == A(0.4)  # 100,4 - 1,000*100


def test_lot_noop_and_partial_not_equal_counts():
    kl = bars()
    r = run(kl, tgt(kl, b0=100.0, b3=100.04), SP)  # 100,04/100 = 1,0004 -> lot 0,001 aşağı = 1,000: delta 0
    assert list(r["intents"].status) == ["sent", "noop_lot"] and r["summary"]["n_noop_lot"] == 1
    assert r["summary"]["n_fills"] == 1  # niyet sayısı (2) dolum sayısına (1) eşit olmak zorunda değil


def test_sent_intent_fills_traced():
    kl = bars()
    r = run(kl, tgt(kl, b0=100.0, b4=0.0), SP)
    it = r["intents"]
    assert list(it.status) == ["sent", "sent"] and list(it.filled_qty) == A([1.0, 1.0]) and r["summary"]["n_engine_unfilled"] == 0


def test_reconcile_basic_gap_and_flat_hours():
    kl = bars(14, drop=[7])  # 07:00 barı yok (boşluk)
    f = pd.DataFrame({"last_funding_rate": [0.0001, 0.0002, 0.0001]}, index=[pd.Timestamp(f"2024-01-01 {h:02d}:00", tz="UTC") for h in (4, 8, 12)])  # 08:00 boşlukta (07:00 barının kapanışı)
    sp = Spec(capital=10000.0, fee_rt_bps=10.0, slip_rt_bps=2.0, tick="0.1", step="0.001", fill="next_open", liq=False)
    d = {"X": dict(kl=kl, target=tgt(kl, b0=1000.0, b9=0.0), funding=f, mark=kl)}
    r = run_portfolio(d, sp)
    rc = report.reconcile(d, r, sp)
    assert rc["ok"], rc
    # elle: açık 10 birim 02:00 -> kapanış; funding 04:00 ve 12:00 (pozisyon kapalı olabilir) — toplam mutabakatı yeterli, ayrıca boş saatlerde funding sıfır pozisyonla sıfır
    assert r["summary"]["funding_missed"] == 1  # 08:00: ne mark ne kline barı var -> sessiz atlanmaz, sayılır; mutabakat yine tutar


def test_reconcile_open_position_exit_valuation_and_missed_detected():
    kl = bars(10)
    sp = Spec(capital=10000.0, fee_rt_bps=10.0, slip_rt_bps=2.0, tick="0.1", step="0.001", fill="next_open", liq=False)
    d = {"X": dict(kl=kl, target=tgt(kl, b0=1000.0), funding=pd.DataFrame({"last_funding_rate": [0.0003]}, index=[pd.Timestamp("2024-01-01 10:00", tz="UTC")]), mark=kl)}  # son kapanış T: dahil
    r = run_portfolio(d, sp)
    rc = report.reconcile(d, r, sp)
    assert rc["ok"] and r["summary"]["funding"] == A(-10.0 * 100 * 0.0003)  # 10 birim x 100 x 0,0003 = 0,3
    assert abs(rc["diff"]) < 1e-9
    broken = dict(r, summary=dict(r["summary"], net_pnl=r["summary"]["net_pnl"] + 1.0))  # muhasebe ayrışırsa sessiz geçmez
    assert not report.reconcile(d, broken, sp)["ok"]
