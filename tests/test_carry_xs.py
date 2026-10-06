"""carry_xs (reports/preregistration/carry_rebuild.md): beklenen değerler elle; gelecek-bozma: d günü tahmini yalnızca d satırına bağlı."""
import numpy as np
import pandas as pd
import pytest

from kepler.experts import carry_xs

D = pd.date_range("2024-01-01", periods=3, freq="1D", tz="UTC")


def st_of(phi, active=None):
    phi = pd.DataFrame(phi, index=D[: len(next(iter(phi.values())))])
    return dict(phi=phi, active=phi.notna() if active is None else active)


def test_cross_sectional_rank_lowest_funding_long():
    phi = {"A": [0.3], "B": [0.1], "C": [-0.2], "D": [0.5]}
    f = carry_xs.forecast(None, st_of(phi), None).iloc[0]
    # −φ = −0,3; −0,1; 0,2; −0,5 -> sıra A=2, B=3, C=4, D=1 -> q = 2(sıra − 1)/3 − 1
    assert f.to_dict() == pytest.approx({"A": -1 / 3, "B": 1 / 3, "C": 1.0, "D": -1.0})


def test_market_wide_funding_level_does_not_change_forecast():
    base = {"A": [0.3], "B": [0.1], "C": [-0.2], "D": [0.5]}
    shifted = {k: [v[0] + 0.7] for k, v in base.items()}  # piyasa geneli funding yükseldi (boğa): dolar-nötr, tahmin aynı
    assert carry_xs.forecast(None, st_of(base), None).iloc[0].tolist() == carry_xs.forecast(None, st_of(shifted), None).iloc[0].tolist()


def test_fewer_than_four_symbols_and_nan_phi_give_zero():
    f3 = carry_xs.forecast(None, st_of({"A": [0.3], "B": [0.1], "C": [-0.2]}), None).iloc[0]
    assert f3.tolist() == [0.0, 0.0, 0.0]  # n < 4
    phi = {"A": [0.3], "B": [0.1], "C": [-0.2], "D": [0.5], "E": [np.nan]}
    act = pd.DataFrame({k: [True] for k in phi}, index=D[:1])
    f = carry_xs.forecast(None, st_of(phi, act), None).iloc[0]
    assert f["E"] == 0.0 and f["C"] == 1.0  # φ yok: 0; kalan 4 sembol sıralanır


def test_future_rows_do_not_change_past_forecast():
    phi = {"A": [0.3, 0.1], "B": [0.1, 0.2], "C": [-0.2, 0.3], "D": [0.5, 0.4]}
    full = carry_xs.forecast(None, st_of(phi), None)
    cut = carry_xs.forecast(None, st_of({k: v[:1] for k, v in phi.items()}), None)
    assert cut.iloc[0].tolist() == full.iloc[0].tolist()
