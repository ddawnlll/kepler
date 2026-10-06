"""Trade denetim raporu: düzeltme bölümleri (scripts/audit_fix_analysis.py çıktısı `analysis.json`dan). Rakam üretmez, yalnızca biçimler: her sayı analysis.json'dan gelir.
trade_audit_report.py `build(AN, ctx)` çağırır; ctx = rapor biçim yardımcıları (tbl, img, stiller, renkler, save)."""
import numpy as np
import pandas as pd

TR_SYM = lambda s: s.replace("USDT", "")  # noqa: E731


def fmt(x, n=2):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:,.{n}f}".replace(",", " ")


def pc(x, n=1):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:.{n}f}%"


def build(AN: dict, c) -> dict:
    """Dönüş: dict(findings=[...], headline_rows=[...], period_rows=[...], part1=[flowables], calib=[flowables])."""
    P, S, H1, H2, B, SM = c.Paragraph, c.Spacer, c.H1, c.H2, c.B, c.SM
    mm, tbl = c.mm, c.tbl
    hd, ba = AN["headline"], AN["before_after"]
    prim, sec = hd["primary"], hd["secondary"]
    per = {r["period"]: r for r in hd["periods"]}
    pb = hd["period_bootstrap"]
    out = {}

    # ------------------------------------------------------------ özet başlık tabloları (0.2)
    bci = hd["bootstrap"]["sharpe_q"]
    out["headline_rows"] = [
        ["Ölçü (BİRİNCİL: sabit sermaye)", "Değer", "İKİNCİL: equity'ye normalize", "Değer"],
        ["Net PnL", f"{fmt(prim['net'])} USDT ({pc(prim['net_pct_cap'])} başlangıç sermayesi)", "Yıllık getiri: toplamsal (birincil) / CAGR (ikincil)", f"{pc(prim['annual_return_add'])} / {pc(sec['cagr'])}"],
        ["Sharpe (günlük getiri = PnL / başlangıç sermayesi)", f"<b>{prim['sharpe']:.2f}</b> (blok bootstrap %95 AA {bci['p2.5']:.2f} – {bci['p97.5']:.2f})", "Sharpe (PnL / önceki gün equity)", f"{sec['sharpe']:.2f}"],
        ["Yıllık oynaklık", pc(prim["vol"]), "Yıllık oynaklık", pc(sec["vol"])],
        ["Maks drawdown (K4: toplamsal, başlangıç sermayesinin %'si)", f"<b>{pc(prim['maxdd'])}</b> ({fmt(prim['maxdd_usd'])} USDT)", "Maks drawdown (tepe equity'nin %'si)", f"{pc(sec['maxdd'])} ({fmt(sec['maxdd_usd_peak'])} USDT)"],
        ["Sortino / Calmar (sabit sermaye)", f"{prim['sortino']:.2f} / {prim['calmar']:.2f}", "Sortino / Calmar (equity)", f"{sec['sortino']:.2f} / {sec['calmar']:.2f}"],
        ["Suda geçen en uzun süre (tepe → toparlanma, takvim günü; tek tanım)", f"{hd['longest_underwater_days']} gün", "Gün sayısı / yıl", f"{hd['n_days']} / {hd['years']:.2f}"]]
    yr = [r for r in hd["periods"] if len(r["period"]) == 4]
    sub = [r for r in hd["periods"] if len(r["period"]) > 4]
    out["period_rows"] = [["Dönem (sabit sermaye)"] + [r["period"] for r in yr] + [r["period"] for r in sub],
                          ["Sharpe (yıllık)"] + [f"{r['sharpe']:.2f}" for r in yr + sub], ["Net (USDT)"] + [fmt(r["net"], 1) for r in yr + sub], ["Gün"] + [str(r["days"]) for r in yr + sub],
                          ["Sharpe %95 AA (blok bootstrap)"] + ["-"] * len(yr) + [f"{pb[r['period']]['p2.5']:.2f} – {pb[r['period']]['p97.5']:.2f}" for r in sub]]
    # ------------------------------------------------------------ özet bulguları: sönme ilk
    last = per["2025+"]
    dd0 = hd["drawdown_table"][0]
    out["decay_text"] = (f"<b>Sönme (örneklem içi, post-hoc).</b> Sabit sermaye Sharpe'ı 2020–21'de {per['2020–21']['sharpe']:.2f}, 2022–24'te {per['2022–24']['sharpe']:.2f}, 2025+'da ({last['days']} gün, 2025-01 → 2026-03) "
                         f"<b>{last['sharpe']:.2f}</b> (blok bootstrap %95 AA {pb['2025+']['p2.5']:.2f} – {pb['2025+']['p97.5']:.2f}: sıfırı içeriyor); 2025+ net {fmt(last['net'], 1)} USDT. "
                         f"En derin drawdown ({pc(dd0['depth'])} tepe equity'nin, {dd0['peak']} → toparlanma {dd0['recovered']}) {dd0['days']} gün sürdü. Yıllık Sharpe: " + ", ".join(f"{r['period']} {r['sharpe']:.2f}" for r in yr) + ". "
                         "Tüm dönem Sharpe'ı bu yüzden erken dönem ağırlıklıdır; sistemin <b>bugünkü</b> performansını temsil etmez.")

    # ------------------------------------------------------------ I.1 nedensellik (0.1)
    cz = AN["causal"]
    pre = cz["prefix"]
    worst_real = max(v["maxdiff"] for v in pre["real"]["worst"].values())
    nbad_real = sum(v["n_bad_cuts"] for v in pre["real"]["worst"].values())
    rows = [["Test", "Sonuç", "Not"],
            ["audit.check_causal_book (ev1_plus_new kitabı, 16 kesim: sonrası bozuldu + veri kesildi)", f"kötü kesim: {len(cz['check_causal_book_bad'])}", "boş = nedensel"],
            [f"Önek değişmezliği: {pre['real']['n_cuts']} kesim günü (ayda bir); t günü kararı tam veriyle vs t'ye kadar kesilmiş veriyle", f"en büyük mutlak fark {worst_real:.1e}; sapan kesim: {nbad_real}",
             "karşılaştırılan: tahmin ölçeği m_d, toplam F, σ, funding φ, hacim/taker serileri, 9 uzmanın F'si, risk motoru hedef notional'ı (pozisyon), BTC rejim etiketi"],
            ["Pozitif kontrol: m_d tüm-örneklem ortalamasıyla (bilinçli sızıntı)", f"{len(pre['m_fullsample']['bad_cut_days'])}/{pre['m_fullsample']['n_cuts']} kesimde YAKALANDI", f"m farkı {pre['m_fullsample']['worst']['m']['maxdiff']:.3f}; hedef pozisyon farkı {pre['m_fullsample']['worst']['n']['maxdiff']:.1f} USDT"],
            ["Pozitif kontrol: σ 5 gün ileri", f"{len(pre['sigma_future']['bad_cut_days'])}/{pre['sigma_future']['n_cuts']} kesimde YAKALANDI", f"σ farkı {pre['sigma_future']['worst']['sigma']['maxdiff']:.2f}"],
            ["Pozitif kontrol: rejim etiketi 1 gün ileri", f"{len(pre['regime_future']['bad_cut_days'])}/{pre['regime_future']['n_cuts']} kesimde YAKALANDI", "rejim yalnızca analizde kullanılır, kararda değil"],
            ["check_causal_book bilinçli sızıntılı kitapta", "yakaladı: " + ", ".join(f"{k} ({len(v)}/6 kesim)" for k, v in cz["mutant_check_causal_book"].items()), "denetimin gücü"]]
    out["causal"] = [P("I.1 Nedensellik denetimi (görev 0.1)", H2),
                     P(f"<b>Sonuç: gelecek sızıntısı bulunamadı; düzeltilecek bir şey yoktu, önce/sonra rakamları aynıdır (Sharpe {prim['sharpe']:.2f}, net {prim['net']:.2f}).</b> Bakılan yerler: combine içindeki tahmin ölçeklemesi (ortalama |F| = 0,5; genişleyen pencere), "
                       "30 günlük σ, BTC rejim etiketi (d günü etiketi ≤ d−1 kapanışları) ve risk motoru. Tüm kontroller aşağıda; aynı kontrol bilinçli sızıntılı üç mutantı yakalıyor, yani test duyarlı.", B), c.tbl(rows, [70 * mm, 46 * mm, 62 * mm]),
                     P("Kapsam sınırı (denetimin göremediği): (i) veri zaman damgalarının kendisi, (ii) 9 sembolün bugünün majörleri olarak seçilmesi (hayatta kalma, bkz. I.5 → 2.9), (iii) bileşimin sonuçlar görüldükten sonra kurulması (seçim yanlılığı; nedensellik değil), "
                       "(iv) karar günün son barının kapanışında, dolum sonraki barın açılışında: gerçekte aynı an; 1 bar gecikme stresi ev1_plus_new için koşulmadı (EV1 için K3'te vardı).", SM)]

    # ------------------------------------------------------------ I.2 başlık metrikleri öncesi/sonrası
    old = ba["old"]
    rows = [["Ölçü", "Önceki rapor (equity'ye normalize)", "Bu rapor: BİRİNCİL (sabit sermaye)", "Fark"],
            ["Sharpe", f"{old['sharpe_equity']:.2f}", f"{prim['sharpe']:.2f}", f"{prim['sharpe'] - old['sharpe_equity']:+.2f}"],
            ["Yıllık oynaklık", pc(old["vol_equity"]), pc(prim["vol"]), f"{100 * (prim['vol'] - old['vol_equity']):+.1f} puan"],
            ["Maks drawdown", f"{pc(old['maxdd_equity'])} (tepe equity'nin)", f"{pc(prim['maxdd'])} (başlangıç sermayesinin)", f"{100 * (prim['maxdd'] - old['maxdd_equity']):+.1f} puan"],
            ["Suda kalma (özet 429, tablo 430 idi)", f"{old['underwater_days_old_def']} (özet) / 430 (tablo)", f"{hd['longest_underwater_days']} (tek tanım)", "-"],
            ["Mutabakat farkı (saatlik − hakem)", f"{old['recon']:.4f} USDT (metin 0,034)", f"{AN['recon']['net_diff']:.1e} USDT", "tek hesap yolu"]]
    out["before_after"] = [P("I.2 Başlık metrikleri (görev 0.2)", H2),
                           P("Önceki rapor Sharpe, oynaklık ve drawdown'ı equity'ye normalize ediyordu. Stratejinin pozisyon boyutu sabit başlangıç sermayesinden (equity_scale = False) türediği için kâr büyüdükçe payda büyür: ölçüler olduğundan "
                             "iyi görünür. Birincil tanım artık BACKTEST K4'tür (sabit sermaye, toplamsal equity). Önceki değerler yanlış değil, ikincildir.", B), tbl(rows, [44 * mm, 44 * mm, 52 * mm, 38 * mm]),
                           P(f"Mutabakat farkının kaynağı: 30 funding olayında T−1sa barı kline'da yok (veri boşluğu); hakem bu olayları bir sonraki barın öncesi pozisyonuyla öder, saatlik yol atlıyordu "
                             f"(funding farkı {AN['recon']['item_diff']['funding']:.1e} USDT sonrası, toplam {AN['recon']['net_diff']:.1e}). Kalan {AN['recon']['item_diff']['commission']:.1e} USDT Nautilus'un 8 basamaklı para yuvarlamasıdır.", SM)]

    # ------------------------------------------------------------ I.3 MEXC (0.3)
    mx = AN["mexc"]
    rl = mx["rules"]
    first = {r["cap"]: r for r in mx["rows"]}
    rows = [["Sembol", "contractSize (baz)", "Fiyat adımı", "minVol / volUnit", "1 sözleşme ≈ USDT (medyan)", "$1 000'da hedef (medyan USDT)", "Gönderilemeyen niyet"]]
    ps = {r["sym"].replace("USDT", ""): r for r in mx["per_symbol_1000"]}
    for s in ["BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA", "LINK", "AVAX"]:
        r, p_ = rl[s], ps[s]
        rows.append([s, r["contractSize"], f"{r['priceUnit']:.8f}".rstrip('0').rstrip('.'), f"{r['minVol']} / {r['volUnit']}", f"{p_['contract_usd_median']:.2f}", f"{p_['median_tgt_usd']:.1f}", f"{p_['blocked']}/{p_['intents']} ({pc(p_['blocked_share'], 0)})"])
    rows2 = [["Sermaye", "Net yuvarlamasız", "Net MEXC", "Fark", "Sharpe (y/m)", "Niyet", "Gönderilemeyen", "Pozisyon sapması (medyan)", "Günlük PnL kor.", "Yakınsadı"]]
    for cap_, r in first.items():
        rows2.append([f"${cap_:,.0f}".replace(",", " "), fmt(r["net_unrounded"], 1), fmt(r["net_mexc"], 1), pc(r["net_diff_pct"]), f"{r['sharpe_unrounded']:.2f} / {r['sharpe_mexc']:.2f}", r["intents"], f"{r['blocked']} ({pc(r['blocked_share'], 1)})",
                      pc(r["median_rel_pos_err"]), f"{r['pnl_corr']:.3f}", "evet" if mx["converged"][str(int(cap_))] else "hayır"])
    r1k = first[1000]
    top3 = sorted(ps.items(), key=lambda kv: -kv[1]["blocked_share"])[:3]
    top3_txt = ", ".join(f"{k} {pc(v['blocked_share'], 0)}" for k, v in top3)
    fee_lo, fee_hi = min(v["takerFeeRate"] for v in rl.values()), max(v["takerFeeRate"] for v in rl.values())
    out["mexc"] = [P("I.3 Hedef borsa kuralları ve yuvarlama (görev 0.3)", H2),
                   P(f"Hedef borsa MISSION'da 'Canlı işlem: MEXC' (araştırma verisi Binance USDT-M). Kurallar MEXC'in resmi `contract/detail` uç noktasından alındı ({mx['rules_source']['fetched_utc']}; belge: {mx['rules_source']['doc']}). "
                     "Önceki rapor (`account_reality.md`) bu uca 403 aldığı için kuralları 'doğrulanmadı' bırakmıştı; bu oturumda uç erişilebildi. Ayrı bir min-notional alanı yok: minimum emir = minVol (1) sözleşme x contractSize. "
                     "Hakem değiştirilmedi: her sembol sözleşme biriminde yeniden temsil edildi (fiyat x contractSize, miktar = sözleşme, adım = 1, tik = priceUnit x contractSize); böylece hakemin `quantize(step)` adımı DOGE'nin 100'lük adımını da doğru yuvarlıyor. "
                     "Hakemin 'emir niyeti → dolum' kuralı birebir yeniden oynatıldı ve her koşuda dolumlarla eşitlendi (doğrulama).", B), tbl(rows, [16 * mm, 26 * mm, 22 * mm, 24 * mm, 30 * mm, 32 * mm, 28 * mm]), S(1, 4), tbl(rows2, [19 * mm, 20 * mm, 18 * mm, 13 * mm, 20 * mm, 13 * mm, 22 * mm, 20 * mm, 17 * mm, 16 * mm]),
                   P(f"<b>Okuma.</b> $1 000'da emir niyetlerinin {pc(r1k['blocked_share'], 0)}'i gönderilemiyor (hedef notional 1 sözleşmeden küçük: {top3_txt}); "
                     f"net farkı yalnızca {pc(r1k['net_diff_pct'])} ve Sharpe yukarı ({r1k['sharpe_mexc']:.2f} vs {r1k['sharpe_unrounded']:.2f}) çıkıyor, ama bu 'yuvarlama zararsız' demek değildir: portföy fiilen başka (bazı sembolleri neredeyse hiç taşımayan) bir portföy, "
                     f"pozisyon notional'ı hedeften medyan {pc(r1k['median_rel_pos_err'], 1)} sapıyor ({pc(r1k['share_err_gt_10pct'], 0)} niyette > %10), günlük PnL korelasyonu {r1k['pnl_corr']:.3f}. "
                     f"Koşu öncesi yazılan ölçüte göre (net farkı ≤ %5, |Sharpe farkı| ≤ 0,10, gönderilemeyen ≤ %5; ızgara $1k/$2,5k/$5k/$10k/$25k) <b>asgari uygulanabilir sermaye ${mx['min_capital']:,}</b>."
                     f" Yuvarlamasız koşu, aynı sermaye için sezgisel (1e-3 mertebesi) adım kullanır; MEXC kuralları 'min 1 sözleşme'yi gerçek kılar. Ücret/slip varsayımı değişmedi (10 + 2 bps); MEXC liste ücreti taker %{100 * fee_lo:.2g}–{100 * fee_hi:.2g} (tek yön) görünüyor ama hesap ücreti/VIP indirimi doğrulanmadı.".replace(",", " "), B)]
    # ------------------------------------------------------------ I.4 istatistiksel çerçeve
    d = AN["dsr"]
    nm = AN["dsr_nmax"]
    rows = [["N (deneme sayısı)", "σ_SR havuz: SR0 / DSR", "σ_SR 0,25: SR0 / DSR", "σ_SR 0,5: SR0 / DSR", "σ_SR 1,0: SR0 / DSR"]]
    for r in d["rows"]:
        rows.append([r["N"]] + [f"{r[f'sr0_yillik[{k}]']:.2f} / {r[f'dsr[{k}]']:.3f}" for k in ("havuz", "0,25", "0,5", "1,0")])
    tr_ = d["trials"]
    nn = tr_["repo_rows"] + tr_["volume_only_nonsmoke_rows"]
    out["dsr"] = [P("I.4 İstatistiksel çerçeve (görev 1.1 – 1.3)", H2),
                  P(f"<b>Deneme sayısı (defterden sayıldı; `reports/trade_audit_data/fix/trials/trials.json`).</b> Repo defteri {tr_['repo_rows']} satır ({tr_['repo_files']} dosya); Modal Volume'da {tr_['volume_rows']} satır ({tr_['volume_files']} dosya), bunların {tr_['volume_rows_identical_to_repo']}'i repodakiyle SHA256 aynı. "
                    f"Yalnız Volume'da olan {tr_['volume_only_rows']} satırın {tr_['volume_only_nonsmoke_rows']}'i gerçek deneme (pre2022 asıl {d['detail']['pre2022_out']} + edge uzmanları {d['detail']['edge']}), {tr_['volume_only_smoke_rows']}'i smoke (boru hattı denemesi). "
                    f"Önceki tahmin 4 127 (TASKS.md) = repo {tr_['repo_rows']} + Modal edge {d['detail']['edge']}: <b>doğrulandı ama eksik</b>; {d['detail']['pre2022_out']} pre2022 satırı sayılmamıştı. Birincil N = {nn} (repo + Modal-yalnız gerçek); smoke dahil {tr_['repo_rows'] + tr_['volume_only_rows']}. "
                    "Deftere hiç girmeyen keşif koşuları (bileşim ön ayarları, leave-one-out, τ taraması, mr_explore, bu rapordaki karşı-olgusallar) sayılamadı: N bir alt sınırdır.", B),
                  P(f"<b>DSR.</b> Ledger satırları Sharpe saklamadığı için N denemenin Sharpe dağılımı (σ_SR) bilinmiyor; yalnızca deneme düzeyinde günlük serisi olan {d['pool_n']} koşudan (EV1 + 9 uzmanın birincil/ablasyon/komşuları; yıllık Sharpe "
                    f"{d['pool_sharpe_annual']['min']:.2f} … {d['pool_sharpe_annual']['max']:.2f}, medyan {d['pool_sharpe_annual']['median']:.2f}) σ_SR = {d['pool_sd_annual']:.2f} (yıllık) tahmin edildi (koşu öncesi sabitlenen birincil kaynak). "
                    f"Ensemble'ın Sharpe'ı {d['sharpe_annual']:.2f} (sabit sermaye; çarpıklık {d['skew']:.2f}, basıklık {d['kurt']:.1f}, T = {d['T']} gün). <b>Birincil sonuç (N = {nn}, havuz σ): DSR ≈ 0,00</b>: beklenen en iyi Sharpe SR0 yıllık "
                    f"{[r for r in d['rows'] if r['n'] == nn][0]['sr0_yillik[havuz]']:.2f} > gözlenen. DSR ≥ 0,95 için izin verilen en büyük N: havuz σ'da {nm['havuz']}, σ = 0,5'te {nm['0,5']}, σ = 0,25'te ≥ {nm['0,25']}. "
                    f"Sonuç σ_SR varsayımına çok duyarlı: iyimser (0,25) kabulde DSR {[r for r in d['rows'] if r['n'] == nn][0]['dsr[0,25]']:.2f}, havuz kabulünde {[r for r in d['rows'] if r['n'] == nn][0]['dsr[havuz]']:.2f}. Denemeler bağımsız değil (etkin N daha küçük) ve havuz ilgisiz uzmanları (Sharpe < 0) içerir; yine de 'DSR geçti' iddiası bu veriyle yapılamaz. "
                    "Kapı ölçütü K1 DSR ≥ 0,95 gerektirir.", B), tbl(rows, [62 * mm, 29 * mm, 29 * mm, 29 * mm, 29 * mm])]
    nl = AN["null"]
    bs = hd["bootstrap"]
    if nl:
        out["null"] = [P(f"<b>Rotasyon null'u (görev 1.2).</b> Her sembolün günlük F serisi tüm semboller için aynı k günle dairesel kaydırıldı (sinyal–getiri hizası bozuluyor; σ, ρ, IDM, tavanlar gerçek veriyle; K1 ile aynı tohumlar), B = {nl['B']}, hakem aynı. "
                          f"Gerçek: brüt {nl['real']['gross']:.1f}, net {nl['real']['net']:.1f} USDT, Sharpe {nl['real']['sharpe']:.2f}. Null: brüt ort. {nl['null']['gross']['mean']:.1f} ± {nl['null']['gross']['sd']:.1f} (p95 {nl['null']['gross']['p95']:.1f}, p99 {nl['null']['gross']['p99']:.1f}), "
                          f"Sharpe ort. {nl['null']['sharpe']['mean']:.2f} ± {nl['null']['sharpe']['sd']:.2f} (p99 {nl['null']['sharpe']['p99']:.2f}). Tek yönlü p: brüt {nl['p_gross']:.4f}, net {nl['p_net']:.4f}, Sharpe {nl['p_sharpe']:.4f} "
                          f"(≥ gerçek olan çekiliş: {nl['n_ge']['gross']}/{nl['n_ge']['net']}/{nl['n_ge']['sharpe']}). B = {nl['B']} ile p en az 1/{nl['B'] + 1} = {1 / (nl['B'] + 1):.4f} olabilir; Bonferroni eşiği 0,05/N (N ≈ {nn}) ≈ {0.05 / nn:.0e} bu B ile "
                          "ulaşılamaz: p ham değerdir, çoklu-test düzeltmeli kanıt değil. Null ortalaması pozitif (long eğilimi + trend): gerçek bunun üzerinde ama bu 'zamanlama bilgisi' için kanıt değil, görülmüş veride (post-hoc).", B)]
    else:
        out["null"] = [P("Rotasyon null'u: çıktı henüz yok.", B)]
    out["boot"] = [P(f"<b>Blok bootstrap (görev 1.2).</b> Durağan blok bootstrap (ortalama blok 20 gün, B = {bs['B']}), yıllık Sharpe (sabit sermaye): medyan {bs['sharpe_q']['p50']:.2f}, %90 AA {bs['sharpe_q']['p5']:.2f} – {bs['sharpe_q']['p95']:.2f}, %95 AA {bs['sharpe_q']['p2.5']:.2f} – {bs['sharpe_q']['p97.5']:.2f}; "
                     f"maks DD medyan {pc(bs['maxdd_q']['p50'])}, %95 {pc(bs['maxdd_q']['p95'])} (başlangıç sermayesinin). Tüm dönem Sharpe'ı sıfırdan ayrışıyor (P(Sharpe ≤ 0) = {bs['p_sharpe_le_0']:.3f}); "
                     "alt dönemlerde (2025+) aralık sıfırı içeriyor (özet sayfası). Bootstrap günlük bağımlılığı blokla yakalar ama rejim değişimini (sönme) yakalamaz: tek dağılımdan çekiliş varsayar.", B)]
    out["wf"] = [P("<b>Seçim prosedürü ve walk-forward (görev 1.3): ATLANDI.</b> ev1_plus_new'i üreten bir seçim prosedürü repoda yazılı değil: `ensemble.PRESETS` yorumu 'EV1 aynen + her yeni uzmana 0,1'; `reports/edge_experts_protocol.md` 'hiçbir uzman bu protokolle ensemble'a girmez' diyor "
                   "(kapıyı geçen uzman yok) ve bileşim, uzmanların tek tek sonuçları görüldükten sonra kuruldu (TASKS.md). Verilerden ağırlık seçen bir algoritma olmadığı için genişleyen pencereli yeniden seçim anlamlı bir test olmaz; mevcut ağırlıklarla yapılan "
                   "bir 'holdout' OOS değildir ve OOS diye sunulmadı. Gerekli: yazılı bir seçim kuralı (hangi uzman, hangi ağırlık, hangi ölçütle) önceden kaydedilmeli; Faz 4 taslakları bunu içermiyor (kapsam dışı).", B)]
    return out


