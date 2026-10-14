# Kepler — çalışma talimatları

Bu dosya tüm kodlama ve araştırma ajanları için kısa çalışma rehberidir. Ajanlar kullanıcı tarafından istenen işleri, mevcut depo ve sistem izinleri dahilinde bağımsızca yürütür; salt süreç bürokrasisi yüzünden durmaz.

## Ortam ve komutlar
- Proje Python 3.12, uv ve Modal kullanır. Ana giriş: `modal_app.py`; veri Modal Volume `kepler-data` içinde `/data` altındadır.
- Tam test: `modal run modal_app.py --cmd "pytest -q"`. Tek test: `modal run modal_app.py --cmd "pytest -q tests/test_referee.py"`.
- Hızlı mimari kontrol: `python3 tests/test_architecture.py`. Bu test katman ayrımını denetler; kod hacmi veya belge adı sınırı koymaz.
- Erişim sırları repoya, commit'e ve raporlara yazılmaz.

## Geliştirme serbestliği
- Ajanlar yeni veya mevcut Python modüllerini, testleri, yapılandırmayı ve Markdown belgelerini gerektikçe ekleyebilir/düzenleyebilir.
- **300 satır/dosya, 3.000 satır/paket, Markdown izin listesi veya `KEPLER_CORE_UNLOCK` yoktur.**
- Claude Stop/PreToolUse veya Git pre-commit hook'ları geliştirmeyi durdurmaz. Testleri ilgili değişiklikte çalıştır; gerçekten koşulmayan test için başarı iddia etme.
- Kod değişikliği için otomatik issue/PR, önceden yazılmış tasarım dokümanı, belirli model, zorunlu inceleme ritüeli veya aynı commit'te belge güncellemesi gerekmez. İşin hedefi gerektiriyorsa plan ve test ekle.

## Araştırma doğruluğu
- `MISSION.md` ve `BACKTEST.md` içindeki ekonomik değerlendirme sözleşmeleri geçerlidir.
- Uzman tahmin üretir; pozisyon boyutlama ve risk yürütmesini hakemden ayır. Sonuçları gerçek veri/komut/commit ile kanıtla.
- Deneme kimliği, kod/veri hash'i, ledger, leakage/gelecek-veri testleri, ücret/funding/likidasyon hesabı ve mühürlü holdout bütünlüğünü koru. Negatif sonuçları silme; ölçütleri sonuca bakarak geriye dönük değiştirme.
- Canlı emir, mühürlü dönem anahtarı, hesap sırları ve geri döndürülemez veri silme işlemleri araştırma kodu yazma yetkisinden farklıdır; bunları yalnızca açıkça yetkilendirilmiş kanaldan yap.
- VPS'in gerçek çalışma izinleri ve fabrikadaki `policy`/`merge_gate` kontrolleri yalnız doküman değiştirilerek devre dışı kalmaz. Otonom çalışma iddiaları gerçek kabul testi gerektirir.

## İş birliği
- `TASKS.md` ve varsa `state/STATUS.md` iş devri için okunabilir; sürekli tek satırlık durum güncellemesi zorunlu değildir.
- İşi bitirince değişen dosyaları, çalıştırılan testleri, açık sorunları ve varsa commit SHA'sını raporla.
