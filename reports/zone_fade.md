# Zone Fade v1: sonuç NO_EDGE (K1'de kaldı; 165 işlem, örnek yeterli)

Ön kayıt: `reports/zone_fade_protocol.md` (olduğu gibi uygulandı; tanım, parametre, eşik, evren, N = 1 ve dönem değişmedi). Kod: `kepler/state.py` (state servisi v0), `kepler/experts/zone_fade.py`, işçi `scripts/zone_fade.py`, rapor `scripts/zone_fade_report.py`. Otomatik tablolar ve ham JSON: `reports/zone_fade_data/` (`tables.md`, `summary.json`); defter `ledger/zone_fade/ledger_zf1.jsonl` (1 hakem satırı).

**Karar:** K1 kalıyor (rotasyon null p = 0,371 > 0,05; DSR = PSR(0) = 0,706 < 0,95) → `robust.decision` = NO_EDGE. Birincil dönemde 165 işlem (≥ 60), "YETERSİZ ÖRNEK" değil. ADAY değil, G3 ve mühür açılmadı.

## Kurulum
- Birincil: 2022-07-01 → 2026-04-01, genişletilmiş-9, veri 2022-01'den, 4h karar, `next_open`. Spec: fee 10 + slip 2 bps RT, mmr 0,005, kaldıraç limiti 10, likidasyon ve çıkış maliyeti açık, sermaye 10 000, `gross_cap` 3x, `equity_scale` ve kill switch kapalı. İkinci pencere 2020-07-01 → 2022-01-01 (`pre2022`).
- Hakem, denetim, risk, mühür koduna dokunulmadı. Hedefte çıkış ve koşullu giriş **sinyalle taklit edildi** (taklit yetti; TASKS'a "protokol yetmedi" notu gerekmedi).
- **Ortam notu (dürüstlük):** Modal bu bulut konteynerinden erişilemedi (gRPC proxy'den geçmiyor). Koşu **Modal'de değil, bu konteynerde** yapıldı: ham veri Binance arşivinden yeniden indirildi, 9 EXT + 14 K7 sembolü için **zip sha256'ların hepsi `data_manifest/manifest*.json` ile birebir eşleşti (uyuşmayan 0)**; `universe` ve `usable.json` manifestten kuruldu (Parquet sha256'ı karşılaştırılmadı, yalnız zip). Aynı kod, Python 3.12 + Nautilus 2.0.0rc5 (`uv.lock`). Süreler: birincil ~100 sn, null B = 500 birkaç on dakika (4 çekirdek).
- Her aşama bir kez koşuldu; altyapı çökmesi olmadı. Gerçek koşudan önce 2 aylık **duman koşusu** (ayrı dizin, deftere girmedi, karar için kullanılmadı) boru hattını ve bir K7 yükleme hatasını (ENA dosyası yok; ilk-bar kuralı manifestten okunur oldu) yakaladı; sonuçlara bakılarak hiçbir şey ayarlanmadı.

## Başarı kartı (K1–K10)
| # | test | değer | eşik | geçti |
|---|---|---|---|---|
| K1 | rotasyon null p (brüt, B = 500) / DSR (N = 1) | p = 0,371 (null ort. 360 ± 1322; gerçek 684) / 0,706 | p ≤ 0,05; DSR ≥ 0,95 | **hayır** |
| K2 | Sharpe vs al-tut / NW alfa | 0,28 vs 0,08 / t = 0,60 | > ve t ≥ 2 | hayır (alfa t) |
| K3 | net Sharpe / fee 16 + slip 6 / gecikme 1 | 0,28 / +618 / +835 | ≥ 1,0; > 0; > 0 | hayır (Sharpe) |
| K4 | maks DD / bootstrap DD95 (blok 20) | %12,9 / %27,5 | ≤ %25; ≤ %30 | evet |
| K5 | komşu net > 0 / medyan Sharpe | 0/8 / −0,25 | ≥ %70; ≥ 0,14 | hayır |
| K6 | pozitif pencere / kaydırma | 4/8 / hepsi > 0 (712, 712, 712, 728) | ≥ %60; hepsi > 0 | hayır |
| K7 | çapraz varlık, 14 sembol, fee 16 | +150 | > 0 | evet |
| K8 | Sharpe birincil vs ablasyon | 0,28 vs no_impulse 0,04, no_trigger −0,21, no_poc 0,16, no_rr −0,42 | hepsinden büyük | evet |
| K9 | rejim net (bull / bear / range) | −58 / 174 / 596 | ≥ 2 rejim ≥ 0; tek ≤ %80 | hayır (tek rejim %80'den fazla: range 596 / toplam 712 = %84) |
| K10 | G3 | koşulmadı | — | — |

## Ana sonuç (fee 10 + slip 2)
Net +712 USDT (brüt 684, fee −94, slip −19, funding +140); yıllık getiri %1,9, oynaklık %6,8, Sharpe 0,28 (al-tut 0,08); PSR(0) 0,706, MinTRL 34,7 yıl. Dolum 330, **hakem stop 102 = yönetici stop taklidi 102**, likidasyon 0, red 0; yıllık devir 5,0x. Hakem–yönetici uzlaşması: saatlik PnL yeniden kurulumu farkı 1,6e-12. Kümülatif deneme sayısı (defter): önceki 4 117 + bu test 1 = **4 118**; Bonferroni (M = 4 118) p = 1,000; DSR(N = M) doğrulanmadı (defterde deneme Sharpe'ları yok).
Maliyet (net): fee 4/slip 2 → 768; 16/2 → 655; 10/6 → 674; 16/6 → 618; gecikme 1 → 835.

## Raporlanacaklar (karar dışı)
- **İşlem:** 165 (2022: 6, 2023: 49, 2024: 65, 2025: 35, 2026: 10). Kazanma %35,8; ort. R ≈ 0,08 (yaklaşık: pnl / planlanan işlem riski); ort. brüt 62 bps.
- **Çıkış:** stop 102 (%62; toplam −5 100, R = −1,00), hedef 26 (%16; +3 769, ort. R 2,90), zaman 37 (%22; +2 014, ort. R 1,09).
- **Yön:** long 57 işlem, net +1 434, kazanma %45,6; short 108 işlem, net −750, kazanma %30,6.
- **Bölge türü:** VA dışı 137 işlem, net −301; VA içi 28 işlem, net +985 (küçük örnek).
- **Sembol (net):** BTC 14, ETH −79, SOL 210, XRP 325, BNB 337, DOGE 245, ADA −451, LINK 62, AVAX 47.
- **Aday hunisi (doğum ≥ 2022-07-01):** 1 864 aday: R:R iptali 882, geçersiz (kapanış stop seviyesi ötesi) 571, limit 170, süre 69, stop 102, hedef 26, zaman 37, açık 7.
- **İkinci pencere (2020-07 → 2022-01; görülmüş veri, yalnız bilgi):** net −901 (brüt −1 066), 52 işlem, Sharpe −1,03 (al-tut 0,57), kazanma %23, hakem stop 39.
- Protokol lafzıyla (mutlak stop, bilgi) rotasyon null'u: p = 0,178 (B = 100); karara girmez.

## Tahmin ve gerçek
Tahmin "düşük işlem sayısı, YETERSİZ ÖRNEK olasılığı gerçek" idi: **yanlış**, 165 işlem. Kazanma %35–50 aralığına düştü (%35,8); ort. R pozitif ama ihmal edilebilir (0,08); K9'da bull payı yüksek değil ama kazanç range rejiminde toplandı. Ana soru cevabı: maliyet sonrası kazanç null'dan ayrışmıyor (p = 0,37; null ortalaması gerçekten büyük: 360 ± 1322), al-tuttan da (alfa t = 0,60).

## Yorum notları (protokol belirsizliklerinde seçilen okuma; kural eklenmedi)
1. Aynı 4h barda bölgeye giriş ve tetik (high ≥ alt, kapanış < alt) tetik sayılır (İZLEMEDE geçişi barda tetikten önce değerlendirilir). Sıra: süre > giriş > geçersizlik > tetik (süre bitiş barında tetik olsa iptal).
2. Impuls: "o max'tan ÖNCEKİ min low" = max barı hariç; eşit max'ta ilk bar (kısıtlayıcı). ATR ve bölge/stop, aday oluşumundaki son tamamlanmış 1d ATR14 ile sabitlenir.
3. İki yön de uygunsa fiyata yakın olan S; eşitlikte short. Limit nedeniyle (aynı barda 4 pozisyon / 3 aynı yön) giremeyen tetik adayı İPTAL eder.
4. Hacim profili: bar hacmi [low, high]'in kestiği kutulara eşit pay dağıtılır (kutu = ⌊(fiyat − min)/w⌋); POC eşitliğinde en alt kutu; VA genişlemesinde komşu eşitliğinde alt taraf; VAH/VAL = kutu kenarı.
5. **Isınma:** "≥ 240 günlük veri" yüklenen verinin başından sayılır; veri 2022-01-01'den yüklendiği için ilk işlem 2022-09-07 (aktiflik 2022-08-28). Birincil pencerenin ilk ~2 ayı ve K6'nın 0/1/2/3 ay kaydırmaları bu yüzden aynı sonucu verir (712, 712, 712, 728); Sharpe ve yıllık rakamlar bu ölü günleri içerir (muhafazakâr). İkinci pencerede aynı kural.
6. K1 null'unda **stop göreli taşındı** (stop / pozisyon açılış kapanışı oranı, kaymış pozisyonun açılış kapanışıyla yeniden fiyatlanır): mutlak fiyat seviyesi başka zamana taşınınca anlamsızlaşıp anında vurur ve null'u yapay daraltır; göreli yorum daha geniş/kötümser null verir. Protokol lafzı (mutlak) bilgi olarak raporlandı (yukarıda).
7. K6 pencereleri birincil dönemi örten 8 yarıyıl (2022-H2 … 2026-Q1; BACKTEST §8.1'deki 7'lik liste 2022-H2'yi içermez). K9'daki "tek rejim ≤ %80" sabiti ensemble raporundan miras (protokol metninde yok); K9 bu sabitle kalıyor, ama zaten K1 kaldığı için karar değişmez.

## Bağımsız inceleme (ayrı bağlamda alt ajan; kod ve testler)
BLOCKER yok. 1 MAJOR + 12 MINOR; nedensellik, hakem sözleşmesi uyumu, protokol formülleri, hacim profili ve K1–K9 rapor mantığı temiz bulundu. Giderilenler: long stop taklidi, iki yönlü `form`, süre/tetik sırası ve yeniden oluşum testleri eklendi (39 test), rapor betiğine B = 500 doğrulaması, BACKTEST §15 durumu ve değişiklik kaydı güncellendi. **Giderilmeyen (sonucu değiştirecekleri koşu sonrası olduğundan ve ön kayıt gereği yeniden koşu yok):**
- (MAJOR) İptal/kapanıştan sonra aynı bölge aynı kararda yeniden aday olabilir (protokol yalnız "açık aday/pozisyon yok" der); R:R iptallerinden sonra "geçene kadar yeniden dene" etkisi var (huni: 882 R:R iptali). Davranış testle belgelendi; engelli varyantı **koşulmadı**, sonuca etkisi UNKNOWN. Yeni hipotez olarak ön kayıt gerektirir.
- K3 gecikme/maliyet koşuları delay-0 kitabını kullanır (yönetici stop taraması giriş barına göre; delay 1'de ≤ 1 saat sapma). Etki küçük beklenir, doğrulanmadı.
- Çıkış barının sonraki açılışındaki gap stop'u hakemde stop, yöneticide hedef/zaman loglanabilir (hakem stop ile yönetici stop sayısı bu koşuda 102 = 102 çıktı).
- Defter `code_hash`'i `state.py`'yi kapsamıyor ve state `id`'si deftere yazılmıyor (`evaluate.py` hakem tarafı: kullanıcı onayı olmadan dokunulmadı).
- Hakemin tam eşitlikte (H = stop) tetikleyip tetiklemediği doğrulanmadı.

## Satır sayıları (MISSION kural 7)
Hakem + yapıştırma: değişmedi (473). `kepler/state.py` 178 ve `kepler/experts/zone_fade.py` 193 (boş/yorum hariç; servis ≲ 300 beklentisi içinde, araştırma kodu: tavansız). Testler: `tests/test_state.py` + `tests/test_zone_fade.py`: 39 geçti (yerelde, Python 3.12 + Nautilus; Nautilus'lu iki hakem uçtan uca test dahil). Betikler: `scripts/zone_fade.py` 212, `scripts/zone_fade_report.py` 154.

## UNKNOWN
Slippage, sembol kuralları (tick/lot/mmr kademeleri), hayatta kalma yanlılığı (bugünün majörleri), 1h barlardan yaklaşık hacim profili, stop dolum kayması; dev dönemi görülmüş veri (BACKTEST §8.5). Parametreler tek grafik örneğine ve literatür varsayılanlarına dayanıyordu; bu, trader'ın gerçek yönteminin değil mekanik yorumun testidir.

## Öneri (ayar turu yok)
Bu aile için parametre ayarına girilmez. K1 p = 0,37 ve stop çıkışlarının payı (%62) ayrışmanın zayıf olduğunu gösteriyor; yön asimetrisi (long +1 434, short −750) ve VA içi/dışı farkı **koşu sonrası gözlemdir**, bunlara bakıp seçim yapmak yeni ön kayıt ve yeni deneme sayısı gerektirir. Devam istenirse yalnızca (a) yeniden oluşumu engelleyen varyant (inceleme MAJOR bulgusu; hata düzeltmesine yakın) ayrı ön kayıtla, ya da (b) state servisinin başka bir uzmanla (ilk uzman sonucundan sonra "genişler ya da atılır", BACKTEST §15.7) kullanılıp kullanılmayacağı kullanıcı kararıdır. Önerilen: servis v0 testli ve küçük olduğu için tutulsun, yeni uzman yalnızca yeni bir ön kayıtla eklensin.
