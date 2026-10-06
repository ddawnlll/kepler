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
- `volrev` ve `fundcrowd` seyrek uzmanlar (|F| ortalaması 0,14 / 0,19; `combine` ölçeklemesi tetik günlerinde ±1'e doyuruyor): bu iki NO_EDGE sonucu orantılı tahminin değil fiilen işaret-yalnızca varyantın sonucudur (protokolün zinciri böyle tanımlıyor, sapma yok).
- `test_expert_mode_flip_and_ev1_default_unchanged` ikinci yarısı totolojiktir; EV1 yolunu sayısal koruyan otomatik test yok, koruma yalnızca elle yapılan regresyon (yukarıda) ve bağımsız incelemenin kod okumasıdır. Bağımsız inceleme (tek, `arch-reviewer`): BLOCKER/MAJOR yok; "EV1 birebir" ve gerçek veride denetim iddialarını gerçek veri olmadığından yeniden koşamadı.
- Deneme sayacı: protokol 9 birincil derken ledger'a 8 satır girdi (Bollinger yazılamadı); DSR için seçim yanlılığı sayacı bir eksik.
- `scripts/ensemble.py` geçersiz-main yedeği (`except ValueError`) EV1 `main` yolunu da kapsar: reddedilen emirli bir EV1 koşusu artık patlamak yerine `invalid` bayrağıyla sürer; bayrak `primary.json`, `tables.md` başlığı ve `summary.json` (`invalid_run`) içinde.
- `evaluate.py` `code_hash` yeni uzman dosyalarını kapsamıyor (yalnızca `ensemble.py` kaynağı); ledger satırlarının kod bağlantısı commit ile kurulur: koşular `0f12bf2` + `scripts/ensemble.py` invalid-yedeği (sonraki commit).

## Yeniden koşmak
`modal run modal_app.py --cmd "python scripts/ensemble.py --stage primary --expert <ad> --out /data/edge/<ad> --procs 4"`, `--stage k7 --expert <ad> --procs 1`, `--stage null --expert <ad> --procs 4 --null-from a --null-to b` (5 parça × 60), sonra `EXPERT=<ad> PYTHONPATH=. python scripts/ensemble_report.py reports/edge_experts_data/<ad> reports/edge_experts_data/<ad>`. Tüm aile (9 uzman × 7 iş) Modal'de paralel yaklaşık 30 dk. Ham JSON ve tablolar `reports/edge_experts_data/<ad>/`.
Uzmanlar: `trend`, `xs_momentum`, `carry`, `bollinger`, `lowvol`, `nearhigh`, `fundcrowd`, `volrev`, `orderflow` (`ensemble.REG`).

## Yapılmayanlar
- BACKTEST.md değişiklik günlüğü ve MISSION: korumalı çekirdek (`KEPLER_CORE_UNLOCK` gerekir), yazılmadı; gerekli ek: BACKTEST §3'e "dvol/tbr girdileri [VAR]" notu.
- Hiçbir uzman ensemble'a katılmadı; ters yön (Bollinger −F vb.) için ön kayıt yazılmadı; yeni veri (OI, likidasyon, haber) eklenmedi; G3/mühür açılmadı; Faz 3 kararı ve EV1 dondurma hâlâ kullanıcıda.
- Önerim (tek cümle): bir sonraki adım yeni uzman değil, K9'u çözen tek mekanizmayı (rejime göre risk bütçesi) ön kayda bağlamak; bu aile testi karşı-trend uzmanlarıyla range'i kapatmanın bull kaybına mal olduğunu gösterdi.

## Keşif eki (2026-10-05, kullanıcı kararıyla ön kayıtsız): stoplu, rejim filtreli, saatlik mean reversion
**Bu bölümün hiçbir sonucu karar kanıtı değildir.** Görülmüş veride, sonuçlara bakılarak seçilmiş varyantlar; yukarıdaki 9 uzmanlık ön kayıtlı aile testinden ayrıdır. Koşular `run_book` ile (denetimsiz, deftersiz): 20 simülasyon (8 + 12) ve olay tabloları; N sayacına girmez, ama çoklu karşılaştırma riski gerçektir (aşağıdaki hücrelerin çoğunda t < 2, ve ~100 hücre bakıldı).
Kod: `scripts/mr_explore.py` (saatlik durum makinesi: z ≤ −k / ≥ +k giriş, stop = giriş ∓ 2×ATR(14) hakem stop-market, çıkış z = 0 ya da 24 bar, risk sabit 0,5%/işlem, sembol tavanı 0,5× sermaye), `scripts/mr_events.py` (olay çalışması), ham tablolar `reports/edge_experts_data/mr_explore/`. Nedensellik: `audit.check_causal_book` iki varyantta da boş (temiz). Yönetici doğrulaması: sentetik OU serisinde kâr (+32 bin stoplu, +58 bin stopsuz), rastgele yürüyüşte ≈0 (stopsuz), trendde zarar, ters yön OU'da zarar: yani mantık ve işaret doğru.

**Literatür (araştırma; hepsi ikincil okuma, kuralları tam doğrulanmadı):**
- Bitcoin'de negatif otokorelasyon / mean reversion **1-2-4 saatlik** ufukta raporlanıyor; Hurst üs 2019-22 arasında 0,42'den 0,49'a yükselmiş (piyasa kısa ufukta daha etkin hâle geldi) ([arXiv 2402.11930](https://arxiv.org/abs/2402.11930v1); yalnızca betimsel, işlem kuralı/maliyet yok).
- Günlük/haftalık ufukta geri dönüş **küçük ve illikit** coinlerde; en büyük ve likit coinlerde **momentum** ([Up or down? Short-term reversal, momentum, and liquidity effects in cryptocurrency markets](https://ideas.repec.org/a/eee/finana/v78y2021ics1057521921002349.html), 3 600+ coin, maliyet analizi yok). Bizim büyük-9 evrenimizde günlük Bollinger'in başarısızlığıyla uyumlu.
- Bollinger'in saatlikte günlüğe göre daha iyi çalıştığını söyleyen bir yüksek lisans tezi ([Theseus](https://www.theseus.fi/handle/10024/902903)); kural/stop ayrıntısı ve maliyet varsayımı alıntıdan doğrulanamadı.
- Pairs trading kriptoda maliyet sonrası çoğunlukla kârsız ([arXiv 2109.10662](https://arxiv.org/pdf/2109.10662v1)); pratik şablonlar ADX < 20-25 ve ATR% filtresiyle yatay piyasa arar (kaynak: TradingView betikleri, kanıt değil).

**Olay çalışması** (|z| ≥ 2, giriş sonraki açılış, çıkış h saat sonra; geri dönüş yönlü bps, + = geri dönüş var; maliyet eşiği 12 bps; t gün-kümeli):
| koşul | h = 1 | 2 | 4 | 8 | 24 |
|---|---|---|---|---|---|
| hepsi, n = 20 saat (57 231 olay) | +1,0 (1,1) | +1,8 (1,2) | −0,5 | −7,8 (−1,9) | −3,0 |
| hepsi, n = 80 saat (69 668) | −1,9 (−2,2) | −4,0 (−2,5) | −9,7 (−3,1) | −19,8 (−3,2) | −19,7 |
| 2020-21, n = 20 | +5,1 (2,6) | +9,1 (2,9) | +6,2 | −16,8 | −19,7 |
| 2022-26, n = 20 | −0,6 | −0,9 | −3,0 | −4,4 | +3,2 |
| 2020-21 ve ADX > 25, n = 20 | +11,9 (3,7) | +20,2 (3,8) | +18,0 (1,9) | −12,7 | −2,4 |
| 2022-26 ve ADX > 25, n = 20 | +0,7 | +1,0 | −0,6 | −2,8 | +11,0 |
| BTC rejimi range, n = 20 (5 201) | −1,4 | −2,1 | −8,8 | −4,6 | **+70,2 (2,8)** |
| BTC rejimi range, n = 80 | −0,2 | +2,8 | +8,8 | +27,1 (1,6) | **+99,1 (2,1)** |
| BTC rejimi bull, n = 20 | +3,0 (2,5) | +4,4 | +1,0 | −11,9 (−2,1) | −22,1 (−1,9) |
| hacim şoku > 2x, n = 20 | 0,0 | +0,9 | −5,3 | −18,7 (−3,1) | −28,2 (−2,2) |
| hacim ≤ 2x, n = 20 | +1,6 | +2,4 | +2,6 | −0,8 | +13,0 (1,7) |
Okuma: (1) Saatlik uçta ortalama geri dönüş **yok ya da maliyetin çok altında** (1-2 saatte +1…+2 bps vs 12 bps maliyet); 8-24 saatte devam. (2) Kısa ufuk geri dönüşü yalnızca **2020-21** döneminde ve yüksek ADX'te belirgin (+12…+20 bps) ve 2022-26'da yok: edge zamanla eridi (literatürdeki Hurst artışıyla uyumlu). (3) **Hacim şoklu uçlar devam ediyor** (24 saatte −28 bps): bilgi içeren hareketler; hacimsiz uçlar zayıf geri dönüyor (+13 bps). (4) **BTC range rejiminde 24 saatlik geri dönüş büyük** (+70/+99 bps, t ≈ 2-2,8): tek hücre, sonradan bulundu, 206 range gününden gelen kümeli olaylar; çoklu karşılaştırma altında kırılgan.

**Simülasyon, ilk 8 varyant** (n 20 / 80 saat; ADX ≤ 25 filtresi var/yok; stop var/yok; 2020-04 → 2026-04, fee 10 + slip 2): hepsi hesabı bitirdi (net −9 5xx … −10 2xx, 9 likidasyon). Brüt hepsinde negatif (−3 642 … −7 658), yani sorun maliyet değil; stop brüt kaybı küçülttü (stopsuz −7 621 → stoplu −5 190) ama bitirmedi. Ters yön (`h20_filter_stop_flip`) brüt **+7 278**, ama 18 924 dolumun maliyeti −17 270 → net −10 291. (Hesap battıktan sonraki sayılar geçersiz; yalnızca brüt işareti bilgilidir.)

**Simülasyon, olay çalışmasından sonra seçilen kapı** (BTC rejimi = range, nedensel `robust.regime`; giriş saati hacmi ≤ 2× önceki 24 saat ortalaması; n = 20, k = 2, max 24 saat):
| varyant | pencere | net | brüt | maliyet | dolum | Sharpe |
|---|---|---|---|---|---|---|
| range + hacim, **stoplu** | 2020-04→2026-04 | −3 418 | +739 | −4 200 | 3 841 | −0,46 |
| range + hacim, stoplu | 2020-21 | −1 086 | −361 | −746 | 1 164 | −0,54 |
| range + hacim, stoplu | 2022-26 | −2 332 | +1 100 | −3 455 | 2 677 | −0,43 |
| range + hacim, **stopsuz** | 2020-04→2026-04 | **+937** | +4 916 | −4 099 | 4 002 | +0,09 |
| range + hacim, stopsuz | 2020-21 | −1 187 | −495 | −727 | 1 215 | −0,38 |
| range + hacim, stopsuz | 2022-26 | +2 124 | +5 412 | −3 372 | 2 787 | +0,28 |
| yalnız range (hacim filtresi yok), stoplu | tümü | −4 872 | +235 | −5 163 | 4 482 | −0,57 |
| yalnız hacim filtresi (rejim kapısı yok), stoplu | tümü | −9 588 | −3 599 | −6 396 | 8 419 | −1,22 (hesap bitti) |
Okuma: **rejim kapısı hesabı kurtaran şey** (yalnız hacim filtresiyle bull'da −5 649 ve 9 likidasyon). Kapıyla brüt pozitif ama **maliyet brütün tamamına yakınını yiyor**; stopsuz net +937 (Sharpe 0,09), 2020-21 negatif, 2022-26 pozitif: kanıt değil, kararsız. **2×ATR saatlik stop bu kuralda brütü 4 916'dan 739'a düşürdü** (gürültüde erken kesiyor); stop hesabı korumak için şart (kullanıcı kararı), ama bu genişlikte bedeli çok yüksek. Stop mesafesi ayarlanmadı (görülmüş veride ayar = aşırı uyum).

**Ne anlaşıldı (kısa):** (a) bu evrende, bu dönemde saatlik mean reversion **brüt** olarak küçük ve kırılgan; (b) asıl engel taker maliyeti: ~12 bps gidiş-dönüş, bandın beklenen geri dönüşünden büyük; (c) kâr izi yalnızca range rejimi + hacimsiz uç + 24 saatlik tutuşta var ve o da tek hücre; (d) bu tür strateji doğal olarak **pasif (limit) emirle** uygulanır, yani execution edge (maker ücreti ve dolum), ve hakemimizde limit emir/emir defteri olmadığından test edilemiyor (BACKTEST §4). Maker ücreti ~2 bps varsayılırsa (doğrulanmadı) maliyet −4 100'den ≈ −700 civarına iner ve stopsuz net ≈ +4 000 görünür; bu hesap dolum varsayımı yüzünden iyimser ve kanıt değildir.

### Stop genişliği taraması (kullanıcı itirazı: kâr stopla azalıyorsa sorun yönetimde; aynı rejim + hacim kapısı, ön kayıtsız, +9 koşu)
| stop | tüm dönem net / brüt / stop dolumu | 2020-21 net | 2022-26 net |
|---|---|---|---|
| stopsuz | +937 / +4 916 / 0 | −1 187 | +2 124 |
| 2 ATR | −3 418 / +739 / 597 | −1 086 | −2 332 |
| 3 ATR | −1 968 / +864 / 385 | −791 | −1 177 |
| 4 ATR | −1 160 / +964 / 259 | −604 | −556 |
| 6 ATR | +17 / +1 431 / 113 | −282 | +300 |
Okuma: stop genişledikçe net tek yönlü iyileşiyor (−3 418 → +17), yani 2 ATR gerçekten "gürültünün içinde" seçilmişti; ama 6 ATR'de bile brüt 4 916'dan 1 431'e düşüyor. Mean reversion'ın kârı, önce aleyhe giden sonra dönen **seyrek işlemlerden** geliyor; fiyat stopu bunları zarara çeviriyor. Stopsuz ise gate'siz hesabı bitirdi (ilk 8 varyant); yani yönetim gerçekten gerekli, ama fiyat-mesafe stopu bu stratejiye uygun biçimi değil. Denenmemiş yönetim biçimleri: yapısal geçersizleşme (band genişlemesi |z| > 3,5 ya da BTC rejiminin range'den çıkması), zaman stopu + portföy zarar limiti (kill switch), felaket stopu olarak geniş (≥ 6 ATR) fiyat stopu + küçük boyut.
Ücret notu: varsayılan fee 10 bps gidiş-dönüş = Binance USDⓈ-M normal kullanıcı taker 0,05% × 2 (kaynak: [Finder](https://www.finder.com/binance-futures-fees); Binance'in kendi sayfası alıntıda boş döndü, resmi sayfa doğrulanmadı); maker 0,02% (4 bps gidiş-dönüş), BNB ile %10 indirim. Slippage 2 bps gidiş-dönüş **varsayım** (BTC için makul, alt coin ve oynak saatler için düşük olabilir).

### Drawdown karşılaştırması (aynı kapı, tüm dönem; günlük PnL'den, sermaye 10 000; kullanıcı itirazı: stopsuz net yüksek ama batma riski)
| stop | net | maks DD ($ / tepeye göre %) | en kötü gün | suda geçen en uzun süre | min equity |
|---|---|---|---|---|---|
| stopsuz | +938 | 3 058 / %30,2 | −1 114 (2022-04-06) | 1 183 gün | 7 063 |
| 2 ATR | −3 417 | 4 553 / %45,0 | −526 | 1 776 gün | 5 569 |
| 3 ATR | −1 967 | 3 262 / %32,4 | −510 | 1 776 gün | 6 819 |
| 4 ATR | −1 159 | 2 204 / %21,9 | −454 | 1 776 gün | 7 857 |
| 6 ATR | +17 | 1 117 / %11,1 | −374 | 1 196 gün | 8 924 |
Karşılaştırma: EV1 net 8 297, maks DD %9,7. Stopsuz varyantın maks DD'si net kârının 3,3 katı; 6 yılın yaklaşık 3,2 yılı su altında. En kötü gün tüm varyantlarda aynı (2022-04-06); stop o günkü kaybı yarıya indirdi (−1 114 → −374…−526). Rejim kapısı olmadan stopsuz varyantlar hesabı sıfırladı (9 likidasyon). Kapılı stopsuz serinin kuyruğu **gözlenmedi, yok değil**: pozisyon başına kayıp sınırsız, brüt tavan 3×; kriptoda korele bir gün içi çöküş 9 sembolde birden vurursa tek günde %60'a kadar kayıp mümkün (aritmetik üst sınır, gözlem değil).

### Kaldıraç taraması (kullanıcı: az trade + uzun vade + kaldıraç; keşif, gerçek hakem koşusu, ledger dışı, +9 koşu)
Yıllık hedef oynaklık τ (varsayılan 0,20) yükseltildi; diğer her şey aynı (2020-04 → 2026-04, fee 10 + slip 2, sermaye 10 000). Maks DD sermayenin yüzdesi (K4 tanımı: toplamsal, başlangıç sermayesine göre).
| sistem | τ | net | yıllık getiri | maks DD (sermayeye) | Sharpe | en kötü gün | likidasyon / red |
|---|---|---|---|---|---|---|---|
| EV1 | 0,2 | 8 298 | %13,8 | %9,7 | 1,45 | −471 | 0 / 0 |
| EV1 | 0,4 | 16 601 | %27,7 | %19,4 | 1,45 | −942 | 0 / 0 |
| EV1 | 0,6 | 24 903 | %41,5 | %29,1 | 1,45 | −1 413 | 0 / 0 |
| EV1 | 0,8 | 33 204 | %55,3 | %38,9 | 1,45 | −1 884 | 0 / 0 |
| `trend` | 0,2 / 0,4 / 0,6 / 0,8 | 9 206 / 18 413 / 27 620 / 36 828 | %15,3 … %61,4 | %12,3 / 24,7 / 37,0 / 49,3 | 1,23 | −618 … −2 473 | 0 / 0 |
| `nearhigh` | 0,2 / 0,4 / 0,6 / 0,8 | 3 483 / 6 969 / 10 459 / 13 945 | %5,8 … %23,2 | %4,9 / 9,8 / 14,7 / 19,5 | 1,45 | −278 … −1 113 | 0 / 0 |
Okuma: net ve DD **tam doğrusal** ölçekleniyor, Sharpe sabit (kaldıraç edge yaratmaz; yalnızca getiriyi ve DD'yi aynı oranda büyütür). EV1'in ortalama brüt pozisyonu 0,15× sermaye, yıllık devri 12×, maliyet brütün %4,7'si: yani "az trade, günlük/uzun vade" zaten bu sistem; kaldıraç payı geniş (hakem limiti 10×). K4 sınırları (maks DD ≤ %25, bootstrap DD %95 ≤ %30; EV1 τ = 0,2'de bootstrap %18,7) doğrusal ölçeklemeyle τ ≲ 0,32 (bootstrap sınırı bağlayıcı) → net ≈ +13 000, yıllık ≈ %22, DD %95 ≈ %30 civarı. **Sınırlar:** (1) tümü görülmüş veride ve günlük PnL'den (bar içi DD yok); (2) likidasyon/red yok ama Binance kademeli bakım marjı UNKNOWN; (3) doğrusal ölçek maliyet/funding'in de doğrusal olduğunu varsayar (hakem koşusunda doğrulandı); (4) EV1 K9'u hâlâ kalıyor (kazancın %105'i bull); kaldıraç bu kırılganlığı da büyütür; (5) kuyruk riski (korele çöküş, gap) örneklemde gözlenenin ötesinde olabilir.

### Altyapıya entegrasyon: 9 uzmanlı hazır bileşimler (kullanıcı kararı "yeni 6 uzmanı da altyapıya entegre et"; keşif, ön kayıtsız, ledger dışı, gerçek hakem, 2020-04 → 2026-04)
Altyapı: `ensemble.PRESETS` (varsayılan `Params()` = `ev1`, DEĞİŞMEDİ). Ağırlıklar sonuca bakmadan bir kez sabitlendi: `all9_equal` (9 uzman 1/9) ve `ev1_plus_new` (EV1 0,6/0,2/0,2 aynen + her yeni uzmana 0,1). Ağırlık araması yapılmadı.
| bileşim | net | yıllık | maks DD (sermaye) | Sharpe | EV1 günlük kor. | bull / bear / range | 2020-21 Sharpe | 2022-26 Sharpe |
|---|---|---|---|---|---|---|---|---|
| `ev1` (varsayılan) | 8 298 | %13,8 | %9,7 | 1,45 | 1,00 | 7 329 / 536 / −895 | 3,03 | 0,81 |
| `all9_equal` | 1 110 | %1,8 | %14,3 | 0,26 | −0,41 | 1 185 / −216 / 66 | 0,29 | 0,24 |
| `ev1_plus_new` | 8 111 | %13,5 | %6,8 | 1,89 | 0,91 | 6 969 / 479 / −615 | 3,53 | 1,17 |
Okuma: eşit ağırlıkla 9 uzman kötü (zayıf/negatif uzmanlar karışımı çökertiyor). EV1 + küçük ağırlıklı yeni uzmanlar ise net'i neredeyse koruyup (−%2) Sharpe'ı 1,45 → 1,89, maks DD'yi %9,7 → %6,8, range kaybını −895 → −615 ve 2022-26 Sharpe'ını 0,81 → 1,17 çıkarıyor. Mekanizma: karşı-trend uzmanlarının (bollinger, volrev, fundcrowd) range'de kazanıp bull'da kaybetmesi EV1'in tersi yönde. **Bu kanıt değil:** (1) görülmüş veride, tek koşu; (2) ağırlık, uzmanların tek tek sonuçlarını gördükten sonra sabitlendi (seçilim yanlılığı); (3) rotasyon null'u / DSR / K1–K9 kartı koşulmadı; (4) EV1 korelasyonu 0,91, yani fark küçük bir ek. Varsayılanı değiştirmek için en azından aynı K-kartının (null, komşu ağırlıklar, pencereler, K7) koşulması gerekir.

### Başlangıç bakiyesi $1 000 (kullanıcı önerisi; keşif, gerçek hakem, ledger dışı; `--cap 1000`)
Lot çözünürlüğü kuralı (sinyal-bağımsız, `scripts/ensemble.py::load`) ve min notional 5 USDT (hakem varsayılanı) ile. **Gerçek borsa lot/min-notional kuralları UNKNOWN** (`reports/account_reality.md`; MEXC/Binance sembol kuralları doğrulanmadı).
| bileşim | net | brüt | fee / slip / funding | dolum | red / likidasyon |
|---|---|---|---|---|---|
| `ev1` @ $1 000 | +829,9 (= 10 000'deki 8 297,3'ün %10'u) | 918,3 | −35,8 / −7,2 / −45,4 | 5 305 | 0 / 0 |
| `ev1_plus_new` @ $1 000 | +790,5 | 838,1 | −31,5 / −6,3 / −9,8 | 5 041 | 0 / 0 |
Getiri yüzdesi sermayeyle aynı (doğrusal), ama **pozisyonlar çok küçük**: EV1'de sembol başına hedef notional medyanı ≈ $11–19; hedeflerin %15–23'ü $5'in, %53–75'i $20'nin altında, **%100'ü $100'ün altında**. Borsa minimum notional'ı sembole göre yüksekse (BTC/ETH için belleğimde 100/20 USDT, **doğrulanmadı**) $1 000'da BTC/ETH pozisyonları açılamaz ve sonuç bu satırlardan farklı olur. Küçük hesap için kaldıraç (τ) ve sembol listesi birlikte düşünülmeli: τ yükselince pozisyonlar doğrusal büyür (≈ ×3 için τ = 0,6; tahmin).
