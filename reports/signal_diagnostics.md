# Sinyal teşhisi: 9 uzman gerçekte ne biliyor?

Bu dosya `scripts/signal_diag_report.py` ile üretildi (rakamlar `reports/signal_diagnostics_data/*.json`'dan). Ön kayıtlar: `reports/preregistration/signal_diagnostics.md`, `neutral_zone_hysteresis.md`, `carry_rebuild.md` (hepsi ilgili koşudan önceki commit'lerde). Tüm sonuçlar görülmüş veride (2020-04 → 2026-03) **örneklem içi**; mühürlü dönem (≥ 2026-04-01) yüklenmedi; ensemble ağırlığı, sizing, vol hedefi ve parametre araması yapılmadı.

## Özet

- **Sinyal düzeyinde bilgi dar ve çoğunlukla kesitsel.** 108'lik Holm ailesinde 4/9 uzman IC ölçütünü geçti: `carry` (XS h=40, IC +0.087, Holm p 0.0006), `lowvol` (XS h=1, IC +0.048, Holm p 0.0000), `nearhigh` (XS h=5, IC +0.074, Holm p 0.0000), `volrev` (TS h=1, IC +0.035, Holm p 0.0206). Kalan beşinin en iyi hücresi Holm'u geçmedi.
- **TUT etiketlerinin anlamı sınırlı:** `carry` yalnızca KESİTSEL kullanımıyla (IC-XS) geçti; ensemble'daki zaman serisi kullanımında bilgi yok (Faz 2.2). `lowvol` ve `nearhigh` kesitsel IC'leri evren seçim etkisine açık (sınırlar). `volrev` yalnızca h=1 IC-TS'de ve Holm p sınırda; yıllara göre IC sönüyor (kartta).
- **Trend ve kesitsel momentum ön kayıtlı kuralla AT çıktı, ama sınırda:** en iyi hücre `trend` XS h=40 (IC +0.075, ham p 0.0047, Holm p 0.42), `xs_momentum` XS h=5 (IC +0.035, ham p 0.0066, Holm p 0.57); üç alt dönemde de pozitifler. 108 testlik Holm bu büyüklükteki etkiyi yakalayacak güçte değil; kural mekanik uygulandı, ölçüt değiştirilmedi. `trend`'in zaman serisi IC'si tüm ufuklarda sıfırdan ayırt edilemiyor (|IC-TS| ≤ 0.014); momentum bilgisi kesitsel. 9 sembollü evrende trend IC-TS h=20: +0.054, dinamik evrende +0.014: trendin zaman serisi 'edge'inin büyük kısmı hayatta kalan semboller seçiminden geliyordu (nokta tahmin, p yok).
- **Bağımsız fikir sayısı: 7 küme / 9 uzman** (trend ile bollinger ters kopya; xs_momentum + nearhigh tek küme).
- **Faz 2.1 (nötr bölge + histerezis): ÇALIŞMADI** iki çekirdekte de (ΔSharpe trend -0.007, ensemble -0.030); dolum sayısı yalnızca -31 / -69 değişti: bu eşiklerle etki ihmal edilebilir, yönü olumsuz.
- **Faz 2.2 (`carry_xs`): ön elemeyi geçti (KABUL)**: net +2358, Sharpe 1.24 (bootstrap %5 +0.53), trend ile günlük PnL korelasyonu +0.12. Eski carry aynı evrende net -1040, Sharpe -0.17. Netin %84'i bull rejiminde ve mutlak getiri küçük; K1–K9 kartı koşulmadı, 'edge kanıtlandı' denmez.

**Kararlar (ön kayıtlı ölçüt):** TUT: `carry`, `lowvol`, `nearhigh`, `volrev`; YENİDEN KUR: `bollinger`, `fundcrowd`, `orderflow`; AT: `trend`, `xs_momentum`. IC ölçütünü geçen 4/9. Bağımsız fikir (küme) sayısı: **7** (IC ölçütü geçen en az bir uzmanlı küme: 4).

## Karar tablosu

| uzman | H | karar | en iyi hücre | IC [ham %95 AA] | düzeltilmiş AA (108) | z | Holm p | alt dönemde + | negatif anlamlı | max \|ρ\| diğer (≥ 0,5: aynı fikir) | küme |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `trend` | 1 | **AT** | XS h=40 | +0.075 [+0.022, +0.126] | [-0.018, +0.168] | 2.82 | 0.4178 | 3/3 | hayır | bollinger -0.83 (aynı fikir) | 1 |
| `xs_momentum` | 1 | **AT** | XS h=5 | +0.035 [+0.009, +0.060] | [-0.010, +0.079] | 2.72 | 0.5665 | 3/3 | hayır | nearhigh +0.58 (aynı fikir) | 2 |
| `carry` | 2 | **TUT** | XS h=40 | +0.087 [+0.048, +0.124] | [+0.020, +0.154] | 4.53 | 0.0006 | 3/3 | hayır | fundcrowd +0.48 (değil) | 3 |
| `bollinger` | 2 | **YENİDEN KUR** | TS h=1 | +0.019 [-0.003, +0.047] | [-0.026, +0.064] | 1.46 | 1.0000 | 3/3 | hayır | trend -0.83 (aynı fikir) | 1 |
| `lowvol` | 1 | **TUT** | XS h=1 | +0.048 [+0.033, +0.064] | [+0.022, +0.075] | 6.35 | 0.0000 | 3/3 | hayır | nearhigh +0.33 (değil) | 7 |
| `nearhigh` | 2 | **TUT** | XS h=5 | +0.074 [+0.049, +0.100] | [+0.029, +0.120] | 5.77 | 0.0000 | 3/3 | hayır | xs_momentum +0.58 (aynı fikir) | 2 |
| `fundcrowd` | 2 | **YENİDEN KUR** | XS h=5 | +0.006 [-0.017, +0.028] | [-0.035, +0.047] | 0.50 | 1.0000 | 1/3 | hayır | carry +0.48 (değil) | 4 |
| `volrev` | 2 | **TUT** | TS h=1 | +0.035 [+0.017, +0.054] | [+0.002, +0.068] | 3.69 | 0.0206 | 3/3 | hayır | bollinger +0.22 (değil) | 6 |
| `orderflow` | 2 | **YENİDEN KUR** | XS h=20 | +0.010 [-0.020, +0.037] | [-0.041, +0.061] | 0.71 | 1.0000 | 2/3 | hayır | fundcrowd +0.22 (değil) | 5 |

Aile: 9 uzman × 6 ufuk × 2 IC türü = 108 iki yönlü test; Holm FWER 0,05. Düzeltilmiş AA = nokta ± z_(1−0,05/216)·SE (Bonferroni, z = 3.50). p-değerleri durağan blok bootstrap (B = 2000) SE'sinden normal yaklaşım. Hücre sayısı (karar günü × üye sembol): 38805. Oynaklığa normalize ileri getiri, giriş = ertesi gün açılışı.

