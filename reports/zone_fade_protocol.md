# Ön kayıt: Zone Fade v1 (arz/talep bölgesinden dönüş; hacim profili hedefli)

**Durum:** ÖN KAYIT. Kullanıcı tasarım kararı (2026-10-02), kod ve koşudan önce commit'lendi. Tanım, parametre, eşik, evren, N ve dönem sonuçtan sonra değişmez (MISSION kural 11). Uygulayan ajan bu belgeyi **olduğu gibi** uygular; belirsizlik varsa kısıtlayıcı/kötümser yorumu seçer ve not düşer, kural eklemez.

## Soru ve kaynak
Seviye/hacim tabanlı mean-reversion ailesi (supply & demand zone fade, volume profile hedefi; BACKTEST §15 market state servisinin ilk uzmanı), maliyet sonrası şanstan ve al-tuttan ayrışıyor mu? Fikir bir trader örneğinden (BTC 3d grafik: sert yükseliş sonrası üstte arz bölgesi, hedef hacim yığını/POC) geliyor. **Parametreler o grafiğin şekline ve literatür varsayılanlarına göre, veri sonuçlarına bakılmadan seçildi.** Bu, trader'ın gerçek yönteminin değil, bu mekanik yorumun testidir.

## Veri, evren, dönem
- Veri: `tape.load` (klines 1h, mark, funding). Mühür (≥ 2026-04-01) dokunulmaz. Evren: genişletilmiş-9 (BTC ETH SOL XRP BNB DOGE ADA LINK AVAX); sembol, ≥ 240 günlük (ısınma) verisi olunca aktif.
- **Birincil dönem:** 2022-07-01 → 2026-04-01 (ısınma 2022-01'den). **İkinci pencere (görülmüş veri, temiz değil, yalnızca bilgi):** 2020-07-01 → 2022-01-01 (`/data/pre2022`, ısınma 2020-01'den).
- Karar saati: her **4h kapanışı** (00, 04, 08, 12, 16, 20 UTC). Dolum: sonraki bar açılışı (`next_open`). Diğer saatler NaN (tut). Tüm girdiler kapanış ≤ karar anı (nedensel).

