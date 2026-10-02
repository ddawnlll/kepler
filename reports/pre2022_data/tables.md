# 2020–2021 replikasyon tabloları (otomatik; reports/pre2022_protocol.md)
Blok A: N = 4; DSR SR0 (yıllık) = 0.28; al-tut yıllık Sharpe = 0.50, net = 163846

## S1: NO_EDGE (ilk kalan: K1)
| # | değer | eşik | geçti |
|---|---|---|---|
| K1 | brüt p=0.0679 (B=500; null ort. 39510 ± 26159, gerçek 78660) / DSR=0.941 | p ≤ 0.0125; DSR ≥ 0,95 | False |
| K2 | Sharpe 1.43 vs al-tut 0.50; alfa 3.195/yıl, b=0.029, t=1.93 | > ve t ≥ 2 | False |
| K3 | Sharpe 1.43; fee16+slip6 63157; gecikme1 61997 | ≥ 1; > 0; > 0 | True |
| K4 | ölçekli boyut maks DD 25.0%; bootstrap DD95 47.2% | ≤ %25; ≤ %30 | False |
| K5 | komşu net>0 100.0% (n=24); medyan Sharpe 1.45 | ≥ %70; ≥ 0.71 | True |
| K6 | yarıyıllar [22257, 17897, 6742]; kaydırma [63508, 59488, 59271, 56009] | ≥ 2/3; hepsi > 0 | True |
| K7 | çapraz varlık net @fee16 25152 | > 0 | True |
| K8 | full 1.43 vs no_stop 1.38, fixed_size 1.38, no_pyramid 1.32, no_limits 1.46 | full hepsinden büyük | False |
| K9 | bull 47551 (n=393) / bear -166 (n=53) / range 341 (n=55) | ≥ 2 rejim ≥ 0; tek rejim ≤ %80 | False |

## S2: NO_EDGE (ilk kalan: K1)
| # | değer | eşik | geçti |
|---|---|---|---|
| K1 | brüt p=0.0958 (B=500; null ort. 86554 ± 271318, gerçek 82199) / DSR=0.830 | p ≤ 0.0125; DSR ≥ 0,95 | False |
| K2 | Sharpe 1.00 vs al-tut 0.50; alfa 2.693/yıl, b=0.073, t=1.21 | > ve t ≥ 2 | False |
| K3 | Sharpe 1.00; fee16+slip6 61278; gecikme1 62346 | ≥ 1; > 0; > 0 | False |
| K4 | ölçekli boyut maks DD 36.4%; bootstrap DD95 73.8% | ≤ %25; ≤ %30 | False |
| K5 | komşu net>0 100.0% (n=24); medyan Sharpe 0.96 | ≥ %70; ≥ 0.50 | True |
| K6 | yarıyıllar [16555, 13938, 22482]; kaydırma [61386, 61474, 61005, 61461] | ≥ 2/3; hepsi > 0 | True |
| K7 | çapraz varlık net @fee16 -192 | > 0 | False |
| K8 | full 1.00 vs no_stop 0.79, fixed_size 1.03, no_pyramid 0.76, no_limits 0.95 | full hepsinden büyük | False |
| K9 | bull 40546 (n=393) / bear 1305 (n=53) / range 19419 (n=55) | ≥ 2 rejim ≥ 0; tek rejim ≤ %80 | True |

## S1c: NO_EDGE (ilk kalan: K1)
| # | değer | eşik | geçti |
|---|---|---|---|
| K1 | brüt p=0.1118 (B=500; null ort. 37846 ± 23657, gerçek 61590) / DSR=0.894 | p ≤ 0.0125; DSR ≥ 0,95 | False |
| K2 | Sharpe 1.20 vs al-tut 0.50; alfa 2.300/yıl, b=0.035, t=1.61 | > ve t ≥ 2 | False |
| K3 | Sharpe 1.20; fee16+slip6 47722; gecikme1 47632 | ≥ 1; > 0; > 0 | True |
| K4 | ölçekli boyut maks DD 23.8%; bootstrap DD95 44.9% | ≤ %25; ≤ %30 | False |
| K5 | komşu net>0 100.0% (n=24); medyan Sharpe 1.27 | ≥ %70; ≥ 0.60 | True |
| K6 | yarıyıllar [11567, 6301, 20761]; kaydırma [46275, 46809, 47986, 45990] | ≥ 2/3; hepsi > 0 | True |
| K7 | çapraz varlık net @fee16 -330 | > 0 | False |
| K8 | full 1.20 vs no_stop 0.81, fixed_size 0.78, no_pyramid 0.97, no_limits 1.09 | full hepsinden büyük | True |
| K9 | bull 40142 (n=393) / bear -430 (n=53) / range 2681 (n=55) | ≥ 2 rejim ≥ 0; tek rejim ≤ %80 | False |

