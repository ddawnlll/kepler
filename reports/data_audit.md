# İş A — Veri/ölçüm kalitesi

**KIRMIZI: denetim tamamlandı; tape'de boşluk ve mark–last ayrışması var.** Modal `kepler-data:/data` altındaki 2.531 Parquet dosyasının tamamı tarandı; 0 okunamayan, 0 atlanan dosya. Bu bir veri/ölçüm raporudur; edge veya canlıya geçiş kararı değildir. Hiçbir veri düzeltilmedi, strateji/hakem/denetim/risk/mühür kodu değiştirilmedi.

Ölçüm: 3 Ekim 2026 (Europe/Istanbul), salt okunur Modal Volume. Yalnız zaman sütunu önce okunup bütün zamanların `<2026-04-01 UTC` olduğu kontrol edildi; sonra veri sütunları okundu. Mühür yoluna/sınırına rastlanmadı; anahtar kullanılmadı, seal aracı çalıştırılmadı. Dosya SHA256 ve satır sayıları `data_audit_data/files.csv`'de. Önceki QC özetlerini kopyalamak yerine tam Volume yeniden ölçüldü.

## Kapsam ve yöntem

- 494 OHLCV tape dosyası (247 last + 247 mark), 246 funding tape, 2 universe, 1.789 aylık hacim/yardımcı Parquet = 2.531. Aynı sembol iki kökte varsa sembol sayılarında bir kez sayılır; kayıt sayıları dosyalardaki gözlemlerin toplamıdır.
- 1h boşluk: benzersiz sıralı zamanlar arasında fark >1h. Çift bar: aynı tape dosyasındaki yinelenen `ts`; aylık hacim tablosunda anahtar `(sym, month)` olur. Farklı sembollerin aynı ayı çift bar değildir; shard'ların fiziksel sırası bir piyasa-bar sırası değildir.
- Aykırı fiyat: ardışık close oranında >%50 değişim veya high/gövde-üstü ya da gövde-altı/low >1,5. Bu eşikler keşif bayrağıdır, veri hatasını kanıtlamaz. Eski QC'nin %30 getiri / `(high-low)/close>%50` eşikleriyle sayılar birebir karşılaştırılmaz.
- Ayrışma: aynı saatte `abs(last_close/mark_close−1)>%5`; kesim bayrağı ≥24 gerçek ardışık saat. Funding 8h testi saniyeye yuvarlanmış zaman aralığında yapılır; millisecond jitter ayrıca raporlanır.
- Evren uyumu dosya kümesi ile üyelik kümesini karşılaştırır; erken veri sonu resmi delist kanıtı değildir. Listeleme/delist resmi doğrulaması bu işte yapılmadı: **doğrulanmadı**.

## Bulgular ve etkileri

