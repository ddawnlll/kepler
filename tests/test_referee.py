"""C2: bilinen-cevaplı testler. Beklenen her değer ELLE hesaplanıp yazıldı (motor çıktısıyla karşılaştırma yok).

Ortak: fiyat 100, hedef notional 100 -> miktar 1.000; lot 0.001, tick 0.01; sermaye 10000; yan başına fee = gidiş-dönüş/2.
"""
import numpy as np
import pandas as pd
import pytest

from kepler.referee import Spec, run

A = pytest.approx


def bars(closes, rows=None):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="1h", tz="UTC")
    c = np.array(closes, float)
    d = dict(open=c.copy(), high=c.copy(), low=c.copy(), close=c.copy(), volume=1000.0)
    for k, (o, h, l, cl) in enumerate(rows or []):  # (i, ohlc) yerine tam satır listesi
        d["open"][k], d["high"][k], d["low"][k], d["close"][k] = o, h, l, cl
    return pd.DataFrame(d, index=idx)


def tgt(kl, **at):
    s = pd.Series(np.nan, index=kl.index)
    for k, v in at.items():
        s.iloc[int(k[1:])] = v  # b3=100.0 -> 3. bar
    return s


def spec(**kw):
    return Spec(**{**dict(tick="0.01", step="0.001", capital=10000.0, liq=False, fee_rt_bps=10.0, slip_rt_bps=0.0, fill_mode="close"), **kw})


def test_long_round_trip():
    kl = bars([100, 100, 110, 110])
    r = run(kl, tgt(kl, b0=100.0, b2=0.0), spec())
    s = r["summary"]
    assert list(r["fills"].qty) == [1.0, 1.0] and list(r["fills"].px) == [100.0, 110.0]
    assert s["gross_pnl"] == A(10.0) and s["fee"] == A(0.105) and s["net_pnl"] == A(9.895)  # 5bps*(100+110)
    assert s["end_position"] == 0 and r["rejected"] == []


def test_short_round_trip():
    kl = bars([100, 100, 90, 90])
    s = run(kl, tgt(kl, b0=-100.0, b2=0.0), spec())["summary"]
    assert s["gross_pnl"] == A(10.0) and s["fee"] == A(0.095) and s["net_pnl"] == A(9.905)  # 5bps*(100+90)


def test_open_position_is_marked_to_last_close():
    kl = bars([100, 100, 110])
    s = run(kl, tgt(kl, b0=100.0), spec())["summary"]
    assert s["end_position"] == 1.0 and s["net_pnl"] == A(10.0 - 0.05 - 0.055)  # realize edilmemiş +10, giriş ve tahmini çıkış fee'si


@pytest.mark.parametrize("rt,expect", [(4, -0.04), (9, -0.09), (10, -0.10), (11, -0.11), (16, -0.16)])
def test_round_trip_fee_bps(rt, expect):
    kl = bars([100, 100, 100])
    s = run(kl, tgt(kl, b0=100.0, b1=0.0), spec(fee_rt_bps=rt))["summary"]  # fiyat sabit: net = -rt/1e4 * 100 (toplam notional 200 * rt/2)
    assert s["net_pnl"] == A(expect, abs=1e-9) and s["fee"] == A(-expect)


def test_slippage_is_separate_from_fee():
    kl = bars([100, 100, 100])
    s = run(kl, tgt(kl, b0=100.0, b1=0.0), spec(fee_rt_bps=10, slip_rt_bps=6))["summary"]
    assert s["fee"] == A(0.10) and s["slippage"] == A(0.06) and s["net_pnl"] == A(-0.16)
    assert s["engine_commission"] == A(0.16)  # motor komisyonu = fee + slippage (tutarlılık)


def test_lot_step_rounds_down():
    kl = bars([100, 100])
    f = run(kl, tgt(kl, b0=123.456), spec())["fills"]
    assert list(f.qty) == [1.234]  # 1.23456 -> 1.234


def test_min_notional_blocks_small_orders_but_not_reductions():
    kl = bars([100] * 5)
    assert run(kl, tgt(kl, b0=0.4), spec())["fills"].empty  # 0.004 adet = 0.4 < 5
    f = run(kl, tgt(kl, b0=100.0, b1=100.5, b2=99.5), spec())["fills"]
    # b1: +0.005 adet = 0.5 USDT < 5 -> atlanır; b2: -0.005 azaltma -> min notional muaf
    assert list(f.qty) == [1.0, 0.005] and list(f.side) == ["BUY", "SELL"]


def test_nan_target_holds_position():
    kl = bars([100, 100, 120, 130, 130])
    r = run(kl, tgt(kl, b0=100.0, b4=0.0), spec())  # b1..b3 NaN: pozisyon tutulur
    assert list(r["fills"].qty) == [1.0, 1.0] and r["summary"]["gross_pnl"] == A(30.0)
    assert run(kl, tgt(kl), spec())["fills"].empty  # hep NaN: hiç işlem yok


def test_flip_long_to_short():
    kl = bars([100, 110, 100])
    r = run(kl, tgt(kl, b0=100.0, b1=-100.0, b2=0.0), spec())
    # b1: hedef -100/110 -> -0.909; delta = -1.909 (tek emirde çevirme). b2: 0.909 geri alınır.
    assert list(r["fills"].qty) == [1.0, 1.909, 0.909] and list(r["fills"].side) == ["BUY", "SELL", "BUY"]
    s = r["summary"]
    assert s["gross_pnl"] == A(10 + 0.909 * 10) and s["fee"] == A((100 + 1.909 * 110 + 0.909 * 100) * 0.0005)
    assert s["net_pnl"] == A(19.09 - 0.200445)


