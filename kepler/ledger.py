"""C1: deney defteri = append-only JSONL, DuckDB ile sorgulanır.

Kural: sonuç (PnL vb.) deftere YALNIZCA source="referee" ile girer; source="screen" (vectorbt) yalnızca `score` taşır.
Her olay (eleme/başarısızlık dahil) defter sırasını (`trial`) artırır. Bu sıra bağımsız hipotez veya DSR aile sayısı değildir; istatistik aile/protokol kapsamını kullanır.
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
    return sha([Path(p).read_text() for p in paths])


def trial_count(path) -> int:
    p = Path(path)
    return sum(1 for _ in p.open()) if p.exists() else 0


STATUSES = ("planned", "running", "completed", "invalid", "failed", "incomplete")
INVALID_KEYS = ("n_rejected", "funding_missed", "n_engine_unfilled")


class InvalidRun(ValueError):
    """Geçersiz hakem koşusu (red/eksik funding/motor kaynaklı dolumsuz): performans satırı olamaz; araştırma izine `invalid` denemesi olarak yazılır (record_attempt)."""


def invalid_reason(result: dict) -> str | None:
    bad = {k: result[k] for k in INVALID_KEYS if result.get(k, 0)}
    return f"geçersiz koşu: {bad}" if bad else None


def _append(path, source, hypothesis, config, code, data, status, reason, kind, result, score, invalid_result, receipt, family=None) -> dict:
    p = Path(path)
    job_dir = os.environ.get("KEPLER_JOB_RECEIPTS")
    if job_dir:
        p = Path(job_dir) / ((receipt or {}).get("run_id", uuid.uuid4().hex) + ".jsonl")
    p.parent.mkdir(parents=True, exist_ok=True)
    json.dumps([config, result, score, receipt, invalid_result], default=str, allow_nan=False)  # satır sayacı artmadan önce doğrula
    with p.open("a+") as f:  # append-only: mevcut satırlar asla yeniden yazılmaz; flock YALNIZ aynı makine/konteyner içinde güvence (Modal Volume'da konteynerler arası güvence DEĞİL: aşağıda job-receipt modeli)
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        prev = [json.loads(l) for l in f if l.strip()]
        eid = (receipt or {}).get("economic_id")
        row = dict(trial=len(prev) + 1, time=time.time(), source=source, hypothesis=hypothesis, config=config, config_hash=sha(config), code_hash=code, data_hash=data,
                   result=result, score=score, status=status, reason=reason, kind=kind, attempt=(next((r["attempt"] for r in prev if receipt and kind == "run" and (r.get("receipt") or {}).get("run_id") == receipt.get("run_id")), None) or (1 + max((r.get("attempt", 1) for r in prev if eid and r.get("economic_id") == eid), default=0))))
        if invalid_result is not None:
            row["invalid_result"] = invalid_result  # performans alanı (result) boş; ham sonuç yalnız araştırma izi
        if family is not None:
            row["family"] = family  # scripts/trial_policy.check_family_meta sözleşmesi
        if receipt is not None:
            row.update(receipt=dict(receipt, attempt=row["attempt"]), economic_id=eid)  # eski satırlarda yok: provenance_status 'legacy_partial_provenance'
        if job_dir:
            row["ledger_target"] = str(path)  # only the single collector appends to this logical ledger
        f.write(json.dumps(row, default=str, allow_nan=False) + "\n")  # NaN/inf sessizce yazılmaz (JSONL bozulmasın)
        f.flush()
    return row


def record(path, source: str, hypothesis: str, config: dict, code: str, data: str, result: dict | None = None, score: float | None = None, receipt: dict | None = None, kind: str = "run", family: dict | None = None) -> dict:
    """kind: run | retry | smoke (retry/smoke yeni bağımsız hipotez sayılmaz: `summary`). family: hipotez/aile/kontrol rolü/run/attempt sözleşmesi (scripts/trial_policy.check_family_meta ile doğrulanır; opsiyonel, eski çağrılar bozulmaz)."""
    if source not in ("referee", "screen"):
        raise ValueError("source referee veya screen olmalı")
    if source == "screen" and result is not None:
        raise ValueError("eleme (vectorbt) sonuç yazamaz; yalnızca score")
    if source == "referee" and result is None:
        raise ValueError("hakem kaydı result içermeli")
    if source == "referee" and (why := invalid_reason(result)):
        raise InvalidRun(why + "; deftere performans satırı olarak yazılmaz (record_attempt status=invalid)")
    if source == "referee" and config.get("audit_causal") is not True:  # korkuluk (güvenlik değil): bayrağı evaluate koyar; elle yazan bunu atlatabilir
        raise ValueError("hakem kaydı nedensellik denetiminden (evaluate) geçmemiş: config.audit_causal=True yok")
    return _append(path, source, hypothesis, config, code, data, "completed", "", kind, result, score, None, receipt, family)


def record_attempt(path, status: str, hypothesis: str, config: dict, code: str, data: str, reason: str = "", result: dict | None = None, receipt: dict | None = None, kind: str = "run", family: dict | None = None) -> dict:
    """Performans dışı deneme olayı (planned/running/invalid/failed/incomplete): araştırma geçmişinde korunur, `result` boş kalır (invalid ise ham sonuç `invalid_result`), deneme sayacını artırır.
    completed için `record` kullanılır."""
    if status not in STATUSES or status == "completed":
        raise ValueError(f"status {STATUSES[:2] + STATUSES[3:]} içinden olmalı (completed -> record)")
    return _append(path, "referee", hypothesis, config, code, data, status, reason, kind, None, None, result if status == "invalid" else None, receipt, family)


def query(path, sql: str) -> pd.DataFrame:
    """sql içinde tablo adı `ledger`."""
    con = duckdb.connect()
    con.execute(f"create view ledger as select * from read_json_auto('{path}', format='newline_delimited')")
    return con.execute(sql).df()
