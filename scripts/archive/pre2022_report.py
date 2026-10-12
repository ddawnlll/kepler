"""2020–2021 replikasyon özet tabloları: scripts/pre2022.py çıktıları (JSON) -> tables.md + summary.json. Karar kuralı reports/pre2022_protocol.md'deki gibi.

  python scripts/pre2022_report.py <işçi çıktı dizini> <çıktı dizini>"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from kepler import robust, stats

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
CAP, N, SYS = 10_000.0, 4, ("S1", "S2", "S1c", "S2c")
ABL = ("no_stop", "fixed_size", "no_pyramid", "no_limits")
SHIFTS = ("2020-03-01", "2020-04-01", "2020-05-01", "2020-06-01")
P = json.loads((SRC / "primary.json").read_text())
R = {}
for f in sorted(SRC.glob("robust_*_of_*.json")):
    R.update(json.loads(f.read_text()))
BTC = pd.Series(json.loads((SRC / "btc_close.json").read_text()))
BTC.index = pd.to_datetime(BTC.index, utc=True)
NULL = {s: {} for s in SYS}
for f in sorted(SRC.glob("null_*.json")):
    for s, d in json.loads(f.read_text()).items():
        NULL[s].update({int(i): r for i, r in d.items()})


def ser(d):
    x = pd.Series(d, dtype=float)
    x.index = pd.to_datetime(x.index, utc=True)
    return x.sort_index()


def shp(r):
    return stats.annual(stats.moments(r)[0])


def pct(x):
    return f"{100 * x:.1f}%"


daily = {s: ser(P[f"{s}_full"]["daily"]) / CAP for s in SYS}
trial_srs = [stats.moments(daily[s])[0] for s in SYS]
bh = ser(R["bh"]["daily"]) / CAP
lab = robust.regime(BTC)
summ = {}
md = ["# 2020–2021 replikasyon tabloları (otomatik; reports/pre2022_protocol.md)", f"Blok A: N = {N}; DSR SR0 (yıllık) = {stats.annual(stats.sr0_from_trials(trial_srs)):.2f}; al-tut yıllık Sharpe = {shp(bh):.2f}, net = {R['bh']['summary']['net_pnl']:.0f}", ""]
for s in SYS:
    r, full = daily[s], P[f"{s}_full"]["summary"]
    ng = np.array([NULL[s][i]["gross_pnl"] for i in sorted(NULL[s])])
    p = stats.rotation_p(full["gross_pnl"], ng)
    dsr = stats.dsr(r, trial_srs)
    rr, bb = r.align(bh, join="inner")
    a, b, t = stats.nw_alpha(rr.to_numpy(), bb.to_numpy(), 5)
    c = lambda fee, slip, d=0: R[f"cost_{s}_{fee}_{slip}_{d}"]["summary"]["net_pnl"]  # noqa: E731
    rs = ser(P[f"{s}_scaled"]["daily"]) / CAP  # K4: planlanan (ölçekli) boyut
    dd, boot = float(stats.max_drawdown(rs.to_numpy())), stats.bootstrap_summary(rs.to_numpy(), 20, 2000, 0)
    nb = [v for k, v in R.items() if k.startswith(f"nb_{s}_")]
    nb_net, nb_sh = np.array([v["summary"]["net_pnl"] for v in nb]), np.array([shp(ser(v["daily"]) / CAP) for v in nb])
    wk = {k.split("_", 2)[2]: v["summary"]["net_pnl"] for k, v in R.items() if k.startswith(f"win_{s}_")}
    shifts = {k: v for k, v in wk.items() if k.split("_")[0] in SHIFTS and k.endswith("2022-01-01")}
    halves = {k: v for k, v in wk.items() if k not in shifts}
    k7 = R[f"k7_{s}"]["summary"]["net_pnl"]
    sh_v = {v: shp(ser(P[f"{s}_{v}"]["daily"]) / CAP) for v in ABL}
    reg = robust.by_regime(r * CAP, lab)
    tot = sum(v["total"] for v in reg.values())
    passed = dict(K1=p <= 0.05 / N and dsr >= 0.95, K2=shp(r) > shp(bh) and t >= 2, K3=shp(r) >= 1.0 and c(16, 6) > 0 and c(10, 2, 1) > 0, K4=dd <= 0.25 and boot["maxdd"][1] <= 0.30,
                  K5=(nb_net > 0).mean() >= 0.7 and np.median(nb_sh) >= 0.5 * shp(r), K6=sum(v > 0 for v in halves.values()) >= 2 and all(v > 0 for v in shifts.values()), K7=k7 > 0,
                  K8=all(shp(r) > x for x in sh_v.values()), K9=sum(v["total"] >= 0 for v in reg.values()) >= 2 and tot > 0 and max(v["total"] for v in reg.values()) / tot <= 0.8)
    passed = {k: bool(v) for k, v in passed.items()}
    summ[s] = dict(decision=robust.decision(passed), passed=passed, net=full["net_pnl"], gross=full["gross_pnl"], funding=full["funding"], sharpe=shp(r), p=p, p_dev_n12=min(1, p * 12), dsr=dsr, alpha_year=a * 365, beta=b, t_alpha=t,
                   dd_scaled=dd, boot_dd95=boot["maxdd"][1], nb_pos=float((nb_net > 0).mean()), nb_med=float(np.median(nb_sh)), halves=halves, shifts=shifts, k7=k7, abl=sh_v, regimes=reg,
                   null_mean=float(ng.mean()), null_sd=float(ng.std()), sym_net=P[f"{s}_full"]["sym_net"])
    md += [f"## {s}: {summ[s]['decision']} (ilk kalan: {next((k for k in passed if not passed[k]), '-')})", "| # | değer | eşik | geçti |", "|---|---|---|---|",
           f"| K1 | brüt p={p:.4f} (B={len(ng)}; null ort. {ng.mean():.0f} ± {ng.std():.0f}, gerçek {full['gross_pnl']:.0f}) / DSR={dsr:.3f} | p ≤ {0.05 / N:.4f}; DSR ≥ 0,95 | {passed['K1']} |",
           f"| K2 | Sharpe {shp(r):.2f} vs al-tut {shp(bh):.2f}; alfa {a * 365:.3f}/yıl, b={b:.3f}, t={t:.2f} | > ve t ≥ 2 | {passed['K2']} |",
           f"| K3 | Sharpe {shp(r):.2f}; fee16+slip6 {c(16, 6):.0f}; gecikme1 {c(10, 2, 1):.0f} | ≥ 1; > 0; > 0 | {passed['K3']} |",
           f"| K4 | ölçekli boyut maks DD {pct(dd)}; bootstrap DD95 {pct(boot['maxdd'][1])} | ≤ %25; ≤ %30 | {passed['K4']} |",
           f"| K5 | komşu net>0 {pct((nb_net > 0).mean())} (n={len(nb)}); medyan Sharpe {np.median(nb_sh):.2f} | ≥ %70; ≥ {0.5 * shp(r):.2f} | {passed['K5']} |",
           f"| K6 | yarıyıllar {[round(v) for v in halves.values()]}; kaydırma {[round(v) for v in shifts.values()]} | ≥ 2/3; hepsi > 0 | {passed['K6']} |",
           f"| K7 | çapraz varlık net @fee16 {k7:.0f} | > 0 | {passed['K7']} |",
           f"| K8 | full {shp(r):.2f} vs " + ", ".join(f"{k} {v:.2f}" for k, v in sh_v.items()) + f" | full hepsinden büyük | {passed['K8']} |",
           f"| K9 | " + " / ".join(f"{k} {reg[k]['total']:.0f} (n={reg[k]['n']})" for k in reg) + f" | ≥ 2 rejim ≥ 0; tek rejim ≤ %80 | {passed['K9']} |", ""]
md += ["## Blok A ana tablo (fee 10 + slip 2; USDT; sermaye 10 000)", "| sistem | net | brüt | funding | funding/brüt | dolum | stop | Sharpe | sembol neti |", "|---|---|---|---|---|---|---|---|---|"]
for s in SYS:
    x = P[f"{s}_full"]["summary"]
    md.append(f"| {s} | {x['net_pnl']:.0f} | {x['gross_pnl']:.0f} | {x['funding']:.0f} | {pct(-x['funding'] / x['gross_pnl'])} | {x['n_fills']:.0f} | {x['n_stop']:.0f} | {shp(daily[s]):.2f} | "
              + ", ".join(f"{k[:-4]} {v:.0f}" for k, v in P[f"{s}_full"]["sym_net"].items()) + " |")

# Blok B: 6 yapılandırma x semboller (kriter: brüt p ≤ 0,05/6 ve net > 0 fee 10 ve 16)
B = json.loads((SRC / "blockb_real.json").read_text())
BN = {}
for f in sorted(SRC.glob("blockb_null_*.json")):
    for nm, d in json.loads(f.read_text()).items():
        for sym, dd_ in d.items():
            BN.setdefault(nm, {}).setdefault(sym, {}).update(dd_)
md += ["", "## Blok B (6 yapılandırma, genişletilmiş-9, sembol başına bağımsız; kriter p ≤ 0,0083 ve net > 0 @fee 10 ve 16)",
       "| yapılandırma | brüt | net fee4 | net fee10 | net fee16 | net fee10 slip6 | null ort. | p (brüt) | Bonf. ×6 | Sharpe | alfa t | kriter |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
summ["blockb"] = {}
for nm, syms in B["real"].items():
    net = lambda fee, slip=2.0: sum(r["net_pnl"] for rows in syms.values() for r in rows if r["fee_bps"] == fee and r["slip_bps"] == slip)  # noqa: E731
    gross = sum([r for r in rows if r["fee_bps"] == 10 and r["slip_bps"] == 2.0][0]["gross_pnl"] for rows in syms.values())
    keys = sorted(set.intersection(*[set(BN[nm][s]) for s in syms]), key=int)
    nul = np.array([sum(BN[nm][s][k]["gross_pnl"] for s in syms) for k in keys])
    p = stats.rotation_p(gross, nul)
    d = pd.concat([ser([r for r in rows if r["fee_bps"] == 10 and r["slip_bps"] == 2.0][0]["daily"]) for rows in syms.values()], axis=1).fillna(0.0).sum(axis=1)  # geç listelenen sembol: öncesi 0
    cap = 1000.0 * len(syms)  # g2.NOTIONAL x sembol sayısı (Sharpe/alfa t ölçekten bağımsız)
    dr, bb = (d / cap).align(bh, join="inner")
    _, _, t = stats.nw_alpha(dr.to_numpy(), bb.to_numpy(), 5)
    ok = bool(p <= 0.05 / 6 and net(10) > 0 and net(16) > 0)
    summ["blockb"][nm] = dict(gross=gross, net10=net(10), net16=net(16), p=p, bonf=min(1, 6 * p), sharpe=shp(d / cap), t_alpha=t, null_mean=float(nul.mean()), b=len(nul), passed=ok)
    md.append(f"| {nm} | {gross:.0f} | {net(4):.0f} | {net(10):.0f} | {net(16):.0f} | {net(10, 6.0):.0f} | {nul.mean():.0f} | {p:.4f} | {min(1, 6 * p):.3f} | {shp(d / cap):.2f} | {t:.2f} | {ok} |")
md += ["", f"Geçersiz Blok A koşusu (n_rejected/funding_missed > 0): {[k for k, v in P.items() if v['summary']['n_rejected'] or v['summary']['funding_missed']] or 'yok'}; Blok B defter dışı (ledger=False) satır: "
       f"{sum(1 for rows in (r for syms in B['real'].values() for r in syms.values()) for x in rows if x.get('ledger') is False)}."]
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "tables.md").write_text("\n".join(md))
(OUT / "summary.json").write_text(json.dumps(summ, indent=1, default=float))
print("\n".join(md))
