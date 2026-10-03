# Ön kayıt: Seviye olay çalışması (destek/direnç seviyeleri bilgi taşıyor mu?)

**Durum:** ÖN KAYIT. Kullanıcı onaylı parametrelerle (2026-10-03), kod ve koşudan önce commit'lendi. Tanım, parametre, eşik, evren, N ve dönem sonuçtan sonra değişmez (MISSION kural 11). Uygulayan ajan bu belgeyi **olduğu gibi** uygular; belirsizlik varsa kısıtlayıcı yorumu seçer (şüpheli olayı **sayma**) ve nota düşer, kural eklemez. Tasarım: `BACKTEST.md` §15.10. Bu bir **keşif ölçümüdür**: hakem, dolum, strateji ve başarı kartı yok; tek soru "seviye bilgi taşıyor mu".

## Soru
Bir seviyeye ilk dokunuştan sonraki 24 saatlik fiyat hareketi, aynı yapıdaki ama yerinden oynatılmış (placebo) çizgilere dokunuştan sonraki harekete göre farklı mı? (Geri dönüş de, devam/kırılma da "bilgi" sayılır: iki yönlü.)

## Veri, evren, dönem
- `tape.load` (klines 1h, mark kullanılmaz). Mühür (≥ 2026-04-01) dokunulmaz. Evren: genişletilmiş-9 (BTC ETH SOL XRP BNB DOGE ADA LINK AVAX, USDT-M); sembol ≥ 240 günlük veri biriktirince aktif.
- **Birincil dönem:** olaylar 2022-07-01 → 2026-04-01 (ısınma 2022-01'den). **İkinci pencere (görülmüş, yalnızca bilgi, karar dışı):** 2020-07-01 → 2022-01-01 (`/data/pre2022`).
- **Karar ızgarası:** 4h barlar (UTC; `state.bars`/`tape.aggregate`, 00-04-…-20). Yalnızca 4 saatlik barı **eksiksiz** (n = 4) olanlar bar sayılır; eksik bar atlanır ve ufku ona değen olay düşer.
- **ATR (A):** 1d ATR14 (Wilder, `risk.wilder_n`), bar **açılışında** bilinen son tamamlanmış gün. Her bar için `A_i`.
- Sonuç zaman damgalı tüm girdiler kapanış ≤ karar anı (nedensel).

## Ortak sabitler (ayarlanmaz)
Dokunuş bandı ±0,25 A. Yeniden silahlanma: bir olaydan sonra, olay barından **sonraki** bir 4h **kapanışı** seviyeden ≥ 0,5 A uzaklaşınca (|C − L| ≥ 0,5 A_j). Kırılma: seviye `born_at`'ta kapanışın bulunduğu taraf s0 = işaret(C_born − L) olsun; bir 4h kapanışı karşı tarafta ≥ 0,5 A geçerse (s0·(C − L) ≤ −0,5 A) seviye **kırılmış** sayılır ve birincil analizden çıkar (yuvarlak sayı hariç: kafes, kırılmaz). Yaş: `swing` seviyeleri `born_at` + 180 gün sonra düşer. Ufuk h = 6 dört-saatlik bar.

## Seviye tanımları (her tür kendi `born_at`'ı ve geçerlilik süresiyle)
- **swing_1d / swing_3d:** tf = 1d veya 3d (3d çıpası BACKTEST §15.3). Fractal k = 2: bar j swing tepe ⇔ H_j, j±1 ve j±2 barlarının H'sinden **kesin** büyük; swing dip simetrik (L). Fiyat = H_j veya L_j. `born_at` = j+2 barının kapanışı (nedensel); komşu eksikse swing yok. State v0'daki 3d swing koduyla aynı tanım.
- **pivot_classic_1w:** hafta = pazartesi 00:00 UTC; önceki haftanın H/L/C'sinden (saatlik barlardan; hafta ≥ 24×5 saatlik bar içermiyorsa yok) P = (H+L+C)/3, R1 = 2P−L, S1 = 2P−H, R2 = P+(H−L), S2 = P−(H−L), R3 = P+2(H−L), S3 = P−2(H−L) (`kepler/indicators.py::pivots("classic")`, TradingView ile doğrulandı). Yedi seviye; `born_at` = pazartesi 00:00; geçerlilik = o hafta.
- **prev_hl_1w:** önceki haftanın high, low, close'u (üç seviye); aynı `born_at` ve geçerlilik.
- **profile_180d:** her UTC gün başında (00:00 = `born_at`), [t − 180 gün, t) saatlik barlardan hacim profili: 100 eşit kutu (pencere min low → max high), her barın hacmi [low, high]'in kestiği kutulara eşit dağıtılır; POC (en yüksek kutunun merkezi, eşitlikte alt), VAH/VAL (POC'tan başlayıp hacmi büyük komşuyu ekleyerek %70 değer alanı). Üç seviye; geçerlilik = o gün (sonraki 00:00'da yenilenir). Pencere dolu değilse yok. State v0 `_profile` ile aynı kod.
- **round_major:** bar i için adım = 10^⌊log10 C_{i−1}⌋ ve seviyeler adımın tam katları (BTC ≈ 85 000 → 10 000'in katları). `born_at` yok (her zaman geçerli, kırılmaz); silahlanma durumu seviye **fiyatı** başına tutulur.

## Hipotezler (N = 7, tek yapılandırma, grid yok)
H1 swing_1d · H2 swing_3d · H3 pivot_classic_1w · H4 prev_hl_1w · H5 profile_180d · H6 round_major · H7 **çakışma bölgesi**: bar açılışında geçerli ve kırılmamış tüm seviyeler (H1–H6'nın hepsi) fiyata göre sıralanır (yalnızca C_{i−1}'in ±6 A içindekiler), komşu fark ≤ 0,5 A ise aynı bölgeye zincirlenir; `n_types ≥ 2` olan bölge tek "seviye"dir (fiyat = üyelerin ortalaması, bant = [alt − 0,25 A, üst + 0,25 A], kimlik = üye seviye anahtarlarının kümesi, silahlanma bu kimliğe göre; yeniden silahlanma için kapanış bölgenin en yakın kenarından ≥ 0,5 A uzakta olmalı; kırılma: bölge ortalaması s0'a göre karşı kenarı ≥ 0,5 A geçen kapanış).

## Olay ve tepki
- **Olay:** seviye (bölge) silahlıyken, `born_at` ≤ bar açılışı ve bar i'nin [low, high] aralığı seviye bandıyla kesişiyorsa i. bar **dokunur**. Olay = dokunan ilk bar; ardından yeniden silahlanana kadar yeni olay yok. Bir bar birden çok seviyeye dokunabilir: her biri ayrı olay (korelasyon bloğa girer).
- **Yaklaşma yönü** σ = işaret(L − C_{i−1}) (σ = +1: aşağıdan geldi, direnç; −1: destek; eşitse olayı sayma). `C_{i−1}` önceki 4h kapanışı.
- **Tepki:** r = −σ · (C_{i+6} − C_i) / A_i. r > 0 geri dönüş, r < 0 devam/kırılma. i+6 yoksa veya (i, i+6] aralığında eksik bar varsa olay düşer. Hipotez istatistiği **R̄ = tüm olayların (9 sembol toplam) r ortalaması**; her olay eşit ağırlıklı.

## Null (yerinden oynatılmış çizgiler)
B = 300 replikasyon, `default_rng([0, b])`, b = 1…300. Her replikasyonda sembol başına (alfabetik sıra) önce u ~ U(0,75; 2,5), sonra işaret sg ∈ {−1, +1} çekilir; sembolün κ = tüm örneklemde ATR_d/kapanış'ın medyanı. **Tüm tür seviye fiyatları** L' = L · exp(sg · u · κ) olur (yuvarlak sayı kafesi dahil: kafesin tamamı aynı çarpanla kayar, 10^k hizası bozulur). `born_at`, geçerlilik, yaş, s0 (L' ve C_born ile yeniden hesaplanır), kırılma, dokunuş, yeniden silahlanma, tepki ve bölgeleme **aynen** aynı koddur; yalnızca fiyat kaymıştır. Her replikasyon için R̄_b hesaplanır; m = ortalama(R̄_b).
**p = (1 + #{b : |R̄_b − m| ≥ |R̄ − m|}) / (B + 1)** (iki yönlü). Güven aralığı: olayları haftaya göre bloklayıp 1000 kez yeniden örnekle (`default_rng([1, 0])`), (R̄ − m) %95 aralığı.

## Karar (her hipotez ayrı; "bilgi taşıyor" ⇔ hepsi birden)
1. p ≤ 0,05 / 7. 2. |R̄ − m| ≥ 0,10 (ATR birimi; BTC'de günlük ATR ≈ %2–3 ≈ 20–30 bps, gidiş-dönüş 10 + 2 bps'in üstü; yargıdır). 3. Gerçek olay sayısı ≥ 300 (altı "YETERSİZ ÖRNEK": karar verilmez). 4. **Tutarlılık:** (R̄ − m) iki yarıda (2022-07 → 2024-06, 2024-07 → 2026-04) aynı işaretli; her yarı kendi placebo ortalamasını kullanır (yarının olaylarından R̄_yarı − m_yarı, m_yarı = replikasyonların o yarıdaki R̄_b ortalaması). 5. **Yapı uyumu:** placebo ortalama olay sayısı gerçeğin %50–200'ü içinde (dışında "YAPI UYUMSUZ": karar verilmez).
**Genel karar:** hiçbiri "bilgi taşıyor" değilse **"SEVİYE ANLAMSIZ (bu tanımlarla)"**: destek/direnç uzmanları rafa kalkar, yeni tanım = yeni ön kayıt. Biri veya birkaçı geçerse hangi tür ve hangi yönde (geri dönüş / devam) raporlanır; ilgili uzman ön kaydı bu bulgudan türetilir ve dev verisinin görülmüşlüğü belirtilir. **Hiçbir sonuç ADAY veya kart sayılmaz; G3 açılmaz.**

## Raporlanacaklar (karar dışı)
Olay sayıları (gerçek / placebo ortalaması), R̄, m, fark, p, aralık, P(r > 0) gerçek ve placebo, kırılma oranı (olaydan sonra h içinde), sembol ve yarı kırılımları, h ∈ {3, 12} duyarlılığı, ikinci pencere (2020-07 → 2022-01) sonucu, **kırılmış seviyelere yeniden dokunuş** (tanımlayıcı: sayı ve R̄), hipotez başına yürütme süresi ve satır sayıları (`kepler/levels.py`, `scripts/levels_event_study.py`).

## Deneme sayacı ve defter
N = 7 ("seviye" ailesi); proje kümülatif deneme sayısına 7 eklenir ve TASKS.md'ye yazılır. `ledger.record` yalnızca hakem/eleme kaydı kabul ettiği için (hakem dışı ölçüm) sonuçlar `reports/levels_event_study_data/summary.json` içine yazılır; `ledger.py`, hakem, denetim, risk ve mühür koduna dokunulmaz. Yeni tanım veya parametre = yeni ön kayıt ve ayrı N.

## Tahmin (veriye bakmadan)
Çoğu tür için etkinin küçük olması ve "SEVİYE ANLAMSIZ" çıkması muhtemel; yuvarlak sayılar ve çakışma bölgeleri (H6, H7) en olası adaylar, ama yönü (geri dönüş mü devam mı) bilmiyorum. Bunlar tahmin; yanlış çıkabilir.

## Sınırlar / UNKNOWN
Bant, bağ, ufuk, yaş, eşik ve κ ölçeği yargıdır (ayarlanmaz). Hacim profili 1h barlardan yaklaşık. Evren bugünün majörleri (hayatta kalma yanlılığı); dev dönemi görülmüş veri (BACKTEST §8.5), gerçek zaman-dışı kanıt yalnızca mühür (yalnızca ADAY'da) ve canlı veridir. Olaylar çakışır (bir bar çok seviyeye, ardışık barlar komşu seviyelere dokunur); aralık haftalık bloklu bootstrap'tir, p placebo yapısından gelir. κ tüm örneklemden türetilir (yalnızca null ölçeği; işlem yok).