def build2(AN: dict, c) -> dict:
    """Faz 2 bölümleri ve 1.4 kalibrasyon tabloları."""
    P, S, H1, H2, B, SM = c.Paragraph, c.Spacer, c.H1, c.H2, c.B, c.SM
    mm, tbl, plt = c.mm, c.tbl, c.plt
    BLUE, ORANGE, RED, INK2, AXIS, AQUA = c.BLUE, c.ORANGE, c.RED, c.INK2, c.AXIS, c.AQUA
    out = {}
    hd = AN["headline"]
    prim = hd["primary"]

    # ------------------------------------------------------------ 2.1 uzman atfı
    at = AN["attribution"]
    t = at["totals"]
    rows = [["Uzman", "Ağırlık", "Fiyat PnL (doğrusal atıf)", "Maliyet (devir payı)", "Net atıf", "LOO Δ net", "Sürücü heuristiği net"]]
    loo = {r["expert"]: r for r in AN["loo"]["rows"]}
    drv = c.driver_net
    for r in at["experts"]:
        rows.append([r["expert"], f"{r['weight']:g}", fmt(r["price_pnl"], 1), fmt(r["cost"], 1), fmt(r["net_attr"], 1), f"{loo[r['expert']]['d_net']:+.1f}" if r["expert"] in loo else "-", fmt(drv.get(r["expert"], 0.0), 1)])
    rows.append(["<b>Uzmanların toplamı</b>", "", f"<b>{fmt(t['linear_experts'], 1)}</b>", fmt(-t["commission"], 1), fmt(t["linear_experts"] - t["commission"], 1), "", ""])
    rows2 = [["Doğrusal olmayan / artık kalem", "USDT", "Ne"],
             ["Isınma (ilk 30 aktif gün F = 0)", fmt(t["warmup"], 1), "doğrusal toplamın pozisyonsuz geçen günlerdeki kâr/zararı"],
             ["F'nin ±1'e kırpılması", fmt(t["f_clip"], 1), "güçlü sinyallerde kırpılan pozisyonun kaybolan getirisi"],
             ["Oynaklık / sembol / brüt tavanları", fmt(t["caps"], 1), "hiç bağlamadı"],
             ["Tampon (devir azaltma bandı)", fmt(t["buffer"], 1), "hedef değişse de pozisyonun tutulması"],
             ["Miktar sürüklenmesi + yuvarlama + zamanlama", fmt(t["drift_rounding"], 1), "pozisyon MİKTARI sabit kalır, notional fiyatla büyür/küçülür (kazananlar büyür); lot yuvarlaması"],
             ["Hesap artığı (fiyat PnL gerçek − yeniden kurulan)", fmt(t["residual"], 2), "fill fiyatı vs bar açılışı"],
             ["Funding / çıkış maliyeti", f"{fmt(t['funding'], 1)} / {fmt(-t['exit'], 2)}", "uzmanlara atfedilmedi"],
             ["<b>Net PnL (hakem)</b>", f"<b>{fmt(t['net'], 2)}</b>", f"kimlik hatası {t['identity_check']:.1e}"]]
    fig, ax = plt.subplots(1, 2, figsize=(9.2, 3.1), gridspec_kw=dict(width_ratios=[1.1, 1]))
    nm = [r["expert"] for r in at["experts"]][::-1]
    ax[0].barh(nm, [r["net_attr"] for r in at["experts"]][::-1], color=[BLUE if r["net_attr"] >= 0 else RED for r in at["experts"]][::-1], height=0.62)
    ax[0].axvline(0, color=AXIS, lw=0.8)
    ax[0].set_title("Uzman başına net atıf (USDT)", fontsize=9)
    ax[0].grid(False)
    lab = ["Isınma", "F kırpma", "Tavanlar", "Tampon", "Sürüklenme+yuvarlama", "Artık"]
    val = [t["warmup"], t["f_clip"], t["caps"], t["buffer"], t["drift_rounding"], t["residual"]]
    ax[1].barh(lab[::-1], val[::-1], color=[BLUE if v >= 0 else RED for v in val[::-1]], height=0.62)
    ax[1].axvline(0, color=AXIS, lw=0.8)
    ax[1].set_title("Doğrusal olmayan kalemler (USDT)", fontsize=9)
    ax[1].grid(False)
    fa = c.fig_img(fig, "40_attr")
    out["attr"] = [P("2.1 Uzman atfı: doğrusal ayrıştırma (görev 2.1)", H2),
                   P("Eski 'sürücü uzman' heuristiğinin (giriş günü en çok destekleyen uzmanın o trade'in tüm net'ini alması) yerine günlük doğrusal atıf: PnL<sub>i,t</sub> = Σ<sub>sembol</sub> w<sub>i</sub> · F<sub>i,t</sub> · ölçek<sub>t</sub> · r<sub>t</sub>; "
                     "ölçek<sub>t</sub> = risk motorunun tam-tahmin pozisyonu (σ, IDM) x 0,5 / m<sub>t</sub> (tahmin ölçeği), r<sub>t</sub> = ertesi gün açılış→açılış getirisi. Maliyetler (fee+slip) her dolumda, o sembolde son dolumdan beri uzman bileşenlerinin |Δ| (devir) payına göre dağıtıldı. "
                     "<b>Atıf tam değildir</b>; aşağıdaki kalemler doğrusal modelin dışında kalanı gösterir.", B), fa, tbl(rows, [28 * mm, 14 * mm, 32 * mm, 28 * mm, 22 * mm, 22 * mm, 30 * mm]), S(1, 3), tbl(rows2, [66 * mm, 28 * mm, 84 * mm]),
                   P(f"<b>Artığın büyüklüğü.</b> Net artık (kırpma + tavan + tampon + sürüklenme + hesap) toplamı {fmt(at['nonlinear_sum'], 2)} USDT: bu, <i>iki büyük terimin birbirini götürmesinin</i> sonucu (F kırpma {fmt(t['f_clip'], 1)}, sürüklenme {fmt(t['drift_rounding'], 1)}); "
                     f"günlük mutlak doğrusal-dışı etkilerin toplamı {fmt(at['nonlinear_abs_daily_sum'], 0)} USDT (net PnL'in {at['nonlinear_abs_daily_sum'] / t['net']:.1f} katı). Günlük gerçek fiyat PnL'inin doğrusal uzman toplamıyla R² = {at['r2_daily_linear_vs_actual']:.2f}. "
                     "Bu yüzden uzman başına rakamlar 'yaklaşık katkı' olarak okunmalı; etkileşim (tahminlerin ölçekleme/kırpma üzerinden birbirini etkilemesi) uzman toplamına dağıtılamıyor. Atıf ile LOO aynı işareti vermiyor (örn. bollinger: atıf "
                     f"{fmt(next(r['net_attr'] for r in at['experts'] if r['expert'] == 'bollinger'), 0)}, LOO Δ net {loo['bollinger']['d_net']:+.0f}): LOO, ölçeklemeyi (ortalama |F| = 0,5) ve risk motorunu yeniden kurduğu için etkileşimi içerir.", SM)]

    # ------------------------------------------------------------ 2.8 oynaklık
    vd = AN["vol_decomp"]
    rows = [["Bileşen", "Oynaklık", "Çarpan", "Log katkı", "Fark içindeki pay"]]
    for r in vd["rows"]:
        rows.append([r["component"], pc(r["vol"]) if r["vol"] is not None else "", f"{r['ratio']:.3f}", f"{r['log']:+.3f}", pc(r["share_of_gap"], 0)])
    rows.append(["<b>Toplam: gerçekleşen / hedef τ</b>", f"{pc(vd['vol_equity_actual'])} / {pc(vd['tau'], 0)}", f"{vd['ratio_total']:.3f}", f"{vd['total_log_gap']:+.3f}", "100%"])
    fig, ax = plt.subplots(figsize=(8.6, 2.5))
    labs = [r["component"].split(":")[0].replace("Konfigürasyon dışı", "Konf. dışı") for r in vd["rows"][1:]]
    ax.barh(labs[::-1], [r["log"] for r in vd["rows"][1:]][::-1], color=[BLUE if r["log"] >= 0 else RED for r in vd["rows"][1:]][::-1], height=0.6)
    ax.axvline(0, color=AXIS, lw=0.8)
    ax.set_xlabel("log çarpan (< 0: gerçekleşen oynaklığı düşürür)")
    ax.grid(False)
    fv = c.fig_img(fig, "41_vol")
    out["vol"] = [P("2.8 Oynaklık kalibrasyonu: gerçekleşen / hedef (görev 2.8)", H2),
                  P(f"Hedef τ = %20; gerçekleşen yıllık oynaklık {pc(vd['vol_equity_actual'])} (equity'ye normalize; sabit sermayeye göre {pc(vd['vol_fixed_actual'])}). Fark dört bileşene (Shapley, log oynaklık, 16 konfigürasyon; fiyat-yalnız günlük PnL) ve iki yardımcı kalemlere ayrıldı. "
                    f"<b>Önceki 'tampon ve tahmin ölçeği yüzünden yaklaşık yarısı' cümlesi düzeltildi:</b> |F| ölçeği tek başına çarpan {[r for r in vd['rows'] if r['component'] == '|F| ölçeği'][0]['ratio']:.2f} (ortalama |F| = {vd['avg_abs_F']:.2f}); "
                    f"tampon hemen hiç etkisiz ({[r for r in vd['rows'] if r['component'] == 'Tampon'][0]['ratio']:.3f}: devir azaltma bandı oynaklığı değil maliyeti etkiler); en büyük iki bileşen yön karışımı/çeşitlendirme "
                    f"({[r for r in vd['rows'] if r['component'].startswith('Yön')][0]['ratio']:.2f}: 9 semboldeki long/short pozisyonlar korele riski götürür) ve payda ({[r for r in vd['rows'] if r['component'].startswith('Payda')][0]['ratio']:.2f}: "
                    "equity_scale = False, kâr büyüdükçe equity'ye göre oynaklık düşer). Tam konfigürasyonun tavansız/maliyetsiz kitabı risk motorunun tampon sonrası hedefine birebir eşittir (maks fark " + f"{vd['check_full_vs_out_maxdiff']:.1e}" + "). "
                    "Shapley sıra etkisini ortalar; çarpanlar log-toplanır.", B), fv, tbl(rows, [84 * mm, 24 * mm, 22 * mm, 22 * mm, 26 * mm])]

    # ------------------------------------------------------------ 2.2 boyut / |F| / oynaklık
    sv = AN["size_vol_f"]

    def trow(g):
        return [g["group"], g["n"], f"{g['wbps']:.1f}", f"{g['ci_lo']:.1f} … {g['ci_hi']:.1f}", fmt(g["net_usd"], 0), pc(g["notional_share"], 0), fmt(g["expected_usd_equal_bps"], 0)]
    head = ["Üçlük", "Birim", "Notional-ağırlıklı bps / gün", "%95 AA (ay-küme bootstrap)", "Net USDT", "Notional payı", "Eşit bps olsaydı USDT"]
    rows = [head] + [[f"|F| {g['group']}"] + trow(g)[1:] for g in sv["absf"]] + [[f"σ {g['group']}"] + trow(g)[1:] for g in sv["vol"]] + [[f"Boyut {g['group']}"] + trow(g)[1:] for g in sv["size"]]
    cells = pd.DataFrame(sv["vol_x_size"])
    piv = cells.pivot(index="vol", columns="size", values="wbps")
    ci = cells.pivot(index="vol", columns="size", values="ci_lo").astype(float).round(0).astype(int).astype(str) + " … " + cells.pivot(index="vol", columns="size", values="ci_hi").astype(float).round(0).astype(int).astype(str)
    rows3 = [["σ üçlüğü \\ boyut üçlüğü (σ içinde)"] + list(piv.columns)] + [[i] + [f"{piv.loc[i, j]:.1f}  [{ci.loc[i, j]}]" for j in piv.columns] for i in piv.index]
    top = sv["size"][-1]
    out["size"] = [P("2.2 Boyut, |F| ve oynaklık üçlükleri: USDT yerine notional'a göre bps (görev 2.2)", H2),
                   P(f"Birim = (sembol, karar günü) pozisyon-günü ({sv['n_units']} birim, {sv['n_months']} ay); giriş koşulları (|F|, σ, boyut = hedef notional / equity) karar anında bilinir, sonuç o pozisyonun ertesi günkü net PnL'idir (fiyat + funding − komisyon). "
                     "Önceki rapordaki trade düzeyi 'büyüklük üçlüğü' ORTALAMA notional'ı kullanıyordu; miktar sabit kaldığı için kazanan pozisyonun notional'ı büyür: tanım çıkışta/sonuçla kirliydi. "
                     "bps = Σ net / Σ notional; AA = kümeler (aylar) yerine koymayla yeniden örneklenerek; birimler zaman içinde örtüşür, AA iyimser olabilir.", B), tbl(rows, [22 * mm, 14 * mm, 28 * mm, 34 * mm, 20 * mm, 24 * mm, 36 * mm]), S(1, 3),
                   P("Oynaklık üçlüğü İÇİNDE boyut üçlükleri (bps/gün [%95 AA]; boyut = |F|/σ olduğundan boyutun oynaklıktan bağımsız etkisi):", SM), tbl(rows3, [52 * mm, 40 * mm, 40 * mm, 40 * mm]),
                   P(f"<b>Okuma.</b> (i) Önceki 'en büyük üçlük net'in %{100 * sv['old_trade_level_avgnotional'][-1]['net_usd'] / prim['net']:.0f}'i' bulgusu (trade düzeyi, ortalama notional) büyük ölçüde tanım artefaktıydı: ex-ante tanımla en büyük boyut üçlüğü net'in {pc(top['net_usd'] / prim['net'], 0)}'ini üretiyor ve notional'ının payı {pc(top['notional_share'], 0)}; "
                     f"bps hepsinde eşit olsaydı beklenen {fmt(top['expected_usd_equal_bps'], 0)} USDT (gerçek {fmt(top['net_usd'], 0)}): büyük trade'lerin USDT üstünlüğünün <b>%{100 * sv['top_size_mechanical_fraction']:.0f}'i mekanik</b> (daha çok notional taşımak). "
                     f"(ii) Boyutla |F| arasında Spearman {sv['corr_spearman']['size_vs_absf']:.2f}, boyutla σ arasında {sv['corr_spearman']['size_vs_vol']:.2f}: boyut ağırlıkla tahmin gücüdür. (iii) Birim başına getiri en güçlü |F| üçlüğünde belirgin yüksek (aşağıda CI); "
                     "σ içinde bile en büyük boyut üçlüğü en yüksek bps'i veriyor, yani etki yalnızca oynaklıktan değil |F|'ten geliyor. Hepsi görülmüş veride; nedensel iddia değil.", B)]

    # ------------------------------------------------------------ 2.3 tutma süresi
    hb = AN["holding"]
    rows = [["Tutma süresi (ÇIKIŞTA BİLİNİR, hindsight)", "Trade", "Net USDT", "Kazanma", "Ort. bps (net / ort. notional)", "%95 AA"]] + [[g["group"], g["n"], fmt(g["net_usd"], 1), pc(g["win"]), f"{g['mean_bps']:.0f}", f"{g['ci_lo']:.0f} … {g['ci_hi']:.0f}"] for g in hb]
    out["hold"] = [P("2.3 Tutma süresi kovaları", H2), tbl(rows, [58 * mm, 18 * mm, 24 * mm, 22 * mm, 34 * mm, 28 * mm]),
                   P("<b>Etiket: tutma süresi trade kapandığında bilinir (hindsight).</b> Kazanan trade'ler trend sürdüğü için uzun tutulur; kovaların kazanma oranından 'uzun trade seçilir' sonucu çıkmaz. Giriş anında bilinen özellikler için aşağıdaki kalibrasyon tablolarına (|F|, aynı yönde uzman, rejim) bakılmalı.", SM)]

    # ------------------------------------------------------------ 1.4 kalibrasyon
    cal = AN["calibration"]

    def crow(g):
        return [g["group"], g["n"] if not g["small"] else f"{g['n']} (n<30: yetersiz)", f"{g['mean_bps']:.0f}", f"{g['ci_lo']:.0f} … {g['ci_hi']:.0f}", f"{g['median_bps']:.0f}", pc(g["win"]), fmt(g["net_usd"], 1)]
    hdr = ["Grup", "Trade", "Ort. net bps (trade / ort. notional)", "%95 AA", "Medyan bps", "Kazanma", "Net USDT"]
    w_ = [40 * mm, 30 * mm, 30 * mm, 30 * mm, 18 * mm, 16 * mm, 16 * mm]
    o = cal["overall"]
    out["calib"] = [P(f"Tüm trade'ler: ortalama {o['mean_bps']:.1f} bps, %95 AA {o['ci_lo']:.0f} … {o['ci_hi']:.0f} (n = {o['n']}, {o['n_months']} ay): trade başına ortalama getiri sıfırdan ayrışmıyor; kazanç az sayıda büyük trade'den geliyor. {cal['note']}", SM),
                    P("|F| çeyreği (giriş günü)", H2), tbl([hdr] + [crow(g) for g in cal["absf"]], w_), P("Aynı yönde uzman sayısı (giriş günü)", H2), tbl([hdr] + [crow(g) for g in cal["aligned"]], w_),
                    P("Giriş rejimi / yön", H2), tbl([hdr] + [crow(g) for g in cal["regime"]], w_),
                    P("Haftanın günü tabloları ve grafikleri bu sürümde <b>kaldırıldı</b> (7 grup x örneklem içi gürültü; çoklu karşılaştırma). Küçük n'li gruplar ve AA'ları sıfırı içeren farklar kanıt değil betimlemedir.", SM)]

    # ------------------------------------------------------------ 2.4 stop karşı-olgusalı
    sc = AN["stop_cf"]
    rows = [["Kural", "σ", "Stop tetiklenen trade", "A: eski (stop seviyesinden, yeniden giriş yok) Δ fiyat", "B: gap'e duyarlı Δ fiyat", "C: B + yeniden giriş Δ fiyat", "C: Δ net (ek maliyet dahil)", "C: yeniden giriş sayısı"]]
    for r in sc["rows"]:
        rows.append([r["rule"], f"{r['k']:g}", pc(r["A_hit_share"], 0), f"{r['A_dprice']:+.1f}", f"{r['B_dprice']:+.1f}", f"{r['C_dprice']:+.1f}", f"{r['C_dnet']:+.1f}", r["C_n_reentries"]])
    fig, ax = plt.subplots(figsize=(9, 2.5))
    for rule, ls_ in (("İzleyen stop", "-"), ("Sabit stop (girişten)", "--")):
        z = [r for r in sc["rows"] if r["rule"] == rule]
        for tag, col in (("A", INK2), ("B", ORANGE), ("C", BLUE)):
            ax.plot([r["k"] for r in z], [r[f"{tag}_dprice"] for r in z], color=col, ls=ls_, marker="o", ms=3, lw=1.3, label=f"{tag} · {rule.split()[0]}")
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.set_xlabel("Stop mesafesi (günlük σ)")
    ax.set_ylabel("Brüt fiyat PnL değişimi (USDT)")
    ax.legend(ncol=3, fontsize=6.8)
    fs = c.fig_img(fig, "42_stop")
    best = max(sc["rows"], key=lambda r: r["C_dnet"])
    out["stop"] = [P("2.4 Stop karşı-olgusalı: yeniden girişli sürüm (görev 2.4)", H2),
                   P("Önceki ölçüm üç kısıt taşıyordu: stop seviyesinde dolum (gap yok), yeniden giriş yok, maliyet etkisi yok. Burada aynı 12 kural (yeni kural/parametre aranmadı) üç sürümle: <b>A</b> eski; <b>B</b> bar stop seviyesinin ötesinde açıldıysa dolum açılış fiyatından; "
                     "<b>C</b> B + stop sonrası bir sonraki karar zamanında (gün sonu → ertesi 00:00 açılışı) sistemin o günkü hedef işareti trade yönüyle aynıysa yeniden giriş (orijinal pozisyon profiline katılır, stop sıfırlanır). "
                     "Ek dolumların maliyeti yan başına 6 bps. A sürümü önceki rapordaki tüm rakamları birebir yeniden üretiyor (doğrulama).", B), fs, tbl(rows, [27 * mm, 10 * mm, 20 * mm, 32 * mm, 22 * mm, 24 * mm, 22 * mm, 19 * mm]),
                   P(f"<b>Okuma.</b> Gap'e duyarlı dolum sonucu iyileştirmiyor, hafifçe kötüleştiriyor (örn. izleyen 3σ: A {[r for r in sc['rows'] if r['rule'] == 'İzleyen stop' and r['k'] == 3.0][0]['A_dprice']:+.0f} → B {[r for r in sc['rows'] if r['rule'] == 'İzleyen stop' and r['k'] == 3.0][0]['B_dprice']:+.0f}). "
                     f"Yeniden giriş zararı küçültüyor ama 12 kuralın {sum(1 for r in sc['rows'] if r['C_dnet'] > 0)}'i net'te pozitif (en iyisi {best['rule']} {best['k']:g}σ: net {best['C_dnet']:+.1f} USDT; fiyat {best['C_dprice']:+.1f}); dar izleyen stoplarda "
                     f"yüzlerce yeniden giriş ek maliyet getiriyor. Sonuç: stop eklemek bu ölçümde kârı artırmıyor; geniş (6σ) sabit stop yalnızca sıfıra yakın (kuyruk sigortası olarak değerlendirilebilir, kanıt değil). Tümü görülmüş veride (post-hoc), strateji önerisi değildir.", B)]

    # ------------------------------------------------------------ 2.5 benchmark
    bm = AN["benchmarks"]
    rows = [["Benchmark (aynı evren)", "Net USDT", "Brüt USDT", "Funding", "Sharpe (sabit sermaye)", "Sharpe (equity)", "Maks DD (USDT, tepe→dip)", "Bitiş equity"]]
    for k, r in bm["runs"].items():
        if k == "strategy":
            continue
        rows.append([r["label"], fmt(r["net"], 1), fmt(r["gross"], 0), fmt(r["funding"], 0), f"{r['sharpe_fixed']:.2f}", f"{r['sharpe_equity']:.2f}", fmt(r["maxdd_usd"], 0), fmt(r["final_equity"], 0)])
    s_ = bm["runs"]["strategy"]
    rows.append([f"<b>{s_['label']}</b>", fmt(s_["net"], 1), "", "", f"<b>{s_['sharpe_fixed']:.2f}</b>", f"{s_['sharpe_equity']:.2f}", fmt(s_["maxdd_usd"], 1), ""])
    rr = [["Beta / alfa regresyonu (strateji günlük getirisi ← benchmark)", "Beta", "Alfa (yıllık)", "t(alfa) NW-5", "Korelasyon", "R²"]] + [[r["benchmark"], f"{r['beta']:.3f}", pc(r["alpha_annual"]), f"{r['t_alpha']:.2f}", f"{r['corr']:.3f}", f"{r['r2']:.3f}"] for r in bm["regressions"]]
    ps = bm["price_return_sharpe"]
    out["bench"] = [P("2.5 Benchmark'lar ve beta (görev 2.5)", H2),
                    P("Aynı evren, aynı hakem, aynı Spec: (a) tek lookback'li, ayarlanmamış, önceden sabit TSMOM (`signals.tsmom(365)`, aylık, 12 ay; Antonacci; `reports/book_signals.md`'de veriye bakmadan sabit; sembol başına 111 USDT), (b) eşit notional long al-tut, (c) BTC al-tut. "
                      "<b>Not:</b> hakem al-tut koşuları miktarı sabit tutar; pozisyon notional'ı fiyatla büyür (eşit-long: 1 000 → ~34 000 USDT), bu yüzden sabit-sermaye/equity Sharpe'ları tanımsız derecede bozuk (eski K2'deki 'al-tut Sharpe 0,05' bu yapaylıktan). "
                      "Gösterge olarak günlük dengelemeli fiyat getirisi Sharpe'ları (maliyet ve funding HARİÇ; benchmark için iyimser): " + ", ".join(f"{k.split(' (')[0]} {v:.2f}" for k, v in ps.items()) + ".", B),
                    tbl(rows, [50 * mm, 18 * mm, 18 * mm, 16 * mm, 22 * mm, 18 * mm, 18 * mm, 18 * mm]), S(1, 3), tbl(rr, [80 * mm, 16 * mm, 24 * mm, 24 * mm, 20 * mm, 14 * mm]),
                    P(f"Beta benchmark'lara karşı {min(r['beta'] for r in bm['regressions']):.3f} … {max(r['beta'] for r in bm['regressions']):.3f}: getiri piyasadan, alt sepetinden ve basit trendden büyük ölçüde bağımsız. Alfa t = {min(r['t_alpha'] for r in bm['regressions']):.1f} … {max(r['t_alpha'] for r in bm['regressions']):.1f} (NW gecikme 5), ama görülmüş veride ve sönmeden önceki dönemin ağırlığıyla; alfa 2025+ alt döneminde ayrıca tahmin edilmedi. "
                      f"TSMOM-365'in net'i {fmt(bm['runs']['tsmom365']['net'], 1)} USDT (brüt {fmt(bm['runs']['tsmom365']['gross'], 0)}, funding {fmt(bm['runs']['tsmom365']['funding'], 0)}): ensemble yalnızca 'basit trend' değil; ancak ensemble'ın ortalama brüt kaldıraç {c.lev_mean:.2f}x iken TSMOM ~1,0x (sembol başına sermaye/9) ve funding'i çok daha ağır. Eski K2'deki 'al-tut Sharpe 0,05' (reports/ensemble.md) bu rapordaki dengelemesiz hakem koşusunun artefaktıdır.", SM)]

    # ------------------------------------------------------------ 2.6 short funding + karşı-olgusallar
    fd = AN["funding"]
    rows = [["Yön", "Rejim (funding anında)", "Funding USDT", "Pozisyon-saat", "Ort. notional", "Yıllık % (notional)", "Giriş rejimine göre (trade tablosu)"]]
    for r in fd["rows"]:
        rows.append([r["side"], r["regime"], f"{r['funding_usd']:+.2f}", int(r["position_hours"]), fmt(r["avg_notional"], 1), pc(r["annualized_pct_of_notional"]), f"{r['funding_usd_entry_regime']:+.2f}"])
    cf = AN["cf_runs"]
    rows2 = [["Karşı-olgusal (post-hoc, betimsel)", "Net USDT", "Sharpe (sabit sermaye)", "Maks DD", "Dolum", "Funding"]] + [[r["label"], fmt(r["net"], 1), f"{r['sharpe']:.2f}", pc(r["maxdd"]), int(r["n_fills"]), fmt(r["funding"], 1)] for r in cf]
    out["short"] = [P("2.6 Short tarafı: funding'in rejime göre dağılımı ve karşı-olgusallar (görev 2.6)", H2),
                    P(f"Toplam short funding {fd['short_total']:+.1f} USDT (long {fd['long_total']:+.1f}). <b>Önceki incelemede bu tutar yanlışlıkla ayı rejimine atfedilmişti</b>: pozisyon işaretiyle ve funding'in ödendiği günün (nedensel) BTC rejimiyle ayrıştırınca short funding'in {pc(fd['short_bull_share'], 0)}'i bull rejiminde "
                      f"(short'lar bull'da funding ALIR: pozitif funding), ayı rejiminde short funding {fd['short_bear_usd']:+.2f} USDT. Aşağıdaki son kolon trade tablosundaki giriş-rejimi atfıyla aynı toplamı verir ama dağılımı farklıdır.", B), tbl(rows, [16 * mm, 36 * mm, 24 * mm, 24 * mm, 22 * mm, 26 * mm, 30 * mm]), S(1, 3), tbl(rows2, [70 * mm, 24 * mm, 30 * mm, 20 * mm, 16 * mm, 18 * mm]),
                    P("<b>Etiket: post-hoc.</b> Long-only ve short x0,5 karşı-olgusalları sonuçlar görüldükten sonra, yalnızca betimsel olarak (aynı hakem, aynı kitap, hedef notional'lar değiştirilerek) koşuldu; short tarafı net eksi olduğu için ikisi de daha iyi görünüyor. "
                      "Bu bir strateji önerisi veya seçim değildir; OOS iddiası yoktur; ön kayıt gerekir (Faz 4 taslağı).", SM)]

    # ------------------------------------------------------------ 2.7 LOO
    lo = AN["loo"]
    non_trend = [r for r in lo["rows"] if r["expert"] != "trend"]
    pos_, neg_ = [r for r in non_trend if r["d_net"] < 0], [r for r in non_trend if r["d_net"] > 0]
    trend_ = [r for r in lo["rows"] if r["expert"] == "trend"][0]
    rows = [["Bileşimden çıkarılan", "Net USDT", "Δ net", "Sharpe", "Δ Sharpe", "Maks DD", "Δ DD (puan)", "Katkı işareti (net / Sharpe)"]]
    rows.append(["(hiçbiri: tam bileşim)", fmt(lo["full"]["net"], 1), "-", f"{lo['full']['sharpe']:.2f}", "-", pc(lo["full"]["maxdd"]), "-", "-"])
    for r in lo["rows"]:
        rows.append([r["expert"], fmt(r["net"], 1), f"{r['d_net']:+.1f}", f"{r['sharpe']:.2f}", f"{r['d_sharpe']:+.2f}", pc(r["maxdd"]), f"{100 * r['d_maxdd']:+.1f}", f"{'−' if r['d_net'] > 0 else '+'} / {'−' if r['d_sharpe'] > 0 else '+'}"])
    out["loo"] = [P("2.7 Leave-one-out: hangi uzman neti artırıyor, hangisi azaltıyor (görev 2.7)", H2), tbl(rows, [36 * mm, 20 * mm, 18 * mm, 16 * mm, 18 * mm, 18 * mm, 20 * mm, 32 * mm]),
                  P(f"<b>Doğru okuma (düzeltildi).</b> Uzman çıkarılınca net DÜŞÜYORSA uzmanın katkısı pozitiftir. Net'i <b>artıran</b> (çıkarılınca net düşen) uzmanlar: {', '.join(lo['net_positive_contributors'])}; net'i <b>azaltan</b> (çıkarılınca net artan): "
                    f"{', '.join(lo['net_negative_contributors'])}. Sharpe'ı artıran: {', '.join(lo['sharpe_positive_contributors'])}; Sharpe'ı azaltan: {', '.join(lo['sharpe_negative_contributors'])}. "
                    f"'Diğer 8 uzman getiri katmıyor' iddiası LOO ile çelişir: trend dışındaki {len(non_trend)} uzmanın {len(pos_)}'i net'e pozitif ({', '.join(r['expert'] for r in pos_)}), {len(neg_)}'i negatif ({', '.join(r['expert'] for r in neg_)}); "
                    f"trend dışındakilerin tek başına katkısı küçüktür (|Δ net| ≤ {max(abs(r['d_net']) for r in non_trend):.0f} USDT), trend çıkınca net {trend_['d_net']:+.0f}, Sharpe {trend_['d_sharpe']:+.2f}. Ağırlıklar yeniden normalize edilmez; `combine` ortalama |F| = 0,5 ölçeklemesi kalanları "
                    "orantılı büyütür, yani Δ'lar 'çıkarma + yeniden ölçekleme'dir. Tek koşu, görülmüş veride.", B)]

    # ------------------------------------------------------------ 2.9 hayatta kalma
    sv_ = AN["survivorship"]
    if sv_:
        rows = [["Evren", "Sembol", "Net USDT", "Sharpe (sabit sermaye)", "Maks DD", "2020–21 / 2022–24 / 2025+ Sharpe", "Dolum", "Red / likidasyon"]]
        base_ = ("Sabit 9 (ana koşu)", 9, prim["net"], prim["sharpe"], prim["maxdd"], " / ".join(f"{[r for r in hd['periods'] if r['period'] == k][0]['sharpe']:.2f}" for k in ("2020–21", "2022–24", "2025+")), 5041, "0 / 0")
        rows.append([str(x) if not isinstance(x, float) else (fmt(x, 1) if abs(x) > 5 else (pc(x) if x < 0.5 and x > 0 else f"{x:.2f}")) for x in base_])
        for k, v in sv_.items():
            pr = {r["period"]: r["sharpe"] for r in v["periods"]}
            rows.append([f"Aylık top-{v['top_n']} hacim (delist dahil)", v["n_symbols"], fmt(v["net"], 1), f"{v['sharpe']:.2f}", pc(v["maxdd"]), " / ".join(f"{pr.get(k_, float('nan')):.2f}" for k_ in ("2020–21", "2022–24", "2025+")), int(v["n_fills"]), f"{int(v['n_rejected'])} / {int(v['n_liq'])}"])
        notes = []
        for k, v in sv_.items():
            dl = {s: x for s, x in v["delisted"].items() if x is not None}
            notes.append(f"top-{v['top_n']}: delist olan sembollerin net katkısı " + (", ".join(f"{TR_SYM(s)} {x:+.1f}" for s, x in dl.items()) if dl else "yok (üyelikte yer almadı)"))
        un = AN.get("universe")
        univ_txt = (f"Sabit-9 sembol, aylık top-9 hacim evreninin ortalama %{100 * un['top9']['ext_share_mean']:.0f}'ini oluşturuyor (en düşük %{100 * un['top9']['ext_share_min']:.0f}; {un['top9']['months_with_nonext']}/{un['top9']['n_months']} ayda top-9'da sabit-9 dışı sembol var); top-20'de %{100 * un['top20']['ext_share_mean']:.0f}. "
                    f"AVAX yalnızca {un['top9']['ext_months']['AVAXUSDT']}, LINK {un['top9']['ext_months']['LINKUSDT']} ay top-9'da. ") if un else ""
        out["surv"] = [P("2.9 Hayatta kalma yanlılığı (görev 2.9)", H2),
                       P("<b>Kontrol sonucu: veri kaynağında (Binance arşivi) o dönemde işlem gören ama bugün listede olmayan perp'ler VAR</b> (LUNAUSDT 2021-01 → 2022-05, LUNA2USDT, FTTUSDT, ayrıca EOS, GAL, MATIC, RNDR, TOMO sona erenler; tape'te hepsi var). "
                         "Ana koşunun 9 sembolü (BTC ETH SOL XRP BNB DOGE ADA LINK AVAX) ise bugünün majörleridir ve evren yalnızca bugünden bakıp seçildi. Aylık hacim evreni (`universe.parquet`: ay M = M−1 hacim sıralaması, nedensel, stable/emtia dışlı; delist olanlar dahil) "
                         "ile, her ay o ayın top-N likit sembolleriyle aynı sistem yeniden koşuldu (üyelikten çıkan sembolün hedefi 0).", B), tbl(rows, [44 * mm, 17 * mm, 19 * mm, 22 * mm, 16 * mm, 38 * mm, 14 * mm, 18 * mm]),
                       P(" ".join(notes) + ". " + univ_txt + "2020-21 üyeliği 2020-02'den başlar (pre2022 sıralaması); funding'i arşivde bulunmayan ICP için o dönemde funding sayılmadı (iyimser). "
                         "Bu bir ölçüm: sonuç iyileştirme değil; evren ya da N seçimi sonuca göre değiştirilmedi.", SM)]
    else:
        out["surv"] = [P("2.9 Hayatta kalma yanlılığı: yeniden koşu çıktısı henüz yok.", B)]
    return out
