"""Yeni hakemin (numba) eski hakemin (Nautilus) GERÇEK veri çıktılarıyla birebir karşılaştırması + süre ölçümü (Modal'de koşar).
  modal run modal_app.py --cmd "python scripts/referee_validate.py --out /data/vbt_val"
Referans: reports/trade_audit_data/<ön ayar>/{fills.csv,meta.json} (Nautilus koşusu). Karşılaştırma: dolum satırı satırı (sembol, ts, yön, miktar, fiyat), özet kalemleri."""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ensemble as E  # noqa: E402

from kepler import ensemble as en  # noqa: E402
from kepler import evaluate as ev  # noqa: E402

REF = Path(__file__).resolve().parents[1] / "reports" / "trade_audit_data"


OUT = "/data/vbt_val"


def compare(name, res, t):
    ref_f, meta = pd.read_csv(REF / name / "fills.csv"), json.loads((REF / name / "meta.json").read_text())
    f = res["fills"].sort_values("ts", kind="stable").reset_index(drop=True)
    ref_f = ref_f.sort_values("ts", kind="stable").reset_index(drop=True)
    out = dict(preset=name, n_new=len(f), n_ref=len(ref_f), seconds=t)
    key = ["sym", "ts", "side"]
    f["qty"], ref_f["qty"] = f.qty.round(8), ref_f.qty.round(8)  # CSV gidiş-dönüşünde 1 ulp
    m = f.merge(ref_f, on=key + ["qty"], how="outer", suffixes=("_new", "_ref"), indicator=True)
    out["rows_matched"] = int((m._merge == "both").sum())
    out["rows_only_new"], out["rows_only_ref"] = int((m._merge == "left_only").sum()), int((m._merge == "right_only").sum())
    b = m[m._merge == "both"]
    out["max_abs_px_diff"] = float((b.px_new - b.px_ref).abs().max()) if len(b) else None
    out["max_abs_comm_diff"] = float((b.commission_new - b.commission_ref).abs().max()) if len(b) else None
    s, r = res["summary"], meta["summary"]
    b2 = b.sort_values("ts")
    np.savez_compressed(Path(OUT) / f"{name}_diff.npz", ts=b2.ts.to_numpy(), dpx=(b2.px_new - b2.px_ref).to_numpy(), dcomm=(b2.commission_new - b2.commission_ref).to_numpy(),
                        cash_new=(-np.where(b2.side == "BUY", 1, -1) * b2.qty * b2.px_new - b2.commission_new).cumsum().to_numpy(), cash_ref=(-np.where(b2.side == "BUY", 1, -1) * b2.qty * b2.px_ref - b2.commission_ref).cumsum().to_numpy())
    out["summary_diff"] = {k: float(s[k]) - float(r[k]) for k in r if k in s and isinstance(r[k], (int, float))}
    out["net_new"], out["net_ref"] = float(s["net_pnl"]), float(r["net_pnl"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/data/vbt_val")
    ap.add_argument("--cap", type=float, default=1000.0)
    a = ap.parse_args()
    global OUT
    OUT = a.out
    Path(a.out).mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    E.load(E.EXT, [("/data/pre2022", None, E.SPLIT), ("/data", E.SPLIT, None)], cap=a.cap)
    t_load = time.perf_counter() - t0
    data, sp = E.data_of(E.EXT), E.spec(cap=a.cap)
    kls = {s: d["kl"] for s, d in data.items()}
    results = []
    for name in ("ev1", "ev1_plus_new", "all9_equal"):
        p = en.Params(**en.PRESETS[name])
        t1 = time.perf_counter()
        book = en.make_book(a.cap, p)(kls)
        t_book = time.perf_counter() - t1
        t2 = time.perf_counter()
        res, _, _ = ev.run_book(book, data, sp, *E.utc(E.MAIN))
        t_ref = time.perf_counter() - t2
        t3 = time.perf_counter()
        res2, _, _ = ev.run_book(book, data, sp, *E.utc(E.MAIN))  # ısınmış ikinci koşu
        t_warm = time.perf_counter() - t3
        c = compare(name, res, t_ref)
        c.update(t_load=t_load, t_book=t_book, t_first=t_ref, t_warm=t_warm, symbols=len(data), bars=int(sum(len(k) for k in kls.values())))
        results.append(c)
        print(json.dumps(c, indent=1, default=str), flush=True)
    Path(a.out, "validate.json").write_text(json.dumps(results, indent=1, default=str))


if __name__ == "__main__":
    main()
