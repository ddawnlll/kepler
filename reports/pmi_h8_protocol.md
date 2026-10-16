# PMI-H8: Evidence synthesis and transportability

**Status:** Preregistered before any H8 transportability score. This delivery is a provenance ledger only; H8 diagnostics are `NOT_RUN` because no PMI-H1–H7 canonical forecast result is available. Existing synthetic fixtures and the historical ERF-01 atlas do not make an H1–H7 hypothesis eligible for H8 scoring.

## Question and evidence unit

For a specific H1–H7 claim that first meets its own frozen seen-DEV support rule, does the same observable target and baseline-relative information persist across held-out assets, chronological eras, or genuinely unseen future/external data? Implementation, synthetic testing, empirical DEV evidence, and independent confirmation are separate fields. Only a result with complete source, protocol, code, configuration and run provenance can enter the evidence ledger as empirically run.

The unit of evidence is a preregistered hypothesis × target × horizon × data source × validation split. Different target families (risk distributions, high-risk events, q-v1 onsets and spell survival) are not pooled into one score. A model's hidden-state labels cannot validate that model's regime claim.

## Current DEV evidence and eligibility gate

Use only the canonical nine-symbol tape and the pre-seal development period already permitted by Kepler. The 2026-04-01-and-later seal remains closed. The existing survivor-biased symbol list is reported as fixed; no post-hoc universe repair is allowed.

An H1–H7 claim is eligible for exploratory H8 diagnostics only after its own committed protocol and real canonical run have produced all required target, baseline, calibration, support, and uncertainty outputs. A synthetic pass is implementation evidence only. Historical ERF-01 outputs are listed separately as adjacent evidence and cannot be relabeled as PMI-H1–H7 results. If no eligible claim exists, H8 diagnostics are `NOT_RUN`; do not select a “best” candidate from incomplete or synthetic results.

When eligible, reuse only the original matched out-of-fold forecasts and the original precommitted targets. Report symbol, year, fold, direction/event support, calibration, baseline-relative scores, and worst-group performance. Use the existing seven chronological folds; do not create new era boundaries after viewing errors. A leave-one-symbol-out test is admissible only for a candidate whose model was originally pooled across symbols; per-symbol estimators are reported by symbol and are `NOT_APPLICABLE` for cross-symbol model transfer. Do not refit or recalibrate on a held-out symbol's test outcomes.

For pooled candidates, a leave-one-symbol-out diagnostic omits the held symbol from model fitting, transformations, feature selection and calibration, then reports that symbol's untouched chronological test scores. Era diagnostics remain chronological expanding-window tests, with training labels matured before each fold. Calibration-only adaptation and full refit are reported as separate procedures; neither may use final-test labels. Common shocks are resampled as UTC date blocks (28 calendar days, 2,000 replicates, fixed seed 20261016), not as independent assets. Report all group outcomes, including the worst year and worst symbol with support; an aggregate gain cannot hide a subgroup reversal.

## Independent forward protocol

No independent or prospective evaluation may use the sealed G3 period or data dated 2026-04-01 or later from the protected canonical Volume. A genuinely independent evaluation requires a new, explicitly authorized, unsealed prospective collection or an independently sourced external-market dataset with verified as-of timestamps, source hashes, point-in-time instrument membership including delisted assets, and source QC. The source and access route must be approved before collection; do not probe the sealed key or substitute revised/hindsight data.

Before the first forecast or score in that new source, create a hypothesis-specific immutable protocol commit that records the eligible prior H1–H7 claim, primary target and horizon, candidate and baseline, minimum meaningful effect, calibration-only adaptation versus full-refit analyses, event-support gate, multiplicity, chronological split, scoring metric, date-block uncertainty, data-availability cutoff, source and universe manifest requirements, and stopping rule. Its source data must not overlap the explored DEV source period. Preserve a sealed prospective window from model selection. If genuinely unseen data or a hypothesis-specific frozen claim is absent, report `PROSPECTIVE_NOT_RUN`.

`INDEPENDENTLY_VALIDATED` requires a supported precommitted effect, appropriate baseline and calibration, adequate event/group support, a dependence-aware interval meeting the frozen rule, complete source/code/config/run provenance, and an evaluation on data that were unavailable to all development analysis. Otherwise report `EXPLORATORY`, `INCONCLUSIVE`, `DATA_BLOCKED`, or `NOT_RUN` as appropriate. No in-sample development diagnostic, historical ERF-01 result, synthetic test or successful workflow can by itself satisfy this status.

## Deliverable and stopping rule

The current H8 deliverable is a dated evidence ledger with four provenance-backed status fields for #65–#73, exact protocol and PR references where available, the historical ERF-01 evidence kept in a separate row, limitations, and a list of what remains unknown. This synthesis performs no market-data read and produces no model forecast. Cross-symbol/era scores remain `NOT_RUN` until the eligibility gate is met; prospective confirmation remains `PROSPECTIVE_NOT_RUN` until a new authorized source and a specific pre-score protocol exist.
