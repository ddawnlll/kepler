"""Arama özeti (Modal'de koşar): /data/search/*.json -> tables.md. Kriter reports/search_protocol.md'de sabit."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, spearmanr

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/data/search")
FAMS = ("donchian", "ema", "tsmom", "xs_mom", "xs_carry", "xs_rev")
NOT, G = 1000.0, 0.5772156649


def stats(daily_by_sym, n):
    r = pd.DataFrame(daily_by_sym).sum(axis=1).sort_index() / (n * NOT)  # sütun = sembol, indeks = gün
    sr = r.mean() / r.std() if r.std() > 0 else 0.0
    return sr, float(((r - r.mean()) ** 3).mean() / r.std(ddof=0) ** 3) if r.std() > 0 else 0.0, float(((r - r.mean()) ** 4).mean() / r.std(ddof=0) ** 4) if r.std() > 0 else 3.0, len(r)


def dsr(sr, sk, ku, T, sr0):
    return float(norm.cdf((sr - sr0) * np.sqrt(T - 1) / np.sqrt(max(1e-9, 1 - sk * sr + (ku - 1) / 4 * sr**2))))


rows = []
for fam in FAMS:
    d = json.loads((OUT / f"search_{fam}.json").read_text())
    for n, per in d["res"].items():
        net, gross, traded = (sum(v[k] for v in per.values()) for k in ("net_pnl", "gross_pnl", "traded"))
        sr, sk, ku, T = stats({s: v["daily"] for s, v in per.items()}, len(per))
        rows.append(dict(fam=fam, name=n, net=net, gross=gross, funding=sum(v["funding"] for v in per.values()), rt=traded / 2, gbps=gross / (traded / 2) * 1e4 if traded else 0.0,
                         sr=sr * np.sqrt(365), sr_d=sr, sk=sk, ku=ku, T=T, screen=sum(d["screen"][n].values()), fills=sum(v["n_fills"] for v in per.values())))
df = pd.DataFrame(rows)
N = len(df)
sr0 = df.sr_d.std(ddof=1) * ((1 - G) * norm.ppf(1 - 1 / N) + G * norm.ppf(1 - 1 / (N * np.e)))
df["dsr"] = [dsr(r.sr_d, r.sk, r.ku, r.T, sr0) for r in df.itertuples()]
md = [f"# Arama tabloları (otomatik)", f"N={N} yapılandırma (arama dönemi 2022-01→2025-01, fee 10 + slip 2, sembol başına notional {NOT:.0f}, 9 sembol toplamı). SR0 (deneme-düzeltme eşiği) = {sr0 * np.sqrt(365):.2f} yıllık.", ""]
rho, rho_p = spearmanr(df.screen, df.net)
md += [f"## Eleme–hakem uyumu (N={N}, fee-baskın olmayan geniş ızgara): Spearman {rho:.3f} (p={rho_p:.2g}); aile içi: " + ", ".join(f"{f} {spearmanr(g.screen, g.net)[0]:.2f}" for f, g in df.groupby("fam") if len(g) > 3) + ". Öneri eşiği ≥0,8 (doğrulanmadı).", "",
       "## Aile başına en iyi 3 (arama dönemi net; seçim yanlılığı içerir)", "| aile | yapılandırma | net | brüt bps/RT | funding | Sharpe(y) | DSR(N=88) | RT notional |", "|---|---|---|---|---|---|---|---|"]
for f in FAMS:
    for r in df[df.fam == f].sort_values("net", ascending=False).head(3).itertuples():
        md.append(f"| {f} | {r.name} | {r.net:.0f} | {r.gbps:.0f} | {r.funding:.0f} | {r.sr:.2f} | {r.dsr:.2f} | {r.rt:.0f} |")
md += ["", f"Arama döneminde net>0 olan yapılandırma: {int((df.net > 0).sum())}/{N}; ortalama net {df.net.mean():.0f}; medyan {df.net.median():.0f}."]
vps = sorted(OUT.glob("validate_*.json"))
summ = {}
if vps:
    v = dict(best={}, real={}, null={}, b=0)
    for vp in vps:
        w = json.loads(vp.read_text())
        v["best"] |= w["best"]
        v["real"] |= w["real"]
        v["null"] |= w["null"]
        v["b"] = w["b"]
    md += ["", "## Doğrulama dönemi (2025-01→2026-04): aile-başına arama-seçilmiş yapılandırma, tek atış", "| aile | yapılandırma | brüt | net @fee4/9/10/11/16 (slip2) | net @10 slip6 | p(brüt, ortak-ofset null) | Bonf.(×6) p | Sharpe(y) | DSR(N=6) | karar |", "|---|---|---|---|---|---|---|---|---|---|"]
    vs, valsr = {}, {}
    for fam, nm in v["best"].items():
        rr = v["real"][nm]
        sc = {(x["fee_bps"], x["slip_bps"]): sum(rr[s][i]["net_pnl"] for s in rr) for i in range(6) for x in [rr[next(iter(rr))][i]]}
        gross = sum(rr[s][2]["gross_pnl"] for s in rr)
        ng = np.array([sum(v["null"][nm][s][str(i)]["gross_pnl"] for s in rr) for i in range(v["b"])])
        p = (1 + (ng >= gross).sum()) / (len(ng) + 1)
        sr, sk, ku, T = stats({s: rr[s][2]["daily"] for s in rr}, len(rr))
        vs[fam] = (sr, sk, ku, T)
        cand = p <= 0.05 / 6 and sc[(10, 2.0)] > 0 and sc[(16, 2.0)] > 0
        summ[fam] = dict(name=nm, gross=gross, p=p, sr=sr * np.sqrt(365), net=sc, cand=bool(cand), null_mean=float(ng.mean()), null_sd=float(ng.std()))
        valsr[fam] = sr
    sr0v = np.std(list(valsr.values()), ddof=1) * ((1 - G) * norm.ppf(1 - 1 / 6) + G * norm.ppf(1 - 1 / (6 * np.e)))
    for fam, s in summ.items():
        sr, sk, ku, T = vs[fam]
        s["dsr6"], s["dsr88"] = dsr(sr, sk, ku, T, sr0v), dsr(sr, sk, ku, T, sr0)
        md.append(f"| {fam} | {s['name']} | {s['gross']:.0f} | " + " / ".join(f"{s['net'][(f, 2.0)]:.0f}" for f in (4, 9, 10, 11, 16)) + f" | {s['net'][(10, 6.0)]:.0f} | {s['p']:.3f} | {min(1, s['p'] * 6):.2f} | {s['sr']:.2f} | {s['dsr6']:.2f} | {'ADAY' if s['cand'] else 'yok'} |")
    md.append("")
    md.append(f"Doğrulama DSR (N=88 arama eşiğiyle): " + ", ".join(f"{f} {s['dsr88']:.2f}" for f, s in summ.items()))
(OUT / "tables.md").write_text("\n".join(md))
for s_ in summ.values():
    s_["net"] = {f"{k[0]}|{k[1]}": x for k, x in s_["net"].items()}
(OUT / "summary.json").write_text(json.dumps(dict(summary=summ, search=df.drop(columns=["sk", "ku"]).to_dict("records")), indent=1))
print("\n".join(md))
