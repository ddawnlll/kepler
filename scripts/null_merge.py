"""Null fan-out yardımcıları (stdlib; Modal'siz test edilir): worker çıkış kodu aktarımı ve parça birleşimi doğrulaması.
Başarı ölçütü yalnızca worker returncode'u + parçanın şemaya uyması; log süzme (grep) başarıyı belirlemez. Hakem/ledger'a dokunmaz."""
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

NEEDED = ("u",)  # çekiliş çıktısı: u (ensemble.py: keep(res) alanları + u; carryxs_card.py: summary + u)


class MergeError(RuntimeError):
    pass


def spans(b: int, chunk: int) -> list[tuple[int, int]]:
    if b < 1 or chunk < 1:
        raise MergeError("b and chunk must be positive")
    return [(lo, min(lo + chunk, b)) for lo in range(0, b, chunk)]


def run_worker(argv: list[str], cwd: str | None = None, log: str | None = None, tail: int = 20, env=None) -> int:
    """Worker'ı shell'siz koşar; DÖNEN DEĞER worker'ın gerçek returncode'udur. Log yalnız gösterim içindir (son satırlar + Error/Traceback satırları)."""
    p = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, errors="replace")
    text = (p.stdout or "") + (p.stderr or "")
    if log:
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        Path(log).write_text(text)
    lines = text.splitlines()
    shown = [l for l in lines if "null bitti" in l or "Error" in l or "Traceback" in l] or lines[-tail:]
    print("\n".join(shown[-tail:]), file=sys.stderr)
    return p.returncode


def _canon(v) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), allow_nan=False)


def finite(v):
    if isinstance(v, dict):
        return all(finite(x) for x in v.values())
    if isinstance(v, list):
        return all(finite(x) for x in v)
    return not isinstance(v, (float, int)) or math.isfinite(v)


def sha(v) -> str:
    return hashlib.sha256(_canon(v).encode()).hexdigest()


def publish_identity(path, economic_id):
    """Sidecar from the worker's actual loaded data/config; runtime supplies run manifest."""
    import os
    if raw := os.environ.get("KEPLER_NULL_MANIFEST"):
        meta = Path(path).with_suffix(".manifest.json")
        meta.write_text(json.dumps(dict(run_manifest=json.loads(raw), economic_id=economic_id), sort_keys=True, allow_nan=False))


def validate_economics(r):
    """Production shards must contain finite economic metrics and a valid engine run."""
    for k in ("net_pnl", "funding", "n_fills", "n_rejected", "n_engine_unfilled", "funding_missed"):
        if not isinstance(r.get(k), (int, float)) or isinstance(r[k], bool) or not math.isfinite(r[k]):
            raise MergeError(f"missing or nonnumeric economic metric: {k}")
    if r["n_fills"] < 0 or r["n_fills"] != int(r["n_fills"]) or any(r[k] != 0 for k in ("n_rejected", "n_engine_unfilled", "funding_missed")):
        raise MergeError("invalid engine run in null shard")


def merge(out_dir: str, b: int, chunk: int, expect_u=None, key: str = "{}", required=NEEDED, run_manifest=None) -> dict:
    """Beklenen her [lo,hi) parçasını okur ve doğrular; {tohum: kayıt} birleşimini + manifest döndürür. Hata → MergeError (başarı kartı üretilmez).
    Parça: tam olarak lo..hi-1 anahtarları; her kayıt dict, NEEDED alanlı, sonlu sayı. Retry aynı dosya adının üzerine yazar (idempotent); başka aralıklı/çakışan dosya = beklenmeyen → hata (çelişkili duplicate sessizce seçilmez).
    key: kayıt anahtarı biçimi (ensemble.py "{}" -> "17"; carryxs_card.py "null_{}" -> "null_17"). expect_u(i) verilirse u tohum-belirlenimli olarak doğrulanır. Beklenmeyen null_*.json dosyası (aralık dışı/yanlış chunk) hata."""
    d = Path(out_dir)
    want = {d / f"null_{lo}_{hi}.json": (lo, hi) for lo, hi in spans(b, chunk)}
    stray = sorted(p.name for p in d.glob("null_*_*.json") if p not in want and p.name != "null_merged.json" and not p.name.endswith(".manifest.json"))
    if stray:
        raise MergeError(f"beklenmeyen parça dosyaları: {stray}")
    merged, manifest, identities = {}, {}, set()
    for path, (lo, hi) in want.items():
        if not path.exists():
            raise MergeError(f"eksik shard: {path.name}")
        if run_manifest is not None:
            meta = path.with_suffix(".manifest.json")
            try:
                identity = json.loads(meta.read_text())
            except (OSError, json.JSONDecodeError) as e:
                raise MergeError(f"{path.name}: missing or malformed run manifest") from e
            eid = identity.get("economic_id") if isinstance(identity, dict) else None
            if not isinstance(eid, str) or len(eid) != 64 or any(c not in "0123456789abcdef" for c in eid) or identity.get("run_manifest") != run_manifest:
                raise MergeError(f"{path.name}: run manifest mismatch")
            identities.add(eid)
            if len(identities) != 1:
                raise MergeError(f"{path.name}: economic/data identity mismatch")
        try:
            part = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            raise MergeError(f"yarım/bozuk çıktı {path.name}: {e}") from e
        if not isinstance(part, dict) or sorted(map(str, part)) != sorted(key.format(i) for i in range(lo, hi)):
            raise MergeError(f"{path.name}: tohum kümesi {lo}..{hi - 1} ile eşleşmiyor")
        for k, rec in part.items():
            i = int(k.rsplit("_", 1)[-1])
            if not isinstance(rec, dict) or any(f not in rec for f in required) or not isinstance(rec.get("u"), (float, int)):
                raise MergeError(f"{path.name}[{k}]: kayıt şeması bozuk")
            if not finite(rec):
                raise MergeError(f"{path.name}[{k}]: NaN/Inf değer")
            if expect_u is not None and abs(rec["u"] - expect_u(i)) > 1e-12:
                raise MergeError(f"{path.name}[{k}]: u tohumla uyuşmuyor")
            merged[i] = rec
        manifest[path.name] = sha(part)
    if sorted(merged) != list(range(b)):
        raise MergeError(f"tohum aralığı 0..{b - 1} tam değil: {len(merged)} benzersiz")
    out = dict(results={key.format(i): merged[i] for i in sorted(merged)}, n=len(merged), shards=manifest, content_sha=sha(merged))
    if run_manifest is not None:
        out.update(run_manifest=run_manifest, economic_id=next(iter(identities)))
    return out
