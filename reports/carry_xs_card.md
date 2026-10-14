# `carry_xs` başarı kartı (K1–K9): edge var mı?

> **Kapsam etiketi (#14):** bu sonuç YEREL/KEŞİF kapsamlıdır: yalnız bu kartın/ölçümün kendi ailesini kapsar, tüm seçim geçmişini (ledger dışı keşif, post-hoc seçimler) ve karşılaştırılabilir hipotez evrenini temsil etmez; ham satır sayısı bağımsız hipotez sayısı değildir. NO_EDGE ve negatif sonuçlar korunur, bu etiket onları değiştirmez. Politika: BACKTEST.md §9 'Deneme ailesi'.

Ön kayıt: `reports/preregistration/carry_xs_card.md` (koşudan önceki commit `1873adb`). Üreten: `scripts/carryxs_card_report.py` (rakamlar `reports/signal_diagnostics_data/carry_xs_card/`). Dinamik evren (aylık top-20, delist dahil), mevcut hakem, fee 10 + slip 2, sermaye 10 000; **görülmüş veride örneklem içi**; mühür dokunulmadı.

## Karar: **NO_EDGE**

| K | ölçüt | sonuç | geçti |
|---|---|---|---|
| K1 | rotasyon null'u: brüt p ≤ 0,05/3 = 0,0167 ve DSR ≥ 0,95 | gerçek brüt +1707; null ort. +373 ± 890 (%50/%95/%99: +431 / +1726 / +2041); **p = 0.0565** (B = 300, taban 0.0033); DSR = 0.989 | ✗ |
| K2 | Sharpe > benchmark ve NW alfa t ≥ 2 | Sharpe 1.24 vs benchmark (EW üye fiyat getirisi) 0.49; alfa yıllık +0.040, beta -0.002, **t = 3.00** | ✓ |
| K3 | Sharpe ≥ 1,0; net > 0 fee 16 + slip 6'da ve 1 bar gecikmede | Sharpe 1.24; net fee16/slip6 +2050; net gecikme +2298 | ✓ |
| K4 | maks DD ≤ %25; bootstrap DD %95 ≤ %30 | DD %3.8; bootstrap %95 %7.3 | ✓ |
| K5 | komşuların ≥ %70'i net > 0; medyan Sharpe ≥ ana/2 | net > 0 payı 1.00; medyan Sharpe 1.44 (ana 1.24) | ✓ |
| K6 | pencerelerin ≥ %60'ı net > 0; 4 kaydırma net > 0 | yarıyıl net > 0 payı 0.75 (12 pencere); kaydırmalar: +2358, +2344, +2349, +2332 | ✓ |
| K7 | çapraz varlık | koşulamadı (evren dışı sembol kümesi yok) | – |
| K8 | ana Sharpe her ablasyondan büyük | ana 1.24; abl_no_risk 0.58, abl_no_buffer 1.20 | ✓ |
| K9 | ≥ 2 rejimde net ≥ 0 ve tek rejim payı ≤ %80 | bull/bear/range net: +1987 / -11 / +101; en büyük pay %96 | ✗ |

## Ayrıntı

**K5 komşuları:** ×0.8: net +2447, Sharpe 1.28 (carry_days 6); ×0.9: net +2568, Sharpe 1.35 (carry_days 6); ×1.1: net +2874, Sharpe 1.53 (carry_days 8); ×1.2: net +2939, Sharpe 1.58 (carry_days 8).

**K6 yarıyıllar (net):** 2020-07-01_: +289, 2021-01-01_: +826, 2021-07-01_: +69, 2022-01-01_: +153, 2022-07-01_: -152, 2023-01-01_: -22, 2023-07-01_: +80, 2024-01-01_: +414, 2024-07-01_: +536, 2025-01-01_: +47, 2025-07-01_: +302, 2026-01-01_: -241.

**K1 bilgi:** aynı p'nin Faz 1 ailesinin Bonferroni eşiğine (0,05/108 = 0.00046) karşısı B = 300 çözünürlüğüyle ulaşılamaz. Null'ın NET ortalaması +219 (gerçek net +2358).

## Okuma

**Karar mekanik olarak NO_EDGE, ama tablo karışık.** K1 kalıyor: gerçek brüt +1707, rotasyon null'unun %95 dilimine (+1726) neredeyse eşit; p = 0.056 hem ön kayıtlı eşiğin (0,0167) hem de nominal %5'in biraz üstünde (B = 300'de p'nin örnekleme belirsizliği ≈ ±0,013). Null'ın kendisi pozitif ortalama brüt veriyor (+373 ± 890): kesitsel carry yapısı (dolar-nötr, düşük oynaklık) zamanlama olmadan da küçük pozitif getiri taşıyor; gerçek sonucun bunun ÜSTÜNDE olduğuna dair kanıt zayıf. Öte yandan diğer kartlar güçlü: K2 geçti (alfa t = 3.00, beta ≈ -0.002, Sharpe 1.24 vs benchmark 0.49), K3 geçti (fee 16 + slip 6'da bile net +2050, Sharpe 1.07; 1 bar gecikmede net +2298), K4, K5 (komşuların hepsi net > 0, Sharpe 1,3–1,6), K6 ve K8 geçti. K7 koşulamadı; K9 kalıyor (netin ~%84'i bull rejiminde; rejim netlerinin toplamına göre pay %96). **Sonuç:** 'edge kanıtlandı' denemez, 'edge yok' da denemez. Sinyal düzeyinde bilgi (Faz 1) ve maliyetten/gecikmeden bağımsız dayanıklı bir getiri var; ancak ön kayıtlı zamanlama null'u (K1) bunu şanstan ayıramadı ve kazanç tek rejime yaslanıyor. Bu bir NO_EDGE kararının K1 sınırında verildiği ve ZAYIF'a çok yakın bir durumdur; karar kuralı değiştirilmedi.

## Dürüstlük notları

- Tasarım Faz 1 bulgusundan türetildi (örneklem içi); kart bunu telafi etmez. Zaman-dışı kanıt yalnızca G3 (mühür, yalnızca ADAY ve kullanıcı komutuyla) ve canlıdır.
- K2 benchmark'ı gösterge: maliyetsiz, fonlamasız EW fiyat getirisi (hakem al-tut'u artefakt verir). K7 koşulamadı, K9 Faz 2'de görülmüştü: en iyi olası karar ZAYIF idi.
- Kontrol koşuları (null, maliyet, komşu, ablasyon, pencere) deftere girmedi; K1 p-testi 1 satır (`trials_card.jsonl`): N + 1. Önceki toplam N 5 090 → **5 091** (muhafazakâr).
- Funding Binance'ten; MEXC doğrulanmadı. Sermaye 10 000; küçük hesapta lot/min-notional etkisi ölçülmedi (önceki denetim: asgari uygulanabilir sermaye ensemble için $2 500).

