"""İmaj build adımı: hakem çekirdeğini çalışma zamanındakiyle AYNI tiplerle bir kez çalıştırıp numba önbelleğini imaja yazar (NUMBA_CACHE_DIR). Çalışma zamanı derlemesi ~10-16 sn -> yükleme."""
import numpy as np

from kepler import referee_core as c

n, cap, K = 64, 4096, 2
T0 = np.arange(n, dtype=np.int64) * c.HOUR
ev_t = np.r_[T0, T0 + c.HOUR - 1]
b = np.r_[np.arange(n), np.arange(n)].astype(np.int64)
order = np.lexsort((np.zeros(2 * n), ev_t))
px = np.full(n, 100.0)
for kind_mode in (0, 1):  # next_open (A/B olayları) ve close
    ev_kind = (np.r_[np.zeros(n, np.int8), np.ones(n, np.int8)] if kind_mode == 0 else np.full(2 * n, c.KIND_CLOSE, np.int8))[order]
    P = np.array([6e-4, 10, 0.005, 1.0, 5.0, 1000.0, 0.0, 0.0, float(kind_mode)])
    c.simulate(np.zeros(2 * n, np.int64), b[order], ev_kind, T0, px, px, px, px, np.full((n, 4), 1000, np.int64), np.r_[np.nan, np.full(n - 1, 500.0)], np.full(n, np.nan), np.array([[1000.0, 100.0, 0.01]] * K), P, cap,
               np.zeros(0, np.int64), np.zeros(0, np.int64), np.zeros(0), np.zeros(0), np.zeros((cap, 4), np.int64), np.zeros((cap, 3)), np.zeros((cap, 3), np.int64), np.zeros(cap), np.zeros((cap, 3), np.int64), np.zeros((cap, 3), np.int64), np.zeros((cap, 5)))
print("numba önbelleği ısıtıldı")
