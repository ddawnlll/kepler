"""E7 funding kalabalığı (structural: zorunlu akış vekili; protokol): z = kendi L günlük geçmişine göre funding z-skoru; yalnızca |z| > thr iken F = -clip(z/3, -1, 1), aksi 0."""
import pandas as pd

from kepler.experts._interface import par

DEFAULT = dict(L=90, thr=1.5)


def forecast(close: pd.DataFrame, st: dict, p) -> pd.DataFrame:
    q, phi = par(p, DEFAULT), st["phi"]
    r = phi.rolling(q["L"], min_periods=max(2, q["L"] // 2))
    z = (phi - r.mean()) / r.std().where(r.std() > 0)
    return (-z / 3).clip(-1, 1).where(z.abs() > q["thr"], 0.0).where(st["active"])
