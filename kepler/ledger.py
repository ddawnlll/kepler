"""C1: deney defteri = append-only JSONL. Sonuç yalnızca source="referee" ile girer; her kayıt `trial` sayacını artırır (DSR girdisi).
Tek yazar: defteri `factory/ingest.py` ya da tek süreçli `record` değiştirir; işçiler `Staging(dir)` ile ayrı teslim dosyası yazar.
Teslim kimliği içerikten türer: aynı deneme iki kez teslim edilse de bir kez sayılır."""
import fcntl
import hashlib
import importlib.metadata as md
import inspect
import json
import os
import platform
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIRS = ("kepler", "scripts", "factory")  # bu dizinlerdeki yüklü modüller sonucu etkileyebilir
RESULT_FILES = ("pyproject.toml", "uv.lock")  # bağımlılık sürümleri de sonucun parçası
RUNTIME = ("numpy", "pandas", "numba", "duckdb")


@dataclass(frozen=True)
class Staging:
    """İşçi hedefi: record bu dizine ayrı bir teslim dosyası yazar (defteri değiştirmez)."""
    dir: Path


def sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def code_hash(*paths) -> str:
    return sha([Path(p).read_text() for p in paths])


def _project_file(f) -> bool:
    try:
        return Path(f).resolve().relative_to(ROOT).parts[0] in PROJECT_DIRS
    except (ValueError, IndexError):
        return False


def code_fingerprint(*producers) -> str:
    """Deney kodu parmak izi: kepler/ paketi, yüklü proje modülleri (scripts/, factory/), üretici fonksiyonların dosyaları,
    bağımlılık kilidi (pyproject, uv.lock) ve çalışma zamanı sürümleri. Bu dosyalardan biri değişirse hash değişir."""
    paths = set(Path(__file__).parent.rglob("*.py"))
    paths.update(Path(inspect.getsourcefile(fn)) for fn in producers if fn is not None)
    paths.update(Path(m.__file__).resolve() for m in list(sys.modules.values()) if getattr(m, "__file__", None) and _project_file(m.__file__))
    paths.update(ROOT / f for f in RESULT_FILES if (ROOT / f).exists())
    runtime = dict(python=platform.python_version(), **{m: md.version(m) for m in RUNTIME})
    return sha([code_hash(*sorted(paths)), runtime])


def trial_count(path) -> int:
    p = Path(path)
    return sum(1 for _ in p.open()) if p.exists() else 0


def _check(source, config, result, score):
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
    json.dumps([config, result, score], default=str, allow_nan=False)  # satır sayacı artmadan önce doğrula


def _body(source, hypothesis, config, code, data, result, score) -> dict:
    return dict(source=source, hypothesis=hypothesis, config=config, config_hash=sha(config), code_hash=code, data_hash=data, result=result, score=score)


def delivery_id(body: dict) -> str:
    return sha([body[k] for k in ("hypothesis", "config_hash", "code_hash", "data_hash", "result", "score")])


def _rows(path):
    p = Path(path)
    return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []


def record(path, source: str, hypothesis: str, config: dict, code: str, data: str, result: dict | None = None, score: float | None = None) -> dict:
    """Hedef `Staging` ise işçi teslimi (defter değişmez); değilse defterin tek yazarı olarak doğrudan ekleme."""
    _check(source, config, result, score)
    body = _body(source, hypothesis, config, code, data, result, score)
    if isinstance(path, Staging):
        body["delivery"] = delivery_id(body)
        d = Path(path.dir)
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / f".{uuid.uuid4().hex}.tmp"
        tmp.write_text(json.dumps(body, default=str, allow_nan=False))
        os.replace(tmp, d / f"{body['delivery']}.json")  # atomik: yarım teslim dosyası okunmaz
        return body
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a+") as f:  # append-only; flock yalnızca tek süreçli yerel koşuda anlamlı (merkezi yazar `ingest` kullanır)
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        row = dict(trial=sum(1 for _ in f) + 1, time=time.time(), **body, delivery=None)
        f.write(json.dumps(row, default=str, allow_nan=False) + "\n")
        f.flush()
    return row


def query(path, sql: str) -> pd.DataFrame:
    """sql içinde tablo adı `ledger`."""
    con = duckdb.connect()
    con.execute(f"create view ledger as select * from read_json_auto('{path}', format='newline_delimited')")
    return con.execute(sql).df()
