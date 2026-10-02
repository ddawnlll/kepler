"""Zone Fade v1 özet tabloları: scripts/zone_fade.py çıktıları (JSON) -> tables.md + summary.json. Kart ve karar kuralı reports/zone_fade_protocol.md'deki gibi (N = 1).

  python scripts/zone_fade_report.py <işçi çıktı dizini> <çıktı dizini> [kümülatif deneme için ledger dizinleri...]"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from kepler import robust, stats

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
CAP, MAIN_START, END = 10_000.0, "2022-07-01", "2026-04-01"
ABL = ("no_impulse", "no_trigger", "no_poc", "no_rr")
SHIFT_STARTS = ("2022-07-01", "2022-08-01", "2022-09-01", "2022-10-01")
MIN_TRADES = 60
P = {}
for f in sorted(SRC.glob("primary*.json")):
    P.update(json.loads(f.read_text()))
K7 = json.loads((SRC / "k7.json").read_text())
SEC = json.loads((SRC / "second.json").read_text())
BTC = pd.Series(json.loads((SRC / "btc_close.json").read_text()))
BTC.index = pd.to_datetime(BTC.index, utc=True)
NULL, NULL_ABS = {}, {}
for f in sorted(SRC.glob("null_rel_*.json")):
    NULL.update({int(i): r for i, r in json.loads(f.read_text()).items()})
for f in sorted(SRC.glob("null_abs_*.json")):
    NULL_ABS.update({int(i): r for i, r in json.loads(f.read_text()).items()})


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
bh = ser(P["bh"]["daily"]) / CAP
lab = robust.regime(BTC)
s = main["summary"]
tr = pd.DataFrame(main["trades"])
cd = pd.DataFrame(main["cands"])
n_trades = len(tr)
# K1 (N = 1: eşik p <= 0,05; DSR = PSR(0) >= 0,95)
ng, nn = np.array([NULL[i]["gross_pnl"] for i in sorted(NULL)]), np.array([NULL[i]["net_pnl"] for i in sorted(NULL)])
p_g, p_n = stats.rotation_p(s["gross_pnl"], ng), stats.rotation_p(s["net_pnl"], nn)
dsr = stats.psr(r)
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
shifts = {k: v for k, v in wk.items() if k.split("_")[0] in SHIFT_STARTS and k.endswith(END)}
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
decision = "YETERSİZ ÖRNEK" if n_trades < MIN_TRADES else robust.decision(passed)
first_fail = next((k for k in passed if not passed[k]), None)
sr_d, g3, g4, _ = stats.moments(r)
n_prev = sum(sum(1 for _ in p.open()) for d in sys.argv[3:] for p in Path(d).rglob("*.jsonl"))
M = n_prev + 1
# bilgi: işlem düzeyi
cand_by_entry = {(x["sym"], x["t_entry"]): x for x in main["cands"] if x["state"] in ("KAPALI", "POZISYONDA")}
tr["R"] = np.nan
tr["va"] = ""
tr["why"] = ""
for i, x in tr.iterrows():
    cnd = cand_by_entry.get((x.sym, x.opened))
    if cnd:
        tr.loc[i, "R"] = x.pnl / (x.notional * abs(cnd["ref"] - cnd["stop"]) / cnd["ref"])  # ~R: pnl / planlanan işlem riski (tetik kapanışı ile stop mesafesi)
        tr.loc[i, "va"], tr.loc[i, "why"] = cnd["va"], cnd["why"]
win_c = cd[cd.born >= MAIN_START]
pos = win_c[win_c.state.isin(["KAPALI", "POZISYONDA"])]
funnel = win_c.groupby(["state", "why"]).size().to_dict()
by = lambda col: {k: dict(n=int(len(g)), net=float(g.pnl.sum()), win=float((g.pnl > 0).mean()), R=float(g.R.mean())) for k, g in tr.groupby(col)}  # noqa: E731
info = dict(n_trades=n_trades, win_rate=float((tr.pnl > 0).mean()) if n_trades else None, avg_R=float(tr.R.mean()) if n_trades else None, avg_bps=float(tr.gross_bps.mean()) if n_trades else None,
            by_side=by("side"), by_sym=by("sym"), by_va=by("va"), by_exit=by("why"), manager_positions=int(len(pos)), manager_stops=int((pos.why == "stop").sum()), hakem_n_stop=s["n_stop"],
            funnel={f"{k[0]}/{k[1]}": v for k, v in funnel.items()}, sym_net=main["sym_net"])
sec_r, sec_bh = ser(SEC["daily"]) / CAP, ser(SEC["bh"]["daily"]) / CAP
sec_tr = pd.DataFrame(SEC["trades"])
sec = dict(net=SEC["summary"]["net_pnl"], gross=SEC["summary"]["gross_pnl"], n_trades=len(sec_tr), sharpe=shp(sec_r), bh_sharpe=shp(sec_bh), bh_net=SEC["bh"]["summary"]["net_pnl"], maxdd=float(stats.max_drawdown(sec_r.to_numpy())),
           n_stop=SEC["summary"]["n_stop"], win_rate=float((sec_tr.pnl > 0).mean()) if len(sec_tr) else None)
years = len(r) / 365
summ = dict(decision=decision, first_fail=first_fail, passed=passed, n_trades=n_trades, net=s["net_pnl"], gross=s["gross_pnl"], funding=s["funding"], fee=s["fee"], slippage=s["slippage"], exit_cost=s["exit_cost"],
            sharpe=shp(r), sharpe_bh=shp(bh), ann_return=float(r.sum() / years), ann_vol=float(r.std() * np.sqrt(365)), p_gross=p_g, p_net=p_n, null_b=len(ng), null_mean=float(ng.mean()), null_sd=float(ng.std()),
            dsr_n1=dsr, bonf_M=min(1, M * p_g), M=M, alpha_year=a * 365, beta=b, t_alpha=t, maxdd=dd, boot={L: v["maxdd"] for L, v in boot.items()},
            nb={k: dict(net=float(n), sharpe=float(x)) for k, n, x in zip(nb, nb_net, nb_sh)}, halves=halves, shifts=shifts, k7=K7["summary"]["net_pnl"], k7_sym=K7["sym_net"], k7_trades=K7.get("n_trades"),
            abl=sh_abl, abl_trades={k: P[f"abl_{k}"]["n_trades"] for k in ABL}, regimes=reg, info=info, second=sec, recon=main["recon"], cost={k[5:]: v["summary"]["net_pnl"] for k, v in P.items() if k.startswith("cost_")},
            mintrl_years=(stats.min_trl(sr_d, g3, g4) / 365 if sr_d > 0 else None), turnover_year=main["traded"] / years / CAP,
            p_gross_abs=(stats.rotation_p(s["gross_pnl"], np.array([NULL_ABS[i]["gross_pnl"] for i in sorted(NULL_ABS)])) if NULL_ABS else None), null_abs_b=len(NULL_ABS))
md = [f"# Zone Fade v1 tabloları (otomatik): karar {decision} (ilk kalan: {first_fail}; işlem {n_trades}, eşik {MIN_TRADES})", "", "| # | test | değer | eşik | geçti |", "|---|---|---|---|---|",
      f"| K1 | rotasyon null p (brüt; B={len(ng)}) / DSR (N=1, PSR(0)) | p={p_g:.4f} (null ort. {ng.mean():.0f} ± {ng.std():.0f}; gerçek {s['gross_pnl']:.0f}) / DSR={dsr:.3f} | p ≤ 0,05; DSR ≥ 0,95 | {k1} |",
      f"| K2 | Sharpe vs al-tut / NW alfa | {shp(r):.2f} vs {shp(bh):.2f} / a={a * 365:.3f}/yıl, b={b:.3f}, t={t:.2f} | > ve t ≥ 2 | {k2} |",
      f"| K3 | net Sharpe / fee16+slip6 / gecikme 1 | {shp(r):.2f} / {c(16, 6):.0f} / {c(10, 2, 1):.0f} | ≥ 1,0; > 0; > 0 | {k3} |",
      f"| K4 | maks DD / bootstrap DD95 (blok 10/20/40) | {pct(dd)} / {pct(boot[10]['maxdd'][1])} / {pct(boot[20]['maxdd'][1])} / {pct(boot[40]['maxdd'][1])} | ≤ %25; ≤ %30 | {k4} |",
      f"| K5 | komşu net>0 / medyan Sharpe | {pct((nb_net > 0).mean())} (n={len(nb)}) / {np.median(nb_sh):.2f} | ≥ %70; ≥ {0.5 * shp(r):.2f} | {k5} |",
      f"| K6 | pozitif pencere / kaydırma | {sum(v > 0 for v in halves.values())}/{len(halves)} / {[round(v) for v in shifts.values()]} | ≥ %60; hepsi > 0 | {k6} |",
      f"| K7 | çapraz varlık ({len(K7['syms'])} sembol) net @fee16 | {K7['summary']['net_pnl']:.0f} | > 0 | {k7} |",
      f"| K8 | Sharpe birincil vs ablasyon | {shp(r):.2f} vs " + ", ".join(f"{k} {v:.2f}" for k, v in sh_abl.items()) + f" | hepsinden büyük | {k8} |",
      f"| K9 | rejim net (bull/bear/range) | " + " / ".join(f"{reg[k]['total']:.0f} (n={reg[k]['n']})" for k in ("bull", "bear", "range")) + f" | ≥ 2 rejim ≥ 0; tek ≤ %80 | {k9} |", "| K10 | G3 | koşulmadı (mühür açılmaz) | — | — |", "",
      "## Ana sonuç (fee 10 + slip 2; sermaye 10 000)",
      f"net {s['net_pnl']:.0f} (brüt {s['gross_pnl']:.0f}, fee {-s['fee']:.0f}, slip {-s['slippage']:.0f}, funding {s['funding']:.0f}, çıkış {-s['exit_cost']:.0f}); yıllık getiri {pct(summ['ann_return'])}, yıllık oynaklık {pct(summ['ann_vol'])}; "
      f"dolum {s['n_fills']:.0f}, hakem stop {s['n_stop']:.0f}, likidasyon {s['n_liq']:.0f}, red {s['n_rejected']:.0f}; yıllık devir {summ['turnover_year']:.1f}x sermaye; PSR(0) {dsr:.3f}; MinTRL "
      f"{summ['mintrl_years'] if summ['mintrl_years'] is None else round(summ['mintrl_years'], 1)} yıl; Bonferroni (M={M}) p={min(1, M * p_g):.3f}; DSR(N=M): doğrulanmadı (defterde deneme Sharpe'ları yok); recon {main['recon']:.2g}",
      f"Protokol lafzıyla (mutlak stop) rotasyon null'ı (bilgi): " + (f"p={summ['p_gross_abs']:.4f} (B={len(NULL_ABS)})" if NULL_ABS else "koşulmadı"), "",
      "## İşlemler (hakem; bilgi)", f"işlem {n_trades}; kazanma {pct(info['win_rate']) if n_trades else '-'}; ort. R (yaklaşık, planlanan risk) {info['avg_R']:.2f}; ort. brüt {info['avg_bps']:.0f} bps; yönetici pozisyon {len(pos)}, yönetici stop taklidi {info['manager_stops']}, hakem stop {s['n_stop']:.0f}"
      if n_trades else "işlem yok", "", "aday hunisi (doğum ≥ 2022-07-01): " + ", ".join(f"{k} {v}" for k, v in sorted(info["funnel"].items())), ""]
for name in ("by_side", "by_exit", "by_va", "by_sym"):
    md += [f"| {name[3:]} | işlem | net | kazanma | ort. R |", "|---|---|---|---|---|"] + [f"| {k or '-'} | {v['n']} | {v['net']:.0f} | {pct(v['win'])} | {v['R']:.2f} |" for k, v in info[name].items()] + [""]
md += ["## Alt pencere: 2020-07 → 2022-01 (bilgi, görülmüş veri)", f"net {sec['net']:.0f} (brüt {sec['gross']:.0f}); işlem {sec['n_trades']}; Sharpe {sec['sharpe']:.2f} (al-tut {sec['bh_sharpe']:.2f}, net {sec['bh_net']:.0f}); maks DD {pct(sec['maxdd'])}; hakem stop {sec['n_stop']:.0f}", "",
       "## Maliyet (net)", "| fee/slip/gecikme | net |", "|---|---|"] + [f"| {k} | {v:.0f} |" for k, v in summ["cost"].items()]
md += ["", "## Ablasyon ve komşular", "| koşu | net | Sharpe | işlem |", "|---|---|---|---|"] + [f"| {k} | {P[f'abl_{k}']['summary']['net_pnl']:.0f} | {sh_abl[k]:.2f} | {P[f'abl_{k}']['n_trades']} |" for k in ABL]
md += [f"| nb {k} | {n:.0f} | {x:.2f} | {nb[k]['n_trades']} |" for k, n, x in zip(nb, nb_net, nb_sh)]
md += ["", "## Pencereler (net)", "| pencere | net |", "|---|---|"] + [f"| {k} | {v:.0f} |" for k, v in {**halves, **shifts}.items()]
md += ["", "## Sembol dağılımı (net)", "| " + " | ".join(main["sym_net"]) + " |", "|" + "---|" * len(main["sym_net"]), "| " + " | ".join(f"{v:.0f}" for v in main["sym_net"].values()) + " |"]
md += ["", "## K7 sembolleri (fee 16 + slip 2; net)", "| " + " | ".join(K7["sym_net"]) + " |", "|" + "---|" * len(K7["sym_net"]), "| " + " | ".join(f"{v:.0f}" for v in K7["sym_net"].values()) + " |"]
md += ["", f"Kümülatif deneme sayısı (ledger satırları): önceki {n_prev} + bu test 1 = {M}."]
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "tables.md").write_text("\n".join(md))
(OUT / "summary.json").write_text(json.dumps(summ, indent=1, default=float))
print("\n".join(md))
