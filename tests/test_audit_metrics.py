"""scripts/audit_metrics.py: sabit-sermaye ve equity-normalize ölçüler, tek tanımlı suda kalma süresi, dönem tablosu; beklenen değerler elle."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import audit_metrics as am  # noqa: E402

IDX = pd.date_range("2024-01-01", periods=4, freq="1D", tz="UTC")


def test_sharpe_fixed_uses_initial_capital():
    pnl = pd.Series([10.0, -5.0, 0.0, 20.0], index=IDX)  # cap 100: r = .1, -.05, 0, .2; ort .0625, sapma kareleri toplamı .036875
    assert am.sharpe_fixed(pnl, 100.0) == pytest.approx(0.0625 / np.sqrt(0.036875 / 3) * np.sqrt(365))
    assert am.vol_fixed(pnl, 100.0) == pytest.approx(np.sqrt(0.036875 / 3) * np.sqrt(365))


def test_sharpe_equity_divides_by_previous_equity():
    pnl = pd.Series([10.0, -5.0, 0.0, 20.0], index=IDX)  # önceki equity: 100, 110, 105, 105 -> r = .1, -.04545, 0, .190476
    r = np.array([0.1, -5 / 110, 0.0, 20 / 105])
    assert am.sharpe_equity(pnl, 100.0) == pytest.approx(r.mean() / r.std(ddof=1) * np.sqrt(365))


def test_maxdd_fixed_vs_equity():
    pnl = pd.Series([10.0, -5.0, 0.0, 20.0], index=IDX)  # equity 110, 105, 105, 125: toplamsal DD = 5 / 100; tepe-yüzde DD = 5 / 110
    assert am.max_dd_fixed(pnl, 100.0) == pytest.approx(0.05)
    assert am.max_dd_equity(pnl, 100.0) == pytest.approx(5 / 110)


def test_drawdown_table_single_duration_definition():
    d = pd.date_range("2024-01-01", periods=6, freq="1D", tz="UTC")
    eq = pd.Series([105.0, 100.0, 95.0, 105.0, 104.0, 110.0], index=d)
    t = am.drawdown_table(eq, 100.0)
    a, b = t.iloc[0], t.iloc[1]  # derinlik sırası: 10/105 (gün 0 → 3), 1/105 (gün 3 → 5)
    assert a.depth == pytest.approx(10 / 105) and a.usd == pytest.approx(10.0) and a.days == 3 and a.trough == d[2] and a.recovered == d[3]
    assert b.depth == pytest.approx(1 / 105) and b.days == 2
    assert am.longest_underwater_days(eq, 100.0) == 3


def test_open_drawdown_runs_to_end_of_data():
    d = pd.date_range("2024-01-01", periods=4, freq="1D", tz="UTC")
    eq = pd.Series([110.0, 100.0, 101.0, 102.0], index=d)
    t = am.drawdown_table(eq, 100.0)
    assert pd.isna(t.iloc[0].recovered) and t.iloc[0].days == 3


def test_period_table_subperiods():
    d = pd.date_range("2020-04-01", "2026-03-31", freq="1D", tz="UTC")
    pnl = pd.Series(np.tile([1.0, -0.5, 0.25], len(d) // 3 + 1)[: len(d)], index=d)
    t = am.period_table(pnl, 1000.0).set_index("period")
    assert {"2020", "2025", "2026", "2020–21", "2022–24", "2025+"} <= set(t.index)
    assert t.loc["2025+", "days"] == len(pnl["2025-01-01":"2026-03-31"])
    assert t.loc["2022–24", "net"] == pytest.approx(pnl["2022-01-01":"2024-12-31"].sum())


def test_bootstrap_ci_brackets_point_estimate():
    rng = np.random.default_rng(1)
    pnl = pd.Series(rng.normal(0.5, 5.0, 800), index=pd.date_range("2022-01-01", periods=800, freq="1D", tz="UTC"))
    ci = am.bootstrap_sharpe_ci(pnl, 1000.0, B=500)
    assert ci["sharpe_q"]["p2.5"] < am.sharpe_fixed(pnl, 1000.0) < ci["sharpe_q"]["p97.5"]
    assert 0 <= ci["p_sharpe_le_0"] <= 1
