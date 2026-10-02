# Ön kayıt: Kepler Ensemble v1 (EV1) — piyasa durumu → uzmanlar → aday → risk motoru

**Durum:** ön kayıt; koddan ve koşudan önce commit'lendi (2026-10-02, kullanıcı görevi: "sebebini bul, sistemi kârlı hale getir").
Kural, evren, N ve ölçüt koşudan sonra değişmez (MISSION kural 11). Değişiklik = yeni ön kayıt + yeni deneme.

## Neden (gözlenmiş engel; MISSION kural 4)
Teşhis `reports/pre2022.md`'de. Önceki sistemlerin kartta kalma nedenleri ve EV1'in her birine karşılığı:

| gözlenen engel | EV1'deki karşılık |
|---|---|
| (1) piyasa yönü, küçük zamanlama edge'i | Sürekli (z-skor) trend tahmini + dolar-nötr kesitsel momentum uzmanı |
| (3) yoğunlaşma | Sembol başına eşit risk (ters oynaklık) |
| (4) portföy riski yok | Korelasyon farkındalıklı portföy oynaklık hedefi ve tavanları |
| (5) funding yükü | Funding/carry uzmanı |
| (6) tek hız | Dört trend ufku birlikte |

Bileşenler kitaplardan:
- Trend takibi: Covel *Trend Following*, Faith *Way of the Turtle*
- Mutlak momentum: Antonacci *Dual Momentum*
- Oynaklık ve pozisyon boyutlama: Tharp *Trade Your Way to Financial Freedom*, Chan *Algorithmic Trading*
- Carry: *Currency Strategy* (perp'te funding)

**Dürüstlük notu:** tasarım, dev (2022–26) ve 2020–21 sonuçlarını görmüş bir araştırmacının tasarımıdır. Örneğin 14 günlük ufuk, 2020–21'de geçen `tsmom_14_1`'i içeriyor.
Bu yüzden aşağıdaki test **görülmüş veride ön kayıtlı test**tir (BACKTEST §8.5). Gerçek zaman-dışı kanıt yalnızca mühürlü dönem (G3, kullanıcı komutu, yalnızca ADAY çıkarsa) ve canlı veridir.
Parametreler literatürdeki yaygın değerlerden seçildi; sonuçlara bakılarak ızgara taraması yapılmadı. Bu tasarım için tek ön kayıtlı koşu yapılır.

## Veri, evren, dönem
- **Veri:** sembol başına iki kök birleştirilir, örtüşme yok:
  - `/data/pre2022` (2020-01 → 2021-12, `tape.load(..., end="2022-01-01")`)
  - `/data` (2022-01-01 → 2026-04-01)
  - Klines 1h, mark 1h, funding. Mühür sınırı kodla korunuyor (`tape.load`).
- **Evren:** genişletilmiş-9 (BTC ETH SOL XRP BNB DOGE ADA LINK AVAX). Önceki tüm testlerle aynı; K7 kuralı hazır.
- **Aktiflik:** sembol, ≥ 90 günlük kapanışı olunca aktif olur. Geç listelenenler (SOL, AVAX: 2020-09) o andan sonra girer.
- **Değerlendirme dönemi:** **2020-04-01 → 2026-04-01** (6 yıl). Kitap 2020-01'den itibaren tam seride hesaplanır (ısınma). Hakem yalnızca pencerede koşar.

## Sistem (tüm parametreler sabit)
Karar her UTC gününün kapanışında (23:00 barı) verilir. Dolum sonraki barın açılışında (`fill=next_open`). Bir günün karar girdileri yalnızca o güne kadarki (dahil) verilerdir.

### 1. Piyasa durumu (MarketState)
Notasyon: C_{i,d} = d gününün son saatlik kapanışı, r_{i,d} = ln(C_{i,d}/C_{i,d−1}).
- **Oynaklık:** σ_{i,d} = std(r_{i,d−29..d}, ddof = 1) × √365, alt sınır 0,25.
- **Korelasyon:** ρ_d = aktif sembollerin son 90 günlük r korelasyonu (ikili tam gözlem). ρ⁺ = negatifler 0'a çekilmiş hali.
- **Funding:** φ_{i,d} = son 7 günün (168 saat) ortalama saatlik funding oranı × 24 × 365 (yıllık). Saatlik oran = `fund_hr`, yani oran / aralık saati, bar kapanışında bilinen son değer.

### 2. Uzmanlar (her biri [−1, 1] aralığında tahmin üretir)
- **E1 trend:**
  - L ∈ {7, 14, 28, 56} gün için z_L = ln(C_d / C_{d−L}) / (σ_{i,d}/√365 · √L), f_L = clip(z_L / 2, −1, 1).
  - E1 = ortalama_L f_L.
- **E2 kesitsel momentum:**
  - L ∈ {14, 28, 56} için aktif ve geçerli semboller ln(C_d/C_{d−L})'ye göre sıralanır (eşitlikte ortalama sıra).
  - q = 2·(sıra − 1)/(n − 1) − 1. n < 4 ise q = 0.
  - E2 = ortalama_L q_L.
- **E3 carry:**
  - c = −(φ − 0,1095) / σ. 0,1095 = 0,01%/8 saat taban faiz bileşeni, yıllık.
  - E3 = clip(2c, −1, 1).

### 3. Aday (birleştirme)
- F_raw = 0,6·E1 + 0,2·E2 + 0,2·E3.
- **Tahmin ölçekleme** (nedensel): m_d = d'ye kadarki tüm aktif sembol-günlerde |F_raw| ortalaması (genişleyen pencere).
- F = clip(F_raw · 0,5 / m_d, −1, 1).
- Panelde 30 günden az geçmiş varsa pozisyon yok.

### 4. Risk motoru
Aktif küme A_d, M = |A_d|, w = 1/M.
- **Çeşitlendirme çarpanı:** IDM = min(2,5; 1/√(wᵀρ⁺w)), w eşit ağırlık vektörü.
- **Ham hedef:** n_i = K · τ · w · IDM · F_i / σ_i. K = sermaye, τ = **0,20** (yıllık hedef oynaklık).
- **Portföy oynaklık tavanı:** V = √(nᵀΣn)/K, Σ = diag(σ) ρ diag(σ). V > τ ise tüm n'ler τ/V ile çarpılır.
- **Tavanlar:** |n_i| ≤ 1,0·K. Σ|n_i| ≤ 3·K; aşılırsa tüm n'ler orantılı küçültülür.
- **Tampon** (devir azaltma): u_i = K·τ·w·IDM/σ_i (tam tahmindeki pozisyon). |n_i − n_önceki| > 0,2·u_i ise hedef n_i olur, değilse önceki hedef korunur.
  Aktiflikten çıkan sembolün (veri sonu) hedefi 0.
- **Stop yok** (`stop = NaN`). Hakemin likidasyon koruması açık.
- **Kill switch birincil koşuda yok** (operasyonel kontrol; canlıda %30). %25 ve %30'da tetiklenip tetiklenmeyeceği bilgi olarak raporlanır.

### Hakem
- Portföy hakemi (`evaluate.evaluate_book`): denetim + defter.
- Spec: sermaye 10 000, fee 10 + slip 2 bps RT, kaldıraç limiti 10, mmr 0,005, `gross_cap` = 3 × sermaye, likidasyon açık.
- tick/step `scripts/full_systems.py::load` kuralıyla.
- Funding verisi kitaba `kl.fund_hr` sütunuyla girer.
- `audit.check_causal_book` yalnızca OHLCV'yi bozuyor. Funding nedenselliği ayrı birim testle sınanır (fund_hr bozulunca geçmiş hedefler değişmez).

## Denemeler
- **N = 1:** birincil EV1.
- **Kontroller** (N'ye girmez, deftere girmez):
  - 5 ablasyon (K8):
    - `trend_only` (ağırlık 1/0/0)
    - `no_xs` (0,75/0/0,25)
    - `no_carry` (0,75/0,25/0)
    - `no_risk`: n_i = K·F_i/M; σ, IDM, V tavanı yok; tavanlar ve tampon (u_i = K/M) aynı
    - `no_buffer` (tampon 0)
  - 6 komşu (K5)
  - Rotasyon null'u (K1)
  - Maliyet, pencere, K7, al-tut koşuları
- **DSR:** deneme Sharpe kümesi = birincil + 5 ablasyon (N = 6; muhafazakâr). Bilgi olarak Bonferroni ×6 de yazılır.

## Başarı kartı (BACKTEST §11 eşikleri; uygulama ayrıntıları)
- **K1:** ortak ofsetli rotasyon null'u.
  - B = 300, u_i = `default_rng([0, i]).uniform(0,05; 0,95)`.
  - Her sembolün günlük F serisi (ısınmada 0) aynı k = ⌊u·gün sayısı⌋ ile dairesel kaydırılır, sonra sembolün aktif olmadığı günlerde 0'a maskelenir. σ, ρ, IDM ve tavanlar gerçek veriyle kalır.
  - Geçme: brüt p ≤ 0,05 **ve** DSR ≥ 0,95.
- **K2:** eşit notional al-tut (`robust.buy_hold`, ext-9, her sembol K/9, aynı hakem ve Spec). Geçme: Sharpe > al-tut Sharpe'ı **ve** NW alfa t ≥ 2 (gecikme 5).
- **K3:** net Sharpe ≥ 1,0; net > 0 hem fee 16 + slip 6'da hem 1 bar gecikmede (`delay=1`).
- **K4:** planlanan boyut τ = 0,20 ile maks DD (sermayeye, toplamsal) ≤ %25 ve bootstrap DD %95 ≤ %30 (blok 20, B 2000, tohum 0).
- **K5:** 6 komşu:
  - Tüm geri bakışlar (trend L, kesitsel L, carry 7, σ 30, ρ 90 günü) ×{0,8; 0,9; 1,1; 1,2} ile ölçeklenir, tamsayıya yuvarlanır.
  - Ağırlıklar (0,5/0,25/0,25) ve (0,7/0,15/0,15).
  - Geçme: ≥ %70'i fee 10'da net > 0 **ve** komşu medyan Sharpe ≥ birincilin yarısı.
- **K6:** 12 pencere: 2020-07 → 2026-01 arası 11 yarıyıl + 2026-Q1. ≥ %60'ı net > 0. Başlangıç 2020-04-01 / 05-01 / 06-01 / 07-01 kaydırmalarında (bitiş 2026-04-01) dördü de net > 0.
- **K7:** dev K7 sembolleri (14: PEPE SHIB APE APT ARB BCH ETC FIL GMT LTC MATIC NEAR OP SUI; `scripts/search.py` replikasyon kuralı), kendi paneli, 2023-07-01 → 2026-04-01, fee 16 + slip 2. Geçme: net > 0.
- **K8:** birincil Sharpe her ablasyondan büyük.
- **K9:** `robust.regime` (BTC). Geçme: ≥ 2 rejimde net ≥ 0, tek rejim payı ≤ %80.
- **Karar:** `robust.decision`.
  - K1 veya K2 kalırsa NO_EDGE.
  - K3–K9'dan biri kalırsa ZAYIF.
  - Hepsi geçerse ADAY. G3 yine yalnızca kullanıcı komutuyla, tek atış.
- **Bilgi (karar dışı):**
  - İki alt dönem ayrı (2020-04 → 2022-01, 2022-01 → 2026-04): net, Sharpe, alfa t
  - 500 USD sermayeli koşu (min notional 5 etkisi)
  - Funding payı, sembol payları, devir
  - Tarihsel stres pencereleri (LUNA, FTX, 2021-05-17 → 05-24)
  - Kill switch tetik bilgisi, MinTRL

## Tahmin (koşudan önce)
- Net Sharpe 0,7–1,2. K4'ün geçmesi beklenir (τ = 0,20 ve portföy tavanı).
- En olası kalma noktaları K1 (null) ve K3 (Sharpe ≥ 1). 2022 ayı piyasasında trend uzmanının short'ları al-tuta karşı alfa üretebilir; K2 belirsiz.

## Bütçe ve deneme sayısı
- Kod: `kepler/ensemble.py` (araştırma kodu) + `tests/test_ensemble.py` (elle hesaplı) + `scripts/ensemble.py` (Modal işçisi) + `scripts/ensemble_report.py`.
- Hakem, denetim, risk ve mühür koduna dokunulmaz.
- Koşu tahmini 1–3 saat Modal. Aşılırsa dur ve raporla.
- Kümülatif defter: önceki satırlar + 1.
