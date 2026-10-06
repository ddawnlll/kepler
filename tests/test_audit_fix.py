"""scripts/audit_fix.py: sözleşme birimi (MEXC), emir niyeti yeniden oynatımı = hakem dolumları, risk motoru ara adımları = portfolio.size, tik dizesi normalizasyonu; beklenen değerler elle."""
import sys
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
import audit_fix as AF  # noqa: E402

from kepler import ensemble as en  # noqa: E402
from kepler import portfolio, referee  # noqa: E402


def kl_of(prices):
    idx = pd.date_range("2024-01-01", periods=len(prices), freq="1h", tz="UTC")
    p = pd.Series(prices, index=idx, dtype=float)
    return pd.DataFrame(dict(open=p, high=p, low=p, close=p, volume=1e6))


def target(kl, **at):
    t = pd.Series(np.nan, index=kl.index)
    for k, v in at.items():
        t.iloc[int(k[1:])] = v
    return t


def test_replay_orders_hand_calc():
    kl = kl_of([100.0] * 8)
    # karar b0: 250 USDT / 100 = 2,5 -> 2 sözleşme; b1: 290 -> 2 (delta 0: gönderilmez); b2: 400 -> 4 (delta +2); b3: 0 -> kapat (-4)
    r = AF.replay_orders(kl, target(kl, b0=250.0, b1=290.0, b2=400.0, b3=0.0), step="1", tick="0.1", min_notional=0.0)
    assert list(r.want) == [2.0, 2.0, 4.0, 0.0] and list(r.sent) == [True, False, True, True]
    assert list(r.reason) == ["sent", "delta_zero", "sent", "sent"] and list(r.delta) == [2.0, 0.0, 2.0, -4.0]


def test_replay_min_notional_blocks_increase_but_not_reduction():
    kl = kl_of([100.0] * 6)
    r = AF.replay_orders(kl, target(kl, b0=1000.0, b1=1250.0, b2=1000.0), step="0.1", tick="0.1", min_notional=50.0)
    # b1: 12,5 birim - 10 = 2,5 birim x 100 = 250 >= 50 gönderilir; test yerine küçük artış: aşağıdaki
    assert list(r.sent) == [True, True, True]
    r2 = AF.replay_orders(kl, target(kl, b0=1000.0, b1=1030.0, b2=500.0), step="0.1", tick="0.1", min_notional=50.0)
    assert list(r2.reason) == ["sent", "min_notional", "sent"]  # +0,3 birim = 30 USDT < 50 atlanır; azaltma muaf


@pytest.mark.parametrize("tgts", [dict(b0=250.0, b1=290.0, b2=-400.0, b3=0.0), dict(b0=-90.0, b1=520.0, b2=520.0, b4=15.0)])
def test_replay_matches_referee_fills(tgts):
    kl = kl_of([100.0, 101.0, 99.5, 100.2, 100.0, 100.4, 101.0, 100.0, 99.0, 100.0])
    t = target(kl, **tgts)
    sp = replace(referee.Spec(capital=1000.0, fee_rt_bps=10.0, slip_rt_bps=2.0, leverage=10, min_notional=0.0), tick="0.1", step="1")
    res = referee.run(kl, t, sp)
    rep = AF.replay_orders(kl, t, step="1", tick="0.1", min_notional=0.0)
    sent = rep[rep.sent]
    f = res["fills"]
    assert len(sent) == len(f)
    assert np.allclose(sent.delta.to_numpy(), np.where(f.side == "BUY", f.qty, -f.qty))


def test_contract_view_scaling_and_tick_normalization():
    kl = kl_of([0.2, 0.2, 0.2])
    d = dict(kl=kl.assign(volume=1000.0), funding=None, mark=kl.copy(), tick="1e-6", step="1e-3")
    rules = dict(DOGEUSDT=dict(contractSize=100, priceUnit=1e-05, volUnit=1, minVol=1))
    v = AF.contract_view(dict(DOGEUSDT=d), rules)["DOGEUSDT"]
    assert v["tick"] == "0.001" and v["step"] == "1"  # "0.00100" değil: artık sıfır hassasiyeti tikle uyumsuz kılar, hakem emri sessizce doldurmaz
    assert v["kl"].close.iloc[0] == pytest.approx(20.0) and v["kl"].volume.iloc[0] == pytest.approx(10.0) and v["mark"].close.iloc[0] == pytest.approx(20.0)
    assert v["cs"] == 100.0


def test_size_parts_matches_portfolio_size():
    rng = np.random.default_rng(3)
    n, m = 140, 4
    idx = pd.date_range("2022-01-01", periods=n, freq="1D", tz="UTC")
    cols = ["A", "B", "C", "D"]
    ret = pd.DataFrame(rng.normal(0, 0.03, (n, m)), index=idx, columns=cols)
    st = dict(ret=ret, sigma=pd.DataFrame(0.6 + 0.1 * rng.random((n, m)), index=idx, columns=cols), active=pd.DataFrame(True, index=idx, columns=cols))
    f = pd.DataFrame(np.clip(rng.normal(0, 0.6, (n, m)), -1, 1), index=idx, columns=cols)
    p = en.Params()
    ref = portfolio.size(f, st, 1000.0, p)
    parts = AF.size_parts(f, st, 1000.0, p)
    assert np.array_equal(ref.to_numpy(), parts["out"].to_numpy())
    # ara adım kimliği: n0 = unit x F; tavanlar bağlamıyorsa n2 = n1 = n0 (bağlayanda küçülür)
    assert np.allclose(parts["n0"].to_numpy(), (parts["unit"] * f).to_numpy(), equal_nan=True)
    assert (parts["n2"].abs() <= parts["n0"].abs() + 1e-9).to_numpy()[~np.isnan(parts["n2"].to_numpy())].all()
