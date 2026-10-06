# Ön kayıt: Carry'nin yeniden kurulması (`carry_xs`; Faz 2.2, `signal_diagnostics` görevi)

**Durum:** ön kayıt; koddan ve koşudan önce commit'lenir (2026-10-06). Kural, evren, ölçüt ve karar sonuçtan sonra değişmez (MISSION kural 11). Görülmüş veride ön kayıtlı test: **örneklem içi**; mühür dokunulmaz. Not: `reports/<ad>_protocol.md` yerine kullanıcı görevi gereği `reports/preregistration/` altındadır.

## Teşhis: mevcut `carry` neden başarısız (Faz 1 bulguları; kaynak: `reports/signal_diagnostics_data/results.json`, yuvarlı)
Dinamik evren (aylık top-20, 38 805 hücre), oynaklığa normalize ileri getiri, giriş = ertesi gün açılışı:
1. **İşaret doğru.** Kesitsel rank IC (IC-XS) tüm ufuklarda pozitif: h = 1: +0,022 (z 3,9), h = 5: +0,040 (z 4,0), h = 40: +0,087 (z 4,5); 108'lik Holm ailesinde 6/6 ufuk anlamlı; 3 alt dönemin 3'ünde pozitif (0,057 / 0,104 / 0,087); bull/bear/range'de de pozitif. Yani "yüksek funding'li sembol sonraki haftalarda göreli zayıf, düşük/negatif funding'li göreli güçlü" bilgisi var.
2. **Kullanım şekli yanlış (zaman serisi).** Zaman serisi IC (IC-TS, sembol içi, havuzlanmış) tüm ufuklarda sıfırdan ayırt edilemez (−0,007 … +0,009; |z| ≤ 0,6). Mevcut uzman `F = clip(2·(−(φ − 0,1095)/σ))`: sembolün funding'ini SABİT bir tabana göre ölçer; yani piyasa geneli funding düzeyi (boğada yüksek, ayıda düşük/negatif) F'nin işaretini sürer → boğada yönlü short, ayıda yönlü long: piyasa zamanlaması. Hücre havuzlu kalibrasyon bunu gösterir: F beşliklerine göre ortalama ileri getiri monoton DEĞİL ve uç kovalarda ters (en düşük F kovası +0,10, en yüksek −0,09; en iyi hücre ufkunda), yani havuzlanmış tahmin-getiri ilişkisi zaman serisi bileşenin yön hatasıyla bozuluyor, kesitsel bilgiyi örtüyor.
3. **Ufuk.** IC-XS ufukla artıyor (40 gün en iyi, 1 gün en zayıf); sinyal yavaş, bilgi haftalar sonra fiyatlanıyor: düşük devirli kullanım doğru.
4. **Funding zaman damgası hizası sorun değil.** φ'nin ham olaylardan bağımsız yeniden hesabı gerçek veride 2e−16 içinde eşleşti (80 örnek; kline boşluğundaki tek örnekte mevcut barlarla eşleşme); karar anı damgalı olayı hariç tutan katı sürümle IC-XS farkı ≤ 0,0006 (`funding_strict`). Hizalama sızıntısı ya da gecikmesi başarısızlığı açıklamıyor.
5. **Maliyet/fiyat dengesi.** Funding dahil toplam getiri hedefine IC-XS (h = 40: +0,116) fiyat getirisine IC-XS'ten (0,087) büyük: sinyalin yönündeki taraf funding de kazanıyor; ama yönlü kurulumda fiyat zararı baskın (`reports/g2.md`: carry_funding funding'den kazanır, brüt fiyat zararı null'dan ayırt edilemez).

