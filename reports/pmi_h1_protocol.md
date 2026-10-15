# PMI-H1: Multiscale risk forecasting protocol

**Status:** Preregistration, committed before any PMI-H1 scored market-data run. The commit containing this file is the protocol SHA; every run receipt must record it. This protocol makes no empirical claim.

## Question and primary estimand

Does multiscale risk history improve calibrated forecasts of a high-risk week over simple recent-risk baselines? The primary target is a training-defined high-risk event over seven future UTC daily returns. Direction, PnL, trade count and Sharpe are out of scope.

For asset s at completed UTC daily close t, let r[s,t+j] = log(C[s,t+j] / C[s,t+j-1]). The observable outcome is RV7[s,t] = sqrt(sum(r[s,t+j]^2, j=1..7)). A target is unknown if any of the seven daily closes is missing, non-finite, non-positive, or non-consecutive; it is excluded from every model's matched-date score. Labels mature at the seventh future daily close.

Within each outer fold and asset, the event is RV7 >= q75, where q75 is the linearly interpolated 75th percentile of eligible outcomes in the oldest 80% model-fitting segment only. Freeze that threshold for the fold's calibration and test rows. Never estimate it from calibration or test outcomes.

## Data and time

Use only the verified canonical development tape at /data/erf01/staging/tape through experiments/erf01/tape_adapter.py, after existing per-source hash, timestamp, mark/close and QC checks. Universe is the existing survivor-biased nine USDT-M perpetuals. Use 2020-01-01 onward for warmup and score only completed daily predictions in 2021-04-01 through 2026-03-31. Reject any observation, feature or label reaching 2026-04-01 or later.

Use the seven frozen chronological test folds already defined in experiments/erf01/pipeline.py (2023-H1 through 2026-Q1). At a fold start, training rows must have prediction time before the test start and label end strictly before the test start. This seven-day maturity purge also prevents a training target from overlapping a test prediction. Features may use only values available at their prediction timestamp.

## Frozen candidates and evaluation

Fit each asset's model independently. Use a chronological 80/20 split of eligible outer-training rows: the oldest 80% fits models, standardization and the event threshold; the latest 20% is a calibration set. Purge model-fit rows whose seven-day label window overlaps the calibration predictions. Fit the calibration map once per fold/model and do not refit with test data. If the calibration segment lacks both event classes, that model/fold is NOT_RUN. Do not sweep windows, thresholds, model families or horizons.

The fixed candidates are: (1) per-asset event prevalence from the model-fitting segment; (2) last-risk persistence, whose risk forecast is the trailing seven-day RV; (3) one-scale AR(1), ordinary least squares of future log(RV7) on current log(RV7); and (4) three-scale HAR, ordinary least squares of future log(RV7) on current log(RV1), log(RV7) and log(RV30). RVk is the square root of the sum of squared close-to-close daily returns over the trailing k complete days. Standardize regression features using model-fitting rows only; zero-variance scales are set to one. Convert each risk forecast into an event probability with the same Platt map: sigmoid(intercept + slope * forecast log risk), fit by logistic loss with fixed L2=1.0 on intercept and slope on the later calibration segment. Clip reported probabilities to [1e-6, 1-1e-6]. The primary multiscale event forecast is HAR. The primary comparator is calibrated last-risk persistence. A 14-day outcome is secondary only.

Primary metric: binary Brier score. Also report log loss, calibration-in-the-large, five fixed-width reliability bins, event precision/recall, and support by fold, year, symbol and distinct event date. Evaluate models on the intersection of valid prediction rows. For uncertainty, average paired asset loss differences by UTC date, then use a 28-day moving-block bootstrap over dates (2,000 replicates; seed 20261016); assets on one date are not independent bootstrap units.

The preregistered minimum meaningful effect is a 1% relative reduction in 7-day Brier versus calibrated last-risk persistence. SUPPORTED_ON_SEEN_DEV requires that point threshold, a two-sided 95% paired date-block interval wholly above zero, positive and negative event examples in the calibration data, and positive-event test dates in at least two outer folds. A wide interval, inadequate event support, missing data or a broken calibration fit is INCONCLUSIVE or NOT_RUN as applicable. Other results are exploratory; do not alter the decision rule after scoring.

## Provenance and interpretation

Each receipt records protocol commit SHA, source-code SHA, canonical source-file SHA-256 values, configuration and its SHA-256, fold dates, seed, prediction counts, event counts and run URL. The expected scientific status for this already-seen DEV panel is EXPLORATORY; this experiment cannot establish independent or prospective validation. The existing q_v1_proxy is not an H1 target or economic ground truth.
