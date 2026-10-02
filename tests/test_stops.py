"""Strateji stopu (BACKTEST.md §6.4, §12.2 madde 1-8). Beklenen değerler ELLE: fiyat 100, hedef notional 1000 -> 10.000 adet.
Slippage komisyon olarak sayılır (fee+slip)/2 yan başına; stop fiyatı değil maliyet kalemi. Kararlar b0'da, ilk dolum b1 açılışı."""
import numpy as np
import pandas as pd

from kepler import audit
from kepler.referee import Spec, run
from tests.test_referee import A, bars

FLAT = (100, 100, 100, 100)


def sp(**kw):
    return Spec(**{**dict(tick="0.01", step="0.001", capital=10000.0, liq=False, fee_rt_bps=10.0, slip_rt_bps=6.0), **kw})  # yan başına 8 bps


def series(kl, **at):
    s = pd.Series(np.nan, index=kl.index)
    for k, v in at.items():
        s.iloc[int(k[1:])] = v
    return s


def scen(rows, target, stop_lvl, **kw):
    kl = bars([100] * len(rows), rows=rows)
    stop = pd.Series(stop_lvl, index=kl.index) if np.isscalar(stop_lvl) else stop_lvl
    return run(kl, series(kl, **target), sp(**kw), stop=stop)


def test_long_stop_fills_at_stop_price_inside_bar():
    r = scen([FLAT, FLAT, (99, 100, 94, 96), FLAT], dict(b0=1000.0), 95.0)  # b2: açılış 99 > stop, düşük 94 < 95
    f, s = r["fills"], r["summary"]
    assert list(f.px) == [100.0, 95.0] and list(f.stop) == [False, True] and s["n_stop"] == 1 and s["end_position"] == 0
    assert s["gross_pnl"] == A(-50.0) and s["fee"] == A(0.0005 * 1950) and s["slippage"] == A(0.0003 * 1950)
    assert s["net_pnl"] == A(-50.0 - 0.0008 * 1950)  # = -51.56


def test_long_gap_through_stop_fills_at_open_not_at_stop():
    r = scen([FLAT, FLAT, (90, 91, 89, 90), FLAT], dict(b0=1000.0), 95.0)
    assert list(r["fills"].px) == [100.0, 90.0] and r["summary"]["gross_pnl"] == A(-100.0) and r["summary"]["net_pnl"] == A(-100.0 - 0.0008 * 1900)


def test_short_stop_and_gap_mirror():
    r = scen([FLAT, FLAT, (101, 106, 100, 104), FLAT], dict(b0=-1000.0), 105.0)
    assert list(r["fills"].px) == [100.0, 105.0] and r["summary"]["gross_pnl"] == A(-50.0) and r["summary"]["net_pnl"] == A(-50.0 - 0.0008 * 2050)
    r = scen([FLAT, FLAT, (110, 111, 109, 110), FLAT], dict(b0=-1000.0), 105.0)
    assert list(r["fills"].px) == [100.0, 110.0] and r["summary"]["gross_pnl"] == A(-100.0)


def test_entry_and_stop_in_the_same_bar():
    r = scen([FLAT, (100, 101, 94, 96), FLAT], dict(b0=1000.0), 95.0)  # giriş b1 açılışı 100, aynı barın gövdesi stopu geçer
    f = r["fills"]
    assert list(f.px) == [100.0, 95.0] and list(f.ts)[0] // 3_600_000_000_000 == list(f.ts)[1] // 3_600_000_000_000 and r["summary"]["gross_pnl"] == A(-50.0)


