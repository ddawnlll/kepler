# Ön kayıt: Sinyal teşhisi (9 uzmanın gerçekte ne bildiğini ölçme) — Faz 0–1

**Durum:** ön kayıt; Faz 1'in (gerçek veride herhangi bir IC hesabı) ve ilgili koddan çıkan sonuçların ÖNCESİNDE commit'lenir (2026-10-06, kullanıcı görevi). Ufuk, IC tanımı, bootstrap, çoklu test düzeltmesi, karar ölçütü ve sınıflandırma sonuçtan sonra değişmez. Değişirse eski ve yeni sonuç birlikte raporlanır, neden yazılır (MISSION kural 11).
**Kapsam:** yalnızca TEŞHİS. Ensemble ağırlığı, boyutlama, vol hedefi, parametre araması yok. Faz 2 (nötr bölge/histerezis ve carry yeniden kurulumu) için ayrı ön kayıt dosyaları yazılır (Faz 1 bulgularından sonra, ayrı commit, ayrı koşu); bu dosya onları bağlamaz.
**Etiket:** tüm sonuçlar görülmüş veride (2020-04 → 2026-03) **örneklem içi**; mühürlü dönem (≥ 2026-04-01) yüklenmez (`tape.load` kodla zorlar). Hakem Faz 1'de kullanılmaz.

## Neden (gözlenmiş engel; MISSION kural 4)
Önceki denetim (`reports/audit_fixes.md`): (i) kanıtlanabilir tek fikir momentum; 6 uzman tek başına edge göstermiyor (`reports/edge_experts.md`); (ii) |F| kalibre değil; (iii) ensemble ağırlıkları ensemble PnL'ine bakılarak seçildi, DSR(N = 4 775) ≈ 0; (iv) sabit 9 sembollü evren hayatta kalma yanlılığı taşıyor (dinamik evrende Sharpe 1,86 → 0,82–1,04). Bu iş sırayı düzeltir: önce her uzmanın SİNYAL düzeyindeki bilgisi (IC), sonra ensemble. Hakem/PnL bakmadan, tahmin → ileri getiri.

## 0.1 Uzman kartları (taslak; yalnızca koddan ve belgelerden okunan; hipotez yazılı değilse "yok")
`C` günlük kapanış (ffill), σ = `market_state.sigma` (30 gün, yıllık, alt sınır 0,25), `act` = aktiflik, φ = 7 günlük ortalama funding (yıllık), `dvol`/`tbr` = günlük quote hacmi / taker alış payı. Tüm tahminler [−1, 1], karar günün kapanışında.

