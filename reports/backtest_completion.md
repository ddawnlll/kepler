# BACKTEST.md tamamlama

**Sonuç.** BACKTEST.md %100 tamam: 42 [VAR] (kodda, testli, gerçek veride kullanılmış) + 5 gerekçeli [YOK]; kalan [PLANLI]/[KISMEN]: yok. Yeni araçlar mevcut sonuçlara uygulandı, yeni edge aranmadı; hiçbiri bir sonucu aday yapmadı. Yeni bulgular: (1) planlanan %1 risk/birimde %25 kill switch hafta içinde tetikleniyor (tam Turtle S1 2022-04-11), işlem sırası MC'si %15–17 risk ölçeği öneriyor; (2) equity'ye göre ölçekleme (bileşik Turtle) kazancı siliyor (S1 +39 398 → −3 315, DD %93); (3) gerçek zarar serileri MC'nin %99'undan uzun (kümelenme); (4) FTX penceresinde S1 sermayenin %43'ünü kaybediyor, stop DD'yi %105 → %45'e indiriyor ama stop barları seviyeyi 563 bps'e kadar aşıyor; (5) seçim prosedürü rastgele seçimden ayrışmıyor (nested p = 0,64) ve trend ailelerinde aile-içi PBO %66–78; (6) kapasite sınırı katılım payına göre 10k (100k'da dolumların %21–26'sı > %0,1), karekök etki maliyeti küçük (brüt PnL'nin %1–2'si).

Ön kayıtlar: `reports/backtest_completion_protocol.md` (madde 1–5, 4b) ve `reports/nested_wf_protocol.md`; ikisi de koddan ve koşudan önce commit'lendi, parametre/eşik koşulardan sonra değişmedi. İşçi: `scripts/completion.py` (Modal), tablolar `reports/backtest_completion_data/tables.md` (+ ham JSON), defterler `ledger/backtest_completion/`. Mühür, ≥ 2026-04-01 veri ve G3'e dokunulmadı. Hiçbir sonuç ADAY/ZAYIF/NO_EDGE kararı değiştirmez (kart yeniden çıkarılmadı).

## Doğrulama ve sayımlar
- Taban koşu tam Turtle S1/S2'yi birebir yeniden üretti: net 39 397,7 / 27 641,1 (beklenen 39 398 / 27 641); saatlik PnL yeniden kurulumu farkı 1,06 / 0,00 USDT.
- Testler: `modal run modal_app.py --cmd "pytest -q"` → **199 geçti, 1 atlandı** (gerçek ağ testi; önceki 187 + 12 yeni). Yeni testler (elle hesaplı): `tests/test_stats.py` (+3), `test_stress.py` (2), `test_capacity.py` (2), `test_nested.py` (4), `test_portfolio.py` (+1, `equity_scale`).
- Hakem+yapıştırma satırı: **473** (Motor v2 sonu 467; referee.py +6: `Spec.equity_scale`, `Adapter.equity()`); tavan 600. Veri/QC/mühür araçlarına dokunulmadı.
- Kümülatif deneme: önceki defterler 3 311 satır + risk 6 + BTC duman testi 3 + nested 792 = **4 112**. Stres, MC, kapasite, PBO/SPA ve taban koşuları deftersiz kontroldür, N'ye girmez.

## 1. Tarihsel stres [VAR] (`kepler/stress.py`)
Pencereler: LUNA 05-05→05-16 (2022), FTX 11-06→11-15 (2022), 2024-08-01→08-12 ve sepetin (9 sembol eşit ağırlık) en büyük 3 günlük düşüşü (adlı pencereler dışı, ≥ 7 gün ara): 2025-10-10 (−%17,3), 2025-03-03 (−%16,0), 2026-02-05 (−%15,0); mutlak en kötü gün 2022-11-09 (−%20,9). Tam Turtle `full`, taban Spec, pencere içi:

