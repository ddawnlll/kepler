"""Faz 2 işçisi (reports/preregistration/neutral_zone_hysteresis.md ve carry_rebuild.md): dinamik evren (aylık top-20, delist dahil), mevcut hakem, tek seferlik koşular.

  modal run modal_app.py --cmd "python scripts/signal_phase2.py --run B1 --out /data/signal_diag/phase2"
  Koşular: B1 trend tabanı | T1 trend + histerezis | B2 ev1_plus_new tabanı | T2 ev1_plus_new + histerezis | C0 mevcut carry (baz) | C1 carry_xs.
  T1, T2, C1: `evaluate.evaluate_book` (nedensellik denetimi + defter); B1, B2, C0: `run_book` (ölçüm, deftersiz).
Histerezis `portfolio.size` çıktısı üzerinde pozisyon-izin maskesidir (boyutlama/tampon değişmez); eşikler θ_out = 0,10, θ_in = 0,25 (ön kayıt)."""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_fix as AF  # noqa: E402  (referee günlüğünü kapatır; E.load/E.D/E.spec)
import ensemble as E  # noqa: E402
import signal_diag as sd  # noqa: E402

from kepler import ensemble as en  # noqa: E402
from kepler import evaluate as ev  # noqa: E402
from kepler import portfolio, receipt, report  # noqa: E402
from kepler.experts import carry_xs  # noqa: E402

CAPR, TH_OUT, TH_IN = 10_000.0, 0.10, 0.25
RUNS = {  # ad: (bileşim, histerezis, deftere yaz)
    "B1": (dict(names=("trend",), weights=(1.0,)), False, False), "T1": (dict(names=("trend",), weights=(1.0,)), True, True),
    "B2": (en.PRESETS["ev1_plus_new"], False, False), "T2": (en.PRESETS["ev1_plus_new"], True, True),
    "C0": (dict(names=("carry",), weights=(1.0,)), False, False), "C1": (dict(names=("carry_xs",), weights=(1.0,)), False, True),
}


def hyst_state(f: pd.DataFrame, th_out: float, th_in: float) -> pd.DataFrame:
    """Sembol başına durum s ∈ {−1, 0, +1} (Schmitt tetik): 0'dan |F| ≥ θ_in ile girer; mevcut yönde |F| ≥ θ_out'a kadar kalır; yön çevirme için karşı yönde |F| ≥ θ_in; aktif olmayan (NaN) gün s = 0."""
    x, s = f.to_numpy(float), np.zeros(f.shape[1])
    out = np.zeros(f.shape)
    for d in range(len(x)):
        v, nan = np.nan_to_num(x[d]), np.isnan(x[d])
        flat = np.where(v >= th_in, 1.0, np.where(v <= -th_in, -1.0, 0.0))
        long_ = np.where(v <= -th_in, -1.0, np.where(v < th_out, 0.0, 1.0))
        short = np.where(v >= th_in, 1.0, np.where(v > -th_out, 0.0, -1.0))
        s = np.where(nan, 0.0, np.where(s == 0, flat, np.where(s > 0, long_, short)))
        out[d] = s
    return pd.DataFrame(out, index=f.index, columns=f.columns)


def make_book(p: en.Params, mem: pd.DataFrame, hyst: bool, cap: float = CAPR, u: float | None = None):
    """Kitap fabrikası: `ensemble.make_book` ile aynı zincir (durum → uzmanlar → combine → size → place); dinamik evren üyeliği active'e eklenir; hyst: n' = n (s ≠ 0 ve işaret uyumlu), aksi 0."""
    def book(kls):
        close, _ = en.panel(kls)
        st = en.market_state(close, kls, p)
        st = dict(st, active=st["active"] & sd.member_mask(close.index, close.columns, mem))
        es = (carry_xs.forecast(close, st, p),) if p.names == ("carry_xs",) else en.experts(close, st, p)
        f = en.combine(es, st, p)
        if u is not None:  # K1 rotasyon null'u: günlük F aynı k ile dairesel kaydırılır
            f = en.rotate(f, st["active"], u)
        n = portfolio.size(f, st, cap, p)
        if hyst:
            s = hyst_state(f, TH_OUT, TH_IN)
            n = n.where((s != 0) & (np.sign(n) == s), 0.0)
        return {sym: pd.DataFrame(dict(target=en.place(kl, n[sym]), stop=np.nan), index=kl.index) for sym, kl in kls.items()}
    return book


def run(name: str, out: Path):
    t0 = time.time()
    comp, hyst, to_ledger = RUNS[name]
    p = en.Params(**comp)
    mem = sd.members(20)
    syms = sorted(mem.sym.unique())
    E.D.clear()
    AF.load_dynamic(syms, cap=CAPR)
    syms = [s for s in syms if s in E.D]
    data = E.data_of(syms)
    kls = {s: d["kl"] for s, d in data.items()}
    book = make_book(p, mem, hyst)
    sp = E.spec(cap=CAPR)
    out.mkdir(parents=True, exist_ok=True)
    if to_ledger:
        rows = ev.evaluate_book(book, data, [sp], out / f"ledger_phase2_{name}.jsonl", f"Faz 2 {name}: {json.dumps(comp)} hyst={hyst}", "dyn_top20_" + receipt.data_manifest(data)["id"][:16],
                                name=name, params=dict(comp=comp, hyst=hyst, th=[TH_OUT, TH_IN]), window=E.MAIN)
        res, win = rows[0]["res"], rows[0]["win"]
    else:
        res, win, _ = ev.run_book(book(kls), data, sp, *E.utc(E.MAIN))
    pnl = report.book_pnl(win, res, sp)
    daily = pnl.resample("1D").sum()
    daily.to_csv(out / f"daily_{name}.csv", header=["net"])
    res["fills"].to_csv(out / f"fills_{name}.csv", index=False)
    summ = {k: float(v) for k, v in res["summary"].items()}
    (out / f"summary_{name}.json").write_text(json.dumps(dict(name=name, comp=comp, hyst=hyst, ledger=to_ledger, n_symbols=len(syms), summary=summ, sharpe_fixed=AF.sharpe_fixed(daily, CAPR), net_hourly=float(pnl.sum()),
                                                              window=E.MAIN, seconds=time.time() - t0), indent=1, default=str))
    print("tamam", name, f"{time.time() - t0:.0f}s", "net", summ["net_pnl"], "fills", summ["n_fills"], "rejected", summ["n_rejected"], "sharpe", AF.sharpe_fixed(daily, CAPR))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, choices=list(RUNS))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    run(a.run, Path(a.out))


if __name__ == "__main__":
    main()
