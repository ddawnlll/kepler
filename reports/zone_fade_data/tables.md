# Zone Fade v1 tabloları (otomatik): karar NO_EDGE (ilk kalan: K1; işlem 165, eşik 60)

| # | test | değer | eşik | geçti |
|---|---|---|---|---|
| K1 | rotasyon null p (brüt; B=500) / DSR (N=1, PSR(0)) | p=0.3713 (null ort. 360 ± 1322; gerçek 684) / DSR=0.706 | p ≤ 0,05; DSR ≥ 0,95 | False |
| K2 | Sharpe vs al-tut / NW alfa | 0.28 vs 0.08 / a=0.021/yıl, b=-0.013, t=0.60 | > ve t ≥ 2 | False |
| K3 | net Sharpe / fee16+slip6 / gecikme 1 | 0.28 / 618 / 835 | ≥ 1,0; > 0; > 0 | False |
| K4 | maks DD / bootstrap DD95 (blok 10/20/40) | 12.9% / 26.1% / 27.5% / 28.6% | ≤ %25; ≤ %30 | True |
| K5 | komşu net>0 / medyan Sharpe | 0.0% (n=8) / -0.25 | ≥ %70; ≥ 0.14 | False |
| K6 | pozitif pencere / kaydırma | 4/8 / [712, 712, 712, 728] | ≥ %60; hepsi > 0 | False |
| K7 | çapraz varlık (14 sembol) net @fee16 | 150 | > 0 | True |
| K8 | Sharpe birincil vs ablasyon | 0.28 vs no_impulse 0.04, no_trigger -0.21, no_poc 0.16, no_rr -0.42 | hepsinden büyük | True |
| K9 | rejim net (bull/bear/range) | -58 (n=837) / 174 (n=342) / 596 (n=142) | ≥ 2 rejim ≥ 0; tek ≤ %80 | False |
| K10 | G3 | koşulmadı (mühür açılmaz) | — | — |

## Ana sonuç (fee 10 + slip 2; sermaye 10 000)
net 712 (brüt 684, fee -94, slip -19, funding 140, çıkış -0); yıllık getiri 1.9%, yıllık oynaklık 6.8%; dolum 330, hakem stop 102, likidasyon 0, red 0; yıllık devir 5.0x sermaye; PSR(0) 0.706; MinTRL 34.7 yıl; Bonferroni (M=4118) p=1.000; DSR(N=M): doğrulanmadı (defterde deneme Sharpe'ları yok); recon 1.6e-12
Protokol lafzıyla (mutlak stop) rotasyon null'ı (bilgi): p=0.1782 (B=100)

## İşlemler (hakem; bilgi)
işlem 165; kazanma 35.8%; ort. R (yaklaşık, planlanan risk) 0.08; ort. brüt 62 bps; yönetici pozisyon 165, yönetici stop taklidi 102, hakem stop 102

aday hunisi (doğum ≥ 2022-07-01): AKTIF/ 3, IPTAL/expiry 69, IPTAL/invalid 571, IPTAL/limit 170, IPTAL/rr 882, IZLEMEDE/ 4, KAPALI/stop 102, KAPALI/target 26, KAPALI/time 37

| side | işlem | net | kazanma | ort. R |
|---|---|---|---|---|
| long | 57 | 1434 | 45.6% | 0.50 |
| short | 108 | -750 | 30.6% | -0.14 |

| exit | işlem | net | kazanma | ort. R |
|---|---|---|---|---|
| stop | 102 | -5100 | 0.0% | -1.00 |
| target | 26 | 3769 | 100.0% | 2.90 |
| time | 37 | 2014 | 89.2% | 1.09 |

| va | işlem | net | kazanma | ort. R |
|---|---|---|---|---|
| VA_disi | 137 | -301 | 32.8% | -0.04 |
| VA_ici | 28 | 985 | 50.0% | 0.70 |

| sym | işlem | net | kazanma | ort. R |
|---|---|---|---|---|
| ADAUSDT | 18 | -435 | 16.7% | -0.48 |
| AVAXUSDT | 15 | 46 | 33.3% | 0.06 |
| BNBUSDT | 12 | 363 | 58.3% | 0.60 |
| BTCUSDT | 15 | -5 | 33.3% | -0.01 |
| DOGEUSDT | 20 | 228 | 30.0% | 0.23 |
| ETHUSDT | 26 | -102 | 30.8% | -0.08 |
| LINKUSDT | 24 | 63 | 41.7% | 0.05 |
| SOLUSDT | 18 | 191 | 38.9% | 0.21 |
| XRPUSDT | 17 | 336 | 47.1% | 0.40 |

## Alt pencere: 2020-07 → 2022-01 (bilgi, görülmüş veri)
net -901 (brüt -1066); işlem 52; Sharpe -1.03 (al-tut 0.57, net 162624); maks DD 11.4%; hakem stop 39

## Maliyet (net)
| fee/slip/gecikme | net |
|---|---|
| 4_2_0 | 768 |
| 16_2_0 | 655 |
| 10_6_0 | 674 |
| 16_6_0 | 618 |
| 10_2_1 | 835 |

## Ablasyon ve komşular
| koşu | net | Sharpe | işlem |
|---|---|---|---|
| no_impulse | 108 | 0.04 | 156 |
| no_trigger | -1392 | -0.21 | 528 |
| no_poc | 419 | 0.16 | 310 |
| no_rr | -1107 | -0.42 | 511 |
| nb 0.75_3.0 | -667 | -0.23 | 196 |
| nb 0.75_4.0 | -803 | -0.27 | 204 |
| nb 0.75_5.0 | -571 | -0.21 | 180 |
| nb 1.0_3.0 | -329 | -0.13 | 161 |
| nb 1.0_5.0 | -776 | -0.35 | 144 |
| nb 1.25_3.0 | -816 | -0.41 | 127 |
| nb 1.25_4.0 | -319 | -0.16 | 132 |
| nb 1.25_5.0 | -615 | -0.34 | 113 |

## Pencereler (net)
| pencere | net |
|---|---|
| 2022-07-01_2023-01-01 | 389 |
| 2023-01-01_2023-07-01 | 771 |
| 2023-07-01_2024-01-01 | -257 |
| 2024-01-01_2024-07-01 | -493 |
| 2024-07-01_2025-01-01 | 84 |
| 2025-01-01_2025-07-01 | 766 |
| 2025-07-01_2026-01-01 | -187 |
| 2026-01-01_2026-04-01 | -411 |
| 2022-07-01_2026-04-01 | 712 |
| 2022-08-01_2026-04-01 | 712 |
| 2022-09-01_2026-04-01 | 712 |
| 2022-10-01_2026-04-01 | 728 |

## Sembol dağılımı (net)
| BTCUSDT | ETHUSDT | SOLUSDT | XRPUSDT | BNBUSDT | DOGEUSDT | ADAUSDT | LINKUSDT | AVAXUSDT |
|---|---|---|---|---|---|---|---|---|
| 14 | -79 | 210 | 325 | 337 | 245 | -451 | 62 | 47 |

## K7 sembolleri (fee 16 + slip 2; net)
| 1000PEPEUSDT | 1000SHIBUSDT | APEUSDT | APTUSDT | ARBUSDT | BCHUSDT | ETCUSDT | FILUSDT | GMTUSDT | LTCUSDT | MATICUSDT | NEARUSDT | OPUSDT | SUIUSDT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 295 | 443 | -193 | -26 | -101 | -90 | 48 | -132 | 140 | -39 | -195 | 173 | 138 | -310 |

Kümülatif deneme sayısı (ledger satırları): önceki 4117 + bu test 1 = 4118.