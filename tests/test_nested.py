"""Nested walk-forward aracı (BACKTEST §8.2). Beklenen değerler elle."""
import numpy as np
import pandas as pd
import pytest

from kepler import nested

A = pytest.approx


def test_sharpe_and_half_years_hand_values():
    assert nested.sharpe([1, 2, 3, 4]) == A(2.5 / np.sqrt(5 / 3))  # ort 2,5; ddof=1 varyans = 5/3
    assert nested.sharpe([0.1, 0.1, 0.1]) == 0.0 and nested.sharpe([1.0]) == 0.0
    hy = nested.half_years("2022-01-01", "2023-03-01")
    assert [(a.strftime("%Y-%m-%d"), b.strftime("%Y-%m-%d")) for a, b in hy] == [("2022-01-01", "2022-07-01"), ("2022-07-01", "2023-01-01"), ("2023-01-01", "2023-03-01")]


def frame(cols: dict, lo="2022-01-01", hi="2023-07-01"):
    idx = pd.date_range(lo, hi, freq="1D", inclusive="left")
    d = {}
    for name, per in cols.items():  # per: (2022-H1, 2022-H2, 2023-H1) sabit günlük getiri
        d[name] = np.select([idx < "2022-07-01", idx < "2023-01-01"], [per[0], per[1]], per[2])
    return pd.DataFrame(d, index=idx)


def test_select_uses_median_of_half_years_not_mean_and_ties_go_to_first():
    R = frame({"A": (0.01, 0.01, -0.1), "B": (0.004, 0.004, 0.004), "C": (0.0, 0.0, 0.0)})
    # eğitim [2022-01-01, 2023-07-01): 3 yarıyıl. skor = yarıyıl ortalaması (sabit getiride Sharpe 0 olurdu). A: (0,01; 0,01; -0,1) medyan 0,01 (ortalama -0,0267);
    # B: medyan 0,004; C: 0 -> medyan A'yı seçer (ortalama B'yi seçerdi)
    pick, med = nested.select(R, "2022-01-01", "2023-07-01", score=lambda x: float(np.mean(x)))
    assert pick == "A" and med["A"] == A(0.01) and med["B"] == A(0.004) and med["C"] == 0.0
    # varsayılan Sharpe: sabit getiride std = 0 -> hepsi 0 -> eşitlikte ilk sütun
    assert nested.select(R, "2022-01-01", "2023-07-01")[0] == "A" and nested.select(R[["C", "B"]], "2022-01-01", "2023-07-01")[0] == "C"


def test_run_scores_pick_out_of_sample_only_and_percentile():
    R = frame({"A": (0.01, 0.01, -0.001), "B": (0.004, 0.004, 0.002), "C": (0.0, 0.0, 0.0)}, hi="2023-07-01")
    out = nested.run(R, folds=[("2023-01-01", "2023-07-01")], score=lambda x: float(np.mean(x)))
    s = out["steps"][0]
    # eğitim [2022-01-01, 2023-01-01): 2 yarıyıl; A medyan (0,01+0,01)/2 = 0,01 -> A seçilir. OOS 181 gün (2023-01-01..2023-06-30): A toplam -0,181, B +0,362, C 0
    assert s["pick"] == "A" and s["score"] == A(0.01) and s["oos_total"] == A(-0.001 * 181) and s["pct"] == 0.0  # 3 yapılandırmanın en kötüsü: yendiği pay 0/2
    assert len(out["oos"]) == 181 and out["oos"].sum() == A(-0.181)
    # OOS getirisi eğitim seçimini değiştirmez: OOS'u bozunca seçilen aynı
    R2 = R.copy()
    R2.loc["2023-01-01":, "B"] = 9.9
    assert nested.run(R2, folds=[("2023-01-01", "2023-07-01")], score=lambda x: float(np.mean(x)))["steps"][0]["pick"] == "A"


def test_random_sharpes_is_seeded_and_single_config_equals_procedure():
    R = frame({"A": (0.0, 0.0, 0.0)})
    R["A"] = np.tile([0.01, -0.005, 0.02], len(R))[: len(R)]
    r = nested.random_sharpes(R, folds=[("2023-01-01", "2023-07-01")], B=5, seed=3)
    w = R[(R.index >= "2023-01-01") & (R.index < "2023-07-01")]["A"].to_numpy()
    assert np.allclose(r, nested.sharpe(w)) and (nested.random_sharpes(R, [("2023-01-01", "2023-07-01")], 5, 3) == r).all()
    R3 = pd.concat([R, R * 2, -R], axis=1)
    R3.columns = list("ABC")
    a, b = nested.random_sharpes(R3, [("2023-01-01", "2023-07-01")], 50, 1), nested.random_sharpes(R3, [("2023-01-01", "2023-07-01")], 50, 2)
    assert set(np.round(a, 9)) <= {round(nested.sharpe(w), 9), round(-nested.sharpe(w), 9)} and not (a == b).all()  # 2R ve R aynı Sharpe, -R ters işaret
