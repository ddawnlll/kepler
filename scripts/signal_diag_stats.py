"""Sinyal teşhisi: saf istatistik (reports/preregistration/signal_diagnostics.md). Girdiler [gün x sembol] dizileri (NaN = geçersiz hücre); Modal/Nautilus gerekmez.
IC-TS: sembol başına Spearman, n_s ağırlıklı havuz. IC-XS: tarih başına kesitsel Spearman, tarihler üzerinde ortalama. Güven aralığı: durağan blok bootstrap (tarihler; sıra-sonra-yeniden-örnekle: TAM-ÖRNEK sıraları sabit tutulur, replika içinde yeniden sıralanmaz;
bootstrap edilen estimator = sabit tam-örnek sıraların Pearson'ı, nokta tahmin = tam örnek Spearman. Replika-içi yeniden-sıra referansı ve uygunluk simülasyonu: scripts/null_calibration.py, #15),
her iki IC de "oran = toplamlar/toplamlar" olduğundan alt küme (alt dönem, rejim, uzlaşma kovası) hücre maskesiyle alan tahmini olarak aynı sayım matrisiyle bootstrap edilir."""
import numpy as np
import pandas as pd
from scipy.stats import norm, rankdata

HORIZONS = (1, 3, 5, 10, 20, 40)
MIN_N_TS = 250  # IC-TS: ön kayıt, sembol başına en az gün (alt küme analizlerinde 60)


def block_idx(T: int, B: int, mean_block: float, seed: int = 0) -> np.ndarray:
    """Durağan blok bootstrap: [B, T] örneklenen tarih indeksleri (Politis-Romano; yeni blok olasılığı 1/mean_block)."""
    rng = np.random.default_rng(seed)
    new, start = rng.random((B, T)) < 1.0 / mean_block, rng.integers(0, T, (B, T))
    idx = np.empty((B, T), dtype=np.int64)
    idx[:, 0] = start[:, 0]
    for t in range(1, T):
        idx[:, t] = np.where(new[:, t], start[:, t], (idx[:, t - 1] + 1) % T)
    return idx


def block_counts(T: int, B: int, mean_block: float, seed: int = 0) -> np.ndarray:
    """Durağan blok bootstrap: [B, T] tarih sayım matrisi (her satır bir yeniden örneklem, toplam T)."""
    idx = block_idx(T, B, mean_block, seed)
    flat = (idx + np.arange(B)[:, None] * T).ravel()
    return np.bincount(flat, minlength=B * T).reshape(B, T).astype(np.float64)


def _rank_cols(A: np.ndarray, valid: np.ndarray) -> np.ndarray:
    out = np.zeros(A.shape)
    for j in range(A.shape[1]):
        v = valid[:, j]
        if v.any():
            out[v, j] = rankdata(A[v, j])
    return out


