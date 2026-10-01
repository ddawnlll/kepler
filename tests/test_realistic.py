"""Gerçekçi hakem (G2 öncesi): sonraki-bar açılış dolumu, çıkış maliyeti, likidasyon çifte sayımı, evaluate girişi, defter kilidi.
Beklenen değerler elle hesaplandı."""
import multiprocessing as mp

import numpy as np
import pandas as pd
import pytest

from kepler import evaluate as ev
from kepler import ledger
from kepler.referee import Spec, run
from tests.test_referee import A, bars, tgt


def sp(**kw):  # varsayılan = gerçekçi (next_open, close_out); likidasyon açık, sermaye büyük (LP yok sayılır)
    return Spec(**{**dict(tick="0.01", step="0.001", capital=10000.0, liq=True, fee_rt_bps=10.0), **kw})


def test_fill_is_next_bar_open_not_decision_close():
    kl = bars([100, 100, 104, 104], rows=[(100, 100, 100, 100), (101, 105, 101, 105), (104, 104, 104, 104), (104, 104, 104, 104)])
    r = run(kl, tgt(kl, b0=100.0, b1=0.0), sp())  # b0 kapanışı 100 ama dolum b1 açılışı 101; b1 kapanışı 105 ama çıkış b2 açılışı 104
    f, s = r["fills"], r["summary"]
    assert list(f.px) == [101.0, 104.0] and list(f.qty) == [0.99, 0.99]  # 100/101=0.9901 -> 0.990
    assert s["gross_pnl"] == A(0.99 * 3) and s["fee"] == A(0.0005 * (0.99 * 101 + 0.99 * 104)) and s["net_pnl"] == A(2.97 - 0.101475)


def test_last_bar_target_never_fills_and_gap_uses_next_available_bar():
    kl = bars([100, 100, 100])
    assert run(kl, tgt(kl, b2=100.0), sp())["fills"].empty  # kararın sonraki barı yok
    kl = bars([100, 100, 100, 100, 110, 110]).drop(pd.Timestamp("2024-01-01 03:00", tz="UTC"))  # 03:00 barı yok
    f = run(kl, tgt(kl, b2=100.0), sp())["fills"]  # karar 03:00'te; ilk mevcut açılış 04:00 (110)
    assert list(f.px) == [110.0]


def test_open_position_pays_exit_cost():
    kl = bars([100, 100, 110])
    s = run(kl, tgt(kl, b0=100.0), sp())["summary"]  # b1 açılışı 100'de gir, 110'da değerle
    assert s["exit_cost"] == A(110 * 0.0005) and s["net_pnl"] == A(10 - 0.05 - 0.055) and s["gross_pnl"] == A(10.0)
    assert run(kl, tgt(kl, b0=100.0), sp(close_out=False))["summary"]["net_pnl"] == A(10 - 0.05)


@pytest.mark.parametrize("t,charged", [(dict(b6=100.0, b9=0.0), True), (dict(b0=100.0, b6=0.0), False), (dict(b0=100.0, b7=0.0), True), (dict(b7=100.0, b9=0.0), False)])
def test_funding_boundary_unchanged_in_next_open_mode(t, charged):
    kl = bars([100] * 12)
    f = pd.DataFrame({"last_funding_rate": [0.0001]}, index=[pd.Timestamp("2024-01-01 08:00:00.005", tz="UTC")])
    s = run(kl, tgt(kl, **t), sp(fee_rt_bps=0), funding=f, mark=kl.assign(close=102.0))["summary"]
    assert (s["funding"] != 0) is charged and (not charged or s["funding"] == A(-1.0 * 102 * 0.0001))


def test_liquidation_inside_the_fill_bar_and_no_double_fee():
    kl = bars([100, 100, 100], rows=[(100, 100, 100, 100), (100, 100, 94, 100), (100, 100, 100, 100)])
    s = run(kl, tgt(kl, b0=10000.0), sp(capital=1000.0, liq=True, mmr=0.05))["summary"]  # b1 açılışı 100'de dolar; gövdede LP 94.79 vurulur
    # zarar 521 + giriş fee 5 + toplam likidasyon maliyeti mmr*notional = 473.95 (motor fee'si 4.7395 bunun içinde, ek 469.2105)
    assert s["n_liq"] == 1 and s["liq_fee"] == A(469.2105) and s["net_pnl"] == A(-521 - 5 - 473.95)


