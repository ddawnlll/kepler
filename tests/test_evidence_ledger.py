from dataclasses import replace
from pathlib import Path

from experiments.market_intelligence.h8 import (
    CURRENT_EVIDENCE, current_matrix, render_json, render_markdown,
    verify_frozen_protocol, write_ledger,
)
from kepler.intelligence.evidence import EvidenceRecord, evidence_matrix


def _raises(error_type, match, function):
    try:
        function()
    except error_type as exc:
        assert match in str(exc)
    else:
        raise AssertionError(f"expected {error_type.__name__} containing {match!r}")


def _record(**updates):
    values = {
        "hypothesis": "H-test", "implementation_status": "IMPLEMENTED",
        "test_status": "TESTED", "empirical_status": "NOT_RUN",
        "independent_status": "NOT_RUN",
    }
    values.update(updates)
    return EvidenceRecord(**values)


def test_h8_matrix_keeps_implementation_synthetic_and_empirical_statuses_separate():
    rows = current_matrix()
    by_id = {row["hypothesis"]: row for row in rows}
    assert len(rows) == 10
    assert by_id["#66 H1 risk"]["implementation_status"] == "IMPLEMENTED"
    assert by_id["#66 H1 risk"]["test_status"] == "TESTED"
    assert by_id["#66 H1 risk"]["empirical_status"] == "NOT_RUN"
    assert by_id["#66 H1 risk"]["independent_status"] == "NOT_RUN"
    assert by_id["#72 H6 vintage macro"]["empirical_status"] == "DATA_BLOCKED"
    assert by_id["LEGACY ERF-01 atlas (adjacent evidence)"]["empirical_status"] == "EXPLORATORY"
    assert by_id["LEGACY ERF-01 atlas (adjacent evidence)"]["independent_status"] == "NOT_RUN"


def test_matrix_order_and_serialized_receipt_are_deterministic():
    reversed_matrix = evidence_matrix(tuple(reversed(CURRENT_EVIDENCE)))
    assert reversed_matrix == current_matrix()
    assert render_json() == render_json(tuple(reversed(CURRENT_EVIDENCE)))
    assert "PROSPECTIVE_NOT_RUN" in render_markdown()
    assert "79.5%" in render_markdown()


def test_scored_exploratory_entry_requires_source_run_and_artifact():
    _raises(ValueError, "source, run and artifact", lambda: _record(empirical_status="EXPLORATORY"))
    observed = _record(empirical_status="EXPLORATORY", source_class="seen_dev",
                       run_url="https://example.invalid/run/1", artifact_path="metrics.json")
    assert evidence_matrix([observed])[0]["source_class"] == "seen_dev"


def test_independent_validation_rejects_seen_development_evidence():
    _raises(ValueError, "seen-development", lambda: _record(
        empirical_status="EXPLORATORY", independent_status="INDEPENDENTLY_VALIDATED",
        source_class="seen_dev", protocol_sha="a" * 40,
        run_url="https://example.invalid/run/1", artifact_path="metrics.json",
        source_manifest_sha="b" * 64))


def test_independent_validation_requires_frozen_protocol_and_data_manifest():
    valid = _record(empirical_status="EXPLORATORY", independent_status="INDEPENDENTLY_VALIDATED",
                    source_class="prospective_unseen", protocol_sha="a" * 40,
                    run_url="https://example.invalid/run/2", artifact_path="metrics.json",
                    source_manifest_sha="b" * 64)
    assert evidence_matrix([valid])[0]["independent_status"] == "INDEPENDENTLY_VALIDATED"
    _raises(ValueError, "complete run provenance", lambda: replace(
        valid, source_manifest_sha=None))


def test_data_blocked_rows_need_a_specific_blocker_and_not_run_has_no_result():
    _raises(ValueError, "specific blocker", lambda: _record(empirical_status="DATA_BLOCKED"))
    _raises(ValueError, "cannot claim a run artifact", lambda: _record(
        run_url="https://example.invalid/run/3", artifact_path="metrics.json"))


def test_versioned_ledger_files_match_the_validated_evidence_matrix():
    repo_root = Path(__file__).resolve().parents[1]
    verify_frozen_protocol(repo_root)
    markdown, machine = write_ledger(repo_root)
    assert markdown.read_text(encoding="utf-8") == render_markdown()
    assert machine.read_text(encoding="utf-8") == render_json()