| Bulgu | Etkilenen benzersiz sembol | Kayıt/olay | Örnek ve etkisi |
|---|---:|---:|---|
| 1h bar boşluğu | 100 | 324 | `AVAXUSDT`; [{"after": "2021-07-02 00:00:00+00:00", "hours": 25.0, "missing": 24.0}, {"after": "2021-07-28 00:00:00+00:00", "hours": 97.0, "missing": 96.0}]. dolum gecikmesi, ATR/oynaklık ve hedef ömrü sapması. |
| Close değişimi >%50 | 65 | 251 | `ALICEUSDT`; [{"_t": "2021-05-19 12:00:00+00:00", "open": "8.888", "high": "9.144", "low": "4.125", "close": "4.84"}]. uç fiyat gerçek olay mı hata mı doğrulanmadı; stop/null/vol etkilenir. |
| Fitil/gövde oranı >1,5 | 157 | 350 | `1000SHIBUSDT`; [{"_t": "2021-05-19 13:00:00+00:00", "open": "0.007424", "high": "0.012071", "low": "0.00475", "close": "0.008735"}]. uç fiyat gerçek olay mı hata mı doğrulanmadı; stop/null/vol etkilenir. |
| Mark–last close ayrışması >%5 | 54 | 204216 | `AAVEUSDT`; [{"_t": "2021-05-19 12:00:00+00:00", "close_last": "438.03", "close_mark": "393.30512783"}]. veri kullanılabilirlik kesimi ve hayali PnL riski. |
| Funding zaman farkı 8h değil | 101 | 298456 | `OMGUSDT`; [{"ts": "2021-11-11 14:00:00.004000+00:00", "interval_hours": 5.999997777777778}, {"ts": "2021-11-11 16:00:00.007000+00:00", "interval_hours": 2.0000008333333334}]. 8h sabit varsayımı funding maliyetini yanlış hesaplar; değişken aralık tek başına hata değildir. |
| Beyan edilen funding aralığı 8h değil | 101 | 298527 | `OMGUSDT`; [{"_t": "2021-11-11 14:00:00.004000+00:00", "funding_interval_hours": "2", "last_funding_rate": "-0.024"}, {"_t": "2021-11-11 16:00:00.007000+00:00", "funding_interval_hours": "2", "last_funding_rate": "-0.024"}]. 1/2/4h oranlarını 8h sanmak maliyeti saptırır. |
| Zaman farkı ile aralık metadata uyuşmazlığı | 36 | 50 | `OMGUSDT`; [{"_t": "2021-11-11 14:00:00.004000+00:00", "funding_interval_hours": "2"}]. eksik settlement veya geçiş; olay aralığı metadata ile uyuşmuyor. |
| Mutlak funding oranı >%1 | 78 | 975 | `OMGUSDT`; [{"_t": "2021-11-09 16:00:00.001000+00:00", "last_funding_rate": "-0.018"}, {"_t": "2021-11-10 00:00:00+00:00", "last_funding_rate": "-0.018"}]. tek settlement >%1; funding getiriye baskın olabilir. |
| Kökün veri sonundan >7 gün erken biten kontrat | 7 | 7 | `LENDUSDT`; [{"last": "2020-11-10 08:00:00+00:00", "root_last": "2021-12-31 23:00:00+00:00", "days_before_end": 416.625}]. veri sonu erken; delist resmi kaynaktan doğrulanmadı, kesik tape ile karıştırılmamalı. |
| Boş yardımcı hacim dosyası | 762 | 943 | `0GUSDT`; []. girdi yok. |
| Evren dışında kalan last dosyası | 3 | 3 | `PAXGUSDT`; ["PAXGUSDT"]. üyelik ile disk sembolleri farklı; fazladan dosya tek başına araştırma evrenine alınmaz. |
| Çift bar (last/mark/funding tape) | 0 | 0 | 740 tape dosyasının zaman kontrolünde tekrar yok; BTC 37.224 last barıyla ayrıca doğrulandı. |
| Sıfır / negatif / NaN-inf fiyat; bozuk OHLC | 0 | 0 | 494 fiyat tape'inde bu kontroller tetiklenmedi. Bu sonuç aykırı fakat pozitif fiyatların doğruluğunu kanıtlamaz. |
| Last var, mark yok (yalnız ortak başlangıç/bitiş aralığında) | 97 | 8688 | AVAXUSDT pre2022: 2021-07-01 00:00/01:00; mark fallback, stop/likidasyon ve funding fiyatı etkilenir. |
| Mark var, last yok (yalnız ortak aralıkta) | 33 | 4297 | Eksik işlem barı/karar/dolum gecikmesi; tam örnek listesi `time_checks.json`. |
| Funding tam saatten millisecond sapması | 201 | 332.165 | 1000SHIBUSDT 2021-05-10 16:00:00.013; en büyük sapma 0,047 saniye; >1 saniye sapma 0 sembol/0 kayıt. Bu bir saatlerce gecikme değildir. |

Boşlukların toplamı **12,999 eksik saat** (last ve mark ayrı sayılır; aynı saatin iki kaynakta eksik olması iki ölçümdür). AVAXUSDT pre2022 mark'ta 24+96=120 saat eksiktir; BTC ana tape'de 37.224 last, 37.152 mark barı vardır (72 mark saati farkı). Toplam zaman kümesi farkı 188 sembolde 65.409 satırdır; yukarıdaki ortak-aralık sayıları listeleme başlangıcı/sonu farklarını bundan ayırır. Bütün farkı iç boşluk diye okumak yanlış olur.

