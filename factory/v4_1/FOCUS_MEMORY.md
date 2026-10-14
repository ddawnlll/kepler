# Kepler Research Factory — v4

**Odağı olan, öğrenen, yalın araştırma organizasyonu**  
**Durum:** Eleştirel tasarım önerisi; uygulanmadı, test edilmedi, `main` değiştirilmedi. 15 Ekim 2026.

> **Yetki:** `MISSION.md`, `BACKTEST.md`, `ARCHITECTURE.md`, `AGENTS.md` ve `tests/test_architecture.py` yürürlüktedir. Bu belge onların üstüne yeni politika koymaz. Açık çelişkiler §13'te işaretlenmiştir. Kabul edildiğinde `docs/factory.md` yerine geçmesi ve ilgili üst belgelerin bilinçli biçimde uyarlanması gerekir.
>
> **Kanıt sınırı:** `factory/broker.py`, `factory/store.py`, `factory/runner.py`, `factory/research.py`, `factory/merge_gate.py` incelendi. `factory/research.py` mevcut durumda yalnız onaylı `main` kodu ve ön onaylı DEV protokolünü kabul eder. VPS/Modal uçtan uca işletim bu taslağın parçası olarak çalıştırılmadı. Sistemin 7/24 hazır olduğu varsayılmıyor.

## 0. Tasarım cümlesi

**Bir amaç → az sayıda araştırma programı → ön kayıtlı kısa deneyler → doğrulanabilir kanıt → geri çağrılabilir öğrenme → sonraki en değerli soru.**

Kepler'in ürünü görev, issue, PR, rapor sayısı veya ajan etkinliği değildir. Ürün, kripto-perpetual piyasasında maliyet sonrası güvenilir edge hakkında verilen bilimsel karardır: `NO_EDGE`, `WEAK/ZAYIF`, `ADAY`, `INCONCLUSIVE` ve yalnız otorite belgelerinin izin verdiği terfi sonuçları.

**Müdür araştırma direktörüdür, sekreter veya otomatik issue fabrikası değil.** Stratejik odağı korur, kaynak dağıtır, ön kabulleri sorgular, uzman çağırır, sonuçlardan öğrenir ve kullanıcının kararını gerektiren sınırları bilir.

Tek insan iletişim yüzeyi: müdürle doğrudan Telegram sohbeti. Kod çalışan asıl iş alanı: Kepler repo + güvenilir broker + izole işçiler + DEV deney motoru. Telegram bir yürütme/kimlik yükseltme kanalı değildir.

## 1. Amaç hiyerarşisi: neden çalıştığını unutmasın

Üç farklı zaman ölçeği vardır. Bunlar departman veya yeni doküman değildir; broker'da saklanan hedef kayıtlarıdır.

### 1.1 Mission (değişmez üst amaç)

Kaynak `MISSION.md`: 500 USD başlangıç sermayesi için ücretsiz Binance USDT-M tarihsel veriyle, gerçekçi fee/funding/slippage/likidasyon ve risk kısıtları altında bağımsız veride sürdürülebilir edge olup olmadığını dürüst biçimde test etmek. Negatif sonuç başarıyla tamamlanmış araştırma sayılır. Bu katmanı müdür kendiliğinden değiştiremez.

### 1.2 Focus (insanın verdiği veya onayladığı güncel yön)

**Mevcut önerilen ana odak:** `EDGE_DISCOVERY`. Bir alt araştırma programı: `EARLY_REGIME_FORECASTING`.

- Birincil bilimsel soru: H1-A, rejim başlamadan 1–7 gün önce öncü bilgi var mı?
- Açık rakip sorular: H1-B erken tespit/devamlılık; H1-C volatilite öngörüsü. Bunların başarısı H1-A lehine sayılmaz.
- Ekonomik soru: Bu bilginin maksimum 21 gün tutulan long/short işlemlerde risk-eşleştirilmiş basit momentumdan maliyet sonrası bağımsız katkısı var mı?
- **Hedef iki aşamalı kanıttır:** öngörü kalitesi ve ekonomik yarar farklı iddialardır; ikisi tek bir Sharpe skoruna indirgenmez.
- Müdür programı sürdürür, alt hipotezleri reddeder/değiştirir, birinci amaç hakkında ilerleme kaydeder. H1-A'dan H1-B'ye sessizce pivot yapamaz. Stratejik yön değişikliğini gerekçeyle kullanıcıya önerir.

