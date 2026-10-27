"""Fail-closed static guard for named research workflows while budget is unapproved.

This does not prove provider-side runtime/billing caps, stop external Modal dispatch,
or replace explicit owner authorization. It intentionally disables every job in
these workflows, including jobs added later or invoking Modal differently.
"""

import json
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PAID_RESEARCH_WORKFLOWS = (
    "erf01-overnight-research.yml",
    "erf01-regime-atlas.yml",
    "pmi-v2-modal.yml",  # optional until the draft PMI stack is integrated
)


def _job_blocks(source: str):
    jobs_header = re.search(r"(?m)^jobs:\s*$", source)
    assert jobs_header, "research workflow must have a jobs section"
    jobs = source[jobs_header.end():]
    headers = list(re.finditer(r"(?m)^  ([a-zA-Z][\w-]*):\s*$", jobs))
    assert headers, "research workflow must have at least one job"
    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(jobs)
        yield header.group(1), jobs[header.end():end]


def _assert_paused_workflow(source: str, name: str):
    # Disallow inline/multi-trigger syntax; the only permitted trigger is a
    # top-level manual workflow_dispatch mapping, with no implicit extra events.
    on_header = re.search(r"(?m)^on:\s*$", source)
    assert on_header, f"{name}: expected explicit top-level on: mapping"
    triggers = []
    for line in source[on_header.end():].splitlines():
        if line.strip() and not line[0].isspace() and not line.startswith("#"):
            break
        trigger = re.match(r"^  ([A-Za-z_][\w-]*):", line)
        if trigger:
            triggers.append(trigger.group(1))
    assert triggers == ["workflow_dispatch"], f"{name}: only manual dispatch is permitted"

    # Guard ALL jobs, not just jobs containing the literal 'modal run'. A new
    # job or a changed command spelling must not bypass the hold.
    for job, block in _job_blocks(source):
        assert re.search(r"(?m)^    if:\s*\$\{\{\s*false\s*\}\}\s*$", block), (
            f"{name}/{job}: job-level disabled guard required until fresh "
            "owner authorization and provider-side hard caps"
        )


def test_research_factory_remains_paused():
    policy = json.loads((ROOT / "factory/policy.json").read_text(encoding="utf-8"))
    assert policy["research_enabled"] is False


def test_paid_research_workflows_cannot_dispatch_remote_compute():
    workflows = ROOT / ".github/workflows"
    assert (workflows / PAID_RESEARCH_WORKFLOWS[0]).is_file()
    assert (workflows / PAID_RESEARCH_WORKFLOWS[1]).is_file()
    for name in PAID_RESEARCH_WORKFLOWS:
        path = workflows / name
        if path.exists():
            _assert_paused_workflow(path.read_text(encoding="utf-8"), name)


@pytest.mark.parametrize("injection", [
    "  push:\n",  # new automatic trigger
    "  workflow_call:\n",  # reusable workflow dispatch
])
def test_rejects_extra_triggers(injection):
    source = "on:\n  workflow_dispatch:\n" + injection + "jobs:\n  compute:\n    if: ${{ false }}\n"
    with pytest.raises(AssertionError, match="only manual dispatch"):
        _assert_paused_workflow(source, "synthetic.yml")


def test_rejects_new_job_without_guard_even_if_modal_command_is_renamed():
    source = ("on:\n  workflow_dispatch:\njobs:\n  old:\n    if: ${{ false }}\n"
              "  new:\n    runs-on: ubuntu-latest\n    steps:\n"
              "      - run: python -m modal run modal_app.py\n")
    with pytest.raises(AssertionError, match="new: job-level disabled"):
        _assert_paused_workflow(source, "synthetic.yml")
