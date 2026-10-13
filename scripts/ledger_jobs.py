"""#13: defter yardımcıları (kepler/ dışı; satır tavanı için): özet sayımı ve dağıtık güvenli job-receipt modeli. `kepler.ledger.record/record_attempt` satır biçimini üretir, burası okur/toplar."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kepler.ledger import sha  # noqa: E402


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
