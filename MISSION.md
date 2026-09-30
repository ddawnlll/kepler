# KEPLER — MISSION (v2, 2026-09-30)

## Soru

500 USD sermayeyle kripto perpetual piyasasında (long + short), maliyet (fee, funding,
slippage) sonrası, görülmemiş veride pozitif ve güvenilir bir edge var mı?
Cevap "yok" ise sonuç `NO_EDGE` / `NO_DEPLOY` olarak raporlanır. Bu başarısızlık değil,
geçerli bir sonuçtur.

## Hedef

Hesabı büyütmek. Ama dürüst cevap, kâr iddiasından önce gelir: kanıtlanmamış edge
canlıya gitmez.

## Sabit girdiler (kullanıcı kararları)

| Konu | Karar |
|---|---|
| Sermaye | 500 USD; kanıt gelirse artırılır |
| Araştırma verisi | Binance USDT-M, yalnızca ücretsiz (klines, funding, mark) |
| Canlı işlem | MEXC (Binance → MEXC farkı aday çıkınca ölçülür) |
| Evren | Top 10–20 major |
| Yön | Long + short |
| Tempo | Swing ağırlıklı, uzun vadeye açık (fee nedeniyle) |
| Drawdown toleransı | %20–30 |
| Canlı bot | Tam otonom (geliştirme ajanları değil, bkz. kurallar) |
| Hipotez kaynağı | Okunmuş trading kitapları |
| Emir tipi | Önce taker; maker ayrı hipotez |
| Negatif sonuç | Aynı altyapıyla başka fikre geç; baştan başlama yok |
| Çalışma ortamı | Modal. Hiçbir bileşen belirli bir ajana/ortama bağlı olmaz (Claude cloud, Hermes vb. aynı repo ve komutlarla çalışır) |
| Bütçe (G0–G1) | ~4–6 saat, ~200 araç çağrısı; aşılırsa dur ve raporla |
| Bildirim | Telegram (canlı bot için; şimdi kurulmaz) |
| Operasyon | Sistem kurulunca 7/24 ajan araştırır; 15–20 dk'da durum mesajı; telefondan sohbetle yönetilen "müdür" ajan (`ARCHITECTURE.md` → Operasyon katmanı). Harcama tavanı yok, yalnızca uyarı |

Kaldıraç girdi değildir. Risk bütçesinden ve sinyalin normal oynaklığından çıkan bir
sonuçtur (%25 drawdown bütçesi 10x'te ~%2,5, 3x'te ~%8 ters harekete denk gelir).

## Hipotezler

- **S1** Bir sinyalin brüt edge'i, aynı işlem sayısı ve tutma süresindeki rastgele/rotasyon
  null'ının dışında mı?
- **S2** İşlem başına brüt edge, fee + slippage + funding maliyetini geçiyor mu? (fee
  duyarlılığı: gidiş-dönüş 4 / 9 / 10 / 11 / 16 bps; 16 = MEXC API taker, kullanıcı bilgisi,
  doğrulanmadı)
