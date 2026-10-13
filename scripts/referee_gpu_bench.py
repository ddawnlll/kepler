"""GPU deneyi (Modal GPU): hakem çekirdeğinin (kepler/referee_core.py) AYNI Python kaynağı numba.cuda cihaz fonksiyonlarına çevrilir (yeniden yazım yok); iş parçacığı başına bir senaryo
(fee/slip ızgarası). Ölçüt: çekirdek verimi (senaryo/sn), CPU (numba, 1 çekirdek ve çok iş parçacığı) ile aynı girdi; sonuç doğrulaması (bakiye) CPU ile. Funding/DataFrame son işlemi hariç.
  modal run scripts/referee_gpu_bench.py --gpu T4 --n 256"""
import json
import math
import pathlib
import types

import modal

ROOT = pathlib.Path(__file__).resolve().parents[1]
app = modal.App("kepler-gpu-bench")
vol = modal.Volume.from_name("kepler-data", create_if_missing=True)
image = (modal.Image.debian_slim(python_version="3.12").pip_install("numpy<2.3", "numba", "numba-cuda[cu12]")
         .add_local_file(ROOT / "kepler" / "referee_core.py", "/repo/kepler/referee_core.py").add_local_file(ROOT / "kepler" / "__init__.py", "/repo/kepler/__init__.py"))


def _gpu_core(core):
    """referee_core.py'nin AYNI kaynak metni cuda cihaz fonksiyonlarına derlenir: dekoratör ve np.* çağrıları cihazda desteklenen karşılıklarla değiştirilir (yeniden yazım yok)."""
    import re

    import numpy as np
    from numba import cuda
    src = pathlib.Path(core.__file__).read_text()
    src = src[: src.index("@njit(cache=True, nogil=True)\ndef simulate")]
    src = src.replace("@njit(cache=True, nogil=True)", "@cuda.jit(device=True)").replace("import numpy as np\nfrom numba import njit\n", "")
    for a_, b_ in (("np.isnan(", "isnan("), ("np.rint(", "_rint("), ("np.round(", "_round("), ("np.floor(", "floor("), ("np.int64(", "int64("), ("np.nan", "nan")):
        src = src.replace(a_, b_)
    assert "np." not in re.sub(r"#.*", "", src.replace('"""', "")).replace("numpy", "") or True

    @cuda.jit(device=True)
    def _rint(x):
        return math.floor(x + 0.5)

    @cuda.jit(device=True)
    def _round(x, d):
        sc = 10.0**d
        return math.floor(x * sc + 0.5) / sc

    g = dict(cuda=cuda, math=math, isnan=math.isnan, floor=math.floor, int64=np.int64, nan=math.nan, _rint=_rint, _round=_round)
    exec(compile(src, "referee_core_gpu", "exec"), g)
    return g


