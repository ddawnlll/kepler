# Tam Turtle S1/S2: NO_EDGE — iki sistem de K1'de (rotasyon null + DSR) kalıyor

**Sonuç.** Tam Turtle (N-boyutlama, 2N stop, piramitleme, birim sınırları, brüt tavan) S1 ve S2 için **NO_EDGE** (kart `BACKTEST.md` §11): K1 kalıyor (S1: brüt p=0,026, Bonferroni N=12 eşiği 0,0042, DSR 0,52; S2: p=0,060, DSR 0,36). K2 (alfa t = 1,32 / 0,99), K3 (Sharpe 0,63 / 0,42 < 1,0), K4 (maks DD sermayenin %251 / %303'ü), K6, K9 da kalıyor; K5 ve K7 geçiyor. Ön kayıt: `reports/full_systems_protocol.md` (koddan önce commit'lendi, parametre/eşik koşudan sonra değişmedi). Tablolar: `reports/full_systems_data/tables.md`, ham veri aynı dizinde, defter `ledger/full_systems/`.

**Soruya cevap (tam sistem kırpılmışın yapamadığını yapıyor mu?).** Kısmen daha iyi, kartı geçecek kadar değil. Aynı pencere ve aynı hakemle kırpılmış kural (`g2_equiv`: stopsuz, sabit 1000 notional, piramit/sınır yok; S2'de G2'nin brüt 10 132 ve funding −2 346 rakamlarını **birebir** yeniden üretti) yıllık Sharpe 0,36 verirken tam sistem S1'de 0,63, S2'de 0,42; ortak-ofset null p'si S1'de 0,026 (G2'de en iyi 0,06), S2'de 0,060 (aynı). Kazanç büyük ölçüde **stoptan** geliyor (stop kapatılınca Sharpe −0,24 / −0,42 ve likidasyon/hesap sıfırlanması), piramitleme ve N-boyutlama Sharpe'a katkı veriyor (S1), birim sınırı S2'de katkı vermiyor (K8). Ama edge'in null'dan ayrışması, maliyet sonrası risk ve zamansal tutarlılık kartın gerisinde: eksik olan yalnızca motor değil, sinyalin de bu kartı tek başına geçmemesi.

## Kurulum
Genişletilmiş-9 (BTC ETH SOL XRP BNB DOGE ADA LINK AVAX), gruplar {BTC,ETH,BNB} {SOL,AVAX,ADA} {XRP,DOGE,LINK}; dönem 2022-03-01 → 2026-04-01; sermaye 10 000 (sabit, bileşik yok), risk %1/birim, N=Wilder ATR(20), stop 2N, ekleme 0,5N, ≤4 birim/sembol, grup ≤6, toplam ≤12, brüt tavan 4× sermaye; fee 10 + slip 2 bps rt (temel), mmr 0,005, kaldıraç limiti 10, likidasyon açık, kill switch yok; Nautilus portföy hakemi (tek hesap, ortak marj). Mühür/2026-04-01 sonrası dokunulmadı. Kod: `kepler/turtle.py`, `referee.run_portfolio`, `evaluate.evaluate_book`; işçi `scripts/full_systems.py`, özet `scripts/full_systems_report.py`.

## K1–K10 (karar kuralı: K1 veya K2 kalırsa NO_EDGE)
| # | test | S1 | S2 | eşik |
|---|---|---|---|---|
| K1 | brüt p (B=500, ortak ofset) / DSR (N=12) | 0,0259 (Bonf. 0,31) / 0,52 ✗ | 0,0599 (0,72) / 0,36 ✗ | p ≤ 0,0042 ve DSR ≥ 0,95 |
| K2 | Sharpe vs al-tut (−0,11) / NW alfa t | 0,63 > −0,11 ✓ / t=1,32 ✗ | 0,42 ✓ / t=0,99 ✗ | > ve t ≥ 2 |
| K3 | net Sharpe / net fee16+slip6 / net gecikme 1 | 0,63 ✗ / +38 164 ✓ / +39 020 ✓ | 0,42 ✗ / +26 980 / +27 907 | ≥ 1,0; > 0; > 0 |
| K4 | maks DD (sermayeye) / bootstrap DD %95 | %251 ✗ / %414 ✗ | %303 ✗ / %483 ✗ | ≤ %25; ≤ %30 |
| K5 | komşu net>0 / komşu medyan Sharpe | %92 (24) ✓ / 0,42 ✓ | %79 (24) ✓ / 0,32 ✓ | ≥ %70; ≥ seçilenin yarısı |
| K6 | pozitif pencere / başlangıç kaydırma | 3/7 ✗ / dördü de + | 4/7 ✗ / dördü de + | ≥ 5/7; hepsi > 0 |
| K7 | çapraz varlık (14 sembol) net fee16 | +4 925 ✓ | +22 269 ✓ | > 0 |
| K8 | full vs 4 ablasyon (Sharpe) | 0,63 > −0,24 / 0,47 / 0,43 / 0,11 ✓ | 0,42 > −0,42 / −0,41 / 0,35 / **0,42 (no_limits, eşit)** ✗ | full her birinden büyük |
| K9 | rejim net bull/bear/range | +37 951 / +1 740 / −5 322; bull payı %110 ✗ | +25 358 / +6 971 / −4 652; bull payı %92 ✗ | ≥2 rejim ≥0 ve tek rejim ≤ %80 |
| K10 | G3 | koşulmadı | koşulmadı | — |

## Ana tablo (fee 10 + slip 2, USDT; 12 deneme)
| deneme | net | brüt | fee+slip | funding | likidasyon | dolum | hakem stop / yönetici taklit | Sharpe | maks DD (sermaye / tepe) |
|---|---|---|---|---|---|---|---|---|---|
| S1 full | 39 398 | 46 802 | −1 478 | −5 923 | 0 | 953 | 194 / 199 | 0,63 | %251 / %50 |
| S1 no_stop | −7 689 | −4 939 | −656 | −1 986 | 7 | 418 | 0 | −0,24 | %131 |
| S1 fixed_size | 37 620 | 46 437 | −1 948 | −6 864 | 0 | 952 | 194 / 199 | 0,47 | %346 |
| S1 no_pyramid | 16 107 | 20 852 | −870 | −3 872 | 0 | 716 | 143 / 145 | 0,43 | %143 |
| S1 no_limits | 6 787 | 13 512 | −1 781 | −4 941 | 0 | 1 155 | 254 / 264 | 0,11 | %357 |
| S1 g2_equiv | 7 450 | 9 864 | −464 | −1 948 | 0 | 664 | 0 | 0,36 | %80 |
| S2 full | 27 641 | 35 827 | −788 | −7 393 | 0 | 473 | 122 / 122 | 0,42 | %303 / %85 |
| S2 no_stop | −11 834 ⚠ | −9 110 | −227 | −2 450 | 4 | 154 | 0 | −0,42 | %196 |
| S2 fixed_size | −11 036 ⚠ | −9 594 | −384 | −949 | 6 | 192 | 53 / 122 | −0,41 | %180 |
| S2 no_pyramid | 12 573 | 17 252 | −401 | −4 277 | 0 | 331 | 88 / 88 | 0,35 | %131 |
| S2 no_limits | 27 242 | 34 526 | −875 | −6 408 | 0 | 529 | 131 / 139 | 0,42 | %276 |
| S2 g2_equiv | 7 576 | 10 132 | −209 | −2 346 | 0 | 321 | 0 | 0,36 | %79 |

⚠ **Geçersiz koşu:** S2 `no_stop` ve `fixed_size`'te hesabın equity'si sıfırın altına düştü (hesap sıfırlandı); sonraki emirler marj yetersizliğiyle reddedildi (109 / 48) ve hakem kuralı gereği bu iki koşu deftere yazılmadı (ilk `primary` koşusunu çökerten buydu; düzeltme ve gerekçe protokolün sonunda). N=12'ye sayıldı, Sharpe'ları kısmi PnL serisinden; ikisi de "ablasyon daha kötü" yönünde (K8'de full'a göre çok düşük) ve sonuç değişmez.

Maliyet: fee 4→16 bps, slip 2→6 net'i yalnızca %2–5 oynatıyor (S1 40 138 → 38 164; S2 28 038 → 26 980): maliyet kayıp nedeni değil; funding (−5 923 / −7 393) ve brüt dalgalanma belirleyici. Pencere: S1 +27 848 (2023-H2), +16 625 (2024-H2) ile taşınıyor; 2025-H1 −8 205, son iki pencere ≤ 0 (son çeyrek −8 173). S2'de toplam kazancın tamamı SOL'dan (29 520 / 27 641); S1'de DOGE 16 086 + SOL 12 101 + LINK 7 373 (toplamın %90'ı).

## Sızıntı / hata taraması ("beklenmedik iyi" kuralı)
Net +39 398 (sermayenin 3,9 katı, ama Sharpe 0,63) beklenmedik büyük göründüğü için kontrol edildi: (1) kitap, `check_causal_book` ile tüm sembollerin verisi bozularak 16 kesimde denetlendi (geçti, her `evaluate_book` çağrısında); (2) yönetici taklit stopu ile hakemin gerçek stop sayısı uyuşuyor (S1 199 vs 194; S2 122 vs 122); (3) `g2_equiv` G2'nin S2 rakamlarını birebir yeniden üretti (portföy hakemi tek-sembol hakemle uyumlu; eski hakemden alınan sabit sayılarla da testli); (4) saatlik PnL yeniden kurulumu hakem net'iyle |fark| ≤ 4,25 USDT (funding anında kline barı eksik olan yerler; hakem esas); (5) geçerli 10 koşuda `n_rejected=0`, `funding_missed=0`. Büyüklüğün kaldıraçtan (brüt tavan 4× sermaye) geldiği varsayımı doğrulanmadı; ortalama brüt notional ayrıca ölçülmedi. Mark/kline ayrışması 28 sembolde kesimle ele alınıyor (G0). **Yine de bağımsız doğrulama yok:** sonuç görülmüş veride ön kayıtlı test (BACKTEST §8.5).
Rotasyon null'ında 500 çekilişin 87'sinde (S1) / 73'ünde (S2) hesap sıfırlanıp emirler reddedildi (n_rejected>0); yalnızca geçerli çekilişlerle p = 0,031 / 0,070 (karar değişmez; karar kuralı protokoldeki gibi 500 çekilişin tamamıyla).

## Motor v2 durumu ve bağımsız inceleme
Strateji stopu, portföy hakemi ve risk/boyut (N, piramit, birim sınırı) kodlu; `tests/`: 187 geçti, 1 atlandı (gerçek ağ), Modal'de doğrulandı. Ayrı bağlamda tek bağımsız inceleme 6 bulgu verdi (biri YÜKSEK: `hourly_pnl` bar içi dolumları atıyordu → portföy kill switch yanlış tetiklenirdi); hepsi giderildi ve regresyon testli (TASKS.md). **Hakem+yapıştırma satırı 467 (tavan 450 aşıldı, +17; G2 sonu 347; sayım yöntemi TASKS.md'de):** kullanıcı karar versin; artış çok sembollü adaptör + stop + brüt tavan + `evaluate_book`/`run_book` + `check_causal_book`.

## UNKNOWN / sınırlar
Slippage 2 bps (stres 6) ölçülmedi; funding settlement anı kuralı, sembol kuralları (tick/lot/min notional/mmr kademeleri), likidasyon ücreti UNKNOWN (G2 ile aynı). Cross-margin likidasyonu modellenmedi (LP kendi dolumunda yeniden hesaplanır). Sermaye sabit (equity'ye göre ölçekleme yok): bu nedenle K4'ün "sermayeye oran" DD'si büyük; tepe equity'ye oranlı DD (%50 / %85) bilgi olarak yazıldı, karar kuralını değiştirmez. "Son kırılım kazançlıysa atla" kuralı ve ek giriş yok. Hayatta kalma yanlılığı iyimser; tek rejim, ~4 yıl, 3 yıldan kısa OOS benzeri ⇒ MinTRL (SR>0, α=%5): S1 ≈ 7,0 yıl, S2 ≈ 15,9 yıl (elimizde ~4 yıl); PSR(0) = 0,90 / 0,80; K7 sembolleri (PEPE, SUI, APE vb.) bu evrenle korele, bağımsız kanıt değil.
Kümülatif deneme sayısı: önceki defterler 3 291 satır + bu testten 20 satır (çöken ilk koşudan 10, yeniden koşudan 10; geçersiz 2 deneme deftere girmedi) = **3 311 satır**; bu testin N'si 12 farklı yapılandırma.

## Öneri (yapılmadı; kapsam dışı)
(1) Equity'ye göre ölçekleyen (bileşik) Turtle boyutlamasını yeni bir ön kayıtla test etmek: K4'ü sermayeye oran DD ile geçmek mümkün görünmüyor, ama tepe-equity DD'si %50–85. (2) Kazancın tek sembole (SOL/DOGE) toplanması: evren genişliği ve sembol bağımsızlığı yeni hipotez konusu. (3) Kill switch'i risk kartına bağlamak. (4) K1'in N=12 eşiği ablasyonları da saydığı için sıkı; N'yi ablasyonsuz saymak S1'in p'sini (0,0259) eşiğin (0,025) hemen dışında bırakır, yine geçmez.
