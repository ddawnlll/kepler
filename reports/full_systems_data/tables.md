# V4 tabloları (otomatik)
N = 12 deneme; DSR eşik SR0 = 0.0314 (günlük; yıllık 0.60); al-tut yıllık Sharpe = -0.11; null B = S1: 500, S2: 500

## S1: karar NO_EDGE (ilk kalan madde: K1)
| # | test | değer | eşik | geçti |
|---|---|---|---|---|
| K1 | rotasyon null p (brüt), B=500 / DSR | p=0.0259 (Bonf. 0.311) / DSR=0.520 | p ≤ 0.0042 ve DSR ≥ 0,95 | False |
| K2 | Sharpe vs al-tut / NW alfa t | 0.63 vs -0.11 / a=0.997/yıl, b=0.42, t=1.32 | > ve t ≥ 2 | False |
| K3 | net Sharpe / net@fee16+slip6 / net@gecikme1 | 0.63 / 38164 / 39020 | ≥ 1,0; > 0; > 0 | False |
| K4 | maks DD / bootstrap DD %95 (blok 10/20/40) | 250.7% / 425.9% / 413.9% / 400.5% | ≤ %25; ≤ %30 (blok 20) | False |
| K5 | komşu net>0 oranı / komşu medyan Sharpe (seçilen 0.63) | 91.7% (n=24) / 0.42 | ≥ %70; ≥ 0.31 | True |
| K6 | pozitif pencere / başlangıç kaydırma | 3/7 / [39398, 38901, 39878, 35960] | ≥ %60; hepsi > 0 | False |
| K7 | çapraz varlık net @fee16+slip2 (14 sembol) | 4925 | > 0 | True |
| K8 | Sharpe full vs ablasyonlar | full 0.63; no_stop -0.24, fixed_size 0.47, no_pyramid 0.43, no_limits 0.11 | full her birinden büyük | True |
| K9 | rejim net (bull/bear/range, USDT) | 37951 (n=837) / 1740 (n=342) / -5322 (n=142) | ≥ 2 rejimde ≥ 0; tek rejim ≤ %80 | False |
| K10 | G3 | koşulmadı | — | — |

## S2: karar NO_EDGE (ilk kalan madde: K1)
| # | test | değer | eşik | geçti |
|---|---|---|---|---|
| K1 | rotasyon null p (brüt), B=500 / DSR | p=0.0599 (Bonf. 0.719) / DSR=0.355 | p ≤ 0.0042 ve DSR ≥ 0,95 | False |
| K2 | Sharpe vs al-tut / NW alfa t | 0.42 vs -0.11 / a=0.713/yıl, b=0.47, t=0.99 | > ve t ≥ 2 | False |
| K3 | net Sharpe / net@fee16+slip6 / net@gecikme1 | 0.42 / 26980 / 27907 | ≥ 1,0; > 0; > 0 | False |
| K4 | maks DD / bootstrap DD %95 (blok 10/20/40) | 302.5% / 473.1% / 483.4% / 455.1% | ≤ %25; ≤ %30 (blok 20) | False |
| K5 | komşu net>0 oranı / komşu medyan Sharpe (seçilen 0.42) | 79.2% (n=24) / 0.32 | ≥ %70; ≥ 0.21 | True |
| K6 | pozitif pencere / başlangıç kaydırma | 4/7 / [27641, 27772, 28215, 28267] | ≥ %60; hepsi > 0 | False |
| K7 | çapraz varlık net @fee16+slip2 (14 sembol) | 22269 | > 0 | True |
| K8 | Sharpe full vs ablasyonlar | full 0.42; no_stop -0.42, fixed_size -0.41, no_pyramid 0.35, no_limits 0.42 | full her birinden büyük | False |
| K9 | rejim net (bull/bear/range, USDT) | 25358 (n=837) / 6971 (n=342) / -4652 (n=142) | ≥ 2 rejimde ≥ 0; tek rejim ≤ %80 | False |
| K10 | G3 | koşulmadı | — | — |

