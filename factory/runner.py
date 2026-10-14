"""One supervised worker, durable claims, bounded retry, immutable commit jobs."""
import json
import signal
import subprocess
import time
import uuid

from factory import enqueue, policy, store
from factory.merge_gate import check, git
from factory.research import validate as validate_research


def reconcile(con, config, queue=enqueue.QUEUE):
    for q in enqueue.latest(queue).values():
        payload = q.get("payload", {})
        if not payload or q["status"] not in {"open", "approved"}:
            continue
        if payload.get("kind") not in {"check", "research"}:
            continue  # unknown operations never become executable commands
        base = git("rev-parse", "refs/heads/main").decode().strip()
        try:
            if payload["kind"] == "research":
                if q["type"] != "C" or q["status"] != "approved" or "approved_by_uid" not in q:
                    continue
                job = validate_research(payload, config)
            else:
                if set(payload) != {"kind", "commit"}:
                    raise ValueError("check payload şeması")
                check(payload["commit"], base)
                job = {**payload, "base": base, "policy": config}
            with store.transaction(con):
                store.add_job(con, q["id"], job)
        except (ValueError, TypeError, KeyError, PermissionError) as exc:
            store.notify(con, "rejected:" + q["id"], f"İş reddedildi: {str(exc)[:300]}")


def control(con):
    row = con.execute("SELECT value FROM meta WHERE key='control'").fetchone()
    return row[0] if row else "paused"  # installation never starts work automatically


def stop_unit(token):
    subprocess.run(["sudo", "-n", "/usr/local/sbin/kepler-sandbox", "stop", token], check=True, timeout=30)


def recover(con, config, now=None):
    now = time.time() if now is None else now
    for row in con.execute("SELECT * FROM jobs WHERE state='running' AND heartbeat<?", (now - config["lease_seconds"],)).fetchall():
        stop_unit(row["token"])  # fence the old process BEFORE releasing the claim
        finish(con, row, config, 75, "worker heartbeat kayıp", now)


def claim(con, config, now=None):
    now = time.time() if now is None else now
    with store.transaction(con):
        if control(con) != "running" or con.execute("SELECT count(*) FROM jobs WHERE state='running'").fetchone()[0]:
            return None
        row = con.execute("SELECT * FROM jobs WHERE state='ready' AND next_at<=? ORDER BY next_at,id LIMIT 1", (now,)).fetchone()
        if not row:
            return None
        token = uuid.uuid4().hex
        con.execute("UPDATE jobs SET state='running',attempts=attempts+1,token=?,heartbeat=?,started=?,error=NULL WHERE id=?",
                    (token, now, now, row["id"]))
        store.event(con, "started", {"id": row["id"], "token": token})
        return dict(con.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone())


def finish(con, job, config, rc, error, now=None):
    now = time.time() if now is None else now
    research = json.loads(job["payload"])["kind"] == "research"
    retry = rc == 75 and not research and job["attempts"] < config["max_attempts"]
    state = "ready" if retry else "done" if rc == 0 else "unknown" if research and rc != 0 else "failed"
    with store.transaction(con):
        changed = con.execute("UPDATE jobs SET state=?,ended=?,exit_code=?,error=?,next_at=? WHERE id=? AND token=? AND state='running'",
                              (state, now, rc, error[:500], now + min(900, 30 * 2 ** job["attempts"]), job["id"], job["token"])).rowcount
        if changed:
            store.event(con, state, {"id": job["id"], "rc": rc})
            store.notify(con, f"job:{job['id']}:{job['attempts']}", f"İş {job['id']}: {state}; çıkış {rc}")


def execute(con, job, config):
    payload = json.loads(job["payload"])
    if payload.get("kind") not in {"check", "research"} or payload.get("policy") != config:
        finish(con, job, config, 78, "politika değişti veya bilinmeyen iş")
        return
    process = None
    try:
        if payload["kind"] == "research":
            validate_research({k: v for k, v in payload.items() if k not in {"policy", "code_hash"}}, config)
            command = ["sudo", "-n", "/usr/local/sbin/kepler-research", job["token"], payload["commit"],
                       json.dumps({"script": payload["script"], "argv": payload["argv"]})]
        else:
            check(payload["commit"], payload["base"])
            command = ["sudo", "-n", "/usr/local/sbin/kepler-sandbox", "run", job["token"], payload["commit"]]
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        started = time.monotonic()
        while process.poll() is None:
            if control(con) == "stop" or time.monotonic() - started > config["timeout_seconds"]:
                stop_unit(job["token"])
                process.wait(timeout=30)
                finish(con, job, config, 124, "durduruldu veya süre sınırı")
                return
            con.execute("UPDATE jobs SET heartbeat=? WHERE id=? AND token=? AND state='running'", (time.time(), job["id"], job["token"]))
            time.sleep(config["heartbeat_seconds"])
        if process.returncode == 0 and payload["kind"] == "research":
            import hashlib
            from pathlib import Path
            from factory.ledger_writer import ingest
            folder = Path("/var/lib/kepler-results") / job["token"] / "spool"
            receipt = json.loads((folder / "receipt.json").read_text())
            events = list(folder.glob("*/event.json"))
            if receipt != {"token": job["token"], "exit_code": 0, "code_hash": payload["code_hash"], "events": len(events)}:
                raise ValueError("tamamlanma/kod/event mutabakatı başarısız")
            targets = {json.loads(p.read_text())["ledger"] for p in events}
            for producer in targets:
                name = hashlib.sha256(producer.encode()).hexdigest()[:16] + ".jsonl"
                ingest(folder, Path("/srv/kepler/ledger/factory") / job["id"] / name,
                       expected_code=payload["code_hash"], expected_data=payload["data_hash"], producer_ledger=producer)
        finish(con, job, config, process.returncode, "" if process.returncode == 0 else "kontrol başarısız; journal'a bak")
    except (ValueError, TypeError, PermissionError, OSError, subprocess.SubprocessError) as exc:
        if process is not None:
            stop_unit(job["token"])
            process.wait(timeout=30)
        finish(con, job, config, 78, str(exc)[:500])
    except BaseException:
        if process is not None:
            stop_unit(job["token"])
            process.wait(timeout=30)
        finish(con, job, config, 75, "çalıştırıcı kesildi")
        raise


def main():
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    config = policy.load()
    with store.connect() as con:
        while True:
            try:
                recover(con, config)
                reconcile(con, config)
                con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('runner_heartbeat',?)", (str(time.time()),))
                job = claim(con, config)
                if job:
                    execute(con, job, config)
                else:
                    time.sleep(5)
            except (ValueError, PermissionError, subprocess.SubprocessError, OSError) as exc:
                store.event(con, "infra", {"error": str(exc)[:500]})
                time.sleep(5)


if __name__ == "__main__":
    main()
