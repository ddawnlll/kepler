"""#13: başarısız/geçersiz denemeler kaybolmaz; job-receipt + deterministik toplama; retry/smoke ayrımı."""
import json
import multiprocessing as mp

import numpy as np
import pandas as pd
import pytest

import sys
from pathlib import Path

from kepler import evaluate, ledger, receipt

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ledger_jobs  # noqa: E402
from kepler.referee import Spec

CFG = dict(audit_causal=True, name="x")


def test_invalid_run_recorded_without_performance(tmp_path):
    p = tmp_path / "l.jsonl"
    with pytest.raises(ledger.InvalidRun):
        ledger.record(p, "referee", "h", CFG, "c", "d", result=dict(net_pnl=5.0, n_rejected=2, funding_missed=0))
    assert not p.exists()  # record performans satırı yazmaz
    r = ledger.record_attempt(p, "invalid", "h", CFG, "c", "d", reason="n_rejected=2", result=dict(net_pnl=5.0, n_rejected=2))
    assert r["status"] == "invalid" and r["result"] is None and r["invalid_result"]["net_pnl"] == 5.0 and ledger.trial_count(p) == 1
    assert ledger.invalid_reason(dict(n_engine_unfilled=1)) and ledger.invalid_reason(dict(net_pnl=1.0)) is None


def test_statuses_and_failed_attempt(tmp_path):
    p = tmp_path / "l.jsonl"
    for st in ("planned", "running", "failed", "incomplete"):
        assert ledger.record_attempt(p, st, "h", CFG, "c", "d", reason=st)["status"] == st
    with pytest.raises(ValueError):
        ledger.record_attempt(p, "completed", "h", CFG, "c", "d")
    with pytest.raises(ValueError):
        ledger.record_attempt(p, "bogus", "h", CFG, "c", "d")
    assert ledger_jobs.summary(p)["by_status"] == dict(planned=1, running=1, failed=1, incomplete=1)


def test_retry_and_smoke_not_independent_hypotheses(tmp_path):
    p = tmp_path / "l.jsonl"
    rc = receipt.make(CFG, {"A": dict(kl=pd.DataFrame({"close": [1.0]}, index=pd.date_range("2024", periods=1, tz="UTC")))})
    a = ledger.record(p, "referee", "h", CFG, "c", "d", result=dict(net_pnl=1.0), receipt=rc)
    b = ledger.record(p, "referee", "h", CFG, "c", "d", result=dict(net_pnl=1.0), receipt=rc, kind="retry")
    ledger.record(p, "referee", "h", CFG, "c", "d", result=dict(net_pnl=1.0), receipt=rc, kind="smoke")
    assert (a["attempt"], b["attempt"]) == (1, 2)
    s = ledger_jobs.summary(p)
    assert s["rows"] == 3 and s["independent_hypotheses"] == 1 and s["retries_or_smoke"] == 2 and s["max_attempt"] == 3
    other = receipt.make(dict(CFG, symbol="B"), {"B": dict(kl=pd.DataFrame({"close": [1.0]}, index=pd.date_range("2024", periods=1, tz="UTC")))})
    ledger.record(p, "referee", "h", dict(CFG, symbol="B"), "c", "d", result=dict(net_pnl=1.0), receipt=other)
    assert ledger_jobs.summary(p)["independent_hypotheses"] == 2  # farklı sembol/config ayrı iş


def _job(args):
    d, i = args
    row = dict(source="referee", hypothesis="h", config=dict(i=i), config_hash=ledger.sha(dict(i=i)), code_hash="c", data_hash="d", result=dict(net_pnl=float(i)), score=None, status="completed", attempt=1)
    ledger_jobs.write_job_receipt(d, row)
    return i


def test_two_concurrent_jobs_no_loss_unique_order_idempotent(tmp_path):
    d = tmp_path / "rc"
    with mp.get_context("fork").Pool(4) as pool:
        pool.map(_job, [(d, i) for i in range(40)] + [(d, i) for i in range(20)])  # 20 tekrar (aynı içerik): idempotent
    out = tmp_path / "ledger.jsonl"
    a = ledger_jobs.aggregate(d, out)
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert a["n"] == 40 and [r["trial"] for r in rows] == list(range(1, 41)) and sorted(r["result"]["net_pnl"] for r in rows) == [float(i) for i in range(40)]
    assert ledger_jobs.aggregate(d, out)["sha"] == a["sha"]  # tekrar toplama aynı sonuç


def test_conflicting_duplicate_and_corrupt_receipt_error(tmp_path):
    d = tmp_path / "rc"
    row = dict(config_hash="h" * 8, status="completed", attempt=1, result=dict(net_pnl=1.0))
    ledger_jobs.write_job_receipt(d, row)
    ledger_jobs.write_job_receipt(d, row)
    with pytest.raises(ValueError, match="çelişkili"):
        ledger_jobs.write_job_receipt(d, dict(row, result=dict(net_pnl=2.0)))
    (d / "zzz.json").write_text('{"x": ')
    with pytest.raises(ValueError, match="bozuk"):
        ledger_jobs.aggregate(d, tmp_path / "o.jsonl")
    assert not (tmp_path / "o.jsonl").exists()  # yarım çıktı yok


def test_evaluate_book_records_invalid_and_failed(tmp_path, monkeypatch):
    n = 30
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    c = np.full(n, 100.0)
    kl = pd.DataFrame(dict(open=c, high=c, low=c, close=c, volume=1e6), index=idx)
    data = {"A": dict(kl=kl, funding=pd.DataFrame({"last_funding_rate": [0.0001]}, index=[pd.Timestamp("2024-01-01 08:00", tz="UTC")]), mark=kl)}

    def book(kls):
        t = pd.Series(np.nan, index=idx)
        t.iloc[1] = 1000.0
        return {"A": pd.DataFrame(dict(target=t, stop=np.nan), index=idx)}
    sp = Spec(capital=10000.0, fee_rt_bps=10.0, slip_rt_bps=2.0, tick="0.1", step="0.001", fill="next_open")
    p = tmp_path / "l.jsonl"
    ok = evaluate.evaluate_book(book, data, [sp], p, "h", "d")
    assert ok[0]["row"]["status"] == "completed" and "recon_diff" in ok[0]["res"]["summary"]
    assert ledger_jobs.summary(p)["by_status"] == dict(completed=1)
    orig = evaluate.referee.run_portfolio
    monkeypatch.setattr(evaluate.referee, "run_portfolio", lambda *a, **k: (lambda r: (r["summary"].update(n_engine_unfilled=1), r)[1])(orig(*a, **k)))
    with pytest.raises(ledger.InvalidRun):
        evaluate.evaluate_book(book, data, [sp], p, "h", "d")  # motor kaynaklı dolumsuz: performansa girmez ama araştırma izinde kalır
    monkeypatch.setattr(evaluate.referee, "run_portfolio", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("motor çöktü")))
    with pytest.raises(RuntimeError):
        evaluate.evaluate_book(book, data, [sp], p, "h", "d")
    s = ledger_jobs.summary(p)
    assert s["by_status"] == dict(completed=1, invalid=1, failed=1)
    rows = [json.loads(l) for l in p.read_text().splitlines()]
    assert rows[1]["result"] is None and rows[1]["invalid_result"]["n_engine_unfilled"] == 1 and "motor çöktü" in rows[2]["reason"]
