# Ön kayıt: 10 edge türü → uzmanlar (aile testi; her uzman tek başına EV1 zincirinden geçer)

**Durum:** ön kayıt; koddan ve koşudan önce commit'lendi (2026-10-04). Kural, evren, parametre, N ve ölçüt koşudan sonra değişmez (MISSION kural 11). Değişiklik = yeni ön kayıt + yeni deneme.
**Kapsam kararı (kullanıcı, 2026-10-04, oturumda):** "hepsini yap, sırayla". Bu karar TASKS "Durma kuralı"nı (Faz 3 kararından önce yeni strateji koşusu yok) **yalnızca bu iş için** kaldırır; Faz 3 kararı ve EV1 dondurma bekleyen iş olarak kalır. Bu ön kayıt `reports/bollinger_protocol.md` taslağının yerine geçer (Bollinger için hipotez gerekçesi o dosyada kalır; komşu kuralı burada tek tip).

## Neden (gözlenmiş engel; MISSION kural 4) ve dürüstlük notu
- EV1 üç uzmanı (trend, kesitsel momentum, funding carry) aynı yönde: süreklilik/akış. K9 kalıyor (range −895; bull payı %105). Bu **mean-reversion** (Bollinger) için gözlenmiş engel.
- Diğer uzmanlar için gözlenmiş engel **zayıf**: yalnızca "tüm girdiler OHLCV + funding; farklı mekanizma aileleri hiç sınanmadı". Kural 4'ün "önceki basit hale karşı karşılaştırma" şartı şöyle karşılanır: her uzman EV1 ile aynı zincirde, al-tut ve EV1'in günlük PnL'i (M2) karşısında raporlanır.
- Kullanıcı bu 10 türü bir tablo olarak verdi; hipotezleri onun listesinden geliyor, verinin sonuçlarına bakılarak seçilmedi. Yine de dönem/evren çok kullanıldı: bu **görülmüş veride ön kayıtlı testlerdir** (BACKTEST §8.5). Aile çapında 9 test yapıldığı için yanlış pozitif riski var, aşağıdaki "aile düzeltmesi" bunun içindir.

## 10 türün eşleştirmesi
| # | Edge türü | Bu testte | Gerekçe |
|---|---|---|---|
| 1 | Trend / momentum | **E1 `trend`** (mevcut) tek başına | EV1'in birinci uzmanı |
| 2 | Mean-reversion | **E4 `bollinger`** (yeni) | K9 engeli; z-skor geri dönüş |
| 3 | Risk-premium | **E5 `lowvol`** (yeni, vekil) | Opsiyon verisi yok → volatility selling sınanamaz. Düşük-oynaklık / betting-against-beta anomalisi, risk primi ailesinin bar-verisi vekili |
| 4 | Carry | **E3 `carry`** (mevcut) tek başına | Funding carry. Futures basis verisi yok |
| 5 | Liquidity | **E8 `volrev`** (yeni, vekil) | Gerçek maker/market making: limit emir + emir defteri verisi gerekir (BACKTEST §4 kapsam dışı) → **KOŞULAMAZ**. Vekil: yüksek hacimli günde ters tepki (likidite sağlayıcı tazminatı, Campbell–Grossman–Wang). Taker olarak uygulanır: gerçek maker edge'i test edilmez |
| 6 | Information | **E9 `orderflow`** (yeni, vekil) | Haber/NLP verisi yok → **KOŞULAMAZ**. Order-flow vekili: klines'taki taker alış payı |
| 7 | Behavioral | **E6 `nearhigh`** (yeni) | Çıpalama / az-tepki: 180 günlük zirveye yakınlık (George–Hwang tipi), kesitsel |
| 8 | Structural | **E7 `fundcrowd`** (yeni) | Zorunlu akış vekili: aşırı funding = kalabalık pozisyon → tasfiye baskısı. Likidasyon/OI verisi arşivde yok (`TASKS` pozisyonlanma verisi görevi tamamlanmadı); endeks rebalansı kriptoda yok |
| 9 | Cross-sectional | **E2 `xs_momentum`** (mevcut) tek başına | Value/quality için kripto verisi yok. Kesitsel kısa-vade geri dönüşü zaten NO_EDGE (`reports/search.md`, xs_rev) |
| 10 | Execution | **Uzman değil; koşulmaz** | Uzman yalnızca tahmin verir; maliyet hakem/risk katmanında. Mevcut kanıt: EV1 `no_buffer` ablasyonu (tampon = devir azaltma) ve K3 maliyet duyarlılığı (`reports/ensemble.md`). Yeni koşu yok |

