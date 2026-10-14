"""Çalıştırıcı: iş başına tek sahip (kiralama), heartbeat, zaman aşımı, sınırlı yeniden deneme, durdurmada sonlandırma.

  python -m factory.runner <iş_kimliği> --timeout 3600 --retries 1 -- <komut ...>

İş yalnızca kuyrukta izinli durumdaysa alınır (A: open; B/C: insan onayı sonrası approved; önceki hata: failed).
Tamamlanmış (done) iş yeniden koşmaz. Kiralama süresi dolmuş ama süreci hâlâ yaşayan iş yeniden alınmaz (çift yürütme yok).
Çocuk süreç, çalıştırıcı ölürse PDEATHSIG ile kapanır (Linux). Teslim kimliği içerikten türediği için yeniden koşu defteri şişirmez."""
import argparse
import ctypes
import fcntl
import json
import os
import signal
import socket
import subprocess
import sys
import time

from factory import enqueue

RUNS = enqueue.ROOT / "state" / "runs"
LEASE_S, BEAT_S, GRACE_S = 120, 5, 10
CLAIMABLE = {"open", "approved", "failed", "running"}  # running: yalnızca kiralama süresi dolmuşsa (claim denetler)


def _alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:  # zombi (sonlanmış, toplanmamış) süreç yaşıyor sayılmaz; PID 1 toplamıyorsa kiralama sonsuza kadar kilitlenmesin
        return open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return True


def _read(job):
    p = RUNS / f"{job}.json"
    return json.loads(p.read_text()) if p.exists() else None


def _write(job, rec):
    RUNS.mkdir(parents=True, exist_ok=True)
    tmp = RUNS / f".{job}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(rec))
    os.replace(tmp, RUNS / f"{job}.json")  # atomik: yarım durum dosyası okunmaz


def claim(job: str, owner: str, lease: float = LEASE_S) -> dict:
    if enqueue.halted():
        raise RuntimeError("durdurma etkin: iş alınmıyor")
    q = enqueue.latest().get(job)
    if q is None or q["status"] not in CLAIMABLE:
        raise RuntimeError(f"{job} izinli durumda değil: {q and q['status']}")
    RUNS.mkdir(parents=True, exist_ok=True)
    with open(RUNS / f"{job}.lock", "a+") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        cur, now = _read(job), time.time()
        if cur and cur["state"] == "done":
            raise RuntimeError("iş zaten tamamlandı; yeniden koşulmuyor")
        if cur and cur["state"] == "running" and (now - cur["heartbeat"] < lease or _alive(cur["pid"])):
            raise RuntimeError("iş başka sahipte ya da eski süreç hâlâ yaşıyor")
        rec = dict(job=job, owner=owner, state="running", attempt=(cur or {}).get("attempt", 0) + 1, pid=None, started=now, heartbeat=now)
        _write(job, rec)
    return rec


def _pdeathsig():  # Linux: çalıştırıcı ölünce çocuk da ölür (eski süreç + yeni sahip çakışması olmaz)
    try:
        ctypes.CDLL("libc.so.6").prctl(1, signal.SIGKILL)
    except OSError:
        pass


def _kill(proc: subprocess.Popen) -> int:
    for sig, wait in ((signal.SIGTERM, GRACE_S), (signal.SIGKILL, 5)):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            break
        try:
            proc.wait(timeout=wait)
            break
        except subprocess.TimeoutExpired:
            continue
    return proc.wait()


def kill_running(grace: float = GRACE_S) -> list[str]:
    """Çalışan işlerin süreç gruplarını sonlandırır (TERM, sonra KILL). Halt'tan çağrılır; çalıştırıcı ayrı süreçte olabilir."""
    if not RUNS.exists():
        return []
    victims = [json.loads(p.read_text()) for p in RUNS.glob("*.json")]
    victims = [r for r in victims if r.get("state") == "running" and _alive(r.get("pid"))]
    for r in victims:
        try:
            os.killpg(r["pid"], signal.SIGTERM)
        except ProcessLookupError:
            pass
    end = time.time() + grace
    while time.time() < end and any(_alive(r["pid"]) for r in victims):
        time.sleep(0.2)
    for r in victims:
        if _alive(r["pid"]):
            try:
                os.killpg(r["pid"], signal.SIGKILL)
            except ProcessLookupError:
                pass
    return [r["job"] for r in victims]


def run(job: str, argv: list[str], timeout: float, retries: int = 0, owner: str | None = None) -> int:
    owner = owner or f"{socket.gethostname()}:{os.getpid()}"
    for n in range(retries + 1):
        try:
            rec = claim(job, owner)
        except RuntimeError as e:
            print(e, file=sys.stderr)
            return 2
        enqueue.enqueue("mudur", enqueue.latest()[job]["type"], "status", f"koşuyor (deneme {n + 1})", id=job, status="running")
        proc = subprocess.Popen(argv, start_new_session=True, preexec_fn=_pdeathsig, env={**os.environ, "KEPLER_JOB_ID": job})
        rec.update(pid=proc.pid)
        _write(job, rec)
        t0, reason, rc = time.time(), None, None
        while rc is None:
            try:
                rc = proc.wait(timeout=BEAT_S)
            except subprocess.TimeoutExpired:
                reason = "durdurma" if enqueue.halted() else "zaman aşımı" if time.time() - t0 > timeout else None
                if reason:
                    rc = _kill(proc)
                    break
                rec["heartbeat"] = time.time()
                _write(job, rec)
        ok = reason is None and rc == 0
        rec.update(state="done" if ok else "failed", rc=rc, reason=reason, finished=time.time())
        _write(job, rec)
        enqueue.enqueue("mudur", enqueue.latest()[job]["type"], "status", f"rc={rc} {reason or ''} deneme={n + 1}".strip(), id=job, status="done" if ok else "failed")
        if ok:
            return 0
        if reason == "durdurma":
            return 3
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="İş çalıştırıcı (kiralama + zaman aşımı + sınırlı tekrar)")
    ap.add_argument("job")
    ap.add_argument("--timeout", type=float, required=True, help="saniye")
    ap.add_argument("--retries", type=int, default=0)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    cmd = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
    if not cmd:
        ap.error("komut verilmedi")
    return run(a.job, cmd, a.timeout, a.retries)


if __name__ == "__main__":
    sys.exit(main())
