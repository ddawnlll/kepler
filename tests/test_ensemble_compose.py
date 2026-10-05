"""Ensemble tek altyapı: bileşim names/weights ile kurulur; EV1 = varsayılan bileşim. Beklenen değerler elle (formül + sayı)."""
import numpy as np
import pandas as pd
import pytest

from kepler import ensemble as en

DAYS = pd.date_range("2024-01-01", periods=3, freq="1D", tz="UTC")


def test_default_composition_is_ev1():
    names, w = en.composition(en.Params())
    assert names == ("trend", "xs_momentum", "carry") and w == (0.6, 0.2, 0.2)
    assert set(names) <= set(en.REG)


def test_any_registered_expert_can_join_with_a_weight():
    p = en.Params(names=en.EV1_NAMES + ("nearhigh",), weights=(0.6, 0.2, 0.2, 0.1))
    assert en.composition(p) == (en.EV1_NAMES + ("nearhigh",), (0.6, 0.2, 0.2, 0.1))
    assert en.composition(en.Params(expert="bollinger", flip=True)) == (("bollinger",), (-1.0,))  # tek uzman = tek üyeli bileşim


def test_combine_weights_and_negative_weight_flips_sign():
    act = pd.DataFrame(True, index=DAYS, columns=["A", "B"])
    st = dict(active=act)
    e1 = pd.DataFrame({"A": [1.0, 1.0, 1.0], "B": [-1.0, -1.0, -1.0]}, index=DAYS)
    e2 = pd.DataFrame({"A": [0.0, 0.0, 0.0], "B": [1.0, 1.0, 1.0]}, index=DAYS)
    p = en.Params(names=("trend", "carry"), weights=(0.5, 0.5), warm=1)
    # raw_A = 0,5·1 + 0,5·0 = 0,5; raw_B = 0,5·(−1) + 0,5·1 = 0 -> m = (0,5 + 0)/2 = 0,25; F_A = 0,5 · 0,5 / 0,25 = 1 (clip), F_B = 0
    f = en.combine((e1, e2), st, p)
    assert f["A"].iloc[-1] == pytest.approx(1.0) and f["B"].iloc[-1] == pytest.approx(0.0)
    g = en.combine((e1, e2), st, en.Params(names=("trend", "carry"), weights=(-0.5, -0.5), warm=1))
    assert g["A"].iloc[-1] == pytest.approx(-1.0)  # ağırlıkların işareti dönünce tahmin ters döner (m aynı, |F| aynı)


def test_experts_returns_one_forecast_per_member():
    idx = pd.date_range("2024-01-01", periods=120, freq="1D", tz="UTC")
    close = pd.DataFrame(100 * np.exp(np.cumsum(np.random.default_rng(0).normal(0, 0.02, (120, 5)), axis=0)), index=idx, columns=list("ABCDE"))
    st = dict(active=close.notna(), sigma=close * 0 + 0.5, ret=np.log(close).diff(), phi=close * 0, dvol=close * 0 + 1, tbr=close * 0 + 0.5)
    for p in (en.Params(), en.Params(names=("bollinger",), weights=(1.0,)), en.Params(names=("trend", "nearhigh"), weights=(0.5, 0.5))):
        assert len(en.experts(close, st, p)) == len(en.composition(p)[0])
