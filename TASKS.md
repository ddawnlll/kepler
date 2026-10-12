# KEPLER — TASKS

Aktif iş: EV1 kararı (ADAY → G3 → küçük canlı, ya da NO_DEPLOY) | durum: engelli (kullanıcı kararı bekliyor) | protokol: reports/preregistration/signal_diagnostics.md

Bu dosya yalnızca güncel durum ve açık kararları tutar. Eski devralma notları, faz tabloları ve görev listeleri
git geçmişinde (`git log -- TASKS.md`) ve `reports/` altında.
Hedef/kurallar `MISSION.md`, harita `ARCHITECTURE.md`, ajan kuralları `AGENTS.md`; çelişkide onlar kazanır.

## Ana sistem: EV1 (varsayılan)
`trend` + `xs_momentum` + `carry`, ağırlık 0,6/0,2/0,2 (`ensemble.PRESETS["ev1"]`, varsayılan `Params()`). Altyapı eklemesi kapalı (AGENTS.md).
- Ölçülen: 6 yılda net +8 297 / 10 000; Sharpe 1,45 (sabit sermayede 1,86), yıllık %13,8, maks DD %9,7. Netin ~%60'ı 2020–21; 2022+ Sharpe 0,12–0,81, alfa t 1,60.
- Kanıt durumu: sönme testi KANITSIZ (W2 brüt p 0,010, DSR 0,926); DSR(N=4 775) ≈ 0; K9 (range rejimi) kalıyor; seçim prosedürü yazılı olmadığından walk-forward yok. Nedensellik: sızıntı bulunmadı. `reports/ensemble_decay.md`, `reports/audit_fixes.md`, `reports/trade_audit.pdf`.
- Uygulanabilirlik: MEXC kuralları doğrulandı, asgari uygulanabilir sermaye ~$2 500 (`reports/account_reality.md`); $500 hedef boyutları minimumların altında kalabilir.
- Deneme sayısı N: 5 091 (muhafazakâr), birincil 4 913 (`reports/signal_diagnostics_data/trials*.jsonl`).

## Açık kararlar (kullanıcı)
1. **EV1: ADAY mı NO_DEPLOY mu.** Yeni strateji koşusu yapılmadan önce karar (Faz 3 durma kuralı geçerli).
2. `trend` / `xs_momentum`: IC testinde ham p ≈ 0,005 ama Holm'da elendi. Kural gereği AT; kullanıcı kararı gerekir.
3. `carry_xs`: K1–K9 kartı NO_EDGE (K1 sınırda, K9 kaldı). Ensemble'a girmez.
4. Çekirdek kilidi gerektirenler: deftere `ledger/` taşıma (Modal Volume'daki edge/pre2022 satırları), `evaluate.code_hash` uzman dosyalarını kapsamıyor, BACKTEST.md günlüğü (`dvol`/`tbr` notu).

## Bilinen açıklar
- Veri denetimi kırmızı (`reports/data_audit.md`); etkisi EV1 pozisyonlarında ölçülmedi.
- Sızıntı mutant testi (`tests/test_leak_mutants.py`) yok.
- `tests/data/tradingview` `.gitignore`'da: temiz klonda Modal'de 9 TV testi kırmızı (fixture yeniden alınmalı).
- Ters yön (Bollinger −F net +8 025) post-hoc: yeni ön kayıt olmadan kullanılmaz.

## Geçmiş sonuçlar (özet; ayrıntı `reports/`)
- G2 kitap sinyalleri: NO_EDGE. Zone Fade v1: NO_EDGE (K1). Edge ailesi (9 uzman): ADAY yok. Sinyal teşhisi: IC'yi geçen 4/9.
- Mühür (son 6 ay) hiç açılmadı; aday çıkarsa kullanıcı açar.

## Bu dosyayı kim günceller
Her ajan yalnızca üstteki `Aktif iş:` satırını ve ilgili bölümü günceller; yeni bölüm/devralma notu eklenmez, sonuçlar `reports/` altına yazılır.
