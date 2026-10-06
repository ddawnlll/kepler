"""scripts/trade_audit.py::episodes: pozisyon dönemi (sıfırdan sıfıra / çevirme) ve maliyet/MAE/MFE kalemleri, beklenen değerler elle."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("trade_audit", ROOT / "scripts" / "trade_audit.py")
ta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ta)

H = pd.date_range("2024-01-01", periods=6, freq="1h", tz="UTC")
NS = lambda i: int(H[i].value)  # noqa: E731


def hourly(close, high=None, low=None, funding=0.0, exit_=0.0):
    c = pd.Series(close, index=H, dtype=float)
    return pd.DataFrame(dict(pos=0.0, close=c, high=c if high is None else pd.Series(high, index=H), low=c if low is None else pd.Series(low, index=H), funding=funding, exit=exit_, net=0.0, commission=0.0, price=0.0))


def fills(rows):
    return pd.DataFrame(rows, columns=["ts", "side", "qty", "px", "commission", "liq", "stop"]).assign(sym="X")


def test_long_add_then_close_is_one_episode():
    # BUY 2 @100, BUY 1 @110, SELL 3 @120: nakit = -200 - 110 + 360 = 50; VWAP giriş = 310/3 = 103,3333; brüt = (120/103,3333 - 1) = %16,129
    f = fills([(NS(0), "BUY", 2.0, 100.0, 0.1, False, False), (NS(1), "BUY", 1.0, 110.0, 0.1, False, False), (NS(3), "SELL", 3.0, 120.0, 0.3, False, False)])
    h = hourly([100, 105, 110, 115, 120, 120], high=[101, 106, 112, 125, 121, 121], low=[99, 104, 108, 114, 119, 119])
    r = ta.episodes("X", f, h, pd.Series(1000.0, index=H))
    assert len(r) == 1
    e = r[0]
    assert e["side"] == "long" and e["n_fills"] == 3
    assert e["price_pnl"] == pytest.approx(50.0) and e["commission"] == pytest.approx(0.5) and e["net"] == pytest.approx(49.5)
    assert e["vwap_in"] == pytest.approx(310 / 3) and e["gross_bps"] == pytest.approx((120 / (310 / 3) - 1) * 1e4)
    assert e["mfe_bps"] == pytest.approx((125 / (310 / 3) - 1) * 1e4)  # saatlik en yüksek 125 (bar 3)
    assert e["mae_bps"] == pytest.approx((99 / (310 / 3) - 1) * 1e4)  # en düşük 99 (bar 0)
    assert e["max_notional"] == pytest.approx(3 * 110.0)  # 3 birim @ son dolum 110


def test_flip_splits_commission_and_opens_new_episode():
    # SELL 2 @100 (short), BUY 5 @90 (2 kapatır + 3 long açar). Short PnL = 2·(100-90) = 20. Komisyon BUY: 0,5 -> kapanan 2/5 = 0,2; yeni 3/5 = 0,3
    f = fills([(NS(0), "SELL", 2.0, 100.0, 0.1, False, False), (NS(2), "BUY", 5.0, 90.0, 0.5, False, False)])
    h = hourly([100, 95, 90, 91, 92, 93], exit_=pd.Series([0, 0, 0, 0, 0, 0.07], index=H))
    r = ta.episodes("X", f, h, pd.Series(1000.0, index=H))
    assert [e["side"] for e in r] == ["short", "long"]
    s, lg = r
    assert s["price_pnl"] == pytest.approx(20.0) and s["commission"] == pytest.approx(0.3) and s["net"] == pytest.approx(19.7)
    assert lg["open_at_end"] and lg["commission"] == pytest.approx(0.3)
    # açık kalan long 3 @90, son kapanış 93: değerleme = -3·90 + 3·93 = 9; çıkış maliyeti 0,07
    assert lg["price_pnl"] == pytest.approx(9.0) and lg["exit_cost"] == pytest.approx(0.07) and lg["net"] == pytest.approx(9.0 - 0.3 - 0.07)


def test_funding_only_counted_while_position_open():
    f = fills([(NS(1), "BUY", 1.0, 100.0, 0.0, False, False), (NS(4), "SELL", 1.0, 100.0, 0.0, False, False)])
    h = hourly([100] * 6, funding=pd.Series([-9.0, -1.0, -2.0, -3.0, -4.0, -9.0], index=H))  # bar 1,2,3 pozisyon açık (bar başında); bar 0, 4, 5 dışarıda
    e = ta.episodes("X", f, h, pd.Series(1000.0, index=H))[0]
    assert e["funding"] == pytest.approx(-1.0 - 2.0 - 3.0) and e["net"] == pytest.approx(-6.0)
    assert np.isclose(e["hours"], 3.0)
