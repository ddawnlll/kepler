# Tam Turtle S1/S2 ön kaydı (V4; kod ve koşudan ÖNCE commit'lenir; sonuca bakılıp değiştirilmez)

**Soru.** Kitaptaki tam sistem (N-boyutlama, 2N stop, piramitleme, birim sınırları + portföy brüt tavanı), G2'deki kırpılmış sürümün (stopsuz, sabit boyut, sınırsız) yapamadığını yapıyor mu?
Karar `BACKTEST.md` §11 başarı kartıyla (K1–K9; K10 = G3, açılmaz). Eşikler kartta yazılı olduğu gibi; bu belge yalnızca kartın uygulama ayrıntısını (dönem, evren, N, formül ayrıntısı) sabitler.

## Sistem (her ikisi aynı yönetici; fark yalnızca yön sinyali)
- Yön sinyali: `signals.turtle(20, 10)` = **S1**, `signals.turtle(55, 20)` = **S2** (G2'dekiyle birebir aynı kod; Faith'in "son kırılım kazançlıysa atla" kuralı ve trend filtresi YOK, G2 ile aynı sapma).
- Yönetici: `kepler/turtle.py::turtle_book` varsayılanları: risk %1/birim, N = Wilder ATR(20) günlük, stop 2N, ekleme 0,5N, en çok 4 birim/sembol, aynı gruptaki aynı yön ≤ 6 birim, toplam aynı yön ≤ 12 birim, sermaye **sabit** 10 000 USDT (ölçek; sonuçlar sermayeye oranlı getiri/Sharpe/DD olarak okunur; 500 USD gerçek sermaye lot/min-notional kısıtları UNKNOWN olduğundan kullanılmaz).
- Evren (sinyalden bağımsız, önceden sabit): genişletilmiş-9 = BTC, ETH, SOL, XRP, BNB, DOGE, ADA, LINK, AVAX.
- Korele gruplar (önceden sabit, veriye bakılmadan): **{BTC, ETH, BNB}**, **{SOL, AVAX, ADA}**, **{XRP, DOGE, LINK}**.
- Hakem Spec (temel): fee 10 bps rt + slip 2 bps rt, kaldıraç limiti 10, mmr 0,005, likidasyon açık, çıkış maliyeti açık, **`gross_cap` = 4 × sermaye = 40 000 USDT** (L_max = 4). tick = 10^(⌊log10(min kapanış)⌋ − 5), step = 10^(⌊log10(2500 / max kapanış)⌋ − 3) (sembole göre; gerçek kurallar UNKNOWN). Kill switch **yok** (Turtle'ın parçası değil; canlıda ayrıca konur).
- Dönem: **2022-03-01 → 2026-04-01** (60 gün ısınma; mühür ≥ 2026-04-01 açılmaz, veri yalnızca `tape.load`). Pencere başında tutulan pozisyon açık hedef olur (kitap tam seride hesaplanır). Isınma günleri dönem dışı olduğundan DSR/Sharpe serisinde sıfır-PnL ısınma günü yok.
- Günlük net getiri = günlük PnL / 10 000 (toplamsal, bileşik yok); yıllık Sharpe = günlük × √365.

## Denemeler ve N
Her sistem (S1, S2) için 6 yapılandırma, hepsi `evaluate_book` üzerinden deftere (`ledger/full_systems/ledger.jsonl`), **N = 12**:
`full` · `no_stop` (stop kapalı) · `fixed_size` (N-boyutlama yerine birim notional sabit 2 500 = sermaye × 0,25) · `no_pyramid` (en çok 1 birim) · `no_limits` (birim sınırları kapalı) · `g2_equiv` (stop, piramit, sınır kapalı, sabit notional 1 000 = G2'nin kuralı; "önceki basit hal" karşılaştırması).
Sağlamlık koşuları (maliyet ızgarası, gecikme, komşuluk, pencereler, başlangıç kaydırma, K7, null) kontrol sayılır, deftere değil `reports/full_systems_data/` JSON'una yazılır, N'ye girmez. Kümülatif proje deneme sayısı (tüm `ledger/` dosyaları) raporda ayrıca yazılır.

## Kart maddeleri (hepsi S1 ve S2 için ayrı ayrı; geçme eşiği kartta)
- **K1** Null: sinyalin günlük karar dizisi `robust.rotate_signal` ile ortak ofsetle (tüm semboller aynı u ~ U(0,05; 0,95), `default_rng([0, i])`) dairesel kaydırılır, aynı yönetici + portföy hakemi ile koşulur (temel maliyet). **B = 500**. p = (1 + #{null brüt ≥ gerçek brüt}) / 501, tek yönlü; eşik **p ≤ 0,05/12**. **VE** DSR ≥ 0,95: `stats.dsr`, deneme Sharpe'ları = 12 denemenin günlük net Sharpe'ları (N = 12), seri = `full`'ın günlük net getirisi. PSR(0) ve MinTRL raporlanır.
- **K2** Benchmark: eşit notional al-tut (9 sembol, toplam 10 000, aynı hakem/Spec/pencere); koşul: yıllık net Sharpe(strateji) > Sharpe(al-tut) **ve** `stats.nw_alpha` (gecikme 5) t(a) ≥ 2.
- **K3** Net Sharpe (yıllık, temel maliyet) ≥ 1,0 **ve** net > 0 hem (fee 16 + slip 6)'da hem `Spec.delay = 1` (fee 10 + slip 2) koşusunda. Fee 4/9/10/11/16 (slip 2) tablosu raporlanır.
- **K4** Gerçekleşen maks DD (toplamsal equity, sermayeye oran, temel maliyet) ≤ %25 **ve** `stats.bootstrap_summary` (ortalama blok 20, B = 2000, seed 0) maks DD %95 dilimi ≤ %30. Blok 10/40 duyarlılığı raporlanır, karar 20 ile.
- **K5** Komşuluk: `robust.neighbors(dict(entry, exit))` tam ızgara (24 komşu; S1: giriş {16,18,20,22,24} × çıkış {8,9,10,11,12}; S2: {44,50,55,61,66} × {16,18,20,22,24}), yönetici parametreleri sabit; fee 10 + slip 2. Koşul: komşuların ≥ %70'inde net > 0 **ve** komşu medyan Sharpe ≥ seçilenin yarısı.
- **K6** Pencereler: 7 yarıyıl (2023-H1 … 2025-H2, 2026-Q1; `scripts/g2.py::WINDOWS`) net > 0 olanlar ≥ %60 (yani ≥ 5/7) **ve** başlangıç 2022-03-01 / 04-01 / 05-01 / 06-01 (bitiş 2026-04-01) dördünde net > 0 (fee 10 + slip 2).
- **K7** Çapraz varlık: sinyalden bağımsız kural (`scripts/search.py` replikasyon kuralı: aylık top-20'de ≥ 8 ay, genişletilmiş-9 dışı, ilk bar ≤ 2023-07-01, kesim yok); dönem 2023-07-01 → 2026-04-01; aynı yönetici; **her sembol kendi grubu** (korele grup bilgisi önceden yok), toplam/sembol sınırı aynı; fee 16 + slip 2'de net > 0. Evren listesi koşuda yazılır.
- **K8** Ablasyon: temel maliyet, ana dönem; `full`'ın yıllık Sharpe'ı dört ablasyonun (`no_stop`, `fixed_size`, `no_pyramid`, `no_limits`) **her birinden büyük** olmalı (bir bileşen Sharpe'ı düşürmüyorsa o bileşen atılır). `g2_equiv` karar dışı: yalnızca "tam sistem kırpılmışı yeniyor mu" tablosu.
- **K9** Rejim: `robust.regime` (BTC günlük, 200 gün EMA, 30 gün eğim, etiket ≤ d−1 verisiyle; ilk 230 gün etiketsiz = K9 dışı); günlük net PnL rejime bölünür. Koşul: üç rejimden en az ikisinde net ≥ 0 **ve** tek bir rejimin toplam net'e oranı ≤ %80 (toplam net > 0 iken).
- **K10** Koşulmaz (G3, kullanıcı komutu).
- **Karar:** `robust.decision` (K1–K9 hepsi → ADAY; K1 veya K2 kalırsa NO_EDGE; K3–K9'dan biri kalırsa ZAYIF). Raporun ilk cümlesi kaldığı ilk madde(ler)i yazar.

## Koşu kuralı
Tek koşu. Altyapı çökmesi (kod hatası, bellek, zaman aşımı) dışında yeniden koşulmaz; çökme olursa yalnızca çökmeyi gideren değişiklik yapılır ve rapora yazılır. Parametre, eşik, evren, N ve kart maddesi sonuç görüldükten sonra değiştirilmez. Aday çıkarsa G3 yine yalnızca kullanıcı komutuyla.

## Bilinen sapmalar ve UNKNOWN (rapora kopyalanır)
- Sermaye sabit (equity geri beslemesi yok); Turtle'ın "son kırılım kazançlıysa atla" kuralı ve ek giriş yok (yön sinyali durumu kalır; stop sonrası yön değişene kadar yeniden giriş yok); günde en çok 1 ekleme; stop kararı günlük kapanışta kurulur, hakem bar içinde yürütür, yönetici taklidi hakemle aynı tetik verisini (mark H/L; mark yoksa kline) ve tick yuvarlamasını kullanır (bağımsız incelemeden sonra, koşudan önce eklendi); yine de küçük ayrışma olabilir, sayaçlar (taklit stop sayısı, hakem `n_stop`) raporlanır. Veri boşluklarında eksik günler atılır, hedef günün son mevcut barına yazılır.
- Slippage fiyat değil komisyon kalemi (2 bps rt; 6 stres); gap stop dolumu açılıştan (KNOWN: hakem testleri). Funding settlement anı, sembol kuralları, mmr kademeleri, likidasyon ücreti UNKNOWN (G2 ile aynı). Hayatta kalma yanlılığı (evren bugünkü majörler) iyimser. Tek rejim, ~4 yıl.
- Gerçek anlamda dokunulmamış veri yok (dev dönemi G2 ve aramada görüldü, BACKTEST §8.5): sonuç "görülmüş veride ön kayıtlı test"tir.
