"""Hakem çekirdeğinin GPU yolu (numba.cuda): referee_core.py'nin AYNI kaynak metni cihaz fonksiyonlarına derlenir (kod kopyası yok), iş parçacığı başına bir senaryo.
Kullanım: referee.run_many(data, specs, kernel=simulate_many). Yalnızca aynı veriyle çok senaryo (fee/slip/gecikme ızgarası) için; tek koşu CPU'da 0,6 sn. Çıktı CPU çekirdeğiyle aynı ham dizilerdir, funding/özet referee._finish'te hesaplanır.
Ölçüm (Modal, EV1 462 bin bar): yalnız çekirdek T4 9 ms, A10G 5 ms / senaryo (8 iş parçacıklı CPU 63-87 ms); TAM HAT (funding+özet CPU'da, T4, 128 senaryo) 149 ms vs CPU 168 ms = 1,1x: darboğaz CPU'daki _finish, bu yüzden varsayılan CPU. Derleme ~11 sn (süreç başına bir kez). Taşma (fills/RJ kapasitesi) -> None: çağıran CPU'ya düşer."""
import math
import pathlib

import numpy as np

from kepler import referee_core as core

_kern = None

def available() -> bool:
    try:
        from numba import cuda
        return bool(cuda.is_available())
    except Exception:  # noqa: BLE001  CUDA yok/sürücü uyumsuz: CPU'ya düş
        return False


def _build():
    """referee_core.py kaynağını cihaz fonksiyonlarına çevir ve senaryo çekirdeğini (kern) derle."""
    from numba import cuda
    src = pathlib.Path(core.__file__).read_text()
    src = src[: src.index("@njit(cache=True, nogil=True)\ndef simulate")].replace("@njit(cache=True, nogil=True)", "@cuda.jit(device=True)").replace("import numpy as np\nfrom numba import njit\n", "")
    for a, b in (("np.isnan(", "isnan("), ("np.rint(", "_rint("), ("np.round(", "_round("), ("np.floor(", "floor("), ("np.int64(", "int64("), ("np.nan", "nan")):
        src = src.replace(a, b)

    @cuda.jit(device=True)
    def _rint(x):
        return math.floor(x + 0.5)  # np.rint'in beraberlik (yarı-çift) farkı: ~1e-8 USDT mertebesi, CPU ile bakiye farkı ölçüldü

    @cuda.jit(device=True)
    def _round(x, d):
        return math.floor(x * 10.0**d + 0.5) / 10.0**d

    g = dict(cuda=cuda, math=math, isnan=math.isnan, floor=math.floor, int64=np.int64, nan=math.nan, _rint=_rint, _round=_round)
    exec(compile(src, "referee_core_gpu", "exec"), g)
    exec(compile('''
@cuda.jit
def kern(ev_k, ev_b, ev_kind, T0, O, H, L, C, SZ, TG, ST, U, Ps, F, I, G, N, FI, FF, PI, PF, RJ, PRE, END):
    s = cuda.grid(1)
    if s >= Ps.shape[0]:
        return
    P, f, i_, gg, nn, fi, ff, pi, pf, rj, pre, end = Ps[s], F[s], I[s], G[s], N[s], FI[s], FF[s], PI[s], PF[s], RJ[s], PRE[s], END[s]
    for k in range(f.shape[0]):
        f[k, STOP], f[k, ORD], f[k, LP], f[k, TLAST], f[k, BP] = nan, nan, nan, nan, nan
    gg[0] = P[CAP]
    for e in range(ev_k.shape[0]):
        if nn[0] + 8 >= fi.shape[0] or nn[2] + 8 >= rj.shape[0]:
            nn[0] = -1
            return
        k, b, kind = ev_k[e], ev_b[e], ev_kind[e]
        if kind == KIND_BODY:
            ts = T0[b] + HOUR - 1
            _bar(k, O[b], H[b], L[b], C[b], SZ[b], ts, f, i_, gg, nn, U, P, fi, ff, pi, pf, rj)
            f[k, PX] = C[b]
            end[b] = i_[k, LOT]
        elif kind == KIND_OPEN:
            ts = T0[b]
            _bar(k, O[b], O[b], O[b], O[b], SZ[b], ts, f, i_, gg, nn, U, P, fi, ff, pi, pf, rj)
            pre[b] = i_[k, LOT]
            _decide(k, TG[b], ST[b], O[b], ts, f, i_, gg, nn, U, P, fi, ff, pi, pf, rj)
        else:
            ts = T0[b] + HOUR
            _bar(k, O[b], H[b], L[b], C[b], SZ[b], ts, f, i_, gg, nn, U, P, fi, ff, pi, pf, rj)
            pre[b] = i_[k, LOT]
            _decide(k, TG[b], ST[b], C[b], ts, f, i_, gg, nn, U, P, fi, ff, pi, pf, rj)
''', "referee_kernel_gpu", "exec"), g)
    return g["kern"]


def simulate_many(pr: dict, inputs: list) -> list:
    """inputs = [(TG, ST, P)] -> senaryo başına ham çıktı sözlüğü (CPU çekirdeğiyle aynı alanlar) ya da taşma olursa None."""
    global _kern
    from numba import cuda
    _kern = _kern or _build()
    nb, K = len(pr["T0"]), len(pr["U"])
    sim_cap, rj_cap = int(min(max(4096, nb // 8), 60000)), 4096
    per = 16 * nb + sim_cap * 88 + rj_cap * 24 + K * 100
    B = int(max(1, min(512, cuda.current_context().get_memory_info()[0] * 0.55 // per)))
    shared = [cuda.to_device(pr[k]) for k in ("ev_k", "ev_b", "ev_kind", "T0", "O", "H", "L", "C", "SZ")]
    dU = cuda.to_device(pr["U"])
    groups: dict[int, list[int]] = {}
    for i, (TG, ST, _) in enumerate(inputs):
        groups.setdefault(hash((TG.tobytes(), ST.tobytes())), []).append(i)
    out = [None] * len(inputs)
    for idx in groups.values():
        TG, ST, _ = inputs[idx[0]]
        tg, st = cuda.to_device(TG), cuda.to_device(ST)
        for lo in range(0, len(idx), B):
            sel = idx[lo: lo + B]
            m = len(sel)
            bufs = dict(F=np.zeros((m, K, 9)), I=np.zeros((m, K, 5), np.int64), G=np.zeros((m, 1)), N=np.zeros((m, 3), np.int64), FI=np.zeros((m, sim_cap, 4), np.int64), FF=np.zeros((m, sim_cap, 3)),
                        PI=np.zeros((m, sim_cap, 3), np.int64), PF=np.zeros((m, sim_cap)), RJ=np.zeros((m, rj_cap, 3), np.int64), PRE=np.zeros((m, nb), np.int64), END=np.zeros((m, nb), np.int64))
            dv = {k: cuda.to_device(v) for k, v in bufs.items()}
            _kern[(m + 31) // 32, 32](*shared, tg, st, dU, cuda.to_device(np.stack([inputs[i][2] for i in sel])), *(dv[k] for k in ("F", "I", "G", "N", "FI", "FF", "PI", "PF", "RJ", "PRE", "END")))
            cuda.synchronize()
            host = {k: v.copy_to_host() for k, v in dv.items()}
            for j, i in enumerate(sel):
                if host["N"][j][0] >= 0:
                    out[i] = {k: v[j] for k, v in host.items()}
            del dv
    return out
