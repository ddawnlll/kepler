"""Compare frozen pre-refactor and post-refactor real-DEV atlas outputs.

Run inside the pinned Modal DEV environment after the two runs have completed.
A moved source file necessarily changes its SHA; scientific fields must not change.
"""
import json
from pathlib import Path

REFERENCE = Path("/data/erf01/regime_atlas_20261015/metrics.json")
CANDIDATE = Path("/data/erf01/refactor_parity_20261016/metrics.json")
EXPECTED_PROVENANCE_CHANGE = {"source_sha256", "erf01_definition_sha256"}


def compare(reference: dict, candidate: dict) -> dict:
    old = {k: v for k, v in reference.items() if k not in EXPECTED_PROVENANCE_CHANGE}
    new = {k: v for k, v in candidate.items() if k not in EXPECTED_PROVENANCE_CHANGE}
    if old != new:
        mismatched = sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k))
        raise AssertionError("Scientific refactor parity FAIL, changed top-level keys: " + ", ".join(mismatched))
    assert reference["source_sha256"] != candidate["source_sha256"]
    assert reference["erf01_definition_sha256"] != candidate["erf01_definition_sha256"]
    return {"status": "PASS", "compared_keys": len(old), "excluded_code_sha_keys": sorted(EXPECTED_PROVENANCE_CHANGE),
            "finite_asset_days": new["descriptive_counts"]["finite_asset_days"],
            "horizons": sorted(new["forecast_oos_horizon_days"].keys())}


if __name__ == "__main__":
    if not REFERENCE.is_file() or not CANDIDATE.is_file():
        raise SystemExit("NOT_RUN: missing saved real-DEV atlas evidence; do not claim numeric parity")
    a = json.loads(REFERENCE.read_text())
    b = json.loads(CANDIDATE.read_text())
    print("ERF01_REFACTOR_PARITY=" + json.dumps(compare(a, b), sort_keys=True), flush=True)
