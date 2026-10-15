"""Causal, reusable scientific features and fixed-proxy market-state panel.

Experiment-specific symbols, feature columns and date ranges are explicit inputs.
Do not change historical calculation order without a numerical parity study.
"""
import math
from datetime import date, datetime, timedelta, timezone
import numpy as np

def _roll_sum(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(x.size, np.nan)
    for i in range(n - 1, x.size):
        z = x[i - n + 1:i + 1]
        if np.isfinite(z).all():
            out[i] = z.sum()
    return out


def _roll_median_log_ratio(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(x.size, np.nan)
    for i in range(n - 1, x.size):
        w = x[i - n + 1:i + 1]
        if np.isfinite(w).all() and np.all(w > 0):
            med = float(np.median(w))
            if med > 0:
                out[i] = math.log(w[-1] / med)
    return out


def _funding_stress(events: list[tuple[int, float]], days: list[date]) -> np.ndarray:
    out = np.full(len(days), np.nan)
    if not events:
        return out
    ts = np.asarray([x[0] for x in events], dtype=np.int64)
    rates = np.asarray([x[1] for x in events], dtype=np.float64)
    for i, d in enumerate(days):
        end = int(datetime.combine(d + timedelta(days=1), datetime.min.time(), timezone.utc).timestamp() * 1000)
        lo90, lo37, lo7 = end - 90 * 86400000, end - 37 * 86400000, end - 7 * 86400000
        a, b, c = np.searchsorted(ts, [lo90, lo37, lo7], side="left")
        e = np.searchsorted(ts, end, side="left")  # strictly before close
        if e - a < 45 or c == e or b == c:
            continue
        hist = rates[a:e]
        sd = float(np.std(hist, ddof=0))
        if sd > 0:
            out[i] = (float(np.mean(rates[c:e])) - float(np.mean(rates[b:c]))) / sd
    return out


def make_panel(klines, funding, *, symbols, day_bounds, m1_names, m2_names):
    days = [day_bounds[0] + timedelta(days=i) for i in range((day_bounds[1] - day_bounds[0]).days + 1)]
    nd = len(days); date_index = {d: i for i, d in enumerate(days)}
    panel = {}
    for sym in symbols:
        arr = np.full((nd, 5), np.nan)
        for d, vals in klines[sym].items():
            if d in date_index:
                arr[date_index[d]] = vals[:5]
        o, h, l, c, vol = arr.T
        ret = np.full(nd, np.nan)
        good = np.isfinite(c[1:]) & np.isfinite(c[:-1])
        # Exact adjacent calendar days only; a missing day breaks the return.
        ret[1:][good] = np.log(c[1:][good] / c[:-1][good])
        rsum20, abs20, sq20 = _roll_sum(ret, 20), _roll_sum(np.abs(ret), 20), _roll_sum(ret * ret, 20)
        z20 = np.divide(rsum20, np.sqrt(sq20 + 1e-12), out=np.full(nd, np.nan), where=np.isfinite(sq20))
        er20 = np.divide(np.abs(rsum20), abs20 + 1e-12, out=np.full(nd, np.nan), where=np.isfinite(abs20))
        q = np.full(nd, np.nan)
        valid = np.isfinite(z20) & np.isfinite(er20)
        q[valid] = 0
        q[valid & (z20 >= 1.25) & (er20 >= .35)] = 1
        q[valid & (z20 <= -1.25) & (er20 >= .35)] = -1
        age = np.full(nd, np.nan)
        for i in range(nd):
            if not np.isfinite(q[i]):
                continue
            age[i] = 1 if i == 0 or not np.isfinite(q[i-1]) or q[i] != q[i-1] else age[i-1] + 1
        ret7, ret21, ret63 = (_roll_sum(ret, n) for n in (7, 21, 63))
        rv5 = np.sqrt(_roll_sum(ret * ret, 5)); rv20 = np.sqrt(sq20)
        vol_surp = _roll_median_log_ratio(vol, 20)
        fund = _funding_stress(funding[sym], days)
        panel[sym] = {"open": o, "high": h, "low": l, "close": c, "volume": vol, "ret": ret, "q": q, "age": age,
                      "z20": z20, "er20": er20, "ret7": ret7, "ret21": ret21, "ret63": ret63,
                      "rv5": rv5, "rv20": rv20, "volume_surprise20": vol_surp, "funding_stress90": fund}
    # One same-origin breadth/dispersion scalar, only when >=3 symbols have complete trailing returns.
    breadth = np.full((len(symbols), nd), np.nan)
    for i in range(nd):
        xs = np.asarray([panel[s]["ret7"][i] for s in symbols])
        xs = xs[np.isfinite(xs)]
        if xs.size >= 3:
            sd = float(np.std(xs, ddof=0))
            value = float(np.mean(xs) / sd) if sd > 0 else 0.0
            breadth[:, i] = value
    for j, sym in enumerate(symbols):
        p = panel[sym]
        with np.errstate(divide="ignore", invalid="ignore"):
            p["rv5_rv20"] = p["rv5"] / p["rv20"]
        p["breadth_dispersion7"] = breadth[j]
        p["base"] = np.column_stack([*(p["q"] == v for v in (-1, 0, 1)), np.log1p(p["age"]),
                                      *(np.full(nd, float(s == sym)) for s in symbols)])
        p["m1"] = np.column_stack([p[k] for k in m1_names])
        p["m2"] = np.column_stack([p[k] for k in m2_names])
        p["features"] = np.column_stack([p["base"], p["m1"], p["m2"]])
    return days, panel