### 1.3 Next bets (müdürün seçtiği taktik iş)

Müdür en fazla **bir ana bilimsel program** ve gerekirse birkaç bağımsız kısa iş üzerinde çalışır. Bu sınır önerilen ilk ayardır, sabit bilimsel yasa değil. Her iş bir odak hedefini, bir sonuç teslimini ve bitiş şartını referanslar. "Yeni iş üretmiş olmak" ilerleme sayılmaz.

**Taktik iş önceliği:** (a) bilimsel doğruluğu engelleyen açık hata, (b) mevcut ana odağın en yüksek bilgi değerli yanlışlanabilir sorusu, (c) bunu çalıştırmak için *kanıtlanmış* teknik engel, (d) geri kalmış bakım. Sadece GitHub etiketinin P0/P1 olması yeterli değildir; kapsam ve kanıt etkisi de değerlendirilir.

**Örnek kaynak tahsisi (kullanıcıyla ayarlanabilir, zorunlu kota değil):** araştırma ve deney `%70`, bilimsel güvenilirlik `%20`, bakım `%10`. Hatalı hakem veya sızıntı bulunursa güvenilirlik işi geçici olarak tüm araştırmanın önüne geçer. Sadece daha fazla GPU/agent kullanımını teşvik eden kota yoktur.

### 1.4 Hedef kaydı (broker'ın doğruluk kaynağı)

İlk sürümde `factory/store.py` içinde `goals`/`programs` kayıtları veya eşdeğer basit yapı; ayrı Notion, Jira, Kanban hakikat kaynağı yok.

```yaml
id: EDGE_DISCOVERY
mission_ref: MISSION.md
focus: EARLY_REGIME_FORECASTING
hypothesis_primary: H1-A
alternative_tracks: [H1-B, H1-C]
status: active
success: "independent forecast evidence; net economic comparison separately"
current_bet: "H1A-D1: M2 vs strong momentum M1"
next_decision: "pre-registered feasibility protocol review"
constraint_refs: [MISSION.md, BACKTEST.md]
source: "user directive / approved focus"
updated_at: "2026-10-15"
```

Kullanıcı Telegram'da "odağımız funding oldu" diyebilir: müdür yeni focus önerisini gösterip **kullanıcı mesajını yetkili kimlikle doğrulayarak** kayıt günceller; kritik yürütme hakları değişmez. Odak sürümleri ve eski kararlar korunur. Yönetici araştırma alt işlerini kendisi seçebilir; mission / mühür / risk / gerçek para kurallarını değiştiremez.

## 2. Müdürün yürütme döngüsü

```text
                MISSION + ACTIVE FOCUS
                          │
            oku: yakın olaylar, kanıt, darboğazlar
                          │
                 bir sonraki BET'i seç
                   ┌──────┴──────┐
                   │             │
            LITERATURE GAP   PROTOCOL READY
                   │             │
         kısa/deep research   prereg + kontrollü kod
                   │             │
          çelişen kanıtları  sentetik test → DEV hakem
             incele              │
                   └──────┬──────┘
                          │
          bağımsız eleştiri / mekanik değerlendirme
                          │
      MEMORY: ne denendi, ne öğrenildi, neyi bilmiyoruz?
                          │
            odakta kal / yeni bet / kullanıcıya pivot öner
```

**Her döngü sonunda tek soru:** Bir sonraki küçük deney karar belirsizliğini gerçekten azaltacak mı? Hayırsa yeni job açma. Beklemek, daha güçlü veri beklemek veya `NO_EDGE` raporlamak geçerli sonuçtur.

Derin monografi **araştırma açığının büyük olduğu ve yön belirleyecek durumda** üretilir; her parametre, her günlük görev veya her issue için tekrar yazılmaz. Monografinin amacı iyi görünen rapor üretmek değil, ölçülebilir/yanlışlanabilir protokol ve karşıt bulgu getirmektir.

## 3. İşçi modeli: üç yetenek, sıfır departman

