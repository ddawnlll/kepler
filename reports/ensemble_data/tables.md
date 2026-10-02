# Ensemble v1 tabloları (otomatik): karar ZAYIF (ilk kalan: K9)

| # | test | değer | eşik | geçti |
|---|---|---|---|---|
| K1 | rotasyon null p (brüt; B=300) / DSR (N=6) | p=0.0033 (null ort. 694 ± 2242; gerçek 9195) / DSR=0.999 | p ≤ 0,05; DSR ≥ 0,95 | True |
| K2 | Sharpe vs al-tut / NW alfa | 1.45 vs 0.05 / a=0.138/yıl, b=0.000, t=3.37 | > ve t ≥ 2 | True |
| K3 | net Sharpe / fee16+slip6 / gecikme 1 | 1.45 / 7933 / 8365 | ≥ 1,0; > 0; > 0 | True |
| K4 | maks DD / bootstrap DD95 (blok 10/20/40) | 9.7% / 18.7% / 18.7% / 17.9% | ≤ %25; ≤ %30 | True |
| K5 | komşu net>0 / medyan Sharpe | 100.0% (n=6) / 1.36 | ≥ %70; ≥ 0.73 | True |
| K6 | pozitif pencere / kaydırma | 9/12 / [8297, 8215, 8101, 8021] | ≥ %60; hepsi > 0 | True |
| K7 | çapraz varlık (14 sembol) net @fee16 | 742 | > 0 | True |
| K8 | Sharpe birincil vs ablasyon | 1.45 vs trend_only 1.23, no_xs 1.32, no_carry 1.31, no_risk 1.12, no_buffer 1.25 | hepsinden büyük | True |
| K9 | rejim net (bull/bear/range) | 7329 (n=1230) / 536 (n=616) / -895 (n=206) | ≥ 2 rejim ≥ 0; tek ≤ %80 | False |
| K10 | G3 | koşulmadı | — | — |

## Ana sonuç (fee 10 + slip 2; sermaye 10 000)
net 8297 (brüt 9195, fee -363, slip -73, funding -461, çıkış -1); yıllık getiri 13.8%, yıllık oynaklık 9.5%; dolum 5561, likidasyon 0, red 0; yıllık devir 12.1x sermaye; ort. brüt pozisyon 0.15x; |F| ort. 0.46, long payı 48.5%; PSR(0) 1.000; MinTRL 1.3 yıl; tepe DD 5.1%; kill switch tetik %25: None, %30: None; recon 0.34

## Alt dönemler (bilgi)
| dönem | net | Sharpe | al-tut Sharpe | alfa t | maks DD |
|---|---|---|---|---|---|
| 2020-04→2022-01 | 5016 | 3.03 | 0.53 | 3.66 | 3.7% |
| 2022-01→2026-04 | 3281 | 0.81 | -0.25 | 1.60 | 9.7% |

## Maliyet (net)
| fee/slip/gecikme | net |
|---|---|
| 4_2_0 | 8516 |
| 16_2_0 | 8079 |
| 10_6_0 | 8152 |
| 16_6_0 | 7933 |
| 10_2_1 | 8365 |

## Ablasyon ve komşular
| koşu | net | Sharpe |
|---|---|---|
| trend_only | 9206 | 1.23 |
| no_xs | 9363 | 1.32 |
| no_carry | 8088 | 1.31 |
| no_risk | 30983 | 1.12 |
| no_buffer | 6876 | 1.25 |
| scale_0.8 | 6876 | 1.18 |
| scale_0.9 | 7736 | 1.33 |
| scale_1.1 | 8026 | 1.41 |
| scale_1.2 | 7523 | 1.30 |
| w_50_25_25 | 7573 | 1.50 |
| w_70_15_15 | 8849 | 1.38 |

## Pencereler (net)
| pencere | net |
|---|---|
| 2020-07-01_2021-01-01 | 1629 |
| 2021-01-01_2021-07-01 | 2147 |
| 2021-07-01_2022-01-01 | 951 |
| 2022-01-01_2022-07-01 | 368 |
| 2022-07-01_2023-01-01 | -139 |
| 2023-01-01_2023-07-01 | 5 |
| 2023-07-01_2024-01-01 | 1770 |
| 2024-01-01_2024-07-01 | 736 |
| 2024-07-01_2025-01-01 | 833 |
| 2025-01-01_2025-07-01 | -601 |
| 2025-07-01_2026-01-01 | 370 |
| 2026-01-01_2026-04-01 | -66 |
| 2020-04-01_2026-04-01 | 8297 |
| 2020-05-01_2026-04-01 | 8215 |
| 2020-06-01_2026-04-01 | 8101 |
| 2020-07-01_2026-04-01 | 8021 |

## Sembol dağılımı (net)
| BTCUSDT | ETHUSDT | SOLUSDT | XRPUSDT | BNBUSDT | DOGEUSDT | ADAUSDT | LINKUSDT | AVAXUSDT |
|---|---|---|---|---|---|---|---|---|
| 1393 | 747 | 1182 | 808 | 874 | 965 | 904 | 93 | 1331 |

## K7 sembolleri (fee 16 + slip 2; net)
| 1000PEPEUSDT | 1000SHIBUSDT | APEUSDT | APTUSDT | ARBUSDT | BCHUSDT | ETCUSDT | FILUSDT | GMTUSDT | LTCUSDT | MATICUSDT | NEARUSDT | OPUSDT | SUIUSDT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 376 | 171 | 254 | -72 | 170 | -228 | -23 | -89 | 111 | -115 | 86 | 75 | -180 | 204 |

## Stres pencereleri
| pencere | net | net_pct | max_dd | max_dd_pct | worst_hour | worst_day | n_stop | n_liq | gross_start | net_start | stop_slip_bps_mean | stop_slip_bps_max | n_stop_slip | overshoot_bps_mean | overshoot_bps_max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021-05 | -40.9 | -0.00409 | 168 | 0.0168 | -69.9 | -95.4 | 0 | 0 | 957 | 80.1 | None | None | 0 | None | None |
| LUNA | 294 | 0.0294 | 335 | 0.0335 | -133 | -88.8 | 0 | 0 | 1.54e+03 | -1.19e+03 | None | None | 0 | None | None |
| FTX | -394 | -0.0394 | 419 | 0.0419 | -93.4 | -214 | 0 | 0 | 2.42e+03 | 2.42e+03 | None | None | 0 | None | None |

500 USD sermaye (bilgi): net 392.74, Sharpe 1.47, red 0, dolum 4193
Kümülatif deneme sayısı (ledger satırları): önceki 4116 + bu test 1 = 4117.