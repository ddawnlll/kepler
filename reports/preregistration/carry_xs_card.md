# Ön kayıt: `carry_xs` için K1–K9 başarı kartı ("edge var mı?")

**Durum:** ön kayıt; koddan ve koşudan önce commit'lenir (2026-10-06, kullanıcı isteği "edge olup olmadığına bak"). Kural, eşik, evren ve karar sonuçtan sonra değişmez (MISSION kural 11). Görülmüş veride (2020-04 → 2026-03) ön kayıtlı test: **örneklem içi**; mühür dokunulmaz. Kart `BACKTEST.md` §11 eşiklerini ve `reports/ensemble_protocol.md` uygulama ayrıntılarını aynen izler; farklar aşağıda açıkça yazılı.

## Soru ve ne olmadığı
`carry_xs` (`reports/preregistration/carry_rebuild.md`: kesitsel funding sırası, dolar-nötr) dinamik evrende kartı geçiyor mu? **Önceden bilinen iki kısıt (görüldü, dürüstlük notu):** (a) **K9** Faz 2 çıktısında zaten görüldü: netin %84'ü bull rejiminde (tek rejim payı ≤ %80 kuralı kalır); (b) **K7** bu evrende tanımlı değil (aşağıda). Bu yüzden **en iyi olası karar ZAYIF** olur; ADAY denemez. Asıl soru K1/K2: NO_EDGE mi, ZAYIF mı. Karar `robust.decision`: K1 veya K2 kalırsa NO_EDGE; K3–K9'dan biri kalırsa ZAYIF.

## Ortak kurulum (Faz 2 `C1` ile birebir)
Dinamik evren (aylık top-20, delist dahil, `scripts/signal_diag.py::members`), 2020-04-01 → 2026-04-01, sermaye 10 000, fee 10 + slip 2 bps RT, kaldıraç 10, mmr 0,005, gross_cap 3×; kitap = `carry_xs` tek başına, `combine` → `portfolio.size` (τ = 0,20, tampon 0,2) → hakem (`scripts/signal_phase2.py::make_book`). **Ana koşu = Faz 2 `C1`** (yeniden koşulmaz; net +2 358, brüt +1 707, Sharpe 1,24; defter satırı zaten var: yeni hakem satırı yok).