## Mekanizma ve dolar-nötrlük teşhisi (#17, 12 Ekim 2026)

Kod: `scripts/carry_mechanism.py`; ham çıktı: `reports/signal_diagnostics_data/carry_mechanism/`. Strateji, uzman ve boyutlama DEĞİŞMEDİ; geliştirme verisi (2020-04 → 2026-04), mühür yok; **NO_EDGE kararı korunur** (K1 p=17/301≈0,0565 > yerel eşik 0,0167; bu bölüm onu kurtarmaz). Mekanizma testi, tradeable edge kararı değildir: $500 uygulanabilirliği ayrıca FAIL (`reports/account_reality.md`, #16).

**Falsifiye edilebilir hipotez (koşudan önce yazıldı, script başlığında):** carry_xs, kesitte 7 günlük funding'i en yüksek (kalabalık long) sembollere short, en düşük olanlara long olarak toplar; funding gelirini o bacakların taşıdığı fiyat riskinin karşılığı olarak alır. Tahminler: (a) funding bileşeni yıl/rejim kırılımlarının çoğunda pozitif; (b) funding bileşeni aynı kesit dağılımı ve boyutlamayla rastgele atanmış tahminlerin dağılımının üstünde; (c) fiyat bileşeni sistematik pozitif değil.

**Dolar maruziyeti (forecast → vol/risk/cap → tampon → lot → fiili, günlük, 2.164 gün):**

| aşama | ort. net $ | ort. brüt $ | ort. net/brüt | ort. \|net\|/brüt | günler \|net\|/brüt > 0,20 |
|---|---:|---:|---:|---:|---:|
| tahmin (F) | 0,0 | 8,9 | 0 | 0 | %0 |
| boyutlama (tampon yok) | 46,4 | 1.475 | 0,030 | 0,116 | %18,5 |
| tampon sonrası hedef | 38,3 | 1.458 | 0,025 | 0,121 | %19,4 |
| fiili (lot sonrası, fill'lerden) | 42,6 | 1.463 | 0,026 | 0,128 | %21,5 |

Tahmin toplamı sıfır (|Σ F| ort. 2e-16) dolar nötrlüğünü GARANTİ ETMEZ: σ'ya bölme + tavanlar net dolar maruziyeti üretir (4 sentetik varlıkta net/brüt %70: `tests/test_carry_mechanism.py`; eşit σ'da nötr kalır). 20 sembollük gerçek evrende önceden seçilen ölçüt (ort. \|net\|/brüt ≤ 0,20) sağlanıyor (≈ %12–13), ama kısıt yok: günlerin ≈ %20'sinde aşılıyor. **İddia düzeltmesi:** carry_xs "rank-nötr tahmin; ortalamada yaklaşık dolar-nötr, kısıtsız" olarak anılır, "dolar-nötr" değil (`carry_xs.py` docstring güncellendi). Dolar nötrlüğü hipotez için gerekirse (beta/funding karışımını ayırmak), kısıt sizing/buffer/lot SONRASI uygulanmalı ve parent family'yi koruyan yeni önkayıt gerekir; bu iş strateji değiştirmedi. BTC günlük getirisine beta = 0,0007 (korelasyon 0,014): beta ≈ 0 dolar nötrlüğünü kanıtlamaz, ikisi ayrı raporlandı.

**PnL ayrışması (saatlik yeniden kurulum; toplam hakem net'iyle mutabık, residual 5e-8 USDT):** fiyat +1.706,85, funding +1.021,94, maliyet −370,39, net **+2.358,40** (kartla aynı). Yıl: 2020 fiyat 218 / funding 144; 2021 825 / 125; 2022 −95 / 147; 2023 −117 / 277; 2024 934 / 86; 2025 275 / 137; 2026 (90 gün) −334 / 106. Rejim (nedensel BTC EMA etiketi): bull net +1.987 (1.230 gün), bear −32 (616), range +101 (206), etiketsiz ısınma +303 (139 gün). Funding her yıl ve her rejimde pozitif; fiyat bileşeni 2022, 2023, 2026'da ve bear rejiminde negatif. Net'in %84'ü bull rejim günlerinden gelir.

**Benchmark (önceden seçildi: 'perm' = günlük kesitte tahminleri aktif semboller arasında permüte et; kesit dağılımı, aktiflik, boyutlama korunur):** referee ile permüte koşular 3 saatlik Modal sınırında bitmedi (rastgele atama devri patlatıyor), bu yüzden sürtünmesiz GÜNLÜK VEKİL muhasebe kullanıldı (fiyat = Σ n·R, funding = −Σ n·F, maliyet = 6 bps/yan × Σ|Δn|; lot/stop/gecikme yok). Vekil doğrulaması (gerçek kitap): fiyat 1.502 (referee 1.707, −%12), funding 980 (1.022, −%4), maliyet −369 (−370). 200 permütasyon (tohum 0-199): funding gerçek 980 vs perm ort. −1,5 (p95 37,3; hiçbir permütasyon gerçeği aşmadı); fiyat gerçek 1.502 vs perm ort. −28 (p95 980; 200'den 2'si gerçeği aştı). Sıra-p'si: funding 1/201 = 0,00498 (çözünürlük sınırı), fiyat 3/201 = 0,0149; null kalibre EDİLMEDİ (#15 uyarıları geçerli: bağımlılık altında p'ler anti-muhafazakâr olabilir). Toplam karşılaştırma ADİL değil: permüte kitapların devir maliyeti çok yüksek (toplam perm ort. −2.715).

**Hipotez sonucu:** (a) destekleniyor (funding her yıl/rejimde pozitif), (b) destekleniyor (funding perm dağılımının çok üstünde), **(c) desteklenmiyor**: fiyat bileşeni de perm dağılımının üstünde ve toplam brütün %63'ü, ama yıl ve rejime göre dağınık (bull'da yoğun, bear/2022/2023/2026 negatif). Yani gelir "yalnız funding" değildir; funding'i kimin neden ödediği (kalabalık long'ların pahalı taşıması) ve bunun karşılığında beklenen risk (taşıma/yön riski) bu veriyle ayrıştırılamaz. Fiyat bileşeni için ayrı bir açıklama (ör. bull rejimde yön/altcoin beta'sı) önerisi falsifiye edilmedi: UNKNOWN. Maliyet ve $500 uygulanabilirliği hesaba katıldığında karar yine yok (NO_EDGE, $500 FAIL).
