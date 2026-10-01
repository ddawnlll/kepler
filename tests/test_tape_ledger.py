import numpy as np
import pandas as pd
import pytest

from kepler import ledger, tape


def write_tape(root, sym="TESTUSDT", n=48, start="2024-01-01"):
    ts = pd.date_range(start, periods=n, freq="1h", tz="UTC")
    c = 100 + np.arange(n, dtype=float)
    frames = {
        "klines": pd.DataFrame({"ts": ts, "open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 1.0, "ts_unit": "ms"}),
        "markPriceKlines": pd.DataFrame({"ts": ts, "open": c, "high": c, "low": c, "close": c, "volume": 0.0, "ts_unit": "ms"}),
        "fundingRate": pd.DataFrame({"ts": ts[::8], "funding_interval_hours": 8, "last_funding_rate": 1e-4, "ts_unit": "ms"}),
    }
    for kind, df in frames.items():
        (root / "tape" / kind).mkdir(parents=True, exist_ok=True)
        df.to_parquet(root / "tape" / kind / f"{sym}.parquet", index=False)


def test_load_returns_utc_indexed_frames(tmp_path):
    write_tape(tmp_path)
    t = tape.load(tmp_path, "TESTUSDT")
    assert set(t) == {"klines", "mark", "funding"}
    assert str(t["klines"].index.tz) == "UTC" and len(t["klines"]) == 48 and "ts_unit" not in t["klines"]
    assert len(tape.load(tmp_path, "TESTUSDT", start="2024-01-02")["klines"]) == 24  # tarih süzgeci


def test_load_refuses_sealed_period(tmp_path):
    write_tape(tmp_path)
    with pytest.raises(ValueError):
        tape.load(tmp_path, "TESTUSDT", end="2026-05-01")


def test_target_contract(tmp_path):
    write_tape(tmp_path)
    kl = tape.load(tmp_path, "TESTUSDT")["klines"]
    ok = pd.Series(np.nan, index=kl.index)
    assert tape.check_target(kl, ok) is ok
    for bad in (ok.iloc[:-1], ok.reset_index(drop=True), ok.astype(int) if False else pd.Series(1, index=kl.index),
                ok.where(ok.index != kl.index[3], np.inf), list(ok)):
        with pytest.raises(ValueError):
            tape.check_target(kl, bad)


def test_ledger_append_only_counts_and_queries(tmp_path):
    p = tmp_path / "ledger.jsonl"
    ledger.record(p, "screen", "h1", {"n": 10}, "c", "d", score=0.3)
    ledger.record(p, "referee", "h1", {"n": 10}, "c", "d", result={"net_pnl": 1.5})
    before = p.read_text().splitlines()
    ledger.record(p, "screen", "h2", {"n": 20}, "c", "d", score=0.1)
    after = p.read_text().splitlines()
    assert after[:2] == before and len(after) == 3  # önceki satırlar değişmedi
    assert ledger.trial_count(p) == 3
    q = ledger.query(p, "select trial, source, config_hash from ledger order by trial")
    assert list(q.trial) == [1, 2, 3] and list(q.source) == ["screen", "referee", "screen"]
    assert q.config_hash[0] == q.config_hash[1] != q.config_hash[2]  # aynı config -> aynı hash
    assert ledger.query(p, "select count(*) n from ledger where source='screen'").n[0] == 2  # eleme denemeleri de sayılıyor


def test_screen_cannot_write_results_and_referee_must(tmp_path):
    p = tmp_path / "l.jsonl"
    with pytest.raises(ValueError):
        ledger.record(p, "screen", "h", {}, "c", "d", result={"net_pnl": 1})
    with pytest.raises(ValueError):
        ledger.record(p, "referee", "h", {}, "c", "d")
    with pytest.raises(ValueError):
        ledger.record(p, "other", "h", {}, "c", "d", score=1)
    assert ledger.trial_count(p) == 0  # reddedilenler deftere girmedi
