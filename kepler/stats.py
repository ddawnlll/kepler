"""Değerlendirme istatistikleri (BACKTEST.md §9): PSR / DSR / MinTRL, rotasyon-null p, Bonferroni, stationary block bootstrap, Newey–West alfa.
Getiri serileri GÜNLÜK ve sermayeye oranlı (PnL / sermaye, toplamsal: sabit sermaye, bileşik yok); Sharpe günlük hesaplanır, yıllık = x sqrt(365)."""
import numpy as np
import pandas as pd
from scipy.stats import norm

EULER = 0.5772156649015329


def annual(sr_daily: float) -> float:
    return float(sr_daily * np.sqrt(365))


def moments(r) -> tuple[float, float, float, int]:
    """(günlük Sharpe, çarpıklık g3, basıklık g4 [normalde 3], T). Sharpe = ort/std (ddof=1); g3/g4 ddof=0 momentleriyle (scripts/g2_report.py ile aynı)."""
    r = np.asarray(r, float)
    m, sd = r.mean(), r.std(ddof=0)
    return float(m / r.std(ddof=1)), float(((r - m) ** 3).mean() / sd**3), float(((r - m) ** 4).mean() / sd**4), len(r)


def psr(r, sr0: float = 0.0) -> float:
    """Probabilistic Sharpe Ratio: P(gerçek SR > sr0). sr0 günlük. Φ((SR − SR0)·√(T−1) / √(1 − g3·SR + (g4−1)/4·SR²))."""
    sr, g3, g4, t = moments(r)
    return float(norm.cdf((sr - sr0) * np.sqrt(t - 1) / np.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr**2)))


def sr0_from_trials(trial_srs) -> float:
    """Beklenen en iyi SR (N deneme, hepsinde gerçek SR = 0): std(denemelerin SR'leri) × [(1−γ)Φ⁻¹(1−1/N) + γΦ⁻¹(1−1/(N·e))]."""
    n = len(trial_srs)
    return float(np.std(trial_srs, ddof=1) * ((1 - EULER) * norm.ppf(1 - 1 / n) + EULER * norm.ppf(1 - 1 / (n * np.e))))


def dsr(r, trial_srs) -> float:
    """Deflated Sharpe Ratio = PSR(SR0 = sr0_from_trials). trial_srs: aynı testteki TÜM denemelerin günlük Sharpe'ları (N = uzunluğu)."""
    return psr(r, sr0_from_trials(trial_srs))


def min_trl(sr: float, g3: float = 0.0, g4: float = 3.0, sr_star: float = 0.0, alpha: float = 0.05) -> float:
    """Minimum Track Record Length (gözlem sayısı, sr ile aynı periyot): 1 + (1 − g3·SR + (g4−1)/4·SR²)·(z_α/(SR − SR*))²."""
    return float(1 + (1 - g3 * sr + (g4 - 1) / 4 * sr**2) * (norm.ppf(1 - alpha) / (sr - sr_star)) ** 2)


def rotation_p(real: float, null) -> float:
    """Tek yönlü: (1 + #{null ≥ gerçek}) / (B + 1)."""
    return float((1 + (np.asarray(null) >= real).sum()) / (len(null) + 1))


def bonferroni(p: float, n: int) -> float:
    return float(min(1.0, p * n))


def stationary_bootstrap(n: int, mean_block: float = 20.0, B: int = 2000, seed: int = 0) -> np.ndarray:
    """Politis–Romano: (B, n) indeks matrisi. İlk indeks rastgele; sonra olasılık 1/mean_block ile yeni rastgele başlangıç, aksi halde önceki + 1 (mod n)."""
    rng = np.random.default_rng(seed)
    new, start = rng.random((B, n)) < 1 / mean_block, rng.integers(0, n, (B, n))
    new[:, 0] = True
    idx = np.empty((B, n), int)
    for t in range(n):
        idx[:, t] = np.where(new[:, t], start[:, t], (idx[:, t - 1] + 1) % n) if t else start[:, 0]
    return idx


def max_drawdown(r) -> np.ndarray:
    """Toplamsal equity (sermaye = 1): tepe − equity'nin en büyüğü (başlangıç 0 dahil). r: (..., T) -> (...)."""
    eq = np.cumsum(np.asarray(r, float), axis=-1)
    return (np.maximum.accumulate(np.concatenate([np.zeros(eq.shape[:-1] + (1,)), eq], axis=-1), axis=-1)[..., 1:] - eq).max(axis=-1)


