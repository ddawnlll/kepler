# Ön kayıt TASLAĞI 2/4: Asimetrik short (short tarafında daha düşük ağırlık)

**Durum: TASLAK, KOŞULMADI.** Kullanıcı onayı + ayrı commit olmadan kod yazılmaz/koşulmaz (MISSION kural 11); onaylandıktan sonra değişmez.

## Neden (gözlenmiş engel; kural 4) ve DÜRÜSTLÜK NOTU
ev1_plus_new'de long 515 trade net +950,2 USDT, short 514 trade net −159,6 USDT (rapor özeti; bull rejiminde 298 short trade −139,9 USDT). Short funding +41,6 USDT'dir ve **bull rejiminde** alınır (2.6; önceki incelemedeki "ayı rejimi" atfı yanlıştı). Post-hoc, betimsel karşı-olgusallar (rapor Bölüm I.5 → 2.6): long-only Sharpe 2,12 / net 948,9; short ×0,5 Sharpe 2,16 / net 870,1 (tam bileşim: 1,86 / 790,5). **Bu sonuç görüldü**; bu yüzden aynı veride yeniden koşmak kanıt değildir. Ön kayıt, görülmemiş sembol/dönem üzerinde sınamayı zorunlu kılar (aşağıda).
**Hipotez (tek):** "Short hedef notional'larını ×0,5'le ölçeklemek (yalnızca negatif hedefler; tampon, tavanlar ve risk motoru aynı), net Sharpe'ı bağımsız (görülmemiş) evrende artırır." Yüksek tahmin eşiği varyantı **bu taslağın parçası değildir** (ayrı hipotez, ayrı ön kayıt).

## Kural (sabit)
- Bileşim = ev1_plus_new (ağırlıklar değişmez). Risk motoru çıktısı n_i < 0 ise n_i ← 0,5 · n_i (hedefe uygulanır, tampon sonrası değil, tampondan ÖNCE: `portfolio.size` içinde değil kitap çıkışında `target.where(target >= 0, 0.5 * target)`; rapordaki karşı-olgusalla aynı biçim).
- Çarpan 0,5 yuvarlak varsayımdır; başka çarpan (0,25, 0,75…) denenmez.

## Test evreni (görülmemiş veri üzerinde)
1. **K7 sembol kümesi** (14 sembol; `reports/ensemble_protocol.md` K7 kuralı; 2023-07-01 → 2026-04-01; fee 16 + slip 2): ev1_plus_new'in short×0,5'i vs tam bileşim.
2. **Aylık top-20 hacim evreni** (delist dahil; rapor 2.9'daki aynı mekanik; 2020-04 → 2026-03): bu evrende ev1_plus_new daha önce yalnızca tam bileşimle koşuldu (Sharpe 1,04); short×0,5 yeni koşu.
3. İleri veri (kullanıcı H5 canlı/paper): zaman-dışı tek gerçek kanıt; mühür yalnızca ADAY'da.

## Başarı ve red ölçütü (koşudan ÖNCE)
- **BAŞARI**: (1) K7 kümesinde Sharpe(short×0,5) − Sharpe(tam) ≥ +0,10 **ve** (2) top-20 evrende ≥ +0,10 **ve** (3) iki testte de net(short×0,5) > 0 fee 16'da.
- **RED**: iki testten birinde fark < 0 ya da net ≤ 0. Arası = KANITSIZ.
- Başarı, tek başına short ağırlığını değiştirmek için yeterli değildir; ADAY değil. Değişiklik yalnızca ayrı onayla.

## Tahmin (yargı)
Short ayağı bull-ağırlıklı örnekte negatif; K7 ve top-20 evrenleri de 2023–2025 boğa ağırlıklı. Short ×0,5 fark ≥ +0,10 beklenir ama ayı ağırlıklı bir dönemde (örn. 2022) aleyhine olabilir; 2022 ayrıca raporlanır. En olası sonuç: iyimser yön, KANITSIZ.

## Denemeler
N + 2 (iki test evreni; her biri `evaluate_book`/deftere). Karşı-olgusal kontroller deftere girmez.

## Sınırlar
Short taraf kaybı rejim bağımlı (boğa dönemi); asimetri kalıcı bir yapı değil, örneklem özelliği olabilir. MEXC'te short funding işareti/kuralları doğrulanmadı (`account_reality.md`).
