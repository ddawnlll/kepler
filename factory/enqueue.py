"""Kuyruğa tek giriş: append-only JSONL, kilitli, alan ve durum geçişleri doğrulanır.

- Yol sabit (QUEUE); yazma API'sinde yol parametresi yok. Alanlar whitelist, kimlik ve metin doğrulanır.
- A işi `open` ile girer. B/C isteği `needs_approval` / `needs_human` ile girer; ajan bu durumdan ileri yazamaz.
- Onay yalnızca `approve()` ile (factory/approve.py): HMAC imzalı `approval` kaydı. İmzasız onay satırı okunmaz.
- Durdurma etkinken (state/PAUSED) yeni iş (directive/request/brief) eklenmez; mevcut iş durumu güncellenebilir.
"""
import fcntl
import json
import re
import time
import uuid
from pathlib import Path

from factory import auth

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "state" / "queue.jsonl"
HALT = ROOT / "state" / "PAUSED"  # docs/factory.md: durdurma bayrağı
FROM = {"sekreter", "mudur", "isci", "insan"}
TYPES = {"A", "B", "C"}  # A araştırma direktifi, B yeni özellik, C korumalı çekirdek (hakem, denetim, mühür)
KINDS = {"directive", "request", "brief", "result", "status"}
NEW_WORK = {"directive", "request", "brief"}
GATED = {"B": "needs_approval", "C": "needs_human"}  # B/C ilk durumu: insan onayı olmadan ilerlemez
WAITING = set(GATED.values())
AGENT_STATUS = {"open", "running", "done", "failed", "blocked"}  # ajanın yazabildiği durumlar (approved/rejected yok)
NEXT = {"open": {"running", "done", "failed", "blocked"}, "approved": {"running", "done", "failed", "blocked"},
        "running": {"done", "failed", "blocked"}, "blocked": {"open", "running", "failed"},
        "failed": {"open", "running"}, "done": set()}
ID_RE = re.compile(r"^[a-z0-9]{8,32}$")
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def halted() -> bool:
    return HALT.exists()


def _lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "a+")
    fcntl.flock(f, fcntl.LOCK_EX)
    return f


def _initial(type_, status):
    if type_ in GATED:
        return GATED[type_]
    return status if status in AGENT_STATUS else "open"


def _apply(state: dict, r: dict):
    """Tek satırı durum tablosuna uygular; geçersiz (izinsiz) satır sessizce yok sayılır (savunma katmanı)."""
    cur = state.get(r.get("id"))
    if r.get("kind") == "approval":  # yalnızca bekleyen B/C, imzalı kayıtla ilerler
        if cur and cur["status"] in WAITING and r.get("status") in ("approved", "rejected") and auth.verify(r):
            cur["status"], cur["by"] = r["status"], r.get("by")
        return
    if cur is None:
        if r.get("type") in TYPES:
            state[r["id"]] = {**r, "status": _initial(r["type"], None if r.get("kind") == "request" else r.get("status"))}
        return
    st = r.get("status")
    if cur["status"] in WAITING or r.get("type") != cur["type"] or r.get("kind") == "request":
        return
    if st in AGENT_STATUS and st in NEXT.get(cur["status"], set()) | {cur["status"]}:
        cur["status"] = st
    cur.update({k: r[k] for k in ("text", "ts", "from") if k in r})


def _replay(f) -> dict:
    f.seek(0)
    state: dict = {}
    for line in f.read().splitlines():
        if line.strip():
            _apply(state, json.loads(line))
    return state


def latest(path=None) -> dict:
    """Her kimlik için son geçerli durum (yalnızca okur)."""
    p = Path(path) if path else QUEUE
    if not p.exists():
        return {}
    with p.open() as f:
        return _replay(f)


def _write(f, row: dict):
    f.seek(0, 2)
    f.write(json.dumps(row, ensure_ascii=False) + "\n")
    f.flush()


def enqueue(frm, type_, kind, text, id=None, **extra):
    if frm not in FROM or type_ not in TYPES or kind not in KINDS or set(extra) - {"status"}:
        raise ValueError(f"geçersiz: {frm}/{type_}/{kind}/{sorted(extra)}")
    if not isinstance(text, str) or not text.strip() or len(text) > 2000 or CONTROL.search(text):
        raise ValueError("metin boş, 2000 karakterden uzun ya da kontrol karakteri içeriyor")
    if id is not None and not ID_RE.match(id):
        raise ValueError(f"geçersiz kimlik: {id!r}")
    status = extra.get("status")
    if status is not None and status not in AGENT_STATUS:
        raise ValueError(f"ajan bu durumu yazamaz: {status}")
    with _lock(QUEUE) as f:
        state = _replay(f)
        cur = state.get(id) if id else None
        if cur is None:
            if kind in NEW_WORK and halted():
                raise RuntimeError("durdurma etkin: yeni iş kabul edilmiyor (insan: factory/halt.py release)")
            new_id = id or uuid.uuid4().hex[:8]
            row_status = _initial(type_, None if kind == "request" else status)
        else:
            if kind == "request":
                raise ValueError("istek mevcut bir kimliğe yazılamaz")
            if type_ != cur["type"]:
                raise ValueError("iş türü değiştirilemez")
            if cur["status"] in WAITING:
                raise RuntimeError(f"{id} insan onayı bekliyor ({cur['status']}); ajan yazamaz")
            if status is not None and status != cur["status"] and status not in NEXT.get(cur["status"], set()):
                raise RuntimeError(f"izinsiz durum geçişi: {cur['status']} -> {status}")
            new_id, row_status = id, status or cur["status"]
        row = {"id": new_id, "ts": time.time(), "from": frm, "type": type_, "kind": kind, "text": text, "status": row_status}
        _write(f, row)
    return new_id


def approve(id: str, decision: str, by: str) -> dict:
    """İnsan onayı (yalnızca factory/approve.py çağırır). Anahtar yoksa PermissionError; bekleyen iş yoksa RuntimeError."""
    if decision not in ("approved", "rejected") or not ID_RE.match(id or "") or not by:
        raise ValueError("geçersiz onay")
    with _lock(QUEUE) as f:
        cur = _replay(f).get(id)
        if cur is None or cur["status"] not in WAITING:
            raise RuntimeError(f"{id} için bekleyen onay yok")
        row = {"id": id, "ts": time.time(), "from": "insan", "type": cur["type"], "kind": "approval", "text": f"{decision} ({by})", "status": decision, "by": by}
        row["sig"] = auth.sign(row)
        _write(f, row)
    return row
