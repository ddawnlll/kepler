"""#12: deney kimliği (receipt). economic_id = f(kepler/ TÜM kaynağı + ek dosyalar, config, kitap closure'ı, kullanılan veri içeriği, kesim). Köken (git, lockfile, ortam) ve run/attempt kimliğe girmez; anahtar/ortam değişkeni alınmaz."""
import dataclasses
import hashlib
import inspect
import os
import platform
import subprocess
import time
import uuid
from contextlib import suppress
from importlib import metadata
from pathlib import Path
from functools import partial

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
    if isinstance(o, partial):
        return fingerprint((o.func, o.args, o.keywords), depth)
    if callable(o):
        try:
            return _h((getattr(o, "__module__", type(o).__module__) + ":" + getattr(o, "__qualname__", type(o).__qualname__)).encode() + inspect.getsource(o).encode() + fingerprint((getattr(o, "__defaults__", None), getattr(o, "__kwdefaults__", None))).encode() + (closure_fp(o, depth + 1) if depth < 3 else "").encode())
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
    """Canonical dependency hash: all package/scripts sources, lock and explicit inputs."""
    from kepler import ledger
    # Pass the canonical package file list explicitly so dependency coverage is inspectable.
    files = sorted((ROOT / "kepler").rglob("*.py"))
    return ledger.code_hash(*files, *extra_files)


def data_manifest(data: dict[str, dict], cut=None) -> dict:
    """Kullanılan veri: sembol başına kline/funding/mark içerik hash'i, satır sayısı, aralık; kesim ve sembol kümesi (yalnız sembol listesi kimlik sayılmaz)."""
    per = {}
    for s in sorted(data):
        d = data[s]
        per[s] = {k: dict(sha=fingerprint(v), n=len(v), first=str(v.index[0]) if len(v) else None, last=str(v.index[-1]) if len(v) else None)
                  for k in ("kl", "funding", "mark", "target", "stop", "funding_fallback_kl") if (v := d.get(k)) is not None}
        per[s]["execution_rules"] = {k: d.get(k) for k in ("tick", "step")}
    window = [str(c) for c in cut] if cut else None
    return dict(symbols=sorted(data), execution_order=list(data), per_symbol=per, cut=window, id=fingerprint((list(data), per, window)))


def _git(*a) -> str:
    try:
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _ver(pkg):
    with suppress(metadata.PackageNotFoundError):
        return metadata.version(pkg)


def provenance() -> dict:
    """Köken: Git SHA, kirli-diff hash'i (izlenen dosyalar), uv.lock hash'i, Python/paket sürümleri."""
    lock = ROOT / "uv.lock"
    return dict(git_sha=_git("rev-parse", "HEAD").strip() or os.environ.get("KEPLER_SOURCE_SHA"), dirty_diff_sha=os.environ.get("KEPLER_DIRTY_DIFF_SHA") or _h(_git("diff", "HEAD").encode()), lock_sha=_h(lock.read_bytes()) if lock.exists() else None,
                python=platform.python_version(), packages={p: _ver(p) for p in ("numpy", "pandas", "numba", "scipy", "duckdb")})


def make(config: dict, data: dict[str, dict], cut=None, book=None, extra_files=(), run_id: str | None = None, attempt: int = 1, size=None) -> dict:
    """Receipt: economic_id (ekonomik kimlik) + bileşen hash'leri + köken + run/attempt (kimlik dışı)."""
    code = code_hash(*extra_files)
    cfg, dm, clo = fingerprint(config), data_manifest(data, cut), fingerprint((book, size))
    return dict(economic_id=_h(f"{code}|{cfg}|{dm['id']}|{clo}".encode()), code_hash=code, config_sha=cfg, data=dm, closure_sha=clo, provenance=provenance(),
                run_id=run_id or uuid.uuid4().hex, attempt=attempt, created=time.time())


def provenance_status(row: dict) -> str:
    """Eski kayıtlar silinmez/değiştirilmez; receipt'i olmayan kayıt açıkça işaretlenir."""
    return "full" if row.get("receipt") else "legacy_partial_provenance"
