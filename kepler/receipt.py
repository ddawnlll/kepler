"""#12: küçük deney kimliği (receipt). Ekonomik kimlik = f(kepler/ paketinin TÜM kaynak içeriği + ek dosyalar, kanonik config, kitap closure'ı, gerçekten kullanılan veri içeriği ve kesim);
aynı girdi aynı kimlik, davranışı değiştiren kod/config/veri farklı kimlik verir. Köken (git SHA, kirli-diff, lockfile, çalışma ortamı) ve run/attempt/zaman AYRI tutulur, kimliğe girmez.
Anahtar/ortam değişkeni alınmaz; yalnızca fonksiyona verilen (kullanılan) veri hash'lenir."""
import dataclasses
import hashlib
import inspect
import platform
import subprocess
import time
import uuid
from importlib import metadata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _h(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fingerprint(o, depth: int = 0) -> str:
    """İçerik hash'i (DataFrame/Series/ndarray/dataclass/dict/list/fonksiyon kaynağı dahil; repr kesmesine güvenmez)."""
    if isinstance(o, (pd.DataFrame, pd.Series)):
        return _h(pd.util.hash_pandas_object(o, index=True).to_numpy().tobytes() + str(list(o.columns) if isinstance(o, pd.DataFrame) else o.name).encode() + str(o.index.dtype).encode())
    if isinstance(o, np.ndarray):
        return _h(o.tobytes() + str(o.shape).encode() + str(o.dtype).encode())
    if dataclasses.is_dataclass(o) and not isinstance(o, type):
        return fingerprint(dataclasses.asdict(o), depth)
    if isinstance(o, dict):
        return _h("|".join(f"{k!r}:{fingerprint(v, depth)}" for k, v in sorted(o.items(), key=lambda kv: repr(kv[0]))).encode())
    if isinstance(o, (list, tuple, set, frozenset)):
        items = sorted((fingerprint(x, depth) for x in o)) if isinstance(o, (set, frozenset)) else (fingerprint(x, depth) for x in o)
        return _h(("[" + ",".join(items) + "]").encode())
    if callable(o):
        try:
            return _h(inspect.getsource(o).encode() + (closure_fp(o, depth + 1) if depth < 3 else "").encode())
        except (OSError, TypeError):
            return _h(repr(o).encode())
    return _h(repr(o).encode())


def closure_fp(f, depth: int = 0) -> str:
    """Kitap/fonksiyon closure'unun (örn. make_book'un p, üyelik tablosu, hyst) içerik hash'i (iç içe fonksiyonlar en çok 3 düzey)."""
    cells = []
    for c in getattr(f, "__closure__", None) or ():
        try:
            cells.append(c.cell_contents)
        except ValueError:  # boş hücre
            cells.append(None)
    return fingerprint(cells, depth) if cells else ""


def code_hash(*extra_files) -> str:
    """kepler/ altındaki TÜM .py içeriği + ek dosyalar (örn. çağıran betik)."""
    files = sorted((ROOT / "kepler").rglob("*.py")) + [Path(p) for p in extra_files]
    return _h("".join(f"{p.name}:{_h(p.read_bytes())};" for p in files).encode())


def data_manifest(data: dict[str, dict], cut=None) -> dict:
    """Gerçekten kullanılan veri: sembol başına kline/funding/mark içerik hash'i, satır sayısı ve aralık; kesim (pencere) ve sembol kümesi. Yalnız sembol listesi kimlik sayılmaz."""
    per = {}
    for s in sorted(data):
        d = data[s]
        per[s] = {k: dict(sha=fingerprint(v), n=len(v), first=str(v.index[0]) if len(v) else None, last=str(v.index[-1]) if len(v) else None)
                  for k in ("kl", "funding", "mark") if (v := d.get(k)) is not None}
    return dict(symbols=sorted(data), per_symbol=per, cut=[str(c) for c in cut] if cut else None, id=fingerprint(per) + fingerprint(sorted(data)) + fingerprint([str(c) for c in cut] if cut else None))


def _git(*a) -> str:
    try:
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def provenance() -> dict:
    """Köken (kimliğe girmez): Git SHA, kirli-diff hash'i (izlenen dosyalar), uv.lock hash'i, çalışma ortamı."""
    lock = ROOT / "uv.lock"
    vers = {}
    for pkg in ("numpy", "pandas", "nautilus_trader", "scipy", "duckdb"):
        try:
            vers[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            vers[pkg] = None
    return dict(git_sha=_git("rev-parse", "HEAD").strip() or None, dirty_diff_sha=_h(_git("diff", "HEAD").encode()), lock_sha=_h(lock.read_bytes()) if lock.exists() else None,
                python=platform.python_version(), packages=vers)


def make(config: dict, data: dict[str, dict], cut=None, book=None, extra_files=(), run_id: str | None = None, attempt: int = 1) -> dict:
    """Receipt: economic_id (ekonomik kimlik) + bileşen hash'leri + köken + run/attempt (kimlik dışı)."""
    code = code_hash(*extra_files)
    cfg, dm, clo = fingerprint(config), data_manifest(data, cut), closure_fp(book) if book is not None else ""
    return dict(economic_id=_h(f"{code}|{cfg}|{dm['id']}|{clo}".encode()), code_hash=code, config_sha=cfg, data=dm, closure_sha=clo, provenance=provenance(),
                run_id=run_id or uuid.uuid4().hex, attempt=attempt, created=time.time())


def provenance_status(row: dict) -> str:
    """Eski kayıtlar silinmez/değiştirilmez; receipt'i olmayan kayıt açıkça işaretlenir."""
    return "full" if row.get("receipt") else "legacy_partial_provenance"
