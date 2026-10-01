"""Kuyruğa tek giriş noktası: append-only JSONL, kilitli. Bir id'nin durumu = son satırı."""
import fcntl, json, time, uuid
from pathlib import Path

QUEUE = Path("state/queue.jsonl")
FROM = {"sekreter", "mudur", "isci", "insan"}
TYPES = {"A", "B", "C"}  # A araştırma direktifi, B yeni özellik, C korumalı çekirdek (hakem, denetim, mühür)
KINDS = {"directive", "request", "brief", "result", "status"}


def enqueue(frm, type_, kind, text, id=None, path=QUEUE, **extra):
    if frm not in FROM or type_ not in TYPES or kind not in KINDS:
        raise ValueError(f"geçersiz: {frm}/{type_}/{kind}")
    status = extra.pop("status", None)
    if kind == "request":  # B ve C isteği ajan tarafından onaylanamaz
        status = {"A": "open", "B": "needs_approval", "C": "needs_human"}[type_]
    row = {"id": id or uuid.uuid4().hex[:8], "ts": time.time(), "from": frm, "type": type_,
           "kind": kind, "text": text, "status": status or "open", **extra}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row["id"]


def latest(path=QUEUE):
    rows = {}
    if path.exists():
        for line in path.read_text().splitlines():
            r = json.loads(line)
            rows[r["id"]] = {**rows.get(r["id"], {}), **r}
    return rows
