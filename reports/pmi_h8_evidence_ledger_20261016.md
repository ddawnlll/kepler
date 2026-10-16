# PMI-H8 evidence ledger — 2026-10-16

**Scope:** Provenance synthesis only. No market data were read for this ledger, no PMI market score was generated, and no independent validation is claimed.

Implementation status, synthetic tests, real PMI evaluation and independent confirmation are separate. `TESTED` means software behavior was checked; it does not mean predictive skill. Draft PRs are not merged into `main`.

| Workstream | Frozen protocol | Review branch / PR | Code | Tests | PMI empirical | Independent | Remaining blocker / interpretation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| #65 shared contracts | — | [PR](https://github.com/ddawnlll/kepler/pull/74) | IMPLEMENTED | TESTED | NOT_RUN | NOT_RUN | Shared target/evaluation contracts exist, but no PMI canonical scored run is recorded. PR #74 review branch; synthetic contract coverage only. |
| #66 H1 risk | reports/pmi_h1_protocol.md (d89003c7c956) | [PR](https://github.com/ddawnlll/kepler/pull/74) | IMPLEMENTED | TESTED | NOT_RUN | NOT_RUN | No canonical PMI-H1 forecast metrics or run artifacts are recorded. Frozen 7-day RV7 q75 forecast; candidate/baseline synthetic fold only. |
| #67 H7 distribution alternatives | reports/pmi_h7_protocol.md (6e6008088e55) | [PR](https://github.com/ddawnlll/kepler/pull/74) | IMPLEMENTED | TESTED | NOT_RUN | NOT_RUN | No canonical PMI-H7 density scores or run artifacts are recorded. Synthetic Student-t and transition-cutoff checks only. |
| #68 H2 duration | reports/pmi_h2_protocol.md (97db1f8ea813) | [PR](https://github.com/ddawnlll/kepler/pull/75) | IMPLEMENTED | TESTED | NOT_RUN | NOT_RUN | Canonical PMI-H2 scoring, residual-life coverage and a Modal result artifact have not been generated. Date-block uncertainty and the single frozen label-sensitivity path are implemented and synthetically tested. The H2 event-support deduplication fix is on PR #75. Historical ERF-01 age evidence remains separate. |
| #69 H3 fast/slow | reports/pmi_h3_protocol.md (72af5363ec89) | [PR](https://github.com/ddawnlll/kepler/pull/76) | IMPLEMENTED | TESTED | NOT_RUN | NOT_RUN | No canonical PMI-H3 density comparison or run artifacts are recorded. Small partial-pooling benchmark; not an HMM/HSMM or latent-regime validation. |
| #70 H4 funding ablation | reports/pmi_h4_protocol.md (d83a085c0068) | [PR](https://github.com/ddawnlll/kepler/pull/78) | IMPLEMENTED | TESTED | NOT_RUN | NOT_RUN | Funding comparison is unrun; OI, basis, liquidation-event and multi-exchange sources remain unverified. Funding-only scope; synthetic matched-cohort checks only. |
| #71 H5 pre-onset alarms | reports/pmi_h5_protocol.md (2755a7709eb1) | [PR](https://github.com/ddawnlll/kepler/pull/79) | IMPLEMENTED | TESTED | NOT_RUN | NOT_RUN | Canonical support census is not run; H5 alarm skill is not scored. Support-only runner freezes q-v1 and excludes the last daily close at the seal. |
| #72 H6 vintage macro | reports/pmi_h6_protocol.md (b6fcbff25065) | [PR](https://github.com/ddawnlll/kepler/pull/77) | IMPLEMENTED | TESTED | DATA_BLOCKED | NOT_RUN | No eligible publication-time/vintage source or frozen series roster has been verified. As-of vintage contract has synthetic tests; no revised values are treated as historical releases. |
| #73 H8 synthesis | reports/pmi_h8_protocol.md (d9f1c2f4c7d3) | codex/pmi-h8-evidence-synthesis | IMPLEMENTED | TESTED | NOT_RUN | NOT_RUN | No eligible H1-H7 scored claim exists yet; independent prospective study is not run. This ledger is a provenance synthesis; it performs no market-data read or forecast. |
| LEGACY ERF-01 atlas (adjacent evidence) | — | — | IMPLEMENTED | TESTED | EXPLORATORY | NOT_RUN | Five-year real canonical DEV atlas; q=0 was 79.5%; hard Markov directional recall was zero at 7/14/21d. Age-conditioned q-spell survival improved Brier slightly over a state-age-blind hazard. Seen-DEV, survivor-biased, technical proxy; not a PMI-H1-H7 result or independent validation. The report records 27 per-source SHA receipts; an aggregate manifest SHA is not copied into this ledger. |

## Historical evidence kept separate

The adjacent ERF-01 row refers to the completed five-year canonical Modal atlas, Actions run [38770049440](https://github.com/ddawnlll/kepler/actions/runs/38770049440). Its published status is `EXPLORATORY_SEEN_DEV_NOT_INDEPENDENT_CONFIRMATION`. On the frozen q-v1 proxy, 79.5% of observed symbol-days were neutral/unclassified; the previous hard Markov classifier had zero up/down recall at 7, 14 and 21 days. The age-conditioned survival Brier improvements over a state-specific age-blind hazard were small and exploratory. These results are not PMI-H2 or H5 scores and do not validate an economic regime.

The older ERF-01 onset evaluation also reported 34 up and 20 down OOS events and that M2 was worse than M1 on 7-day event Brier. That result predates the H5 registration and does not establish true 7–14-day pre-onset warning skill.

## H8 disposition

- Same-period cross-symbol and cross-era H8 diagnostics: `NOT_RUN`; no canonical PMI-H1–H7 forecast receipts are available to audit.
- Independent/prospective validation: `PROSPECTIVE_NOT_RUN`; the protected post-2026-04-01 period remains sealed and no new authorized external source is registered.
- Data/cost gates: the canonical Volume, Actions secrets and provider billing were not verified in this session; the manual PMI workflow is not present on `main`, and no connected workflow-dispatch tool is available.
- Next: review/integrate the draft implementation branches through repository governance; dispatch one bounded H1/H7 run only after the manual workflow is available on the default branch and the canonical source, secrets and provider controls are verified. Then consider H8 diagnostics only for claims meeting their frozen support rules.

H8 protocol commit: `d9f1c2f4c7d3489fd2722757439e595caf3aba9c`. The source file records its timestamp-boundary and independent-source rules; this ledger does not open a data source.
