# Eleme (vectorbt) ↔ hakem (Nautilus) uyumu

Sembol BTCUSDT, 2022-01-01 → 2026-03-31, 16 fixture konfigürasyonu, gidiş-dönüş fee 10.0 bps.
**Spearman sıralama korelasyonu: 1.000** (öneri eşiği ≥0,8 — doğrulanmadı, eşik konmadı; yalnızca raporlanır). Pearson: 1.000.
Fark kaynakları: eleme lot/min-notional yuvarlamasını, funding'i ve likidasyonu içermez; hakem içerir.

| config | eleme PnL | hakem net PnL |
|---|---|---|
| rev6 | -7893.38 | -7628.96 |
| mom6 | -7780.51 | -7611.61 |
| rev12 | -6755.84 | -6523.12 |
| mom12 | -4322.08 | -4253.95 |
| mom24 | -4156.93 | -4069.68 |
| rev24 | -3388.96 | -3272.42 |
| rev48 | -2995.39 | -2891.69 |
| rev96 | -2822.73 | -2683.30 |
| mom48 | -2342.56 | -2302.37 |
| rev168 | -1831.28 | -1662.19 |
| trend24 | -1404.56 | -1511.65 |
| mom168 | -754.79 | -845.75 |
| mom96 | -729.20 | -768.04 |
| trend168 | -359.67 | -530.30 |
| trend72 | -146.13 | -305.90 |
| trend336 | 433.77 | 232.67 |

Geçersiz hakem koşusu (reddedilen emir / eksik funding; deftere ve korelasyona girmedi): 0 — {}