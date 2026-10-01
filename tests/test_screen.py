import numpy as np
import pandas as pd
import pytest

from kepler import ledger, referee, screen


def market(n=400, seed=1):
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    c = (100 * np.exp(np.cumsum(np.random.default_rng(seed).normal(0, 0.01, n)))).round(2)
    return pd.DataFrame(dict(open=c, high=c, low=c, close=c, volume=1000.0), index=idx)


def mom(kl, n, size):  # test fixture (sinyal değil): n bar momentum
    up = kl.close > kl.close.shift(n)
    return pd.Series(np.where(up, size, -size), index=kl.index).where(kl.close.shift(n).notna())


def test_actions_follow_referee_rule():
    t = pd.Series([np.nan, 100, 100, np.nan, 100, -100, -100, 0.0, 0.0])
    a = screen.actions(t)
    assert list(a.dropna().index) == [1, 5, 7] and list(a.dropna()) == [100, -100, 0.0]  # yalnızca değişimlerde emir


def test_screen_matches_referee_on_simple_fixture(tmp_path):
    kl = market()
    t = mom(kl, 24, 1000.0)
    sp = referee.Spec(tick="0.01", step="0.0001", capital=10000.0, liq=False, fee_rt_bps=10.0)
    ref = referee.run(kl, t, sp)["summary"]["net_pnl"]
    scr = screen.screen(kl, {"a": t}, 10.0, tmp_path / "l.jsonl", capital=10000.0)["a"]
    assert scr == pytest.approx(ref, abs=0.05 * max(1.0, abs(ref)) + 0.5)  # yuvarlama farkı içinde; eşik deneysel


def test_every_screened_config_is_ledgered_without_results(tmp_path):
    kl = market()
    p = tmp_path / "l.jsonl"
    targets = {f"mom{n}": mom(kl, n, 500.0) for n in (6, 12, 24)}
    s = screen.screen(kl, targets, 10.0, p, hypothesis="fixture", data_hash="x")
    q = ledger.query(p, "select trial, source, result, score from ledger order by trial")
    assert len(s) == 3 and len(q) == 3 and set(q.source) == {"screen"} and q.result.isna().all()
    assert ledger.trial_count(p) == 3  # deneme sayacına girdi
