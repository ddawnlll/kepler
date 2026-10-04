# Ön kayıt: EV1 sönme testi — 2022-01 → 2026-04 için ayrı rotasyon null'u (TASKS Faz 1.5)

**Durum:** ön kayıt; koddan ve koşudan önce commit'lendi (2026-10-05, kullanıcı komutu: "2022-2026 null'unu koş").
Kural, ölçüt ve N koşudan sonra değişmez (MISSION kural 11). Strateji, parametre ve kart eşikleri **değişmez**; yalnızca EV1'in ikinci alt dönemi ayrıca sınanır.

## Soru
`reports/ensemble.md`: tüm dönemde K1 geçti (p = 0,0033), ama alt dönemler farklı (2020-04 → 2022-01 Sharpe 3,03 alfa t 3,66; 2022-01 → 2026-04 Sharpe 0,81 alfa t 1,60) ve null yalnızca tüm dönem için koşuldu.
Soru: **EV1'in 2022-01-01 → 2026-04-01 getirisi, yalnızca bu dönemin içinde kurulan rotasyon null'unun dışında mı?** Evet → edge o dönemde de var. Hayır → kanıt tek dönemden (2020–21) geliyor.

## Tanım
- **W2 = [2022-01-01, 2026-04-01)** (UTC). Veri, evren (ext-9), sistem (EV1), `Params()`, Spec (sermaye 10 000, fee 10 + slip 2, kaldıraç limiti 10, `gross_cap` 3×) birebir `reports/ensemble_protocol.md` ile. Kitap 2020-01'den tam seride hesaplanır (ısınma); hakem yalnızca W2'de koşar.
- **Gerçek:** EV1, `evaluate_book` (denetim + defter) ile yalnızca W2'de koşulur. İstatistik: brüt PnL.
- **Null (birincil, karar buna göre):** günlük F paneli tam seride hesaplanır; **W2'ye düşen satırlar** (2022-01-01 ve sonrası) tek ortak k = ⌊u · n_W2⌋ gün ile dairesel kaydırılır (tüm semboller aynı k), aktif olmayan günler maskelenir, W2 öncesi satırlar dokunulmaz. σ, ρ, IDM, tavanlar ve tampon gerçek veriyle kalır. B = 300, u_i = `default_rng([0, i]).uniform(0,05; 0,95)` (K1 ile aynı tohumlar). Her çekiliş W2'de hakemden geçer; istatistik brüt PnL.
- **p:** `stats.rotation_p(gerçek brüt, null brüt)` (tek yönlü, (1 + #{null ≥ gerçek}) / (B + 1)).
- **DSR (W2):** `stats.dsr(r_W2, trial_srs)`; r_W2 = mevcut tam dönem koşusunun (`reports/ensemble_data/primary.json`) günlük net PnL'inin ≥ 2022-01-01 dilimi / 10 000. trial_srs = birincil + 5 ablasyonun (K8) aynı dilimdeki Sharpe'ları (N = 6, `reports/ensemble_protocol.md` ile aynı küme). Hakem yeniden koşulmaz.
- **Bilgi (karar dışı):** (i) tam seri dairesel kaydırma, W2'de hakem (`--rot full`; B = 300, aynı u): tüm dönem null'unun W2 dilimi; (ii) net p; (iii) W2 Sharpe, NW alfa t (al-tut'a karşı, mevcut `bh` serisi), maks DD.

## Karar kuralı (koşudan önce yazıldı)
- **EDGE SÜRÜYOR (W2):** brüt p ≤ 0,05 **ve** DSR(W2) ≥ 0,95 (K1 eşikleri aynen).
- **KANITSIZ (W2):** aksi halde. p ve DSR değerleri raporlanır; ek eşik ya da ara kategori yok.
- Sonuç hiçbir kart kararını (ZAYIF) değiştirmez ve G3'ü açmaz. Yalnızca "edge tek dönemden mi geliyor" sorusunu cevaplar.

## Tahmin (koşudan önce)
- Brüt p ≈ 0,03–0,15. DSR(W2) < 0,95 (Sharpe 0,81, 4,25 yıl, N = 6 ile deflasyon). En olası sonuç: **KANITSIZ**, ama p tek başına 0,05'in altında olabilir.
- Birincil ve bilgi null'ları aynı yönü göstermeli; ayrışırsa dikiş etkisi (aşağıda) şüphelidir.

## Denemeler ve deneme sayısı
- **N + 1:** gerçek W2 koşusu `evaluate_book` ile deftere girer (`ledger/ensemble_decay/`). Kümülatif sayı koşudan sonra defterden sorgulanır, hafızadan yazılmaz.
- 600 null çekilişi (300 birincil + 300 bilgi) ve DSR dilimleri kontroldür: deftere ve N'ye girmez (K1'deki gibi).

## Bilinen sınırlar
1. **Görülmüş veri.** Tasarım W2 sonuçlarını görmüş bir araştırmacının işi. Geçme, zaman-dışı kanıt değildir; kalma ise bilgilendirici.
2. **Dikiş.** Dairesel kaydırma W2 sonunu başına bağlar; tampon yol bağımlı olduğundan dikişte bir ek işlem olabilir. Gerçek koşuda yok. Etki bilgi null'uyla (i) karşılaştırılır; ayrıca ölçülmez.
3. **Hakem başlangıcı.** Hesap W2 başında düz başlar; tam dönem koşusunun W2 dilimiyle birebir aynı PnL değildir. Karşılaştırma için dilim brüt/net rapor edilir.
4. Sembol kuralları, MEXC farkı, hayatta kalma yanlılığı: önceki raporlarla aynı UNKNOWN'lar.

## Kapsam ve bütçe
- Kod: `kepler/ensemble.py` (`rotate` + `forecasts` + `make_book` için `rot_from` parametresi, varsayılan davranış aynı), `scripts/ensemble.py` (`--stage decay`), `tests/test_ensemble_window.py` (yeni, elle hesaplı), `scripts/ensemble_report.py` yerine kısa `scripts/ensemble_decay_report.py`.
- Hakem, denetim, risk, defter, mühür kodu ve mevcut testlere dokunulmaz. Mühürlü dönem (≥ 2026-04-01) açılmaz.
- Çıktı: `reports/ensemble_decay.md`, `reports/ensemble_decay_data/`. TASKS Faz 1.5 güncellenir.
- Bütçe: ~1–2 saat Modal, ~70 araç çağrısı. Aşılırsa dur ve raporla.
