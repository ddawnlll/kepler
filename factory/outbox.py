"""Kalıcı giden kutusu: bildirim önce diske yazılır, teslim edilene kadar yeniden denenir (üstel geri çekilme), anahtarla tekrar gönderim önlenir.
Teslim en az bir kez (at-least-once): teslim sonrası kayıt yazılamadan çökerse mesaj yeniden gider; alıcı `key` ile tekilleştirebilir.

  send(key, text)                 -> yeni kayıt mı (aynı anahtar ikinci kez eklenmez)
  flush(deliver)                  -> bekleyenleri dener; deliver(text) hata fırlatırsa deneme kaydedilir
  deliver_until_done(deliver)     -> flush'ı üstel geri çekilmeyle MAX_TRIES'a kadar tekrarlar
"""
import fcntl
import json
import time
from pathlib import Path

from factory import enqueue

OUTBOX = enqueue.ROOT / "state" / "outbox.jsonl"
MAX_TRIES, BASE_S = 5, 2.0


def _lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "a+")
    fcntl.flock(f, fcntl.LOCK_EX)
    return f


def _replay(f):
    f.seek(0)
    msgs, done, tries = {}, set(), {}
    for line in f.read().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["event"] == "msg":
            msgs.setdefault(r["key"], r)
        elif r["event"] == "delivered":
            done.add(r["key"])
        elif r["event"] == "attempt":
            tries[r["key"]] = r["n"]
    return msgs, done, tries


def _append(f, row):
    f.seek(0, 2)
    f.write(json.dumps(row, ensure_ascii=False) + "\n")
    f.flush()


def send(key: str, text: str, path=OUTBOX) -> bool:
    with _lock(path) as f:
        msgs, _, _ = _replay(f)
        if key in msgs:
            return False
        _append(f, dict(event="msg", key=key, text=text, ts=time.time()))
        return True


def pending(path=OUTBOX) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open() as f:
        msgs, done, tries = _replay(f)
    return [m for k, m in msgs.items() if k not in done and tries.get(k, 0) < MAX_TRIES]


def flush(deliver, path=OUTBOX) -> dict:
    counts = dict(delivered=0, failed=0)
    with _lock(path) as f:  # süreçler arası çift teslimi önlemek için tüm tur kilit altında
        msgs, done, tries = _replay(f)
        for key, m in msgs.items():
            if key in done or tries.get(key, 0) >= MAX_TRIES:
                continue
            try:
                deliver(m["text"])
            except Exception as e:  # ağ/alıcı hatası: kayıt, bir sonraki turda tekrar denenir
                n = tries.get(key, 0) + 1
                _append(f, dict(event="attempt", key=key, n=n, error=str(e)[:200], ts=time.time()))
                counts["failed"] += 1
                continue
            _append(f, dict(event="delivered", key=key, ts=time.time()))
            counts["delivered"] += 1
    return counts


def deliver_until_done(deliver, path=OUTBOX, sleep=time.sleep) -> dict:
    counts = dict(delivered=0, failed=0)
    for turn in range(MAX_TRIES):
        r = flush(deliver, path)
        counts["delivered"] += r["delivered"]
        counts["failed"] = r["failed"]
        if not pending(path):
            break
        sleep(BASE_S * 2**turn)
    return counts
