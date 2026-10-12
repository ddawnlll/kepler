"""#19: fan-out parity fixture'ı (küçük, sabit, offline; Modal/gerçek veri yok). `scripts/ensemble.py --stage null` ile AYNI şekilde çalışır: --null-from/--null-to aralığı için
her tohum i, u = default_rng([0, i]).uniform(0.05, 0.95) ile sabit bir tahmin serisini dairesel kaydırır, hakemde koşar ve {i: {net, n_fills, daily (günlük net PnL listesi), u}} yazar.
Seri referans (tek aralık) ile parçalı koşunun tohum bazında net/dolum/günlük PnL parity'sini tests/test_null_parity.py doğrular. Gerçek EV1 null'u değildir."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kepler import report  # noqa: E402
from kepler.referee import Spec, run_portfolio  # noqa: E402

N, SP = 24 * 20, Spec(capital=10000.0, fee_rt_bps=10.0, slip_rt_bps=2.0, tick="0.01", step="0.001", fill="next_open", liq=False)


def fixture():
    idx = pd.date_range("2024-01-01", periods=N, freq="1h", tz="UTC")
    rng = np.random.default_rng(7)
    c = 100 * np.exp(np.cumsum(rng.normal(size=N) * 0.004))
    kl = pd.DataFrame(dict(open=np.r_[c[0], c[:-1]], high=c * 1.002, low=c * 0.998, close=c, volume=1e6), index=idx)
    f = np.sign(np.sin(np.arange(N // 24) / 2.0)) * 800.0  # günlük hedef
    fund = pd.DataFrame({"last_funding_rate": rng.normal(size=N // 8) * 1e-4}, index=idx[7::8][: N // 8] + pd.Timedelta("1h"))
    return kl, f, fund


def draw(i: int) -> dict:
    kl, f, fund = fixture()
    u = float(np.random.default_rng([0, i]).uniform(0.05, 0.95))
    g = np.roll(f, int(u * len(f)))
    tgt = pd.Series(np.nan, index=kl.index)
    tgt.iloc[23::24] = g[: len(tgt.iloc[23::24])]
    data = {"X": dict(kl=kl, target=tgt, funding=fund, mark=kl)}
    res = run_portfolio(data, SP)
    daily = report.book_pnl(data, res, SP).resample("1D").sum()
    return dict(u=u, net=float(res["summary"]["net_pnl"]), n_fills=int(res["summary"]["n_fills"]), daily=[float(x) for x in daily])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--null-from", type=int, default=0)
    ap.add_argument("--null-to", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fail-with", type=int, default=0, help="test: Traceback yazıp bu kodla çık")
    a = ap.parse_args()
    if a.fail_with:
        print("Traceback: synthetic failure")
        sys.exit(a.fail_with)
    res = {str(i): draw(i) for i in range(a.null_from, a.null_to)}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    Path(a.out, f"null_{a.null_from}_{a.null_to}.json").write_text(json.dumps(res))
    print("null bitti")
