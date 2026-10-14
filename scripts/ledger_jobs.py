"""#13: defter yardımcıları (kepler/ dışı; satır tavanı için): özet sayımı ve dağıtık güvenli job-receipt modeli. `kepler.ledger.record/record_attempt` satır biçimini üretir, burası okur/toplar."""
import json
import errno
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kepler.ledger import sha  # noqa: E402


def summary(path) -> dict:
    """Unique economic experiments; uniqueness does not establish statistical independence.
    `independent_hypotheses` is a legacy alias, never a family/DSR correction count.
    """
    rows = [json.loads(l) for l in Path(path).open() if l.strip()] if Path(path).exists() else []
    key = lambda r: r.get("economic_id") or r["config_hash"]  # noqa: E731
    indep = {key(r) for r in rows if r.get("kind", "run") == "run" and r.get("status", "completed") in ("completed", "invalid")}
    st = {}
    for r in rows:
        st[r.get("status", "completed")] = st.get(r.get("status", "completed"), 0) + 1
    return dict(rows=len(rows), by_status=st, unique_experiments=len(indep), independent_hypotheses=len(indep), retries_or_smoke=sum(1 for r in rows if r.get("kind", "run") != "run"), max_attempt=max((r.get("attempt", 1) for r in rows), default=0))


# --- Dağıtık güvenli model: job başına DEĞİŞMEZ receipt + tek toplayıcı. Konteynerler arası flock'a güvenilmez (BACKTEST.md; Modal testi yalnız belirli kurulumu kapsıyordu).
def write_job_receipt(dir_, row: dict) -> Path:
    """Publish a complete immutable receipt directory by no-clobber rename.
    Identical retries are idempotent, including legacy regular JSON receipts.
    """
    d = Path(dir_)
    d.mkdir(parents=True, exist_ok=True)
    row = {k: v for k, v in row.items() if k not in ("trial", "time")}  # sıra kimliği/zaman toplayıcıda atanır
    name = f"{row.get('economic_id') or row['config_hash']}.{row.get('attempt', 1)}.{row['status']}.json"
    body = json.dumps(row, sort_keys=True, default=str, allow_nan=False)
    path = d / name
    temp = Path(tempfile.mkdtemp(prefix=".receipt-", dir=d))
    try:
        (temp / "row.json").write_text(body)
        try:
            os.rename(temp, path)  # nonempty directory publication: concurrent destination cannot be replaced
        except OSError as e:
            if e.errno not in (errno.EEXIST, errno.ENOTEMPTY) and not (e.errno == errno.ENOTDIR and path.is_file()):
                raise
            stored = path / "row.json" if path.is_dir() else path
            if stored.read_text() != body:
                raise ValueError(f"çelişkili duplicate receipt: {name}") from None
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    return path


def aggregate(dir_, out, expected_jobs=None) -> dict:
    """Tek yazarlı deterministik toplama: receipt'ler ada göre sıralanır, trial = sıra. `out` her seferinde aynı içerikle yeniden üretilir (idempotent; kesinti sonrası tekrar güvenli). Eksik/bozuk receipt hata verir."""
    files = sorted(p for p in [*Path(dir_).glob("*.json"), *Path(dir_).glob("*.jsonl")] if p.resolve() != Path(out).resolve())
    if expected_jobs is not None and {f.name for f in files} != set(expected_jobs):
        raise ValueError("missing or unexpected job receipts")
    rows = []
    for i, f in enumerate(files, 1):
        try:
            src = f / "row.json" if f.is_dir() else f
            events = [json.loads(l) for l in src.read_text().splitlines() if l.strip()] if f.suffix == ".jsonl" else [json.loads(src.read_text())]
        except json.JSONDecodeError as e:
            raise ValueError(f"bozuk receipt {f.name}: {e}") from e
        for r in events:
            if not isinstance(r, dict) or r.get("status") not in ("planned", "running", "completed", "invalid", "failed", "incomplete") or not r.get("config_hash"):
                raise ValueError(f"invalid receipt schema: {f.name}")
            rows.append(dict(trial=len(rows) + 1, **{k: v for k, v in r.items() if k not in ("trial", "time")}))
    body = "".join(json.dumps(r, sort_keys=True, default=str, allow_nan=False) + "\n" for r in rows)
    tmp = Path(str(out) + ".tmp")
    tmp.write_text(body)
    tmp.replace(out)  # atomik: yarım çıktı görünmez
    return dict(n=len(rows), sha=sha(body))


def command_status(dir_, worker, status, command, returncode=None):
    """One worker owns its command record; atomic snapshots expose pre-evaluator failures too."""
    d = Path(dir_) / "commands"
    d.mkdir(parents=True, exist_ok=True)
    row = dict(worker=worker, status=status, command_sha=sha(command), returncode=returncode)
    tmp = d / f".{worker}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(row, sort_keys=True, allow_nan=False))
    tmp.replace(d / f"{worker}.json")


def collect(dir_, expected_workers=None) -> dict:
    """One collector after all workers exit; append to logical ledgers without altering old bytes."""
    commands = sorted((Path(dir_) / "commands").glob("*.json"))
    if expected_workers is not None and {p.stem for p in commands} != {str(i) for i in range(expected_workers)}:
        raise ValueError("missing or unexpected command receipts")
    statuses = [json.loads(p.read_text()) for p in commands]
    if any(r["status"] not in ("completed", "failed") or r["returncode"] is None for r in statuses):
        raise ValueError("unfinished worker command")
    files = sorted(Path(dir_).glob("*.jsonl"))
    groups = {}
    for f in files:
        rows = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
        if not rows or rows[-1]["status"] not in ("completed", "invalid", "failed", "incomplete"):
            raise ValueError(f"unfinished job: {f.name}")
        for row in rows:
            groups.setdefault(row["ledger_target"], []).append(row)
    for target, rows in groups.items():
        p = Path(target)
        p.parent.mkdir(parents=True, exist_ok=True)
        existing = [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
        seen = {sha({k: v for k, v in r.items() if k not in ("trial", "time")}) for r in existing}
        with p.open("a") as dst:
            for row in rows:
                content = {k: v for k, v in row.items() if k not in ("trial", "time")}
                signature = sha(content)
                if signature in seen:
                    continue
                seen.add(signature)
                content["trial"] = len(existing) + 1
                existing.append(content)
                dst.write(json.dumps(content, sort_keys=True, allow_nan=False) + "\n")
    return dict(jobs=len(files), targets=len(groups), commands=len(commands), failed_commands=sum(r["status"] == "failed" for r in statuses))
