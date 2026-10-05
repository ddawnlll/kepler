# Edge ailesi: 10 edge türü → 9 uzman, her biri tek başına EV1 zincirinden geçti

**Sonuç (ilk cümle):** 9 uzmanın hiçbiri ADAY değil ve hiçbiri ensemble'a girme kapısını geçmedi; 3'ü ZAYIF (trend, kesitsel momentum, zirveye yakınlık: hepsi aynı momentum ailesi ve hepsi EV1'in K9 kusurunu taşıyor), 6'sı NO_EDGE; karşı-trend ailesi (Bollinger, hacim şoku, funding kalabalığı) bull'da kaybedip range'de küçük kazanıyor ama toplamda negatif. Ön kayıt: `reports/edge_experts_protocol.md` (commit `e76cf5d`, koddan ve koşudan önce). Mühür açılmadı, G3 yok.

## Sonuç tablosu (fee 10 + slip 2 bps RT, sermaye 10 000, 2020-04-01 → 2026-04-01, genişletilmiş-9)
| Uzman | Edge türü | Karar | Net | Brüt | Sharpe | p (brüt) | DSR | Kalan kartlar | Aile düz. | M1 range | M2 EV1 kor. | Ters yön net (bilgi) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `trend` | 1 Trend/momentum | **ZAYIF** | 9206 | 10824 | 1.23 | 0.0033 | 0.997 | K9 | geçti | -1140 | 0.92 | -10027 |
| `xs_momentum` | 9 Cross-sectional | **ZAYIF** | 3707 | 3917 | 1.39 | 0.0033 | 1.000 | K7,K9 | geçti | -435 | 0.41 | -4514 |
| `carry` | 4 Carry | **NO_EDGE** | -1419 | -2683 | -0.21 | 0.9601 | 0.273 | K1,K2,K3,K4,K5,K6,K7,K8,K9 | kaldı | 648 | -0.26 | 1079 |
| `bollinger` | 2 Mean-reversion | **NO_EDGE** (geçersiz koşu*) | -9341 | -9763 | -1.39 | 1.0000 | 0.000 | K1,K2,K3,K4,K5,K6,K7,K8,K9 | kaldı | 419 | -0.72 | 8025 |
| `lowvol` | 3 Risk-premium (vekil) | **NO_EDGE** | -232 | 124 | -0.08 | 0.7110 | 0.195 | K1,K2,K3,K4,K5,K6,K8,K9 | kaldı | 98 | -0.10 | 1 |
| `nearhigh` | 7 Behavioral | **ZAYIF** | 3483 | 3737 | 1.45 | 0.0033 | 0.998 | K9 | geçti | -358 | 0.24 | -4039 |
| `fundcrowd` | 8 Structural | **NO_EDGE** | -2985 | -3673 | -0.58 | 0.9668 | 0.045 | K1,K2,K3,K4,K5,K6,K7,K8,K9 | kaldı | 630 | -0.51 | 2526 |
| `volrev` | 5 Liquidity (vekil) | **NO_EDGE** | -2507 | -1839 | -0.54 | 0.9136 | 0.051 | K1,K2,K3,K4,K5,K6,K7,K8,K9 | kaldı | 600 | -0.40 | 550 |
| `orderflow` | 6 Information (vekil) | **NO_EDGE** | 1909 | 2606 | 0.35 | 0.1462 | 0.760 | K1,K2,K3,K4,K7 | kaldı | -515 | -0.12 | -4069 |

\* Bollinger birincil koşusu hakemde **geçersiz**: maks DD %99,6, 3 likidasyon, 1 275 reddedilen emir. Ledger kuralı bu koşunun deftere yazılmasını yasaklar; sonuç yine hakemden (`run_book`) hesaplandı ve "geçersiz" bayrağıyla raporlandı (`full_systems` emsali). Karar zaten NO_EDGE: brüt −9 763.
**Aile düzeltmesi** ön kayıtlı eşik p ≤ 0,05/9 = 0,0056. B = 300 olduğundan en küçük ölçülebilir p 1/301 = 0,0033; üç momentum uzmanı tam o tabanda (gerçek brüt, 300 null çekilişinin hepsinden büyük). Yani eşiği geçtiler ama p'nin çözünürlüğü sınırda; B büyütülmedi (ön kayıt B = 300).

## 10 edge türünün sonucu
| # | Edge türü | Ne yapıldı | Sonuç |
|---|---|---|---|
| 1 | Trend / momentum | `trend` (mevcut E1) tek başına | ZAYIF (yalnızca K9); EV1'in `trend_only` ablasyonuyla **birebir aynı** (net 9 206,0527; 5 400 dolum) |
| 2 | Mean-reversion | `bollinger` (n 20, k 2) | NO_EDGE, geçersiz koşu (hesap bitti). Bull −6 940, range +419 |
| 3 | Risk-premium | `lowvol` (vekil: düşük oynaklık / BAB) | NO_EDGE (p 0,711, net −232). Opsiyon verisi yok → volatility selling **sınanamadı** |
| 4 | Carry | `carry` (mevcut E3) tek başına | NO_EDGE (net −1 419, Sharpe −0,21). Tek başına kanıt yok. Futures basis verisi yok |
| 5 | Liquidity | `volrev` (vekil: hacim şoku sonrası geri dönüş, taker) | NO_EDGE (net −2 507). Gerçek maker/market making **koşulamadı** (emir defteri/limit emir yok) |
| 6 | Information | `orderflow` (vekil: taker alış payı) | NO_EDGE (p 0,146, DSR 0,76; net +1 909, Sharpe 0,35; K9 geçti ama K1/K2/K3/K4/K7 kaldı). Haber/NLP **koşulamadı** (veri yok) |
| 7 | Behavioral | `nearhigh` (180 gün zirveye yakınlık, kesitsel) | ZAYIF (yalnızca K9): net 3 483, Sharpe 1,45, alfa t 3,53, K1–K8 geçti |
| 8 | Structural | `fundcrowd` (aşırı funding kontrarian) | NO_EDGE (net −2 985). Likidasyon/OI verisi arşivde yok → bu vekille sınırlı |
| 9 | Cross-sectional | `xs_momentum` (mevcut E2) tek başına | ZAYIF (K7 ve K9 kaldı): net 3 707, Sharpe 1,39. Value/quality verisi yok |
| 10 | Execution | **koşulmadı** (uzman değil) | Mevcut kanıt: EV1 `no_buffer` ablasyonu ve K3 maliyet duyarlılığı (`reports/ensemble.md`) |

## Ne öğrendik (yorum; doğrulanmış sayılara dayanıyor)
- **Aynı kusur, iki yüzü.** Süreklilik (trend) yönündeki uzmanların range rejimi net'i negatif (trend −1 140, xs_momentum −435, nearhigh −358, orderflow −515); karşı-trend uzmanlarının range net'i pozitif (bollinger +419, volrev +600, fundcrowd +630, carry +648) ama bull net'leri çok daha negatif (−6 940, −2 735, −3 230, −1 881). Hiçbir uzman hem K1'i geçip hem K9'u geçmedi. EV1'in K9 sorunu (range −895) bu aile testinde de çözülmedi: range'de kazanan fikirler bull'da daha çok kaybediyor.
- **Üç ZAYIF sonuç bir bilgidir, üç bağımsız bulgu değil.** `trend`, `xs_momentum`, `nearhigh` momentum ailesi; korelasyonları EV1'le 0,92 / 0,41 / 0,24. `nearhigh` en az korele ve K1–K8'i geçiyor, ama rejim net'lerinin toplamının %106'sı bull'dan (3 194 / 3 014; K9 ve M1 kalıyor) ve K7 (14 sembol) yalnızca +453.
- **Karşı-trend uzmanlarının ters yönü kazanıyor (bilgi, karar dışı, post-hoc):** Bollinger −F net +8 025 (Sharpe 1,08), fundcrowd −F +2 526 (0,49), carry −F +1 079 (0,16), volrev −F +550 (0,12). Bu "Bollinger bandında trend takibi"dir: trend ailesinin yeniden keşfi; Ters yönün günlük PnL'inin EV1 ile korelasyonu +0,84 (Bollinger), +0,51 (fundcrowd), +0,40 (volrev), +0,26 (carry); yani Bollinger'in ters yönü çeşitlendirme değil, EV1'in kendisine çok benziyor. Protokol gereği bu bir sonuç sayılmaz; yeni bir ön kayıt olmadan kullanılamaz.
- **Beklenen sahte geçiş:** 9 testte ≈ 0,45 (0,05×9). Üç momentum uzmanının geçişi tek bir hipotezin üç görünüşü olduğundan bağımsız değil.

## Ön kayıtlı tahminle karşılaştırma
Protokol "çoğu NO_EDGE" dedi: 6/9 doğru. Tutmayanlar: (1) `nearhigh` için özel bir beklenti yoktu, ama K1–K8'i geçti; (2) Bollinger için "Sharpe −0,3…0,4" denmişti, gerçekte hesap bitti (Sharpe −1,39); (3) `fundcrowd`'ın en olası "daha iyi" aday olması beklenmişti, NO_EDGE çıktı.

## Entegrasyon kapısı (ön kayıtlı): hiçbiri açılmadı
Kapı: K1 + K2 + aile düzeltmesi + M1 + M2. `nearhigh`: K1, K2, aile düzeltmesi, M2 (0,24) geçti; **M1 kaldı** (range −358) → "NEARHIGH RAFA (bu tanımla)". `trend`/`xs_momentum` zaten ensemble'da; ayrı kapı yok (M2 0,92 / 0,41; xs_momentum K7'de de kaldı). Diğer 6: K1 kaldı. Ensemble'a hiçbir şey katılmadı.

