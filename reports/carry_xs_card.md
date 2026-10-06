# `carry_xs` başarı kartı (K1–K9): edge var mı?

Ön kayıt: `reports/preregistration/carry_xs_card.md` (koşudan önceki commit `1873adb`). Üreten: `scripts/carryxs_card_report.py` (rakamlar `reports/signal_diagnostics_data/carry_xs_card/`). Dinamik evren (aylık top-20, delist dahil), mevcut hakem, fee 10 + slip 2, sermaye 10 000; **görülmüş veride örneklem içi**; mühür dokunulmadı.

## Karar: **NO_EDGE**

| K | ölçüt | sonuç | geçti |
|---|---|---|---|
| K1 | rotasyon null'u: brüt p ≤ 0,05/3 = 0,0167 ve DSR ≥ 0,95 | gerçek brüt +1707; null ort. +373 ± 890 (%50/%95/%99: +431 / +1726 / +2041); **p = 0.0565** (B = 300, taban 0.0033); DSR = 0.989 | ✗ |
| K2 | Sharpe > benchmark ve NW alfa t ≥ 2 | Sharpe 1.24 vs benchmark (EW üye fiyat getirisi) 0.49; alfa yıllık +0.040, beta -0.002, **t = 3.00** | ✓ |
| K3 | Sharpe ≥ 1,0; net > 0 fee 16 + slip 6'da ve 1 bar gecikmede | Sharpe 1.24; net fee16/slip6 +2050; net gecikme +2298 | ✓ |
| K4 | maks DD ≤ %25; bootstrap DD %95 ≤ %30 | DD %3.8; bootstrap %95 %7.3 | ✓ |
| K5 | komşuların ≥ %70'i net > 0; medyan Sharpe ≥ ana/2 | net > 0 payı 1.00; medyan Sharpe 1.44 (ana 1.24) | ✓ |
| K6 | pencerelerin ≥ %60'ı net > 0; 4 kaydırma net > 0 | yarıyıl net > 0 payı 0.75 (12 pencere); kaydırmalar: +2358, +2344, +2349, +2332 | ✓ |
| K7 | çapraz varlık | koşulamadı (evren dışı sembol kümesi yok) | – |
| K8 | ana Sharpe her ablasyondan büyük | ana 1.24; abl_no_risk 0.58, abl_no_buffer 1.20 | ✓ |
| K9 | ≥ 2 rejimde net ≥ 0 ve tek rejim payı ≤ %80 | bull/bear/range net: +1987 / -11 / +101; en büyük pay %96 | ✗ |

## Ayrıntı

**K5 komşuları:** ×0.8: net +2447, Sharpe 1.28 (carry_days 6); ×0.9: net +2568, Sharpe 1.35 (carry_days 6); ×1.1: net +2874, Sharpe 1.53 (carry_days 8); ×1.2: net +2939, Sharpe 1.58 (carry_days 8).

**K6 yarıyıllar (net):** 2020-07-01_: +289, 2021-01-01_: +826, 2021-07-01_: +69, 2022-01-01_: +153, 2022-07-01_: -152, 2023-01-01_: -22, 2023-07-01_: +80, 2024-01-01_: +414, 2024-07-01_: +536, 2025-01-01_: +47, 2025-07-01_: +302, 2026-01-01_: -241.

**K1 bilgi:** aynı p'nin Faz 1 ailesinin Bonferroni eşiğine (0,05/108 = 0.00046) karşısı B = 300 çözünürlüğüyle ulaşılamaz. Null'ın NET ortalaması +219 (gerçek net +2358).

## Okuma

**Karar mekanik olarak NO_EDGE, ama tablo karışık.** K1 kalıyor: gerçek brüt +1707, rotasyon null'unun %95 dilimine (+1726) neredeyse eşit; p = 0.056 hem ön kayıtlı eşiğin (0,0167) hem de nominal %5'in biraz üstünde (B = 300'de p'nin örnekleme belirsizliği ≈ ±0,013). Null'ın kendisi pozitif ortalama brüt veriyor (+373 ± 890): kesitsel carry yapısı (dolar-nötr, düşük oynaklık) zamanlama olmadan da küçük pozitif getiri taşıyor; gerçek sonucun bunun ÜSTÜNDE olduğuna dair kanıt zayıf. Öte yandan diğer kartlar güçlü: K2 geçti (alfa t = 3.00, beta ≈ -0.002, Sharpe 1.24 vs benchmark 0.49), K3 geçti (fee 16 + slip 6'da bile net +2050, Sharpe 1.07; 1 bar gecikmede net +2298), K4, K5 (komşuların hepsi net > 0, Sharpe 1,3–1,6), K6 ve K8 geçti. K7 koşulamadı; K9 kalıyor (netin ~%84'i bull rejiminde; rejim netlerinin toplamına göre pay %96). **Sonuç:** 'edge kanıtlandı' denemez, 'edge yok' da denemez. Sinyal düzeyinde bilgi (Faz 1) ve maliyetten/gecikmeden bağımsız dayanıklı bir getiri var; ancak ön kayıtlı zamanlama null'u (K1) bunu şanstan ayıramadı ve kazanç tek rejime yaslanıyor. Bu bir NO_EDGE kararının K1 sınırında verildiği ve ZAYIF'a çok yakın bir durumdur; karar kuralı değiştirilmedi.

## Dürüstlük notları

- Tasarım Faz 1 bulgusundan türetildi (örneklem içi); kart bunu telafi etmez. Zaman-dışı kanıt yalnızca G3 (mühür, yalnızca ADAY ve kullanıcı komutuyla) ve canlıdır.
- K2 benchmark'ı gösterge: maliyetsiz, fonlamasız EW fiyat getirisi (hakem al-tut'u artefakt verir). K7 koşulamadı, K9 Faz 2'de görülmüştü: en iyi olası karar ZAYIF idi.
- Kontrol koşuları (null, maliyet, komşu, ablasyon, pencere) deftere girmedi; K1 p-testi 1 satır (`trials_card.jsonl`): N + 1. Önceki toplam N 5 090 → **5 091** (muhafazakâr).
- Funding Binance'ten; MEXC doğrulanmadı. Sermaye 10 000; küçük hesapta lot/min-notional etkisi ölçülmedi (önceki denetim: asgari uygulanabilir sermaye ensemble için $2 500).