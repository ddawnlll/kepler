"""Durability, fencing, delivery and recovery checks; subprocess/network boundaries mocked."""
import json
from pathlib import Path

import pytest

from factory import outbox, runner, store
from factory.status import runtime_status

CONFIG = json.loads((Path(__file__).resolve().parents[1] / "factory/policy.json").read_text())


def ready(con, identity="12345678", kind="check"):
    store.add_job(con, identity, {"kind": kind, "commit": "a" * 40, "base": "b" * 40, "policy": CONFIG})
    con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('control','running')")


def test_claim_is_durable_exclusive_and_paused_by_default(tmp_path):
    db = tmp_path / "runtime.sqlite3"
    with store.connect(db) as con:
        store.add_job(con, "12345678", {"kind": "check"})
        assert runner.claim(con, CONFIG, 100) is None
        con.execute("INSERT INTO meta VALUES('control','running')")
        claimed = runner.claim(con, CONFIG, 100)
        assert claimed["attempts"] == 1
        assert runner.claim(con, CONFIG, 101) is None
    with store.connect(db) as con:
        assert con.execute("SELECT state FROM jobs").fetchone()[0] == "running"


def test_recovery_fences_before_requeue_and_rejects_old_completion(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(runner, "stop_unit", calls.append)
    with store.connect(tmp_path / "db") as con:
        ready(con)
        old = runner.claim(con, CONFIG, 100)
        runner.recover(con, CONFIG, 300)
        assert calls == [old["token"]]
        assert con.execute("SELECT state FROM jobs").fetchone()[0] == "ready"
        new = runner.claim(con, CONFIG, 500)
        runner.finish(con, old, CONFIG, 0, "", 501)
        assert con.execute("SELECT state,token FROM jobs").fetchone()[1] == new["token"]
        assert con.execute("SELECT state FROM jobs").fetchone()[0] == "running"


def test_bounded_retry_and_research_uncertainty(tmp_path):
    with store.connect(tmp_path / "db") as con:
        ready(con)
        for attempt in range(CONFIG["max_attempts"]):
            job = runner.claim(con, CONFIG, 1000 + attempt * 1000)
            runner.finish(con, job, CONFIG, 75, "transient", 1001 + attempt * 1000)
        assert con.execute("SELECT state FROM jobs").fetchone()[0] == "failed"
        ready(con, "research1", "research")
        research = runner.claim(con, CONFIG, 10000)
        runner.finish(con, research, CONFIG, 75, "remote result unknown", 10001)
        assert con.execute("SELECT state FROM jobs WHERE id='research1'").fetchone()[0] == "unknown"


def test_prelaunch_failure_finishes_job(tmp_path, monkeypatch):
    def rejected(*args):
        raise PermissionError("changed main")
    monkeypatch.setattr(runner, "check", rejected)
    with store.connect(tmp_path / "db") as con:
        ready(con)
        job = runner.claim(con, CONFIG)
        runner.execute(con, job, CONFIG)
        assert con.execute("SELECT state FROM jobs").fetchone()[0] == "failed"


def test_outbox_survives_restart_and_does_not_resend_acknowledged(tmp_path):
    db = tmp_path / "db"
    def unavailable(text):
        raise RuntimeError("offline")
    with store.connect(db) as con:
        store.notify(con, "result:1", "test")
        outbox.flush(con, unavailable, 100)
        assert con.execute("SELECT state FROM outbox").fetchone()[0] == "pending"
    delivered = []
    with store.connect(db) as con:
        outbox.flush(con, lambda text: delivered.append(text) or "42", 500)
        outbox.flush(con, lambda text: delivered.append(text) or "43", 1000)
        assert con.execute("SELECT state,message_id FROM outbox").fetchone()[1] == "42"
    assert len(delivered) == 1 and "result:1" in delivered[0]


def test_old_sending_attempt_is_recovered(tmp_path):
    with store.connect(tmp_path / "db") as con:
        store.notify(con, "notice", "test")
        con.execute("UPDATE outbox SET state='sending',updated=100")
        outbox.flush(con, lambda text: "42", 200)
        assert con.execute("SELECT state FROM outbox").fetchone()[0] == "sent"


def test_status_does_not_call_stale_runner_healthy(tmp_path):
    db = tmp_path / "db"
    with store.connect(db) as con:
        con.execute("INSERT INTO meta VALUES('runner_heartbeat','100')")
    assert "BAYAT" in runtime_status(db, now=500)[0]
    assert "güncel" in runtime_status(db, now=110)[0]


def test_job_identity_cannot_change_payload(tmp_path):
    with store.connect(tmp_path / "db") as con:
        store.add_job(con, "12345678", {"commit": "a"})
        with pytest.raises(ValueError):
            store.add_job(con, "12345678", {"commit": "b"})
