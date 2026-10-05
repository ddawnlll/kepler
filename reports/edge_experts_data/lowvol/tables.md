# Edge uzmanı lowvol tabloları (otomatik): karar NO_EDGE (ilk kalan: K1); aile düzeltmesi (p ≤ 0.0056): kaldı; M1 range net 98; M2 EV1 korelasyonu -0.10; ters yön (bilgi): net 1, Sharpe 0.00

| # | test | değer | eşik | geçti |
|---|---|---|---|---|
| K1 | rotasyon null p (brüt; B=300) / DSR (N=3) | p=0.7110 (null ort. 714 ± 970; gerçek 124) / DSR=0.195 | p ≤ 0,05; DSR ≥ 0,95 | False |
| K2 | Sharpe vs al-tut / NW alfa | -0.08 vs 0.05 / a=-0.004/yıl, b=0.000, t=-0.19 | > ve t ≥ 2 | False |
| K3 | net Sharpe / fee16+slip6 / gecikme 1 | -0.08 / -329 / -413 | ≥ 1,0; > 0; > 0 | False |
| K4 | maks DD / bootstrap DD95 (blok 10/20/40) | 14.4% / 30.0% / 30.5% / 31.1% | ≤ %25; ≤ %30 | False |
| K5 | komşu net>0 / medyan Sharpe | 50.0% (n=4) / -0.02 | ≥ %70; ≥ -0.04 | False |
| K6 | pozitif pencere / kaydırma | 7/12 / [-232, -263, -87, 46] | ≥ %60; hepsi > 0 | False |
| K7 | çapraz varlık (14 sembol) net @fee16 | 344 | > 0 | True |
| K8 | Sharpe birincil vs ablasyon | -0.08 vs no_risk -0.50, no_buffer 0.11 | hepsinden büyük | False |
| K9 | rejim net (bull/bear/range) | -193 (n=1230) / 289 (n=616) / 98 (n=206) | ≥ 2 rejim ≥ 0; tek ≤ %80 | False |
| K10 | G3 | koşulmadı | — | — |

## Ana sonuç (fee 10 + slip 2; sermaye 10 000)
net -232 (brüt 124, fee -95, slip -19, funding -241, çıkış -1); yıllık getiri -0.4%, yıllık oynaklık 4.7%; dolum 1629, likidasyon 0, red 0; yıllık devir 3.2x sermaye; ort. brüt pozisyon 0.17x; |F| ort. 0.50, long payı 41.0%; PSR(0) 0.419; MinTRL None yıl; tepe DD 13.5%; kill switch tetik %25: None, %30: None; recon -0.26

## Alt dönemler (bilgi)
| dönem | net | Sharpe | al-tut Sharpe | alfa t | maks DD |
|---|---|---|---|---|---|
| 2020-04→2022-01 | -420 | -0.38 | 0.53 | -0.47 | 11.0% |
| 2022-01→2026-04 | 187 | 0.12 | -0.25 | 0.24 | 10.8% |

## Maliyet (net)
| fee/slip/gecikme | net |
|---|---|
| 16_6_0 | -329 |
| 10_2_1 | -413 |

## Ablasyon ve komşular
| koşu | net | Sharpe |
|---|---|---|
| no_risk | -6776 | -0.50 |
| no_buffer | 263 | 0.11 |
| scale_0.8 | -869 | -0.30 |
| scale_0.9 | -169 | -0.06 |
| scale_1.1 | 50 | 0.02 |
| scale_1.2 | 167 | 0.06 |

## Pencereler (net)
| pencere | net |
|---|---|
| 2020-07-01_2021-01-01 | 870 |
| 2021-01-01_2021-07-01 | -610 |
| 2021-07-01_2022-01-01 | -419 |
| 2022-01-01_2022-07-01 | 58 |
| 2022-07-01_2023-01-01 | 202 |
| 2023-01-01_2023-07-01 | 380 |
| 2023-07-01_2024-01-01 | -756 |
| 2024-01-01_2024-07-01 | 279 |
| 2024-07-01_2025-01-01 | -390 |
| 2025-01-01_2025-07-01 | 34 |
| 2025-07-01_2026-01-01 | 362 |
| 2026-01-01_2026-04-01 | -151 |
| 2020-04-01_2026-04-01 | -232 |
| 2020-05-01_2026-04-01 | -263 |
| 2020-06-01_2026-04-01 | -87 |
| 2020-07-01_2026-04-01 | 46 |

## Sembol dağılımı (net)
| BTCUSDT | ETHUSDT | SOLUSDT | XRPUSDT | BNBUSDT | DOGEUSDT | ADAUSDT | LINKUSDT | AVAXUSDT |
|---|---|---|---|---|---|---|---|---|
| 892 | 8 | -1553 | 786 | 1076 | -74 | -322 | -659 | -386 |

## K7 sembolleri (fee 16 + slip 2; net)
| 1000PEPEUSDT | 1000SHIBUSDT | APEUSDT | APTUSDT | ARBUSDT | BCHUSDT | ETCUSDT | FILUSDT | GMTUSDT | LTCUSDT | MATICUSDT | NEARUSDT | OPUSDT | SUIUSDT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -360 | 530 | -51 | -73 | -216 | 416 | 159 | 2 | 220 | 158 | -22 | -140 | 77 | -356 |

## Stres pencereleri
| pencere | net | net_pct | max_dd | max_dd_pct | worst_hour | worst_day | n_stop | n_liq | gross_start | net_start | stop_slip_bps_mean | stop_slip_bps_max | n_stop_slip | overshoot_bps_mean | overshoot_bps_max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021-05 | -133 | -0.0133 | 163 | 0.0163 | -26.3 | -66.4 | 0 | 0 | 1.41e+03 | 480 | None | None | 0 | None | None |
| LUNA | -11.3 | -0.00113 | 94.4 | 0.00944 | -16.9 | -21.6 | 0 | 0 | 1.57e+03 | 369 | None | None | 0 | None | None |
| FTX | -70.5 | -0.00705 | 162 | 0.0162 | -34.1 | -53.3 | 0 | 0 | 2.1e+03 | 478 | None | None | 0 | None | None |