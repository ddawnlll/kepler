"""C1: deney defteri = append-only JSONL, DuckDB ile sorgulanır.

Kural: sonuç (PnL vb.) deftere YALNIZCA source="referee" ile girer; source="screen" (vectorbt) yalnızca `score` taşır.
Her kayıt (eleme dahil) deneme sayacını (`trial`) bir artırır; sayaç çoklu-test düzeltmesinin (DSR) girdisidir.
"""
import fcntl
import hashlib
import json
import time
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


FAMILY_KEYS = ("hypothesis_id", "parent_hypothesis", "selection_family", "control_role", "run_id", "attempt")
CONTROL_ROLES = ("primary", "secondary", "negative_control", "neutral_null", "exploratory")


def check_family_meta(meta: dict) -> dict:
    """Ledger/önkayıt sözleşmesi (run/attempt hipotezden ayrı): hypothesis_id, parent_hypothesis, selection_family, control_role, run_id, attempt."""
    if any(k not in meta for k in FAMILY_KEYS) or meta["control_role"] not in CONTROL_ROLES or not isinstance(meta["attempt"], int) or meta["attempt"] < 1:
        raise ValueError(f"aile meta'sı geçersiz: {FAMILY_KEYS}; control_role {CONTROL_ROLES}; attempt >= 1")
    return {k: meta[k] for k in FAMILY_KEYS}


STATUSES = ("planned", "running", "completed", "invalid", "failed", "incomplete")
INVALID_KEYS = ("n_rejected", "funding_missed", "n_engine_unfilled")


class InvalidRun(ValueError):
    """Geçersiz hakem koşusu (red/eksik funding/motor kaynaklı dolumsuz): performans satırı olamaz; araştırma izine `invalid` denemesi olarak yazılır (record_attempt)."""


def invalid_reason(result: dict) -> str | None:
    bad = {k: result[k] for k in INVALID_KEYS if result.get(k, 0)}
    return f"geçersiz koşu: {bad}" if bad else None


def _append(path, source, hypothesis, config, code, data, status, reason, kind, result, score, invalid_result, receipt, family=None) -> dict:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    json.dumps([config, result, score, receipt, invalid_result], default=str, allow_nan=False)  # satır sayacı artmadan önce doğrula
    with p.open("a+") as f:  # append-only: mevcut satırlar asla yeniden yazılmaz; flock YALNIZ aynı makine/konteyner içinde güvence (Modal Volume'da konteynerler arası güvence DEĞİL: aşağıda job-receipt modeli)
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        prev = [json.loads(l) for l in f if l.strip()]
        eid = (receipt or {}).get("economic_id")
        row = dict(trial=len(prev) + 1, time=time.time(), source=source, hypothesis=hypothesis, config=config, config_hash=sha(config), code_hash=code, data_hash=data,
                   result=result, score=score, status=status, reason=reason, kind=kind, attempt=1 + sum(1 for r in prev if eid and r.get("economic_id") == eid))
        if invalid_result is not None:
            row["invalid_result"] = invalid_result  # performans alanı (result) boş; ham sonuç yalnız araştırma izi
        if family is not None:
            row["family"] = family  # stats.check_family_meta: hypothesis_id, parent_hypothesis, selection_family, control_role, run_id, attempt
        if receipt is not None:
            row.update(receipt=receipt, economic_id=eid)  # eski satırlarda yok: provenance_status 'legacy_partial_provenance'
        f.write(json.dumps(row, default=str, allow_nan=False) + "\n")  # NaN/inf sessizce yazılmaz (JSONL bozulmasın)
        f.flush()
    return row


def record(path, source: str, hypothesis: str, config: dict, code: str, data: str, result: dict | None = None, score: float | None = None, receipt: dict | None = None, kind: str = "run", family: dict | None = None) -> dict:
    """kind: run | retry | smoke (retry/smoke yeni bağımsız hipotez sayılmaz: `summary`). family: check_family_meta ile doğrulanan hipotez/aile/kontrol rolü/run/attempt sözleşmesi (opsiyonel; eski çağrılar bozulmaz)."""
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
    return _append(path, source, hypothesis, config, code, data, "completed", "", kind, result, score, None, receipt, family and check_family_meta(family))


