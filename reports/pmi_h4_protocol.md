# PMI-H4: Funding-only conditional risk ablation

**Protocol status:** Frozen before any scored H4 market-data run. This registers one funding-only, same-source development ablation; it is not a global derivatives result. Historical OI, spot-futures basis, liquidation-event archives and multi-exchange provenance are not verified. No OI/basis/heatmap model is included, and `markPriceKlines` alone is not basis.

## Question and target

Does the canonical funding-stress feature add information about a high-risk week after conditioning on price-only HAR risk features? At each completed UTC daily close, the primary outcome is future RV7 at or above the q75 threshold estimated from the model-fit segment only. Unknown gaps, invalid closes and right-censored outcomes remain unknown. PnL, positions and trading behavior are out of scope.

The experiment uses only funding events already present in the canonical `fundingRate` source. The adapter normalizes each observed rate to an 8-hour equivalent from the source interval. An event is treated as available at its recorded funding settlement timestamp; the existing causal `funding_stress90` feature excludes events at or after the prediction close. This availability assumption and per-symbol coverage must be reported. No external or paid source is authorized.

## Chronology and matched cohort

Use the fixed nine-symbol pre-seal DEV tape, existing seven chronological folds, 2020 warmup and exclusive 2026-04-01 seal. Within each symbol and fold, training labels must mature strictly before the test boundary. Use the H1 target, fit/calibration split and Platt calibration contract.

The comparison cohort requires finite trailing logRV1/logRV7/logRV30, finite `funding_stress90`, and an observed future target. Fit and score both the HAR baseline and HAR-plus-funding candidate on this exact common cohort. The event q75 is computed from the oldest 80% model-fit rows in that matched cohort; only the later 20% training segment calibrates each model. There is one fixed candidate and no threshold or feature sweep.

## Frozen candidates and scoring

Baseline: OLS HAR of future log(RV7) on current logRV1/logRV7/logRV30, standardized from fit rows only. Candidate: the same HAR design plus one current `funding_stress90` input, with the same training-only standardization. Each receives one Platt map with fixed L2=1.0 on intercept and slope, fit on the same chronological calibration rows.

Primary horizon is seven days. Primary metric is matched Brier reduction (`HAR Brier − HAR+funding Brier`); minimum meaningful effect is a 1% relative Brier reduction. A seen-DEV support decision requires a point reduction at least that large, a two-sided 95% paired 28-calendar-day date-block interval wholly above zero (2,000 replicates, seed 20261016), absolute candidate calibration-in-the-large ≤0.05, at least ten distinct positive test dates and positive events in at least two folds. Otherwise report `INCONCLUSIVE` or `NOT_SUPPORTED_ON_SEEN_DEV` according to the frozen evidence; insufficient matched support is `NOT_RUN`.

Report log loss, reliability bins, calibration-in-the-large, precision/recall, matched funding coverage and scores by fold, year and symbol. Aggregate paired asset differences by UTC prediction date before bootstrap. Secondary horizons, 24-hour latency stress and out-of-exchange comparisons are `NOT_RUN` unless separately preregistered with verified source timing; the canonical funding timestamp alone does not prove vendor publication lag.

## Interpretation and limits

Any scored result on this previously examined DEV panel is `EXPLORATORY`, not independent validation. This ablation cannot establish incremental value for OI, spot-futures basis, liquidation maps or other exchanges. If canonical funding coverage, units, QC or as-of timing fails verification, report the funding experiment `DATA_BLOCKED`; do not fill missing funding or proxy basis with mark-price data.
