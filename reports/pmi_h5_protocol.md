# PMI-H5: True pre-onset warnings versus post-onset detection

**Status:** Preregistered before the H5 event-support census. The first H5 run is a support-only census and emits no model scores. A scored result is `NOT_RUN` until the frozen minimum event support is met. The q-state is an observable technical proxy, not an economic or latent-regime ground truth.

## Question and target ontology

Can a causal warning score identify an upcoming onset of the frozen `q_v1_proxy` 7–14 calendar days before its onset, under a fixed budget of at most three alarm episodes per asset-year? Recognition within six days before onset and detection on or after onset are reported separately and cannot count as primary early-warning evidence.

Use the existing ERF-01 q calculation without changing its thresholds or smoothing: trailing 20-day return sum-to-root-sum-square ratio `z20`, 20-day efficiency ratio `er20`, and q=+1 when `z20 >= 1.25` and `er20 >= .35`, q=-1 when `z20 <= -1.25` and `er20 >= .35`, otherwise q=0 when both inputs are valid. Missing/invalid q is unknown. This ontology is an operational technical label only.

A candidate onset for symbol s is the first day t with q(s,t) in {-1,+1} after exactly ten consecutive observed UTC days with q=0. Its direction is q(s,t). Confirmation requires all ten following calendar days to be present with finite q and at least eight of those ten q values equal to q(s,t). The event date remains t; the later confirmation date never shifts the onset. A complete confirmation window failing the 8-of-10 rule is a rejected candidate. A gap or incomplete right edge is an unknown/censored candidate, not a negative. A candidate lacking the ten observed neutral days before t is not eligible. No future-smoothed labels or model-inferred states define the event.

## Data, chronology, and support-only gate

Use the QC-validated canonical nine-symbol development tape through the exclusive 2026-04-01 seal, with 2020 warmup. OOS event support is counted only in the seven existing chronological folds (2023-H1 through 2026-Q1), and only when the complete 14-day warning origin window begins inside that same test fold and the confirmation window ends before the seal. The survivor-biased universe and q-v1's technical-proxy limitations must accompany all results. Do not inspect sealed/G3 data.

First run an event census that reports raw candidates, confirmed events, rejected candidates, unknown/gap candidates, left/right eligibility and independent cross-symbol event clusters by fold, year, symbol and direction. Independent event clusters are formed by sorting confirmed OOS onsets by date and assigning each event to the earliest cluster whose first date is within 13 calendar days; otherwise start a new cluster. This fixed anchored 14-day grouping avoids treating same-shock events across symbols as independent.

Scored alarm evaluation is eligible only if there are at least 30 independent OOS date clusters spanning at least four of the seven folds. This is a minimum support gate, not a formal power guarantee. Below it, report `INCONCLUSIVE`, do not score candidate models and do not relax the gate. The support-only run has no predictions, thresholds, model selection or scored outcomes.

## Frozen scored comparison (only after the support gate)

For any later scored phase, origins must be valid completed UTC daily closes and every feature must be available by its origin. Use the same seven chronological test folds, fit-before-test chronology, training-only transformations, label maturity purging and a separately chronological calibration segment. Scored origins are limited to observed days with a complete forward event-matching window; gaps and the seal censor eligibility.

The primary pre-onset window is onset minus 14 through onset minus 7 calendar days, inclusive. Late pre-onset recognition (onset minus 6 through onset minus 1), onset/post-onset detection (onset through onset plus 7), and warning after the target transition are separate secondary categories. Merge thresholded alarm days into one episode when consecutive alarm starts are at most seven calendar days apart. Each alarm episode can match at most one event and each event at most one episode. Matching is chronological, deterministic and prioritizes primary-window pairs, then total matches; report every matched lead time. An episode counts as an early warning only when its start lies in the primary window.

The fixed candidate is a one-sided 14-day rolling CUSUM on the absolute observed `z20` proxy. Center and scale are fitted from the training portion only using median and 1.4826×MAD (scale floor 1e-6); each day's input is `(abs(z20)-center)/scale - 0.5`, negative cumulative values reset to zero, and the score is the sum of positive increments over the current day and prior 13 consecutive valid days. Gaps reset the accumulation. The threshold is selected once on the chronological calibration segment as the lowest score threshold that keeps total alarm episodes at or below three per asset-year; test outcomes cannot affect it.

The comparator is a non-informative constant-hazard schedule: estimate event incidence from matured training events with a Jeffreys Beta(0.5,0.5) prior, then rank calibration/test UTC origins by SHA-256 of the fixed seed plus symbol and date. Select the calibration hash cutoff that attains the same alarm-episode budget and apply it unchanged to test. This deterministic calendar-randomized schedule represents constant hazard at the operational alarm budget; it has no market-predictive input.

Primary metric is unique-event recall for 7–14-day pre-onset warnings at the fixed alarm budget. Minimum meaningful effect is +10 percentage points over the constant-hazard schedule. Support requires the point effect to meet that delta and the lower endpoint of a two-sided 95% paired bootstrap interval over the frozen 14-day cross-symbol onset clusters to exceed zero. All attempted candidates are fixed to the two above; there is no threshold, window, model or label sweep.

Report primary warning precision/recall, lead-time distribution, near-onset and post-onset detections, unmatched false alarm episodes per covered asset-year, fraction of observed time in alarm, and results by fold, year, symbol and direction. Report independent cluster count and paired cluster-bootstrap interval. Confidence intervals must resample common date clusters, not symbols. A post-onset hit cannot be presented as a warning.

## Status and interpretation

The first support census is `EXPLORATORY` development evidence and the scored phase remains `NOT_RUN` until support passes. Passing software tests means `TESTED`, not that the warning hypothesis is supported. Any eventual score on this previously inspected DEV era remains exploratory, not independent validation. Insufficient event support is `INCONCLUSIVE`; missing/dirty canonical inputs are `DATA_BLOCKED`. No result establishes a latent economic regime, profitability, tradability or prospective skill.
