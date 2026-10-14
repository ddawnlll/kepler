# Kepler Research Factory — v4.1

**V4 mimarisinin uygulama, deney özerkliği ve 24 saatlik kabul sözleşmesi**  
**Tarih:** 15 Ekim 2026  
**Durum:** Uygulamaya yönelik hedefli değişiklik sözleşmesi. **Henüz uygulanmadı; VPS/Modal/Telegram kabulü yapılmadı; GitHub `main` değiştirilmedi.**  
**Dayanak:** `kepler_factory_v4_focus_memory.md` (V4), `MISSION.md`, `BACKTEST.md`, `ARCHITECTURE.md`, `AGENTS.md`, `docs/factory.md` (mevcut v2 kod/deployment referansı), Kepler `factory/` kodu ve kullanıcı tarafından sağlanan *Early Market Regime Forecasting* monografisi.

> **Karar:** V5 yok. Yeni agent organizasyonu, yeni yönetim sistemi veya sırf şık göründüğü için yeni soyutlama yok. Mevcut V4 hedef ve hafıza tasarımı, mevcut broker/runner ve mevcut Kepler laboratuvarı **çalışan bir araştırma döngüsüne** bağlanacak. Bu dosya V4'ün yerine baştan yazılmış bir fabrika değildir; V4'ün uygulanması için değişiklik/kabul ekidir. Üst belgelerle çelişen kurallar, ancak insanın onayladığı eşzamanlı belge ve kod değişikliğiyle geçerli olur.

## 0. Ürün ve dondurma kararı

**Tek ürün:** `MISSION → FOCUS → HYPOTHESIS → PREREG → SANDBOX → DEV EVIDENCE → CRITIQUE → MEMORY → NEXT BET`.

**Tek aktif araştırma programı:** `EARLY_REGIME_FORECASTING`; üst amaç `EDGE_DISCOVERY`. Müdür H1-A'yı hedefler: henüz başlamamış yönlü piyasa rejiminin önceden tahmini. H1-B (başlamış değişimi erken fark etme/devamlılık) ve H1-C (volatilite tahmini) ayrı çalışmalardır; olumlu sonuçları H1-A'ya mal edilemez.

**V4 mimarisi donduruldu:** Tek müdür, ihtiyaç oldukça araştırmacı/uygulayıcı/eleştirmen; mevcut Kepler, mevcut broker/SQLite, mevcut ledger ve hakem. Sekreter Telegram arayüzü yok; tek Telegram sohbetinde doğrudan müdür var. Night Mode ayrı bir agent değil, aynı müdürün çalışma ve bildirim davranışıdır.

**V4.1 tamamlanmış sayılmaz**: Son sürüm komutla açılmış, 24 saat yeniden başlatma/işçi hataları altında çalışmış, en az bir kayıtlı araştırma döngüsünü tamamlamış ve bilimsel sonuçları tekrar üretilebilir olarak saklamış olmalı. Bir agentın “bitti” demesi kabul değildir.

**Değişiklik bütçesi:** Dört teknik çıktı ve tek pilot; faz adı altında sonsuz yeni görev yaratılmaz. Her yeni iş için somut blocker, kabul testi, en küçük çözüm ve maliyet gerekçesi gerekir.

## 1. Doğrulanmış mevcut durum ve düzeltilmesi gereken uyumsuzluklar

15 Ekim 2026 GitHub `main` kod incelemesinde:

- `factory/broker.py`: Unix socket + `SO_PEERCRED` ile insan (`jj`/root) ile ajan (`kagent`) yetkileri ayrılıyor. `approve`, `resume`, `review`, `merge`, `cost` insan yetkisinde. Mevcut şemada **program yetki devri / mandate API'si yok**.
- `factory/store.py`: SQLite `jobs`, `events`, `outbox`, `meta` var. Bu tabloyu genişlet; paralel ikinci iş kayıt veritabanı kurma.
- `factory/runner.py`: araştırma işi `type=C`, `status=approved`, `approved_by_uid` olmadan yürümüyor. Kesintisiz otomatik yeni araştırma bu noktada takılıyor. `research` hata/timeout sonrası otomatik yeniden koşulmuyor; bu doğru başlangıç davranışı.
- `factory/research.py`: araştırma yalnız onaylı `main`, daha eski commit'te ön kayıt ve izinli `script/argv` ile DEV'de koşuyor. Yeni agent kodunun onaysız `main`'e girip çalışmasına izin vermiyor.
- `factory/merge_gate.py`: `main` terfisi insanın **ayrı** `review` + `merge` çağrılarıyla yapılıyor. **Bu kapı korunacak.**
- `factory/policy.json`: `research_enabled=false`; `dev_workspace_verified=false`, `provider_limits_verified=false`, `acceptance_verified=false`. `budget_usd_daily=5.0` ve `budget_hard_action="warn"`: bu **sert yerel harcama kesicisi değildir**.
- `factory/status.py`: 15 dakikalık kalıcı durum bildirim olayı yaratıyor. Sadece SOUL'e “gece sessiz ol” yazmak Night Mode'u uygulamaz.
- `MISSION.md`: kaynakta “okunmuş trading kitapları” ve işletimde 15–20 dakikalık durum mesajı bulunuyor. Akademik monografi kaynağı ve sessiz gece modu üst belgenin bilinçli revizyonunu gerektiriyor.
- `AGENTS.md`: DEV araştırmasının insan onaylı `main` ve protokol üzerinde koşulmasını istiyor. Yeni otonom *deney çalışma alanı*, bunu sessizce ihlal etmek yerine açık ve dar istisna olarak insan onayı, ayrılmış sandbox ve testle tanımlanacak.

