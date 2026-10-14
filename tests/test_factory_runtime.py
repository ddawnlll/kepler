"""Çalıştırıcı (kiralama, zaman aşımı, tekrar, durdurma), giden kutusu, acil durdurma ve birleştirme kapısı. Gerçek alt süreçlerle, stdlib."""
import json
import os
import subprocess
import sys
import time

import pytest

from factory import auth, enqueue, gate, halt, outbox, runner

KEY = "k" * 40
PY = [sys.executable, "-c"]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(enqueue, "QUEUE", tmp_path / "q.jsonl")
    monkeypatch.setattr(enqueue, "HALT", tmp_path / "HALT")
    monkeypatch.setattr(runner, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(runner, "BEAT_S", 0.2)
    monkeypatch.setattr(halt, "LOG", tmp_path / "halt_log.jsonl")
    monkeypatch.setenv(auth.KEY_ENV, KEY)
    return tmp_path


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def test_done_job_runs_once_and_queue_reflects_it(env):
    enqueue.enqueue("sekreter", "A", "directive", "tek koşu", id="job00001")
    assert runner.run("job00001", PY + ["print('ok')"], timeout=20) == 0
    assert enqueue.latest()["job00001"]["status"] == "done"
    with pytest.raises(RuntimeError):
        runner.claim("job00001", "başka")  # done: yeniden koşu yok (kuyruk durumu da bunu reddeder)


def test_timeout_kills_the_process_and_marks_failed(env):
    enqueue.enqueue("sekreter", "A", "directive", "uzun", id="job00002")
    assert runner.run("job00002", PY + ["import time; time.sleep(60)"], timeout=0.5) == 1
    rec = runner._read("job00002")
    assert rec["state"] == "failed" and rec["reason"] == "zaman aşımı" and not _alive(rec["pid"])
    assert enqueue.latest()["job00002"]["status"] == "failed"


def test_retry_is_bounded_and_counted(env):
    enqueue.enqueue("sekreter", "A", "directive", "hata", id="job00003")
    assert runner.run("job00003", PY + ["raise SystemExit(1)"], timeout=20, retries=1) == 1
    assert runner._read("job00003")["attempt"] == 2


def test_claim_refuses_unapproved_gated_job_and_halted_system(env):
    enqueue.enqueue("sekreter", "B", "request", "özellik")
    jid = next(iter(enqueue.latest()))
    with pytest.raises(RuntimeError, match="izinli durumda değil"):
        runner.claim(jid, "x")
    enqueue.approve(jid, "approved", "insan")
    enqueue.HALT.write_text("{}")
    with pytest.raises(RuntimeError, match="durdurma"):
        runner.claim(jid, "x")


def test_live_old_process_blocks_takeover(env):
    enqueue.enqueue("sekreter", "A", "directive", "çift", id="job00004")
    child = subprocess.Popen(PY + ["import time; time.sleep(30)"])
    try:
        runner.RUNS.mkdir(parents=True)
        runner._write("job00004", dict(job="job00004", state="running", attempt=1, pid=child.pid, heartbeat=time.time() - 9999))
        with pytest.raises(RuntimeError, match="yaşıyor"):  # kiralama dolmuş ama süreç hâlâ yaşıyor
            runner.claim("job00004", "yeni")
    finally:
        child.kill()
        child.wait()


def test_kill_running_terminates_live_jobs(env):
    child = subprocess.Popen(PY + ["import time; time.sleep(30)"], start_new_session=True)
    try:
        runner.RUNS.mkdir(parents=True)
        runner._write("job00005", dict(job="job00005", state="running", attempt=1, pid=child.pid, heartbeat=time.time()))
        assert runner.kill_running(grace=3) == ["job00005"]
        assert child.wait(timeout=10) != 0
    finally:
        if child.poll() is None:
            child.kill()


def test_release_needs_the_approval_key(env, monkeypatch):
    halt.engage("ajan", "test")
    assert enqueue.halted()
    monkeypatch.delenv(auth.KEY_ENV)
    with pytest.raises(PermissionError):
        halt.release("ajan")
    assert enqueue.halted()  # ajan imzasız kaldıramaz
    monkeypatch.setenv(auth.KEY_ENV, KEY)
    halt.release("insan")
    assert not enqueue.halted()
    assert any(json.loads(line).get("action") == "release" and json.loads(line)["sig"] for line in halt.LOG.read_text().splitlines())


def test_outbox_is_durable_and_deduplicated(env):
    path = env / "outbox.jsonl"
    assert outbox.send("k1", "merhaba", path) and not outbox.send("k1", "merhaba", path)
    sent = []

    def flaky(text):
        if not sent and not getattr(flaky, "ok", False):
            flaky.ok = True
            raise ConnectionError("ağ kesildi")
        sent.append(text)

    assert outbox.flush(flaky, path) == dict(delivered=0, failed=1)
    assert outbox.pending(path)[0]["key"] == "k1"  # yeniden başlatma: süreç yeni olsa da kayıt diskte
    assert outbox.flush(flaky, path) == dict(delivered=1, failed=0)
    assert outbox.flush(flaky, path) == dict(delivered=0, failed=0) and sent == ["merhaba"]  # tekrar teslim yok


def test_outbox_gives_up_after_max_tries_without_losing_the_record(env):
    path = env / "outbox.jsonl"
    outbox.send("k2", "ulaşmadı", path)

    def down(text):
        raise ConnectionError("kapalı")

    counts = outbox.deliver_until_done(down, path, sleep=lambda s: None)
    assert counts["delivered"] == 0 and not outbox.pending(path)
    assert "ulaşmadı" in path.read_text()  # kayıt silinmez


def test_gate_is_green_on_a_clean_base(env):
    problems, review = gate.check("HEAD")
    assert problems == [] and review == []
