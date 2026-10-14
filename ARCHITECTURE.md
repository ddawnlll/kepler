# KEPLER — ARCHITECTURE (v2, 2026-10-03)

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
| 2 | **Durum + uzman** | Piyasa durumunu hesaplar (oynaklık, korelasyon, funding, ATR); uzman bundan tahmin üretir. Basit sinyaller (`signals.py`) aynı akışın yön-only halidir | tape → durum → tahmin [-1, 1] veya yön | **Biz** |
| 3 | **Risk motoru** | Tahmini/niyeti pozisyon büyüklüğüne ve kaldıraca çevirir; hesabı korur | tahmin + oynaklık + korelasyon + hesap durumu → hedef pozisyon | **Biz** |
| 4 | **Yürütme/muhasebe** | Hedef pozisyonu fill, fee, funding, slippage, likidasyonla işler | hedef pozisyon + tape → işlem defteri, equity eğrisi | Platform: eleme vectorbt, hakem numba olay motoru (Nautilus'un yerini aldı); yedek hakem Freqtrade |
| 5 | **Denetim** | Sonucun gerçek olup olmadığını sınar: defter, null kontroller, nedensellik, mühürlü dönem, çoklu test | 2–4'ün çıktıları → karar | **Biz** (+ `arch`, `skfolio`) |
| 6 | **Rapor** | İşlem seviyesinde açıklanabilir sonuç | 4–5 → rapor | **Biz** (küçük) |
| 7 | **Araştırma ajanı** (7/24; G2'den sonra) | LLM sinyal önerir; aynı hat ölçer | öneri → 2 → 3 → 4 → 5 | Runtime: Hermes veya RD-Agent (doğrulanmadı); sözleşme bizim |
| 8 | **Canlı emir katmanı** (sonra) | MEXC'e emir gönderir | hedef pozisyon → borsa | **Karar verilmedi** |
| 9 | **Güncelleme katmanı** | 15–20 dk'da bir durum mesajı | defter → Telegram | **Biz** (deterministik, LLM yok) |
| 10 | **Müdür ajan** (sohbet) | Direktifini alır, sistemden sorumludur, önemli durumda seni uyarır | sen ↔ sistem | Hermes (Telegram geçidi); yetki sınırları bizim |

İlişki kuralları:
- Akış 1 → 2 → 3 → 4 olarak ilerler; 5 hepsinin dışında durur ve hiçbirini değiştirmez.
- Uzman/sinyal yalnızca **tahmin** (yön ya da [-1, 1]) verir. Büyüklüğü ve kaldıracı yalnızca risk motoru belirler.
- **Ana sistem Ensemble'dır** (`kepler/ensemble.py`): durum → uzmanlar (trend, kesitsel momentum, carry) → aday → risk motoru. Tek sinyaller (`signals.py`, `turtle.py`) karşılaştırma ve kontrol içindir.
- Ajan (7) yalnızca sinyalleri (2) değiştirebilir. Risk parametrelerine ve mühürlü döneme
  erişemez.
- Sonuç üreten hakem tektir (numba motoru; yedek Freqtrade). vectorbt yalnızca eleme filtresidir,
  deftere sonuç yazmaz; elemede koşulan her konfigürasyon yine de deneme sayacına girer.

## Katmanlar ve kurallar (kod bunu zorlar)

Tek kaynak `tests/test_architecture.py` (stdlib, Modal'siz: `python3 tests/test_architecture.py`).
Alt katman üst katmanı import edemez. Düşükten yükseğe:

| Katman | Modüller | Görev |
|---|---|---|
| veri | `data qc tape universe` | indirme, kalite, tape yükleme |
| temel | `ledger report stats capacity stress nested signals` | defter, istatistik, basit sinyaller |
| risk | `risk portfolio` | boyutlama, kaldıraç, kill switch |
| durum | `market_state state indicators` | oynaklık/korelasyon/funding, ATR/swing/profil, göstergeler |
| uzman | `experts/* turtle` | tahmin üretir: `experts/trend`, `xs_momentum`, `carry`, `zone_fade`; edge ailesi (`reports/edge_experts_protocol.md`): `bollinger`, `lowvol`, `nearhigh`, `fundcrowd`, `volrev`, `orderflow`. **Ensemble tek altyapıdır**: uzmanlar `ensemble.REG`'e kayıtlı takılabilir üyeler, bileşim `Params.names` + `Params.weights`. EV1 ayrı bir sistem değil, varsayılan bileşimdir (trend 0,6 / xs_momentum 0,2 / carry 0,2); yeni uzman henüz hiçbir bileşime ağırlıkla girmedi (kapı: `reports/edge_experts.md`) |
| kompozisyon | `ensemble` | uzmanları birleştirir, kitap sözleşmesi |
| hakem | `referee audit robust screen evaluate` | tek hakem, denetim, defter girişi |

Değişmez kurallar:
- **Uzman yalnızca tahmin verir.** `risk`, `portfolio`, `ledger`, `referee`, `evaluate`, `ensemble` import edemez.
  (Bilinen tek istisna: `zone_fade` → `ledger`; yönetici ayrılınca kalkar, test listede tutar.)
- **Hakem hattı sinyalden habersizdir.** `referee audit ledger stats robust` uzman, ensemble, sinyal, durum
  ve risk koduna bakmaz.
- `kepler/` dışarıdaki `scripts`, `factory`, `tools` koduna bağlanmaz (akış tek yönlü).
- **Boyut bütçesi:** dosya başına 300, `kepler/` toplam 3000 satır. Aşılırsa önce var olan sadeleşir.
- **Belge izin listesi:** yeni `.md` açılmaz; kalıcı belge türleri MISSION, ARCHITECTURE, BACKTEST, TASKS (+ `docs/factory.md` dondurulmuş, `reports/` deney çıktıları). GitHub katkı akışı için `.github/CONTRIBUTING.md`, `.github/SECURITY.md` ve `.github/pull_request_template.md` dosya bazında izinlidir; issue formları YAML'dir. İzin listesinin tek kaynağı `tests/test_architecture.py`'dir.
- Yeni modül = `LAYERS`a satır; test bunu zorlar. Kural değişince bu bölüm aynı commit'te güncellenir.

Nereye ne konur: yeni tahmin fikri → `experts/<ad>.py` (+ ön kayıt `reports/<ad>_protocol.md`);
yeni girdi (oynaklık, ATR gibi) → `market_state.py` veya `state.py`; boyut/tavan → `portfolio.py`/`risk.py`;
deneyi koşan betik → `scripts/`. Uzman içinde boyut hesaplanmaz, durum yeniden hesaplanmaz.

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
- **Portföy düzeyi (Ensemble):** korelasyon farkındalıklı oynaklık hedefi (IDM), sembol ve brüt
  tavanları, tampon. Kod `kepler/portfolio.py`; sembol başına hedefleme + kill switch `kepler/risk.py`.
  İkisinin tek modülde birleşmesi bağımsız incelemeli ayrı iştir (TASKS.md).
- **Yapılmayanlar (şimdilik):** sinyal güvenine göre boyut (Kelly benzeri), kademeli
  drawdown merdiveni.
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
| Eleme: vectorbt. Hakem muhasebe (fee/funding/marjin): numba motoru | Durum, uzmanlar ve basit sinyaller |
| `lookahead-analysis` (Freqtrade, yedek hakem devredeyse) | Risk motoru |
| `arch` (SPA / StepM / MCS), `skfolio` (CPCV) | Denetim katmanı: defter, null, mühür, DSR |
| LLM sağlayıcı (H4'te) | Yapıştırma kodu: funding, hedef→emir adaptörü; rapor; ince ajan döngüsü |

Kural: yazdığımız kod küçük kalır (dosya başına 300, `kepler/` toplamı 3000 satır; testle zorlanır).
Bir parça platformda yoksa yazmadan önce kanıtlı engel gösterilir (`MISSION.md` kural 4, 7).

## Operasyon katmanı (7/24, telefondan yönetim)

Ayrıntı ve güncel tasarım **`docs/factory.md`** (roller, kapılar, değişmezler D1–D14); çelişkide o kazanır.
v1 özeti: sekreter (Telegram, karar vermez), müdür (seyrek uyanır, brif yazar), işçiler (tek brif, taze
bağlam, ayrı worktree), güncelleme ajanı (deterministik durum mesajı). Kalıcı kurallar:
- **Sayı hafızadan değil, sorgudan gelir** (ledger / `state/STATUS.md`); sorguda yoksa "bilmiyorum".
- **İletişim ortak çalışma alanından:** `state/queue.jsonl` (tek giriş `factory/enqueue.py`; B/C onayı yalnızca imzalı `factory/approve.py`), ledger (tek yazar `factory/ingest.py`; işçiler `ledger.Staging` ile teslim yazar), raporlar.
- **Yazma sınırı:** ajanlar değerlendiriciyi, denetimi, risk parametrelerini, mühür dosyasını değiştiremez;
  yol kuralları `.claude/hooks/guard.py` (Claude Code) ve `.githooks/pre-commit` (tüm ajanlar) ile zorlanır.
- **Geri dönüşsüz komutlar** (mühür açmak, gerçek para) sohbet yorumuyla yürümez; LLM'siz onay adımı gerekir.
- Erişim yalnızca kullanıcıya; harcama için kullanıcı kararı uyarı, sert limit sağlayıcı anahtarında.

## Laboratuvar (araçlar ve çalışma şekli)

- **Ortam:** Python 3.12, `uv` + kilit dosyası. Çalışma ortamı Modal; aynı repo ve komutlarla
  Claude cloud'da veya başka bir ajanla (ör. Hermes) da çalışır. Ajana/ortama özel bağımlılık yok.
- **Veri:** saatlik (1h) tape ana; 4h ve 1d yukarı toplanır. Depolama Parquet + DuckDB.
- **Kitap sözleşmesi:** `book({sym: kl}) -> {sym: DataFrame[target, stop]}` (BACKTEST §4). Sürekli
  uzmanlar `experts/_interface.py` (`forecast(close, st, p)`, [-1, 1]); boyutlamayı risk katmanı yapar.
  vectorbt (eleme) ve numba hakem aynı seriyi oynatır. Yapıştırma kodu hakemle birlikte
  sayılır (MISSION kural 7a: tavan kaldırıldı, sayı raporlanır).
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
- **Ajan döngüsü (H4):** LiteLLM üzerinden yapılandırılan modeller; kritik kod değişiklikleri kullanıcı
  yetkilendirmesi ve bağımsız incelemeyle yürür (`MISSION.md` kural 9).
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
