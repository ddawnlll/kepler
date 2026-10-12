# KEPLER — BACKTEST TASARIMI (v1, 2026-10-02)

Bu dosya Kepler'in backtest ve değerlendirme mimarisinin **tek ayrıntılı tasarım belgesidir**: veri bölme,
simülasyon (hakem), istatistik, sağlamlık testleri, başarı kartı ve test senaryoları. Kural ve kapılar
`MISSION.md`'de; çelişkide MISSION kazanır, çelişkiyi raporla. Sistem haritası `ARCHITECTURE.md`'de,
nasıl çalıştırılır `AGENTS.md`'de.

## 0. LLM / ajan için okuma talimatı

- Backtest, sinyal, risk, hakem, değerlendirme veya rapor ile ilgili **her işten önce** bu dosyayı oku.
- Her bölümün durumu etiketlidir: **[VAR]** kodda, testli ve en az bir kez gerçek veride kullanılmış; **[KISMEN]** kodda ama eksik; **[PLANLI]**
  tasarlandı, kod yok (TASKS.md'de iş olarak açık); **[YOK]** bilinçli olarak kapsam dışı.
- [PLANLI] bir parçayı yazarken buradaki sözleşmeye ve test senaryolarına uy. Sözleşmeyi değiştirmen
  gerekiyorsa önce bu dosyayı güncelle, sonra kodu yaz (aynı commit'te olabilir), değişiklik kaydına ekle.
- Bir test yapılandırmasını, eşiğini veya ölçütünü **sonuca bakıp değiştirme** (MISSION kural 11).
- Doğrulanmamış her varsayım **UNKNOWN** etiketiyle kalır; tahmini gerçek gibi yazma.

## 1. Terimler

| Terim | Anlamı (Kepler'de) |
|---|---|
| Dev dönemi | 2022-01-01 → 2026-04-01 (UTC). İndirilmiş, ajanların gördüğü veri |
| Mühürlü dönem | ≥ 2026-04-01. İndirilmedi; G3'te kullanıcı komutuyla tek atış |
| Train / iç döngü | Parametre veya model seçimi yapılan veri |
| Validation | Seçenekleri karşılaştırma verisi (nested yapıda iç döngü içinde) |
| OOS / test | Seçimde hiç kullanılmamış veri. Dev dönemi araştırmacı tarafından görülmüştür; gerçek anlamda dokunulmamış tek veri mühürlü dönemdir |
| Deneme (trial) | Deftere giren her yapılandırma koşusu; N = bir testteki deneme sayısı |
| Ön kayıt | Kural, evren, deneme sayısı ve geçme ölçütünün koddan ve koşudan önce `reports/` altında commit'lenmesi |
| Aday | Başarı kartında K1–K9'u geçen yapılandırma |
| RT | Gidiş-dönüş (round trip); fee ve slippage bps cinsinden RT verilir, yan başına yarısı uygulanır |

## 2. Katman mimarisi

```
 [1] VERİ (tape)           Binance USDT-M 1h kline + mark + funding, Parquet (Modal Volume)
        │  tape.load(root, sym)  — mühür sınırını kodla reddeder
        ▼
 [2] SİNYAL                signal(kl) -> birim pozisyon serisi [-1, 1], NaN = tut   (saf, nedensel)
        │
        ▼
 [3] RİSK / BOYUT          size(kl, unit, capital) -> hedef notional (USDT); turtle_book: hedef + stop [VAR]
        │
        ▼
 [4] HAKEM (yürütme)       referee.run(kl, target, Spec, funding, mark) -> fills, özet
        │  Nautilus 2.0.0rc5 + yapıştırma: sonraki-bar dolum, fee+slip, funding, mark-tetikli likidasyon
        ▼
 [5] DENETİM + DEFTER      evaluate(): nedensellik denetimi -> hakem -> ledger.record (append-only; flock yalnız yerel, dağıtık: job-receipt + toplayıcı)
        │
        ▼
 [6] DEĞERLENDİRME         bölme (walk-forward / nested) + null + istatistik (Bonferroni, DSR, ...)
        │
        ▼
 [7] SAĞLAMLIK             parametre, pencere, rejim, çapraz varlık, maliyet, bootstrap, ablasyon
        │
        ▼
 [8] BAŞARI KARTI          K1–K10 -> ADAY / ZAYIF / NO_EDGE
        │
        ▼
 [9] G3                    mühürlü dönem tek atış (kullanıcı komutu)
```

Ek yol: **eleme** (vectorbt, `kepler/screen.py`) yalnızca hızlı filtredir, sonuç sayılmaz, deftere `score`
yazar ve deneme sayacına girer (§6.6).

## 3. Veri katmanı [VAR]

- **Kaynak:** `data.binance.vision` aylık arşiv; klines 1h, markPriceKlines 1h, fundingRate. sha256 doğrulamalı,
  idempotent indirme (`kepler/data.py`). `DEV_END = "2026-03"`: sonrası hiçbir yoldan indirilmez.
- **Depolama:** Modal Volume `kepler-data` → `/data/tape/{klines,markPriceKlines,fundingRate}/SYM.parquet`,
  `universe.parquet`. Manifest ve kalite raporu git'te: `data_manifest/`.
- **Zaman:** tüm indeksler UTC, bar indeksi = bar **açılış** zamanı; bar t'nin kapanışı t + 1h.
- **Funding:** `calc_time, funding_interval_hours, last_funding_rate`; aralık 1/2/4/8 saat olabilir (99 sembol 8 saat dışı).
- **Evrenler (sabit, sinyale bakmadan):** çekirdek-5 = BTC, ETH, SOL, XRP, BNB; genişletilmiş-9 = + DOGE, ADA,
  LINK, AVAX. Aylık hacim evreni (top-20, nedensel: ay M = M-1 hacmi) `tape.membership(root)` ile; emtia/stable/
  endeks sıralamadan önce çıkarılır.
- **Kullanılabilirlik kesimi:** kline–mark ≥24 ardışık bar >%5 ayrışırsa sembolün verisi o andan sonra kullanılmaz
  (`qc.divergence_cutoff`, `tape.load` uygular). 28 sembol kesildi.
- **Türetme:** `tape.aggregate(kl, "4h" | "1D")`; eksik bar sayısı `n` sütununda. Gerçek veride (BTCUSDT 37 224 saat → 9 306 4h / 1 551 1D) hacim, ilk açılış, son kapanış, high/low ve bar sayısı korunuyor (`reports/backtest_completion.md` madde 4b).
- **Bilinen sınırlar:** klines'ta %0,10 eksik bar; 77 sembolde |funding| > %1 anları (gerçek mi hata mı UNKNOWN);
  sembol kuralları (tick, lot, min notional, bakım marjı kademeleri) **UNKNOWN**, arşivde yok.
- **Hayatta kalma yanlılığı:** çekirdek-5 / genişletilmiş-9 bugün bilinen "hayatta kalan" majörlerdir; sonuçları
  iyimser yönde etkiler. Raporda belirtilir.

## 4. Sinyal sözleşmesi [VAR]

```
signal(kl: DataFrame[open, high, low, close, volume (+ fund_hr)]) -> Series
```
- İndeks `kl` ile birebir aynı; değerler float, |x| ≤ 1; +1 tam long, −1 tam short, 0 flat, **NaN = mevcut pozisyonu tut**.
- `target[t]` = t barının **kapanışında** istenen pozisyon. Dolum sonraki barın açılışında (§6).
- Günlük sinyaller günlük mumla hesaplanır, karar yalnızca günün 23:00 barına (kapanış 00:00 UTC) yazılır; diğer barlar NaN.
  Aylık sinyaller ay sonu gününün 23:00 barına. `signals._put` bunu uygular.
- **Saf ve nedensel:** aynı girdi → aynı çıktı; t'deki karar yalnızca ≤ t kapanışındaki veriye bakar.
- Funding kullanan sinyaller `signals.with_funding(kl, funding)` ile `fund_hr` sütunu alır (bar kapanışında bilinen son oran / aralık saati).
- Mevcut sinyaller (`kepler/signals.py`): `turtle(entry, exit_, trend)`, `tsmom(days, every)`, `ema_trend(fast, slow)`,
  `dual_mom(panel, sym)`, `xs_signal(panel, sym, kind, days, every)`, `carry_funding(days)`.
- **Panel sinyalleri:** `check_causal` yalnızca sembolün kendi `kl`'ini bozar; paneli de bozan test `check_causal_book` (yukarıda).
- **[VAR] kitap (portföy) sözleşmesi (Motor v2):** `book({sym: kl}) -> {sym: DataFrame[target, stop]}` (`turtle.turtle_book` ve kapanışları). `target` = hedef notional
  (USDT, işaretli; NaN = tut), `stop` = t kapanışında bilinen koruyucu stop fiyatı (NaN = stop yok), t+1 açılışından (gecikmede 1+delay) itibaren geçerli; hourly indeks `kl` ile aynı.
  Kitap yalnızca ≤ t verisiyle hesaplanır: `audit.check_causal_book` tüm sembollerin k sonrasını bozar (panel dahil) ve kitabı kesip karşılaştırır. Tek-seri sinyal sözleşmesi
  (yukarısı) değişmedi; `stop = NaN` her yerde = stopsuz, sonuç eski hakemle birebir aynı (tests/test_portfolio.py madde 9).
- **Panel sinyallerinin nedensellik testi [VAR]:** `audit.check_causal_book(fn, data)`; tek-sembol `check_causal` bunun tek sembollü halidir.

## 5. Risk / boyut katmanı

### 5.1 Risk motoru [VAR] (`kepler/risk.py`, `Spec.equity_scale`; gerçek veri: `reports/backtest_completion.md`)
| Fonksiyon | Davranış | Varsayılan |
|---|---|---|
| `realized_vol(kl, days)` | Günlük log-getiri std × √365, yalnızca tamamlanmış günler (shift 1) | 30 gün |
| `vol_target(kl, unit, capital, target_vol, max_lev, band, days)` | notional = yön × capital × min(max_lev, target_vol / vol); göreli sapma < band ise yeniden boyutlama yok | %20, 3x, %25 |
| `kill_switch(target, equity, max_dd)` | Equity tepeden max_dd düşünce hedef o andan sonra 0 | MISSION önerisi %25 |
| `evaluate(size=, kill_dd=)` | Boyutlu hedef capital × leverage tavanını aşarsa hata | — |

Kill switch tetiklenince **hakem baştan, kırpılmış hedefle yeniden koşar**; tetik zamanı deftere `kill_at` olarak yazılır. Tetikten sonra hesap flat kalır (insan onayına kadar; yeniden devreye alma yok).
- **Portföy kill switch:** `evaluate.run_book/evaluate_book(kill_dd=)`: portföy saatlik equity'si (`report.book_pnl`) tepeden `kill_dd` düşünce tüm hedefler 0 (tests/test_turtle.py).
- **Equity'ye göre ölçekleme:** `Spec.equity_scale` (§6.1): hakem emir anında hedef notional'ı equity/capital ile çarpar (tests/test_portfolio.py).
- **Gerçek veride kullanım:** `equity_scale` + portföy kill switch tam Turtle S1/S2'de (6 deneme), `vol_target` + kill BTC turtle duman testinde (3 deneme), `realized_vol` onun içinde: `reports/backtest_completion.md` madde 4/4b. Parametreler ayarlanmadı.

### 5.2 Motor v2 [VAR] (`kepler/risk.py::wilder_n`, `kepler/turtle.py`; tests/test_turtle.py)
Sinyal yalnızca yön verir; yönetici (`turtle_book`) günlük kararla (23:00 barı) şunları ekler. Kurallar `turtle.py` başlığında; özet:
- **N (ATR) boyutlama:** N = Wilder ATR(20) günlük (`risk.wilder_n`); birim qty u = capital × risk / N (risk = %1; N giriş günü, pozisyon boyunca sabit); hedef notional = yön × birim sayısı × u × kapanış.
  Sermaye **sabit** (başlangıç sermayesi; equity geri beslemesi yok: Turtle'ın bileşik sermaye ayarı yok, sapma).
- **Piramitleme:** son birimin referans kapanışından yön × 0,5N ilerleyince (günde en çok 1) +1 birim, en çok 4.
- **Strateji stopu:** referans kapanış − yön × 2N; her eklemede son referanstan yeniden kurulur. Hakem bar içinde yürütür (§6.4); yönetici günlük H/L ile taklit eder (durum eşitleme).
- **Birim sınırları:** sembol ≤ 4, aynı gruptaki aynı yön ≤ 6, toplam aynı yön ≤ 12; gruplar ön kayıtta. Günde iki geçiş: önce stop taklidi + çıkış/çevirme (alan açar), sonra girişler/eklemeler alfabetik. Engellenen giriş yön değişene kadar tekrar denenmez.
- **Veri boşlukları:** eksik günler atılır (N sürekli); yön günün son değeriyle (ffill); karar günün son mevcut barına yazılır. Stop taklidi hakemin tetik verisini (mark H/L) ve tick yuvarlamasını kullanır.
- **Portföy tavanı:** `Spec.gross_cap` (§6.5).
- Kural: risk parametreleri sonuçtan önce yazılır, sonuca göre oynanmaz.

## 6. Hakem (yürütme ve muhasebe)

### 6.1 Spec [VAR] (`kepler/referee.py`)
| Alan | Varsayılan | Anlam |
|---|---|---|
| `tick`, `step` | "0.1", "0.001" | Fiyat ve miktar çözünürlüğü; G2'de sembole göre türetilir (UNKNOWN gerçek kurallar) |
| `min_notional` | 5.0 | Bu notional'ın altındaki **artıran** emirler yapılmaz; azaltanlar her zaman yapılır |
| `fee_rt_bps` | 10.0 | Taker fee, RT bps; yan başına yarısı |
| `slip_rt_bps` | 0.0 | Slippage, RT bps; `evaluate` ≥ 1 bps zorunlu kılar, G2'de 2 (alt sınır), stres 6 |
| `leverage` | 10 | Başlangıç marjı = 1 / leverage |
| `mmr` | 0.005 | Bakım marjı oranı (UNKNOWN: kademe tablosu yok) |
| `capital` | 500.0 | Başlangıç bakiyesi (USDT) |
| `liq` | True | Mark-tetikli likidasyon stopu |
| `liq_fee_rate` | None → mmr | Likidasyonda kaybedilen oran; motorun taker fee'si bunun içinde (çifte sayım yok) |
| `fill` | "next_open" | "close" yalnızca test/eski; `evaluate` reddeder |
| `close_out` | True | Dönem sonunda açık pozisyon son kapanıştan fee+slip ile değerlenir |
| `delay` | 0 | Ek gecikme (bar): dolum karardan sonraki (1 + delay). açılışta (K3 stres: delay=1) |
| `gross_cap` | None | Toplam brüt notional tavanı (USDT); artıran emir kalan alana küçülür (§6.5) |
| `equity_scale` | False | True: yeni/değişen hedef notional × (equity / `capital`), equity = bakiye + settlement'ta uygulanmış funding + gerçekleşmemiş PnL (emir anında, son görülen fiyatla; çıkış maliyeti ve likidasyon ücreti farkı dahil değil); `gross_cap` da aynı çarpanla ölçeklenir; hedef değişmedikçe yeniden boyutlama yok. **Davranış:** her hedef değişiminde TÜM pozisyon güncel f ile yeniden boyutlanır (yalnız delta değil); bu yüzden f düşükken yukarı giden bir hedef (piramit eklemesi) pozisyonu küçültebilir. Turtle'ın birim-başına-sabit boyutundan sapma (§5.1) |

### 6.2 Yürütme semantiği [VAR]
1. Her saatlik bar motora iki parça gider: açılış tiki (o,o,o,o) zaman t (karar anı) ve gövde (o,h,l,c) zaman t+1h−1ns.
2. t barının kapanışında verilen hedef, **ilk mevcut sonraki barın açılışında** piyasa emriyle dolar (boşluk varsa sonraki mevcut bar). Son barın hedefi dolmaz.
3. Hedef değişmedikçe yeniden boyutlama yok; değişince miktar = hedef notional / dolum fiyatı, lot adımına aşağı yuvarlanır.
4. Maliyet: (fee + slip)/2 bps her dolumun notional'ına; özet `fee`, `slippage`, `exit_cost` ayrı raporlar.
5. **Funding:** T anındaki oran × T'den önce (T'deki dolumlardan önce; açılış tikinde dolan gap stopu/likidasyon dahil) tutulan pozisyon × mark kapanışı; oran > 0 iken long öder. Mark yoksa kline'a düşer (`funding_mark_fallback` sayılır); ikisi de yoksa `funding_missed` sayılır ve koşu deftere giremez.
   **Settlement anında uygulama (#10):** funding tutarı T'de bir kez bakiyeye (nakit akışı) işlenir; equity, `equity_scale` boyutlaması ve likidasyon fiyatının cüzdan bakiyesi aynı akışı görür (koşu sonunda yeniden eklenmez; çift sayım yok). Sıra: (1) önceki barın gövdesindeki stop/likidasyon, (2) T'deki funding (karardan önceki pozisyon), (3) açık pozisyonların koruyucu emirleri yeni bakiyeyle yeniden kurulur: özsermaye bakım marjının altındaysa reduce-only market ile kapanır ve likidasyon sayılır (`n_liq`), (4) T'deki kararlar/dolumlar. Negatif bakiye mümkündür; likidasyon fiyatı fiyatın ötesine geçer ve pozisyon hemen kapanır. Sınır: bakım marjı tek `mmr` oranıdır, gerçek borsa risk kademeleri ve cross-margin likidasyonu doğrulanmadı (UNKNOWN); model "tam gerçekçi" değildir.
6. **Likidasyon:** Nautilus bar verisinde likide etmez; her pozisyon değişiminde likidasyon fiyatına reduce-only stop-market konur. Gövde barının H/L'si **mark** H/L'sidir (mark yoksa kline). Boşlukla geçilirse stop piyasa fiyatından dolar (iyimser LP dolumu yok). Likidasyondan sonra hesap ölüdür, yeni işlem yok.
7. Reddedilen emir (`n_rejected > 0`), eksik funding veya motor kaynaklı dolumsuz emir (`n_engine_unfilled > 0`, örn. fiyat hassasiyeti uyumsuzluğu) olan koşu geçersizdir; deftere yazılmaz.
   **Niyet izi (#11):** `res['intents']`: her hedef değişimi için niyet → lot/tavan sonrası hedef → emir → dolum/red/bloke (`sent`, `partial`, `rejected`, `blocked_minimum`, `noop_lot`, `blocked_halt`, `engine_unfilled`). Minimum altı/lot no-op'u hata değil, görünür bir sınırlamadır (tutar `blocked_notional`, sapma `gap_notional`). `n_rejected=0` tüm niyetlerin yürütüldüğü anlamına gelmez; niyet sayısı ile dolum sayısı eşit olmak zorunda değildir. Minimuma yukarı yuvarlama ve risk bütçesi büyütme yoktur.
   **Mutabakat:** `report.reconcile` saatlik PnL yeniden kurulumunu (fiyat + funding − fee − slip − likidasyon/çıkış) hakem `net_pnl` ile karşılaştırır; tolerans 0,01 USDT + 1e-7 × işlem hacmi. `evaluate_book` ayrışmada hata verir ve `recon_diff`'i özete yazar.
8. Çıktı: `summary` (net_pnl, gross_pnl, fee, slippage, funding, liq_fee, exit_cost, n_fills, n_liq, end_position, n_rejected, funding_missed, funding_mark_fallback), `fills`, `positions`, `rejected`.

### 6.3 Mevcut sınırlar
- Portföy [VAR] (§6.5): `run_portfolio` tek motor, tek hesap; `run` tek sembollü özel hali.
- Yalnızca piyasa emri; limit/maker [YOK]: gerekçe — MISSION "önce taker; maker ayrı hipotez"; limit dolum olasılığı ve kuyruk önceliği emir defteri/L2 verisi ister (kapsam dışı), bar verisinden varsayımsal olur.
- Bar çözünürlüğü: bar içi olay sırası bilinmez (§6.4 kuralı).
- Slippage hakemde sabit bps. Hacme bağlı etki hakem **dışı maliyet bindirmesi** olarak [VAR] (`kepler/capacity.py`, §10 Kapasite): katılım = dolum notional'ı / aynı saatin quote hacmi; karekök etki = Y·σ_h·√katılım·notional (Y = 1 birincil, UNKNOWN), sabit slippage'a ek; yol bağımlılığı yok sayılır. Hakemin kendisi hacme bağlı dolum yapmaz.

### 6.4 Strateji stopu [VAR] (Motor v2; tests/test_stops.py)
- `stop[t]` (t kapanışında bilinen), t+1 açılışından itibaren reduce-only stop-market olarak durur; seviye her açılış tikinde ve her dolumdan sonra yeniden kurulur.
- **Sembol başına tek koruyucu emir:** stop ile likidasyon fiyatından (LP) fiyata **yakın** olan konur (aynı tikte iki stop'un sırası belirsiz olmasın; yakın olan fiyat yolunda zaten önce vurulur).
  Dolum fiyatı LP'de ya da ötesindeyse olay likidasyondur (hesap/sembol ölür, likidasyon ücreti), değilse strateji stopudur (`fills.stop`).
- Gövde barında fiyat stopu geçerse dolum stop fiyatından; **açılış stopun ötesindeyse (gap) açılış fiyatından**. Seviye kurulurken fiyatın ötesindeyse (açılış gap'i) piyasa emriyle hemen kapanır.
- Slippage fiyatı oynatmaz, her dolumda komisyon kalemi olarak sayılır ((fee+slip)/2 yan başına, §6.2.4); stop dolumu da aynı.
- Tetik: motora giden barların H/L'si **mark** H/L'sidir (likidasyonla aynı kaynak; Binance `workingType=MARK_PRICE`); mark yoksa kline.
- Aynı barda giriş ve stop: giriş açılışta dolar, aynı barın gövdesi stopu geçtiyse stop o barda tetiklenir (iki dolum).
- **Stop sonrası flat:** hedef yönü (işareti) değişene (ters ya da 0) kadar yeniden giriş yok; aynı yönlü hedef değişiklikleri (örn. piramit) yok sayılır.
- Bar içi belirsizlikte (aynı barda hem kâr hedefi hem stop) kötümser: önce stop. (Kâr hedefi emri yok; stop ve LP tek emirde.)

### 6.5 Portföy hakemi [VAR] (Motor v2; tests/test_portfolio.py)
- `referee.run_portfolio(data, spec)`: tek Nautilus motorunda N enstrüman, tek USDT hesap, ortak marj. `data[sym] = dict(kl, target, stop, funding, mark, tick, step)`.
- **Brüt tavan hakemde (`Spec.gross_cap`):** artıran emir, diğer sembollerin son fiyatla brütünü düşen kalan alana (lot adımına aşağı) küçülür, ama sembolün mevcut aynı yönlü pozisyonunun altına inmez (artıran hedef satışa dönmez); azaltan emir tavandan etkilenmez. Hedefler yeniden ölçeklenmez
  (churn yok); küçülen emir için alan sonradan açılsa da hedef değişmedikçe tamamlanmaz. (Eski taslak: "orantılı küçültme"; yol bağımlı ama churn'süz ve test 10 bunu sabitler.)
- **Denklik şartı:** tek sembolde sonuç yeniden yazımdan önceki hakemle birebir aynı (tests/test_portfolio.py: eski hakemden alınan sabit sayılar; 28 dolumlu funding'li koşu ve 10x likidasyon).
- Funding sembol başına; likidasyon yalnızca o sembolü kapatır, diğerleri açık kalır (cross-margin likidasyonu [YOK], UNKNOWN Binance davranışına bağlı). LP'nin kullandığı bakiye = cüzdan − diğer pozisyonların
  başlangıç marjı (notional/kaldıraç); LP yalnızca o sembolün kendi dolumlarında yeniden hesaplanır (başkasının PnL'siyle kayması yok sayılır: yaklaşıklık, UNKNOWN).
  **Cross-margin [YOK] gerekçesi:** doğru model bakım marjı kademelerini ve Binance likidasyon motorunu ister (ikisi UNKNOWN; `fapi` bulut ortamından 451). Yaklaşıklığın payı ölçüldü: tam Turtle `full` koşularında (S1, S2) n_liq = 0; likidasyon yalnızca stopsuz ablasyonlarda (S1 7, S2 4) ve S1 `equity_scale`'de (2) görüldü, yani yaklaşıklık yalnızca aşırı kaldıraçlı/stopsuz yollarda devreye girer (`reports/full_systems.md`, `reports/backtest_completion.md`).
- `evaluate.evaluate_book`: gerçekçi Spec → panel nedensellik denetimi → belirlenimlilik → portföy hakemi → portföy kill switch (tüm hedefler 0) → defter.

### 6.6 Eleme (vectorbt) [VAR]
- `kepler/screen.py`: hedef değişince **kapanış** fiyatından hedef notional'a ayarlar (hakemden iyimser: next_open değil).
- Sonuç sayılmaz, deftere yalnızca `score` yazar, her konfigürasyon deneme sayacına girer.
- Eleme–hakem uyumu (arama ızgarası, n=88): Spearman 0,871; aile içi donchian 0,94, ema 0,89, tsmom 0,97, xs_mom 0,71, xs_rev 0,60.
  Kural: aile içi Spearman < 0,8 olan ailelerde eleme kullanılmaz, doğrudan hakem.

## 7. Denetim ve defter [VAR]

- **Tek giriş:** `kepler/evaluate.py::evaluate(signal, kl, specs, ledger_path, hypothesis, data, funding, mark, notional, name, params, window, size, kill_dd)`.
- **Deney kimliği (#12):** her hakem kaydı `receipt` taşır (`kepler/receipt.py`): `economic_id` = f(kepler/ paketinin tüm kaynak içeriği + betik, kanonik config, kitap closure'ı [Params, üyelik tablosu, hyst], hakemin tükettiği kline/funding/mark içerik hash'i + sembol kümesi + kesim). Git SHA, kirli-diff hash'i, uv.lock, çalışma ortamı, run_id/attempt/zaman AYRI tutulur ve kimliğe girmez. Eski satırlar değişmez; `receipt` yoksa `legacy_partial_provenance`. Sınır: tüm paket hash'i muhafazakârdır (yorum değişikliği de kimliği değiştirir); kullanılmayan mühürlü veri ve anahtarlar receipt'e girmez (yalnız verilen veri hash'lenir).
  Sıra: Spec gerçekçilik kontrolü → `audit.assert_causal` (16 kesim noktasında geleceği bozar, geçmiş kararlar değişmemeli) →
  belirlenimlilik (sinyal iki kez aynı) → |unit| ≤ 1 → hakem → `ledger.record`.
- `window=(başlangıç, bitiş)`: sinyal tam seride hesaplanır (ısınma), hakem yalnızca pencerede koşar; pencere başında tutulan pozisyon açık hedef olur.
- **Defter satırı:** `trial, time, source (referee|screen), hypothesis, config, config_hash, code_hash, data_hash, result, score`.
  Append-only; `fcntl.flock` yalnız AYNI makine/konteyner içindeki yazarlar için güvence verir (yerel flock testi dağıtık güvence değildir; Modal Volume'da konteynerler arası kilit bu depoda doğrulanmadı ve güvenilmez). Dağıtık işler için tek yazar modeli: her job `ledger.write_job_receipt` ile değişmez (O_EXCL) receipt dosyası yazar, `ledger.aggregate` tek toplayıcı olarak deterministik sırayla (ad sıralı) ve atomik olarak deftere toplar; tekrar toplama idempotent, aynı adda farklı içerik veya bozuk receipt açık hata. Her satır `status` (completed/invalid/failed/incomplete/planned/running), `reason`, `kind` (run/retry/smoke), `attempt` taşır: geçersiz koşu (`n_rejected`, `funding_missed`, `n_engine_unfilled`, PnL mutabakatı) `record_attempt(status=invalid)` ile araştırma izinde `result=None` olarak (ham sonuç `invalid_result`) korunur ve `evaluate*` ardından `InvalidRun` fırlatır; çöken koşu `failed` yazılır. Deneme sayacı tüm satırları sayar (muhafazakâr). `ledger.summary`: retry/smoke ve aynı ekonomik kimliğin tekrarları bağımsız hipotez sayılmaz; NaN/inf reddedilir; hakem satırı `config.audit_causal=True` ister (korkuluk, güvenlik değil).
- **Deneme sayımı:** her hakem ve eleme satırı +1. Null çekilişleri ve sağlamlık koşuları kontrol sayılır, **N'ye girmez**,
  ancak sonuçlarına göre seçim yapılırsa girer. Projenin kümülatif deneme sayısı her raporda ayrıca yazılır (DuckDB: `ledger.query`).
- Hash'ler: `code_hash` = hakem, evaluate, audit, ledger, tape ve sinyal kaynak dosyaları; `data_hash` = manifest sha256.

## 8. Veri bölme (değerlendirme tasarımı)

### 8.1 Sabit kural, ön kayıtlı [VAR]
Parametre seçimi yoksa eğitim de yoktur. Karar **tüm dev dönemi** üzerinden null'a karşı verilir; walk-forward pencereleri
yalnızca **zamansal dağılımı** göstermek için raporlanır (K6).
- Raporlama pencereleri (anchored değil, ardışık yarıyıllar): 2023-H1, 2023-H2, 2024-H1, 2024-H2, 2025-H1, 2025-H2, 2026-Q1.
- Isınma: en uzun geri bakış (ör. 365 gün) kadar başlangıç işlemsiz kalır; DSR/Sharpe günlük serisinde ısınma günleri dışlanır [VAR: `stats.sharpe_series(warmup_days)`; G2'de sıfır PnL olarak dahildi, o sonuçlar değişmedi].

### 8.2 Seçim yapan araştırma: nested walk-forward [VAR] (`kepler/nested.py`, tests/test_nested.py; ön kayıt `reports/nested_wf_protocol.md`; tek koşu: `reports/backtest_completion.md` madde 6)
Parametre veya model seçen her test bu yapıyı kullanır; seçim prosedürünün kendisi test edilir.
```
Dış döngü (anchored, genişleyen):   eğitim [2022-01-01, T_k)   →   OOS [T_k, T_k + 6 ay)
   T_k ∈ {2024-01-01, 2024-07-01, 2025-01-01, 2025-07-01, 2026-01-01 (3 ay)}
İç döngü (yalnızca eğitim penceresi içinde):
   eğitim penceresi ardışık yarıyıllara bölünür; her aday yapılandırma bu yarıyıllarda koşar;
   seçim ölçütü = iç yarıyılların medyan net Sharpe'ı (fee 10, slip 2)  — ön kayıtta değiştirilebilir, sonradan değil
Sonuç: dış OOS parçaları birleştirilir; başarı kartı bu birleşik OOS serisiyle değerlendirilir.
```
- Seçim her dış adımda yeniden yapılır; seçilen yapılandırma ve skor deftere yazılır.
- Dış OOS sonuçlarına bakıp ızgarayı, ölçütü veya pencereyi değiştirmek seçim yanlılığıdır: yeni bir deneme olarak sayılır ve ön kayıt gerekir.
- G2 sonrası "arama → doğrulama → replikasyon" (`reports/search_protocol.md`) bu yapının tek dış adımlı, basit sürümüdür.
- Uygulama: iç skor günlük Sharpe (std = 0 → 0), medyan, eşitlikte ilk sütun; aday getirileri sürekli koşunun dilimleridir; araç ayrıca seçim prosedürünü **rastgele seçime** karşı sınar (`nested.random_sharpes`, p = rotasyon-p formülü).

### 8.3 Purge / embargo / CPCV [YOK, koşullu]
- Kural tabanlı sinyallerde ileri getiri etiketi yoktur; sızıntıyı §7 nedensellik denetimi engeller. Purge/embargo gerekmez.
- **[YOK] gerekçesi:** purge/embargo/CPCV ileri getiri etiketi çakışmasını giderir; kural tabanlı sinyallerde etiket yok, sızıntıyı §7 nedensellik denetimi (geleceği bozunca geçmiş kararlar değişmez) engeller. Bilinen artık: CSCV ve nested yarıyıl bloklarında pozisyon blok sınırını aşar (komşu bloklar arasında seri bağımlılık; etkisi ölçülmedi, UNKNOWN).
- **Koşul:** ileri getiri etiketi kullanan ML modeli eklenirse: purge = eğitimde etiket aralığı test aralığıyla kesişen örnekler atılır;
  embargo = her test bloğundan sonra en uzun etiket ufku kadar (en az 1 gün) eğitim örneği atılır; Purged K-fold yalnızca model
  karşılaştırması için, kronolojik walk-forward'un yerine değil, ona ek olarak; CPCV ek sağlamlık incelemesi olarak yorumlanır.

### 8.4 Final test
Mühürlü dönem (≥ 2026-04-01, ~6 ay), G3, tek atış, yalnızca kullanıcı komutuyla (`tools/seal_holdout.py` / `open_holdout.py`).
6 ay kısa olduğu için edge'i kanıtlamaz; bariz çöküşü yakalar (K10).

### 8.5 Görülmüş veri uyarısı
Dev dönemi G2 ve aramada tamamen görüldü. Bu veride yapılan her yeni test, ön kayıtlı olsa da "görülmüş veride test"tir;
kanıt gücü sınırlıdır. Bu yüzden: (a) her test ön kayıtlı, (b) kümülatif deneme sayısı raporlanır, (c) gerçek doğrulama mühür ve
yeni veridir.

## 9. Null ve istatistik

### 9.1 Rotasyon null'ı [VAR]
- Sinyalin saatlik birim serisi (`ffill`, ısınma 0) dairesel kaydırılır: ofset = ⌊u × uzunluk⌋, u ~ U(0,05, 0,95).
- **Ortak ofset (birincil):** tüm semboller aynı u ile kayar; sembol-arası korelasyon korunur. Bağımsız ofset null varyansını küçümser (G2'de sd 1,3–2x küçük), yalnızca ek bilgi olarak raporlanır.
- Korunanlar: işlem sayısı, tutma süreleri, long/short oranı. Kopan: sinyal ile fiyat arasındaki zamanlama ilişkisi.
- Her çekiliş hakemle koşar (fee 10, slip 2). B ≥ 300 (p çözünürlüğü ~0,003).
- p = (1 + #{null brüt PnL ≥ gerçek brüt PnL}) / (B + 1), tek yönlü. Net PnL için de aynı şekilde raporlanır.
- **Sınır:** rotasyon, piyasa yönüne (beta) karşı kısmi kontrol sağlar (long/short oranı korunur), tam değil; bu yüzden ayrıca benchmark testi (K2).

### 9.2 Çoklu test düzeltmesi
- **Bonferroni [VAR]:** eşik 0,05 / N; düzeltilmiş p = min(1, p × N).
- **DSR [VAR]** (Bailey & López de Prado): günlük net getiri serisi r (sembol toplamı / toplam notional);
  SR = ort(r)/std(r), çarpıklık γ3, basıklık γ4, gözlem T;
  SR0 = std(denemelerin SR'leri) × [(1−γ)·Φ⁻¹(1 − 1/N) + γ·Φ⁻¹(1 − 1/(N·e))], γ = 0,5772;
  DSR = Φ( (SR − SR0)·√(T−1) / √(1 − γ3·SR + (γ4−1)/4·SR²) ). Eşik ≥ 0,95.
- **PSR [VAR]** (`stats.psr`): aynı formül, SR0 = 0 (ya da belirlenen eşik). `stats.dsr(r, trial_srs)`, `stats.sr0_from_trials`.
- **MinTRL [VAR, `stats.min_trl`; raporda]:** MinTRL = 1 + (1 − γ3·SR + (γ4−1)/4·SR²)·(z_α / (SR − SR*))². Normal getiri, SR* = 0, α = %5 için
  yaklaşık: yıllık SR 0,7 → ~5,5 yıl; 1,0 → ~2,7 yıl; 1,5 → ~1,2 yıl. Elimizde ~3 yıl OOS benzeri veri var: SR ≲ 1 kanıtlanamaz.
- **SPA [VAR]** (`stats.spa`, Hansen 2005; kendi uygulama, `arch` bağımlılığı eklenmedi): d_k = model − benchmark günlük getiri; ω̂ Newey–West (Bartlett, gecikme 20); stationary bootstrap (blok 20, B = 2000); p_lower / **p_consistent** / p_upper (p_upper = Reality Check). Test: elle hesaplı istatistik, p sıralaması, tohum, sinyalsiz/sinyalli sentetik. Gerçek veri: 88 yapılandırma, nakit ve al-tut benchmark (`reports/backtest_completion.md` madde 5).
- **StepM / MCS [YOK, koşullu]:** gerekçe — SPA "en az bir model üstün mü" sorar; hangi modellerin üstün olduğunu (StepM) ya da güvenilir alt kümeyi (MCS) ayıklamak aday listesi ister, aday çıkmadı. 7/24 arama (H4) çok aday üretirse eklenir.
- **PBO / CSCV [VAR]** (`stats.cscv`; ön kayıt S = 16, 12 870 bölme, metrik günlük Sharpe): IS-en-iyinin OOS'ta medyanın altına düşme olasılığı (λ ≤ 0); aile içi PBO ayrıca. Not: PBO sıra kalıcılığını ölçer, kârlılığı değil; aileler arası getiri farkı tüm-88 PBO'yu düşürür, bu yüzden aile içi PBO'yla birlikte okunur. Gerçek veri: 88 yapılandırma (`reports/backtest_completion.md` madde 5). Arama-tabanlı her rapor için kullanılır.

### 9.3 Block bootstrap [VAR] (`stats.stationary_bootstrap`, `stats.bootstrap_summary`)
- Stationary bootstrap (Politis–Romano), günlük net getiri, ortalama blok 20 gün, 2000 tekrar, sabit tohum.
- Çıktı: yıllık Sharpe %5/%50/%95, maks DD %50/%95, toplam getiri aralığı. K4 bu çıktıyla değerlendirilir. DD tanımı: toplamsal equity (sabit sermaye = 1, bileşik yok), tepe (başlangıç 0 dahil) − equity'nin en büyüğü.
- Blok uzunluğu duyarlılığı (10/20/40 gün) raporlanır, karar 20 günle verilir.

### 9.4 Benchmark [VAR] (`robust.buy_hold`, `stats.nw_alpha`)
- **Al-tut:** aynı evrende eşit notional long, aynı toplam notional, aynı hakemle (fee, slip, funding dahil), pencere başında al, sonunda kapat.
- **Alfa:** günlük r_strateji = a + b · r_al-tut + e; a'nın t istatistiği Newey–West (gecikme 5) ile. K2: t(a) ≥ 2 ve SR_strateji > SR_al-tut.
- Ayrıca "nakit" (sıfır) referansı her tabloda.

### Deneme ailesi ve çoklu test politikası (#14)
- **Ayrım:** `hypothesis_id` (ne sınanıyor), `parent_hypothesis` (hangi aileden türedi; yeni önkayıt geçmiş veri kullanımını sıfırlamaz), `selection_family` (seçimin yapıldığı küme), `control_role` (primary/secondary/negative_control/neutral_null/exploratory), `run_id`, `attempt`. Defter bunları `ledger.record(family=trial_policy.check_family_meta(...))` ile satırın `family` alanına yazar (doğrulama `scripts/trial_policy.py`'de); eski çağrılar değişmez. Ledger dışı keşif ve post-hoc seçimler bilgi geçmişinde sayılır.
- **N:** ham satır sayısı otomatik global N olmaz (5.091 betimsel kayıt kanıtlanmış bağımsız hipotez sayısı değildir; 9 uzman × 2 IC × 6 ufuk = 108 test keşif ailesidir, kart ailesi değildir). Karşılaştırılabilir ailede `scripts/trial_policy.family_report`: ortak takvimli getiriler, Sharpe dağılımı, deneme bağımlılığı. `n_eff_info` yalnız bilgidir; DSR eşiği N_eff/varyans ile ayarlanmaz.
- **DSR/PSR varsayımları:** `stats.dsr` docstring'i (ortak takvim, yalnız denenen aile, seri bağımlılık/örtüşen etiket ihmali).
- **p çözünürlüğü:** en küçük p = 1/(B+1). B=300 → 0,003322; 108 test Bonferroni eşiği 0,05/108 = 0,000463 bu tasarımda ulaşılamaz; sıfır exceedance için asgari B = 2.159 yalnız çözünürlük sınırıdır, güç/null geçerliliği kanıtı değildir. `trial_policy.check_resolution` koşudan ÖNCE yakalar; çözüm otomatik devasa fan-out değil, aileyi küçültmektir.
- **Sonraki dar deney:** `trial_policy.check_prereg` ana hipotezi, azami varyant sayısını, birincil ölçütü, çoklu test yöntemini (bonferroni/holm/single), B/güç/maliyet notunu, durma kuralını ve planın kaydedildiği commit'i sonuç görülmeden ister; hash'i rapora yazılır. Bu politika kapanmadan yeni uzman/grid/factory araması genişletilmez.
- **Repo defter envanteri** (`python scripts/trial_policy.py ledger` → `reports/trial_inventory_data/policy_inventory.json`; yalnız repo, Modal-yalnız satırlar ve ledger dışı keşif dahil değil): 46 dosya, 4.119 satır (3.247 hakem, 872 eleme), 2.964 benzersiz `config_hash` (1.155 fazla satır aynı config_hash'i paylaşıyor), 4.086 satırda config'te açık sembol kimliği yok, 4.119 satırın hepsi receipt'siz (`legacy_partial_provenance`), hiçbiri `invalid/failed` durumlu değil (eski kayıt biçimi). Bu sayımlar bağımsız hipotez sayısı değildir.
- Mevcut kartlar yerel/keşif kapsamıyla etiketlidir (carry_xs_card, signal_diagnostics, trial_inventory); carry NO_EDGE korunur.

### Rotasyon null'u ve IC bootstrap kalibrasyonu (#15)
Kaynak: `scripts/null_calibration.py` (yalnız sentetik; sayılar `reports/signal_diagnostics_data/null_calibration.json`; tohumlar sabit; seri koşu ~2 dk).
- **Estimand:** K1 rotasyon null'u KOŞULLU zamanlama testidir: uzman/bileşim, evren, parametreler ve aktiflik maskesi donmuş; "bu sabit sinyal serisinin zamanlaması şans mı?" sorulur. Varsayımlar: dairesel kayma sinyalin kendi zaman yapısını korur, getiriyle sıfır-edge altında değiştirilebilir (exchangeability) ve süreç yeterince durağan. Kayma takvim (haftanın günü), funding ve aktiflik ilişkisini bozar. Uzman/evren SEÇİMİNİ tekrarlamaz, bu yüzden mevcut koşullu p global araştırma sertifikası değildir.
- **Aktiflik kaybı (E07):** `exposure_diag` sıfır dolu dönemlerin kaydırılıp maske uygulanmasıyla aktif sıfır-olmayan hücre sayısının düştüğünü, brüt/net maruziyet, değişim sayısı, tutma süresi ve haftanın günü dağılımının değiştiğini ölçer (sentetik testte gösterildi). Bu, dolum sayısı ya da işlem korunumu kanıtı değildir.
- **Gerçek dev panelinde (EV1, `null_calibration.py --real`, `reports/signal_diagnostics_data/null_real_exposure.json`):** 9 sembol × 2.282 gün; gerçek F: 18.827 aktif sıfır-olmayan hücre, ort. brüt |F| toplamı 3,97, 17.418 değişim. K1 offsetlerinin 100'ü ile kaydırınca (mevcut aktiflik maskesiyle): aktif sıfır-olmayan hücre ort. 17.288 (min 17.211, max 17.868; −%8,2), brüt 3,64 (−%8,3), değişim ort. 16.006 (−%8,1), ort. sürekli sıfır-olmayan dizi uzunluğu 1.448 → 706 gün (bu tutma süresi değil, F'nin kesintisiz sıfır-olmayan kaldığı koşu uzunluğu). Yani null, gerçek sinyalden ~%8 daha az maruziyet/işlemle koşuyor: sonradan aktif olan sembollerin sıfır dolu dönemleri aktif hücrelere kayıyor. Son 40 gün × ilk 4 sembol alt panelinde (E07 benzeri) kayıp YOK (160/160; o pencerede geç aktif sembol yok): E07'deki 140→120 gerçek veride bu pencerede yeniden üretilmedi.
- **Negatif kontroller (önceden seçildi, hepsi raporlanır):** ortak-offset rotasyon (birincil, mevcut), sembol-başına bağımsız offset, blok karıştırma (ort. 20 gün). En iyi sonucu veren null sonradan seçilmez.
- **Bootstrap estimator (E08):** nokta tahmin = tam örnek Spearman; bootstrap'te TAM-ÖRNEK sıraları sabit tutulur (rank-then-resample). Replika-içi yeniden sıralı referansla aynı indekslerde karşılaştırma (3 tohum, T=300, S=6, B=300): SE oranı fixed/rerank 0,94–1,00, replika korelasyonu 0,986–0,993; değerler farklıdır (max |fark| ≈ 0,02) ama dağılım yakındır; yanlış-pozitif oranları iki estimator'da gürültü sınırları içinde aynıdır. Sabit-sıra yaklaşımı korundu ve bu şekilde gerekçelendi (gerekçe SE/yanlış-pozitif simülasyonudur, kuram kanıtı değil).
- **Yanlış-pozitif (sıfır-edge, AR(1) φ=0,9 tahmin, örtüşen h-gün etiket; iki yönlü p<0,05, nominal 0,05; 300 tekrar, Wilson %95):** h=1/blok 20: 0,093 [0,065–0,132]; h=10/blok 5: 0,187; h=10/blok 20: 0,133 [0,099–0,176]; h=40/blok 5: 0,270; h=40/blok 20: 0,147 [0,111–0,191]; h=40/blok 80: 0,217 [0,174–0,267]. Replika-içi sıralı: h=10: 0,160 [0,094–0,259], h=40: 0,213 [0,136–0,319] (75 tekrar). **Sonuç: bootstrap-SE'li normal p bu rejimde anti-muhafazakârdır (estimator seçiminden bağımsız; sorun bağımlılık kalibrasyonu: blok uzunluğu etiket örtüşmesinin ve tahmin kalıcılığının altında kalır); `signal_diag_stats.summarize` p'leri betimsel ölçüdür, sertifika değildir.** 40 günlük örtüşen etiket + ortalama blok 20 için ayrıca güvenilir bir kalibrasyon yoktur (blok 80'de bile düzelmedi; küçük T etkisi ayrıştırılmadı).
- **Seçim prosedürü null'u:** sıfır-edge 9 uzmandan en yüksek IC-TS'liyi seçmek: yalnız seçileni kaydıran koşullu rotasyon p'si yanlış-pozitif 0,30 [0,22–0,40]; tüm uzmanları aynı offsetle kaydırıp her kaydırmada yeniden max alan prosedür-düzeyi null 0,03 [0,01–0,08] (100 tekrar, nominal 0,05). Dar, dondurulmuş seçim prosedürü için bu null ayrıca kalibre edilir; mevcut koşullu p global araştırma sertifikası diye sunulmaz.
- **NO_EDGE korunur:** eşik/null değiştirilerek kurtarılmaz; bu bölüm mevcut kartların sonucunu değiştirmez, yalnız yorumlama sınırını yazar.

## 10. Sağlamlık test kataloğu

Her test: ne yapılır, ön kayıtta ne yazılır, hangi karta bağlı, N'ye girer mi, durum.

| Test | Prosedür (sabit) | Kart | N'ye girer | Durum |
|---|---|---|---|---|
| Null / placebo | §9.1 | K1 | Hayır | [VAR] |
| Maliyet stresi | Fee 4/9/10/11/16 × slip 2/6; ek: 1 bar gecikme (dolum 2. sonraki açılış; `Spec.delay=1`) | K3 | Hayır | [VAR] |
| Block bootstrap | §9.3 | K4 | Hayır | [VAR] |
| Parametre duyarlılığı | Seçilen her parametre ±%10 ve ±%20 (tamsayıya yuvarlanmış, tekrarlar atılır); tam ızgara ön kayıtta (`robust.neighbors`: tam kartezyen, seçilen hariç) | K5 | Hayır (seçim yapılmazsa) | [VAR] |
| Pencere / başlangıç | Yarıyıl pencereleri (§8.1) + başlangıç 0/1/2/3 ay kaydırma | K6 | Hayır | [VAR] (`robust.shift_windows`) |
| Çapraz varlık | Ön kayıtlı, kullanılmamış sembol kümesi (kural: aylık top-20'de ≥ 8 ay, evren dışı, ilk bar ≤ 2023-07-01, kesim yok); korele olduğu için tek başına kanıt değil | K7 | Hayır | [VAR] (replikasyon) |
| Ablasyon | Stop, boyutlama, filtre, piramitleme tek tek kapatılır; aynı seçim prosedürü | K8 | Evet (her varyant bir deneme) | [VAR: Turtle'da `turtle_book` bayrakları stop/pyramid/limits/fixed] |
| Rejim | Nedensel rejim: 200 günlük EMA'nın 30 günlük eğimi ve fiyatın EMA'ya göre konumu → boğa / ayı / yatay; BTC'ye göre tanımlanır, o an bilinen veriyle (`robust.regime`: etiket[d] ≤ d−1 verisi; eğim > 0 & EMA üstü = bull, eğim < 0 & EMA altı = bear, diğer = range) | K9 | Hayır | [VAR] |
| Tarihsel stres | 2022-05 LUNA, 2022-11 FTX, 2024-08 çöküşü, dev dönemindeki en büyük 3 likidasyon dalgası (veriden: eşit ağırlıklı sepetin en büyük günlük düşüşü; adlı pencereler dışı, ≥ 7 gün ara). Metrikler: pencere PnL, saatlik DD, stop/likidasyon sayısı, stop seviyesi aşma | Rapor | Hayır | [VAR] (`kepler/stress.py`; `reports/backtest_completion.md` madde 1) |
| İşlem sırası Monte Carlo | İşlem PnL'leri 5000 kez karıştırılır; DD ve en uzun kayıp serisi dağılımı; kill switch eşiğinin girdisi (kural: s* = 0,25/DD95; öneri = min(DD99(s*), 0,30)) | Rapor | Hayır | [VAR] (`stats.trade_mc`, `path_stats`, `kill_stats`; madde 2) |
| Kapasite | Her emrin notional'ı / o saatin quote hacmi ≤ %0,1; aşan emir sayısı raporlanır; karekök etki bindirmesi (Y = 1; duyarlılık 0,5/2); sermaye 500 / 10k / 100k | Rapor | Hayır | [VAR] (`kepler/capacity.py`; madde 3) |
| Sentetik senaryo | GBM + rejim değişimi + gap olayları | — | — | [YOK]: gerekçe — aday yok (NO_EDGE), sentetik veri edge'in varlığını değil yalnızca sistemin davranışını sınar; gerçek kriz pencereleri ayrı (Tarihsel stres). Aday çıkarsa yeniden değerlendirilir |
| Eleme–hakem uyumu | Aynı ızgara iki motorda; Spearman (genel ve aile içi) | §6.6 | Eleme satırları girer | [VAR] |

## 11. Başarı kartı (karar 2026-10-02; MISSION'daki G2 ölçütünü genişletir)

Başlık metriği: maliyet sonrası, OOS, yıllık Sharpe + DSR. Net PnL (USDT) yalnızca hesap raporu; yüzde getiri tek başına karar ölçütü değildir.

| # | Test | Geçme eşiği |
|---|---|---|
| K1 | Null / placebo | Ortak-ofset rotasyon null'ında (B ≥ 300) brüt PnL p ≤ 0,05/N **ve** DSR ≥ 0,95 |
| K2 | Benchmark | OOS Sharpe > eşit ağırlıklı al-tut Sharpe'ı **ve** alfa t ≥ 2 (Newey–West) |
| K3 | Ekonomik + maliyet stresi | OOS net Sharpe ≥ 1,0; net > 0 hem fee 16 + slip 6 bps'de hem 1 bar ek gecikmede |
| K4 | Risk (block bootstrap) | Planlanan boyutla maks DD ≤ %25; bootstrap DD %95 dilimi ≤ %30 |
| K5 | Parametre duyarlılığı | Komşu ızgaranın ≥ %70'i fee 10'da net > 0; komşu medyan Sharpe ≥ seçilenin yarısı |
| K6 | Pencere / başlangıç | Pencerelerin ≥ %60'ı net > 0; başlangıç 0/1/2/3 ay kaydırmada hepsi net > 0 |
| K7 | Çapraz varlık | Kullanılmamış sembol kümesinde fee 16'da net > 0 |
| K8 | Ablasyon | Her bileşen çıkarılınca OOS Sharpe düşmeli; düşmüyorsa bileşen atılır (MISSION kural 4) |
| K9 | Rejim | Üç rejimin en az ikisinde net ≥ 0; kazanç tek rejimden gelmemeli |
| K10 | Final (G3) | Mühürlü dönemde fee 16'da net > 0 |

**Karar:** K1–K9 geçerse **ADAY** → G3 (kullanıcı komutu). K1 veya K2 kalırsa **NO_EDGE**. K3–K9'dan biri kalırsa **ZAYIF** (canlıya gitmez).
Eşikler yargıdır, kanıtlanmış standart değildir; yalnızca ön kayıtla ve bir sonraki testten **önce** değiştirilebilir.

**Geçmiş sonuçlar bu kartla:** G2 kitap sinyalleri (kırpılmış): K1 kalıyor (en iyi p 0,06, DSR ≤ 0,67), K3 kalıyor (en iyi Sharpe 0,49) → NO_EDGE.
Arama + doğrulama + replikasyon: K1 kalıyor → NO_EDGE.
Ensemble v1 (`reports/ensemble.md`, 2020-04 → 2026-04): K1–K8 geçti (p 0,0033, DSR 0,999, Sharpe 1,45, alfa t 3,37, DD %9,7), K9 kalıyor (bull payı %105) → ZAYIF. 2020–21 replikasyonu (`reports/pre2022.md`): tam Turtle NO_EDGE; Blok B tsmom_14_1 ölçütü geçti.
Tam Turtle S1/S2 (Motor v2: N-boyutlama, 2N stop, piramit, birim sınırları; `reports/full_systems.md`): K1 kalıyor (p 0,026 / 0,060 N=12 eşiği 0,0042; DSR 0,52 / 0,36) → NO_EDGE; K2, K3, K4, K6, K9 da kalıyor.

## 12. Test senaryoları

### 12.1 Mevcut birim testleri [VAR] (`tests/`, 202 geçti, 1 atlandı: `KEPLER_NET=1` gerektiren gerçek ağ testi)
| Dosya | Test fonksiyonu | Kapsam |
|---|---|---|
| `test_referee.py` | 19 | long/short gidiş-dönüş, açık pozisyon değerleme, fee ve slippage ayrımı, lot yuvarlama, min notional (artıran engellenir, azaltan değil), NaN = tut, flip, funding (long öder/alır, short, mark kullanımı, sınır anı), likidasyon, Nautilus'un tek başına likide etmediği |
| `test_realistic.py` | 12 | sonraki-bar açılış dolumu, son bar dolmaz, boşlukta sonraki mevcut bar, çıkış maliyeti, next_open modunda funding sınırı, dolum barında likidasyon ve çifte fee yok, boşlukta funding, likidasyon sonrası işlem yok, evaluate'in gerçekçi olmayan Spec'i reddi, eşzamanlı defter yazarları |
| `test_liq_mark.py` | 7 | 10x senaryo, mark geçince likidasyon (last geçince değil), short tarafı, mark eksikse kline, LP ≈ 1/kaldıraç − mmr |
| `test_funding_settlement.py` | 6 | #10: E03 (funding sonrası marj ihlali likidasyon), hayatta kalan sınır (5 ödeme), sıfır-funding parity ve çift sayım yok, short alır, equity_scale funding'i görür, iki sembol ortak nakit akışı |
| `test_intents_reconcile.py` | 5 | #11: E04 blocked_minimum, lot no-op, niyet↔dolum izi, boşluk/boş saat funding mutabakatı, açık pozisyon çıkış değerlemesi, ayrışmanın yakalanması |
| `test_receipt.py` | 8 | #12: aynı girdi aynı kimlik; closure/config/üyelik/fiyat/funding/mark/kesim/paket kodu değişince kimlik değişir; köken sırsız; legacy işareti |
| `test_ledger_attempts.py` | 6 | #13: geçersiz/başarısız deneme kaydı, durumlar, retry/smoke, eşzamanlı job receipt + deterministik toplama, çelişkili duplicate, evaluate_book invalid/failed |
| `test_trial_policy.py` | 4 | #14: p çözünürlüğü (B=300 vs 108 test), önkayıt alanları, aile meta'sı (ledger), ortak takvimli aile raporu |
| `test_null_calibration.py` | 6 | #15: aktiflik kaybı teşhisi, replika-içi referans = nokta tahmin, sabit-sıra vs yeniden-sıra, yanlış-pozitif AA ve bağımlılık, seçim null'u, Wilson |
| `test_review_fixes.py` | 9 | funding aralıkları, NaN/ms sapması, fitil/NaN hacim, red/eksik funding deftere girmez, boşlukta likidasyon gap fiyatından |
| `test_trust.py` | 7 | nedensellik (sızdıran ve uzunluğa bağlı sinyal yakalanır), belirlenimlilik hash'i, pencereli = tam tape, flat = 0, rastgele ≈ −maliyet |
| `test_signals.py` | 11 | Turtle giriş/çıkış/flip, Donchian trend filtresi (350 gün EMA), aylık sinyal yerleşimi, dual momentum, carry ve nedensel funding birleşimi, tüm sinyaller nedensel ve |x| ≤ 1, kesitsel dolar-nötr, EMA trend |
| `test_ops.py` | 10 | işlem tablosu, saatlik PnL'nin hakem net'ini yeniden kurması, vol hedefleme (nedensel, tavanlı, bantlı, elle değer), kill switch, 4h/1d türetme, evaluate + risk, durum özeti |
| `test_tape_ledger.py` | 5 | UTC indeks, mühür reddi, hedef sözleşmesi, append-only defter, eleme sonuç yazamaz |
| `test_screen.py` | 3 | eleme kuralı = hakem kuralı, basit fixture'da eşleşme, her eleme deftere |
| `test_xcheck.py` | 1 | hakem = bağımsız muhasebe |
| `test_stops.py`, `test_portfolio.py`, `test_turtle.py`, `test_stats.py`, `test_stress.py`, `test_capacity.py`, `test_nested.py` | 8+11+14+16+2+2+4 | Motor v2 ve tamamlama araçları (§12.2–12.3) |
| `test_data.py`, `test_qc.py`, `test_universe_rules.py`, `test_seal.py`, `test_env.py`, `test_enqueue.py` | 7+7+3+6+3+3 | veri, kalite, evren, mühür, ortam, kuyruk |

Kural: beklenen değerler **testte elle hesaplanır**; çıktıyı kendisiyle karşılaştıran test sayılmaz.

### 12.2 Motor v2 testleri [VAR: 1–25 yazıldı; 1–8 tests/test_stops.py, 9–13 + 25 test_portfolio.py, 14–18 test_turtle.py, 19–24 test_stats.py] (her birinin beklenen değeri elle)
**Strateji stopu**
1. Long 100'den, stop 95; gövde L = 94, açılış 99 → dolum 95 − slip; PnL elle.
2. Gap: açılış 90 (stopun altında) → dolum 90 (açılış), 95 değil.
3. Short simetriği (stop yukarıda, gap yukarı).
4. Aynı barda giriş (açılış) ve stop (gövde) → iki dolum aynı barda.
5. Stop ve likidasyon aynı barda: stop LP'den yakınsa yalnızca stop; değilse likidasyon.
6. Stop sonrası aynı yönlü sinyal sürse de yeniden giriş yok; ters sinyalde giriş var.
7. Stop seviyesi nedensellik: geleceği bozunca geçmiş stop seviyeleri değişmez (`check_causal` genişletilmiş).
8. `stop = NaN` her yerde → sonuç mevcut hakemle birebir aynı.

**Portföy hakemi**
9. Tek sembol: portföy hakemi = `referee.run` (net, fills, funding birebir).
10. İki sembol, ortak sermaye 1000, her biri 600 notional, kaldıraç 1 → ikincinin artırıcı emri tavana göre orantılı küçülür; elle değer.
11. İki sembolde funding aynı anda: toplam = sembol funding'lerinin toplamı.
12. Bir sembol likide olunca diğeri açık kalır; bakiye elle.
13. Bağımsız koşu toplamı ile portföy sonucu, tavan bağlayıcı değilken eşit.

**Risk / boyut**
14. ATR(20) elle hesaplanmış fixture'da N ve birim büyüklüğü.
15. Piramitleme: +0,5N, +1N, +1,5N'de birim eklenir, 4'te durur.
16. Birim sınırları: korele grup 6'ya ulaşınca yeni birim reddedilir.
17. Boyutlu hedef capital × L_max'ı aşamaz.
18. Kill switch: equity %25 düşünce flat, sonra işlem yok.

**Değerlendirme araçları**
19. Rotasyon null'ı işlem sayısını ve long/short oranını korur (u sabit, elle).
20. p formülü: bilinen null dağılımında elle p.
21. DSR: bilinen SR, γ3, γ4, T, N için elle değer.
22. Block bootstrap: sabit tohumla tekrarlanabilir; blok uzunluğu 1'de iid bootstrap'e eşit dağılım.
23. Benchmark alfası: sentetik r_s = 0,001 + 0,5·r_bh + gürültü → a ≈ 0,001, b ≈ 0,5.
24. Rejim etiketi nedensel: geleceği bozunca geçmiş etiketler değişmez.
25. 1 bar gecikme modu: dolum 2. sonraki açılışta, elle.

### 12.3 Tamamlama araçları testleri [VAR] (beklenen değerler elle; `reports/backtest_completion.md`)
26. `stats.path_stats / trade_mc / kill_stats`: [3,−1,−2,2] → DD 3, zarar serisi 2, en kötü ardışık zarar 3; permütasyon toplamı korur; kill yolu kesilir (tests/test_stats.py).
27. `stats.cscv`: N = 2, S = 4, ortalama metriği: PBO = 2/6, λ = ±ln 2, IS-en-iyi OOS'ta zararda 1/6; eşitlikte PBO = 1.
28. `stats.nw_lrv / spa`: ω̂² = 2 (elle), T = √2; p_lower ≤ p_consistent ≤ p_upper; sinyalsiz gürültüde reddedilmez, sinyalli sütunda p ≈ 0; sabit sütunlar t = 0.
29. `stress.drop_days / window_stats / basket_return`: sepet düşüşü seçimi (ayrım + dışlama), pencere DD'si (tepe başlangıç dahil), stop kayması ve bar aşma payı, pencere başı brüt/net notional (tests/test_stress.py).
30. `capacity.fill_table / impact_cost / summary`: katılım 0,001, etki = ln(1,01)·√0,001·1000 = 0,31466; hacimsiz bar katılım 1; σ nedensel (tests/test_capacity.py).
31. `Spec.equity_scale`: kazançta +0,5 alım (660/120 = 5,5), kayıpta −0,5 satım (360/80 = 4,5), brüt tavan ölçeklenir; ölçeksiz kontrol (tests/test_portfolio.py).
32. `nested.sharpe / half_years / select / run / random_sharpes`: medyan ≠ ortalama, eşitlikte ilk sütun, OOS seçimi değiştirmez, tohum (tests/test_nested.py).

## 13. Çalıştırma ve raporlama

- Komutlar `AGENTS.md`'de (Modal). Ağır koşular `scripts/` altındaki işçilerle, `--procs` ile paralel.
- **Rapor şablonu** (`reports/<test>.md`): ilk cümle sonucu söyler (ADAY / ZAYIF / NO_EDGE ve hangi kart maddesinde kaldığı);
  ardından ön kayıt bağlantısı, kurulum (veri, evren, Spec, maliyet), K1–K10 tablosu, ana tablo (brüt, net @ fee 4/10/16, funding,
  p, Bonferroni p, Sharpe, DSR), maliyet ayrıştırması, zamansal dağılım, sembol dağılımı, sızıntı/hata taraması, UNKNOWN listesi,
  kümülatif deneme sayısı.
- Otomatik tablolar `reports/<test>_data/` altında (JSON + Markdown); defter `ledger/<test>/`.

## 14. Bilinen sınırlar ve UNKNOWN'lar

| Konu | Durum |
|---|---|
| Turtle pencereleri | Dev dönemindeki S1/S2 20/10, 55/20 ve ATR(20)'yi kripto takvim günü olarak kullandı; kitapta işlem günü (≈ ×7/5 takvim günü). Sadık sürüm S1c/S2c `reports/pre2022_protocol.md`'de ön kayıtlı |
| Slippage gerçek değeri | UNKNOWN; 2 bps alt sınır, 6 bps stres |
| Funding settlement anındaki dolumun funding'e dahil olup olmadığı | UNKNOWN; kabul: T'deki dolumlar settlement'tan sonra |
| Sembol kuralları (tick, lot, min notional, mmr kademeleri) | UNKNOWN; `fapi` bulut ortamından 451, sunucudan çekilmeli |
| Likidasyon ücreti | UNKNOWN; varsayım mmr × notional |
| MEXC fee (16 bps) ve MEXC–Binance fiyat farkı | UNKNOWN; canlıdan önce ölçülecek |
| Hayatta kalma yanlılığı | Evrenler bugünkü majörler; iyimser yön |
| Tek rejim | 2022–2026, çoğunlukla ayı sonrası boğa |
| Panel sinyallerinde nedensellik denetimi | `audit.check_causal_book` (tüm panel bozulur), tests/test_trust.py'de |
| Stop dolum kayması | UNKNOWN; hakem stopu seviyeden doldurur (gap hariç), slippage komisyon kalemi. Üst gösterge: stop dolum barının seviyeyi aşma payı ort. 50–230 bps, FTX'te maks 563 bps; PnL etkisi hesaplanmadı |
| Karekök etki katsayısı Y | UNKNOWN; Y = 1 birincil, 0,5/2 duyarlılık. Etki maliyeti 100k'da bile brüt PnL'nin %1–2'si; kapasiteyi belirleyen katılım payı (> %0,1) |
| İşlem sırası MC varsayımı | İşlem getirileri bağımsız varsayılır; gerçek ardışık zarar serisi MC %99'una eşit ya da üstünde (zarar kümelenmesi: S1 32 = MC %99'u, S2 38 > 32); işlem-seviyesi equity yalnızca gerçekleşmiş PnL (saatlik DD ≈ 2–2,5x), s* iyimser |
| MC DD tanımı | `kill_stats`/MC DD'si başlangıç sermayesine oranlı toplamsal; üretimdeki `risk.kill_switch` tepe-equity'ye oranlı (1 − eq/tepe): önerilen eşik ve yanlış-tetik olasılığı üretim tetiğiyle aynı olay değil (UNKNOWN) |
| SPA boyutu | Sentetik iid null'da SPA p'leri liberal (bağımsız incelemede n = 1096, K = 88: p_upper < 0,05 oranı ≈ %8; yöntemin kendisinden, blok-20 bootstrap + max); 0,05'e yakın p'ler sınırda okunur. Gerçek veri sonucu (p_consistent 0,11) zaten anlamlı değil |
| Kill switch eşiği | Planlanan %1 risk/birimde %25 eşik hafta içinde tetiklenir (tam Turtle S1 2022-04-11, S2 2022-05/08); ölçekli boyut (s* ≈ 0,16–0,17) önerisi test edilmedi |

## 15. Market state servisi ve uzman arayüzü [KISMEN: v0 kodda ve testli, Zone Fade'de bir kez gerçek veride kullanıldı] (tasarım 2026-10-02)

Amaç: her uzmanın kendi piyasa durumunu (market state) istediği zaman dilimlerinde (1h, 4h, 1d, 3d) veri katmanından almasını sağlamak. Uzman ihtiyacını beyan eder, servis hesaplar ve yalnızca karar anında bilinen veriyi verir. Mevcut sözleşme (§4: `book -> {sym: DataFrame[target, stop]}`) ve hakem değişmez. **Katalog baştan yazılmaz** (MISSION kural 4): bir özellik, ancak bir uzman onu istediğinde servise girer.

```
UZMAN                                         SERVİS (kepler/state.py)
StateSpec ──────────────────────────────►     build(data, specs)
  sym, views[tf, lookback, features],            1. tape.load (mühür sınırı kodda)
  context                                        2. zaman dilimine topla
MarketState ◄──────────────────────────────      3. özellikleri hesapla (nedensel)
  yalnızca istenen, yalnızca <= karar anı        4. karar anına hizala
                                                 5. önbellek (spec hash'i)
```

### 15.1 StateSpec (uzmanın beyanı)
`StateSpec = {sym, views: [View{tf ∈ {1h,4h,1d,3d}, lookback (bar), features: ["atr:14", "swing:5", "profile:180", "ret:7", ...]}], context: ["funding", "mark", "xs:<evren>"], id = içerik hash'i}`. `id` deftere yazılır (hangi state tanımıyla koşuldu).

### 15.2 MarketState (servisin çıktısı, karar anı t)
`as_of = t` (saatlik karar anı). Her view için: **tamamlanmış** barlar (kapanış ≤ t), istenen özellikler (ATR, oynaklık, getiri), `levels` (swing tepe/dip: fiyat, oluşma zamanı, dokunuş sayısı; genişletilmiş tasarım §15.10), `profile` (hacim profili: POC, VAH, VAL, HVN/LVN; lookback penceresi için), nedensel trend/rejim etiketi. İstenmeyen hiçbir şey hesaplanmaz.

### 15.3 Zaman dilimi kuralları (sözleşmenin kalbi)
| tf | bar sınırı (UTC) | tamamlanmış sayılma |
|---|---|---|
| 1h | her saat | kapanışta |
| 4h | 00, 04, 08, 12, 16, 20 | kapanışta |
| 1d | 00:00 | kapanışta |
| 3d | **sabit takvim çıpası**: gün_no = 1970-01-01'den gün sayısı; bar = gün_no ÷ 3 (tam bölüm); kayma yok | kapanışta |

**Kural:** t anındaki karar yalnızca kapanış zamanı ≤ t olan barları görür; oluşmakta olan (forming) bar servise girmez. Eksik bar sayısı her view'da raporlanır (sessiz boşluk yok). Servis yalnızca `tape.load` üzerinden okur: mühür sınırını aşamaz.

### 15.4 Uzman çıktısı: Candidate ve yaşam döngüsü
`expert(state) -> Candidate[]`; `Candidate = {expert_id, sym, side, zone [alt, üst], trigger (kural), stop (fiyat), target (fiyat), expiry (bar), id = hash}`.
Durum makinesi (deterministik): `AKTİF → (fiyat zone'a girince) İZLEMEDE → (tetik) POZİSYONDA → (hedef/stop/süre) KAPALI`; zone'a gelmeden `expiry` dolarsa `İPTAL`. Adaylar yönetici katmanından (boyut, risk, birim/portföy sınırları) geçip `book({sym: kl})` olarak hakeme gider: **hakem tarafı değişmez**.
Hakemde eksik olanlar: hedefte çıkış (take-profit) ve koşullu giriş. Tercih: sinyalle taklit (kapanışta hedefe ulaşıldıysa sonraki açılışta çık / tetik kapanışta görülürse sonraki açılışta gir; mevcut `next_open` dolumu, kötümser). Taklit yetersizse yalnızca **minimal** take-profit eki (reduce-only limit), elle hesaplı testlerle ve BACKTEST §6'ya yazılarak (MISSION kural 4 istisnası).

### 15.5 Kurallar ve testler (§12.2'ye eklenir)
1. **Nedensellik:** gelecek bar bozulunca geçmiş state'ler (ve adaylar) değişmez (`check_causal`'ın state sürümü).
2. **Belirlenimlilik:** aynı spec + aynı veri → aynı state hash'i.
3. **Pencere denkliği:** tam seride hesaplanan state = pencerede hesaplanan state (ısınma dahil).
4. **Toplama:** 3d çıpası elle hesaplanmış tarihlerde; tamamlanmamış bar servise girmez; eksik bar sayısı doğru.
5. **Özellikler elle hesaplı:** ATR, swing seviyesi (fractal), hacim profili (POC/VAH/VAL) küçük sentetik veride beklenen değer testte elle yazılır.
6. **Aday yaşam döngüsü:** zone'a girmeden iptal, tetik, stop, hedef, süre dolması; aynı bar içinde stop ve hedef: kötümser (önce stop).
7. **Önbellek:** aynı spec iki kez hesaplanmaz; farklı spec farklı hash.

### 15.6 Yer ve boyut
`kepler/state.py` (servis, ≲300 satır beklenir), `kepler/experts/` (uzmanlar: araştırma kodu), `tests/test_state.py`. Hakem+yapıştırma sayısına girmez (veri/araştırma tarafı); satır sayısı yine her raporda yazılır.

### 15.7 İlk sürüm sınırı
**Durum (v0 kodlandı):** `kepler/state.py` (servis; 3d çıpa, 1d ATR + impuls, 3d fractal swing, 4h karar ızgarası, lazy 1h hacim profili, önbellek), `kepler/experts/zone_fade.py` (uzman + yönetici + K1 rotasyonu), `tests/test_state.py` (§15.5'in 7 kuralı, elle hesaplı) ve `tests/test_zone_fade.py` (yönetici, hakem e2e). Hedefte çıkış ve koşullu giriş **sinyalle taklit edildi, hakemde değişiklik yok** (§15.4 tercihi yetti). §15.1'deki `lookback`/`context` v0'da yalnızca geçerlilik penceresi/boş; swing seviyesinde dokunuş sayısı v0'da yok (uzman istemedi). İlk uzmanın sonucu: `reports/zone_fade.md`.

v0 yalnızca ilk uzmanın (arz/talep bölgesi fade, `reports/` altındaki ön kayıt) istediklerini sunar: 3d ve 1d OHLC, ATR, swing seviyeleri, hacim profili, 4h/1h tetik verisi. Mevcut sinyallerin (trend, momentum, funding) bu servise taşınması şimdilik yapılmaz. Servis, ilk uzmanın sonucundan sonra genişler ya da atılır.

### 15.8 Yeni trader hattı: sorumluluk ve uygulama sınırı [PLANLI] (2026-10-03)

Gözlenmiş engel: §15.4 adaydan book'a geçişin sahibini ve bar sırasını tanımlamıyordu; Zone Fade ön kaydı koşulabilmek için bu adaptöre ihtiyaç duyuyor. Bu bölüm tasarımdır; bu oturumda strateji, state servisi, risk, hakem veya denetim kodu uygulanmaz. İstatistik eşikleri ve mevcut ön kayıt değişmez.

```text
tape.load (dev sınırı) → StateSpec / MarketState → uzman → Candidate
                                                   ↓
                     uzman yöneticisi: yaşam döngüsü + ön kayıtlı boyut/sınırlar
                                                   ↓
                       book({sym: kl}) → {sym: target, stop} (mevcut §4)
                                                   ↓
                        evaluate_book → tek hakem → fills / equity → defter
                                                   ↓
                               mevcut başarı kartı → rapor
```

**Yaşam döngüsünün sahibi:** araştırma tarafındaki uzman yöneticisi (ilk uygulamada Zone Fade book adaptörü), state servisi veya hakem değil. Servis yalnızca veriyi/özellikleri verir; uzman yalnızca bölge, tetik, stop ve hedef niyetini verir. Yönetici her tamamlanmış karar barında adayları deterministik olarak ilerletir, ön kayıtlı sermayeye göre boyutlandırır ve mevcut book sözleşmesini üretir. Adayın fiyat hedefi ile book'un USDT `target` alanı farklıdır; hedef fiyatına dokunmak adaptörde sonraki açılış için `target=0` niyetidir.

**Zone Fade sırası:** önce önceki pozisyonların stop/hedef/süre durumları ve açık adayların geçersizlik/expiry koşulları işlenir; sonra uygun yeni tetikler, ön kayıttaki alfabetik sıra ve en çok 4 pozisyon / aynı yönde 3 / brüt 3×sermaye sınırlarıyla ele alınır. Aday/pozisyon varken aynı sembolde ikinci aday yaratılmaz. Giriş niyeti `target=side×min(sermaye, 0,005×sermaye / (|tetik_kapanışı−stop|/tetik_kapanışı))` ve sabit stop olarak yazılır; tetikte POC ve stop sabitlenir. R:R, 30 günlük aday ve 40 günlük pozisyon süresi, 4h karar saatleri ve bütün özellik hesapları yalnızca `reports/zone_fade_protocol.md`'deki kurallardır.

**Karar ve dolum ayrı olaylardır:** tetik, `POZİSYONDA` gerçekleştiğinin kanıtı değildir. Geçici `GİRİŞ_BEKLİYOR` / `ÇIKIŞ_BEKLİYOR` yönetici kayıtları sonraki mevcut 1h açılışına kadar niyeti temsil eder. Adaptörün pozisyon kaydı bir yürütme taklididir; gerçek pozisyon/fill/fee/funding yalnızca hakem çıktısından doğrulanır. Gerçek fill fiyatı, miktarı, zamanı ve reddi yönetici günlüğüyle karşılaştırılmadan yaşam döngüsü [VAR] sayılmaz. Min-notional/lot/brüt tavan reddi veya küçültmesi taklitle uyuşmazsa sonuç geçerli trader yönetimi diye raporlanmaz; engel raporlanır. Bu sınır mevcut `book` fonksiyonunun hakem fills'ini bar bar geri alamamasından kaynaklanır.

**Stop/hedef:** koruyucu stop hakemin mevcut mark H/L ve tick kurallarıyla yürür (§6.4). Hedefe 4h low/high ile dokunma, o bar kapanınca çıkış niyeti; dolum sonraki açılıştır, hedef fiyatından limit dolumu iddiası yoktur. Aynı barda stop ve hedef varsa stop önceliklidir. Yönetici taklidi gerçek stop fill'iyle karşılaştırılır; stop sonrası eski hedefle tekrar giriş yoktur. İptal/çıkış kararı görünmeden book'ta geriye dönük pozisyon değiştirilmez. Dolumun stopun ötesine gap yaptığı durumda koruyucu emrin sonucu hakemindir; tetik anı risk hesabı gerçekleşmiş 0,5% zarar garantisi vermez.

**Henüz tanımsız olanlar:** genel çoklu-uzman aday çakışması, uzmanlara sermaye dağıtımı ve genel özellik kataloğu ikinci uzmanla birlikte, gözlenmiş engel varsa tanımlanır. EV1'in mevcut 0,6/0,2/0,2 tahmin birleşimi kendi ön kaydına aittir; Zone Fade ile birleşim kuralı değildir. Trailing stop, kısmi kâr alma, break-even ve stop taşıma bu ilk uzmanda yoktur; sonuç sonrası yeni ön kayıt gerektirir. `funding`, `mark` ve `xs` context adları genel bir servis hesabı tanımlamaz; ilk uzmanın istediği girdiler açık hesap/availability kuralı olmadan eklenmez. Genel rejim servisi tanımsızdır; mevcut değerlendirme etiketi `robust.regime` (§10) kendi kapsamıyla kalır.

**Uygulamadan önce gerekli doğrulama:** mevcut §15.5'e ek olarak tetik→sonraki açılış, giriş/çıkış bekleme, stop sonrası hedef, küçültülen/reddedilen emir, aynı anda fazla tetik, veri boşluğu ve gap giriş örneklerinde yönetici ile hakem fill'lerinin elle hesaplı karşılaştırması gerekir. Bunlar bu dokümantasyon/denetim oturumunda koşulmadı: atlandı. Mühürlü dönem, defter ve `evaluate()` değişmez. Hakem arayüzüne geri besleme veya TP eki gerekirse bu ayrı korumalı-kod işidir; bu tasarım uygulama izni değildir.

### 15.9 Gösterge kütüphanesi [VAR; state servisine henüz bağlı değil] (2026-10-03)

`kepler/indicators.py`: TradingView BTCUSDT "Teknik Analiz" sayfasındaki tüm satırlar: 11 osilatör (RSI 14, Stochastic %K 14/3/3, CCI 20, ADX 14, Awesome, Momentum 10, MACD 12/26, Stochastic RSI Fast 3/3/14/14, Williams %R 14, Bull Bear Power, Ultimate 7/14/28), 15 hareketli ortalama (EMA ve SMA 10/20/30/50/100/200, Ichimoku taban 9/26/52/26, VWMA 20, Hull 9) ve 5 pivot türü (Classic, Fibonacci, Camarilla, Woodie, DM). `technicals(df)` sayfadaki 26 sayısal satırı her bar için verir; `pivots` / `on_tf_pivots` pivotları; `on_tf(kl, tf, fn)` herhangi bir göstergeyi 1h/4h/1d/3d tamamlanmış barlarda hesaplayıp saatlik karar anına §15.3 kuralıyla hizalar.
Tanımlar Pine yerleşikleridir (EMA/RMA tohumu ilk n değerin SMA'sı, Wilder düzleştirme, `ta.dmi`). Sıfıra bölme NaN (RSI'da kayıp 0 ise 100). Pivot satırı i, bir önceki dönemin (i-1) HLC'sinden (Woodie: i. dönemin açılışı da) türer.
**Doğrulama (tests/test_indicators.py, 33 test):** (1) **TradingView ile birebir** (2026-10-03, BINANCE:BTCUSDT): aynı anda alınan 1000 mum ve TradingView tarama API'sinin değerleri (`tests/data/tradingview/`), 1d/4h/1h/1w: 11 osilatörün hepsi, SMA 10-200, EMA 10-50, Ichimoku taban, VWMA 20, Hull 9 ve beş pivot türü 1e-6 bağıl veya daha iyi eşleşiyor. RSI/ADX/MACD tohum yakınsaması nedeniyle 1e-5…5e-4. EMA 100/200'de küçük fark var ve nedeni gösterildi: tarama API'si bunları ~600 mumluk geçmişle hesaplıyor; aynı formülü son 600 muma uygulayınca 4h ve 1h'de fark < 1e-6 (tohum penceresi farkı, formül farkı değil). (2) Elle hesaplı örnekler ve Wilder RSI bilinen cevabı (70,53 / 66,32 / ...). (3) Formülden bağımsız saf-Python oracle'lar (1e-9). (4) Nedensellik: kesme ve gelecek bozma, tüm göstergeler ve pivotlar; `on_tf` hizalamasında oluşmakta olan bar sızmaz. (5) Referans kütüphaneler: TA-Lib (SMA, EMA, RSI, Momentum, Williams, CCI, Ultimate, Stochastic K/D, StochRSI, DI/ADX, MACD ısınma sonrası; TA-Lib'in DI/MACD tohumu farklı), `ta` (Awesome, Ichimoku), pandas-ta-classic (Hull, VWMA); kütüphane kurulu değilse atlanır: `uv run --with TA-Lib --with ta --with pandas-ta-classic pytest tests/test_indicators.py`. Gerçek BTCUSDT 1h (2025-12 → 2026-03) duman testi: tüm aralıklar geçerli.
**Pivot kuralları (TradingView ile doğrulandı):** pivotlar grafik zaman dilimine bağlı bir üst dönemden türer: **1h ve 4h grafikte önceki hafta (pazartesi 00:00 UTC), 1d grafikte önceki ay** (`TV_PIVOT_TF`, `on_tf_pivots(kl, "1w"|"1M", tür)`). **Classic** R3/S3 = P ± 2 (H − L) (ilk yazdığım formül H + 2 (P − L) idi ve TradingView'dan farklıydı; gerçek karşılaştırma yakaladı); **Woodie** R3/S3 = H + 2 (P − L) / L − 2 (H − P); Woodie P = (H + L + 2·dönem açılışı)/4. DM: önceki dönem O/C'ye bağlı X. **Doğrulanmadı:** 1w grafikte TradingView'in pivot dönemi (yıllık denedim, uymadı); ≥1h dışı zaman dilimleri; spot yerine USDT-M perp (TradingView'de BINANCE:BTCUSDT.P) üzerinde aynı karşılaştırma (formüller aynı, veri farklı).
**Kullanım kuralı:** göstergeler OHLCV'nin dönüşümleridir, yeni bilgi eklemez; serbest gösterge/parametre taraması yapılmaz (MISSION kural 11). Bir uzman, ön kayıtlı tek hipotezde birkaç göstergeyi kullanır; state servisine (`StateSpec.features`) ancak bir uzman istediğinde bağlanır (§15.8 genel katalog kuralı).

### 15.10 Seviye servisi (destek/direnç) ve seviye olay çalışması [PLANLI; kod yok] (tasarım 2026-10-03)

**Gözlenmiş engel:** state v0 seviye olarak yalnızca 3d onaylı swing fiyatını (`sw_hi/sw_lo`) ve hacim profilini (POC/VAH/VAL) sunuyor; dokunuş sayısı, kırılma, bölge, pivot ve diğer seviye türleri yok. Zone Fade (tek mekanik yorum) NO_EDGE verdi (165 işlem) ama bu, "seviye bilgi taşımıyor" mu "kural kötüydü" mü ayırmıyor. Kullanıcı: trader seviyeleri çok türden okuyor. İlke: **seviyenin tanımı servise, kullanımı uzmana aittir**; servis yorum yapmaz ve trade önermez; uzman bir seviye türünü ve parametresini ön kayıtla dondurur.

**Katman:** `StateSpec` sözleşmesine `levels: [LevelSpec{types, tf, param}]` eklenir; `AsOf.levels()` karar anında kapanıştan ±6 ATR içindeki seviyeleri, `AsOf.zones()` bölgeleri verir (lazy, spec hash'iyle önbellekli, yalnızca istenen tür hesaplanır). v0'daki swing ve profil tanımları **aynen** kullanılır (Zone Fade sonuçları geçerli kalır; testle sabitlenir).

**Seviye nesnesi (statik):** `Level = {id (içerik hash'i), type, tf, price, born_at, anchor_ts, touches, last_touch_ts, broken_at, flipped}`. `born_at` = seviyenin bilinir hale geldiği an (swing: sağdaki k bar kapanınca; pivot/önceki dönem: dönem açılışı; profil: günlük kapanış yenilemesi; yuvarlak: her zaman). Karar anı t < `born_at` ise seviye yoktur. Destek/direnç rolü saklanmaz, t'de kapanışa göre türetilir (`role_at(t)`: kapanışın altındaysa destek, üstündeyse direnç); kırılma sonrası rol değişir (`flipped`).

**Seviye türleri (v1, yalnızca bunlar; hepsi nesnel ve tanımlı):**
| tür | tanım |
|---|---|
| `swing` | fractal k = 2 (tf ∈ {4h, 1d, 3d}); tepe = high, dip = low; onay: sağdaki k bar kapanışı (state v0 ile aynı kod) |
| `pivot` | Classic / Fibonacci / Camarilla / Woodie / DM (`kepler/indicators.py::pivots`, TradingView ile doğrulandı); dönem: 1d grafik mantığıyla önceki ay, 1h/4h için önceki hafta (`TV_PIVOT_TF`); servis dönemi `period ∈ {1w, 1M}` olarak seçtirir |
| `prev_hl` | önceki dönemin (gün/hafta/ay) high, low, close'u |
| `profile` | W günlük (varsayılan 180) saatlik hacim profili: POC, VAH, VAL (Zone Fade ön kaydındaki tanım: 100 kutu, %70 değer alanı); günlük kapanışta yenilenir, kimliği yenileme gününü içerir |
| `round` | yuvarlak sayı: ana = 10^⌊log10 p⌋ katları (BTC 10 000), ara = ana / 2 (BTC 5 000); veriden türemez |

Dinamik çizgiler (hareketli ortalama, anchored VWAP), trend çizgisi, kanal ve formasyonlar **v1 dışı** [PLANLI v2]; yalnızca bir uzman veya olay çalışması ister ve yatay seviyeler bilgi taşıyorsa girer (çok parametreli ve öznel; MISSION kural 4).

**Dokunuş ve kırılma (karar ızgarası 4h; sabitler v1'de ayarlanmaz):** ATR = 1d ATR14 (t'de bilinen). Bir 4h bar seviyeye **dokunur**: [low, high] aralığı [L − 0,25 ATR, L + 0,25 ATR] bandıyla kesişir ve bar `born_at`'tan sonradır. Ardışık dokunan barlar tek dokunuş sayılır; yeni dokunuş için fiyatın banttan ≥ 0,5 ATR uzaklaşmış olması gerekir. **Kırıldı:** bir 4h bar seviyenin öte yanında > 0,5 ATR kapanır (`broken_at`; sonraki dokunuşlar `flipped` rolüyle sayılır). Sayılar ham tutulur; **tek bir "güç skoru" yok** (bileşik skor serbest parametredir).

**Bölge (confluence):** tüm türlerden seviyeler fiyata göre sıralanır; komşu fark ≤ 0,5 ATR ise aynı bölgeye zincirlenir. `Zone = {lo, hi, members, n_levels, n_types}`; `n_types ≥ 2` "çakışma" demektir. Ham sayılar verilir, uzman eşiği ön kayıtla seçer.

**Seviye olay çalışması (uzman yazmadan önce; karar: seviye bilgi taşıyor mu?).** Strateji değil, **keşif ölçümü** (hakem yok, dolum yok, kart yok). Soru: bir seviyeye dokunduktan sonra fiyatın hareketi, aynı yapıdaki ama yerinden oynatılmış çizgilere göre farklı mı?
- **Hipotezler (N = 7, deftere "seviye" ailesi olarak yazılır):** H1 `swing` 1d, H2 `swing` 3d, H3 `pivot` Classic (period 1w), H4 `prev_hl` (haftalık), H5 `profile` (180g POC/VAH/VAL), H6 `round` (ana), H7 çakışma bölgesi (`n_types ≥ 2`, tüm türler). Her biri tek yapılandırma, grid yok.
- **Veri:** genişletilmiş-9 (BTC ETH SOL XRP BNB DOGE ADA LINK AVAX), 2022-07-01 → 2026-04-01 (ısınma 2022-01'den), karar ızgarası 4h, mühür dokunulmaz.
- **Olay:** yeni dokunuş (yukarıdaki kural). **Yaklaşma yönü** σ = +1 (fiyat seviyeye aşağıdan geldi: direnç), −1 (yukarıdan: destek). **Tepki** r = −σ · (C(t+h) − C(t)) / ATR; t = dokunuş barının kapanışı, h = 6 bar (24 saat) sabit. r > 0 "geri dönüş", r < 0 "devam/kırılma". İkincil raporlar (karar dışı): P(r > 0), kırılma oranı, h ∈ {3, 12} duyarlılığı.
- **Null (yerinden oynatılmış çizgiler):** her replikasyonda b = 1…B (B = 300, `default_rng([0, b])`) sembol başına tek ortak kaydırma s_b ∈ ±U(0,75; 2,5) × ATR(`born_at`); aynı tür seviyeler L + s_b·ATR fiyatında, aynı `born_at`, **aynı dokunuş kodu** ile yeniden ölçülür. Yoğunluk ve aralık yapısı korunur, gerçek swing/pivot/POC hizası bozulur (yuvarlak sayılar nesnel olmayan fiyatlara kayar). Gerçek istatistik R̄ (olay başına ortalama r), placebo R̄_b dağılımıyla iki yönlü karşılaştırılır: p = (1 + #{|R̄_b − m| ≥ |R̄ − m|}) / (B + 1), m = placebo ortalaması. Güven aralığı haftalık blok bootstrap.
- **Karar (her hipotez ayrı; ölçüt koşudan önce yazılır):** "seviye bilgi taşıyor" ⇔ p ≤ 0,05 / 7 **ve** |R̄ − m| ≥ 0,10 ATR (BTC'de günlük ATR ≈ %2–3 olduğundan ≈ 20–30 bps, gidiş-dönüş maliyetinin 10 + 2 bps'inin üstü; eşik yargıdır) **ve** olay sayısı ≥ 300 (altı "YETERSİZ ÖRNEK"). Hiçbiri geçmezse: **"SEVİYE ANLAMSIZ (bu tanımlarla)"**, destek/direnç uzmanları rafa kalkar (yeni tanım = yeni ön kayıt). Biri geçerse: hangi tür ve hangi yönde (geri dönüş mü kırılma mı) bilinir; ilgili uzman ön kaydı bu bulgudan türetilir ve dev verisinin görülmüşlüğü (§8.5) belirtilir.
- **Ön kayıt:** `reports/levels_event_study_protocol.md` (2026-10-03, koddan önce commit'lendi; parametreler dondurulmuş, belirsizlikte kısıtlayıcı yorum). Bu bölümdeki özet ile ön kayıt çelişirse **ön kayıt kazanır**: ön kayıt ek olarak şunları sabitler: seviye geçerlilik/yaş (swing 180 gün), olay silahlanması ve yaklaşma yönü, placebo ölçeği κ (sembolün medyan ATR/kapanış'ı, L' = L·exp(±u·κ)), tutarlılık ve yapı uyumu koşulları, H7 bölge kimliği. Sonuçtan sonra tanım, eşik, h, band veya evren değişmez.

**Testler (§15.5'e ek, tümü elle hesaplı):** (1) nedensellik: gelecek bozulunca t öncesi seviyeler, dokunuşlar ve bölgeler değişmez; `born_at` onay anıdır; (2) küçük sentetik grafikte bilinen swing, 2 dokunuş, 1 kırılma, rol değişimi; (3) `swing` ve `profile` sayıları state v0 ile ve Zone Fade testleriyle birebir aynı; (4) `pivot` değerleri `indicators.pivots` ile birebir; (5) bölge zincirleme örneği (fiyatlar 100 / 100,4 / 101, ATR 1, bağ 0,5: 100 ve 100,4 aynı bölge, 101 ayrı); (6) belirlenimlilik (aynı spec + veri → aynı hash); (7) yuvarlak sayı kafesi (her fiyat için ana/ara katlar, BTC 85 000 → 80 000/90 000 ve 85 000); (8) placebo kayması dokunuş kodunu değiştirmez (yalnızca fiyat).
**Yer ve boyut:** `kepler/levels.py` (≲400 satır; `state.py` içinden çağrılır), `tests/test_levels.py`, `scripts/levels_event_study.py` (Modal), `tools/plot_levels.py` (seviyeleri ve bölgeleri fiyat grafiği üstüne **bağımlılıksız SVG** olarak çizer; kullanıcı kendi trader'ının çizdiğiyle gözle karşılaştırır). Satır sayıları her raporda yazılır.
**Sorumluluk:** tasarım Opus 5.5 + kullanıcı onayı (mimari değişiklik); kodlama Sonnet 5.5 high; bağımsız inceleme farklı model ailesinden. Hakem, denetim, risk ve mühür koduna dokunulmaz.
**UNKNOWN / sınırlar:** 0,25 / 0,5 ATR bandı, 0,5 ATR bölge bağı, h = 6, ±6 ATR penceresi ve 0,10 ATR eşiği yargıdır (ayarlanmaz; yalnızca ön kayıtla ve sonraki testten önce değişir). Kline'dan hesaplanan hacim profili yaklaşıktır. Evren bugünün majörleri (hayatta kalma yanlılığı). Dev dönemi görülmüş veridir.

## 16. Değişiklik kaydı

| Tarih | Değişiklik |
|---|---|
| 2026-10-03 | §15.10 seviye servisi (destek/direnç: 5 statik tür, dokunuş/kırılma, bölge) ve seviye olay çalışması tasarımı; ön kayıt `reports/levels_event_study_protocol.md` yazıldı (kod henüz yok) |
| 2026-10-03 | §15.9 gösterge kütüphanesi (`kepler/indicators.py`): TradingView teknik analiz sayfasının 11 osilatörü, 15 hareketli ortalaması ve 5 pivot türü; referans kütüphanelerle doğrulandı; state servisine bağlanmadı |
| 2026-10-03 | Ensemble katmanlara ayrıldı (sonuç birebir aynı, sentetik golden testle doğrulandı): `market_state.py`, `experts/{trend,xs_momentum,carry}.py`, `portfolio.py`; `ensemble.py` yalnızca kompozisyon; mimari kuralları `tests/test_architecture.py`, ARCHITECTURE v2 |
| 2026-10-03 | §15.8 yeni trader hattı: yaşam döngüsü sahibi, Zone Fade book adaptörü, niyet/fill ayrımı ve tanımsız çoklu uzman/trade yönetimi sınırları; yalnızca tasarım |
| 2026-10-02 | §15 Market state servisi ve uzman arayüzü (tasarım, [PLANLI]); ilk uzman: arz/talep bölgesi fade |
| 2026-10-02 | State servisi v0 (`kepler/state.py`) ve Zone Fade uzmanı (`kepler/experts/zone_fade.py`) kodlandı, testlendi; ön kayıtlı tek koşu `reports/zone_fade.md`; hakem değişmedi, kart değişmedi |
| 2026-10-02 | Ensemble v1 (`kepler/ensemble.py`: piyasa durumu → uzmanlar → aday → risk motoru) ön kayıtlı koşu: ZAYIF (K9); pre2022 raporu; kart değişmedi |
| 2026-10-02 | Tamamlama: tarihsel stres, işlem sırası MC, kapasite/karekök etki, `Spec.equity_scale` + portföy kill switch, PBO/CSCV, SPA, nested walk-forward kodlandı, testlendi ve gerçek veride kullanıldı (`reports/backtest_completion.md`); [PLANLI]/[KISMEN] kalmadı; yeni [YOK] gerekçeleri (limit emir, cross-margin, purge/CPCV, StepM/MCS, sentetik) yazıldı; `vol_target`/`aggregate`/`sharpe_series` gerçek veride kullanıldı (ön kayıt 4b) |
| 2026-10-02 | Tam Turtle koşusu: NO_EDGE (K1); kart değişmedi |
| 2026-10-02 | Bağımsız inceleme (Motor v2) 6 bulgu giderildi: `report.hourly_pnl` gövde dolumları, brüt tavan artıran hedefi azaltmaya çeviremez, funding'de gap stopu, kısmi stop dolumunda yeniden emir yok, turtle veri boşlukları + mark H/L + tick + iki geçiş; regresyon testleri |
| 2026-10-02 | Değerlendirme araçları (`stats.py`, `robust.py`): PSR/DSR/MinTRL, block bootstrap, NW alfa, al-tut, komşuluk, başlangıç kaydırma, nedensel rejim, rotasyon kaydırma, karar kuralı; testler madde 19–24 |
| 2026-10-02 | Motor v2 (stop, portföy hakemi, risk/boyut) kodlandı: §4 kitap sözleşmesi, §5.2, §6.4 (tek koruyucu emir, gap, halt), §6.5 (brüt tavan hakemde), Spec.delay/gross_cap; madde 1–18 ve 25 testleri |
| 2026-10-02 | v1: G0–G2 ve arama sonrası mevcut mimari, Motor v2 tasarımı, başarı kartı (MISSION'dan taşındı), test senaryoları |