| pencere | S1 net (% sermaye) / maks DD | S2 net / maks DD | stop S1 / S2 | likidasyon |
|---|---|---|---|---|
| LUNA | +5 170 (%52) / %26 | +1 833 / %31 | 0 / 1 | 0 |
| FTX | **−4 286 (−%43)** / %45 | −1 522 / %18 | 11 / 6 | 0 |
| 2024-08 | +816 / %40 | −110 / %15 | 3 / 1 | 0 |
| 2025-10-10 | −806 / %13 | −529 / %7 | 2 / 0 | 0 |
| 2025-03-03 | −1 824 / %23 | −575 / %20 | 3 / 2 | 0 |
| 2026-02-05 | +2 362 / %24 | +2 129 / %21 | 0 / 0 | 0 |

- Yön kazanan belirler: LUNA ve 2026-02'de sistem net short'tu (kazandı); FTX'te net long 26k (S1) / 16k (S2) idi (kaybetti); 2025-03-03'te short pozisyon sıçramaya yakalandı.
- **Stop koruyor:** `no_stop` ablasyonunda FTX penceresi S1 −9 225 (DD %105: hesap tükenir), S2 −4 986 (%62); stoplu S1 −4 286 (%45), S2 −1 522 (%18). `full` koşularında hiçbir pencerede likidasyon yok.
- **Stop davranışı ve kayma:** hakem stopu seviyeden doldurur (gap dışında), bu yüzden dolum−seviye kayması 0 bps (tanım gereği). Daha bilgilendirici gösterge: dolum barının seviyeyi aşma payı ortalama 50–230 bps, FTX'te **maks 563 bps** (kline H/L'si; hakem tetiği mark H/L'dir, gösterge hakem sonucuna girmez). Gerçek stop-market kayması bu aralıkta olabilir; PnL etkisi **doğrulanmadı** (UNKNOWN).
- Pencere içi maks DD'ler sermayenin %7–45'i: tek bir 9 günlük olay, %20–30 DD toleransını (MISSION) aşabiliyor (S1 FTX, 2024-08, LUNA).

## 2. İşlem sırası Monte Carlo [VAR] (`stats.trade_mc / path_stats / kill_stats`)
5 000 permütasyon, işlem başına net (fiyat PnL'si − maliyet payı + funding payı; işlem toplamı hakem net'inden S1 +107, S2 −1 059 USDT farklı: açık pozisyonlar ve pay dağıtımı). S1 341 işlem (%23 kazanan), S2 154 işlem (%19).

| | DD (sermayeye) %5 / %50 / %95 / %99 | zarar serisi %50 / %95 / %99 | gerçek sıra DD (yüzdelik) | gerçek zarar serisi |
|---|---|---|---|---|
| S1 | %62 / %92 / %147 / %178 | 17 / 26 / 31 | %120 (%83) | **32** |
| S2 | %74 / %111 / %163 / %186 | 17 / 27 / 33 | %122 (%65) | **38** |

- Gerçek ardışık zarar serileri MC %99'unun üstünde: zarar sıraya bağımsız değil, kümeleniyor (yatay/range dönemleri). İşlem karıştırma bu riski küçümser.
- **Kill switch önerisi (ön kayıtlı kural):** s* = 0,25/DD95 = **0,170 (S1) / 0,153 (S2)** (planlanan %1 risk/birim → ≈ %0,15–0,17); önerilen eşik = min(DD99(s*), %30) = **%30 (S1), %28,5 (S2)**. s* boyutunda yanlış-tetik olasılığı: %30'da %1,1 / %0,4, %25'te %5,0, %20'de %19–26; planlanan boyutta (ölçeksiz) her eşikte (%50 dahil) ≈ %100 tetiklenir. %30 eşiğinde kesme ortalama finali yalnızca 0,2–0,5 puan düşürür (%25'te 1,8–2,2 puan).
- **Sınır:** işlem-seviyesi equity yalnızca gerçekleşmiş PnL'dir; saatlik DD işlem DD'sinin ≈ 2–2,5 katı (S1: hakem saatlik DD %251 vs işlem %120). s* bu yüzden iyimser; saatlik DD'ye göre ≈ 0,06–0,08 olurdu. Doğrusal ölçekleme yaklaşıklığı (gross_cap, likidasyon yok sayıldı). Öneri test edilmedi, madde 4 koşularını değiştirmedi.

