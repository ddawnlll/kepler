# Ön kayıt: Bollinger uzmanı (E4, tek başına) — yatay rejimde geri dönüş EV1'in K9 kusurunu kapatır mı?

**Durum:** TASLAK (dalda commit'li, henüz DONMADI). Kullanıcı onayı bekliyor; onaydan sonra "ön kayıt onaylandı" commit'i koddan ve koşudan önce atılır ve ancak o commit'ten sonra kural donar (MISSION kural 11). Onaya kadar taslak serbestçe düzeltilebilir; koşu yapılmadı. Onaydan sonra kural, parametre, evren, N ve ölçüt değişmez; değişiklik = yeni ön kayıt + yeni deneme.
**Karar bekleyen noktalar** (aşağıda varsayılan seçildi, değiştirilecekse commit'ten önce): (1) yön: yalnızca geri dönüş; (2) n = 20, k = 2; (3) evren ext-9, dönem EV1 ile aynı; (4) uzman günlük kapanışta çalışır.

## Neden (gözlenmiş engel; MISSION kural 4)
EV1 (`reports/ensemble.md`) ZAYIF: K1–K8 geçti, **K9 kaldı**. Net kâr rejimlere şöyle dağılıyor: bull +7 329, bear +536, range −895; bull payı %105 > %80. Üç uzmanın üçü de süreklilik/akış (trend, kesitsel momentum, carry) yönünde; yatay piyasada trend sinyali ileri geri döner ve kaybeder.
**Mekanizma varsayımı:** yatay rejimde fiyat ortalamasına döner; geri dönüş uzmanı tam orada kazanıp trend uzmanıyla negatif ilişkili olabilir. Bu bir varsayımdır, kanıt değil.
**Aleyhte kanıt (kendi verimiz):** `xs_rev` (kesitsel 1–5 gün geri dönüş) net negatif, brüt ≈ −25 bps/işlem (`reports/search.md`); Zone Fade (bölgeden dönüş) NO_EDGE (`reports/zone_fade.md`). Bu test zaman serisi bandı ve günlük ufuk olduğu için aynı şey değil, ama önsel beklenti düşük.
**Dürüstlük notu:** hipotez, EV1'in rejim tablosu görüldükten sonra seçildi (dallanma riski: orta). Dönem ve evren daha önce çok kullanıldı (dev 2022–26 + pre2022); bu **görülmüş veride ön kayıtlı test**tir (BACKTEST §8.5). K7 sembol kümesi EV1 K7 ve aramada zaten kullanıldı: bağımsızlığı zayıf.

## Veri, evren, dönem (EV1 ile birebir aynı, karşılaştırılabilirlik için)
- `tape.load`: `/data/pre2022` (2020-01 → 2021-12) + `/data` (2022-01 → 2026-03), sembol başına birleştirilmiş. Mühür (≥ 2026-04-01) dokunulmaz.
- **Evren:** genişletilmiş-9 (BTC ETH SOL XRP BNB DOGE ADA LINK AVAX). Aktiflik: ≥ 90 günlük kapanış.
- **Değerlendirme dönemi:** 2020-04-01 → 2026-04-01. Karar her UTC gününün kapanışında, dolum sonraki bar açılışında (`next_open`).

## Uzman (tüm parametreler sabit)
`kepler/experts/bollinger.py`, `forecast(close, st, p)`, günlük kapanış paneli `C`:
- SMA_t = ortalama(C_{t−n+1..t}); S_t = **popülasyon** std (ddof = 0; Bollinger tanımı, TradingView `ta.bb` ile aynı olduğu varsayıldı: **sayı karşılaştırması yapılmadı, doğrulanmadı**).
- z_t = (C_t − SMA_t) / S_t. S_t = 0 ise forecast 0.
- **F_t = clip(−z_t / k, −1, 1)**, n = 20, k = 2. Yani alt banda (z ≤ −2) tam long, üst banda tam short, ortada sıfıra doğru doğrusal; geri dönüş yönünde, eşik/durum yok (sürekli tahmin).
- Aktif olmayan hücre NaN. Gün t kararı yalnızca C_{≤t} görür.
- Girdi `close` panelinden gelir; piyasa durumundan yeni bir şey gerekmez (`market_state.py`/`state.py` değişmez).

## Sistem (EV1 ile aynı zincir, tek uzman)
Aday ve risk motoru `reports/ensemble_protocol.md` §3–§4 ile **birebir**: `combine` (F_raw ölçeklemesi), `portfolio.size` (τ = 0,20, IDM, tavanlar, tampon 0,2), hakem spec'i (sermaye 10 000, fee 10 + slip 2 bps RT, kaldıraç 10, mmr 0,005).
**Uygulama:** `ensemble.Params.weights`a 4. eleman (E4) eklenir, varsayılanı 0; EV1 çıktısı birebir aynı kalmalı (golden eşitlik testi). Bu koşu weights = (0, 0, 0, 1). Ensemble'a pozitif ağırlıkla katmak **bu protokolün kapsamı dışındadır** (ayrı ön kayıt).

## Denemeler
- **N = 1:** birincil (E4 tek başına, n = 20, k = 2).
- **Kontroller** (N'ye girmez, deftere girmez):
  - K5 komşuları: n ∈ {16, 18, 20, 22, 24} × k ∈ {1,6; 1,8; 2,0; 2,2; 2,4} − birincil = **24 komşu** (BACKTEST §11 ±%10/±%20, tam kartezyen). σ, ρ, τ sabit.
  - K8 ablasyonları: `no_risk` (n_i = K·F_i/M), `no_buffer` (tampon 0).
  - Rotasyon null'u (K1), maliyet/pencere/K7/al-tut koşuları (EV1 ile aynı).
  - **Yön testi (bilgi, karar dışı):** F işareti ters (`-F`, bandda trend takibi). Etki mean-reversion'dan mı geliyor, tersinden mi, ayırt etmek için.
- **DSR:** deneme Sharpe kümesi = birincil + 2 ablasyon (N = 3, muhafazakâr). Bonferroni ×3 bilgi olarak yazılır.
- Kümülatif deneme sayacı: TASKS.md'deki güncel değer + 1 (okuma anında 4 118 (Zone Fade sonrası); koşudan önce yeniden bak, sayıyı TASKS.md'den al).

## Başarı kartı
BACKTEST §11 eşikleri ve uygulama ayrıntıları `reports/ensemble_protocol.md` "Başarı kartı" ile **birebir** (K1: ortak ofset rotasyon null'u B = 300, p ≤ 0,05 ve DSR ≥ 0,95; K2 al-tut + NW alfa t ≥ 2; K3 net Sharpe ≥ 1,0 ve fee 16 + slip 6 / 1 bar gecikmede net > 0; K4 DD; K5 komşular; K6 pencereler; K7 14 sembol; K8; K9 `robust.regime`). Karar: `robust.decision` (K1/K2 kalırsa NO_EDGE, K3–K9'dan biri kalırsa ZAYIF, hepsi geçerse ADAY; G3 yalnızca kullanıcı komutuyla).

### Mekanizma kriterleri (bu protokole özgü; karar kartının dışında, entegrasyon kapısı)
- **M1:** `robust.regime` ile **range** rejiminde net PnL > 0.
- **M2:** günlük net PnL korelasyonu EV1'inkiyle (`ledger/ensemble/`) ≤ 0,30 (çeşitlendirme).
- **Entegrasyon kapısı:** ensemble'a katma önerisi (ayrı ön kayıt) **yalnızca** K1 ve K2 geçerse **ve** M1 ve M2 sağlanırsa açılır. Aksi halde: **"BOLLINGER RAFA (bu tanımla)"**; ensemble'a katılmaz, yeni tanım = yeni ön kayıt.
- Sonuç ne olursa olsun K9'u kapatma iddiası ancak ensemble entegrasyonunun ayrı sonucuyla yapılır.

## Bilgi (karar dışı)
İki alt dönem ayrı (2020-04 → 2022-01, 2022-01 → 2026-04), rejim payları, devir ve işlem sayısı, funding payı, sembol payları, 500 USD sermayeli koşu, tarihsel stres pencereleri (LUNA, FTX), kill switch tetik bilgisi, MinTRL.

## Tahmin (koşudan önce; yargı, doğrulanmadı)
- Olası sonuç **NO_EDGE** (K1 kalır). Net Sharpe −0,3 … 0,4 aralığı beklenir; aleyhte kanıt yukarıda.
- Pozitif çıkarsa en olası açıklama yatay rejimdeki kazanç ve bull'da kayıp olur (M2 bunu ayırt eder). Yön testi (−F) daha iyi çıkarsa, bu "Bollinger çalışıyor" değil "bandda trend takibi" anlamına gelir ve **ayrı ön kayıt gerektirir**, bu protokolden sonuç çıkarılmaz.

## Bütçe
- Kod: `kepler/experts/bollinger.py` (~10 satır), `Params.weights` 4. eleman ve `combine` genişletmesi (`ensemble.py`), `tests/test_bollinger.py` (elle hesaplı: ör. kapanışlar 1…20 için z, F; std = 0 → 0; gelecek-bozma), `scripts/ensemble.py`'ye `--weights` bayrağı (yeni betik yok). Hakem, denetim, risk, state ve mühür koduna dokunulmaz.
- Koşu tahmini 1–3 saat Modal (EV1 ile aynı iş). Aşılırsa dur ve raporla.