**Kuralın sertliği (ön kayıt gereği değiştirilmedi):** karar, 108 hücrelik ailenin Holm düzeltmesine dayanır; bu, orta büyüklükte gerçek etkileri de reddedebilen muhafazakâr bir eşiktir (özellikle `trend` ve `xs_momentum`: ham p ≈ 0,005, alt dönemlerin üçünde pozitif). Ham p'ler ve BH q-değerleri kart tablosunda ve `results.json`'da duruyor; ölçütü sonuca göre gevşetmek ön kayıt ihlali olurdu, bu yüzden 'AT' etiketi ölçütün mekanik sonucu olarak kalır ve **kullanıcı kararı gerektirir**. H sınıfı (hipotez) belge metninden okundu: `trend`, `xs_momentum`, `lowvol` için belgede mekanizma cümlesi yok (H = 1), bu yüzden IC ölçütü kalınca YENİDEN KUR yerine AT çıktı.

## IC tabloları (tüm aile)

**IC-TS (zaman serisi, sembol içi, n_s ağırlıklı havuz)**; hücre = IC (z) [Holm-düzeltmeli p ≤ 0,05: ★]

| uzman | h=1 | h=3 | h=5 | h=10 | h=20 | h=40 |
|---|---|---|---|---|---|---|
| `trend` | -0.013 (-1.0) | -0.005 (-0.2) | -0.005 (-0.2) | +0.001 (+0.0) | +0.014 (+0.4) | -0.007 (-0.2) |
| `xs_momentum` | -0.006 (-1.2) | -0.004 (-0.4) | -0.004 (-0.4) | -0.001 (-0.1) | +0.001 (+0.1) | -0.020 (-1.0) |
| `carry` | -0.007 (-0.5) | -0.006 (-0.3) | -0.007 (-0.2) | -0.002 (-0.1) | -0.018 (-0.4) | +0.009 (+0.1) |
| `bollinger` | +0.019 (+1.5) | +0.005 (+0.2) | +0.010 (+0.4) | +0.000 (+0.0) | -0.017 (-0.5) | -0.002 (-0.1) |
| `lowvol` | +0.001 (+0.1) | -0.001 (-0.1) | -0.004 (-0.3) | -0.006 (-0.4) | -0.011 (-0.5) | -0.021 (-0.8) |
| `nearhigh` | -0.004 (-0.7) | +0.001 (+0.1) | +0.003 (+0.2) | +0.007 (+0.5) | +0.006 (+0.3) | -0.005 (-0.2) |
| `fundcrowd` | -0.013 (-1.3) | -0.018 (-1.2) | -0.019 (-1.0) | -0.018 (-0.8) | -0.038 (-1.5) | -0.009 (-0.3) |
| `volrev` | +0.035 (+3.7)★ | +0.015 (+1.7) | +0.006 (+0.6) | -0.009 (-1.0) | -0.011 (-1.2) | -0.010 (-1.1) |
| `orderflow` | -0.007 (-0.7) | +0.004 (+0.3) | +0.011 (+0.6) | -0.008 (-0.4) | -0.013 (-0.5) | +0.015 (+0.6) |

**IC-XS (kesitsel rank, tarih başına)**; hücre = IC (z) [Holm-düzeltmeli p ≤ 0,05: ★]

| uzman | h=1 | h=3 | h=5 | h=10 | h=20 | h=40 |
|---|---|---|---|---|---|---|
| `trend` | +0.004 (+0.6) | +0.019 (+1.8) | +0.029 (+2.2) | +0.046 (+2.6) | +0.062 (+2.8) | +0.075 (+2.8) |
| `xs_momentum` | +0.008 (+1.3) | +0.025 (+2.5) | +0.035 (+2.7) | +0.046 (+2.7) | +0.056 (+2.5) | +0.065 (+2.5) |
| `carry` | +0.022 (+3.9)★ | +0.036 (+4.4)★ | +0.040 (+4.0)★ | +0.049 (+3.6)★ | +0.073 (+4.3)★ | +0.087 (+4.5)★ |
| `bollinger` | +0.006 (+0.9) | -0.011 (-1.0) | -0.019 (-1.6) | -0.028 (-1.9) | -0.055 (-2.8) | -0.056 (-2.6) |
| `lowvol` | +0.048 (+6.4)★ | +0.067 (+5.2)★ | +0.078 (+4.8)★ | +0.099 (+4.4)★ | +0.130 (+4.1)★ | +0.158 (+3.7)★ |
| `nearhigh` | +0.031 (+5.0)★ | +0.057 (+5.7)★ | +0.074 (+5.8)★ | +0.093 (+5.4)★ | +0.116 (+4.9)★ | +0.147 (+4.3)★ |
| `fundcrowd` | -0.000 (-0.0) | +0.001 (+0.1) | +0.006 (+0.5) | -0.005 (-0.4) | -0.018 (-1.1) | -0.014 (-0.7) |
| `volrev` | +0.019 (+2.6) | +0.014 (+1.8) | +0.009 (+1.2) | -0.005 (-0.7) | -0.005 (-0.6) | -0.000 (-0.0) |
| `orderflow` | -0.010 (-1.5) | +0.004 (+0.4) | +0.006 (+0.6) | +0.007 (+0.6) | +0.010 (+0.7) | +0.008 (+0.5) |

## Uzman kartları

### `trend`: **AT**

- **Hipotez (H = 1):** mekanizma cümlesi YOK; kaynak atfı: Covel, Faith, Antonacci; likit coinlerde momentum (betimsel literatür).
- **Ateşleme / büyüklük:** hücrelerin %100.0'inde F ≠ 0; ort. |F| = 0.305; 38805 hücre.
- **En iyi hücre:** XS, h = 40 gün: IC = +0.0751 (SE 0.0266, z +2.82); ham %95 AA [+0.022, +0.126]; düzeltilmiş (108 test) AA [-0.018, +0.168]; ham p = 0.0047, **Holm p = 0.4178**, BH q = 0.0244. Ham (oynaklık normalizasyonsuz) getiri hedefiyle aynı hücrenin IC'si: +0.0643 (normalize: +0.0751).
- **En kötü hücre:** TS, h = 1: IC = -0.0127 (z -1.02, Holm p = 1.000).
- **Kalibrasyon (en iyi ufuk, hücre havuzlu):** F beşliklerine göre ort. Y = [-0.133, -0.073, -0.039, -0.046, +0.082]; Q5−Q1 = +0.215 [-0.106, +0.498]; monoton: hayır. |F| beşliklerine göre ort. işaret-ayarlı Y = [+0.006, -0.019, +0.060, +0.056, +0.143] (büyüklük kalibrasyonu: monoton değil).
- **Sönme:** alt dönemler 2020–21 / 2022–24 / 2025+ IC = +0.118 / +0.053 / +0.069; yıllık: 2020: +0.198, 2021: +0.061, 2022: -0.078, 2023: +0.072, 2024: +0.164, 2025: +0.112, 2026: -0.252.
- **Koşullu:** rejim IC bull / bear / range = +0.148 / -0.098 / +0.036 (gün: 1230 / 615 / 206); uzlaşma ≤2 / 3–4 / ≥5 = +0.014 / +0.048 / +0.178 (hücre: 15810 / 18296 / 3850).
- **Duyarlılıklar (betimsel):** funding dahil toplam getiri hedefiyle IC = +0.0834; terminal-fiyatlı hücreler hariç IC = +0.0739 (terminal pay %0.44).
- **Fazlalık:** tahmin korelasyonu en yüksek olduğu uzman `bollinger` (ρ = -0.83); küme 1.

