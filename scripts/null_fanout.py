"""K1 rotasyon null'unu Modal'de çok konteynere dağıtır (hakem ve hesap aynı; yalnızca çekilişler paralel).
  modal run scripts/null_fanout.py --b 300 --out /data/ensemble [--chunk 4] [--args "--expert trend"]
Her konteyner `scripts/ensemble.py --stage null --null-from lo --null-to hi` koşar; çıktı `--out/null_<lo>_<hi>.json`, tek koşuyla aynı biçim ve aynı tohumlar
(sonuçlar sıralı koşuyla birebir aynı: Modal'de DOĞRULANMADI; bkz. TASKS.md).
Başarısızlık: worker returncode'u doğrudan aktarılır (shell/pipe yok); herhangi bir shard ≠ 0 ise iş exit 1 verir ve birleşim yazılmaz. Tüm shard'lar bitince `null_merge.merge`
tohum aralığı, eksik/yarım shard, şema ve u'yu doğrular, içerik hash'li `null_merged.json` yazar. Retry aynı shard dosyasının üzerine yazar (aynı çıktı = aynı hash).
FAILURE/RETRY (gerçek davranış): bir shard ≠ 0 dönerse iş exit 1 ile biter, birleşim ve başarı kartı üretilmez; düzeltmeden sonra AYNI komut yeniden koşulur (tüm shard'lar yeniden çalışır, aynı adlı dosyaların üstüne yazılır; yalnız-eksik-shard kipi yok).
Seri referansla parity: tests/test_null_parity.py (küçük offline fixture; EV1 gerçek null'unda Modal'de DOĞRULANMADI). Hız ölçümü: fixture ölçeğinde süreç başlatma baskın, anlamlı hızlanma ölçülmedi; B=300 EV1 hız iddiası (≈65 dk → 97 sn) bağımsız doğrulanmadı. modal_app.py'nin imajı/volume'u yeniden kullanılır (korumalı dosyaya dokunulmaz)."""
import json
import pathlib
import sys

import modal

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import modal_app as M  # noqa: E402
import null_merge as NM  # noqa: E402

app = modal.App("kepler-null")


@app.function(image=M.img, volumes={"/data": M.vol}, timeout=3600, cpu=4, memory=8192)
def draws(lo: int, hi: int, out: str, args: str) -> int:
    # shell/pipe yok: başarı = worker'ın gerçek returncode'u (log süzme yalnız gösterim)
    rc = NM.run_worker(["python", "scripts/ensemble.py", "--stage", "null", "--null-from", str(lo), "--null-to", str(hi), "--procs", "4", "--out", out, *args.split()],
                       cwd="/repo", log=f"{out}/null_{lo}_{hi}.log")
    M.vol.commit()
    return rc


@app.function(image=M.img, volumes={"/data": M.vol}, timeout=600)
def merge(out: str, b: int, chunk: int) -> dict:
    """Yalnızca tüm shard'lar doğrulanırsa null_merged.json yazar (eksik/yarım/çelişkili → MergeError → üst iş başarısız)."""
    import numpy as np
    M.vol.reload()
    m = NM.merge(out, b, chunk, expect_u=lambda i: float(np.random.default_rng([0, i]).uniform(0.05, 0.95)))
    pathlib.Path(out, "null_merged.json").write_text(json.dumps(m))
    M.vol.commit()
    return dict(n=m["n"], content_sha=m["content_sha"])


@app.local_entrypoint()
def main(b: int = 300, out: str = "/data/ensemble", chunk: int = 4, args: str = ""):
    spans = NM.spans(b, chunk)
    rcs = list(draws.starmap([(lo, hi, out, args) for lo, hi in spans]))
    print(f"{len(spans)} konteyner, çıkış kodları: {sorted(set(rcs))}; çıktı {out}/null_<lo>_<hi>.json")
    if any(rcs):  # başarısız shard varsa birleşim ve başarı kartı üretilmez
        raise SystemExit(1)
    print("birleşim doğrulandı:", merge.remote(out, b, chunk))