Yani: 9 uzman koşulur (3 mevcut tek başına + 6 yeni). 3 tür (liquidity-gerçek, information-haber, execution) tanım gereği koşulamaz ya da uzman değildir; vekilleri etiketli olarak koşulur.

## Veri, evren, dönem (EV1 ile birebir)
`tape.load`: `/data/pre2022` (2020-01 → 2021-12) + `/data` (2022-01 → 2026-03). Evren genişletilmiş-9 (BTC ETH SOL XRP BNB DOGE ADA LINK AVAX), aktiflik ≥ 90 günlük kapanış. Değerlendirme **2020-04-01 → 2026-04-01**; karar her UTC günün kapanışında, dolum sonraki bar açılışı. Mühür dokunulmaz.
Yeni girdiler (hepsi aynı UTC günün saatlik barlarından, `d` gününe kadar dahil): `dvol` = günlük `quote_volume` toplamı, `tbr` = günlük `taker_buy_quote_volume / quote_volume`. Sütunlar tape'te zaten var (ham adlar korunur); `market_state.py` bunları `st`ye ekler (yeni anahtar; mevcut çıktılar değişmez, regresyon testi: EV1 günlük PnL'i birebir aynı).

## Zincir (EV1 ile aynı)
`combine` (F_raw ölçeklemesi: mean|F| = 0,5) → `portfolio.size` (τ = 0,20, IDM, tavanlar, tampon 0,2) → portföy hakemi (sermaye 10 000, fee 10 + slip 2 bps RT, kaldıraç 10, mmr 0,005, `gross_cap` 3x). Tek uzman: ağırlık 1. Uygulama: `ensemble.Params.expert` (boş = EV1), `Params.xp` (K5 komşusu için parametre geçersiz kılma), `Params.flip` (yön testi). Boş `expert` ile EV1 çıktısı değişmez.

## Uzmanlar (tüm parametreler sabit; hepsi günlük, [−1, 1], aktif olmayan hücre NaN)
`C` günlük kapanış paneli (ffill), `act` aktiflik, `σ` = `st["sigma"]`.
- **E1 `trend`, E2 `xs_momentum`, E3 `carry`:** `reports/ensemble_protocol.md` §2 ile birebir (kod değişmez).
- **E4 `bollinger`** (mean-reversion): n = 20, k = 2. SMA, popülasyon std (ddof 0); z = (C − SMA)/std; std = 0 ise F = 0. **F = clip(−z/k, −1, 1).**
- **E5 `lowvol`** (risk-premium vekili): L = 60. σ_L = std(günlük log getiri, L gün, en az 40) × √365. Aktif semboller arasında −σ_L'ye göre sıra: q = 2·(sıra − 1)/(n − 1) − 1 (en düşük oynaklık +1). n < 4 ise 0. **F = q** (dolar-nötr: düşük oynaklık long, yüksek short).
- **E6 `nearhigh`** (behavioral): L = 180. x = C / max(C_{d−L+1..d}) (en az 90 gün). x'e göre kesitsel sıra, E5 ile aynı q formülü (zirveye en yakın +1). **F = q** (az-tepki/çıpalama: zirveye yakın olan devam eder).
- **E7 `fundcrowd`** (structural): φ = `st["phi"]` (7 günlük ort. funding, yıllık). L = 90. z = (φ − ortalama_L(φ)) / std_L(φ) (en az 45 gün). **F = −clip(z/3, −1, 1) yalnızca |z| > 1,5 ise, değilse 0** (aşırı pozitif funding → short, aşırı negatif → long).
- **E8 `volrev`** (liquidity vekili): L = 30, eşik 1,5. v = `dvol_d` / ortalama(`dvol_{d−L..d−1}`) (en az 15 gün). **F = −clip(r₁ / (2 · σ/√365), −1, 1) yalnızca v > 1,5 ise, değilse 0**; r₁ = günlük log getiri.
- **E9 `orderflow`** (information vekili): L = 60, m = 3. imb = 2·`tbr` − 1; z = (ortalama_m(imb) − ortalama_L(imb)) / std_L(imb) (en az 30 gün). **F = clip(z/2, −1, 1)** (agresif alış akışı = devam; ters yön bilgi testi).
Hepsi `C_{≤d}`, `st` ve `dvol/tbr_{≤d}` dışında bir şey görmez.

