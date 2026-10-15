# PMI-H2: Age contribution to uninterrupted state survival

**Protocol status:** Frozen before any scored H2 market-data run. This file's Git commit is the protocol SHA recorded in every H2 receipt. It does not reinterpret the earlier ERF-01 age result, which remains exploratory.

## Primary question and target

Within the existing observable q-state ontology `q_v1_proxy ∈ {-1,0,+1}`, does elapsed age add information to a 14-day uninterrupted-state survival forecast after conditioning on current market risk conditions? The q proxy is a technical observation, not latent economic ground truth. This test does not forecast an expiration date.

At a completed UTC daily close, the primary target is 1 if the current observed q episode remains the same state for the next 14 consecutive, complete daily closes, and 0 if an observed state change occurs first. A missing/incomplete close or unknown q before day 14 censors that landmark; it is not a state exit or a survival negative. Primary scoring uses censor-aware IPCW Brier with a censor curve fitted on training data only, delayed entry represented by current spell age, and event support reported. Horizons 3, 7 and 21 days are secondary.

An episode begins only when a new q value is observed after a consecutive observed day with a different q. Episodes beginning at the start of available history or after a gap have unknown onset and are left-censored. Age-conditioned comparisons use only landmarks with observed onset; the age-blind and market-only controls use that same paired cohort. Left-censored counts and missing-data censoring are reported separately.

## Data and chronological design

Use the nine-symbol survivor-biased canonical Binance USDT-M development tape through the existing `experiments/erf01/tape_adapter.py`; QC errors fail closed, all warnings and gaps remain visible. The scored period and seven outer folds are the frozen ERF-01 folds. Warmup begins in 2020. No observation, feature or label may reach 2026-04-01 UTC. Training risk rows must mature strictly before each test fold. Feature windows are trailing log RV1/RV7/RV30 from the shared H1 implementation and are available at the prediction timestamp.

Risk-set rows are one-day transitions within a known-onset episode. A same-state consecutive next close is a non-event; a different consecutive next close is an exit; a missing day or unknown q censors the interval and contributes no fabricated exit. No future-smoothed or model-inferred labels are permitted.

## Frozen candidate hazards

Fit exactly four fixed discrete-time hazard candidates on identical chronological training risk rows, without test tuning:

1. State-specific age-blind Jeffreys-smoothed exit hazard.
2. Age-only ridge logistic hazard: state indicators and `log1p(elapsed_age)`.
3. Market-conditions-only ridge logistic hazard: state indicators and training-standardized logRV1/logRV7/logRV30.
4. Market conditions plus age: the same fixed covariates as candidate 3 plus `log1p(elapsed_age)`.

For logistic hazards, standardize continuous covariates on fit rows only, set zero-variance scales to one, fit one convex logistic-loss model with fixed L2=1.0, and do not sweep settings. Convert daily hazards into conditional remaining-survival probabilities by multiplying the next 14 daily survival probabilities. Hold current market covariates fixed across the forecast window; advance elapsed age by one day in age-bearing models.

## Scoring and frozen decision rule

Primary: paired 14-day IPCW Brier difference, market-conditions-only minus market-conditions-plus-age, averaged by UTC prediction date. Estimate the observation-censor survival curve from training-only risk rows using delayed-entry ages; state changes are competing events, while data gaps and the tape edge are observation censoring. Test landmarks censored before day 14 receive zero weight. Report censor support and effective weighted support so extreme IPCW cannot hide weak coverage.

Also report IPCW calibration-in-the-large and five fixed-width reliability bins; residual-life 50/80/95% interval coverage on identifiable event-time support; state exit counts, left/right censoring, unique episode and event support; and results by fold, year and symbol. Use 28-calendar-day moving-block bootstrap over date-clustered paired loss differences (2,000 replicates, seed 20261016); do not bootstrap symbols as independent macro observations. If there is no continuous 28-day support, do not emit an interval.

Minimum meaningful effect: absolute IPCW Brier improvement of 0.005. `SUPPORTED_ON_SEEN_DEV` requires the point improvement to meet this threshold, a two-sided 95% date-block interval wholly above zero, and observed state exits in at least two test folds. An interval spanning zero and the meaningful effect, inadequate event/censor support, or unusable IPCW is `INCONCLUSIVE`; otherwise report `NOT_SUPPORTED_ON_SEEN_DEV`. Whatever the result, this already examined DEV panel is `EXPLORATORY`, never independent validation.

## Synthetic controls and limits

Known-answer tests cover onset/left censoring, delayed entry, completed exits, right-censoring, gaps, UTC boundaries, feature availability, maturity purging, future-perturbation invariance, IPCW weights and deterministic date-block resampling. Include a hidden-heterogeneity control in which two fixed-hazard subtypes create an apparent pooled age gradient through survivor selection. Do not interpret an age gradient as causal duration dependence or report historical mean spell duration as expected remaining lifetime.

No OI, spot/futures basis, macro vintages, post-seal data or economic outcomes enter H2. The historical V1 q-age result is not confirmatory evidence. Missing or insufficient real data means `NOT_RUN` or `INCONCLUSIVE`, not a relaxed rule.
