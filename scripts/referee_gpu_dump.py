"""GPU deneyi için girdi dökümü (CPU imajında, Modal): EV1 kitabı -> hazırlanmış çekirdek dizileri (npz). Sonra: modal run scripts/referee_gpu_bench.py
  modal run modal_app.py --cmd "python scripts/referee_gpu_dump.py --out /data/vbt_val/gpu_inputs.npz" """
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ensemble as E  # noqa: E402

from kepler import ensemble as en  # noqa: E402
from kepler import referee  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/data/vbt_val/gpu_inputs.npz")
    a = ap.parse_args()
    E.load(E.EXT, [("/data/pre2022", None, E.SPLIT), ("/data", E.SPLIT, None)], cap=1000.0)
    data, sp = E.data_of(E.EXT), E.spec(cap=1000.0)
    kls = {s: d["kl"] for s, d in data.items()}
    book = en.make_book(1000.0, en.Params(**en.PRESETS["ev1"]))(kls)
    lo, hi = E.utc(E.MAIN)
    keep = {s: (d["kl"].index >= lo) & (d["kl"].index < hi) for s, d in data.items()}
    win = {s: dict(d, kl=d["kl"][keep[s]], target=book[s].target.ffill().fillna(0.0)[keep[s]], stop=book[s].stop[keep[s]], mark=None if d.get("mark") is None else d["mark"].loc[(d["mark"].index >= lo) & (d["mark"].index < hi)]) for s, d in data.items()}
    pr = referee.prepare(win, sp)
    off = pr["off"]
    TG, ST = pr["tg"].copy(), pr["st"].copy()
    for k in range(len(pr["syms"])):
        sl = slice(off[k], off[k + 1])
        TG[sl], ST[sl] = referee._shift(pr["tg"][sl], 1), referee._shift(pr["st"][sl], 1)
    P = np.array([(sp.fee_rt_bps + sp.slip_rt_bps) / 2 / 1e4, sp.leverage, sp.mmr, 1.0, sp.min_notional, sp.capital, 0.0, sp.gross_cap or 0.0, 0.0])
    np.savez(a.out, T0=pr["T0"], O=pr["O"], H=pr["H"], L=pr["L"], C=pr["C"], SZ=pr["SZ"], TG=TG, ST=ST, U=pr["U"], P=P, ev_k=pr["ev_k"], ev_b=pr["ev_b"], ev_kind=pr["ev_kind"])
    print("yazıldı", a.out, len(pr["T0"]), "bar")


if __name__ == "__main__":
    main()
