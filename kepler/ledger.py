"""C1: deney defteri = append-only JSONL, DuckDB ile sorgulanır.

Kural: sonuç (PnL vb.) deftere YALNIZCA source="referee" ile girer; source="screen" (vectorbt) yalnızca `score` taşır.
Her kayıt (eleme dahil) deneme sayacını (`trial`) bir artırır; sayaç çoklu-test düzeltmesinin (DSR) girdisidir.
"""
import fcntl
import hashlib
import json
import os
import time
import uuid
from pathlib import Path

import duckdb
import pandas as pd


def sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def code_hash(*paths) -> str:
    # Conservative closure: all in-repo computation, lock and explicit external sources.
    # File names participate; renaming identical sources must also change the identity.
    root = Path(__file__).resolve().parent.parent
    files = set((root / "kepler").rglob("*.py"))
    files.update((root / "scripts").rglob("*.py"))
    files.update(root / name for name in ("pyproject.toml", "uv.lock"))
    files.update(Path(p).resolve() for p in paths if p is not None)
    entries = [(p.relative_to(root).as_posix() if p.is_relative_to(root) else p.name,
                hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]
    return sha(sorted(entries))


def trial_count(path) -> int:
    p = Path(path)
    return sum(1 for _ in p.open()) if p.exists() else 0


def record(path, source: str, hypothesis: str, config: dict, code: str, data: str, result: dict | None = None, score: float | None = None, *, event_id: str | None = None) -> dict:
    if source not in ("referee", "screen"):
        raise ValueError("source referee veya screen olmalı")
    if source == "screen" and result is not None:
        raise ValueError("eleme (vectorbt) sonuç yazamaz; yalnızca score")
    if source == "referee" and result is None:
        raise ValueError("hakem kaydı result içermeli")
    if source == "referee" and (result.get("n_rejected", 0) or result.get("funding_missed", 0)):
        raise ValueError("reddedilen emir / eksik funding olan koşu geçerli sonuç değildir; deftere yazılmaz")
    if source == "referee" and config.get("audit_causal") is not True:  # korkuluk (güvenlik değil): bayrağı evaluate koyar; elle yazan bunu atlatabilir
        raise ValueError("hakem kaydı nedensellik denetiminden (evaluate) geçmemiş: config.audit_causal=True yok")
    p = Path(path)
    json.dumps([config, result, score], default=str, allow_nan=False)  # satır sayacı artmadan önce doğrula
    spool = os.environ.get("KEPLER_LEDGER_SPOOL")
    if spool and p.resolve().is_relative_to(Path("/data")):
        # Every producer owns its own directory; no shared-file locking on Modal.
        folder = Path(spool) / uuid.uuid4().hex
        folder.mkdir(parents=True, exist_ok=False)
        row = dict(trial=None, time=time.time(), source=source, hypothesis=hypothesis, config=config,
                   config_hash=sha(config), code_hash=code, data_hash=data, result=result, score=score,
                   event_id=event_id or (sha([os.environ["KEPLER_RUN_ID"], p.as_posix(), source, hypothesis, config, code, data])[:32]
                                         if os.environ.get("KEPLER_RUN_ID") else uuid.uuid4().hex))
        payload = {"version": 1, "ledger": p.as_posix(), "row": row}
        temp = folder / "pending"
        temp.write_text(json.dumps(payload, default=str, allow_nan=False) + "\n")
        temp.replace(folder / "event.json")
        return row  # trial is assigned only by the central writer, never by a worker.
    if p.resolve().is_relative_to(Path("/data")):
        raise ValueError("Modal Volume defterine doğrudan yazma yasak; KEPLER_LEDGER_SPOOL gerekli")
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a+") as f:  # append-only: mevcut satırlar asla yeniden yazılmaz; flock: eşzamanlı yazarlarda sayaç/satır yarışı olmaz
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        previous = [json.loads(line) for line in f]
        if event_id:
            same = [r for r in previous if r.get("event_id") == event_id]
            if same:
                expected = dict(source=source, hypothesis=hypothesis, config=config, code_hash=code,
                                data_hash=data, result=result, score=score)
                if any(same[0].get(k) != v for k, v in expected.items()):
                    raise ValueError("event_id farklı içerikle tekrar kullanıldı")
                return same[0]
        row = dict(trial=len(previous) + 1, time=time.time(), source=source, hypothesis=hypothesis, config=config,
                   config_hash=sha(config), code_hash=code, data_hash=data, result=result, score=score)
        if event_id:
            row["event_id"] = event_id
        f.write(json.dumps(row, default=str, allow_nan=False) + "\n")  # NaN/inf sessizce yazılmaz (JSONL bozulmasın)
        f.flush()
        os.fsync(f.fileno())
    return row


def query(path, sql: str) -> pd.DataFrame:
    """sql içinde tablo adı `ledger`."""
    con = duckdb.connect()
    con.execute(f"create view ledger as select * from read_json_auto('{path}', format='newline_delimited')")
    return con.execute(sql).df()
