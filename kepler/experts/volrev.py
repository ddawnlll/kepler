"""E8 hacim şoku sonrası geri dönüş (liquidity vekili: likidite sağlayıcı tazminatı; taker olarak uygulanır; protokol): v = dvol_d / ort(dvol_{d-L..d-1}); v > thr iken F = -clip(r1 / (2 sd), -1, 1), aksi 0."""
import numpy as np
import pandas as pd

from kepler.experts._interface import par

DEFAULT = dict(L=30, thr=1.5)


def forecast(close: pd.DataFrame, st: dict, p) -> pd.DataFrame:
    q, dv = par(p, DEFAULT), st["dvol"]
    v = dv / dv.rolling(q["L"], min_periods=max(2, q["L"] // 2)).mean().shift(1)
    f = (-st["ret"] / (2 * st["sigma"] / np.sqrt(365))).clip(-1, 1)
    return f.where(v > q["thr"], 0.0).fillna(0.0).where(st["active"])