1. **Araştırmacı (on demand):** literatür, mekanizma, alternatif açıklama, as-of veri erişimi, minimal deney tasarımı. Gerekirse akademik seviyede HTML monografi üretebilir. Metin ve kaynak dışı deney sonucu icat edemez.
2. **Uygulayıcı (on demand):** dondurulan hipotezi bağımsız deney koduna dönüştürür; sentetik test ve izin verilen DEV koşularını yürütür. Kritik çekirdek, mühür ve canlı kimlik bilgileri yoktur.
3. **Hakem/eleştirmen (on demand):** kör nokta, etiket daireselliği, lookahead, yanlış benchmark, muhasebe ve iddia-deney uyumu taraması. "Başarılı" demesi deterministik K1–K10 yerine geçmez.

Her iş için üç ajanı da uyandırmak gereksiz. Müdür kısa işte tek işçiyle ilerler; iddia/terfi veya kritik koda dokunulmasıyla bağımsız inceleme zorunlu olur. Rollerin ayrı Telegram hesabı veya sürekli akan anıları yoktur. İşçi taze bağlam alır; müdürün ve fabrikanın **ortak hafızasını** sorgular.

Birden fazla işçi aynı anda çalışabilir; ilk kurulumda tek izole sandbox politikasına (`workers_max=1`) uyulur. Paralelliği arttırmak istendiğinde ayrı uid/sandbox, kaynak sınırı ve ledger izolasyonu kanıtlanmadan sadece konfigürasyon sayısı yükseltilmez.

## 4. Araştırma eylem sözleşmesi

**Araştırma brifi** minimum şu alanları taşır:

```yaml
program: EARLY_REGIME_FORECASTING
question: "Do volume surprises and volatility compression forecast pre-onset?"
hypothesis: H1-A
counterfactual: "M1 momentum + threshold-distance already explains it"
existing_evidence: ["monograph: section 06-12", "Kepler BACKTEST §11"]
allowed_data: "DEV, <= 2026-04-01; no G3"
artifact: "preregistered forecast protocol + test/report"
stop_if: "data insufficient, leakage, weak incremental forecast"
budget: "bounded, stated before dispatch"
```

Bir araştırma brifi kendi başına deneme yetkisi vermez. Her koşu, MISSION kural 11 ve BACKTEST ile uyumlu ön kayıt; config/kod/veri hash; aile/trial sayacı; geriye doğru okunabilir sonuç kimliği gerektirir.

**Eylem tipleri:** `read`, `research`, `protocol`, `sandbox_test`, `dev_experiment`, `review`, `propose_change`. Tamamını GitHub issue'suna çevirmeyiz. Sadece repository düzeyinde kalıcı mühendislik işi veya insan inceleme ihtiyacı doğarsa issue/PR açılır.

## 5. Gönderdiğin monografiyle örnek uçtan uca çalışma

**Girdi:** *Early Market Regime Forecasting* monografisi. Bu, henüz koşulmuş deney değil, araştırma hipotezi ve önerilen protokoldür.

1. Müdür kaynağı ve sürümü kaydeder; H1-A ve H1-B/H1-C ayrımını stratejik hafızaya ekler. Önemli hüküm: ilk iş, basit momentum ile eşik yakınlığını yenip yenmediğini test etmektir.
2. Bir araştırmacı monografiyi **tekrarlamaz**, denetlenebilir teknik eleştiri yapar: operasyonalize edilmiş onset tanımı, 10-gün teyit ve 7-gün horizon; etiket olgunlaşma/purge, olay kümesi sayısı, fold kapsamı; M0/M1/M2 karşılaştırmasının yeterliliği. Çelişki varsa düzeltmeyi **deneyden önce** gerekçelendirir.
3. Müdür *tek birincil karşılaştırmayı* seçer: güçlü momentum M1 karşısında volatilite sıkışması + hacim sürprizli M2. M0 bir kalibrasyon/baz oran kontrolüdür. 1D ilk deney, 4H ve funding yeni bağımsız protokoller olarak sonraya bırakılır.
4. Ön kayıtlı H1A-D1 kartı; olay tanımı ve doğrulama, varsayılan ΔBrier ölçütü, yanlış alarm, lead-time, yeterli bağımsız küme, tüm koşu maliyetleri **hash'lenir**. Eşikler denemeden sonra değişmez. İlk aşama *sadece tahmin*: trading hakemini boşuna çalıştırmaz.
5. Uygulayıcı kodu veri sızıntısı, nedensel zaman damgası, baz model, kalibrasyon ve sentetik fixture testlerinden geçirir. Mevcut izinlerin elverdiği durumda kontrollü DEV çalışır; aksi hâlde merge/izin kararı bekleyen bir değişiklik önerisi çıkar. **Sırf kod yazıldı diye koşuldu denmez.**
6. Deney sonucu `SUPPORTED_THIS_TEST` / `REJECTED_INCREMENTAL_H1A` / `INCONCLUSIVE` gibi *forecast içi* kararlarla raporlanır; bunlar Kepler'in K1–K10 **trading-edge** kararlarıyla karıştırılmaz. Forecast olumluysa ekonomik deney ayrı ön kayıtla, mevcut hakemin net-maliyetli risk-eşleştirilmiş basit momentum karşılaştırmasıyla yapılır.
7. Müdür kanıt hafızasına şunu işler: **hangi etiket/ufuk/veride**, hangi baseline'a karşı hangi sonuç; nüans ve zayıflıklar. H1-A başarısızsa H1-B'nin ayrı değerini önerebilir ama H1-A'yı başarılı diye raporlayamaz.