def ts_stats(F: np.ndarray, Y: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """[T, S, 6] yeterli istatistikler (n, Σx, Σz, Σx², Σz², Σxz); x, z = sembol içi (alan içi) tam örneklem sıraları, ortalamadan merkezlenmiş (sayısal kararlılık)."""
    valid = np.isfinite(F) & np.isfinite(Y)
    if mask is not None:
        valid &= mask
    x, z = _rank_cols(F, valid), _rank_cols(Y, valid)
    n = valid.sum(0)
    mu = np.where(n > 0, (n + 1) / 2.0, 0.0)
    x, z = np.where(valid, x - mu, 0.0), np.where(valid, z - mu, 0.0)
    return np.stack([valid.astype(float), x, z, x * x, z * z, x * z], axis=2)


def _pool(sums: np.ndarray, elig: np.ndarray) -> np.ndarray:
    n, sx, sz, sxx, szz, sxz = (sums[..., k] for k in range(6))
    with np.errstate(divide="ignore", invalid="ignore"):
        rho = (sxz / n - (sx / n) * (sz / n)) / np.sqrt((sxx / n - (sx / n) ** 2) * (szz / n - (sz / n) ** 2))
    w = np.where(elig & np.isfinite(rho), n, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.nansum(np.where(w > 0, w * np.nan_to_num(rho), 0.0), axis=-1) / w.sum(axis=-1)


def ic_ts(F, Y, C: np.ndarray | None = None, mask=None, min_n: int = MIN_N_TS) -> tuple[float, np.ndarray | None]:
    """(nokta IC-TS, bootstrap dağılımı | None). C = block_counts çıktısı."""
    st = ts_stats(F, Y, mask)
    full = st.sum(0)
    elig = full[:, 0] >= min_n
    est = float(_pool(full, elig))
    if C is None:
        return est, None
    B, (T, S, _) = C.shape[0], st.shape
    boots = _pool((C @ st.reshape(T, S * 6)).reshape(B, S, 6), elig)
    return est, boots


def xs_series(F, Y, mask=None, min_cells: int = 8) -> np.ndarray:
    """Tarih başına kesitsel Spearman (NaN: < min_cells geçerli hücre ya da sabit)."""
    valid = np.isfinite(F) & np.isfinite(Y)
    if mask is not None:
        valid &= mask
    rf = pd.DataFrame(np.where(valid, F, np.nan)).rank(axis=1).to_numpy()
    ry = pd.DataFrame(np.where(valid, Y, np.nan)).rank(axis=1).to_numpy()
    n = valid.sum(1)
    mu = ((n + 1) / 2.0)[:, None]
    dx, dy = np.where(valid, rf - mu, 0.0), np.where(valid, ry - mu, 0.0)
    cov, vx, vy = (dx * dy).sum(1), (dx * dx).sum(1), (dy * dy).sum(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        ic = cov / np.sqrt(vx * vy)
    ic[(n < min_cells) | (vx <= 0) | (vy <= 0)] = np.nan
    return ic


def ic_xs(F, Y, C: np.ndarray | None = None, mask=None, min_cells: int = 8) -> tuple[float, np.ndarray | None, int]:
    """(nokta IC-XS, bootstrap dağılımı | None, geçerli tarih sayısı)."""
    s = xs_series(F, Y, mask, min_cells)
    ok = np.isfinite(s)
    est = float(s[ok].mean()) if ok.any() else float("nan")
    if C is None:
        return est, None, int(ok.sum())
    with np.errstate(divide="ignore", invalid="ignore"):
        boots = (C @ np.where(ok, s, 0.0)) / (C @ ok.astype(float))
    return est, boots, int(ok.sum())


def summarize(theta: float, boots: np.ndarray | None, z_corr: float | None = None) -> dict:
    """Nokta tahmin + bootstrap SE → z, iki yönlü normal p, %95 yüzdelik AA; z_corr verilirse düzeltilmiş (Bonferroni) AA.
    UYARI (#15, scripts/null_calibration.py): kalıcı tahmin + örtüşen etiket altında bu p anti-muhafazakârdır (sıfır-edge sentetikte nominal 0,05 yerine ≈0,09–0,27); sertifika değil, betimsel ölçüdür."""
    if boots is None:
        return dict(ic=theta)
    b = boots[np.isfinite(boots)]
    if b.size < 2:  # alt kümede geçerli hücre yok
        return dict(ic=theta, se=float("nan"), z=float("nan"), p=float("nan"), lo=float("nan"), hi=float("nan"))
    se = float(b.std(ddof=1)) if len(b) > 1 else float("nan")
    z = theta / se if se and np.isfinite(se) and se > 0 else float("nan")
    out = dict(ic=theta, se=se, z=z, p=float(2 * norm.sf(abs(z))) if np.isfinite(z) else float("nan"),
               lo=float(np.percentile(b, 2.5)), hi=float(np.percentile(b, 97.5)))
    if z_corr is not None:
        out.update(lo_c=theta - z_corr * se, hi_c=theta + z_corr * se)
    return out


def holm(p: np.ndarray) -> np.ndarray:
    """Holm-Bonferroni düzeltilmiş p (FWER); NaN p korunur (aileden çıkar)."""
    p = np.asarray(p, float)
    out = np.full(p.shape, np.nan)
    ok = np.flatnonzero(np.isfinite(p))
    order = ok[np.argsort(p[ok])]
    m, run = len(order), 0.0
    for i, j in enumerate(order):
        run = max(run, min(1.0, (m - i) * p[j]))
        out[j] = run
    return out


def bh(p: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg düzeltilmiş p (q-değeri)."""
    p = np.asarray(p, float)
    out = np.full(p.shape, np.nan)
    ok = np.flatnonzero(np.isfinite(p))
    order = ok[np.argsort(p[ok])]
    m = len(order)
    q = np.minimum.accumulate((p[order] * m / (np.arange(m) + 1))[::-1])[::-1]
    out[order] = np.minimum(q, 1.0)
    return out


def buckets(F: np.ndarray, valid: np.ndarray, nb: int = 5) -> tuple[np.ndarray, int]:
    """Hücre havuzlu eşit sayılı kovalar (qcut, duplicates=drop); kova kimliği [T, S] (-1 = geçersiz), kova sayısı."""
    out = np.full(F.shape, -1, dtype=np.int64)
    v = np.asarray(F)[valid]
    if v.size == 0 or np.unique(v).size < 2:
        return out, 0
    codes = pd.qcut(pd.Series(v), nb, labels=False, duplicates="drop").to_numpy()
    out[valid] = codes
    return out, int(codes.max()) + 1


def bucket_means(V: np.ndarray, bid: np.ndarray, nb: int, C: np.ndarray | None = None) -> dict:
    """Kova başına ortalama V (hücre havuzlu); bootstrap ile kova ortalamaları ve (en yüksek − en düşük kova) farkı."""
    T = V.shape[0]
    sums, cnts = np.zeros((T, nb)), np.zeros((T, nb))
    for b in range(nb):
        m = bid == b
        sums[:, b], cnts[:, b] = np.where(m, V, 0.0).sum(1), m.sum(1)
    mean = sums.sum(0) / np.maximum(cnts.sum(0), 1)
    out = dict(mean=mean.tolist(), n=cnts.sum(0).astype(int).tolist(), diff=float(mean[-1] - mean[0]) if nb > 1 else float("nan"),
               monotone=bool(np.all(np.diff(mean) > 0)) if nb > 1 else False)
    if C is not None and nb > 1:
        with np.errstate(divide="ignore", invalid="ignore"):
            bm = (C @ sums) / (C @ cnts)
        d = bm[:, -1] - bm[:, 0]
        d = d[np.isfinite(d)]
        if d.size > 1:
            out.update(diff_lo=float(np.percentile(d, 2.5)), diff_hi=float(np.percentile(d, 97.5)), diff_se=float(d.std(ddof=1)))
    return out


def cell_spearman(A: dict[str, np.ndarray], valid: np.ndarray) -> pd.DataFrame:
    """Uzman tahminleri arasında hücre havuzlu Spearman (geçerli hücrelerde, NaN → 0; ensemble'ın gördüğü hâl)."""
    names = list(A)
    R = pd.DataFrame({k: rankdata(np.nan_to_num(A[k][valid])) for k in names})
    return R.corr()


def daily_xs_corr(A: dict[str, np.ndarray], valid: np.ndarray, min_cells: int = 8) -> pd.DataFrame:
    """Günlük kesitsel Spearman'ın tarihler üzerinde ortalaması (uzman çiftleri)."""
    names = list(A)
    R = {k: pd.DataFrame(np.where(valid, np.nan_to_num(A[k]), np.nan)).rank(axis=1).to_numpy() for k in names}
    n = valid.sum(1)
    mu = ((n + 1) / 2.0)[:, None]
    D = {k: np.where(valid, R[k] - mu, 0.0) for k in names}
    out = pd.DataFrame(np.eye(len(names)), index=names, columns=names)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            cov, va, vb = (D[a] * D[b]).sum(1), (D[a] ** 2).sum(1), (D[b] ** 2).sum(1)
            with np.errstate(divide="ignore", invalid="ignore"):
                r = cov / np.sqrt(va * vb)
            r[(n < min_cells) | (va <= 0) | (vb <= 0)] = np.nan
            out.loc[a, b] = out.loc[b, a] = float(np.nanmean(r)) if np.isfinite(r).any() else float("nan")
    return out


def cluster(corr: pd.DataFrame, cut: float = 0.5) -> dict[str, int]:
    """Ortalama bağlantı, mesafe 1 − |ρ|, mesafe ≤ cut ile kes → {uzman: küme no} (1'den)."""
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform
    d = 1.0 - corr.fillna(0.0).abs().to_numpy()  # sabit tahmin (korelasyon tanımsız) → ilişkisiz sayılır, kendi kümesi
    np.fill_diagonal(d, 0.0)
    lab = fcluster(linkage(squareform(np.clip(d, 0, None), checks=False), "average"), t=cut, criterion="distance")
    return dict(zip(corr.index, lab.tolist()))