## Doğrulama kanıtları ve bulgular
- **Regresyon (EV1 yolu değişmedi):** yeni kodla EV1 günlük PnL'i `reports/ensemble_data/primary.json` ile birebir aynı (2 191 gün, en büyük fark 0,0; net 8 297,33; 5 561 dolum). `tests/test_ensemble.py` 14 test yeşil.
- **Tek uzman yolu:** `trend` tek başına = EV1 `trend_only` ablasyonu birebir (yukarıda).
- **Nedensellik:** `tests/test_edge_experts.py` (22 test): 6 uzmanın elle hesaplı değerleri, gelecek-bozma (tüm sütunlar: taker/hacim/funding dahil) ve kesme, `audit.check_causal_book`. Bilinçli sızıntı mutantı (`orderflow`'a `shift(-1)`) 3 testte kırmızıya düştü, geri alındı. Gerçek veride `evaluate_book` nedensellik denetimi 9 uzmanın hepsi için geçti (Bollinger'de hata denetimden sonra, deftere yazım aşamasında).
- **Bulgu (düzeltildi):** ilk duman koşusunda Bollinger denetimi `[5476]` ile kaldı. Neden sızıntı değil: tahmin satırları kesik/tam seride birebir aynıydı; fark `combine` içindeki `raw.abs().sum(axis=1)`'de, tam panelde henüz listelenmemiş SOL/AVAX sütunları NaN olarak durduğu için 9 sütun ve kesik panelde 7 sütun farklı toplama sırasıyla 1 ulp farklı çıkıyordu. Çözüm: tek uzman kipinde sıradan bağımsız `math.fsum`; EV1 yolu aynen. Testi (`test_forecast_does_not_depend_on_not_yet_listed_columns`) sentetik veride düzeltmesiz de geçiyor (ulp'u yeniden üretemedi), asıl kanıt gerçek veride denetimin geçmesi.
- **Deneme sayacı N:** 4 119 + 8 = **4 127** (9 birincil; Bollinger geçersiz olduğundan deftere yazılmadı). Defter satırlarını hakem betiği Modal Volume'a yazdı: `kepler-data:/edge/<uzman>/ledger_<uzman>.jsonl` (her biri 1 satır; 8 dosya, 8 satır, sayım doğrulandı). **Repoya taşınmadı**: `ledger/*` ajan tarafından yazılamaz (guard/pre-commit); kullanıcı `KEPLER_CORE_UNLOCK=1` ile `modal volume get kepler-data edge/<uzman>/ledger_<uzman>.jsonl ledger/edge_experts/` yapıp commit edebilir. Satırların `trial` alanı ve sonuçlar `primary.json` içindeki `main` ile birebir aynıdır. Kontroller (ablasyon, komşu, pencere, null, ters yön) deftere girmez.

