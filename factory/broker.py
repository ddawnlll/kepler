"""Unix socket broker: OS identity is authoritative, request JSON never supplies a uid/path."""
import argparse
import json
import os
import pwd
import socket
import struct
import re
import sqlite3
import subprocess
from pathlib import Path

from factory import enqueue, policy, store

SOCKET = "/run/kepler/broker.sock"
LIMIT = 65536


def authorize(uid, operation):
    name = pwd.getpwuid(uid).pw_name
    human = uid == 0 or name == "jj"
    if not human and name != "kagent":
        raise PermissionError("bu OS kullanıcısı fabrikaya erişemez")
    if operation in {"approve", "reject", "resume", "stop", "review", "merge", "cost"} and not human:
        raise PermissionError("bu işlem insan OS kimliği gerektirir")
    return human


def handle(request, uid, queue=enqueue.QUEUE, db=store.DB):
    if not isinstance(request, dict):
        raise ValueError("JSON nesnesi gerekli")
    op = request.get("op")
    if not isinstance(op, str):
        raise ValueError("op metin olmalı")
    human = authorize(uid, op)
    schemas = {"enqueue": {"op", "from", "type", "kind", "text", "id", "status", "payload", "idempotency_key"},
               "approve": {"op", "id"}, "reject": {"op", "id"}, "status": {"op"},
               "pause": {"op"}, "stop": {"op"}, "resume": {"op"},
               "cost": {"op", "id", "usd"}, "review": {"op", "id"}, "merge": {"op", "id"}}
    if op not in schemas or set(request) - schemas[op]:
        raise ValueError("bilinmeyen işlem/alan")
    if op in {"approve", "reject", "review", "merge", "cost"} and (not isinstance(request.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", request["id"])):
        raise ValueError("geçersiz işlem kimliği")
    if op == "enqueue":
        frm = request.get("from", "insan" if human else "sekreter")
        if not human and frm != "sekreter":
            raise PermissionError("ajan yalnız sekreter kimliğiyle kuyruk açabilir")
        args = {k: v for k, v in request.items() if k not in {"op", "from", "type", "kind", "text"}}
        identity = enqueue.enqueue(frm, request["type"], request["kind"], request["text"], path=queue, **args)
        return {"id": identity}
    if op in {"approve", "reject"}:
        return {"id": enqueue.human_decision(request["id"], op == "approve", uid, path=queue)}
    with store.connect(db) as con:
        if op in {"pause", "stop", "resume"}:
            with store.transaction(con):
                con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('control',?)",
                            ("running" if op == "resume" else op,))
                store.event(con, "control", {"action": op, "uid": uid})
            if op == "stop":
                from factory.runner import stop_unit
                for row in con.execute("SELECT token FROM jobs WHERE state='running'"):
                    stop_unit(row["token"])
            return {"control": op}
        if op == "cost":
            import math
            usd = request["usd"]
            if type(usd) not in {int, float} or not math.isfinite(usd) or usd < 0:
                raise ValueError("geçersiz maliyet")
            changed = con.execute("UPDATE jobs SET cost_usd=? WHERE id=?", (usd, request["id"])).rowcount
            if not changed:
                raise ValueError("iş bulunamadı")
            store.event(con, "cost", {"id": request["id"], "usd": usd, "uid": uid})
            return {"recorded": True}
        if op == "review":
            from factory.merge_gate import review
            return review(con, request["id"], policy.load(), uid)
        if op == "merge":
            from factory.merge_gate import merge
            return merge(con, request["id"], policy.load(), uid)
        from factory.status import runtime_status
        return {"health": runtime_status(db), "queue": list(enqueue.latest(queue).values()),
                "jobs": [dict(r) for r in con.execute("SELECT id,state,attempts,heartbeat,error,cost_usd FROM jobs")],
                "control": (con.execute("SELECT value FROM meta WHERE key='control'").fetchone() or ["paused"])[0]}


def serve():
    Path(SOCKET).unlink(missing_ok=True)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(SOCKET)
        os.chmod(SOCKET, 0o660)
        server.listen(16)
        while True:
            connection, _ = server.accept()
            with connection:
                connection.settimeout(10)
                try:
                    _, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    data = connection.makefile("rb").readline(LIMIT + 1)
                    if len(data) > LIMIT or not data.endswith(b"\n"):
                        raise ValueError("istek boyutu/satır sınırı")
                    response = {"ok": True, "result": handle(json.loads(data), uid)}
                except (ValueError, TypeError, KeyError, PermissionError, OSError, sqlite3.Error, subprocess.SubprocessError) as exc:
                    response = {"ok": False, "error": str(exc)}
                try:
                    connection.sendall(json.dumps(response, ensure_ascii=False).encode() + b"\n")
                except OSError:
                    pass


def call(request, endpoint=SOCKET):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(30)
        client.connect(endpoint)
        client.sendall(json.dumps(request, ensure_ascii=False, allow_nan=False).encode() + b"\n")
        response = json.loads(client.makefile("rb").readline(1024 * 1024))
        if not response["ok"]:
            raise RuntimeError(response["error"])
        return response["result"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("request", nargs="?")
    args = parser.parse_args()
    if args.serve:
        serve()
    else:
        print(json.dumps(call(json.loads(args.request)), ensure_ascii=False))