**Kritik sınır:** Kullanıcının monografi istemindeki "henüz strateji uygulama/pahalı backtest başlatma" yasağı o çalışmanın kapsamındadır; bu belge araştırmayı geçmişte koşulmuş gibi göstermez. Buradaki sonraki deney eylemleri ayrı, yetkilendirilmiş iş olarak başlatılır.

## 6. Hafıza: sohbet geçmişi değil, bilimsel birikim

Hermes'in küçük `MEMORY.md`/`USER.md` özetleri yalnız *bootstrap* işlevi görür. Ayrıntılı bilimsel bilgi, operasyonel durum ve deney tarihi **Hermes profil dosyasına gömülmez**. Doğruluk kaynakları Kepler'e aittir.

| Katman | Ne saklar? | Yetkili kaynak | Ne zaman okunur? |
|---|---|---|---|
| 0 — **Sözleşme** | MISSION, BACKTEST, mühür, yetki | Repo + trusted policy | Her kritik işte |
| 1 — **Stratejik hafıza** | Amaç, focus, hipotez kimlikleri, yasak pivot | Broker DB (`goals`, `programs`) | Müdür başlangıcında ve iş seçerken |
| 2 — **Episodik hafıza** | Görev, tamamlanma, hata, izin, maliyet | Broker `events` / jobs / outbox | Durum ve yeniden başlatmada |
| 3 — **Bilimsel kanıt hafızası** | Ön kayıt, sonuç, değişkenler, hash, trial | Mevcut append-only ledger + artifacts | Her araştırma öncesi/sonrası |
| 4 — **Öğrenilmiş dersler** | Kapsamlı, kaynaklı, çürütülebilir bulgular | Broker DB `claims`/`lessons`, linkli ledger | Benzer fikir seçerken |
| 5 — **Arşiv arama** | Sohbet/HTML/PDF/GitHub tartışmaları | Dosyalar, repo, session search, SQLite FTS5 | Gerektiğinde arama |

**Açılış bağlamı sadece şu altı şeyi içermeli:** mission özeti ve otorite bağlantısı; aktif focus; tek mevcut bet; son birkaç önemli karar; açık engel; son istatistik/kanıt sorgusunun ID'si. Saatlerce konuşmanın özeti veya her geçmiş issue prompt'a basılmaz.

### 6.1 Bir bilimsel hafıza kaydı mutlaka kapsam taşır

```yaml
claim_id: CLAIM_H1A_001
statement: "M2 adds no measurable forecast skill over momentum M1"
status: hypothetical_example_not_a_result
hypothesis: H1-A
scope:
  label: "Z20/ER20 confirmed directional trend onset"
  universe: "BTC ETH SOL XRP BNB"
  horizon: "7d"
  data_period: "DEV only"
compared_with: "M1, same folds"
source_refs: ["run_id", "protocol_sha", "code_sha", "data_sha"]
conclusion_limit: "Does not rule out all market transitions or H1-B/H1-C"
last_review: "not applicable; illustrative record"
```

**Bu kayıt ÖRNEKTİR, bulgu değildir.** Gerçek tabloya `OBSERVED` olarak yalnız doğrulanmış ledger referanslı deney sonucu girer.

