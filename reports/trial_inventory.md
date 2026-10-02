# İş C — Deneme envanteri ve Modal Volume flock

**KIRMIZI: Volume üzerinde konteynerler arası `flock` dışlaması iki turda da çalışmadı; repo defteri kümülatif envanteri eksik taşıyor.** A ve B'den sonra yürütüldü. Repo'da 44 defter dosyası / **4.117 satır**, Modal'de 73 / **5.434 satır** var. 44 dosyanın tamamı Modal'deki bir dosyayla SHA256 olarak eşleşti; iki konumdaki kopyalar yeni deneme diye toplanmadı. Defter, evaluate, hakem, risk, denetim ve mühür değiştirilmedi.

## Kapsam ve sayım

3 Ekim 2026 (Europe/Istanbul). Repo reports/scripts dosya envanteri: bu denetim çıktıları eklenmeden önceki anlık görüntü `report_file_inventory.csv` ve `script_inventory.csv`; A/B raporları snapshot'a dahildir, C raporu ve kendi ekleri dahil değildir. 18 script vardır. Ham deneme çıktıları Modal'den salt okunur incelendi; **93 JSON** yapısı sayıldı (fiyat serisi `btc_close.json` atlandı). Parquet veya mühürlü piyasa verisi bu işte açılmadı. Rapor kopyası ve ham JSON bir denemenin iki kanıtıdır, iki deneme değildir.

| Defter kümesi | Repo satır | Modal satır | Durum |
|---|---:|---:|---|
| G1 fixture/corr | 112 (80 screen, 32 referee) | 112 | birebir kopya |
| G2 | 767 | 767 | birebir kopya |
| Search (arama/eleme/doğrulama/replikasyon) | 2.412 | 2.412 | birebir kopya |
| Tam Turtle (ilk girişim + tekrar) | 20 | 20 | birebir kopya |
| Completion (risk/misc/nested/scaled) | 805 | 805 | birebir kopya |
| Ensemble v1 | 1 | 1 | birebir kopya |
| pre2022 asıl (A + iki B girişimi) | 0 | **648** | defterde var, repoda yok |
| Smoke: pre2022 / full / ensemble | 0 | **656 + 12 + 1 = 669** | Volume defterinde var, repoda yok |
| **Toplam** | **4.117** | **5.434** | **1.317 satır fark** |

Repo kaynak toplamı: referee 3.245, screen 872. 73 Volume defterinde bozuk JSON satırı 0; her dosyada `trial=1..n`, yinelenen dosya-içi trial 0. Bunlar anlık görüntü kontrolüdür; ileride aynı dosyaya iki konteyner yazılmasının güvenliğini kanıtlamaz.

Defter sadece repo ile sayılınca pre2022'nin 648 ve smoke'un 669 satırı kayboluyor. “4.117 proje kümülatif” ifadesi bu anlık görüntüde yalnız **repo sayısı**; bütün saklanan defter satırları 5.434. Smoke/fixture çıkarılacaksa açık kapsam gerekir: 5.434−669−112=**4.653** asıl-koşu defter satırı. Bu sayı bile deftere reddedilen/hiç yazılmayan denemeleri veya eski Qlib/RD-Agent'i kapsamaz; **istatistik N'si değildir**. Bu denetim sayaçları yeniden yazmadı.

## Taramalar / grid'ler: hangisi deftere girmiş?

