# G2 sinyalleri — veriye bakılmadan sabitlendi

Bu dosya, G2 koşusundan ve `kepler/signals.py` yazılmadan önce commit'lenir. Parametreler kitaptan alınmıştır; sonuca bakılıp **ayarlanmaz**.
Sinyal ve evren (çekirdek-5: BTC, ETH, SOL, XRP, BNB; genişletilmiş-9: + DOGE, ADA, LINK, AVAX) sonuçtan önce sabit.

Ortak kurallar
- Kararlar **günlük** mumla verilir (kitaplar günlük/aylık çalışır): günlük mum = 24 saatlik bar; karar 00:00 UTC kapanışında, dolum ertesi bar açılışında (hakem `next_open`).
- Birim pozisyon ±1 (notional sabit); vol hedefleme/risk motoru yok (MISSION: G3 sonrası). Stop yok: kitaplardaki 2N/ATR stopu hakemde modellenmedi → **sapma**, rapora yazılır.
- Long+short. "Aylık" kararlar ayın ilk günü 00:00 UTC kapanışında (önceki ayın son günü bilgisiyle) verilir, ay boyu tutulur.

| Sinyal | Kaynak | Kural (sabit) |
|---|---|---|
| `turtle_s1` | Curtis Faith, *Way of the Turtle* (2007), System 1 | Giriş: kapanış önceki 20 günün en yüksek (en düşük) değerini aşarsa long (short). Çıkış: long için önceki 10 günün en düşüğünün, short için en yükseğinin ihlali. Ters giriş pozisyonu çevirir. Faith'in "son kırılım kazançlıysa atla" kuralı **uygulanmadı** (sapma). |
| `turtle_s2` | aynı, System 2 | Giriş 55 gün, çıkış 20 gün. |
| `donchian_trend` | aynı, bölüm 10 "Donchian Trend" | `turtle_s1` + trend filtresi: yalnız 25-gün EMA > 350-gün EMA iken long, tersiyken short; filtre karşıtı girişler yok sayılır, çıkış kuralı aynı. 2-ATR stopu uygulanmadı. |
| `tsmom` | Gary Antonacci, *Dual Momentum Investing* (2015), mutlak (zaman serisi) momentum; formasyon 12 ay (kitap: "en iyi sonuçlar 12 ayda kümelenir") | Aylık: son 365 günlük getiri > 0 → long, < 0 → short. Antonacci T-bill'e geçer (long/cash); burada long/short'a uyarlandı (**sapma**; bono getirisi 0 alındı). |
| `dual_mom` | aynı, çift momentum (göreli + mutlak) | Aylık: evrende 365 günlük getiriye göre sırala; getirisi > 0 **ve** evren medyanının üstünde → long; getirisi < 0 **ve** medyanın altında → short; diğer → flat. Evren = o koşunun evreni (5 veya 9). |
| `carry_funding` | forex carry trade (*Currency Strategy*, *Little Book of Currency Trading*): yüksek getirili (faiz alan) tarafı tut; perp'te "faiz" = funding | Aylık: son 30 günün ortalama funding oranı > 0 → short (funding alır), < 0 → long. Kitaplar sayısal parametre vermiyor: 30 gün **keyfi, UNKNOWN**; yalnızca perp kullanıldığı için delta-nötr değil, yönlü bir pozisyondur (ayrım için null'a bakılır). |

Deneme sayısı (DSR için): 6 sinyal × 2 evren = 12 yapılandırma (parametre taraması yok). Walk-forward'da parametre seçimi yok; sabit kural pencerelerde ayrı ayrı değerlendirilir.
