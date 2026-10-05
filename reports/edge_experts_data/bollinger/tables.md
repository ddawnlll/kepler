# Edge uzmanı bollinger tabloları (otomatik) — GEÇERSİZ KOŞU: hesap bitti, deftere yazılmadı (reddedilen emir / eksik funding olan koşu geçerli sonuç deği…): karar NO_EDGE (ilk kalan: K1); aile düzeltmesi (p ≤ 0.0056): kaldı; M1 range net 419; M2 EV1 korelasyonu -0.72; ters yön (bilgi): net 8025, Sharpe 1.08

| # | test | değer | eşik | geçti |
|---|---|---|---|---|
| K1 | rotasyon null p (brüt; B=300) / DSR (N=3) | p=1.0000 (null ort. 347 ± 3113; gerçek -9763) / DSR=0.000 | p ≤ 0,05; DSR ≥ 0,95 | False |
| K2 | Sharpe vs al-tut / NW alfa | -1.39 vs 0.05 / a=-0.155/yıl, b=-0.001, t=-3.20 | > ve t ≥ 2 | False |
| K3 | net Sharpe / fee16+slip6 / gecikme 1 | -1.39 / -9123 / -9066 | ≥ 1,0; > 0; > 0 | False |
| K4 | maks DD / bootstrap DD95 (blok 10/20/40) | 99.6% / 148.1% / 149.7% / 150.7% | ≤ %25; ≤ %30 | False |
| K5 | komşu net>0 / medyan Sharpe | 0.0% (n=4) / -1.38 | ≥ %70; ≥ -0.69 | False |
| K6 | pozitif pencere / kaydırma | 1/12 / [-9341, -8984, -9332, -9633] | ≥ %60; hepsi > 0 | False |
| K7 | çapraz varlık (14 sembol) net @fee16 | -2082 | > 0 | False |
| K8 | Sharpe birincil vs ablasyon | -1.39 vs no_risk -0.77, no_buffer -1.14 | hepsinden büyük | False |
| K9 | rejim net (bull/bear/range) | -6940 (n=1230) / -1573 (n=616) / 419 (n=206) | ≥ 2 rejim ≥ 0; tek ≤ %80 | False |
| K10 | G3 | koşulmadı | — | — |

## Ana sonuç (fee 10 + slip 2; sermaye 10 000)
net -9341 (brüt -9763, fee -448, slip -90, funding 963, çıkış -0); yıllık getiri -15.6%, yıllık oynaklık 11.2%; dolum 5558, likidasyon 3, red 1275; yıllık devir 14.9x sermaye; ort. brüt pozisyon 0.17x; |F| ort. 0.49, long payı 47.2%; PSR(0) 0.000; MinTRL None yıl; tepe DD 97.7%; kill switch tetik %25: 2021-01-06, %30: 2021-02-09; recon -0.31

## Alt dönemler (bilgi)
| dönem | net | Sharpe | al-tut Sharpe | alfa t | maks DD |
|---|---|---|---|---|---|
| 2020-04→2022-01 | -4827 | -2.10 | 0.53 | -2.48 | 54.5% |
| 2022-01→2026-04 | -4514 | -1.03 | -0.25 | -2.17 | 49.8% |

## Maliyet (net)
| fee/slip/gecikme | net |
|---|---|
| 16_6_0 | -9123 |
| 10_2_1 | -9066 |

## Ablasyon ve komşular
| koşu | net | Sharpe |
|---|---|---|
| no_risk | -17159 | -0.77 |
| no_buffer | -8308 | -1.14 |
| scale_0.8 | -9086 | -1.44 |
| scale_0.9 | -9126 | -1.41 |
| scale_1.1 | -9052 | -1.32 |
| scale_1.2 | -9066 | -1.34 |

## Pencereler (net)
| pencere | net |
|---|---|
| 2020-07-01_2021-01-01 | -1860 |
| 2021-01-01_2021-07-01 | -2183 |
| 2021-07-01_2022-01-01 | -935 |
| 2022-01-01_2022-07-01 | -985 |
| 2022-07-01_2023-01-01 | -145 |
| 2023-01-01_2023-07-01 | -145 |
| 2023-07-01_2024-01-01 | -1467 |
| 2024-01-01_2024-07-01 | -886 |
| 2024-07-01_2025-01-01 | -1074 |
| 2025-01-01_2025-07-01 | 714 |
| 2025-07-01_2026-01-01 | -291 |
| 2026-01-01_2026-04-01 | -338 |
| 2020-04-01_2026-04-01 | -9341 |
| 2020-05-01_2026-04-01 | -8984 |
| 2020-06-01_2026-04-01 | -9332 |
| 2020-07-01_2026-04-01 | -9633 |

## Sembol dağılımı (net)
| BTCUSDT | ETHUSDT | SOLUSDT | XRPUSDT | BNBUSDT | DOGEUSDT | ADAUSDT | LINKUSDT | AVAXUSDT |
|---|---|---|---|---|---|---|---|---|
| -985 | -735 | -1136 | -1208 | -1257 | -1040 | -1110 | -392 | -1478 |

## K7 sembolleri (fee 16 + slip 2; net)
| 1000PEPEUSDT | 1000SHIBUSDT | APEUSDT | APTUSDT | ARBUSDT | BCHUSDT | ETCUSDT | FILUSDT | GMTUSDT | LTCUSDT | MATICUSDT | NEARUSDT | OPUSDT | SUIUSDT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| -558 | -374 | -183 | 90 | -290 | 126 | 65 | -188 | -109 | 90 | -142 | -400 | -9 | -201 |

## Stres pencereleri
| pencere | net | net_pct | max_dd | max_dd_pct | worst_hour | worst_day | n_stop | n_liq | gross_start | net_start | stop_slip_bps_mean | stop_slip_bps_max | n_stop_slip | overshoot_bps_mean | overshoot_bps_max |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021-05 | -125 | -0.0125 | 463 | 0.0463 | -81.3 | -122 | 0 | 0 | 898 | 165 | None | None | 0 | None | None |
| LUNA | -547 | -0.0547 | 934 | 0.0934 | -239 | -321 | 0 | 0 | 2.33e+03 | 2.33e+03 | None | None | 0 | None | None |
| FTX | 243 | 0.0243 | 318 | 0.0318 | -93.6 | -262 | 0 | 0 | 3.45e+03 | -3.45e+03 | None | None | 0 | None | None |