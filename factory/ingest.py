"""Merkezi yazar: işçi teslimlerini doğrular ve defterin tek yazarı olarak ekler. Tek süreç, tek kilit.

  python -m factory.ingest <defter.jsonl> <teslim_dizini>
"""
import fcntl
import json
import sys
import time
from pathlib import Path

from kepler import ledger


def ingest(path, staging) -> dict:
    """Defterde olmayan teslimleri sayaçla ekler, işlenenleri siler. Bozuk ya da kimliği içerikle uyuşmayan teslim
    `rejected/` altına taşınır ve sayılmaz. Dönüş: added / duplicate / rejected."""
    p, st = Path(path), Path(staging)
    counts = dict(added=0, duplicate=0, rejected=0)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(f"{p}.lock", "a+") as lk:  # tek yazar kilidi (aynı makinede çift ingest'i engeller)
        fcntl.flock(lk, fcntl.LOCK_EX)
        rows = ledger._rows(p)
        seen, trial = {r.get("delivery") for r in rows}, len(rows)
        for f in sorted(st.glob("*.json")) if st.exists() else []:
            try:
                body = json.loads(f.read_text())
                ledger._check(body["source"], body["config"], body["result"], body["score"])
                if body["delivery"] != ledger.delivery_id(body):
                    raise ValueError("teslim kimliği içerikle uyuşmuyor")
            except (ValueError, KeyError, TypeError):
                (st / "rejected").mkdir(exist_ok=True)
                f.replace(st / "rejected" / f.name)
                counts["rejected"] += 1
                continue
            if body["delivery"] in seen:
                counts["duplicate"] += 1
            else:
                trial += 1
                row = dict(trial=trial, time=time.time(), **{k: v for k, v in body.items() if k != "delivery"}, delivery=body["delivery"])
                with p.open("a") as out:
                    out.write(json.dumps(row, default=str, allow_nan=False) + "\n")
                seen.add(body["delivery"])
                counts["added"] += 1
            f.unlink()  # defter yazıldıktan sonra; arada çökerse yeniden ingest `duplicate` sayar (çift kayıt yok)
    return counts


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("kullanım: python -m factory.ingest <defter.jsonl> <teslim_dizini>")
    print(json.dumps(ingest(sys.argv[1], sys.argv[2])))
