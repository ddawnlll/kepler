"""Faz 2 ölçütlerini ön kayıtlara göre hesaplar (neutral_zone_hysteresis.md, carry_rebuild.md): günlük net PnL CSV'leri + özet JSON'larından karar.
  python scripts/signal_phase2_report.py reports/signal_diagnostics_data/phase2   → <dizin>/phase2_results.json"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import audit_metrics as am  # noqa: E402

from kepler import stats  # noqa: E402

CAP = 10_000.0
REGIME = Path(__file__).resolve().parent.parent / "reports" / "signal_diagnostics_data" / "regime.csv"


def load(d: Path, name: str):
    s = json.loads((d / f"summary_{name}.json").read_text())
    x = pd.read_csv(d / f"daily_{name}.csv", index_col=0, parse_dates=True)["net"]
    x.index = pd.DatetimeIndex(x.index).tz_convert("UTC") if x.index.tz else pd.DatetimeIndex(x.index).tz_localize("UTC")
    return s, x


def metrics(s: dict, x: pd.Series) -> dict:
    sm = s["summary"]
    pt = am.period_table(x, CAP)
    per = {r.period: dict(net=r.net, sharpe=r.sharpe) for r in pt.itertuples() if r.period in ("2020–21", "2022–24", "2025+")}
    reg = pd.read_csv(REGIME, index_col=0, parse_dates=True)["regime"]
    reg.index = pd.DatetimeIndex(reg.index).tz_convert("UTC") if reg.index.tz else pd.DatetimeIndex(reg.index).tz_localize("UTC")
    lab = reg.reindex(x.index.normalize()).to_numpy()
    rg = {k: float(x[lab == k].sum()) for k in ("bull", "bear", "range")}
    return dict(net=sm["net_pnl"], gross=sm["gross_pnl"], fee=sm["fee"], slippage=sm["slippage"], funding=sm["funding"], exit_cost=sm["exit_cost"], n_fills=sm["n_fills"], n_liq=sm["n_liq"], n_rejected=sm["n_rejected"],
                sharpe=am.sharpe_fixed(x, CAP), vol=am.vol_fixed(x, CAP), maxdd=am.max_dd_fixed(x, CAP), periods=per, regime=rg, ledger=s["ledger"], n_symbols=s["n_symbols"])


def paired_delta(a: pd.Series, b: pd.Series, B: int = 2000, seed: int = 0, mean_block: float = 20.0) -> dict:
    """ΔSharpe = Sharpe(b) − Sharpe(a), eşleştirilmiş durağan blok bootstrap (aynı gün örneği)."""
    j = a.index.intersection(b.index)
    ra, rb = (a.loc[j] / CAP).to_numpy(), (b.loc[j] / CAP).to_numpy()
    idx = stats.stationary_bootstrap(len(j), mean_block, B, seed)
    sh = lambda r: r.mean(axis=1) / r.std(axis=1, ddof=1) * np.sqrt(365)  # noqa: E731
    d = sh(rb[idx]) - sh(ra[idx])
    point = float(am.sharpe_fixed(b.loc[j], CAP) - am.sharpe_fixed(a.loc[j], CAP))
    return dict(point=point, p2_5=float(np.quantile(d, 0.025)), p50=float(np.quantile(d, 0.5)), p97_5=float(np.quantile(d, 0.975)), p5=float(np.quantile(d, 0.05)), n_days=len(j))


def main(d: Path):
    runs = {n: load(d, n) for n in ("B1", "T1", "B2", "T2", "C0", "C1") if (d / f"summary_{n}.json").exists()}
    out = dict(runs={n: metrics(s, x) for n, (s, x) in runs.items()})
    for core, (b, t) in dict(trend=("B1", "T1"), ensemble=("B2", "T2")).items():
        if b in runs and t in runs:
            dl = paired_delta(runs[b][1], runs[t][1])
            mb, mt = out["runs"][b], out["runs"][t]
            if dl["p2_5"] > 0 and mt["net"] >= mb["net"]:
                dec = "ÇALIŞTI"
            elif dl["point"] <= 0:
                dec = "ÇALIŞMADI"
            else:
                dec = "KANITSIZ"
            sub = {p: am.sharpe_fixed(runs[t][1][(runs[t][1].index >= pd.Timestamp(a_, tz="UTC")) & (runs[t][1].index <= pd.Timestamp(e_, tz="UTC") + pd.Timedelta("23h"))], CAP)
                   - am.sharpe_fixed(runs[b][1][(runs[b][1].index >= pd.Timestamp(a_, tz="UTC")) & (runs[b][1].index <= pd.Timestamp(e_, tz="UTC") + pd.Timedelta("23h"))], CAP)
                   for p, (a_, e_) in dict(zip(("2020–21", "2022–24", "2025+"), (("2020-04-01", "2021-12-31"), ("2022-01-01", "2024-12-31"), ("2025-01-01", "2026-03-31")))).items()}
            out[f"hyst_{core}"] = dict(decision=dec, delta_sharpe=dl, d_net=mt["net"] - mb["net"], d_gross=mt["gross"] - mb["gross"], d_cost=(mt["fee"] + mt["slippage"]) - (mb["fee"] + mb["slippage"]), d_fills=mt["n_fills"] - mb["n_fills"],
                                       d_funding=mt["funding"] - mb["funding"], d_sharpe_by_period=sub)
    if "C1" in runs and "B1" in runs:
        c = runs["C1"][1]
        boot = am.bootstrap_sharpe_ci(c, CAP)
        m = out["runs"]["C1"]
        corr = float(runs["C1"][1].corr(runs["B1"][1]))
        s1, s2 = m["net"] > 0, boot["sharpe_q"]["p5"] > 0
        s3, s4 = sum(v["net"] > 0 for v in m["periods"].values()) >= 2, corr <= 0.30
        out["carry_xs"] = dict(S1_net_pos=s1, S2_sharpe_p5_pos=s2, S3_periods=s3, S4_corr_le_030=s4, corr_trend_daily_pnl=corr, bootstrap=boot,
                               corr_c0=float(runs["C0"][1].corr(runs["C1"][1])) if "C0" in runs else None,
                               decision="KABUL" if (s1 and s2 and s3 and s4) else "KISMİ" if (s1 and s2) else "RED")
    (d / "phase2_results.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: v for k, v in out.items() if k != "runs"}, indent=1, default=float)[:3000])
    for n, m in out["runs"].items():
        print(n, round(m["net"], 1), "sharpe", round(m["sharpe"], 3), "fills", m["n_fills"], "dd", round(m["maxdd"], 3))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
