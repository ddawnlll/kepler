"""#14: çoklu test politikası araçları (kepler/ dışı; ledger sözleşmesi `kepler/ledger.py::check_family_meta`). Yeni dar deneyden ÖNCE koşulur."""
import numpy as np
import pandas as pd

FAMILY_KEYS = ("hypothesis_id", "parent_hypothesis", "selection_family", "control_role", "run_id", "attempt")
CONTROL_ROLES = ("primary", "secondary", "negative_control", "neutral_null", "exploratory")
MT_METHODS = ("bonferroni", "holm", "single")
PREREG_KEYS = ("main_hypothesis", "max_variants", "primary_metric", "multiple_testing", "alpha", "B", "power_note", "cost_note", "stopping_rule", "registered_commit")


def check_family_meta(meta: dict) -> dict:
    """Ledger/önkayıt sözleşmesi (run/attempt hipotezden ayrı): FAMILY_KEYS; `ledger.record(family=check_family_meta(...))`."""
    if any(k not in meta for k in FAMILY_KEYS) or meta["control_role"] not in CONTROL_ROLES or not isinstance(meta["attempt"], int) or meta["attempt"] < 1:
        raise ValueError(f"aile meta'sı geçersiz: {FAMILY_KEYS}; control_role {CONTROL_ROLES}; attempt >= 1")
    return {k: meta[k] for k in FAMILY_KEYS}


def min_B(alpha: float, m: int = 1) -> int:
    """Bonferroni eşiğine (alpha/m) ulaşmak için asgari B: 1/(B+1) <= alpha/m. YALNIZ çözünürlük sınırı; güç/null geçerliliği kanıtı değil."""
    return int(np.ceil(m / alpha) - 1)


def check_resolution(B: int, alpha: float, m: int = 1) -> None:
    """Koşudan ÖNCE: ulaşılamaz p çözünürlüğünü (en küçük p = 1/(B+1)) yakalar; çözüm devasa fan-out değil, aileyi küçültmek/tasarımı değiştirmek."""
    if 1 / (B + 1) > alpha / m:
        raise ValueError(f"B={B}: en küçük p {1 / (B + 1):.6f} > alpha/m = {alpha / m:.6f} (m={m}); asgari B={min_B(alpha, m)} (yalnız çözünürlük). Aileyi küçült")


def check_prereg(d: dict) -> str:
    """Sonuç görülmeden sabitlenen dar-deney planını doğrular (alanlar PREREG_KEYS; registered_commit = planın kaydedildiği commit) ve çözünürlüğü kontrol eder. Dönüş: plan hash'i."""
    import hashlib
    import json
    if miss := [k for k in PREREG_KEYS if d.get(k) in (None, "", 0)]:
        raise ValueError(f"önkayıt eksik alan: {miss}")
    if d["multiple_testing"] not in MT_METHODS or int(d["max_variants"]) < 1:
        raise ValueError(f"multiple_testing {MT_METHODS} içinden, max_variants >= 1 olmalı")
    check_resolution(int(d["B"]), float(d["alpha"]), 1 if d["multiple_testing"] == "single" else int(d["max_variants"]))
    return hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()


def family_report(R: pd.DataFrame) -> dict:
    """Karşılaştırılabilir aile (sütun = deneme, satır = ortak takvim günü): Sharpe dağılımı ve deneme bağımlılığı. n_eff_info = (Σλ)²/Σλ² YALNIZ bilgi, dsr eşiğini ayarlamaz."""
    if R.isna().any().any() or not (R.index.is_monotonic_increasing and R.index.is_unique) or R.shape[1] < 2:
        raise ValueError("aile: ortak, NaN'sız, artan tekil takvim ve >= 2 deneme gerekir")
    sr, C = R.mean() / R.std(ddof=1), R.corr().to_numpy()
    lam = np.clip(np.linalg.eigvalsh(C), 0, None)
    return dict(n_raw=R.shape[1], n_days=len(R), sr_mean=float(sr.mean()), sr_var=float(sr.var(ddof=1)), mean_pair_corr=float(C[np.triu_indices(len(C), 1)].mean()), n_eff_info=float(lam.sum() ** 2 / (lam**2).sum()))
