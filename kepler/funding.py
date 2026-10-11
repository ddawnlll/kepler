"""#10: funding settlement takvimi (hakem Adapter.settle tüketir). Olay = (T ns, oran, mark kapanışı, kline-geri-düşüş bayrağı); mark da kline da yoksa kapanış NaN (hakem 'funding_missed' sayar)."""
import math

import pandas as pd

HOUR_NS = 3_600_000_000_000


def schedule(kl: pd.DataFrame, mark: pd.DataFrame | None, funding: pd.DataFrame | None) -> list[tuple]:
    if funding is None or not len(funding):
        return []
    ns = lambda ix: [int(x) for x in pd.DatetimeIndex(ix).as_unit("ns").asi8]  # noqa: E731
    lo, hi = ns(kl.index)[0] + HOUR_NS, ns(kl.index)[-1] + HOUR_NS
    mk = (mark if mark is not None else kl).close.astype(float)
    by_close = dict(zip([t + HOUR_NS for t in ns(mk.index)], mk))  # T'de biten barın mark kapanışı
    out = []
    for ts, rate in zip(ns(pd.DatetimeIndex(funding.index).round("1min")), funding["last_funding_rate"].astype(float)):
        if not lo <= ts <= hi:
            continue
        c, fb = by_close.get(ts, math.nan), 0
        if math.isnan(c) and mark is not None:  # mark barı eksik (gerçek veri: BTC'de 3 boşluk): kline kapanışına düş, özette say
            c = float(kl.close.get(pd.Timestamp(ts, unit="ns", tz="UTC") - pd.Timedelta("1h"), math.nan))
            fb = int(not math.isnan(c))
        out.append((ts, rate, c, fb))
    return sorted(out, key=lambda e: e[0])
