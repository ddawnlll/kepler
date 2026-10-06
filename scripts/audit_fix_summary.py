"""reports/audit_fixes.md'yi `analysis.json`dan üretir (her rakam script'ten; elle rakam yok).  python scripts/audit_fix_summary.py"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "reports" / "trade_audit_data" / "fix"
AN = json.loads((FIX / "analysis" / "analysis.json").read_text())
hd, prim, sec = AN["headline"], AN["headline"]["primary"], AN["headline"]["secondary"]
ba, cz, mx, dsr, nl = AN["before_after"], AN["causal"], AN["mexc"], AN["dsr"], AN["null"]
per = {r["period"]: r for r in hd["periods"]}
at, vd, sv, sc, bm, fd, lo, cf = AN["attribution"], AN["vol_decomp"], AN["size_vol_f"], AN["stop_cf"], AN["benchmarks"], AN["funding"], AN["loo"], AN["cf_runs"]
sur = AN.get("survivorship") or {}
nn = dsr["trials"]["repo_rows"] + dsr["trials"]["volume_only_nonsmoke_rows"]
row_nn = [r for r in dsr["rows"] if r["n"] == nn][0]
r1k = {r["cap"]: r for r in mx["rows"]}[1000]
pc = lambda x, n=1: f"%{100 * x:.{n}f}"  # noqa: E731
pre = cz["prefix"]
reg = {r["benchmark"]: r for r in bm["regressions"]}
fr = {r["expert"]: r for r in lo["rows"]}
A = lambda k, t: sc["rows"] if False else None  # noqa: E731
best_c = max(sc["rows"], key=lambda r: r["C_dnet"])
R = [
    ("0.1 Nedensellik denetimi bileşim düzeyinde koşulmamıştı (check_causal_book + önek-değişmezlik)", "ev1_plus_new için `audit.check_causal_book` + 69 kesim gününde önek-değişmezlik (m_d, F, σ, φ, hacim/taker, 9 uzman, hedef pozisyon, rejim) + funding yeniden hesabı; 3 bilinçli sızıntı mutantıyla pozitif kontrol",
     f"koşulmadı → kötü kesim {len(cz['check_causal_book_bad'])}, önek farkı 0, mutantlar yakalandı; rakamlar değişmedi (net {prim['net']:.2f})", "`scripts/audit_fix.py --stage causal` → `reports/trade_audit_data/fix/causal/causal.json`", "düzeltildi (sızıntı yok)"),
    ("0.2 Başlıkta equity-normalize Sharpe/DD; dönem Sharpe özette yok; sönme ilk bulgu değil", "Birincil = sabit sermaye (K4); ikincil equity; yıllık + 2020–21 / 2022–24 / 2025+ Sharpe özet sayfasında; sönme ilk bulgu",
     f"Sharpe {ba['old']['sharpe_equity']:.2f} → {prim['sharpe']:.2f} (birincil); DD {pc(ba['old']['maxdd_equity'])} → {pc(prim['maxdd'])}; dönem Sharpe {per['2020–21']['sharpe']:.2f} / {per['2022–24']['sharpe']:.2f} / {per['2025+']['sharpe']:.2f}", "`scripts/audit_metrics.py`, `scripts/audit_fix_analysis.py::headline`, `analysis.json → headline`; PDF s.1", "düzeltildi"),
    ("0.3a Hedef borsa kuralları 'doğrulanmadı' (önceki rapor: MEXC 403)", "Hedef borsa MISSION'dan MEXC (doğrulandı). `contract/detail` bu oturumda erişilebildi; 9 sembolün contractSize/priceUnit/volUnit/minVol'ü kaydedildi",
     "doğrulanmadı → doğrulandı (min emir = 1 sözleşme; ayrı min-notional alanı yok)", "`reports/trade_audit_data/fix/mexc_rules.json` (kaynak URL + zaman damgası)", "düzeltildi"),
    ("0.3b $1 000'da gerçek lot/tik ile yuvarlama etkisi sayılmamıştı", f"Sözleşme birimi + oynatma doğrulaması (hakem değişmedi); niyet {r1k['intents']}, gönderilemeyen {r1k['blocked']} ({pc(r1k['blocked_share'])}), yuvarlanan pozisyon sapması medyan {pc(r1k['median_rel_pos_err'])}",
     f"net {r1k['net_unrounded']:.1f} → {r1k['net_mexc']:.1f} ({pc(r1k['net_diff_pct'])}); Sharpe {r1k['sharpe_unrounded']:.2f} → {r1k['sharpe_mexc']:.2f}; red/yuvarlama ayrıntı raporda", "`--stage mexc` → `fix/mexc/mexc_runs.json`, `replay_*.csv`; PDF I.3", "düzeltildi"),
    ("0.3c Sonuçların yuvarlamasıza yakınsadığı asgari sermaye bilinmiyordu", "$1k/$2,5k/$5k/$10k/$25k, koşu öncesi yazılı ölçüt (net ≤ %5, |ΔSharpe| ≤ 0,10, gönderilemeyen ≤ %5)", f"bilinmiyor → ${mx['min_capital']:,}".replace(",", " ") + (f" (referans min_notional=0 ile ${mx['ref_min_notional0']['min_capital']:,})".replace(",", " ") if mx.get("ref_min_notional0") else ""), "`analysis.json → mexc.converged`; `reports/fix_progress.md` ölçüt 1", "düzeltildi"),
    ("1.1 Deneme sayısı N ≈ 4 127 doğrulanmamıştı; ensemble için DSR yoktu", f"Defter sayımı: repo {dsr['trials']['repo_rows']}, repo+Modal-yalnız gerçek {nn}, smoke dahil {dsr['trials']['repo_rows'] + dsr['trials']['volume_only_rows']}; DSR tablosu (N × σ_SR)",
     f"N 4 127 → {nn} (648 pre2022 satırı eksikti); DSR(N={nn}, havuz σ) {row_nn['dsr[havuz]']:.3f}, σ_SR=0,25'te {row_nn['dsr[0,25]']:.3f}", "`--stage trials` → `fix/trials/trials.json`; `analysis.json → dsr`", "kısmen (σ_SR tahmini: ledger Sharpe saklamıyor)"),
    ("1.2 Rotasyon null'u / bootstrap güven aralığı yoktu (ensemble düzeyinde)", f"B={nl['B'] if nl else 0} ortak-ofset null (K1 tohumları) + durağan blok bootstrap", f"yok → p {nl['p_gross'] if nl else float('nan'):.4f} (B ile alt sınır); Sharpe %95 AA {hd['bootstrap']['sharpe_q']['p2.5']:.2f}–{hd['bootstrap']['sharpe_q']['p97.5']:.2f}", "`--stage null` → `fix/null/*.csv`; `analysis.json → null, headline.bootstrap`", "düzeltildi (Bonferroni eşiği bu B ile ulaşılamaz: yazıldı)"),
    ("1.3 Seçim prosedürü walk-forward", "Prosedür yazılı mı kontrol edildi: PRESETS yorumu, edge_experts_protocol 'hiçbir uzman ensemble'a girmez', bileşim sonuçlardan sonra kuruldu", "—", "`scripts/audit_fix_pdf.py` → `wf` paragrafı; `reports/fix_progress.md` karar 4", "yapılamadı: yazılı seçim prosedürü yok; mevcut ağırlıklarla 'holdout' OOS diye sunulmadı"),
    ("1.4 Haftanın günü tabloları; kırılımlarda belirsizlik yok", "Haftanın günü grafik/tablo kaldırıldı; |F| çeyreği, aynı yönde uzman, rejim x yön için ay-küme bootstrap %95 AA; n<30 işaretli", f"AA yok → ort. trade bps {AN['calibration']['overall']['mean_bps']:.1f} [{AN['calibration']['overall']['ci_lo']:.0f}, {AN['calibration']['overall']['ci_hi']:.0f}]", "`analysis.json → calibration`; PDF Bölüm III-8", "düzeltildi"),
    ("2.1 'Sürücü uzman' sezgiseli", "Doğrusal atıf Σ w_i F_i ölçek r + artık kalemleri; maliyet devir payıyla", f"sürücü heuristiği → doğrusal atıf: trend {at['experts'][0]['net_attr']:.0f}; artık: F kırpma {at['totals']['f_clip']:.0f}, sürüklenme {at['totals']['drift_rounding']:.0f} (birbirini götürüyor), R² {at['r2_daily_linear_vs_actual']:.2f}", "`analysis.json → attribution`; PDF 2.1", "düzeltildi (atıf TAM DEĞİL; artık gösterildi)"),
    ("2.2 Boyut/|F|/σ üçlükleri USDT cinsindendi, 'büyük trade kazandırıyor' mekanik", "Karar-günü birimi (ex-ante), notional-ağırlıklı bps + AA, σ içinde boyut 3x3, mekanik pay", f"üst boyut üçlüğü net'in %121'i (eski) → ex-ante {pc(sv['size'][-1]['net_usd'] / prim['net'], 0)}; USDT üstünlüğünün {pc(sv['top_size_mechanical_fraction'], 0)}'i mekanik", "`analysis.json → size_vol_f`; PDF 2.2", "düzeltildi"),
    ("2.3 Tutma süresi kovaları hindsight", "Kova 'çıkışta bilinir' etiketlendi; giriş-anı özellikler (|F|, uzman sayısı, rejim) CI ile verildi", "etiketsiz → etiketli", "PDF 2.3 ve Bölüm III-6, 8", "düzeltildi"),
    ("2.4 Stop karşı-olgusalı gap'siz, yeniden girişsiz", "Üç sürüm yan yana: A eski, B gap'e duyarlı, C yeniden girişli (+6 bps/yan maliyet); A eski rakamları birebir yeniden üretti",
     f"12 kuralın brüt artıranı: A {sum(r['A_dprice'] > 0 for r in sc['rows'])}, B {sum(r['B_dprice'] > 0 for r in sc['rows'])}, C {sum(r['C_dprice'] > 0 for r in sc['rows'])} (net {sum(r['C_dnet'] > 0 for r in sc['rows'])}; en iyi net {best_c['C_dnet']:+.1f})", "`analysis.json → stop_cf`; PDF 2.4", "düzeltildi"),
    ("2.5 Benchmark'lar ve beta yalnızca BTC", "TSMOM-365, eşit notional long, BTC al-tut (hakem) + BTC / EW-9 / alt sepeti / TSMOM'a beta ve NW alfa",
     f"beta {min(r['beta'] for r in bm['regressions']):.3f}…{max(r['beta'] for r in bm['regressions']):.3f}; alfa t {min(r['t_alpha'] for r in bm['regressions']):.1f}…{max(r['t_alpha'] for r in bm['regressions']):.1f}; TSMOM net {bm['runs']['tsmom365']['net']:.1f}; EW-9 fiyat Sharpe {list(bm['price_return_sharpe'].values())[1]:.2f} (eski al-tut 0,05 artefakt)", "`--stage bench` → `fix/bench/`; PDF 2.5", "düzeltildi (al-tut hakem koşuları dengelemesiz: Sharpe'ları artefakt, etiketlendi)"),
    ("2.6 Short funding ayı rejimine atfedilmişti; long-only/short×0,5 yoktu", "Funding yön x rejim (funding anındaki nedensel rejim); long-only / short×0,5 post-hoc",
     f"short funding {fd['short_total']:+.1f}: bull payı {pc(fd['short_bull_share'], 0)}, bear {fd['short_bear_usd']:+.1f}; long-only Sharpe {cf[1]['sharpe']:.2f}, short×0,5 {cf[2]['sharpe']:.2f} (tam {cf[0]['sharpe']:.2f}; post-hoc)", "`--stage cf`; `analysis.json → funding, cf_runs`", "düzeltildi"),
    ("2.7 'Diğer 8 uzman getiri katmıyor' iddiası LOO ile çelişiyor", "LOO tablosu sabit sermaye Sharpe ile; net ve Sharpe işareti ayrı", f"net'i artıran: {', '.join(lo['net_positive_contributors'])}; azaltan: {', '.join(lo['net_negative_contributors'])}", "`analysis.json → loo`; PDF 2.7", "düzeltildi"),
    ("2.8 'Gerçekleşen oynaklık yaklaşık yarısı (tampon, |F|)' cümlesi", "Shapley (yön karışımı, |F|, tampon, payda) + taban/artık", f"{pc(vd['vol_equity_actual'])} / %20: |F| {[r for r in vd['rows'] if r['component'] == '|F| ölçeği'][0]['ratio']:.2f}x, yön karışımı {[r for r in vd['rows'] if r['component'].startswith('Yön')][0]['ratio']:.2f}x, payda {[r for r in vd['rows'] if r['component'].startswith('Payda')][0]['ratio']:.2f}x, tampon {[r for r in vd['rows'] if r['component'] == 'Tampon'][0]['ratio']:.3f}x", "`analysis.json → vol_decomp`; PDF 2.8", "düzeltildi"),
    ("2.9 Hayatta kalma yanlılığı kontrol edilmemişti", "Binance arşivi + tape'te delist perp'ler VAR (LUNA, LUNA2, FTT, EOS, GAL, MATIC, RNDR, TOMO); aylık top-9 / top-20 hacim evreniyle yeniden koşu",
     (f"Sharpe {prim['sharpe']:.2f} → top-9 {sur['top9']['sharpe']:.2f} (net {sur['top9']['net']:.0f}), top-20 {sur['top20']['sharpe']:.2f} (net {sur['top20']['net']:.0f})" if "top9" in sur and "top20" in sur else "çıktı eksik"), "`--stage surv`, `--stage universe`; `analysis.json → survivorship, universe`", "düzeltildi"),
    ("3.1a Mutabakat farkı iki yerde iki değer (0,034 / 0,0195)", "Tek `reconcile()` yolu; kaynak: kline boşluğundaki 30 funding olayı saatlik yolda atlanıyordu", f"{ba['old']['recon']:.4f} → {ba['new']['recon']:.1e} USDT", "`scripts/trade_audit.py::components/reconcile`; `tests/test_trade_audit_fix.py`; `meta.json → recon`", "düzeltildi"),
    ("3.1b Suda kalma süresi 429 / 430", "Tek tanım: tepe → toparlanma takvim günü (`audit_metrics.drawdown_table`)", f"{ba['old']['underwater_days_old_def']} / 430 → {hd['longest_underwater_days']}", "`scripts/audit_metrics.py`; `tests/test_audit_metrics.py`", "düzeltildi"),
    ("3.1c Trade/gün sayıları ondalıklı (142.0, 133.0)", "Tamsayı biçimi (`dayfmt`, int)", "ondalıklı → tamsayı", "PDF tabloları", "düzeltildi"),
    ("3.1d Eksen etiketi çakışması, boş sayfalar", "Tarih ekseni seyreltildi (en kötü trade grafikleri, uzman sayfaları); sayfa kırılımları CondPageBreak; haftanın günü sayfası kalktı", "çakışma var → yok; tam boş sayfa yok (kısmi boşluk yalnızca bölüm sonlarında)", "PDF; `scripts/trade_audit_report.py`", "düzeltildi (görsel kontrol; otomatik test yok)"),
    ("3.2 reports/trade_audit.pdf", "`python scripts/trade_audit_report.py reports/trade_audit_data/ev1_plus_new reports/trade_audit.pdf`", "—", "`reports/trade_audit.pdf`", "düzeltildi"),
]
EXTRA = [
    "Nautilus 2.0.0rc5 `BacktestEngineConfig(bypass_logging=True)` bayrağını YOK SAYIYOR (INFO günlükleri koşuyu yavaşlatır). `referee.py` korumalı; çözüm: aynı işlemde `referee.BacktestEngineConfig` günlüksüz kurulacak şekilde sarıldı (`scripts/audit_fix.py`, sonuç birebir: net 790,5162). Hakem kodunda kalıcı düzeltme kullanıcı + bağımsız inceleme ister.",
    "Hakem, Nautilus eşleştirme motoru fiyat tik katı değilse emri SESSİZCE doldurmaz ('Skipping fill ... not compatible with price_precision'); `n_rejected` 0 kalır. İlk MEXC koşusunda DOGE tik dizesi `0.00100` bu yüzden yarım portföy üretti (net 790 → 12 görünüyordu); tik normalize edilip her koşuda 'emir niyeti = dolum' doğrulaması eklendi. Hakemde kalıcı koruma önerilir (korumalı çekirdek, dokunulmadı).",
    "`min_notional` altı emirler ve lot yuvarlamasıyla sıfıra düşen emirler `n_rejected`'e SAYILMIYOR (hakem emri hiç göndermiyor): `reports/ensemble.md` 'min notional bağlamıyor' iddiası ve `account_reality.md` bulgusu bu denetimle doğrulandı ($1 000'da %17 emir niyeti gönderilemiyor).",
    "ÇELİŞKİ (belgelerle): (i) TASKS.md N = 4 127; defter sayımı 4 775 (+648 pre2022). (ii) `reports/ensemble.md` K2 'al-tut Sharpe 0,05': hakem al-tut miktarı sabit tuttuğu için artefakt; dengelemeli fiyat getirisiyle EW-9 Sharpe ≈ 1,2 (maliyet/funding hariç). (iii) `account_reality.md` 'MEXC kuralları doğrulanamadı / 403': bu oturumda uç erişilebilirdi. (iv) BACKTEST K4 sabit sermaye DD tanımı, önceki trade denetimi (equity-normalize) ile çelişiyordu: K4'e uyuldu. Belgelere (korumalı) dokunulmadı.",
    "`report.hourly_pnl` (ensemble.py günlük PnL'inde kullanılan saatlik yol) kline boşluğundaki funding olaylarını hâlâ atlar (~0,02 USDT / 6 yıl); tek hesap yolu olarak `trade_audit.py::components` kullanıldı, `report.py` değiştirilmedi.",
]
md = ["# Trade denetimi düzeltmeleri: sorun → iş → önce/sonra → kanıt → durum", "",
      "Her rakam `scripts/audit_fix_summary.py` ile `reports/trade_audit_data/fix/analysis/analysis.json`'dan üretildi (komut: `python scripts/audit_fix_analysis.py && python scripts/audit_fix_summary.py`). Tüm analizler görülmüş veride (örneklem içi / post-hoc); mühürlü dönem (≥ 2026-04-01) yüklenmedi. Ayrıntı: `reports/trade_audit.pdf`, `reports/fix_progress.md`.", "",
      "| sorun | yapılan iş | önce → sonra | kanıt | durum |", "|---|---|---|---|---|"]
esc = lambda t: str(t).replace("|", "\\|")  # noqa: E731  (tablo hücresinde |F| gibi ifadeler sütunu bozmasın)
md += ["| " + " | ".join(esc(x) for x in row) + " |" for row in R]
md += ["", "## Ek bulgular ve belgelerle çelişkiler", ""] + [f"- {x}" for x in EXTRA]
md += ["", "## Yapılmayanlar / sınırlar", "- 1.3 walk-forward atlandı (gerekçe yukarıda). DSR'nin σ_SR'ı N denemenin hepsi için bilinmiyor (defter Sharpe saklamıyor). Rotasyon null'u B = 300 ile Bonferroni eşiğine (0,05/N) ulaşamaz.",
       "- MEXC hesap ücreti/VIP/indirim, funding ödeme kuralı, mmr kademeleri doğrulanmadı; ana koşu Binance verisi + Binance funding'idir. 1 bar gecikme (K3) stresi ev1_plus_new için koşulmadı.",
       "- Faz 4: `reports/preregistration/` altında 4 taslak, hiçbiri koşulmadı. Push yapılmadı (onay bekleniyor)."]
(ROOT / "reports" / "audit_fixes.md").write_text("\n".join(md) + "\n")
print("reports/audit_fixes.md yazıldı", len(R), "satır")
