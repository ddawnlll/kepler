# Edge uzmanı volrev tabloları (otomatik): karar NO_EDGE (ilk kalan: K1); aile düzeltmesi (p ≤ 0.0056): kaldı; M1 range net 600; M2 EV1 korelasyonu -0.40; ters yön (bilgi): net 550, Sharpe 0.12

| # | test | değer | eşik | geçti |
|---|---|---|---|---|
| K1 | rotasyon null p (brüt; B=300) / DSR (N=3) | p=0.9136 (null ort. -226 ± 1261; gerçek -1839) / DSR=0.051 | p ≤ 0,05; DSR ≥ 0,95 | False |
| K2 | Sharpe vs al-tut / NW alfa | -0.54 vs 0.05 / a=-0.042/yıl, b=-0.000, t=-1.30 | > ve t ≥ 2 | False |
| K3 | net Sharpe / fee16+slip6 / gecikme 1 | -0.54 / -3323 / -2754 | ≥ 1,0; > 0; > 0 | False |
| K4 | maks DD / bootstrap DD95 (blok 10/20/40) | 32.3% / 62.4% / 64.4% / 63.1% | ≤ %25; ≤ %30 | False |
| K5 | komşu net>0 / medyan Sharpe | 0.0% (n=4) / -0.53 | ≥ %70; ≥ -0.27 | False |
| K6 | pozitif pencere / kaydırma | 3/12 / [-2507, -2591, -2638, -2792] | ≥ %60; hepsi > 0 | False |
| K7 | çapraz varlık (14 sembol) net @fee16 | -304 | > 0 | False |
| K8 | Sharpe birincil vs ablasyon | -0.54 vs no_risk -0.29, no_buffer -0.49 | hepsinden büyük | False |
| K9 | rejim net (bull/bear/range) | -2735 (n=1230) / -352 (n=616) / 600 (n=206) | ≥ 2 rejim ≥ 0; tek ≤ %80 | False |
| K10 | G3 | koşulmadı | — | — |

## Ana sonuç (fee 10 + slip 2; sermaye 10 000)
net -2507 (brüt -1839, fee -816, slip -163, funding 311, çıkış -0); yıllık getiri -4.2%, yıllık oynaklık 7.8%; dolum 3720, likidasyon 0, red 0; yıllık devir 27.2x sermaye; ort. brüt pozisyon 0.05x; |F| ort. 0.14, long payı 6.1%; PSR(0) 0.089; MinTRL None yıl; tepe DD 31.2%; kill switch tetik %25: 2024-11-23, %30: 2026-02-05; recon -0.21

## Alt dönemler (bilgi)
| dönem | net | Sharpe | al-tut Sharpe | alfa t | maks DD |
|---|---|---|---|---|---|
| 2020-04→2022-01 | -1294 | -0.85 | 0.53 | -1.05 | 19.5% |
| 2022-01→2026-04 | -1214 | -0.39 | -0.25 | -0.83 | 24.4% |

## Maliyet (net)
| fee/slip/gecikme | net |
|---|---|
| 16_6_0 | -3323 |
| 10_2_1 | -2754 |

## Ablasyon ve komşular
| koşu | net | Sharpe |
|---|---|---|
| no_risk | -5102 | -0.29 |
| no_buffer | -2210 | -0.49 |
| scale_0.8 | -2484 | -0.43 |
| scale_0.9 | -2522 | -0.49 |
| scale_1.1 | -2830 | -0.67 |
| scale_1.2 | -2204 | -0.58 |

## Pencereler (net)
| pencere | net |
|---|---|
| 2020-07-01_2021-01-01 | -533 |
| 2021-01-01_2021-07-01 | -817 |
| 2021-07-01_2022-01-01 | -228 |
| 2022-01-01_2022-07-01 | 549 |
| 2022-07-01_2023-01-01 | -408 |
| 2023-01-01_2023-07-01 | 268 |
| 2023-07-01_2024-01-01 | -228 |
| 2024-01-01_2024-07-01 | -26 |
| 2024-07-01_2025-01-01 | -1049 |
| 2025-01-01_2025-07-01 | 348 |
| 2025-07-01_2026-01-01 | -473 |
| 2026-01-01_2026-04-01 | -196 |
| 2020-04-01_2026-04-01 | -2507 |
| 2020-05-01_2026-04-01 | -2591 |
| 2020-06-01_2026-04-01 | -2638 |
| 2020-07-01_2026-04-01 | -2792 |

## Sembol dağılımı (net)
| BTCUSDT | ETHUSDT | SOLUSDT | XRPUSDT | BNBUSDT | DOGEUSDT | ADAUSDT | LINKUSDT | AVAXUSDT |
|---|---|---|---|---|---|---|---|---|
| -104 | -137 | -617 | -119 | -593 | -987 | -157 | 594 | -388 |

## K7 sembolleri (fee 16 + slip 2; net)
| 1000PEPEUSDT | 1000SHIBUSDT | APEUSDT | APTUSDT | ARBUSDT | BCHUSDT | ETCUSDT | FILUSDT | GMTUSDT | LTCUSDT | MATICUSDT | NEARUSDT | OPUSDT | SUIUSDT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -285 | -511 | -78 | -45 | 27 | 259 | 0 | -122 | -69 | -1 | 80 | 168 | 50 | 224 |

## Stres pencereleri
| pencere | net | net_pct | max_dd | max_dd_pct | worst_hour | worst_day | n_stop | n_liq | gross_start | net_start | stop_slip_bps_mean | stop_slip_bps_max | n_stop_slip | overshoot_bps_mean | overshoot_bps_max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021-05 | 353 | 0.0353 | 90.5 | 0.00905 | -75.8 | -0.157 | 0 | 0 | 304 | -258 | None | None | 0 | None | None |
| LUNA | 454 | 0.0454 | 329 | 0.0329 | -191 | -86.5 | 0 | 0 | 1.57e-11 | 5.55e-12 | None | None | 0 | None | None |
| FTX | -242 | -0.0242 | 697 | 0.0697 | -132 | -591 | 0 | 0 | 3.26e+03 | -3.26e+03 | None | None | 0 | None | None |