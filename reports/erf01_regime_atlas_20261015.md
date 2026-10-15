# ERF-01 Regime Atlas — five-year real-data findings (2026-10-15)

**Scientific verdict:** `EXPLORATORY_SEEN_DEV_NOT_INDEPENDENT_CONFIRMATION`. This is a market-state diagnostic, **not** a trading simulation, PnL result or certificate of latent regimes.

**Exact evidence:** [GitHub Actions #38770049440](https://github.com/ddawnlll/kepler/actions/runs/38770049440) (real Modal CPU; 27 original nine-symbol hourly Kline/mark/funding source SHA receipts, source code hash, metrics.json + report.md and original logs in artifact); same run full pinned suite **566 passed, 15 skipped, zero failures, architecture 8/8**. Canonical data came from isolated `kepler-data:/erf01/staging/tape`; G3/seal and production trading were untouched. Artifacts have retention limits; archived Volume `/erf01/regime_atlas_20261015` retains full metrics.

## The observed world — five years, nine symbols

Analysis range **2021-04-01 through 2026-03-31** inclusive, warmup from 2020-01-01. Source: Kepler existing `q` proxy (20-day z20 magnitude threshold 1.25 with efficiency ratio >=0.35). A `q=0` value means **neutral/unclassified**, not necessarily a sideways market. **16,344 finite symbol-days** and **90 unknown symbol-days** across the 9-asset five-year grid.

| q-state | Symbol-days | Uncensored spells | Average days | Median days | 90th percentile days |
|---|---:|---:|---:|---:|---:|
| q=-1, negative directional proxy | 1,420 | 416 | **3.41** | **2** | 8 |
| q=0, neutral/unclassified | 12,999 | 763 | **16.42** | **9** | 41.8 |
| q=+1, positive directional proxy | 1,925 | 358 | **5.36** | **2** | 16 |

In these definitions q=0 accounts for **79.5%** of all observed symbol-days; positive q **11.8%**, negative q **8.7%**. For fully observed spells, at least 8 uninterrupted days were observed in **74/358 positive spells (20.7%)** and **43/416 negative spells (10.3%)**. Do **not** equate this with the separate original 8-of-next-10 onset confirmation gate; it illustrates how restrictive that gate is relative to the observed proxy's short runs. 26 episodes were boundary/gap censored across the three states (no fabricated ending date). A repeated technical indicator is not proof of an economically meaningful, stable market regime.

## Forecasts, not backtest returns

Every state forecast is produced at the end of day `t` for `q(t+h)`; every duration forecast predicts whether the **same uninterrupted q episode** remains after `h` calendar days, using only state and elapsed age at `t`. All models are refit on historical data prior to each of seven untouched-*within-fold* chronological testing blocks (2023–2026). Since this full development panel was previously explored, results are **not fully independent confirmation**.

| Future horizon | Markov future-state Brier | Always-current-q Brier | State-age episode-survival Brier | State-only survival Brier |
|---|---:|---:|---:|---:|
| 3 days | **0.2490** | 0.3205 | **0.1435** | 0.1490 |
| 7 days | **0.3184** | 0.4708 | **0.2007** | 0.2111 |
| 14 days | **0.3405** | 0.6236 | **0.2173** | 0.2287 |
| 21 days | **0.3377** | 0.7092 | **0.1853** | 0.1936 |

Brier is a probability score (lower better). An overconfident always-current-q forecast is an **easy baseline**: beating it does not demonstrate directional regime skill. In fact:

- At 7, 14 and 21 days the hard-class Markov decision predicted **neutral q only**: downtrend recall **0%**, uptrend recall **0%**. Overall 7-day accuracy `79.62%` simply tracks the dominant class.
- At 3 days the hard-class model has uptrend recall `67.4%` but **downtrend recall remains 0%**. Its 3-day Brier is better than an unconditional historic class distribution, but these results do not certify useful directional forecasts.
- Against historical **climatology** (the more demanding comparator), 21-day state-class Brier is effectively tied: Markov `0.3377395` vs climatology `0.3377773`, paired 28-day block-bootstrap improvement interval `[-0.000186, +0.000300]` (includes zero).

The **promising narrow observation** is forecasting **duration of the already observed q-state**, not its directional future label. Across 3/7/14/21 days, the age-conditioned duration model improves Brier over a state-specific age-blind constant-hazard comparator by `+0.00555/+0.01047/+0.01143/+0.00826`; paired 28-day block-bootstrap 95% DEV intervals respectively `[+0.00319,+0.00790]`, `[+0.00536,+0.01487]`, `[+0.00414,+0.01883]`, `[+0.00136,+0.01543]`. This is **small, exploratory predictive information about the current technical proxy's survival**, not independent proof of general market predictability.

## What we learned / next research axis

1. **Ontology first.** Current q is overwhelmingly neutral and directional spell medians are only 2 days. Determine whether that state ontology fits the user's actual questions about trending, transitioning, compression, expansion and volatility regimes. Defining new labels after looking at the data is *new exploration*, not validation of the old q definition.
2. **Duration is promising as a scientific target.** Consider censored time-to-exit estimation, age-conditioned transition hazards and calibration across symbols/years. Already seen DEV comparisons cannot substitute for a future genuinely unseen sample.
3. **Directional onset skill is not established.** Measure per-class precision/recall, transition detection lead times, calibration and baseline-relative 3/7/14/21-day probabilistic scores before proposing any trade. Original M2 had insufficient down onsets and was worse than M1 on 7-day event Brier; do not rewrite that history.
4. **No immediate trading step.** Disable automatically scheduled economic trial runs, preserve all original ledger/history. Keep Kepler research factory PAUSED; do not use PnL, Sharpe, fees or number of trades as success criteria for this research stream.

**Status:** the regime atlas and its tests are working on actual historical data. Predicting the genuinely useful *economic* regime, and showing independently robust forward skill, remain open scientific questions.
