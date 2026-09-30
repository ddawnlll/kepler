# KEPLER — ARCHITECTURE (v1, 2026-09-30)

Teknik ayrıntı yok. Bu belge şunu söyler: hangi sistemler var, birbirleriyle nasıl
ilişkili, hangisini biz yazıyoruz, hangisi platformdan geliyor. Hedef ve kapılar için
`MISSION.md`.

## İlke

Tek yönlü akış, tek gerçek kaynak: **tarihsel tape**. Paper trading ve canlı veri akışı
yok; her şey tape'in tekrar oynatılmasıyla (replay) yapılır. Sonuçlar tek değerlendiriciden
çıkar ve hepsi deftere yazılır.

## Sistemler ve ilişkileri

| # | Sistem | Görev | Girdi → Çıktı | Kimden |
|---|---|---|---|---|
| 1 | **Veri hattı** | Tarihsel veriyi indirir, doğrular, sürümler | Binance → tape + manifest (hash) | Platform (indirici) + biz (kalite kontrol, manifest) |
| 2 | **Sinyal** | Her bar için long / short / flat niyeti | tape → yön | **Biz** (2–3 basit sinyal) |
| 3 | **Risk motoru** | Niyeti pozisyon büyüklüğüne ve kaldıraca çevirir; hesabı korur | yön + oynaklık + hesap durumu → hedef pozisyon | **Biz** |
| 4 | **Yürütme/muhasebe** | Hedef pozisyonu fill, fee, funding, slippage, likidasyonla işler | hedef pozisyon + tape → işlem defteri, equity eğrisi | Platform (Freqtrade backtest); yedek: ince çekirdek |
| 5 | **Denetim** | Sonucun gerçek olup olmadığını sınar: defter, null kontroller, nedensellik, mühürlü dönem, çoklu test | 2–4'ün çıktıları → karar | **Biz** (+ `arch`, `skfolio`) |
| 6 | **Rapor** | İşlem seviyesinde açıklanabilir sonuç | 4–5 → rapor | **Biz** (küçük) |
| 7 | **Ajan döngüsü** (sonra) | LLM sinyal önerir; aynı hat ölçer | öneri → 2 → 3 → 4 → 5 | **Biz** (ince) + LLM sağlayıcı |
| 8 | **Canlı emir katmanı** (sonra) | MEXC'e emir gönderir | hedef pozisyon → borsa | **Karar verilmedi** |

İlişki kuralları:
- Akış 1 → 2 → 3 → 4 olarak ilerler; 5 hepsinin dışında durur ve hiçbirini değiştirmez.
- Sinyal yalnızca **yön** verir. Büyüklüğü ve kaldıracı yalnızca risk motoru belirler.
- Ajan (7) yalnızca sinyalleri (2) değiştirebilir. Risk parametrelerine ve mühürlü döneme
  erişemez.
- Değerlendirici (4) tektir. Başka bir simülatör yalnızca çapraz kontrol (oracle) olarak
  kullanılır, sonuç üretmez.

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
  funding; gerekirse open interest. Evren: top 10–20 major.
- **Depolama:** dosya tabanlı tape (kolon formatlı dosyalar) + manifest. Manifest her
  dosyanın hash'ini, zaman aralığını, sembol listesini, listeleme/delist tarihlerini ve
  dev / mühürlü dönem sınırını taşır.
- **Akış:** tek yönlü. İndir → doğrula → tape → replay. Canlı akış yok.
- **MEXC:** araştırma verisi değil. Yalnızca aday çıktıktan sonra fee, funding, min notional,
  lot ve fiyat farkını ölçmek için küçük bir örnek.
- **Ağ:** Binance veri host'larına erişim gerekir (G0). Bu container'da engelli; kullanıcı
  izni bekleniyor.

## Biz ne yazıyoruz, platformdan ne alıyoruz

| Platformdan (yazmıyoruz) | Biz yazıyoruz |
|---|---|
| Veri indirme (Freqtrade indiricisi) | Veri kalite kontrolü + manifest |
| Backtest, fee/funding/likidasyon muhasebesi (Freqtrade) | Sinyaller (2–3 tane) |
| `lookahead-analysis` (Freqtrade) | Risk motoru |
| `arch` (SPA / StepM / MCS), `skfolio` (CPCV) | Denetim katmanı: defter, null, mühür, DSR |
| LLM sağlayıcı (H4'te) | Rapor, ince ajan döngüsü |

Kural: yazdığımız kod küçük kalır (çekirdek ≲300 satır). Bir parça platformda yoksa
yazmadan önce kanıtlı engel gösterilir (`MISSION.md` kural 4).

## Açık noktalar

- **Freqtrade'in dinamik boyut (volatilite hedefleme) ifadesi:** Freqtrade giriş/çıkış
  odaklı. Bar bar hedef boyut ayarı için uygun olup olmadığı doğrulanmadı
  (UNKNOWN — TARGETED EXPERIMENT REQUIRED, G1). Olmazsa yedek: ince çekirdek (hedef
  pozisyonu doğal destekler).
- **MEXC canlı emir katmanı:** karar verilmedi. MEXC futures'ın Freqtrade/ccxt desteği
  doğrulanmadı (UNKNOWN — TARGETED RESEARCH REQUIRED). G3 sonrasında ele alınır.
- **Paper yok kararı:** ileriye dönük doğrulama, mühürlü dönemden sonra ancak küçük gerçek
  parayla olur (`MISSION.md` H5).
- **Kill switch eşiği ve hedef volatilite parametreleri:** G2 sonuçlarından sonra
  belirlenir; önceden ayarlanmaz.
