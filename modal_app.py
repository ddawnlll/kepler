"""Tek giriş: tüm kod Modal'de çalışır (yerelde proje kodu çalıştırılmaz).

  modal run modal_app.py --lock            # uv.lock üret (yerel dosyaya yazar)
  modal run modal_app.py --cmd "pytest -q" # repo'yu /repo'ya bağla, komutu koş
Kalıcı veri: Volume `kepler-data` -> /data (ham veri git'e girmez).
"""
import pathlib
import subprocess

import modal

ROOT = pathlib.Path(__file__).parent
IGNORE = ["books/**", "lab/**", ".venv/**", ".git/**", ".pi/**", "data/**", "mlruns/**", "log/**",
          "git_ignore_folder/**", "pickle_cache/**", ".env", "**/__pycache__/**", "**/.DS_Store", "selector.log"]
ENV = {"UV_PROJECT_ENVIRONMENT": "/opt/venv", "PYTHONUNBUFFERED": "1", "PYTHONPATH": "/repo",
       "PATH": "/opt/venv/bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"}

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
img = img.add_local_dir(ROOT, "/repo", ignore=IGNORE)


@app.function(image=lock_img, timeout=900)
def make_lock() -> str:
    subprocess.run("cd /repo && uv lock", shell=True, check=True)
    return pathlib.Path("/repo/uv.lock").read_text()


@app.function(image=img, volumes={"/data": vol}, timeout=3 * 3600, cpu=4, memory=8192)
def run(cmd: str) -> int:
    proc = subprocess.Popen(cmd, shell=True, cwd="/repo")
    while True:  # uzun indirmede ilerleme kaybolmasın: dakikada bir Volume'a commit
        try:
            rc = proc.wait(timeout=60)
            break
        except subprocess.TimeoutExpired:
            vol.commit()
    vol.commit()
    return rc


@app.local_entrypoint()
def main(cmd: str = "", lock: bool = False):
    if lock:
        lockfile.write_text(make_lock.remote())
        print("uv.lock yazıldı")
    if cmd:
        rc = run.remote(cmd)
        print(f"[exit {rc}]")
        raise SystemExit(rc)
