# Kepler Predictive Market Intelligence V2 — implementation handoff

**Date:** 2026-10-16 UTC  
**Scope:** Reviewable implementation and synthetic verification only. No PMI real-market score or independent validation was produced.

## Repository and review state

- Starting `main` SHA: `66efdcfcba7d2fc2960f96edcda09faae48d0c74`.
- Ending `main` SHA: `66efdcfcba7d2fc2960f96edcda09faae48d0c74`. No branch was merged.
- The PMI implementation is in seven open draft PRs. All remain subject to review.

| PR | Workstream | Branch head at handoff |
| --- | --- | --- |
| [#74](https://github.com/ddawnlll/kepler/pull/74) | #65 shared targets; #66 H1; #67 H7; bounded manual Modal workflow | `c5623cf6bc3f9a6326a9a13d0579840115f87a93` |
| [#75](https://github.com/ddawnlll/kepler/pull/75) | #68 H2 duration and survival | `9d5bb8eae71af052075a6faa557fdacbdb99c485` |
| [#76](https://github.com/ddawnlll/kepler/pull/76) | #69 H3 linked fast/slow benchmark | `614b701f0bae4d02340fd26d24f405e0ed2ee206` |
| [#77](https://github.com/ddawnlll/kepler/pull/77) | #72 H6 vintage-aware macro contracts | `63c3daadfac8a9be719abba1310a6b67c75ec995` |
| [#78](https://github.com/ddawnlll/kepler/pull/78) | #70 H4 funding-only ablation | `711bd30f08e1fee19c4be7c7955138a8d8699a09` |
| [#79](https://github.com/ddawnlll/kepler/pull/79) | #71 H5 onset support and alarm evaluation | `dec17f0cf5ba38c470e248e0ff42cb9764090957` |
| [#80](https://github.com/ddawnlll/kepler/pull/80) | #73 H8 evidence synthesis and forward-validation contract | `cd49b5d526588b34eacbb769ff4f1aeb917b2afb` before adding this handoff |

The PRs are drafts. They have not been merged; method review and the protected default-branch workflow gate remain open.

## Issue status

| Issue | Implementation and tests | Empirical status |
| --- | --- | --- |
| #65 shared contract | Partial implementation in #74: causal realized-risk targets, UTC/as-of checks, strict label maturity purge, train-only thresholds, date-block scoring, deterministic receipts, and manifest/protocol controls. Synthetic checks pass. Further review and the ordinary pytest gate remain. | No PMI score; NOT_RUN. |
| #66 H1 risk | Implemented a seven-day primary risk-event runner comparing prevalence, recent-risk persistence, AR(1), and HAR with a train-only event threshold and a distinct calibration period. Synthetic fold tested. | NOT_RUN; no Modal execution or predictive-skill claim. |
| #67 H7 discrete vs continuous | Implemented matched observable log(RV7) forecasts from a small q-proxy transition/Student-t model and a continuous Student-t OLS rival. Synthetic density, tail, and transition-cutoff checks pass. | NOT_RUN; no Modal execution or predictive-skill claim. |
| #68 H2 duration | Implemented censor-aware hazard candidates, age and market-condition comparisons, residual-life summaries, and support-aware scoring. Fixed event deduplication and UTC exit-date alignment; synthetic tests pass. | NOT_RUN; no canonical score or calibrated residual-life result. |
| #69 H3 hierarchical | Implemented a small linked fast/slow partial-pooling risk benchmark against unlinked, flat, and continuous HAR comparators. This is not a full hierarchical HMM/HSMM. | Synthetic TESTED; canonical comparison NOT_RUN. |
| #70 H4 derivatives | Implemented the preregistered funding-only matched ablation using the existing causal funding-stress feature. | Real funding comparison NOT_RUN. Point-in-time OI, validated spot/futures basis, liquidation-event archives, and multi-exchange provenance are DATA_BLOCKED/unverified. |
| #71 H5 early warning | Implemented q-v1 onset/event matching, alarm accounting, and a support-only census path. Synthetic event and support tests pass. | Canonical onset census and alarm scoring NOT_RUN. Statistical adequacy is not established; no warning result is claimed. |
| #72 H6 macro | Implemented release-time/vintage contracts and fixed selection to use the latest vintage visible at prediction time, after filtering by actual availability. Eight synthetic tests pass. | DATA_BLOCKED: no verified point-in-time macro source and vintage roster; no 90/180-day forecast scores. |
| #73 H8 portability | Implemented a provenance-checked evidence ledger that separates implementation, synthetic tests, empirical scores, and independent validation. Seven synthetic ledger checks pass. | Cross-era/market and prospective validation NOT_RUN; future/prospective status remains PROSPECTIVE_NOT_RUN. |

No issue is closed on the basis of these code and synthetic-test deliveries.

## Verification performed

- `python3 tests/test_architecture.py`: PASS, 9/9.
- `python3 -m compileall` on changed scientific modules and tests: PASS.
- `git diff --check`: PASS.
- Direct invocation of individual synthetic test functions: H1/shared 14/14, H2 4/4, H3 6/6, H4 4/4, H5 support 2/2, H6 vintage contracts 8/8, H8 evidence ledger 7/7. H5 event-contract checks were previously recorded as 11/11; the H1/H7 smoke fixture was recorded as 4/4.
- H1/shared test functions were invoked with a minimal local pytest-compatibility shim because pytest is not installed here. This is not a pytest-runner result. The ordinary pytest suite was NOT RUN (`ModuleNotFoundError: pytest`).
- H2's event regression covers multiple landmarks for one exit and the UTC date-keyed bar alignment. H6's added regression covers a late-arriving old vintage alongside a newer visible revision.

These checks establish software behavior on synthetic fixtures only. They do not establish a forecast effect, calibration on market data, or a scientific hypothesis.


- GitHub head checks: combined commit status was empty and the connected commit-run lookup returned no pull-request-triggered workflow runs for PR heads #74–#80 at this check. This is not a passing CI result.

## Modal and market-data record

There is no PMI Actions run URL, Modal invocation, runtime, result artifact, configuration receipt, or scored market metric to report. No real PMI market-data evaluation was executed.

The manual CPU workflow is only in draft PR #74, not the default branch. The connected GitHub interface exposes no workflow-dispatch action. The `kepler-data` Volume, required Actions/Modal secrets, canonical-source cleanliness, and provider spending controls are unverified. No hard dollar cap has been verified. A manual experiment must wait for human review and the workflow to be available from the default branch, followed by a bounded source/credential/cost preflight. The workflow sets a 430-second Modal command timeout and a 15-minute Actions job timeout and serializes PMI jobs across refs.

The only linked real-data run is the historical ERF-01 V1 run [38770049440](https://github.com/ddawnlll/kepler/actions/runs/38770049440). It is not a PMI V2 run and is not independent validation.

## Existing evidence and limitations

The previously published five-year V1 atlas reported q=0 on about 79.5% of valid observed symbol-days and a hard Markov classifier that predicted only neutral at 7/14/21 days, giving zero directional class recall. A survival-age signal was exploratory on previously examined DEV data. None of these historical results demonstrates PMI V2 skill or an economic latent regime.

The available atlas universe is survivor-biased and limited to nine crypto symbols on one exchange. The q-state is a trailing technical proxy. Synthetic tests do not resolve hidden heterogeneity, ontology sensitivity, event dependence, or source publication delays. H3 is a lightweight benchmark rather than a full hierarchical state model. H4 lacks verified historical OI/basis/liquidation archives. H6 lacks a verified vintage source. H5 canonical independent-onset support is uncounted. H8 has no unseen external or prospective evidence. No sealed-period or G3 data were opened.

## Next research steps

1. Review the frozen protocols, target maturity rules, fold purges, calibration split, event-time alignment, Student-t calculations, and date-block inference across the draft PRs.
2. Review and make the bounded manual workflow available on the default branch only through the repository's normal human review.
3. Verify the canonical DEV Volume, exact endpoint through 2026-03-31 UTC, data manifest/QC, Actions secrets, and provider spending limits without exposing credentials.
4. Run one small manual CPU end-to-end H1 preflight, bounded by the workflow timeouts; archive its logs, manifest, source hashes, protocol SHA, runtime, and artifacts under a unique PMI V2 path.
5. Only after preflight succeeds, execute the frozen H1/H7 matched comparison within the stated invocation budget. Preserve negative or inconclusive results and report per-fold/year/symbol support.
6. Continue with H2/H3/H4/H5/H6 only after their individual data and event-support gates pass. Keep H8 cross-era and independent validation separate from seen-DEV research.

Human review remains necessary before merge. Security/data-source and provider-cost verification remain necessary before a real Modal run. No deployment or trading changes are proposed.
