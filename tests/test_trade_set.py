"""carryxs_card.trade_set: hakeme yalnızca pencerede hedefi/stop'u olan semboller verilir (issue #29). Saf pandas; Modal'siz koşar."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def _trade_set():
    # carryxs_card Nautilus/duckdb'ye bağlı içe aktarmalar yapar; Modal'siz ortamda atla
    import pytest
    pytest.importorskip("nautilus_trader")
    import carryxs_card
    return carryxs_card.trade_set


def book(idx, target, stop=None):
    return pd.DataFrame(dict(target=pd.Series(target, index=idx, dtype=float), stop=pd.Series(np.nan if stop is None else stop, index=idx, dtype=float)))


def test_flat_symbols_dropped_only_when_flat_in_window():
    ts = _trade_set()
    idx = pd.date_range("2021-01-01", periods=96, freq="1h", tz="UTC")
    kl = pd.DataFrame(dict(close=1.0), index=idx)
    data = {s: dict(kl=kl) for s in "ABCD"}
    t_a = np.full(96, np.nan); t_a[10] = 0.0                     # yalnız 0 ve NaN: düz
    t_b = np.full(96, np.nan); t_b[50] = 100.0                   # pencerede pozisyon açıyor
    t_c = np.full(96, np.nan); t_c[5] = 100.0; t_c[30] = 0.0     # pencere dışında (öncesi) pozisyon: ffill ile pencereye taşınıyor
    out = {"A": book(idx, t_a), "B": book(idx, t_b), "C": book(idx, t_c), "D": book(idx, np.full(96, np.nan), stop=np.where(np.arange(96) == 60, 9.0, np.nan))}
    lo, hi = idx[40], idx[96 - 1]
    kept = ts(out, data, lo, hi)
    assert set(kept) == {"B", "D"}    # A düz; C pencerede 0 (30. barda kapandı, pencere 40'ta başlıyor); B hedefli; D stop'lu
    kept_all = ts(out, data, idx[0], idx[-1] + pd.Timedelta("1h"))
    assert set(kept_all) == {"B", "C", "D"}   # C pencerenin başında hedefli
