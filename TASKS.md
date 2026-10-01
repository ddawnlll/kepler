# KEPLER — TASKS (G0–G1, çekirdek)

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
| 2 | Sinyal | ☐ | Gerçek sinyal kodu yok (momentum, Donchian, funding yazılmadı); yalnızca test fixture'ları |
| 3 | Risk motoru | ☐ | Yok: vol hedefleme, boyutlama, kill switch yazılmadı. Hakemde yalnızca sabit `leverage=10` ve likidasyon benzetimi var. MISSION bunu G3 sonrasına bırakıyor; G2 için sabit boyut yeter |
| 4 | Backtest/hakem (yürütme+muhasebe) | ◐ | Nautilus hakem: long/short, fee, funding, slippage, likidasyon; elle hesaplı testler + BTC'de 3773 işlem eşleşti. Eksik: iyimser dolum (kapanıştan, slippage 0), tek sembol, portföy yok |
| 5 | Denetim | ◐ | Defter (ledger) ve nedensellik denetimi var, ama denetim deftere bağlı değil. Yok: walk-forward, null dağılımı, DSR, çoklu test düzeltmesi |
| 6 | Rapor | ◐ | Elle yazılan Markdown raporlar; otomatik rapor yok |
| 7 | Araştırma ajanı (7/24) | ☐ | Yalnızca talimat dosyaları (`factory/agents/`) |
| 8 | Canlı emir katmanı | ☐ | Yok; MEXC desteği doğrulanmadı |
| 9 | Güncelleme (15–20 dk) | ☐ | Yalnızca talimat |
| 10 | Sekreter/müdür (Hermes) | ◐ | Hermes sunucuda kurulmuş (başka oturumdan), sekreter talimatı henüz uygulanmadı; kuyruk kodu var (`factory/enqueue.py`) |

**Döngü** (sinyal → boyut → backtest → denetim → rapor) bugün uçtan uca **çalışmıyor**: yalnızca 1 → 4 gerçek veride, fixture sinyalle koştu.
**Sıradaki en kısa yol "edge var mı" cevabına:** hakem düzeltmesi (sonraki-bar dolum + slippage) → 3 sinyal → walk-forward + null + fee ızgarası (G2). Risk motoru bu cevap için gerekmiyor.

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
| G2 | G2 öncesi sertleştirme (devralma notundaki 6 madde) + sinyaller, null, fee duyarlılığı | 20 | ☐ | |
| F4 | Aşama 2: müdür + işçiler | (H4'te) | ☐ | G2 hazır olunca |
| H4 | 7/24 LLM arama vs rastgele | 15 | ☐ | |
| G3 | Mühür açılışı (tek atış, kullanıcı komutuyla) | 5 | ☐ | Mühür uzunluğu ve aracı gerçek veriyle çalıştırmak kullanıcıda |
| H5 | Küçük gerçek para | 7 | ☐ | |
