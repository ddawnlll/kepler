# ERF-01 Economic Exploratory Probe V1 — Registered 2026-10-15

## Scope and motivation

The original real pre-seal DEV nine-symbol OOS experiment has **NOT** shown incremental M2 onset-forecast skill (M2 Brier worse than M1; down onsets 20/30 needed). Continued work must not change its recorded verdict or retroactively reclassify seen development data as an untouched holdout.

This protocol defines a **separate, explicitly exploratory economic diagnostic**, fixed in code before this run's results exist. Question: *Do frozen previously generated M1/M2 OOS daily probabilities contain any gross directional swing profitability after the Kepler Numba economic referee applies funding, spread-proxy slippage and taker commissions?* This is not scientific proof of new trading alpha and cannot be used to declare ERF-01 PASS.

## Predeclared family and count

Exactly **eight numbered trials**, indexed by model M1/M2 × directional dominance/threshold × planned hold horizon:

- For each M1 and M2: moderate signal (winning direction probability at least 0.015 and >1.5× opposite probability), 7-day and 21-day maximum hold.
- For each M1 and M2: strict signal (winning direction probability at least 0.03 and >3× opposite probability), 7-day and 21-day maximum hold.

No other threshold, time frame, subset or signal family will be dynamically tuned from the results of these trials. This family is exploratory on **already examined DEV 2023-01 to 2026-03**; eight selection opportunities must be counted. Output is not forward confirmation.

## Causality, data and economics

- Input is the **existing and immutable** `/data/erf01/canonical_20261015/results/oos_predictions.csv`, not fitted on these new trading PnL outcomes. The per-symbol predictions are used **without** labels `y`; check duplicate rows, probability simplex, fixed symbols, DEV-only timestamps and SHA256.
- Load verified 1-hour Binance klines, mark and funding from isolated `/data/erf01/staging/tape` with verified QC receipts. Source is **staging only** and production `/data/tape` remains untouched. Sealed period begins 2026-04-01, never accessed.
- Each forecast date's signal is emitted only after its **23:00 UTC bar closes**. Kepler referee must fill at the **next bar's open**. A position cannot reenter/flip on its time-based exit bar. Positions target ±1,000 USDT notional per symbol with initial capital 10,000 USDT across all nine symbols; absolute gross cap 10,000; no pyramiding.
- Halt each position after a fixed **7 or 21 calendar days** of intended exposure. No future labels, oracle event dates, dynamic score-selection, true-outcome filtering, or market-activity-based parameter changes.
- Real Numba shared-wallet referee includes actual price/mark, actual interval funding, next-open fills, liquidation, tick/lot approximation (signal-independent, price-derived, exact venue precision UNKNOWN). Base assumption **10bps round-trip taker + 2bps round-trip slippage**; stress **16+6bps**. An inverse-direction, same-exposure control is diagnostic only.
- Reconcile Kepler independently assembled hourly funding-adjusted portfolio PnL with referee. Any rejected orders, missing funding, inconsistent ledger or source/data QC => `INVALID`, never silently accepted.
- For each trial persist configuration, model predictions SHA, all nine QC receipts' SHA, code hash, full net/gross/fee/slippage/funding, fills, annual PnL, cost stress and inverse control to a **unique JSON** in Modal Volume. Return to GitHub logs/artifacts. One run consumes at most one new candidate, and checks existence to skip completed work. No duplicates.

## Status vocabulary

- `EXPLORATORY_ONLY_NOT_AN_EDGE_CERTIFICATE`: actual economic computation attempted, results in JSON, **never means profitable or validated**.
- `INVALID`: economic run rejected by strict finance integrity gate; needs repair, not optimization.
- `EXHAUSTED`: all eight recorded trials exist, stop this family. Repeated runs do NOT introduce more trials or relabel outcomes.
- `PROVEN_EDGE` is **not a possible output** of this protocol. Formal candidate would require selection-adjusted statistical nulls, exposure-matched benchmarks and net positive economic returns in an **independently untouched future data window**, plus user-approved sealed-test/live workflow; none is authorized here.

## Unattended resource/trigger limit

GitHub Actions scheduled at **02:00–07:00 Europe/Istanbul** (23:00–04:00 UTC) daily, one job per hour, sequential via concurrency and one CPU-based Modal `modal_app.py` invocation per run. CLI hard timeout **300 seconds** plus GitHub job limit **8 minutes**; one candidate per run, maximum eight total. This is a bounded unattended exploration mechanism, **not a spending guarantee**. Modal provider billing cannot be queried through the GitHub integration, so actual USD cost is UNKNOWN. Do not enable production factory's paused flag, execute G3 or live trade. Exit/halt honestly after the eight tests, and require a new prior-registered idea instead of brute-force rescoring the same dataset.

GitHub run receipts and issue #56 must show authentic status and cannot claim edge on unconfirmed DEV data.
