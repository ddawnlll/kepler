# V4.1 SOUL geçiş notu — sadece uygulama kontrol listesi

Bu bir yeni mimari dokümanı değildir. İki SOUL'un projede tek başına işe yaraması için mevcut kodda gereken minimum işlemleri belirtir.

## Tutulan roller

- **Müdür:** tek Telegram muhatabı, araştırma lideri, aktif bilimsel hafıza tüketicisi ve raporlayan kişi. [`MANAGER_SOUL.md`](./MANAGER_SOUL.md) taslağı.
- **İşçi:** her görev için birincil mod seçilen kısa ömürlü araştırmacı/uygulayıcı/eleştirmen. [`WORKER_SOUL.md`](./WORKER_SOUL.md) taslağı.

**Silinen LLM rolleri:** Sekreter SOUL (doğrudan müdüre Telegram aktarımı); Güncelleme Ajanı SOUL (deterministik trusted telemetry ve outbox bildirim fonksiyonu). **Önemli:** bu rollerin çalışır entegrasyonunu yönlendirmeden prompt dosyalarını silmek Telegram'ı ve kuyruk doğrulamasını bozabilir.

## SOUL'dan önce/aynı değişiklikte zorunlu kod uyumu

1. `factory/broker.py` bugün ajan `enqueue` çağrısını `from=sekreter` olarak doğruluyor. Tek müdür kimliği ve aracı Telegram için sahte insan yetkisi kazandırmayan, UID-temelli açık yetki şeması gerekiyor.
2. `factory/runner.py` araştırmayı insanın her tekil C onayına bağlıyor. V4.1 mandate, scope, expire/revoke, trial/limit, focus ve idempotent admission olmadan müdür yeni deney özerkliği kazanmaz.
3. `factory/research.py` sadece onaylı `main` ve sınırlı `script/argv` kabul ediyor. Yeni aday kod yalnız izole ve token/ağ/G3 erişimsiz candidate lane'de çalışmalı; trusted scoring ve ledger'a geçiş ayrı olmalı. İnsan `review + merge` kapısı korunmalı.
4. `factory/policy.json` `research_enabled=false` ve `budget_hard_action=warn`. Sert sağlayıcı limitleri kanıtlanmadan 7/24 maliyetli iş açılmamalı. Salt SOUL yazısı bu güvenliği sağlamaz.
5. `factory/status.py` 900 saniyede bir outbox mesajı oluşturuyor. Night Mode için quiet-hours, dedupe, severity ve sabah özetinin outbox işleyicisinde uygulanması gerekir. `MISSION.md`'deki 15–20 dk mesaj kuralı insan yetkisiyle uyumlandırılmalı.
6. Müdürün retrieval receipt'i ve claim/lesson kaydı mevcut SQLite/ledger'e bağlanmalı. Salt SOUL belleği ve sohbet geçmişi bilimsel hafıza değildir.
7. Tüm rol/izolasyon/izin değişiklikleri mevcut `AGENTS.md`, `ARCHITECTURE.md`, `docs/factory.md`, mimari testler ve VPS kabulüyle tutarlı olmalı.

## Yayın sırası

- Güven sınırları ve üst-politika uyumu → mandate ve candidate sandbox → trusted evidence + memory → Telegram yönlendirme ve notifications → SOUL'ları canlı konfigürasyona bağlama → kontrollü 24 saat H1A-D1 pilotu.
- Özellikle sekreter ve durum ajanının etkin runtime yollarını yeni müdüre ve deterministik raporlayıcıya taşıma işi bitmeden eski SOUL'ları kaldırma.
- PASS: tek `resume` sonrası kullanıcı tek tek onaylamadan H1-A deneyi hazırlanır ve izinli DEV'de doğrulanabilir sonuç ya da dürüst `INCONCLUSIVE` üretir; hafıza sonucu yeni seçimde kullanılır; gece rutin spam olmaz; maliyet/secret/G3/core ihlali sıfır.

**Bu dosyalar taslaktır.** Repo dosyaları, Telegram, VPS servisi ve broker bu dosyaları oluşturmakla değişmiş olmaz.