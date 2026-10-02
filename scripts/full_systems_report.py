"""V4 özet tabloları: scripts/full_systems.py çıktıları (JSON) -> tables.md + summary.json. Karar kuralı reports/full_systems_protocol.md'deki gibi (kart K1–K9).

  python scripts/full_systems_report.py <işçi çıktı dizini> <çıktı dizini> [kümülatif deneme için ledger dizinleri...]"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from kepler import robust, stats

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
CAP, N, SYS = 10_000.0, 12, ("S1", "S2")
VARS = ("full", "no_stop", "fixed_size", "no_pyramid", "no_limits", "g2_equiv")
ABL = ("no_stop", "fixed_size", "no_pyramid", "no_limits")
P, R, K7 = (json.loads((SRC / f).read_text()) for f in ("primary.json", "robust.json", "k7.json"))
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


daily = {(s, v): ser(P[f"{s}_{v}"]["daily"]) / CAP for s in SYS for v in VARS}
trial_srs = [stats.moments(daily[k])[0] for k in daily]  # N = 12 denemenin günlük Sharpe'ları (DSR girdisi)
sr0 = stats.sr0_from_trials(trial_srs)
bh = ser(R["bh"]["daily"]) / CAP
btc_lab = robust.regime(BTC)
summ, md = {}, ["# V4 tabloları (otomatik)", f"N = {N} deneme; DSR eşik SR0 = {sr0:.4f} (günlük; yıllık {stats.annual(sr0):.2f}); al-tut yıllık Sharpe = {shp(bh):.2f}; null B = " + ", ".join(f"{s}: {len(NULL[s])}" for s in SYS), ""]
for s in SYS:
    r, full = daily[(s, "full")], P[f"{s}_full"]["summary"]
    sr_d = stats.moments(r)[0]
    # K1
    null_g = np.array([NULL[s][i]["gross_pnl"] for i in sorted(NULL[s])])
    null_n = np.array([NULL[s][i]["net_pnl"] for i in sorted(NULL[s])])
    p_g, p_n = stats.rotation_p(full["gross_pnl"], null_g), stats.rotation_p(full["net_pnl"], null_n)
    dsr = stats.dsr(r, trial_srs)
    k1 = p_g <= 0.05 / N and dsr >= 0.95
    # K2
    rr, bb = r.align(bh, join="inner")
    a, b, t = stats.nw_alpha(rr.to_numpy(), bb.to_numpy(), 5)
    k2 = shp(r) > shp(bh) and t >= 2
    # K3
    c = lambda fee, slip, d=0: R[f"cost_{s}_{fee}_{slip}_{d}"]["summary"]["net_pnl"]  # noqa: E731
    k3 = shp(r) >= 1.0 and c(16, 6) > 0 and c(10, 2, 1) > 0
    # K4
    dd, boot = float(stats.max_drawdown(r.to_numpy())), {L: stats.bootstrap_summary(r.to_numpy(), L, 2000, 0) for L in (10, 20, 40)}
    k4 = dd <= 0.25 and boot[20]["maxdd"][1] <= 0.30
    # K5
    nb = {k: v for k, v in R.items() if k.startswith(f"nb_{s}_")}
    nb_net, nb_sh = np.array([v["summary"]["net_pnl"] for v in nb.values()]), np.array([shp(ser(v["daily"]) / CAP) for v in nb.values()])
    k5 = (nb_net > 0).mean() >= 0.7 and np.median(nb_sh) >= 0.5 * shp(r)
    # K6
    wk = {k: v["summary"]["net_pnl"] for k, v in R.items() if k.startswith(f"win_{s}_")}
    shift_starts = ("2022-03-01", "2022-04-01", "2022-05-01", "2022-06-01")
    shifts = {k: v for k, v in wk.items() if k.split("_")[2] in shift_starts}
    wins = {k: v for k, v in wk.items() if k not in shifts}
    k6 = sum(v > 0 for v in wins.values()) >= 0.6 * len(wins) and all(v > 0 for v in shifts.values())
    # K7
    k7 = K7[f"k7_{s}"]["summary"]["net_pnl"] > 0
    # K8
    sh_v = {v: shp(daily[(s, v)]) for v in VARS}
    k8 = all(sh_v["full"] > sh_v[v] for v in ABL)
    # K9
    reg = robust.by_regime(r * CAP, btc_lab)
    tot = sum(v["total"] for v in reg.values())
    k9 = sum(v["total"] >= 0 for v in reg.values()) >= 2 and tot > 0 and max(v["total"] for v in reg.values()) / tot <= 0.8
    passed = {"K1": k1, "K2": k2, "K3": k3, "K4": k4, "K5": bool(k5), "K6": k6, "K7": k7, "K8": k8, "K9": k9}
    passed = {k: bool(v) for k, v in passed.items()}
    summ[s] = dict(decision=robust.decision(passed), passed=passed, sharpe=shp(r), sharpe_bh=shp(bh), p_gross=p_g, p_net=p_n, bonf_p=stats.bonferroni(p_g, N), dsr=dsr, psr0=stats.psr(r), alpha=a, beta=b, t_alpha=t,
                   maxdd=dd, boot=boot, nb_pos=float((nb_net > 0).mean()), nb_med_sharpe=float(np.median(nb_sh)), n_nb=len(nb), wins_pos=int(sum(v > 0 for v in wins.values())), n_wins=len(wins), shifts=shifts, k7=K7[f"k7_{s}"]["summary"]["net_pnl"],
                   regimes=reg, null=dict(b=len(null_g), gross_mean=float(null_g.mean()), gross_sd=float(null_g.std()), gross_q95=float(np.quantile(null_g, .95)), net_mean=float(null_n.mean())), sh_variants=sh_v,
                   mintrl_years=(stats.min_trl(sr_d, *stats.moments(r)[1:3]) / 365 if sr_d > 0 else None))
    first_fail = next((k for k in passed if not passed[k]), None)
    md += [f"## {s}: karar {summ[s]['decision']} (ilk kalan madde: {first_fail})", "| # | test | değer | eşik | geçti |", "|---|---|---|---|---|",
           f"| K1 | rotasyon null p (brüt), B={len(null_g)} / DSR | p={p_g:.4f} (Bonf. {stats.bonferroni(p_g, N):.3f}) / DSR={dsr:.3f} | p ≤ {0.05 / N:.4f} ve DSR ≥ 0,95 | {k1} |",
           f"| K2 | Sharpe vs al-tut / NW alfa t | {shp(r):.2f} vs {shp(bh):.2f} / a={a * 365:.3f}/yıl, b={b:.2f}, t={t:.2f} | > ve t ≥ 2 | {k2} |",
           f"| K3 | net Sharpe / net@fee16+slip6 / net@gecikme1 | {shp(r):.2f} / {c(16, 6):.0f} / {c(10, 2, 1):.0f} | ≥ 1,0; > 0; > 0 | {k3} |",
           f"| K4 | maks DD / bootstrap DD %95 (blok 10/20/40) | {pct(dd)} / {pct(boot[10]['maxdd'][1])} / {pct(boot[20]['maxdd'][1])} / {pct(boot[40]['maxdd'][1])} | ≤ %25; ≤ %30 (blok 20) | {k4} |",
           f"| K5 | komşu net>0 oranı / komşu medyan Sharpe (seçilen {shp(r):.2f}) | {pct((nb_net > 0).mean())} (n={len(nb)}) / {np.median(nb_sh):.2f} | ≥ %70; ≥ {0.5 * shp(r):.2f} | {bool(k5)} |",
           f"| K6 | pozitif pencere / başlangıç kaydırma | {sum(v > 0 for v in wins.values())}/{len(wins)} / {[round(v) for v in shifts.values()]} | ≥ %60; hepsi > 0 | {k6} |",
           f"| K7 | çapraz varlık net @fee16+slip2 (14 sembol) | {K7[f'k7_{s}']['summary']['net_pnl']:.0f} | > 0 | {k7} |",
           f"| K8 | Sharpe full vs ablasyonlar | full {sh_v['full']:.2f}; " + ", ".join(f"{v} {sh_v[v]:.2f}" for v in ABL) + f" | full her birinden büyük | {k8} |",
           f"| K9 | rejim net (bull/bear/range, USDT) | " + " / ".join(f"{reg[k]['total']:.0f} (n={reg[k]['n']})" for k in ("bull", "bear", "range")) + f" | ≥ 2 rejimde ≥ 0; tek rejim ≤ %80 | {k9} |", "| K10 | G3 | koşulmadı | — | — |", ""]
md += ["## 12 deneme (fee 10 + slip 2; USDT; sermaye 10 000)", "| deneme | net | brüt | fee | slippage | funding | çıkış | likidasyon | dolum | hakem stop | yönetici taklit stop | Sharpe | maks DD | recon farkı |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for s in SYS:
    for v in VARS:
        x, m = P[f"{s}_{v}"]["summary"], P[f"{s}_{v}"]
        md.append(f"| {s}_{v} | {x['net_pnl']:.0f} | {x['gross_pnl']:.0f} | {-x['fee']:.0f} | {-x['slippage']:.0f} | {x['funding']:.0f} | {-x['exit_cost']:.0f} | {x['n_liq']:.0f} | {x['n_fills']:.0f} | {x['n_stop']:.0f} | {m['manager']['stops']} | {shp(daily[(s, v)]):.2f} | {pct(float(stats.max_drawdown(daily[(s, v)].to_numpy())))} | {m['recon']:.2f} |")
md += ["", "## Maliyet ızgarası (full; net USDT)", "| sistem | fee 4 | 9 | 10 | 11 | 16 (slip 2) | fee 10 slip 6 | fee 16 slip 6 | gecikme 1 (fee 10) |", "|---|---|---|---|---|---|---|---|---|"]
for s in SYS:
    md.append(f"| {s} | " + " | ".join(f"{R[f'cost_{s}_{f}_{sl}_{d}']['summary']['net_pnl']:.0f}" for f, sl, d in ((4, 2, 0), (9, 2, 0), (10, 2, 0), (11, 2, 0), (16, 2, 0), (10, 6, 0), (16, 6, 0), (10, 2, 1))) + " |")
md += ["", "## Pencereler ve başlangıç kaydırma (full, fee 10 + slip 2; net USDT)", "| sistem | pencere | net |", "|---|---|---|"]
for s in SYS:
    for k, v in R.items():
        if k.startswith(f"win_{s}_"):
            md.append(f"| {s} | {k.split('_', 2)[2]} | {v['summary']['net_pnl']:.0f} |")
md += ["", "## Komşuluk (full; net USDT ve yıllık Sharpe; fee 10 + slip 2)", "| sistem | giriş/çıkış | net | Sharpe |", "|---|---|---|---|"]
for s in SYS:
    for k, v in R.items():
        if k.startswith(f"nb_{s}_"):
            md.append(f"| {s} | {k.split('_', 2)[2].replace('_', '/')} | {v['summary']['net_pnl']:.0f} | {shp(ser(v['daily']) / CAP):.2f} |")
md += ["", "## Sembol dağılımı (full; net USDT, hakem fills'ten saatlik yeniden kurulum, funding dahil)", "| sistem | " + " | ".join(P["S1_full"]["sym_net"]) + " |", "|---|" + "---|" * len(P["S1_full"]["sym_net"])]
for s in SYS:
    md.append(f"| {s} | " + " | ".join(f"{v:.0f}" for v in P[f"{s}_full"]["sym_net"].values()) + " |")
md += ["", "## K7 sembol dağılımı (fee 16 + slip 2; net USDT)", "| sistem | " + " | ".join(K7["k7_S1"]["syms"]) + " |", "|---|" + "---|" * len(K7["k7_S1"]["syms"])]
for s in SYS:
    md.append(f"| {s} | " + " | ".join(f"{K7[f'k7_{s}']['sym_net'].get(y, float('nan')):.0f}" for y in K7["k7_S1"]["syms"]) + " |")
md += ["", "## Rotasyon null (brüt PnL, fee 10 + slip 2)", "| sistem | gerçek brüt | null ort. | null sd | null %95 | p (brüt) | p (net) |", "|---|---|---|---|---|---|---|"]
for s in SYS:
    n = summ[s]["null"]
    md.append(f"| {s} | {P[f'{s}_full']['summary']['gross_pnl']:.0f} | {n['gross_mean']:.0f} | {n['gross_sd']:.0f} | {n['gross_q95']:.0f} | {summ[s]['p_gross']:.4f} | {summ[s]['p_net']:.4f} |")
md += ["", "## Bilgi (karar dışı)", "| sistem | maks DD (tepe equity'ye oran) | tepe equity (sermaye=1) | geçerli null çekilişi (n_rejected=0) | p (brüt; yalnız geçerli çekilişler) | ilk-1/4 ve son-1/4 net |", "|---|---|---|---|---|---|"]
for s in SYS:
    eq = 1 + daily[(s, "full")].cumsum()
    ok = [i for i in sorted(NULL[s]) if NULL[s][i]["n_rejected"] == 0]
    pv = stats.rotation_p(P[f"{s}_full"]["summary"]["gross_pnl"], [NULL[s][i]["gross_pnl"] for i in ok])
    summ[s].update(dd_peak=float(((eq.cummax() - eq) / eq.cummax()).max()), peak_equity=float(eq.max()), null_valid=len(ok), p_gross_valid=pv)
    q = len(eq) // 4
    md.append(f"| {s} | {pct(summ[s]['dd_peak'])} | {eq.max():.2f} | {len(ok)}/{len(NULL[s])} | {pv:.4f} | {(daily[(s, 'full')].iloc[:q].sum() * CAP):.0f} / {(daily[(s, 'full')].iloc[-q:].sum() * CAP):.0f} |")
bad = [(k, v["summary"]["n_rejected"], v["summary"]["funding_missed"]) for k, v in P.items() if v["summary"]["n_rejected"] or v["summary"]["funding_missed"]]
md += ["", f"Geçersiz koşu (n_rejected/funding_missed > 0): {bad or 'yok'}; en büyük |recon farkı| = {max(abs(v['recon']) for v in P.values()):.2f} USDT; null'larda n_rejected toplamı = {sum(r['n_rejected'] for s in SYS for r in NULL[s].values()):.0f}."]
n_prev = sum(sum(1 for _ in p.open()) for d in sys.argv[3:] for p in Path(d).rglob("*.jsonl"))
md += [f"Kümülatif deneme sayısı (ledger satırları: eski {n_prev} + bu test {N} = {n_prev + N}): eleme+hakem."]
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "tables.md").write_text("\n".join(md))
(OUT / "summary.json").write_text(json.dumps(summ, indent=1, default=float))
print("\n".join(md))