**Funding:** 101 sembolde 298.456 ardışık settlement aralığı 8h değildir; metadata 101 sembolde 298.527 settlement'ta 8h dışı aralık verir. Aynı büyüklük beklenmez: ilk olayın önceki settlement'ı yoktur, aralık geçişleri vardır. 36 sembolde 50 zaman-aralık metadata uyuşmazlığı gözlendi; ör. OMGUSDT 2021-11-11 14:00:00.004 (beyan 2h), AIAUSDT 2025-10-30 16:00:00.001 (4h). Eksik olay mı program değişimi mi **doğrulanmadı**. Sabit 8h funding varsayımı bu dosyalarda ölçümü bozar; geçerli 1/2/4h aralık tek başına veri bozukluğu değildir.

**Kalıcı ayrışma:** 28 sembolde ≥24 ardışık saat >%5 ayrışma var; `tape/usable.json` da 28 kesim taşır. Örnekler ve başlangıçlar bulgu JSON'unda. Ham tape'nin kesim sonrasını stratejiye vermek hayali/ölü-kontrat PnL'si yaratabilir; bu denetim mevcut kesimleri değiştirmedi. pre2022 kullanılabilirlik kesimi 0. Kalıcı-ayrışma tablosundaki `count`, en uzun koşunun saat sayısıdır; settlement/bar adediyle toplanmaz.

## Evren, delist ve survivorship

| Kök | Ay | Universe sembolü | Disk last sembolü | Eksik üye | Fazladan dosya |
|---|---:|---:|---:|---:|---|
| Ana `/data/tape` | 51 | 178 | 181 | 0 | PAXGUSDT, XAGUSDT, XAUUSDT (3) |
| `/data/pre2022/tape` | 23 | 66 | 66 | 0 | yok |

Aylık üyelik `(month,sym)` çiftlerinde tekrar yok. 943 boş Parquet, 762 benzersiz sembolün **yardımcı `vol/` dosyalarıdır**; bunlar 762 bozuk strateji sembolü demek değildir. pre2022 döneminde henüz listelenmemiş adayların boş hacim dosyaları da bu sayıya girer. İşlem tape'sinde boş dosya bulunmadı. 1.789 hacim dosyasını bar dosyası gibi saymak evren büyüklüğünü şişirir.

7 sembol kendi kök sonundan >7 gün önce biter: LENDUSDT (pre2022; son 2020-11-10 08:00), EOSUSDT, GALUSDT, LUNAUSDT, MATICUSDT, RNDRUSDT, TOMOUSDT (tam tarihler bulgu dosyasında). Bunlar delist/isim dönüşümü/kesik indirme adaylarıdır; resmi delist **doğrulanmadı**. Son bar tarihi ile kullanılabilirlik kesimi farklı olaylardır. Aylık universe yeni/sona eren üyeleri barındırıyor; EV1 ve Zone Fade'in sabit BTC/ETH/SOL/XRP/BNB/DOGE/ADA/LINK/AVAX sepetleri ise 9/9 bugün seçilmiş semboldür. Bu seçim survivorship yönünde iyimserdir; tarihsel aylık evren bulunması sabit-sepet testinden bu yanlılığı çıkarmaz.

## Doğrulama ve sınır

Tam dosya envanteri + zaman bağımsız kontrolü tamamlandı (**yeşil**). Sıfır/negatif fiyat ve çift bar kontrolü **yeşil**; boşluk/ayrışma/funding ölçüm-riskleri **kırmızı**. Resmi delist teyidi **atlandı / doğrulanmadı**. Mühürlü dönem ve anahtar erişimi **atlandı** (kural gereği). Aykırının gerçek piyasa olayı mı arşiv hatası mı olduğu; özel likidasyon olayları; Binance→MEXC farkı **doğrulanmadı**. Hiçbir düzeltme veya yeni strateji denemesi yapılmadı; deftere yeni satır 0.

Kod sayıları (boş/yorum satırı hariç mevcut yöntem): hakem+yapıştırma 473; veri/QC/mühür araçları 439. Artış 0. Dokümantasyon için proje testleri **atlandı**; üretim kodunda değişiklik yok.

**İş durumları:** A **kırmızı** (denetim tamam; bulgular var); B **atlandı** (henüz başlamadı); C **atlandı** (henüz başlamadı).