| İş / kaynak | Sayılan yapılandırma/koşu | Defter durumu | Defter dışı kayıt / sınır |
|---|---|---|---|
| Eski M0 Qlib + RD-Agent (`smoke.md`, iki smoke script'i) | 1 Qlib smoke + 1 RD-Agent döngüsü | Kepler defteri yok | Metin raporu var; RD-Agent hipotezi iki faktör söyler ama kanıt örneği 20g vol kodudur; tam iç deneme sayısı **doğrulanmadı**. |
| Eski donuk Qlib (`backtest_only.py/.sh`, metrics.yaml) | 1 saklanan backtest raporu | defter yok | Kepler perp hakemi değil. Rapordaki pencere 2023-01→2026-08; eski başka veri hattı özetidir, Kepler mühür açıldı kanıtı değildir; betik çalıştırılmadı. |
| G1 korelasyon (`g1_real.py`) | 16 config (6 mom + 6 rev + 4 trend) | 112 tarihsel satır, 80 screen/32 referee | Tek 16-config grid'in tekrarları; aynı girişlerin tekrarları silinmedi. `xcheck_btc.md` mekanik muhasebe kontrolü, yeni edge hipotezi değil. |
| G2 (`g2.py`, `book_signals.md`) | 7 çalıştırılan job; 59 sembol-job × (6 maliyet + 7 pencere)=767 | 767 referee | Rapor 6 sinyal×2 evren=12 toplulaştırma sunar; core-5 çoğu job için ext-9 satırlarından altküme, ayrı yeni 767 koşu değildir. Null iki yöntemle toplam 35.400 sembol-çekiliş sonucu deftersiz kontrol. |
| Arama (`search.py`) | **88** config: Donchian 30, EMA 24, tsmom 21, xs_mom 6, xs_carry 3, xs_rev 4; ×9 sembol | 792 referee + 792 screen | Altı ailede sayılan bütün config isimleri kayıtlarda var. Eleme score satırı sonuç değil, sayaca girer. |
| Arama doğrulama | seçilmiş 6 config×9 sembol×6 maliyet=324 | 324 referee | 6×9×300=16.200 null sonucu deftersiz. |
| Arama replikasyon | 6 config×14 sembol×6 maliyet=504 | 504 referee | 6×14×300=25.200 null sonucu deftersiz. |
| Tam Turtle (`full_systems.py`) | 2 sistem×6 varyant=12 | ilk girişim 10 + yeniden koşu 10 =20 | Son primary'de **S2_no_stop** ve **S2_fixed_size** invalid/row_trial=None; 109/48 red. İkisi deftere girmedi, protokol N=12'ye dahil eder. 87 robust +2 K7 +1.000 null sonucu kontrol, deftersiz. |
| Completion risk | 2 sistem×3 yeni varyant=6 | 6 referee | 2 base yeniden hesap kontrolü deftersiz; risk JSON toplam8. |
| Completion BTC vol_target | 3 config | 3 referee | `aggregate` doğrulaması deneme sayılmaz. |
| Completion ölçekli kill | 2 sistem×2=4 | 4 referee | Ön kayıt scaled_kill; yeni satırlar kaydedilmiş. |
| Completion nested | aynı88 config×9=792 | 792 referee | Beş dış WF adımındaki seçim raporları yeni strateji koşusu satırı değildir; sürekli seriden dilimlenir. Rastgele seçim 5.000 kontrol. |
| Completion kapasite/stres/MC/PBO/SPA | kapasite 2×3 sermaye=6; Y=0,5/1/2 maliyet bindirmesi18; stres4 ana koşu; 2×5.000 işlem permütasyonu; PBO 88 config, SPA 2 benchmark | deftersiz kontrol | Yeni config seçilirse N'ye girmesi gerekir; bu rapor sonuçtan seçim yapmaz. |
| pre2022 Blok A (`pre2022.py`) | primary 4 sistem×6=24; full4 | 4 referee (yalnız Volume) | 20 ablasyon/ölçekli kontrol deftersiz. Robust shard'larında161 summary sonucu, ek shard metadata4; null4×500=2.000. |
| pre2022 Blok B | 6 config×9×6=324 final maliyet sonucu | ilk girişim321, final323 =644 (yalnız Volume) | Final **xsrev_3/BTCUSDT/fee11-slip2** `ledger=False`, n_rejected=50, funding_missed=0. İlk girişim beklenen324'e göre3 satır kısa; bunların her birinin koşulup koşulmadığı **doğrulanmadı**. 16.200 null kontrol. |
| Ensemble v1 (`ensemble.py`) | primary JSON35: 1 asıl +34 kontrol; ayrıca K7=1 ve null300 | asıl1 referee | 5 ablasyon, 6 komşu, 5 maliyet, 16 pencere/başlangıç, BH1, cap5001 kontrol; deftersiz. |
| Zone Fade (`zone_fade_protocol.md`) | **PLANLI** asıl1 +8 komşu +4 ablasyon +500 null | 0 | Kod/çıktı/defter yok; koşulmuş deneme sayılmaz. |
| Veri/QC/kitap kalitesi ve A/B/C | strateji grid'i yok | yeni satır0 | Rapor/ölçüm ve bu scratchpad kilit testi, edge araması değildir. |

Smoke kayıtları ayrıca sayıldı: full_smoke 12 asıl-varyant satırı; ensemble_smoke 1 asıl satır (primary JSON21 sonuç); pre2022_smoke A4, ilk B432, ikinci B216 ve `ledger_t_donchian` debug4 =656. Bunlar “kaybolmuş strateji sonuçları” diye ana araştırma tablosuyla birleştirilmedi; saklanan deneme izleridir.

## Envanterde ölçüm/izlenebilirlik bulguları

1. **Repo defteri eksik:** asıl pre2022 sonuçları raporda var, 648 defter satırı yalnız Volume'da. Smoke/debug669 da repo kümülatife girmez. Kopya SHA256 eşleştirmeleri `ledger_reconciliation.csv`'de; satırlar taşınmadı.
2. **Başarısız koşular defterde yok:** Tam Turtle iki primary config, final pre2022 B bir maliyet senaryosu ham çıktıda işaretli. `pre2022.md` bunu funding diye özetlerken final artifact n_rejected=50, funding_missed=0 taşır; rapor ile artifact'in gerekçesi uyuşmuyor. Başarısız denemeyi yalnız satır toplamından görmek mümkün değil. Ön kaydın N sayımı ve gerçek defter sayımı ayrılmalıdır.
3. **Ablasyon sayım çelişkisi:** BACKTEST §10 ablasyon için “her varyant bir deneme” der; EV1/pre2022/Zone Fade ön kayıtları ablasyonları kontrol diye defter dışında bırakır. EV1 ayrıca DSR N=6 (asıl+5 ablasyon) kullanır ama defterde1 satır vardır. Bu çelişki raporlandı; belge/defter/evaluate kuralı değiştirilmedi.
4. **Satırdan sembol eşleme eksik:** g2/search/nested satırlarının `config`'inde sembol kimliği yok; data_hash global manifesttir. Repo'da aynı source/config_hash/code_hash/data_hash bileşimini paylaşan **1.129 fazla satır** var. Bunlar kanıtlanmış tekrar koşu değildir: aynı çözünürlükteki farklı semboller aynı kimliği paylaşabilir. Kopya elemek için config hash tek başına yeterli değildir; bu sayıyla trial'lar silinmedi, data/result/hypothesis kimliği düzeltilmedi.
5. **Eski hat kalıntıları:** Qlib/RD-Agent ve books_quality betikleri çağrı envanterinde ayrı tutuldu. Dosya olması çalıştırılmış scan kanıtı değildir. Tüm18 script'in hash ve evaluate/run_book/record/screen çağrıları `script_inventory.csv`'de; rapor üreticileri yalnız var olan sonuçları toplulaştırır.

## `flock`: iki ayrı eşzamanlı Modal konteyneri

Test kaynağı **`scratchpad/flock_modal_volume.py`**. İki ayrı sandbox aynı `kepler-data:/scratchpad/<benzersiz>/shared.lock` dosyasını açtı; dosya önce yüklenmişti, içerik SHA256 iki konteynerde aynıydı. Aynı UTC epoch anında `LOCK_EX|LOCK_NB` denendi ve kazanan kilidi12 saniye tuttu. Aynı konteynerde ayrı ikinci file descriptor yerel negatif kontroldür. Modal SDK `1.2.0`, Debian/Python 3.12; iki bağımsız tur, dört ayrı sandbox; süre/başlangıç/geçerlilik ve sandbox kimlikleri `trial_inventory_data/flock.json`'da. Test kilit dosyaları Volume scratchpad'de kaldı, gerçek ledger açılıp yazılmadı.

| Tur | A exclusive lock | B exclusive lock | Aynı-konteyner ikinci açılış | Exclusive sürelerin örtüşmesi | Sonuç |
|---|---|---|---|---|---|
| 1 | aldı | aldı | ikisinde de engellendi | 12.009143 saniye | **kırmızı** |
| 2 | aldı | aldı | ikisinde de engellendi | 12.009322 saniye | **kırmızı** |

Her iki tur geçerli eşzamanlı girişimdir (başlangıçlar aynı planlı anda, dosya içeriği aynı; hata yok). **Bu Volume/mount/SDK-konteyner kurulumunda flock konteynerler arasında mutual exclusion sağlamaz.** Aynı konteynerde çalışması başka konteyner yazarı için güvence değildir. Etki: aynı Volume ledger dosyasına eşzamanlı yazan konteynerlerde `trial` ve append/commit bütünlüğü için kilide güvenilemez; mevcut lokal concurrency testinin yeşil olması bunu kapatmaz. Bu test geçmiş defterlerin bozulduğunu kanıtlamaz (snapshot'ta sıra/JSON bozukluğu yok), diğer Modal sürümleri/Volume düzenleri için genellenmez. Düzeltme uygulanmadı.

## Doğrulama / kapanış

Defter JSON/sıra ve SHA256 kopya eşleşmesi **yeşil**; eksik repo envanteri/başarısız-deneme izi/ablasyon sayımı **kırmızı**. Konteynerler arası kilit **kırmızı (2/2 tur)**; aynı-konteyner kontrolü **yeşil**. Korunan üretim kodu ve defter SHA256 kontrolü ayrıca yapıldı; ilgili kaynaklarda diff yok. Proje suite'i **atlandı** (üretim kodu değiştirilmedi); test dosyası yalnız scratchpad'de. Hakem+yapıştırma473; veri/QC/mühür439 (artış0); scratchpad test yardımcı kodu bu iki üretim sayısına eklenmedi. Mühür açma/anahtar/seal aracı **atlandı**.

**İş durumları:** A **kırmızı** (tamamlandı, veri ölçüm-riskleri); B **kırmızı** (hesap tamam, güncel MEXC doğrulaması engelli); C **kırmızı** (tamamlandı, envanter ve dağıtık kilit bulguları). Üç iş de rapor üretti; yeşil bir canlı uygunluk iddiası yok.
