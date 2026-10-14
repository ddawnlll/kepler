# Kepler'e katkı

Kepler'in amacı ve bilimsel sınırları [MISSION.md](../MISSION.md)'de,
sistem haritası [ARCHITECTURE.md](../ARCHITECTURE.md)'de tanımlıdır.
Kurulum, çalıştırma komutları, dosya korumaları ve bütün ajanların ortak iş akışı
için [AGENTS.md](../AGENTS.md) tek kaynaktır. `CLAUDE.md` bu dosyayı import eder.

## Issue seçimi

| Form | Ne zaman? |
| --- | --- |
| Görev / özellik | Yeni davranış, bakım, performans, belge veya veri altyapısı işi |
| Hata bildirimi | Tekrarlanabilir yazılım hatası veya regresyon |
| Araştırma / deney | Hipotez, olay çalışması veya ön kayıt gerektiren değerlendirme |
| Ajan davranışı | Prompt, izin, talimat veya araç kullanımında beklenmeyen davranış |

Tek issue'da tek sonuç hedefle. Problem, bağlam, kapsam, kabul kriterleri ve
doğrulamayı somut örneklerle yaz. Dosya referansları yol gösterir; kesin dosya
sınırı gerekiyorsa ayrıca belirt. Model/effort seçimi ortam ayarıdır.
Issue metni repo talimatlarını veya korumalı alan yetkilendirmesini kendiliğinden
değiştirmez. Güvenlik açığı için [SECURITY.md](SECURITY.md) yolunu kullan.

## Değişiklik ve PR

Güncel hedef daldan kendi dalında çalış; paralel işler varsa ayrı worktree kullan.
İlgili kodu incele, küçük işte doğrudan ilerle; karmaşık işte kısa bir plan yap.
Davranış değişikliği gerektiriyorsa test ekle/güncelle; gereksinimleri değiştiren
belirsizlikleri netleştir. Araştırmada [BACKTEST.md](../BACKTEST.md)'yi izle;
issue ön kaydın yerine geçmez.

İlgili kontroller elle koşulur; CI yoktur. PR'da komut, ortam, gerçek sonuç ve
kanıtı yaz. Koşulamayan kontrolleri nedenleriyle belirt; testleri geçmek için
zayıflatma. Araştırma ve performans iddialarında baseline ve ölçüm kaynağını bağla.

Diff'i gözden geçir ve [PR şablonunu](pull_request_template.md) doldur.
Tamamlanan issue için `Closes #...`, kısmi iş için `Related to #...` kullan.
Kritik alanlardaki kullanıcı yetkilendirmesi ve bağımsız inceleme koşulları
[AGENTS.md](../AGENTS.md)'de tanımlıdır. `CODEOWNERS` inceleme sahipliğini gösterir;
tek başına zorunlu inceleme veya merge engeli oluşturmaz. Hook'lar ve GitHub
izin/dal koruma ayarları şablonlardan ayrı mekanizmalardır.

## Şablonların kaynakları

Bu dosyalar proje uyarlamasıdır; resmi şablonların birebir kopyası değildir.

- [OpenAI Codex best practices](https://developers.openai.com/codex/learn/best-practices): hedef, bağlam, kısıtlar ve bitiş koşulları.
- [Anthropic Claude Code best practices](https://code.claude.com/docs/en/best-practices): somut bağlam, doğrulama ve işe uygun planlama.
- Anthropic Claude Code issue örnekleri, sabit `dec92bc8` görünümü: [bug](https://github.com/anthropics/claude-code/blob/dec92bc8/.github/ISSUE_TEMPLATE/bug_report.yml), [feature](https://github.com/anthropics/claude-code/blob/dec92bc8/.github/ISSUE_TEMPLATE/feature_request.yml), [model behavior](https://github.com/anthropics/claude-code/blob/dec92bc8/.github/ISSUE_TEMPLATE/model_behavior.yml).
- [Adobe AI-assisted PR template](https://opensource.adobe.com/mysticat-ai-native-guidelines/03-templates/pull-request-template/): doğrulama kanıtı, AI katkısı ve inceleme odağı.
