# Arama tabloları (otomatik)
N=88 yapılandırma (arama dönemi 2022-01→2025-01, fee 10 + slip 2, sembol başına notional 1000, 9 sembol toplamı). SR0 (deneme-düzeltme eşiği) = 1.42 yıllık.

## Eleme–hakem uyumu (N=88, fee-baskın olmayan geniş ızgara): Spearman 0.871 (p=3.1e-28); aile içi: donchian 0.94, ema 0.89, tsmom 0.97, xs_mom 0.71, xs_rev 0.60. Öneri eşiği ≥0,8 (doğrulanmadı).

## Aile başına en iyi 3 (arama dönemi net; seçim yanlılığı içerir)
| aile | yapılandırma | net | brüt bps/RT | funding | Sharpe(y) | DSR(N=88) | RT notional |
|---|---|---|---|---|---|---|---|
| donchian | don_80_20 | 9720 | 1504 | -2055 | 0.63 | 0.09 | 78975 |
| donchian | don_10_5 | 9518 | 257 | -1540 | 0.65 | 0.09 | 451628 |
| donchian | don_100_20 | 9293 | 1673 | -1910 | 0.64 | 0.09 | 67465 |
| ema | ema_10_100 | 11099 | 908 | -2474 | 0.54 | 0.07 | 151588 |
| ema | ema_5_100 | 11009 | 618 | -2530 | 0.53 | 0.07 | 223452 |
| ema | ema_50_100 | 8066 | 1238 | -2293 | 0.41 | 0.04 | 84535 |
| tsmom | tsmom_14_1 | 18667 | 182 | -1439 | 1.13 | 0.31 | 1184383 |
| tsmom | tsmom_30_7 | 13124 | 490 | -1933 | 0.73 | 0.12 | 315132 |
| tsmom | tsmom_30_1 | 13009 | 215 | -1836 | 0.79 | 0.14 | 733399 |
| xs_mom | xsmom_7 | 9944 | 180 | -181 | 1.81 | 0.77 | 603973 |
| xs_mom | xsmom_30 | 7479 | 299 | -410 | 1.15 | 0.32 | 275031 |
| xs_mom | xsmom_60 | 5761 | 328 | -333 | 0.84 | 0.16 | 193128 |
| xs_carry | xscarry_7 | 6070 | 149 | 920 | 1.39 | 0.48 | 377464 |
| xs_carry | xscarry_14 | 4233 | 151 | 953 | 0.94 | 0.21 | 236672 |
| xs_carry | xscarry_30 | 2939 | 154 | 827 | 0.50 | 0.05 | 150277 |
| xs_rev | xsrev_3 | -7795 | -24 | 159 | -0.08 | 0.00 | 2226488 |
| xs_rev | xsrev_5 | -8021 | -34 | 114 | -0.87 | 0.00 | 1772754 |
| xs_rev | xsrev_2 | -9327 | -25 | 102 | -1.43 | 0.00 | 2526568 |

Arama döneminde net>0 olan yapılandırma: 80/88; ortalama net 5381; medyan 5768.

## Doğrulama dönemi (2025-01→2026-04): aile-başına arama-seçilmiş yapılandırma, tek atış
| aile | yapılandırma | brüt | net @fee4/9/10/11/16 (slip2) | net @10 slip6 | p(brüt, ortak-ofset null) | Bonf.(×6) p | Sharpe(y) | DSR(N=6) | karar |
|---|---|---|---|---|---|---|---|---|---|
| donchian | don_80_20 | 1302 | 1187 / 1170 / 1166 / 1163 / 1145 | 1152 | 0.319 | 1.00 | 0.30 | 0.48 | yok |
| ema | ema_10_100 | 1988 | 1759 / 1729 / 1722 / 1716 / 1686 | 1698 | 0.399 | 1.00 | 0.27 | 0.47 | yok |
| tsmom | tsmom_14_1 | 854 | 394 / 131 / 78 / 25 / -238 | -133 | 0.382 | 1.00 | 0.01 | 0.36 | yok |
| xs_carry | xscarry_7 | -119 | -31 / -112 / -128 / -144 / -224 | -192 | 0.502 | 1.00 | -0.10 | 0.31 | yok |
| xs_mom | xsmom_7 | -312 | -486 / -622 / -649 / -676 / -812 | -757 | 0.761 | 1.00 | -0.38 | 0.21 | yok |
| xs_rev | xsrev_3 | 1054 | 445 / -85 / -191 / -297 / -826 | -614 | 0.146 | 0.88 | -0.11 | 0.31 | yok |

Doğrulama DSR (N=88 arama eşiğiyle): donchian 0.11, ema 0.10, tsmom 0.06, xs_carry 0.04, xs_mom 0.02, xs_rev 0.04