- **S3** S1–S2'yi geçen sinyal, mühürlü dönemde de geçiyor mu?
- **H4** (G2'den sonra, 7/24) LLM ajanlı arama, aynı deneme bütçesindeki rastgele aramadan iyi mi?
- **H5** (sonra) Aday, mühürlü dönemden sonra küçük gerçek parayla (paper yok) araştırmayla
  uyumlu davranıyor mu?

Sonuç notional üzerinden bps/işlem olarak raporlanır. Stop'suz politikada "R" kullanılmaz.

## Kapılar

Her kapı bir kapanış koşuluna sahip. Geçmeden sonrakine başlanmaz. Kapı sonunda ajan durur
ve kullanıcıya raporlar.

| Kapı | İş | Geçti | Dur |
|---|---|---|---|
| **G0 Veri** | Ağ izni (kullanıcı); majörler için ≥3–4 yıl klines + funding + mark; veri kalite kontrolü (boşluk, saat dilimi, sha256, manifest) | Manifest ve kalite raporu temiz | Veri çekilemiyorsa dur, kullanıcıya bildir |
| **G1 Değerlendirici** | Long/short/flat hedef; fee, funding, slippage, likidasyon; elle hesaplanmış bilinen-cevaplı testler; nedensellik (gelecek bozulunca karar değişmez); determinizm; negatif kontroller (flat ≈ 0, rastgele ≈ −maliyet) | Tüm testler yeşil | Bir test kırmızıysa düzelt; sinyale geçme |
| **G2 S1–S2** | 2–3 sinyal (zaman serisi momentum, Donchian breakout, funding tabanlı); walk-forward; etiketler çakışıyorsa purge + embargo; null dağılımı; fee duyarlılığı | En az bir sinyal null'ın dışında **ve** en az bir fee senaryosunda net > 0 | Hiçbiri geçmezse `NO_EDGE` raporu; S3'e geçme; yeni hipotez öner |
| **G3 S3** | Mühürlü dönemi (son 6 ay) tek seferlik aç; yalnızca kullanıcı komutuyla | `SUPPORTED` / `REJECTED` / `INCONCLUSIVE` kararı | Açıldıktan sonra o dönem temiz sayılmaz |

G2'den sonra 7/24 ajanlı arama (H4) mühürlü dönem açılmadan, yalnızca dev verisinde yürür;
G3 tek atışı en iyi aday için yapılır. G3 geçerse, **ayrı onayla**: Monte Carlo, stres testi,
risk/kaldıraç ve trade yönetimi (her biri önceki basit haline karşı), MEXC farkı ölçümü, küçük
canlı (H5).

## Değişmez kurallar (mekanik; yönetişim belgesi değil)

1. **Tek hakem.** Sonuç deftere yalnızca hakem motordan girer; vectorbt sadece filtredir
   (eleme), hiçbir sonuç ondan deftere yazılmaz.
2. **Her deneme deftere yazılır** (hipotez, config/kod/veri hash'i, deneme sayısı). Elemede
   koşulan her konfigürasyon da deftere ve DSR deneme sayısına girer. Deneme sayacı çoklu
   test düzeltmesinin girdisidir.
3. **Mühürlü dönem tek atış**, ajandan mekanik olarak gizli, insan komutuyla açılır. Veri
   şifreli saklanır, anahtar yalnızca kullanıcıdadır ve hiçbir ajanın ortamına girmez
   (ayrıntı `ARCHITECTURE.md` → Laboratuvar).
4. **Yeni bileşen = gözlenmiş engel + önceki basit hale karşı karşılaştırma.** Engel yoksa
   BUILD yok.
5. **Doküman tavanı.** Yeni spec, karar, anayasa belgesi yazılmaz. Sonuçlar `reports/`
   altında kısa notlardır.
6. **Bütçe.** Her blok için açık süre ve araç çağrısı/token tavanı yazılır; aşılınca dur ve
   raporla. Dış sınır: 1 hafta.
7. **Kendi kodumuz küçük kalır** (≲300 satır). Yapıştırma kodu (funding, hedef→emir
   adaptörü) bu tavana dahildir. Aşılırsa kullanıcıya sor; bakım maliyeti V8'de projeyi
   bitirdi.
8. **Geliştirme ajanları kilometre taşında onay bekler**, aralarda serbest çalışır.
9. **Kritik kod** (değerlendirici, denetim) güçlü model + bağımsız inceleme ile yazılır
   (G0–G1: Claude Code + Sonnet 5.5 high); veri çekme ve toplu koşum ucuz modelle yapılabilir.
   G1'den sonraki 7/24 işleri ucuz modelle yürür ve değerlendirici/denetim koduna dokunamaz.
10. **Sonuçlar dürüst raporlanır:** test kırmızıysa söylenir, atlanan adım "atlandı" diye
    yazılır, doğrulanmamış rakam "doğrulanmadı" etiketiyle gelir
    (KNOWN / LIKELY / UNKNOWN).

## Varsayılan stack (G1 sonunda testle doğrulanır)

İki aşamalı değerlendirme: **vectorbt eleme** (hızlı filtre; sonuç sayılmaz) + **NautilusTrader
hakem** (sonuç yalnızca buradan deftere girer). **Freqtrade yedek hakemdir**: Nautilus G1'i
geçemezse hakem Freqtrade olur. Üstüne ince denetim katmanı (deney defteri, null kontroller,
mühürlü dönem, `arch` SPA/StepM, `skfolio` CPCV, DSR). Veri: Parquet + DuckDB. Qlib ve RD-Agent
bu projeden çıkarıldı (short, funding ve likidasyon desteği yok; ayrıntı Phase 2 raporunda,
repoda değil).

## Onay bekleyen kararlar

- Binance host'ları için ağ izni (G0).
- Mühürlü dönem uzunluğu (öneri: son 6 ay).
- Eleme–hakem uyum eşiği (öneri: sıralama korelasyonu ≥0,8; doğrulanmadı).

## Kapsam dışı (şimdilik)

Qlib, RD-Agent, portföy optimizasyonu, drawdown throttle, Kelly, L2/L3 veri,
canlı borsa bağlantısı, yönetişim/anayasa belgeleri.
