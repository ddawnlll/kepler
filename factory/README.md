# Fabrika: kurulum özeti (doğrulanmadı: Hermes henüz kurulup denenmedi)

Roller: sekreter (Telegram'da seninle konuşur), müdür (seyrek uyanan zeki ajan), işçiler (kısa ömürlü),
güncelleme ajanı (15–20 dk). Hepsi LLM; talimatlar `factory/agents/`. Durum dosyaları `state/`
(`queue.jsonl`, `STATUS.md`); yazma yalnızca `factory/enqueue.py` ile.

Aşama 1 (şimdi): sekreter + güncelleme ajanı, salt okunur. Aşama 2 (G2 hazır olunca): müdür + işçiler.

## Senden gerekenler
1. Küçük bir VPS (2–4 GB) ve SSH erişimi.
2. Telegram botu (BotFather) ve kendi kullanıcı kimliğin (yalnızca ona cevap verilecek).
3. Sağlayıcı anahtarları (ucuz modeller) ve ChatGPT Plus OAuth. Sağlayıcı tarafında **sert günlük limit** koy.
4. Modal token'ı (ağır koşum) ve mühür anahtar çifti (özel anahtar yalnızca sende).

## Kurulum sırası
0. Hızlı yol: sunucuda `factory/setup_hermes.sh` (gizli değerler ortam değişkeniyle; doğrulanmadı, hiç koşulmadı).
   Telegram için BotFather **bot token'ı** ve @userinfobot'tan **sayısal kullanıcı id** gerekir; my.telegram.org'daki
   `api_id/api_hash` Hermes geçidi için kullanılmaz.
1. VPS'te ayrı bir OS kullanıcısı (`kepler-agent`): repoya yazabilir ama hakem, denetim, mühür ve
   MISSION dosyaları salt okunur (sahip: sen). Mühür anahtarı bu kullanıcıda yok.
2. Hermes'i resmî dokümandan kur; sekreter ve müdür için ayrı profil, güncelleme ajanı için cron.
   Alt ajan modeli ayrı (`delegation.model`).
3. `factory/commands_tr.yaml` sekreter testi: 10 komutun hepsi doğru sınıflanmadan model seçimi bitmez.
4. Sunucu `state/STATUS.md` ve kuyruk özetini `state` dalına düzenli push'lar; yerel ajanlar oturum
   başında çeker, canlı ledger sorgusu için salt okunur SSH kullanır.
5. Geri dönüşsüz komutlar (mühür açma, gerçek para) sohbetle yürümez; ajanların erişemediği ayrı, LLM'siz
   bir onay adımı gerekir (ör. tek kullanımlık kod).

## Doğrulanacaklar
- Hermes'in yazma yetkisinin gerçekten kısıtlanabildiği (kendi skill'lerini yazabiliyor).
- ChatGPT Plus OAuth'un Hermes'te sorunsuz çalışması.
- Ucuz modelin Türkçe komutları doğru sınıflaması (test seti).
- B işlerinde ucuz modelin kod kalitesi; yetersizse B işleri yerel Claude Code ile yapılır.
