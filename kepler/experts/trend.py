"""E1 trend (EV1, reports/ensemble_protocol.md §2): çok ufuklu z-skor trend, [-1, 1]."""
import numpy as np
import pandas as pd


def forecast(close: pd.DataFrame, st: dict, p) -> pd.DataFrame:
    cf, act, sd = close.ffill(), st["active"], st["sigma"] / np.sqrt(365)
    e1 = sum((np.log(cf / cf.shift(L)) / (sd * np.sqrt(L)) / 2).clip(-1, 1) for L in p.trend_L) / len(p.trend_L)
    return e1.where(act)
