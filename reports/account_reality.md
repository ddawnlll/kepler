# İş B — $500 gerçekliği

**KIRMIZI / KISMEN ENGELLİ: güncel MEXC sembol kuralları ve hesap ücreti doğrulanamadı; $500 için hedef boyutları hesaplandı, canlı çalışabilir sembol sayısı doğrulanmadı.** İş A tamamlandıktan sonra yürütüldü. Bu denetim strateji kodu, parametre, hakem, risk, denetim veya defter değiştirmedi; yeni backtest/edge denemesi 0.

## Kaynak ve erişim

3 Ekim 2026, Europe/Istanbul. `contract.mexc.com/api/v1/contract/detail` ve `www.mexc.com/fee`: proxy CONNECT **403 Forbidden**. Bu engel başka ağ yolundan aşılmadı. Resmi `mexcdevelop/apidocs` GitHub deposunun **contract_v1_en** dalı erişildi: [sabit sürüm](https://github.com/mexcdevelop/apidocs/blob/deae62dcb89df0f8a839b657dc99084d6c3fb3ad/source/index.html.md), commit `deae62dcb89df0f8a839b657dc99084d6c3fb3ad`, belge tarihi 20 Kasım 2025. Ana dal Slate şablonudur, ürün kuralı kaynağı sayılmadı. Erişim sonucu `account_reality_data/sources.json`'da.

**Güncel halka açık sembol kuralları:** tape'nin 202 benzersiz last sembolünün tamamı için tick/lot/minimum ve MEXC'de listelenme durumu `account_reality_data/symbol_rules.csv`'de **doğrulanmadı**. Binance→MEXC sembol adları da yalnız eşleme adaylarıdır; 1000× kontratlar veya ad dönüşümleri teyit edilmedi. API emir yetkisi de doğrulanmadı (`apiAllowed` resmi contract/detail alanıdır).

| Strateji sembolü | MEXC tick | Base lot/contractSize | minVol / min notional | Güncel kaynak |
|---|---|---|---|---|
| BTCUSDT | doğrulanmadı | doğrulanmadı | doğrulanmadı | public endpoint 403 |
| ETHUSDT | doğrulanmadı | doğrulanmadı | doğrulanmadı | public endpoint 403 |
| SOLUSDT | doğrulanmadı | doğrulanmadı | doğrulanmadı | public endpoint 403 |
| XRPUSDT | doğrulanmadı | doğrulanmadı | doğrulanmadı | public endpoint 403 |
| BNBUSDT | doğrulanmadı | doğrulanmadı | doğrulanmadı | public endpoint 403 |
| DOGEUSDT | doğrulanmadı | doğrulanmadı | doğrulanmadı | public endpoint 403 |
| ADAUSDT | doğrulanmadı | doğrulanmadı | doğrulanmadı | public endpoint 403 |
| LINKUSDT | doğrulanmadı | doğrulanmadı | doğrulanmadı | public endpoint 403 |
| AVAXUSDT | doğrulanmadı | doğrulanmadı | doğrulanmadı | public endpoint 403 |

Resmi dokümanda `priceUnit` fiyat adımı; `volUnit` kontrat adımı; `minVol` minimum kontrat sayısı; `contractSize` bir kontratın base miktarıdır ([alanlar](https://github.com/mexcdevelop/apidocs/blob/deae62dcb89df0f8a839b657dc99084d6c3fb3ad/source/index.html.md#L375)). Dolayısıyla base miktar adımı = `volUnit×contractSize`; minimum pozisyon değeri en az `minVol×contractSize×fiyat` olur. Ek bir min-notional kuralının güncel varlığı/değeri **doğrulanmadı**; `Spec.min_notional=5` borsa kuralı değildir.

Dokümanın **örnek** BTC cevabı: priceUnit=0,5; volUnit=1; minVol=1; contractSize=0,0001 ([örnek](https://github.com/mexcdevelop/apidocs/blob/deae62dcb89df0f8a839b657dc99084d6c3fb3ad/source/index.html.md#L296)). Bunlar güncel kontrat kuralları değildir: **doğrulanmadı**. Yalnız örnek aritmetiği: dev dönemi 31 Mart 2026 açılışı 66.764,4 ile bu örnek minimum $6,67644 olur. Aynı fiyatta EV1'in son dolabilir BTC hedefi $3,0379'dur; örnek lotla bile yetmez. Bu karşılaştırma güncel BTC kuralı teyidi değildir.

## MEXC ücret ve funding

- Resmi contract/detail dokümanı `takerFeeRate` ve `makerFeeRate` alanlarını tanımlar ([kaynak](https://github.com/mexcdevelop/apidocs/blob/deae62dcb89df0f8a839b657dc99084d6c3fb3ad/source/index.html.md#L394)). BTC **örneğinde** taker 0,0006 (=yan başına 6 bps, RT 12 bps), maker 0,0002 (=yan başına 2 bps, RT 4 bps) yazılıdır; **güncel uygulanan ücret doğrulanmadı**. MISSION'daki MEXC RT 16 bps kullanıcı bilgisi, yine **doğrulanmadı**. EV1 ön kayıt RT 10 + slip 2 bps model varsayımıdır.
- Kullanıcının geçerli fee'si için resmi doküman `GET /api/v1/private/account/tiered_fee_rate`, `takerFee`, `makerFee`, `takerFeeDiscount`, `makerFeeDiscount` alanlarını verir ([kaynak](https://github.com/mexcdevelop/apidocs/blob/deae62dcb89df0f8a839b657dc99084d6c3fb3ad/source/index.html.md#L2350)). Hesap/VIP/indirim kuralı bu yüzden herkese aynı sayı sayılamaz. Özel borsa anahtarı yok ve istenmedi; özel endpoint çağrılmadı (**atlandı**).
- Resmi funding API'si `GET /api/v1/contract/funding_rate/{symbol}`: `fundingRate`, `maxFundingRate`, `minFundingRate`, `collectCycle` (charge cycle), `nextSettleTime` (next charge time) ve `timestamp` ([kaynak](https://github.com/mexcdevelop/apidocs/blob/deae62dcb89df0f8a839b657dc99084d6c3fb3ad/source/index.html.md#L647)). BTC **örneği** collectCycle=8 taşır; her sembol/gün için sabit 8h kuralı kanıtlamaz. History API'si ayrıca `settleTime` ve `fundingRate` olaylarını verir. Bunlar dokümanda **doğrulandı**, güncel cycle/rate alınamadı (**doğrulanmadı**).
- Erişilen resmi API dokümanı funding ücretinin hangi pozisyon değerinden, hangi kesin fill/settlement sırasıyla hesaplanacağını veya long/short ödeme yönünü açıkça tanımlamıyor. Bu ekonomik kuralı resmi SSS'den çıkarma kısmı **engelli / doğrulanmadı**; Binance hakem varsayımı MEXC kuralı diye sunulmadı. Binance funding örneklemi MEXC funding kanıtı değildir.

## Ensemble v1: mevcut kodun $500 boyutları

`kepler/ensemble.py` ve `signals.with_funding` kaynakları değiştirilmeden Modal'de çalıştırıldı; kaynak SHA256 `sizing.json`'da. Sermaye $500, aynı ön kayıtlı parametreler, 2020-04-01→2026-04-01 dev dönemi; son kararın dev içindeki sonraki açılışı yoksa o hedef sayılmadı. Son dolabilir karar 30 Mart kapanışı → 31 Mart 00:00 UTC açılışıdır; **bugünkü fiyat/karar değildir**.

Ham hedef `500×0,20×(1/M)×IDM×F_i/σ_i`, portföy oynaklık/1×sembol/3×brüt tavanları ve mevcut tampon aynen uygulanır. Hedefin next-open fiyatındaki miktarı mevcut **heuristic** lota aşağı yuvarlanıp varsayımsal $5 toplam pozisyon değerine karşı kontrol edildi. Bu, flat'ten o hedefe açılma uygunluğudur; mevcut pozisyondan emir **delta**'sı veya gerçek borsa kuralı değildir.

| Sembol | Sıfır olmayan hedef-gün | Varsayımsal min5'e uyan gün | Min5 altında gün | Medyan / en büyük mutlak hedef ($) | Son dolabilir hedef ($) | O gün min5 |
|---|---:|---:|---:|---|---:|---|
| BTCUSDT | 2163 | 1428 | 735 | 8.6303 / 53.4677 | -3.0379 | uygun değil |
| ETHUSDT | 2163 | 1385 | 778 | 7.4621 / 42.0113 | 3.1804 | uygun değil |
| SOLUSDT | 1930 | 1131 | 799 | 6.2530 / 27.5677 | -7.6144 | uygun |
| XRPUSDT | 2157 | 1271 | 886 | 6.5390 / 40.9548 | -15.5696 | uygun |
| BNBUSDT | 2152 | 1589 | 563 | 9.2938 / 47.3448 | -15.3734 | uygun |
| DOGEUSDT | 2001 | 1093 | 908 | 5.6987 / 55.8456 | -1.0195 | uygun değil |
| ADAUSDT | 2162 | 1293 | 869 | 6.5341 / 35.7582 | -16.0893 | uygun |
| LINKUSDT | 2163 | 1219 | 944 | 5.9414 / 26.7589 | -1.9453 | uygun değil |
| AVAXUSDT | 1926 | 1211 | 715 | 6.8197 / 37.1254 | -7.2110 | uygun |

**Sayım:** min5 + mevcut heuristic lot varsayımı altında geçmişte en az bir gün uygun **9/9** sembol; son dolabilir dev gününde **5/9** (SOL, XRP, BNB, ADA, AVAX). Gerçek MEXC kurallarıyla doğrulanmış uygun sembol **0/9**; bu “hepsi başarısız” değil, dokuzunun da borsa uygunluğunun bilinmediği anlamındadır. 18.817 sıfır olmayan sembol-günün 7.197'si (%38,2473) min5 toplam hedefinin altındadır. Bunlar 7.197 reddedilen emir değildir; hedef-gün ve emir farklı sayılardır.

Mevcut `scripts/ensemble.py` cap500 bilgisel koşusunun saklanan çıktısı: net $392,7440, 4.193 fill, n_rejected=0; 10k ana koşuda 5.561 fill. `reports/ensemble.md` “Min notional bağlamıyor” iddiası bu denetimle desteklenmiyor: `referee.py` artıran **delta** min-notional altında ise emri **göndermez**; bu n_rejected sayılmaz. Azaltan emirler istisnadır. Dolayısıyla n_rejected=0 minimumun etkisizliği kanıtı değildir. Bu denetimde hakem yeniden koşturulmadı, PnL yeniden ölçülmedi; eski PnL canlı kâr beklentisi değildir.

Heuristic tick/step, mevcut yükleyicide fiyat extrema ve sermayeden türetilir; API'den alınmaz. BTC örneğinde model step=1e−7 base iken resmi dokümanın tarihsel örneği base step=1e−4 verir (1000× fark); güncel fark **doğrulanmadı**. Lot yuvarlaması hedef boyutu kadar artırma/azaltma delta'sını da etkiler.

## Zone Fade: ön kayıt formülü ve uygulanabilirlik sınırı

Henüz Zone Fade uygulaması veya gerçekleşmiş aday/pozisyon çıktısı yok. Bu denetimde yeni strateji kodu/tarama üretilmedi. Mevcut `reports/zone_fade_protocol.md` formülü $500'a doğrudan ölçeklendi:

- İşlem risk bütçesi $500×%0,5 = **$2,50**. Göreli stop uzaklığı `d=|entry−stop|/entry` için `N=min(500, 2,50/d)`.
- Stop uzaklığı %0,5/%1/%2/%5/%10/%20/%50 için notional sırasıyla **$500/$250/$125/$50/$25/$12,50/$5**. Bunlar aritmetik senaryodur, gerçek aday stop dağılımı **doğrulanmadı**.
- Min5 varsayımı altında ve lot yok sayılırsa `0<d≤%50` koşulunda ön kayıtlı **9/9 sembol kuramsal olarak** minimumu sağlayabilir. Gerçek aday/fill bazında çalışan sembol sayısı **doğrulanmadı**. Güncel MEXC lot/minimum ve stop tick mesafesiyle uygunluğu doğrulanmış **0/9**; bilinmeyen 9/9.
- Gerçek kontrat hesabında `c=floor(N/(price×contractSize×volUnit))×volUnit`; `c≥minVol`, notional minimumu ve tick'e yuvarlanmış stopla risk kontrolü gerekir. `c` yukarı yuvarlanarak minimum zorla sağlanırsa ön kayıtlı $2,50 risk aşılabilir; bu raporda böyle bir düzeltme yapılmadı.
- Ön kayıt en çok **4 eşzamanlı**, aynı yönde **3**, toplam brüt **$1.500**; “9 çalışabilir sembol” aynı anda 9 pozisyon değildir. %0,5 stopla dört adet $500 hedefin $2.000 brütü tavana sığmaz; gap/slippage/fee/funding nedeniyle $2,50 stop riski gerçekleşmiş zarar garantisi değildir. Nominal dört risk bütçesi $10, aynı yön üç bütçe $7,50; korelasyon bunu bağımsız risk yapmaz.

## Sonuç ve doğrulama

**Engel:** güncel MEXC contract/fee/SSS ağ erişimi yok; hesap fee'si özel yetki gerektiriyor. Resmi doküman şeması ve alanlar **yeşil**; canlı tick/lot/minimum/fee/funding ödeme kuralı **doğrulanmadı / kırmızı**. Mevcut EV1 boyut hesabı **yeşil** (varsayımlar yukarıda); gerçek MEXC uygunluk testi ve Zone Fade gerçek aday sayımı **atlandı**. Bu eksikler düzeltilmeden $500 canlı gerçekliği teyit edilmiş sayılmaz. Kullanıcı talimatı gereği engel kaydedildi, sıradaki İş C'ye geçildi.

Kod sayısı: hakem+yapıştırma 473; veri/QC/mühür 439, artış 0. Proje testleri **atlandı** (üretim kodu değişmedi); deftere yeni satır 0; mühürlü dönem/anahtar **atlandı**.

## Çalışma penceresi kapanışı

3 Ekim 2026 09:45 Europe/Istanbul penceresi kapandı; kontrol saati 2026-10-03 09:50:11 +0300. Hesap tamam; güncel MEXC kuralları/fee/funding resmi doğrulaması engelli ve doğrulanmadı olarak kapandı. Ağ politikası değişmedi; engelli istek tekrarlanmadı. Gerçek MEXC uygunluk/Zone Fade aday testi atlandı. Kapanış bütünlük ve erişim kanıtı: `audit_closure.json`. Mühür/anahtar/seal aracı ve üretim test suite'i **atlandı**; yeni strateji denemesi 0.

**İş durumları:** A **kırmızı** (tamamlandı); B **kırmızı** (hesap tamam, güncel MEXC doğrulaması engelli); C **kırmızı** (tamamlandı, Volume flock/deneme envanteri bulguları).