### 6.2 Okuma/yazma mekanizması

- İş başlamadan `retrieve(focus, mechanism, family, baselines, label, period)` çağrılır. Önce ilişkili başarısız testler, çelişkiler ve deney maliyetleri döner; ilgisiz anılar gelmez.
- İş bittikten sonra structured `evidence_event` yazılır, sonucu ledger'dan doğrulanır; sonra ayrı `lesson` türetilir. İnsan/eleştirmen gerekmedikçe basit olgu yazımı otomatik olabilir; **LLM çıkarımı sonuç yerine geçmez**.
- `claim.status ∈ {HYPOTHESIS, LITERATURE, PROJECT_OBSERVATION, DESIGN_INFERENCE, UNKNOWN, CONTRADICTED, SUPERSEDED}`. Tüm bilimsel çıkarımlar en az bir kaynak kimliği ve kapsam taşır.
- Yeni kanıt eskisiyle çatışırsa eskisi silinmez: `supersedes`, `contradicts` ve zaman damgasıyla bağlanır. Motor değişince eski Sharpe/net PnL yeni sürüm için `UNVERIFIED_UNDER_NEW_ENGINE` olur.
- Geçmiş negatif sonuç belirsiz biçimde `H1-A YOK` diye genellenmez: sadece tanımlanmış varyant/test için reddedilmiş hipotezdir.
- Etkin olmayan işlerin uzun sohbet özetlerini prompt'a taşıma; `SQLite FTS5` gibi düz metin arama ilk yeterli çözümdür. Vektör veritabanı, knowledge graph, Mem0/Honcho vb. ancak ölçülmüş sorgu başarısızlığına karşı kıyasla eklenir.
- Bir claim'in kaynak referansı kayıpsa veya zaman/politika bilgisi yoksa araştırmada **UNKNOWN** döner. Bellek yazısının kendisi kaynak değildir.

### 6.3 Yöntem hafızası ≠ sonuç hafızası

Tekrarlanan 5+ adımlı operasyonlar için şablon/skill olabilir: `monograph_review`, `pre_register`, `dev_eval`, `audit_regime_leakage`, `report_decision`. Bunlar `nasıl`, claim tablosu `ne biliyoruz` sorusunu yanıtlar. Süreç şablonu yeni otorite yaratmaz; `BACKTEST.md` gibi belgeleri kopyalayıp çatallaştırmaz.

## 7. Tek kuyruk, GitHub ile sakin ilişki

**Tek operasyon kaynağı:** mevcut `factory/store.py` SQLite. GitHub issue ve PR'lar **proje mühendisliği kayıtlarıdır**, bilimsel her denemenin görevi değildir. Telegram sohbet geçmişi, Hermes Kanban ve `TASKS.md` operasyonel verinin paralel ana veritabanları olmaz; gerekiyorsa yansıtılır.

| Olay | Yeni issue? | Yeni PR? | Doğru kayıt |
|---|---|---|---|
| Bir literatür sorusunu tartışma | Hayır | Hayır | Research job + kaynak |
| Ön kayıtlı H1A-D1 deneyini koşma | Normalde hayır | Kod gerekiyorsa | Ledger + artifact |
| Aynı null kalibrasyonu hatası birçok işi bozuyor | Mevcut issue'yu kullan | Düzeltme hazırlanırsa | İlgili issue/PR + test |
| Ufak sandbox düzeltmesi | Gerekmedikçe hayır | Mevcut branch veya dar PR | Değişiklik/kanıt |
| Mühür veya kritik hakem değişikliği | Gerekirse | İnsan incelemesiyle | Ayrı yetki ve bağımsız audit |

Güncel repo örneği (15 Ekim sorgusu): 23 açık issue, 10 açık PR. Müdür önce bunları **aynı hedefe etkilerine ve bağımlılıklarına** göre sınıflandırır; sırf sayıları sıfırlamak için rastgele kapatıp merge etmez. Örnek olarak #46 bootstrap-null kalibrasyonu gelecekteki güvenilirliğe dokunabilir; #51 satır tavanı karar gerektirir ama doğrudan edge değildir; #52 güncel hakem gerçek-veri muhasebesi ekonomik teste etki edebilir. Bunlar tümüyle aynı öncelik kümesinde değildir.

