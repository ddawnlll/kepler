"""Likidasyon tetiği MARK fiyatıyla; 10x (sermaye 500, notional 5000) Binance-benzeri mmr 0.5% ile gerçekten tetikleniyor.

Elle hesap (yan fee 5 bps, giriş fee 2.5 => WB 497.5):
  long  50@100: LP = (q*E - WB) / (q*(1-mmr)) = (5000-497.5)/(50*0.995) = 90.5025 -> 90.50
  short 50@100: LP = (WB + s*E) / (s*(1+mmr)) = (497.5+5000)/(50*1.005) = 109.4030 -> 109.40
"""
import pytest

from kepler.referee import run
from tests.test_referee import A, bars, spec, tgt

X10 = dict(capital=500.0, leverage=10, mmr=0.005, liq=True, liq_fee_rate=0.0)
FLAT = (100, 100, 100, 100)


def case(last_rows, mark_rows, target):
    kl, mk = bars([100] * 3, rows=last_rows), bars([100] * 3, rows=mark_rows)
    return run(kl, tgt(kl, b0=target), spec(**X10), mark=mk)


def test_scenario_is_really_10x():
    assert 5000.0 / X10["capital"] == 10.0


def test_long_10x_liquidated_when_mark_crosses_even_if_last_does_not():
    r = case([FLAT, (100, 100, 91, 95), FLAT], [FLAT, (100, 100, 90.0, 95), FLAT], 5000.0)  # mark düşüğü 90 <= 90.50; son fiyat 91
    f = r["fills"]
    assert list(f.liq) == [False, True] and f.qty.iloc[0] == A(50.0) and f.px.iloc[1] == A(90.50)
    # kayıp -(100-90.5)*50 = -475; fee 2.5 + 50*90.5*0.0005 = 2.2625
    assert r["summary"]["net_pnl"] == A(-479.7625) and r["summary"]["n_liq"] == 1 and r["summary"]["end_position"] == 0


def test_long_10x_not_liquidated_when_only_last_price_crosses():
    r = case([FLAT, (100, 100, 89, 95), FLAT], [FLAT, (100, 100, 91.0, 95), FLAT], 5000.0)  # son fiyat 89 < LP ama mark 91 > LP
    assert r["summary"]["n_liq"] == 0 and r["summary"]["end_position"] == A(50.0)


def test_short_10x_liquidated_by_mark_high():
    r = case([FLAT, (100, 108, 100, 105), FLAT], [FLAT, (100, 110.0, 100, 105), FLAT], -5000.0)
    f = r["fills"]
    assert list(f.liq) == [False, True] and f.px.iloc[1] == A(109.40)
    assert r["summary"]["net_pnl"] == A(-(109.40 - 100) * 50 - 2.5 - 50 * 109.40 * 0.0005)  # -475.235


def test_short_10x_not_liquidated_when_only_last_price_crosses():
    r = case([FLAT, (100, 112, 100, 105), FLAT], [FLAT, (100, 108.0, 100, 105), FLAT], -5000.0)
    assert r["summary"]["n_liq"] == 0 and r["summary"]["end_position"] == A(-50.0)


def test_missing_mark_bar_falls_back_to_kline_extremes():
    kl = bars([100] * 3, rows=[FLAT, (100, 100, 89, 95), FLAT])
    mk = bars([100] * 3, rows=[FLAT, (100, 100, 100, 100), FLAT]).drop(kl.index[1])  # 2. barın mark'ı yok
    r = run(kl, tgt(kl, b0=5000.0), spec(**X10), mark=mk)
    assert r["summary"]["n_liq"] == 1  # kline düşüğü 89 < 90.50


@pytest.mark.parametrize("lev", [10])
def test_liquidation_price_is_about_one_over_leverage_minus_mmr_away(lev):
    # %10 ters hareket (1/lev) bakım marjı payı (%0.5) kadar eksik: LP ~ -%9.5
    assert (100 - 90.50) / 100 == A(1 / lev - X10["mmr"], abs=2e-3)
