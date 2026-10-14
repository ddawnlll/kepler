"""#10: funding settlement anında bakiyeye/marja/equity'ye uygulanır (tek kez). Beklenen değerler ELLE hesaplı.

E03: 24 saat sabit 100 fiyat, sermaye 100, ilk kararda 900 long (9 birim), fee 10bp + slip 2bp gidiş-dönüş (yan başına 6 bp), mmr 0,005, kaldıraç 10.
Funding +0,02 saat 2/4/6/8/10/12 (T = o saatin başı): her ödeme 9*100*0,02 = 18. Giriş fee'si 900*0,0006 = 0,54 -> bakiye 99,46.
k ödeme sonrası özsermaye 99,46 - 18k; bakım marjı 0,005*900 = 4,5. k=5: 9,46 > 4,5 (hayatta); k=6: -8,54 < 4,5 -> likidasyon.
"""
import numpy as np
import pandas as pd
import pytest

from kepler.referee import Spec, run

A = pytest.approx


def bars(n=24, px=100.0):
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    c = np.full(n, px)
    return pd.DataFrame(dict(open=c, high=c, low=c, close=c, volume=1e6), index=idx)


def tgt(kl, **at):
    s = pd.Series(np.nan, index=kl.index)
    for k, v in at.items():
        s.iloc[int(k[1:])] = v
    return s


def fund(hours, rate):
    return pd.DataFrame({"last_funding_rate": [rate] * len(hours)}, index=[pd.Timestamp(f"2024-01-01 {h:02d}:00", tz="UTC") for h in hours])


E03 = dict(capital=100.0, fee_rt_bps=10.0, slip_rt_bps=2.0, mmr=0.005, leverage=10, tick="0.1", step="0.001", fill="next_open")


def e03(rate=0.02, **kw):
    kl = bars()
    return run(kl, tgt(kl, b0=900.0), Spec(**{**E03, **kw}), funding=fund([2, 4, 6, 8, 10, 12], rate), mark=kl)


def test_e03_margin_violation_after_funding_liquidates_not_silent():
    r = e03()
    s = r["summary"]
    assert s["funding"] == A(-108.0) and s["n_liq"] == 1 and s["end_position"] == 0 and s["n_rejected"] == 0
    liq = r["fills"][r["fills"].liq]
    assert len(liq) == 1 and abs(liq.iloc[0].ts - int(pd.Timestamp("2024-01-01 12:00", tz="UTC").value)) <= 1  # gövde tiki T-1ns; 6. ödeme anında (özsermaye -8,54 < 4,5), 5. ödemede değil
    assert s["liq_fee"] == A(900 * (0.005 - 0.0006))  # 3,96
    assert s["net_pnl"] == A(-108.0 - 0.54 - 0.54 - 3.96)  # funding, giriş fee, çıkış fee, likidasyon ücreti farkı; fiyat PnL 0


def test_survives_when_equity_stays_above_maintenance():
    kl = bars()
    s = run(kl, tgt(kl, b0=900.0), Spec(**E03), funding=fund([2, 4, 6, 8, 10], 0.02), mark=kl)["summary"]  # 5 ödeme: özsermaye 9,46 > 4,5
    assert s["n_liq"] == 0 and s["end_position"] == A(9.0) and s["funding"] == A(-90.0)


def test_zero_funding_parity_and_no_double_count():
    kl = bars()
    a = run(kl, tgt(kl, b0=900.0, b10=0.0), Spec(**E03))
    b = run(kl, tgt(kl, b0=900.0, b10=0.0), Spec(**E03), funding=fund([2, 4], 0.0), mark=kl)
    assert b["summary"]["funding"] == 0 and a["summary"]["net_pnl"] == A(b["summary"]["net_pnl"])
    assert list(a["fills"].qty) == list(b["fills"].qty) and list(a["fills"].px) == list(b["fills"].px)
    c = run(kl, tgt(kl, b0=900.0, b10=0.0), Spec(**E03), funding=fund([4], 0.001), mark=kl)["summary"]  # tek ödeme: 9*100*0,001 = 0,9, bir kez
    assert c["funding"] == A(-0.9) and c["net_pnl"] == A(a["summary"]["net_pnl"] - 0.9)


def test_short_receives_and_raises_margin():
    kl = bars()
    s = run(kl, tgt(kl, b0=-900.0), Spec(**E03), funding=fund([2, 4, 6, 8, 10, 12], 0.02), mark=kl)["summary"]
    assert s["funding"] == A(108.0) and s["n_liq"] == 0 and s["end_position"] == A(-9.0)


def test_equity_scale_sees_funding():
    kl = bars()
    sp = Spec(capital=1000.0, fee_rt_bps=0.0, slip_rt_bps=0.0, tick="0.1", step="0.001", fill="next_open", equity_scale=True, liq=False)
    r = run(kl, tgt(kl, b0=500.0, b6=600.0), sp, funding=fund([3], 0.1), mark=kl)  # 5 birim, 3:00'de -50 -> equity 950; yeni hedef 600*0,95 = 570 -> 5,7 birim
    assert list(r["fills"].qty) == A([5.0, 0.7]) and r["summary"]["funding"] == A(-50.0)


def test_two_symbols_share_cash_flow():
    kl = bars()
    d = {s: dict(kl=kl, target=tgt(kl, b0=900.0), funding=fund([2, 4, 6, 8, 10, 12], 0.02), mark=kl) for s in ("AAA", "BBB")}
    from kepler.referee import run_portfolio
    s = run_portfolio(d, Spec(**{**E03, "capital": 1000.0}))["summary"]  # her sembol 9 birim; 6 ödeme x 2 sembol x 18; ortak 1000 sermaye hayatta kalır
    assert s["funding"] == A(-216.0) and s["n_liq"] == 0
