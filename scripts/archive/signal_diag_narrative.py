"""Rapor yorum metinleri (reports/signal_diag_report.py okur): sayılar JSON dosyalarından çekilir, yorum nitel. python scripts/signal_diag_narrative.py → reports/signal_diagnostics_data/narrative.json"""
import json
from pathlib import Path

D = Path(__file__).resolve().parent.parent / "reports" / "signal_diagnostics_data"
r = json.loads((D / "results.json").read_text())
chk = json.loads((D / "checks.json").read_text())
p2 = json.loads((D / "phase2" / "phase2_results.json").read_text())
cx = json.loads((D / "carryxs.json").read_text())
F, C, DS, R = r["family"], r["cards"], r["desc"], p2["runs"]
b = lambda n: C[n]["best"]  # noqa: E731
tr, xm = b("trend"), b("xs_momentum")
dec = {k: [n for n, c in C.items() if c["decision"] == k] for k in ("TUT", "YENİDEN KUR", "AT")}
hy, he, cxs = p2["hyst_trend"], p2["hyst_ensemble"], p2["carry_xs"]
c1, c0, b1 = R["C1"], R["C0"], R["B1"]
e9 = r["ext9"]
bull_share = c1["regime"]["bull"] / c1["net"]
nar = {}
nar["summary"] = (
    f"- **Sinyal düzeyinde bilgi dar ve çoğunlukla kesitsel.** 108'lik Holm ailesinde {sum(c['ic_pass'] for c in C.values())}/9 uzman IC ölçütünü geçti: "
    + ", ".join(f"`{n}` ({b(n)['type'].upper()} h={b(n)['h']}, IC {b(n)['ic']:+.3f}, Holm p {b(n)['p_holm']:.4f})" for n in C if C[n]['ic_pass'])
    + ". Kalan beşinin en iyi hücresi Holm'u geçmedi.\n"
    "- **TUT etiketlerinin anlamı sınırlı:** `carry` yalnızca KESİTSEL kullanımıyla (IC-XS) geçti; ensemble'daki zaman serisi kullanımında bilgi yok (Faz 2.2). `lowvol` ve `nearhigh` kesitsel IC'leri evren seçim etkisine açık (sınırlar). `volrev` yalnızca h=1 IC-TS'de ve Holm p sınırda; yıllara göre IC sönüyor (kartta).\n"
    f"- **Trend ve kesitsel momentum ön kayıtlı kuralla AT çıktı, ama sınırda:** en iyi hücre `trend` {tr['type'].upper()} h={tr['h']} (IC {tr['ic']:+.3f}, ham p {tr['p']:.4f}, Holm p {tr['p_holm']:.2f}), `xs_momentum` {xm['type'].upper()} h={xm['h']} "
    f"(IC {xm['ic']:+.3f}, ham p {xm['p']:.4f}, Holm p {xm['p_holm']:.2f}); üç alt dönemde de pozitifler. 108 testlik Holm bu büyüklükteki etkiyi yakalayacak güçte değil; kural mekanik uygulandı, ölçüt değiştirilmedi. "
    f"`trend`'in zaman serisi IC'si tüm ufuklarda sıfırdan ayırt edilemiyor (|IC-TS| ≤ {max(abs(F[f'trend|ts|{h}']['ic']) for h in (1, 3, 5, 10, 20, 40)):.3f}); momentum bilgisi kesitsel. 9 sembollü evrende trend IC-TS h=20: {e9['trend|ts|20']:+.3f}, dinamik evrende {F['trend|ts|20']['ic']:+.3f}: "
    "trendin zaman serisi 'edge'inin büyük kısmı hayatta kalan semboller seçiminden geliyordu (nokta tahmin, p yok).\n"
    f"- **Bağımsız fikir sayısı: {r['n_clusters']} küme / 9 uzman** (trend ile bollinger ters kopya; xs_momentum + nearhigh tek küme).\n"
    f"- **Faz 2.1 (nötr bölge + histerezis): ÇALIŞMADI** iki çekirdekte de (ΔSharpe trend {hy['delta_sharpe']['point']:+.3f}, ensemble {he['delta_sharpe']['point']:+.3f}); dolum sayısı yalnızca {hy['d_fills']:+.0f} / {he['d_fills']:+.0f} değişti: bu eşiklerle etki ihmal edilebilir, yönü olumsuz.\n"
    f"- **Faz 2.2 (`carry_xs`): ön elemeyi geçti (KABUL)**: net {c1['net']:+.0f}, Sharpe {c1['sharpe']:.2f} (bootstrap %5 {cxs['bootstrap']['sharpe_q']['p5']:+.2f}), trend ile günlük PnL korelasyonu {cxs['corr_trend_daily_pnl']:+.2f}. Eski carry aynı evrende net {c0['net']:+.0f}, Sharpe {c0['sharpe']:.2f}. "
    f"Netin %{100 * bull_share:.0f}'i bull rejiminde ve mutlak getiri küçük; K1–K9 kartı koşulmadı, 'edge kanıtlandı' denmez."
)
nar["rule_note"] = (
    "**Kuralın sertliği (ön kayıt gereği değiştirilmedi):** karar, 108 hücrelik ailenin Holm düzeltmesine dayanır; bu, orta büyüklükte gerçek etkileri de reddedebilen muhafazakâr bir eşiktir (özellikle `trend` ve `xs_momentum`: ham p ≈ 0,005, alt dönemlerin üçünde pozitif). "
    "Ham p'ler ve BH q-değerleri kart tablosunda ve `results.json`'da duruyor; ölçütü sonuca göre gevşetmek ön kayıt ihlali olurdu, bu yüzden 'AT' etiketi ölçütün mekanik sonucu olarak kalır ve **kullanıcı kararı gerektirir**. "
    "H sınıfı (hipotez) belge metninden okundu: `trend`, `xs_momentum`, `lowvol` için belgede mekanizma cümlesi yok (H = 1), bu yüzden IC ölçütü kalınca YENİDEN KUR yerine AT çıktı."
)
nar["clusters"] = (
    "Okuma: `trend` ile `bollinger` birbirinin ters kopyası (ρ ≈ −0,83): Bollinger'in ters yönü yeni bir fikir değil trend'in tekrarıdır (ön kayıt 1.5 kuralı). `xs_momentum` ile `nearhigh` aynı ailenin iki biçimi. "
    "`carry` ile `fundcrowd` eşiğin (0,5) hemen altında: ayrı küme sayıldı ama funding bilgisi paylaşıyorlar. `lowvol`, `volrev`, `orderflow` birbirinden ve diğerlerinden bağımsız. "
    "Sonuç: ensemble'daki 9 uzman ≈ 7 'fikir'; bunlardan yalnızca birkaçı sinyal düzeyinde kanıt taşıyor."
)
nar["ext9"] = (
    f"Okuma: mevcut 9 sembollü evrende `trend` IC-TS h=20 = {e9['trend|ts|20']:+.3f} iken dinamik evrende {F['trend|ts|20']['ic']:+.3f}; `carry` IC-XS 9 sembolde {e9['carry|xs|20']:+.3f}, dinamik evrende {F['carry|xs|20']['ic']:+.3f}. "
    "Kesitsel bilgi iki evrende de var; zaman serisi trend bilgisi dar evrende görünür, geniş ve hayatta kalma yanlılığından arınmış evrende görünmez. Ham getiri hedefiyle IC (oynaklık normalizasyonu olmadan): `checks.json` → `raw_target`; "
    "özellikle `lowvol` için ham hedef IC'si normalize olandan belirgin büyük (düşük oynaklık sembollerin göreli getirisi + normalizasyon etkisi)."
)
nar["phase2"] = (
    f"**2.1 teşhis özeti:** nötr bölge ve histerezis (θ_out = 0,10; θ_in = 0,25) pozisyon-izin maskesi olarak uygulandı; tampon ve boyutlama aynen. Trend çekirdeğinde dolum {R['B1']['n_fills']:.0f} → {R['T1']['n_fills']:.0f}, ensemble'da {R['B2']['n_fills']:.0f} → {R['T2']['n_fills']:.0f}: "
    f"devir zaten tampon (0,2) ile bastırıldığı için ek filtre az şey değiştiriyor; fee+slip tasarrufu ({hy['d_cost']:+.0f} / {he['d_cost']:+.0f} USDT) brüt kaybından ({hy['d_gross']:+.0f} / {he['d_gross']:+.0f}) küçük. "
    "Ölçütle ÇALIŞMADI; tek eşik çifti denendi (tarama yok), bu yüzden 'histerezis hiçbir zaman işe yaramaz' demiyoruz.\n\n"
    f"**2.2 teşhis ve sonuç:** Faz 1: mevcut carry'nin işareti doğru ama zaman serisi kullanımı yanlış (IC-TS ≈ 0 tüm ufuklarda, IC-XS pozitif ve ufukla artıyor, funding hizası sorun değil, hücre havuzlu kalibrasyon ters). `carry_xs` (kesitsel funding sırası, dolar-nötr) aynı hakem ve evrende "
    f"mevcut carry'den belirgin iyi: net {c1['net']:+.0f} vs {c0['net']:+.0f}; brüt {c1['gross']:+.0f} vs {c0['gross']:+.0f}; funding {c1['funding']:+.0f} vs {c0['funding']:+.0f}. Netin önemli kısmı funding geliri (brüt fiyat PnL'si {c1['gross']:+.0f}); "
    f"günlük PnL korelasyonu eski carry ile {cxs['corr_c0']:+.2f}, tahmin (günlük kesitsel) korelasyonu {cx['corr_xs_daily']['carry']:+.2f}: aynı kesitsel bilgi, zaman serisi bacağı kaldırıldı. "
    f"**Uyarılar:** (i) netin %{100 * bull_share:.0f}'i bull rejiminde, bear {c1['regime']['bear']:+.0f}, range {c1['regime']['range']:+.0f} (K9 payı kuralı ≤ %80 geçmezdi); (ii) 2025+ net yalnızca {c1['periods']['2025+']['net']:+.0f}; "
    f"(iii) mutlak getiri küçük (6 yılda {c1['net']:+.0f} / 10 000) çünkü risk motoru dolar-nötr düşük oynaklık üretiyor (maks DD %{100 * c1['maxdd']:.1f}); Sharpe ölçek-bağımsız ama kullanılabilir getiri değil; (iv) tasarım Faz 1 bilgisinden türetildi (örneklem içi); (v) Binance funding'i, MEXC doğrulanmadı; "
    f"(vi) K1 (rotasyon null'u), K2, K3 vb. koşulmadı. Bu sonuç 'bir sonraki ön kayıtlı K kartını hak eder' anlamına gelir."
)
nar["new_data"] = (
    "1. **Spot–perp basis (spot klines + premium/index klines): momentum'dan bağımsız olma ihtimali en yüksek.** Kaynak, funding'in ham ekonomisi: perp primi kaldıraçlı long talebinin kalabalığıdır ve fiyat yönünden büyük ölçüde bağımsızdır (carry_xs'in trend ile PnL korelasyonu düşük). "
    "Spot ile hedge edilen (delta-nötr) carry fiyat riskini kaldırır; yani kazanç doğrudan funding/basis. Eksik: kapasite, spot bacağı maliyeti ve MEXC spot/perp erişimi; ücretsiz (Binance arşivi 2017/2020'den) ve hepsi veri işi.\n"
    "2. **OI + konumlanma (`metrics`: OI, üst trader / hesap long-short, taker oranı): orta-yüksek.** Funding bir fiyat, OI bir miktardır: kalabalığın büyüklüğünü ölçer; fundcrowd'un (yalnızca funding) başarısızlığı OI'nin de başarısız olacağını göstermez. "
    "Riskler: OI değişimi eşzamanlı getiriyle çok ilişkili (momentum vekili çıkabilir); kapsam yalnızca BTC 2020-09'dan, diğerleri 2021-12'den (dinamik evrenin 2020–21 kısmı kapsanmaz); sütun anlamı doğrulanmadı. Önce Faz 1'deki gibi IC testiyle sınanmalı.\n"
    "3. **Likidasyonlar: bu ortamdan sınanamaz.** Binance arşivinde yok; OKX yalnızca yakın zaman; MEXC yok. Veri satın alma/biriktirme gerekir (ücretli sağlayıcılar: doğrulanmadı).\n"
    "4. **İşlem/L2 verisi (aggTrades, bookDepth/bookTicker): düşük öncelik.** `orderflow` (taker alış payı vekili) IC'si sıfırdan ayırt edilemedi; ek bilgi ihtimali düşük, hacim ve hesap maliyeti çok yüksek; kısa ufuklu mikroyapı bilgisi taker tabanlı hakemde ve fee 10 bps'de kullanılamaz (limit emir/emir defteri modeli yok).\n"
    "5. **MEXC verisi araştırma kaynağı olamaz:** funding geçmişi yalnızca ~1,5 yıl, OI geçmişi yok, kline 2020-06'dan. MEXC yalnızca aday çıkınca uygulama farkı ölçümü için."
)
nar["limits"] = (
    "- Her sonuç görülmüş veride; hiçbir test zaman-dışı değil. Alt dönem 2025+ en yakın 'sonraki' dönem ama o da görüldü.\n"
    "- Dinamik evren aylık hacim sıralamasıyla seçiliyor: yeni şişen küçük/meme sembollerin üye olduğu aylarda sonraki zayıflığı `lowvol`/`nearhigh` gibi kesitsel IC'leri etkileyebilir; bu seçim etkisi ayrıştırılmadı. `lowvol`'ın ham hedef IC'si normalize olandan büyük (mekanik normalizasyon etkisi + gerçek ilişki karışık).\n"
    "- IC-XS küçük kesitlerde aşağı yanlı (n = 15'te yaklaşık −0,02; testlerde ölçüldü): kesitsel IC'ler muhafazakâr.\n"
    "- p-değerleri blok bootstrap SE'sinden normal yaklaşım (B = 2000); IC-TS sıra-sonra-yeniden-örnekle yaklaşımı. 108'lik aile Holm'u muhafazakâr; BH q-değerleri tabloda.\n"
    "- Karar H sınıfı belge metninden okundu ve sonuçtan önce sabitlendi; mekanizma cümlesi eksik üç uzman için bu bir belge boşluğudur, uzmanın kalitesi hakkında yargı değil.\n"
    "- Faz 2: tek eşik çifti, tek koşu, sermaye 10 000 (önceki dinamik koşu 1 000: Sharpe 1,04; burada ensemble tabanı yaklaşık aynı). Baz koşular ölçümdür, deftere girmedi.\n"
    "- Belgelerle çelişki/not: (i) `reports/edge_experts.md` ve `ensemble.md` trend/momentum'u 'kanıtlanabilir tek fikir' sayıyor; bu iş dinamik evrende trendin zaman serisi bilgisini bulamadı, kesitsel momentum bilgisini ham p ≈ 0,005'te buldu (Holm'da tutmadı). (ii) Ön kayıt `neutral_zone_hysteresis.md`'de defter yolu ifadesi koşudan önce (kodla aynı commit'te) koşu başına dosya olarak netleştirildi; kural/eşik değişmedi. "
    "(iii) `scripts/signal_diag.py` Faz 1 analizinden sonra `checks` ve `carryxs` aşamalarıyla genişletildi; Faz 1 defter satırlarının `code_hash`'i analiz anındaki sürümdür.\n"
    "- Doğrulanmadı: MEXC funding/fee, Binance fapi/Bybit geçmiş derinlikleri (bu ortamdan engelli), `metrics` sütun anlamları, resmi delist tarihleri.\n"
    "- Yapılmayan: ensemble ağırlığı/sizing/parametre araması; yeni uzman ensemble'a katılmadı (`carry_xs` REG'e eklenmedi); G3/mühür; veri pipeline'ı."
)
(D / "narrative.json").write_text(json.dumps(nar, ensure_ascii=False, indent=1))
print("narrative", {k: len(v) for k, v in nar.items()})