## 12 deneme (fee 10 + slip 2; USDT; sermaye 10 000)
| deneme | net | brüt | fee | slippage | funding | çıkış | likidasyon | dolum | hakem stop | yönetici taklit stop | Sharpe | maks DD | recon farkı |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1_full | 39398 | 46802 | -1232 | -246 | -5923 | -3 | 0 | 953 | 194 | 199 | 0.63 | 250.7% | 1.06 |
| S1_no_stop | -7689 | -4939 | -547 | -109 | -1986 | -0 | 7 | 418 | 0 | 0 | -0.24 | 131.2% | 1.06 |
| S1_fixed_size | 37620 | 46437 | -1623 | -325 | -6864 | -5 | 0 | 952 | 194 | 199 | 0.47 | 345.7% | 1.95 |
| S1_no_pyramid | 16107 | 20852 | -725 | -145 | -3872 | -3 | 0 | 716 | 143 | 145 | 0.43 | 142.9% | 1.06 |
| S1_no_limits | 6787 | 13512 | -1484 | -297 | -4941 | -3 | 0 | 1155 | 254 | 264 | 0.11 | 356.7% | 4.25 |
| S1_g2_equiv | 7450 | 9864 | -387 | -77 | -1948 | -2 | 0 | 664 | 0 | 0 | 0.36 | 80.2% | 0.78 |
| S2_full | 27641 | 35827 | -657 | -131 | -7393 | -5 | 0 | 473 | 122 | 122 | 0.42 | 302.5% | -0.00 |
| S2_no_stop | -11834 | -9110 | -189 | -38 | -2450 | -3 | 4 | 154 | 0 | 0 | -0.42 | 195.9% | 0.00 |
| S2_fixed_size | -11036 | -9594 | -320 | -64 | -949 | -0 | 6 | 192 | 53 | 122 | -0.41 | 179.8% | -0.00 |
| S2_no_pyramid | 12573 | 17252 | -334 | -67 | -4277 | -1 | 0 | 331 | 88 | 88 | 0.35 | 130.9% | -0.00 |
| S2_no_limits | 27242 | 34526 | -729 | -146 | -6408 | -0 | 0 | 529 | 131 | 139 | 0.42 | 276.2% | 0.00 |
| S2_g2_equiv | 7576 | 10132 | -174 | -35 | -2346 | -1 | 0 | 321 | 0 | 0 | 0.36 | 78.6% | -0.00 |

## Maliyet ızgarası (full; net USDT)
| sistem | fee 4 | 9 | 10 | 11 | 16 (slip 2) | fee 10 slip 6 | fee 16 slip 6 | gecikme 1 (fee 10) |
|---|---|---|---|---|---|---|---|---|
| S1 | 40138 | 39521 | 39398 | 39274 | 38657 | 38904 | 38164 | 39020 |
| S2 | 28038 | 27707 | 27641 | 27575 | 27244 | 27377 | 26980 | 27907 |

## Pencereler ve başlangıç kaydırma (full, fee 10 + slip 2; net USDT)
| sistem | pencere | net |
|---|---|---|
| S1 | 2023-01-01_2023-07-01 | 2283 |
| S1 | 2023-07-01_2024-01-01 | 27848 |
| S1 | 2024-01-01_2024-07-01 | -721 |
| S1 | 2024-07-01_2025-01-01 | 16625 |
| S1 | 2025-01-01_2025-07-01 | -8205 |
| S1 | 2025-07-01_2026-01-01 | -199 |
| S1 | 2026-01-01_2026-04-01 | -1375 |
| S1 | 2022-03-01_2026-04-01 | 39398 |
| S1 | 2022-04-01_2026-04-01 | 38901 |
| S1 | 2022-05-01_2026-04-01 | 39878 |
| S1 | 2022-06-01_2026-04-01 | 35960 |
| S2 | 2023-01-01_2023-07-01 | -2485 |
| S2 | 2023-07-01_2024-01-01 | 23730 |
| S2 | 2024-01-01_2024-07-01 | 2399 |
| S2 | 2024-07-01_2025-01-01 | -4761 |
| S2 | 2025-01-01_2025-07-01 | -2329 |
| S2 | 2025-07-01_2026-01-01 | 6983 |
| S2 | 2026-01-01_2026-04-01 | 363 |
| S2 | 2022-03-01_2026-04-01 | 27641 |
| S2 | 2022-04-01_2026-04-01 | 27772 |
| S2 | 2022-05-01_2026-04-01 | 28215 |
| S2 | 2022-06-01_2026-04-01 | 28267 |

