"""Yeni hakem motoru (numba): L1 hacim kuralları (Nautilus kaynağından okunan), marj reddi ve BAĞIMSIZ muhasebe testleri. Beklenenler elle; Nautilus çalıştırılmaz."""
import numpy as np
import pandas as pd
import pytest

from kepler import report
from kepler.referee import Spec, run, run_portfolio
from tests.test_referee import A, bars, spec, tgt


def vol_bars(closes, vol):
    return bars(closes).assign(volume=float(vol))


def test_order_larger_than_quarter_volume_slips_remainder_one_tick():
    """Hacim 400 -> tik boyutu 100 (hacim/4). Hedef 150 adet @100: ilk dolum 100 @100, kalan 50 @100.01 (alış +1 tick = 0.01)."""
    kl = vol_bars([100] * 4, 400)
    f = run(kl, tgt(kl, b0=15000.0), spec(tick="0.01", step="0.001", capital=1e6, fill="next_open"))["fills"]
    assert list(f.qty) == [100.0, 50.0] and list(f.px) == [100.0, 100.01] and list(f.side) == ["BUY", "BUY"]


def test_sell_remainder_slips_down_and_small_order_is_single_fill():
    kl = vol_bars([100] * 4, 400)
    f = run(kl, tgt(kl, b0=-15000.0), spec(tick="0.01", capital=1e6, fill="next_open"))["fills"]
    assert list(f.px) == [100.0, 99.99] and list(f.qty) == [100.0, 50.0]
    assert len(run(kl, tgt(kl, b0=5000.0), spec(tick="0.01", capital=1e6, fill="next_open"))["fills"]) == 1


def test_zero_volume_ticks_leave_no_book_and_reject_orders():
    kl = vol_bars([100] * 4, 0.001)  # tik boyutu 0 (lot adımı 0.001 -> 1 artış < 4 parça): kitap hiç oluşmaz
    r = run(kl, tgt(kl, b0=1000.0), spec(fill="next_open"))
    assert r["fills"].empty and r["summary"]["n_rejected"] == 1


def test_stop_fill_is_limited_by_tick_size_with_one_tick_slip():
    """10 adet long, stop 95, hacim 20 -> tik 5. Gövde L tikinde tetik: 5 @95 (tetik fiyatı), kalan 5 @94.99."""
    rows = [(100,) * 4, (100,) * 4, (99, 100, 94, 96), (100,) * 4]
    kl = bars([100] * 4, rows=rows).assign(volume=2000.0)
    kl.loc[kl.index[2], "volume"] = 20.0
    kl.loc[kl.index[1], "volume"] = 2000.0
    r = run(kl, pd.Series([1000.0, np.nan, np.nan, np.nan], index=kl.index), spec(tick="0.01", liq=False, capital=10000.0, fill="next_open"), stop=pd.Series(95.0, index=kl.index))
    f = r["fills"]
    assert list(f.px) == [100.0, 95.0, 94.99] and list(f.qty) == [10.0, 5.0, 5.0] and list(f.stop) == [False, True, True] and r["summary"]["end_position"] == 0


def test_margin_reject_when_account_is_bankrupt():
    """Bakiye ~0 iken artıran emir reddedilir (INITIAL_MARGIN_EXCEEDS_FREE_BALANCE); azaltan emir muaf."""
    kl = bars([100] * 6)
    r = run(kl, tgt(kl, b0=1000.0), spec(capital=0.5, fill="next_open"))
    assert r["fills"].empty and r["summary"]["n_rejected"] == 1