## Denemeler (her uzman için ayrı)
- **N = 1 birincil** (9 uzman → ailede 9 birincil, kümülatif deneme +9; okuma anında 4 119, kesin sayı raporda ledger satırlarından).
- **Kontroller** (deftere girmez, N'ye girmez): K8 ablasyonları `no_risk`, `no_buffer`; **K5 komşuları: 4** = parametrelerin tamamı ×{0,8; 0,9; 1,1; 1,2} (tamsayılar yuvarlanır; σ, ρ, τ sabit; E1–E3 için EV1'in `Params.scaled` kuralı); K3 maliyetleri (fee 16 + slip 6; 1 bar gecikme); K6 pencereleri (11 yarıyıl + 2026-Q1 + 4 kaydırma); K7; K1 rotasyon null'u B = 300 (EV1 ile aynı tohumlar, `u_i = default_rng([0, i]).uniform(0,05; 0,95)`).
- **Yön testi (bilgi, karar dışı):** F işareti ters. Bir uzman ters yönde kazanırsa bu ayrı bir ön kayıttır, buradan sonuç çıkarılmaz.
- **DSR:** deneme Sharpe kümesi = birincil + 2 ablasyon (N = 3, muhafazakâr).

## Başarı kartı (BACKTEST §11; ayrıntılar `reports/ensemble_protocol.md` "Başarı kartı" ile birebir)
K1 (brüt p ≤ 0,05 ve DSR ≥ 0,95), K2 (al-tut karşısında Sharpe ve NW alfa t ≥ 2), K3, K4, K5, K6, K7, K8, K9; karar `robust.decision`. Bilgi: alt dönemler, rejim payları, sembol payları, devir, funding payı, stres pencereleri.
**Aile düzeltmesi (bu protokole özgü):** 9 uzman aynı veride sınandığı için, bir uzman için "kanıt var" iddiası **ancak** K1 brüt p ≤ 0,05/9 = 0,0056 ise yapılır. Kart kararı (NO_EDGE/ZAYIF/ADAY) yine tek başına BACKTEST §11 ile verilir; düzeltmeyi geçmeyen ADAY/ZAYIF "aile düzeltmesinde kaldı" diye etiketlenir.
**Mekanizma kriterleri** (karar dışı; ensemble'a katma kapısı):
- **M1:** `robust.regime` ile **range** rejiminde net PnL > 0 (K9 engeline karşılık).
- **M2:** günlük net PnL korelasyonu EV1'inkiyle ≤ 0,30 (çeşitlendirme; EV1 günlüğü `reports/ensemble_data/primary.json`).
**Entegrasyon kapısı:** ensemble'a katma önerisi (ayrı ön kayıt) yalnızca K1 + K2 geçer, aile düzeltmesi geçer ve M1 + M2 sağlanırsa açılır. Aksi halde uzman "RAFA (bu tanımla)"; yeni tanım = yeni ön kayıt. Hiçbir uzman bu protokolle ensemble'a girmez; G3/mühür açılmaz.

## Tahmin (koşudan önce; yargı, doğrulanmadı)
- Çoğunun **NO_EDGE** çıkması beklenir (K1 kalır). Gerekçe: kendi verimizde xs_rev ve Zone Fade NO_EDGE; trend/momentum dışındaki aileler net negatif ya da sıfıra yakın.
- En olası "daha iyi" adaylar: `fundcrowd` (funding E3 ile aynı yönde, korele olabilir → M2 kalır), `bollinger` (range'de kazanıp bull'da kaybeder). `orderflow` ve `volrev` için işaret belirsiz.
- E1/E2/E3 tek başına: EV1 ablasyonlarından (`trend_only` vb.) benzer sonuç beklenir; EV1 K1'i zaten tek zincirde geçmişti ama DSR/p ayrı bakılır.
- 9 testten ≥ 1'inin ham p ≤ 0,05 çıkması tek başına kanıt değil: beklenen sahte geçiş ≈ 0,45.

## Bütçe
Kod: `kepler/experts/{bollinger,lowvol,nearhigh,fundcrowd,volrev,orderflow}.py` (her biri ~10 satır), `_interface.py` (+`par`, `scale`, `xrank`), `market_state.py` (+`dvol`, `tbr`), `ensemble.py` (+`expert`, `xp`, `flip`), `scripts/ensemble.py` (`--expert`), `scripts/ensemble_report.py` (EXPERT kipi), `tests/test_edge_experts.py`. Hakem, denetim, risk, state, tape, ledger, mühür koduna dokunulmaz. Koşu: Modal, uzman başına paralel; ~6 saat toplam pencere. Aşılırsa dur ve raporla.