def test_funding_in_kline_gap_is_charged_to_pre_fill_position():
    kl = bars([100] * 12).drop([pd.Timestamp("2024-01-01 07:00", tz="UTC"), pd.Timestamp("2024-01-01 08:00", tz="UTC")])  # 07:00 ve 08:00 barları yok
    f = pd.DataFrame({"last_funding_rate": [0.0001]}, index=[pd.Timestamp("2024-01-01 08:00", tz="UTC")])
    r = run(kl, tgt(kl, b6=100.0, b8=0.0), sp(fee_rt_bps=0), funding=f, mark=kl)  # karar 07:00'de, ilk dolum 09:00 (T=08:00'den SONRA) -> funding yok
    assert list(r["fills"].ts)[0] == int(pd.Timestamp("2024-01-01 09:00", tz="UTC").value) and r["summary"]["funding"] == 0


def test_no_trading_after_liquidation():
    kl = bars([100, 100, 100, 120], rows=[(100, 100, 100, 100), (100, 100, 94, 100), (100, 100, 100, 100), (120, 120, 120, 120)])
    r = run(kl, tgt(kl, b0=10000.0, b2=10000.0), sp(capital=1000.0, mmr=0.05, leverage=10))  # b2'de aynı hedefle yeniden giriş denemesi
    assert r["summary"]["n_liq"] == 1 and len(r["fills"]) == 2 and r["summary"]["end_position"] == 0
    assert r["summary"]["net_pnl"] == A(-999.95)  # hesap sıfırlandı; sonraki +%20 hayalet bakiyeyle kâr yazmaz


def test_evaluate_rejects_liq_off_and_oversized_signal(tmp_path):
    kl = walk()
    with pytest.raises(ValueError, match="gerçekçi"):
        ev.evaluate(mom, kl, [sp(slip_rt_bps=2.0, liq=False)], tmp_path / "l.jsonl", "h", "d")
    with pytest.raises(ValueError, match="birim"):
        ev.evaluate(lambda k: 3 * mom(k), kl, [sp(slip_rt_bps=2.0)], tmp_path / "l.jsonl", "h", "d")


def walk(n=600, seed=1):
    r = np.random.default_rng(seed).normal(0, 0.004, n)
    return bars(list(100 * np.exp(np.cumsum(r))))


def mom(kl):
    return np.sign(kl.close.pct_change(24)).astype(float)  # nedensel


def test_evaluate_refuses_unrealistic_specs_and_leaky_signals_before_ledger(tmp_path):
    kl, p = walk(), tmp_path / "l.jsonl"
    for bad in (sp(slip_rt_bps=0.0), sp(slip_rt_bps=2.0, fill="close"), sp(slip_rt_bps=2.0, close_out=False)):
        with pytest.raises(ValueError, match="gerçekçi"):
            ev.evaluate(mom, kl, [bad], p, "h", "d")
    with pytest.raises(AssertionError, match="geleceğe"):
        ev.evaluate(lambda k: np.sign(k.close.shift(-1) - k.close).astype(float), kl, [sp(slip_rt_bps=2.0)], p, "h", "d")
    assert ledger.trial_count(p) == 0
    out = ev.evaluate(mom, kl, [sp(slip_rt_bps=2.0, fee_rt_bps=f) for f in (4, 10)], p, "h", "d", name="mom24")
    assert ledger.trial_count(p) == 2 and out[0]["row"]["config"]["audit_causal"] is True and out[0]["row"]["result"]["n_rejected"] == 0
    assert out[0]["res"]["summary"]["net_pnl"] > out[1]["res"]["summary"]["net_pnl"]  # düşük fee daha iyi


def test_evaluate_window_runs_signal_on_full_series(tmp_path):
    kl = walk()
    full = mom(kl)
    w = ev.evaluate(mom, kl, [sp(slip_rt_bps=2.0)], tmp_path / "w.jsonl", "h", "d", window=(kl.index[300], kl.index[500]))[0]["res"]
    # sinyal pencerenin 300. barında zaten tanımlı (24 bar ısınma tam seride hesaplandı): ilk dolum 300. barın kararından, 301. barın açılışında
    assert full.iloc[300] != 0 and w["fills"].ts.min() == int(kl.index[301].value)


def _writer(args):
    p, i = args
    for k in range(25):
        ledger.record(p, "screen", f"w{i}", {"i": i, "k": k}, "c", "d", score=0.0)


def test_ledger_concurrent_writers_keep_unique_trials(tmp_path):
    p = tmp_path / "l.jsonl"
    with mp.get_context("fork").Pool(4) as pool:
        pool.map(_writer, [(p, i) for i in range(4)])
    q = ledger.query(p, "select trial from ledger order by trial")
    assert list(q.trial) == list(range(1, 101))  # yarış yok: 100 satır, deneme sayacı tekil


def test_causal_audit_handles_integer_volume_columns():
    from kepler import audit
    kl = walk().assign(volume=np.arange(600) + 1000)  # int64 hacim (gerçek veride DOGE vb.)
    assert audit.check_causal(mom, kl) == []
