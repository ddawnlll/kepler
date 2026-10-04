"""E6 zirveye yakınlık (behavioral: çıpalama / az-tepki; protokol): x = C / max(C, L gün); kesitsel sıra, zirveye en yakın +1; n < 4 ise 0."""
import pandas as pd

from kepler.experts._interface import par, xrank

DEFAULT = dict(L=180)


def forecast(close: pd.DataFrame, st: dict, p) -> pd.DataFrame:
    L, cf = par(p, DEFAULT)["L"], close.ffill()
    return xrank(cf / cf.rolling(L, min_periods=max(2, L // 2)).max(), st["active"])
