"""Xcheck: önce elle hesapla sabitle, sonra zaman eşleşmesi ve açık son döngü dahil toplamı denetle."""
import numpy as np
import pandas as pd
import pytest

from kepler import referee
from scripts import g1_real
from tests.test_referee import bars, tgt


def test_independent_and_referee_each_match_hand_calculated_gap_flip_and_open_tail():
    kl = bars([100, 120, 80, 90, 110], rows=[(100, 100, 100, 100), (110, 120, 110, 120),
                                           (100, 100, 80, 80), (95, 95, 90, 90), (105, 110, 105, 110)])
    mark = kl.assign(close=[102, 122, 82, 92, 112])
    fund = pd.DataFrame({"last_funding_rate": [0.0001, -0.0002, 0.0001]}, index=kl.index[[2, 3, 4]] + pd.to_timedelta([0, 0, 1], unit="h"))
    target = tgt(kl, b0=110.0, b1=-95.0, b2=0.0, b3=105.0, b4=-999.0)
    sp = referee.Spec(tick="0.01", step="0.001", fee_rt_bps=10.0, slip_rt_bps=6.0, liq=False, capital=10000)
    r = referee.run(kl, target, sp, funding=fund, mark=mark)
    trades, funding, cur, missed = g1_real.independent(kl, target, fund, mark, sp)
    # Bir adet long110→100: -10-.088-.08=-10.168.
    # .95 short100→95: 4.75-.076-.0722=4.6018.
    # Açık bir adet105→son110: 5-.084-.088=4.828; son b4 kararı dolmaz.
    assert [x["net"] for x in trades] == pytest.approx([-10.168, 4.6018])
    assert cur["net"] == pytest.approx(4.828)
    assert cur["closed"] is pd.NaT and missed == 0
    assert r["positions"].realized.iloc[:2].tolist() == pytest.approx([-10.168, 4.6018])
    assert r["fills"].px.tolist() == [110, 100, 95, 105]
    # T2 long1 *mark122 *+1bp=-.0122; T3 short.95 *mark82 *-2bp=-.01558;
    # terminal T5 long1 *mark112 *+1bp=-.0112; funding=-.03898.
    assert funding == pytest.approx(-0.03898)
    assert r["summary"]["funding"] == pytest.approx(-0.03898)
    assert r["summary"]["net_pnl"] == pytest.approx(-0.77718)  # -10.168+4.6018+4.828-.03898
    for ind, ref in zip([*trades, cur], r["positions"].itertuples(), strict=True):
        assert ind["opened"] == ref.opened
        assert (pd.isna(ind["closed"]) and pd.isna(ref.closed)) or ind["closed"].floor("s") == ref.closed.floor("s")


@pytest.mark.parametrize("seed,n", [(1, 700), (2, 700)])
def test_referee_equals_independent_accounting_by_trade_time_and_total(seed, n):
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    c = (30000 * np.exp(np.cumsum(np.random.default_rng(seed).normal(0, 0.006, n)))).round(1)
    o = np.r_[c[0], c[:-1]]  # açılış=kapanış eşitliğinin varsayımını kaldır
    kl = pd.DataFrame(dict(open=o, high=np.maximum(o, c), low=np.minimum(o, c), close=c, volume=100.0), index=idx)
    mark = kl.assign(close=(c * 1.0005).round(1))
    fund = pd.DataFrame({"last_funding_rate": np.random.default_rng(seed + 9).normal(1e-4, 2e-4, n // 8)},
                        index=pd.date_range("2024-01-01 00:00:00.004", periods=n // 8, freq="8h", tz="UTC"))
    target = g1_real.mom(kl, 12)
    sp = referee.Spec(tick="0.1", step="0.001", min_notional=100.0, fee_rt_bps=10.0, slip_rt_bps=2.0, capital=500.0)
    r = referee.run(kl, target, sp, funding=fund, mark=mark)
    trades, funding, cur, missed = g1_real.independent(kl, target, fund, mark, sp)
    all_trades = [*trades, *([cur] if cur else [])]
    assert missed == r["summary"]["funding_missed"] == 0
    assert r["summary"]["n_liq"] == 0 and r["rejected"] == []
    # Açılış VE kapanış kimliği: sıralanmış net multiset'i yanlış işlemleri de eşleştirirdi.
    ind = pd.DataFrame(all_trades)
    ref = r["positions"].copy()
    # Nautilus ts_closed raporu 1 ns simülasyon ofsetini kesiyor; saat kimliğini koruyarak saniyeye indir.
    for frame in (ind, ref):
        frame["closed"] = pd.to_datetime(frame.closed, utc=True).dt.floor("s")
    merged = ref.merge(ind, on=["opened", "closed"], how="outer", indicator=True, validate="one_to_one")
    assert (merged._merge == "both").all() and len(merged) > 5
    closed = merged[merged.closed.notna()]
    assert np.allclose(closed.realized, closed.net, atol=1e-6, rtol=0)
    assert r["summary"]["funding"] == pytest.approx(funding, abs=1e-9)
    assert r["summary"]["net_pnl"] == pytest.approx(sum(t["net"] for t in all_trades) + funding, abs=1e-6)
