# Edge uzmanı nearhigh tabloları (otomatik): karar ZAYIF (ilk kalan: K9); aile düzeltmesi (p ≤ 0.0056): geçti; M1 range net -358; M2 EV1 korelasyonu 0.24; ters yön (bilgi): net -4039, Sharpe -1.68

| # | test | değer | eşik | geçti |
|---|---|---|---|---|
| K1 | rotasyon null p (brüt; B=300) / DSR (N=3) | p=0.0033 (null ort. -47 ± 924; gerçek 3737) / DSR=0.998 | p ≤ 0,05; DSR ≥ 0,95 | True |
| K2 | Sharpe vs al-tut / NW alfa | 1.45 vs 0.05 / a=0.058/yıl, b=0.000, t=3.53 | > ve t ≥ 2 | True |
| K3 | net Sharpe / fee16+slip6 / gecikme 1 | 1.45 / 3252 / 3275 | ≥ 1,0; > 0; > 0 | True |
| K4 | maks DD / bootstrap DD95 (blok 10/20/40) | 4.9% / 9.0% / 8.7% / 8.0% | ≤ %25; ≤ %30 | True |
| K5 | komşu net>0 / medyan Sharpe | 100.0% (n=4) / 1.37 | ≥ %70; ≥ 0.73 | True |
| K6 | pozitif pencere / kaydırma | 9/12 / [3483, 3431, 3295, 3106] | ≥ %60; hepsi > 0 | True |
| K7 | çapraz varlık (14 sembol) net @fee16 | 453 | > 0 | True |
| K8 | Sharpe birincil vs ablasyon | 1.45 vs no_risk 0.99, no_buffer 1.44 | hepsinden büyük | True |
| K9 | rejim net (bull/bear/range) | 3194 (n=1230) / 178 (n=616) / -358 (n=206) | ≥ 2 rejim ≥ 0; tek ≤ %80 | False |
| K10 | G3 | koşulmadı | — | — |

## Ana sonuç (fee 10 + slip 2; sermaye 10 000)
net 3483 (brüt 3737, fee -231, slip -46, funding 25, çıkış -1); yıllık getiri 5.8%, yıllık oynaklık 4.0%; dolum 3929, likidasyon 0, red 0; yıllık devir 7.7x sermaye; ort. brüt pozisyon 0.17x; |F| ort. 0.50, long payı 41.1%; PSR(0) 1.000; MinTRL 1.4 yıl; tepe DD 4.2%; kill switch tetik %25: None, %30: None; recon -0.25

## Alt dönemler (bilgi)
| dönem | net | Sharpe | al-tut Sharpe | alfa t | maks DD |
|---|---|---|---|---|---|
| 2020-04→2022-01 | 1866 | 2.03 | 0.53 | 2.77 | 4.8% |
| 2022-01→2026-04 | 1617 | 1.13 | -0.25 | 2.27 | 3.7% |

## Maliyet (net)
| fee/slip/gecikme | net |
|---|---|
| 16_6_0 | 3252 |
| 10_2_1 | 3275 |

## Ablasyon ve komşular
| koşu | net | Sharpe |
|---|---|---|
| no_risk | 11229 | 0.99 |
| no_buffer | 3392 | 1.44 |
| scale_0.8 | 3357 | 1.40 |
| scale_0.9 | 3437 | 1.44 |
| scale_1.1 | 3309 | 1.35 |
| scale_1.2 | 3197 | 1.26 |

## Pencereler (net)
| pencere | net |
|---|---|
| 2020-07-01_2021-01-01 | 734 |
| 2021-01-01_2021-07-01 | 449 |
| 2021-07-01_2022-01-01 | 311 |
| 2022-01-01_2022-07-01 | -359 |
| 2022-07-01_2023-01-01 | 280 |
| 2023-01-01_2023-07-01 | -20 |
| 2023-07-01_2024-01-01 | 595 |
| 2024-01-01_2024-07-01 | 546 |
| 2024-07-01_2025-01-01 | 212 |
| 2025-01-01_2025-07-01 | 70 |
| 2025-07-01_2026-01-01 | 412 |
| 2026-01-01_2026-04-01 | -220 |
| 2020-04-01_2026-04-01 | 3483 |
| 2020-05-01_2026-04-01 | 3431 |
| 2020-06-01_2026-04-01 | 3295 |
| 2020-07-01_2026-04-01 | 3106 |

## Sembol dağılımı (net)
| BTCUSDT | ETHUSDT | SOLUSDT | XRPUSDT | BNBUSDT | DOGEUSDT | ADAUSDT | LINKUSDT | AVAXUSDT |
|---|---|---|---|---|---|---|---|---|
| 1306 | 377 | 247 | -70 | 360 | -304 | 760 | 345 | 463 |

## K7 sembolleri (fee 16 + slip 2; net)
| 1000PEPEUSDT | 1000SHIBUSDT | APEUSDT | APTUSDT | ARBUSDT | BCHUSDT | ETCUSDT | FILUSDT | GMTUSDT | LTCUSDT | MATICUSDT | NEARUSDT | OPUSDT | SUIUSDT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -46 | 76 | 263 | 6 | 128 | 192 | -16 | 131 | -92 | -146 | -70 | -267 | 157 | 138 |

## Stres pencereleri
| pencere | net | net_pct | max_dd | max_dd_pct | worst_hour | worst_day | n_stop | n_liq | gross_start | net_start | stop_slip_bps_mean | stop_slip_bps_max | n_stop_slip | overshoot_bps_mean | overshoot_bps_max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021-05 | -7.03 | -0.000703 | 71.5 | 0.00715 | -31.5 | -43.6 | 0 | 0 | 1.11e+03 | 74 | None | None | 0 | None | None |
| LUNA | 41.5 | 0.00415 | 43.3 | 0.00433 | -12.6 | -14.4 | 0 | 0 | 1.6e+03 | 145 | None | None | 0 | None | None |
| FTX | 78.8 | 0.00788 | 69.4 | 0.00694 | -20.8 | -30.2 | 0 | 0 | 2.44e+03 | -57.4 | None | None | 0 | None | None |