### `xs_momentum`: **AT**

- **Hipotez (H = 1):** mekanizma cümlesi YOK; kaynak/etiket: Antonacci göreli momentum.
- **Ateşleme / büyüklük:** hücrelerin %99.2'inde F ≠ 0; ort. |F| = 0.409; 38805 hücre.
- **En iyi hücre:** XS, h = 5 gün: IC = +0.0347 (SE 0.0128, z +2.72); ham %95 AA [+0.009, +0.060]; düzeltilmiş (108 test) AA [-0.010, +0.079]; ham p = 0.0066, **Holm p = 0.5665**, BH q = 0.0309. Ham (oynaklık normalizasyonsuz) getiri hedefiyle aynı hücrenin IC'si: +0.0223 (normalize: +0.0347).
- **En kötü hücre:** TS, h = 1: IC = -0.0057 (z -1.17, Holm p = 1.000).
- **Kalibrasyon (en iyi ufuk, hücre havuzlu):** F beşliklerine göre ort. Y = [-0.022, -0.024, -0.000, +0.017, +0.042]; Q5−Q1 = +0.065 [+0.005, +0.127]; monoton: hayır. |F| beşliklerine göre ort. işaret-ayarlı Y = [-0.014, +0.023, +0.008, +0.004, +0.068] (büyüklük kalibrasyonu: monoton değil).
- **Sönme:** alt dönemler 2020–21 / 2022–24 / 2025+ IC = +0.055 / +0.024 / +0.032; yıllık: 2020: +0.145, 2021: -0.010, 2022: +0.037, 2023: +0.001, 2024: +0.034, 2025: +0.062, 2026: -0.097.
- **Koşullu:** rejim IC bull / bear / range = +0.051 / +0.013 / -0.043 (gün: 1230 / 615 / 206); uzlaşma ≤2 / 3–4 / ≥5 = +0.012 / +0.042 / +0.050 (hücre: 9114 / 22434 / 6806).
- **Duyarlılıklar (betimsel):** funding dahil toplam getiri hedefiyle IC = +0.0408; terminal-fiyatlı hücreler hariç IC = +0.0343 (terminal pay %0.08).
- **Fazlalık:** tahmin korelasyonu en yüksek olduğu uzman `nearhigh` (ρ = +0.58); küme 2.

### `carry`: **TUT**

- **Hipotez (H = 2):** forex carry'nin perp karşılığı: funding alan tarafı tut (`book_signals.md`).
- **Ateşleme / büyüklük:** hücrelerin %94.9'inde F ≠ 0; ort. |F| = 0.294; 38805 hücre.
- **En iyi hücre:** XS, h = 40 gün: IC = +0.0869 (SE 0.0192, z +4.53); ham %95 AA [+0.048, +0.124]; düzeltilmiş (108 test) AA [+0.020, +0.154]; ham p = 0.0000, **Holm p = 0.0006**, BH q = 0.0001. Ham (oynaklık normalizasyonsuz) getiri hedefiyle aynı hücrenin IC'si: +0.0861 (normalize: +0.0869).
- **En kötü hücre:** TS, h = 1: IC = -0.0069 (z -0.55, Holm p = 1.000).
- **Kalibrasyon (en iyi ufuk, hücre havuzlu):** F beşliklerine göre ort. Y = [+0.102, +0.064, -0.174, -0.108, -0.094]; Q5−Q1 = -0.196 [-0.741, +0.348]; monoton: hayır. |F| beşliklerine göre ort. işaret-ayarlı Y = [-0.124, -0.161, -0.120, -0.198, +0.016] (büyüklük kalibrasyonu: monoton değil).
- **Sönme:** alt dönemler 2020–21 / 2022–24 / 2025+ IC = +0.057 / +0.104 / +0.087; yıllık: 2020: +0.013, 2021: +0.089, 2022: +0.068, 2023: +0.060, 2024: +0.184, 2025: +0.107, 2026: -0.064.
- **Koşullu:** rejim IC bull / bear / range = +0.107 / +0.058 / +0.078 (gün: 1230 / 615 / 206); uzlaşma ≤2 / 3–4 / ≥5 = +0.008 / +0.065 / +0.124 (hücre: 10833 / 18220 / 6934).
- **Duyarlılıklar (betimsel):** funding dahil toplam getiri hedefiyle IC = +0.1156; terminal-fiyatlı hücreler hariç IC = +0.0898 (terminal pay %0.44).
- **Fazlalık:** tahmin korelasyonu en yüksek olduğu uzman `fundcrowd` (ρ = +0.48); küme 3.

### `bollinger`: **YENİDEN KUR**

- **Hipotez (H = 2):** yatay rejimde fiyat ortalamasına döner; belgede 'varsayım, kanıt değil'; kim ödüyor yazılı değil.
- **Ateşleme / büyüklük:** hücrelerin %100.0'inde F ≠ 0; ort. |F| = 0.530; 38805 hücre.
- **En iyi hücre:** TS, h = 1 gün: IC = +0.0187 (SE 0.0129, z +1.46); ham %95 AA [-0.003, +0.047]; düzeltilmiş (108 test) AA [-0.026, +0.064]; ham p = 0.1455, **Holm p = 1.0000**, BH q = 0.4030. Ham (oynaklık normalizasyonsuz) getiri hedefiyle aynı hücrenin IC'si: +0.0222 (normalize: +0.0187).
- **En kötü hücre:** XS, h = 20: IC = -0.0546 (z -2.84, Holm p = 0.397).
- **Kalibrasyon (en iyi ufuk, hücre havuzlu):** F beşliklerine göre ort. Y = [+0.069, -0.002, -0.026, -0.020, -0.013]; Q5−Q1 = -0.083 [-0.160, +0.002]; monoton: hayır. |F| beşliklerine göre ort. işaret-ayarlı Y = [+0.001, -0.023, -0.009, -0.049, -0.034] (büyüklük kalibrasyonu: monoton değil).
- **Sönme:** alt dönemler 2020–21 / 2022–24 / 2025+ IC = +0.038 / +0.026 / +0.050; yıllık: 2020: +0.077, 2021: +0.016, 2022: +0.046, 2023: +0.034, 2024: +0.030, 2025: +0.052, 2026: +0.062.
- **Koşullu:** rejim IC bull / bear / range = +0.025 / +0.022 / +0.111 (gün: 1230 / 615 / 206); uzlaşma ≤2 / 3–4 / ≥5 = +0.028 / +0.009 / +0.058 (hücre: 18444 / 15555 / 4753).
- **Duyarlılıklar (betimsel):** funding dahil toplam getiri hedefiyle IC = +0.0236; terminal-fiyatlı hücreler hariç IC = +0.0187 (terminal pay %0.02).
- **Fazlalık:** tahmin korelasyonu en yüksek olduğu uzman `trend` (ρ = -0.83); küme 1.

