# PMI-H3: Linked fast/slow observable-state forecasts

**Protocol status:** Frozen before any scored H3 market-data run. This hypothesis concerns forecast distributions of future realized risk; the q-state is a technical observation, not a verified economic regime.

## Primary question and target

Does a small linked fast/slow state model improve a seven-day future realized-volatility distribution forecast over an unlinked fast/slow mixture, when both use only information available at the prediction timestamp? The primary observable target is log future RV7 from the shared PMI target contract. Unknown gaps and right-censored targets are excluded from density scoring and reported; they are not assigned fabricated values.

At each completed UTC daily close, the slow state is the existing causal `q_v1_proxy` in {-1, 0, +1}. The fast state is high/low trailing RV7, where the high threshold is the 75th percentile of current RV7 among matured fit rows for that symbol/fold. The threshold and all model parameters are fit using training rows only. Forecast timestamps and feature publication timestamps are explicit.

## Data and chronological design

Use the fixed nine-symbol canonical Binance USDT-M DEV tape through `experiments/erf01/tape_adapter.py`, the frozen ERF-01 outer folds, 2020 warmup, and the exclusive 2026-04-01 seal. Use only complete consecutive daily closes for future RV7. The nine-symbol universe is survivor-biased. No sealed/G3 source, OI, macro data, PnL, or execution outcome enters the experiment.

Within each symbol and fold, training target labels must mature strictly before test start. Candidate models share identical finite target rows and current-state inputs. Run exactly one fixed configuration per candidate; there is no hyperparameter search or test-fold tuning.

## Frozen candidate forecasts

All distribution candidates use a location-scale Student-t density with df=5 and training-only residual scale. Residual RMS is calculated from each model's fit rows; the Student-t scale is `RMS × sqrt((df−2)/df)`, matching the residual variance to the Student-t implied variance, with a fixed numerical floor of 1e-6. The unlinked mixture uses the equal-weight average of its fast-component and slow-component residual mean squares before this conversion. Candidate locations are:

1. **Unlinked fast/slow mixture:** equal-weight mixture of a fast-risk-class mean model and a slow-q-state mean model; the components are fit separately and are not linked.
2. **Flat combined cells:** a separate mean for each observed slow-q × fast-risk cell, with a pooled fallback only for a cell absent from training.
3. **Linked hierarchical:** ridge location model with a shared intercept, slow-state main effects, a fast-state main effect, and slow-specific fast-state interactions. Fixed L2 is 1.0 for main effects and 10.0 for interactions; the intercept is unpenalized. This is a lightweight partial-pooling benchmark, not an HMM/HSMM or proof of latent-regime recovery.
4. **Continuous HAR:** OLS location using trailing logRV1/logRV7/logRV30 and training-only residual scale.

The **primary comparison** is mean test log-density gain of linked hierarchical minus unlinked mixture. Flat combined and continuous HAR are fixed secondary comparators. Parameter counts and cell/state support are reported so apparent segmentation gains cannot be mistaken for predictive gains.

## Scoring, uncertainty and decision rule

Primary score is paired log predictive density on matched target rows. Report PIT calibration in ten fixed-width bins, central 50/80/95% predictive interval coverage, support, parameter counts, and log scores by fold, year, and symbol. Aggregate correlated assets by UTC prediction date before a 28-calendar-day moving-block bootstrap (2,000 replicates, seed 20261016); do not bootstrap symbols as independent macro observations. If continuous 28-day support is unavailable, no interval is emitted.

Also report each model's mean proper log score within the observed current joint-state cells `q_v1_proxy × fast_RV7_high/low`, with cell support. This is a stratified score of the future observable-risk density conditional on the joint current state, not a multivariate joint probability law across assets; cross-symbol dependence is represented only in the date-clustered uncertainty calculation. It is a prespecified diagnostic and does not replace the pooled primary score.

Minimum meaningful effect is +0.01 nats per target. `SUPPORTED_ON_SEEN_DEV` requires a mean gain at least this large, a two-sided 95% date-block interval wholly above zero, and at least two test folds with valid scores. An interval spanning zero and the meaningful effect or inadequate target support is `INCONCLUSIVE`; otherwise report `NOT_SUPPORTED_ON_SEEN_DEV`. Any result on this previously examined development panel remains `EXPLORATORY`, never independent validation.

## Leakage controls and interpretation

Tests must prove that future perturbations cannot change current slow/fast inputs, the fast-state threshold uses matured fit targets only, all predictions use timestamps no later than their features, train labels mature before test starts, and gaps/censoring are not scored as ordinary values. No future-smoothed hidden states are used. A linked model that changes state segmentation without improving observable future log score does not support predictive superiority. This benchmark is a lightweight test of shared fast/slow information; a full filtered HMM/HSMM remains incomplete.
