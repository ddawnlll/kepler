"""Geçici profil betiği (Modal): bir null çekilişinin (scripts/ensemble.py null_draw) aşama süreleri + cProfile. Karar/defter üretmez."""
import cProfile
import io
import pstats
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import ensemble as E  # noqa: E402

from kepler import ensemble as en  # noqa: E402
from kepler import evaluate as ev  # noqa: E402
from kepler.market_state import market_state, panel  # noqa: E402


def t(label, f):
    t0 = time.time()
    r = f()
    print(f"[{time.time() - t0:7.2f}s] {label}", flush=True)
    return r


roots = [("/data/pre2022", None, E.SPLIT), ("/data", E.SPLIT, None)]
t("load", lambda: E.load(E.EXT, roots))
kls = {s: E.D[s]["kl"] for s in E.EXT}
p, sp = en.Params(), E.spec()
u = float(np.random.default_rng([0, 0]).uniform(0.05, 0.95))
close, _ = t("panel", lambda: panel(kls))
st = t("market_state", lambda: market_state(close, kls, p))
es = t("experts", lambda: en.experts(close, st, p))
f = t("combine", lambda: en.combine(es, st, p))
f = t("rotate", lambda: en.rotate(f, st["active"], u))
n = t("size", lambda: en.size(f, st, sp.capital, p))
out = t("place", lambda: {s: pd.DataFrame(dict(target=en.place(kl, n[s]), stop=np.nan), index=kl.index) for s, kl in kls.items()})
pr = cProfile.Profile()
pr.enable()
res, win, _ = t("run_book (hakem)", lambda: ev.run_book(out, E.data_of(E.EXT), sp, *E.utc(E.MAIN)))
pr.disable()
print("net", res["summary"]["net_pnl"], "fills", res["summary"]["n_fills"], "bars", {s: len(win[s]["kl"]) for s in list(win)[:2]})
s = io.StringIO()
pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(18)
print(s.getvalue()[:3500])
s = io.StringIO()
pstats.Stats(pr, stream=s).sort_stats("tottime").print_stats(10)
print(s.getvalue()[:2500])
