"""#15: rotasyon null maruziyet teşhisi, bootstrap estimator uygunluğu ve yanlış-pozitif kalibrasyonu (küçük sentetik; tam koşu scripts/null_calibration.py)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import null_calibration as nc  # noqa: E402
import signal_diag_stats as sx  # noqa: E402


def e07_panel(T=40, S=4, late_from=10):
    f = np.zeros((T, S))
    f = np.where((g := np.sin(np.arange(T))[:, None] + 0.1 * np.arange(S) + 0.05) >= 0, 1.0, -1.0)  # her hücrede sıfır olmayan tahmin
    act = np.ones((T, S), bool)
    act[:late_from, 3] = False  # sonradan aktif olan sembol
    f[~act] = 0.0
    return f, act


def test_rotation_with_late_active_symbol_loses_active_nonzero_cells():
    f, act = e07_panel()
    real = nc.exposure_diag(f, act)
    rot = nc.exposure_diag(f, act, k=17)
    assert real["active_nonzero_cells"] == int(act.sum()) and rot["active_cells"] == real["active_cells"]
    assert rot["active_nonzero_cells"] < real["active_nonzero_cells"]  # E07: sıfır dolu dönemler aktif hücrelere kayıyor (dolum sayısı değil, maruziyet korunumu ihlali göstergesi)
    assert set(real) >= {"gross_mean", "net_mean", "n_changes", "mean_hold_days", "dow_gross"}
    assert nc.exposure_diag(f, np.ones_like(act), k=17)["active_nonzero_cells"] == (f != 0).sum()  # tam aktif panelde korunur


def test_rerank_reference_equals_point_estimate_on_identity_resample():
    rng = np.random.default_rng(0)
    F, Y = rng.normal(size=(200, 5)), rng.normal(size=(200, 5))
    est = sx.ic_ts(F, Y, None, min_n=10)[0]
    assert nc.ic_ts_rerank(F, Y, np.arange(200)[None, :], 10)[0] == pytest.approx(est, abs=1e-12)  # tanım: tam örnek Spearman


def test_fixed_rank_vs_rerank_same_replicas_close_but_not_identical():
    r = nc.estimator_check(seed=0, B=120)
    assert r["max_abs_diff"] > 0 and r["corr_replicas"] > 0.95  # E08: değerler farklı, dağılımlar yakın
    assert r["se_fixed"] == pytest.approx(r["se_rerank"], rel=0.25)


def test_false_positive_report_has_ci_and_flags_dependence():
    iid = nc.fp_rate(250, 5, 1, 0.0, 1.0001, reps=60, B=100)
    dep = nc.fp_rate(250, 5, 40, 0.9, 5, reps=60, B=100)
    assert iid["lo"] <= iid["fp"] <= iid["hi"] and iid["fp"] <= 0.2  # bağımsız sıfır-edge: nominale yakın
    assert dep["fp"] > iid["fp"]  # kalıcı tahmin + örtüşen etiket: anti-muhafazakâr


def test_selection_null_conditional_is_inflated_vs_procedure():
    r = nc.selection_null(reps=40, K=9, T=300, S=6, B=40)
    assert r["conditional_fp"] > r["procedure_fp"] and r["procedure_fp"] <= 0.15


def test_wilson_interval():
    lo, hi = nc._wilson(5, 100)
    assert 0.02 < lo < 0.05 < hi < 0.12
