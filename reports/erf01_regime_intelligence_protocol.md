# ERF-01 Regime Intelligence / Regime Atlas V1 — Research scope (15 October 2026)

## Scientific goal

**We are studying market structure, not trading or profitability.** Before selecting any long/short strategy we want to know: What regimes exist under our *operational* definition; how long do their observed uninterrupted episodes last; how reliably can we predict the state at horizons 3/7/14/21 days; and at each day, how likely is the current state to persist for another 3/7/14/21 days?

This document describes a **new exploratory descriptive/forecasting analysis**. It is written after the initial M0/M1/M2 ERF-01 screening data were already seen; historical DEV results cannot count as independent confirmatory evidence. Original failed ERF-01 forecast gate and evidence are immutable.

## Regime ontology (do not overinterpret)

Initially reuse, unchanged, `scripts/erf01.py::make_panel`'s *causal* trailing-20-day state **q**:
- **q=+1**: positive standardized 20-day price displacement `z20 >= 1.25` and efficiency ratio `er20 >= 0.35`.
- **q=-1**: negative displacement `z20 <= -1.25` and `er20 >= 0.35`.
- **q=0**: neither criterion is met, **neutral/unclassified**; **NOT** necessarily sideways/range.
- Missing/incomplete source data or the 20-day warmup => **unknown**, not q=0.

This is a rolling technical proxy, not a validated latent economic regime. The 20-day smoothing strongly influences measured persistence and episode duration. We must not manufacture a claim that market regimes naturally last 20 days, nor reuse future-confirmed event labels as current decisions.

## Dataset and exact timeline

Binance monthly published-SHA-verified original 1-hour klines, mark-price klines, fundingRate, nine previously fixed survivor-biased perpetuals: BTC/ETH/SOL/XRP/BNB/DOGE/ADA/LINK/AVAX.

- **Warmup:** 2020-01-01 onward.
- **Five-year descriptive atlas:** 2021-04-01 through **2026-03-31**, inclusive.
- **Chronological forecast evaluation:** frozen ERF-01 test folds (half-year periods starting 2023-01, ending 2026-03), model inputs fitted only on earlier historical states, never on the fold's test labels.
- **Hard seal:** 2026-04-01 onward is unopened; no access, even for verifying future regimes.
- Use only the existing isolated QA/QC-passed `kepler-data:/erf01/staging/tape` and source checks, not production `/data/tape`; report per-symbol source SHA and QC warnings. Missing or defective data means NOT_RUN, not synthesized values.

## Questions and planned reports

1. **Historical regime atlas:** episodes and duration in actual calendar days, mean, median, p25, p75, p90; number of episodes and censored episodes per state/symbol. Annual state occupancy, missing-data counts. Segment boundary and gaps are *right/left censored*, not actual state exits. A 2021–2026 atlas is descriptive; when computing summary means, exclude incomplete spans and display their count.
2. **Future state forecasting:** at each daily observation `t`, make separate forecasts for `q(t+3)`, `q(t+7)`, `q(t+14)`, `q(t+21)`. Compare a *chronologically fitted* three-state daily Markov transition matrix raised to horizon h with the current-state persistence and unconditional historical climatology baselines. Record 3-class proper Brier score, hard classification accuracy, directional class recall, class confusion matrix, and yearly/fold sample support. Never score a future state absent due to a gap or the seal.
3. **Remaining episode duration:** at time `t` knowing current state and elapsed state-age only, predict the probability that the **same uninterrupted episode** survives h more days. Compare state-specific empirical age-conditioned discrete hazards (right censoring in training respected, deterministic prior smoothing 10) against **state-specific age-blind** constant daily hazard. Score binary Brier for each horizon and observed survival frequency; missing forward paths are excluded, **not** marked failures. *No future duration is used as an input.*
4. **Uncertainty:** paired 28-day moving-block bootstrap across chronological date scores, one-sided fifth percentile and 95% intervals on baseline-minus-method Brier. Correlated assets share block dates, not independent bootstrap rows. Descriptive result and finite-date support are mandatory, and any apparent gain is still exploratory because the DEV data have already been examined.
5. **Interpretation:** distinguish estimating today's proxy q from forecasting q(t+h), and distinguish either from inferring a genuinely useful future market regime. Examine q=0, rising, falling class imbalances; compare persistence-related accuracy against naive baselines, including transition-recall. Forecast Brier improvements alone cannot prove the ontology represents tradeable regimes.

## Frozen V1 knobs

Horizons = **3, 7, 14, 21 days**; states = **-1, 0, +1**, pooled age-hazard pseudo count = **10**; Laplace-smoothed state transition matrix; frozen chronological folds. No dynamic parameter search, trading rules, or fee/PnL scores. Historical observed spell summaries use **fully observed episodes only** and report censoring; forecast survival estimator uses properly censored historical episodes through the start of each test fold.

## Outcome status, scope and guards

- `EXPLORATORY_SEEN_DEV_NOT_INDEPENDENT_CONFIRMATION`: descriptive observations / OOS-within-previously-seen-DEV predictions, not proof of universal market structure.
- `INCONCLUSIVE`: sample too small, baseline not beaten, confidence interval crosses zero, unknown labels, or unreliable episode ontology.
- `PROSPECTIVE_VALIDATED` is impossible without a **genuinely unseen future sample** and precommitted gates. A new regime ontology requires *separate* scientific registration and prospective evaluation; do not tune existing q thresholds using present results and then claim OOS.
- **Trading and PnL are not part of the experiment**, and neither a profitable nor loss-making backtest answers the science question. Trading workflow is removed from its cron schedule, old ledger retained. Factory remains PAUSED; G3/seal/live untouched.

Outputs: `/data/erf01/regime_atlas_20261015/metrics.json` and `report.md` (plus exported CI artifact/committed honest summary). One bounded Modal CPU run is initially used to validate real 5-year results; follow-on research is not automatically turned into arbitrary model search.
