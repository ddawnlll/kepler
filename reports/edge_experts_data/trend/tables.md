# Edge uzmanı trend tabloları (otomatik): karar ZAYIF (ilk kalan: K9); aile düzeltmesi (p ≤ 0.0056): geçti; M1 range net -1140; M2 EV1 korelasyonu 0.92; ters yön (bilgi): net -10027, Sharpe -1.54

| # | test | değer | eşik | geçti |
|---|---|---|---|---|
| K1 | rotasyon null p (brüt; B=300) / DSR (N=3) | p=0.0033 (null ort. -7 ± 3095; gerçek 10824) / DSR=0.997 | p ≤ 0,05; DSR ≥ 0,95 | True |
| K2 | Sharpe vs al-tut / NW alfa | 1.23 vs 0.05 / a=0.153/yıl, b=0.000, t=2.86 | > ve t ≥ 2 | True |
| K3 | net Sharpe / fee16+slip6 / gecikme 1 | 1.23 / 8838 / 9348 | ≥ 1,0; > 0; > 0 | True |
| K4 | maks DD / bootstrap DD95 (blok 10/20/40) | 12.3% / 27.1% / 26.9% / 26.1% | ≤ %25; ≤ %30 | True |
| K5 | komşu net>0 / medyan Sharpe | 100.0% (n=4) / 1.12 | ≥ %70; ≥ 0.61 | True |
| K6 | pozitif pencere / kaydırma | 9/12 / [9206, 9079, 9066, 9145] | ≥ %60; hepsi > 0 | True |
| K7 | çapraz varlık (14 sembol) net @fee16 | 1365 | > 0 | True |
| K8 | Sharpe birincil vs ablasyon | 1.23 vs no_risk 1.03, no_buffer 1.03 | hepsinden büyük | True |
| K9 | rejim net (bull/bear/range) | 8033 (n=1230) / 698 (n=616) / -1140 (n=206) | ≥ 2 rejim ≥ 0; tek ≤ %80 | False |
| K10 | G3 | koşulmadı | — | — |

## Ana sonuç (fee 10 + slip 2; sermaye 10 000)
net 9206 (brüt 10824, fee -367, slip -73, funding -1176, çıkış -1); yıllık getiri 15.3%, yıllık oynaklık 12.5%; dolum 5400, likidasyon 0, red 0; yıllık devir 12.2x sermaye; ort. brüt pozisyon 0.15x; |F| ort. 0.46, long payı 46.0%; PSR(0) 0.999; MinTRL 1.8 yıl; tepe DD 7.1%; kill switch tetik %25: None, %30: None; recon 0.29

## Alt dönemler (bilgi)
| dönem | net | Sharpe | al-tut Sharpe | alfa t | maks DD |
|---|---|---|---|---|---|
| 2020-04→2022-01 | 5964 | 2.57 | 0.53 | 3.07 | 7.5% |
| 2022-01→2026-04 | 3243 | 0.63 | -0.25 | 1.21 | 12.3% |

## Maliyet (net)
| fee/slip/gecikme | net |
|---|---|
| 16_6_0 | 8838 |
| 10_2_1 | 9348 |

## Ablasyon ve komşular
| koşu | net | Sharpe |
|---|---|---|
| no_risk | 31403 | 1.03 |
| no_buffer | 7484 | 1.03 |
| scale_0.8 | 7362 | 0.97 |
| scale_0.9 | 8701 | 1.13 |
| scale_1.1 | 9319 | 1.24 |
| scale_1.2 | 8412 | 1.11 |

## Pencereler (net)
| pencere | net |
|---|---|
| 2020-07-01_2021-01-01 | 1983 |
| 2021-01-01_2021-07-01 | 2995 |
| 2021-07-01_2022-01-01 | 881 |
| 2022-01-01_2022-07-01 | 737 |
| 2022-07-01_2023-01-01 | -324 |
| 2023-01-01_2023-07-01 | -384 |
| 2023-07-01_2024-01-01 | 1859 |
| 2024-01-01_2024-07-01 | 844 |
| 2024-07-01_2025-01-01 | 742 |
| 2025-01-01_2025-07-01 | -743 |
| 2025-07-01_2026-01-01 | 305 |
| 2026-01-01_2026-04-01 | 202 |
| 2020-04-01_2026-04-01 | 9206 |
| 2020-05-01_2026-04-01 | 9079 |
| 2020-06-01_2026-04-01 | 9066 |
| 2020-07-01_2026-04-01 | 9145 |

## Sembol dağılımı (net)
| BTCUSDT | ETHUSDT | SOLUSDT | XRPUSDT | BNBUSDT | DOGEUSDT | ADAUSDT | LINKUSDT | AVAXUSDT |
|---|---|---|---|---|---|---|---|---|
| 1220 | 853 | 1450 | 937 | 1252 | 1347 | 705 | 113 | 1329 |

## K7 sembolleri (fee 16 + slip 2; net)
| 1000PEPEUSDT | 1000SHIBUSDT | APEUSDT | APTUSDT | ARBUSDT | BCHUSDT | ETCUSDT | FILUSDT | GMTUSDT | LTCUSDT | MATICUSDT | NEARUSDT | OPUSDT | SUIUSDT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 314 | 267 | 212 | -58 | 189 | -173 | 11 | 26 | 132 | -16 | 118 | 194 | -35 | 186 |

## Stres pencereleri
| pencere | net | net_pct | max_dd | max_dd_pct | worst_hour | worst_day | n_stop | n_liq | gross_start | net_start | stop_slip_bps_mean | stop_slip_bps_max | n_stop_slip | overshoot_bps_mean | overshoot_bps_max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021-05 | -96.2 | -0.00962 | 259 | 0.0259 | -94.4 | -156 | 0 | 0 | 941 | 322 | None | None | 0 | None | None |
| LUNA | 477 | 0.0477 | 416 | 0.0416 | -173 | -118 | 0 | 0 | 2.01e+03 | -2.01e+03 | None | None | 0 | None | None |
| FTX | -383 | -0.0383 | 463 | 0.0463 | -113 | -297 | 0 | 0 | 2.77e+03 | 2.77e+03 | None | None | 0 | None | None |