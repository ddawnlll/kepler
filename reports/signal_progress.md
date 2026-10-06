# Sinyal teşhisi: ilerleme günlüğü

Kaynak görev: kullanıcı mesajı (2026-10-06). Ön kayıt: `reports/preregistration/signal_diagnostics.md`. Rapor (Faz 3): `reports/signal_diagnostics.md`. Bağlam sıkışırsa bu dosyadan ve `git log`dan devam et.
Ortam: yerel venv `/tmp/claude-0/venv` (modal 1.6.1, pandas, numpy, scipy, duckdb, pytest); gerçek veri yalnızca Modal Volume `kepler-data` (`modal run modal_app.py --cmd ...`, token ortamda). Push yok (kullanıcı onayı gerekir).

## Faz günlüğü
- **Faz 0 (2026-10-06)**: belgeler/kod okundu; Modal erişimi doğrulandı (veri: /data/tape + /data/pre2022/tape, universe.parquet 2022-01→2026-03 ve 2020-02→2021-12). Ön kayıt yazıldı (kartlar, ufuklar, IC tanımları, Holm ailesi 108, TUT/YENİDEN KUR/AT ölçütü, kontroller).
- **Faz 1 kodu (2026-10-06)**: `scripts/signal_diag_stats.py`, `scripts/signal_diag.py`, `tests/test_signal_diag.py`. Ön kayıttaki kontroller Modal'de geçti: 13/13 (pozitif kontrol ρ=0,3 → Spearman 0,2875 ±0,02; negatif kontrol 200 tekrar ham p<0,05 oranı [0,02, 0,09] ve Holm yanlış keşif ≤ %10; hizalama: karar günü getirisi sızmıyor, giriş = d+1 açılışı, terminal fiyat, funding penceresi; Holm/BH elle; φ ham olaylardan yeniden hesap; rejim nedenselliği + mutant; uçtan uca sentetik). Yerelde nautilus yok: rejim/uçtan uca testleri orada atlanır. `tests/test_architecture.py` yeşil.
  Test sırasında bulunan: kesitsel Spearman küçük n'de aşağı yanlı (n=15'te ≈ −0,02); bu bir kod hatası değil, tahmin edicinin özelliği (dinamik evrende kesit ~11–20 sembol: XS IC'ler hafif muhafazakâr).
