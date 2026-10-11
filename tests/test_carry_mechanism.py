"""#17: sıfır toplamlı tahmin dolar-nötr değildir (E05); aşama maruziyeti, fiyat/funding/maliyet ayrımı mutabakatı, perm benchmark, beta."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import carry_mechanism as cm  # noqa: E402

from kepler import ensemble as en  # noqa: E402
from kepler.referee import Spec, run_portfolio  # noqa: E402


def panel4(T=150, sig=(0.01, 0.03, 0.05, 0.07), seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=T, freq="D", tz="UTC")
    cols = list("ABCD")
    ret = pd.DataFrame(rng.normal(size=(T, 4)) * np.array(sig), index=idx, columns=cols)
    sigma = pd.DataFrame(np.tile(np.array(sig) * np.sqrt(365), (T, 1)), index=idx, columns=cols)
    return idx, cols, dict(ret=ret, sigma=sigma, active=pd.DataFrame(True, index=idx, columns=cols))


def test_zero_sum_forecast_is_not_dollar_neutral_after_vol_sizing():
    idx, cols, st = panel4()
    f = pd.DataFrame(np.tile([1.0, 0.3, -0.3, -1.0], (len(idx), 1)), index=idx, columns=cols)
    assert f.sum(1).abs().max() < 1e-12  # tahmin toplamı sıfır
    p = en.Params(names=("carry_xs",), weights=(1.0,), buffer=0.0)
    s = cm.stages(f, st, 10_000.0, p)
    e = cm.exposure(s["sized"].iloc[30:])
    assert e["abs_net_over_gross_mean"] > 0.3 and not e["neutral"]  # σ ile bölünce düşük-vol bacak baskın: net/brüt büyük (E05: %69,7)
    assert cm.exposure(s["forecast"])["neutral"]  # tahmin düzeyinde nötr görünür; dolar düzeyinde değil
    eq = cm.stages(pd.DataFrame(np.tile([1.0, 0.3, -0.3, -1.0], (len(idx), 1)), index=idx, columns=cols), dict(st, sigma=st["sigma"] * 0 + 0.5), 10_000.0, p)
    assert cm.exposure(eq["sized"].iloc[30:])["neutral"]  # eşit σ: sıfır-toplam tahmin dolar-nötr kalır (karşı kontrol)


def tiny_run(rate=0.0003):
    n = 72
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    rng = np.random.default_rng(1)
    c = 100 * np.exp(np.cumsum(rng.normal(size=n) * 0.002))
    kl = pd.DataFrame(dict(open=np.r_[c[0], c[:-1]], high=c * 1.001, low=c * 0.999, close=c, volume=1e6), index=idx)
    f = pd.DataFrame({"last_funding_rate": [rate] * 3}, index=[pd.Timestamp(f"2024-01-0{d} 08:00", tz="UTC") for d in (1, 2, 3)])
    tgt = pd.Series(np.nan, index=idx)
    tgt.iloc[2], tgt.iloc[30], tgt.iloc[50] = 1000.0, -800.0, 0.0
    data = {"X": dict(kl=kl, target=tgt, funding=f, mark=kl)}
    sp = Spec(capital=10000.0, fee_rt_bps=10.0, slip_rt_bps=2.0, tick="0.01", step="0.001", fill="next_open", liq=False)
    return data, sp, run_portfolio(data, sp)


def test_decompose_components_sum_and_reconcile():
    data, sp, res = tiny_run()
    d = cm.decompose(data, res, sp)
    t = d["totals"]
    assert t["price"] + t["funding"] + t["cost"] == pytest.approx(t["total"], abs=1e-9) and abs(d["residual"]) < 1e-6  # residual görünür ve ~0
    assert t["funding"] == pytest.approx(res["summary"]["funding"], abs=1e-9) and t["cost"] < 0
    assert set(d["by_regime"]) == {"unclassified"} and "2024" in d["by_year"]  # ısınma/etiketsiz dönem görünür


def test_permute_preserves_cross_section_and_beta():
    idx, cols, st = panel4(60)
    f = pd.DataFrame(np.random.default_rng(2).normal(size=(60, 4)), index=idx, columns=cols)
    q = cm.permute_forecast(f, st["active"], 0)
    assert np.allclose(np.sort(q.to_numpy(), 1), np.sort(f.to_numpy(), 1)) and not q.equals(f) and q.equals(cm.permute_forecast(f, st["active"], 0))
    btc = pd.Series(np.random.default_rng(3).normal(size=100) * 0.02, index=pd.date_range("2024", periods=100, tz="UTC"))
    pnl = btc * 10_000 * 0.5 + np.random.default_rng(4).normal(size=100) * 5
    assert cm.beta(pnl, btc, 10_000.0)["beta"] == pytest.approx(0.5, abs=0.15)
