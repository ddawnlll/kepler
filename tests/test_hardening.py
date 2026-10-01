"""G2 öncesi: beklenen fiyat/maliyetler aşağıda elle hesaplanmıştır."""
import multiprocessing as mp

import numpy as np
import pandas as pd
import pytest

from kepler import ledger, referee
from tests.test_referee import bars, spec, tgt


def realistic(**kw):
    return spec(fill_mode="next_open", slip_rt_bps=6.0, **kw)


@pytest.mark.parametrize("sign,gross,net", [(1, -5.0, -5.172), (-1, 5.0, 4.828)])
def test_next_open_gap_fills_and_costs_are_hand_calculated(sign, gross, net):
    # Karar C0=100'de; sonraki açılış 110, çıkış açılışı 105. Bir adet; 215 notional.
    kl = bars([100, 120, 90, 100], rows=[(100, 100, 100, 100), (110, 120, 110, 120), (105, 105, 90, 90), (95, 100, 95, 100)])
    r = referee.run(kl, tgt(kl, b0=sign * 110.0, b1=0.0), realistic())
    assert r["fills"].px.tolist() == [110.0, 105.0]
    assert r["fills"].qty.tolist() == [1.0, 1.0]
    assert r["fills"].ts.tolist() == [(kl.index[i] + pd.Timedelta(1, unit="ns")).value for i in (1, 2)]
    s = r["summary"]
    assert s["gross_pnl"] == pytest.approx(gross)
    assert s["fee"] == pytest.approx(0.1075) and s["slippage"] == pytest.approx(0.0645)
    assert s["net_pnl"] == pytest.approx(net) and s["exit_cost"] == 0


def test_last_decision_has_no_fill_and_gap_uses_next_observed_open():
    kl = bars([100, 100, 200]).drop(pd.Timestamp("2024-01-01 01:00", tz="UTC"))
    r = referee.run(kl, tgt(kl, b0=200.0, b1=-200.0), realistic())
    # Son karar dolmaz; boşluktan sonraki açılış 200 => bir adet, fiyat kazancı sıfır.
    assert r["fills"].px.tolist() == [200.0] and r["fills"].qty.tolist() == [1.0]
    assert r["summary"]["net_pnl"] == pytest.approx(-0.32)  # giriş+varsayımsal çıkış: 400*8bps
    assert referee.run(kl, tgt(kl, b1=200.0), realistic())["fills"].empty


@pytest.mark.parametrize("sign,gross,net", [(1, 10.0, 9.816), (-1, -10.0, -10.184)])
def test_open_position_includes_exit_fee_and_slippage(sign, gross, net):
    kl = bars([100, 120], rows=[(100, 100, 100, 100), (110, 120, 110, 120)])
    s = referee.run(kl, tgt(kl, b0=sign * 110.0), realistic())["summary"]
    # Bir adet @110, son fiyat120: fee230*5bps=.115, slip230*3bps=.069.
    assert s["end_position"] == sign and s["gross_pnl"] == pytest.approx(gross)
    assert s["fee"] == pytest.approx(0.115) and s["slippage"] == pytest.approx(0.069)
    assert s["exit_cost"] == pytest.approx(0.096) and s["engine_commission"] == pytest.approx(0.088)
    assert s["net_pnl"] == pytest.approx(net)


@pytest.mark.parametrize("slip", [None, 0.0, -1.0, np.nan, np.inf])
def test_next_open_requires_explicit_positive_finite_slippage(slip):
    kl = bars([100, 100])
    with pytest.raises(ValueError, match="slippage"):
        referee.run(kl, tgt(kl), referee.Spec(slip_rt_bps=slip))


@pytest.mark.parametrize("at,expected", [({"b6": 100.0}, -0.0102), ({"b7": 100.0}, 0.0),
                                          ({"b0": 100.0, "b6": 0.0}, 0.0), ({"b0": 100.0, "b7": 0.0}, -0.0102)])
def test_next_open_funding_boundary_is_before_same_time_fill(at, expected):
    kl = bars([100] * 12)
    fund = pd.DataFrame({"last_funding_rate": [0.0001]}, index=[pd.Timestamp("2024-01-01 08:00", tz="UTC")])
    s = referee.run(kl, tgt(kl, **at), realistic(), funding=fund, mark=kl.assign(close=102.0))["summary"]
    assert s["funding"] == pytest.approx(expected)  # 1*mark102*1bp; settlement kabulu değişmedi


