"""#13: Modal Volume'da gerçek depolama modeli yoklaması (yalnız sentetik satırlar; gerçek defterlere dokunmaz).
  modal run --detach modal_app.py --cmd "python scripts/ledger_probe.py write --id 0 --n 50 --out /data/ledger_probe"   # K ayrı konteyner
  modal run --detach modal_app.py --cmd "python scripts/ledger_probe.py flock --id 0 --hold 180 --out /data/ledger_probe" # 2 konteyner, aynı dosyada LOCK_EX
  modal run modal_app.py --cmd "python scripts/ledger_probe.py check --out /data/ledger_probe"
write: her konteyner kendi job-receipt'lerini yazar (ledger_jobs.write_job_receipt, O_EXCL); check: tüm dosyalar görünür mü, kayıp/çakışma var mı, aggregate deterministik mi.
flock: iki ayrı konteyner aynı Volume dosyasında non-blocking LOCK_EX dener; ikisi de aynı anda alabiliyorsa konteynerler arası flock GÜVENCE DEĞİLDİR (issue #13'teki gözlem)."""
import argparse
import fcntl
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from kepler import ledger  # noqa: E402,F401
import ledger_jobs  # noqa: E402


def write(out: Path, jid: int, n: int):
    for i in range(n):
        row = dict(source="referee", hypothesis="probe", config=dict(job=jid, i=i), config_hash=ledger.sha(dict(job=jid, i=i)), code_hash="c", data_hash="d", result=dict(net_pnl=float(i)), status="completed", attempt=1)
        ledger_jobs.write_job_receipt(out / "receipts", row)
    print("write", jid, n)


def flock(out: Path, jid: int, hold: float):
    out.mkdir(parents=True, exist_ok=True)
    lockfile = out / "shared.lock"
    t0 = time.time()
    with lockfile.open("a+") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            got = True
        except BlockingIOError:
            got = False
        start = time.time()
        if got:
            time.sleep(hold)
        end = time.time()
    (out / f"flock_{jid}.json").write_text(json.dumps(dict(id=jid, acquired=got, start=start, end=end, waited=start - t0)))
    print("flock", jid, got, start, end)


def check(out: Path, expect_jobs: int, n: int):
    files = sorted((out / "receipts").glob("*.json"))
    agg = ledger_jobs.aggregate(out / "receipts", out / "ledger_probe.jsonl")
    rows = [json.loads(line) for line in (out / "ledger_probe.jsonl").read_text().splitlines()]
    seen = {(r["config"]["job"], r["config"]["i"]) for r in rows}
    res = dict(files=len(files), expected=expect_jobs * n, aggregated=agg["n"], unique_pairs=len(seen), trials_unique=len({r["trial"] for r in rows}), trial_is_sequence=[r["trial"] for r in rows] == list(range(1, len(rows) + 1)),
               missing=sorted({(j, i) for j in range(expect_jobs) for i in range(n)} - seen)[:20], sha=agg["sha"], again_same=ledger_jobs.aggregate(out / "receipts", out / "ledger_probe.jsonl")["sha"] == agg["sha"])
    fl = [json.loads(p.read_text()) for p in sorted(out.glob("flock_*.json"))]
    res["flock"] = fl
    if len(fl) >= 2:
        res["flock_both_acquired"] = all(x["acquired"] for x in fl)
        res["flock_intervals_overlap"] = fl[0]["start"] < fl[1]["end"] and fl[1]["start"] < fl[0]["end"]
    (out / "check.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["write", "flock", "check"])
    ap.add_argument("--id", type=int, default=0)
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--hold", type=float, default=180)
    ap.add_argument("--out", default="/data/ledger_probe")
    a = ap.parse_args()
    o = Path(a.out)
    {"write": lambda: write(o, a.id, a.n), "flock": lambda: flock(o, a.id, a.hold), "check": lambda: check(o, a.jobs, a.n)}[a.cmd]()
