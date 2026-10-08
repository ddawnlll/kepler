"""K1 rotasyon null'unu Modal'de çok konteynere dağıtır (hakem ve hesap aynı; yalnızca çekilişler paralel).
  modal run scripts/null_fanout.py --b 300 --out /data/ensemble [--chunk 4] [--args "--expert trend"]
Her konteyner `scripts/ensemble.py --stage null --null-from lo --null-to hi` koşar; çıktı `--out/null_<lo>_<hi>.json`, tek koşuyla aynı biçim ve aynı tohumlar
(sonuçlar sıralı koşuyla birebir aynı). modal_app.py'nin imajı/volume'u yeniden kullanılır (korumalı dosyaya dokunulmaz)."""
import pathlib
import subprocess
import sys

import modal

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import modal_app as M  # noqa: E402

app = modal.App("kepler-null")


@app.function(image=M.img, volumes={"/data": M.vol}, timeout=3600, cpu=4, memory=8192)
def draws(lo: int, hi: int, out: str, args: str) -> int:
    rc = subprocess.run(f"python scripts/ensemble.py --stage null --null-from {lo} --null-to {hi} --procs 4 --out {out} {args} 2>&1 | grep -a 'null bitti\\|Error\\|Traceback'",
                        shell=True, cwd="/repo").returncode
    M.vol.commit()
    return rc


@app.local_entrypoint()
def main(b: int = 300, out: str = "/data/ensemble", chunk: int = 4, args: str = ""):
    spans = [(lo, min(lo + chunk, b)) for lo in range(0, b, chunk)]
    rcs = list(draws.starmap([(lo, hi, out, args) for lo, hi in spans]))
    print(f"{len(spans)} konteyner, çıkış kodları: {sorted(set(rcs))}; çıktı {out}/null_<lo>_<hi>.json")
    raise SystemExit(int(any(rcs)))
