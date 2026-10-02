"""BACKTEST tamamlama özet tabloları: scripts/completion.py çıktıları (JSON) -> tables.md (yalnızca stdlib).

  python scripts/completion_report.py reports/backtest_completion_data"""
import json
import sys
from pathlib import Path

D = Path(sys.argv[1])
load = lambda f: json.loads((D / f).read_text()) if (D / f).exists() else None  # noqa: E731
pc = lambda x: "—" if x is None else f"{100 * x:.1f}%"  # noqa: E731
n0 = lambda x: "—" if x is None else f"{x:,.0f}".replace(",", " ")  # noqa: E731
f1 = lambda x: "—" if x is None else f"{x:.1f}"  # noqa: E731
f2 = lambda x: "—" if x is None else f"{x:.2f}"  # noqa: E731
md = ["# BACKTEST tamamlama tabloları (otomatik; scripts/completion_report.py)", ""]

if b := load("base.json"):
    md += ["## 1. Tarihsel stres (tam Turtle `full`; sermaye 10 000; pencere içi, [başlangıç, bitiş))", "",
           "Mutlak en kötü 5 sepet günü: " + ", ".join(f"{d} ({pc(v)})" for d, v in b["abs5"]), "Seçilen en büyük 3 düşüş (adlı pencereler dışı): " + ", ".join(f"{d} ({pc(v)})" for d, v in b["top"]), "",
           "| sistem | pencere | sepet fiyat | net | net %sermaye | maks DD (%sermaye) | en kötü saat | en kötü gün | stop / likidasyon | başta brüt / net yön | stop kayma bps (ort/maks) | bar aşma bps (ort/maks) |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in b["stress"].items():
        for w, x in v["windows"].items():
            md.append(f"| {k} | {w} | {pc(x['basket'])} | {n0(x['net'])} | {pc(x['net_pct'])} | {pc(x['max_dd_pct'])} | {n0(x['worst_hour'])} | {n0(x['worst_day'])} | {x['n_stop']} / {x['n_liq']} | {n0(x['gross_start'])} / {n0(x['net_start'])} "
                      f"| {f1(x['stop_slip_bps_mean'])} / {f1(x['stop_slip_bps_max'])} | {f1(x['overshoot_bps_mean'])} / {f1(x['overshoot_bps_max'])} |")
    md += ["", "Taban koşu net (kontrol: S1 39 398, S2 27 641 beklenir): " + ", ".join(f"{k} {n0(v['net'])} (reddedilen {v['n_rejected']}, saatlik yeniden kurulum farkı {f2(v['recon'])})" for k, v in b["stress"].items()), "",
           "## 2. İşlem sırası Monte Carlo (5000 permütasyon, seed 0; DD ve seri sermayeye / adet)", "",
           "| sistem | işlem | kazanan | recon (işlem toplamı − hakem net) | DD %5/%50/%95/%99 | zarar serisi %50/%95/%99 | en kötü ardışık zarar %50/%95 | gerçek sıra DD / yüzdelik | gerçek seri | DD95 → s* | önerilen kill |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s, m in b["mc"].items():
        q = lambda d: "/".join(pc(d[k]) for k in ("p05", "p50", "p95", "p99"))  # noqa: E731
        md.append(f"| {s} | {m['n_trades']} | {pc(m['win_rate'])} | {n0(m['recon'])} | {q(m['dd'])} | {m['streak']['p50']:.0f}/{m['streak']['p95']:.0f}/{m['streak']['p99']:.0f} | {pc(m['worst_run']['p50'])}/{pc(m['worst_run']['p95'])} "
                  f"| {pc(m['actual']['dd'])} / {pc(m['actual_dd_pctile'])} | {m['actual']['streak']:.0f} | {pc(m['dd95'])} → {m['s_star']:.3f} | {pc(m['rec_kill'])} |")
    for s, m in b["mc"].items():
        md += ["", f"Kill switch yanlış-tetik tablosu {s} (s* = {m['s_star']:.3f} ölçekli boyut; ölçeksiz = planlanan %1 risk/birim):", "", "| eşik | p(tetik) s* | ort. final s* (kesmeli / kesmesiz) | p(tetik) ölçeksiz |", "|---|---|---|---|"]
        md += [f"| {pc(float(t))} | {pc(x['scaled']['p_trip'])} | {pc(x['scaled']['mean_final'])} / {pc(x['scaled']['mean_final_nokill'])} | {pc(x['unscaled']['p_trip'])} |" for t, x in m["kill_table"].items()]
    md.append("")

if c := load("capacity.json"):
    md += ["## 3. Kapasite + karekök etki (sermaye başına tam Turtle; fee 10 + slip 2 + etki)", "", "| koşu | net | brüt | dolum | reddedilen | katılım p50/p95/p99/maks | > %0,1 olan dolum | etki Y=1 (USDT, brüt payı) | net sonrası Y=0,5 / 1 / 2 | yıllık Sharpe taban → Y=1 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in c.items():
        p, y = v["part"], v["y"]
        md.append(f"| {k} | {n0(v['net'])} | {n0(v['gross'])} | {v['n_fills']} | {v['n_rejected']} | {p['p50'] * 100:.3f}/{p['p95'] * 100:.3f}/{p['p99'] * 100:.3f}/{p['max'] * 100:.3f}% | {p['n_over']} ({pc(p['share_over'])}) "
                  f"| {n0(y['1.0']['cost'])} ({pc(y['1.0']['cost_over_gross'])}) | {n0(y['0.5']['net_after'])} / {n0(y['1.0']['net_after'])} / {n0(y['2.0']['net_after'])} | {f2(v['sharpe_base'])} → {f2(y['1.0']['sharpe_after'])} |")
    md.append("")

if r := load("risk.json"):
    md += ["## 4. Risk motoru koşuları (S1/S2 `full`; sermaye 10 000; DD tepe equity'ye göre)", "", "| koşu | net | final equity | yıllık Sharpe (önceki gün equity) | maks DD saatlik / günlük | dolum | stop | likidasyon | kill_at | deneme | bootstrap DD %50/%95, Sharpe %5/%50/%95 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in r.items():
        bs = v["boot"]
        md.append(f"| {k}{' ⚠ geçersiz' if v['invalid'] else ''} | {n0(v['net'])} | {n0(v['final_equity'])} | {f2(v['sharpe'])} | {pc(v['dd_hourly'])} / {pc(v['dd_daily'])} | {v['n_fills']} | {v['n_stop']} | {v['n_liq']} | {v['kill_at']} | {v['trial']} "
                  f"| {'—' if not bs else pc(bs['maxdd'][0]) + '/' + pc(bs['maxdd'][1]) + ', ' + '/'.join(f2(x) for x in bs['sharpe'])} |")
    md.append("")

if p := load("pbo.json"):
    md += ["## 5. PBO/CSCV ve SPA (88 yapılandırma, arama dönemi 2022-01-01 → 2025-01-01, S = 16, 12 870 bölme)", "", "| küme | N | PBO | λ medyanı | P(IS-en-iyi OOS'ta zararda) |", "|---|---|---|---|---|"]
    md += [f"| {k} | {v['n']} | {pc(v['pbo'])} | {f2(v['lam_median'])} | {pc(v['loss'])} |" for k, v in p["cscv"].items()]
    md += ["", "| SPA benchmark | T (en iyi t) | en iyi | p_lower | **p_consistent** | p_upper (RC) |", "|---|---|---|---|---|---|"]
    md += [f"| {k} | {f2(v['t_best'])} | {v['best']} | {v['p_lower']:.4f} | **{v['p_consistent']:.4f}** | {v['p_upper']:.4f} |" for k, v in p["spa"].items()]
    md += ["", f"Al-tut yıllık Sharpe {f2(p['bh_sharpe'])}; en yüksek yıllık Sharpe: " + ", ".join(f"{k} {f2(v)}" for k, v in p["best_sharpe"].items()), ""]

if n := load("nested_report.json"):
    md += ["## 6. Nested walk-forward (88 aday; iç ölçüt: yarıyıl Sharpe medyanı)", "", "| dış adım | OOS | seçilen | iç medyan Sharpe (günlük) | OOS net (sermaye payı, 18 000) | 88 içinde yenilen pay |", "|---|---|---|---|---|---|"]
    md += [f"| {s['T']} | {s['oos'][0]} → {s['oos'][1]} | {s['pick']} | {s['score']:.3f} | {pc(s['oos_total'])} | {pc(s['pct'])} |" for s in n["steps"]]
    md += ["", f"Birleşik OOS ({n['n_days']} gün): net {n0(n['oos_net'])} USDT, yıllık Sharpe {f2(n['oos_sharpe'])}, PSR(0) {f2(n['psr0'])}, DSR(N=88) {f2(n['dsr'])}, maks DD {pc(n['max_dd'])} (sermaye 18 000'e oran).",
           f"Rastgele seçim: p = {n['p_random']:.4f}; rastgele medyan yıllık Sharpe {f2(n['random_median_sharpe'])}, %95 {f2(n['random_p95_sharpe'])}. 88'in aynı günlerde ortalama net {n0(n['mean_config_net'])}, medyan {n0(n['median_config_net'])}; en iyi (post-hoc) {n['best_config_oos']}. Geçersiz (reddedilen emirli) koşu: {n['invalid']}.", ""]
(D / "tables.md").write_text("\n".join(md) + "\n")
print("yazıldı", D / "tables.md")
