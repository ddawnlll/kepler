# PMI-H7: Discrete-state versus continuous heavy-tail forecasting protocol

**Status:** Preregistration, committed before any PMI-H7 scored market-data run. The commit containing this file is the protocol SHA; every run receipt must record it. This protocol makes no empirical claim.

## Question and primary estimand

For matched prediction dates and the same observable target, does a small discrete-state model forecast future risk distribution better than a continuous heavy-tailed model? The primary outcome is log predictive density of the observed log(RV7) target defined in reports/pmi_h1_protocol.md: the log of realized risk over the next seven complete UTC daily returns. The q-state is a predictor only; no model is scored against its own inferred or filtered state labels.

## Data and evaluation design

Use the exact H1 canonical DEV source, universe, observation period, seven chronological folds, prediction timestamps, 7-day horizon, gap rules, maturity purge and matched test records. Fit each asset separately. Each fold's training set contains only outcomes matured strictly before that fold's first test timestamp. Per-asset high-risk thresholds are fit on the oldest model-fitting portion of the outer training set and are used only for secondary tail-probability diagnostics. No 2026-04-01 or later data are permitted.

Use a chronological 80/20 split of eligible outer-training rows. Purge model-fit label windows that overlap calibration rows. Fit density models using only the oldest 80%; primary density forecasts require no post-hoc probability calibration. If tail-probability calibration is applied, fit it only on the later 20% training segment. Do not select test dates or alter model settings after scoring.

Fit exactly two fixed candidates, with no hyperparameter sweep:

1. **Discrete:** the existing causal q_v1_proxy (-1, 0, +1) as a discrete observable state, with an add-one-smoothed daily transition matrix fit only on consecutive model-fitting q observations and raised to the seven-day horizon. Fit a Student-t (df=5) distribution for log(RV7) conditional on the future observable q-state in matured model-fitting rows; mix these state-conditional densities using the forecast state probabilities. For each future state, shrink its location as (n*state_mean + 20*pooled_mean)/(n+20). Shrink its residual variance as (state_sum_squared_residuals + 20*pooled_variance)/(n+20). Future q is used only to fit historical training distributions and is never read for a test prediction.
2. **Continuous heavy-tail rival:** Student-t regression (df=5, fixed) for log(RV7) on the same as-of return history summarized as trailing log(RV1), log(RV7) and log(RV30). Fit ordinary least squares coefficients and residual scale on model-fitting rows only. Set the Student-t scale to residual_RMS * sqrt((df-2)/df), so its variance matches the fitted residual variance. No Gaussian-only strawman is a qualifying rival.

All RV features use squared close-to-close daily returns over the named trailing complete days. Fit the regression standardization on model-fitting rows only; zero-variance scales are set to one. Score both candidates on the exact intersection of rows where their densities are finite.

## Scores and frozen decision rule

Primary score is mean log predictive density (higher is better); report discrete minus continuous log density in nats per forecast. Secondary metrics are Brier score for the training-defined 75th-percentile tail event, probabilities derived from each Student-t predictive CDF, five fixed-width reliability bins, fold/year/symbol support, and state occupancy/transition counts. Estimate the primary paired interval by averaging asset score differences per UTC date and resampling 28-day date blocks (2,000 replicates; seed 20261016). Never bootstrap assets independently.

The minimum meaningful density gain is fixed at 0.01 nats per forecast over the Student-t rival. A discrete-model result is SUPPORTED_ON_SEEN_DEV only if its mean gain meets that threshold, the two-sided 95% date-block interval is above zero, and valid forecasts span more than one fold. If tail-event Brier worsens by over 0.01 absolute, report the conflict and do not describe the discrete model as a generally better risk forecast. Sparse support or an interval spanning meaningful gain and zero is INCONCLUSIVE; missing/invalid canonical input is NOT_RUN/DATA_BLOCKED. No criteria may change after scoring.

## Provenance and interpretation

Record protocol SHA, code SHA, canonical input hashes, fixed configuration SHA, data/QC status, fold and per-symbol metrics, event support, runtime and Actions run URL. The expected status on the previously examined 2020-2026 development panel is EXPLORATORY. This experiment cannot prove that discrete states are economic regimes or establish independent forward validity.
