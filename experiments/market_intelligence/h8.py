"""Deterministic PMI-H8 provenance ledger; this module runs no market scores."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Sequence

from kepler.intelligence.evidence import EvidenceRecord, evidence_matrix

PROTOCOL_SHA = "d9f1c2f4c7d3489fd2722757439e595caf3aba9c"
PROTOCOL_FILE_SHA256 = "80bf0574bac7aa566caf3b1408d03463f0ca72b6246c16b948133d64d4336354"

CURRENT_EVIDENCE = (
    EvidenceRecord(
        hypothesis="#65 shared contracts", implementation_status="IMPLEMENTED",
        test_status="TESTED", empirical_status="NOT_RUN", independent_status="NOT_RUN",
        blocker="Shared target/evaluation contracts exist, but no PMI canonical scored run is recorded.",
        note="PR #74 review branch; synthetic contract coverage only.",
        review_url="https://github.com/ddawnlll/kepler/pull/74",
        branch="codex/market-intelligence-v2"),
    EvidenceRecord(
        hypothesis="#66 H1 risk", implementation_status="IMPLEMENTED",
        test_status="TESTED", empirical_status="NOT_RUN", independent_status="NOT_RUN",
        protocol_path="reports/pmi_h1_protocol.md",
        protocol_sha="d89003c7c956ff25a3b1602fdffdaf5cb81028c0",
        blocker="No canonical PMI-H1 forecast metrics or run artifacts are recorded.",
        note="Frozen 7-day RV7 q75 forecast; candidate/baseline synthetic fold only.",
        review_url="https://github.com/ddawnlll/kepler/pull/74",
        branch="codex/market-intelligence-v2"),
    EvidenceRecord(
        hypothesis="#67 H7 distribution alternatives", implementation_status="IMPLEMENTED",
        test_status="TESTED", empirical_status="NOT_RUN", independent_status="NOT_RUN",
        protocol_path="reports/pmi_h7_protocol.md",
        protocol_sha="6e6008088e55d670a55378c64ea9ac48f77d0ce9",
        blocker="No canonical PMI-H7 density scores or run artifacts are recorded.",
        note="Synthetic Student-t and transition-cutoff checks only.",
        review_url="https://github.com/ddawnlll/kepler/pull/74",
        branch="codex/market-intelligence-v2"),
    EvidenceRecord(
        hypothesis="#68 H2 duration", implementation_status="IMPLEMENTED",
        test_status="TESTED", empirical_status="NOT_RUN", independent_status="NOT_RUN",
        protocol_path="reports/pmi_h2_protocol.md",
        protocol_sha="97db1f8ea813d101e3cd69008ee63e1b3add5a4a",
        blocker="PMI-H2 date-block evaluation and full sensitivity acceptance remain unrun.",
        note="Separate historical ERF-01 age signal is adjacent exploratory evidence, not this protocol's result.",
        review_url="https://github.com/ddawnlll/kepler/pull/75",
        branch="codex/pmi-h2-duration"),
    EvidenceRecord(
        hypothesis="#69 H3 fast/slow", implementation_status="IMPLEMENTED",
        test_status="TESTED", empirical_status="NOT_RUN", independent_status="NOT_RUN",
        protocol_path="reports/pmi_h3_protocol.md",
        protocol_sha="72af5363ec89482d904c0c0a80e4867a1f122369",
        blocker="No canonical PMI-H3 density comparison or run artifacts are recorded.",
        note="Small partial-pooling benchmark; not an HMM/HSMM or latent-regime validation.",
        review_url="https://github.com/ddawnlll/kepler/pull/76",
        branch="codex/pmi-h3-hierarchical"),
    EvidenceRecord(
        hypothesis="#70 H4 funding ablation", implementation_status="IMPLEMENTED",
        test_status="TESTED", empirical_status="NOT_RUN", independent_status="NOT_RUN",
        protocol_path="reports/pmi_h4_protocol.md",
        protocol_sha="d83a085c00688d30a4942e80a8888ea6656064be",
        blocker="Funding comparison is unrun; OI, basis, liquidation-event and multi-exchange sources remain unverified.",
        note="Funding-only scope; synthetic matched-cohort checks only.",
        review_url="https://github.com/ddawnlll/kepler/pull/78",
        branch="codex/pmi-h4-funding-ablation"),
    EvidenceRecord(
        hypothesis="#71 H5 pre-onset alarms", implementation_status="IMPLEMENTED",
        test_status="TESTED", empirical_status="NOT_RUN", independent_status="NOT_RUN",
        protocol_path="reports/pmi_h5_protocol.md",
        protocol_sha="2755a7709eb1e84814c9b99237a88e73c6ec549c",
        blocker="Canonical support census is not run; H5 alarm skill is not scored.",
        note="Support-only runner freezes q-v1 and excludes the last daily close at the seal.",
        review_url="https://github.com/ddawnlll/kepler/pull/79",
        branch="codex/pmi-h5-onset-evaluation"),
    EvidenceRecord(
        hypothesis="#72 H6 vintage macro", implementation_status="IMPLEMENTED",
        test_status="TESTED", empirical_status="DATA_BLOCKED", independent_status="NOT_RUN",
        protocol_path="reports/pmi_h6_protocol.md",
        protocol_sha="b6fcbff2506540a9188d7c91276c6eb74d00a94e",
        blocker="No eligible publication-time/vintage source or frozen series roster has been verified.",
        note="As-of vintage contract has synthetic tests; no revised values are treated as historical releases.",
        review_url="https://github.com/ddawnlll/kepler/pull/77",
        branch="codex/pmi-h6-vintage-contracts"),
    EvidenceRecord(
        hypothesis="#73 H8 synthesis", implementation_status="IMPLEMENTED",
        test_status="TESTED", empirical_status="NOT_RUN", independent_status="NOT_RUN",
        protocol_path="reports/pmi_h8_protocol.md", protocol_sha=PROTOCOL_SHA,
        blocker="No eligible H1-H7 scored claim exists yet; independent prospective study is not run.",
        note="This ledger is a provenance synthesis; it performs no market-data read or forecast.",
        branch="codex/pmi-h8-evidence-synthesis"),
    EvidenceRecord(
        hypothesis="LEGACY ERF-01 atlas (adjacent evidence)", implementation_status="IMPLEMENTED",
        test_status="TESTED", empirical_status="EXPLORATORY", independent_status="NOT_RUN",
        source_class="seen_dev",
        run_url="https://github.com/ddawnlll/kepler/actions/runs/38770049440",
        artifact_path="reports/erf01_regime_atlas_20261015.md; archived Volume /erf01/regime_atlas_20261015",
        note=("Five-year real canonical DEV atlas; q=0 was 79.5%; hard Markov directional recall was zero at 7/14/21d. "
              "Age-conditioned q-spell survival improved Brier slightly over a state-age-blind hazard. "
              "Seen-DEV, survivor-biased, technical proxy; not a PMI-H1-H7 result or independent validation. "
              "The report records 27 per-source SHA receipts; an aggregate manifest SHA is not copied into this ledger."),
        protocol_path="reports/erf01_regime_intelligence_protocol.md"),
)


def current_matrix() -> list[dict]:
    """Return the validated, stable current hypothesis/status matrix."""
    return evidence_matrix(CURRENT_EVIDENCE)


def verify_frozen_protocol(repo_root: Path) -> None:
    path = repo_root / "reports" / "pmi_h8_protocol.md"
    if hashlib.sha256(path.read_bytes()).hexdigest() != PROTOCOL_FILE_SHA256:
        raise RuntimeError("H8 protocol content differs from its frozen pre-score commit")


def render_markdown(records: Sequence[EvidenceRecord] = CURRENT_EVIDENCE) -> str:
    rows = evidence_matrix(records)
    lines = [
        "# PMI-H8 evidence ledger — 2026-10-16",
        "",
        "**Scope:** Provenance synthesis only. No market data were read for this ledger, no PMI market score was generated, and no independent validation is claimed.",
        "",
        "Implementation status, synthetic tests, real PMI evaluation and independent confirmation are separate. `TESTED` means software behavior was checked; it does not mean predictive skill. Draft PRs are not merged into `main`.",
        "",
        "| Workstream | Frozen protocol | Review branch / PR | Code | Tests | PMI empirical | Independent | Remaining blocker / interpretation |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        protocol = (f"{row['protocol_path']} ({row['protocol_sha'][:12]})"
                    if row.get("protocol_path") and row.get("protocol_sha") else "—")
        review = (f"[PR]({row['review_url']})" if row.get("review_url")
                  else row.get("branch") or "—")
        blocker = row.get("blocker") or row.get("note") or "—"
        note = row.get("note") or ""
        if note and note != blocker:
            blocker = f"{blocker} {note}"
        blocker = blocker.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {row['hypothesis']} | {protocol} | {review} | {row['implementation_status']} | "
            f"{row['test_status']} | {row['empirical_status']} | {row['independent_status']} | {blocker} |")
    lines += [
        "",
        "## Historical evidence kept separate",
        "",
        "The adjacent ERF-01 row refers to the completed five-year canonical Modal atlas, Actions run [38770049440](https://github.com/ddawnlll/kepler/actions/runs/38770049440). Its published status is `EXPLORATORY_SEEN_DEV_NOT_INDEPENDENT_CONFIRMATION`. On the frozen q-v1 proxy, 79.5% of observed symbol-days were neutral/unclassified; the previous hard Markov classifier had zero up/down recall at 7, 14 and 21 days. The age-conditioned survival Brier improvements over a state-specific age-blind hazard were small and exploratory. These results are not PMI-H2 or H5 scores and do not validate an economic regime.",
        "",
        "The older ERF-01 onset evaluation also reported 34 up and 20 down OOS events and that M2 was worse than M1 on 7-day event Brier. That result predates the H5 registration and does not establish true 7–14-day pre-onset warning skill.",
        "",
        "## H8 disposition",
        "",
        "- Same-period cross-symbol and cross-era H8 diagnostics: `NOT_RUN`; no canonical PMI-H1–H7 forecast receipts are available to audit.",
        "- Independent/prospective validation: `PROSPECTIVE_NOT_RUN`; the protected post-2026-04-01 period remains sealed and no new authorized external source is registered.",
        "- Data/cost gates: the canonical Volume, Actions secrets and provider billing were not verified in this session; the manual PMI workflow is not present on `main`, and no connected workflow-dispatch tool is available.",
        "- Next: review/integrate the draft implementation branches through repository governance; dispatch one bounded H1/H7 run only after the manual workflow is available on the default branch and the canonical source, secrets and provider controls are verified. Then consider H8 diagnostics only for claims meeting their frozen support rules.",
        "",
        f"H8 protocol commit: `{PROTOCOL_SHA}`. The source file records its timestamp-boundary and independent-source rules; this ledger does not open a data source.",
        "",
    ]
    return "\n".join(lines)


def render_json(records: Sequence[EvidenceRecord] = CURRENT_EVIDENCE) -> str:
    return json.dumps({"ledger_date": "2026-10-16", "protocol_sha": PROTOCOL_SHA,
                       "evidence": evidence_matrix(records)},
                      indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def write_ledger(repo_root: Path) -> tuple[Path, Path]:
    """Write the versioned source ledger and its machine-readable status matrix."""
    verify_frozen_protocol(repo_root)
    md = repo_root / "reports" / "pmi_h8_evidence_ledger_20261016.md"
    js = repo_root / "reports" / "pmi_h8_evidence_ledger_20261016.json"
    md.write_text(render_markdown(), encoding="utf-8")
    js.write_text(render_json(), encoding="utf-8")
    return md, js
