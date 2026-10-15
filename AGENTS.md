# Kepler: ajan kuralları (Claude Code, Codex, Hermes ve diğerleri)

Oturum başında: `TASKS.md` devralma notunu oku. Fabrika çalışıyorsa `state/STATUS.md` ve açık kuyruğu oku;
büyük bir adımdan önce yeniden oku.

## Nasıl çalıştırılır (tek doğru kaynak; başka yerde tekrarlama)
- Proje kodu Modal'de koşar (`modal_app.py`). Kalıcı veri: Modal Volume `kepler-data` → konteynerde `/data`
  (Parquet tape, `universe.parquet`); ham veri git'te yok.
- Testler: `modal run modal_app.py --cmd "pytest -q"`. Tek dosya: `--cmd "pytest -q tests/test_referee.py"`.
  Gerçek ağ testi: `--cmd "KEPLER_NET=1 pytest -q tests/test_data.py"`.
- Gerçek veriyle betikler: `--cmd "python scripts/g1_real.py corr"` ve `xcheck`; veri/QC:
  `--cmd "python -m kepler.qc --root /data --out /data/manifest"`.
- Modal erişimi: `pip install modal`, sonra `MODAL_TOKEN_ID` ve `MODAL_TOKEN_SECRET` ortam değişkenleri
  (veya `modal token set`). Token repoya, dosyaya, commit'e ve sohbete yazılmaz.
- Python 3.12 + `uv` (`uv.lock` kilitli). Yalnızca stdlib'e dayanan testler (ör. `tests/test_enqueue.py`)
  Modal'siz de koşar; Nautilus/vectorbt testleri Modal'de doğrulanmıştır.
