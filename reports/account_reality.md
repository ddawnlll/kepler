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


## 12 Ekim 2026: $500 uygulanabilirlik offline replay (#16)

**Karar: FAIL (her iki sistem, her ücret senaryosu). Bu operasyonel uygunluk ölçümüdür, edge veya kârlılık kanıtı değildir.** Kod/ölçüt: `scripts/account500.py` (ölçütler koşudan ÖNCE docstring'e yazıldı); ham çıktı: `reports/account500_data/<sistem>__<senaryo>.json`. Canlı API emri, anahtar ve mühürlü dönem yok; pencere 2020-04 → 2026-04 (geliştirme verisi), sermaye $500, mevcut hakem + `min_notional=0` (borsada ayrı min-notional alanı yok; gerçek minimum `minVol` sözleşme), kör yukarı yuvarlama ve risk bütçesi büyütme yok.

**Kural kaynağı ve tarihi:** MEXC `contract/detail` halka açık GET, `fetched_utc` = 2026-10-11T20:05:05Z, 1.088 USDT sözleşmesi (`reports/account500_data/mexc_rules.json`). Bu dosya 6 Ekim'deki 9 sembollük `trade_audit_data/fix/mexc_rules.json` ile 3 Ekim'deki "engelli" `account_reality.md` bulgusunun YERİNE geçer: 3 Ekim erişemedi, 6 Ekim ve bu koşu eriştı; iki belge tarihleriyle okunmalıdır. Eşleme yalnız ad olarak `BASEUSDT` = `BASE_USDT`; 1000× vb. dönüşümler doğrulanmadı. Güncel kurallar geçmiş döneme uygulanır; listeleme tarihi ve eski kurallar UNKNOWN.

| sistem | senaryo (fee+slip RT bps) | niyet | lot/minimum'da gönderilemeyen | medyan hedef→fiili sapma | risk sapması payı | net $ (kurallı / ince adım) | Sharpe (kurallı / ince adım) | ölçüt kararı |
|---|---|---:|---:|---:|---:|---:|---:|---|
| EV1 (9 sembol) | model 10+2 | 5.297 | %28,5 | %20,8 | %28,3 | 363,4 / 405,6 | 2,07 / 1,89 | FAIL (C1, C2) |
| EV1 | MEXC liste 4+2 | 5.297 | %28,5 | %20,8 | %28,3 | 370,9 / 415,2 | 2,12 / 1,93 | FAIL |
| EV1 | stres 16+4 | 5.297 | %28,5 | %20,8 | %28,3 | 353,3 / 392,8 | 2,02 / 1,83 | FAIL |
| carry_xs (dinamik evren) | MEXC liste 4+2 | 8.528 | %42,3 | %46,2 | %41,7 | 69,4 / 134,6 | 0,96 / 1,44 | FAIL |
| carry_xs | stres 16+4 | 8.528 | %42,3 | %46,2 | %41,7 | 57,4 / 116,3 | 0,80 / 1,24 | FAIL |

(carry_xs model 10+2 senaryosu: bkz. `reports/account500_data/` (varsa); gönderilemeyen oranı senaryodan bağımsızdır.) Ölçüt C1: bloke ≤ %5; C2: |Δnet| ≤ %5 ve |ΔSharpe| ≤ 0,10. Hepsi aşıldı. "Ince adım" = aynı hedeflerin yuvarlamasız referansı (heuristic adım, min_notional=0).

- **Bloke niyetlerin tamamı lot no-op'tur (`noop_lot`)**: hedef, bir sözleşmeye yuvarlanınca mevcut pozisyondan farklı çıkmıyor; hata/red değil, görünür bir sınırlama (`n_rejected=0`, `n_engine_unfilled=0`, `n_liq=0`). EV1'de sembol bazında: ETH 476/606, DOGE 419/587, SOL 350/623, AVAX 97/585, BNB 72/589 gibi; ADA ve XRP neredeyse hiç bloke değil. carry_xs'te 119 sembolün 42'sinde niyetlerin yarıdan fazlası bloke.
- **Eşlenemeyen/listelenmeyen semboller (carry_xs):** 43 sembol (ör. `1000PEPEUSDT`, `1000SHIBUSDT`, `FTMUSDT`, `EOSUSDT`) MEXC listesinde birebir adla bulunamadı; hedef notional payı %17,4. Bu koşu onları dışarıda bıraktı; ölçüt C4 bu yüzden UNKNOWN (FAIL değil).
- **Maruziyet/maliyet:** ideal ortalama brüt hedef ≈ $8,38 (EV1) ve $3,49 (carry) ölçeğinde kalır; fiili ortalama brüt EV1'de $6,01, carry'de $2,04 (sermaye $500, hedef kaldıraç düşük). Devir (işlem hacmi / sermaye, 6 yıl): EV1 50,2×, carry 34,2×. Fee+slip toplamı EV1'de 7,5 / 15,1 / 25,1 USDT (liste / model / stres), carry'de 5,1 / 17,1 (liste / stres). Funding: EV1 toplamı −0,35 USDT, carry +22,36 USDT (Binance funding verisiyle; MEXC funding kanıtı değildir).
- **Muhasebe:** `report.reconcile` her koşuda tuttu (fark ~0). Stop sapması: EV1/carry kitaplarında strateji stopu yok (`stop=NaN`); yalnız likidasyon stopu var, `n_liq=0`.
- **Bu replay'in KANITLAMADIĞI (UNKNOWN):** hesap ücreti/VIP/indirim (liste ücreti ≠ hesap ücreti), likidite/slippage (yalnız sabit bps), MEXC funding ödeme kuralı ve zamanı, mmr/marj kademeleri ve likidasyon kuralı, Binance fiyat ve funding'inin MEXC davranışıyla eşdeğerliği, güncel kuralların 2020-2026 boyunca geçerliliği, sembol listeleme/delist tarihleri, 1000× kontrat eşlemeleri. "Daha yüksek sermayede yakınsama" (6 Ekim: $2.500) evrensel minimum sermaye veya carry/$500 doğrulaması değildir.
- **Sonuç:** $500'da EV1 niyetlerinin ~%28'i ve carry_xs niyetlerinin ~%42'si borsa kontrat adımı yüzünden uygulanamıyor ve sonuçlar yuvarlamasız referanstan ölçüt dışı sapıyor. Çözüm (daha büyük sermaye, daha az/ucuz sembol, farklı boyutlama) yeni önkayıt ister; bu iş hedefleri yukarı yuvarlamadı ve risk bütçesini büyütmedi.
