"""E2 kesitsel momentum (EV1 §2): geri bakışlara göre sembol sırası, [-1, 1]; n < 4 ise 0."""
import numpy as np
import pandas as pd


def forecast(close: pd.DataFrame, st: dict, p) -> pd.DataFrame:
    cf, act = close.ffill(), st["active"]
    qs = []
    for L in p.xs_L:
        r = np.log(cf / cf.shift(L)).where(act)
        n = r.notna().sum(axis=1)
        q = 2 * (r.rank(axis=1, method="average") - 1).div((n - 1).where(n >= 4), axis=0) - 1
        qs.append(q.where(r.notna()).fillna(0.0))
    return (sum(qs) / len(qs)).where(act)