def _rand_case(seed, n=500):
    rng = np.random.default_rng(seed)
    c = np.round(100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))), 2)
    o = np.round(np.r_[c[0], c[:-1]] * (1 + rng.normal(0, 0.001, n)), 2)
    h, l = np.round(np.maximum(o, c) * (1 + rng.uniform(0, 0.01, n)), 2), np.round(np.minimum(o, c) * (1 - rng.uniform(0, 0.01, n)), 2)
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    kl = pd.DataFrame(dict(open=o, high=h, low=l, close=c, volume=rng.uniform(50, 3000, n).round(3)), index=idx)
    t = pd.Series(np.nan, index=idx)
    t.iloc[3::17] = rng.choice([-4000.0, -1500.0, 0.0, 1500.0, 4000.0], len(t.iloc[3::17]))
    fi = pd.date_range("2024-01-01 08:00", periods=n // 8, freq="8h", tz="UTC")
    fund = pd.DataFrame(dict(last_funding_rate=rng.normal(1e-4, 2e-4, len(fi))), index=fi)
    return kl, t, fund, kl.assign(close=c * 1.0003)


@pytest.mark.parametrize("seed", range(6))
def test_independent_cash_identity_and_hourly_reconstruction(seed):
    """BAĞIMSIZ muhasebe: (1) net = nakit akışı + son pozisyon x son kapanış - komisyon + funding - likidasyon ücreti - çıkış maliyeti, dolumlardan Decimal'siz yeniden hesap;
    (2) saatlik PnL yeniden kurulumu (report.hourly_pnl) toplamı hakem net'ine eşit; (3) komisyon = notional x yan ücret."""
    kl, t, fund, mark = _rand_case(seed)
    sp = Spec(tick="0.01", step="0.001", capital=2000.0, leverage=10, liq=True, fee_rt_bps=10.0, slip_rt_bps=2.0, mmr=0.01)
    r = run(kl, t, sp, fund, mark)
    f, s = r["fills"], r["summary"]
    assert len(f) > 20 and r["rejected"] == []
    sgn = np.where(f.side == "BUY", 1.0, -1.0)
    side_fee = 6e-4
    assert np.allclose(f.commission, (f.qty * f.px * side_fee).round(8), atol=1e-8)
    end_pos = float((sgn * f.qty).sum())
    cash = float(-(sgn * f.qty * f.px).sum())
    liq_fee = float((f.qty * f.px * f.liq).sum()) * max(0.0, sp.mmr - side_fee)
    net = cash + end_pos * kl.close.iloc[-1] - float(f.commission.sum()) + s["funding"] - liq_fee - abs(end_pos) * kl.close.iloc[-1] * side_fee
    assert s["net_pnl"] == A(net, abs=1e-6) and s["end_position"] == A(end_pos, abs=1e-9)
    # funding bağımsız yeniden hesap: T'den ÖNCE (ts < T) gerçekleşen dolumların net pozisyonu x T'de biten barın mark kapanışı x oran
    signed, ts = sgn * f.qty.to_numpy(), f.ts.to_numpy()
    ind = 0.0
    for T, rate in fund.last_funding_rate.items():
        if kl.index[0] + pd.Timedelta("1h") <= T <= kl.index[-1] + pd.Timedelta("1h"):
            ind += -signed[ts < T.value].sum() * mark.close[T - pd.Timedelta("1h")] * rate
    assert s["funding"] == A(ind, abs=1e-6)
    hp = report.hourly_pnl(kl, mark, fund, f, sp)
    assert abs(hp.sum() - s["net_pnl"]) < 0.5


def test_vectorbt_independent_pnl_of_engine_fills():
    """vectorbt'a (ayrı muhasebe kodu) motorun dolumlarını emir olarak ver; fiyat PnL - komisyon toplamı hakemin (net - funding + çıkış maliyeti) değeriyle örtüşmeli."""
    vbt = pytest.importorskip("vectorbt")
    kl, t, fund, mark = _rand_case(11)
    sp = Spec(tick="0.01", step="0.001", capital=2000.0, leverage=10, liq=True, fee_rt_bps=10.0, slip_rt_bps=2.0, mmr=0.01)
    r = run(kl, t, sp, None, None)
    f = r["fills"]
    idx = pd.DatetimeIndex(pd.to_datetime(f.ts, unit="ns", utc=True)).floor("1h")
    size = pd.Series(np.where(f.side == "BUY", f.qty, -f.qty), index=idx).groupby(level=0).sum()
    px = pd.Series((f.px * f.qty).to_numpy(), index=idx).groupby(level=0).sum() / pd.Series(f.qty.to_numpy(), index=idx).groupby(level=0).sum()
    fee = pd.Series(f.commission.to_numpy(), index=idx).groupby(level=0).sum() / pd.Series((f.qty * f.px).to_numpy(), index=idx).groupby(level=0).sum()
    keep = size.abs() > 0
    pf = vbt.Portfolio.from_orders(kl.close.reindex(size.index[keep]), size=size[keep], price=px[keep], fees=fee[keep], init_cash=1e9, direction="both", size_type="amount")
    end = float(size.sum())
    exp = r["summary"]["net_pnl"] - r["summary"]["funding"] + r["summary"]["exit_cost"]
    got = float(pf.value().iloc[-1]) - 1e9 + end * (kl.close.iloc[-1] - float(kl.close.reindex(size.index[keep]).iloc[-1]))
    assert got == A(exp, abs=5e-2)


def test_batch_runs_are_deterministic_and_thread_safe():
    from concurrent.futures import ThreadPoolExecutor
    kl, t, fund, mark = _rand_case(3)
    sp = spec(tick="0.01", fill="next_open", capital=2000.0, liq=True)
    base = run(kl, t, sp, fund, mark)["summary"]["net_pnl"]
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda _: run(kl, t, sp, fund, mark)["summary"]["net_pnl"], range(8)))
    assert all(x == base for x in res)


def _grid_specs(n=6):
    return [Spec(tick="0.01", step="0.001", capital=2000.0, leverage=10, liq=True, fee_rt_bps=4.0 + 2 * i, slip_rt_bps=1.0 + (i % 3), delay=i % 2, mmr=0.01) for i in range(n)]


def test_run_many_cpu_matches_serial_and_summary_only_mode():
    kl, t, fund, mark = _rand_case(5)
    data = {"X": dict(kl=kl, target=t, funding=fund, mark=mark)}
    specs = _grid_specs()
    many = run_portfolio_many(data, specs, "cpu", True)
    lite = run_portfolio_many(data, specs, "cpu", False)
    for sp, m, l_ in zip(specs, many, lite):
        s = run_portfolio(data, sp)["summary"]
        assert m["summary"] == s and l_["summary"] == s and "fills" not in l_


def run_portfolio_many(data, specs, device, full):
    from kepler.referee import run_many
    return run_many(data, specs, workers=2, device=device, full=full)


def test_gpu_matches_cpu_when_cuda_available():
    """GPU yolu (referee_gpu): CUDA yoksa atlanır; varsa tüm özet kalemleri CPU ile aynı (bakiye ~1e-7 farkı: np.rint beraberlik kuralı)."""
    from kepler import referee_gpu
    if not referee_gpu.available():
        pytest.skip("CUDA yok")
    kl, t, fund, mark = _rand_case(5)
    data = {"X": dict(kl=kl, target=t, funding=fund, mark=mark)}
    specs = _grid_specs(8)
    cpu, gpu = run_portfolio_many(data, specs, "cpu", False), run_portfolio_many(data, specs, "gpu", False)
    for c, g in zip(cpu, gpu):
        for k in ("n_fills", "n_liq", "n_stop", "n_rejected", "funding_missed", "funding_mark_fallback"):
            assert c["summary"][k] == g["summary"][k]
        for k in ("net_pnl", "funding", "fee", "slippage", "exit_cost", "end_position"):
            assert g["summary"][k] == A(c["summary"][k], abs=1e-5)
