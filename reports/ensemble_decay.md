# EV1 sönme testi (2022-01 → 2026-04): KANITSIZ (W2), ama brüt p = 0,0100

**Sonuç.** Ön kayıtlı kurala göre (`reports/ensemble_decay_protocol.md`, commit `d6bb74a`) karar **KANITSIZ (W2)**: brüt p ölçütü geçti, DSR(W2) ölçütü kıl payı kaldı. Sistem, kart kararı (ZAYIF) ve mühür durumu değişmedi.

| ölçü | değer | eşik | geçti |
|---|---|---|---|
| brüt p (W2 içinde rotasyon null'u, B = 300) | **0,0100** (gerçek brüt 3 842; null ort. −136 ± 1 699; medyan/95p/99p −147 / 2 733 / 3 741) | ≤ 0,05 | ✓ |
| DSR(W2), N = 6 | **0,926** (yıllık Sharpe: birincil 0,81; trend_only 0,63; no_xs 0,74; no_carry 0,62; no_risk 0,59; no_buffer 0,68) | ≥ 0,95 | ✗ |

Gerçek brüt, 300 null çekilişinden yalnızca 2'sinden küçük kaldı ((1 + 2) / 301 = 0,00997).

## Bilgi (karar dışı)
| ölçü | değer |
|---|---|
| net p (W2 içinde rotasyon) | 0,0166 (gerçek net 3 289; null ort. −455) |
| brüt p ve net p, tüm seri rotasyonu null'u (W2'de hakem) | 0,0332 ve 0,0332 (null 95p 3 125; 9 çekiliş ≥ gerçek) |
| W2 taze hakem koşusu: net / brüt / Sharpe | 3 289 / 3 842 / 0,81 |
| tam dönem koşusunun W2 dilimi: net / Sharpe / maks DD | 3 281 / 0,81 / %9,7 |
| al-tut Sharpe (W2) / NW alfa (yıllık), beta, t | −0,25 / 0,077, 0,000, **1,60** |
| fee / slippage / funding | −282 / −56 / −214 |
| dolum / likidasyon / red | 4 220 / 0 / 0 |

## Nasıl okunmalı
- **Zamanlama bilgisi var gibi görünüyor.** Aynı dönemin içinde, aynı semboller ve aynı risk boyutlamasıyla tahminleri rastgele kaydırınca, gerçek sonuçtan iyisini ancak ~%1 şansla elde ediyoruz. Tüm seriyi kaydıran daha gevşek null'da bu ~%3. Tüm dönem için `reports/ensemble.md`'deki p = 0,0033 ile aynı yönde.
- **Ama kanıt ölçütü karşılanmadı.** DSR, N = 6 deneme için düzeltilmiş Sharpe'ın sıfırdan ayırt edilebilirliğini ölçer; W2'de 4,25 yıl ve Sharpe 0,81 ile 0,926 çıktı (eşik 0,95).
- **Al-tuta karşı alfa anlamlı değil** (t = 1,60), bu da `reports/ensemble.md`'de zaten yazılı olan sayı. Rotasyon null'u ile alfa testi aynı şeyi sormaz: biri zamanlamayı, diğeri al-tut getirisinin üstüne eklenen yıllık getiriyi sınar.
- Birleşik cümle: **W2'de zamanlama sinyali için ince ama olumlu kanıt, ön kayıtlı eşiği geçmeyen bir güven düzeyinde.** "Edge sönmüş" de "edge kanıtlandı" da bu veriyle söylenemez.

## Tahmin ile sonuç
Tahminim brüt p ≈ 0,03–0,15 idi; çıkan 0,0100 aralığın **altında**, yani edge lehine tahminimden iyi. DSR < 0,95 tahmini tuttu.

## Dürüstlük notları
1. **Görülmüş veri.** Tasarım W2 sonuçlarını görmüş bir araştırmacının işi (`reports/ensemble_protocol.md`). Geçen p zaman-dışı kanıt değildir; kalan DSR ise bilgilendirici.
2. **N = 6 muhafazakâr değil, karşılaştırılabilir.** DSR için ön kayıtlı N = 6 (birincil + 5 ablasyon). Proje ölçeğindeki kümülatif deneme sayısı çok daha büyük (aşağıda); o N ile DSR daha da düşük olurdu. Rakam hesaplanmadı.
3. **Dikiş.** İki null (W2 içi / tüm seri) arasındaki p farkı (0,0100 vs 0,0332) kaydırma tasarımına duyarlılığı gösteriyor; hangisinin "doğru" olduğu sonradan seçilmedi, birincil önceden belliydi.
4. **Hakem başlangıcı:** W2'de hesap düz başlıyor; tam dönem koşusunun dilimiyle net farkı 8 (3 289 vs 3 281).
5. **UNKNOWN'lar önceki raporlarla aynı:** sembol kuralları, MEXC farkı, hayatta kalma yanlılığı, slippage.

## Süreç notları (sonucu etkilemez)
- Bir bilgi-null parçası (full 100–150) yerel çalışma dizinindeki bir dosya build sırasında değiştiği için (`factory/vps/mudur_interim_SOUL.md`, başka bir süreç) hiç koşmadan düştü ve aynı komutla yeniden başlatıldı. Tohumlar sabit, çıktı birincil sonuca girmiyor.
- Bağımsız inceleme (arch-reviewer + code-reviewer, commit `085a318`): bloke eden bulgu yok. Düşük önemli notlar: protokoldeki `--stage decay` / `ledger/ensemble_decay/` adları kodda `decay_real` / `decay_null` ve `--out/ledger_ev1_w2.jsonl`; defter dosyası repoya `ledger/ensemble_decay/` altına kopyalandı. Rapor betiği için birim testi yok (sentetik veriyle uçtan uca denendi). `decay_real` yeniden koşulursa deftere ikinci satır ekler (N şişer).
- Koşu `modal run` ile Modal'de (4 CPU konteyner, 13 paralel iş); smoke çıktıları karar için kullanılmadı.

## Deneme sayısı
`ledger/` altındaki tüm `.jsonl` satırları: **4 119** (TASKS'taki önceki 4 118 + bu test 1). Yalnızca repo sayısıdır; Modal Volume'daki ek satırlar `reports/trial_inventory.md`'de.

Kod: `kepler/ensemble.py` (`rotate(..., rot_from)`), `scripts/ensemble.py` (`decay_real`, `decay_null`), `scripts/ensemble_decay_report.py`, `tests/test_ensemble_window.py` (4 test; `rot_from`'u yok sayan bilinçli mutant 3 testi kırdı). Hakem, denetim, risk, defter, mühür koduna ve mevcut testlere dokunulmadı. Mühürlü dönem açılmadı. Tablolar: `reports/ensemble_decay_data/`, defter: `ledger/ensemble_decay/ledger_ev1_w2.jsonl`.