### `lowvol`: **TUT**

- **Hipotez (H = 1):** yalnızca ad: düşük oynaklık / betting-against-beta (mekanizma cümlesi YOK).
- **Ateşleme / büyüklük:** hücrelerin %97.7'inde F ≠ 0; ort. |F| = 0.529; 38805 hücre.
- **En iyi hücre:** XS, h = 1 gün: IC = +0.0484 (SE 0.0076, z +6.35); ham %95 AA [+0.033, +0.064]; düzeltilmiş (108 test) AA [+0.022, +0.075]; ham p = 0.0000, **Holm p = 0.0000**, BH q = 0.0000. Ham (oynaklık normalizasyonsuz) getiri hedefiyle aynı hücrenin IC'si: +0.1040 (normalize: +0.0484).
- **En kötü hücre:** TS, h = 40: IC = -0.0206 (z -0.77, Holm p = 1.000).
- **Kalibrasyon (en iyi ufuk, hücre havuzlu):** F beşliklerine göre ort. Y = [-0.028, -0.007, -0.014, +0.018, +0.041]; Q5−Q1 = +0.070 [+0.031, +0.106]; monoton: hayır. |F| beşliklerine göre ort. işaret-ayarlı Y = [+0.009, +0.017, +0.014, +0.030, +0.037] (büyüklük kalibrasyonu: monoton değil).
- **Sönme:** alt dönemler 2020–21 / 2022–24 / 2025+ IC = +0.050 / +0.054 / +0.034; yıllık: 2020: +0.069, 2021: +0.036, 2022: +0.059, 2023: +0.046, 2024: +0.056, 2025: +0.046, 2026: -0.017.
- **Koşullu:** rejim IC bull / bear / range = +0.055 / +0.050 / +0.033 (gün: 1230 / 615 / 206); uzlaşma ≤2 / 3–4 / ≥5 = +0.029 / +0.052 / +0.042 (hücre: 11346 / 20324 / 6190).
- **Duyarlılıklar (betimsel):** funding dahil toplam getiri hedefiyle IC = +0.0444; terminal-fiyatlı hücreler hariç IC = +0.0484 (terminal pay %0.02).
- **Fazlalık:** tahmin korelasyonu en yüksek olduğu uzman `nearhigh` (ρ = +0.33); küme 7.

### `nearhigh`: **TUT**

- **Hipotez (H = 2):** çıpalama / az-tepki: zirveye yakın olan devam eder.
- **Ateşleme / büyüklük:** hücrelerin %97.7'inde F ≠ 0; ort. |F| = 0.529; 38805 hücre.
- **En iyi hücre:** XS, h = 5 gün: IC = +0.0744 (SE 0.0129, z +5.77); ham %95 AA [+0.049, +0.100]; düzeltilmiş (108 test) AA [+0.029, +0.120]; ham p = 0.0000, **Holm p = 0.0000**, BH q = 0.0000. Ham (oynaklık normalizasyonsuz) getiri hedefiyle aynı hücrenin IC'si: +0.0935 (normalize: +0.0744).
- **En kötü hücre:** TS, h = 1: IC = -0.0038 (z -0.66, Holm p = 1.000).
- **Kalibrasyon (en iyi ufuk, hücre havuzlu):** F beşliklerine göre ort. Y = [-0.046, -0.031, -0.018, +0.054, +0.057]; Q5−Q1 = +0.103 [+0.030, +0.168]; monoton: evet. |F| beşliklerine göre ort. işaret-ayarlı Y = [+0.003, +0.022, +0.066, +0.065, +0.034] (büyüklük kalibrasyonu: monoton değil).
- **Sönme:** alt dönemler 2020–21 / 2022–24 / 2025+ IC = +0.080 / +0.063 / +0.093; yıllık: 2020: +0.165, 2021: +0.020, 2022: +0.037, 2023: +0.070, 2024: +0.082, 2025: +0.109, 2026: +0.026.
- **Koşullu:** rejim IC bull / bear / range = +0.104 / +0.032 / -0.005 (gün: 1230 / 615 / 206); uzlaşma ≤2 / 3–4 / ≥5 = -0.001 / +0.068 / +0.061 (hücre: 7372 / 23315 / 7074).
- **Duyarlılıklar (betimsel):** funding dahil toplam getiri hedefiyle IC = +0.0754; terminal-fiyatlı hücreler hariç IC = +0.0743 (terminal pay %0.08).
- **Fazlalık:** tahmin korelasyonu en yüksek olduğu uzman `xs_momentum` (ρ = +0.58); küme 2.

### `fundcrowd`: **YENİDEN KUR**

- **Hipotez (H = 2):** aşırı funding = kalabalık pozisyon → tasfiye baskısı.
- **Ateşleme / büyüklük:** hücrelerin %16.2'inde F ≠ 0; ort. |F| = 0.119; 38805 hücre.
- **En iyi hücre:** XS, h = 5 gün: IC = +0.0059 (SE 0.0118, z +0.50); ham %95 AA [-0.017, +0.028]; düzeltilmiş (108 test) AA [-0.035, +0.047]; ham p = 0.6158, **Holm p = 1.0000**, BH q = 0.9398. Ham (oynaklık normalizasyonsuz) getiri hedefiyle aynı hücrenin IC'si: -0.0007 (normalize: +0.0059).
- **En kötü hücre:** TS, h = 20: IC = -0.0382 (z -1.50, Holm p = 1.000).
- **Kalibrasyon (en iyi ufuk, hücre havuzlu):** F beşliklerine göre ort. Y = [+0.001, +0.027]; Q5−Q1 = +0.026 [-0.078, +0.134]; monoton: evet. |F| beşliklerine göre ort. işaret-ayarlı Y = [-0.089, -0.032, -0.049, -0.141, -0.142] (büyüklük kalibrasyonu: monoton değil).
- **Sönme:** alt dönemler 2020–21 / 2022–24 / 2025+ IC = -0.003 / -0.003 / +0.038; yıllık: 2020: +0.006, 2021: -0.011, 2022: -0.054, 2023: +0.035, 2024: +0.012, 2025: +0.036, 2026: +0.043.
- **Koşullu:** rejim IC bull / bear / range = +0.015 / -0.022 / +0.011 (gün: 1230 / 615 / 206); uzlaşma ≤2 / 3–4 / ≥5 = -0.267 / +0.034 / +0.075 (hücre: 521 / 3184 / 2558).
- **Duyarlılıklar (betimsel):** funding dahil toplam getiri hedefiyle IC = +0.0162; terminal-fiyatlı hücreler hariç IC = +0.0067 (terminal pay %0.08).
- **Fazlalık:** tahmin korelasyonu en yüksek olduğu uzman `carry` (ρ = +0.48); küme 4.

### `volrev`: **TUT**

