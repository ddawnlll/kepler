"""Gerçek veride kesme/bozma nedensellik denetimi (Modal'de koşar): ensemble kitabı, audit.check_causal_book ile.

Her kesim noktası k için: k sonrası OHLCV bozulur ve veri k'da kesilir; k öncesi hedefler değişmemeli (funding ayrıca bozulur). Boş liste = nedensel.
  python scripts/causal_real.py [--lo 2021-06-01 --hi 2022-12-31]"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np  # noqa: E402

import ensemble as ew  # noqa: E402
from kepler import audit  # noqa: E402
from kepler import ensemble as en  # noqa: E402


def main(lo: str, hi: str) -> int:
    ew.load(ew.EXT, [("/data/pre2022", None, ew.SPLIT), ("/data", ew.SPLIT, None)])
    kls = {s: d["kl"].loc[lo:hi] for s, d in ew.D.items()}
    print(f"{len(kls)} sembol, {lo} -> {hi}, {len(next(iter(kls.values())))} saatlik bar", flush=True)
    book = en.make_book(ew.CAP)
    bad = audit.check_causal_book(book, kls, fracs=tuple(np.linspace(0.2, 0.9, 8)))
    base = book(kls)
    k = int(len(next(iter(kls.values()))) * 0.5)
    t = next(iter(kls.values())).index[k]
    alt = {s: kl.assign(fund_hr=kl.fund_hr.where(kl.index < t, 1e-3)) for s, kl in kls.items()}
    pert = book(alt)
    fund_bad = [s for s in kls if not base[s].target[base[s].index < t].equals(pert[s].target[pert[s].index < t])]
    print(f"OHLCV bozma/kesme: değişen kesim noktaları {bad}; funding bozma: değişen semboller {fund_bad}")
    return int(bool(bad or fund_bad))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lo", default="2021-06-01")
    ap.add_argument("--hi", default="2022-12-31")
    a = ap.parse_args()
    raise SystemExit(main(a.lo, a.hi))
