"""Synthetic canonical-tape adapter checks: no network or market download."""
import importlib.util
import sys
import types
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "erf01_tape.py"


def _subject():
    spec = importlib.util.spec_from_file_location("erf01_tape_subject", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fixture(monkeypatch, tmp_path, issues=None):
    symbol = "BTCUSDT"
    for kind in ("klines", "markPriceKlines", "fundingRate"):
        f = tmp_path / "tape" / kind / f"{symbol}.parquet"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"synthetic placeholder; tape.load is monkeypatched")

    hours = pd.date_range("2025-01-01", periods=25, freq="h", tz="UTC")
    values = np.arange(25, dtype=float) + 100
    kl = pd.DataFrame({"open": values, "high": values + 1, "low": values - 1,
                       "close": values, "volume": np.ones(25)}, index=hours)
    mk = kl.copy()
    funding_ts = pd.date_range("2025-01-01", periods=3, freq="8h", tz="UTC")
    fr = pd.DataFrame({"funding_interval_hours": [8.0] * 3,
                       "last_funding_rate": [.0001] * 3}, index=funding_ts)

    tape = types.ModuleType("kepler.tape")
    tape.load = lambda *a, **kw: {"klines": kl, "mark": mk, "funding": fr}
    qc = types.ModuleType("kepler.qc")
    qc.SEAL_START = pd.Timestamp("2026-04-01", tz="UTC")
    qc.check_frame = lambda frame, kind: issues or []
    qc.check_mark_vs_kline = lambda *_: []
    qc.divergence_cutoff = lambda *_: None
    kepler = types.ModuleType("kepler")
    kepler.tape, kepler.qc = tape, qc
    monkeypatch.setitem(sys.modules, "kepler", kepler)
    monkeypatch.setitem(sys.modules, "kepler.tape", tape)
    monkeypatch.setitem(sys.modules, "kepler.qc", qc)
    return qc


def test_canonical_tape_ignores_incomplete_utc_day(monkeypatch, tmp_path):
    _fixture(monkeypatch, tmp_path)
    kl, funding, frows, meta, acquisition = _subject().load_development(
        tmp_path, ["BTCUSDT"], date(2025, 1, 1), date(2025, 1, 3), date(2026, 4, 1))
    assert sorted(kl["BTCUSDT"]) == [date(2025, 1, 1)]
    assert len(funding["BTCUSDT"]) == len(frows) == 3
    assert meta["BTCUSDT"]["dropped_incomplete_days"] == 1
    assert acquisition["complete"] and acquisition["record_count"] == 3


def test_canonical_tape_fails_on_qc_error(monkeypatch, tmp_path):
    _fixture(monkeypatch, tmp_path, [{"severity": "ERROR", "check": "bad_candle"}])
    with pytest.raises(RuntimeError, match="QC errors"):
        _subject().load_development(
            tmp_path, ["BTCUSDT"], date(2025, 1, 1), date(2025, 1, 3), date(2026, 4, 1))


def test_canonical_tape_fails_on_seal_drift(monkeypatch, tmp_path):
    qc = _fixture(monkeypatch, tmp_path)
    qc.SEAL_START = pd.Timestamp("2026-05-01", tz="UTC")
    with pytest.raises(RuntimeError, match="seal"):
        _subject().load_development(
            tmp_path, ["BTCUSDT"], date(2025, 1, 1), date(2025, 1, 3), date(2026, 4, 1))
