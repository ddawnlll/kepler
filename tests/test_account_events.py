"""Settlement nakdi sonraki boyutlama, marj ve likidasyonu etkiler; beklentiler elle hesaplı."""
import numpy as np
import pandas as pd
import pytest

from kepler.referee import Spec, run, run_portfolio
from tests.test_referee import bars, tgt


def sp(**kw):
    return Spec(**{**dict(tick="0.01", capital=1000.0, fee_rt_bps=0.0, close_out=False), **kw})


def funding(kl, rate, hour=8):
    return pd.DataFrame({"last_funding_rate": [rate]}, index=[kl.index[hour]])


@pytest.mark.parametrize("direction,rate,want", [(1, 0.1, 5.7), (1, -0.1, 6.3), (-1, 0.1, -6.3), (-1, -0.1, -5.7)])
def test_funding_cash_changes_the_next_equity_scaled_target(direction, rate, want):
    kl = bars([100.0] * 12)
    target = tgt(kl, b0=direction * 500.0, b7=direction * 600.0)
    r = run(kl, target, sp(equity_scale=True), funding(kl, rate))
    # 5 adet * 100 * oran: WB = 1000 - yön*500*oran; hedef 600*WB/1000.
    assert r["summary"]["end_position"] == pytest.approx(want)
    assert r["summary"]["funding"] == pytest.approx(-direction * 500 * rate)


def test_funding_is_settled_before_margin_check_at_the_same_open():
    kl = bars([100.0] * 12)
    r = run(kl, tgt(kl, b0=1000.0, b7=2000.0), sp(capital=100.0), funding(kl, 0.09))
    # Funding -90: WB=10; bakım kilidi=1000/10*.005=.5; delta marjı=1000/100=10 > 9.5.
    assert r["summary"]["n_rejected"] == 1
    assert r["summary"]["end_position"] == 10.0
    assert r["summary"]["funding"] == pytest.approx(-90.0)


def test_funding_rearms_liquidation_before_the_settlement_bar():
    kl = bars([100.0] * 12)
    kl.loc[kl.index[8], "low"] = 92.0
    target = tgt(kl, b0=10000.0)
    control = run(kl, target, sp(liq_fee_rate=0.0))
    r = run(kl, target, sp(liq_fee_rate=0.0), funding(kl, 0.02))
    # Funding yokken LP=9000/99.5=90.45: low 92 tetiklemez.
    # Funding -200 sonrası LP=9200/99.5=92.46: low 92 tetikler.
    assert control["summary"]["n_liq"] == 0
    assert r["summary"]["n_liq"] == 1
    assert r["fills"].px.iloc[-1] == pytest.approx(92.46)
    assert r["summary"]["funding"] == pytest.approx(-200.0)


def test_funding_can_liquidate_even_when_the_next_market_price_is_unchanged():
    kl = bars([100.0] * 12)
    r = run(kl, tgt(kl, b0=10000.0), sp(liq_fee_rate=0.0), funding(kl, 0.11))
    # WB = 1000 - 1100 = -100, LP > 100; settlement sonrası ilk piyasa tiki 100.
    assert r["summary"]["n_liq"] == 1
    assert r["summary"]["end_position"] == 0.0
    assert list(r["fills"].px) == [100.0, 100.0]
    assert r["summary"]["net_pnl"] == pytest.approx(-1100.0)


def test_retired_gpu_route_fails_closed_and_cpu_parity_is_preserved():
    from kepler.referee import run_many
    from scripts.referee_gpu import simulate_many
    kl = bars([100.0] * 12)
    data = {"A": dict(kl=kl, target=tgt(kl, b0=500.0, b7=600.0), funding=funding(kl, 0.1))}
    specs = [sp(equity_scale=True), sp()]
    # Retired GPU must not silently pretend its funding/intent behavior is verified.
    with pytest.raises(NotImplementedError, match="GPU yolu"):
        run_many(data, specs, kernel=simulate_many)
    many = run_many(data, specs)
    assert [r["summary"] for r in many] == [run_portfolio(data, s)["summary"] for s in specs]


def test_close_mode_funding_follows_the_preceding_body_stop():
    kl = bars([100.0] * 12)
    kl.loc[kl.index[7], "low"] = 94.0
    r = run(kl, tgt(kl, b0=100.0), sp(fill="close", liq=False), funding(kl, 0.01), stop=pd.Series(95.0, index=kl.index))
    assert r["summary"]["funding"] == 0.0  # 07:00 gövdesinde kapandı, T=08:00'de flat
    assert r["summary"]["net_pnl"] == pytest.approx(-5.0)
    assert r["fills"].ts.iloc[-1] < kl.index[8].value


def test_funding_cannot_apply_a_new_liquidation_level_to_an_already_finished_body():
    kl = bars([100.0] * 12)
    kl.loc[kl.index[7], "low"] = 92.0
    r = run(kl, tgt(kl, b0=10000.0), sp(fill="close", liq_fee_rate=0.0), funding(kl, 0.02))
    # 07:00 gövdesi LP=90.45 ile biter; 08:00 settlement LP'yi 92.46 yapar.
    # Yeni seviye geçmişteki low=92'ye uygulanamaz, sonraki gövde low=100.
    assert r["summary"]["n_liq"] == 0
    assert r["summary"]["funding"] == pytest.approx(-200.0)


def test_liquidation_fee_reduces_cash_before_another_symbol_is_sized():
    a, b = bars([100.0] * 6), bars([100.0] * 6)
    a.loc[a.index[2], ["low", "close"]] = [80.0, 85.0]
    a.loc[a.index[3]:, ["open", "high", "low", "close"]] = 85.0
    data = {"A": dict(kl=a, target=tgt(a, b0=9000.0)), "B": dict(kl=b, target=tgt(b, b3=1000.0))}
    r = run_portfolio(data, sp(equity_scale=True))
    control = run_portfolio(data, sp(equity_scale=True, liq_fee_rate=0.0))
    # A: LP 89.34, realize -959.4, liq fee 90*89.34*.005=40.203.
    # WB .397 => B hedef .397 < min 5. Ücret yokken WB 40.6 => B .406 adet.
    assert r["summary"]["liq_fee"] == pytest.approx(40.203)
    assert r["summary"]["net_pnl"] == pytest.approx(-999.603)
    assert list(r["fills"].sym) == ["A", "A"]
    assert list(control["fills"].sym) == ["A", "A", "B"]
    assert control["fills"].qty.iloc[-1] == pytest.approx(0.406)


@pytest.mark.parametrize("step,target,want", [("0.005", 100.3, 1.0), ("0.025", 103.7, 1.025), ("5", 1499.0, 10.0)])
def test_target_quantities_are_multiples_of_the_actual_step(step, target, want):
    kl = bars([100.0] * 4).assign(volume=10000.0)
    r = run(kl, tgt(kl, b0=target), sp(step=step))
    assert r["summary"]["end_position"] == pytest.approx(want)
    assert np.allclose(r["fills"].qty / float(step), np.round(r["fills"].qty / float(step)))
