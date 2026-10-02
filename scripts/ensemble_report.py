"""Ensemble v1 özet tabloları: scripts/ensemble.py çıktıları (JSON) -> tables.md + summary.json. Kart ve karar kuralı reports/ensemble_protocol.md'deki gibi.

  python scripts/ensemble_report.py <işçi çıktı dizini> <çıktı dizini> [kümülatif deneme için ledger dizinleri...]"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from kepler import robust, stats

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
CAP, SPLIT = 10_000.0, "2022-01-01"
ABL = ("trend_only", "no_xs", "no_carry", "no_risk", "no_buffer")
SHIFT_STARTS = ("2020-04-01", "2020-05-01", "2020-06-01", "2020-07-01")
P = {}
for f in sorted(SRC.glob("primary*.json")):
    P.update(json.loads(f.read_text()))
K7 = json.loads((SRC / "k7.json").read_text())
BTC = pd.Series(json.loads((SRC / "btc_close.json").read_text()))
BTC.index = pd.to_datetime(BTC.index, utc=True)
NULL = {}
for f in sorted(SRC.glob("null_*.json")):
    NULL.update({int(i): r for i, r in json.loads(f.read_text()).items()})


def ser(d):
    x = pd.Series(d, dtype=float)
    x.index = pd.to_datetime(x.index, utc=True)
    return x.sort_index()


def shp(r):
    return stats.annual(stats.moments(r)[0])


def pct(x):
    return f"{100 * x:.1f}%"


main = P["main"]
r = ser(main["daily"]) / CAP
abl = {k: ser(P[f"abl_{k}"]["daily"]) / CAP for k in ABL}
trial_srs = [stats.moments(r)[0]] + [stats.moments(x)[0] for x in abl.values()]  # N = 6 (birincil + 5 ablasyon; muhafazakâr)
bh = ser(P["bh"]["daily"]) / CAP
lab = robust.regime(BTC)
s = main["summary"]
# K1
ng = np.array([NULL[i]["gross_pnl"] for i in sorted(NULL)])
nn = np.array([NULL[i]["net_pnl"] for i in sorted(NULL)])
p_g, p_n = stats.rotation_p(s["gross_pnl"], ng), stats.rotation_p(s["net_pnl"], nn)
dsr = stats.dsr(r, trial_srs)
k1 = p_g <= 0.05 and dsr >= 0.95
# K2
rr, bb = r.align(bh, join="inner")
a, b, t = stats.nw_alpha(rr.to_numpy(), bb.to_numpy(), 5)
k2 = shp(r) > shp(bh) and t >= 2
# K3
c = lambda fee, slip, d=0: P[f"cost_{fee}_{slip}_{d}"]["summary"]["net_pnl"]  # noqa: E731
k3 = shp(r) >= 1.0 and c(16, 6) > 0 and c(10, 2, 1) > 0
# K4
dd, boot = float(stats.max_drawdown(r.to_numpy())), {L: stats.bootstrap_summary(r.to_numpy(), L, 2000, 0) for L in (10, 20, 40)}
k4 = dd <= 0.25 and boot[20]["maxdd"][1] <= 0.30
# K5
nb = {k[3:]: v for k, v in P.items() if k.startswith("nb_")}
nb_net, nb_sh = np.array([v["summary"]["net_pnl"] for v in nb.values()]), np.array([shp(ser(v["daily"]) / CAP) for v in nb.values()])
k5 = (nb_net > 0).mean() >= 0.7 and np.median(nb_sh) >= 0.5 * shp(r)
# K6
wk = {k[4:]: v["summary"]["net_pnl"] for k, v in P.items() if k.startswith("win_")}
shifts = {k: v for k, v in wk.items() if k.split("_")[0] in SHIFT_STARTS and k.endswith("2026-04-01") and not k.startswith("2026")}
halves = {k: v for k, v in wk.items() if k not in shifts}
k6 = sum(v > 0 for v in halves.values()) >= 0.6 * len(halves) and all(v > 0 for v in shifts.values())
# K7
k7 = K7["summary"]["net_pnl"] > 0
# K8
sh_abl = {k: shp(x) for k, x in abl.items()}
k8 = all(shp(r) > v for v in sh_abl.values())
# K9
reg = robust.by_regime(r * CAP, lab)
tot = sum(v["total"] for v in reg.values())
k9 = sum(v["total"] >= 0 for v in reg.values()) >= 2 and tot > 0 and max(v["total"] for v in reg.values()) / tot <= 0.8
passed = {k: bool(v) for k, v in dict(K1=k1, K2=k2, K3=k3, K4=k4, K5=k5, K6=k6, K7=k7, K8=k8, K9=k9).items()}
decision = robust.decision(passed)
sr_d, g3, g4, _ = stats.moments(r)
# bilgi
eq = 1 + r.cumsum()
dd_peak = ((eq.cummax() - eq) / eq.cummax())
kill = {thr: (str(dd_peak.index[dd_peak > thr][0].date()) if (dd_peak > thr).any() else None) for thr in (0.25, 0.30)}
sub = {}
for name, (lo, hi) in {"2020-04→2022-01": ("2020-04-01", SPLIT), "2022-01→2026-04": (SPLIT, "2026-04-01")}.items():
    x, y = r[(r.index >= lo) & (r.index < hi)], bh[(bh.index >= lo) & (bh.index < hi)]
    xx, yy = x.align(y, join="inner")
    sub[name] = dict(net=float(x.sum() * CAP), sharpe=shp(x), bh_sharpe=shp(y), t_alpha=stats.nw_alpha(xx.to_numpy(), yy.to_numpy(), 5)[2], maxdd=float(stats.max_drawdown(x.to_numpy())))
years = len(r) / 365
summ = dict(decision=decision, passed=passed, net=s["net_pnl"], gross=s["gross_pnl"], funding=s["funding"], fee=s["fee"], slippage=s["slippage"], sharpe=shp(r), sharpe_bh=shp(bh), ann_return=float(r.sum() / years),
            ann_vol=float(r.std() * np.sqrt(365)), p_gross=p_g, p_net=p_n, null_b=len(ng), dsr=dsr, dsr_bonf6=min(1, 6 * p_g), psr0=stats.psr(r), alpha_year=a * 365, beta=b, t_alpha=t, maxdd=dd,
            boot={L: v["maxdd"] for L, v in boot.items()}, nb={k: dict(net=float(n), sharpe=float(x)) for k, n, x in zip(nb, nb_net, nb_sh)}, halves=halves, shifts=shifts, k7=K7["summary"]["net_pnl"],
            k7_sym=K7["sym_net"], abl=sh_abl, regimes=reg, sub=sub, kill=kill, dd_peak=float(dd_peak.max()), mintrl_years=(stats.min_trl(sr_d, g3, g4) / 365 if sr_d > 0 else None),
            sym_net=main["sym_net"], stress=main["stress"], recon=main["recon"], turnover_year=main["traded"] / years / CAP, gross_mean=main["gross_notional_mean"] / CAP,
            forecast_abs_mean=main["forecast_abs_mean"], forecast_long_share=main["forecast_long_share"], cap500=P["cap500"]["summary"], cap500_sharpe=shp(ser(P["cap500"]["daily"]) / 500))
first_fail = next((k for k in passed if not passed[k]), None)
md = [f"# Ensemble v1 tabloları (otomatik): karar {decision} (ilk kalan: {first_fail})", "", "| # | test | değer | eşik | geçti |", "|---|---|---|---|---|",
      f"| K1 | rotasyon null p (brüt; B={len(ng)}) / DSR (N=6) | p={p_g:.4f} (null ort. {ng.mean():.0f} ± {ng.std():.0f}; gerçek {s['gross_pnl']:.0f}) / DSR={dsr:.3f} | p ≤ 0,05; DSR ≥ 0,95 | {k1} |",
      f"| K2 | Sharpe vs al-tut / NW alfa | {shp(r):.2f} vs {shp(bh):.2f} / a={a * 365:.3f}/yıl, b={b:.3f}, t={t:.2f} | > ve t ≥ 2 | {k2} |",
      f"| K3 | net Sharpe / fee16+slip6 / gecikme 1 | {shp(r):.2f} / {c(16, 6):.0f} / {c(10, 2, 1):.0f} | ≥ 1,0; > 0; > 0 | {k3} |",
      f"| K4 | maks DD / bootstrap DD95 (blok 10/20/40) | {pct(dd)} / {pct(boot[10]['maxdd'][1])} / {pct(boot[20]['maxdd'][1])} / {pct(boot[40]['maxdd'][1])} | ≤ %25; ≤ %30 | {k4} |",
      f"| K5 | komşu net>0 / medyan Sharpe | {pct((nb_net > 0).mean())} (n={len(nb)}) / {np.median(nb_sh):.2f} | ≥ %70; ≥ {0.5 * shp(r):.2f} | {k5} |",
      f"| K6 | pozitif pencere / kaydırma | {sum(v > 0 for v in halves.values())}/{len(halves)} / {[round(v) for v in shifts.values()]} | ≥ %60; hepsi > 0 | {k6} |",
      f"| K7 | çapraz varlık ({len(K7['syms'])} sembol) net @fee16 | {K7['summary']['net_pnl']:.0f} | > 0 | {k7} |",
      f"| K8 | Sharpe birincil vs ablasyon | {shp(r):.2f} vs " + ", ".join(f"{k} {v:.2f}" for k, v in sh_abl.items()) + f" | hepsinden büyük | {k8} |",
      f"| K9 | rejim net (bull/bear/range) | " + " / ".join(f"{reg[k]['total']:.0f} (n={reg[k]['n']})" for k in ("bull", "bear", "range")) + f" | ≥ 2 rejim ≥ 0; tek ≤ %80 | {k9} |", "| K10 | G3 | koşulmadı | — | — |", "",
      "## Ana sonuç (fee 10 + slip 2; sermaye 10 000)",
      f"net {s['net_pnl']:.0f} (brüt {s['gross_pnl']:.0f}, fee {-s['fee']:.0f}, slip {-s['slippage']:.0f}, funding {s['funding']:.0f}, çıkış {-s['exit_cost']:.0f}); yıllık getiri {pct(summ['ann_return'])}, yıllık oynaklık {pct(summ['ann_vol'])}; "
      f"dolum {s['n_fills']:.0f}, likidasyon {s['n_liq']:.0f}, red {s['n_rejected']:.0f}; yıllık devir {summ['turnover_year']:.1f}x sermaye; ort. brüt pozisyon {summ['gross_mean']:.2f}x; |F| ort. {summ['forecast_abs_mean']:.2f}, long payı {pct(summ['forecast_long_share'])}; "
      f"PSR(0) {summ['psr0']:.3f}; MinTRL {summ['mintrl_years'] if summ['mintrl_years'] is None else round(summ['mintrl_years'], 1)} yıl; tepe DD {pct(summ['dd_peak'])}; kill switch tetik %25: {kill[0.25]}, %30: {kill[0.30]}; recon {main['recon']:.2f}", "",
      "## Alt dönemler (bilgi)", "| dönem | net | Sharpe | al-tut Sharpe | alfa t | maks DD |", "|---|---|---|---|---|---|"]
md += [f"| {k} | {v['net']:.0f} | {v['sharpe']:.2f} | {v['bh_sharpe']:.2f} | {v['t_alpha']:.2f} | {pct(v['maxdd'])} |" for k, v in sub.items()]
md += ["", "## Maliyet (net)", "| fee/slip/gecikme | net |", "|---|---|"] + [f"| {k[5:]} | {v['summary']['net_pnl']:.0f} |" for k, v in P.items() if k.startswith("cost_")]
md += ["", "## Ablasyon ve komşular", "| koşu | net | Sharpe |", "|---|---|---|"] + [f"| {k} | {P[f'abl_{k}']['summary']['net_pnl']:.0f} | {sh_abl[k]:.2f} |" for k in ABL]
md += [f"| {k} | {n:.0f} | {x:.2f} |" for k, n, x in zip(nb, nb_net, nb_sh)]
md += ["", "## Pencereler (net)", "| pencere | net |", "|---|---|"] + [f"| {k} | {v:.0f} |" for k, v in {**halves, **shifts}.items()]
md += ["", "## Sembol dağılımı (net)", "| " + " | ".join(main["sym_net"]) + " |", "|" + "---|" * len(main["sym_net"]), "| " + " | ".join(f"{v:.0f}" for v in main["sym_net"].values()) + " |"]
md += ["", "## K7 sembolleri (fee 16 + slip 2; net)", "| " + " | ".join(K7["sym_net"]) + " |", "|" + "---|" * len(K7["sym_net"]), "| " + " | ".join(f"{v:.0f}" for v in K7["sym_net"].values()) + " |"]
md += ["", "## Stres pencereleri", "| pencere | " + " | ".join(next(iter(main["stress"].values()))) + " |", "|---|" + "---|" * len(next(iter(main["stress"].values())))]
md += [f"| {k} | " + " | ".join(f"{x:.3g}" if isinstance(x, (int, float)) else str(x) for x in v.values()) + " |" for k, v in main["stress"].items()]
md += ["", f"500 USD sermaye (bilgi): net {P['cap500']['summary']['net_pnl']:.2f}, Sharpe {summ['cap500_sharpe']:.2f}, red {P['cap500']['summary']['n_rejected']:.0f}, dolum {P['cap500']['summary']['n_fills']:.0f}"]
n_prev = sum(sum(1 for _ in p.open()) for d in sys.argv[3:] for p in Path(d).rglob("*.jsonl"))
md += [f"Kümülatif deneme sayısı (ledger satırları): önceki {n_prev} + bu test 1 = {n_prev + 1}."]
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "tables.md").write_text("\n".join(md))
(OUT / "summary.json").write_text(json.dumps(summ, indent=1, default=float))
print("\n".join(md))
