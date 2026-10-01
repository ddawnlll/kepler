"""Append-only deney defteri: hakem sonucu, eleme score'u; her satır DSR deneme sayacına girer."""
import hashlib
import json
import time
from fcntl import LOCK_EX, flock
from pathlib import Path

import duckdb
import pandas as pd

_REFEREE_TOKEN = object()  # normal çağıran source="referee" diyerek evaluate kapısını atlayamaz


def sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def code_hash(*paths) -> str:
    return sha([Path(p).read_text() for p in paths])


def trial_count(path) -> int:
    p = Path(path)
    return sum(1 for _ in p.open()) if p.exists() else 0


def record(path, source: str, hypothesis: str, config: dict, code: str, data: str, result: dict | None = None, score: float | None = None, *, _token=None) -> dict:
    if source not in ("referee", "screen"):
        raise ValueError("source referee veya screen olmalı")
    if source == "screen" and result is not None:
        raise ValueError("eleme (vectorbt) sonuç yazamaz; yalnızca score")
    if source == "referee" and (result is None or _token is not _REFEREE_TOKEN):
        raise ValueError("hakem sonucu yalnız evaluate() üzerinden yazılır")
    if source == "referee" and (result.get("n_rejected", 0) or result.get("funding_missed", 0)):
        raise ValueError("reddedilen emir / eksik funding olan koşu geçerli sonuç değildir; deftere yazılmaz")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    json.dumps([config, result, score], default=str, allow_nan=False)  # satır sayacı artmadan önce doğrula
    with p.open("a") as f:  # kilit sayaç OKUMA + append + flush boyunca tutulur; kapanınca serbest kalır
        flock(f, LOCK_EX)
        row = dict(trial=trial_count(p) + 1, time=time.time(), source=source, hypothesis=hypothesis, config=config,
                   config_hash=sha(config), code_hash=code, data_hash=data, result=result, score=score)
        f.write(json.dumps(row, default=str, allow_nan=False) + "\n")  # NaN/inf sessizce yazılmaz (JSONL bozulmasın)
        f.flush()
    return row


def query(path, sql: str) -> pd.DataFrame:
    """sql içinde tablo adı `ledger`."""
    con = duckdb.connect()
    con.execute(f"create view ledger as select * from read_json_auto('{path}', format='newline_delimited')")
    return con.execute(sql).df()