| uzman | girdi | kodun gerçekte hesapladığı | belgede hipotez (kaynak) | H |
|---|---|---|---|---|
| `trend` (E1) | C, σ | L ∈ {7,14,28,56}: z_L = ln(C_d/C_{d−L}) / (σ_d/√365 · √L) (L günlük getiri, kendi öngörülen oynaklığı cinsinden); f_L = clip(z_L/2, −1, 1); E1 = ortalama_L f_L. Sembol bazında zaman serisi, kesitsel bileşen yok | **mekanizma cümlesi yok**; yalnızca kaynak atfı: Covel *Trend Following*, Faith *Way of the Turtle*, Antonacci (`ensemble_protocol.md` "Bileşenler kitaplardan"); likit büyük coinlerde momentum (`edge_experts.md` literatür notu, "Up or down?" 2021, betimsel) | 1 |
| `xs_momentum` (E2) | C, act | L ∈ {14,28,56}: aktif semboller arasında ln(C_d/C_{d−L}) kesitsel sırası, q = 2(sıra−1)/(n−1)−1; E2 = ortalama_L q; n < 4 ise 0. Dolar-nötr | **mekanizma cümlesi yok**; yalnızca kaynak/etiket: Antonacci göreli momentum, "Cross-sectional" (`edge_experts_protocol.md` #9) | 1 |
| `carry` (E3) | φ, σ | c = −(φ − 0,1095)/σ; E3 = clip(2c, −1, 1); NaN → 0. Sembol bazında mutlak seviye (kesitsel dönüşüm yok): yüksek funding → short, düşük/negatif → long | forex carry'nin perp karşılığı: funding'i alan tarafı tut (`book_signals.md`: "perp'te faiz = funding"; `g2.md`: yönlü, delta-nötr değil) | 2 |
| `bollinger` (E4) | C | z = (C − SMA₂₀)/std₂₀ (ddof 0); F = clip(−z/2, −1, 1); std = 0 ise 0 | "yatay rejimde fiyat ortalamasına döner … bu bir varsayımdır, kanıt değil" (`bollinger_protocol.md`); karşı taraf/kim öder yazılı değil | 2 |
| `lowvol` (E5) | σ_60 (günlük getiri std), act | −σ_60'ın kesitsel sırası (en düşük oynaklık +1), dolar-nötr; n < 4 ise 0 | yalnızca ad: "düşük oynaklık / betting-against-beta, risk primi vekili" (`edge_experts_protocol.md` #3); mekanizma cümlesi yok | 1 |
| `nearhigh` (E6) | C, act | x = C/max(C, 180 gün) (en az 90 gün); x'in kesitsel sırası (zirveye en yakın +1); n < 4 ise 0 | çıpalama / az-tepki (George–Hwang tipi): zirveye yakın olan devam eder (`edge_experts_protocol.md` #7) | 2 |
| `fundcrowd` (E7) | φ | z = (φ − ort₉₀(φ))/std₉₀(φ); yalnızca \|z\| > 1,5 iken F = −clip(z/3, −1, 1), aksi 0 | aşırı funding = kalabalık pozisyon → tasfiye baskısı, zorunlu akış vekili (`edge_experts_protocol.md` #8) | 2 |
| `volrev` (E8) | dvol, r₁, σ | v = dvol_d / ort(dvol_{d−30..d−1}); yalnızca v > 1,5 iken F = −clip(r₁/(2σ/√365), −1, 1), aksi 0 | yüksek hacimli günde ters tepki = likidite sağlayıcı tazminatı (Campbell–Grossman–Wang; `edge_experts_protocol.md` #5; vekil: taker olarak uygulanır) | 2 |
| `orderflow` (E9) | tbr | imb = 2 tbr − 1; z = (ort₃(imb) − ort₆₀(imb))/std₆₀(imb); F = clip(z/2, −1, 1) | agresif alış akışı = bilgili akış, devam (`edge_experts_protocol.md` #6; vekil, haber/NLP yok) | 2 |

**H sınıfı (bu tabloda sonuçtan önce sabitlendi):** 2 = belgede en az bir mekanizma cümlesi (kim/neden ters tarafı yapıyor ya da hangi davranış/kısıt) yazılı; 1 = yalnızca kaynak/etiket atfı var, mekanizma cümlesi yok; 0 = hiçbiri. Bu sınıflama belge metninden okundu, kendi yorumum değildir; mekanizma cümlesi eksik olan üç uzman (`trend`, `xs_momentum`, `lowvol`) için yazılması kullanıcı kararıdır.
**Ensemble referansı (uzman değil, karar dışı):** `ev1_plus_new` birleşik F (`ensemble.combine`) ayrıca ölçülür, yalnızca karşılaştırma için.

## Evren, dönem, hizalama
- **Birincil evren (dinamik):** `tape.membership` (iki kökün `universe.parquet`'ı; ay M üyeleri = M−1 ayı USDT-M quote hacmi sıralaması, nedensel; delist olanlar dahil; stable/emtia/endeks dışlı; `usable.json` kesimi) **rank ≤ 20**. Kesit yalnızca üyeler: aktiflik = `market_state.active & üyelik` (`scripts/audit_fix.py::stage_surv` ile aynı kural), uzmanlar bu `active` ile koşar (kesitsel uzmanlar yalnızca üyeler arasında sıralar). Tahmin hücresi = (gün d, sembol s), s ayın üyesi ve aktif.
- **Karşılaştırma evreni:** mevcut 9 sembol (BTC ETH SOL XRP BNB DOGE ADA LINK AVAX): yalnızca IC nokta tahmini, p-değeri ve karar YOK.
- **Karar tarihleri:** 2020-04-01 → 2026-03-30 − (1 + h) gün (son çıkış açılışı ≤ 2026-03-31). Isınma: uzmanlar 2020-01'den tam seride hesaplanır.
- **Alt dönemler:** 2020–21 (2020-04-01 → 2021-12-31), 2022–24, 2025+ (→ 2026-03-31); hücre karar tarihine göre atanır.
- **Nedensel hizalama (1.1):** karar günün kapanışında (23:00 barı, kapanış 00:00 UTC); hakem dolumu sonraki barın açılışında. Bu yüzden **giriş fiyatı = d+1 gününün ilk saatlik barının AÇILIŞI**, çıkış fiyatı = d+1+h gününün ilk saatlik barının açılışı: R_h = ln(O_{d+1+h}/O_{d+1}). Karar gününün (d−1 → d) getirisi ileri pencereye GİRMEZ. Eksik açılış barı hücreyi düşürür; sembolün verisi çıkış tarihinden önce bitmişse (delist / kesim) çıkış = sembolün son mevcut barının kapanışı (terminal fiyat; delist edilen sembolleri sessizce atmak hayatta kalma yanlılığı yaratır). Terminal paylı hücre oranı raporlanır ve bu hücreler çıkarılarak duyarlılık tablosu verilir.
- **Funding zaman damgası (1.1):** `with_funding` bar kapanışı T'de ts ≤ T olayını "bilinen" sayar; bu, T = karar anı damgalı funding olayını (00:00:00,00x) de içerir (kayıt: kesinleşmiş oran dönem sonunda belli olur, öngörülen oran önceden görünür). Kontrol: φ'nin ham olaylardan yeniden hesabı ile birebir eşleşmesi; ve **katı sürüm** (ts < T, karar anı damgalı olay hariç) ile carry/fundcrowd IC'sinin karşılaştırması (duyarlılık, karar dışı). Funding ödemesi için pozisyon (t₀, t₁] içindeki olayları öder (hakem: dolum anındaki damgalı olayı yeni pozisyon ÖDEMEZ, çıkış anındaki olayı öder).
- **Rejim (1.7):** `robust.regime(BTC günlük kapanış)`: etiket[d] yalnızca ≤ d−1 kapanışlarına bakar (EMA₂₀₀, 30 gün eğim). Nedensellik testi: seri kesilince ilk d gün etiketi değişmemeli (gerçek BTC verisinde ve sentetik pozitif kontrolde: etiketi bir gün ileri kaydıran bilinçli mutant testi yakalamalı).

## 1.2 Ufuklar, hedef, IC tanımları
- **Ufuklar h ∈ {1, 3, 5, 10, 20, 40} gün.**
- **Hedef (birincil):** oynaklığa normalize ileri fiyat getirisi Y_h = R_h / (σ_d · √(h/365)), σ_d = karar anındaki `market_state.sigma` (ex-ante, alt sınır 0,25). İkincil (betimsel, karar dışı): funding dahil toplam getiri Y^tot_h = (R_h − Σ_{(t₀,t₁]} funding oranları) / (σ_d √(h/365)); long funding öder, short alır.
- **IC-TS (zaman serisi, havuzlanmış):** her sembol için F ve Y_h'nin Spearman korelasyonu (o sembolün tüm karar tarihlerinde, n_s ≥ 250 gün), sembol ağırlıkları n_s ile ağırlıklı ortalama. (Tahmin sırası ve getiri sırası sembol içinde tüm örneklem üzerinden alınır; blok bootstrap bu sıralarla yeniden örnekler: standart sıra-sonra-yeniden-örnekle yaklaşımı.)
- **IC-XS (kesitsel rank):** her karar tarihinde üyeler arasında F ve Y_h'nin Spearman korelasyonu (≥ 8 geçerli hücre ve F sabit değil; aksi gün düşer); IC-XS = tarihler üzerinde ortalama.
- **Güven aralığı ve p:** durağan blok bootstrap (karar tarihleri, ortalama blok uzunluğu L = max(20, 2h) gün, B = 2 000, tohum 0; sembol/hücreler aynı tarih örneğiyle birlikte gelir: kesitsel bağımlılık korunur). SE = bootstrap standart sapması; z = IC/SE; iki yönlü p = 2(1 − Φ(|z|)). %95 yüzdelik AA ham; **düzeltilmiş AA** = ortalama ± z_{1−0,05/(2·108)} · SE (Bonferroni, 108 test).
- **Çoklu test ailesi:** 9 uzman × 6 ufuk × 2 IC türü = **108 iki yönlü test**, her biri sıfır hipotezi IC = 0. Düzeltme: **Holm, FWER = 0,05** (karar için); BH q ≤ 0,05 yalnız bilgi. Ensemble referansı, karşılaştırma evreni, kalibrasyon, alt dönem, koşullu, funding dahil, katı funding, terminal-hariç duyarlılıkları **aile dışı betimsel** ölçümlerdir (p ile iddia kurulmaz).
- **En iyi hücre (uzman başına):** 108'lik ailede o uzmanın IC > 0 olan hücreleri arasında z'si en büyük (IC türü, ufuk). En kötü hücre: z'si en küçük (ters işaret kontrolü).

## 1.3–1.7 Betimsel analizler (aile dışı)
- **1.3 Kalibrasyon:** en iyi hücrenin ufkunda, (a) F'nin beş eşit sayılı kovası (pd.qcut, duplicates="drop"; kütle sıfırda yığıldığında kova sayısı düşer) → kova başına ortalama Y_h (hücre havuzlu) ve Q5−Q1 farkı (blok bootstrap AA); "monoton" = kova ortalamaları kesin artan; (b) |F| beşlikleri → ortalama sign(F)·Y_h (büyüklük kalibrasyonu: büyük |F| gerçekten daha büyük edge mi).
- **1.4 Sönme:** en iyi hücrenin IC'si üç alt dönemde ve yıllık, dönem içi blok bootstrap AA.
- **1.5 Ters işaret:** ailede Holm-düzeltmeli anlamlı NEGATİF hücresi olan uzman için −F: edge'i aynı testtir (IC(−F) = −IC(F)); asıl soru kopyadır. **Kopya:** −F (ve F) ile diğer 8 uzmanın tahmini arasındaki hücre havuzlu Spearman \|ρ\| ≥ 0,5 ise "kopya, yeni edge değil". Bilgi olarak trend'e göre ortogonalleştirilmiş IC (F sırasının trend sırasına regresyon artığının Y_h ile Spearman'ı).
- **1.6 Fazlalık:** 9 uzmanın tahminleri arasında ensemble'ın gördüğü hâliyle (NaN → 0) hücre havuzlu Spearman matrisi (birincil) ve günlük kesitsel Spearman ortalaması (ikincil); hiyerarşik kümeleme: ortalama bağlantı, mesafe 1 − \|ρ\|, **kesim \|ρ\| ≥ 0,5** (mesafe 0,5). Aynı küme = tek fikir.
- **1.7 Koşullu analiz:** en iyi hücrenin IC türü ve ufku ile (a) uzlaşma sayısı = o hücrede aynı işaretli sıfırdan farklı tahmin veren diğer uzman sayısı (8 üzerinden), kovalar {≤ 2, 3–4, ≥ 5}; (b) BTC rejimi {bull, bear, range}. Her kovada IC ve blok bootstrap AA; p ile iddia kurulmaz.

## 1.8 Karar ölçütü (uzman başına, sonuçtan önce sabit)
**IC ölçütü geçer** ⇔ (a) en iyi hücrenin (IC > 0) Holm-düzeltilmiş p ≤ 0,05 (108'lik aile üzerinden) **ve** (b) o hücrenin IC işareti 3 alt dönemin en az 2'sinde pozitif.
- **TUT:** IC ölçütü geçer **ve** H ≥ 1.
- **YENİDEN KUR:** (IC ölçütü geçmez ve H = 2: mekanizma yazılı, mevcut kurulum bilgi taşımıyor) **ya da** (IC ölçütü geçer ve H = 0). Ayrıca Holm-düzeltmeli anlamlı NEGATİF hücresi olup −F kopya DEĞİLSE (\|ρ\| < 0,5 tüm uzmanlarla): YENİDEN KUR ("ters yön yeni ön kayıt adayı", bu rapor onu kullanmaz).
- **AT:** IC ölçütü geçmez ve H ≤ 1 (kaynakta mekanizma yok ve veri de desteklemiyor). Ayrıca anlamlı negatif IC + −F kopya ise AT (hipotez refüte, yeni fikir değil).
- Başka koşul yok; etki büyüklüğü tabanı konmadı (anlamlılık yetmez uyarısı raporda: büyük n ile küçük IC de anlamlı çıkar; IC değeri ve ilgili bps ayrıca yazılır). TUT bir ensemble'a katma önerisi değildir; yalnızca "sinyal düzeyinde bilgi taşıyor ve gerekçesi var".
- **Küme:** bağımsız fikir sayısı = 1.6'daki küme sayısı (ayrıca: en az bir TUT/IC-geçen uzman içeren küme sayısı).

## Kontroller (gerçek veri koşusundan ÖNCE geçmeli; `tests/test_signal_diag.py`)
1. **Pozitif kontrol (sentetik):** gerçek ileri getirinin gürültülü kopyası (Gauss; bilinen korelasyon ρ). IC-TS ve IC-XS, kuramsal Spearman = (6/π)·asin(ρ/2) ile ±0,02 içinde ve p < 0,001 olmalı.
2. **Negatif kontrol:** saf gürültü; 200 bağımsız tekrarda aileden bağımsız ham p < 0,05 oranı [0,02, 0,09] içinde (nominal 0,05; binom aralığı), ve Holm-düzeltmeli hiçbir hücre geçmemeli.
3. **Hizalama kontrolü:** (i) tahmin = sembolün KARAR GÜNÜ getirisi (d−1→d) iken sentetik rastgele yürüyüşte IC ≈ 0 (karar günü getirisi ileri pencereye sızmıyor); (ii) tahmin = bilinçli gelecek (d+1→d+2) iken h = 1'de IC ≈ 1 (pencere gerçekten d+1 açılışından başlıyor); (iii) 1 bar kaydırma mutantı (giriş = d'nin son barı) bu testlerde yakalanır.
4. **Holm / bootstrap birim testleri:** Holm elle hesaplı örnek; bootstrap SE iid veride analitik 1/√n ile ±%15.
5. **Rejim nedenselliği testi** ve **φ yeniden hesabı** (yukarıda). Mimari: `python3 tests/test_architecture.py` yeşil kalmalı.
Bir kontrol koşulamazsa hangisi ve neden raporlanır; gerçek veri koşusu o kontrol geçmeden başlamaz.

## Deneme sayımı (araştırma defteri)
Her istatistiksel test (108 aile testi) ve karar ölçütüne giren her alt dönem işaret kontrolü (9 uzman × 3) bir satırla `reports/signal_diagnostics_data/trials.jsonl`'a (ve Modal Volume'a `/data/signal_diag/ledger_signal_diag.jsonl`) yazılır; satır: trial sırası, zaman, hipotez, config + hash, kod/veri hash'i, sonuç. `ledger/*` ajan tarafından yazılamaz ve `ledger.record` hakem dışı kaynağı reddeder; bu yüzden ayrı dosya, aynı biçim. Betimsel tablolar (kalibrasyon, sönme, koşullu, funding dahil vb.) kaç ölçüm içerdiği kadar ayrıca sayılır ve "betimsel" etiketiyle yazılır (DSR için muhafazakâr toplam: tümü). Önceki toplam N = 4 775 (`reports/audit_fixes.md`); bu iş eklediklerini raporlar. Faz 2 koşuları (hakem) ayrıca kendi ön kaydıyla yazılır.

## Tahmin (koşudan önce; yargı, doğrulanmadı)
- Momentum ailesi (`trend`, `xs_momentum`, `nearhigh`) 10–40 gün ufkunda pozitif ve anlamlı; kendi içlerinde yüksek korelasyonlu (tek küme).
- `carry`: IC ≈ 0 ya da negatif (yüksek funding boğada, boğa devam eder; tersi işaret); toplam getiri (funding dahil) fiyat IC'sinden daha iyi görünür ama yönlü fiyat riski baskın.
- `bollinger`: kısa ufukta negatif; ters işareti trend ile yüksek korelasyonlu (kopya).
- `lowvol`, `fundcrowd`, `volrev`, `orderflow`: Holm eşiğini geçmez; `orderflow` kısa ufukta zayıf pozitif olabilir.
- Bağımsız fikir sayısı 3–5 küme.

## Sınırlar
Her sonuç görülmüş veride örneklem içi; alt dönem 2025+ ona en yakın "ikinci yarı" ama o da görüldü. Uzmanların kendi parametreleri ön kayıtlı sabit (taranmadı). Dinamik evrende çok sayıda küçük/yeni sembol var (196 sembol yüklenir, her ay ~20 üye); tahmin hücreleri korelasyonludur, bu yüzden bootstrap tarihleri yeniden örnekler. p-değerleri normal yaklaşımıdır (B = 2 000 çözünürlük sınırı yoktur). IC, işlem maliyeti ve boyutlamadan bağımsızdır; yüksek IC ≠ kârlı strateji. Funding'in hakem dışı (ağırlıkla bar-yaklaşık) yeniden hesabı, ikincil hedefte kullanılır.

## Bütçe
Kod: `scripts/signal_diag.py` (panel + analiz, Modal), `scripts/signal_diag_stats.py` (saf istatistik), `tests/test_signal_diag.py`. `kepler/` altına modül eklenmez (satır bütçesi). Hakem, denetim, risk, defter, mühür koduna ve mevcut testlere dokunulmaz. Koşu: Modal, birkaç dakika–yarım saat. Aşılırsa dur ve raporla.
