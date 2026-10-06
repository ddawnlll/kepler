# Ön kayıt: Nötr bölge + histerezis (Faz 2.1, `signal_diagnostics` görevi)

**Durum:** ön kayıt; koddan ve koşudan önce commit'lenir (2026-10-06). Kural, eşikler, evren, ölçüt ve karar sonuçtan sonra değişmez (MISSION kural 11). Görülmüş veride (2020-04 → 2026-03) ön kayıtlı test: **örneklem içi**; mühür dokunulmaz.

## Neden (gözlenmiş engel)
Faz 1 (`reports/signal_diagnostics.md`, `reports/signal_diagnostics_data/results.json`): trend/ensemble tahminlerinin küçük |F| bölgesi ve işaret değişimleri yüksek devir ve maliyet üretir; tahmin büyüklüğü kalibre değil (önceki denetim). Hipotez (tek): **|F| küçükken pozisyon açmamak ve yön çevirmeyi yalnızca güçlü karşı tahminde yapmak, maliyet ve gürültü kaynaklı dönüşleri azaltarak net Sharpe'ı artırır.** Bu bir sizing değişikliği DEĞİL: boyutlama (`portfolio.size`, tampon, tavanlar) aynen çalışır; histerezis hedefin üzerinde bir pozisyon-izin maskesidir.

## Kural (tek eşik çifti, sabit)
`F` = `ensemble.combine` çıktısı (ölçekli: ort. |F| ≈ 0,5; `reports/ensemble_protocol.md` §3). Her sembol için durum s ∈ {−1, 0, +1}, ilk durum 0, aktif olmayan gün s = 0:
- s = 0: F ≥ θ_in → +1; F ≤ −θ_in → −1; aksi 0.
- s = +1: F ≤ −θ_in → −1 (yön çevirme); F < θ_out → 0 (çıkış); aksi +1.
- s = −1: F ≥ θ_in → +1; F > −θ_out → 0; aksi −1.
- **θ_out = 0,10 (nötr bölge: |F| < 0,10 iken pozisyon her zaman sıfır), θ_in = 0,25 (giriş ve yön çevirme eşiği).**
Hedef notional: n'_i = n_i (risk motorunun olağan çıktısı) eğer s_i ≠ 0 ve sign(n_i) = s_i; aksi n'_i = 0. Yani s = 0 iken zorunlu flat (tamponu aşar: nötr bölge bir pozisyon kuralıdır), s ≠ 0 iken boyut ve tampon aynen risk motorunundur.
**Eşik gerekçesi (sonuçtan önce, tarama yok):** `combine` ortalama |F|'yi 0,5'e sabitlediği için eşikler bu ölçeğin sabit kesirleridir: θ_out = 0,2 × 0,5 (ortalama inancın beşte biri altı "inançsız"), θ_in = 0,5 × 0,5 (ortalama inancın yarısı: bir pozisyonu açmak ya da çevirmek için en az "yarım ortalama" inanç). İstatistiksel gerekçe: Faz 1'de bile tek tek uzmanların IC'si küçüktür (|IC| ≲ 0,1), yani küçük |F| bölgesi gürültü baskındır; ancak bu kesirler Faz 1 sonuçlarından OPTİMİZE edilmedi, ölçeğin sabit kesirleri olarak seçildi. Başka eşik çifti denenmez; sonuç kötü çıkarsa "eşikler yanlıştı" diye ikinci koşu yapılmaz (yeni ön kayıt + yeni deneme gerekir).

## Koşular (hakem, dinamik evren, tek seferlik; her çift aynı veri/maliyet)
- **Evren:** `tape.membership` rank ≤ 20 (aylık, nedensel, delist dahil; `scripts/signal_diag.py::members`), aktiflik = `market_state.active & üyelik`; yüklenen ~196 sembol, kitap bu paneldedir.
- **Dönem / spec:** 2020-04-01 → 2026-04-01, sermaye 10 000, fee 10 + slip 2 bps RT, kaldıraç 10, mmr 0,005, `gross_cap` 3×, likidasyon açık (`scripts/ensemble.py::spec`). Mühür dokunulmaz.
- **Çekirdek 1 (trend):** bileşim = (trend) ağırlık 1: taban (histerezissiz) vs histerezisli.
- **Çekirdek 2 (mevcut ensemble):** `ev1_plus_new` (`ensemble.PRESETS`; önceki denetimin konusu): taban vs histerezisli.
- Taban koşuları ölçümdür (`run_book`, deftere girmez); histerezisli iki koşu `evaluate.evaluate_book` ile (nedensellik denetimi + defter, `/data/signal_diag/phase2/ledger_phase2_<koşu>.jsonl` (eşzamanlı konteynerler aynı dosyaya yazmasın diye koşu başına)): **N + 2**.

## Ölçüt ve karar (her çekirdek için ayrı; Bonferroni α = 0,05 / 2)
Birincil ölçü: sabit sermaye yıllık Sharpe (`scripts/audit_metrics.sharpe_fixed`), günlük net PnL. ΔSharpe = histerezisli − taban; eşleştirilmiş durağan blok bootstrap (günler, ortalama blok 20, B = 2 000, tohum 0, iki seri aynı tarih örneğiyle).
- **ÇALIŞTI:** ΔSharpe'ın bootstrap %2,5 yüzdeliği > 0 **ve** net PnL(histerezisli) ≥ net PnL(taban).
- **ÇALIŞMADI:** ΔSharpe nokta tahmini ≤ 0 (histerezis net Sharpe'ı artırmadı).
- **KANITSIZ:** diğer durumlar (yön olumlu, ölçüt geçmedi).
Bilgi (karar dışı): Δnet, Δbrüt, Δ(fee + slip), Δdolum sayısı, Δfunding, maks DD, 3 alt dönem ΔSharpe (2020–21 / 2022–24 / 2025+), rejim (bull/bear/range) net, ortalama brüt kullanım. Mekanizma kontrolü: devir azalıyorsa tasarruf **mekanik** olarak maliyet satırında görülür; asıl soru brüt kaybın tasarruftan küçük kalıp kalmadığıdır.

## Tahmin (koşudan önce; yargı)
Dolum sayısı %10–30 azalır; maliyet tasarrufu brütteki kayıptan küçük olabilir. Trend çekirdeğinde ΔSharpe küçük ve bootstrap AA'sı 0'ı içerir (KANITSIZ en olası). Ensemble'da (6 zayıf uzman) nötr bölge gürültüyü daha çok keser: ΔSharpe daha olumlu ama yine KANITSIZ olması muhtemel.

## Sınırlar
Tek eşik çifti ve tek koşu: "histerezis genel olarak işe yarar/yaramaz" iddiası değil, bu eşik çiftinin bu evrendeki sonucudur. İki çekirdek aynı veride ve ilişkili. Baz koşuların sonucu önceki dinamik evren koşusundan (sermaye 1 000, Sharpe 1,04) farklı olabilir (sermaye 10 000; yuvarlama yok).
