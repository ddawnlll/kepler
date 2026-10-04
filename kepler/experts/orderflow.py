"""E9 taker akışı dengesizliği (information vekili: order-flow; protokol): imb = 2 tbr - 1; z = (ort_m(imb) - ort_L(imb)) / std_L(imb); F = clip(z/2, -1, 1) (devam)."""
import pandas as pd

from kepler.experts._interface import par

DEFAULT = dict(L=60, m=3)


def forecast(close: pd.DataFrame, st: dict, p) -> pd.DataFrame:
    q, imb = par(p, DEFAULT), 2 * st["tbr"] - 1
    r = imb.rolling(q["L"], min_periods=max(2, q["L"] // 2))
    z = (imb.rolling(q["m"]).mean() - r.mean()) / r.std().where(r.std() > 0)
    return (z / 2).clip(-1, 1).fillna(0.0).where(st["active"])
