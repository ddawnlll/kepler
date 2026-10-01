# G2 tabloları (otomatik)
Yapılandırma sayısı N=12; DSR eşiği SR0=0.0144 (günlük, yıllık 0.28); null çekiliş sayısı B=300.

| sinyal | evren | brüt PnL | brüt bps/RT | net PnL @fee4/9/10/11/16 (slip 2) | net @fee10 slip6 | funding | p(brüt, ortak-ofset null) | p(net@10) | Bonf. p | Sharpe(y) | DSR | karar |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| carry_funding | çekirdek-5 | -562 | -124.0 | 959 / 941 / 937 / 933 / 915 | 922 | 1586 | 0.302 | 0.259 | 1.00 | 0.06 | 0.33 | yok |
| carry_funding | genişletilmiş-9 | -3066 | -383.7 | -404 / -433 / -439 / -445 / -473 | -462 | 2789 | 0.399 | 0.346 | 1.00 | 0.13 | 0.38 | yok |
| donchian_trend | çekirdek-5 | 2461 | 263.1 | 1711 / 1664 / 1655 / 1645 / 1598 | 1617 | -693 | 0.246 | 0.289 | 1.00 | 0.21 | 0.45 | yok |
| donchian_trend | genişletilmiş-9 | 3615 | 209.5 | 2300 / 2213 / 2195 / 2178 / 2091 | 2126 | -1211 | 0.233 | 0.296 | 1.00 | 0.16 | 0.41 | yok |
| dual_mom_5 | 5 | -910 | -306.8 | -1576 / -1589 / -1591 / -1594 / -1606 | -1601 | -633 | 0.532 | 0.638 | 1.00 | -0.11 | 0.21 | yok |
| dual_mom_9 | 9 | 1431 | 284.9 | 55 / 31 / 27 / 22 / -2 | 8 | -1328 | 0.312 | 0.355 | 1.00 | 0.05 | 0.32 | yok |
| tsmom | çekirdek-5 | 1193 | 390.5 | -363 / -376 / -379 / -381 / -394 | -389 | -1521 | 0.435 | 0.542 | 1.00 | 0.01 | 0.29 | yok |
| tsmom | genişletilmiş-9 | 2034 | 330.1 | -499 / -528 / -534 / -540 / -569 | -557 | -2478 | 0.372 | 0.405 | 1.00 | -0.00 | 0.28 | yok |
| turtle_s1 | çekirdek-5 | 3596 | 162.5 | 2433 / 2322 / 2300 / 2277 / 2167 | 2211 | -1030 | 0.173 | 0.236 | 1.00 | 0.21 | 0.44 | yok |
| turtle_s1 | genişletilmiş-9 | 8366 | 210.6 | 6167 / 5968 / 5928 / 5888 / 5689 | 5769 | -1959 | 0.143 | 0.193 | 1.00 | 0.28 | 0.50 | yok |
| turtle_s2 | çekirdek-5 | 7283 | 791.7 | 5910 / 5864 / 5855 / 5846 / 5800 | 5818 | -1317 | 0.060 | 0.066 | 0.72 | 0.49 | 0.67 | yok |
| turtle_s2 | genişletilmiş-9 | 10132 | 583.0 | 7681 / 7594 / 7576 / 7559 / 7471 | 7506 | -2346 | 0.070 | 0.100 | 0.84 | 0.35 | 0.56 | yok |

