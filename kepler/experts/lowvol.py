"""E5 düşük oynaklık (risk-premium vekili; protokol): kesitsel sıra, en düşük L günlük oynaklık +1 (dolar-nötr); n < 4 ise 0."""
import numpy as np
import pandas as pd

from kepler.experts._interface import par, xrank

DEFAULT = dict(L=60)


def forecast(close: pd.DataFrame, st: dict, p) -> pd.DataFrame:
    L = par(p, DEFAULT)["L"]
    vol = st["ret"].rolling(L, min_periods=max(2, L * 2 // 3)).std() * np.sqrt(365)
    return xrank(-vol, st["active"])