## Ekonomik mantık (tek cümle) ve yeniden kurulmuş sürüm
Perpetual funding, perp fiyatının spot'a göre primini kapatan taraflar arası transferdir: uzun taraf, kaldıraçlı long talebi arttıkça (perp primi yükseldikçe) kısa tarafa öder. Piyasa geneli funding düzeyi kaldıraç maliyetinin ortak faktörüdür ve yön bilgisi taşımaz (yönlü kullanımı piyasa zamanlamasıdır); **sembolün komşularına göre göreli funding'i ise o sembolün long talebinin kalabalıklığıdır**: kalabalık long tarafı hem funding öder hem tasfiye/geri çekilme riski taşır; karşı taraf bu primi (funding + göreli zayıflık) kazanır. Bu yüzden carry, piyasa yönünden arındırılmış (dolar-nötr, kesitsel) kurulmalıdır.
- **`carry_xs`:** F_i,d = xrank(−φ_i,d) — aktif (üye) semboller arasında 7 günlük ortalama funding'in (yıllık, `market_state.phi`) kesitsel sırası, en DÜŞÜK funding +1, en yüksek −1, q = 2(sıra − 1)/(n − 1) − 1 (ortalama sıra); n < 4 ise 0; φ yok (NaN) ise 0. `kepler/experts/_interface.xrank` ile birebir (xs_momentum/lowvol/nearhigh ile aynı formül). Yeni parametre YOK (7 günlük φ mevcut `Params.carry_days`; sabit taban ve σ ölçeklemesi kaldırıldı). Ufuk/eşik/varyant taraması yapılmaz.
- Uzman yalnızca tahmin verir; boyut `portfolio.size` (aynı), hakem aynı. Uzman `ensemble.REG`'e EKLENMEZ (mevcut `test_ensemble_presets` REG = 9 uzman sabitler; REG'e eklemek ayrı karar); script `Params(names=("carry_xs",), weights=(1.0,))` ile `combine`'a doğrudan verir.

## Koşular (hakem, dinamik evren, tek seferlik)
Evren, dönem, spec: `reports/preregistration/neutral_zone_hysteresis.md` ile aynı (aylık top-20, 2020-04-01 → 2026-04-01, sermaye 10 000, fee 10 + slip 2, kaldıraç 10, mmr 0,005, gross_cap 3×).
- **C1 `carry_xs` tek başına:** `evaluate.evaluate_book` (denetim + defter `/data/signal_diag/ledger_phase2.jsonl`): **N + 1**.
- **C0 mevcut `carry` tek başına** ve **B1 trend tek başına** (baz, ölçüm: `run_book`, deftere girmez; B1 histerezis koşusunun tabanıyla aynı koşudur).

## Ölçüt ve karar
- **S1 (net):** C1 net PnL > 0.
- **S2 (Sharpe):** C1 sabit-sermaye yıllık Sharpe'ının durağan blok bootstrap (günler, ort. blok 20, B = 2 000, tohum 0) %5 yüzdeliği > 0 (tek yönlü α = 0,05).
- **S3 (dönemler):** 3 alt dönemin (2020–21, 2022–24, 2025+) en az 2'sinde net > 0.
- **S4 (çeşitlendirme):** C1 ile B1'in günlük net PnL korelasyonu ≤ 0,30 (M2, `reports/edge_experts_protocol.md` ile aynı eşik). Tahmin düzeyi korelasyonu (hücre havuzlu Spearman ve günlük kesitsel ortalama, trend ile) bilgi olarak.
- **KABUL (ön eleme):** S1–S4 hepsi; **KISMİ:** S1 ve S2 geçer, S3 veya S4 kalır; **RED:** diğer. KABUL bir ADAY değil; K1–K9 kartı (rotasyon null'u, K7 vb.) bu işte KOŞULMAZ ve bu yüzden "edge kanıtlandı" denmez, yalnızca "bir sonraki ön kayıtlı kartı hak eder".
Bilgi (karar dışı): brüt/funding/fee/slip/dolum kalemleri (funding'in ve fiyatın payı), rejim net'leri, C0 ile karşılaştırma, `carry_xs` IC-XS/IC-TS (6 ufuk, nokta tahmin + blok bootstrap SE; p ile iddia kurulmaz), maks DD, ortalama brüt kullanım.

## Tahmin (koşudan önce; yargı)
Faz 1'deki IC-XS (0,02–0,09) günlük karar + tampon ile net pozitif ama küçük bir Sharpe (0,3–0,8) verebilir; maliyet (devir) en büyük risk (kesitsel sıra günlük değişir; tampon devri sınırlar). S4 büyük olasılıkla geçer (carry ile trend tahmin korelasyonu düşük: Faz 1 hücre havuzlu ρ = −0,41 eski carry için, `carry_xs` için ≈ 0'a yakın beklenir). S2 (Sharpe > 0, %95) kıl payı olabilir.

## Sınırlar
Tek tanım, tek koşu; kesitsel carry'nin başka biçimleri (σ ölçekli, ek tabanlı, uzun ufuklu) denenmez. İlk eleme tasarımı Faz 1 bulgularından türetilmiştir (kesitsel IC pozitif, TS yok): bu bir örneklem içi bilgi kullanımıdır; `carry_xs` bu yüzden zaman-dışı kanıt değildir. Funding verisi Binance'tir; MEXC funding'i farklı olabilir (doğrulanmadı).
