"""Security/regression cases for future execution; no privileged host actions are performed."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from factory import broker, enqueue
from kepler import ledger


def guard_module():
    path = Path(__file__).resolve().parents[1] / ".claude/hooks/guard.py"
    spec = importlib.util.spec_from_file_location("test_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_engine_and_deleted_core_are_protected(monkeypatch):
    guard = guard_module()
    monkeypatch.delenv("KEPLER_CORE_UNLOCK", raising=False)
    assert guard.classify("kepler/referee_core.py", False)[0] == "deny"
    monkeypatch.setattr(guard, "_arch_test", lambda: (True, ""))
    monkeypatch.setattr(guard.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="D\tkepler/referee.py\n", returncode=0))
    assert guard.staged() == 1


def test_hash_tracks_engine_experts_scripts_and_lock(tmp_path, monkeypatch):
    package = tmp_path / "kepler"
    (package / "experts").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    files = [package / "referee_core.py", package / "experts/trend.py", tmp_path / "scripts/experiment.py",
             tmp_path / "uv.lock", tmp_path / "pyproject.toml"]
    for f in files:
        f.write_text("original\n")
    monkeypatch.setattr(ledger, "__file__", str(package / "ledger.py"))
    initial = ledger.code_hash()
    for f in files:
        f.write_text("changed\n")
        assert ledger.code_hash() != initial
        f.write_text("original\n")
    files[0].rename(package / "renamed.py")
    assert ledger.code_hash() != initial


@pytest.mark.parametrize("kind,state", [("status", "approved"), ("result", "done"), ("brief", "running")])
def test_agent_cannot_bypass_waiting_approval(tmp_path, kind, state):
    q = tmp_path / "queue.jsonl"
    identity = enqueue.enqueue("sekreter", "C", "request", "çekirdek işi", path=q)
    with pytest.raises(PermissionError):
        enqueue.enqueue("mudur", "C", kind, "atlat", id=identity, status=state, path=q)
    assert enqueue.latest(q)[identity]["status"] == "needs_human"


def test_payload_and_type_cannot_be_replaced(tmp_path):
    q = tmp_path / "queue.jsonl"
    identity = enqueue.enqueue("sekreter", "A", "directive", "test", payload={"commit": "a"}, path=q)
    for type_, payload in [("C", {"commit": "a"}), ("A", {"commit": "b"})]:
        with pytest.raises(ValueError):
            enqueue.enqueue("mudur", type_, "status", "test", id=identity, payload=payload, path=q)
    with pytest.raises(ValueError):
        enqueue.enqueue("mudur", "A", "status", "test", path=q, approved_by_uid=0)


def test_idempotency_survives_completion(tmp_path):
    q = tmp_path / "queue.jsonl"
    identity = enqueue.enqueue("sekreter", "A", "directive", "test", idempotency_key="update:12", path=q)
    enqueue.enqueue("mudur", "A", "result", "bitti", id=identity, status="done", path=q)
    assert enqueue.enqueue("sekreter", "A", "directive", "test", idempotency_key="update:12", path=q) == identity
    assert len(q.read_text().splitlines()) == 2


def test_symlink_and_partial_queue_fail_closed(tmp_path):
    real = tmp_path / "real"
    real.write_text("")
    link = tmp_path / "link"
    link.symlink_to(real)
    with pytest.raises(OSError):
        enqueue.enqueue("sekreter", "A", "directive", "test", path=link)
    real.write_text('{"id":"unfinished"}')
    with pytest.raises(ValueError):
        enqueue.latest(real)


def test_peer_identity_cannot_be_claimed_by_json(monkeypatch, tmp_path):
    monkeypatch.setattr(broker.pwd, "getpwuid", lambda uid: SimpleNamespace(pw_name="kagent"))
    with pytest.raises(PermissionError):
        broker.handle({"op": "approve", "id": "12345678"}, 1001, queue=tmp_path / "q")
    with pytest.raises(PermissionError):
        broker.handle({"op": "enqueue", "from": "insan", "type": "A", "kind": "request", "text": "x"}, 1001, queue=tmp_path / "q")
    with pytest.raises(PermissionError):
        broker.handle({"op": "enqueue", "from": "mudur", "type": "A", "kind": "request", "text": "x"}, 1001, queue=tmp_path / "q")
    for operation in ("stop", "review"):
        with pytest.raises(PermissionError):
            broker.handle({"op": operation, "id": "12345678"} if operation == "review" else {"op": operation}, 1001, queue=tmp_path / "q")
    for request in [{"op": []}, {"op": "status", "uid": 0}, {"op": "enqueue", "path": "/tmp/x"}]:
        with pytest.raises(ValueError):
            broker.handle(request, 1001, queue=tmp_path / "q")


def test_spool_does_not_break_local_test_ledgers(tmp_path, monkeypatch):
    monkeypatch.setenv("KEPLER_LEDGER_SPOOL", str(tmp_path / "spool"))
    target = tmp_path / "local.jsonl"
    assert ledger.record(target, "screen", "h", {}, "c", "d", score=0)["trial"] == 1
    assert target.exists()


def test_modal_direct_ledger_write_is_rejected(monkeypatch):
    monkeypatch.delenv("KEPLER_LEDGER_SPOOL", raising=False)
    with pytest.raises(ValueError):
        ledger.record("/data/never-created-by-test.jsonl", "screen", "h", {}, "c", "d", score=0)


def test_stable_spool_identity_and_single_writer(tmp_path, monkeypatch):
    from factory.ledger_writer import ingest
    spool = tmp_path / "spool"
    monkeypatch.setenv("KEPLER_LEDGER_SPOOL", str(spool))
    monkeypatch.setenv("KEPLER_RUN_ID", "same-job")
    a = ledger.record("/data/run/a.jsonl", "screen", "h", {}, "c", "d", score=0)
    b = ledger.record("/data/run/a.jsonl", "screen", "h", {}, "c", "d", score=0)
    ledger.record("/data/run/b.jsonl", "screen", "other", {}, "c", "d", score=0)
    assert a["trial"] is None and a["event_id"] == b["event_id"]
    monkeypatch.delenv("KEPLER_LEDGER_SPOOL")
    target = tmp_path / "ledger.jsonl"
    ingest(spool, target, expected_code="c", expected_data="d", producer_ledger="/data/run/a.jsonl")
    ingest(spool, target, expected_code="c", expected_data="d", producer_ledger="/data/run/a.jsonl")
    assert ledger.trial_count(target) == 1
    payload_file = next(spool.glob("*/event.json"))
    payload = json.loads(payload_file.read_text())
    payload["row"]["data_hash"] = "wrong"
    payload_file.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        ingest(spool, target, expected_code="c", expected_data="d", producer_ledger=payload["ledger"])
