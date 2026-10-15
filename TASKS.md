# KEPLER — TASKS (G0–G1, çekirdek)

## ACTIVE SCIENTIFIC PRIORITY — Regime intelligence, NOT trading (2026-10-15)

- **Research question corrected by user:** Before all economic strategy testing, learn how 9-symbol crypto market states behave over five years: regime frequencies, how long distinct q-states last, whether their direction and survival can be forecast at 3/7/14/21 days. Trade count, gross/net PnL, fees, funding, Sharpe and economic alpha are **OUT OF SCOPE** for this stream. Preserve old economic studies as archival exploration but no auto-selection on PnL.
- **Scheduled trading research disabled:** Main's `.github/workflows/erf01-overnight-research.yml` has **NO cron**, only an explicit manual legacy entrypoint; no six more economic candidate runs are automatically scheduled. `factory/policy.json` remains PAUSED. New `.github/workflows/erf01-regime-atlas.yml` is **manual-only**, real Modal CPU, no trading or sealed/G3 access; rerunning identical history on an hourly schedule provides no new knowledge.
- **New preregistration:** `reports/erf01_regime_intelligence_protocol.md` defines proxy ontology (`q=-1,0,+1`), 2021-04–2026-03 five-year descriptive period, 2020 warmup, censored regime spells, seven frozen chronological train-before-test folds and future-state vs remaining-duration forecasts at horizons 3/7/14/21d. Model comparison and bootstrap uncertainty require naive persistence, state climatology, and age-blind duration controls. This is newly registered *after* original historical scores were seen, so NOT independently confirmatory.
- **First actual 5-year atlas run:** [GitHub Actions #38770049440](https://github.com/ddawnlll/kepler/actions/runs/38770049440): **566 PASS / 15 SKIP / 0 FAIL**, architecture 8/8; real 9-symbol validated hourly tape, **16,344 observed symbol-days / 90 unknown**. Full SHA provenance, metrics and report as GH artifact and in `kepler-data:/erf01/regime_atlas_20261015`; durable human report `reports/erf01_regime_atlas_20261015.md`.
- **Duration findings (fully observed spans only):** Negative trend q mean **3.41d** / median **2d** (416 spells); neutral q mean **16.42d** / median **9d** (763); positive q mean **5.36d** / median **2d** (358). Neutral accounts for **79.5%** of finite asset-days; 20-day rolling state thresholds may not represent latent market regimes. Gaps/censoring counted, not fabricated exits.
- **Forecast findings:** 3/7/14/21d Markov state class Brier **0.2490 / 0.3184 / 0.3405 / 0.3377**, but from 7d forward hard predictions were **all neutral**, directional q recall **0%**, and 21d Markov vs climatology difference **negligible**. Age-conditioned uninterrupted-state survival forecast did better than age-blind state hazards by Brier **0.00555 / 0.01047 / 0.01143 / 0.00826** (28-day moving-block DEV intervals positive). This is a *modest potentially useful duration signal about a technical proxy*, not proven prediction of future economic regimes or independent validation.
- **Next research:** First validate or replace the regime *definition* (trend, volatility expansion/compression, neutral, transition) under a new prospective protocol; then test directional/transition lead times, baseline-relative calibrated probabilities and censor-aware duration/survival curves. Do not reinterpret prior original M2 7-day Brier FAIL / sparse down-onset count as passing; do not open sealed dates or launch PnL optimization.

## Predictive Market Intelligence V2 — initial gap assessment (2026-10-16)

- **Already implemented:** `kepler/intelligence/features.py` and `regimes.py` provide causal trailing features, the fixed `q_v1_proxy`, gap-aware censored spells, a Markov transition baseline and age-conditioned survival. `experiments/erf01/atlas.py` and `reports/erf01_regime_atlas_20261015.md` preserve the completed five-year DEV atlas and its honest exploratory result. `tests/test_intelligence_core.py` and `test_erf01_regime_atlas.py` cover core causality/censoring; the manual Modal atlas workflow exists.
- **Partially implemented:** `kepler/intelligence/scoring.py` scores Brier and date-block bootstrap for V1. It does not define shared risk targets, event log-loss/calibration, fold-wise label maturity, or a common prediction receipt; V1 scoring must remain behaviorally stable.
- **Missing:** a reusable as-of/availability contract; observable future-risk targets with gap and horizon handling; train-only event thresholds and purged chronological folds; deterministic V2 provenance; H1 multiscale risk and H7 discrete-versus-heavy-tail comparisons on the same target; and the conditional-age comparison and other H2–H8 experiment gates.
- **Blocked / not established:** canonical market data and Modal credentials are not present in this checkout; empirical runs must use the existing `kepler-data` Volume through bounded Actions/Modal. Verified point-in-time OI, spot-futures basis and macro vintages are not established. No genuinely unseen post-seal period is authorized; independent prospective validation remains `NOT_RUN`.

This assessment uses the existing code and V1 atlas as evidence; it does not count the V1 proxy as an economic ground truth or a V2 result.

### PMI V2 implementation checkpoint (2026-10-16)

- **#65 / shared contract:** `kepler/intelligence/validation.py` now defines UTC prediction/label timestamps, future realized risk with gap/invalid-price/right-censor states, strict label-maturity splits, train-only threshold fitting, as-of lookup, causal RV features and deterministic receipts. `metrics_v2.py` adds probability scores and date-clustered moving-block intervals. Legacy V1 scoring and atlas code were not changed.
- **#66 / H1:** `experiments/market_intelligence/h1.py` implements the frozen 7-day q75 high-risk comparison (prevalence, calibrated last-risk, AR(1), HAR) over the existing seven folds and canonical tape adapter. The protocol predates any scored run. H1 is `IMPLEMENTED`; synthetic fold is `TESTED`; market-data result is `NOT_RUN`.
- **#67 / H7:** the executable comparison now uses the existing causal `q_v1_proxy` only as a predictor, add-one daily transitions, shrunk state-conditional Student-t densities, and a df=5 continuous Student-t OLS rival on matched `log(RV7)` targets. H7 is `IMPLEMENTED`; Student-t known-value checks, state-transition cutoff invariance and a synthetic matched fold are `TESTED`; market-data result remains `NOT_RUN`.
- **#68–#73:** implementation and empirical comparisons remain `NOT_RUN`; expected OI/basis and vintage macro inputs remain unverified as stated in the gap assessment.
- **Local checks:** `python3 tests/test_architecture.py` passed 9/9; compileall and Actions YAML parsing passed; bounded synthetic known-answer harnesses passed for target gaps/censoring, future-feature and transition cutoff invariance, H1 fit/calibration, H7 matched density/tail forecasts, Student-t reference values, Brier and deterministic bootstrap. `pytest` could not run here (`No module named pytest`; offline uv cache also lacks pytest). The uncommitted workflow draft would install locked dev dependencies and run the new pytest file before any Modal job. Canonical data and Modal credentials are not present in the checkout; no real-data run or independent validation is claimed.
- **Modal workflow blocker:** a manual-only H1/H7 Actions workflow draft is at `.github/workflows/pmi-v2-modal.yml`, but it is not committed. The repository guard protects every `.github/*` path and requires the user to open the session with `KEPLER_CORE_UNLOCK=1`; that authorization is absent. No workflow dispatch or Modal market-data run has occurred. The workflow draft fails closed on missing credentials/dirty checkout, has a 430-second command timeout, uses CPU only, validates canonical input through the existing adapter, and writes unique run artifacts. It is kept outside the proposed code commit pending that gate.

## ERF-01 unattended, resumable economics — 2026-10-15

- **Real infrastructure fixes:** Prior GitHub→Modal attempt logs identified a file-build race (live `tee` under Modal's mounted source), stale `scripts/numba_warm.py` direct 23-argument core ABI (new core expects 25), and the build image omitting required `kepler.referee` imports. The Action now writes logs outside source; `numba_warm.py` exercises public `referee.run_portfolio` with funding and next-open/close; `modal_app.py` copies the complete immutable `kepler/` tree *before* warming. First three red runs retained: [race](https://github.com/ddawnlll/kepler/actions/runs/38747199414), [ABI](https://github.com/ddawnlll/kepler/actions/runs/38747393813), [build graph](https://github.com/ddawnlll/kepler/actions/runs/38747848409).
- **Actual Modal economic pass:** [Action #38748300251](https://github.com/ddawnlll/kepler/actions/runs/38748300251) completed genuine nine-symbol 2023–2026 pre-seal OOS-probability M1 → up-to-7-day time-based orders through Numba shared-wallet referee. `m1_moderate_7d` with 10,000 USDT starting capital: **−3,700.96 USDT net**, 16+6bps stress **−4,666.51**, inverse-direction same-exposure control **+1,383.65**. The *original* candidate lost money; inverse positive is exploratory and NOT independent alpha proof. Proof is stored as SHA-addressed immutable JSON in `kepler-data:/erf01/research/erf01_economic_v1/`, uploaded GH artifact and commented to [issue #56](https://github.com/ddawnlll/kepler/issues/56#issuecomment-6194056848).
- **Unattended research cadence and hard stop:** [`reports/erf01_economic_probe_protocol.md`](reports/erf01_economic_probe_protocol.md) registered **8 candidate configurations** before these economic results. `.github/workflows/erf01-overnight-research.yml` runs one previously untested configuration per 02:00–07:00 Turkey hourly tick (max 300s Modal CLI and 10min GitHub job; concurrency single), resumes via Volume JSON; stops doing experiments on `EXHAUSTED`. No adaptive tuning, G3 or live orders. Research factory remains PAUSED. Full test suite [#38748888762](https://github.com/ddawnlll/kepler/actions/runs/38748888762): **559 passed, 15 skipped, 8/8 architecture**. Modal provider actual billing still UNKNOWN, fixed time bounds are not a cost cap.
- **Scientific status:** This work tests downstream economic merit of frozen old OOS forecast probabilities on **seen DEV**; no independent untouched prospect, no multiple-testing-adjusted inferential support. **PROVEN_EDGE=FALSE**, no G3, user account trading, production `/data/tape`, or `factory/policy.json` change. New hypothesis family requires separate registration after 8 trials exhaust; the system does not promise that a real edge must exist.

## ERF-01 continued edge research — measured progress (2026-10-15)

- **Hypothesis boundary:** Continued ERF-01 optimization is exploratory, not a mandate to search the frozen DEV panel until it passes. The primary M0/M1/M2 thresholds remain unchanged; an additional minimum alert evidence audit is committed *before* canonical DEV scores in `reports/erf01_protocol.md` and `scripts/erf01_edge_audit.py`. No production `research_enabled` change, G3, trading, GPU or sealed data.
- **Real historical source acquisition:** [public SHA probe](https://github.com/ddawnlll/kepler/actions/runs/38721692328) and [3-symbol shard](https://github.com/ddawnlll/kepler/actions/runs/38721979390) + [six remaining](https://github.com/ddawnlll/kepler/actions/runs/38722209231) verified **1,304 official Binance daily kline/funding ZIPs** for the nine symbol/manifest development history (through 2026-03), 1,832,594 archive bytes. Archive-only evidence; not yet canonical mark/hours.
- **Measured I/O bottleneck, repaired:** Initial 165-second [full-panel attempt](https://github.com/ddawnlll/kepler/actions/runs/38722598796) **TIMED_OUT** after checking all 1,304 Volume-hosted small source files, before scoring. [Three immutable SHA-addressed bundles](https://github.com/ddawnlll/kepler/actions/runs/38723451654) let the same manifest/source checks run in **2.149 s**, with the [entire unchanged frozen exploratory screen](https://github.com/ddawnlll/kepler/actions/runs/38723780237) finishing in **9.971 s**. Never call the timed-out attempt PASS or infer order-of-magnitude engine speedups from storage-path improvements.
- **First real-market OOS diagnostic — EXPLORATORY, not canonical/edge:** [run 38723780237](https://github.com/ddawnlll/kepler/actions/runs/38723780237) over 7 chronological test folds: **M0 Brier 0.06870004, M1 0.06658255, M2 0.06720886** ([frozen predictions/artifact export](https://github.com/ddawnlll/kepler/actions/runs/38724071206)). M1 improved on M0 by ~3.08%, M2 **worsened vs M1 by ~0.94%**, moving-block bootstrap one-sided p05 **−0.00120338**. OOS confirmed up **34**, down **20** (<required 30 down), forecast gate FALSE, declared verdict **INCONCLUSIVE**. Three model screening ledger receipts were counted in scratch (SHA in run log). **No economic referee/trading/PnL**, untouched confirmation or edge; scientific verdict remains UNKNOWN/inconclusive, not rescued by threshold optimization.
- **Canonical hourly evidence now completed (NOT an edge):** [BTC](https://github.com/ddawnlll/kepler/actions/runs/38723881888) and [remaining eight](https://github.com/ddawnlll/kepler/actions/runs/38724190709) processed official SHA-verified 1h klines, mark-price and funding into `/data/erf01/staging/tape`: **nine symbol QC gates passed with 0 critical ERROR**; warnings/holes are recorded, not filled. [Real canonical OOS](https://github.com/ddawnlll/kepler/actions/runs/38724820208), 7 folds: **M0 0.06870168, M1 0.06657040, M2 0.06725760 daily Brier**; M2 **−1.0323%** relative improvement vs M1, bootstrap one-sided p05 **−0.00126301**, OOS **34 up / 20 down** (<30 down required), forecast gate **FALSE**, scientific verdict **INCONCLUSIVE**. Exact immutable summary at `reports/erf01_data/canonical_oos_20261015.json`; artifact includes scored OOS probabilities. Three screen-only trial receipts counted (ledger SHA in JSON); Numba trading/PnL/fee/funding economic stage and independent confirmation **NOT_RUN**, proven edge **FALSE**. No G3/live/research resume; production `/data/tape` unchanged. Provider bill remains UNKNOWN.

## ERF-01 issue #56 hardening and acceptance (2026-10-15)

- **Corrected:** `scripts/erf01.py::_verify_acquisition` no longer trusts its own acquisition JSON for claimed completeness. It compares the actual symbol × stream × monthly archive set with the frozen manifests, and checks unique records, bytes, SHA256 and Binance published-checksum provenance. A truncated but internally consistent receipt, duplicate/forged checksum, missing/modified file or sealed month now fails closed.
- **New protocol:** `reports/erf01_protocol.md` is dated **today**; it is for *future* DEV-only screening and explicitly cannot certify historically pre-registered evidence. M0/M1/M2, 17-day purge, cooldown, statistical/false-alarm criteria and three `screen` trials are locked without changing past NO_EDGE/INCONCLUSIVE. G3/real-money/economic referee remains unavailable.
- **Verification (final tree):** [GitHub Actions run 38717086742](https://github.com/ddawnlll/kepler/actions/runs/38717086742) reports **544 passed / 15 skipped / 0 failed**, architecture **8/8**. Modal remote CPU test ran **10/10 ERF-01 regressions**, using real Parquet→DuckDB→Kepler tape/QC code and checking incomplete 24h bars, funding, corrupt/missing tape fail-closed. No mock acceptance claim; fixture prices were *synthetic*, not empirical market predictions.
- **Real-data blocker:** `kepler-data` Volume still contains **no canonical `/tape/klines/BTCUSDT.parquet`**, confirmed by same Actions run; full nine-symbol actual DEV backtest, M2-vs-M1 Brier, OOS event/alert performance, economic trade PnL, independent peer review and official provider bill are **NOT_RUN/UNKNOWN**. Factory remains PAUSED; do not close #56 as an achieved edge or restart autonomous research until canonical data and separate acceptances pass.
- **Workflow:** one-time Actions workflow used only for validation, removed from merge candidate after passing. Evidence persists as GitHub Actions logs; no standing CI added.

## Consolidation execution (2026-10-15; supersedes preliminary audit gates)

- **Owner authority:** User explicitly authorized protected financial/core files and the 3000 → 3500 physical-line budget change for this full consolidation. `tests/test_architecture.py` retains per-file 300/architectural-layer constraints. The earlier "no authorization" audit entry below is historical and has been superseded; no claim of independent third-party review is made.
- **Preserved lineage:** Validation branch `integration/pr53-validation-20261015` contains `main` and PR #53 source as both parents; all stacked PR #21–26/#35/#36/#38 original head commits are ancestors through PR #53. PR #57's four source/test files were forward-ported exactly onto the integration base; no historic negative decision was edited.
- **Financial/main reconciliation:** Brought forward main's price-vs-funding close-bar chronology (body T−1ns, settlement T), immediate liquidation fee wallet debit before cross-symbol equity sizing, deterministic and causal sizing, full byte-level code/lock/script hashing, and single-writer Volume event spooling. PR #53's intent/economic identity/receipt and invalid-attempt accounting remain. Added rich invalid-receipt collector/idempotence regression, retained GPU fail-closed retirement (CPU-only).
- **Acceptance evidence:** [Pinned full suite on combined candidate](https://github.com/ddawnlll/kepler/actions/runs/38656268136): **545 passed, 13 skipped, 0 failed**, 22 warnings; **8/8 architecture checks passed**, Python 3.12/Numba CPU. The 13 skips and external snapshot/CUDA availability are **not verified**. Earlier red intermediate test runs remain visible for the audit trail.
- **Science and cost:** No whole-EV1/carry/B300 real-parity certification; no 60s/5min speed claim. Existing historical `NO_EDGE`/`FAIL`/`UNKNOWN` stay untouched. A single ≤110s Modal remote mini-replay against pre-seal BTCUSDT DEV may be used as a narrowly scoped data/runtime smoke check; regardless of result it is **not** whole-experiment parity. Modal provider invoice cannot be read through the current GitHub connector and must remain UNKNOWN unless supplied.
- **Factory:** `factory/policy.json`: research_enabled=false, PAUSED/default review gates unchanged. No new strategy research, G3/seal, keys, live order, ML train, GPU or Nautilus execution.
- **Modal DEV preflight result:** [bounded remote mini-run](https://github.com/ddawnlll/kepler/actions/runs/38656699530) reached a Modal CPU container, but canonical tape loader stopped on `/data/tape/klines/BTCUSDT.parquet` missing. [Read-only Volume inventory](https://github.com/ddawnlll/kepler/actions/runs/38656826599) showed `kepler-data` has no `/tape`, `/pre2022` or `/data` directories; Volume root listed no data. **ACTUAL DEV REPLAY NOT_RUN**, financial main-vs-integrated real-data parity **NOT_RUN**. Do NOT assert DEV data is ready or completed/null tests were run. No G3 touched. Modal remote container attempted one short check; exact provider billing **UNKNOWN**. Tests were constrained to a 110-second remote timeout with GitHub 170-second CLI deadline. This is a source data availability blocker, not an approved waived acceptance test.
- **One-time test infrastructure:** All temporary GitHub Actions workflows were removed from the final branch. Full-run logs above and the empty-Volume preflight remain auditable on GitHub. No standing CI or automatic research trigger was added.
- **Legacy analysis scope:** Older uncalibrated null/bootstrap p-values are not global edge certificates. Cross-margin tiers and exchange-exact liquidation fee remain UNKNOWN. Old ledger files are preserved with partial provenance; retrospective reconstruction cannot make them full receipts.

## Consolidation audit / integration staging (2026-10-15; READ FIRST)
- **Active job:** Evidence-led consolidation; branch `integration/kepler-consolidation-20261015`. Main remains unchanged until human review + merge. Initial main `40ba325ea197ff7add69d851417fe58b546096a5`.
- **Live starting inventory:** 11 open PRs (#21–26, #35/#36/#38, #53, #57), 24 open issues (#10–18, #29/#30/#31/#33/#34, #42, #45–52, #56), 28 branches, with preserved annotated archive tags at `refs/tags/archive/2026-10-14/branch/*`. Repository records not changed during audit; numbers not represented as final.
- **Integration ancestry:** PR #53 head `4a9140060d1008120ad17557a69a31027db8a617` contains all original stacked PR heads (#21–26/#35/#36/#38; GitHub compare behind=0); it has diverged from main (98 ahead, 13 behind). NO raw merges. PR #57 head `ed04a0e4b5b192dfceef2f19162c7bb428ec8bed` has diverged (10 ahead, 9 behind); main changes since its base do not touch ERF01 scripts or tests. Both PRs have missing acceptance evidence.
- **Hard gate:** PR #53 changes `kepler/` size cap 3000→3500, while `ARCHITECTURE.md` and main `tests/test_architecture.py` still require 3000. Issue #51 requires explicit human architecture-policy approval; protected financial/evaluation/ledger code requires session `KEPLER_CORE_UNLOCK` authorization and independent review (#42). No authorization inferred. **Do not port PR #53 protected changes, modify limits or merge main pending gates**.
- **Unchanged-behavior contract set BEFORE any financial integration:** no-funding/non-trigger scenarios: exact net, fills, fill-order SHA, fee, slip and daily PnL; identical config/data/seed receipt deterministic economic ID; deterministic serial-vs-shard outputs including output completeness and idempotent replay; flat zero-trade account remains valid. Parity with historical unchanged snapshots required for any reviewed financial merge.
- **Corrected-behavior contract set BEFORE any financial integration:** E03 funding debit at settlement before margin/equity update causes expected margin response (not false zero-liquidation); E04 sub-minimum intent records `blocked_minimum` but no invented fill; same-hour long/short funding cash-flow is atomic before margin/sizing; missing symbol bars do not defer shared funding; terminal funding/exits and tick/step follow preregistered hand-calculated fixtures. Prior PnL differences must match the independent reference, not retrofitted to output. No financial integration yet.
- **PR / issue triage:** PR #53 is the preferred corrected integration ancestry, **blocked** by #42/#51/#52 and real DEV+Volume parity. #21–26/#35/#36/#38 are superseded candidates after #53 acceptance, not yet closable. PR #57 / #56 are separate tape, prospective-calibration and registration scope; no economic/backtest edge claim. #10–14/#42/#49/#51/#52 have protected-code/financial/ledger gates; #48 has series-shard parity gate; #15/#46 have anti-conservative false-positive/null calibration gaps that remain UNKNOWN, and broad search must remain off; #50 models real exchange limits as UNKNOWN. #16–18 and #47 have historical partial evidence only, no automatic PASS. #29/#30/#33/#34 have legacy and Numba-era performance evidence but required complete parity/goal not shown. #31 cache lacks repeatable improvement justification: `not_planned` candidate; #45 huge permutation replay is out of current compute budget: `not_planned` candidate, without relabeling historical failure as success. Every eventual GitHub closure needs its own linked proof and explanation. No issue closed in the audit.
- **Preflight limitation:** Earlier GitHub→Modal connection smoke demonstrated valid token/remote CPU (run `38653282846`) but **did not** inspect `kepler-data` Volume. No new Modal job launched during audit; Volume access, DEV dataset QC, actual billing and cross-machine parity are UNKNOWN until bounded read-only validation/approved run.
- **Workstreams:** A audit complete; read-only Modal credentials and `kepler-data` volume metadata passed. B exact PR #57 four-file ERF-01 port staged on integration branch, no `kepler/` protected financial change. C bounded GitHub Actions CPU-only smoke verified **8/8 architecture**, **9/9 ERF-01 synthetic**, Python syntax passed with 2 pre-existing invalid-escape warnings (script line 921); Modal list/volume ls read-only successful. Logs: [run 38653998106](https://github.com/ddawnlll/kepler/actions/runs/38653998106). Modal remote compute during this consolidation: **0 jobs / 0 measured Modal cost**. Economic DEV replay, actual tape QC, original model refits, full suite, financial parity, independent review, real provider bill: **NOT_RUN / UNKNOWN**. Disposable workflow is removed before review; run logs remain. **Additional financial regression evidence:** [initial corrected-dependency financial run](https://github.com/ddawnlll/kepler/actions/runs/38654424499) and [reproduction+independent real-byte probe](https://github.com/ddawnlll/kepler/actions/runs/38654616810): **75 passed, 2 skipped, 1 failed** (`tests/test_evaluation_gates.py::test_core_source_change_changes_experiment_hash`). Existing test monkeypatches `Path.read_text`, while `ledger.code_hash` now hashes `Path.read_bytes`: test's attempted synthetic mutation is ineffective. Independent probe monkeypatching `read_bytes` and invoking `evaluate._code_hash` **PASSED**, with marker `CODE_HASH_REAL_BYTES_SENSITIVITY_OK`. **Do not hide the original red test**; correcting an existing protected test requires authorization and independent review; full financial suite and real-data parity still NOT_RUN. D evidence-backed dispositions: [#31](https://github.com/ddawnlll/kepler/issues/31) and [#45](https://github.com/ddawnlll/kepler/issues/45) closed **not_planned** with explicit supporting rationale; other PRs/issues retained pending their criteria and human gates.

Aktif iş: Predictive Market Intelligence V2 (#65–#73) | durum: devam | protokol: reports/pmi_h1_protocol.md + reports/pmi_h7_protocol.md

## Backtest düzeltmeleri (2026-10-14)
- Kullanıcı bu oturumdaki düzeltmeler için çekirdek kilidi şartını kaldırdı; yerel sentetik testleri ve push'u açıkça yetkilendirdi. Gerçek tape / mühürlü dönem kullanılmaz.
- Kapsam: settlement funding ve likidasyon ücreti nakdi; boyutlama nedenselliği/determinizmi; gerçek lot adımı; hakem çekirdeği koruması ve paket hash'i; temiz klonda harici TradingView fixture'larının açık durumu.
- Kabul: elle hesaplı yeni regresyonlar eski kodda kırmızı, düzeltmede yeşil; mevcut ilgili testler ve mimari kontrol geçer; bağımsız inceleme; commit + dal push'u. CI eklenmez.
- Bütçe: uygulama/doğrulama/inceleme bloğu 60 dakika, en çok 100 araç çağrısı; strateji ayarı ve gerçek veri koşusu kapsam dışı.
- **Önce kırmızı:** yeni ilk regresyonlar 15 kaldı / 1 geçti (funding'in boyut/marj/LP etkisi, likidasyon ücreti nakdi, gerçek step, sızdıran/belirlenimsiz boyutlama, çekirdek hash/koruma).
- **Geçti:** Python 3.12, `uv.lock` ile kurulan yerel ortamda `.venv/bin/pytest -q`: **410 geçti, 14 atlandı**; mimari **8/8**; numba imaj ısınma betiği (Modal'le aynı PYTHONPATH koşulu); diff whitespace kontrolü. Tam suite 37,20 sn. Önceki 6 deprecation uyarısı sürüyor (fork ve Pandas concat).
- **Bağımsız inceleme:** `backtest_review` salt okunur inceleme; sabit fiyat funding-likidasyonu ve close gövde/settlement sırası bulguları düzeltildi; elle hesaplı regresyonlar eklendi; son incelemede kalan bulgu yok (ilgili 102 geçti / 1 atlandı, mimari 8/8).
- **Atlandı / UNKNOWN:** TradingView dış snapshot'ları yok (9); opsiyonel TA kütüphaneleri (3), ağ (1), CUDA (1). Dataset tamamen yoksa açık skip; kısmi dataset hata. Modal/tape/gerçek veri paritesi ve GPU donanımı koşulmadı; eski raporlar yeniden yazılmadı. Funding'li GPU çağrısı CPU'ya düşer (testli).
- **Boyut:** boş/yorum/docstring hariç hakem+yapıştırma **730**, veri/QC/mühür araçları **407** satır; `kepler/` fiziksel toplam **2943** (tavan 3000). Strateji/parametre/kart eşiği değişmedi; araştırma N'sine yeni deneme eklenmedi.

(Önceki aktif iş: hakem motoru değişimi Nautilus -> numba (kullanıcı görevi 2026-10-13) | durum: bitti (PR #39) | protokol: BACKTEST.md §6.6)

(Aktif altyapı işi: 7/24 ajan fabrikası sertleştirme | kaynak: `factory/`, `docs/factory.md` §20 | kod/test çalıştırılmadı; VPS kabulü ve canlı açılış bekliyor.)

(Önceki aktif iş: Modal koşu süresi < 5 dk (issue #34: fan-out, kırpma, benchmark) | durum: bitti | protokol: yok (araç/hız işi))

(Önceki aktif iş: ev1_plus_new trade denetimi düzeltmeleri | durum: bitti (push onayı bekliyor) | protokol: reports/fix_progress.md)

(Önceki aktif iş: 10 edge türü → uzmanlar (aile testi, kullanıcı görevi 2026-10-04) | durum: bitti | protokol: reports/edge_experts_protocol.md)

(Önceki aktif iş, EV1 iş planı v1, aşağıda; kullanıcı bu iş için Faz 3 durma kuralını kaldırdı, EV1 kararı hâlâ bekliyor.)

## GitHub katkı akışı (2026-10-13)
`.github/` içinde 4 YAML issue formu (görev, hata, araştırma, ajan davranışı), form seçici, PR şablonu, katkı/güvenlik bildirim yönergeleri ve CODEOWNERS. Ortak akış `AGENTS.md`'de; `CLAUDE.md` mevcut `@AGENTS.md` importunu kullanır. Model bazlı kritik kod şartı MISSION/ARCHITECTURE ile birlikte yetkilendirme + bağımsız incelemeye çevrildi; dosya korumaları değişmedi. Markdown izin listesine yalnız 3 yeni belge yolu eklendi.
- **Geçti:** mimari 8/8, YAML/form alanları ve belge bağlantıları, dar izin listesi/korumalı yol kontrolü, yetkilendirilmiş staged hook, `git diff --cached --check`.
- **Koşulmadı:** Modal suite (uygulama kodu değişmedi); GitHub form arayüzü (şablonlar default dala merge edilince kullanılacak). CI eklenmedi.

## Modal koşu süresi (2026-10-12, kullanıcı görevi "5 dakikanın altına"): devam
Ölçümler ve gerekçeler issue #27–#34 (`#34` izleme). Sonuç değişmeden hız: tüm değişiklikler `scripts/` katmanında; hakem/`evaluate`/`modal_app.py` değişmedi.
- **Fan-out (`scripts/null_fanout.py`, `scripts/null_merge.py`, PR #20'nin doğrulanmış birleşimi + genişletme):** `--script ensemble|carryxs_card`, shard başına süre kaydı (`timing_<lo>_<hi>.json`), gerçek returncode, tohum/şema/u doğrulamalı hash'li birleşim. Modal'de bulunan hata: konteynerde `null_merge` yoktu (imaja eklendi). **EV1 K1 null B = 300: 75 konteyner, 110 sn uçtan uca (bugün ≈ 64–72 dk)**; 300/300 çekilişin tüm alanları `/data/ensemble/null_*.json` (eski sıralı koşu) ile birebir aynı.
- **`scripts/carryxs_card.py` `trade_set` (#29, script katmanı):** pencerede hep düz sembol hakeme verilmez (196 → 155 sembol, tek koşu 322 → 262 sn, net/dolum hash'i birebir). Bar-dizisi kırpma artık `evaluate.run_book(trim_flat=True)` (`trade_set` kaldırıldı; test `tests/test_run_book_trim.py`).
- **`scripts/ensemble.py` primary:** en uzun iş (`abl_no_buffer`) ilk başlar.
- **`scripts/perf_bench.py` (#33):** tekrarlı, pariteli benchmark (ev1 / load / null).
- **Ölçüm (2026-10-12, Modal; aynı konteynerde eski/yeni hakem sırayla, 3 tekrar; konteynerler arası makine farkı 21↔34 sn olduğundan yalnız bu kıyas geçerli; parite tüm koşularda birebir: net, dolum sayısı, hash, funding):** medyan sn eski→yeni: EV1 40→37, EV1 buffer=0 319→261, null u=0 41→35, null u=1 41→30, carry_xs ana 335→178, carry_xs delay=1 330→181 (ağır gürültü: aralıklar örtüşüyor, EV1/null kazancı kesin değil). carry_xs null B=300 fan-out (`--chunk 2`, 150 konteyner): **uçtan uca 267 sn**, 300/300 çekiliş eski sonuçla aynı (`funding_missed` hariç: kırpılan saatleri sayar). EV1 null B=300 110 sn (önceki ölçüm). **Primary aşaması ≤ 5 dk: ölçülmedi/doğrulanmadı** (carry_xs ana koşu tek başına 178 sn). Bar listesi önbelleği (#32) ölçüm kanıtı olmadığı için eklenmedi.
- **Uygulandı (oturum kilidi açık, 2026-10-12):** #27 Nautilus günlüğünü kapat (`LoggerConfig(bypass_logging=True)`), #28 dolum başına `Portfolio.account()`, #32 bar başına Python yükü. #31 ölçümle düzeltildi: `load_dynamic` yalnız 11–17 sn; iş parçacıklı yükleme DuckDB varsayılan bağlantısında çöküyor (denendi, geri alındı).

## Sinyal teşhisi (2026-10-06, kullanıcı görevi): bitti, push onayı bekliyor
Ön kayıtlar `reports/preregistration/{signal_diagnostics,neutral_zone_hysteresis,carry_rebuild}.md` (her biri ilgili koşudan önceki commit'te), rapor `reports/signal_diagnostics.md` (`scripts/signal_diag_report.py` üretir), ham çıktılar `reports/signal_diagnostics_data/`, ilerleme `reports/signal_progress.md`. Dinamik evren (aylık top-20, delist dahil), 9 uzman, 6 ufuk, IC-TS + IC-XS, Holm(108).
- **Sonuç:** IC ölçütünü geçen 4/9 (`carry` yalnızca kesitsel, `lowvol`, `nearhigh`, `volrev`); `trend` ve `xs_momentum` ham p ≈ 0,005 ama Holm'da kaldı (kural gereği AT; kullanıcı kararı gerekir); trend zaman serisi IC'si ≈ 0 (9 sembolde pozitif görünüyordu). 7 bağımsız fikir (küme). Faz 2.1 nötr bölge + histerezis ÇALIŞMADI (iki çekirdekte); Faz 2.2 `carry_xs` ön elemeyi geçti (net +2 358, Sharpe 1,24; netin %84'ü bull; K1–K9 koşulmadı).
- **Kod:** `scripts/signal_diag*.py`, `scripts/signal_phase2*.py`, `scripts/signal_data_inventory.py`, `kepler/experts/carry_xs.py` (REG'e eklenmedi), testler `tests/test_signal_diag.py`, `test_carry_xs.py`, `test_signal_phase2.py`.
- **Deneme sayısı:** önceki N = 4 775; bu iş +315 (muhafazakâr, betimsel dahil) → 5 090; birincil sayı +138 → 4 913. Defter `reports/signal_diagnostics_data/trials*.jsonl` ve `phase2/ledger_phase2_*.jsonl` (`ledger/*` ajan tarafından yazılamadığı için ayrı dosya).
- **`carry_xs` K1–K9 kartı (2026-10-06, kullanıcı isteği "edge var mı"):** ön kayıt `reports/preregistration/carry_xs_card.md` (`1873adb`), sonuç `reports/carry_xs_card.md` (`scripts/carryxs_card_report.py`). **Karar NO_EDGE (K1 sınırda kaldı):** rotasyon null'u brüt p = 0,056 (eşik 0,0167), DSR 0,989; K2 (alfa t 3,0), K3 (fee 16 + slip 6'da net +2 050), K4, K5, K6, K8 geçti; K7 koşulamadı, K9 kaldı (bull payı > %80). 'Edge kanıtlandı' ve 'edge yok' denemez. N +1 → 5 091 (muhafazakâr).

## Edge ailesi: 10 edge türü → 9 uzman (2026-10-04/05; kullanıcı görevi "hepsini yap"): bitti, ADAY yok
Ön kayıt `reports/edge_experts_protocol.md` (`e76cf5d`), sonuç `reports/edge_experts.md` (+ `reports/edge_experts_data/<uzman>/`). Defter satırları Modal Volume'da (`/edge/<uzman>/ledger_<uzman>.jsonl`), repoya taşınmadı (`ledger/*` ajan yazamaz; kullanıcı kilidiyle taşınır). Kullanıcı bu iş için "Faz 3 kararından önce yeni koşu yok" kuralını kaldırdı; Faz 3 kararı ve EV1 dondurma hâlâ bekliyor.
- **Sonuç:** ZAYIF 3 (`trend`, `xs_momentum`, `nearhigh`: hepsi momentum ailesi, hepsinde K9 kalıyor), NO_EDGE 6 (`carry`, `bollinger` [geçersiz koşu: hesap bitti, deftere yazılmadı], `lowvol`, `fundcrowd`, `volrev`, `orderflow`). Ensemble'a giren yok (kapı: K1+K2+aile düzeltmesi+M1+M2; `nearhigh` M1'de kaldı).
- **Koşulamayanlar:** gerçek maker/likidite (emir defteri yok), haber/NLP (veri yok), execution (uzman değil); volatility selling (opsiyon verisi yok). Vekiller etiketli.
- **Kod:** 6 yeni uzman `kepler/experts/`, `Params.expert/xp/flip`, `market_state` `dvol`/`tbr`, `scripts/ensemble.py --expert`, `tests/test_edge_experts.py` (22). EV1 yolu değişmedi: günlük PnL birebir (net 8 297,33; 5 561 dolum).
- **Deneme sayısı N:** 4 119 + 8 = **4 127** (Bollinger yazılmadı).
- **Hazır bileşimler (2026-10-05):** `ensemble.PRESETS` (`ev1` varsayılan, `all9_equal`, `ev1_plus_new`). `ev1_plus_new` keşifte Sharpe 1,89 / maks DD %6,8 (EV1 1,45 / %9,7) ama kanıt değil; varsayılan değişmedi, K-kartı koşulmadan değiştirilmez.
- **Yapı (2026-10-05, kullanıcı itirazı "hiyerarşik karmaşa"):** ensemble tek altyapı; uzmanlar takılabilir üye, bileşim `Params.names/weights`; EV1 = varsayılan bileşim. `expert=` yalnızca tek üyeli bileşim kısayolu. EV1 ve tek uzman çıktısı birebir aynı (günlük fark 0,0), `tests/test_ensemble_compose.py` (4).
- **Keşif eki (2026-10-05, kullanıcı kararı: ön kayıt yok, stop şart):** `scripts/mr_explore.py` (stoplu, rejim kapılı saatlik mean reversion) + `scripts/mr_events.py` (olay çalışması); sonuç `reports/edge_experts.md` "Keşif eki". Özet: kapısız hepsi hesabı bitirdi; range rejimi + hacimsiz uç kapısıyla brüt pozitif ama maliyet yiyor (stopsuz net +937, stoplu −3 418, dönemler kararsız). Ledger dışı, N'ye girmez.
- **Trade denetimi (2026-10-05, kullanıcı isteği):** `scripts/trade_audit.py` (Modal, veri) + `scripts/trade_audit_report.py` (PDF, LLM'siz); çıktı `reports/trade_audit.pdf` (+ `reports/trade_audit_data/`); EV1 @ $1 000. Nautilus hesaplayıcılarıyla çapraz kontrol (Sharpe/Sortino/DD/oynaklık/kazanma/beklenti aynı; pozisyon sayısı 1 242 = 1 242). Test: `tests/test_trade_audit.py`. Mutabakat farkı 0,034 USDT (`report.hourly_pnl` bilinen küçük fark). **Tek dosya, uzman bazlı (kullanıcı isteği):** `reports/ev1_new_trade_audit.pdf` (= `ev1_plus_new` bileşimi, 9 uzman; Bölüm II uzman bazlı genel bakış + her uzman için ayrı sayfa: tanım, tek başına K-kartı, bileşim içi rol, grafikler; Bölüm III ensemble genel analizi). Bileşim raporları: ev1 / ev1_plus_new / all9_equal (`reports/trade_audit_data/<bileşim>/`; ev1_plus_new için 9 leave-one-out koşusu `loo/`). Maliyet duyarlılığı tablosu (doğrusal yeniden hesap), uzman atfı, tek başına uzman tablosu, bileşim karşılaştırması eklendi. Genişletilmiş sürüm (19-20 sayfa): drawdown tablosu, getiri dağılımı/BTC beta, long/short maruziyet, sinyal kalibrasyonu, sembol incelemesi, MAE/MFE zamanlaması, karşı-olgusal stop ölçümü (saatlik gerçek pozisyon profiliyle; yeniden kurulum 922,6 vs hakem 918,3 USDT).
- **Trade denetimi düzeltmeleri (2026-10-06, kullanıcı görevi; iki bağımsız inceleme sonrası):** özet ve tablo `reports/audit_fixes.md`, ilerleme/ön-koşu kararları `reports/fix_progress.md`, rapor `reports/trade_audit.pdf` (+ `reports/trade_audit_data/fix/`), ön kayıt TASLAKLARI (koşulmadı) `reports/preregistration/`. Nedensellik: sızıntı yok. Birincil metrikler sabit sermaye (Sharpe 1,86; DD %6,8); 2025+ Sharpe 0,12. MEXC kuralları `contract/detail` ile doğrulandı; asgari uygulanabilir sermaye $2 500. Defter sayımı N = 4 775 (TASKS'taki 4 127 eksik: pre2022 648 satırı Volume'da). DSR(N=4 775) ≈ 0; seçim prosedürü yazılı olmadığından walk-forward yapılamadı. Hayatta kalma: delist perp'ler veride var; dinamik evrende Sharpe 0,82–1,04. Ölçüm koşuları deftere/N'ye girmedi. Hakem/korumalı çekirdeğe dokunulmadı (Nautilus günlük sessizleştirmesi script içinde sarmalandı).
- **Açık:** BACKTEST.md günlüğü (korumalı; `dvol`/`tbr` [VAR] notu). `evaluate.code_hash` uzman dosyalarını kapsamıyor. Ters yön (Bollinger −F net +8 025) post-hoc: yeni ön kayıt olmadan kullanılmaz.

## İş planı v1 (2026-10-04): EV1'i anla, gerçekliğe bağla, karar ver

**Hedef:** ~4 hafta içinde EV1 (ana sistem) için kanıta dayalı tek karar: **ADAY → G3 → küçük canlı (H5)** ya da **NO_DEPLOY**.
Yeni uzman avı bu planın merkezi değildir; her yeni hipotez Faz 1'in teşhisinden çıkmalı (MISSION kural 4, 11).

**Çıkış noktası (ölçülmüş):** EV1 net +8 297 / 10 000, 6 yıl; Sharpe 1,45, yıllık %13,8, oynaklık %9,5, maks DD %9,7; maliyetler brütün ≈ %10.
Zayıf yanlar:
- Netin %60'ı 2020–21'de (2022–26 Sharpe 0,81, alfa t 1,60; bu dönem için null koşulmadı).
- Tasarım görülmüş veriyle yapıldı; K9 kaldı (range −895).
- Ortalama brüt pozisyon 0,15× sermaye.
- $500 hedef boyutları MEXC minimumlarının altında kalabilir (`reports/account_reality.md`, doğrulanmadı).
- Veri denetimi kırmızı (`reports/data_audit.md`).
- Deneme sayısı repo 4 117 / Modal 5 434 (`reports/trial_inventory.md`).

| Faz | İş | Bitti sayılması için (kanıt) | Bağımlılık / kim | Durum |
|---|---|---|---|---|
| **0 Zemin** | 0.1 Modal erişimi bu ortamda | `modal run ... pytest -q` yeşil | kullanıcı: token | ☑ 2026-10-04: token ortamda, `modal` 1.6.1 (`modal[api-proxy-support]`) proxy altında çalışıyor; Modal'de 285 geçti, 4 atlandı, 9 kırmızı (hepsi 0.6: TradingView fixture'ı yok) |
| | 0.2 Deneme sayacı tek kaynak (N) + defter tek yazar (flock Volume'da çalışmıyor) | N tanımı yazılı; iki konteyner aynı deftere yazamıyor (test) | çekirdek (ledger): kullanıcı kilidi + bağımsız inceleme | ☐ |
| | 0.3 Veri kırmızılarının EV1'e etkisi: işaretli barlar/boşluklar/mark–last ayrışması/funding aralığı EV1 pozisyonlarına ne kadar değiyor | etkilenen PnL payı tabloda; eşik ön kayıtlı | 0.1 | ☐ |
| | 0.4 Bugünkü mimari commit'lerinin bağımsız incelemesi (`a2de714`, `4a8ea18`) | bulgular giderildi/belgelendi | kullanıcı + `arch-reviewer` | ☐ |
| | 0.5 Sızıntı mutantları (V8 LEAK fikri): bilinen 6–10 sızıntı (shift(-1), center, günün nihai hacmi, ileri ffill…) `audit` tarafından %100 yakalanıyor | `tests/test_leak_mutants.py` yeşil, her mutant kırmızıya düşüyor | – | ☐ |
| | 0.6 `tests/data/tradingview` `.gitignore`'da (`data/`): TV doğrulaması temiz klonda koşmuyor (Modal'de 9 test bu yüzden kırmızı) | fixture yeniden üretilip repoya girer ya da test fixture yoksa açıkça atlanır | kullanıcı: mevcut test dosyası korumalı; fixture TradingView'den yeniden alınmalı | ☐ |
| **1 EV1 adli analiz** (strateji değişmez; sonuçla EV1 ayarlanmaz) | 1.1 Uzman PnL atfı (E1/E2/E3 + etkileşim artığı) | toplam = net (mutabakat) | 0.1 | ☐ |
| | 1.2 Ayrıştırma küpü: sembol × yıl × rejim × uzman; brüt → fee → slip → funding | tablo + toplamlar netle birebir | 0.1 | ☐ |
| | 1.3 Pozisyon dönemleri: giriş gecikmesi, MFE/MAE, tutma, çıkışta geri verilen; karşı-olgu (işlem yok / +k gün tut / erken çık), yalnızca ölçüm (V8 Outcome Cube) | dönem tablosu + "para nerede kaybediliyor" özeti | 1.2 | ☐ |
| | 1.4 Risk kullanımı: gerçekleşen oynaklık/τ, brüt kullanım, tampon ve IDM etkisi | tablo | 0.1 | ☐ |
| | 1.5 Sönme testi: 2022-01 → 2026-04 için ayrı rotasyon null'u + DSR (ön kayıtlı not; N +1) | p, DSR raporda | 0.2 | ☑ 2026-10-05 `reports/ensemble_decay.md` (ön kayıt `d6bb74a`): **KANITSIZ (W2)**: brüt p 0,0100 geçti, DSR(W2) 0,926 < 0,95 kaldı; N +1 (ledger 4 119) |
| **2 Hesap gerçekliği** (paralel) | 2.1 MEXC kontrat kuralları (9 sembol: tick, lot, minVol, contractSize, fee) | `account_reality_data/symbol_rules.csv` doğrulanmış | kullanıcı (proxy 403) | ☐ |
| | 2.2 Gerçek lot/minimumla EV1 $500 ve $1k/$2k/$5k koşuları (bilgi) | red sayısı, 10k'ya göre takip farkı | 2.1, 0.1 | ☐ |
| | 2.3 Asgari uygulanabilir sermaye ve sembol listesi | tek cümle karar önerisi | 2.2 | ☐ |
| **3 Karar noktası** | K9 / ZAYIF: (a) EV2 ön kaydı, (b) ZAYIF kabul → NO_DEPLOY, (c) K9 eşiği (yalnızca sonraki test için) | karar MISSION/TASKS'a işlendi | kullanıcı; Faz 1–2 bitince | ☐ |
| | EV1 kodunu ve parametrelerini dondur (hash + tarih): ≥ dondurma tarihi gelen veri gerçek ileriye dönük test olur | dondurma kaydı defterde | kullanıcı onayı | ☐ |
| **4 EV2** (yalnız 3a seçilirse) | Faz 1'in teşhis ettiği tek mekanizmaya yönelik en çok 3 denemelik ön kayıt (ör. rejime göre trend ağırlığı, risk bütçesi τ, delta-nötr carry). `reports/bollinger_protocol.md` taslağı yalnızca teşhis range kaybını trend whipsaw'a bağlarsa aday | K1–K9 kartı; ADAY → G3 | Faz 3 | ☐ |
| **5 Doğrulama + canlı** (yalnız ADAY) | G3 mühür tek atış; MEXC emir adaptörü + mutabakat + kill switch; küçük canlı (H5) | G3 kararı; canlı ilk 30 gün mutabakatı | kullanıcı komutu | ☐ |
| **6 Hipotez hattı** (sürekli, bütçeli) | Kaynak sırası: yapısal mekanizma (funding/basis, OI/likidasyon verisi: Binance arşivinde olup olmadığı doğrulanmadı) > kitap kuralları. Çeyrekte en çok 3 ön kayıt; durma kuralı: 3 ardışık NO_EDGE → kaynak değiştir | ön kayıt + rapor | Faz 3'ten sonra | ☐ |
| **7 Altyapı** (düşük öncelik) | WP1 (Zone Fade arayüze), `portfolio.size` + `risk.py` birleşimi (C), fabrika F2/H4 **ADAY çıkana kadar dondurulur** | – | – | ☐ |

**Kullanıcıdan gereken:** Modal token (0.1), çekirdek kilidi + bağımsız inceleme (0.2, 0.4), MEXC kural çıktısı (2.1), K9 kararı ve EV1 dondurma onayı (Faz 3).
**Durma kuralı:** Faz 1–2 bitince Faz 3 kararı verilmeden yeni strateji koşusu yapılmaz. Her faz sonunda TASKS güncellenir, commit + push.

Bu dosya görev planıdır, spec değil. Hedef, kapılar ve kurallar `MISSION.md`'de; sistem haritası
`ARCHITECTURE.md`'de. Çelişki olursa o iki belge kazanır; çelişkiyi raporla.

Yeni ajan: bu listeyi kendi görev sistemine aç, kendi planla, işi sırala ve böl. Aşağıdaki görevler
**ne** bitmeli ve **ne zaman bitti** sayılacağını söyler; **nasıl** yapacağın sana ait.
İlerlemeyi her görev bitince bu dosyadaki tabloda güncelle ve commit + push et (yüzdeler sana ait
tahmin; ama her "yapıldı" işareti için kanıt dosyası/test adı yaz). Başka bir ajan (Hermes) buradan
devralacak.

## KEPLER TOPLAM DURUM (tek bakışta; ARCHITECTURE'daki 10 sistem)

Durum: ☑ çalışıyor ve testli, ◐ kısmen, ☐ yok. "Çalışıyor" = gerçek veride koşuldu veya testle kanıtlı.

| # | Sistem | Durum | Ne var / ne yok |
|---|---|---|---|
| 1 | Veri hattı | ☑ | 2022-01 → 2026-03, 179 sembol, QC raporu, sha256 manifest, mühür ayrı (G0) |
| 2 | Sinyal | ☑ | `kepler/signals.py`: 6 kitap sinyali (Turtle S1/S2, Donchian Trend, tsmom, dual momentum, carry→funding), parametreleri `reports/book_signals.md`'de veriye bakmadan sabit; tests/test_signals.py (12: elle hesaplı kural + nedensellik) |
| 3 | Risk motoru | ☑ | `kepler/risk.py`: vol hedefleme, kaldıraç tavanı, rebalance bandı, kill switch; `evaluate(size=, kill_dd=)`; N-boyutlama/piramit/birim sınırları (`turtle.py`); `Spec.equity_scale` (equity'ye göre ölçekleme) + portföy kill switch (`run_book(kill_dd=)`); tests/test_ops.py, test_turtle.py, test_portfolio.py (elle hesaplı). Gerçek veri: tam Turtle S1/S2 (6 deneme) + BTC `vol_target` duman testi (3 deneme), `reports/backtest_completion.md`. Parametreler ayarlanmadı |
| 4 | Backtest/hakem (yürütme+muhasebe) | ☑ | Nautilus hakem gerçekçi: sonraki-bar açılış dolumu, zorunlu slippage (`evaluate`), açık pozisyon çıkış maliyeti, likidasyon çifte sayımı yok, likidasyon sonrası hesap ölü (tests/test_realistic.py, test_referee.py). Tek sembol: portföy = sembol başına bağımsız koşu toplamı (G2'de) |
| 5 | Denetim | ☑ | `evaluate()` tek giriş: nedensellik denetimi → hakem → defter (ledger flock + `audit_causal` korkuluğu); walk-forward, rotasyon null'ı, DSR; PBO/CSCV (`stats.cscv`), SPA (`stats.spa`), nested walk-forward (`kepler/nested.py`), işlem sırası MC, tarihsel stres (`kepler/stress.py`), kapasite/karekök etki (`kepler/capacity.py`): hepsi gerçek veride kullanıldı (`reports/backtest_completion.md`). Yok (gerekçeli): StepM/MCS, purge/embargo/CPCV (etiket yok), sentetik senaryo, limit emir, cross-margin |
| 6 | Rapor | ☑ | `kepler/report.py` (işlem tablosu, saatlik PnL), `scripts/g2_report.py`, `scripts/search_report.py` (otomatik tablolar); özet raporlar elle |
| 7 | Araştırma ajanı (7/24) | ☐ | Yalnızca talimat dosyaları (`factory/agents/`) |
| 8 | Canlı emir katmanı | ☐ | Yok; MEXC desteği doğrulanmadı |
| 9 | Güncelleme (15–20 dk) | ◐ | `factory/status.py` deterministik özet (LLM yok; tests/test_ops.py); `state/STATUS.md` üretildi. Zamanlama (cron) + Telegram gönderimi F2'ye (sunucu) bağlı |
| 10 | Sekreter/müdür (Hermes) | ◐ | Hermes sunucuda kurulmuş (başka oturumdan), sekreter talimatı henüz uygulanmadı; kuyruk kodu var (`factory/enqueue.py`) |

**Döngü** (sinyal → boyut → backtest → denetim → rapor): boyut (risk motoru) hariç uçtan uca çalıştı (G2: `scripts/g2.py` + `g2_report.py`, Modal'de); rapor elle yazıldı.
**G2 cevabı: NO_EDGE** (kitap sinyalleri, 4–16 bps fee, gerçekçi hakem; en iyi turtle_s2 p=0,06 sert null'da, Bonferroni 0,72). Sıradaki: yeni hipotez (MISSION: aynı altyapıyla başka fikre geç). Hakem+yapıştırma 347 satır: tavan 450'ye çekildi (MISSION kural 7a, 2026-10-02).

## Zone Fade v1 + market state servisi v0 (2026-10-02; kullanıcı görevi): bitti, NO_EDGE (K1)

Ön kayıt `reports/zone_fade_protocol.md`, sonuç `reports/zone_fade.md` (+ `reports/zone_fade_data/`, `ledger/zone_fade/`). 165 işlem (örnek yeterli), K1 p = 0,371, DSR 0,706 → **NO_EDGE**; K2, K3, K5, K6, K9 da kalıyor; K4, K7, K8 geçiyor. Kümülatif deneme 4 118. ADAY değil: G3/mühür açılmadı.

| İş | Durum | Kanıt |
|---|---|---|
| State servisi v0 (BACKTEST §15) | ☑ testli | `kepler/state.py` (178 satır), `tests/test_state.py`: §15.5'in 7 kuralı elle hesaplı (ATR 41/14, impuls 5,75, swing onay tarihleri, profil POC 45/VAL 10/VAH 70, 3d çıpa 2022-01-01) |
| Zone Fade uzmanı + yönetici | ☑ testli | `kepler/experts/zone_fade.py` (193), `tests/test_zone_fade.py` (hakem e2e dahil); hedefte çıkış/koşullu giriş sinyalle taklit edildi (hakem değişmedi, taklit yetti) |
| Tek koşu + K1–K10 | ☑ | `scripts/zone_fade.py`, `scripts/zone_fade_report.py`; 39 test geçti |
| Bağımsız inceleme | ☑ | BLOCKER yok; bulgular `reports/zone_fade.md` içinde (giderilenler ve bilinçle giderilmeyenler) |

**Devralma notları (yeniden keşfetme):**
- Bu koşu Modal'de değil bir bulut konteynerinde yapıldı (Modal gRPC proxy'den geçmiyordu). Ham veri Binance arşivinden indirildi (`kepler.universe.build_symbol`, EXT-9 + K7 14 sembol), zip sha256'lar manifestle birebir; `universe.parquet` ve `usable.json` manifestten kuruldu. Komut: `PYTHONPATH=. python scripts/zone_fade.py --stage primary|second|k7|null --root <kök> --out <dizin>` (`--smoke` kısa boru hattı denemesi). Modal'de aynı komutlar `--root /data --out /data/zone_fade` ile koşar.
- Açık, sonucu etkileyebilecek ama koşulmayan: aday yeniden oluşumunu engelleyen varyant (inceleme MAJOR; yeni ön kayıt ve deneme gerekir). Ayar turu yapılmadı.
- Ekstra: `evaluate.py` `code_hash` state.py'yi kapsamıyor ve state `id`'si deftere yazılmıyor (hakem tarafı; kullanıcı onayı gerekir).
- State servisi v0: ilk uzman sonucuna göre "genişler ya da atılır" (BACKTEST §15.7): öneri tutulsun (küçük, testli), yeni uzman yeni ön kayıtla eklensin.

## Kararlar (2026-10-02, kullanıcı adına; MISSION'a işlendi)

1. PR #2 main'e birleşti (gerçekçi hakem, G2, arama). Benim dalımdaki paralel sertleştirme (`b8ec86e`, `claude/blissful-ptolemy-4kmtvf`) birleştirilmez, arşiv olarak dalda kalır.
2. G2 sonucu geçerli: kitap sinyallerinin kırpılmış sürümleri için `NO_EDGE`. Kapı ölçütü MISSION'da sabit: ortak-ofset rotasyon null'ı + Bonferroni (N = deneme sayısı) + fee 10 ve 16'da net > 0.
3. Risk motoru ve trade yönetimi stratejinin parçası: G3'ten önce kullanılır.
4. Satır tavanı: hakem+yapıştırma tavanı **kaldırıldı** (kullanıcı kararı 2026-10-02; önceki 300→450→600), sayı raporlanmaya devam eder; araştırma kodu tavansız ama testli ve kullanılıyor olmalı. Kullanılmayan `scripts/probe.py` silindi.
5. Aynı veride serbest arama yok (MISSION kural 11).
6. Mühürlü dönem (son 6 ay, ≥ 2026-04-01) **aday çıkmadıkça açılmaz** (kullanıcı kararı 2026-10-02; önceki "hiç kullanılmayacak" ifadesinin yerine). Aday (K1–K9) çıkarsa G3 yalnızca kullanıcı komutuyla, tek atış. MISSION'a işlendi.

## Motor v2 + tam sistem testi (hepsi tamam; kullanıcı görevi 2026-10-02)

Tasarım ve test senaryoları: `BACKTEST.md` §4 (stoplu sözleşme), §5.2, §6.4–6.5, §12.2.

Soru: kitaptaki tam Turtle sistemi (N-boyutlama, 2N stop, piramitleme, portföy birim sınırları), G2'deki kırpılmış sürümün yapamadığını yapıyor mu? Evet → eksik olan motordu; hayır → sorun sinyalde.

| Ad | İş | Bitti sayılması için | Durum |
|---|---|---|---|
| Stop | Strateji stopu: sinyal hedef + stop seviyesi döner; stop-market bar içinde (gap dahil) tetiklenir | Elle hesaplı stop testleri (gap, aynı bar giriş+stop, likidasyonla etkileşim) | ☑ tests/test_stops.py (8) |
| Portföy | Portföy hakemi: tek Nautilus motorunda çok sembol, ortak sermaye, toplam brüt pozisyon tavanı | Tek sembolde mevcut hakemle birebir aynı sonuç + elle hesaplı portföy testleri | ☑ tests/test_portfolio.py (6; denklik: eski hakemden sabit sayılar) |
| Risk | Risk motorunu bağla: N (ATR) boyutlama, piramitleme, birim sınırları (sembol/korele grup/toplam) | Testli; sabit boyuta karşı karşılaştırma raporlanır | ☑ tests/test_turtle.py (14); sabit boyuta karşı karşılaştırma `reports/full_systems.md` (g2_equiv) |
| Tam sistem | Tam Turtle S1/S2 ön kaydı (`reports/full_systems_protocol.md`, koddan önce commit) ve tek koşu | `reports/full_systems.md`: MISSION başarı kartıyla (K1–K9) sonuç | ☑ **NO_EDGE (K1)**; S1 p=0,026 DSR 0,52, S2 p=0,060 DSR 0,36 |

Kapsam dışı: haber, emir defteri, likidasyon akışı (veri yok), limit/maker emirler, diskresyoner kararlar.

## İlerleme (G0–G1 çekirdek görevleri)

| # | Görev | Ağırlık | Durum | Kanıt |
|---|---|---|---|---|
| A | Ortam, proje iskeleti, görev takibi | 5 | ☑ | Modal imajı (modal_app.py, uv.lock), `modal run modal_app.py --cmd 'pytest -q'`; tests/test_env.py 3 geçti |
| B1 | Binance arşiv istemcisi (liste, indirme, checksum) | 8 | ☑ | tests/test_data.py: bozuk sha256 reddi + yeniden indirme, idempotent, mühür koruması (SealedError), gerçek uçtan uca (KEPLER_NET=1, Modal) |
| B2 | Kalite kontrolü + manifest | 8 | ☑ | tests/test_qc.py+test_review_fixes.py: her kontrol sentetik bozuk veride tetikleniyor; gerçek veri: data_manifest/quality_report.md (0 ERROR, 695 WARN, 105 INFO, hiçbiri düzeltilmedi) |
| B3 | Dönemsel hacim evreni + gerçek dev verisi | 8 | ☑ | data_manifest/manifest.json (178 sembol, 51 ay × top20; emtia/stable sıralamadan önce çıkarıldı, kline~mark ayrışma kesimi 28 sembol); son bar 2026-03-31 23:00; mühür ayı indirilmedi (tests/test_data.py::test_sealed_period_is_never_fetched, tests/test_universe_rules.py) |
| B4 | Mühür aracı | 4 | ☑ | tests/test_seal.py: sentetik şifrele→aç birebir, yanlış özel anahtar açamaz, bozulmuş şifreli metin reddedilir, seal aracında özel anahtar yolu yok (5 test) |
| C1 | Hedef-pozisyon sözleşmesi + veri yükleme + deney defteri | 6 | ☑ | kepler/tape.py + kepler/ledger.py; tests/test_tape_ledger.py (5): sözleşme doğrulama, mühür sınırı reddi, append-only defter, DuckDB sorgu, eleme result yazamaz |
| C2 | Hakem motor (Nautilus; yedek Freqtrade) + bilinen-cevaplı testler | 25 | ☑ | tests/test_referee.py (26) + test_liq_mark.py (7: 10x, mark-tetikli) + test_review_fixes.py: elle hesap; likidasyon MARK H/L ile tetiklenir (yalnızca last geçince likide olmaz); test_nautilus_alone_does_not_liquidate. Sapma kullanıcı onaylı: hakem Nautilus + likidasyon yapıştırması (MISSION'da) |
| C3 | vectorbt eleme + eleme–hakem uyumu | 10 | ☑ | reports/screen_vs_referee.md: Spearman 1,000 (n=16; ızgara fee-baskın, zayıf kanıt); ledger/g1_ledger.jsonl 80 kayıt (eleme+hakem); tests/test_screen.py |
| C4 | Nedensellik, determinizm, pencere denkliği, negatif kontroller | 10 | ☑ | tests/test_trust.py (7): nedensellik (nedensel geçer; sızdıran sinyal assert_causal'da AssertionError [120,200,280,360] — elle doğrulandı), determinizm hash, pencere=tam tape (funding sınırı dahil), flat=0, rastgele=brüt~0/net<0 |
| C5 | Gerçek veride çapraz kontrol (hakem vs bağımsız elle hesap) | 5 | ☑ | reports/xcheck_btc.md: BTCUSDT 3773 işlem eşleşti, |net fark| maks 0,00207 USDT, funding birebir; tests/test_xcheck.py |
| D | Kitaplar: PDF → metin (paralel, düşük öncelik) | 3 | ☑ | books_text/ (125 metin) + books_text/QUALITY.md; kaynaklar PDF değil zaten düz metindi (0 PDF, sayfa bilgisi yok); 2 kitap bayraklı; scripts/books_quality.py |
| E | Rapor + bağımsız inceleme | 8 | ☑ | reports/g0_g1.md; bağımsız inceleme (ayrı bağlam) bulguları raporda; 89 test yeşil |

Toplam 100. **Çekirdek = A–C5 + E.** D paralel ve çekirdeği bekletmez.

## Bu oturumda doğrulanmış olgular (yeniden keşfetme; ama değişmiş olabilir, kontrol et)

- `data.binance.vision` erişilebilirdi (HTTP 200). `fapi.binance.com` 451 (coğrafi engel); ihtiyaç yok.
- Sembol ve dosya listesi için S3 uç noktası çalıştı:
  `https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/monthly/klines/`
  (XML `ListBucketResult`, sayfalama `marker` ile; `data.binance.vision.s3.amazonaws.com` sertifika hatası verdi).
- Aylık dosyalar ve her birinin `.CHECKSUM` dosyası (sha256 + dosya adı):
  - `data/futures/um/monthly/klines/{SYM}/1h/{SYM}-1h-YYYY-MM.zip` (CSV, başlık satırlı)
  - `data/futures/um/monthly/markPriceKlines/{SYM}/1h/{SYM}-1h-YYYY-MM.zip` (**aynı dosya adı**: ayrı dizinde sakla; `volume` alanı 0)
  - `data/futures/um/monthly/fundingRate/{SYM}/{SYM}-fundingRate-YYYY-MM.zip`
    (sütunlar: `calc_time, funding_interval_hours, last_funding_rate`)
- Bulut denemesinde: `uv` 0.8.17, Python 3.12 mevcuttu; `uv sync` ile `vectorbt==1.1.1` ve
  `nautilus_trader==2.0.0rc5` Python 3.12'de kuruldu (pandas 3.0.6, numpy 2.5.3, duckdb 1.5.6).
  Nautilus Python ≥3.12 ister (3.11'de sessizce eski sürüme düşüyordu).
- Kendi ortamında (yerel / Modal) bunların hangisinin geçerli olduğunu yoklayarak öğren.

## Görevler

### A. Ortam, iskelet, görev takibi (5)
Python 3.12 + `uv` + kilit dosyası; testler tek komutla çalışır (CI yok). Bu dosyadaki görevleri kendi
görev sistemine aç. Yerel bilgisayar ve Modal ikisi de kullanılabilir; ağır indirme/koşum için hangisinin
uygun olduğuna sen karar ver (Modal'ı kendin kur ve dene). Ham veri git'e girmez; kod, manifest ve
raporlar girer. Ortam silinebilir: indirme idempotent ve devam ettirilebilir olsun, sık commit + push.
**Bitti:** temiz klonda tek komutla ortam kurulur ve boş test paketi çalışır.

### B1. Binance arşiv istemcisi (8)
Sembol/ay listesi, aylık klines + mark price klines + funding indirme, sha256 doğrulama (bozuk dosya
reddedilir, yeniden indirilir), idempotent, devam ettirilebilir, hata/deneme yönetimi.
**Bitti:** küçük gerçek bir örnekte (1–2 sembol, birkaç ay) uçtan uca çalışıyor; bozuk checksum testi var.

### B2. Kalite kontrolü + manifest (8)
Boşluk, yinelenen/bozuk zaman damgası, UTC, tutarsız mum (high<low, open/close dışı vb.), anormal
sıçrama, funding aralığı (1/2/4/8 saat — G1'de düzeltildi: gerçek veride 99 sembol 8 saat dışı kullanıyor), listeleme/delist tarihleri. Manifest: dosya hash'leri, aralıklar,
sembol listesi, ay bazında evren üyeliği, **dev / mühürlü dönem sınırı**. Kalite raporu eksik/şüpheli veriyi
açıkça listeler, sessizce düzeltmez.
**Bitti:** bilerek bozulmuş sentetik veriyle her kontrol tetikleniyor (test); gerçek veride rapor üretiyor.

### B3. Dönemsel hacim evreni + gerçek dev verisi (8)
Her ay o ayın en likit 10–20 USDT-M perp'i (quote volume), delist ve yeni kontratlar dahil (survivorship
düzeltmesi). ≥3–4 yıl saatlik klines, mark, funding: Parquet + DuckDB. **Yalnızca bugünden 6 ay öncesine
kadar (dev dönemi) indirilir; son 6 ay (mühürlü) bu görevde gerçek veriyle hiç indirilmez ve açılmaz.**
**Bitti:** dev dönemi indi, manifest + kalite raporu var, evren üyeliği aylık olarak kayıtlı.

### B4. Mühür aracı (4)
`tools/seal_holdout.py`: mühürlü dönem verisini yalnızca **genel anahtarla** şifreler (özel anahtar ajanda
olmaz, hiçbir ortam değişkenine veya dosyaya girmez). Açma betiği ayrı; ikisi sentetik veriyle test edilir.
Gerçek veriyle çalıştırmayı kullanıcı yapacak; sen çalıştırma.
**Bitti:** sentetik veriyle şifrele → aç → birebir aynı; özel anahtar olmadan açılamıyor (test).

### C1. Hedef-pozisyon sözleşmesi + veri yükleme + deney defteri (6)
Sinyal, tape'ten hedef pozisyon serisi (long/short/flat + büyüklük; bar başına değişebilir) üreten saf
fonksiyondur; iki motor aynı seriyi oynatır. Tape'i Parquet/DuckDB'den yükle. Deney defteri: append-only
JSONL (hipotez, config/kod/veri hash'i, deneme sayısı), DuckDB ile sorgulanır.
**Bitti:** sözleşme kod + testle sabit; defter yazılıp sorgulanıyor.

### C2. Hakem motor + bilinen-cevaplı testler (25)
Sonuç deftere **yalnızca hakem motordan** girer. Birincil: NautilusTrader. Geçemezse Freqtrade (geçemediğini
gösteren bir testle belgele). Elle hesaplanmış senaryolarla birebir örtüşme: long; short; 8 saatlik funding
sınırını aşan tutma (pozitif ve negatif oran); sınır anında açma/kapama (Binance'in resmi kuralını belgeden
bul ve testle sabitle); taker fee (gidiş-dönüş 4 / 9 / 10 / 11 / 16 bps); slippage (bps); min notional ve
lot adımı; yön çevirme; kaldıraçlı likidasyon; NaN tutma.
**Bitti:** tüm senaryolar elle hesapla birebir; her birinin beklenen değeri testte elle yazılı (çıktıyı
kendisiyle karşılaştıran test sayılmaz).

### C3. vectorbt eleme + eleme–hakem uyumu (10)
vectorbt yalnızca hızlı filtre; sonuç sayılmaz ve deftere yazılmaz. Küçük bir konfigürasyon ızgarasında
eleme ile hakem sıralama korelasyonunu ölç ve raporla (eşik koyma; öneri ≥0,8, doğrulanmadı). Elemede
koşulan her konfigürasyon deftere ve deneme sayacına girer.
**Bitti:** korelasyon ölçülüp raporlandı; eleme konfigürasyonları deftere yazılıyor.

### C4. Güven testleri (10)
Nedensellik (gelecek bozulunca geçmiş kararlar değişmez; bilerek lookahead sızdıran sinyal yakalanır),
determinizm (aynı girdi → aynı hash), tam/pencereli tape denkliği (funding sınırı dahil), negatif
kontroller (flat ≈ 0, rastgele sinyal ≈ −maliyet).
**Bitti:** testler yeşil; sızdıran sinyal testi gerçekten kırmızıya düşüyor (kontrol et).

### C5. Gerçek veride çapraz kontrol (5)
Tek sembol, basit sinyal: hakem ile bağımsız elle hesap arasındaki işlem başına net fark.
**Bitti:** fark raporlandı ve açıklandı.

### D. Kitaplar: PDF → metin (3, paralel)
Yerel `books/` klasörü (~160 MB, **yalnızca yerelde**, bulutta yok) içindeki PDF'leri metne çevir. Metni
repoya koy (`books_text/`; repo özel kalmalı, telif); PDF'lerin kendisi git'e girmez (`.gitignore`). Taranmış
(OCR gereken) PDF varsa işaretle, çekirdeği bekletme. Ağır işler için Modal kullanılabilir.
**Bitti:** her PDF için metin dosyası + bir kalite notu (sayfa sayısı, boş/bozuk sayfa oranı).

### E. Rapor + bağımsız inceleme (8)
`reports/g0_g1.md` (≤2 sayfa), ilk cümle sonucu söylesin: "G0 geçti/bloklu, G1 geçti/şu testte kaldı".
Kırmızı test kırmızı yazılır, atlanan "atlandı", doğrulanmamış rakam "doğrulanmadı". Kod yazıldıktan sonra
ayrı bir bağlamda (yalnızca kod ve testler verilerek) **bir** bağımsız inceleme yaptır; bulguları rapora ekle.
Kendi kodun (yapıştırma kodu dahil) ≲300 satır: sayıyı raporla; aşarsan dur ve kullanıcıya sor.
**Bitti:** rapor + inceleme bulguları commit'li.

## Çekirdek bitince (kapsam dışı; yalnızca kredi/zaman kalırsa, G2'ye geçme)

Yalnızca G0–G1'i destekleyen, sinyal içermeyen işler:
- Defterden **deterministik** durum özeti üreten küçük betik (deneme sayısı, en iyi adaylar, null'a göre durum,
  hatalar; LLM yok) — 15–20 dk'lık güncelleme katmanının girdisi.
- İlerleme tablosunun son hali ve "devralma notu": bir sonraki ajan (Hermes) nereden devam eder.

**G2'ye (sinyaller, null, fee duyarlılığı) geçme.** Kapı sonunda dur ve raporla.

## Devralma notu (Hermes / sonraki ajan) — çekirdek bitti, G2'ye geçilmedi

**Durum:** G0 geçti, G1 geçti (99 test yeşil, 0 atlanan; gerçek ağ testi için `KEPLER_NET=1`). Sonuç ve açık bulgular: `reports/g0_g1.md`. **Dal: yalnızca `main`** (G0–G1 işi `49c3354` merge commit'iyle `main`'de; `g0-g1` ve `claude/blissful-ptolemy-4kmtvf` birleştirilip silindi). Yeni iş için `main`'den dal aç.

**Nerede ne var**
- Her şey Modal'de çalışır: `modal run modal_app.py --cmd "pytest -q"` (gerçek ağ testi: `KEPLER_NET=1 pytest tests/test_data.py`). Yerel `.venv` boş; yerelde proje kodu koşulmuyor.
- Veri: Modal Volume `kepler-data:/tape/{klines,markPriceKlines,fundingRate}/SYM.parquet` + `universe.parquet`. Ham zip'ler konteyner diskinde (`/tmp/kepler_raw`), kalıcı değil; manifest `data_manifest/manifest.json` zip sha256'larını taşır. Yeniden kurmak: `python -m kepler.universe --stage rank|universe|build --shard i/12` (12 paralel `modal run --detach`; tek konteyner ≈10 dosya/sn, konteyner sayısıyla ölçekleniyor), sonra `python -m kepler.qc --root /data --out /data/manifest`. Yalnızca ≤ 2026-03 indirilir (`kepler/data.py::DEV_END`).
- Hakem: `kepler/referee.py::run(kl, target, Spec, funding, mark)`; sözleşme `kepler/tape.py` başlığında. Sonuç deftere yalnızca `ledger.record(source="referee")` ile; eleme `kepler/screen.py` (defter zorunlu).
- Mühür: `tools/seal_holdout.py` (genel anahtar) / `tools/open_holdout.py` (kullanıcı). **Gerçek veriyle kullanıcı çalıştıracak**; ajan çalıştırmaz.
- Defter: `ledger/g1_ledger.jsonl` (fixture ızgarası; 112 kayıt = 16 eleme + 16 hakem × yeniden koşular; append-only olduğu için tekrarlar silinmez, deneme sayacına girer). G2 denemeleri ayrı dosyaya.
- Veri notu: evren 178 sembol (emtia/stable sıralamadan önce çıkarıldı). Kuralla çıkarılan semboller (XAU, XAG, PAXG…) Volume'da eski Parquet olarak duruyor ama manifestte/evrende yok; kullanma.

**Kullanıcı kararları (işlendi):** hakem = Nautilus + mark-tetikli likidasyon yapıştırması (MISSION'da); kural 7 iki sayıya bölündü (hakem+yapıştırma ≲300: 285; araçlar ≲500: 434); evren kuralı sabitlendi (emtia/stable/endeks sıralamadan önce çıkar, `EXCLUDE_BASES`; kline~mark ayrışma kesimi). Hâlâ kullanıcıda: mühür uzunluğu (6 ay, 2026-04-01 sınırı), mühür aracını gerçek veriyle ÇALIŞTIRMAK (özel anahtar ajanda/ortamda olmamalı), funding settlement anı kuralının Binance resmi SSS'inden teyidi (UNKNOWN; mark fiyatı kullanımı ve dinamik aralık geliştirici belgesinden KNOWN).

**G2'nin ilk adımı:** eleme↔hakem uyumunu fee-baskın olmayan geniş bir ızgarayla yeniden ölç (Spearman 1,000/n=16 anlamsız). **G2'den önce yapılacaklar (inceleme bulgularından):** sonraki-bar dolum modu ve zorunlu slippage; açık pozisyon çıkış maliyeti; likidasyon çifte sayım; `audit.assert_causal`/`check_target`'ı tek `evaluate()` girişine bağlamak; defter için dosya kilidi. Evren kullanımı: `tape.load` kesimi otomatik uygular, aylık üyelik için `tape.membership(root)`.

**Dikkat:** funding aralığı 1/2/4/8 saat olabilir (99 sembol 8 saat dışı); referee her aralıkta çalışır. 500 USD'lik hesap yüksek devirli sinyalde iflas eder → `n_rejected>0` koşular geçersiz.

## Durma koşulları

- Çekirdek bitti (A–C5 + E) → dur, raporla.
- Kredi/limit doldu → ilerleme tablosunu güncelle, commit + push, dur.
- Gerçek engel (ör. anahtar yok, Modal erişimi yok) → engeli ilerleme tablosuna ve rapora yaz, yapabildiğine
  devam et; soru sorup bekleme.

# Fabrika (7/24 işletme) ve sonraki kapılar

Ağırlıklar kaba tahmindir (G0–G1 çekirdeği bunun 25'i). Durum: ☑ bitti, ◐ kısmen, ☐ başlanmadı.

| # | Görev | Ağırlık | Durum | Kanıt / not |
|---|---|---|---|---|
| F1 | Repo tarafı: kuyruk (`factory/enqueue.py`), ajan talimatları (`factory/agents/`), `AGENTS.md`/`CLAUDE.md`, Türkçe komut test seti, kurulum özeti, mimari bölümü | 10 | ☑ | tests/test_enqueue.py (5); `factory/commands_tr.yaml` henüz bir modelle koşulmadı |
| F2 | Kurulum: VPS, Hermes, Telegram, anahtarlar, yazma sınırı, `state` dalı push'u | 15 | ◐ | VPS (`ssh a`): 3 OS kullanıcısı, bare repo + hook, Hermes, gateway, status timer kuruldu; T7 (OS+dal) ve T8 (OS) yeşil (`factory/vps/test_t7_t8.sh`, 40 PASS). Hermes bulguları ve kalan riskler: `docs/factory.md` §19. Açık: Telegram eşleştirmesi/uçtan uca, Modal token'ı (T8 Modal kısmı), `merge_gate` (T7 ikinci yarı, WP4), `krunner` GitHub token'ı (ayna push'u) |
| F3 | Aşama 1 çalışıyor: sekreter + güncelleme ajanı, salt okunur; test seti 10/10 | (F2'de) | ☐ | |
| G2 | G2 öncesi sertleştirme (devralma notundaki 6 madde) + sinyaller, null, fee duyarlılığı | 20 | ☑ | **Sonuç: NO_EDGE** (`reports/g2.md`; sinyaller `reports/book_signals.md`; 767 hakem kaydı `ledger/g2/`; tablolar `reports/g2_data/`). 130 test yeşil. G3 açılmadı (aday yok) |
| F4 | Aşama 2: müdür + işçiler | (H4'te) | ☐ | G2 hazır olunca |
| H4 | 7/24 LLM arama vs rastgele | 15 | ☐ | |
| G3 | Mühür açılışı (tek atış, kullanıcı komutuyla) | 5 | ☐ | Mühür uzunluğu ve aracı gerçek veriyle çalıştırmak kullanıcıda |
| H5 | Küçük gerçek para | 7 | ☐ | |


## G2 devralma notu (güncel)
- **Durum:** hakem gerçekçi (next_open, slippage ≥1 bps zorunlu, çıkış maliyeti, likidasyon çifte sayım yok, likidasyon sonrası hesap ölü); `kepler/evaluate.py` tek giriş (denetim→hakem→defter; ledger flock + `audit_causal` korkuluğu — kendi beyan eden bayrak, güvenlik değil); `kepler/signals.py` 6 sinyal. G2 = **NO_EDGE** (`reports/g2.md`). Mühür açılmadı, G3 yok.
- **Yeniden koşmak:** `modal run modal_app.py --cmd "python scripts/g2.py --job turtle_s2 --b 300 --out /data/g2"` (ve `--common` null için), sonra `python scripts/g2_report.py /data/g2`. 7 iş paralel ~12 dk. İşler: turtle_s1 turtle_s2 donchian_trend tsmom carry_funding dual_mom_5 dual_mom_9. Not: `modal run` için `pip install 'modal[api-proxy-support]'` gerekebilir (proxy altında).
- **Açık/atlanan:** 4h/1d türetme yapılmadı; kitap stopları/boyutlama yok; inceleme bulguları 8 (gap'te stop dolum fiyatı, doğrulanmadı), 9 (reddedilen koşular deneme sayacına girmiyor), `audit_causal` bayrağı elle yazılabilir; `scripts/g1_real.py` bayrağı elle True yazıyor (fixture). Hakem+yapıştırma 347 satır (MISSION 7a ≲300): kullanıcı karar versin.


## Arama sonrası durum (kullanıcı beklenen işler dışında her şey bitti)
- **Yapıldı:** G2 (NO_EDGE), geniş arama + dev-içi doğrulama (`reports/search.md`: aday yok), risk motoru, otomatik rapor/durum, 4h/1d türetme (`tape.aggregate`), eleme–hakem uyumu ölçümü (0,871, n=88). 141 test yeşil.
- **Kullanıcı/dış girdi gerektirdiği için YAPILAMAYAN:** F2/F3 (VPS, Hermes, Telegram, anahtarlar; `factory/README.md` "Senden gerekenler"), H4 (7/24 LLM arama; sağlayıcı anahtarı + F2), G3 (mühür açılışı yalnızca kullanıcı komutu + özel anahtar; aday da yok), H5 (gerçek para), MEXC emir katmanı/MEXC farkı (karar verilmedi), mühür kaynağı sağlaması (inceleme 33; mühür aracına dokunulmadı).
- **"Pozitif backtest" hedefi:** üretilmedi. Doğrulama dönemi tek atış tüketildi; aynı veriyle daha fazla arama yanlış pozitif üretir (bkz. `reports/search.md` dürüstlük notu).
- **Replikasyon (tek atış):** kullanılmamış 14 majörde aile-seçilmiş 6 yapılandırma: trend/momentum aileleri net pozitif (fee 16'da da), brüt p 0,047–0,106, Bonferroni ≥0,28 → ADAY yok (`reports/search.md`). Yön tutarlı bir hipotez; G3 için aday dondurulmadı (kriter sağlanmadı). Karar kullanıcıda: bu hipotez için G3 (mühür tek atış) açılsın mı? (xs_mom 7g dolar-nötr en temiz: beta'dan arınmış, p=0,047 ham.) Mühür dokunulmadı.


## Motor v2 devralma notu (2026-10-02)
- **Hakem+yapıştırma satırı** (grep -cvE '^\s*(#.*)?$', referee+screen+tape+ledger+audit+evaluate): G2 sonunda 347 (tape 41, evaluate 31); şimdi **467** (referee 234, screen 24, tape 48 [aggregate +7], ledger 45, audit 40, evaluate 76). Tavan 450'yi aşıldı (+17); kullanıcı tavanı 600'e çıkardı (karar 2026-10-02). Artış nedenleri: çok sembollü adaptör + stop + brüt tavan (referee +52), `evaluate_book` + `_realistic` (evaluate +40), `check_causal_book` (audit +14).
- Mevcut `evaluate`/`check_causal` tek sembol API'si korundu (aynı çağrı, aynı kesim noktaları).
- **Bağımsız inceleme (stop/portföy/risk, ayrı bağlamda, 1 kez):** 6 bulgu, hepsi giderildi ve regresyon testli: (1 YÜKSEK) `report.hourly_pnl` bar içi (stop/likidasyon) dolumları atıyordu → portföy kill switch yanlış tetiklenirdi; (2) brüt tavan artıran hedefi satışa çeviriyordu; (3) turtle veri boşluklarında durum ayrışıyordu; (4) gap stopu funding'i siliyordu; (5) kısmi stop dolumunda reddedilen yeniden emir; (6) taklit stop kline H/L + ham seviye kullanıyordu (hakem mark H/L + tick) + alfabetik sıra yanlılığı (iki geçişe çevrildi).
- **Tam Turtle sonucu:** tam Turtle S1/S2 = NO_EDGE (K1; ayrıntı `reports/full_systems.md`). Yeniden koşmak: `modal run modal_app.py --cmd "python scripts/full_systems.py --stage primary|robust|k7 --out /data/full"` ve `--stage null --null-from a --null-to b` (5 paralel konteyner), sonra `PYTHONPATH=. python scripts/full_systems_report.py <dizin> reports/full_systems_data ledger`. Ham JSON `reports/full_systems_data/`, defterler `ledger/full_systems/` (attempt1 = çöken ilk koşu 10 satır; run2 = yeniden koşu 10 satır; 2 deneme ruin nedeniyle deftere yazılamaz).
- **Açık:** hakem+yapıştırma 467 ≤ 600 (tavan 600'e çıkarıldı); equity-ölçekli boyutlama, kill switch kartı, tarihsel stres/MC/kapasite/nested WF/PBO (BACKTEST §10 [PLANLI]) yapılmadı; K10/G3 dokunulmadı.


## BACKTEST tamamlama devralma notu (2026-10-02)
- **Yapıldı (hepsi ön kayıtlı, Modal'de koşuldu, testli):** tarihsel stres, işlem sırası MC + kill switch önerisi, kapasite + karekök etki (500/10k/100k), risk motoru (equity_scale + portföy kill switch; 6 deneme) + BTC `vol_target` duman testi (3 deneme), PBO/CSCV + SPA (88 yapılandırma), nested walk-forward (792 hakem satırı). Ön kayıtlar: `reports/backtest_completion_protocol.md`, `reports/nested_wf_protocol.md`. Sonuç: `reports/backtest_completion.md`; tablolar/ham JSON `reports/backtest_completion_data/`; defterler `ledger/backtest_completion/`. **BACKTEST.md'de [PLANLI]/[KISMEN] kalmadı.** Bağımsız inceleme (tek, ayrı bağlam) yapıldı, bulgular giderildi/belgelendi; 202 test yeşil, 1 atlandı.
- **Yeniden koşmak:** `modal run modal_app.py --cmd "python scripts/completion.py --stage base|capacity|risk|misc|pbo --out /data/completion"`; nested: `--stage nested --family <aile>` (6 aile paralel) sonra `--stage nested_report`; tablo: `python scripts/completion_report.py reports/backtest_completion_data`. Not: Modal log çıktısı Nautilus gürültüsü nedeniyle satır düşürür; sonuçlar `/data/completion/*.json`'da (`modal volume get kepler-data completion/<dosya> .`).
- **Hakem+yapıştırma satırı:** 473 (referee 240: +6 `equity_scale`/`equity()`); tavan kaldırıldı (kullanıcı kararı), sayı raporlanır.
- **Yeni deneme sayısı:** önceki 3 311 satır + risk 6 + misc 3 + nested 792 + ölçekli kill 4 = **4 116** (ölçekli kill: `reports/scaled_kill_protocol.md`; sonuç: öneri iyimser, S2'de kill 2025-08-02 tetiklendi).
- **Açık / öneri (yapılmadı):** bkz. `reports/backtest_completion.md` "Öneri".


## 2020–2021 replikasyonu (pre2022; kullanıcı görevi 2026-10-02; ön kayıt `reports/pre2022_protocol.md`, N = 10)
Durum (adım adım güncellenir; dal `claude/serene-carson-tvrcs8`, main'e push yok):
- ☑ `kepler/universe.py` parametreleştirildi (`--start/--rank-start/--end/--root`; varsayılanlar aynı; veri/QC/mühür araçları (b) 434 → 439 satır, ≲500 altında). Test: 203 geçti, 1 atlandı (Modal).
- ☑ veri indirme (`/data/pre2022`; arşivde 2019 ayları yok, veri 2020-01 → 2021-12, 66 sembol; ayrıntı protokol sonu "Koşu notu (veri)") · ☑ QC (`data_manifest/manifest_pre2022.json`, `quality_report_pre2022.md`: 0 ERROR, 227 WARN, kesim yok) · ☐ Blok A · ☐ Blok B · ☐ rapor `reports/pre2022.md`
Yeniden koşmak / ayrıntılar işler bitince buraya yazılır.


## Ensemble v1 devralma notu (2026-10-02)
- **pre2022 (2020–21) bitti:** Blok A tam Turtle NO_EDGE (K1/K2); Blok B `tsmom_14_1` ölçütü geçti (p 0,0066). Rapor `reports/pre2022.md` (teşhis dahil), tablolar `reports/pre2022_data/` (`scripts/pre2022_report.py`).
- **Ensemble v1** (ön kayıt `reports/ensemble_protocol.md`): **ZAYIF**, K1–K8 geçti, K9 kaldı (bull payı %105). Rapor `reports/ensemble.md`, tablolar `reports/ensemble_data/`, defter `ledger/ensemble/`. Yeniden koşmak: `python scripts/ensemble.py --stage primary|k7|null [--null-from a --null-to b] --out /data/ensemble`, sonra `PYTHONPATH=. python scripts/ensemble_report.py <dizin> reports/ensemble_data ledger`. 217 test yeşil, 1 atlandı.
- **Karar kullanıcıda:** (a) K9 için yeni ön kayıtlı sürüm, (b) ZAYIF'ı kabul, (c) K9 eşiği (yalnızca sonraki testten önce). Mühür açılmadı (aday yok). Kümülatif deneme 4 117.


## Denetim devralma notu (2026-10-03)
- Dal: `codex/kepler-audits-20261003` (güncel main `5e93e12` tabanından); mimari yalnız BACKTEST §15.8'e yazıldı ve `70b5971` ile push edildi. Korunan kodda değişiklik yok.
- Kullanıcı çalışma penceresi: 3 Ekim 2026 01:45–09:45 Europe/Istanbul. Saatlik devam ve 09:45 kapanış kontrolü kaydedildi. Bir sonraki çalışma mevcut koşuyu kontrol eder, tekrar başlatmaz.
- Sıra: A → B → C. A Modal `kepler-data` Volume'unu salt okunur tarar; /data'da 2531 Parquet (şema kontrolü tamamlandı). ≥2026-04-01 zamanları olan dosyada fiyat sütunları okunmaz. Token veya mühür anahtarı dosyaya yazılmaz.
- Devralmada mevcut A sonucu için `/tmp/kepler_data_audit_result.json` ve devam eden Modal sandbox `sb-epmSR4xi0Q4CHqrGQuuk5x` kontrol edilir. Geçici bağlantı betiği `/tmp/modal_http_transport.py`, SDK `/tmp/modal-legacy/bin/python`; bunlar çalışma ortamı araçlarıdır, repoya girmez. A tamamlandı: `reports/data_audit.md` + `data_audit_data/` (2531/2531 dosya, veri riskleri kırmızı); koşu bitti, yeniden başlatma.
- Her rapor tamamlanınca TASKS ve rapor commit/push; engel varsa engelli raporla, sıradakine geç. Hakem, denetim, risk, mühür, ledger ve evaluate değiştirilmez. C'nin test dosyası yalnız scratchpad'e yazılabilir.

- İş B: `reports/account_reality.md`; EV1 $500 hedef hesabı bitti. Güncel MEXC kuralları/hesap ücreti ve funding SSS doğrulaması engelli (proxy CONNECT 403); tüm semboller doğrulanmadı, C'ye geçildi.

- İş C tamamlandı: `reports/trial_inventory.md`; repo4117/Modal5434 satır, 1317 fark. Volume flock iki turda da iki exclusive lock'u aynı anda verdi (kırmızı), yerel kontrol yeşil. Test yalnız scratchpad. A/B/C ilk geçişi tamamlandı; 09:45 kapanışına kadar yalnız çözülmüş engel/yeni kanıt varsa rapor güncellenir, aynı koşu tekrar başlatılmaz.

## Denetim pencere kapanışı — 2026-10-03 09:45 Europe/Istanbul

Kapanış kontrolü: 2026-10-03 09:50:11 +0300. Pencere 01:45–09:45; bu kayıt kontrolün gerçek saatini taşır. İlk A/B/C koşuları tamamlandıktan sonra aynı denetimler yeniden başlatılmadı. Son kontrolde workspace/GitHub/Modal erişimi başarılı; mevcut A sandbox çıkış kodu 0.

| İş | İşin kapanışı | Renk | Kanıt |
|---|---|---|---|
| A | Tamamlandı: 2531/2531 Parquet; okunamayan/atlanan dosya 0 | kırmızı | reports/data_audit.md; data_audit_data/files.csv, findings.json, summary.json, time_checks.json |
| B | Hesap tamam; güncel MEXC tick/lot/minimum/fee/funding doğrulaması engelli (proxy CONNECT 403); doğrulanmadı | kırmızı | reports/account_reality.md; account_reality_data/sizing.json, sources.json, symbol_rules.csv |
| C | Tamamlandı: repo4117/Modal5434 defter satırı; flock iki turda konteynerler arasında dışlama sağlamadı | kırmızı | reports/trial_inventory.md; trial_inventory_data/ledger_reconciliation.csv, flock.json, integrity.json |

Mühür/anahtar/seal aracı **atlandı** (yasak); proje suite'i **atlandı** (üretim kodu değişmedi). Resmi delist teyidi, gerçek MEXC uygunluğu ve Zone Fade gerçekleşmiş aday sayısı **atlandı / doğrulanmadı**; ayrıntı raporlarda. Üç raporun renkleri canlı uygunluk onayı değildir.

Kapanış kanıtı: reports/audit_closure.json (rapor/kanıt SHA256'ları, korunan kaynak/defter denklik kontrolü, erişim ve gerçek kontrol saati). Saatlik devam görevi tamamlanmış/devre dışı, sonraki koşu yok. Yeni strateji/hakem/ledger koşusu 0; mühür açılmadı.

## Gösterge kütüphanesi (2026-10-03, kullanıcı isteği)
`kepler/indicators.py` + `tests/test_indicators.py` (33 test; referans testleri `uv run --with TA-Lib --with ta --with pandas-ta-classic pytest tests/test_indicators.py` ile koşar). TradingView teknik analiz sayfasının 11 osilatörü, 15 hareketli ortalaması, 5 pivot türü; ayrıntı ve doğrulama kapsamı `BACKTEST.md` §15.9. **State servisine bağlı değil**; sıradaki uzmanın ön kaydı hangi göstergeyi istiyorsa o bağlanır. TradingView ile birebir doğrulandı (BINANCE:BTCUSDT 1d/4h/1h/1w, 2026-10-03; `tests/data/tradingview/`); ayrıntı ve sınırlar BACKTEST §15.9.

## Seviye servisi (destek/direnç) ve olay çalışması (2026-10-03, kullanıcı isteği; yalnızca tasarım)
Tasarım `BACKTEST.md` §15.10. Sıra: (1) ☑ `reports/levels_event_study_protocol.md` ön kaydı (2026-10-03, parametreler donuk, koddan önce commit), (2) `kepler/levels.py` + `tests/test_levels.py` (8 test, elle hesaplı), (3) `scripts/levels_event_study.py` ile tek koşu (N = 7), (4) `tools/plot_levels.py` SVG çıktısı. Sonuç "SEVİYE ANLAMSIZ" ise destek/direnç uzmanları rafa kalkar. Kodlama Sonnet 5.5 high, bağımsız inceleme farklı aileden; hakem/denetim/risk/mühür koduna dokunulmaz.

## Fabrika spesifikasyonu v2 (2026-10-03, kullanıcı isteği; yalnızca tasarım)
`docs/factory.md` (Opus 5.5 taslağı + 7 blocker düzeltmesi + bürokrasi azaltma + fazsız bağımlılık sırası). Prompt'lar v1'den neredeyse aynen. İş paketleri (§16): WP1 uzman arayüzü (Zone Fade birebir aynı sonuç), WP2 kayıt + legacy içe aktarım + kütüphaneci, WP3 kapılar + `render_report`, WP4 kontrol düzlemi, WP5 runner + promote (C), WP6 VPS altyapısı, WP7 Hermes doğrulama, WP8 prompt'lar + ekilmiş hata takımı, WP9 entegrasyon provası (kabul takımı T1–T14). Sana kalan kararlar: `docs/factory.md` §18.2 (`N_eff` yöntemi, bütçe, repo koruması, ikinci mühür dönemi, müdür açılışı). Hiçbir kod yazılmadı; Hermes davranışı dokümandan okundu, doğrulanmadı.

## Pozisyonlanma verisi (OI + long/short + taker) — bulut ajanı görevi (2026-10-04, kullanıcı isteği; veri işi, strateji yok)
**Neden (gözlenmiş engel).** Bütün sinyaller, uzmanlar ve göstergeler OHLCV'den (+ funding) türüyor; piyasanın nasıl konumlandığını (OI, kalabalık long/short, taker akışı) ölçen hiçbir girdi yok. Swing (3d karar, 1h/4h giriş) için değerli olan bu; ham işlem akışı, emir defteri ve spread değil (maliyeti spread değil fee belirliyor). Bu görev yalnızca **veriyi** getirir; hipotez, sinyal, hakem koşusu ve defter kaydı yok, deneme sayacına girmez. Sonra gelecek ölçüm (koşullu getiri / olay çalışması) ayrı ön kayıttır.

**Bugün doğrulananlar (2026-10-04; yeniden doğrula, değişmiş olabilir).**
- Kaynak ücretsiz arşiv: `data/futures/um/daily/metrics/{SYM}/{SYM}-metrics-YYYY-MM-DD.zip` (yalnızca günlük; aylık yok). Her dosyanın `.CHECKSUM`'u var; BTCUSDT-2023-06-15 örneğinde sha256 eşleşti.
- Kapsam: BTCUSDT 2020-09-01'den, ETH/SOL/XRP/DOGE 2021-12-01'den 2026-10-03'e; dosya sayısı gün sayısına eşit (eksik gün yok). Sembol başına ~20 MB zip, 5 dakikalık 288 satır/gün. Diğer semboller **bakılmadı**.
- Sütunlar (ham adlar): `create_time, symbol, sum_open_interest, sum_open_interest_value, count_toptrader_long_short_ratio, sum_toptrader_long_short_ratio, count_long_short_ratio, sum_taker_long_short_vol_ratio`. Anlamları ve `create_time`'ın anlık mı dönem sonu mu olduğu **doğrulanmadı**.
- `liquidationSnapshot` arşivde yok (BTC için boş). `premiumIndexKlines` 1h var (2020-01'den) ama bu görevde **kapsam dışı**.
- Taker alış hacmi klines'ta hazır sütun (`taker_buy_volume`, `taker_buy_quote_volume`, `kepler/data.py` NAMES). Parquet'e taşınıp taşınmadığı **kontrol edilmedi**.
- Erişim: Mac'ten `data.binance.vision` SSL hatası verdi, `s3-ap-northeast-1.amazonaws.com/data.binance.vision` çalıştı; `kepler/data.py` iki adresi de tanıyor. `fapi` bulutta 451, gerekmiyor. Modal bulut konteynerinden gRPC proxy'siyle erişilemeyebilir (Zone Fade koşusunda öyleydi): ham veri konteynerde `--root <kök>` altında tutulur.

**Karar (kullanıcı, 2026-10-04, "tamamdir").** Veri/QC kod tavanı (MISSION kural 7b, ≲500 satır, G1 sonunda ~470) bu iş için aşılabilir; tahmin +60–100 satır. Yorum benim: soruya "tamamdir" cevabı onay sayıldı. Sayı yine raporlanır, sessizce geçilmez.

### Görev (bulut ajanı: bu bölümü oku ve işi bitir)
```text
Kepler repo'sunda (AGENTS.md ve MISSION.md çelişkide kazanır) kendi dalında çalış. Önce TASKS.md'deki "Aktif iş:" satırını bu iş için güncelle.

Hedef: çekirdek-5, genişletilmiş-9 ve K7'nin 14 sembolü için Binance arşivinden `metrics` verisini indir, doğrula, tape'e koy ve ileride bir uzmanın nedensel kullanabileceği saatlik özellikler olarak sun. Taker alış hacminin klines'tan tape'e gelmesini de çöz. Neden: bütün mevcut sinyaller aynı OHLCV bilgisinin dönüşümü; OI ve konumlanma verisi yeni bilgi olabilir. Bu veri henüz hiçbir şeyi kanıtlamaz; ölçüm ayrı ön kayıttır.

Bitti sayılması için hepsi doğru olmalı:
1. İndirme mevcut `kepler/data.py` kurallarıyla yürür: sha256 doğrulamalı, idempotent, devam ettirilebilir, bozuk dosya reddedilir. Dev dönemi sonu (`DEV_END`, 2026-03-31) sonrası hiçbir dosya istenmez; mühür testi bu veriyi de kapsar.
2. Bir sembol-gün için eksik/yinelenen/bozuk satır, sıfır veya negatif OI, aşırı sıçrama ve eksik gün kontrol edilir. Düzeltme yapılmaz, yalnızca raporlanır (`data_manifest/` altında dosya hash'leri, aralıklar, satır sayıları, bulgular; ham veri git'e girmez).
3. 5 dakikalık satırlardan saatlik özellik üretilir ve bir 1h bar kapanışında yalnızca o anda bilinen bilgiyi kullanır. `create_time` anlamı doğrulanana kadar muhafazakâr davran (bar kapanışından en az bir satır önceki değeri al). Nedensellik, elle hesaplı küçük bir örnek, mühür reddi ve eksik veri testleriyle kanıtlanır; ham sütun adlarını yeniden adlandırma.
4. Taker sütunlarının tape'te olup olmadığı belli ve gerekiyorsa eklenmiş olur. Mevcut tape değerleri, mevcut testler ve önceki raporlardaki sonuçlar değişmez: ekleme yalnızca yeni sütun olur.
5. Gerçek veride en az bir sembolde (BTC) uçtan uca koştu; sonuç kanıtlıdır (komut, satır sayıları, hash eşleşmesi). Bu görevin sayısal kanıtı 1–4'tür, bir edge iddiası değil.
6. `BACKTEST.md` §3'e kısa bir [VAR] notu ve §14'e doğrulanmamışlar (sütun anlamı, `create_time`) eklenir. Veri/QC kodunun satır sayısı (önce/sonra, MISSION kural 7b yöntemiyle) ve araştırma kodu sayısı ayrı yazılır.

Dokunma: hakem, denetim, risk, defter (`ledger.py`, `evaluate`), mühür araçları ve mühürlü dönem. Mühürlü döneme ait bir dosya gerekirse, ağ erişilemezse veya kural çelişirse dur ve raporla. Strateji, sinyal, parametre taraması veya ölçüm yazma; yeni spec belgesi açma.

Bütçe: yaklaşık 3 saat ve 150 araç çağrısı (öneri; aşılırsa dur ve raporla).

İşi bitirene kadar çalış; yalnızca onsuz ilerleyemeyeceğinde veya geri dönüşü zor bir adımdan önce dur. İş bitip kontrol edildiğinde dur ve raporla: istenmeyen özellik, test, dosya veya refactor ekleme; yararlı olacağını düşünürsen sonda bir cümleyle öner.

Çalıştırılabilen bir kod değiştirdiğinde bildirmeden önce değişikliği gerçekten sınayan bir kontrol koş: ilgili testler, yeni komutun kendisi. Yalnızca söz dizimi kontrolü sayılmaz. Kontrol koşamadıysan hangisini ve neden koşamadığını yaz; "bitti" deme. Kurulum gerekiyorsa `uv sync` kullan, sudo ve sistem paket yöneticisi yok.

Raporun sonunda: değişen dosyalar, koşulan komutlar ve sonuçları (geçti/kaldı/atlandı), bilinen sınırlar, yapılmayanlar. Doğrulanmamış rakamı "doğrulanmadı" diye yaz. TASKS.md'yi güncelle, commit + push et.
```

## Hakem motoru: Nautilus -> numba (2026-10-13, kullanıcı görevi): bitti
`kepler/referee.py` + `kepler/referee_core.py`; Nautilus bağımlılığı kalktı. Gerçek veri: EV1/ev1_plus_new/all9_equal Nautilus dolumlarıyla satır satır eşleşti (net farkı <= 2,7e-7 USDT). Uçtan uca soğuk ~13 sn, sıcak ~3,4 sn; GPU (A10G) yalnızca tarama deneyi: 5 ms/senaryo (çekirdek). Ayrıntı ve açık boşluklar: `reports/vbt_referee/gunaydin_raporu.pdf`, BACKTEST §6.6.
