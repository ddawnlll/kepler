# 2020–2021 zaman-dışı (OOS) replikasyon: ön kayıt (onaylandı)

**Durum:** ÖN KAYIT ONAYLANDI (kullanıcı, 2026-10-02; takvim düzeltmeli S1c/S2c dahil, N = 10). Bu commit'ten sonra veri indirilebilir, kod yazılabilir, koşu yapılabilir. Parametre/eşik/evren/N değişmez (MISSION kural 11); değişiklik yeni ön kayıt ve yeni deneme sayısıdır.

## Soru
Dev dönemi (2022-01 → 2026-03) araştırmasında seçilmiş/ön kayıtlı sistemler, **hiç indirilmemiş ve hiçbir testte kullanılmamış** önceki döneme (2020-03 → 2021-12) aynı parametrelerle taşınınca da null'dan ve al-tuttan ayrışıyor mu? Yeni edge aranmıyor, hiçbir parametre ayarlanmıyor; mevcut sonuçların replikasyonu. Mühürlü dönem (≥ 2026-04-01) ve G3'e dokunulmaz; kullanıcı kararı: son 6 ay hiçbir testte kullanılmayacak.

## Veri (yeni, ayrı kök; mevcut tape/manifest değişmez)
- Kaynak: Binance USDT-M, `data.binance.vision` aylık arşiv; klines 1h, markPriceKlines 1h, fundingRate (mevcut `kepler/data.py`, sha256 doğrulamalı). Aylar **2019-09 → 2021-12**. 2022-01 ve sonrası bu kökte yoktur; yükleme `tape.load(root, sym, end="2022-01-01")`.
- Kök `/data/pre2022` (Modal Volume), manifest `data_manifest/manifest_pre2022.json` (mevcut `manifest.json` ve `data_hash` dokunulmaz). QC (`kepler.qc`) ve kline~mark ayrışma kesimi (`divergence_cutoff`) aynen uygulanır.
- Sembol/ay kullanılabilirliği **UNKNOWN** (arşivde 2020'de bazı sembollerin olmadığı biliniyor, hangilerinin ne zaman başladığı doğrulanmadı). Eksik olan sembol analizden düşer, sayısı raporlanır; sonuca bakıp sembol eklenmez/çıkarılmaz.
- Evren sıralaması (K7 için) aylık quote-volume top-20, nedensel (ay M = M−1 hacmi), emtia/stable sıralamadan önce çıkar (`EXCLUDE_BASES`), mevcut kodla.

## Kod değişikliği (küçük; hakem/denetim/risk/mühür koduna DOKUNULMAZ)
`kepler/universe.py`: `START`, `RANK_START` ve kök parametreleştirilir (CLI `--start 2019-09 --rank-start 2019-08 --root /data/pre2022`; varsayılanlar aynı, davranış değişmez; mevcut testler yeşil kalmalı). `scripts/pre2022.py`: araştırma kodu (tavansız): mevcut işçi kodunu (`scripts/full_systems.py`, `scripts/search.py`, `scripts/completion.py`) yeni pencere/evrenle çağırır. Hakem+yapıştırma satırı değişmez (473).

## Blok A — tam Turtle S1 / S2 ve takvim düzeltmeli S1c / S2c (N = 4)
**Takvim düzeltmesi (2026-10-02 eklendi, veriye bakmadan):** kitaptaki 20/10 ve 55/20 günler ile N = ATR(20)
**işlem günüdür** (haftada 5). Dev dönemindeki S1/S2 bunları kripto takvim günü (haftada 7) olarak kullandı, yani
orijinalden ~%30 hızlıydı. S1c/S2c aynı kuralları 7/5 oranıyla takvim gününe çevirir: **S1c giriş 28 / çıkış 14,
S2c giriş 77 / çıkış 28, ikisinde N = Wilder ATR(28)**; stop 2N, ekleme 0,5N, birim sınırları, gruplar, Spec ve
dönem S1/S2 ile birebir aynı. S1c/S2c dev döneminde hiç koşulmadı. S1/S2 dev sonuçlarıyla karşılaştırma için,
S1c/S2c orijinale sadık sürümdür.
Sistem, yönetici, gruplar ({BTC,ETH,BNB} {SOL,AVAX,ADA} {XRP,DOGE,LINK}), Spec (fee 10 + slip 2, mmr 0,005, kaldıraç limiti 10, gross_cap 4 × sermaye, sermaye 10 000, tick/step kuralı), `equity_scale` kapalı, kill yok: `reports/full_systems_protocol.md` ile **birebir**. Evren: genişletilmiş-9 içinden pencerede verisi olanlar. Dönem **2020-03-01 → 2022-01-01** (kitap tam seride hesaplanır, pencere başında tutulan pozisyon açık hedef; geç listelenen sembol ilk verisinden itibaren işlem görür).
Kart K1–K9 (`BACKTEST.md` §11, eşikler aynı), uygulama ayrıntıları:
- **K1:** ortak-ofset rotasyon null'u (B = 500, `default_rng([0, i])`), brüt p ≤ **0,05/4 = 0,0125** ve DSR ≥ 0,95 (deneme Sharpe'ları = S1, S2, S1c, S2c). Katı raporlama: p ayrıca 0,05/12 (dev N'si) ve DSR kümülatif N = 16 ile yazılır (karar 0,0125 ve N = 4 ile; ablasyonlar seçim değil kontroldür).
- **K2:** eşit notional al-tut (pencerede verisi olan semboller, aynı hakem/Spec); Sharpe > al-tut **ve** NW alfa t ≥ 2.
- **K3:** net Sharpe ≥ 1,0; net > 0 hem fee 16 + slip 6'da hem 1 bar gecikmede.
- **K4:** planlanan boyut = `reports/backtest_completion.md` madde 2'deki ölçekli risk (S1 0,0017, S2 0,0016; S1c S1'inkini, S2c S2'ninkini kullanır, ayrıca türetilmez); kartın tanımıyla maks DD ≤ %25 ve bootstrap DD %95 ≤ %30 (blok 20, B = 2000, seed 0). %1 risk için DD bilgi olarak yazılır.
- **K5:** 24 komşu (S1 giriş {16,18,20,22,24} × çıkış {8,…,12}; S2 {44,50,55,61,66} × {16,…,24}; S1c {22,25,28,31,34} × {11,13,14,15,17}; S2c {62,69,77,85,92} × {22,25,28,31,34}; ATR penceresi sabit), ≥ %70 net > 0 ve komşu medyan Sharpe ≥ seçilenin yarısı.
- **K6:** yarıyıl pencereleri 2020-07→2021-01, 2021-01→2021-07, 2021-07→2022-01 (3 adet; ≥ 2'sinde net > 0) **ve** başlangıç 2020-03-01 / 04-01 / 05-01 / 06-01 (bitiş 2022-01-01) dördünde net > 0.
- **K7:** sinyalden bağımsız kural: aylık top-20'de ≥ 8 ay, genişletilmiş-9 dışı, ilk bar ≤ 2020-07-01, kesim yok; her sembol kendi grubu; fee 16 + slip 2'de net > 0.
- **K8:** 4 ablasyon (stop, N-boyutlama, piramit, birim sınırı kapalı) kontrol olarak koşulur (defter dışı); `full` Sharpe'ı her birinden büyük olmalı.
- **K9:** `robust.regime` (BTC, 200 gün EMA, 30 gün eğim; etiketsiz ilk ≈ 230 gün K9 dışı); ≥ 2 rejimde net ≥ 0 ve tek rejim payı ≤ %80.
- **Karar:** `robust.decision` (K1 veya K2 kalırsa NO_EDGE; K3–K9'dan biri kalırsa ZAYIF; hepsi geçerse ADAY → G3 yine yalnızca kullanıcı komutuyla).
- **Betimleyici stres (karar dışı):** `stress.window_stats` ile 2020-03-09→03-16 (COVID çöküşü) ve 2021-05-17→05-24.

## Blok B — arama ailelerinin aile-seçilmiş 6 yapılandırması (N = 6)
`don_80_20, ema_10_100, tsmom_14_1, xscarry_7, xsmom_7, xsrev_3` (`reports/search_protocol.md`; yeniden seçim YOK), genişletilmiş-9 evreni, sembol-başına bağımsız koşu (`scripts/search.py` yöntemi: hakem, fee 4/9/10/11/16 × slip 2 + fee 10 × slip 6), pencere 2020-03-01 → 2022-01-01, kesitsel aileler panel = pencerede verisi olan semboller. **Kriter (search protokolüyle aynı):** brüt PnL ortak-ofset rotasyon null'ında (B = 300) p ≤ 0,05/6 **ve** net > 0 fee 10'da **ve** fee 16'da. Aile başına sonuç ayrı yazılır; Bonferroni 6'ya.

## Yorum kuralı (sabit)
Replikasyon "başarılı" ⇔ Blok A'da bir sistem ADAY (K1–K9 hepsi) **veya** Blok B'de en az bir yapılandırma kriteri geçer. Başarılı çıksa bile bu **ikinci bir görülmemiş-ama-bilinen dönemdir**; mühürlü dönem (kullanıcı kararı) test edilmeyeceği için bu replikasyon aday için tek zaman-dışı kanıt olur. Başarısızsa mevcut NO_EDGE sonucu pekişir; sonuca bakıp pencere/sistem eklenmez.

## Tahmin (veriye bakmadan yazıldı)
2020-21 güçlü bir boğa döngüsüdür (BTC ≈ 7 000 → 69 000); trend sistemlerinin net pozitif çıkması beklenir. Asıl sorular null (K1), al-tut (K2) ve rejim tek-kaynaklılığı (K9). K2 ve K9'un kalma olasılığı yüksek; K4 (ölçekli boyutta bile) dev dönemi gibi kalabilir.

## Sınırlar / UNKNOWN
(0) S1/S2'nin dev sonuçları takvim günüyle (orijinalden ~%30 hızlı) alındı; bu sapma dev raporlarında yazılı değildi, burada kayda geçti. (1) Rejim: çoğunlukla boğa; trend-takip lehine yanlı. (2) Hayatta kalma yanlılığı: evren bugünün majörleri (iyimser); K7 kısmen düzeltir. (3) **Kör değil:** araştırmacı 2020–21 piyasa tarihini biliyor; yalnızca bu veri hiçbir testte/ayarda kullanılmadı. (4) 2020 hacim ve spread'i bugünkünden kötü: slippage 2 bps iyimser olabilir (K3 stresi 6 bps). (5) Sembol kuralları, mmr kademeleri, likidasyon ücreti UNKNOWN (dev ile aynı). (6) Funding aralığı 8 saat varsayımı veriden doğrulanır.

## Deneme sayısı ve bütçe
Yeni hipotez 10 (A: 4, B: 6; ablasyon/komşuluk/null/stres kontrol); kümülatif defter 4 116 + A'nın defter satırları (2) + B'nin hakem satırları (6 yapılandırma × 9 sembol × 6 maliyet senaryosu). Bütçe tahmini (UNKNOWN): veri indirme ve QC ≈ 30–40 dk Modal (12 paralel), koşular ≈ 1–2 saat; ≲ 150 araç çağrısı, dış sınır 1 gün. Aşılırsa dur ve raporla.

## Onay istenenler
(a) Bu protokol (kart eşikleri, N, pencereler, evren kuralı; takvim düzeltmeli S1c/S2c dahil). (b) Binance arşivinden 2019-09 → 2021-12 indirme (ağ izni). (c) `universe.py` parametreleştirme (veri aracı; satır sayısı (b) tavanı ≲500 altında kalmalı, sayıyı raporlarım).

## Not (2026-10-02, koşudan önce; parametre/eşik/N değişmedi)
Kullanıcı mühür kararını güncelledi: "hiç kullanılmayacak" yerine **"aday çıkmadıkça açılmaz"** (MISSION G3, kural 3). Bu protokolde "son 6 ay hiçbir testte kullanılmayacak" geçen yerler bu karara göre okunur: replikasyonda aday çıkarsa (Blok A'da ADAY) G3 kullanıcı komutuyla açılabilir; bu koşuda mühürlü döneme yine dokunulmaz.

## Koşu notu (veri; 2026-10-02, indirmeden sonra; parametre/eşik/evren/N/dönem değişmedi)
Aylık arşivde klines/markPriceKlines/fundingRate **2020-01'den başlıyor**: 2019-09 → 2019-12 aylık dosyaları yok (BTC/ETH/XRP/ADA/LINK 2020-01, BNB ilk bar 2020-02-10, DOGE 2020-07-10, SOL 2020-09-14, AVAX 2020-09-23; hepsi 9'u pencerede verisi var, hiçbiri düşmedi). Protokolün "2019-09 → 2021-12" aralığının 2019 kısmı bu yüzden yok: ısınma 2 aya (≈ 60 gün) kısalıyor; **S2c'nin 77 günlük kanalı ilk sembollerde ≈ 2020-03-18'de, geç listelenenlerde ilk verinin 77. gününde dolar** (ısınma bitmeden işlem yok, pencere başında flat). Günlük (`daily/`) arşivden 2019 verisi eklenmedi (protokol aylık arşivi sabitledi; indirici değişmedi). Evren üyeliği 2020-02'den (2019-12 hacmi yok; 2020-02 üyeliği yalnızca 2020-01 hacminden, 11 sembol) → 2021-12: 23 ay; K7'nin "aylık top-20'de ≥ 8 ay" sayımı bu aylarda. ICPUSDT için fundingRate dosyası arşivde yok (evrende; K7/Blok B kurallarına girmez: ilk bar > 2020-07-01). QC: 66 sembol, 0 ERROR, 227 WARN, 67 INFO (`delisted` INFO'su veri bilerek 2021-12'de bittiği için 66 sembolde anlamsızdır), kline~mark kesimi (`usable_until`) yok.
