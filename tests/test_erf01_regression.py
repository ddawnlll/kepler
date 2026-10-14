"""ERF-01 acquisition and temporal-calibration regression tests (no network/G3)."""
import hashlib
import importlib.util
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "erf01.py"


def get_module():
    spec = importlib.util.spec_from_file_location("erf01_regression_subject", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_calibration_is_purged_before_heldout():
    mod = get_module()
    start = date(2021, 1, 1)
    rows = [(start + timedelta(days=i), "BTCUSDT", i % 3, np.zeros(2)) for i in range(210)]
    early, calibration = mod._calibration_split(rows)
    assert max(r[0] for r in early) + timedelta(days=17) < min(r[0] for r in calibration)
    assert not ({r[0] for r in early} & {r[0] for r in calibration})


def test_operational_threshold_uses_calibration_rows_only():
    mod = get_module()
    d = date(2024, 1, 1)
    rows = [(d + timedelta(days=i), "BTCUSDT", 0, np.zeros(2)) for i in range(5)]
    scores = np.array([.2, .45, .7, .9, .3])
    probabilities = np.column_stack([1 - scores, scores, np.zeros(5)])
    threshold, _, false, exposure = mod._choose_threshold(rows, probabilities)
    assert threshold > .9
    assert false == 0
    assert exposure == pytest.approx(5 / 365.25)


def test_alert_cooldown_crosses_fold_boundary():
    mod = get_module()
    start = date(2025, 1, 1)
    def row(offset):
        return (start + timedelta(days=offset), "BTCUSDT", 1, np.zeros(2))
    p = np.array([[.05, .90, .05]])
    state = {}
    first = mod._alert_episodes([row(0)], p, .6, state)
    second = mod._alert_episodes([row(3)], p, .6, state)
    third = mod._alert_episodes([row(7)], p, .6, state)
    assert len(first) == len(third) == 1
    assert second == []
    assert state["BTCUSDT"] == start + timedelta(days=7)


def test_acquisition_must_be_complete_and_has_provenance(tmp_path):
    mod = get_module()
    raw = tmp_path / "raw"
    raw.mkdir()
    with pytest.raises(RuntimeError, match="incomplete"):
        mod._verify_acquisition({"complete": True, "records": [], "record_count": 0,
                                 "expected_archives": 1, "workers": 12}, raw)
    blob = raw / "klines" / "BTCUSDT" / "2025-01.zip"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"fixture")
    rec = {"symbol": "BTCUSDT", "kind": "klines", "month": "2025-01",
           "sha256": hashlib.sha256(b"fixture").hexdigest()}
    a = {"complete": True, "errors": [], "records": [rec], "record_count": 1,
         "expected_archives": 1, "workers": 12, "raw_root": str(raw)}
    mod._verify_acquisition(a, raw)
    blob.write_bytes(b"mutated")
    with pytest.raises(RuntimeError, match="modified"):
        mod._verify_acquisition(a, raw)
    blob.write_bytes(b"fixture")
    with pytest.raises(RuntimeError, match="raw_root"):
        mod._verify_acquisition(a, tmp_path)


def test_protocol_missing_aborts_before_network(monkeypatch, tmp_path):
    mod = get_module()
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    with pytest.raises(FileNotFoundError, match="protocol"):
        mod.fetch(tmp_path / "not_downloaded", workers=1)
    assert not (tmp_path / "not_downloaded").exists()


def test_real_label_path_and_purge_boundary():
    mod = get_module()
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(42)]
    q = np.zeros(42)
    q[12:21] = 1
    panel = {s: {"q": q} for s in mod.SYMS}
    outcomes, events, candidates = mod.labels_for(panel, dates)
    assert len(events) == len(mod.SYMS)
    assert all(outcomes[s][5] == 1 for s in mod.SYMS)
    assert all(outcomes[s][12] == 0 for s in mod.SYMS)
    start = dates[30]
    train = [d for d in dates if d < start - timedelta(days=17)]
    assert all(d + timedelta(days=17) < start for d in train)