def record_attempt(path, status: str, hypothesis: str, config: dict, code: str, data: str, reason: str = "", result: dict | None = None, receipt: dict | None = None, kind: str = "run") -> dict:
    """Performans dışı deneme olayı (planned/running/invalid/failed/incomplete): araştırma geçmişinde korunur, `result` boş kalır (invalid ise ham sonuç `invalid_result`), deneme sayacını artırır.
    completed için `record` kullanılır."""
    if status not in STATUSES or status == "completed":
        raise ValueError(f"status {STATUSES[:2] + STATUSES[3:]} içinden olmalı (completed -> record)")
    return _append(path, "referee", hypothesis, config, code, data, status, reason, kind, None, None, result if status == "invalid" else None, receipt)


def summary(path) -> dict:
    """Satır, durum, kimlik ve deneme sayıları. Retry/smoke ve aynı ekonomik kimliğin tekrarları 'bağımsız hipotez' sayılmaz: independent = completed/invalid satırlarının benzersiz economic_id (receipt'siz eski satırlar config_hash ile)."""
    rows = [json.loads(l) for l in Path(path).open() if l.strip()] if Path(path).exists() else []
    key = lambda r: r.get("economic_id") or r["config_hash"]  # noqa: E731
    indep = {key(r) for r in rows if r.get("kind", "run") == "run" and r.get("status", "completed") in ("completed", "invalid")}
    st = {}
    for r in rows:
        st[r.get("status", "completed")] = st.get(r.get("status", "completed"), 0) + 1
    return dict(rows=len(rows), by_status=st, independent_hypotheses=len(indep), retries_or_smoke=sum(1 for r in rows if r.get("kind", "run") != "run"), max_attempt=max((r.get("attempt", 1) for r in rows), default=0))


# --- Dağıtık güvenli model: job başına DEĞİŞMEZ receipt + tek toplayıcı. Konteynerler arası flock'a güvenilmez (BACKTEST.md; Modal testi yalnız belirli kurulumu kapsıyordu).
def write_job_receipt(dir_, row: dict) -> Path:
    """Job satırını `<economic_id|config_hash>.<attempt>.<status>.json` olarak, O_EXCL ile (üstüne yazmadan) yazar. Aynı içerik tekrarı idempotent; farklı içerik aynı adda -> açık hata."""
    d = Path(dir_)
    d.mkdir(parents=True, exist_ok=True)
    row = {k: v for k, v in row.items() if k not in ("trial", "time")}  # sıra kimliği/zaman toplayıcıda atanır
    name = f"{row.get('economic_id') or row['config_hash']}.{row.get('attempt', 1)}.{row['status']}.json"
    body = json.dumps(row, sort_keys=True, default=str, allow_nan=False)
    path = d / name
    try:
        with path.open("x") as f:
            f.write(body)
    except FileExistsError:
        if path.read_text() != body:
            raise ValueError(f"çelişkili duplicate receipt: {name}") from None
    return path


def aggregate(dir_, out) -> dict:
    """Tek yazarlı deterministik toplama: receipt'ler ada göre sıralanır, trial = sıra. `out` her seferinde aynı içerikle yeniden üretilir (idempotent; kesinti sonrası tekrar güvenli). Eksik/bozuk receipt hata verir."""
    files = sorted(Path(dir_).glob("*.json"))
    rows = []
    for i, f in enumerate(files, 1):
        try:
            r = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            raise ValueError(f"bozuk receipt {f.name}: {e}") from e
        rows.append(dict(trial=i, **r))
    body = "".join(json.dumps(r, sort_keys=True, default=str, allow_nan=False) + "\n" for r in rows)
    tmp = Path(str(out) + ".tmp")
    tmp.write_text(body)
    tmp.replace(out)  # atomik: yarım çıktı görünmez
    return dict(n=len(rows), sha=sha(body))


def query(path, sql: str) -> pd.DataFrame:
    """sql içinde tablo adı `ledger`."""
    con = duckdb.connect()
    con.execute(f"create view ledger as select * from read_json_auto('{path}', format='newline_delimited')")
    return con.execute(sql).df()
