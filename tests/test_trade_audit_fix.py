"""scripts/trade_audit.py::components: funding, kline'da eksik T-1sa barı olsa da hakemle aynı kuralla ödenir (önceki saatlik yol bu olayları atlıyordu: mutabakat farkı); elle hesaplı."""
import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("trade_audit", ROOT / "scripts" / "trade_audit.py")
ta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ta)

from kepler import referee  # noqa: E402

H = pd.date_range("2024-01-01", periods=8, freq="1h", tz="UTC")


def frames(drop_kline_bar=None):
    c = pd.Series([100.0] * 8, index=H)
    kl = pd.DataFrame(dict(open=c, high=c + 1, low=c - 1, close=c, volume=1.0))
    mark = pd.DataFrame(dict(open=c, high=c + 1, low=c - 1, close=c + 2.0))  # mark kapanışı 102
    if drop_kline_bar is not None:
        kl = kl.drop(H[drop_kline_bar])
    fills = pd.DataFrame([(int(H[1].value), "BUY", 2.0, 100.0, 0.0, False, False)], columns=["ts", "side", "qty", "px", "commission", "liq", "stop"]).assign(sym="X")
    return kl, mark, fills


def funding_at(i, rate):
    return pd.DataFrame(dict(last_funding_rate=[rate]), index=pd.DatetimeIndex([H[i]]))  # T = bar i-1'in kapanışı


def test_funding_normal_bar():
    kl, mark, fills = frames()
    c = ta.components(kl, mark, funding_at(4, 0.001), fills, referee.Spec())
    # T = H[4]: poz 2 (bar 1'de açıldı), mark kapanışı (bar 3) 102: öder = 2 x 102 x 0,001 = 0,204
    assert c.funding.sum() == pytest.approx(-0.204) and c.funding[H[3]] == pytest.approx(-0.204)


def test_funding_when_previous_bar_missing_in_klines_is_still_paid():
    kl, mark, fills = frames(drop_kline_bar=3)  # kline'da bar 3 yok, mark'ta var
    c = ta.components(kl, mark, funding_at(4, 0.001), fills, referee.Spec())
    assert c.funding.sum() == pytest.approx(-0.204)  # eskiden 0 (atlanıyordu)
    assert c.funding[H[4]] == pytest.approx(-0.204)  # sonraki mevcut bara yazılır
