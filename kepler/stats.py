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