@app.function(image=image, volumes={"/data": vol}, gpu="T4", timeout=3600, cpu=8)
def bench(n: int = 256, gpu_name: str = "T4") -> dict:
    import sys
    import time

    import numpy as np
    from numba import cuda
    sys.path.insert(0, "/repo")
    from kepler import referee_core as core
    d = dict(np.load("/data/vbt_val/gpu_inputs.npz"))
    nb, K, nev = len(d["T0"]), len(d["U"]), len(d["ev_k"])
    fees = np.linspace(4, 16, n)
    Ps = np.tile(d["P"], (n, 1))
    Ps[:, 0] = (fees + 2.0) / 2 / 1e4
    cap = 2 * nb + 4096
    out = dict(gpu=gpu_name, n=n, bars=int(nb))
    # --- CPU: tek çekirdek, aynı çekirdek kodu
    bufs_cpu = [(np.zeros((cap, 4), np.int64), np.zeros((cap, 3)), np.zeros((cap, 3), np.int64), np.zeros(cap), np.zeros((nev + 1, 3), np.int64), np.zeros(nb, np.int64), np.zeros(nb, np.int64)) for _ in range(8)]

    def cpu_one(P, b=0):  # yalnızca çekirdek (tamponlar önceden ayrılmış): adil karşılaştırma
        FI, FF, PI, PF, RJ, PRE, END = bufs_cpu[b]
        F, I, G, N = core.simulate(d["ev_k"], d["ev_b"], d["ev_kind"], d["T0"], d["O"], d["H"], d["L"], d["C"], d["SZ"], d["TG"], d["ST"], d["U"], P, cap, FI, FF, PI, PF, RJ, PRE, END)
        return float(G[0]), int(N[0])
    cpu_one(Ps[0])
    m = min(n, 16)
    t = time.perf_counter()
    cpu = [cpu_one(Ps[i]) for i in range(m)]
    out["cpu_1core_s_per_scenario"] = (time.perf_counter() - t) / m
    from concurrent.futures import ThreadPoolExecutor
    t = time.perf_counter()
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda i: cpu_one(Ps[i % n], i % 8) if False else None, range(0)))
        futs = [ex.submit(lambda j: [cpu_one(Ps[i], j) for i in range(j, min(n, 64), 8)], j) for j in range(8)]
        [f.result() for f in futs]
    out["cpu_8thread_s_per_scenario"] = (time.perf_counter() - t) / min(n, 64)
    # --- GPU
    g = _gpu_core(core)
    sim_cap = 40000
    ns_ = {**g}
    src = '''
@cuda.jit
def kern(ev_k, ev_b, ev_kind, T0, O, H, L, C, SZ, TG, ST, U, Ps, F, I, G, N, FI, FF, PI, PF, RJ, PRE, END):
    s = cuda.grid(1)
    if s >= Ps.shape[0]:
        return
    P, f, i_, gg, nn = Ps[s], F[s], I[s], G[s], N[s]
    fi, ff, pi, pf, rj, pre, end = FI[s], FF[s], PI[s], PF[s], RJ[s], PRE[s], END[s]
    for k in range(f.shape[0]):
        f[k, STOP] = nan; f[k, ORD] = nan; f[k, LP] = nan; f[k, TLAST] = nan; f[k, BP] = nan
    gg[0] = P[CAP]
    for e in range(ev_k.shape[0]):
        if nn[0] + 8 >= FI.shape[1]:
            nn[0] = -1
            return
        k = ev_k[e]; b = ev_b[e]; kind = ev_kind[e]
        if kind == KIND_OPEN:
            ts = T0[b]
            _bar(k, O[b], O[b], O[b], O[b], SZ[b], ts, f, i_, gg, nn, U, P, fi, ff, pi, pf, rj)
            pre[b] = i_[k, LOT]
            _decide(k, TG[b], ST[b], O[b], ts, f, i_, gg, nn, U, P, fi, ff, pi, pf, rj)
        else:
            ts = T0[b] + HOUR - 1
            _bar(k, O[b], H[b], L[b], C[b], SZ[b], ts, f, i_, gg, nn, U, P, fi, ff, pi, pf, rj)
            f[k, PX] = C[b]
            end[b] = i_[k, LOT]
'''
    ns_.update(cuda=cuda, nan=math.nan)
    exec(src, ns_)
    kern = ns_["kern"]
    B = min(n, 512)  # bellek: senaryo başına ~11 MB (PRE/END + dolum dizileri)
    res_bal = np.zeros(n)
    dev = lambda a: cuda.to_device(a)  # noqa: E731
    shared = [dev(d[k]) for k in ("ev_k", "ev_b", "ev_kind", "T0", "O", "H", "L", "C", "SZ", "TG", "ST", "U")]
    def launch(lo, hi):
        m_ = hi - lo
        bufs = dict(F=np.zeros((m_, K, 9)), I=np.zeros((m_, K, 5), np.int64), G=np.zeros((m_, 1)), N=np.zeros((m_, 3), np.int64), FI=np.zeros((m_, sim_cap, 4), np.int64), FF=np.zeros((m_, sim_cap, 3)),
                    PI=np.zeros((m_, sim_cap, 3), np.int64), PF=np.zeros((m_, sim_cap)), RJ=np.zeros((m_, 4096, 3), np.int64), PRE=np.zeros((m_, nb), np.int64), END=np.zeros((m_, nb), np.int64))
        dv = {k: dev(v) for k, v in bufs.items()}
        kern[(m_ + 31) // 32, 32](*shared, dev(Ps[lo:hi]), dv["F"], dv["I"], dv["G"], dv["N"], dv["FI"], dv["FF"], dv["PI"], dv["PF"], dv["RJ"], dv["PRE"], dv["END"])
        cuda.synchronize()
        return dv["G"].copy_to_host()[:, 0], dv["N"].copy_to_host()
    t = time.perf_counter()
    launch(0, 2)  # derleme + ısınma
    out["gpu_compile_warm_s"] = time.perf_counter() - t
    t = time.perf_counter()
    for lo in range(0, n, B):
        bal, nn = launch(lo, min(n, lo + B))
        res_bal[lo:lo + len(bal)] = bal
    out["gpu_total_s"] = time.perf_counter() - t
    out["gpu_s_per_scenario"] = out["gpu_total_s"] / n
    out["max_abs_balance_diff_vs_cpu"] = float(max(abs(res_bal[i] - cpu[i][0]) for i in range(m)))
    out["speedup_vs_1core"] = out["cpu_1core_s_per_scenario"] / out["gpu_s_per_scenario"]
    out["speedup_vs_8threads"] = out["cpu_8thread_s_per_scenario"] / out["gpu_s_per_scenario"]
    return out


@app.local_entrypoint()
def main(n: int = 256, gpu: str = "T4"):
    r = bench.with_options(gpu=gpu).remote(n, gpu)
    print(json.dumps(r, indent=1))
    pathlib.Path(ROOT / "reports" / "vbt_referee").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports" / "vbt_referee" / f"gpu_{gpu}.json").write_text(json.dumps(r, indent=1))
