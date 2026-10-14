"""Single local writer imports immutable, reviewed-run events; replay is idempotent."""
import argparse
import fcntl
import json
import os
from pathlib import Path

from kepler import ledger


def ingest(spool, target, *, expected_code, expected_data, producer_ledger):
    if os.environ.get("KEPLER_LEDGER_SPOOL"):
        raise ValueError("merkezi yazar spool üretici ortamında çalışamaz")
    target = Path(target).resolve()
    if target.is_relative_to(Path("/data")):
        raise ValueError("merkezi defter yerel diskte olmalı")
    target.parent.mkdir(parents=True, exist_ok=True)
    imported = []
    # OS-owned local lock serializes ALL ingestion, never a distributed flock.
    with (target.parent / ".writer.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for p in sorted(Path(spool).glob("*/event.json")):
            if p.is_symlink() or p.parent.is_symlink() or p.stat().st_size > 1024 * 1024:
                raise ValueError("geçersiz event dosyası")
            payload = json.loads(p.read_text())
            if set(payload) != {"version", "ledger", "row"} or payload["version"] != 1:
                raise ValueError("geçersiz event şeması")
            if payload["ledger"] != producer_ledger:
                continue
            row = payload["row"]
            required = {"trial", "time", "source", "hypothesis", "config", "config_hash", "code_hash", "data_hash", "result", "score", "event_id"}
            if set(row) != required or row["trial"] is not None:
                raise ValueError("geçersiz event satırı")
            if row["code_hash"] != expected_code or row["data_hash"] != expected_data:
                raise ValueError("kod/veri kimliği ön kayıtlı koşuyla uyuşmuyor")
            if ledger.sha(row["config"]) != row["config_hash"]:
                raise ValueError("config hash uyuşmuyor")
            if not isinstance(row["event_id"], str) or len(row["event_id"]) != 32:
                raise ValueError("geçersiz event kimliği")
            imported.append(ledger.record(target, row["source"], row["hypothesis"], row["config"],
                                          row["code_hash"], row["data_hash"], row["result"], row["score"], event_id=row["event_id"]))
    return imported


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("spool")
    parser.add_argument("target")
    parser.add_argument("--code", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--producer-ledger", required=True)
    args = parser.parse_args()
    print(json.dumps({"imported": len(ingest(args.spool, args.target, expected_code=args.code, expected_data=args.data, producer_ledger=args.producer_ledger))}))