def test_liquidation_charges_one_exit_fee_and_keeps_slippage():
    kl = bars([100, 100, 100], rows=[(100, 100, 100, 100), (100, 100, 94, 100), (100, 100, 100, 100)])
    sp = realistic(capital=1000.0, liq=True, mmr=0.05, liq_fee_rate=0.01)
    s = referee.run(kl, tgt(kl, b0=10000.0), sp)["summary"]
    # WB=1000-5fee-3slip=992; LP=(10000-992)/95=94.8210526 ->94.82.
    # Brüt -518, giriş fee5, slip3+2.8446, likidasyon94.82; çıkış taker4.741 ikinci kez kesilmez.
    assert s["n_liq"] == 1 and s["end_position"] == 0
    assert s["gross_pnl"] == pytest.approx(-518.0)
    assert s["fee"] == pytest.approx(5.0) and s["liq_fee"] == pytest.approx(94.82)
    assert s["slippage"] == pytest.approx(5.8446) and s["net_pnl"] == pytest.approx(-623.6646)
    assert s["exit_cost"] == 0


def flat(frame):
    return pd.Series(0.0, index=frame.index)


def test_evaluate_audits_before_running_and_ledgering(tmp_path):
    kl = bars([100, 110, 105, 115] * 10)
    path = tmp_path / "ledger.jsonl"
    def leaky(frame):
        return frame.close.shift(-1).astype(float)
    def wrong_type(frame):
        return pd.Series(1, index=frame.index)
    for signal, exc in ((leaky, AssertionError), (wrong_type, ValueError)):
        with pytest.raises(exc):
            referee.evaluate(kl, signal, realistic(), path)
    assert not path.exists()
    with pytest.raises(ValueError, match="next_open"):
        referee.evaluate(kl, flat, spec(), path)
    with pytest.raises(ValueError, match="evaluate"):
        ledger.record(path, "referee", "bypass", {}, "c", "d", result={"net_pnl": 1.0})
    r = referee.evaluate(kl, flat, realistic(), path, hypothesis="flat", config={"fixture": True}, data_hash="fixture")
    assert r["summary"]["net_pnl"] == 0
    row = ledger.query(path, "select * from ledger").iloc[0]
    assert row.trial == 1 and row.source == "referee" and row.result["net_pnl"] == 0
    assert row.config["fill_mode"] == "next_open" and row.config["slip_rt_bps"] == 6


def append_many(path, start, barrier):
    barrier.wait(timeout=30)
    for i in range(20):
        ledger.record(path, "screen", f"worker{start}", {"i": i}, "c", "d", score=float(i))


def test_ledger_lock_keeps_trials_unique_and_jsonl_complete(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(4)
    procs = [ctx.Process(target=append_many, args=(str(path), n, barrier)) for n in range(4)]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(timeout=60)
        assert proc.exitcode == 0
    q = ledger.query(path, "select trial from ledger order by trial")
    assert q.trial.tolist() == list(range(1, 81)) and ledger.trial_count(path) == 80


def test_funding_does_not_look_forward_into_gap_open_liquidation():
    kl = bars([100] * 8 + [80] * 2)
    mark = kl.assign(close=102.0)  # settlement fiyatı mevcut, kline 07:00 barı eksik
    kl = kl.drop(kl.index[7])
    fund = pd.DataFrame({"last_funding_rate": [0.0001]}, index=[pd.Timestamp("2024-01-01 08:00", tz="UTC")])
    s = referee.run(kl, tgt(kl, b0=10000.0), realistic(capital=1000.0, liq=True, mmr=0.05, liq_fee_rate=0.01), funding=fund, mark=mark)["summary"]
    # T'de100 adet hâlâ açık; 80 açılışında liquidation T+1ns. Funding100*102*1bp=-1.02.
    assert s["n_liq"] == 1 and s["funding_missed"] == 0
    assert s["funding"] == pytest.approx(-1.02)


@pytest.mark.parametrize("start", [157, 385])
def test_evaluate_catches_sparse_and_tail_lookahead(tmp_path, start):
    kl = bars([100, 110, 105, 115] * 100)
    def sparse_leak(frame):
        # 16 eski kesim bu tek kararı/tail bölgesini kaçırıyordu; tüm prefix'ler denetlenir.
        return frame.close.shift(-1).where(frame.index == kl.index[start], 0.0).astype(float)
    with pytest.raises(AssertionError, match="geleceğe bakıyor"):
        referee.evaluate(kl, sparse_leak, realistic(), tmp_path / "l.jsonl")
    assert not (tmp_path / "l.jsonl").exists()
