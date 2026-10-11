"""#14: çoklu test politikası: p çözünürlüğü, aile meta'sı, önkayıt, ortak takvimli aile raporu."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import trial_policy as tp  # noqa: E402

from kepler import ledger  # noqa: E402

PRE = dict(main_hypothesis="H1", max_variants=3, primary_metric="net_sharpe", multiple_testing="bonferroni", alpha=0.05, B=2000, power_note="n", cost_note="fee10+slip2",
           stopping_rule="B tamam", registered_commit="abc123")


def test_issue_numbers_resolution():
    assert tp.min_B(0.05, 1) == 19 and tp.min_B(0.05, 108) == 2159  # sıfır exceedance için asgari B yalnız çözünürlük
    with pytest.raises(ValueError, match="en küçük p"):
        tp.check_resolution(300, 0.05, 108)  # 1/301 ≈ 0,003322 > 0,05/108 ≈ 0,000463: ulaşılamaz, koşu öncesi yakalanır
    tp.check_resolution(2159, 0.05, 108)
    tp.check_resolution(300, 0.05, 1)  # B=300 tek test için yeter (1/301 < 0,05)


def test_prereg_fixed_fields_and_resolution():
    h = tp.check_prereg(PRE)
    assert len(h) == 64 and tp.check_prereg(dict(PRE)) == h
    for k in PRE:
        with pytest.raises(ValueError, match="eksik"):
            tp.check_prereg({x: v for x, v in PRE.items() if x != k})
    with pytest.raises(ValueError, match="en küçük p"):
        tp.check_prereg(dict(PRE, B=300, max_variants=108))
    with pytest.raises(ValueError):
        tp.check_prereg(dict(PRE, multiple_testing="best_of"))


def test_family_meta_in_ledger_old_calls_unchanged(tmp_path):
    p = tmp_path / "l.jsonl"
    cfg = dict(audit_causal=True)
    old = ledger.record(p, "referee", "h", cfg, "c", "d", result=dict(net_pnl=1.0))
    assert "family" not in old  # eski çağrı biçimi bozulmadı
    meta = dict(hypothesis_id="H1", parent_hypothesis="carry_xs", selection_family="carry_v2", control_role="primary", run_id="r1", attempt=1)
    assert ledger.record(p, "referee", "h", cfg, "c", "d", result=dict(net_pnl=1.0), family=meta)["family"]["parent_hypothesis"] == "carry_xs"
    for bad in (dict(meta, control_role="x"), {k: v for k, v in meta.items() if k != "run_id"}, dict(meta, attempt=0)):
        with pytest.raises(ValueError):
            ledger.record(p, "referee", "h", cfg, "c", "d", result=dict(net_pnl=1.0), family=bad)


def test_family_report_common_calendar_and_info_only():
    idx = pd.date_range("2024-01-01", periods=200, freq="D", tz="UTC")
    rng = np.random.default_rng(0)
    base = rng.normal(size=200)
    R = pd.DataFrame({f"t{i}": base + 0.3 * rng.normal(size=200) for i in range(5)}, index=idx)
    r = tp.family_report(R)
    assert r["n_raw"] == 5 and r["n_days"] == 200 and 1.0 <= r["n_eff_info"] < 5 and r["mean_pair_corr"] > 0.5  # bağımlı deneme: N_eff < ham N (bilgi)
    with pytest.raises(ValueError):
        tp.family_report(R.iloc[:, :1])
    R2 = R.copy()
    R2.iloc[3, 0] = np.nan
    with pytest.raises(ValueError):
        tp.family_report(R2)