# ---- funding: T=08:00 UTC, bar i'nin kapanışı (i+1):00. Mark 102 (kline kapanışından farklı), oran ±.
def fund_case(rate, **t):
    kl = bars([100] * 12)
    mark = kl.assign(close=102.0)
    f = pd.DataFrame({"last_funding_rate": [rate]}, index=[pd.Timestamp("2024-01-01 08:00:00.005", tz="UTC")])  # ms sapması
    return run(kl, tgt(kl, **t), spec(fee_rt_bps=0), funding=f, mark=mark)["summary"]


def test_funding_long_pays_positive_rate_uses_mark():
    s = fund_case(0.0001, b0=100.0, b9=0.0)  # 01:00'de aç, 10:00'da kapat, 08:00'i aşıyor
    assert s["funding"] == A(-1.0 * 102 * 0.0001) and s["net_pnl"] == A(-0.0102)


def test_funding_long_receives_negative_rate():
    assert fund_case(-0.0002, b0=100.0, b9=0.0)["funding"] == A(+0.0204)


def test_funding_short_receives_positive_rate():
    assert fund_case(0.0001, b0=-100.0, b9=0.0)["funding"] == A(+0.0102)


def test_funding_not_charged_when_not_crossing():
    assert fund_case(0.0001, b0=100.0, b5=0.0)["funding"] == 0  # 06:00'da kapanır, 08:00'e ulaşmaz


@pytest.mark.parametrize("name,t,charged", [
    ("07:00'de açılır (08:00'den önce) -> ödenir", dict(b6=100.0, b9=0.0), True),
    ("07:00'de kapanır (08:00'den önce) -> ödenmez", dict(b0=100.0, b6=0.0), False),
    ("tam 08:00'de kapanır -> T öncesi pozisyon tutulmuş sayılır, ödenir", dict(b0=100.0, b7=0.0), True),
    ("tam 08:00'de açılır -> T anında pozisyon yoktu, ödenmez", dict(b7=100.0, b9=0.0), False),
])
def test_funding_boundary_convention(name, t, charged):
    # Kural (LIKELY, Binance SSS'nin özeti: funding anında pozisyon tutuluyorsa; ~1 dk sapma olabilir): T'de yapılan
    # dolumlar settlement'tan SONRA kabul edilir. Sınır 1 saatlik barla çözülemez; bu sabit bir kabuldür.
    assert (fund_case(0.0001, **t)["funding"] != 0) is charged, name


# ---- likidasyon: sermaye 1000, 100 adet @100 (notional 10000), mmr 5%, yan fee 5bps => WB=995 (giriş fee'sinden sonra)
LIQ = dict(capital=1000.0, liq=True, mmr=0.05, liq_fee_rate=0.0)


def crash(low, high=100.0):
    return bars([100, 100, 100], rows=[(100, 100, 100, 100), (100, high, low, 100.0), (100, 100, 100, 100)])


def test_long_liquidated_at_formula_price_intrabar():
    # LP = (q*E - WB) / (q*(1-mmr)) = (10000-995)/(100*0.95) = 94.7894.. -> tick 94.79
    kl = crash(94.0)
    r = run(kl, tgt(kl, b0=10000.0), spec(**LIQ))
    f = r["fills"]
    assert list(f.liq) == [False, True] and f.px.iloc[1] == A(94.79) and f.qty.iloc[1] == A(100.0)
    assert r["summary"]["n_liq"] == 1 and r["summary"]["end_position"] == 0
    # Likidasyon çıkış ücreti açıkça 0; taker yerine geçer: -521 - 5 = -526
    assert r["summary"]["net_pnl"] == A(-526.0)


def test_long_not_liquidated_above_lp():
    kl = crash(95.0)  # düşük 95 > 94.79
    r = run(kl, tgt(kl, b0=10000.0), spec(**LIQ))
    assert r["summary"]["n_liq"] == 0 and r["summary"]["end_position"] == A(100.0)


def test_short_liquidated_at_formula_price():
    # LP = (WB + s*E) / (s*(1+mmr)) = (995+10000)/(100*1.05) = 104.7142.. -> 104.71
    kl = crash(100.0, high=106.0)
    r = run(kl, tgt(kl, b0=-10000.0), spec(**LIQ))
    assert r["fills"].px.iloc[1] == A(104.71) and r["summary"]["n_liq"] == 1
    assert r["summary"]["net_pnl"] == A(-476.0)  # -471 brüt -5 giriş; likidasyon çıkış ücreti 0


def test_liquidation_fee_default_is_mmr_of_notional():
    kl = crash(94.0)
    s = run(kl, tgt(kl, b0=10000.0), spec(**{**LIQ, "liq_fee_rate": None}))["summary"]
    assert s["liq_fee"] == A(100 * 94.79 * 0.05) and s["net_pnl"] == A(-999.95)  # -521 brüt -5 giriş -473.95 likidasyon; ikinci çıkış fee yok


def test_nautilus_alone_does_not_liquidate():
    """Nautilus 2.0.0rc5: liquidation_enabled=True olsa bile bar verisinde likidasyon olmaz (bizim stop'suz).
    Bu testin geçmesi, yapıştırma likidasyon stopunun GEREKLİ olduğunu belgeler."""
    kl = bars([100, 100, 90, 90], rows=[(100, 100, 100, 100), (100, 100, 60, 90), (90, 90, 90, 90), (90, 90, 90, 90)])
    r = run(kl, tgt(kl, b0=10000.0), spec(capital=1000.0, liq=False, native_liq=True))
    assert r["summary"]["n_liq"] == 0 and r["summary"]["end_position"] == A(100.0)
    assert r["summary"]["net_pnl"] < -1000  # özsermaye negatif, pozisyon hâlâ açık
