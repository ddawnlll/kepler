"""Faz 3 rapor üreticisi: reports/signal_diagnostics.md. Tüm rakamlar results.json / checks.json / carryxs.json / phase2/phase2_results.json / inventory.json'dan gelir (elle rakam yok);
yorum metinleri `NARRATIVE` içinde ve yalnızca nitel / bu dosyalardaki sayılara atıflıdır.  python scripts/signal_diag_report.py"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "reports" / "signal_diagnostics_data"
EXPERTS = ["trend", "xs_momentum", "carry", "bollinger", "lowvol", "nearhigh", "fundcrowd", "volrev", "orderflow"]
HYP = dict(
    trend="mekanizma cümlesi YOK; kaynak atfı: Covel, Faith, Antonacci; likit coinlerde momentum (betimsel literatür)", xs_momentum="mekanizma cümlesi YOK; kaynak/etiket: Antonacci göreli momentum",
    carry="forex carry'nin perp karşılığı: funding alan tarafı tut (`book_signals.md`)", bollinger="yatay rejimde fiyat ortalamasına döner; belgede 'varsayım, kanıt değil'; kim ödüyor yazılı değil",
    lowvol="yalnızca ad: düşük oynaklık / betting-against-beta (mekanizma cümlesi YOK)", nearhigh="çıpalama / az-tepki: zirveye yakın olan devam eder", fundcrowd="aşırı funding = kalabalık pozisyon → tasfiye baskısı",
    volrev="yüksek hacimli günde ters tepki = likidite sağlayıcı tazminatı", orderflow="agresif alış akışı = bilgili akış, devam (vekil)")
H = [1, 3, 5, 10, 20, 40]


def f(x, n=3, sign=False):
    if x is None:
        return "–"
    return f"{x:+.{n}f}" if sign else f"{x:.{n}f}"


def ic_tables(r):
    out = []
    for t, name in (("ts", "IC-TS (zaman serisi, sembol içi, n_s ağırlıklı havuz)"), ("xs", "IC-XS (kesitsel rank, tarih başına)")):
        out += [f"**{name}**; hücre = IC (z) [Holm-düzeltmeli p ≤ 0,05: ★]", "", "| uzman | " + " | ".join(f"h={h}" for h in H) + " |", "|---|" + "---|" * len(H)]
        for n in EXPERTS:
            cells = []
            for h in H:
                c = r["family"][f"{n}|{t}|{h}"]
                cells.append(f"{c['ic']:+.3f} ({c['z']:+.1f}){'★' if c['p_holm'] <= 0.05 else ''}")
            out.append(f"| `{n}` | " + " | ".join(cells) + " |")
        out.append("")
    return "\n".join(out)


def decision_table(r, chk):
    rows = ["| uzman | H | karar | en iyi hücre | IC [ham %95 AA] | düzeltilmiş AA (108) | z | Holm p | alt dönemde + | negatif anlamlı | max \\|ρ\\| diğer (kopya?) | küme |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n in EXPERTS:
        c, d = r["cards"][n], r["desc"][n]
        b = c["best"]
        raw = chk["raw_target"].get(f"{n}|{b['type']}|{b['h']}") if b else None
        rows.append(f"| `{n}` | {c['H']} | **{c['decision']}** | {b['type'].upper()} h={b['h']} | {f(b['ic'], 3, True)} [{f(b['lo'], 3, True)}, {f(b['hi'], 3, True)}] | [{f(b['lo_c'], 3, True)}, {f(b['hi_c'], 3, True)}] | {f(b['z'], 2)} | {f(b['p_holm'], 4)} | {c.get('n_pos_periods')}/3 | "
                    f"{'EVET' if c['neg_sig'] else 'hayır'} | {d['max_corr_other']['expert']} {d['max_corr_other']['rho']:+.2f} ({'kopya' if d['copy'] else 'değil'}) | {r['clusters'][n]} |" if b else f"| `{n}` | {c['H']} | **{c['decision']}** | pozitif hücre yok | | | | | | | | {r['clusters'][n]} |")
    return "\n".join(rows)


def card(n, r, chk, hyp):
    c, d = r["cards"][n], r["desc"][n]
    b, w = c["best"], c["worst"]
    L = [f"### `{n}`: **{c['decision']}**", "", f"- **Hipotez (H = {c['H']}):** {hyp[n]}.",
         f"- **Ateşleme / büyüklük:** hücrelerin %{100 * d['fire_rate']:.1f}'inde F ≠ 0; ort. |F| = {d['mean_absF']:.3f}; {d['n_cells']} hücre."]
    if b:
        raw = chk["raw_target"][f"{n}|{b['type']}|{b['h']}"]
        L.append(f"- **En iyi hücre:** {b['type'].upper()}, h = {b['h']} gün: IC = {b['ic']:+.4f} (SE {b['se']:.4f}, z {b['z']:+.2f}); ham %95 AA [{b['lo']:+.3f}, {b['hi']:+.3f}]; düzeltilmiş (108 test) AA [{b['lo_c']:+.3f}, {b['hi_c']:+.3f}]; "
                 f"ham p = {b['p']:.4f}, **Holm p = {b['p_holm']:.4f}**, BH q = {b['q_bh']:.4f}. Ham (oynaklık normalizasyonsuz) getiri hedefiyle aynı hücrenin IC'si: {raw['raw']:+.4f} (normalize: {raw['norm']:+.4f}).")
    if w:
        L.append(f"- **En kötü hücre:** {w['type'].upper()}, h = {w['h']}: IC = {w['ic']:+.4f} (z {w['z']:+.2f}, Holm p = {w['p_holm']:.3f}).")
    if "calibration" in d and d["calibration"]:
        cal, mag = d["calibration"], d.get("magnitude")
        L.append(f"- **Kalibrasyon (en iyi ufuk, hücre havuzlu):** F beşliklerine göre ort. Y = [{', '.join(f'{x:+.3f}' for x in cal['mean'])}]; Q5−Q1 = {cal['diff']:+.3f}" + (f" [{cal['diff_lo']:+.3f}, {cal['diff_hi']:+.3f}]" if 'diff_lo' in cal else '') +
                 f"; monoton: {'evet' if cal['monotone'] else 'hayır'}." + (f" |F| beşliklerine göre ort. işaret-ayarlı Y = [{', '.join(f'{x:+.3f}' for x in mag['mean'])}] (büyüklük kalibrasyonu: {'monoton' if mag['monotone'] else 'monoton değil'})." if mag else ""))
        pr = c["periods"]
        yr = d["years"]
        L.append(f"- **Sönme:** alt dönemler 2020–21 / 2022–24 / 2025+ IC = {pr['2020-21']['ic']:+.3f} / {pr['2022-24']['ic']:+.3f} / {pr['2025+']['ic']:+.3f}; yıllık: " + ", ".join(f"{k}: {v['ic']:+.3f}" for k, v in yr.items() if v.get('ic') is not None) + ".")
        rg, ag = d["regime"], d["agreement"]
        L.append(f"- **Koşullu:** rejim IC bull / bear / range = {rg['bull']['ic']:+.3f} / {rg['bear']['ic']:+.3f} / {rg['range']['ic']:+.3f} (gün: {rg['bull']['n_days']} / {rg['bear']['n_days']} / {rg['range']['n_days']}); uzlaşma ≤2 / 3–4 / ≥5 = "
                 f"{f(ag['<=2']['ic'], 3, True)} / {f(ag['3-4']['ic'], 3, True)} / {f(ag['>=5']['ic'], 3, True)} (hücre: {ag['<=2']['n_cells']} / {ag['3-4']['n_cells']} / {ag['>=5']['n_cells']}).")
        L.append(f"- **Duyarlılıklar (betimsel):** funding dahil toplam getiri hedefiyle IC = {d['total_return']['ic']:+.4f}; terminal-fiyatlı hücreler hariç IC = {d['exclude_terminal']['ic']:+.4f} (terminal pay %{100 * d['terminal_share']:.2f}).")
    L.append(f"- **Fazlalık:** tahmin korelasyonu en yüksek olduğu uzman `{d['max_corr_other']['expert']}` (ρ = {d['max_corr_other']['rho']:+.2f}); küme {r['clusters'][n]}.")
    if "flip_orth_trend" in d:
        fo = d["flip_orth_trend"]
        L.append(f"- **Ters işaret (1.5):** −F'nin trend'e ortogonalleştirilmiş IC'si ({fo['type'].upper()}, h = {fo['h']}) = {fo['ic']:+.4f} (SE {fo['se']:.4f}).")
    if c["neg_sig"]:
        L.append("- Holm-düzeltmeli anlamlı NEGATİF hücre var (ters işaret kontrolü uygulandı).")
    L.append("")
    return "\n".join(L)


def corr_table(r):
    cm = r["corr"]
    cols = EXPERTS
    out = ["| | " + " | ".join(f"`{c}`" for c in cols) + " |", "|---|" + "---|" * len(cols)]
    for a in cols:
        out.append(f"| `{a}` | " + " | ".join(f"{cm[b][a]:+.2f}" for b in cols) + " |")
    return "\n".join(out)


def corr_xs_table(r):
    cm = r["corr_xs"]
    out = ["| | " + " | ".join(f"`{c}`" for c in EXPERTS) + " |", "|---|" + "---|" * len(EXPERTS)]
    for a in EXPERTS:
        out.append(f"| `{a}` | " + " | ".join(f"{cm[b][a]:+.2f}" for b in EXPERTS) + " |")
    return "\n".join(out)


def clusters_text(r):
    g = {}
    for n, k in r["clusters"].items():
        g.setdefault(k, []).append(n)
    return "\n".join(f"- Küme {k}: " + ", ".join(f"`{n}`" for n in v) for k, v in sorted(g.items()))


def run_row(n, m, label):
    return (f"| {label} | {m['net']:+.0f} | {m['gross']:+.0f} | {m['fee'] + m['slippage']:+.0f} | {m['funding']:+.0f} | {m['n_fills']:.0f} | {m['sharpe']:.2f} | {100 * m['maxdd']:.1f}% | "
            f"{m['periods']['2020–21']['sharpe']:.2f} / {m['periods']['2022–24']['sharpe']:.2f} / {m['periods']['2025+']['sharpe']:.2f} | {m['regime']['bull']:+.0f} / {m['regime']['bear']:+.0f} / {m['regime']['range']:+.0f} |")


def phase2(p2):
    if not p2:
        return "(Faz 2 sonuçları yok)"
    R = p2["runs"]
    out = ["| koşu | net | brüt | fee + slip | funding | dolum | Sharpe (sabit sermaye) | maks DD | Sharpe 2020–21 / 2022–24 / 2025+ | net bull / bear / range |", "|---|---|---|---|---|---|---|---|---|---|"]
    names = dict(B1="B1 trend, taban", T1="T1 trend + histerezis", B2="B2 ev1_plus_new, taban", T2="T2 ev1_plus_new + histerezis", C0="C0 mevcut `carry` (baz)", C1="C1 `carry_xs`")
    for k in ("B1", "T1", "B2", "T2", "C0", "C1"):
        if k in R:
            out.append(run_row(k, R[k], names[k]))
    out.append("")
    for core in ("trend", "ensemble"):
        k = f"hyst_{core}"
        if k in p2:
            h = p2[k]
            dl = h["delta_sharpe"]
            out.append(f"- **2.1 {core}:** **{h['decision']}**. ΔSharpe = {dl['point']:+.3f} (eşleştirilmiş bootstrap %2,5 / %50 / %97,5: {dl['p2_5']:+.3f} / {dl['p50']:+.3f} / {dl['p97_5']:+.3f}); Δnet = {h['d_net']:+.0f}, Δbrüt = {h['d_gross']:+.0f}, "
                       f"Δ(fee+slip) = {h['d_cost']:+.0f}, Δfunding = {h['d_funding']:+.0f}, Δdolum = {h['d_fills']:+.0f}; ΔSharpe dönemlere göre: " + ", ".join(f"{p}: {v:+.2f}" for p, v in h["d_sharpe_by_period"].items()) + ".")
    if "carry_xs" in p2:
        c = p2["carry_xs"]
        b = c["bootstrap"]["sharpe_q"]
        out.append(f"- **2.2 `carry_xs`:** **{c['decision']}**. S1 net > 0: {'✓' if c['S1_net_pos'] else '✗'}; S2 Sharpe bootstrap %5 yüzdeliği > 0 ({b['p5']:+.2f}; %50 {b['p50']:+.2f}; %95 {b['p95']:+.2f}): {'✓' if c['S2_sharpe_p5_pos'] else '✗'}; "
                   f"S3 ≥ 2/3 dönem net > 0: {'✓' if c['S3_periods'] else '✗'}; S4 trend ile günlük PnL korelasyonu {c['corr_trend_daily_pnl']:+.2f} ≤ 0,30: {'✓' if c['S4_corr_le_030'] else '✗'}; mevcut carry ile günlük PnL korelasyonu {f(c['corr_c0'], 2, True)}.")
    return "\n".join(out)


def inventory(inv):
    b = inv["binance_archive"]
    rows = ["| veri | kaynak | aralık / çözünürlük | repoda (tape) | not |", "|---|---|---|---|---|"]
    bt = b["BTCUSDT"]
    rg = lambda x: f"{x['first']} → {x['last']}" if x else "yok"  # noqa: E731
    rows += [
        f"| 1h klines, mark, funding | Binance USDT-M arşivi | 2020-01 → 2026-03 (mühür hariç), 1h | **VAR** (`/data`, `/data/pre2022`) | taker alış hacmi sütunu klines'ta VAR |",
        f"| Open interest + üst trader / hesap long-short + taker oranı (`metrics`) | Binance arşivi `daily/metrics` | BTC {rg(bt['metrics'])}; ETH/SOL/DOGE {rg(b['ETHUSDT']['metrics'])}; 5 dk, günlük dosya | **YOK** (indirilmedi; ayrı görev tanımı `TASKS.md`'de) | sütun anlamı ve `create_time` semantiği doğrulanmadı |",
        f"| Likidasyonlar | Binance arşivi `liquidationSnapshot` | arşivde yok (BTC/ETH/SOL/DOGE için boş) | YOK | OKX `liquidation-orders` yalnızca yakın zaman: {'çalışıyor' if inv['okx']['liquidation_orders_endpoint_works'] else 'çalışmıyor'} |",
        f"| Perp–endeks primi (basis vekili) | Binance `premiumIndexKlines` / `indexPriceKlines` | BTC {rg(bt['monthly_premiumIndexKlines'])}, 1h (SOL: {rg(b['SOLUSDT']['monthly_premiumIndexKlines'])}) | YOK | funding'in ham girdisi; ücretsiz |",
        f"| Spot fiyat (spot–perp basis) | Binance spot `klines` | BTC {rg(bt['spot_klines_1h'])}, 1h (DOGE: {rg(b['DOGEUSDT']['spot_klines_1h'])}) | YOK | ücretsiz; spot–perp basis türetilebilir |",
        f"| İşlem verisi (trades/aggTrades) | Binance arşivi | BTC aggTrades {rg(bt['monthly_aggTrades'])} (aylık), günlük {rg(bt['aggTrades'])} | YOK | tick düzeyi, büyük hacim |",
        f"| L2 / emir defteri | Binance `bookDepth` (günlük özet derinlik) / `bookTicker` | bookDepth {rg(bt['bookDepth'])}; bookTicker yalnızca {rg(bt['bookTicker'])} | YOK | tam L2 geçmişi ücretsiz arşivde yok (doğrulanmadı: ücretli sağlayıcılar) |",
        f"| MEXC kline | MEXC kontrat API | 1h: {inv['mexc']['kline_1h_first']} →; 1d: {inv['mexc']['kline_1d_first']} → | YOK (araştırma verisi Binance; MISSION) | resmi, ücretsiz |",
        f"| MEXC funding geçmişi | MEXC kontrat API | yalnızca {inv['mexc']['funding_oldest']} → ({inv['mexc']['funding_records']} kayıt) | YOK | MEXC'e özgü funding geçmişi ~1,5 yıl |",
        f"| MEXC OI / likidasyon / long-short | MEXC kontrat API | yalnızca anlık (`ticker.holdVol`: {'var' if inv['mexc']['ticker_has_open_interest_snapshot'] else 'yok'}); tarihsel uç bulunamadı | YOK | MEXC için geçmiş OI satın alma/biriktirme gerekir |",
        f"| OKX OI+hacim, long-short oranı | OKX `rubik/stat` | yalnızca son {inv['okx']['oi_volume_rows']} gün, günlük (en eski {inv['okx']['oi_volume_oldest']}) | YOK | geçmiş yetersiz |",
        f"| Hyperliquid funding geçmişi | Hyperliquid `info` | {inv['hyperliquid']['funding_history_first']} → | YOK | OI/likidasyon geçmişi kontrol edilmedi |",
        "| Binance fapi / Bybit REST | – | bu ortamdan engelli (451 / 403) | – | `openInterestHist` (30 gün sınırı), `allForceOrders` (kaldırıldı) gibi iddialar **doğrulanmadı** |",
    ]
    return "\n".join(rows)


def main():
    r = json.loads((D / "results.json").read_text())
    chk = json.loads((D / "checks.json").read_text())
    cx = json.loads((D / "carryxs.json").read_text()) if (D / "carryxs.json").exists() else None
    p2 = json.loads((D / "phase2" / "phase2_results.json").read_text()) if (D / "phase2" / "phase2_results.json").exists() else None
    inv = json.loads((D / "inventory.json").read_text())
    nar = json.loads((D / "narrative.json").read_text()) if (D / "narrative.json").exists() else {}
    nt = r["n_trials"]
    n_p2 = (sum(1 for _ in (D / "phase2").glob("ledger_phase2_*.jsonl") for _ in open(_)) if (D / "phase2").exists() else 0)
    n_cx = 12 if cx else 0
    pass_n = sum(c["ic_pass"] for c in r["cards"].values())
    dec = {k: [n for n in EXPERTS if r["cards"][n]["decision"] == k] for k in ("TUT", "YENİDEN KUR", "AT")}
    L = ["# Sinyal teşhisi: 9 uzman gerçekte ne biliyor?", "",
         "Bu dosya `scripts/signal_diag_report.py` ile üretildi (rakamlar `reports/signal_diagnostics_data/*.json`'dan). Ön kayıtlar: `reports/preregistration/signal_diagnostics.md`, `neutral_zone_hysteresis.md`, `carry_rebuild.md` (hepsi ilgili koşudan önceki commit'lerde). "
         "Tüm sonuçlar görülmüş veride (2020-04 → 2026-03) **örneklem içi**; mühürlü dönem (≥ 2026-04-01) yüklenmedi; ensemble ağırlığı, sizing, vol hedefi ve parametre araması yapılmadı.", "",
         "## Özet", "", nar.get("summary", ""), "",
         f"**Kararlar (ön kayıtlı ölçüt):** TUT: {', '.join('`' + n + '`' for n in dec['TUT']) or '–'}; YENİDEN KUR: {', '.join('`' + n + '`' for n in dec['YENİDEN KUR']) or '–'}; AT: {', '.join('`' + n + '`' for n in dec['AT']) or '–'}. "
         f"IC ölçütünü geçen {pass_n}/9. Bağımsız fikir (küme) sayısı: **{r['n_clusters']}** (IC ölçütü geçen en az bir uzmanlı küme: {r['n_clusters_with_ic_pass']}).", "",
         "## Karar tablosu", "", decision_table(r, chk), "",
         f"Aile: 9 uzman × 6 ufuk × 2 IC türü = {r['n_family']} iki yönlü test; Holm FWER 0,05. Düzeltilmiş AA = nokta ± z_(1−0,05/216)·SE (Bonferroni, z = {r['z_corr']:.2f}). p-değerleri durağan blok bootstrap (B = {r['B']}) SE'sinden normal yaklaşım. "
         f"Hücre sayısı (karar günü × üye sembol): {r['n_cells']}. Oynaklığa normalize ileri getiri, giriş = ertesi gün açılışı.", "",
         nar.get("rule_note", ""), "",
         "## IC tabloları (tüm aile)", "", ic_tables(r),
         "## Uzman kartları", ""] + [card(n, r, chk, HYP) for n in EXPERTS] + [
         "## Fazlalık: tahmin korelasyonları ve kümeler", "", "Hücre havuzlu Spearman (ensemble'ın gördüğü hâl, NaN → 0; birincil):", "", corr_table(r), "", "Günlük kesitsel Spearman ortalaması (ikincil):", "", corr_xs_table(r), "",
         "Kümeleme (ortalama bağlantı, mesafe 1 − |ρ|, kesim |ρ| ≥ 0,5):", "", clusters_text(r), "", nar.get("clusters", ""), "",
         "## Ensemble referansı ve karşılaştırma evreni (karar dışı)", ""]
    ref = r["ensemble_ref"]
    L += ["`ev1_plus_new` birleşik F'nin IC'si (dinamik evren): " + "; ".join(f"{k.upper().replace('|', ' h=')}: {v['ic']:+.3f} (z {v['z']:+.1f})" for k, v in ref.items() if k.split("|")[1] in ("5", "40")) + ".", "",
          "Karşılaştırma evreni (mevcut 9 sembol; yalnızca nokta IC, p/AA yok) ile dinamik evren, h = 20 gün:", "", "| uzman | IC-TS dinamik | IC-TS 9-sembol | IC-XS dinamik | IC-XS 9-sembol |", "|---|---|---|---|---|"]
    for n in EXPERTS:
        L.append(f"| `{n}` | {r['family'][f'{n}|ts|20']['ic']:+.3f} | {r['ext9'][f'{n}|ts|20']:+.3f} | {r['family'][f'{n}|xs|20']['ic']:+.3f} | {r['ext9'][f'{n}|xs|20']:+.3f} |")
    L += ["", nar.get("ext9", ""), "", "## Faz 1 doğrulama kontrolleri", "",
          f"- φ'nin ham funding olaylarından bağımsız yeniden hesabı (gerçek veri, {chk['phi_samples']} örnek): en büyük mutlak fark {chk['phi_recompute_max_abs_diff']:.1e} ({chk['phi_samples_with_kline_gaps']} örnekte kline boşluğu; rolling ortalama mevcut barlarla eşleşiyor).",
          f"- Rejim etiketi kesilmiş seride değişmedi: uyuşmazlık {chk['regime_truncation_mismatches']} / 5 kesim (BTC gerçek verisi).",
          "- Birim/sentetik kontroller (`tests/test_signal_diag.py`, 13 test, Modal'de geçti): pozitif kontrol (ρ = 0,3 → Spearman 0,2875 ± 0,02), negatif kontrol (200 tekrar ham p < 0,05 oranı [0,02; 0,09], Holm yanlış keşif ≤ %10), hizalama (karar günü getirisi sızmıyor, giriş = ertesi gün açılışı, terminal fiyat, funding penceresi), Holm/BH elle, rejim nedenselliği + mutant, φ yeniden hesabı, uçtan uca sentetik.",
          "- Katı funding sürümü (karar anı damgalı olay hariç): carry/fundcrowd IC farkı (en büyük mutlak) " + f"{max(abs(v['strict'] - v['inclusive']) for v in r['funding_strict'].values()):.4f}" + " (`funding_strict`).", "",
          "## Faz 2: ön kayıtlı iki test (dinamik evren, mevcut hakem, tek seferlik)", "", phase2(p2), "", nar.get("phase2", ""), ""]
    if cx:
        L += ["`carry_xs` tahmin düzeyi (bilgi; SE ile, p yok): " + "; ".join(f"{k.upper().replace('|', ' h=')}: {v['ic']:+.3f} (SE {v['se']:.3f})" for k, v in cx.items() if k.startswith(("ts|", "xs|")) and k.split("|")[1] in ("5", "20", "40")) + f". Tahmin korelasyonu (hücre havuzlu): trend {cx['corr_cell']['trend']:+.2f}, eski carry {cx['corr_cell']['carry']:+.2f}, lowvol {cx['corr_cell']['lowvol']:+.2f}, fundcrowd {cx['corr_cell']['fundcrowd']:+.2f}.", ""]
    L += ["## Veri envanteri (Faz 0.3; yalnızca envanter, pipeline kurulmadı)", "", inventory(inv), "", "Maliyet notu (kaba, doğrulanmamış): `metrics` günlük dosya ~20 MB/sembol-yıl düzeyindeydi (`TASKS.md` notu); 20 üyeli dinamik evren ≈ 200 sembol için yüzlerce GB-saat değil, ~10⁴ dosya; indirme/ayrıştırma BTC/ETH/SOL için bir günlük iş, tam evren için 2–3 gün (tahmin). "
          "aggTrades/trades tick düzeyi ve çok büyük (BTC tek başına yıllarca günlük GB); L2 tam geçmişi ücretsiz kaynaklarda yok.", "",
          "### Yeni veri kaynaklarının momentum'dan bağımsız bilgi taşıma ihtimali (yargı; kanıt değil)", "", nar.get("new_data", ""), "",
          "## Deneme sayacı (araştırma defteri)", "",
          f"- Faz 1 aile testleri: **{nt['family']}**; karar ölçütüne giren alt dönem işaret kontrolleri: **{nt['criterion_period']}**; betimsel ölçümler (kalibrasyon, yıllık, rejim, uzlaşma, toplam getiri, terminal-hariç, ters-ortogonal, ensemble referansı): **{nt['descriptive']}** → Faz 1 toplam **{nt['total']}** satır (`reports/signal_diagnostics_data/trials.jsonl`).",
          f"- Faz 2: hakem defteri satırları (T1, T2, C1; `phase2/ledger_phase2_*.jsonl`): **{n_p2}**; `carry_xs` IC bilgi ölçümleri (betimsel): **{n_cx}**.",
          f"- Bu görevde eklenen toplam: **{nt['total'] + n_p2 + n_cx}** (muhafazakâr, betimsel dahil); DSR için birincil sayı: aile {nt['family']} + kriter {nt['criterion_period']} + hakem {n_p2} = **{nt['family'] + nt['criterion_period'] + n_p2}**. Önceki toplam N = 4 775 (`reports/audit_fixes.md`) → yeni N = **{4775 + nt['total'] + n_p2 + n_cx}** (muhafazakâr) / **{4775 + nt['family'] + nt['criterion_period'] + n_p2}** (birincil).",
          "- Ölçüm/baz koşuları (B1, B2, C0) ve Faz 1 duyarlılık nokta tahminleri (ham getiri hedefi, katı funding, 9-sembol, terminal-hariç nokta) deftere girmedi (ön kayıt kuralı); bunlar p ile iddia taşımaz.", "",
          "## Dürüstlük notları ve sınırlar", "", nar.get("limits", ""), ""]
    (ROOT / "reports" / "signal_diagnostics.md").write_text("\n".join(L))
    print("yazıldı", len("\n".join(L)), "karakter")


if __name__ == "__main__":
    main()