**Anti-hell kuralları:**

- **WIP limiti:** önerilen başlangıç 1 ana araştırma + 1 engel giderici mühendislik işi; bunu salt metinle değil broker `claim` ile uygula.
- Yeni iş açmadan eski açık işlerde eşdeğeri var mı `search` ile kontrol et.
- Issue kapanması = gerçek kabul kanıtı veya açık `not planned` gerekçesi. PR merge = ayrı doğru test ve yetki; başlık sayımı başarı değildir.
- Eksik bağımlılık varsa yeni 12 görev yaratma; bir blokaj kaydı oluştur, ilgili işi beklet veya farklı bağımsız araştırmaya geç.
- Müdür aynı anda on ayrı teoriyi derinleştirmez. Negatif bulgu yüzünden bilimsizce varyant çoğaltmaz.
- Günlük karar raporu hedef, sonuç ve engeli söyler; GitHub housekeeping çıktısı kendi başına ilerleme sayılmaz.

## 8. Araştırmayı hızlandırma: hızlı düşün, kontrollü ölç

**Hızlı yol:** önceki kanıt sorgusu (ucuz) → kısa bilimsel karar (ucuz) → tek ön kayıt (kısa) → sentetik doğrulama → izinli CPU/DEV testi → otomatik ölçüm → hafıza. İyi çalışan hat tekrar yazılmaz.

- **Rejime dair olasılık deneyi** için backtest, GPU, vectorbt veya yeni yürütme motoru zorunlu değil. Önce minimal CPU özellik/label/forward-CV testini seç; ekonomik değeri sonra Kepler'in tek numba hakemiyle ayrı protokol olarak sına.
- Maliyet/zaman tavanı iş başlamadan yazılır; gerçek ölçüm sisteme döner. Derin monografiye sık sık ihtiyaç yoktur. Çok ucuz fikirler dahi aynı tarihsel veride gizli çoklu test borcu yaratır.
- `BACKTEST.md` K1–K10 kapıları finansal trading-edge adayları içindir; probabilistik forecast deneyindeki Brier, log loss, calibration ve false alarms ayrı bilimsel düzlemdir. Bu ayrım hem raporda hem hafızada makine-okunur olmalıdır.
- **Öğrenme döngüsü = akıllı araştırma seçimi; random grid brute force değil.** "Bir sürü ucuz model" gerekçe olmadan 10 bin hipotez test etme izni değildir.

## 9. Devamlılık ve yetki: müdür gece de çalışabilir mi?

**Bugünkü somut sınır:** `factory/research.py` onaylı `main` + önceden commit'lenmiş ayrı protokol + izinli `script/argv` ister; `factory/runner.py` `research` işini `approved_by_uid` üzerinden insan onayına bağlar. `merge_gate.py` insan `review` ve ayrıca `merge` olmadan `main` değişikliğini reddeder. Bunlar güzel koruma ama ilk tasarımın amaçladığı **yeni fikir→yeni kod→yeni deney** otomasyonunu bloke edebilir.

**Hedef davranış:** İnsan bir **bounded DEV research mandate** onaylar; müdür bunun içindeki bilimsel alt soruları/ön kayıtları kendisi belirler ve tekrarlı izin istemeden çalışabilir. Bunun nasıl uygulanacağı henüz doğrulanmış değil. Yeni oluşturulan Python'u özel bir sandbox'ta analiz/fixture ile çalıştırmak ile Modal DEV gerçek verisine eriştirip araştırma sonuç defterine sokmak **farklı güvenlik kararlarıdır**.

Olası güvenli tasarım: sınırları belirli, kullanıcıca onaylanmış araştırma programına bağlı tek-use signed/scoped mandate; immutable protokol snapshot; izole veri görünürlüğü; izinli yürütme yüzeyi; server-side bütçe; artefact/ledger doğrulama; bounded retries. Yeni worker kodu doğrudan production `main`, kritik çekirdek veya mühür erişimi almaz. Bu genişleme **MISSION/AGENTS/broker güven sınırlarıyla uyumlandırılıp ayrı red-team kabulünden geçmeden çalışıyor varsayılmaz.**

