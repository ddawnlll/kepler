# KEPLER — ARCHITECTURE (v1, 2026-09-30)

Teknik ayrıntı yok. Bu belge şunu söyler: hangi sistemler var, birbirleriyle nasıl
ilişkili, hangisini biz yazıyoruz, hangisi platformdan geliyor. Hedef ve kapılar için
`MISSION.md`.

## İlke

Tek yönlü akış, tek gerçek kaynak: **tarihsel tape**. Paper trading ve canlı veri akışı
yok; her şey tape'in tekrar oynatılmasıyla (replay) yapılır. Sonuçlar tek hakem motordan
çıkar ve hepsi deftere yazılır.

## Sistemler ve ilişkileri

| # | Sistem | Görev | Girdi → Çıktı | Kimden |
|---|---|---|---|---|
| 1 | **Veri hattı** | Tarihsel veriyi indirir, doğrular, sürümler | Binance → tape + manifest (hash) | Platform (indirici) + biz (kalite kontrol, manifest) |
| 2 | **Sinyal** | Her bar için long / short / flat niyeti | tape → yön | **Biz** (2–3 basit sinyal) |
| 3 | **Risk motoru** | Niyeti pozisyon büyüklüğüne ve kaldıraca çevirir; hesabı korur | yön + oynaklık + hesap durumu → hedef pozisyon | **Biz** |
| 4 | **Yürütme/muhasebe** | Hedef pozisyonu fill, fee, funding, slippage, likidasyonla işler | hedef pozisyon + tape → işlem defteri, equity eğrisi | Platform: eleme vectorbt, hakem Nautilus; yedek hakem Freqtrade |
| 5 | **Denetim** | Sonucun gerçek olup olmadığını sınar: defter, null kontroller, nedensellik, mühürlü dönem, çoklu test | 2–4'ün çıktıları → karar | **Biz** (+ `arch`, `skfolio`) |
| 6 | **Rapor** | İşlem seviyesinde açıklanabilir sonuç | 4–5 → rapor | **Biz** (küçük) |
| 7 | **Araştırma ajanı** (7/24; G2'den sonra) | LLM sinyal önerir; aynı hat ölçer | öneri → 2 → 3 → 4 → 5 | Runtime: Hermes veya RD-Agent (doğrulanmadı); sözleşme bizim |
| 8 | **Canlı emir katmanı** (sonra) | MEXC'e emir gönderir | hedef pozisyon → borsa | **Karar verilmedi** |
| 9 | **Güncelleme katmanı** | 15–20 dk'da bir durum mesajı | defter → Telegram | **Biz** (deterministik, LLM yok) |
| 10 | **Müdür ajan** (sohbet) | Direktifini alır, sistemden sorumludur, önemli durumda seni uyarır | sen ↔ sistem | Hermes (Telegram geçidi); yetki sınırları bizim |

İlişki kuralları:
- Akış 1 → 2 → 3 → 4 olarak ilerler; 5 hepsinin dışında durur ve hiçbirini değiştirmez.
- Sinyal yalnızca **yön** verir. Büyüklüğü ve kaldıracı yalnızca risk motoru belirler.
- Ajan (7) yalnızca sinyalleri (2) değiştirebilir. Risk parametrelerine ve mühürlü döneme
  erişemez.
- Sonuç üreten hakem tektir (Nautilus; yedek Freqtrade). vectorbt yalnızca eleme filtresidir,
  deftere sonuç yazmaz; elemede koşulan her konfigürasyon yine de deneme sayacına girer.

## Risk motoru

**Yaklaşım: volatilite hedefleme.** Risk motoru, portföyün hedef oynaklığına göre her
sembole boyut verir. Kaldıraç girdi değil, bu boyutun sonucudur.

- **Girdiler:** sinyal yönü, sembolün nedensel (geleceğe bakmayan) oynaklığı, hesap
  equity'si, açık pozisyonlar.
- **Çıktı:** sembol başına hedef notional ve buradan türeyen kaldıraç.
- **Sert tavanlar:** sembol başı kaldıraç üst sınırı (kullanıcı üst sınırı 10x), toplam
  brüt pozisyon tavanı (majörler birbirine korele).
- **Mekanik kısıtlar:** min notional, lot adımı, likidasyon fiyatına tampon mesafe.
- **Rebalance bandı:** küçük boyut değişimleri işlem yapmaz (sık yeniden dengeleme fee
  yer).
- **Kill switch:** equity drawdown eşiği aşılırsa **tüm pozisyonlar kapatılır ve bot
  insan onayına kadar durur.** Eşik: parametre; başlangıç önerisi %25 (toleransın ortası).
- **Yapılmayanlar (şimdilik):** sinyal güvenine göre boyut (Kelly benzeri), kademeli
  drawdown merdiveni, rolling korelasyon tahmini.
- **Bilinen risk:** volatilite hedefleme kripto perp'te kanıtlanmış değil. G3'ten sonra
  "sabit boyut" ile karşılaştırılır; üstün çıkmazsa sadeleştirilir.

## Veri ağı

- **Kaynak:** Binance USDT-M, yalnızca ücretsiz (toplu arşiv + REST): klines, mark price,
  funding; gerekirse open interest. Evren: dönemsel hacim sıralamasına göre top 10–20 (her
  tarihte o günün en likit perp'leri).
- **Depolama:** Parquet dosyaları (tape) + DuckDB ile sorgu, ve manifest. Manifest her
  dosyanın hash'ini, zaman aralığını, sembol listesini, listeleme/delist tarihlerini ve
  dev / mühürlü dönem sınırını taşır.
- **Akış:** tek yönlü. İndir → doğrula → tape → replay. Canlı akış yok.
- **MEXC:** araştırma verisi değil. Yalnızca aday çıktıktan sonra fee, funding, min notional,
  lot ve fiyat farkını ölçmek için küçük bir örnek.
- **Ağ:** Binance veri host'larına erişim gerekir (G0). Çalışma ortamı Modal olduğundan ağ
  izni sorunu beklenmiyor (doğrulanmadı). Claude cloud'da bu host'lar varsayılan olarak
  engelli.

## Biz ne yazıyoruz, platformdan ne alıyoruz

| Platformdan (yazmıyoruz) | Biz yazıyoruz |
|---|---|
| Veri indirme (Freqtrade indiricisi) | Veri kalite kontrolü + manifest |
| Eleme: vectorbt. Hakem muhasebe (fee/funding/marjin): Nautilus | Sinyaller (2–3 tane) |
| `lookahead-analysis` (Freqtrade, yedek hakem devredeyse) | Risk motoru |
| `arch` (SPA / StepM / MCS), `skfolio` (CPCV) | Denetim katmanı: defter, null, mühür, DSR |
| LLM sağlayıcı (H4'te) | Yapıştırma kodu: funding, hedef→emir adaptörü; rapor; ince ajan döngüsü |

Kural: yazdığımız kod küçük kalır (≲300 satır; yapıştırma kodu dahil). Bir parça platformda
yoksa yazmadan önce kanıtlı engel gösterilir (`MISSION.md` kural 4, 7).

## Operasyon katmanı (7/24, telefondan yönetim)

Amaç: sistemi bir kez kurarsın; araştırma 7/24 sürer, durum sana düzenli gelir, telefondan
direktif verirsin. Bilgisayar başında olman gerekmez.

| Parça | Ne yapar | LLM |
|---|---|---|
| **Araştırma ajanı** | Sinyal ve parametre önerir; hakemde ölçer; deftere yazar | Evet (ucuz model) |
| **Güncelleme katmanı** | 15–20 dk'da bir durum: deneme sayısı, en iyi adaylar, null'a göre durum, harcama, hatalar. Sayılar defterden kodla üretilir | Hayır |
| **Müdür ajan** | Seninle sohbet eder; direktifini araştırma ajanının kuyruğuna yapılandırılmış komut olarak iletir; durumu açıklar; önemli olayda (hata, aday, harcama sıçraması) seni kendisi uyarır | Evet |

Kurallar:
- **Rapor sayıları LLM'den gelmez.** Güncelleme katmanı deftere bakan deterministik bir
  betiktir; müdür yorum ekleyebilir ama sayıyı o üretmez. Değişiklik yoksa mesaj kısa
  ("değişiklik yok") veya saatlik nabza seyreltilir (öneri; dersteyken spam'i önler).
- **Yazma sınırı.** Araştırma ve müdür ajanı değerlendiriciyi, denetim katmanını, risk
  parametrelerini ve mühür dosyasını **değiştiremez**; yalnızca `signals/` ve deney
  yapılandırmalarına yazar. Hermes kendi "skill"lerini yazabildiği için yazma izni ayrıca
  sınırlanır.
- **Telefondan komutlar** (hepsi sohbetle): durum/rapor, duraklat/devam/durdur, yön ver
  (hipotez/odak), aday onay/red. Müdür bunları yapılandırılmış komuta çevirir.
- **Geri dönüşsüz komutlar** (mühürlü dönemi açmak, gerçek para işlemi) sohbet yorumuyla
  yürümez. Müdür yalnızca "şunu yapmak üzere onay iste" der; asıl tetik, ajanların
  erişemediği ayrı ve LLM'siz bir onay adımıdır (ör. tek kullanımlık kod).
- **Erişim:** Telegram yalnızca senin kullanıcı kimliğine yanıt verir.
- **Harcama:** tavan yok, yalnızca uyarı (kullanıcı kararı). Öneri, karar sende: derste
  müdahale edemeyebileceğin için acil, yüksek bir sert üst sınır da konsun.
- **Runtime:** Hermes Agent (Nous Research; kalıcı servis, Telegram geçidi, cron, bellek;
  doğrulanmadı) veya RD-Agent. Runtime değiştirilebilir; sözleşme bu bölümdür.

## Laboratuvar (araçlar ve çalışma şekli)

- **Ortam:** Python 3.12, `uv` + kilit dosyası. Çalışma ortamı Modal; aynı repo ve komutlarla
  Claude cloud'da veya başka bir ajanla (ör. Hermes) da çalışır. Ajana/ortama özel bağımlılık yok.
- **Veri:** saatlik (1h) tape ana; 4h ve 1d yukarı toplanır. Depolama Parquet + DuckDB.
- **Sinyal arayüzü:** sinyal, tape'ten hedef pozisyon serisi (long/short/flat + büyüklük)
  üreten saf bir fonksiyondur. vectorbt (eleme) ve Nautilus (hakem) aynı seriyi oynatır.
  Yapıştırma kodu ≲300 satır tavanına dahildir.
- **Eleme ve hakem:** eleme başına ~100 konfigürasyon bütçesi; hepsi deftere ve DSR sayısına
  girer. Eleme–hakem sıralama uyumu ölçülür; öneri eşiği ≥0,8 (doğrulanmadı), altındaysa
  eleme devre dışı kalır ve doğrudan hakem kullanılır.
- **Deney defteri:** append-only JSONL dosyası, DuckDB ile sorgulanır (kullanıcı kararı yok,
  varsayılan).
- **Raporlar:** her koşu `reports/` altında Markdown/HTML rapor üretir. Pano yok.
- **Testler:** elle çalıştırılır (CI yok); G1 sonunda yeniden değerlendirilir.
- **Mühürlü dönem (ajan ve ortamdan bağımsız):** son 6 ay verisi şifreli dosya olarak tutulur.
  Anahtar yalnızca kullanıcıdadır ve hiçbir ajanın ortam değişkenine/dosya sistemine girmez.
  Açma betiğini kullanıcı çalıştırır; tek seferde değerlendirir ve sonucu deftere "yakıldı"
  kaydıyla yazar. Şifreli dosya dışında bu veri ajanın ortamında bulunmaz.
- **Ajan döngüsü (H4):** LiteLLM üzerinden ucuz modeller; kritik kod için güçlü model ayrıca
  (`MISSION.md` kural 9).
- **Kitaplar:** PDF'ler repoya eklenir, metne çevrilip repoda tutulur (repo özel kalmalı);
  hipotez kaynağı.
- **Bildirim:** Telegram (canlı bot için; şimdi kurulmaz).

## Açık noktalar

- **Nautilus hakem olarak G1'i geçiyor mu:** G1'de ölçüldü (`reports/g0_g1.md`): geçiyor,
  ama likidasyon yapıştırmasıyla (Nautilus bar verisinde kendisi likide etmiyor; mark H/L ile
  tetiklenen reduce-only stop-market). Python ≥3.12 şart. Hız: 35k saatlik bar ≈ 0,5–2,7 sn
  (önceki "~36 sn" bu sürümde geçerli değil). Funding sınır anı bir KABUL: T'deki dolumlar
  settlement'tan sonra sayılır; Binance'in resmi metni sandbox'tan okunamadı (LIKELY, doğrulanmadı).
  Funding aralığı 4/8 değil 1/2/4/8 saat olabilir (99 sembol 8 saat dışı).
- **Eleme ile hakem uyumu:** vectorbt sıralamasının (hangi konfigürasyon iyi) hakemle
  örtüşüp örtüşmediği doğrulanmadı. Filtre iyi adayı eliyorsa eleme işe yaramaz
  (UNKNOWN — TARGETED EXPERIMENT REQUIRED).
- **MEXC canlı emir katmanı:** karar verilmedi. MEXC futures'ın Freqtrade/ccxt desteği
  doğrulanmadı (UNKNOWN — TARGETED RESEARCH REQUIRED). G3 sonrasında ele alınır.
- **Paper yok kararı:** ileriye dönük doğrulama, mühürlü dönemden sonra ancak küçük gerçek
  parayla olur (`MISSION.md` H5).
- **Kill switch eşiği ve hedef volatilite parametreleri:** G2 sonuçlarından sonra
  belirlenir; önceden ayarlanmaz.
