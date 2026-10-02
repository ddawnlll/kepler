# Ensemble v1: ZAYIF — K1–K8 geçti, K9'da (rejim) kaldı

**Sonuç.** Ensemble v1 kartta **ZAYIF** (`BACKTEST.md` §11). Ön kayıt: `reports/ensemble_protocol.md`, koddan önce commit'lendi; parametre ve eşikler değişmedi. Sistem şu zincirden oluşuyor: piyasa durumu → 3 uzman (çok hızlı trend, kesitsel momentum, funding carry) → aday → korelasyon farkındalıklı risk motoru.

- **Dönem ve sonuç:** 2020-04 → 2026-04 (6 yıl, ext-9). Net Sharpe **1,45**, rastgele kaydırma null'u p = **0,0033**, DSR **0,999**. Al-tuta karşı alfa t = **3,37**, beta ≈ 0. Maks DD **%9,7**.
- **K9:** kâr tek rejimde toplanıyor. bull +7 329, bear +536, range −895; bull payı %105 > %80.
- **Karar kuralı:** ZAYIF canlıya gitmez ve mühürlü döneme (G3) götürülmez; G3 yalnızca ADAY ile açılır.
- **Projede bir ilk:** daha önce hiçbir sistem K1'i, K2'yi ya da K3'ü geçmemişti.

Tablolar: `reports/ensemble_data/tables.md`. Ham JSON aynı dizinde. Defter: `ledger/ensemble/ledger_ev1.jsonl`.

## Kart
| # | değer | eşik | |
|---|---|---|---|
| K1 | brüt p = 0,0033 (B = 300; null 694 ± 2 242, gerçek 9 195); DSR (N = 6) 0,999 | p ≤ 0,05; DSR ≥ 0,95 | ✓ |
| K2 | Sharpe 1,45 vs al-tut 0,05; alfa %13,8/yıl, t = 3,37 | > ve t ≥ 2 | ✓ |
| K3 | Sharpe 1,45; fee 16 + slip 6: +7 933; 1 bar gecikme: +8 365 | ≥ 1; > 0; > 0 | ✓ |
| K4 | maks DD %9,7; bootstrap DD95 %18,7 | ≤ %25; ≤ %30 | ✓ |
| K5 | 6/6 komşu net > 0; medyan Sharpe 1,36 | ≥ %70; ≥ 0,73 | ✓ |
| K6 | 9/12 yarıyıl pozitif; 4 başlangıç kaydırmasının hepsi ≈ +8 000 | ≥ %60; hepsi > 0 | ✓ |
| K7 | 14 kullanılmamış sembol, fee 16: +742 (8/14 pozitif) | > 0 | ✓ |
| K8 | birincil 1,45 > trend_only 1,23, no_xs 1,32, no_carry 1,31, no_risk 1,12, no_buffer 1,25 | hepsinden büyük | ✓ |
| K9 | bull 7 329 / bear 536 / range −895 | ≥ 2 rejim ≥ 0; tek ≤ %80 | ✗ |

## Diğer bulgular
- **Getiri ve risk:** sermaye 10 000; net +8 297 (yıllık %13,8, oynaklık %9,5). Funding −461: brütün %5'i (Turtle'da %13–30 idi).
- **İşlem yükü:** dolum 5 561, likidasyon 0, red 0. Ortalama brüt pozisyon 0,15× sermaye; yıllık devir 12×.
- **Dağılım:** sembol neti dengeli; BTC 1 393 en büyük, LINK 93 en küçük. Turtle'daki tek-sembol yoğunlaşması yok.
- **Alt dönemler:** zayıflama açık.

  | dönem | Sharpe | alfa t |
  |---|---|---|
  | 2020-04 → 2022-01 | 3,03 | 3,66 |
  | 2022-01 → 2026-04 | 0,81 | 1,60 |

  Son 15 ayın pencereleri: −601, +370, −66.
- **Stres:** FTX −394 (−%3,9), LUNA +294, 2021-05 −41. Kill switch (%25 / %30) hiç tetiklenmezdi; tepe DD %5,1.
- **500 USD sermaye:** net +393 (6 yılda), Sharpe 1,47, red yok. Min notional bu boyutta bağlamıyor.
- **MinTRL** (SR > 0): 1,3 yıl.

## Dürüstlük notları
1. **Görülmüş veride test.** Tasarım, iki dönemin sonuçlarını görmüş bir araştırmacının tasarımı; 14 günlük ufuk ve funding/yoğunlaşma teşhisi bu veriden geliyor (BACKTEST §8.5). Sonuç ön kayıtlı, ama zaman-dışı kanıt değil.
2. **Gücün çoğu 2020–21'den geliyor.** Yalnızca 2022–26 dönemiyle K1–K3 muhtemelen geçmezdi (Sharpe 0,81, alfa t 1,60; null bu alt dönem için ayrıca koşulmadı).
3. **Smoke hatası.** Boru hattı denemesinde pencere hatası (`scripts/ensemble.py::run` varsayılan argümanı) yüzünden ablasyon, komşu ve maliyet koşuları tam 6 yılda koştu. Araştırmacı bu kontrol rakamlarını birincil koşudan önce gördü. Birincil sonuç görülmedi, protokol değişmedi, hata düzeltildi.
4. **Kümülatif deneme:** 4 117 defter satırı. DSR'nin N = 6 ile hesabı muhafazakâr değil proje-ölçeğinde iyimser. Ama p = 0,0033 ve DSR 0,999 geniş bir pay bırakıyor.
5. **UNKNOWN'lar (önceki raporlarla aynı):** slippage (2 bps; 6 bps stresinde de pozitif), sembol kuralları, mmr kademeleri, MEXC farkı, hayatta kalma yanlılığı.

## Sonraki adım (kullanıcı kararı; yapılmadı)
- **(a)** K9 zayıflığına (yatay rejimde kayıp, son 15 ayda sönme) yönelik **yeni ön kayıtlı** bir sürüm. Örnek: rejime göre trend ağırlığı ya da daha fazla piyasa-nötr pay. Bu, aynı veride yeni bir deneme sayılır (N artar).
- **(b)** Kartı değiştirmeden ZAYIF'ı kabul edip mühürlü dönemi açmamak. Sistemi yalnızca kâğıt üzerinde izlemek MISSION'da yok (paper yok); H5 için önce ADAY gerekir.
- **(c)** K9 eşiğinin (tek rejim ≤ %80) bu tür bir sistem için uygun olup olmadığına kullanıcının karar vermesi. Eşik ancak ön kayıtla ve bir **sonraki** testten önce değişebilir; bu sonuca geriye dönük uygulanamaz.

Kod: `kepler/ensemble.py` (motor), `tests/test_ensemble.py` (14 elle hesaplı test; nedensellik + funding nedenselliği), `scripts/ensemble.py` (Modal işçisi), `scripts/ensemble_report.py`. Testler: 217 geçti, 1 atlandı (yerel `uv` ortamı; gerçek ağ testi atlandı). Hakem, denetim, risk ve mühür koduna dokunulmadı; hakem+yapıştırma satırı 473 (değişmedi).