- **Hipotez (H = 2):** yüksek hacimli günde ters tepki = likidite sağlayıcı tazminatı.
- **Ateşleme / büyüklük:** hücrelerin %13.5'inde F ≠ 0; ort. |F| = 0.078; 38805 hücre.
- **En iyi hücre:** TS, h = 1 gün: IC = +0.0351 (SE 0.0095, z +3.69); ham %95 AA [+0.017, +0.054]; düzeltilmiş (108 test) AA [+0.002, +0.068]; ham p = 0.0002, **Holm p = 0.0206**, BH q = 0.0014. Ham (oynaklık normalizasyonsuz) getiri hedefiyle aynı hücrenin IC'si: +0.0363 (normalize: +0.0351).
- **En kötü hücre:** TS, h = 20: IC = -0.0113 (z -1.24, Holm p = 1.000).
- **Kalibrasyon (en iyi ufuk, hücre havuzlu):** F beşliklerine göre ort. Y = [-0.004, +0.087]; Q5−Q1 = +0.091 [-0.021, +0.191]; monoton: evet. |F| beşliklerine göre ort. işaret-ayarlı Y = [+0.015, +0.036, +0.027, -0.008] (büyüklük kalibrasyonu: monoton değil).
- **Sönme:** alt dönemler 2020–21 / 2022–24 / 2025+ IC = +0.049 / +0.032 / +0.007; yıllık: 2020: +0.074, 2021: +0.038, 2022: +0.053, 2023: +0.043, 2024: +0.015, 2025: +0.012, 2026: -0.027.
- **Koşullu:** rejim IC bull / bear / range = +0.016 / +0.032 / +0.122 (gün: 1230 / 615 / 206); uzlaşma ≤2 / 3–4 / ≥5 = +0.040 / +0.074 / +0.041 (hücre: 1494 / 2494 / 1242).
- **Duyarlılıklar (betimsel):** funding dahil toplam getiri hedefiyle IC = +0.0365; terminal-fiyatlı hücreler hariç IC = +0.0351 (terminal pay %0.02).
- **Fazlalık:** tahmin korelasyonu en yüksek olduğu uzman `bollinger` (ρ = +0.22); küme 6.

### `orderflow`: **YENİDEN KUR**

- **Hipotez (H = 2):** agresif alış akışı = bilgili akış, devam (vekil).
- **Ateşleme / büyüklük:** hücrelerin %99.9'inde F ≠ 0; ort. |F| = 0.285; 38805 hücre.
- **En iyi hücre:** XS, h = 20 gün: IC = +0.0103 (SE 0.0145, z +0.71); ham %95 AA [-0.020, +0.037]; düzeltilmiş (108 test) AA [-0.041, +0.061]; ham p = 0.4782, **Holm p = 1.0000**, BH q = 0.9060. Ham (oynaklık normalizasyonsuz) getiri hedefiyle aynı hücrenin IC'si: +0.0299 (normalize: +0.0103).
- **En kötü hücre:** XS, h = 1: IC = -0.0103 (z -1.51, Holm p = 1.000).
- **Kalibrasyon (en iyi ufuk, hücre havuzlu):** F beşliklerine göre ort. Y = [-0.018, +0.010, -0.006, -0.010, -0.022]; Q5−Q1 = -0.005 [-0.148, +0.155]; monoton: hayır. |F| beşliklerine göre ort. işaret-ayarlı Y = [-0.013, -0.018, -0.015, -0.023, +0.017] (büyüklük kalibrasyonu: monoton değil).
- **Sönme:** alt dönemler 2020–21 / 2022–24 / 2025+ IC = +0.046 / +0.003 / -0.022; yıllık: 2020: +0.093, 2021: +0.011, 2022: +0.033, 2023: -0.043, 2024: +0.018, 2025: -0.019, 2026: -0.041.
- **Koşullu:** rejim IC bull / bear / range = +0.009 / +0.013 / -0.042 (gün: 1230 / 615 / 206); uzlaşma ≤2 / 3–4 / ≥5 = -0.065 / +0.012 / +0.016 (hücre: 11774 / 19881 / 6655).
- **Duyarlılıklar (betimsel):** funding dahil toplam getiri hedefiyle IC = +0.0128; terminal-fiyatlı hücreler hariç IC = +0.0109 (terminal pay %0.31).
- **Fazlalık:** tahmin korelasyonu en yüksek olduğu uzman `fundcrowd` (ρ = +0.22); küme 5.

## Fazlalık: tahmin korelasyonları ve kümeler

