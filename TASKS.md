# KEPLER — TASKS (G0–G1, çekirdek)

Aktif iş: Seviye servisi ve olay çalışması tasarımı | durum: bitti (yalnızca tasarım; kod ve ön kayıt dosyası sırada) | protokol: BACKTEST.md §15.10

Bu dosya görev planıdır, spec değil. Hedef, kapılar ve kurallar `MISSION.md`'de; sistem haritası
`ARCHITECTURE.md`'de. Çelişki olursa o iki belge kazanır; çelişkiyi raporla.

Yeni ajan: bu listeyi kendi görev sistemine aç, kendi planla, işi sırala ve böl. Aşağıdaki görevler
**ne** bitmeli ve **ne zaman bitti** sayılacağını söyler; **nasıl** yapacağın sana ait.
İlerlemeyi her görev bitince bu dosyadaki tabloda güncelle ve commit + push et (yüzdeler sana ait
tahmin; ama her "yapıldı" işareti için kanıt dosyası/test adı yaz). Başka bir ajan (Hermes) buradan
devralacak.

## KEPLER TOPLAM DURUM (tek bakışta; ARCHITECTURE'daki 10 sistem)

Durum: ☑ çalışıyor ve testli, ◐ kısmen, ☐ yok. "Çalışıyor" = gerçek veride koşuldu veya testle kanıtlı.