def test_stop_vs_liquidation_nearer_level_wins():
    # 1000 sermaye, 10x, 5000 notional = 50 adet @100, fee 2.5 -> WB 997.5; LP = (5000-997.5)/(50*0.995) = 80.4523 -> 80.45 (liq ücreti 0: yalnız motor fee'si)
    kw = dict(capital=1000.0, leverage=10, mmr=0.005, liq=True, liq_fee_rate=0.0, slip_rt_bps=0.0)
    rows = [FLAT, FLAT, (99, 99, 70, 80), FLAT]  # düşük 70 her iki seviyeyi de geçer
    r = scen(rows, dict(b0=5000.0), 95.0, **kw)  # stop (95) LP'den (80.45) yakın -> yalnız stop, hesap ölmez
    assert list(r["fills"].px) == [100.0, 95.0] and r["summary"]["n_stop"] == 1 and r["summary"]["n_liq"] == 0
    assert r["summary"]["net_pnl"] == A(-250.0 - 0.0005 * (5000 + 4750))
    r = scen(rows, dict(b0=5000.0), 75.0, **kw)  # stop LP'den uzak -> likidasyon önce
    assert list(r["fills"].px) == [100.0, 80.45] and r["summary"]["n_liq"] == 1 and r["summary"]["n_stop"] == 0
    assert r["summary"]["net_pnl"] == A(-19.55 * 50 - 0.0005 * (5000 + 50 * 80.45))


def test_no_reentry_after_stop_until_signal_reverses_or_flattens():
    rows = [FLAT, FLAT, (99, 100, 94, 96), FLAT, FLAT, FLAT, FLAT, FLAT, FLAT, FLAT]
    kl = bars([100] * len(rows), rows=rows)
    t = series(kl, b0=1000.0, b3=1500.0, b5=-1000.0, b7=0.0, b8=1000.0)  # b2'de stop; b3 aynı yön (artırma) yok sayılır; b5 ters -> short (b6 açılışı)
    r = run(kl, t, sp(), stop=pd.Series(np.where(np.arange(len(kl)) < 5, 95.0, np.nan), index=kl.index))
    f = r["fills"]
    assert list(f.side) == ["BUY", "SELL", "SELL", "BUY", "BUY"] and list(f.qty) == [10.0] * 5  # long, stop(b2), short(b6), kapat(b8), yeniden long(b9: flat kilidi açtı)
    assert list(f.stop) == [False, True, False, False, False]
    r2 = run(kl, series(kl, b0=1000.0, b3=1500.0, b4=0.0, b5=1000.0), sp(), stop=pd.Series(np.where(np.arange(len(kl)) < 5, 95.0, np.nan), index=kl.index))
    assert list(r2["fills"].side) == ["BUY", "SELL", "BUY"] and list(r2["fills"].qty) == [10.0, 10.0, 10.0]  # b4 flat kilidi açar, b5 yeniden long (b6 açılışı)


def leaky(kl):  # stop = ileri 3 barın en düşüğü: gelecek sızıntısı
    low = kl.low[::-1].rolling(3, min_periods=1).min()[::-1]
    return pd.DataFrame(dict(unit=1.0, stop=low))


def causal(kl):
    return pd.DataFrame(dict(unit=1.0, stop=kl.low.rolling(3, min_periods=1).min()))


def test_stop_level_causality_is_audited():
    rng = np.random.default_rng(1)
    c = 100 + rng.normal(0, 1, 200).cumsum()
    kl = pd.DataFrame(dict(open=c, high=c + 1, low=c - 1, close=c, volume=1000.0), index=pd.date_range("2024-01-01", periods=200, freq="1h", tz="UTC"))
    assert audit.check_causal(causal, kl) == []
    assert audit.check_causal(leaky, kl) != []


def test_stop_nan_everywhere_equals_no_stop_and_far_stop_changes_nothing():
    kl = bars([100, 100, 110, 110])
    t = series(kl, b0=100.0, b2=0.0)
    base = run(kl, t, Spec(tick="0.01", step="0.001", capital=10000.0, liq=False, fee_rt_bps=10.0, fill="close", close_out=False))
    nan = run(kl, t, Spec(tick="0.01", step="0.001", capital=10000.0, liq=False, fee_rt_bps=10.0, fill="close", close_out=False), stop=pd.Series(np.nan, index=kl.index))
    far = run(kl, t, Spec(tick="0.01", step="0.001", capital=10000.0, liq=False, fee_rt_bps=10.0, fill="close", close_out=False), stop=pd.Series(1.0, index=kl.index))
    for r in (base, nan, far):
        assert r["summary"]["net_pnl"] == A(9.895) and list(r["fills"].px) == [100.0, 110.0] and r["summary"]["n_stop"] == 0  # test_referee::test_long_round_trip ile aynı elle değer
