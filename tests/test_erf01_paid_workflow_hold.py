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
    # Reject duplicate YAML keys: a later jobs/job key can replace an earlier
    # guarded block in parsers that silently accept duplicate mappings.
    jobs_headers = list(re.finditer(r"(?m)^jobs:[ \t]*$", source))
    assert len(jobs_headers) == 1, "exactly one jobs section required"
    jobs = source[jobs_headers[0].end():]
    # Valid YAML allows inline job mappings and job IDs beginning with "_".
    # Fail closed rather than silently skipping any unguarded job declaration.
    for line in jobs.splitlines():
        if line.startswith("  ") and not line.startswith("   ") and line.strip() and not line.lstrip().startswith("#"):
            assert re.fullmatch(r"  [A-Za-z][\w-]*:[ \t]*", line), (
                f"noncanonical or unguarded job declaration: {line!r}"
            )
    headers = list(re.finditer(r"(?m)^  ([a-zA-Z][\w-]*):[ \t]*$", jobs))
    assert headers, "research workflow must have at least one job"
    seen = set()
    for index, header in enumerate(headers):
        name = header.group(1)
        assert name not in seen, f"duplicate job name: {name}"
        seen.add(name)
        end = headers[index + 1].start() if index + 1 < len(headers) else len(jobs)
        yield name, jobs[header.end():end]


def _assert_paused_workflow(source: str, name: str):
    # Disallow inline/multi-trigger syntax; the only permitted trigger is a
    # top-level manual workflow_dispatch mapping, with no implicit extra events.
    on_headers = list(re.finditer(r"(?m)^on:[ \t]*$", source))
    assert len(on_headers) == 1, f"{name}: exactly one top-level on mapping required"
    triggers = []
    for line in source[on_headers[0].end():].splitlines():
        if line.strip() and not line[0].isspace() and not line.startswith("#"):
            break
        # Quoted YAML event keys (e.g. "push":) are valid in Actions.
        # Count every trigger-level mapping entry; do not silently ignore
        # quoted keys, explicit keys or YAML merge-key syntax.
        if line.startswith("  ") and not line.startswith("   ") and line.strip() and not line.lstrip().startswith("#"):
            assert re.fullmatch(r"  workflow_dispatch:[ \t]*", line), (
                f"{name}: only manual dispatch is permitted"
            )
            triggers.append("workflow_dispatch")
    assert triggers == ["workflow_dispatch"], f"{name}: only manual dispatch is permitted"

    # Guard ALL jobs, not just jobs containing the literal 'modal run'. A new
    # job or a changed command spelling must not bypass the hold.
    for job, block in _job_blocks(source):
        # A second job-level 'if:' can override an earlier false guard.
        guards = [value.strip() for value in re.findall(r"(?m)^    if:[ \t]*(.*)$", block)]
        assert len(guards) == 1 and re.fullmatch(r"\$\{\{\s*false\s*\}\}", guards[0]), (
            f"{name}/{job}: exactly one job-level disabled guard required until fresh "
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
    '  "push":\n',  # valid quoted YAML event key
    "  'push':\n",  # valid single-quoted YAML event key
    "  <<: *events\n",  # YAML merge-key injection must fail closed
])
def test_rejects_extra_triggers(injection):
    source = "on:\n  workflow_dispatch:\n" + injection + "jobs:\n  compute:\n    if: ${{ false }}\n"
    with pytest.raises(AssertionError, match="only manual dispatch"):
        _assert_paused_workflow(source, "synthetic.yml")


def test_rejects_new_job_without_guard_even_if_modal_command_is_renamed():
    source = ("on:\n  workflow_dispatch:\njobs:\n  old:\n    if: ${{ false }}\n"
              "  new:\n    runs-on: ubuntu-latest\n    steps:\n"
              "      - run: python -m modal run modal_app.py\n")
    with pytest.raises(AssertionError, match="new: exactly one job-level disabled"):
        _assert_paused_workflow(source, "synthetic.yml")


@pytest.mark.parametrize("injection, expected", [
    ("    if: ${{ true }}\n", "exactly one job-level disabled guard"),
    ("  compute:\n    if: ${{ true }}\n", "duplicate job name"),
    ("jobs:\n  replacement:\n    if: ${{ true }}\n", "exactly one jobs section"),
    ("on:\n  push:\n", "exactly one top-level on mapping"),
])
def test_rejects_duplicate_yaml_keys_that_can_override_pause(injection, expected):
    source = "on:\n  workflow_dispatch:\njobs:\n  compute:\n    if: ${{ false }}\n"
    with pytest.raises(AssertionError, match=expected):
        _assert_paused_workflow(source + injection, "synthetic.yml")


@pytest.mark.parametrize("injection", [
    "  rogue: {runs-on: ubuntu-latest, steps: [{run: echo-bypass}]}\n",
    "  _rogue:\n    runs-on: ubuntu-latest\n",
    "  rogue: # comment disguises a valid YAML job\n    runs-on: ubuntu-latest\n",
])
def test_rejects_unguarded_noncanonical_job_keys(injection):
    source = "on:\n  workflow_dispatch:\njobs:\n  compute:\n    if: ${{ false }}\n" + injection
    with pytest.raises(AssertionError, match="noncanonical or unguarded job declaration"):
        _assert_paused_workflow(source, "synthetic.yml")
