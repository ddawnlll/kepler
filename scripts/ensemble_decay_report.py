"""EV1 sönme testi özeti (reports/ensemble_decay_protocol.md): scripts/ensemble.py decay_* çıktıları -> tables.md + summary.json. Karar kuralı protokoldeki gibi.

  python scripts/ensemble_decay_report.py <decay çıktı dizini> <tam dönem çıktı dizini (primary.json)> <çıktı dizini>"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from kepler import stats

SRC, FULL, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
CAP, LO, HI = 10_000.0, "2022-01-01", "2026-04-01"
ABL = ("trend_only", "no_xs", "no_carry", "no_risk", "no_buffer")
B = 300


def ser(d):
    x = pd.Series(d, dtype=float)
    x.index = pd.to_datetime(x.index, utc=True)
    return x.sort_index()


def w2(x):
    return x[(x.index >= LO) & (x.index < HI)]


def shp(r):
    return stats.annual(stats.moments(r)[0])


def null_of(rot):
    d = {}
    for f in sorted(SRC.glob(f"decay_null_{rot}_*.json")):
        d.update({int(i): r for i, r in json.loads(f.read_text()).items()})
    assert sorted(d) == list(range(B)), f"{rot}: {len(d)} çekiliş, beklenen {B} (0..{B - 1})"
    return d


real, P = json.loads((SRC / "decay_real.json").read_text()), json.loads((FULL / "primary.json").read_text())
nw, nf = null_of("window"), null_of("full")
s = real["summary"]
ng, nn = np.array([nw[i]["gross_pnl"] for i in range(B)]), np.array([nw[i]["net_pnl"] for i in range(B)])
fg, fn = np.array([nf[i]["gross_pnl"] for i in range(B)]), np.array([nf[i]["net_pnl"] for i in range(B)])
p_g, p_n, pf_g, pf_n = (stats.rotation_p(s["gross_pnl"], ng), stats.rotation_p(s["net_pnl"], nn), stats.rotation_p(s["gross_pnl"], fg), stats.rotation_p(s["net_pnl"], fn))
r_run = ser(real["daily"]) / CAP  # W2'de taze hakem koşusu
r = w2(ser(P["main"]["daily"]) / CAP)  # tam dönem koşusunun W2 dilimi (DSR için)
abl = {k: w2(ser(P[f"abl_{k}"]["daily"]) / CAP) for k in ABL}
trial_srs = [stats.moments(r)[0]] + [stats.moments(x)[0] for x in abl.values()]  # N = 6, protokol
dsr = stats.dsr(r, trial_srs)
bh = w2(ser(P["bh"]["daily"]) / CAP)
rr, bb = r.align(bh, join="inner")
a, b, t = stats.nw_alpha(rr.to_numpy(), bb.to_numpy(), 5)
verdict = "EDGE SÜRÜYOR (W2)" if p_g <= 0.05 and dsr >= 0.95 else "KANITSIZ (W2)"
pct = lambda x: f"{100 * x:.1f}%"  # noqa: E731
q = lambda x: np.quantile(x, [0.5, 0.95, 0.99])  # noqa: E731
summ = dict(verdict=verdict, p_gross=p_g, p_net=p_n, dsr=dsr, null_b=B, real_gross=s["gross_pnl"], real_net=s["net_pnl"], sharpe_run=shp(r_run), sharpe_slice=shp(r), bh_sharpe=shp(bh), alpha_year=a * 365, beta=b, t_alpha=t,
            maxdd_slice=float(stats.max_drawdown(r.to_numpy())), slice_net=float(r.sum() * CAP), run_net=float(r_run.sum() * CAP), info=dict(p_gross_full_rotation=pf_g, p_net_full_rotation=pf_n),
            trial_sharpes_annual=[stats.annual(x) for x in trial_srs], row_trial=real["row_trial"], n_fills=s["n_fills"], n_rejected=s["n_rejected"], n_liq=s["n_liq"], funding=s["funding"], fee=s["fee"], slippage=s["slippage"],
            null_window=dict(gross_mean=float(ng.mean()), gross_std=float(ng.std()), net_mean=float(nn.mean()), q=[float(x) for x in q(ng)]), null_full=dict(gross_mean=float(fg.mean()), gross_std=float(fg.std()), net_mean=float(fn.mean()), q=[float(x) for x in q(fg)]))
md = [f"# EV1 sönme testi (W2 = {LO} → {HI}, otomatik): {verdict}", "",
      "| ölçü | değer | eşik | geçti |", "|---|---|---|---|",
      f"| brüt p (birincil: W2 içinde rotasyon; B={B}) | p={p_g:.4f} (null ort. {ng.mean():.0f} ± {ng.std():.0f}, medyan/95p/99p {q(ng)[0]:.0f}/{q(ng)[1]:.0f}/{q(ng)[2]:.0f}; gerçek {s['gross_pnl']:.0f}) | ≤ 0,05 | {p_g <= 0.05} |",
      f"| DSR(W2), N=6 | {dsr:.3f} (birincil+5 ablasyon Sharpe, yıllık: " + ", ".join(f"{stats.annual(x):.2f}" for x in trial_srs) + ") | ≥ 0,95 | " + f"{dsr >= 0.95} |", "",
      "## Bilgi (karar dışı)", "| ölçü | değer |", "|---|---|",
      f"| net p (W2 içinde rotasyon) | {p_n:.4f} (null ort. {nn.mean():.0f}; gerçek net {s['net_pnl']:.0f}) |",
      f"| brüt p, tüm seri rotasyonu (bilgi null) | {pf_g:.4f} (null ort. {fg.mean():.0f} ± {fg.std():.0f}, 95p {q(fg)[1]:.0f}) |", f"| net p, tüm seri rotasyonu | {pf_n:.4f} |",
      f"| W2 taze hakem koşusu: net / brüt / Sharpe | {s['net_pnl']:.0f} / {s['gross_pnl']:.0f} / {shp(r_run):.2f} |",
      f"| tam dönem koşusunun W2 dilimi: net / Sharpe / maks DD | {r.sum() * CAP:.0f} / {shp(r):.2f} / {pct(summ['maxdd_slice'])} |",
      f"| al-tut Sharpe (W2) / NW alfa (yıllık), beta, t | {shp(bh):.2f} / {a * 365:.3f}, {b:.3f}, {t:.2f} |",
      f"| fee / slippage / funding (W2 taze koşu) | {-s['fee']:.0f} / {-s['slippage']:.0f} / {s['funding']:.0f} |", f"| dolum / likidasyon / red | {s['n_fills']:.0f} / {s['n_liq']:.0f} / {s['n_rejected']:.0f} |", f"| defter satırı (trial) | {real['row_trial']} |"]
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "tables.md").write_text("\n".join(md))
(OUT / "summary.json").write_text(json.dumps(summ, indent=1, default=float))
print("\n".join(md))