## Market state (BACKTEST §15, v0; yalnızca bunlar)
- **1d:** ATR14 (Wilder), `ATR`. **3d (çıpa §15.3):** swing noktaları: fractal k = 2 (bir bar, her iki yanındaki 2'şer barın high'ından yüksek = swing tepe; low'dan düşük = swing dip); **sağdaki 2 bar kapanınca onaylanır** (gecikme kasıtlı, nedensel).
- **Hacim profili (180 gün, 1h barlardan):** pencere [t−180g, t]; fiyat ekseni 100 eşit kutu (pencere min low → max high); her 1h barın hacmi, [low, high] aralığının kestiği kutulara eşit oransal dağıtılır. **POC** = en yüksek hacimli kutunun merkezi. Value area: POC'tan başlayıp her adımda hacmi büyük komşu tarafı ekleyerek toplam hacmin %70'ini kapsayan en küçük bitişik aralık; VAH/VAL = sınırları.
- **Impuls (yukarı):** son 20 gün (1d barlar): max high − (o max'tan ÖNCEKİ min low) ≥ 4 × ATR. **Impuls (aşağı):** simetrik (o min low'dan önceki max high − min low ≥ 4 × ATR).

## Uzman: short (arz bölgesi)
1. **Aday oluşumu (4h kapanışta):** yukarı impuls var; **S** = fiyatın üstündeki, S ≤ close + 6 × ATR olan en yakın onaylı 3d swing tepe; **bölge = [S − 1,0 × ATR, S]**; o sembolde açık aday/pozisyon yok. Durum AKTİF; süre 30 gün.
2. **İZLEMEDE:** 4h bar high ≥ bölge alt sınırı. İptal: 4h kapanış > bölge üstü + 0,5 × ATR (geçersiz) ya da süre dolması.
3. **Tetik (İZLEMEDE iken, 4h kapanışta):** o barın high'ı bölgeye girmiş (≥ alt sınır) **ve** kapanış < bölge alt sınırı (bölgeden reddedildi). Giriş: sonraki açılışta short.
4. **Stop:** bölge üstü + 0,5 × ATR (hakem stop seviyesi, bar içi). **Hedef:** tetik anındaki POC (sabit). **R:R filtresi:** (tetik kapanışı − POC) / (stop − tetik kapanışı) ≥ 2; değilse aday İPTAL.
5. **Çıkış:** (a) stop (hakem); (b) hedef: bir 4h barın low'u ≤ hedef ise o barın kapanışında hedef = 0 (sonraki açılışta çık; kötümser taklit); (c) zaman: pozisyon 40 günü geçerse kapat. Aynı barda hedef ve stop: stop kabul edilir (kötümser).
## Uzman: long (talep bölgesi) — birebir ayna
Aşağı impuls; fiyatın altındaki, S ≥ close − 6 × ATR olan en yakın onaylı swing dip; bölge = [S, S + 1,0 × ATR]; İZLEMEDE: 4h low ≤ bölge üst sınırı; tetik: low bölgeye girmiş ve kapanış > bölge üst sınırı; stop = bölge altı − 0,5 × ATR; hedef = POC; R:R ≥ 2; aynı çıkış kuralları.

## Boyut ve risk (mevcut yönetici/portföy hakemi, kill switch yok, `equity_scale` kapalı)
Sermaye 10 000 (ölçek). İşlem başına risk = %0,5 × sermaye; notional = risk / (|giriş − stop| / giriş), sembol başına ≤ 1,0 × sermaye. Eşzamanlı en çok 4 pozisyon, aynı yönde en çok 3; aynı anda fazla tetik olursa alfabetik sıra. `gross_cap` = 3 × sermaye. Spec: fee 10 + slip 2 bps rt, mmr 0,005, kaldıraç limiti 10, likidasyon açık, çıkış maliyeti açık.

## Denemeler (N)
**Birincil yapılandırma: 1** (yukarıdaki tanım; long+short birlikte). **N = 1.** Karar p ≤ 0,05 / 1 ve DSR (N = 1, yani PSR(0)) ≥ 0,95 ile; ayrıca katı raporlama: proje kümülatif deneme sayısıyla (`ledger/` toplamı) DSR ve Bonferroni.
Kontroller (deftersiz, N'ye girmez): K5 komşuları: bölge genişliği ∈ {0,75; 1,0; 1,25} × impuls eşiği ∈ {3; 4; 5} ATR (merkez hariç 8). K8 ablasyonları: `no_impulse` (impuls şartı kapalı), `no_trigger` (tetik yok: bölgeye ilk girişte giriş), `no_poc` (hedef = 2R sabit), `no_rr` (R:R filtresi kapalı).

## Kart ve karar (BACKTEST §11, eşikler aynen)
K1–K9 birincil dönemde; K7: kullanılmamış 14 sembol (`scripts/search.py` replikasyon kuralı), dönem 2023-07-01 → 2026-04-01; K9 rejim: `robust.regime`; K4 planlanan boyutla (yukarıdaki risk). Null (K1): book çıktısının (target + stop) **ortak ofset dairesel kaydırması**, B = 500 (`default_rng([0, i])`). Al-tut (K2): eşit notional ext-9, aynı Spec/pencere.
**Örnek yeterliliği (bu teste özel, önceden):** birincil dönemde toplam işlem sayısı < 60 ise karar **"YETERSİZ ÖRNEK"** (NO_EDGE sayılmaz; kanıt yok) ve K1 raporlanır ama karar verilmez.
**Karar:** `robust.decision` (K1 veya K2 kalırsa NO_EDGE; K3–K9'dan biri kalırsa ZAYIF; hepsi ADAY). ADAY olsa bile G3 açılmaz; kullanıcıya bildirilir.

## Raporlanacaklar (karar dışı)
İşlem sayısı, kazanma oranı, ortalama R, long/short ayrımı, sembol dağılımı, bölge türüne göre (VAH üstü / içi) sonuç, 2020–21 ikinci pencere sonucu, hedefe ulaşan / stop / zaman çıkışı oranı, hakem stop sayısı ve yönetici taklit sayısı.

## Tahmin (veriye bakmadan)
Düşük işlem sayısı (sembol başına yılda birkaç), bu yüzden K1'in gücü sınırlı ve "YETERSİZ ÖRNEK" olasılığı gerçek. Kazanma oranı %35–50, R:R ≥ 2 filtresi nedeniyle ortalama R pozitif olabilir ama funding ve devir küçük. K2 (al-tut) boğa dönemlerinde zor; K9'da bull payı yüksek kalması beklenmiyor (kurulum yatay/dönüş piyasasında da çalışır). Bunlar tahmin; yanlış çıkabilir.

## Sınırlar / UNKNOWN
Parametreler tek bir grafik örneğine ve literatür varsayılanlarına dayanıyor; trader'ın gerçek kuralı bilinmiyor. Hacim profili 1h barlardan yaklaşık (tick verisi yok). Slippage, sembol kuralları, mmr kademeleri UNKNOWN. Hayatta kalma yanlılığı (evren bugünün majörleri). Dev dönemi görülmüş veri (BACKTEST §8.5); gerçek zaman-dışı kanıt yalnızca mühür (yalnızca ADAY'da) ve canlı veridir.
