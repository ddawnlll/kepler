# Kepler 7/24 ajan fabrikası

Bu dizin, uzun süre çalışan ajan işçisi için broker, SQLite iş kuyruğu, güvenli ölçüm işçisi,
insan onaylı birleştirme kapısı, ledger yazıcısı, Telegram outbox ve VPS servis tanımlarını içerir.
Kurulum kodu hazırlandı ancak bu oturumda hiçbir kod, test, servis veya VPS komutu çalıştırılmadı.
Dolayısıyla paket kurulumu, sistemd izolasyonu, Telegram teslimatı ve 7/24 davranışı henüz doğrulanmış
değildir; sistemi canlı kabul etmeyin.

## Varsayılanlar ve sınırlar

- `factory/policy.json`: kuyruk duraklatılmış, araştırma kapalı, otomatik birleştirme kapalı.
- `factory/vps/setup.sh` kullanıcıları, root'a ait politika ve servis dosyalarını kurar; hiçbir servisi
  etkinleştirmez veya başlatmaz.
- `kworker` ağsız sandbox'ta, salt okunur bare repo ve bağımlılık bağlamalarından üretilmiş geçici,
  yazılabilir aday kopyasında sabitlenmiş test politikasını çalıştırır. Aday kodu `krunner` kimliğiyle
  çalışmaz; test sonucu insan diff incelemesinin yerini tutmaz.
- Araştırma işi sadece insan onaylı DEV protokolüyle `kcompute` altında çalışır. Modal sağlayıcı
  harcama limiti ayrıca ayarlanmalıdır; yerel kayıt bir sağlayıcı faturalandırma kaynağı değildir.
- `main` güncellemesi için başarılı sandbox kontrolü ve aynı commit/base/politika için ayrı insan
  diff incelemesi gerekir. Onay Telegram'dan verilmez.
- Defter olayları önce her uzak koşunun ayrı spool'una yazılır; tek yerel yazar bunları doğrular ve
  tekrarları engeller.

## Kurulum yolu

1. Root ile `factory/vps/setup.sh` ve `factory/vps/provision.sh` dosyalarını gözden geçirip VPS'te
   elle çalıştır. Bunlar bu çalışma alanında çalıştırılmadı.
2. DEV Modal bilgilerini etkileşimli olarak `sudo kepler-configure-secret modal` ile, Telegram
   bilgilerini `sudo kepler-configure-secret telegram` ile gir. Gizli değerler komut satırına veya
   sohbete yazılmaz. Yalnızca `kagent`, `krunner` ve `jj` için kişisel Gemini/OpenAI gibi model
   oturumlarını ayrı kur; harcama tavanlarını sağlayıcı panellerinde ayarla.
3. `docs/factory.md` §20'deki manuel kabul adımlarını tamamla. Sonra servisleri tek tek aç; araştırma
   kapalı ve kuyruk duraklatılmış halde başla.
4. Canlı araştırmayı ancak DEV veri/protokol kabulü, insan onayı, sağlayıcı sert harcama limiti ve
   ledger aktarım kabulü tamamlandıktan sonra aç.

Sistem kaynakları, operasyon akışları ve açık doğrulama işleri `docs/factory.md` içindedir. Herhangi
bir kabul kontrolü henüz bu değişiklikler için çalıştırılmadığından güvenlik iddiaları tasarım niyetini
anlatır; üretim kanıtı sayılmaz.
