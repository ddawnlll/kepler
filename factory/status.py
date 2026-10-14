"""Güncelleme katmanı (deterministik, LLM yok): defter(ler)den ve kuyruktan kısa durum özeti. Sayılar yalnızca sorgudan gelir.

  python -m factory.status ledger/g2/*.jsonl --summary reports/g2_data/summary.json --out state/STATUS.md"""
import argparse
import glob
import json
import time
from pathlib import Path

import duckdb

from factory import enqueue, outbox, runner


def status(ledgers: list[str], summary: dict | None = None, queue=enqueue.QUEUE, outbox_path=outbox.OUTBOX) -> list[str]:
    files = [f for p in ledgers for f in glob.glob(p)]
    lines = []
    if files:
        con = duckdb.connect()
        lst = "[" + ",".join("'" + f.replace("'", "''") + "'" for f in files) + "]"
        con.execute(f"create view l as select * from read_json_auto({lst}, format='newline_delimited', union_by_name=true)")
        n, src, last = con.execute("select count(*), count(*) filter (source='referee'), max(time) from l").fetchone()
        best = con.execute("select json_extract_string(config,'$.name') nm, round(max(json_extract(result,'$.net_pnl')::double),1) from l where source='referee' group by 1 order by 2 desc limit 3").fetchall()
        lines += [f"deneme: {n} (hakem {src}, eleme {n - src}); son kayıt {int(last)}", "en iyi net (hakem satırı): " + "; ".join(f"{a} {b}" for a, b in best)]
    else:
        lines.append("defter boş: deneme 0")
    if summary:
        summary = summary.get("summary", summary) if isinstance(summary.get("summary", None), dict) else summary  # arama özeti {summary, search} biçimi
        cands = [k for k, v in summary.items() if v.get("cand")]
        lines.append(f"aday: {len(cands)}" + (f" ({', '.join(cands)})" if cands else "") + f"; yapılandırma {len(summary)}")
    q = enqueue.latest(queue)
    wait = [r for r in q.values() if r["status"] in enqueue.WAITING]
    lines.append(f"kuyruk: {len(q)} kayıt, insan onayı bekleyen {len(wait)}" + (": " + "; ".join(r["text"][:40] for r in wait[:3]) if wait else ""))
    runs = [json.loads(p.read_text()) for p in sorted(runner.RUNS.glob("*.json"))] if runner.RUNS.exists() else []
    live = [r for r in runs if r.get("state") == "running"]
    beat = max((time.time() - r["heartbeat"] for r in live), default=None)
    halt = "DURDURULDU" if enqueue.halted() else "çalışıyor"
    lines.append(f"{halt}; koşan iş {len(live)}" + (f" (son kalp atışı {int(beat)} sn önce, kiralama {int(runner.LEASE_S)} sn)" if live else ""))
    lines.append(f"giden kutusu bekleyen {len(outbox.pending(outbox_path))}; özet {time.strftime('%Y-%m-%d %H:%M:%S')} itibarıyla")
    return lines[:6]


if __name__ == "__main__":
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument("ledgers", nargs="*")
    ap.add_argument("--summary")
    ap.add_argument("--out", default="state/STATUS.md")
    a = ap.parse_args()
    out = status(a.ledgers, json.loads(Path(a.summary).read_text()) if a.summary else None)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(out) + "\n")
    print("\n".join(out))