def bootstrap_summary(r, mean_block: float = 20.0, B: int = 2000, seed: int = 0) -> dict:
    """Günlük net getiri r -> yıllık Sharpe %5/%50/%95, maks DD %50/%95, toplam getiri %5/%50/%95 (K4)."""
    r = np.asarray(r, float)
    x = r[stationary_bootstrap(len(r), mean_block, B, seed)]
    sh, dd, tot = x.mean(axis=1) / x.std(axis=1, ddof=1) * np.sqrt(365), max_drawdown(x), x.sum(axis=1)
    q = lambda v, ps: [float(np.quantile(v, p)) for p in ps]  # noqa: E731
    return dict(sharpe=q(sh, (.05, .5, .95)), maxdd=q(dd, (.5, .95)), total=q(tot, (.05, .5, .95)), mean_block=mean_block, B=B, seed=seed)


def nw_alpha(rs, rb, lag: int = 5) -> tuple[float, float, float]:
    """r_s = a + b·r_b + e (OLS); a'nın t istatistiği Newey–West (Bartlett ağırlıkları 1 − l/(lag+1)). (a, b, t_a)."""
    X, y = np.column_stack([np.ones(len(rs)), np.asarray(rb, float)]), np.asarray(rs, float)
    bread = np.linalg.inv(X.T @ X)
    beta = bread @ X.T @ y
    u = X * (y - X @ beta)[:, None]  # x_t e_t
    S = u.T @ u
    for k in range(1, lag + 1):
        G = u[k:].T @ u[:-k]
        S += (1 - k / (lag + 1)) * (G + G.T)
    cov = bread @ S @ bread
    return float(beta[0]), float(beta[1]), float(beta[0] / np.sqrt(cov[0, 0]))


def sharpe_series(pnl_daily: pd.Series, capital: float, warmup_days: int = 0) -> pd.Series:
    """Günlük PnL -> getiri (PnL / sermaye); ilk `warmup_days` gün (ısınma: sıfır PnL'li işlemsiz günler) dışlanır, DSR/Sharpe bozulmasın (§8.1)."""
    return (pnl_daily / capital).iloc[warmup_days:]


def path_stats(r) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """İşlem getiri yolları (B, T) -> (maks DD [toplamsal, tepe başlangıç dahil], en uzun ardışık zarar serisi [adet], en kötü ardışık zarar toplamı [pozitif sayı])."""
    r = np.atleast_2d(np.asarray(r, float))
    run, run_sum, best, worst = (np.zeros(len(r)) for _ in range(4))
    for t in range(r.shape[1]):
        neg = r[:, t] < 0
        run, run_sum = np.where(neg, run + 1, 0), np.where(neg, run_sum + r[:, t], 0)
        best, worst = np.maximum(best, run), np.minimum(worst, run_sum)
    return max_drawdown(r), best, -worst


def trade_mc(nets, B: int = 5000, seed: int = 0) -> np.ndarray:
    """İşlem sırası Monte Carlo: işlem net getirilerini (sermayeye oranlı) B kez permüte eder -> yollar (B, T); DD/seri için path_stats(yollar), kill_stats(yollar, eşik)."""
    x = np.asarray(nets, float)
    return x[np.argsort(np.random.default_rng(seed).random((B, len(x))), axis=1)]


def kill_stats(r, thr: float) -> dict:
    """Yollar r (B, T) (toplamsal getiri, sermayeye oranlı): DD (tepe başlangıç 0 dahil) thr'yi aşınca yol kesilir. p_trip, kesmeli/kesmesiz ortalama final."""
    eq = np.cumsum(np.asarray(r, float), axis=1)
    hit = (np.maximum(np.maximum.accumulate(eq, axis=1), 0) - eq) > thr
    idx = hit.argmax(axis=1)
    final = np.where(hit.any(axis=1), eq[np.arange(len(eq)), idx], eq[:, -1])
    return dict(p_trip=float(hit.any(axis=1).mean()), mean_final=float(final.mean()), mean_final_nokill=float(eq[:, -1].mean()))


