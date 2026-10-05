"""Ensemble hazır bileşimler (ensemble.PRESETS): adlar kayıtlı, ağırlık sayısı üye sayısına eşit, varsayılan Params() = 'ev1'."""
import pytest

from kepler import ensemble as en


@pytest.mark.parametrize("name", list(en.PRESETS))
def test_preset_members_registered_and_weights_match(name):
    c = en.PRESETS[name]
    assert set(c["names"]) <= set(en.REG) and len(c["names"]) == len(c["weights"])


def test_default_params_equal_ev1_preset():
    assert en.composition(en.Params()) == (en.PRESETS["ev1"]["names"], en.PRESETS["ev1"]["weights"])
    assert en.composition(en.Params(**en.PRESETS["ev1"])) == en.composition(en.Params())


def test_all_nine_experts_are_in_the_full_presets():
    for name in ("all9_equal", "ev1_plus_new"):
        assert set(en.PRESETS[name]["names"]) == set(en.REG) and len(en.PRESETS[name]["names"]) == 9
    assert sum(en.PRESETS["all9_equal"]["weights"]) == pytest.approx(1.0)
