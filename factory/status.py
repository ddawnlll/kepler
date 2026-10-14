"""Güncelleme katmanı (deterministik, LLM yok): defter(ler)den ve kuyruktan kısa durum özeti. Sayılar yalnızca sorgudan gelir.

  python -m factory.status ledger/g2/*.jsonl --summary reports/g2_data/summary.json --out state/STATUS.md"""
import argparse
import glob
import datetime
import sqlite3
import time
from pathlib import Path

import duckdb

from factory import enqueue, store


def status(ledgers: list[str], summary: dict | None = None, queue=enqueue.QUEUE) -> list[str]:
    files = sorted({f for p in ledgers for f in glob.glob(p, recursive=True) if Path(f).stat().st_size})
    lines = []
    if files:
        con = duckdb.connect()
        lst = "[" + ",".join("'" + f.replace("'", "''") + "'" for f in files) + "]"
        con.execute(f"create view l as select * from read_json_auto({lst}, format='newline_delimited', union_by_name=true)")
        n, src, last = con.execute("select count(*), count(*) filter (source='referee'), max(time) from l").fetchone()
        best = con.execute("select json_extract_string(config,'$.name') nm, round(max(json_extract(result,'$.net_pnl')::double),1) from l where source='referee' group by 1 order by 2 desc limit 3").fetchall()
        lines += [f"deneme: {n} (hakem {src}, eleme {n - src}); son kayıt {int(last) if last is not None else 'yok'}", "en iyi net (hakem satırı): " + "; ".join(f"{a} {b}" for a, b in best)]
        con.close()
    else:
        lines.append("defter boş: deneme 0")
    if summary:
        summary = summary.get("summary", summary) if isinstance(summary.get("summary", None), dict) else summary  # arama özeti {summary, search} biçimi
        cands = [k for k, v in summary.items() if v.get("cand")]
        lines.append(f"aday: {len(cands)}" + (f" ({', '.join(cands)})" if cands else "") + f"; yapılandırma {len(summary)}")
    q = enqueue.latest(queue)
    wait = [r for r in q.values() if r["status"] in ("needs_human", "needs_approval")]
    lines.append(f"kuyruk: {len(q)} kayıt, kullanıcı bekleyen {len(wait)}" + (": " + "; ".join(r["text"][:40] for r in wait[:3]) if wait else ""))
    return lines[:6]


def runtime_status(db=store.DB, now=None, stale_seconds=120):
    now = time.time() if now is None else now
    stamp = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).isoformat()
    if not Path(db).exists():
        return [f"üretildi: {stamp}; runtime kurulmadı"]
    con = sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        meta = dict(con.execute("SELECT key,value FROM meta"))
        heartbeat = float(meta.get("runner_heartbeat", 0))
        healthy = heartbeat > 0 and now - heartbeat <= stale_seconds
        counts = dict(con.execute("SELECT state,count(*) FROM jobs GROUP BY state"))
        running = con.execute("SELECT id,heartbeat FROM jobs WHERE state='running'").fetchall()
        details = "; ".join(f"{i}: heartbeat yaşı {int(now - (h or 0))} sn" for i, h in running)
        pending = con.execute("SELECT count(*) FROM outbox WHERE state!='sent'").fetchone()[0]
        unknown = con.execute("SELECT count(*) FROM jobs WHERE state='unknown'").fetchone()[0]
        return [f"üretildi: {stamp}; runner {'güncel' if healthy else 'BAYAT/ÇALIŞMIYOR'}; kontrol {meta.get('control', 'paused')}",
                f"işler: {counts}; teslim bekleyen {pending}; mutabakat bekleyen {unknown}" + ("; " + details if details else "")]
    finally:
        con.close()


if __name__ == "__main__":
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument("ledgers", nargs="*")
    ap.add_argument("--summary")
    ap.add_argument("--out", default="state/STATUS.md")
    ap.add_argument("--runtime", action="store_true")
    a = ap.parse_args()
    out = status(a.ledgers, json.loads(Path(a.summary).read_text()) if a.summary else None)
    if a.runtime:
        out = (runtime_status() + out)[:6]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    temp = Path(a.out).with_suffix(".pending")
    temp.write_text("\n".join(out) + "\n")
    temp.replace(a.out)
    if a.runtime:
        with store.connect() as runtime:
            # One status message per 15-minute slot, durable across process restarts.
            store.notify(runtime, "status:" + str(int(time.time() // 900)), "\n".join(out))
    print("\n".join(out))