Manuel merge ve kritik kod yetkisi olduğu gibi kalır. İnsan uzaktayken iş eksik yetkiye takılırsa müdür küçük hazırlıkları bitirir, `blocked_needs_human` üretir ve çember çizmez.

## 10. Raporlama: spam değil, karar

Müdür tek Telegram sohbetine konuşur. İnsan sorarsa hedefi, son bulguyu, aktif işleri ve kaynak durumunu broker/ledger'dan canlı sorgular; sayı hafızadan okunmaz.

Örnek haftalık karar özeti:

> **Odak:** H1-A — pre-onset forecast.  
> **Öğrendik:** Monografideki ana risk momentum/eşik yakınlığı; bu hâlâ deney sonucu değil.  
> **Şu an:** H1A-D1 protokolünün bağımsız eleştirisi.  
> **Engel:** Yeni DEV deney kodu için mevcut broker `main`/insan yetki sınırı.  
> **Sonraki hareket:** Protokol dondurulunca kod/fixture hazırlığı; ekonomik backtest henüz yok.  
> **Senden gereken:** Gerekliyse yeni DEV yetki modeline tasarım onayı.

Mevcut `MISSION.md`, **15–20 dakikalık durum mesajı** istiyor. Bu değiştirilene kadar sessiz sistem bunu çiğneyemez; minimal, LLM'siz delta/status mekanizması kullanılabilir. Gerçekten sadece olay bazlı Telegram bildirimine geçmek isteniyorsa ilgili üst belge insan kararıyla düzeltilmelidir. Yüksek öncelikli çökme/para riski her zaman hemen raporlanır; bilimsel işlem başarısı sadece ledger receipt'inden kaynaklanır.

## 11. Gece boyu insan yokken davranış

- Hedef belli ama iş yok: müdür ilk iddiaları sorgular; varsa en değerli izinli işe geçer; yoksa uydurma iş üretmeden bekler.
- Güncel kayıt çok eski: yeni araştırmayı yanlış engine/period verisine dayandırmadan önce bilgiyi `STALE` işaretler ve doğrular.
- İşçi çöktü: idempotent kayıt, heartbeat, lease fencing, bounded retry. Araştırma yarım kaldıysa sonuç `UNKNOWN`, sahte `NO_EDGE` veya otomatik aynı deney tekrarı değil.
- H1-A veri yetersiz çıktı: `INCONCLUSIVE`; kalan çalışma yeni bağımsız veri veya yeni kullanıcı kararı gerektirebilir. Eşik düşürmek "öğrenme" değildir.
- Yeni iş ancak kapsamlı dış doğrulamayla mümkün: insan engelini tek kez bildirir; aynı raporu 15 dakikada bir başka kelimelerle spamlamaz.
- Mühürlü dönem/gerçek para: LLM yetkisinde değildir. Korumalı çekirdek değişikliği ayrıca insan yetkisi ve bağımsız inceleme gerektirir.

## 12. Kabul testi: rol yapmayan fabrika

Tasarımın başarılı kabulü için *gerçek* uçtan uca gözlem gerekir:

1. İnsan Telegram'da "Focus = H1-A" der; yetkili broker hedef sürümünü kaydeder. 48 saat sonra yeni müdür oturumu aynı amacı kaynaklı biçimde geri çağırır.
2. Müdür monografiyi ana kaynak alıp H1-A / H1-B / H1-C'yi karıştırmadan daha kısa, eleştirel çalışma brifi hazırlar. Metin eleştirisi bir sonuç olarak kaydolur, trade sonucu olarak değil.
3. İşçi hazırladığı protocol'ü gerçek koşudan **önce** dondurur; aynı kod/veri/protokol tekrarlandığında sonuç ile deneme kimliği idempotent ve auditable olur. Her çalıştırma uygun trial/negatif sonuç sayımına girer.
4. Müdür, geçmişte reddedilmiş aynı ekonomik mekanizmayı yeni adla getirince hafıza geri çağırır ve ya reddeder ya **gerçekten farklı** hipotezi açıkça gerekçelendirir.
5. Kod yazıldı ama broker yetki vermedi: `blocked_needs_human` raporu doğar, `DONE`/`TESTED` denmez. İşçi hiçbir şekilde token ya da mühür erişimi edinemez.
6. Geçerli, önceden izinli DEV koşusu sonrası ledger/istatistik raporu üretilir, bilimsel `forecast` ile Kepler `trading-edge` kararları birbirine karışmaz.
7. Müdür mevcut repo issue/PR'larını çoğaltmadan bilimsel blokajları bulur; örneğin istatistik kalibrasyonu sorunu H1-A forecast testini gerçekte engelliyorsa önce onu çözer, sadece genel backlog var diye araştırma durmaz.
8. Broker/Gateway restart, outbox kesintisi, lease timeout ve bütçe limiti altında hedef, bilimsel hash'ler ve durum kaybolmaz. Çift deneme veya çift merge olmaz.
9. Gerçek 24 saatlik işletim ve dış sağlayıcı hard cap doğrulaması olmadan "7/24 hazır" etiketi verilmez.

