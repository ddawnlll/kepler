# PMI-H6: Vintage-aware macro data gate

**Protocol status:** Frozen as a source and point-in-time data gate. This is not a scored H6 model protocol. No historical macro source, vintage archive, series roster, units or publication-lag schedule has been verified for Kepler's permitted development data; empirical H6 is therefore `DATA_BLOCKED`.

## Scope

Implement and test the reusable contract needed to prevent revised macro observations from entering a historical prediction before that exact vintage was available. A record must include its observation-period end, value, normalized unit, source name and SHA256 manifest digest, source vintage identifier, publication timestamp, vintage timestamp and actual availability timestamp. As-of selection uses `available_at <= prediction_at`; no forward filling creates a value for an unreleased observation.

Only synthetic records are used in tests. They validate the contract and are not macro market data, forecast observations or evidence for H6.

## Deferred scored experiment

The intended target family is continuous future realized risk, with 90 days as the prospective primary horizon and 180 days secondary, against the frozen price-only HAR family. This file does not freeze a macro source roster, candidate feature transforms, minimum meaningful effect or decision rule because no eligible point-in-time source has been verified. No scoring is allowed under this gate protocol.

Before any scored H6 run, a later protocol commit must freeze the exact source and series roster, units and transformations, vintage/release-lag handling, target and horizon, price-only baselines, candidate models, matched-cohort rules, minimum effect, uncertainty method and decision rule. That protocol must precede the first scored run. If no valid vintage source is available, report `DATA_BLOCKED`; do not synthesize or backfill historical vintages.

## Boundaries and interpretation

Use only authorized pre-seal DEV data. No paid data source, new secret, sealed period, revised-as-if-known history or independent validation is authorized by this protocol. A passing synthetic as-of test means the contract is `TESTED`; it does not mean a macro series exists or has predictive value. Five years of crypto data alone cannot establish a reliable six-month regime forecast.