## Komşuluk (full; net USDT ve yıllık Sharpe; fee 10 + slip 2)
| sistem | giriş/çıkış | net | Sharpe |
|---|---|---|---|
| S1 | 16/8 | 37459 | 0.59 |
| S1 | 16/9 | 49657 | 0.74 |
| S1 | 16/10 | 45027 | 0.67 |
| S1 | 16/11 | 29675 | 0.47 |
| S1 | 16/12 | 26944 | 0.42 |
| S1 | 18/8 | 25007 | 0.43 |
| S1 | 18/9 | 45522 | 0.72 |
| S1 | 18/10 | 41158 | 0.65 |
| S1 | 18/11 | 24928 | 0.42 |
| S1 | 18/12 | 17856 | 0.33 |
| S1 | 20/8 | 24345 | 0.42 |
| S1 | 20/9 | 45138 | 0.71 |
| S1 | 20/11 | 24646 | 0.42 |
| S1 | 20/12 | 19981 | 0.37 |
| S1 | 22/8 | 21629 | 0.38 |
| S1 | 22/9 | 42503 | 0.68 |
| S1 | 22/10 | 36832 | 0.59 |
| S1 | 22/11 | 19639 | 0.34 |
| S1 | 22/12 | -4164 | -0.09 |
| S1 | 24/8 | 23326 | 0.41 |
| S1 | 24/9 | 21436 | 0.39 |
| S1 | 24/10 | 15819 | 0.29 |
| S1 | 24/11 | 808 | 0.02 |
| S1 | 24/12 | -2373 | -0.05 |
| S2 | 44/16 | -10869 | -0.48 |
| S2 | 44/18 | -9141 | -0.34 |
| S2 | 44/20 | -12238 | -0.46 |
| S2 | 44/22 | -12279 | -0.44 |
| S2 | 44/24 | -10590 | -0.35 |
| S2 | 50/16 | 4021 | 0.10 |
| S2 | 50/18 | 4409 | 0.11 |
| S2 | 50/20 | 17887 | 0.29 |
| S2 | 50/22 | 18012 | 0.35 |
| S2 | 50/24 | 18268 | 0.36 |
| S2 | 55/16 | 8644 | 0.20 |
| S2 | 55/18 | 8186 | 0.19 |
| S2 | 55/22 | 24004 | 0.40 |
| S2 | 55/24 | 24819 | 0.42 |
| S2 | 61/16 | 14373 | 0.29 |
| S2 | 61/18 | 13920 | 0.29 |
| S2 | 61/20 | 31431 | 0.48 |
| S2 | 61/22 | 28735 | 0.42 |
| S2 | 61/24 | 29318 | 0.44 |
| S2 | 66/16 | 17067 | 0.36 |
| S2 | 66/18 | 16893 | 0.36 |
| S2 | 66/20 | 32577 | 0.50 |
| S2 | 66/22 | 31153 | 0.47 |
| S2 | 66/24 | 31037 | 0.48 |

## Sembol dağılımı (full; net USDT, hakem fills'ten saatlik yeniden kurulum, funding dahil)
| sistem | BTCUSDT | ETHUSDT | SOLUSDT | XRPUSDT | BNBUSDT | DOGEUSDT | ADAUSDT | LINKUSDT | AVAXUSDT |
|---|---|---|---|---|---|---|---|---|---|
| S1 | 2043 | -1569 | 12101 | -1156 | -1735 | 16086 | 4390 | 7373 | 1866 |
| S2 | 759 | 1791 | 29520 | -1555 | 2126 | -158 | 1528 | -3333 | -3037 |

## K7 sembol dağılımı (fee 16 + slip 2; net USDT)
| sistem | 1000PEPEUSDT | 1000SHIBUSDT | APEUSDT | APTUSDT | ARBUSDT | BCHUSDT | ETCUSDT | FILUSDT | GMTUSDT | LTCUSDT | MATICUSDT | NEARUSDT | OPUSDT | SUIUSDT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | 6628 | 4089 | 2823 | -1503 | -1537 | -3361 | -2072 | -923 | 866 | -317 | 361 | -1193 | -2134 | 3198 |
| S2 | 2927 | -2213 | 3279 | -252 | 279 | -1476 | -1063 | -1039 | 1429 | -884 | 134 | 9044 | -411 | 12514 |

## Rotasyon null (brüt PnL, fee 10 + slip 2)
| sistem | gerçek brüt | null ort. | null sd | null %95 | p (brüt) | p (net) |
|---|---|---|---|---|---|---|
| S1 | 46802 | 9042 | 17171 | 42241 | 0.0259 | 0.0499 |
| S2 | 35827 | 7259 | 14709 | 37711 | 0.0599 | 0.0818 |

## Bilgi (karar dışı)
| sistem | maks DD (tepe equity'ye oran) | tepe equity (sermaye=1) | geçerli null çekilişi (n_rejected=0) | p (brüt; yalnız geçerli çekilişler) | ilk-1/4 ve son-1/4 net |
|---|---|---|---|---|---|
| S1 | 50.0% | 7.23 | 413/500 | 0.0314 | 5163 / -8173 |
| S2 | 85.0% | 5.89 | 427/500 | 0.0701 | 294 / 3800 |

Geçersiz koşu (n_rejected/funding_missed > 0): [('S2_no_stop', 109.0, 0.0), ('S2_fixed_size', 48.0, 0.0)]; en büyük |recon farkı| = 4.25 USDT; null'larda n_rejected toplamı = 15435.
Kümülatif deneme sayısı (ledger satırları: eski 3291 + bu test 12 = 3303): eleme+hakem.