"""Rotasyon null'unu (K1) Modal'de çok konteynere dağıtır (hakem ve hesap aynı; yalnızca çekilişler paralel).
  modal run scripts/null_fanout.py --b 300 --out /data/ensemble [--chunk 4] [--args "--expert trend"]                       # EV1 (varsayılan)
  modal run scripts/null_fanout.py --script carryxs_card --b 300 --chunk 2 --out /data/signal_diag/carry_xs_card            # carry_xs kartı K1
Her konteyner `scripts/<script>.py --stage null --null-from lo --null-to hi` koşar; çıktı `--out/null_<lo>_<hi>.json`, tek koşuyla aynı biçim ve aynı tohumlar.
Başarısızlık: worker returncode'u doğrudan aktarılır (shell/pipe yok); herhangi bir shard ≠ 0 ise iş exit 1 verir ve birleşim yazılmaz. Tüm shard'lar bitince `null_merge.merge`
tohum aralığını, eksik/yarım shard'ı, şemayı ve u'yu doğrular, içerik hash'li `null_merged.json` yazar. Retry aynı shard dosyasının üzerine yazar (aynı çıktı = aynı hash).
Seri referansla parity: tests/test_null_parity.py (küçük offline fixture, gerçek hakem; EV1/carry gerçek null'unda seri/parçalı karşılaştırma Modal'de burada YAPILMADI). Retry tüm shard'ları yeniden koşar, aynı adlı dosyaların üstüne yazar.
Süreler: shard başına duvar süresi `--out/timing_<lo>_<hi>.json` (sonuç hash'ine girmez). modal_app.py'nin imajı/volume'u yeniden kullanılır (korumalı dosyaya dokunulmaz)."""
import json
import pathlib
import os
import shlex
import sys
import time
import uuid

import modal

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import modal_app as M  # noqa: E402
import null_merge as NM  # noqa: E402

app = modal.App("kepler-null")
IMG = M.img.add_local_file(pathlib.Path(__file__).resolve().parent / "null_merge.py", "/root/null_merge.py")  # konteynerde yalnızca bu dosya /root'a bağlanır; null_merge yanına eklenir
KEYS = {"ensemble": "{}", "carryxs_card": "null_{}"}  # işçinin çıktı anahtarı biçimi (tohum -> anahtar)


@app.function(image=IMG, volumes={"/data": M.vol}, timeout=3600, cpu=4, memory=8192)
def draws(script: str, lo: int, hi: int, out: str, args: str, procs: int, manifest: dict) -> int:
    # shell/pipe yok: başarı = worker'ın gerçek returncode'u (log süzme yalnız gösterim)
    t0 = time.time()
    env = dict(os.environ, KEPLER_NULL_MANIFEST=json.dumps(manifest, sort_keys=True), KEPLER_JOB_RECEIPTS=f"{out}/jobs")
    rc = NM.run_worker(["python", f"scripts/{script}.py", "--stage", "null", "--null-from", str(lo), "--null-to", str(hi), "--procs", str(procs), "--out", out, *shlex.split(args)],
                       cwd="/repo", log=f"{out}/null_{lo}_{hi}.log", env=env)
    pathlib.Path(out, f"timing_{lo}_{hi}.json").write_text(json.dumps(dict(wall_s=round(time.time() - t0, 1), rc=rc, procs=procs)))
    M.vol.commit()
    return rc


@app.function(image=IMG, volumes={"/data": M.vol}, timeout=600)
def merge(script: str, out: str, b: int, chunk: int, manifest: dict) -> dict:
    """Yalnızca tüm shard'lar doğrulanırsa null_merged.json yazar (eksik/yarım/çelişkili → MergeError → üst iş başarısız)."""
    import numpy as np
    M.vol.reload()
    required = ("u", "net_pnl", "funding", "n_fills") if script == "ensemble" else ("u", "summary")
    m = NM.merge(out, b, chunk, expect_u=lambda i: float(np.random.default_rng([0, i]).uniform(0.05, 0.95)), key=KEYS[script], required=required, run_manifest=manifest)
    if script == "carryxs_card" and any(not isinstance(r["summary"], dict) or not {"net_pnl", "funding", "n_fills"} <= r["summary"].keys() for r in m["results"].values()):
        raise NM.MergeError("missing carry economic summary")
    for r in m["results"].values():
        NM.validate_economics(r if script == "ensemble" else r["summary"])
    import ledger_jobs
    ledger_jobs.collect(f"{out}/jobs")
    pathlib.Path(out, "null_merged.json").write_text(json.dumps(m))
    walls = [json.loads(p.read_text())["wall_s"] for p in pathlib.Path(out).glob("timing_*_*.json")]
    M.vol.commit()
    return dict(n=m["n"], content_sha=m["content_sha"], shard_wall_s=dict(n=len(walls), max=max(walls, default=0), mean=round(sum(walls) / max(len(walls), 1), 1)))


@app.local_entrypoint()
def main(b: int = 300, out: str = "/data/ensemble", chunk: int = 4, args: str = "", script: str = "ensemble", procs: int = 0):
    if script not in KEYS:
        raise SystemExit(f"--script {sorted(KEYS)} olmalı")
    if procs < 0:
        raise SystemExit("--procs must be nonnegative")
    t0, procs = time.time(), procs or chunk
    spans = NM.spans(b, chunk)
    from kepler import receipt
    manifest = dict(run_id=uuid.uuid4().hex, script=script, args=shlex.split(args), b=b, chunk=chunk,
                    source_sha=M.ENV["KEPLER_SOURCE_SHA"], code_hash=receipt.code_hash(*pathlib.Path(__file__).parent.glob("*.py")))
    out = f"{out}/runs/{manifest['run_id']}"
    rcs = list(draws.starmap([(script, lo, hi, out, args, min(procs, hi - lo), manifest) for lo, hi in spans]))
    print(f"{len(spans)} konteyner, çıkış kodları: {sorted(set(rcs))}; çıktı {out}/null_<lo>_<hi>.json; shard'lar bitti {time.time() - t0:.0f}s")
    if any(rcs):  # başarısız shard varsa birleşim ve başarı kartı üretilmez
        raise SystemExit(1)
    print("birleşim doğrulandı:", merge.remote(script, out, b, chunk, manifest), f"| uçtan uca {time.time() - t0:.0f}s")
