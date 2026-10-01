"""G2 özet tabloları (Modal'de koşar): /data/g2/<job>.json -> /data/g2/tables.md + summary.json. Karar kuralı (MISSION G2): ADAY = brüt PnL rotasyon null'ının
dışında (tek yönlü p <= 0.05) VE ızgaranın en az bir fee senaryosunda net > 0; ayrıca düzeltilmiş p (Bonferroni, 12 yapılandırma) ve DSR raporlanır."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/data/g2")
CORE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]
NOTIONAL = 1000.0
J = {p.stem: json.loads(p.read_text()) for p in OUT.glob("*.json") if p.stem not in ("summary",)}
CFG = {}  # (ad, evren) -> (job, semboller)
for j, d in J.items():
    if j.startswith("dual_mom"):
        CFG[(j, "5" if j.endswith("_5") else "9")] = (j, d["syms"])
    else:
        CFG[(j, "çekirdek-5")], CFG[(j, "genişletilmiş-9")] = (j, CORE), (j, d["syms"])
KEYS = ("gross_pnl", "net_pnl", "fee", "slippage", "funding", "exit_cost", "liq_fee", "traded", "n_fills", "n_liq")


def agg(rows):
    return {k: float(sum(r[k] for r in rows)) for k in KEYS}


def scen(job, syms, fee, slip=2.0):
    return agg([next(x for x in J[job]["real"][s]["full"] if x["fee_bps"] == fee and x["slip_bps"] == slip) for s in syms])


def daily(job, syms):
    base = [next(x for x in J[job]["real"][s]["full"] if x["fee_bps"] == 10 and x["slip_bps"] == 2.0)["daily"] for s in syms]
    return pd.DataFrame(base).T.sum(axis=1).sort_index() / (len(syms) * NOTIONAL)


def sharpe_stats(r):
    sr = r.mean() / r.std()
    return sr, float(((r - r.mean()) ** 3).mean() / r.std(ddof=0) ** 3), float(((r - r.mean()) ** 4).mean() / r.std(ddof=0) ** 4), len(r)


rows, S = [], {}
for (name, uni), (job, syms) in CFG.items():
    sr, sk, ku, T = sharpe_stats(daily(job, syms))
    S[(name, uni)] = (sr, sk, ku, T)
N = len(CFG)
g = 0.5772156649
sr0 = np.std([v[0] for v in S.values()], ddof=1) * ((1 - g) * norm.ppf(1 - 1 / N) + g * norm.ppf(1 - 1 / (N * np.e)))
md = ["# G2 tabloları (otomatik)", f"Yapılandırma sayısı N={N}; DSR eşiği SR0={sr0:.4f} (günlük, yıllık {sr0 * np.sqrt(365):.2f}); null çekiliş sayısı B={next(iter(J.values()))['b']}.", ""]
head = "| sinyal | evren | brüt PnL | brüt bps/RT | net PnL @fee4/9/10/11/16 (slip 2) | net @fee10 slip6 | funding | p(brüt) | p(net@10) | Bonf. p | Sharpe(y) | DSR | karar |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|"
md.append(head)
summ = {}
for (name, uni), (job, syms) in CFG.items():
    sc = {f: scen(job, syms, f) for f in (4, 9, 10, 11, 16)}
    hi = scen(job, syms, 10, 6.0)
    base = sc[10]
    ng = np.array([sum(J[job]["null"][s][str(i)]["gross_pnl"] for s in syms) for i in range(J[job]["b"])])
    nn = np.array([sum(J[job]["null"][s][str(i)]["net_pnl"] for s in syms) for i in range(J[job]["b"])])
    pg, pn = (1 + (ng >= base["gross_pnl"]).sum()) / (len(ng) + 1), (1 + (nn >= base["net_pnl"]).sum()) / (len(nn) + 1)
    sr, sk, ku, T = S[(name, uni)]
    dsr = norm.cdf((sr - sr0) * np.sqrt(T - 1) / np.sqrt(1 - sk * sr + (ku - 1) / 4 * sr**2))
    rt = base["traded"] / 2
    cand = pg <= 0.05 and any(v["net_pnl"] > 0 for v in sc.values())
    summ[f"{name}|{uni}"] = dict(cand=bool(cand), p_gross=pg, p_net=pn, dsr=float(dsr), sharpe=float(sr * np.sqrt(365)), gross=base["gross_pnl"], rt_notional=rt, sc=sc, hi=hi,
                                 null_gross_mean=float(ng.mean()), null_gross_sd=float(ng.std()), null_gross_q95=float(np.quantile(ng, .95)), null_net_mean=float(nn.mean()))
    md.append(f"| {name} | {uni} | {base['gross_pnl']:.0f} | {base['gross_pnl'] / rt * 1e4:.1f} | " + " / ".join(f"{sc[f]['net_pnl']:.0f}" for f in (4, 9, 10, 11, 16))
              + f" | {hi['net_pnl']:.0f} | {base['funding']:.0f} | {pg:.3f} | {pn:.3f} | {min(1, pg * N):.2f} | {sr * np.sqrt(365):.2f} | {dsr:.2f} | {'ADAY' if cand else 'yok'} |")
md += ["", "## Maliyet kalemleri (fee 10 bps rt, slip 2 bps rt; USDT, sembol başına notional 1000; işareti: PnL'ye etkisi)",
       "| sinyal | evren | brüt fiyat PnL | fee | slippage | çıkış | funding | likidasyon | net | RT notional | işlem (fill) | brüt+funding bps/RT (kırılma maliyeti) |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for (name, uni), (job, syms) in CFG.items():
    b = summ[f"{name}|{uni}"]["sc"][10]
    rt = b["traded"] / 2
    md.append(f"| {name} | {uni} | {b['gross_pnl']:.0f} | {-b['fee']:.0f} | {-b['slippage']:.0f} | {-b['exit_cost']:.0f} | {b['funding']:.0f} | {-b['liq_fee']:.0f} | {b['net_pnl']:.0f} | {rt:.0f} | {b['n_fills']:.0f} | {(b['gross_pnl'] + b['funding']) / rt * 1e4:.1f} |")
W = [w["window"] for w in J[next(iter(J))]["real"]["BTCUSDT"]["windows"]]
md += ["", "## Walk-forward: yarıyıl pencereleri (fee 10, slip 2; net PnL USDT; sabit kural, pencere başında pozisyon devri açık hedef)", "| sinyal | evren | " + " | ".join(W) + " | pozitif pencere |", "|---|---|" + "---|" * (len(W) + 1)]
WN = {}
for (name, uni), (job, syms) in CFG.items():
    v = [sum(J[job]["real"][s]["windows"][k]["net_pnl"] for s in syms) for k in range(len(W))]
    WN[(name, uni)] = v
    md.append(f"| {name} | {uni} | " + " | ".join(f"{x:.0f}" for x in v) + f" | {sum(x > 0 for x in v)}/{len(v)} |")
sel, avg = [], []
for k in range(2, len(W)):  # genişleyen eğitim: önceki pencerelerin kümülatif net'i en yüksek yapılandırma sonraki pencerede
    best = max(WN, key=lambda c: sum(WN[c][:k]))
    sel.append((W[k], best, WN[best][k]))
    avg.append(np.mean([WN[c][k] for c in WN]))
md += ["", "Walk-forward seçimi (eğitim = önceki pencerelerin toplamı; test = sonraki pencere): " + "; ".join(f"{w}: {b[0]}/{b[1]} → {x:.0f}" for w, b, x in sel),
       f"Seçilen toplam (OOS) = {sum(x for _, _, x in sel):.0f}; aynı pencerelerde tüm yapılandırmaların ortalaması toplamı = {sum(avg):.0f}."]
(OUT / "tables.md").write_text("\n".join(md))
(OUT / "summary.json").write_text(json.dumps(summ, indent=1))
print("\n".join(md))