## Kart (eşikler BACKTEST §11)
- **K1 (null/placebo):** ortak-ofset rotasyon null'u, **B = 300**, u_i = `default_rng([0, i]).uniform(0,05; 0,95)` (EV1/K1 ile aynı tohumlar): her sembolün günlük F serisi (aktif olmayan gün 0) aynı k = ⌊u·gün⌋ ile dairesel kaydırılır (`ensemble.rotate`), sonra aktif olmayan günler maskelenir; σ, ρ, IDM, tavanlar gerçek veriyle kalır; aynı hakem/spec. İstatistik: brüt PnL, tek yönlü p = (1 + #{null ≥ gerçek}) / (B + 1). **Geçme: p ≤ 0,05/N ve DSR ≥ 0,95, N = 3** (bu işin Faz 2'deki üç hakem testi: T1, T2, C1; Bonferroni eşiği 0,0167; B = 300 çözünürlüğü p tabanı 0,0033: ulaşılabilir). DSR: deneme Sharpe kümesi = ana + 2 ablasyon (`no_risk`, `no_buffer`; N = 3, muhafazakâr, EV1 emsali). **Bilgi (karar dışı):** aynı p'nin Faz 1'deki 108'lik ailenin Bonferroni eşiği 0,05/108'e karşısı (B = 300 ile ulaşılamaz; yazılır).
- **K2 (benchmark):** Sharpe(strateji) > Sharpe(benchmark) **ve** Newey–West (gecikme 5) alfa t ≥ 2. Benchmark = her gün **o gün aktif (üye) sembollerin eşit ağırlıklı günlük basit fiyat getirisi** (kapanıştan kapanışa, karar günü bilinen küme; maliyetsiz, fonlamasız; "gösterge": hakem al-tut'u pozisyon notional'ı büyüdüğü için artefakt verir, `reports/audit_fixes.md` 2.5). Strateji getirisi = günlük net PnL / 10 000; benchmark getirisi = günlük fiyat getirisi (strateji dolar-nötr, benchmark long-only: beta ≈ 0 beklenir).
- **K3 (ekonomik + maliyet stresi):** ana koşunun net Sharpe'ı ≥ 1,0 **ve** net > 0 hem fee 16 + slip 6'da hem 1 bar ek gecikmede (`Spec.delay = 1`). İki ek hakem koşusu.
- **K4 (risk):** planlanan boyutla (τ = 0,2) maks DD ≤ %25 (sermayeye, toplamsal) **ve** bootstrap (durağan blok 20 gün, B = 2 000, tohum 0) DD %95 dilimi ≤ %30. Ana koşunun günlük PnL'inden.
- **K5 (parametre duyarlılığı):** `Params.scaled(s)` ile tüm geri bakışlar (carry_days 7, vol_days 30, corr_days 90) × s, s ∈ {0,8; 0,9; 1,1; 1,2} (tamsayı yuvarlama; carry_days: 6, 6, 8, 8): 4 komşu koşusu (fee 10 + slip 2). **Geçme: komşuların ≥ %70'i net > 0 ve komşu medyan Sharpe ≥ ana Sharpe'ın yarısı.**
- **K6 (pencere / başlangıç):** hakem pencere başına ayrı koşar (hesap düz başlar; kitap tam seride hesaplanır): 11 yarıyıl (2020-07-01 → 2026-01-01) + 2026-Q1 = 12 pencere; **≥ %60'ı net > 0**; başlangıç 2020-04-01/05-01/06-01/07-01 kaydırmaları (bitiş 2026-04-01): **dördü de net > 0**.
- **K7 (çapraz varlık): KOŞULAMAZ.** Kural "kullanılmamış, evren dışı sembol kümesi" ister; bu işin evreni zaten her ayın tüm top-20'sidir ve `universe.parquet` yalnızca rank ≤ 20 tutar (21–40 yok). Etiket: "koşulamadı (veri yok)"; ADAY kararını engeller.
- **K8 (ablasyon):** `no_risk` (n = K·F/M) ve `no_buffer` (tampon 0) tek tek: **ana Sharpe her ablasyondan büyük olmalı**. (carry_xs'in başka bileşeni yok: stop/filtre/piramit yok.)
- **K9 (rejim):** `robust.regime` (BTC nedensel etiketler): ≥ 2 rejimde net ≥ 0 **ve** tek rejim payı ≤ %80. Faz 2 çıktısından kalır (bull %84); kartta yeniden hesaplanır.

## Koşular ve deneme sayımı
Null B = 300 (15 Modal işi × 20 çekiliş), K3 2, K5 4, K8 2, K6 16 pencere; hepsi `run_book` (kontrol: deftere/N'ye girmez, EV1/edge_experts emsali); K1 p-testi 1 karar satırı olarak deftere (`/data/signal_diag/carry_xs_card/`) yazılır: **N + 1**. DSR için N = 3 yukarıdaki. Ana koşu yeniden koşulmaz.

## Tahmin (koşudan önce; yargı)
K1: brüt p ≈ 0,01–0,10 (Faz 1'de kesitsel IC anlamlı, ama brüt +1 707 küçük ve rotasyon null'u 9 sembolde de tek rejim etkisine duyarlı) → geçme olasılığı ~%40. K2: Sharpe 1,24 benchmark'tan büyük, alfa t ≈ 2–3 → geçme olasılığı ~%65. K3: Sharpe ≥ 1 geçer, maliyet stresi (net 2 358 − ~700) geçer. K4 geçer (DD %3,8). K5, K6, K8: olası kalma noktası K6'nın kısa pencereleri (2025+ net yalnızca +106). K7 koşulamaz, K9 kalır. Beklenen karar: K1/K2 geçerse ZAYIF, aksi NO_EDGE.

## Sınırlar
Tasarım Faz 1 bilgisinden türetildi (örneklem içi); kart bunu telafi etmez, zaman-dışı kanıt yalnızca G3 (mühür, ADAY gerekir) ve canlıdır. Funding Binance'tir (MEXC doğrulanmadı). K1 null'u zamanlama bilgisini sınar; maliyet K3'te. Benchmark gösterge niteliğinde.