## S2c: NO_EDGE (ilk kalan: K1)
| # | değer | eşik | geçti |
|---|---|---|---|
| K1 | brüt p=0.2176 (B=500; null ort. 95735 ± 294578, gerçek 50365) / DSR=0.759 | p ≤ 0.0125; DSR ≥ 0,95 | False |
| K2 | Sharpe 0.80 vs al-tut 0.50; alfa 1.412/yıl, b=0.055, t=0.87 | > ve t ≥ 2 | False |
| K3 | Sharpe 0.80; fee16+slip6 34843; gecikme1 36712 | ≥ 1; > 0; > 0 | False |
| K4 | ölçekli boyut maks DD 39.1%; bootstrap DD95 74.5% | ≤ %25; ≤ %30 | False |
| K5 | komşu net>0 100.0% (n=24); medyan Sharpe 0.80 | ≥ %70; ≥ 0.40 | True |
| K6 | yarıyıllar [16653, 14765, 1609]; kaydırma [34144, 35004, 35004, 35004] | ≥ 2/3; hepsi > 0 | True |
| K7 | çapraz varlık net @fee16 -1896 | > 0 | False |
| K8 | full 0.80 vs no_stop 0.30, fixed_size 0.87, no_pyramid 0.50, no_limits 0.61 | full hepsinden büyük | False |
| K9 | bull 23933 (n=393) / bear 460 (n=53) / range 10432 (n=55) | ≥ 2 rejim ≥ 0; tek rejim ≤ %80 | True |

## Blok A ana tablo (fee 10 + slip 2; USDT; sermaye 10 000)
| sistem | net | brüt | funding | funding/brüt | dolum | stop | Sharpe | sembol neti |
|---|---|---|---|---|---|---|---|---|
| S1 | 63508 | 78660 | -14732 | 18.7% | 309 | 48 | 1.43 | BTC 38119, ETH 2737, SOL 5680, XRP 4141, BNB 403, DOGE 966, ADA 6511, LINK 64, AVAX 4886 |
| S2 | 61461 | 82199 | -20518 | 25.0% | 119 | 31 | 1.00 | BTC 19033, ETH 19832, SOL -211, XRP -593, BNB -880, DOGE -905, ADA 161, LINK -1219, AVAX 26243 |
| S1c | 47986 | 61590 | -13288 | 21.6% | 231 | 43 | 1.20 | BTC 37151, ETH 239, SOL 4314, XRP 5651, BNB 13, DOGE -678, ADA -342, LINK -2120, AVAX 3758 |
| S2c | 35004 | 50365 | -15168 | 30.1% | 110 | 30 | 0.80 | BTC 17945, ETH -1477, SOL 9185, XRP 263, BNB -746, DOGE -544, ADA -169, LINK -1153, AVAX 11698 |

## Blok B (6 yapılandırma, genişletilmiş-9, sembol başına bağımsız; kriter p ≤ 0,0083 ve net > 0 @fee 10 ve 16)
| yapılandırma | brüt | net fee4 | net fee10 | net fee16 | net fee10 slip6 | null ort. | p (brüt) | Bonf. ×6 | Sharpe | alfa t | kriter |
|---|---|---|---|---|---|---|---|---|---|---|---|
| don_80_20 | 98449 | 79421 | 79368 | 79314 | 79332 | 42644 | 0.0664 | 0.399 | 0.40 | -0.02 | False |
| ema_10_100 | 124450 | 97718 | 97633 | 97548 | 97576 | 49924 | 0.0664 | 0.399 | 0.38 | -0.07 | False |
| tsmom_14_1 | 28039 | 23511 | 23167 | 22832 | 22944 | 5152 | 0.0066 | 0.040 | 1.32 | 1.80 | True |
| xscarry_7 | 8385 | 8961 | 8861 | 8758 | 8792 | 5821 | 0.3322 | 1.000 | 0.94 | 1.10 | False |
| xsmom_7 | 4832 | 4120 | 3956 | 3786 | 3847 | -426 | 0.1694 | 1.000 | 0.53 | 0.70 | False |
| xsrev_3 | -11066 | -11956 | -12219 | -12475 | -12387 | 1419 | 1.0000 | 1.000 | -1.50 | -1.92 | False |

Geçersiz Blok A koşusu (n_rejected/funding_missed > 0): yok; Blok B defter dışı (ledger=False) satır: 1.