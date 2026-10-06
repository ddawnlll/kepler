# Edge uzmanı orderflow tabloları (otomatik): karar NO_EDGE (ilk kalan: K1); aile düzeltmesi (p ≤ 0.0056): kaldı; M1 range net -515; M2 EV1 korelasyonu -0.12; ters yön (bilgi): net -4069, Sharpe -0.75

| # | test | değer | eşik | geçti |
|---|---|---|---|---|
| K1 | rotasyon null p (brüt; B=300) / DSR (N=3) | p=0.1462 (null ort. 281 ± 2294; gerçek 2606) / DSR=0.760 | p ≤ 0,05; DSR ≥ 0,95 | False |
| K2 | Sharpe vs al-tut / NW alfa | 0.35 vs 0.05 / a=0.032/yıl, b=0.000, t=0.92 | > ve t ≥ 2 | False |
| K3 | net Sharpe / fee16+slip6 / gecikme 1 | 0.35 / 1009 / 1521 | ≥ 1,0; > 0; > 0 | False |
| K4 | maks DD / bootstrap DD95 (blok 10/20/40) | 13.0% / 33.1% / 31.8% / 30.2% | ≤ %25; ≤ %30 | False |
| K5 | komşu net>0 / medyan Sharpe | 100.0% (n=4) / 0.35 | ≥ %70; ≥ 0.18 | True |
| K6 | pozitif pencere / kaydırma | 9/12 / [1909, 1980, 1879, 1963] | ≥ %60; hepsi > 0 | True |
| K7 | çapraz varlık (14 sembol) net @fee16 | -1644 | > 0 | False |
| K8 | Sharpe birincil vs ablasyon | 0.35 vs no_risk 0.21, no_buffer 0.32 | hepsinden büyük | True |
| K9 | rejim net (bull/bear/range) | 1729 (n=1230) / 1122 (n=616) / -515 (n=206) | ≥ 2 rejim ≥ 0; tek ≤ %80 | True |
| K10 | G3 | koşulmadı | — | — |

## Ana sonuç (fee 10 + slip 2; sermaye 10 000)
net 1909 (brüt 2606, fee -900, slip -180, funding 382, çıkış -1); yıllık getiri 3.2%, yıllık oynaklık 9.0%; dolum 10259, likidasyon 0, red 0; yıllık devir 30.0x sermaye; ort. brüt pozisyon 0.15x; |F| ort. 0.45, long payı 46.6%; PSR(0) 0.808; MinTRL 21.5 yıl; tepe DD 11.3%; kill switch tetik %25: None, %30: None; recon -0.15

## Alt dönemler (bilgi)
| dönem | net | Sharpe | al-tut Sharpe | alfa t | maks DD |
|---|---|---|---|---|---|
| 2020-04→2022-01 | 386 | 0.22 | 0.53 | 0.22 | 13.0% |
| 2022-01→2026-04 | 1523 | 0.41 | -0.25 | 0.88 | 9.3% |

## Maliyet (net)
| fee/slip/gecikme | net |
|---|---|
| 16_6_0 | 1009 |
| 10_2_1 | 1521 |

## Ablasyon ve komşular
| koşu | net | Sharpe |
|---|---|---|
| no_risk | 4359 | 0.21 |
| no_buffer | 1778 | 0.32 |
| scale_0.8 | 1849 | 0.34 |
| scale_0.9 | 2252 | 0.42 |
| scale_1.1 | 1919 | 0.35 |
| scale_1.2 | 1560 | 0.30 |

## Pencereler (net)
| pencere | net |
|---|---|
| 2020-07-01_2021-01-01 | 688 |
| 2021-01-01_2021-07-01 | 707 |
| 2021-07-01_2022-01-01 | -951 |
| 2022-01-01_2022-07-01 | 351 |
| 2022-07-01_2023-01-01 | 588 |
| 2023-01-01_2023-07-01 | 146 |
| 2023-07-01_2024-01-01 | 415 |
| 2024-01-01_2024-07-01 | 610 |
| 2024-07-01_2025-01-01 | -509 |
| 2025-01-01_2025-07-01 | 103 |
| 2025-07-01_2026-01-01 | 112 |
| 2026-01-01_2026-04-01 | -312 |
| 2020-04-01_2026-04-01 | 1909 |
| 2020-05-01_2026-04-01 | 1980 |
| 2020-06-01_2026-04-01 | 1879 |
| 2020-07-01_2026-04-01 | 1963 |

## Sembol dağılımı (net)
| BTCUSDT | ETHUSDT | SOLUSDT | XRPUSDT | BNBUSDT | DOGEUSDT | ADAUSDT | LINKUSDT | AVAXUSDT |
|---|---|---|---|---|---|---|---|---|
| 778 | 326 | 679 | 228 | -94 | -20 | 199 | -295 | 108 |

## K7 sembolleri (fee 16 + slip 2; net)
| 1000PEPEUSDT | 1000SHIBUSDT | APEUSDT | APTUSDT | ARBUSDT | BCHUSDT | ETCUSDT | FILUSDT | GMTUSDT | LTCUSDT | MATICUSDT | NEARUSDT | OPUSDT | SUIUSDT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 425 | -213 | -473 | -250 | -19 | 11 | -202 | -175 | -364 | -258 | 88 | 82 | -330 | 35 |

## Stres pencereleri
| pencere | net | net_pct | max_dd | max_dd_pct | worst_hour | worst_day | n_stop | n_liq | gross_start | net_start | stop_slip_bps_mean | stop_slip_bps_max | n_stop_slip | overshoot_bps_mean | overshoot_bps_max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021-05 | -488 | -0.0488 | 629 | 0.0629 | -165 | -288 | 0 | 0 | 882 | 533 | None | None | 0 | None | None |
| LUNA | -113 | -0.0113 | 400 | 0.04 | -81.3 | -164 | 0 | 0 | 1.95e+03 | 1.95e+03 | None | None | 0 | None | None |
| FTX | 263 | 0.0263 | 180 | 0.018 | -74.6 | -122 | 0 | 0 | 962 | 962 | None | None | 0 | None | None |