## 3. Kapasite + hacme bağlı slippage [VAR] (`kepler/capacity.py`)
Tam Turtle S1/S2, sermaye C ∈ {500; 10 000; 100 000} (birim boyutu ve gross_cap C ile ölçeklenir). Katılım = dolum notional'ı / aynı saatin quote hacmi; karekök etki Y·σ_h·√katılım (Y = 1, hakem dışı bindirme, sabit 2 bps'ye ek).

| koşu | net | katılım p95 / maks | > %0,1 dolum | etki maliyeti (Y=1) | net sonrası Y = 0,5 / 1 / 2 | Sharpe taban → Y=1 |
|---|---|---|---|---|---|---|
| S1 500 | 1 970 | %0,002 / %0,009 | 0 | 2 (%0,1 brüt) | 1 969 / 1 968 / 1 966 | 0,63 → 0,62 |
| S1 10k | 39 398 | %0,030 / %0,172 | 3 (%0,3) | 179 (%0,4) | 39 308 / 39 219 / 39 040 | 0,63 → 0,62 |
| S1 100k | 393 974 | %0,302 / %1,719 | **243 (%25,5)** | 5 651 (%1,2) | 391 148 / 388 323 / 382 672 | 0,63 → 0,62 |
| S2 500 | 1 382 | %0,001 / %0,004 | 0 | 1 | 1 381 / 1 381 / 1 380 | 0,42 → 0,41 |
| S2 10k | 27 641 | %0,027 / %0,087 | 0 | 111 (%0,3) | 27 585 / 27 530 / 27 419 | 0,42 → 0,41 |
| S2 100k | 276 411 | %0,268 / %0,865 | **100 (%21,1)** | 3 518 (%1,0) | 274 652 / 272 893 / 269 376 | 0,42 → 0,41 |