## Sınırlar ve dürüstlük notları
- Dönem ve evren daha önce çok kullanıldı: bunlar **görülmüş veride ön kayıtlı testlerdir**; evren (BTC ETH SOL XRP BNB DOGE ADA LINK AVAX) sonradan bilinen büyük adlardır, hayatta kalma yanlılığı dolar-nötr uzmanlarda (xs_momentum, nearhigh) tam giderilmiş değil. K7 (14 sembol) bağımsızlığı zayıf.
- **Vekil uzmanlar edge türünün kendisini test etmez:** `lowvol` ≠ volatility selling; `volrev` ≠ market making (taker öder, maker kazanır); `orderflow` ≠ haber/NLP; `fundcrowd` ≠ likidasyon akışı. Bu 4 türün "NO_EDGE" sonucu yalnızca o vekil tanımı için geçerlidir.
- Komşu kuralı tek tip (parametrelerin tamamı ×{0,8; 0,9; 1,1; 1,2}); `bollinger_protocol.md` taslağındaki 24 komşulu ızgara yerine bu kullanıldı (protokolde yazılı).
- p tabanı 0,0033 (B = 300). Üç momentum uzmanını birbirinden ayıracak çözünürlük yok.
- Bollinger geçersiz koşuda K4 (maks DD %99,6) ve K5–K8 hesapları da geçersiz hesap üzerinde; karar zaten K1'den NO_EDGE.
- `evaluate.py` `code_hash` yeni uzman dosyalarını kapsamıyor (yalnızca `ensemble.py` kaynağı); ledger satırlarının kod bağlantısı commit ile kurulur: koşular `0f12bf2` + `scripts/ensemble.py` invalid-yedeği (sonraki commit).

