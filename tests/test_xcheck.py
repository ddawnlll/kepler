"""C5 aracının kendisi sentetik veride: hakem (Nautilus) ile bağımsız elle hesap işlem başına aynı net'i vermeli."""
import numpy as np
import pandas as pd
import pytest

from kepler import referee
from scripts import g1_real


@pytest.mark.parametrize("seed,n", [(1, 700), (2, 700)])
def test_referee_equals_independent_accounting(seed, n):
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    c = (30000 * np.exp(np.cumsum(np.random.default_rng(seed).normal(0, 0.006, n)))).round(1)
    kl = pd.DataFrame(dict(open=c, high=c, low=c, close=c, volume=100.0), index=idx)
    mark = kl.assign(close=(c * 1.0005).round(1))
    fund = pd.DataFrame({"last_funding_rate": np.random.default_rng(seed + 9).normal(1e-4, 2e-4, n // 8)},
                        index=pd.date_range("2024-01-01 00:00:00.004", periods=n // 8, freq="8h", tz="UTC"))
    tg = g1_real.mom(kl, 12)
    sp = referee.Spec(tick="0.1", step="0.001", min_notional=100.0, fee_rt_bps=10.0, capital=500.0, fill="close", close_out=False)
    r = referee.run(kl, tg, sp, funding=fund, mark=mark)
    trades, ifund, cur, imissed = g1_real.independent(kl, tg, fund, mark, sp)
    assert imissed == r["summary"]["funding_missed"] == 0
    if cur is not None:
        trades.append(cur)
    ref = r["positions"]
    assert len(trades) == len(ref) > 5 and r["summary"]["n_liq"] == 0 and r["rejected"] == []
    assert np.allclose(sorted(t["net"] for t in trades[:-1]), sorted(ref.realized.iloc[:-1]), atol=1e-6)  # son (açık) döngü hariç: işlem başına net
    assert r["summary"]["funding"] == pytest.approx(ifund, abs=1e-9)