| # | Sistem | Durum | Ne var / ne yok |
|---|---|---|---|
| 1 | Veri hattı | ☑ | 2022-01 → 2026-03, 179 sembol, QC raporu, sha256 manifest, mühür ayrı (G0) |
| 2 | Sinyal | ☑ | `kepler/signals.py`: 6 kitap sinyali (Turtle S1/S2, Donchian Trend, tsmom, dual momentum, carry→funding), parametreleri `reports/book_signals.md`'de veriye bakmadan sabit; tests/test_signals.py (12: elle hesaplı kural + nedensellik) |
| 3 | Risk motoru | ☑ | `kepler/risk.py`: vol hedefleme, kaldıraç tavanı, rebalance bandı, kill switch; `evaluate(size=, kill_dd=)`; N-boyutlama/piramit/birim sınırları (`turtle.py`); `Spec.equity_scale` (equity'ye göre ölçekleme) + portföy kill switch (`run_book(kill_dd=)`); tests/test_ops.py, test_turtle.py, test_portfolio.py (elle hesaplı). Gerçek veri: tam Turtle S1/S2 (6 deneme) + BTC `vol_target` duman testi (3 deneme), `reports/backtest_completion.md`. Parametreler ayarlanmadı |
| 4 | Backtest/hakem (yürütme+muhasebe) | ☑ | Nautilus hakem gerçekçi: sonraki-bar açılış dolumu, zorunlu slippage (`evaluate`), açık pozisyon çıkış maliyeti, likidasyon çifte sayımı yok, likidasyon sonrası hesap ölü (tests/test_realistic.py, test_referee.py). Tek sembol: portföy = sembol başına bağımsız koşu toplamı (G2'de) |
| 5 | Denetim | ☑ | `evaluate()` tek giriş: nedensellik denetimi → hakem → defter (ledger flock + `audit_causal` korkuluğu); walk-forward, rotasyon null'ı, DSR; PBO/CSCV (`stats.cscv`), SPA (`stats.spa`), nested walk-forward (`kepler/nested.py`), işlem sırası MC, tarihsel stres (`kepler/stress.py`), kapasite/karekök etki (`kepler/capacity.py`): hepsi gerçek veride kullanıldı (`reports/backtest_completion.md`). Yok (gerekçeli): StepM/MCS, purge/embargo/CPCV (etiket yok), sentetik senaryo, limit emir, cross-margin |
| 6 | Rapor | ☑ | `kepler/report.py` (işlem tablosu, saatlik PnL), `scripts/g2_report.py`, `scripts/search_report.py` (otomatik tablolar); özet raporlar elle |
| 7 | Araştırma ajanı (7/24) | ☐ | Yalnızca talimat dosyaları (`factory/agents/`) |
| 8 | Canlı emir katmanı | ☐ | Yok; MEXC desteği doğrulanmadı |
| 9 | Güncelleme (15–20 dk) | ◐ | `factory/status.py` deterministik özet (LLM yok; tests/test_ops.py); `state/STATUS.md` üretildi. Zamanlama (cron) + Telegram gönderimi F2'ye (sunucu) bağlı |
| 10 | Sekreter/müdür (Hermes) | ◐ | Hermes sunucuda kurulmuş (başka oturumdan), sekreter talimatı henüz uygulanmadı; kuyruk kodu var (`factory/enqueue.py`) |

**Döngü** (sinyal → boyut → backtest → denetim → rapor): boyut (risk motoru) hariç uçtan uca çalıştı (G2: `scripts/g2.py` + `g2_report.py`, Modal'de); rapor elle yazıldı.
**G2 cevabı: NO_EDGE** (kitap sinyalleri, 4–16 bps fee, gerçekçi hakem; en iyi turtle_s2 p=0,06 sert null'da, Bonferroni 0,72). Sıradaki: yeni hipotez (MISSION: aynı altyapıyla başka fikre geç). Hakem+yapıştırma 347 satır: tavan 450'ye çekildi (MISSION kural 7a, 2026-10-02).

## Zone Fade v1 + market state servisi v0 (2026-10-02; kullanıcı görevi): bitti, NO_EDGE (K1)

Ön kayıt `reports/zone_fade_protocol.md`, sonuç `reports/zone_fade.md` (+ `reports/zone_fade_data/`, `ledger/zone_fade/`). 165 işlem (örnek yeterli), K1 p = 0,371, DSR 0,706 → **NO_EDGE**; K2, K3, K5, K6, K9 da kalıyor; K4, K7, K8 geçiyor. Kümülatif deneme 4 118. ADAY değil: G3/mühür açılmadı.

| İş | Durum | Kanıt |
|---|---|---|
| State servisi v0 (BACKTEST §15) | ☑ testli | `kepler/state.py` (178 satır), `tests/test_state.py`: §15.5'in 7 kuralı elle hesaplı (ATR 41/14, impuls 5,75, swing onay tarihleri, profil POC 45/VAL 10/VAH 70, 3d çıpa 2022-01-01) |
| Zone Fade uzmanı + yönetici | ☑ testli | `kepler/experts/zone_fade.py` (193), `tests/test_zone_fade.py` (hakem e2e dahil); hedefte çıkış/koşullu giriş sinyalle taklit edildi (hakem değişmedi, taklit yetti) |
| Tek koşu + K1–K10 | ☑ | `scripts/zone_fade.py`, `scripts/zone_fade_report.py`; 39 test geçti |
| Bağımsız inceleme | ☑ | BLOCKER yok; bulgular `reports/zone_fade.md` içinde (giderilenler ve bilinçle giderilmeyenler) |

**Devralma notları (yeniden keşfetme):**
- Bu koşu Modal'de değil bir bulut konteynerinde yapıldı (Modal gRPC proxy'den geçmiyordu). Ham veri Binance arşivinden indirildi (`kepler.universe.build_symbol`, EXT-9 + K7 14 sembol), zip sha256'lar manifestle birebir; `universe.parquet` ve `usable.json` manifestten kuruldu. Komut: `PYTHONPATH=. python scripts/zone_fade.py --stage primary|second|k7|null --root <kök> --out <dizin>` (`--smoke` kısa boru hattı denemesi). Modal'de aynı komutlar `--root /data --out /data/zone_fade` ile koşar.
- Açık, sonucu etkileyebilecek ama koşulmayan: aday yeniden oluşumunu engelleyen varyant (inceleme MAJOR; yeni ön kayıt ve deneme gerekir). Ayar turu yapılmadı.
- Ekstra: `evaluate.py` `code_hash` state.py'yi kapsamıyor ve state `id`'si deftere yazılmıyor (hakem tarafı; kullanıcı onayı gerekir).
- State servisi v0: ilk uzman sonucuna göre "genişler ya da atılır" (BACKTEST §15.7): öneri tutulsun (küçük, testli), yeni uzman yeni ön kayıtla eklensin.

## Kararlar (2026-10-02, kullanıcı adına; MISSION'a işlendi)

1. PR #2 main'e birleşti (gerçekçi hakem, G2, arama). Benim dalımdaki paralel sertleştirme (`b8ec86e`, `claude/blissful-ptolemy-4kmtvf`) birleştirilmez, arşiv olarak dalda kalır.
2. G2 sonucu geçerli: kitap sinyallerinin kırpılmış sürümleri için `NO_EDGE`. Kapı ölçütü MISSION'da sabit: ortak-ofset rotasyon null'ı + Bonferroni (N = deneme sayısı) + fee 10 ve 16'da net > 0.
3. Risk motoru ve trade yönetimi stratejinin parçası: G3'ten önce kullanılır.
4. Satır tavanı: hakem+yapıştırma tavanı **kaldırıldı** (kullanıcı kararı 2026-10-02; önceki 300→450→600), sayı raporlanmaya devam eder; araştırma kodu tavansız ama testli ve kullanılıyor olmalı. Kullanılmayan `scripts/probe.py` silindi.
5. Aynı veride serbest arama yok (MISSION kural 11).
6. Mühürlü dönem (son 6 ay, ≥ 2026-04-01) **aday çıkmadıkça açılmaz** (kullanıcı kararı 2026-10-02; önceki "hiç kullanılmayacak" ifadesinin yerine). Aday (K1–K9) çıkarsa G3 yalnızca kullanıcı komutuyla, tek atış. MISSION'a işlendi.

## Motor v2 + tam sistem testi (hepsi tamam; kullanıcı görevi 2026-10-02)

Tasarım ve test senaryoları: `BACKTEST.md` §4 (stoplu sözleşme), §5.2, §6.4–6.5, §12.2.

Soru: kitaptaki tam Turtle sistemi (N-boyutlama, 2N stop, piramitleme, portföy birim sınırları), G2'deki kırpılmış sürümün yapamadığını yapıyor mu? Evet → eksik olan motordu; hayır → sorun sinyalde.

| Ad | İş | Bitti sayılması için | Durum |
|---|---|---|---|
| Stop | Strateji stopu: sinyal hedef + stop seviyesi döner; stop-market bar içinde (gap dahil) tetiklenir | Elle hesaplı stop testleri (gap, aynı bar giriş+stop, likidasyonla etkileşim) | ☑ tests/test_stops.py (8) |
| Portföy | Portföy hakemi: tek Nautilus motorunda çok sembol, ortak sermaye, toplam brüt pozisyon tavanı | Tek sembolde mevcut hakemle birebir aynı sonuç + elle hesaplı portföy testleri | ☑ tests/test_portfolio.py (6; denklik: eski hakemden sabit sayılar) |
| Risk | Risk motorunu bağla: N (ATR) boyutlama, piramitleme, birim sınırları (sembol/korele grup/toplam) | Testli; sabit boyuta karşı karşılaştırma raporlanır | ☑ tests/test_turtle.py (14); sabit boyuta karşı karşılaştırma `reports/full_systems.md` (g2_equiv) |
| Tam sistem | Tam Turtle S1/S2 ön kaydı (`reports/full_systems_protocol.md`, koddan önce commit) ve tek koşu | `reports/full_systems.md`: MISSION başarı kartıyla (K1–K9) sonuç | ☑ **NO_EDGE (K1)**; S1 p=0,026 DSR 0,52, S2 p=0,060 DSR 0,36 |

Kapsam dışı: haber, emir defteri, likidasyon akışı (veri yok), limit/maker emirler, diskresyoner kararlar.

## İlerleme (G0–G1 çekirdek görevleri)

| # | Görev | Ağırlık | Durum | Kanıt |
|---|---|---|---|---|
| A | Ortam, proje iskeleti, görev takibi | 5 | ☑ | Modal imajı (modal_app.py, uv.lock), `modal run modal_app.py --cmd 'pytest -q'`; tests/test_env.py 3 geçti |
| B1 | Binance arşiv istemcisi (liste, indirme, checksum) | 8 | ☑ | tests/test_data.py: bozuk sha256 reddi + yeniden indirme, idempotent, mühür koruması (SealedError), gerçek uçtan uca (KEPLER_NET=1, Modal) |
| B2 | Kalite kontrolü + manifest | 8 | ☑ | tests/test_qc.py+test_review_fixes.py: her kontrol sentetik bozuk veride tetikleniyor; gerçek veri: data_manifest/quality_report.md (0 ERROR, 695 WARN, 105 INFO, hiçbiri düzeltilmedi) |
| B3 | Dönemsel hacim evreni + gerçek dev verisi | 8 | ☑ | data_manifest/manifest.json (178 sembol, 51 ay × top20; emtia/stable sıralamadan önce çıkarıldı, kline~mark ayrışma kesimi 28 sembol); son bar 2026-03-31 23:00; mühür ayı indirilmedi (tests/test_data.py::test_sealed_period_is_never_fetched, tests/test_universe_rules.py) |
| B4 | Mühür aracı | 4 | ☑ | tests/test_seal.py: sentetik şifrele→aç birebir, yanlış özel anahtar açamaz, bozulmuş şifreli metin reddedilir, seal aracında özel anahtar yolu yok (5 test) |
| C1 | Hedef-pozisyon sözleşmesi + veri yükleme + deney defteri | 6 | ☑ | kepler/tape.py + kepler/ledger.py; tests/test_tape_ledger.py (5): sözleşme doğrulama, mühür sınırı reddi, append-only defter, DuckDB sorgu, eleme result yazamaz |
| C2 | Hakem motor (Nautilus; yedek Freqtrade) + bilinen-cevaplı testler | 25 | ☑ | tests/test_referee.py (26) + test_liq_mark.py (7: 10x, mark-tetikli) + test_review_fixes.py: elle hesap; likidasyon MARK H/L ile tetiklenir (yalnızca last geçince likide olmaz); test_nautilus_alone_does_not_liquidate. Sapma kullanıcı onaylı: hakem Nautilus + likidasyon yapıştırması (MISSION'da) |
| C3 | vectorbt eleme + eleme–hakem uyumu | 10 | ☑ | reports/screen_vs_referee.md: Spearman 1,000 (n=16; ızgara fee-baskın, zayıf kanıt); ledger/g1_ledger.jsonl 80 kayıt (eleme+hakem); tests/test_screen.py |
| C4 | Nedensellik, determinizm, pencere denkliği, negatif kontroller | 10 | ☑ | tests/test_trust.py (7): nedensellik (nedensel geçer; sızdıran sinyal assert_causal'da AssertionError [120,200,280,360] — elle doğrulandı), determinizm hash, pencere=tam tape (funding sınırı dahil), flat=0, rastgele=brüt~0/net<0 |
| C5 | Gerçek veride çapraz kontrol (hakem vs bağımsız elle hesap) | 5 | ☑ | reports/xcheck_btc.md: BTCUSDT 3773 işlem eşleşti, |net fark| maks 0,00207 USDT, funding birebir; tests/test_xcheck.py |
| D | Kitaplar: PDF → metin (paralel, düşük öncelik) | 3 | ☑ | books_text/ (125 metin) + books_text/QUALITY.md; kaynaklar PDF değil zaten düz metindi (0 PDF, sayfa bilgisi yok); 2 kitap bayraklı; scripts/books_quality.py |
| E | Rapor + bağımsız inceleme | 8 | ☑ | reports/g0_g1.md; bağımsız inceleme (ayrı bağlam) bulguları raporda; 89 test yeşil |

Toplam 100. **Çekirdek = A–C5 + E.** D paralel ve çekirdeği bekletmez.

## Bu oturumda doğrulanmış olgular (yeniden keşfetme; ama değişmiş olabilir, kontrol et)

- `data.binance.vision` erişilebilirdi (HTTP 200). `fapi.binance.com` 451 (coğrafi engel); ihtiyaç yok.
- Sembol ve dosya listesi için S3 uç noktası çalıştı:
  `https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/monthly/klines/`
  (XML `ListBucketResult`, sayfalama `marker` ile; `data.binance.vision.s3.amazonaws.com` sertifika hatası verdi).
- Aylık dosyalar ve her birinin `.CHECKSUM` dosyası (sha256 + dosya adı):
  - `data/futures/um/monthly/klines/{SYM}/1h/{SYM}-1h-YYYY-MM.zip` (CSV, başlık satırlı)
  - `data/futures/um/monthly/markPriceKlines/{SYM}/1h/{SYM}-1h-YYYY-MM.zip` (**aynı dosya adı**: ayrı dizinde sakla; `volume` alanı 0)
  - `data/futures/um/monthly/fundingRate/{SYM}/{SYM}-fundingRate-YYYY-MM.zip`
    (sütunlar: `calc_time, funding_interval_hours, last_funding_rate`)
- Bulut denemesinde: `uv` 0.8.17, Python 3.12 mevcuttu; `uv sync` ile `vectorbt==1.1.1` ve
  `nautilus_trader==2.0.0rc5` Python 3.12'de kuruldu (pandas 3.0.6, numpy 2.5.3, duckdb 1.5.6).
  Nautilus Python ≥3.12 ister (3.11'de sessizce eski sürüme düşüyordu).
- Kendi ortamında (yerel / Modal) bunların hangisinin geçerli olduğunu yoklayarak öğren.

## Görevler

### A. Ortam, iskelet, görev takibi (5)
Python 3.12 + `uv` + kilit dosyası; testler tek komutla çalışır (CI yok). Bu dosyadaki görevleri kendi
görev sistemine aç. Yerel bilgisayar ve Modal ikisi de kullanılabilir; ağır indirme/koşum için hangisinin
uygun olduğuna sen karar ver (Modal'ı kendin kur ve dene). Ham veri git'e girmez; kod, manifest ve
raporlar girer. Ortam silinebilir: indirme idempotent ve devam ettirilebilir olsun, sık commit + push.
**Bitti:** temiz klonda tek komutla ortam kurulur ve boş test paketi çalışır.

### B1. Binance arşiv istemcisi (8)
Sembol/ay listesi, aylık klines + mark price klines + funding indirme, sha256 doğrulama (bozuk dosya
reddedilir, yeniden indirilir), idempotent, devam ettirilebilir, hata/deneme yönetimi.
**Bitti:** küçük gerçek bir örnekte (1–2 sembol, birkaç ay) uçtan uca çalışıyor; bozuk checksum testi var.

### B2. Kalite kontrolü + manifest (8)
Boşluk, yinelenen/bozuk zaman damgası, UTC, tutarsız mum (high<low, open/close dışı vb.), anormal
sıçrama, funding aralığı (1/2/4/8 saat — G1'de düzeltildi: gerçek veride 99 sembol 8 saat dışı kullanıyor), listeleme/delist tarihleri. Manifest: dosya hash'leri, aralıklar,
sembol listesi, ay bazında evren üyeliği, **dev / mühürlü dönem sınırı**. Kalite raporu eksik/şüpheli veriyi
açıkça listeler, sessizce düzeltmez.
**Bitti:** bilerek bozulmuş sentetik veriyle her kontrol tetikleniyor (test); gerçek veride rapor üretiyor.

### B3. Dönemsel hacim evreni + gerçek dev verisi (8)
Her ay o ayın en likit 10–20 USDT-M perp'i (quote volume), delist ve yeni kontratlar dahil (survivorship
düzeltmesi). ≥3–4 yıl saatlik klines, mark, funding: Parquet + DuckDB. **Yalnızca bugünden 6 ay öncesine
kadar (dev dönemi) indirilir; son 6 ay (mühürlü) bu görevde gerçek veriyle hiç indirilmez ve açılmaz.**
**Bitti:** dev dönemi indi, manifest + kalite raporu var, evren üyeliği aylık olarak kayıtlı.

### B4. Mühür aracı (4)
`tools/seal_holdout.py`: mühürlü dönem verisini yalnızca **genel anahtarla** şifreler (özel anahtar ajanda
olmaz, hiçbir ortam değişkenine veya dosyaya girmez). Açma betiği ayrı; ikisi sentetik veriyle test edilir.
Gerçek veriyle çalıştırmayı kullanıcı yapacak; sen çalıştırma.
**Bitti:** sentetik veriyle şifrele → aç → birebir aynı; özel anahtar olmadan açılamıyor (test).

### C1. Hedef-pozisyon sözleşmesi + veri yükleme + deney defteri (6)
Sinyal, tape'ten hedef pozisyon serisi (long/short/flat + büyüklük; bar başına değişebilir) üreten saf
fonksiyondur; iki motor aynı seriyi oynatır. Tape'i Parquet/DuckDB'den yükle. Deney defteri: append-only
JSONL (hipotez, config/kod/veri hash'i, deneme sayısı), DuckDB ile sorgulanır.
**Bitti:** sözleşme kod + testle sabit; defter yazılıp sorgulanıyor.

### C2. Hakem motor + bilinen-cevaplı testler (25)
Sonuç deftere **yalnızca hakem motordan** girer. Birincil: NautilusTrader. Geçemezse Freqtrade (geçemediğini
gösteren bir testle belgele). Elle hesaplanmış senaryolarla birebir örtüşme: long; short; 8 saatlik funding
sınırını aşan tutma (pozitif ve negatif oran); sınır anında açma/kapama (Binance'in resmi kuralını belgeden
bul ve testle sabitle); taker fee (gidiş-dönüş 4 / 9 / 10 / 11 / 16 bps); slippage (bps); min notional ve
lot adımı; yön çevirme; kaldıraçlı likidasyon; NaN tutma.
**Bitti:** tüm senaryolar elle hesapla birebir; her birinin beklenen değeri testte elle yazılı (çıktıyı
kendisiyle karşılaştıran test sayılmaz).

### C3. vectorbt eleme + eleme–hakem uyumu (10)
vectorbt yalnızca hızlı filtre; sonuç sayılmaz ve deftere yazılmaz. Küçük bir konfigürasyon ızgarasında
eleme ile hakem sıralama korelasyonunu ölç ve raporla (eşik koyma; öneri ≥0,8, doğrulanmadı). Elemede
koşulan her konfigürasyon deftere ve deneme sayacına girer.
**Bitti:** korelasyon ölçülüp raporlandı; eleme konfigürasyonları deftere yazılıyor.

### C4. Güven testleri (10)
Nedensellik (gelecek bozulunca geçmiş kararlar değişmez; bilerek lookahead sızdıran sinyal yakalanır),
determinizm (aynı girdi → aynı hash), tam/pencereli tape denkliği (funding sınırı dahil), negatif
kontroller (flat ≈ 0, rastgele sinyal ≈ −maliyet).
**Bitti:** testler yeşil; sızdıran sinyal testi gerçekten kırmızıya düşüyor (kontrol et).

### C5. Gerçek veride çapraz kontrol (5)
Tek sembol, basit sinyal: hakem ile bağımsız elle hesap arasındaki işlem başına net fark.
**Bitti:** fark raporlandı ve açıklandı.

### D. Kitaplar: PDF → metin (3, paralel)
Yerel `books/` klasörü (~160 MB, **yalnızca yerelde**, bulutta yok) içindeki PDF'leri metne çevir. Metni
repoya koy (`books_text/`; repo özel kalmalı, telif); PDF'lerin kendisi git'e girmez (`.gitignore`). Taranmış
(OCR gereken) PDF varsa işaretle, çekirdeği bekletme. Ağır işler için Modal kullanılabilir.
**Bitti:** her PDF için metin dosyası + bir kalite notu (sayfa sayısı, boş/bozuk sayfa oranı).

### E. Rapor + bağımsız inceleme (8)
`reports/g0_g1.md` (≤2 sayfa), ilk cümle sonucu söylesin: "G0 geçti/bloklu, G1 geçti/şu testte kaldı".
Kırmızı test kırmızı yazılır, atlanan "atlandı", doğrulanmamış rakam "doğrulanmadı". Kod yazıldıktan sonra
ayrı bir bağlamda (yalnızca kod ve testler verilerek) **bir** bağımsız inceleme yaptır; bulguları rapora ekle.
Kendi kodun (yapıştırma kodu dahil) ≲300 satır: sayıyı raporla; aşarsan dur ve kullanıcıya sor.
**Bitti:** rapor + inceleme bulguları commit'li.

## Çekirdek bitince (kapsam dışı; yalnızca kredi/zaman kalırsa, G2'ye geçme)

Yalnızca G0–G1'i destekleyen, sinyal içermeyen işler:
- Defterden **deterministik** durum özeti üreten küçük betik (deneme sayısı, en iyi adaylar, null'a göre durum,
  hatalar; LLM yok) — 15–20 dk'lık güncelleme katmanının girdisi.
- İlerleme tablosunun son hali ve "devralma notu": bir sonraki ajan (Hermes) nereden devam eder.

**G2'ye (sinyaller, null, fee duyarlılığı) geçme.** Kapı sonunda dur ve raporla.

## Devralma notu (Hermes / sonraki ajan) — çekirdek bitti, G2'ye geçilmedi

**Durum:** G0 geçti, G1 geçti (99 test yeşil, 0 atlanan; gerçek ağ testi için `KEPLER_NET=1`). Sonuç ve açık bulgular: `reports/g0_g1.md`. **Dal: yalnızca `main`** (G0–G1 işi `49c3354` merge commit'iyle `main`'de; `g0-g1` ve `claude/blissful-ptolemy-4kmtvf` birleştirilip silindi). Yeni iş için `main`'den dal aç.

**Nerede ne var**
- Her şey Modal'de çalışır: `modal run modal_app.py --cmd "pytest -q"` (gerçek ağ testi: `KEPLER_NET=1 pytest tests/test_data.py`). Yerel `.venv` boş; yerelde proje kodu koşulmuyor.
- Veri: Modal Volume `kepler-data:/tape/{klines,markPriceKlines,fundingRate}/SYM.parquet` + `universe.parquet`. Ham zip'ler konteyner diskinde (`/tmp/kepler_raw`), kalıcı değil; manifest `data_manifest/manifest.json` zip sha256'larını taşır. Yeniden kurmak: `python -m kepler.universe --stage rank|universe|build --shard i/12` (12 paralel `modal run --detach`; tek konteyner ≈10 dosya/sn, konteyner sayısıyla ölçekleniyor), sonra `python -m kepler.qc --root /data --out /data/manifest`. Yalnızca ≤ 2026-03 indirilir (`kepler/data.py::DEV_END`).
- Hakem: `kepler/referee.py::run(kl, target, Spec, funding, mark)`; sözleşme `kepler/tape.py` başlığında. Sonuç deftere yalnızca `ledger.record(source="referee")` ile; eleme `kepler/screen.py` (defter zorunlu).
- Mühür: `tools/seal_holdout.py` (genel anahtar) / `tools/open_holdout.py` (kullanıcı). **Gerçek veriyle kullanıcı çalıştıracak**; ajan çalıştırmaz.
- Defter: `ledger/g1_ledger.jsonl` (fixture ızgarası; 112 kayıt = 16 eleme + 16 hakem × yeniden koşular; append-only olduğu için tekrarlar silinmez, deneme sayacına girer). G2 denemeleri ayrı dosyaya.
- Veri notu: evren 178 sembol (emtia/stable sıralamadan önce çıkarıldı). Kuralla çıkarılan semboller (XAU, XAG, PAXG…) Volume'da eski Parquet olarak duruyor ama manifestte/evrende yok; kullanma.

**Kullanıcı kararları (işlendi):** hakem = Nautilus + mark-tetikli likidasyon yapıştırması (MISSION'da); kural 7 iki sayıya bölündü (hakem+yapıştırma ≲300: 285; araçlar ≲500: 434); evren kuralı sabitlendi (emtia/stable/endeks sıralamadan önce çıkar, `EXCLUDE_BASES`; kline~mark ayrışma kesimi). Hâlâ kullanıcıda: mühür uzunluğu (6 ay, 2026-04-01 sınırı), mühür aracını gerçek veriyle ÇALIŞTIRMAK (özel anahtar ajanda/ortamda olmamalı), funding settlement anı kuralının Binance resmi SSS'inden teyidi (UNKNOWN; mark fiyatı kullanımı ve dinamik aralık geliştirici belgesinden KNOWN).

**G2'nin ilk adımı:** eleme↔hakem uyumunu fee-baskın olmayan geniş bir ızgarayla yeniden ölç (Spearman 1,000/n=16 anlamsız). **G2'den önce yapılacaklar (inceleme bulgularından):** sonraki-bar dolum modu ve zorunlu slippage; açık pozisyon çıkış maliyeti; likidasyon çifte sayım; `audit.assert_causal`/`check_target`'ı tek `evaluate()` girişine bağlamak; defter için dosya kilidi. Evren kullanımı: `tape.load` kesimi otomatik uygular, aylık üyelik için `tape.membership(root)`.

**Dikkat:** funding aralığı 1/2/4/8 saat olabilir (99 sembol 8 saat dışı); referee her aralıkta çalışır. 500 USD'lik hesap yüksek devirli sinyalde iflas eder → `n_rejected>0` koşular geçersiz.

## Durma koşulları

- Çekirdek bitti (A–C5 + E) → dur, raporla.
- Kredi/limit doldu → ilerleme tablosunu güncelle, commit + push, dur.
- Gerçek engel (ör. anahtar yok, Modal erişimi yok) → engeli ilerleme tablosuna ve rapora yaz, yapabildiğine
  devam et; soru sorup bekleme.

# Fabrika (7/24 işletme) ve sonraki kapılar

Ağırlıklar kaba tahmindir (G0–G1 çekirdeği bunun 25'i). Durum: ☑ bitti, ◐ kısmen, ☐ başlanmadı.

| # | Görev | Ağırlık | Durum | Kanıt / not |
|---|---|---|---|---|
| F1 | Repo tarafı: kuyruk (`factory/enqueue.py`), ajan talimatları (`factory/agents/`), `AGENTS.md`/`CLAUDE.md`, Türkçe komut test seti, kurulum özeti, mimari bölümü | 10 | ☑ | tests/test_enqueue.py (5); `factory/commands_tr.yaml` henüz bir modelle koşulmadı |
| F2 | Kurulum: VPS, Hermes, Telegram, anahtarlar, yazma sınırı, `state` dalı push'u | 15 | ☐ | Kullanıcıdan gerekenler `factory/README.md`'de; hiçbiri doğrulanmadı |
| F3 | Aşama 1 çalışıyor: sekreter + güncelleme ajanı, salt okunur; test seti 10/10 | (F2'de) | ☐ | |
| G2 | G2 öncesi sertleştirme (devralma notundaki 6 madde) + sinyaller, null, fee duyarlılığı | 20 | ☑ | **Sonuç: NO_EDGE** (`reports/g2.md`; sinyaller `reports/book_signals.md`; 767 hakem kaydı `ledger/g2/`; tablolar `reports/g2_data/`). 130 test yeşil. G3 açılmadı (aday yok) |
| F4 | Aşama 2: müdür + işçiler | (H4'te) | ☐ | G2 hazır olunca |
| H4 | 7/24 LLM arama vs rastgele | 15 | ☐ | |
| G3 | Mühür açılışı (tek atış, kullanıcı komutuyla) | 5 | ☐ | Mühür uzunluğu ve aracı gerçek veriyle çalıştırmak kullanıcıda |
| H5 | Küçük gerçek para | 7 | ☐ | |


## G2 devralma notu (güncel)
- **Durum:** hakem gerçekçi (next_open, slippage ≥1 bps zorunlu, çıkış maliyeti, likidasyon çifte sayım yok, likidasyon sonrası hesap ölü); `kepler/evaluate.py` tek giriş (denetim→hakem→defter; ledger flock + `audit_causal` korkuluğu — kendi beyan eden bayrak, güvenlik değil); `kepler/signals.py` 6 sinyal. G2 = **NO_EDGE** (`reports/g2.md`). Mühür açılmadı, G3 yok.
- **Yeniden koşmak:** `modal run modal_app.py --cmd "python scripts/g2.py --job turtle_s2 --b 300 --out /data/g2"` (ve `--common` null için), sonra `python scripts/g2_report.py /data/g2`. 7 iş paralel ~12 dk. İşler: turtle_s1 turtle_s2 donchian_trend tsmom carry_funding dual_mom_5 dual_mom_9. Not: `modal run` için `pip install 'modal[api-proxy-support]'` gerekebilir (proxy altında).
- **Açık/atlanan:** 4h/1d türetme yapılmadı; kitap stopları/boyutlama yok; inceleme bulguları 8 (gap'te stop dolum fiyatı, doğrulanmadı), 9 (reddedilen koşular deneme sayacına girmiyor), `audit_causal` bayrağı elle yazılabilir; `scripts/g1_real.py` bayrağı elle True yazıyor (fixture). Hakem+yapıştırma 347 satır (MISSION 7a ≲300): kullanıcı karar versin.


## Arama sonrası durum (kullanıcı beklenen işler dışında her şey bitti)
- **Yapıldı:** G2 (NO_EDGE), geniş arama + dev-içi doğrulama (`reports/search.md`: aday yok), risk motoru, otomatik rapor/durum, 4h/1d türetme (`tape.aggregate`), eleme–hakem uyumu ölçümü (0,871, n=88). 141 test yeşil.
- **Kullanıcı/dış girdi gerektirdiği için YAPILAMAYAN:** F2/F3 (VPS, Hermes, Telegram, anahtarlar; `factory/README.md` "Senden gerekenler"), H4 (7/24 LLM arama; sağlayıcı anahtarı + F2), G3 (mühür açılışı yalnızca kullanıcı komutu + özel anahtar; aday da yok), H5 (gerçek para), MEXC emir katmanı/MEXC farkı (karar verilmedi), mühür kaynağı sağlaması (inceleme 33; mühür aracına dokunulmadı).
- **"Pozitif backtest" hedefi:** üretilmedi. Doğrulama dönemi tek atış tüketildi; aynı veriyle daha fazla arama yanlış pozitif üretir (bkz. `reports/search.md` dürüstlük notu).
- **Replikasyon (tek atış):** kullanılmamış 14 majörde aile-seçilmiş 6 yapılandırma: trend/momentum aileleri net pozitif (fee 16'da da), brüt p 0,047–0,106, Bonferroni ≥0,28 → ADAY yok (`reports/search.md`). Yön tutarlı bir hipotez; G3 için aday dondurulmadı (kriter sağlanmadı). Karar kullanıcıda: bu hipotez için G3 (mühür tek atış) açılsın mı? (xs_mom 7g dolar-nötr en temiz: beta'dan arınmış, p=0,047 ham.) Mühür dokunulmadı.


## Motor v2 devralma notu (2026-10-02)
- **Hakem+yapıştırma satırı** (grep -cvE '^\s*(#.*)?$', referee+screen+tape+ledger+audit+evaluate): G2 sonunda 347 (tape 41, evaluate 31); şimdi **467** (referee 234, screen 24, tape 48 [aggregate +7], ledger 45, audit 40, evaluate 76). Tavan 450'yi aşıldı (+17); kullanıcı tavanı 600'e çıkardı (karar 2026-10-02). Artış nedenleri: çok sembollü adaptör + stop + brüt tavan (referee +52), `evaluate_book` + `_realistic` (evaluate +40), `check_causal_book` (audit +14).
- Mevcut `evaluate`/`check_causal` tek sembol API'si korundu (aynı çağrı, aynı kesim noktaları).
- **Bağımsız inceleme (stop/portföy/risk, ayrı bağlamda, 1 kez):** 6 bulgu, hepsi giderildi ve regresyon testli: (1 YÜKSEK) `report.hourly_pnl` bar içi (stop/likidasyon) dolumları atıyordu → portföy kill switch yanlış tetiklenirdi; (2) brüt tavan artıran hedefi satışa çeviriyordu; (3) turtle veri boşluklarında durum ayrışıyordu; (4) gap stopu funding'i siliyordu; (5) kısmi stop dolumunda reddedilen yeniden emir; (6) taklit stop kline H/L + ham seviye kullanıyordu (hakem mark H/L + tick) + alfabetik sıra yanlılığı (iki geçişe çevrildi).
- **Tam Turtle sonucu:** tam Turtle S1/S2 = NO_EDGE (K1; ayrıntı `reports/full_systems.md`). Yeniden koşmak: `modal run modal_app.py --cmd "python scripts/full_systems.py --stage primary|robust|k7 --out /data/full"` ve `--stage null --null-from a --null-to b` (5 paralel konteyner), sonra `PYTHONPATH=. python scripts/full_systems_report.py <dizin> reports/full_systems_data ledger`. Ham JSON `reports/full_systems_data/`, defterler `ledger/full_systems/` (attempt1 = çöken ilk koşu 10 satır; run2 = yeniden koşu 10 satır; 2 deneme ruin nedeniyle deftere yazılamaz).
- **Açık:** hakem+yapıştırma 467 ≤ 600 (tavan 600'e çıkarıldı); equity-ölçekli boyutlama, kill switch kartı, tarihsel stres/MC/kapasite/nested WF/PBO (BACKTEST §10 [PLANLI]) yapılmadı; K10/G3 dokunulmadı.


## BACKTEST tamamlama devralma notu (2026-10-02)
- **Yapıldı (hepsi ön kayıtlı, Modal'de koşuldu, testli):** tarihsel stres, işlem sırası MC + kill switch önerisi, kapasite + karekök etki (500/10k/100k), risk motoru (equity_scale + portföy kill switch; 6 deneme) + BTC `vol_target` duman testi (3 deneme), PBO/CSCV + SPA (88 yapılandırma), nested walk-forward (792 hakem satırı). Ön kayıtlar: `reports/backtest_completion_protocol.md`, `reports/nested_wf_protocol.md`. Sonuç: `reports/backtest_completion.md`; tablolar/ham JSON `reports/backtest_completion_data/`; defterler `ledger/backtest_completion/`. **BACKTEST.md'de [PLANLI]/[KISMEN] kalmadı.** Bağımsız inceleme (tek, ayrı bağlam) yapıldı, bulgular giderildi/belgelendi; 202 test yeşil, 1 atlandı.
- **Yeniden koşmak:** `modal run modal_app.py --cmd "python scripts/completion.py --stage base|capacity|risk|misc|pbo --out /data/completion"`; nested: `--stage nested --family <aile>` (6 aile paralel) sonra `--stage nested_report`; tablo: `python scripts/completion_report.py reports/backtest_completion_data`. Not: Modal log çıktısı Nautilus gürültüsü nedeniyle satır düşürür; sonuçlar `/data/completion/*.json`'da (`modal volume get kepler-data completion/<dosya> .`).
- **Hakem+yapıştırma satırı:** 473 (referee 240: +6 `equity_scale`/`equity()`); tavan kaldırıldı (kullanıcı kararı), sayı raporlanır.
- **Yeni deneme sayısı:** önceki 3 311 satır + risk 6 + misc 3 + nested 792 + ölçekli kill 4 = **4 116** (ölçekli kill: `reports/scaled_kill_protocol.md`; sonuç: öneri iyimser, S2'de kill 2025-08-02 tetiklendi).
- **Açık / öneri (yapılmadı):** bkz. `reports/backtest_completion.md` "Öneri".


## 2020–2021 replikasyonu (pre2022; kullanıcı görevi 2026-10-02; ön kayıt `reports/pre2022_protocol.md`, N = 10)
Durum (adım adım güncellenir; dal `claude/serene-carson-tvrcs8`, main'e push yok):
- ☑ `kepler/universe.py` parametreleştirildi (`--start/--rank-start/--end/--root`; varsayılanlar aynı; veri/QC/mühür araçları (b) 434 → 439 satır, ≲500 altında). Test: 203 geçti, 1 atlandı (Modal).
- ☑ veri indirme (`/data/pre2022`; arşivde 2019 ayları yok, veri 2020-01 → 2021-12, 66 sembol; ayrıntı protokol sonu "Koşu notu (veri)") · ☑ QC (`data_manifest/manifest_pre2022.json`, `quality_report_pre2022.md`: 0 ERROR, 227 WARN, kesim yok) · ☐ Blok A · ☐ Blok B · ☐ rapor `reports/pre2022.md`
Yeniden koşmak / ayrıntılar işler bitince buraya yazılır.


## Ensemble v1 devralma notu (2026-10-02)
- **pre2022 (2020–21) bitti:** Blok A tam Turtle NO_EDGE (K1/K2); Blok B `tsmom_14_1` ölçütü geçti (p 0,0066). Rapor `reports/pre2022.md` (teşhis dahil), tablolar `reports/pre2022_data/` (`scripts/pre2022_report.py`).
- **Ensemble v1** (ön kayıt `reports/ensemble_protocol.md`): **ZAYIF**, K1–K8 geçti, K9 kaldı (bull payı %105). Rapor `reports/ensemble.md`, tablolar `reports/ensemble_data/`, defter `ledger/ensemble/`. Yeniden koşmak: `python scripts/ensemble.py --stage primary|k7|null [--null-from a --null-to b] --out /data/ensemble`, sonra `PYTHONPATH=. python scripts/ensemble_report.py <dizin> reports/ensemble_data ledger`. 217 test yeşil, 1 atlandı.
- **Karar kullanıcıda:** (a) K9 için yeni ön kayıtlı sürüm, (b) ZAYIF'ı kabul, (c) K9 eşiği (yalnızca sonraki testten önce). Mühür açılmadı (aday yok). Kümülatif deneme 4 117.


## Denetim devralma notu (2026-10-03)
- Dal: `codex/kepler-audits-20261003` (güncel main `5e93e12` tabanından); mimari yalnız BACKTEST §15.8'e yazıldı ve `70b5971` ile push edildi. Korunan kodda değişiklik yok.
- Kullanıcı çalışma penceresi: 3 Ekim 2026 01:45–09:45 Europe/Istanbul. Saatlik devam ve 09:45 kapanış kontrolü kaydedildi. Bir sonraki çalışma mevcut koşuyu kontrol eder, tekrar başlatmaz.
- Sıra: A → B → C. A Modal `kepler-data` Volume'unu salt okunur tarar; /data'da 2531 Parquet (şema kontrolü tamamlandı). ≥2026-04-01 zamanları olan dosyada fiyat sütunları okunmaz. Token veya mühür anahtarı dosyaya yazılmaz.
- Devralmada mevcut A sonucu için `/tmp/kepler_data_audit_result.json` ve devam eden Modal sandbox `sb-epmSR4xi0Q4CHqrGQuuk5x` kontrol edilir. Geçici bağlantı betiği `/tmp/modal_http_transport.py`, SDK `/tmp/modal-legacy/bin/python`; bunlar çalışma ortamı araçlarıdır, repoya girmez. A tamamlandı: `reports/data_audit.md` + `data_audit_data/` (2531/2531 dosya, veri riskleri kırmızı); koşu bitti, yeniden başlatma.
- Her rapor tamamlanınca TASKS ve rapor commit/push; engel varsa engelli raporla, sıradakine geç. Hakem, denetim, risk, mühür, ledger ve evaluate değiştirilmez. C'nin test dosyası yalnız scratchpad'e yazılabilir.

- İş B: `reports/account_reality.md`; EV1 $500 hedef hesabı bitti. Güncel MEXC kuralları/hesap ücreti ve funding SSS doğrulaması engelli (proxy CONNECT 403); tüm semboller doğrulanmadı, C'ye geçildi.

- İş C tamamlandı: `reports/trial_inventory.md`; repo4117/Modal5434 satır, 1317 fark. Volume flock iki turda da iki exclusive lock'u aynı anda verdi (kırmızı), yerel kontrol yeşil. Test yalnız scratchpad. A/B/C ilk geçişi tamamlandı; 09:45 kapanışına kadar yalnız çözülmüş engel/yeni kanıt varsa rapor güncellenir, aynı koşu tekrar başlatılmaz.

## Denetim pencere kapanışı — 2026-10-03 09:45 Europe/Istanbul

Kapanış kontrolü: 2026-10-03 09:50:11 +0300. Pencere 01:45–09:45; bu kayıt kontrolün gerçek saatini taşır. İlk A/B/C koşuları tamamlandıktan sonra aynı denetimler yeniden başlatılmadı. Son kontrolde workspace/GitHub/Modal erişimi başarılı; mevcut A sandbox çıkış kodu 0.

| İş | İşin kapanışı | Renk | Kanıt |
|---|---|---|---|
| A | Tamamlandı: 2531/2531 Parquet; okunamayan/atlanan dosya 0 | kırmızı | reports/data_audit.md; data_audit_data/files.csv, findings.json, summary.json, time_checks.json |
| B | Hesap tamam; güncel MEXC tick/lot/minimum/fee/funding doğrulaması engelli (proxy CONNECT 403); doğrulanmadı | kırmızı | reports/account_reality.md; account_reality_data/sizing.json, sources.json, symbol_rules.csv |
| C | Tamamlandı: repo4117/Modal5434 defter satırı; flock iki turda konteynerler arasında dışlama sağlamadı | kırmızı | reports/trial_inventory.md; trial_inventory_data/ledger_reconciliation.csv, flock.json, integrity.json |

Mühür/anahtar/seal aracı **atlandı** (yasak); proje suite'i **atlandı** (üretim kodu değişmedi). Resmi delist teyidi, gerçek MEXC uygunluğu ve Zone Fade gerçekleşmiş aday sayısı **atlandı / doğrulanmadı**; ayrıntı raporlarda. Üç raporun renkleri canlı uygunluk onayı değildir.

Kapanış kanıtı: reports/audit_closure.json (rapor/kanıt SHA256'ları, korunan kaynak/defter denklik kontrolü, erişim ve gerçek kontrol saati). Saatlik devam görevi tamamlanmış/devre dışı, sonraki koşu yok. Yeni strateji/hakem/ledger koşusu 0; mühür açılmadı.

## Gösterge kütüphanesi (2026-10-03, kullanıcı isteği)
`kepler/indicators.py` + `tests/test_indicators.py` (33 test; referans testleri `uv run --with TA-Lib --with ta --with pandas-ta-classic pytest tests/test_indicators.py` ile koşar). TradingView teknik analiz sayfasının 11 osilatörü, 15 hareketli ortalaması, 5 pivot türü; ayrıntı ve doğrulama kapsamı `BACKTEST.md` §15.9. **State servisine bağlı değil**; sıradaki uzmanın ön kaydı hangi göstergeyi istiyorsa o bağlanır. TradingView ile birebir doğrulandı (BINANCE:BTCUSDT 1d/4h/1h/1w, 2026-10-03; `tests/data/tradingview/`); ayrıntı ve sınırlar BACKTEST §15.9.

## Seviye servisi (destek/direnç) ve olay çalışması (2026-10-03, kullanıcı isteği; yalnızca tasarım)
Tasarım `BACKTEST.md` §15.10. Sıra: (1) `reports/levels_event_study_protocol.md` ön kaydı (parametreler §15.10'daki değerlerle donuk, koddan önce commit), (2) `kepler/levels.py` + `tests/test_levels.py` (8 test, elle hesaplı), (3) `scripts/levels_event_study.py` ile tek koşu (N = 7), (4) `tools/plot_levels.py` SVG çıktısı. Sonuç "SEVİYE ANLAMSIZ" ise destek/direnç uzmanları rafa kalkar. Kodlama Sonnet 5.5 high, bağımsız inceleme farklı aileden; hakem/denetim/risk/mühür koduna dokunulmaz.
