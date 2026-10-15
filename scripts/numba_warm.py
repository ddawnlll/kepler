"""Warm the *public* Numba referee API when building the Modal image.

Never hard-code the private referee_core.simulate positional signature: core
funding/intent accounting adds buffers over time. A small real portfolio call
builds exactly the runtime argument structure and fails the build if it drifts.
"""
import numpy as np
import pandas as pd

from kepler import referee

index = pd.date_range("2024-01-01", periods=64, freq="h", tz="UTC")
px = np.full(len(index), 100.0)
kl = pd.DataFrame({"open": px, "high": px + 1.0, "low": px - 1.0,
                   "close": px, "volume": np.full(len(index), 1000.0)},
                  index=index)
rates = pd.DataFrame({"last_funding_rate": [0.0001] * len(index[8::8])},
                     index=index[8::8])
targets = {}
for sym, sign in (("WARM_LONG", 1.0), ("WARM_SHORT", -1.0)):
    target = pd.Series(0.0, index=index)
    target.iloc[2:40] = sign * 1000.0
    targets[sym] = {"kl": kl, "target": target, "mark": kl, "funding": rates,
                    "tick": "0.01", "step": "0.001"}

for fill in ("next_open", "close"):
    spec = referee.Spec(capital=10000.0, leverage=10, liq=True,
                        fill=fill, fee_rt_bps=10.0, slip_rt_bps=2.0,
                        gross_cap=10000.0)
    result = referee.run_portfolio(targets, spec)
    metrics = result["summary"]
    if (metrics["n_fills"] < 2 or metrics["n_rejected"]
            or metrics["funding_missed"]):
        raise RuntimeError(f"Numba warmup finance contract failed for {fill}: {metrics}")
print("NUMBA_RUNTIME_PUBLIC_API_WARMUP_OK")
