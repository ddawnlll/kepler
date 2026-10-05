# Edge uzmanı xs_momentum tabloları (otomatik): karar ZAYIF (ilk kalan: K7); aile düzeltmesi (p ≤ 0.0056): geçti; M1 range net -435; M2 EV1 korelasyonu 0.41; ters yön (bilgi): net -4514, Sharpe -1.69

| # | test | değer | eşik | geçti |
|---|---|---|---|---|
| K1 | rotasyon null p (brüt; B=300) / DSR (N=3) | p=0.0033 (null ort. -125 ± 1098; gerçek 3917) / DSR=1.000 | p ≤ 0,05; DSR ≥ 0,95 | True |
| K2 | Sharpe vs al-tut / NW alfa | 1.39 vs 0.05 / a=0.062/yıl, b=-0.000, t=3.48 | > ve t ≥ 2 | True |
| K3 | net Sharpe / fee16+slip6 / gecikme 1 | 1.39 / 3371 / 3628 | ≥ 1,0; > 0; > 0 | True |
| K4 | maks DD / bootstrap DD95 (blok 10/20/40) | 4.7% / 8.9% / 9.0% / 9.1% | ≤ %25; ≤ %30 | True |
| K5 | komşu net>0 / medyan Sharpe | 100.0% (n=4) / 1.13 | ≥ %70; ≥ 0.69 | True |
| K6 | pozitif pencere / kaydırma | 9/12 / [3707, 3718, 3478, 3312] | ≥ %60; hepsi > 0 | True |
| K7 | çapraz varlık (14 sembol) net @fee16 | -194 | > 0 | False |
| K8 | Sharpe birincil vs ablasyon | 1.39 vs no_risk 1.23, no_buffer 1.30 | hepsinden büyük | True |
| K9 | rejim net (bull/bear/range) | 3540 (n=1230) / 92 (n=616) / -435 (n=206) | ≥ 2 rejim ≥ 0; tek ≤ %80 | False |
| K10 | G3 | koşulmadı | — | — |

## Ana sonuç (fee 10 + slip 2; sermaye 10 000)
net 3707 (brüt 3917, fee -335, slip -67, funding 193, çıkış -1); yıllık getiri 6.2%, yıllık oynaklık 4.4%; dolum 4890, likidasyon 0, red 0; yıllık devir 11.2x sermaye; ort. brüt pozisyon 0.16x; |F| ort. 0.49, long payı 43.2%; PSR(0) 1.000; MinTRL 1.3 yıl; tepe DD 3.4%; kill switch tetik %25: None, %30: None; recon 0.20

## Alt dönemler (bilgi)
| dönem | net | Sharpe | al-tut Sharpe | alfa t | maks DD |
|---|---|---|---|---|---|
| 2020-04→2022-01 | 2389 | 2.41 | 0.53 | 3.30 | 3.6% |
| 2022-01→2026-04 | 1318 | 0.81 | -0.25 | 1.73 | 4.7% |

## Maliyet (net)
| fee/slip/gecikme | net |
|---|---|
| 16_6_0 | 3371 |
| 10_2_1 | 3628 |

## Ablasyon ve komşular
| koşu | net | Sharpe |
|---|---|---|
| no_risk | 14647 | 1.23 |
| no_buffer | 3203 | 1.30 |
| scale_0.8 | 3101 | 1.01 |
| scale_0.9 | 3420 | 1.26 |
| scale_1.1 | 3467 | 1.32 |
| scale_1.2 | 2654 | 0.96 |

## Pencereler (net)
| pencere | net |
|---|---|
| 2020-07-01_2021-01-01 | 885 |
| 2021-01-01_2021-07-01 | 661 |
| 2021-07-01_2022-01-01 | 443 |
| 2022-01-01_2022-07-01 | -99 |
| 2022-07-01_2023-01-01 | 407 |
| 2023-01-01_2023-07-01 | -75 |
| 2023-07-01_2024-01-01 | 374 |
| 2024-01-01_2024-07-01 | 121 |
| 2024-07-01_2025-01-01 | 524 |
| 2025-01-01_2025-07-01 | 161 |
| 2025-07-01_2026-01-01 | 283 |
| 2026-01-01_2026-04-01 | -410 |
| 2020-04-01_2026-04-01 | 3707 |
| 2020-05-01_2026-04-01 | 3718 |
| 2020-06-01_2026-04-01 | 3478 |
| 2020-07-01_2026-04-01 | 3312 |

## Sembol dağılımı (net)
| BTCUSDT | ETHUSDT | SOLUSDT | XRPUSDT | BNBUSDT | DOGEUSDT | ADAUSDT | LINKUSDT | AVAXUSDT |
|---|---|---|---|---|---|---|---|---|
| 1032 | 526 | 493 | 560 | -233 | 20 | 734 | 4 | 569 |

## K7 sembolleri (fee 16 + slip 2; net)
| 1000PEPEUSDT | 1000SHIBUSDT | APEUSDT | APTUSDT | ARBUSDT | BCHUSDT | ETCUSDT | FILUSDT | GMTUSDT | LTCUSDT | MATICUSDT | NEARUSDT | OPUSDT | SUIUSDT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 388 | 144 | 278 | -87 | 10 | -172 | -133 | -232 | 92 | -264 | -35 | -105 | -262 | 185 |

## Stres pencereleri
| pencere | net | net_pct | max_dd | max_dd_pct | worst_hour | worst_day | n_stop | n_liq | gross_start | net_start | stop_slip_bps_mean | stop_slip_bps_max | n_stop_slip | overshoot_bps_mean | overshoot_bps_max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021-05 | 45 | 0.0045 | 49.1 | 0.00491 | -17.5 | -15.6 | 0 | 0 | 919 | -186 | None | None | 0 | None | None |
| LUNA | -17.7 | -0.00177 | 47.6 | 0.00476 | -11.3 | -42 | 0 | 0 | 1.83e+03 | -99.6 | None | None | 0 | None | None |
| FTX | 51.1 | 0.00511 | 93.5 | 0.00935 | -21.2 | -60.8 | 0 | 0 | 1.79e+03 | -236 | None | None | 0 | None | None |