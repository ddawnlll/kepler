"""Cross-check transparent Brier scoring and deterministic bootstrap."""
from datetime import date, timedelta
import numpy as np
from kepler.intelligence.scoring import summarise_forecast, _moving_block_ci

def test_multiclass_perfect_forecasts_have_zero_brier():
    records = [
        {"date": date(2025,1,1), "true": -1, "model": [1.,0.,0.], "base": [0.,1.,0.]},
        {"date": date(2025,1,2), "true": 0, "model": [0.,1.,0.], "base": [0.,1.,0.]},
    ]
    result = summarise_forecast(records, "model", "base", state_names={-1:"down",0:"neutral",1:"up"})
    assert result["brier"] == 0
    assert result["baseline_brier"] == 1

def test_moving_block_seed_is_reproducible():
    x = {date(2025,1,1)+timedelta(days=i): float(i%7) for i in range(35)}
    assert _moving_block_ci(x,B=25,block=7,seed=21)==_moving_block_ci(x,B=25,block=7,seed=21)
