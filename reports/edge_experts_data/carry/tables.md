# Edge uzmanı carry tabloları (otomatik): karar NO_EDGE (ilk kalan: K1); aile düzeltmesi (p ≤ 0.0056): kaldı; M1 range net 648; M2 EV1 korelasyonu -0.26; ters yön (bilgi): net 1079, Sharpe 0.16

| # | test | değer | eşik | geçti |
|---|---|---|---|---|
| K1 | rotasyon null p (brüt; B=300) / DSR (N=3) | p=0.9601 (null ort. 3454 ± 3498; gerçek -2683) / DSR=0.273 | p ≤ 0,05; DSR ≥ 0,95 | False |
| K2 | Sharpe vs al-tut / NW alfa | -0.21 vs 0.05 / a=-0.024/yıl, b=0.000, t=-0.52 | > ve t ≥ 2 | False |
| K3 | net Sharpe / fee16+slip6 / gecikme 1 | -0.21 / -1561 / -1168 | ≥ 1,0; > 0; > 0 | False |
| K4 | maks DD / bootstrap DD95 (blok 10/20/40) | 40.1% / 75.2% / 75.7% / 76.5% | ≤ %25; ≤ %30 | False |
| K5 | komşu net>0 / medyan Sharpe | 0.0% (n=4) / -0.22 | ≥ %70; ≥ -0.11 | False |
| K6 | pozitif pencere / kaydırma | 5/12 / [-1419, -1508, -1555, -1631] | ≥ %60; hepsi > 0 | False |
| K7 | çapraz varlık (14 sembol) net @fee16 | -1327 | > 0 | False |
| K8 | Sharpe birincil vs ablasyon | -0.21 vs no_risk -0.23, no_buffer -0.14 | hepsinden büyük | False |
| K9 | rejim net (bull/bear/range) | -1881 (n=1230) / -174 (n=616) / 648 (n=206) | ≥ 2 rejim ≥ 0; tek ≤ %80 | False |
| K10 | G3 | koşulmadı | — | — |

## Ana sonuç (fee 10 + slip 2; sermaye 10 000)
net -1419 (brüt -2683, fee -140, slip -28, funding 1434, çıkış -2); yıllık getiri -2.4%, yıllık oynaklık 11.3%; dolum 2194, likidasyon 0, red 0; yıllık devir 4.7x sermaye; ort. brüt pozisyon 0.15x; |F| ort. 0.39, long payı 64.9%; PSR(0) 0.303; MinTRL None yıl; tepe DD 36.2%; kill switch tetik %25: 2021-04-06, %30: 2021-04-13; recon 0.13

## Alt dönemler (bilgi)
| dönem | net | Sharpe | al-tut Sharpe | alfa t | maks DD |
|---|---|---|---|---|---|
| 2020-04→2022-01 | -2422 | -1.01 | 0.53 | -1.16 | 37.9% |
| 2022-01→2026-04 | 1003 | 0.23 | -0.25 | 0.77 | 14.5% |

## Maliyet (net)
| fee/slip/gecikme | net |
|---|---|
| 16_6_0 | -1561 |
| 10_2_1 | -1168 |

## Ablasyon ve komşular
| koşu | net | Sharpe |
|---|---|---|
| no_risk | -8811 | -0.23 |
| no_buffer | -954 | -0.14 |
| scale_0.8 | -1064 | -0.16 |
| scale_0.9 | -751 | -0.11 |
| scale_1.1 | -2238 | -0.34 |
| scale_1.2 | -1929 | -0.29 |

## Pencereler (net)
| pencere | net |
|---|---|
| 2020-07-01_2021-01-01 | -184 |
| 2021-01-01_2021-07-01 | -2297 |
| 2021-07-01_2022-01-01 | -163 |
| 2022-01-01_2022-07-01 | -393 |
| 2022-07-01_2023-01-01 | -47 |
| 2023-01-01_2023-07-01 | 1003 |
| 2023-07-01_2024-01-01 | 835 |
| 2024-01-01_2024-07-01 | -218 |
| 2024-07-01_2025-01-01 | 173 |
| 2025-01-01_2025-07-01 | 3 |
| 2025-07-01_2026-01-01 | 219 |
| 2026-01-01_2026-04-01 | -587 |
| 2020-04-01_2026-04-01 | -1419 |
| 2020-05-01_2026-04-01 | -1508 |
| 2020-06-01_2026-04-01 | -1555 |
| 2020-07-01_2026-04-01 | -1631 |

## Sembol dağılımı (net)
| BTCUSDT | ETHUSDT | SOLUSDT | XRPUSDT | BNBUSDT | DOGEUSDT | ADAUSDT | LINKUSDT | AVAXUSDT |
|---|---|---|---|---|---|---|---|---|
| 380 | -609 | -270 | -537 | 116 | -841 | 141 | 788 | -589 |

## K7 sembolleri (fee 16 + slip 2; net)
| 1000PEPEUSDT | 1000SHIBUSDT | APEUSDT | APTUSDT | ARBUSDT | BCHUSDT | ETCUSDT | FILUSDT | GMTUSDT | LTCUSDT | MATICUSDT | NEARUSDT | OPUSDT | SUIUSDT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -237 | -345 | -60 | -44 | -2 | -57 | -74 | -25 | -26 | -172 | 96 | -212 | -128 | -42 |

## Stres pencereleri
| pencere | net | net_pct | max_dd | max_dd_pct | worst_hour | worst_day | n_stop | n_liq | gross_start | net_start | stop_slip_bps_mean | stop_slip_bps_max | n_stop_slip | overshoot_bps_mean | overshoot_bps_max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021-05 | 188 | 0.0188 | 111 | 0.0111 | -44.9 | -30.8 | 0 | 0 | 854 | -854 | None | None | 0 | None | None |
| LUNA | -270 | -0.027 | 490 | 0.049 | -80.8 | -154 | 0 | 0 | 1.44e+03 | 1.44e+03 | None | None | 0 | None | None |
| FTX | -507 | -0.0507 | 602 | 0.0602 | -127 | -264 | 0 | 0 | 2.5e+03 | 2.5e+03 | None | None | 0 | None | None |