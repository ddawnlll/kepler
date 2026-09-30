"""C1: deney defteri = append-only JSONL, DuckDB ile sorgulanır.

Kural: sonuç (PnL vb.) deftere YALNIZCA source="referee" ile girer; source="screen" (vectorbt) yalnızca `score` taşır.
Her kayıt (eleme dahil) deneme sayacını (`trial`) bir artırır; sayaç çoklu-test düzeltmesinin (DSR) girdisidir.
"""
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


def record(path, source: str, hypothesis: str, config: dict, code: str, data: str, result: dict | None = None, score: float | None = None) -> dict:
    if source not in ("referee", "screen"):
        raise ValueError("source referee veya screen olmalı")
    if source == "screen" and result is not None:
        raise ValueError("eleme (vectorbt) sonuç yazamaz; yalnızca score")
    if source == "referee" and result is None:
        raise ValueError("hakem kaydı result içermeli")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = dict(trial=trial_count(p) + 1, time=time.time(), source=source, hypothesis=hypothesis, config=config,
               config_hash=sha(config), code_hash=code, data_hash=data, result=result, score=score)
    with p.open("a") as f:  # append-only: mevcut satırlar asla yeniden yazılmaz
        f.write(json.dumps(row, default=str) + "\n")
        f.flush()
    return row


def query(path, sql: str) -> pd.DataFrame:
    """sql içinde tablo adı `ledger`."""
    con = duckdb.connect()
    con.execute(f"create view ledger as select * from read_json_auto('{path}', format='newline_delimited')")
    return con.execute(sql).df()
