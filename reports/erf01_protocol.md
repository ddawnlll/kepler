# ERF-01 — Prospective DEV Screening Protocol (15 Oct 2026)

**Status:** new registration only; NOT an earlier preregistration. Original ERF-01 implementation and some development-era evidence predate this document. It cannot turn historical measurements into independent confirmatory evidence.

## Research claim (forecast only)

On frozen nine-symbol survivor-biased development data, can adding volatility/volume/breadth/funding (M2) improve directional **new regime onset** forecasting relative to price-only M1, and can the alarm rule warn of an onset ahead of time? This is **not** an economic trading-edge hypothesis. No G3, live orders or sealed records are authorized.

## Locked before the next scored run

- Source: verified canonical `/data/tape` (klines, markPriceKlines, fundingRate), verified by Kepler QC; never synthesize real data to satisfy a gate. Missing or dirty source => `NOT_RUN`.
- Universe: fixed BTC, ETH, SOL, XRP, BNB, DOGE, ADA, LINK, AVAX perpetual symbols. Survivor bias disclosed.
- Development input: 2020-01-01 through 2026-03-31 inclusive; 2026-04-01 seal, never opened.
- Test folds: chronological semiannual 2023-01 through 2026-03 as frozen in `scripts/erf01.py::FOLDS`; 17-day label purge. Inside each training block, final 20% reserved for out-of-training chronological threshold calibration after 17-day purge. Alarm cooldown seven days per symbol, continuing over adjacent test folds.
- Models: M0 fixed state baseline, M1 price/return/volatility, M2 M1 plus volume/breadth/funding features. Source `scripts/erf01.py` and this protocol SHA recorded in output.
- Scoring: 3 `screen` trials M0/M1/M2 in append-only trial ledger; each configuration identified by code/data/protocol SHA and no `referee`/PnL claim.
- Forecast acceptance: >=30 up and >=30 down confirmed OOS onsets, >=5 nonempty OOS folds, M2 Brier >=5% relative improvement over M1 on paired scored dates, 28-day moving-block bootstrap one-sided fifth percentile >0 (B=2000, frozen seed 20261014); operational alarm <=3 false alerts per asset-year, >=2 median lead days; interpret alert precision/recall alongside counts. Failure => `NO_EDGE` for this screening definition; inadequate valid data/events => `INCONCLUSIVE`.
- No tunable new thresholds, symbol subsets, lookback horizons or model choices based on this run. Posthoc event diagnostics strictly exploratory and cannot rescue rejection.

## Verification and limits

Before any scored run, require complete canonical data, clean QC, seal guard, real chronological temporal/calibration tests, all model screens accounted for and deterministic source/protocol hashes. A synthetic fixture only validates program behavior; it is not evidence for price prediction. Old data observations already influenced the hypothesis; historical DEV cannot become untouched independent confirmation.

**Current block:** `kepler-data` Modal Volume was listed on 2026-10-15 without the expected `/tape` path. Actual DEV run, forecast gate scores and economic/21-day swing trade evaluation remain `NOT_RUN`. Do not create a passing PnL card from a forecast screen.


## Additional evidence audit — fixed before first empirical ERF-01 run (15 Oct 2026)

The original screening rule above is preserved unmodified. An additional *secondary* prospective gate is required before any forecast candidate can be considered for a separate economic test, to prevent a single lucky alarm from passing the low-false-alarm rule.

- Require at least **20 correctly matched OOS alerts**, alert precision **≥25%**, unique event recall **≥20%**, correctly matched alerts across **≥4 test folds** and **≥3 symbols**. None of these requirements can rescue a failed original screen.
- Report all attempts, symbol/fold counts, selected calibration threshold per fold, discarded alerts and original OOS score. `scripts/erf01_edge_audit.py` audits immutable `metrics.json` + `alerts.csv`, rejects missing or duplicate alert receipts, and never returns `EDGE`.
- Even `FORECAST_CANDIDATE_ONLY` is **not** economic evidence: a separate registered max-21-day long/short/flat mapping, deterministic Numba referee including funding/fees/slippage, fee sensitivity, exposure-matched benchmarks, dependence-aware null and multiple-trial adjustment would be needed. No such trial is authorized by this forecast-only protocol; until then `economic_edge=NOT_RUN`.
- Repeatedly optimizing on the same 2020–2026 DEV data consumes selection degrees of freedom; a newly tuned model would be a *new exploratory trial* and require a genuinely unseen future/paper period for independent confirmation. G3/seal is not opened by this change.

## Data acquisition readiness, separate from empirical acceptance

The `kepler-data` Volume's missing canonical tape is an observed prerequisite. Bounded public archive *connectivity and checksum* probes may use old pre-seal months without changing the frozen universe or scoring any forecasts. These probes are NOT a substitute for the full tape, archival QC or economic test. Do not populate a production Volume with unchecked sample data.


## Exploratory full-panel archive diagnostic (committed before any scored download-based run)

To debug the missing canonical Volume tape, one 9-symbol 2020-01 through 2026-03 **Binance published-SHA-verified** archive panel may be evaluated with the same frozen M0/M1/M2 models and fixed chronological folds. It uses **daily kline + fundingRate ZIPs** and is explicitly **not canonical hourly klines/markPriceKlines/QC**. This exploratory diagnostic consumes one recorded M0/M1/M2 screen family (3 model configurations). It may estimate Brier and alert counts to prioritize engineering; it cannot pass the canonical screening gate, repair survivor bias, justify tuning against its test outcomes or prove trading edge. If any month, checksum or input is missing, report `NOT_RUN`. Aggregate all shard manifests into one complete, deduplicated manifest before analysis. No G3, no live order, no economic referee, no production ledger write on Volume.