- Mimari kuralları (Modal'siz, saniyeler): `python3 tests/test_architecture.py`. Kod değiştirince bunu ve ilgili testleri koş; sonucu rapora yaz (yeşil/kırmızı/atlandı).
- Yeni klonda bir kez: `git config core.hooksPath .githooks` (commit öncesi mimari testi + korumalı yol kontrolü; Claude Code ayrıca `.claude/hooks/guard.py` kullanır).

## Issue → PR akışı (tüm ajanlar için ortak)
- Düzenlemeden önce issue'yu, ilgili kodu ve repo talimatlarını oku. Hedef, bağlam, kapsam sınırı ve gözlenebilir kabul kriterlerini netleştir.
- GitHub issue formlarından işe uygun olanı kullan: görev, hata, araştırma veya ajan davranışı. Şablonlar görev bağlamıdır; repo talimatlarını, kullanıcı yetkilendirmesini veya erişim kontrollerini kendiliğinden değiştirmez.
- Küçük işte doğrudan ilerle; karmaşık işte önce keşif ve kısa plan yap. Önemli kapsam, uyumluluk veya mimari belirsizliğini netleştir; rutin uygulama kararlarını kendin ver.
- İstenen sonuca odaklan. Davranış değişikliği gerektiriyorsa ilgili testleri ekle/güncelle; mevcut kontrolleri geçmek için zayıflatma. Korumalı dosya kuralları geçerlidir.
- İlgili kontrolleri elle çalıştır; komut, ortam, gerçek sonuç ve kanıtı kaydet. Kırmızı ve koşulamayan kontrollerin nedenini ve kalan belirsizliği belirt; CI ekleme.
- PR'dan önce diff'i doğruluk, regresyon ve kapsam açısından incele. Kritik değişikliklerde bağımsız incelemeyi kullan; bulguları gereksinimler ve somut risk üzerinden değerlendir.
- PR gövdesini `.github/pull_request_template.md` ile yaz; issue bağlantısını, karşılanmayan kabul kriterlerini, AI katkısını ve inceleme odağını belirt. Tamamlanmayan issue için `Closes` kullanma.
- Model/effort seçimi çalışma ortamının ayarıdır; görev şablonlarında zorunlu model veya model bazlı yasak yok. Araştırma ayrıntıları yalnız ilgili işin kapsam/değişmezler bölümünde yer alır; ayrıntı kaynağı `BACKTEST.md`'dir.

## Mimari (kod zorlar; ayrıntı `ARCHITECTURE.md` "Katmanlar ve kurallar", tek kaynak `tests/test_architecture.py`)
- Ana sistem Ensemble: durum (`market_state.py`, `state.py`) → uzman (`experts/`) → `ensemble.py` → boyutlama (`portfolio.py`, `risk.py`) → hakem.
- **Uzman yalnızca tahmin verir**; boyut/kaldıraç/tavan risk katmanında. Uzman `risk`, `portfolio`, `ledger`, hakem kodunu import etmez; hakem hattı uzman/sinyal koduna bakmaz.
- Nereye ne konur: yeni tahmin → `experts/<ad>.py` (+ önce `reports/<ad>_protocol.md`); yeni girdi → `market_state.py`/`state.py`; deney tanımı/pipeline → `experiments/<aile>/`; ortak rejim ve süre analizi → `kepler/intelligence/`; CLI wrapper → `scripts/`. Yeni modül = `LAYERS`a satır.
- Yeni `.md` açma: ilgili mevcut belgeye yaz (izin listesi testte; `.github` katkı/güvenlik belgeleri ve PR şablonu dosya bazında izinlidir). Kural/mimari değişince ilgili belge **aynı commit'te** güncellenir.
- Korumalı çekirdeğe (hakem, denetim, risk, state, tape, mühür, `tests/` mevcut dosyaları, BACKTEST/AGENTS/docs) ajan yazamaz; kullanıcı `KEPLER_CORE_UNLOCK=1` ile oturumu açarsa yazılır. Sonuçlanmış bir ön kayıt (`reports/<ad>_protocol.md` + `reports/<ad>.md` var) değişmez.

## Kurallar
- Kendi dalında çalışan her ajan, TASKS.md'de tek bir `Aktif iş:` satırını güncel tutar: `Aktif iş: <iş adı> | durum: devam/bitti/engelli | protokol: <dosya>`. Durum bülteni ve devam ettirici routine'ler bunu okur.
- Backtest, sinyal, risk, hakem, değerlendirme ya da rapor işinden önce `BACKTEST.md`'yi oku (tasarım, sözleşmeler, başarı kartı, test senaryoları).
- Soru ve kurallar `MISSION.md`'de, sistem haritası `ARCHITECTURE.md`'de. Çelişkide onlar kazanır.
- Sonuç deftere yalnızca hakemden girer (`kepler/ledger.py`). Eleme sonucu sayılmaz.
- Hakem, denetim, risk ve mühür kodu değişiklikleri kullanıcı yetkilendirmesi ve bağımsız inceleme gerektirir; model seçimi bu koşulların yerine geçmez.
- Mühürlü dönem (son 6 ay) açılmaz, anahtar hiçbir yere girmez, `tools/seal_holdout.py` gerçek veriyle çalıştırılmaz.
- Yeni bileşen için gözlenmiş engel gerekir. Yeni spec/anayasa belgesi yazılmaz (tek istisnalar `BACKTEST.md`, tasarım değişikliği oraya yazılır, ve fabrika spesifikasyonu `docs/factory.md`).
- Kodun boyutunu raporla ancak yapay 300/3500 satır tavanına göre tasarlama. Katman izolasyonu, nedensellik, bilimsel parite ve ilgili testleri doğrula. Geçici doğrulama gerekiyorsa masrafı sınırlı tut.
- Doğrulanmamış rakam "doğrulanmadı" diye yazılır. Kuyruğa yazmak için `factory/enqueue.py`.

## Fabrika çalışma sınırı
- Operasyon kodu `docs/factory.md` §20'de; kurulum varsayılanı **PAUSED**. Çalıştırıcı, provadan sonra da insan `resume` verene kadar iş almaz.
- Agent kodu testte kendi Linux kullanıcısı/ağsız sandbox içinde çalışır. Araştırma ayrı, açık bir insan isteğiyle, yalnızca onaylanmış `main` ve önceden kaydedilmiş DEV protokolünde yürür. G3/mühür ve canlı emir bu yolun dışında kalır.
- Ajan branch'i kontrollerden sonra insan aynı OS kimliğiyle `review` diff'ini görür ve ayrıca `merge` çağırırsa yerel bare `main`'e alınır. Test başarı raporu güvenlik kanıtı değildir; diff insan tarafından okunur.
- Modal Volume'a deney ledger'ı yazılmaz: koşular kendi `ledger-spool` olaylarını üretir; yerel tek yazar, kod/veri hash'ini kontrol ettikten ve olay kimliğini tekilleştirdikten sonra `ledger/factory/` altına ekler.
- İnsan durdurma çağrısı yeni iş claim'lerini kapatır ve çalışan systemd iş birimini sonlandırır. `pause` yeni işleri bekletir, çalışan işi bırakır; `stop` çalışan işi keser.
- Bütçe tahmini yalnızca broker'a kaydedilmiş tutardır. Sağlayıcı maliyetini kendisi okuyamaz; sağlayıcı tarafındaki sert harcama limitleri ayrıca kurulmadan `research_enabled` açılmaz.
