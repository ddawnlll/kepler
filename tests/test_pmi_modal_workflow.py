"""Safety contracts for the manual, bounded PMI Modal workflow."""
from pathlib import Path


def test_pmi_modal_workflow_is_manual_bounded_and_serialized_across_refs():
    workflow = (Path(__file__).parents[1] / ".github/workflows/pmi-v2-modal.yml").read_text()
    assert "  workflow_dispatch:" in workflow
    assert "  group: pmi-v2-modal" in workflow
    assert "group: pmi-v2-${{ github.ref }}" not in workflow
    assert "  cancel-in-progress: false" in workflow
    assert "    timeout-minutes: 15" in workflow
    assert "timeout --signal=TERM --kill-after=10s 430s modal run" in workflow
    assert 'test -n "$MODAL_TOKEN_ID" && test -n "$MODAL_TOKEN_SECRET"' in workflow
    assert 'git merge-base --is-ancestor "$protocol_sha" HEAD' in workflow
    assert 'test "$committed_sha" = "$working_sha"' in workflow