## Yeniden koşmak
`modal run modal_app.py --cmd "python scripts/ensemble.py --stage primary --expert <ad> --out /data/edge/<ad> --procs 4"`, `--stage k7 --expert <ad> --procs 1`, `--stage null --expert <ad> --procs 4 --null-from a --null-to b` (5 parça × 60), sonra `EXPERT=<ad> PYTHONPATH=. python scripts/ensemble_report.py reports/edge_experts_data/<ad> reports/edge_experts_data/<ad>`. Tüm aile (9 uzman × 7 iş) Modal'de paralel yaklaşık 30 dk. Ham JSON ve tablolar `reports/edge_experts_data/<ad>/`.
Uzmanlar: `trend`, `xs_momentum`, `carry`, `bollinger`, `lowvol`, `nearhigh`, `fundcrowd`, `volrev`, `orderflow` (`ensemble.REG`).

## Yapılmayanlar
- BACKTEST.md değişiklik günlüğü ve MISSION: korumalı çekirdek (`KEPLER_CORE_UNLOCK` gerekir), yazılmadı; gerekli ek: BACKTEST §3'e "dvol/tbr girdileri [VAR]" notu.
- Hiçbir uzman ensemble'a katılmadı; ters yön (Bollinger −F vb.) için ön kayıt yazılmadı; yeni veri (OI, likidasyon, haber) eklenmedi; G3/mühür açılmadı; Faz 3 kararı ve EV1 dondurma hâlâ kullanıcıda.
- Önerim (tek cümle): bir sonraki adım yeni uzman değil, K9'u çözen tek mekanizmayı (rejime göre risk bütçesi) ön kayda bağlamak; bu aile testi karşı-trend uzmanlarıyla range'i kapatmanın bull kaybına mal olduğunu gösterdi.
