"""`carry_xs` K1–K9 kartı: reports/preregistration/carry_xs_card.md eşiklerini uygular. Girdi: reports/signal_diagnostics_data/{carry_xs_card, phase2}; çıktı: carry_xs_card.json, reports/carry_xs_card.md, 1 defter satırı.
  python scripts/carryxs_card_report.py"""
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
import audit_metrics as am  # noqa: E402

from kepler import stats  # noqa: E402

D = ROOT / "reports" / "signal_diagnostics_data"
CARD, P2 = D / "carry_xs_card", D / "phase2"
CAP = 10_000.0


def daily(d: dict) -> pd.Series:
    s = pd.Series(d)
    s.index = pd.DatetimeIndex(s.index).tz_localize("UTC") if pd.DatetimeIndex(s.index).tz is None else pd.DatetimeIndex(s.index).tz_convert("UTC")
    return s.astype(float)


def sr_daily(x: pd.Series) -> float:
    r = x / CAP
    return float(r.mean() / r.std(ddof=1))


def main():
    c1 = json.loads((P2 / "summary_C1.json").read_text())
    c1d = pd.read_csv(P2 / "daily_C1.csv", index_col=0, parse_dates=True)["net"]
    c1d.index = pd.DatetimeIndex(c1d.index).tz_localize("UTC") if c1d.index.tz is None else c1d.index
    nulls = {}
    for f in sorted(CARD.glob("null_*.json")):
        nulls.update(json.loads(f.read_text()))
    fixed = json.loads((CARD / "fixed.json").read_text())
    wins = json.loads((CARD / "windows.json").read_text())
    bench = pd.read_csv(CARD / "bench_ew.csv", index_col=0, parse_dates=True)["ret"]
    bench.index = pd.DatetimeIndex(bench.index).tz_localize("UTC") if bench.index.tz is None else bench.index
    out, K = {}, {}
    gross = c1["summary"]["gross_pnl"]
    ng = np.array([v["summary"]["gross_pnl"] for v in nulls.values()])
    p = stats.rotation_p(gross, ng)
    trial = [sr_daily(c1d), sr_daily(daily(fixed["abl_no_risk"]["daily"])), sr_daily(daily(fixed["abl_no_buffer"]["daily"]))]
    dsr = stats.dsr((c1d / CAP).to_numpy(), trial)
    out["K1"] = dict(B=len(ng), real_gross=gross, null_mean=float(ng.mean()), null_sd=float(ng.std(ddof=1)), null_q=[float(np.quantile(ng, q)) for q in (0.5, 0.95, 0.99)], p=p, p_floor=1 / (len(ng) + 1), thr=0.05 / 3, dsr=dsr,
                     p_vs_108_thr=0.05 / 108, trial_sr_daily=trial, net_null_mean=float(np.mean([v["summary"]["net_pnl"] for v in nulls.values()])))
    K["K1"] = bool(p <= 0.05 / 3 and dsr >= 0.95)
    j = c1d.index.intersection(bench.dropna().index)
    rs, rb = (c1d.loc[j] / CAP).to_numpy(), bench.loc[j].to_numpy()
    a, b, t = stats.nw_alpha(rs, rb, 5)
    shs, shb = rs.mean() / rs.std(ddof=1) * np.sqrt(365), rb.mean() / rb.std(ddof=1) * np.sqrt(365)
    out["K2"] = dict(sharpe_strategy=float(shs), sharpe_benchmark=float(shb), alpha_daily=a, alpha_annual=a * 365, beta=b, t_alpha=t, n_days=len(j))
    K["K2"] = bool(shs > shb and t >= 2)
    sh = c1["sharpe_fixed"]
    c16, cd = fixed["cost_16_6_0"]["summary"]["net_pnl"], fixed["cost_10_2_1"]["summary"]["net_pnl"]
    out["K3"] = dict(sharpe=sh, net_fee16_slip6=c16, net_delay1=cd, sharpe_fee16_slip6=am.sharpe_fixed(daily(fixed["cost_16_6_0"]["daily"]), CAP), sharpe_delay1=am.sharpe_fixed(daily(fixed["cost_10_2_1"]["daily"]), CAP))
    K["K3"] = bool(sh >= 1.0 and c16 > 0 and cd > 0)
    boot = am.bootstrap_sharpe_ci(c1d, CAP)
    dd = am.max_dd_fixed(c1d, CAP)
    out["K4"] = dict(maxdd=dd, maxdd_p95=boot["maxdd_q"]["p95"])
    K["K4"] = bool(dd <= 0.25 and boot["maxdd_q"]["p95"] <= 0.30)
    nb = {k: v for k, v in fixed.items() if k.startswith("nb_")}
    nbs = {k: dict(net=v["summary"]["net_pnl"], sharpe=am.sharpe_fixed(daily(v["daily"]), CAP), carry_days=v["params"]["carry_days"]) for k, v in nb.items()}
    share = float(np.mean([v["net"] > 0 for v in nbs.values()]))
    med = float(np.median([v["sharpe"] for v in nbs.values()]))
    out["K5"] = dict(neighbors=nbs, share_net_pos=share, median_sharpe=med, main_sharpe=sh)
    K["K5"] = bool(share >= 0.7 and med >= sh / 2)
    halves = {k: v["summary"]["net_pnl"] for k, v in wins.items() if not (k.endswith("_2026-04-01") and not k.startswith("win_2026-01"))}
    shifts = {k: v["summary"]["net_pnl"] for k, v in wins.items() if k.endswith("_2026-04-01") and k.startswith("win_2020-")}
    out["K6"] = dict(halves=halves, shifts=shifts, share_halves_pos=float(np.mean([v > 0 for v in halves.values()])), n_halves=len(halves), n_shifts=len(shifts))
    K["K6"] = bool(out["K6"]["share_halves_pos"] >= 0.6 and all(v > 0 for v in shifts.values()))
    K["K7"] = None
    out["K7"] = dict(note="koşulamadı: evren zaten tüm top-20; evren dışı sembol kümesi yok (universe.parquet yalnızca rank ≤ 20)")
    abl = {k: am.sharpe_fixed(daily(v["daily"]), CAP) for k, v in fixed.items() if k.startswith("abl_")}
    out["K8"] = dict(main_sharpe=sh, ablations=abl)
    K["K8"] = bool(all(sh > v for v in abl.values()))
    p2 = json.loads((P2 / "phase2_results.json").read_text())["runs"]["C1"]["regime"]
    tot = sum(p2.values())
    out["K9"] = dict(regime_net=p2, max_share=max(p2.values()) / tot, n_nonneg=sum(v >= 0 for v in p2.values()))
    K["K9"] = bool(out["K9"]["n_nonneg"] >= 2 and out["K9"]["max_share"] <= 0.80)
    if not (K["K1"] and K["K2"]):
        dec = "NO_EDGE"
    else:
        dec = "ADAY" if all(K[f"K{i}"] for i in range(3, 10)) else "ZAYIF"
    out["pass"], out["decision"] = K, dec
    (CARD / "carry_xs_card.json").write_text(json.dumps(out, indent=1, default=float))
    code_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    row = dict(trial=1, time=time.time(), source="diagnostic", hypothesis="reports/preregistration/carry_xs_card.md K1", config=dict(test="K1 rotation null", B=len(ng), thr=0.05 / 3), code_hash=code_hash, result=dict(p=p, dsr=dsr, passed=K["K1"]))
    (CARD / "trials_card.jsonl").write_text(json.dumps(row) + "\n")
    fm = lambda x, n=2: f"{x:+.{n}f}"  # noqa: E731
    L = ["# `carry_xs` başarı kartı (K1–K9): edge var mı?", "",
         "Ön kayıt: `reports/preregistration/carry_xs_card.md` (koşudan önceki commit `1873adb`). Üreten: `scripts/carryxs_card_report.py` (rakamlar `reports/signal_diagnostics_data/carry_xs_card/`). Dinamik evren (aylık top-20, delist dahil), mevcut hakem, fee 10 + slip 2, sermaye 10 000; "
         "**görülmüş veride örneklem içi**; mühür dokunulmadı.", "",
         f"## Karar: **{dec}**" + ("  (ADAY denemez: K7 koşulamadı ve K9 Faz 2'de zaten görülmüştü)" if dec == "ZAYIF" else ""), "",
         "| K | ölçüt | sonuç | geçti |", "|---|---|---|---|",
         f"| K1 | rotasyon null'u: brüt p ≤ 0,05/3 = 0,0167 ve DSR ≥ 0,95 | gerçek brüt {gross:+.0f}; null ort. {out['K1']['null_mean']:+.0f} ± {out['K1']['null_sd']:.0f} (%50/%95/%99: {out['K1']['null_q'][0]:+.0f} / {out['K1']['null_q'][1]:+.0f} / {out['K1']['null_q'][2]:+.0f}); **p = {p:.4f}** (B = {len(ng)}, taban {out['K1']['p_floor']:.4f}); DSR = {dsr:.3f} | {'✓' if K['K1'] else '✗'} |",
         f"| K2 | Sharpe > benchmark ve NW alfa t ≥ 2 | Sharpe {shs:.2f} vs benchmark (EW üye fiyat getirisi) {shb:.2f}; alfa yıllık {a * 365:+.3f}, beta {b:+.3f}, **t = {t:.2f}** | {'✓' if K['K2'] else '✗'} |",
         f"| K3 | Sharpe ≥ 1,0; net > 0 fee 16 + slip 6'da ve 1 bar gecikmede | Sharpe {sh:.2f}; net fee16/slip6 {c16:+.0f}; net gecikme {cd:+.0f} | {'✓' if K['K3'] else '✗'} |",
         f"| K4 | maks DD ≤ %25; bootstrap DD %95 ≤ %30 | DD %{100 * dd:.1f}; bootstrap %95 %{100 * boot['maxdd_q']['p95']:.1f} | {'✓' if K['K4'] else '✗'} |",
         f"| K5 | komşuların ≥ %70'i net > 0; medyan Sharpe ≥ ana/2 | net > 0 payı {share:.2f}; medyan Sharpe {med:.2f} (ana {sh:.2f}) | {'✓' if K['K5'] else '✗'} |",
         f"| K6 | pencerelerin ≥ %60'ı net > 0; 4 kaydırma net > 0 | yarıyıl net > 0 payı {out['K6']['share_halves_pos']:.2f} ({out['K6']['n_halves']} pencere); kaydırmalar: " + ", ".join(f"{v:+.0f}" for v in shifts.values()) + f" | {'✓' if K['K6'] else '✗'} |",
         "| K7 | çapraz varlık | koşulamadı (evren dışı sembol kümesi yok) | – |",
         f"| K8 | ana Sharpe her ablasyondan büyük | ana {sh:.2f}; " + ", ".join(f"{k} {v:.2f}" for k, v in abl.items()) + f" | {'✓' if K['K8'] else '✗'} |",
         f"| K9 | ≥ 2 rejimde net ≥ 0 ve tek rejim payı ≤ %80 | bull/bear/range net: " + " / ".join(f"{p2[k]:+.0f}" for k in ("bull", "bear", "range")) + f"; en büyük pay %{100 * out['K9']['max_share']:.0f} | {'✓' if K['K9'] else '✗'} |", "",
         "## Ayrıntı", "", "**K5 komşuları:** " + "; ".join(f"×{k[3:]}: net {v['net']:+.0f}, Sharpe {v['sharpe']:.2f} (carry_days {v['carry_days']})" for k, v in nbs.items()) + ".", "",
         "**K6 yarıyıllar (net):** " + ", ".join(f"{k[4:15]}: {v:+.0f}" for k, v in halves.items()) + ".", "",
         f"**K1 bilgi:** aynı p'nin Faz 1 ailesinin Bonferroni eşiğine (0,05/108 = {0.05 / 108:.5f}) karşısı B = 300 çözünürlüğüyle ulaşılamaz. Null'ın NET ortalaması {out['K1']['net_null_mean']:+.0f} (gerçek net {c1['summary']['net_pnl']:+.0f}).", "",
         "## Okuma", "", (f"**Karar mekanik olarak NO_EDGE, ama tablo karışık.** K1 kalıyor: gerçek brüt {gross:+.0f}, rotasyon null'unun %95 dilimine ({out['K1']['null_q'][1]:+.0f}) neredeyse eşit; p = {p:.3f} hem ön kayıtlı eşiğin (0,0167) hem de nominal %5'in biraz üstünde (B = 300'de p'nin örnekleme belirsizliği ≈ ±0,013). "
          f"Null'ın kendisi pozitif ortalama brüt veriyor ({out['K1']['null_mean']:+.0f} ± {out['K1']['null_sd']:.0f}): kesitsel carry yapısı (dolar-nötr, düşük oynaklık) zamanlama olmadan da küçük pozitif getiri taşıyor; gerçek sonucun bunun ÜSTÜNDE olduğuna dair kanıt zayıf. "
          f"Öte yandan diğer kartlar güçlü: K2 geçti (alfa t = {t:.2f}, beta ≈ {b:+.3f}, Sharpe {shs:.2f} vs benchmark {shb:.2f}), K3 geçti (fee 16 + slip 6'da bile net {c16:+.0f}, Sharpe {out['K3']['sharpe_fee16_slip6']:.2f}; 1 bar gecikmede net {cd:+.0f}), K4, K5 (komşuların hepsi net > 0, Sharpe 1,3–1,6), K6 ve K8 geçti. "
          f"K7 koşulamadı; K9 kalıyor (netin ~%{100 * p2['bull'] / c1['summary']['net_pnl']:.0f}'i bull rejiminde; rejim netlerinin toplamına göre pay %{100 * out['K9']['max_share']:.0f}). "
          "**Sonuç:** 'edge kanıtlandı' denemez, 'edge yok' da denemez. Sinyal düzeyinde bilgi (Faz 1) ve maliyetten/gecikmeden bağımsız dayanıklı bir getiri var; ancak ön kayıtlı zamanlama null'u (K1) bunu şanstan ayıramadı ve kazanç tek rejime yaslanıyor. "
          "Bu bir NO_EDGE kararının K1 sınırında verildiği ve ZAYIF'a çok yakın bir durumdur; karar kuralı değiştirilmedi."), "",
         "## Dürüstlük notları", "",
         "- Tasarım Faz 1 bulgusundan türetildi (örneklem içi); kart bunu telafi etmez. Zaman-dışı kanıt yalnızca G3 (mühür, yalnızca ADAY ve kullanıcı komutuyla) ve canlıdır.",
         "- K2 benchmark'ı gösterge: maliyetsiz, fonlamasız EW fiyat getirisi (hakem al-tut'u artefakt verir). K7 koşulamadı, K9 Faz 2'de görülmüştü: en iyi olası karar ZAYIF idi.",
         "- Kontrol koşuları (null, maliyet, komşu, ablasyon, pencere) deftere girmedi; K1 p-testi 1 satır (`trials_card.jsonl`): N + 1. Önceki toplam N 5 090 → **5 091** (muhafazakâr).",
         "- Funding Binance'ten; MEXC doğrulanmadı. Sermaye 10 000; küçük hesapta lot/min-notional etkisi ölçülmedi (önceki denetim: asgari uygulanabilir sermaye ensemble için $2 500)."]
    (ROOT / "reports" / "carry_xs_card.md").write_text("\n".join(L))
    print(json.dumps({k: v for k, v in out.items() if k in ("pass", "decision")}), "p", p, "dsr", dsr, "t", t)


if __name__ == "__main__":
    main()
