"""Integration regressions: identities, single/batch failures and worker-private ledgers."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from kepler import evaluate, ledger, receipt, referee

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ledger_jobs


def frame():
    ix = pd.date_range("2024-01-01", periods=40, freq="1h", tz="UTC")
    return pd.DataFrame(dict(open=100., high=100., low=100., close=100., volume=1e6), index=ix)


def signal(k):
    return pd.Series(1., index=k.index)


def book(kls):
    return {s: pd.DataFrame(dict(target=100., stop=np.nan), index=k.index) for s, k in kls.items()}


def alternative_book(kls):
    return {s: pd.DataFrame(dict(target=-100., stop=np.nan), index=k.index) for s, k in kls.items()}


SP = referee.Spec(capital=1000, fee_rt_bps=10, slip_rt_bps=2)


def test_rule_order_target_and_callable_changes_cannot_collide():
    a, b = {"A": dict(kl=frame(), step=".001")}, {"B": dict(kl=frame())}
    cfg = dict(spec=SP.__dict__)
    def identity(d, fn=book):
        return receipt.make(cfg, d, book=fn)["economic_id"]
    assert identity(a) != identity({"A": dict(a["A"], step=".005")})
    assert identity(a) != identity(a, alternative_book)
    assert identity(a | b) != identity(b | a)
    assert identity(a) != identity({"A": dict(a["A"], target=pd.Series(10., index=frame().index))})
    assert identity(a) == identity(a)


@pytest.mark.parametrize("batch", [False, True])
def test_motor_failure_survives_both_evaluator_routes(tmp_path, monkeypatch, batch):
    def crash(*args, **kwargs):
        raise RuntimeError("deliberate engine failure")
    path = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(referee, "run_many" if batch else "run", crash)
    with pytest.raises(RuntimeError, match="deliberate"):
        if batch:
            evaluate.evaluate_book(book, {"A": dict(kl=frame())}, [SP, replace(SP, fee_rt_bps=16)], path, "h", "d")
        else:
            evaluate.evaluate(signal, frame(), [SP], path, "h", "d")
    rows = [json.loads(l) for l in path.read_text().splitlines()]
    assert len(rows) == (2 if batch else 1)
    assert all(r["status"] == "failed" and r["result"] is None and "deliberate" in r["reason"] for r in rows)


def test_distributed_workers_do_not_write_shared_target_and_collector_is_idempotent(tmp_path, monkeypatch):
    private, target = tmp_path / "jobs", tmp_path / "shared.jsonl"
    monkeypatch.setenv("KEPLER_JOB_RECEIPTS", str(private))
    for n in range(3):
        rc = receipt.make(dict(n=n), {"A": dict(kl=frame())})
        ledger.record(target, "referee", "h", dict(audit_causal=True), "c", "d", result=dict(net_pnl=n), receipt=rc)
    assert not target.exists() and len(list(private.glob("*.jsonl"))) == 3
    assert ledger_jobs.collect(private)["jobs"] == 3
    before = target.read_bytes()
    ledger_jobs.collect(private)
    assert target.read_bytes() == before
    assert [r["trial"] for r in map(json.loads, target.read_text().splitlines())] == [1, 2, 3]


def test_summary_only_scans_preserve_full_intent_accounting():
    k = frame()
    t = pd.Series(np.nan, index=k.index)
    t.iloc[[0, 2, 5, 8]] = [100, 100.4, 100.04, 0]
    data = {"A": dict(kl=k, target=t)}
    a = referee.run_many(data, [SP], full=True)[0]
    b = referee.run_many(data, [SP], full=False)[0]
    assert a["summary"] == b["summary"]


def test_collector_missing_expected_receipt_fails(tmp_path):
    with pytest.raises(ValueError, match="missing"):
        ledger_jobs.aggregate(tmp_path, tmp_path / "out", expected_jobs=["absent.jsonl"])


def test_complete_receipt_publication_is_concurrent_and_legacy_retry_safe(tmp_path):
    row = dict(config_hash="abc", attempt=1, status="completed", result=dict(net=1.))
    with ThreadPoolExecutor(8) as pool:
        paths = list(pool.map(lambda _: ledger_jobs.write_job_receipt(tmp_path, row), range(32)))
    assert len(set(paths)) == 1
    assert json.loads((paths[0] / "row.json").read_text()) == row
    assert ledger_jobs.aggregate(tmp_path, tmp_path / "merged.jsonl")["n"] == 1
    before = (tmp_path / "merged.jsonl").read_bytes()
    assert ledger_jobs.aggregate(tmp_path, tmp_path / "merged.jsonl")["n"] == 1
    assert (tmp_path / "merged.jsonl").read_bytes() == before
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    old = legacy / "abc.1.completed.json"
    old.write_text(json.dumps(row, sort_keys=True))
    assert ledger_jobs.write_job_receipt(legacy, row) == old
    with pytest.raises(ValueError, match="duplicate"):
        ledger_jobs.write_job_receipt(legacy, dict(row, result=dict(net=2.)))


def test_command_lifecycle_detects_missing_unfinished_and_pre_evaluator_failure(tmp_path):
    ledger_jobs.command_status(tmp_path, 0, "running", "preflight")
    with pytest.raises(ValueError, match="unfinished"):
        ledger_jobs.collect(tmp_path, expected_workers=1)
    ledger_jobs.command_status(tmp_path, 0, "failed", "preflight", 23)
    assert ledger_jobs.collect(tmp_path, expected_workers=1)["failed_commands"] == 1
    with pytest.raises(ValueError, match="missing"):
        ledger_jobs.collect(tmp_path, expected_workers=2)
