"""E4 Bollinger z-skor (mean-reversion; reports/edge_experts_protocol.md): F = clip(-z/k, -1, 1), z = (C - SMA_n) / std_n (ddof 0); std = 0 ise 0."""
import pandas as pd

from kepler.experts._interface import par

DEFAULT = dict(n=20, k=2.0)


def forecast(close: pd.DataFrame, st: dict, p) -> pd.DataFrame:
    q, cf = par(p, DEFAULT), close.ffill()
    s = cf.rolling(q["n"]).std(ddof=0)
    z = (cf - cf.rolling(q["n"]).mean()) / s.where(s > 0)
    return (-z / q["k"]).clip(-1, 1).where(s > 0, 0.0).where(st["active"])
