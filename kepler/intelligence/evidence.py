"""Provenance-first status records for predictive-market research claims."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Sequence


IMPLEMENTATION_STATUSES = frozenset({"IMPLEMENTED", "NOT_RUN"})
TEST_STATUSES = frozenset({"TESTED", "NOT_RUN"})
EMPIRICAL_STATUSES = frozenset({"EXPLORATORY", "INCONCLUSIVE", "DATA_BLOCKED", "NOT_RUN"})
INDEPENDENT_STATUSES = frozenset({"INDEPENDENTLY_VALIDATED", "NOT_RUN"})
SOURCE_CLASSES = frozenset({"none", "seen_dev", "prospective_unseen", "external_unseen"})


@dataclass(frozen=True)
class EvidenceRecord:
    """Separate implementation, test, empirical and independent evidence."""

    hypothesis: str
    implementation_status: str
    test_status: str
    empirical_status: str
    independent_status: str
    source_class: str = "none"
    protocol_path: str | None = None
    protocol_sha: str | None = None
    review_url: str | None = None
    branch: str | None = None
    run_url: str | None = None
    artifact_path: str | None = None
    source_manifest_sha: str | None = None
    blocker: str | None = None
    note: str = ""

    def __post_init__(self):
        if not self.hypothesis:
            raise ValueError("hypothesis identifier is required")
        allowed = (
            ("implementation_status", self.implementation_status, IMPLEMENTATION_STATUSES),
            ("test_status", self.test_status, TEST_STATUSES),
            ("empirical_status", self.empirical_status, EMPIRICAL_STATUSES),
            ("independent_status", self.independent_status, INDEPENDENT_STATUSES),
            ("source_class", self.source_class, SOURCE_CLASSES),
        )
        for name, value, values in allowed:
            if value not in values:
                raise ValueError(f"invalid {name}: {value}")
        if self.protocol_sha is not None and not re.fullmatch(r"[0-9a-f]{40}", self.protocol_sha):
            raise ValueError("protocol_sha must be a full lowercase Git commit SHA")
        if self.source_manifest_sha is not None and not re.fullmatch(
                r"[0-9a-f]{64}", self.source_manifest_sha):
            raise ValueError("source_manifest_sha must be a full lowercase SHA-256")
        if self.empirical_status in {"EXPLORATORY", "INCONCLUSIVE"}:
            if not (self.source_class != "none" and self.run_url and self.artifact_path):
                raise ValueError("scored empirical evidence requires source, run and artifact provenance")
        if self.empirical_status == "DATA_BLOCKED" and not self.blocker:
            raise ValueError("DATA_BLOCKED evidence requires its specific blocker")
        if self.empirical_status == "NOT_RUN" and any(
                (self.run_url, self.artifact_path, self.source_manifest_sha)):
            raise ValueError("NOT_RUN evidence cannot claim a run artifact or data manifest")
        if self.independent_status == "INDEPENDENTLY_VALIDATED":
            if self.source_class not in {"prospective_unseen", "external_unseen"}:
                raise ValueError("seen-development data cannot support independent confirmation")
            if (self.empirical_status not in {"EXPLORATORY", "INCONCLUSIVE"}
                    or not self.protocol_sha or not self.run_url or not self.artifact_path
                    or not self.source_manifest_sha):
                raise ValueError("independent validation requires a frozen protocol and complete run provenance")


def evidence_matrix(records: Sequence[EvidenceRecord]) -> list[dict]:
    """Validate unique claim IDs and return a stable, serializable matrix."""
    by_hypothesis = {}
    for record in records:
        if not isinstance(record, EvidenceRecord):
            raise TypeError("evidence matrix entries must be EvidenceRecord values")
        if record.hypothesis in by_hypothesis:
            raise ValueError(f"duplicate evidence row: {record.hypothesis}")
        # Reconstruct so mutated or deserialized data cannot skip validation.
        EvidenceRecord(**asdict(record))
        by_hypothesis[record.hypothesis] = asdict(record)
    return [by_hypothesis[key] for key in sorted(by_hypothesis)]