def cscv(R, S: int = 16, metric: str = "sharpe") -> dict:
    """PBO / CSCV (Bailey, Borwein, López de Prado, Zhu). R: (T, N) günlük getiri, N yapılandırma. S ardışık blok (np.array_split), tüm C(S, S/2) bölme: IS-en-iyi (eşitlikte ilk) →
    OOS sırası (artan, eşitlikte ortalama) ω = sıra/(N+1), λ = ln(ω/(1−ω)); PBO = P(λ ≤ 0). metric: 'sharpe' (std = 0 → 0) | 'mean'. Dönüş: pbo, lam, loss (P(IS-en-iyinin OOS ort. getirisi < 0)), n_splits."""
    import itertools
    R = np.asarray(R, float)
    blocks = np.array_split(np.arange(len(R)), S)
    n, s1, s2 = np.array([len(b) for b in blocks]), np.array([R[b].sum(0) for b in blocks]), np.array([(R[b] ** 2).sum(0) for b in blocks])
    mean = lambda i: s1[i].sum(0) / n[i].sum()  # noqa: E731
    def perf(i):
        m = mean(i)
        if metric == "mean":
            return m
        sd = np.sqrt(np.maximum(s2[i].sum(0) / n[i].sum() - m**2, 0))
        return np.where(sd > 1e-12, m / np.where(sd > 1e-12, sd, 1), 0.0)
    lam, loss = [], []
    for c in itertools.combinations(range(S), S // 2):
        i, o = np.array(c), np.setdiff1d(np.arange(S), c)
        k, po = int(np.argmax(perf(i))), perf(o)
        rank = (po < po[k]).sum() + ((po == po[k]).sum() + 1) / 2
        w = rank / (R.shape[1] + 1)
        lam.append(np.log(w / (1 - w)))
        loss.append(mean(o)[k] < 0)
    lam = np.array(lam)
    return dict(pbo=float((lam <= 0).mean()), lam=lam, lam_median=float(np.median(lam)), loss=float(np.mean(loss)), n_splits=len(lam))


def nw_lrv(x, lag: int) -> np.ndarray:
    """Sütun başına Newey–West (Bartlett) uzun dönem varyansı, ortalamadan sapmalarla, 1/n normalizasyonu. lag = 0: ddof=0 varyans."""
    u = np.asarray(x, float) - np.mean(x, axis=0)
    n, v = len(u), (u * u).sum(0) / len(u)
    for k in range(1, lag + 1):
        v = v + 2 * (1 - k / (lag + 1)) * (u[k:] * u[:-k]).sum(0) / n
    return v


def spa(d, mean_block: float = 20.0, B: int = 2000, seed: int = 0, lag: int = 20) -> dict:
    """Superior Predictive Ability (Hansen 2005). d: (n, K) performans farkı (model − benchmark; pozitif = model daha iyi). T = max(max_k √n d̄_k/ω̂_k, 0), ω̂ = Newey–West std;
    stationary bootstrap altında T* = max(max_k √n (d̄*_k − d̄_k + g_k)/ω̂_k, 0), g: lower min(d̄,0) · consistent d̄·1{√n d̄/ω̂ ≤ −√(2 ln ln n)} · upper 0 (= Reality Check).
    Aynı bootstrap yollarında g_l ≤ g_c ≤ g_u olduğundan p_lower ≤ p_consistent ≤ p_upper. Sabit sütunlar (ω̂ = 0) t = 0 sayılır."""
    d = np.asarray(d, float)
    n, K = d.shape
    dbar, om = d.mean(0), np.sqrt(nw_lrv(d, lag))
    ok = om > 0
    sc = np.where(ok, om, 1.0)
    t = np.where(ok, np.sqrt(n) * dbar / sc, 0.0)
    stat = max(float(t.max()), 0.0)
    thr = np.sqrt(2 * np.log(np.log(n)))
    g = dict(lower=np.minimum(dbar, 0), consistent=np.where(t <= -thr, dbar, 0.0), upper=np.zeros(K))
    idx, tstar = stationary_bootstrap(n, mean_block, B, seed), {k: [] for k in g}
    for c in range(0, B, 100):
        dstar = d[idx[c:c + 100]].mean(1) - dbar  # (b, K)
        for k, gk in g.items():
            tstar[k].append(np.maximum(np.where(ok, np.sqrt(n) * (dstar + gk) / sc, 0.0).max(axis=1), 0.0))
    p = {k: float((np.concatenate(v) >= stat).mean()) for k, v in tstar.items()}
    return dict(stat=stat, best=int(np.argmax(t)), t=t, p_lower=p["lower"], p_consistent=p["consistent"], p_upper=p["upper"], n=n, K=K)