- **Kapasite sınırı (ön kayıtlı kural: > %0,1 dolum payı ≤ %5 ve etki ≤ brüt PnL'nin %10'u): 10 000.** 100k'da katılım payı kuralı bozuyor (%21–26); etki maliyeti küçük kaldığı için bağlayıcı olan karekök etkisi değil, emirlerin saatlik hacmin %0,1'ini aşması.
- Net PnL sermayeyle doğrusal (500 → 10k'nın %5'i): tick/lot kuralları sinyal-bağımsız ince çözünürlükle ayarlı, `n_rejected = 0`. Gerçek lot / min-notional kuralları UNKNOWN (500 USD'de BTC lotu gibi kısıtlar ölçülmedi).
- Karekök etki katsayısı Y literatürde 0,5–1; burada UNKNOWN. Etki maliyeti Sharpe'ı en fazla 0,01 oynatıyor. Kriz saatlerinde hacim ve σ birlikte değiştiği için ortalama etki alt sınırdır.

## 4. Risk motoru (§5.1) [VAR] (`Spec.equity_scale`, `run_book(kill_dd=)`, `risk.vol_target`)
6 ön kayıtlı deneme (deftere; S1/S2, sermaye 10 000, DD tepe equity'ye göre):

| koşu | net | final equity | maks DD (saatlik) | likidasyon | kill_at |
|---|---|---|---|---|---|
| S1 sabit boyut (taban) | +39 398 | 49 399 | %53 | 0 | — |
| S1 `equity_scale` | **−3 315** | 6 686 | **%93** | 2 | — |
| S1 sabit + kill %25 | −1 205 | 8 796 | %26 | 0 | 2022-04-11 |
| S1 `equity_scale` + kill %25 | −1 336 | 8 665 | %27 | 0 | 2022-04-11 |
| S2 sabit boyut (taban) | +27 641 | 37 641 | %86 | 0 | — |
| S2 `equity_scale` | +4 174 | 14 174 | %93 | 0 | — |
| S2 sabit + kill %25 | +608 | 10 608 | %27 | 0 | 2022-08-17 |
| S2 `equity_scale` + kill %25 | +139 | 10 139 | %25 | 0 | 2022-05-31 |

- Bileşik (equity'ye göre ölçekli) Turtle kazancı siliyor: S1 −3 315 (DD %93, 2 likidasyon), S2 +4 174 (DD %93). Erken kayıplar sonraki boyutları küçültüyor, kazançlar geç ve sabit boyutta toplanıyordu (yol bağımlılığı). K4 (DD ≤ %25) hiçbir ölçeksiz/ölçekli koşuda geçmiyor; bootstrap DD %95 dilimi %39–55 (kill'li) ve %289–381 (kill'siz ölçekli).
- %25 kill switch planlanan %1 risk/birimde 6 hafta ile 5,5 ay içinde tetikleniyor ve hesap kalan 4 yıl flat kalıyor (net −1 336 … +608): MC önerisiyle (risk ölçeği ≈ 0,15–0,17) tutarlı; bu sonuç "kill switch'li tam Turtle'ın pozitif edge'i yok" demek değil, ön kayıtlı %25 eşiğinin bu boyutla kullanılamadığını gösteriyor. Eşik/boyut ayarlanmadı.
- **BTC `vol_target` duman testi (4b, 3 deneme, tek sembol, sermaye 2 000):** sabit 1 000 notional net −322 (DD %38); `vol_target` −155 (%37); `vol_target` + kill %25 −132 (kill 2025-10-01, DD %26). Yalnızca aracın gerçek veride çalıştığını gösterir; sonuç yorumlanmaz (tek sembol, negatif).
- `tape.aggregate` (BTC 1h → 4h / 1D) hacim, ilk açılış, son kapanış, high/low ve bar sayısını koruyor.

## 5. PBO/CSCV ve SPA [VAR] (`stats.cscv`, `stats.spa`)
88 yapılandırma × 1 096 gün (arama dönemi), S = 16, 12 870 bölme.

| küme | N | PBO | IS-en-iyi OOS'ta zararda |
|---|---|---|---|
| tümü | 88 | %14,0 | %3,2 |
| donchian | 30 | **%66,5** | %27 |
| ema | 24 | **%78,0** | %52 |
| tsmom | 21 | %43,0 | %20 |
| xs_mom | 6 | %19,4 | %6 |
| xs_carry | 3 | %5,5 | %0,2 |
| xs_rev | 4 | %3,9 | **%76** |

- Tüm-88 PBO'su düşük çünkü kesitsel aileler trend ailelerinden sistematik iyiydi (aile etkisi: sıra kalıcı). Seçim aile içinde yapıldığında trend ailelerinde PBO %66–78: IS-en-iyi OOS'ta çoğunlukla medyanın altına düşüyor. xs_rev'de sıra kalıcı ama mutlak getiri negatif (PBO sıra kalıcılığını ölçer, kârlılığı değil).
- **SPA** (Hansen; B = 2000, blok 20): nakde karşı en iyi xsmom_7 (t = 2,56): p_consistent = **0,1075** (p_lower 0,0975, p_upper/RC 0,1095); al-tuta karşı tsmom_14_1 (t = 1,79): **0,3115**. 88 yapılandırmanın en iyisi bile sıfırdan ayrışmıyor (eşik 0,05) → `reports/search.md` NO_EDGE sonucuyla tutarlı.

## 6. Nested walk-forward [VAR] (`kepler/nested.py`; tek koşu, 792 hakem satırı)
Aday: 88 yapılandırma; iç ölçüt yarıyıl Sharpe medyanı; 5 dış adım (2024-01 → 2026-04).

| dış adım | seçilen | OOS net (sermaye payı) | 88 içinde yenilen |
|---|---|---|---|
| 2024-H1 | xscarry_14 | +%10,0 | %90 |
| 2024-H2 | xscarry_14 | −%4,9 | %14 |
| 2025-H1 | xsmom_7 | −%6,9 | %62 |
| 2025-H2 | xsmom_14 | +%5,8 | %68 |
| 2026-Q1 | xsmom_14 | −%2,6 | %13 |

Birleşik OOS (821 gün): net **+248 USDT** (sermaye 18 000), yıllık Sharpe **0,07**, PSR(0) 0,54, DSR(N = 88) 0,06, maks DD %17. Rastgele seçim: **p = 0,64** (rastgele medyan Sharpe 0,17; %95: 0,59); 88'in aynı günlerde ortalama neti +2 109, medyanı +2 168 (prosedürden iyi). Ön kayıtlı yorum kuralıyla (p ≤ 0,05 ve net > 0): **"seçim değer katmıyor"**. Ortalama yenilen pay %49 ≈ beceri yok.

## [YOK] gerekçeleri (kontrol edildi)
- **Purge/embargo/CPCV:** etiket yok → doğru; ek not: CSCV/nested bloklarında pozisyon sınırı aşar (seri bağımlılık, UNKNOWN) BACKTEST §8.3'e yazıldı.
- **Limit emir:** gerekçe doğru (MISSION "önce taker"; kuyruk/L2 verisi yok); BACKTEST §6.3'e açıkça yazıldı.
- **Cross-margin:** gerekçeye ölçüm eklendi: `full` koşularında likidasyon 0; yaklaşıklık yalnızca stopsuz ablasyonlarda (S1 7, S2 4) ve S1 `equity_scale`'de (2) devreye giriyor.
- **Sentetik senaryo:** aday yok, gerçek kriz pencereleri ayrı; gerekçe yazıldı.
- **StepM/MCS:** SPA'dan ayrıldı; aday yok.
- Önceki [VAR] etiketlerinden `risk.vol_target`, `tape.aggregate`, `stats.sharpe_series` gerçek veride hiç kullanılmamıştı; ön kayıt 4b ile kullanıldı (aksi halde etiket doğru değildi).

## UNKNOWN / sınırlar
Stop kayması (üst gösterge 563 bps, PnL etkisi hesaplanmadı); karekök etki Y; gerçek lot/min-notional ve mmr kademeleri; MC işlem bağımsızlığı varsayımı (gerçek seriler kümelenmiş) ve gerçekleşmiş-PnL DD'si; doğrusal s* ölçeklemesi; PBO'nun aile etkisi; nested'de yarıyıl dilimlerinin yeniden başlatılmış koşuya eşdeğer olmaması; hayatta kalma yanlılığı ve tek rejim (önceki raporlarla aynı); dev dönemi görülmüş veri (§8.5). SPA/CSCV kendi uygulama (`arch` yok), elle hesaplı testlerle sabitlendi; harici kütüphaneyle çapraz doğrulama yapılmadı (doğrulanmadı).

## Bağımsız inceleme
(aşağıda)

## Öneri (yapılmadı; kapsam dışı)
(1) Kill switch'i s* ölçekli boyutla (≈ %0,15 risk/birim) ve %30 eşikle ön kayıtlı yeniden test etmek (yeni hipotez, yeni N). (2) Stop kaymasını bar aşma payıyla stres etmek (stop dolumunu bar ucuna taşıyan hakem modu). (3) Zarar kümelenmesi için blok-MC (işlem sırasını bloklarla karıştırmak). (4) Kesitsel aileler (xs_mom/xs_carry) arama dönemi dışında kaldıkça sıra kalıcı; bu hipotez için G3 kararı kullanıcıda (`reports/search.md` önerisi geçerli).
