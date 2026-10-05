# Edge uzmanı fundcrowd tabloları (otomatik): karar NO_EDGE (ilk kalan: K1); aile düzeltmesi (p ≤ 0.0056): kaldı; M1 range net 630; M2 EV1 korelasyonu -0.51; ters yön (bilgi): net 2526, Sharpe 0.49

| # | test | değer | eşik | geçti |
|---|---|---|---|---|
| K1 | rotasyon null p (brüt; B=300) / DSR (N=3) | p=0.9668 (null ort. -212 ± 1821; gerçek -3673) / DSR=0.045 | p ≤ 0,05; DSR ≥ 0,95 | False |
| K2 | Sharpe vs al-tut / NW alfa | -0.58 vs 0.05 / a=-0.049/yıl, b=-0.000, t=-1.53 | > ve t ≥ 2 | False |
| K3 | net Sharpe / fee16+slip6 / gecikme 1 | -0.58 / -3176 / -2783 | ≥ 1,0; > 0; > 0 | False |
| K4 | maks DD / bootstrap DD95 (blok 10/20/40) | 36.5% / 71.9% / 72.4% / 70.6% | ≤ %25; ≤ %30 | False |
| K5 | komşu net>0 / medyan Sharpe | 0.0% (n=4) / -0.61 | ≥ %70; ≥ -0.29 | False |
| K6 | pozitif pencere / kaydırma | 4/12 / [-2985, -2985, -2985, -2979] | ≥ %60; hepsi > 0 | False |
| K7 | çapraz varlık (14 sembol) net @fee16 | -1393 | > 0 | False |
| K8 | Sharpe birincil vs ablasyon | -0.58 vs no_risk -0.33, no_buffer -0.53 | hepsinden büyük | False |
| K9 | rejim net (bull/bear/range) | -3230 (n=1230) / -167 (n=616) / 630 (n=206) | ≥ 2 rejim ≥ 0; tek ≤ %80 | False |
| K10 | G3 | koşulmadı | — | — |

## Ana sonuç (fee 10 + slip 2; sermaye 10 000)
net -2985 (brüt -3673, fee -191, slip -38, funding 918, çıkış -0); yıllık getiri -5.0%, yıllık oynaklık 8.6%; dolum 1089, likidasyon 0, red 0; yıllık devir 6.4x sermaye; ort. brüt pozisyon 0.06x; |F| ort. 0.19, long payı 7.3%; PSR(0) 0.078; MinTRL None yıl; tepe DD 35.5%; kill switch tetik %25: 2024-11-29, %30: 2025-07-19; recon -0.00

## Alt dönemler (bilgi)
| dönem | net | Sharpe | al-tut Sharpe | alfa t | maks DD |
|---|---|---|---|---|---|
| 2020-04→2022-01 | -859 | -0.50 | 0.53 | -0.61 | 14.2% |
| 2022-01→2026-04 | -2126 | -0.62 | -0.25 | -1.42 | 30.7% |

## Maliyet (net)
| fee/slip/gecikme | net |
|---|---|
| 16_6_0 | -3176 |
| 10_2_1 | -2783 |

## Ablasyon ve komşular
| koşu | net | Sharpe |
|---|---|---|
| no_risk | -6108 | -0.33 |
| no_buffer | -2600 | -0.53 |
| scale_0.8 | -5213 | -0.83 |
| scale_0.9 | -4149 | -0.72 |
| scale_1.1 | -2200 | -0.49 |
| scale_1.2 | -1472 | -0.37 |

## Pencereler (net)
| pencere | net |
|---|---|
| 2020-07-01_2021-01-01 | -435 |
| 2021-01-01_2021-07-01 | 44 |
| 2021-07-01_2022-01-01 | -466 |
| 2022-01-01_2022-07-01 | 281 |
| 2022-07-01_2023-01-01 | -197 |
| 2023-01-01_2023-07-01 | 257 |
| 2023-07-01_2024-01-01 | -613 |
| 2024-01-01_2024-07-01 | -438 |
| 2024-07-01_2025-01-01 | -957 |
| 2025-01-01_2025-07-01 | 176 |
| 2025-07-01_2026-01-01 | -547 |
| 2026-01-01_2026-04-01 | -71 |
| 2020-04-01_2026-04-01 | -2985 |
| 2020-05-01_2026-04-01 | -2985 |
| 2020-06-01_2026-04-01 | -2985 |
| 2020-07-01_2026-04-01 | -2979 |

## Sembol dağılımı (net)
| BTCUSDT | ETHUSDT | SOLUSDT | XRPUSDT | BNBUSDT | DOGEUSDT | ADAUSDT | LINKUSDT | AVAXUSDT |
|---|---|---|---|---|---|---|---|---|
| 53 | -413 | -479 | -1132 | 0 | -398 | 138 | 196 | -951 |

## K7 sembolleri (fee 16 + slip 2; net)
| 1000PEPEUSDT | 1000SHIBUSDT | APEUSDT | APTUSDT | ARBUSDT | BCHUSDT | ETCUSDT | FILUSDT | GMTUSDT | LTCUSDT | MATICUSDT | NEARUSDT | OPUSDT | SUIUSDT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -93 | -291 | 116 | -84 | -161 | -117 | -130 | 55 | 44 | -146 | -10 | -187 | -315 | -75 |

## Stres pencereleri
| pencere | net | net_pct | max_dd | max_dd_pct | worst_hour | worst_day | n_stop | n_liq | gross_start | net_start | stop_slip_bps_mean | stop_slip_bps_max | n_stop_slip | overshoot_bps_mean | overshoot_bps_max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021-05 | -178 | -0.0178 | 386 | 0.0386 | -66.3 | -112 | 0 | 0 | 7.3e-13 | -4.41e-13 | None | None | 0 | None | None |
| LUNA | -36 | -0.0036 | 356 | 0.0356 | -68.3 | -99.6 | 0 | 0 | 354 | 354 | None | None | 0 | None | None |
| FTX | -168 | -0.0168 | 254 | 0.0254 | -45.5 | -214 | 0 | 0 | 2.9e-13 | -2.28e-13 | None | None | 0 | None | None |