**Asıl kalite ölçüleri:** kanıt üretme süresi, aynı soru için tekrar harcanan iş miktarı, yanlış olumlu sonuç oranı, öğrenmenin geri çağırma doğruluğu, insana düşen gerçek blokaj sayısı ve bütçe. Ajan sayısı, token hacmi, issue kapatma hızı ve HTML uzunluğu başarı ölçütü değildir.

## 13. Repo ile açıkça uzlaştırılması gerekenler

1. **Hipotez kaynağı:** `MISSION.md` öncelikle trading kitaplarını yazar. Bu örnek monografi akademik makalelere dayanır. Kaynak politikasının kitap + hakemli makale + proje negatif kanıtını kapsayacak biçimde değiştirilmesi kullanıcı onayı gerektirir; v4 bunu sessizce yürürlüğe koymaz.
2. **Telegram ritmi:** `MISSION.md` 15–20 dakika ister; yalnız olay-bazlı çalışma için üst belge revize edilmelidir. Mevcut politika süresince hafif deterministik status geçerlidir.
3. **Tam otonom araştırma:** `AGENTS.md`, `factory/research.py`, `factory/runner.py`, `factory/merge_gate.py` main/human kapılarını zorlar. Yeni DEV mandate ve kod yürütme tasarımı bunlara aykırıdır; test ve bilinçli politika değişikliği olmadan uygulanmaz.
4. **ML kapsamı:** v2 `docs/factory.md` model eğitimini kapsam dışı sayar, monografide ise basit multinomial ridge model bir *forecast araştırma aracı* olarak kullanılır. Bu genişleme kabul edilirken deney türlerinin farklılığı ve K1–K10 ekonomiye geçiş sınırı açık tutulmalıdır.
5. **21 gün:** H1-A için seçilmiş maks işlem ufkudur; `MISSION.md` genel swing temposunun otomatik global değişikliği değildir.
6. **Bütçe ve bilimsel eşikler:** `MISSION/BACKTEST` üstün tutulur. Monografideki Brier/false alarm eşikleri yalnız onun önerdiği ayrı forecast protokolünün varsayımlarıdır; fabrika genel test çıtası olarak dayatılamaz.

## 14. Bilinçli biçimde yapılmayanlar

**Hayır:** sekreter botu, 14 rol, paralel Kanban hakikatleri, sonsuz ticket üretimi, günlük tam monografi, görev bitince zorunlu yeni görev, sonuç odaklı parametre brute force, kendi kendini yetkilendiren LLM, yeni vector DB zorunluluğu, tüm eski raporların otomatik "kanıt" sayılması, yeni backtest engine, otomatik mühür, otomatik gerçek para.

**Evet:** az sayıda hedef; gerektiğinde derin araştırma; küçük ve kayıtlı deney; tekrar kullanılabilir işçi; açık koşullu öğrenme; eski negatif çalışmaların geri çağrılması; mevcut güvenilir broker/ledger; yalnızca gerçekten engelleyici issue/PR işi; kullanıcıya az ama karar değeri yüksek geri bildirim.

---

### Nihai karar

**V3'ün asıl boşluğu görev orkestrasyonu değil, sürekli amaç ve epistemik hafızaydı.** V4 bunun için yeni bir ajan ordusu kurmak yerine mevcut broker'a hedef/claim katmanı ekler ve müdürü *goals → evidence → next best experiment* döngüsüne bağlar. v4 de yalnız doküman: implementasyon, yetki geçişi, VPS kabulü ve gerçek koşular ayrı iş olarak doğrulanmalıdır.