**Üç ayrı şey birbirine karışmayacak:** (a) bir işin 24 saat çalışması, (b) araştırmayı insan müdahalesi olmadan sürdürebilmesi, (c) ekonomik edge iddiasının bilimsel olarak güvenilir olması.

## 2. Dört zorunlu teslimat

### A — Gerçek araştırma özerkliği: kapsamlı DEV yetki devri

**Hedef:** Kullanıcı **bir kez** sınırlı bir araştırma yetkisi verir; müdür bu süre ve kapsam içinde yeni hipotez, kaynak araştırması, ön kayıt, kod adayı, test ve izinli DEV deneyi için her seferinde kullanıcıyı uyandırmaz.

**Yetkinin kaynağı model değil broker'dır.** Güvenilir SQLite store'da (ve gerekiyorsa root-owned policy'de) bir `mandate` kaydı tutulur. İnsan, broker'ın mevcut OS kimlik doğrulamalı yerel yönetim arayüzünden oluşturur/iptal eder. Telegram üzerinden “tam yetki veriyorum” metni **tek başına yürütme ayrıcalığı açmaz**. Kriptografik token dağıtımı zorunlu değildir; mevcut socket, UID ve transaction sistemi yeterli ise onu kullan.

İlk mandate sözleşmesi aşağıdaki **mantıksal alanları** taşır; gerçek tablo/JSON şeması en küçük mevcut kod değişikliğiyle uygulanır:

```yaml
mandate_id: DEV-H1A-001
program: EARLY_REGIME_FORECASTING
focus_lock: H1-A
issuer: verified_human_os_uid
principal: kagent
status: active                     # active | paused | revoked | expired
allowed_actions: [literature, preregister, sandbox_code, fixture_test, dev_forecast]
allowed_period: DEV                # 2026-04-01 ve sonrası G3 erişilemez
allowed_executor: isolated_cpu     # ilk pilot: sır erişimsiz CPU sandbox
allowed_artifacts: [protocol, code_candidate, forecast_receipt, critique, lesson]
expires_at: configured_by_human
max_trials: configured_by_human
max_runtime_seconds: configured_by_human
max_compute_jobs: configured_by_human
max_parallel_workers: 1
estimated_budget_usd: configured_by_human
forbidden: [sealed_data, live_orders, core_write, main_merge, policy_write, credential_access]
```

Bu **şema örneğidir**, mevcut API ya da imzalanmış gerçek yetki kaydı değildir. Sayısal limitler kullanıcı tarafından belirlenir; fabrika sessizce “varsayılan $5 güvenli” sonucunu çıkarmaz.

**Broker tarafından atomik uygulanacak:** kapsam/odak doğrulaması; ön kayıt hash'i; izinli veri dönemi; manifestteki trial ve iş sınırları; tekil iş kimliği; lease ve idempotency; iptal/son kullanma süresi; `pause`/`stop`; restart sonrasında limitlerin kaybolmaması. Dispatch'ten **önce** trial/iş rezervasyonu yap; sonuçlanma ile rezervasyonu çift saymadan mutabık tut. Deneme yapılmışsa kayıt silinmez; başarısız/UNKNOWN da kalır.

**Harcamada güvenlik:** broker'ın USD tahmini gerçek fatura garantisi değildir. Sağlayıcı/Modal tarafında doğrulanmış sert dış limit olmadan araştırma açma. Tahminin `warn` olarak kaldığını açıkça göster. Kota tüketimi ölçülemiyorsa **yeni maliyetli iş dispatch etme**; bunu `budget_unverified` olarak raporla. Güvenli durdurma, önceki işleri veya kanıtları silmez.

**İki çalışma yolu:**

1. **Trusted DEV lane:** Mevcut onaylı `main` üzerindeki izinli betik ve parametrelerle ön kayıtlı deney. Mevcut `factory/research.py` doğrulamasını korur; mandate yalnız her koşu için tekrar eden insan onayı gereğini güvenli kapsam içinde ikame eder.
2. **Untrusted candidate lane:** Müdürün işçiye yazdırdığı *yeni deney kodu*, `main`'i değiştirmeden ayrı immutable commit/snapshot kimliğiyle, ağsız ve secretsız `kworker` sandbox'ında, **yalnız read-only DEV verisine** erişerek çalışabilir. Dış API/Modal token'ı, broker socket'i, bare repo yazımı ve G3 verisi erişilemez. İlk H1-A deneyi için CPU yeterli; GPU/Modal'a yeni yürütme kanalı eklemek gerekmez.

**Çok kritik:** Untrusted lane'in verdiği skor veya rapor **kanıt olarak otomatik terfi etmez**. Çıktı şema/hash, zaman kesimi, kayıtlı protokol ve negatif kontrollerle doğrulanır; mümkün olduğunda tahminler **trusted scoring koduyla** bağımsız yeniden puanlanır. Model kodu ile ona başarı notu veren değerlendirme kodu aynı untrusted adaydan import edilmez. Kodun kendisi sızıntı yaparsa sonraki kontroller ve bağımsız denetim onu yakalamaya çalışır; sandbox tek başına araştırma doğruluğu garantisi değildir. Güvenilir ekonomi/ledger yazarı değiştirilmez.

**Main'e otomatik merge yok.** Mühürlü dönem, gerçek para, çekirdek/risk/hakem ve politika değişikliği yine insanın OS-onayı/bağımsız incelemesini gerektirir. Araştırma için üretilmiş protokol/snapshot *immutability* ve eşit hash koşulları ile tanımlanır; üretilen her yeni varyant yeni deneme ve gerekiyorsa yeni bilimsel kayıt sayılır.

**A teslimat testi:** İnsan mandate'i açar; müdür insanı tekrar çağırmadan tek ön kayıtlı H1-A kod adayı geliştirir, izole fixture'ı koşar ve izinli gerçek DEV forecast denemesini sonuç/UNKNOWN olarak kaydeder. Ayrı testte G3, core, token, `main` merge, dış ağ, ikinci trial kotası, süresi dolmuş mandate reddedilir. Yetki iptali aktif işlere tanımlı `stop` politikasıyla güvenli biçimde uygulanır.

### B — Aktif bilimsel hafıza: karar vermeden önce geçmiş kanıt

**Hedef:** Yeni denemeyi seçmeden önce geçmişte aynı mekanizmanın, aynı etiket/horizon'ın, benzer baseline'ın nasıl performans gösterdiği ve neden reddedildiği **gerçekten** geri çağrılır. Sadece “gece raporu yazıldı” hafıza başarısı değildir.

Yeni vektör veritabanı veya ayrı bilgi ormanı yok. V4'teki katmanları mevcut kaynaklara dağıt:

- **Mission/focus/mandate:** trusted broker DB ve üst repo sözleşmeleri;
- **İş/olay:** mevcut `jobs/events/outbox`;
- **Deney gerçeği:** append-only ledger + immutable ön kayıt + veri/kod/engine/protokol hash'leri;
- **İddia ve ders:** broker DB'de küçük `claims` ve `lessons` kayıtları + mevcut SQLite FTS5 veya eşdeğer basit arama;
- **Kaynak arşivi:** repo raporları, monografi, literatür ve GitHub; kaynak arşivi deney defterinin yerine geçmez.

Her bilimsel iddia asgari şu kapsamı taşır: `claim_id`, `program`, `hypothesis` (H1-A/B/C), `mechanism`, `label`, `horizon`, `universe`, `period`, `comparison_baseline`, `evidence_type`, `source_refs`, `status`, `limitations`, `engine_version`, `created_at`. Bilinmeyen alan `UNKNOWN`; LLM tahmini `PROJECT_OBSERVATION` yapılamaz.

**Zorunlu yöntem:**

```text
wake → oku mission + focus + açık işleri
     → retrieve prior claims / negative outcomes / contradictions
     → aday hipotezi eski mekanizma ve trial family ile eşleştir
     → novelty + information-value gerekçesi
     → tek preregistered experiment
     → trusted result receipt + critique
     → evidence-linked claim / lesson
     → NEXT BET veya IDLE
```

**Yazım ilkesi:** Eski negatif sonuç silinmez; mekanizma ve örneklem sınırıyla saklanır. Yeni veri çelişiyorsa `contradicts`/`supersedes` ilişkisi açılır. Hakem motoru değiştiğinde eski PnL sayıları otomatik güncel kanıt sayılamaz; `UNVERIFIED_UNDER_NEW_ENGINE` etiketi kullanılır. Kaynak hash'i kayıp iddia kesin bilimsel sonuç değildir.

**Karar denetimi:** Müdürün yeni hipotez kararı `retrieval_receipt`, incelenen yakın bulgular, neden aynı test olmadığı, neden şimdi yapılacağı ve seçilmeyen alternatifleri kısaca kaydetmelidir. Müdürün **ham alt-kırılım metriklere bakarak** başarısız varyantları yeniden optimize etmesi engellenir; hassas sonuçlara erişim gerektiğinde kör/ayrı denetçi ile özet karar arayüzü kullanılır. Prompt'ta “bakma” demek tek başına erişim kontrolü değildir.

**B teslimat testi:** Negatif, çelişkili ve mühür-erişimi yasak üç fixture claim ekle. Müdür aynı hipotezi yeniden sunduğunda ilgili negatif deney kimliğini geri çağırsın ve ya reddetsin ya mekanizma farkını kanıtlasın. Uydurma metrik/olmayan kaynak ve eski motor altında `edge confirmed` reddedilsin. Restart sonrası aynı sorgu aynı kaynakları döndürsün.

### C — Bilimsel kanıt kilidi: pozitif edge kararını durduran blokajlar

**Hedef:** Araştırma yürüsün, fakat eksik bilimsel altyapı nedeniyle yanlış pozitif trading-edge terfisi yapılamasın. Tek küresel “her şey hazır değilse hiç düşünme” kilidi oluşturma; **araştırma türüne özgü kapı** uygula.

| Çalışma türü | Gerekli kontrol | Güvenilmezse izin verilen sonuç |
|---|---|---|
| Literatür/monografi | Kaynak kimliği, rakip açıklamalar, doğrulanma düzeyi | `LITERATURE` / `DESIGN_INFERENCE` / `UNKNOWN`; gerçek performans iddiası yok |
| H1-A forecast feasibility | Ön kayıt, label maturity/purge, temporal leakage testleri, baseline, bağımsız scoring, ledger/trial kimliği | `FORECAST_SUPPORTED_IN_THIS_TEST`, `REJECT_INCREMENTAL_H1A`, `INCONCLUSIVE`, `INVALID`; **trading EDGE değil** |
| Ekonomik swing stratejisi | K1–K9, numba referee muhasebesi, fee/funding/slippage/risk, null ve çoklu-deneme kalibrasyonu, ledger bütünlüğü, bağımsız denetim | `NO_EDGE`, `WEAK`, `INSUFFICIENT`, `INVALID`; blokaj varken **PROMISING/CANDIDATE yok** |
| G3 mühür | K1–K9 sonrası insanın tek kullanımlık ayrı kararı | Yalnız insan; otomatik çalıştırma yok |

**Repo triage (15 Ekim snapshot'ı):** `#46` bağımlılık altında null/bootstrap kalibrasyonu; `#49` deneme/ledger göçü; `#42` bağımsız çekirdek incelemesi; `#52` numba gerçek-veri muhasebe teyidi; `PR #53` numba finansal entegrasyon. Öncelikleri “kaç açık issue var” değil **hangi güvenilir kararın önünde duruyor** sorusuyla belirle. `#51` satır tavanı kararı ayrı mühendislik/politika sorunudur. Referans: `https://github.com/ddawnlll/kepler/issues/46`, `/issues/49`, `/issues/42`, `/issues/52`, `/pull/53`.

**İlk H1-A probabilistik forecast deneyi**, finansal hakemi çalıştırmadığından `#46` gibi *trading null* blocker'ı yüzünden gereksiz ertelenmesin. Fakat kendi forecast istatistiği ve örneklem bağımsızlığı doğru doğrulansın. Trading alpha'ya terfi talebi geldiğinde yukarıdaki çekirdek blocker'lar çözülmeden olumlu ekonomik hüküm yok.

**N_eff ve eski deneyler:** `MISSION.md`/`BACKTEST.md`'in çoklu test kuralları üstündür. Mevcut trial tarihi korunur; `N_eff` tahmini yeni kanıt gibi kullanılıp eşik gevşetilmez. Hangi eski deneylerin hash/engine/karar bakımından güvenilir olduğu açıkça sınıflanır.

**C teslimat testi:** Bilerek bozuk null kalibrasyon, bozuk ledger event kimliği ve funding/lot regresyon fixture'larında ekonomik aday terfisi deterministik reddedilsin; aynı anda ayrı H1-A forecast protokolü kendi doğru kontrolleri geçtiği ölçüde koşabilsin. Skor üreten ajan, bağımsız skor kodunu veya sınav eşiklerini değiştiremesin.

### D — 7/24 süreklilik, doğrudan Telegram ve Night Mode

**Hedef:** Müdür her dakika düşünmez. Event olduğunda veya seyrek bakım zamanında uyanır; işçi bitince ilerler; boşta kalırsa token harcamaz. VPS kapanıp açılsa da focus, lease, kanıt ve outbox kaybolmaz.

**Tek iletişim:** Telegram → müdür. Sekreter/departman botları yok. Müdür canlı sayı gerektiğinde broker/ledger sorgular; eski SOUL satırından harcama, deney sayısı veya aktif iş durumu uydurmaz. Telegram chat kimliği/hijyeni doğrulanır, fakat Telegram metni OS insan kimliğinin yerine geçip mühür, merge, policy veya core onayı veremez.

**Night Mode:** Aynı yetki, aynı araştırma döngüsü; sadece insanın seçtiği `quiet_hours`/timezone içinde `INFO`/rutin bildirimleri **kalıcı outbox'ta** biriktirir. Kritik güvenlik ve sert limit olayları derhal gönderilir; kullanıcı kararı gerektiren istek tek bir idempotent kayıtta bekler, aynı mesajla tekrarlı uyandırmaz. Sabah `FOCUS | ne denendi | ne öğrenildi | geçersiz/UNKNOWN | sonraki iş | gereken karar | harcama` özeti gönderilir. Gece saati kullanıcı tarafından yapılandırılana kadar kendiliğinden saat uydurma.

**Yayına geçiş için üst-politika düzeltmesi:** `MISSION.md` içindeki 15–20 dakikalık durum mesajı kuralı, insanın açık kabulüyle “gündüz istenirse hafif durum, gece yalnız kritik; sabah bilimsel özet” olarak güncellenmeli. Bu değişiklik yapılana kadar v4.1 Night Mode'un mevcut misyonla çeliştiği belirtilir; sessizce yürürlüğe girdi denmez. Mevcut `factory/status.py` 900 saniyelik outbox mesajını yazmaya devam ettiği için **sadece Telegram prompt'u değiştirmek yetmez**.

**Süreklilik ve kurtarma:** `PAUSED` varsayılanı; önceden doğrulanan insan `resume` ile açar. Worker lease kaybolduğunda önce eski süreç fence edilir; sonra iş `failed`/`UNKNOWN` olur. Maliyete bağlı, belirsiz bitmiş araştırma otomatik yeniden koşulmaz; `UNKNOWN` sonuç untrusted metinle başarıya çevrilmez. Outbox bağlantı arızalarında idempotent tekrar gönderilir. Harcama veya policy doğruluğu bilinmiyorsa yeni maliyetli dispatch durur.

**D teslimat testi:** Gerçek 24 saatlik VPS pilotu, kontrollü restart/kill, bilinçli hatalı iş, outbox/Telegram kesintisi, `stop`, sert sağlayıcı limiti doğrulaması, gece/sabah sessizlik; broker DB/ledger hash'leri ve mandate sayaçları bozulmadan toparlanmalı.

## 3. İlk otonom bilimsel görev: H1A-D1

**Kaynak:** Kullanıcının 15 Ekim 2026 tarihli *Early Market Regime Forecasting — Scientific Monograph* HTML'i **araştırma kaynağıdır; yürütülmüş deney değildir**. Bu monografiye ait rakamlar tasarım önerileridir; Kepler'in K1–K10 sonuçları değildir. Müdür ilk iş olarak monografiyi tekrar yazmaz; uygulama öncesi yöntem hatalarını ve örneklem gücünü eleştirir.

**Birinci deney (donmadan önce bağımsız kontrol):**

- **Soru:** Mevcut momentum/etiket eşiği yakınlığı karşısında hacim sürprizi ve volatilite sıkışması, gelecek yönlü trend başlangıcını erken tahmin etmekte gerçekten artı bilgi taşıyor mu?
- **Hedef:** Önceden tanımlı olay için gelecek **7 tamamlanmış günlük bar** içinde `+onset`, `-onset` veya `none` tahmini. Rejim oluşumu ile sonradan teyit ayrılır; H1-B/H1-C sayıları H1-A skoru değildir.
- **Tasarım adayı:** 1D, BTC/ETH/SOL/XRP/BNB (survivorship caveat), `M0` temel olay oranı/duration, `M1` momentum + Z20/ER20 ve **threshold proximity**, `M2` = M1 + volatilite sıkışması + hacim sürprizi. 4H ve funding ilk turda yok; ayrı araştırma gerekçesi/ön kayıt gerektirir.
- **Etiketleme adayı:** Monografide Z20/ER20 ile operasyonelleştirilmiş onset; 10 nötr gün risk kümesi, ilk eşik geçişi, sonraki 10 günün 8'inde teyit. **Gelecekteki teyit yalnız olgunlaşmış eğitim etiketidir; t anındaki feature değildir.** 7 günlük horizon + teyit için 17 günlük maturity/purge denetimi.
- **Birincil karşılaştırma:** aynı dış zaman fold'ları ve aynı tarihlerde M2 vs güçlü M1; out-of-fold çok-sınıflı Brier ve ortak takvim blok bootstrap belirsizliği. Önerilen ön-kayıt eşiği: göreli Brier iyileşmesi en az %5 ve %95 alt güven sınırı > 0. Bu eşik bilimsel öneridir, mevcut evrensel Kepler gate'i değil.
- **Yardımcı metrikler:** calibrated loss, olay/yıl yanlış alarm, lead time, ayrık makro olay kümeleri, olayların her yön için yeterliliği. Monografinin planında ≥20 + ve ≥20 − teyitli onset, ≥12 ayrık takvim olayı kümesi; aksi hâlde `INCONCLUSIVE` düşünülür. Eşikler sonuç görüldükten sonra oynanmaz.
- **Önemli fizibilite itirazı:** `BACKTEST.md`'deki ana DEV penceresi 2022-01-01 → 2026-04-01 (~4,25 yıl). İlk 3 yıl eğitim ve 6 aylık outer fold tasarımında **yaklaşık iki tam dış fold** mümkündür; monografinin “mümkünse 5+ fold” hedefi bu pencerede garanti edilemez. 2020–2021 kayıtları varsa bunların erişimi/veri QC'si ayrıca doğrulanır; mühürlü dönem bu eksikliği kapatmak için açılmaz. Müdür protokolü dondurmadan **olay/fold yeterlilik fizibilitesini** incelemeli; eğer tanımı koruyarak test mümkün değilse `INCONCLUSIVE/INSUFFICIENT_DATA` kararı ve gerekli yeni bağımsız veri koşulu yazmalı.
- **Önce düşük maliyet:** sadece CPU, read-only DEV ve deterministik etiket/fixture. Forecast geçmezse pahalı backtest yok. Forecast geçerse risk-eşleştirilmiş momentum ve volatility-only baseline karşısında net ekonomik katkı için **ayrı protokol ve mevcut numba hakemi** gerekir.
- **Asla yapılmayacak:** sonuçtan sonra label/lookback/feature/evren/horizon değiştirip “aynı H1A-D1” diye koşmak; H1-B'yi H1-A zaferi saymak; raporun HTML kalitesini deney kanıtı sanmak; G3'e dokunmak.

**İlk görev çıktısı** şu tek satırlık durumlardan biriyle kapanır:

`FORECAST_SUPPORTED_IN_THIS_TEST` | `REJECT_INCREMENTAL_H1A` | `INCONCLUSIVE_LOW_POWER` | `INVALID_LEAKAGE_OR_PROTOCOL` | `BLOCKED_PERMISSION_OR_DATA`.

Bu kodlar **deney türüne özel iç sınıflandırmadır**; `BACKTEST.md` K1–K10 ekonomik kararlarını değiştirmez. Yeni kod veya API isimleri tasarımın kesin mevcut uygulaması olarak sunulmaz.

## 4. Issue/PR cehennemine geri dönmeme kuralı

Broker **tek operasyon kuyruğudur**. GitHub yalnız kalıcı mühendislik değişikliği ve inceleme için kullanılır. Tek ön kayıtlı hipotez için bir issue + üç PR + on ayrı kart açılmaz.

**Başlangıç WIP limiti:** 1 ana bilimsel iş + 1 gerçek engel giderici mühendislik işi. İstisna yalnız kanıtlanmış güvenlik/kritik muhasebe olayı. Bunu müdürün nezaketiyle değil job admission/claim ile uygula.

**Her yeni issue/PR önce sorar:** Mevcut bir kayıt aynı problemi kapsıyor mu? Bu iş H1-A forecast veya ilerideki ekonomik doğrulamanın gerçekten önünde mi? Tek bir küçük değişiklikle çözülebilir mi? Kullanıcıya ancak ana focus, risk veya sermaye etkileniyorsa karar getir.

**Dondurulan işler:** Tamamlanmamış eski PR'ları otomatik topluca merge etme. Güncel `main` farklıysa eski diff yeniden bazlanır, hash/test doğrulanır, insanın korumalı çekirdek incelemesi korunur. “23 issue, 10 PR sıfırlandı” başarı metriği değildir.

## 5. Uygulama kapsamı: dosya / değişiklik / bitiş kanıtı

Aşağıdaki maddeler **önerilen implementasyon haritası**dır. Kod ve dosyalar bugün değiştirilmemiştir; mühendisin mevcut API'yi inceleyerek en küçük değişikliği seçmesi gerekir.

| İş paketi | Dokunulacak mevcut yerler | Gerçek kabul |
|---|---|---|
| **T1 / sözleşme uyumu** | `MISSION.md`, `AGENTS.md`, `ARCHITECTURE.md`, `docs/factory.md` (V4'ü temellendiren v4.1 eki) | Kaynak türü, DEV istisnası, gece bildirimi ve otorite zinciri çelişmiyor; mimari test yeşil; eski hakem sözleşmesi korunuyor |
| **T2 / mandate** | `factory/broker.py`, `factory/store.py`, `factory/runner.py`, `factory/research.py`, `factory/policy.py`, root policy | İnsan UID doğrulaması; revoke/expire/quota testleri; atomik admission; `main`/G3/core izolasyonu |
| **T3 / güvenli aday lane** | Mevcut `factory/vps/*sandbox*` sarmalayıcıları, mevcut işçi/test hattı, gerekli **en küçük** artifact validator | Yeni agent kodu sır/ağ/bare-main erişimsiz DEV fixture'da koşuyor; kanıta terfi trusted scorer/denetimle yapılıyor; sandbox escape/yanlış sonuç sentetik testlerle reddediliyor |
| **T4 / evidence-memory** | `factory/store.py`, `factory/status.py` veya yakın modül, mevcut ledger yazıcısı | Claim her zaman kaynağa bağlı; yeni bet seçmeden retrieval receipt; engine-stale, contradiction, negative-dedupe ve restart testi |
| **T5 / gate ayrımı** | Önce mevcut istatistik/defter/hakem testleri ve blocker issue/PR'lar; gerekiyorsa dar güvenilir gate kontrolü | Forecast bağımsız koşabilir; ekonomik terfi `#46/#49/#42/#52` gibi kritik teyitler eksikken bloke; test geçme iddiası kaynaklı |
| **T6 / Telegram + Night Mode** | Mevcut Hermes entegrasyonu, broker outbox, `factory/status.py` ve policy | Müdürle tek sohbet; bilgi seviyesine göre bildirim; gece rutin sessiz; sabah tek özet; insan ayrıcalıkları chat metniyle alınamıyor |
| **T7 / 24 saat kabul** | Mevcut `make accept` testi varsa onu genişlet; `tests/test_factory_runtime.py`, `tests/test_factory_boundaries.py`, VPS kontrollü gözlem log'u | Aşağıdaki kabul senaryoları gerçekten yeşil; gerçek sağlayıcı hard cap görülmüş; 24 saat kesintisiz işletim kanıtlı |

**Önerilen iş sırası:** T1 ve T5'in kritik test tespiti → T2/T3 (gerçek yürütme) → T4 (öğrenme) → T6 (insanla işbirliği) → T7 (pilot). Gerektiği kadar paralellik; bağımlılık doğrulamadan paralel görev yığma yok. Bu bir *bağımlılık sırası*, yeni yönetim fazları değil.

## 6. Tek komut ve 24 saat kabul sözleşmesi

**İnsan eylemi:** Daha önce kabul edilmiş kurulum ve sınırlanmış DEV mandate'inden sonra **tek `resume`**. Komutun mevcut CLI/broker arayüzüne göre gerçek karşılığı uygulama/test sırasında sabitlenir; belgede yeni bir CLI varmış gibi davranma. Sıfırdan VPS provision etmek “tek komut” kapsamına girmez; önce güvenlik kabulü gerekir.

**Pilot şartları:** Gerçek DEV veri (G3 hariç), tek çalışabilir worker, önceden kayıtlı H1A-D1, kapalı gerçek para, sınırlı süre/trial/sağlayıcı harcaması ve kullanıcı tarafından tanımlanmış quiet hours. Test, mümkünse literatür hazırlığından otomatik kod/deney/yorumlamaya uzanır; metodolojik fizibilite yeterli değilse doğru `INCONCLUSIVE` hükmü de bilimsel sonuçtur.

### 6.1 Otomatik test matrisi

- [ ] `PAUSED` ilk kurulumda hiçbir deneyi başlatmaz; yalnız insan `resume` başlatır.
- [ ] Müdür focus'u ve H1-A/B/C ayrımını 24 saat ve tüm restartlar boyunca korur.
- [ ] Geçerli mandate ile yeni iş için tekil, hash'li prereg oluşur; limit dışı ve süresi bitmiş mandate reddedilir.
- [ ] Yeni aday kod `main`'i değiştirmeden, ağsız/secretsız, yalnız DEV verisiyle test olur; yetkisiz veriye erişme testi başarısız olur.
- [ ] Trial/period/engine/protocol/data/commit kimliği ve deneme sayacı çift kaydolmaz, başarısız deneme silinmez.
- [ ] Bağımsız sonuç skorlaması, gelecek bozma ve label-maturity/purge testleri sahte yüksek forecast sonucunu yakalar.
- [ ] K1–K10 ekonomik sonuçları trusted hakem/kalibrasyon tamamlanmadan `CANDIDATE`/`SEAL_PASS` olamaz.
- [ ] Müdür hafızadaki aynı negatif hipotezi bulur; gerekçesiz kopyasını tekrar koşmaz.
- [ ] Worker timeout, broker restart, Hermes restart, ağ arızası, Telegram outbox gecikmesi sonrası iş ve kanıt doğru toparlanır.
- [ ] `stop` çalışan süreci keser ve yeni iş alımını kapatır; revoke ve bütçe tükenmesi yeni iş alımını engeller.
- [ ] Gece rutin Telegram mesajı gelmez; kritik olay anında bildirilir; sabah kaynaklı kısa bilimsel özet çıkar.
- [ ] Gerçek dış sağlayıcı sert harcama limitleri doğrulanır; yerel USD tahmini gerçek kesin fatura diye sunulmaz.
- [ ] Bilimsel karar bağımsız test/receipt kaynaklarına dayanır; yaşanmamış sonuç yazılmaz.

### 6.2 Pilot başarı eşiği ve dürüst başarısızlık

**PASS:** 24 saatlık çalıştırma sırasında sistem olaylar üzerine ilerler ve *en az bir* tam kayıtlı döngü üretir: `focus → prior-evidence retrieval → prereg → izinli DEV çalışma (veya önceden tanımlı bilimsel yetersizlik kararı) → bağımsız kontrol → claim/lesson → next bet/IDLE → Telegram summary`. Maliyet, güvenlik ve mühür ihlali sıfır. Bir işçi / runtime çökmesi güvenli toparlanmış olabilir; olaylar loglanır. Sahte “hep aktiftik” değil gözlenmiş runtime kayıtları gerekir.

**PARTIAL:** Müdür/işçiler yeniden başlayabiliyor ama gerçek DEV deneyini kendi başına başlatamıyor ya da hafıza bir sonraki seçimi etkilemiyor. Tamamlanmamış olan basamak açıkça raporlanır. Sadece bir monografi daha yazmak tam başarı değildir.

**FAIL:** Yetkisiz onay, G3 erişimi, broker/ledger kaybı, limit dışında yeni maliyetli iş, atlanan bilimsel gate veya üretilmemiş sonucu yapılmış diye raporlama. Böyle durumda `PAUSED/STOPPED`, olay kaydı ve dar kapsamlı düzeltme gerekir. Fail'e çözüm olarak bütün fabrikayı V5'e taşıma.

**24 saat raporu** yalnız şu kısa özetleri içerir: aktif program, verilen mandate kapsamı, tamamlanan araştırma kararları, geçersiz/yetersiz deneyler, retrievalla önlenmiş tekrarlar, deneme/trial sayısı ve kullanılan gerçek/ölçülemeyen kaynak, öğrenme/sonraki iş, açık blokaj ve insan kararı, restart/stop/izin testleri. Ölçülmemiş metrikte `UNKNOWN` yaz.

## 7. Müdür davranış sözleşmesi (SOUL'e kısa aktarım)

> **Sen Kepler'in bilimsel müdürüsün.** Misyonu ve aktif odağı koru. Önce geçmiş kanıtları sorgula, sonra gerçekten yeni bir yanlışlanabilir soru seç. Kısa, tek-hipotezli, ön kayıtlı deneyleri yetkili DEV sınırında bitir; başarısız deneyden öğren ve gereksiz varyant üretme. Uzmanları gerektiğinde çalıştır, ama departman veya ticket tiyatrosu kurma. Gerçek sayıları sadece trusted kayıt ve doğrulanmış receipts'ten bildir. Stratejik pivotları insana öner; yürütme yetkisi, `main`, çekirdek, mühür, gerçek para ve bütçe sınırlarını kendin yükseltme. İnsan yokken araştırmaya devam et, fakat yetki/kanıt yokken beklemeyi bil. Her uyanışın sonunda **ne öğrendik, sırada ne var, senden karar gerekiyor mu** sorularına cevap ver.

SOUL **özet davranış** içindir; bilimsel kaynak, mutable policy, hash, deney metrikleri veya broker yetkisinin kendisi değildir.

## 8. Dondurulmuş kapsam ve V5 için tek meşru tetik

**V4.1 kapsamında yok:** yeni sekreter, ek Telegram botu, sürekli çalışan 8 araştırmacı, yeni vector DB, yeni workflow ürünü, baştan yazılmış backtesting motoru, otomatik `main` merge, ajan yetkisine G3 veya gerçek para açılması, sonuç geldikçe etiket/parametre araması, her deney için HTML monografi, 23 issue/10 PR'ı kör toplu kapatma, sırf yoğunluk gösteren cron görevleri.

**V5 tartışma koşulu:** V4.1'in gerçek pilotundaki bir başarısızlıkla aynı güvenli davranışın küçük değişiklikle sağlanamadığı **ölçülmüş** olmalı; darboğaz kaydı, yeniden üretim, en küçük çözüm denemesi ve neden yetersiz kaldığı gösterilmeli. Pilot yapılmadan V5 tasarımı açılmaz.

---

## Nihai uygulama kararı

**Önce çalışan loop, sonra yeni teori.** İlk hedef 24 saatlik özerk **H1-A araştırma döngüsü**, değil 24 saatlik sonsuz LLM konuşması. Sonuç `NO_EDGE`, `INCONCLUSIVE` veya `BLOCKED` bile olsa kayıt güvenilir ve araştırma kararı anlamlıysa fabrika öğrenmiştir. **Ekonomik edge iddiası** ise her durumda Kepler'in finansal hakem, bağımsız veri, null/çoklu deneme, maliyet ve mühür sınırlarına tabidir.