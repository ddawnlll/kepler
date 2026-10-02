import json
import pandas as pd
from kepler import tape
S = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT"]
cut = tape._usable("/data")
for s in S:
    try:
        d = tape.load("/data", s)
    except Exception as e:
        print(s, "ERR", e); continue
    kl, mk, f = d["klines"], d["mark"], d["funding"]
    full = pd.date_range(kl.index[0], kl.index[-1], freq="1h")
    print(s, kl.index[0], kl.index[-1], len(kl), "missing_h", len(full) - len(kl), "mark_missing", len(kl.index.difference(mk.index)), "fund", len(f), f.funding_interval_hours.value_counts().to_dict(), "cut", cut.get(s), "px", round(kl.close.min(), 5), round(kl.close.max(), 2), "nanfund", int(f.last_funding_rate.isna().sum()), "cols", list(kl.columns)[:6])
