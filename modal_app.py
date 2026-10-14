"""Tek giriş: tüm kod Modal'de çalışır (yerelde proje kodu çalıştırılmaz).

  modal run modal_app.py --lock            # uv.lock üret (yerel dosyaya yazar)
  modal run modal_app.py --cmd "pytest -q" # repo'yu /repo'ya bağla, komutu koş
Kalıcı veri: Volume `kepler-data` -> /data (ham veri git'e girmez).
"""
import os
import hashlib
import pathlib
import shlex
import subprocess
import uuid

import modal

ROOT = pathlib.Path(__file__).parent
IGNORE = ["books/**", "lab/**", ".venv/**", ".git/**", ".pi/**", "data/**", "mlruns/**", "log/**",
          "git_ignore_folder/**", "pickle_cache/**", ".env", "**/__pycache__/**", "**/.DS_Store", "selector.log"]
ENV = {"UV_PROJECT_ENVIRONMENT": "/opt/venv", "PYTHONUNBUFFERED": "1", "PYTHONPATH": "/repo",
       "PATH": "/opt/venv/bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"}
ENV["KEPLER_SOURCE_SHA"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
ENV["KEPLER_DIRTY_DIFF_SHA"] = hashlib.sha256(subprocess.run(["git", "diff", "HEAD"], cwd=ROOT, capture_output=True).stdout).hexdigest()

app = modal.App("kepler")
vol = modal.Volume.from_name("kepler-data", create_if_missing=True)
base = modal.Image.debian_slim(python_version="3.12").apt_install("git").pip_install("uv").env(ENV)
lock_img = base.add_local_file(ROOT / "pyproject.toml", "/repo/pyproject.toml")
lockfile = ROOT / "uv.lock"
if lockfile.exists():
    img = (base.add_local_file(ROOT / "pyproject.toml", "/repo/pyproject.toml", copy=True)
           .add_local_file(lockfile, "/repo/uv.lock", copy=True)
           .run_commands("cd /repo && uv sync --frozen --no-install-project"))
else:
    img = lock_img
# Numba önbelleği imaja pişirilir: çekirdek dosyası copy=True katmanında (zaman damgası sabit), çalışma zamanı mount'undan hariç; kod değişmedikçe soğuk başlangıçta derleme yok.
CORE = ["kepler/__init__.py", "kepler/referee_core.py"]
img = img.env({"NUMBA_CACHE_DIR": "/opt/numba_cache", "NUMBA_CPU_NAME": "generic"})  # generic: önbellek build ve çalışma makinesi CPU modeli farklı olsa da geçerli kalır
for f_ in CORE + ["scripts/numba_warm.py"]:
    img = img.add_local_file(ROOT / f_, f"/repo/{f_}", copy=True)
img = img.run_commands("mkdir -p /opt/numba_cache && cd /repo && python scripts/numba_warm.py")
img = img.add_local_dir(ROOT, "/repo", ignore=IGNORE + CORE)


@app.function(image=lock_img, timeout=900)
def make_lock() -> str:
    subprocess.run("cd /repo && uv lock", shell=True, check=True)
    return pathlib.Path("/repo/uv.lock").read_text()


def _run(cmd: str, run_id: str = "", worker: int = 0) -> int:
    import sys
    sys.path.insert(0, "/repo/scripts")
    import ledger_jobs
    child_env = os.environ.copy()
    namespace = f"/data/job-receipts/{run_id or uuid.uuid4().hex}"
    # Tests assert local scratch paths; research workers always write private journals.
    if not any(t == "pytest" or t.endswith("/pytest") for t in shlex.split(cmd)):
        child_env["KEPLER_JOB_RECEIPTS"] = namespace
    ledger_jobs.command_status(namespace, worker, "running", cmd)
    proc = subprocess.Popen(cmd, shell=True, cwd="/repo", env=child_env)
    while True:  # uzun indirmede ilerleme kaybolmasın: dakikada bir Volume'a commit
        try:
            rc = proc.wait(timeout=60)
            break
        except subprocess.TimeoutExpired:
            vol.commit()
    ledger_jobs.command_status(namespace, worker, "completed" if rc == 0 else "failed", cmd, rc)
    vol.commit()
    return rc


@app.function(image=img, volumes={"/data": vol}, timeout=3 * 3600, cpu=4, memory=8192)
def run(cmd: str, run_id: str = "") -> int:
    return _run(cmd, run_id)


@app.function(image=img, volumes={"/data": vol}, timeout=3 * 3600, cpu=4, memory=8192)
def run_shard(a: tuple) -> int:
    """Aynı komutu N container'da koş: komut KEPLER_SHARD=i/n ortam değişkenini okuyup senaryo ızgarasından grid[i::n] alır (GIL'i aşmak için süreç/container ayrımı)."""
    cmd, i, n, run_id = a
    os.environ["KEPLER_SHARD"] = f"{i}/{n}"
    return _run(cmd, run_id, i)


@app.function(image=img, volumes={"/data": vol}, timeout=600)
def collect_run(run_id: str, expected_workers: int) -> dict:
    vol.reload()
    import sys
    sys.path.insert(0, "/repo/scripts")
    import ledger_jobs
    result = ledger_jobs.collect(f"/data/job-receipts/{run_id}", expected_workers=expected_workers)
    vol.commit()
    return result


@app.local_entrypoint()
def main(cmd: str = "", lock: bool = False, gpu: bool = False, shards: int = 1):
    if lock:
        lockfile.write_text(make_lock.remote())
        print("uv.lock yazıldı")
    if cmd:
        if shards < 1:
            raise SystemExit("--shards must be positive")
        if gpu:
            raise SystemExit("GPU path is retired: funding/intent CPU equivalence has not been validated. Use Numba CPU.")
        run_id = uuid.uuid4().hex
        rc = max(run_shard.map([(cmd, i, shards, run_id) for i in range(shards)])) if shards > 1 else run.remote(cmd, run_id)
        print("ledger collection:", collect_run.remote(run_id, shards))
        print(f"[exit {rc}]")
        raise SystemExit(rc)
