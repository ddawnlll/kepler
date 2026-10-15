"""Fast causal/scientific regressions against the extracted core modules."""
from datetime import date, timedelta
import numpy as np
from kepler.intelligence.regimes import spells, spell_distribution, transition_matrix, continuation_probability
from kepler.intelligence.features import _roll_sum

def test_gap_censors_not_exits():
    days = [date(2025,1,1) + timedelta(days=i) for i in range(6)]
    eps = spells(days, np.array([0,0,np.nan,1,1,0], float))
    assert eps[0]["right_censored"]
    assert eps[1]["left_censored"]
    assert spell_distribution(eps)["completed"] == 0

def test_transition_training_cutoff():
    days = [date(2025,1,1) + timedelta(days=i) for i in range(6)]
    panel = {"X": {"q": np.array([0,0,1,1,-1,-1], float)}}
    before = transition_matrix(panel, days, days[3])
    panel["X"]["q"][4:] = 0
    after = transition_matrix(panel, days, days[3])
    np.testing.assert_array_equal(before, after)

def test_rolling_feature_prefix_is_causal():
    a = np.arange(20, dtype=float)
    b = a.copy()
    b[10:] = -1000
    np.testing.assert_array_equal(_roll_sum(a, 3)[:10], _roll_sum(b, 3)[:10])

def test_survival_probability_bounded():
    training = [{"state":0, "duration":4, "left_censored":False, "right_censored":False},
                {"state":0, "duration":6, "left_censored":False, "right_censored":True}]
    value = continuation_probability(training, 0, 2, 7)
    assert 0 <= value <= 1
