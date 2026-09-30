# KEPLER — TASKS (G0–G1, çekirdek)

Bu dosya görev planıdır, spec değil. Hedef, kapılar ve kurallar `MISSION.md`'de; sistem haritası
`ARCHITECTURE.md`'de. Çelişki olursa o iki belge kazanır; çelişkiyi raporla.

Yeni ajan: bu listeyi kendi görev sistemine aç, kendi planla, işi sırala ve böl. Aşağıdaki görevler
**ne** bitmeli ve **ne zaman bitti** sayılacağını söyler; **nasıl** yapacağın sana ait.
İlerlemeyi her görev bitince bu dosyadaki tabloda güncelle ve commit + push et (yüzdeler sana ait
tahmin; ama her "yapıldı" işareti için kanıt dosyası/test adı yaz). Başka bir ajan (Hermes) buradan
devralacak.

## İlerleme

| # | Görev | Ağırlık | Durum | Kanıt |
|---|---|---|---|---|
| A | Ortam, proje iskeleti, görev takibi | 5 | ☑ | Modal imajı (modal_app.py, uv.lock), `modal run modal_app.py --cmd 'pytest -q'`; tests/test_env.py 3 geçti |
| B1 | Binance arşiv istemcisi (liste, indirme, checksum) | 8 | ☑ | tests/test_data.py: bozuk sha256 reddi + yeniden indirme, idempotent, mühür koruması (SealedError), gerçek uçtan uca (KEPLER_NET=1, Modal) |
| B2 | Kalite kontrolü + manifest | 8 | ☐ | |
| B3 | Dönemsel hacim evreni + gerçek dev verisi | 8 | ☐ | |
| B4 | Mühür aracı | 4 | ☐ | |
| C1 | Hedef-pozisyon sözleşmesi + veri yükleme + deney defteri | 6 | ☐ | |
| C2 | Hakem motor (Nautilus; yedek Freqtrade) + bilinen-cevaplı testler | 25 | ☐ | |
| C3 | vectorbt eleme + eleme–hakem uyumu | 10 | ☐ | |
| C4 | Nedensellik, determinizm, pencere denkliği, negatif kontroller | 10 | ☐ | |
| C5 | Gerçek veride çapraz kontrol (hakem vs bağımsız elle hesap) | 5 | ☐ | |
| D | Kitaplar: PDF → metin (paralel, düşük öncelik) | 3 | ☐ | |
| E | Rapor + bağımsız inceleme | 8 | ☐ | |

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
sıçrama, funding aralığı (4 veya 8 saat), listeleme/delist tarihleri. Manifest: dosya hash'leri, aralıklar,
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

## Durma koşulları

- Çekirdek bitti (A–C5 + E) → dur, raporla.
- Kredi/limit doldu → ilerleme tablosunu güncelle, commit + push, dur.
- Gerçek engel (ör. anahtar yok, Modal erişimi yok) → engeli ilerleme tablosuna ve rapora yaz, yapabildiğine
  devam et; soru sorup bekleme.