Hücre havuzlu Spearman (ensemble'ın gördüğü hâl, NaN → 0; birincil):

| | `trend` | `xs_momentum` | `carry` | `bollinger` | `lowvol` | `nearhigh` | `fundcrowd` | `volrev` | `orderflow` |
|---|---|---|---|---|---|---|---|---|---|
| `trend` | +1.00 | +0.50 | -0.41 | -0.83 | -0.03 | +0.33 | -0.35 | -0.17 | -0.08 |
| `xs_momentum` | +0.50 | +1.00 | +0.05 | -0.36 | -0.02 | +0.58 | +0.01 | -0.08 | +0.11 |
| `carry` | -0.41 | +0.05 | +1.00 | +0.26 | +0.10 | +0.10 | +0.48 | +0.02 | +0.20 |
| `bollinger` | -0.83 | -0.36 | +0.26 | +1.00 | -0.05 | -0.24 | +0.27 | +0.22 | -0.08 |
| `lowvol` | -0.03 | -0.02 | +0.10 | -0.05 | +1.00 | +0.33 | -0.04 | +0.01 | +0.08 |
| `nearhigh` | +0.33 | +0.58 | +0.10 | -0.24 | +0.33 | +1.00 | +0.01 | -0.06 | +0.09 |
| `fundcrowd` | -0.35 | +0.01 | +0.48 | +0.27 | -0.04 | +0.01 | +1.00 | +0.03 | +0.22 |
| `volrev` | -0.17 | -0.08 | +0.02 | +0.22 | +0.01 | -0.06 | +0.03 | +1.00 | -0.09 |
| `orderflow` | -0.08 | +0.11 | +0.20 | -0.08 | +0.08 | +0.09 | +0.22 | -0.09 | +1.00 |

Günlük kesitsel Spearman ortalaması (ikincil):

| | `trend` | `xs_momentum` | `carry` | `bollinger` | `lowvol` | `nearhigh` | `fundcrowd` | `volrev` | `orderflow` |
|---|---|---|---|---|---|---|---|---|---|
| `trend` | +1.00 | +0.84 | +0.07 | -0.71 | -0.02 | +0.55 | -0.01 | -0.17 | +0.19 |
| `xs_momentum` | +0.84 | +1.00 | +0.12 | -0.57 | -0.00 | +0.57 | +0.02 | -0.12 | +0.12 |
| `carry` | +0.07 | +0.12 | +1.00 | -0.00 | +0.15 | +0.17 | +0.35 | -0.01 | +0.07 |
| `bollinger` | -0.71 | -0.57 | -0.00 | +1.00 | -0.07 | -0.37 | +0.04 | +0.20 | -0.34 |
| `lowvol` | -0.02 | -0.00 | +0.15 | -0.07 | +1.00 | +0.34 | -0.06 | +0.02 | +0.10 |
| `nearhigh` | +0.55 | +0.57 | +0.17 | -0.37 | +0.34 | +1.00 | +0.03 | -0.09 | +0.10 |
| `fundcrowd` | -0.01 | +0.02 | +0.35 | +0.04 | -0.06 | +0.03 | +1.00 | -0.01 | +0.04 |
| `volrev` | -0.17 | -0.12 | -0.01 | +0.20 | +0.02 | -0.09 | -0.01 | +1.00 | -0.11 |
| `orderflow` | +0.19 | +0.12 | +0.07 | -0.34 | +0.10 | +0.10 | +0.04 | -0.11 | +1.00 |

Kümeleme (ortalama bağlantı, mesafe 1 − |ρ|, kesim |ρ| ≥ 0,5):

- Küme 1: `trend`, `bollinger`
- Küme 2: `xs_momentum`, `nearhigh`
- Küme 3: `carry`
- Küme 4: `fundcrowd`
- Küme 5: `orderflow`
- Küme 6: `volrev`
- Küme 7: `lowvol`

Okuma: `trend` ile `bollinger` birbirinin ters kopyası (ρ ≈ −0,83): Bollinger'in ters yönü yeni bir fikir değil trend'in tekrarıdır (ön kayıt 1.5 kuralı). `xs_momentum` ile `nearhigh` aynı ailenin iki biçimi. `carry` ile `fundcrowd` eşiğin (0,5) hemen altında: ayrı küme sayıldı ama funding bilgisi paylaşıyorlar. `lowvol`, `volrev`, `orderflow` birbirinden ve diğerlerinden bağımsız. Sonuç: ensemble'daki 9 uzman ≈ 7 'fikir'; bunlardan yalnızca birkaçı sinyal düzeyinde kanıt taşıyor.

## Ensemble referansı ve karşılaştırma evreni (karar dışı)

`ev1_plus_new` birleşik F'nin IC'si (dinamik evren): TS h=5: -0.013 (z -0.8); TS h=40: -0.020 (z -0.8); XS h=5: +0.064 (z +4.8); XS h=40: +0.129 (z +4.1).

Karşılaştırma evreni (mevcut 9 sembol; yalnızca nokta IC, p/AA yok) ile dinamik evren, h = 20 gün:

| uzman | IC-TS dinamik | IC-TS 9-sembol | IC-XS dinamik | IC-XS 9-sembol |
|---|---|---|---|---|
| `trend` | +0.014 | +0.054 | +0.062 | +0.046 |
| `xs_momentum` | +0.001 | +0.016 | +0.056 | +0.041 |
| `carry` | -0.018 | -0.032 | +0.073 | +0.099 |
| `bollinger` | -0.017 | -0.059 | -0.055 | -0.044 |
| `lowvol` | -0.011 | -0.031 | +0.130 | +0.072 |
| `nearhigh` | +0.006 | +0.024 | +0.116 | +0.117 |
| `fundcrowd` | -0.038 | -0.047 | -0.018 | +0.038 |
| `volrev` | -0.011 | -0.025 | -0.005 | -0.012 |
| `orderflow` | -0.013 | -0.014 | +0.010 | +0.024 |

Okuma: mevcut 9 sembollü evrende `trend` IC-TS h=20 = +0.054 iken dinamik evrende +0.014; `carry` IC-XS 9 sembolde +0.099, dinamik evrende +0.073. Kesitsel bilgi iki evrende de var; zaman serisi trend bilgisi dar evrende görünür, geniş ve hayatta kalma yanlılığından arınmış evrende görünmez. Ham getiri hedefiyle IC (oynaklık normalizasyonu olmadan): `checks.json` → `raw_target`; özellikle `lowvol` için ham hedef IC'si normalize olandan belirgin büyük (düşük oynaklık sembollerin göreli getirisi + normalizasyon etkisi).

## Faz 1 doğrulama kontrolleri

- φ'nin ham funding olaylarından bağımsız yeniden hesabı (gerçek veri, 80 örnek): en büyük mutlak fark 2.2e-16 (1 örnekte kline boşluğu; rolling ortalama mevcut barlarla eşleşiyor).
- Rejim etiketi kesilmiş seride değişmedi: uyuşmazlık 0 / 5 kesim (BTC gerçek verisi).
- Birim/sentetik kontroller (`tests/test_signal_diag.py`, 13 test, Modal'de geçti): pozitif kontrol (ρ = 0,3 → Spearman 0,2875 ± 0,02), negatif kontrol (200 tekrar ham p < 0,05 oranı [0,02; 0,09], Holm yanlış keşif ≤ %10), hizalama (karar günü getirisi sızmıyor, giriş = ertesi gün açılışı, terminal fiyat, funding penceresi), Holm/BH elle, rejim nedenselliği + mutant, φ yeniden hesabı, uçtan uca sentetik.
- Katı funding sürümü (karar anı damgalı olay hariç): carry/fundcrowd IC farkı (en büyük mutlak) 0.0022 (`funding_strict`).

## Faz 2: ön kayıtlı iki test (dinamik evren, mevcut hakem, tek seferlik)

| koşu | net | brüt | fee + slip | funding | dolum | Sharpe (sabit sermaye) | maks DD | Sharpe 2020–21 / 2022–24 / 2025+ | net bull / bear / range |
|---|---|---|---|---|---|---|---|---|---|
| B1 trend, taban | +3586 | +5041 | +455 | -998 | 12285 | 0.53 | 14.8% | 1.00 / 0.52 / -0.14 | +3551 / +404 / -1162 |
| T1 trend + histerezis | +3524 | +4963 | +446 | -992 | 12254 | 0.52 | 13.9% | 1.00 / 0.54 / -0.21 | +3570 / +365 / -1189 |
| B2 ev1_plus_new, taban | +3552 | +3592 | +377 | +337 | 11528 | 1.02 | 8.0% | 2.25 / 1.01 / -0.24 | +4017 / -88 / -627 |
| T2 ev1_plus_new + histerezis | +3429 | +3459 | +368 | +340 | 11459 | 0.99 | 8.2% | 2.29 / 0.97 / -0.32 | +3911 / -156 / -614 |
| C0 mevcut `carry` (baz) | -1040 | -2907 | +164 | +2033 | 4986 | -0.17 | 24.3% | -0.51 / 0.16 / -0.33 | -805 / -406 / +779 |
| C1 `carry_xs` | +2358 | +1707 | +369 | +1022 | 10251 | 1.24 | 3.8% | 2.17 / 1.08 / 0.27 | +1987 / -11 / +101 |

- **2.1 trend:** **ÇALIŞMADI**. ΔSharpe = -0.007 (eşleştirilmiş bootstrap %2,5 / %50 / %97,5: -0.034 / -0.007 / +0.023); Δnet = -63, Δbrüt = -78, Δ(fee+slip) = -9, Δfunding = +6, Δdolum = -31; ΔSharpe dönemlere göre: 2020–21: -0.01, 2022–24: +0.02, 2025+: -0.07.
- **2.1 ensemble:** **ÇALIŞMADI**. ΔSharpe = -0.030 (eşleştirilmiş bootstrap %2,5 / %50 / %97,5: -0.089 / -0.030 / +0.025); Δnet = -122, Δbrüt = -133, Δ(fee+slip) = -9, Δfunding = +2, Δdolum = -69; ΔSharpe dönemlere göre: 2020–21: +0.04, 2022–24: -0.04, 2025+: -0.08.
- **2.2 `carry_xs`:** **KABUL**. S1 net > 0: ✓; S2 Sharpe bootstrap %5 yüzdeliği > 0 (+0.53; %50 +1.23; %95 +1.97): ✓; S3 ≥ 2/3 dönem net > 0: ✓; S4 trend ile günlük PnL korelasyonu +0.12 ≤ 0,30: ✓; mevcut carry ile günlük PnL korelasyonu -0.05.

**2.1 teşhis özeti:** nötr bölge ve histerezis (θ_out = 0,10; θ_in = 0,25) pozisyon-izin maskesi olarak uygulandı; tampon ve boyutlama aynen. Trend çekirdeğinde dolum 12285 → 12254, ensemble'da 11528 → 11459: devir zaten tampon (0,2) ile bastırıldığı için ek filtre az şey değiştiriyor; fee+slip tasarrufu (-9 / -9 USDT) brüt kaybından (-78 / -133) küçük. Ölçütle ÇALIŞMADI; tek eşik çifti denendi (tarama yok), bu yüzden 'histerezis hiçbir zaman işe yaramaz' demiyoruz.

**2.2 teşhis ve sonuç:** Faz 1: mevcut carry'nin işareti doğru ama zaman serisi kullanımı yanlış (IC-TS ≈ 0 tüm ufuklarda, IC-XS pozitif ve ufukla artıyor, funding hizası sorun değil, hücre havuzlu kalibrasyon ters). `carry_xs` (kesitsel funding sırası, dolar-nötr) aynı hakem ve evrende mevcut carry'den belirgin iyi: net +2358 vs -1040; brüt +1707 vs -2907; funding +1022 vs +2033. Netin önemli kısmı funding geliri (brüt fiyat PnL'si +1707); günlük PnL korelasyonu eski carry ile -0.05, tahmin (günlük kesitsel) korelasyonu +0.84: aynı kesitsel bilgi, zaman serisi bacağı kaldırıldı. **Uyarılar:** (i) netin %84'i bull rejiminde, bear -11, range +101 (K9 payı kuralı ≤ %80 geçmezdi); (ii) 2025+ net yalnızca +106; (iii) mutlak getiri küçük (6 yılda +2358 / 10 000) çünkü risk motoru dolar-nötr düşük oynaklık üretiyor (maks DD %3.8); Sharpe ölçek-bağımsız ama kullanılabilir getiri değil; (iv) tasarım Faz 1 bilgisinden türetildi (örneklem içi); (v) Binance funding'i, MEXC doğrulanmadı; (vi) K1 (rotasyon null'u), K2, K3 vb. koşulmadı. Bu sonuç 'bir sonraki ön kayıtlı K kartını hak eder' anlamına gelir.

`carry_xs` tahmin düzeyi (bilgi; SE ile, p yok): TS h=5: +0.021 (SE 0.012); XS h=5: +0.037 (SE 0.011); TS h=20: +0.024 (SE 0.018); XS h=20: +0.056 (SE 0.018); TS h=40: +0.001 (SE 0.023); XS h=40: +0.061 (SE 0.022). Tahmin korelasyonu (hücre havuzlu): trend +0.05, eski carry +0.46, lowvol +0.08, fundcrowd +0.22.

## Veri envanteri (Faz 0.3; yalnızca envanter, pipeline kurulmadı)

| veri | kaynak | aralık / çözünürlük | repoda (tape) | not |
|---|---|---|---|---|
| 1h klines, mark, funding | Binance USDT-M arşivi | 2020-01 → 2026-03 (mühür hariç), 1h | **VAR** (`/data`, `/data/pre2022`) | taker alış hacmi sütunu klines'ta VAR |
| Open interest + üst trader / hesap long-short + taker oranı (`metrics`) | Binance arşivi `daily/metrics` | BTC 2020-09-01 → 2026-10-05; ETH/SOL/DOGE 2021-12-01 → 2026-10-05; 5 dk, günlük dosya | **YOK** (indirilmedi; ayrı görev tanımı `TASKS.md`'de) | sütun anlamı ve `create_time` semantiği doğrulanmadı |
| Likidasyonlar | Binance arşivi `liquidationSnapshot` | arşivde yok (BTC/ETH/SOL/DOGE için boş) | YOK | OKX `liquidation-orders` yalnızca yakın zaman: çalışıyor |
| Perp–endeks primi (basis vekili) | Binance `premiumIndexKlines` / `indexPriceKlines` | BTC 2020-01 → 2026-09, 1h (SOL: 2020-09 → 2026-09) | YOK | funding'in ham girdisi; ücretsiz |
| Spot fiyat (spot–perp basis) | Binance spot `klines` | BTC 2017-08 → 2026-09, 1h (DOGE: 2019-07 → 2026-09) | YOK | ücretsiz; spot–perp basis türetilebilir |
| İşlem verisi (trades/aggTrades) | Binance arşivi | BTC aggTrades 2020-01 → 2026-09 (aylık), günlük 2019-12-31 → 2026-10-05 | YOK | tick düzeyi, büyük hacim |
| L2 / emir defteri | Binance `bookDepth` (günlük özet derinlik) / `bookTicker` | bookDepth 2023-01-01 → 2026-10-05; bookTicker yalnızca 2023-05-16 → 2024-03-30 | YOK | tam L2 geçmişi ücretsiz arşivde yok (doğrulanmadı: ücretli sağlayıcılar) |
| MEXC kline | MEXC kontrat API | 1h: 2020-06-22 →; 1d: 2020-06-05 → | YOK (araştırma verisi Binance; MISSION) | resmi, ücretsiz |
| MEXC funding geçmişi | MEXC kontrat API | yalnızca 2025-04-15 → (1618 kayıt) | YOK | MEXC'e özgü funding geçmişi ~1,5 yıl |
| MEXC OI / likidasyon / long-short | MEXC kontrat API | yalnızca anlık (`ticker.holdVol`: var); tarihsel uç bulunamadı | YOK | MEXC için geçmiş OI satın alma/biriktirme gerekir |
| OKX OI+hacim, long-short oranı | OKX `rubik/stat` | yalnızca son 180 gün, günlük (en eski 2026-04-10) | YOK | geçmiş yetersiz |
| Hyperliquid funding geçmişi | Hyperliquid `info` | 2023-05-12 → | YOK | OI/likidasyon geçmişi kontrol edilmedi |
| Binance fapi / Bybit REST | – | bu ortamdan engelli (451 / 403) | – | `openInterestHist` (30 gün sınırı), `allForceOrders` (kaldırıldı) gibi iddialar **doğrulanmadı** |

Maliyet notu (kaba tahmin, doğrulanmadı): `metrics` zip'leri BTC için ~20 MB/sembol-yıl düzeyindeydi (`TASKS.md` notu); ~200 sembolün tam geçmişi onlarca GB ve ~10⁴ dosya; BTC/ETH/SOL için bir günlük iş, tam evren için birkaç gün. aggTrades/trades tick düzeyi ve çok büyük (BTC tek başına yıllarca günlük GB); L2 tam geçmişi ücretsiz kaynaklarda yok.

### Yeni veri kaynaklarının momentum'dan bağımsız bilgi taşıma ihtimali (yargı; kanıt değil)

1. **Spot–perp basis (spot klines + premium/index klines): momentum'dan bağımsız olma ihtimali en yüksek.** Kaynak, funding'in ham ekonomisi: perp primi kaldıraçlı long talebinin kalabalığıdır ve fiyat yönünden büyük ölçüde bağımsızdır (carry_xs'in trend ile PnL korelasyonu düşük). Spot ile hedge edilen (delta-nötr) carry fiyat riskini kaldırır; yani kazanç doğrudan funding/basis. Eksik: kapasite, spot bacağı maliyeti ve MEXC spot/perp erişimi; ücretsiz (Binance arşivi 2017/2020'den) ve hepsi veri işi.
2. **OI + konumlanma (`metrics`: OI, üst trader / hesap long-short, taker oranı): orta-yüksek.** Funding bir fiyat, OI bir miktardır: kalabalığın büyüklüğünü ölçer; fundcrowd'un (yalnızca funding) başarısızlığı OI'nin de başarısız olacağını göstermez. Riskler: OI değişimi eşzamanlı getiriyle çok ilişkili (momentum vekili çıkabilir); kapsam yalnızca BTC 2020-09'dan, diğerleri 2021-12'den (dinamik evrenin 2020–21 kısmı kapsanmaz); sütun anlamı doğrulanmadı. Önce Faz 1'deki gibi IC testiyle sınanmalı.
3. **Likidasyonlar: bu ortamdan sınanamaz.** Binance arşivinde yok; OKX yalnızca yakın zaman; MEXC yok. Veri satın alma/biriktirme gerekir (ücretli sağlayıcılar: doğrulanmadı).
4. **İşlem/L2 verisi (aggTrades, bookDepth/bookTicker): düşük öncelik.** `orderflow` (taker alış payı vekili) IC'si sıfırdan ayırt edilemedi; ek bilgi ihtimali düşük, hacim ve hesap maliyeti çok yüksek; kısa ufuklu mikroyapı bilgisi taker tabanlı hakemde ve fee 10 bps'de kullanılamaz (limit emir/emir defteri modeli yok).
5. **MEXC verisi araştırma kaynağı olamaz:** funding geçmişi yalnızca ~1,5 yıl, OI geçmişi yok, kline 2020-06'dan. MEXC yalnızca aday çıkınca uygulama farkı ölçümü için.

## Deneme sayacı (araştırma defteri)

- Faz 1 aile testleri: **108**; karar ölçütüne giren alt dönem işaret kontrolleri: **27**; betimsel ölçümler (kalibrasyon, yıllık, rejim, uzlaşma, toplam getiri, terminal-hariç, ters-ortogonal, ensemble referansı): **165** → Faz 1 toplam **300** satır (`reports/signal_diagnostics_data/trials.jsonl`).
- Faz 2: hakem defteri satırları (T1, T2, C1; `phase2/ledger_phase2_*.jsonl`): **3**; `carry_xs` IC bilgi ölçümleri (betimsel): **12**.
- Bu görevde eklenen toplam: **315** (muhafazakâr, betimsel dahil); DSR için birincil sayı: aile 108 + kriter 27 + hakem 3 = **138**. Önceki toplam N = 4 775 (`reports/audit_fixes.md`) → yeni N = **5090** (muhafazakâr) / **4913** (birincil).
- Ölçüm/baz koşuları (B1, B2, C0) ve Faz 1 duyarlılık nokta tahminleri (ham getiri hedefi, katı funding, 9-sembol, terminal-hariç nokta) deftere girmedi (ön kayıt kuralı); bunlar p ile iddia taşımaz.

## Dürüstlük notları ve sınırlar

- Her sonuç görülmüş veride; hiçbir test zaman-dışı değil. Alt dönem 2025+ en yakın 'sonraki' dönem ama o da görüldü.
- Dinamik evren aylık hacim sıralamasıyla seçiliyor: yeni şişen küçük/meme sembollerin üye olduğu aylarda sonraki zayıflığı `lowvol`/`nearhigh` gibi kesitsel IC'leri etkileyebilir; bu seçim etkisi ayrıştırılmadı. `lowvol`'ın ham hedef IC'si normalize olandan büyük (mekanik normalizasyon etkisi + gerçek ilişki karışık).
- IC-XS küçük kesitlerde aşağı yanlı (n = 15'te yaklaşık −0,02; testlerde ölçüldü): kesitsel IC'ler muhafazakâr.
- p-değerleri blok bootstrap SE'sinden normal yaklaşım (B = 2000); IC-TS sıra-sonra-yeniden-örnekle yaklaşımı. 108'lik aile Holm'u muhafazakâr; BH q-değerleri tabloda.
- Karar H sınıfı belge metninden okundu ve sonuçtan önce sabitlendi; mekanizma cümlesi eksik üç uzman için bu bir belge boşluğudur, uzmanın kalitesi hakkında yargı değil.
- Faz 2: tek eşik çifti, tek koşu, sermaye 10 000 (önceki dinamik koşu 1 000: Sharpe 1,04; burada ensemble tabanı yaklaşık aynı). Baz koşular ölçümdür, deftere girmedi.
- Belgelerle çelişki/not: (i) `reports/edge_experts.md` ve `ensemble.md` trend/momentum'u 'kanıtlanabilir tek fikir' sayıyor; bu iş dinamik evrende trendin zaman serisi bilgisini bulamadı, kesitsel momentum bilgisini ham p ≈ 0,005'te buldu (Holm'da tutmadı). (ii) Ön kayıt `neutral_zone_hysteresis.md`'de defter yolu ifadesi koşudan önce (kodla aynı commit'te) koşu başına dosya olarak netleştirildi; kural/eşik değişmedi. (iii) `scripts/signal_diag.py` Faz 1 analizinden sonra `checks` ve `carryxs` aşamalarıyla genişletildi; Faz 1 defter satırlarının `code_hash`'i analiz anındaki sürümdür.
- Doğrulanmadı: MEXC funding/fee, Binance fapi/Bybit geçmiş derinlikleri (bu ortamdan engelli), `metrics` sütun anlamları, resmi delist tarihleri.
- Yapılmayan: ensemble ağırlığı/sizing/parametre araması; yeni uzman ensemble'a katılmadı (`carry_xs` REG'e eklenmedi); G3/mühür; veri pipeline'ı.
