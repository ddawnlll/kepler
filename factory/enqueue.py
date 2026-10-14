"""Validated append-only queue. Production writes arrive through broker peer credentials."""
import fcntl
import json
import os
import re
import time
import uuid
from pathlib import Path

QUEUE = Path("/srv/kepler/state/queue.jsonl")
FROM = {"sekreter", "mudur", "isci", "insan"}
TYPES = {"A", "B", "C"}
KINDS = {"directive", "request", "brief", "result", "status"}
STATES = {"open", "needs_approval", "needs_human", "approved", "running", "done", "failed", "blocked", "rejected"}
AGENT_TRANSITIONS = {"open": {"running", "done", "blocked", "failed"},
                     "approved": {"running", "blocked"}, "running": {"done", "failed", "blocked"},
                     "blocked": {"open"}}


def _read(f):
    f.seek(0)
    rows = {}
    for line in f:
        if not line.endswith("\n"):
            raise ValueError("kuyrukta yarım satır; insan onarımı gerekli")
        r = json.loads(line)
        rows[r["id"]] = r
    return rows


def _append(path, build):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o640)
    with os.fdopen(fd, "a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        row = build(_read(f))
        if row.pop("_duplicate", False):
            return row["id"]
        f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
        return row["id"]


def enqueue(frm, type_, kind, text, id=None, path=QUEUE, **extra):
    if any(not isinstance(v, str) for v in (frm, type_, kind)) or frm not in FROM or type_ not in TYPES or kind not in KINDS:
        raise ValueError(f"geçersiz: {frm}/{type_}/{kind}")
    if not isinstance(text, str) or not 0 < len(text) <= 16000:
        raise ValueError("text 1–16000 karakter olmalı")
    if set(extra) - {"status", "idempotency_key", "payload"}:
        raise ValueError("izin verilmeyen kuyruk alanı")
    key = extra.get("idempotency_key")
    if key is not None and (not isinstance(key, str) or not 1 <= len(key) <= 128):
        raise ValueError("geçersiz idempotency_key")
    payload = extra.get("payload", {})
    if not isinstance(payload, dict) or len(json.dumps(payload, allow_nan=False)) > 32000:
        raise ValueError("geçersiz payload")
    identity = id or uuid.uuid4().hex
    if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", identity):
        raise ValueError("geçersiz id")

    def build(rows):
        if key:
            matches = [r for r in rows.values() if r.get("idempotency_key") == key]
            if matches:
                old = matches[0]
                if (old.get("initial_from", old["from"]), old["type"], old.get("initial_text"), old.get("payload")) != (frm, type_, text, payload):
                    raise ValueError("idempotency_key farklı istek için kullanıldı")
                return {"id": old["id"], "_duplicate": True}
        old = rows.get(identity)
        state = extra.get("status") or "open"
        if kind == "request":
            state = {"A": "open", "B": "needs_approval", "C": "needs_human"}[type_]
        if not isinstance(state, str) or state not in STATES or state in {"approved", "rejected"}:
            raise PermissionError("onay yalnızca kimliği doğrulanmış insan işlemidir")
        if old:
            if old["type"] != type_ or kind == "request":
                raise ValueError("istek türü/kimliği yeniden tanımlanamaz")
            if state != old["status"] and state not in AGENT_TRANSITIONS.get(old["status"], set()):
                raise PermissionError("izin verilmeyen durum geçişi")
            if payload and payload != old.get("payload"):
                raise ValueError("onaylanan payload değişmez")
        elif state not in {"open", "needs_approval", "needs_human"}:
            raise PermissionError("yeni kayıt terminal durumda başlayamaz")
        if not old and type_ in {"B", "C"}:
            state = {"B": "needs_approval", "C": "needs_human"}[type_]
        return {**(old or {}), "id": identity, "ts": time.time(), "from": frm,
                "type": type_, "kind": kind, "text": text, "status": state,
                "payload": (old or {}).get("payload", payload),
                "initial_text": (old or {}).get("initial_text", text),
                "initial_from": (old or {}).get("initial_from", frm),
                "idempotency_key": (old or {}).get("idempotency_key", key)}

    return _append(path, build)


def human_decision(identity, approved, uid, path=QUEUE):
    # uid must be supplied ONLY by broker SO_PEERCRED, never from a JSON request.
    import pwd
    if uid != 0 and pwd.getpwuid(uid).pw_name != "jj":
        raise PermissionError("insan OS kimliği gerekli")

    def build(rows):
        old = rows[identity]
        if old["status"] == ("approved" if approved else "rejected") and old.get("approved_by_uid") == uid:
            return {"id": identity, "_duplicate": True}
        if old["status"] not in {"needs_approval", "needs_human"}:
            raise ValueError("istek onay beklemiyor")
        return {**old, "ts": time.time(), "status": "approved" if approved else "rejected",
                "approved_by_uid": uid, "kind": "status"}

    return _append(path, build)


def latest(path=QUEUE):
    if not Path(path).exists():
        return {}
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        return _read(f)
