"""Nested walk-forward (BACKTEST.md §8.2). R: (gün x yapılandırma) günlük getiri DataFrame (PnL / sermaye; gün indeksi tz'siz). Dış döngü anchored/genişleyen:
eğitim [train_lo, T), OOS [T, bitiş); iç döngü: eğitim ardışık yarıyıllara bölünür, seçim ölçütü = yarıyıl skorlarının (varsayılan günlük Sharpe) MEDYANI, eşitlikte ilk sütun."""
import numpy as np
import pandas as pd

FOLDS = [("2024-01-01", "2024-07-01"), ("2024-07-01", "2025-01-01"), ("2025-01-01", "2025-07-01"), ("2025-07-01", "2026-01-01"), ("2026-01-01", "2026-04-01")]


def sharpe(x) -> float:
    """Günlük Sharpe (ort/std, ddof=1); std = 0 ya da < 2 gözlem -> 0."""
    x = np.asarray(x, float)
    sd = x.std(ddof=1) if len(x) > 1 else 0.0
    return float(x.mean() / sd) if sd > 1e-15 else 0.0


def half_years(lo, hi) -> list[tuple]:
    """[lo, hi) aralığını ardışık yarıyıllara (lo'dan başlayarak 6'şar ay) böler; son parça hi'da kesilir."""
    lo, hi, out = pd.Timestamp(lo), pd.Timestamp(hi), []
    while lo < hi:
        nxt = min(lo + pd.DateOffset(months=6), hi)
        out.append((lo, nxt))
        lo = nxt
    return out


def select(R: pd.DataFrame, lo, hi, score=sharpe) -> tuple[str, pd.Series]:
    """İç döngü: her yapılandırmanın [lo, hi) yarıyıl skorlarının medyanı; (seçilen, medyan skorlar)."""
    med = pd.Series({c: float(np.median([score(R[c][(R.index >= a) & (R.index < b)].to_numpy()) for a, b in half_years(lo, hi)])) for c in R.columns})
    return med.idxmax(), med


def run(R: pd.DataFrame, folds=FOLDS, train_lo="2022-01-01", score=sharpe) -> dict:
    """Her dış adımda seçimi yeniden yap. steps: T, oos (başlangıç, bitiş), pick, score (iç medyan), oos_total (seçilenin OOS toplam getirisi), pct (88 içinde seçilenin yendiği pay, eşitlik yarım);
    oos: birleşik OOS günlük serisi (seçilenlerden)."""
    steps, parts = [], []
    for a, b in folds:
        pick, med = select(R, train_lo, a, score)
        w = R[(R.index >= a) & (R.index < b)]
        tot = w.sum()
        steps.append(dict(T=a, oos=(a, b), pick=pick, score=float(med[pick]), oos_total=float(tot[pick]), pct=float(((tot < tot[pick]).sum() + 0.5 * ((tot == tot[pick]).sum() - 1)) / (len(tot) - 1)) if len(tot) > 1 else 0.5))
        parts.append(w[pick])
    return dict(steps=steps, oos=pd.concat(parts))


def random_sharpes(R: pd.DataFrame, folds=FOLDS, B: int = 5000, seed: int = 0) -> np.ndarray:
    """Rastgele seçim: her adımda yapılandırmalardan eşit olasılıkla biri, B çekiliş; birleşik OOS günlük Sharpe'ı (yıllıklandırılmamış) dizisi (B,)."""
    rng = np.random.default_rng(seed)
    cols = [R[(R.index >= a) & (R.index < b)].to_numpy()[:, rng.integers(0, R.shape[1], B)] for a, b in folds]
    x = np.concatenate(cols, axis=0)
    sd = x.std(axis=0, ddof=1)
    return np.where(sd > 1e-15, x.mean(axis=0) / np.where(sd > 1e-15, sd, 1.0), 0.0)