## Maliyet kalemleri (fee 10 bps rt, slip 2 bps rt; USDT, sembol başına notional 1000; işareti: PnL'ye etkisi)
| sinyal | evren | brüt fiyat PnL | fee | slippage | çıkış | funding | likidasyon | net | RT notional | işlem (fill) | brüt+funding bps/RT (kırılma maliyeti) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| carry_funding | çekirdek-5 | -562 | -45 | -9 | -2 | 1586 | -31 | 937 | 45286 | 45 | 226.2 |
| carry_funding | genişletilmiş-9 | -3066 | -80 | -16 | -3 | 2789 | -62 | -439 | 79910 | 81 | -34.7 |
| donchian_trend | çekirdek-5 | 2461 | -94 | -19 | -1 | -693 | -0 | 1655 | 93522 | 181 | 189.0 |
| donchian_trend | genişletilmiş-9 | 3615 | -173 | -35 | -2 | -1211 | -0 | 2195 | 172501 | 335 | 139.4 |
| dual_mom_5 | 5 | -910 | -30 | -6 | -1 | -633 | -12 | -1591 | 29656 | 51 | -520.2 |
| dual_mom_9 | 9 | 1431 | -50 | -10 | -2 | -1328 | -14 | 27 | 50235 | 84 | 20.6 |
| tsmom | çekirdek-5 | 1193 | -31 | -6 | -2 | -1521 | -13 | -379 | 30560 | 29 | -107.1 |
| tsmom | genişletilmiş-9 | 2034 | -62 | -12 | -3 | -2478 | -13 | -534 | 61633 | 61 | -72.0 |
| turtle_s1 | çekirdek-5 | 3596 | -221 | -44 | -1 | -1030 | -0 | 2300 | 221255 | 384 | 116.0 |
| turtle_s1 | genişletilmiş-9 | 8366 | -397 | -79 | -2 | -1959 | -0 | 5928 | 397227 | 684 | 161.3 |
| turtle_s2 | çekirdek-5 | 7283 | -92 | -18 | -0 | -1317 | -0 | 5855 | 91999 | 169 | 648.5 |
| turtle_s2 | genişletilmiş-9 | 10132 | -174 | -35 | -1 | -2346 | -0 | 7576 | 173800 | 321 | 448.0 |

## Walk-forward: yarıyıl pencereleri (fee 10, slip 2; net PnL USDT; sabit kural, pencere başında pozisyon devri açık hedef)
| sinyal | evren | 2023-01-01 | 2023-07-01 | 2024-01-01 | 2024-07-01 | 2025-01-01 | 2025-07-01 | 2026-01-01 | pozitif pencere |
|---|---|---|---|---|---|---|---|---|---|
| carry_funding | çekirdek-5 | 117 | -345 | 250 | -2320 | 514 | -667 | 1298 | 4/7 |
| carry_funding | genişletilmiş-9 | 2180 | -4695 | 955 | -5186 | 2254 | -72 | 1519 | 4/7 |
| donchian_trend | çekirdek-5 | -1617 | 917 | 888 | 1447 | -821 | 92 | 489 | 5/7 |
| donchian_trend | genişletilmiş-9 | -1697 | 2441 | 1021 | 2042 | -2974 | 184 | 566 | 5/7 |
| dual_mom_5 | 5 | -228 | -574 | 307 | -1646 | -133 | -819 | 302 | 2/7 |
| dual_mom_9 | 9 | 979 | 873 | -825 | -859 | -888 | -1201 | 764 | 3/7 |
| tsmom | çekirdek-5 | -432 | 942 | 811 | -1225 | -793 | -806 | 821 | 3/7 |
| tsmom | genişletilmiş-9 | 685 | 1942 | -779 | 602 | -2158 | -1545 | 1874 | 4/7 |
| turtle_s1 | çekirdek-5 | -1304 | 2664 | 785 | 1422 | -1325 | 128 | -86 | 4/7 |
| turtle_s1 | genişletilmiş-9 | -1377 | 7947 | 774 | 3152 | -4572 | 1423 | -569 | 4/7 |
| turtle_s2 | çekirdek-5 | -1061 | 2549 | 1115 | 1602 | -514 | 1240 | -7 | 4/7 |
| turtle_s2 | genişletilmiş-9 | -3244 | 5855 | 675 | 3056 | -1358 | 2148 | -191 | 4/7 |

Walk-forward seçimi (eğitim = önceki pencerelerin toplamı; test = sonraki pencere): 2024-01-01: turtle_s1/genişletilmiş-9 → 774; 2024-07-01: turtle_s1/genişletilmiş-9 → 3152; 2025-01-01: turtle_s1/genişletilmiş-9 → -4572; 2025-07-01: turtle_s1/genişletilmiş-9 → 1423; 2026-01-01: turtle_s1/genişletilmiş-9 → -569
Seçilen toplam (OOS) = 209; aynı pencerelerde tüm yapılandırmaların ortalaması toplamı = 182.