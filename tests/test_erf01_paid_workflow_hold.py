"""Fail-closed regression guard for research compute while budget is unapproved.

This intentionally does not attempt Modal access or prove provider-side billing caps.
It prevents a future PR from silently enabling a paid manual workflow on main.
"""

import json
import re
from pathlib import Path


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


def test_research_factory_remains_paused():
    policy = json.loads((ROOT / "factory/policy.json").read_text(encoding="utf-8"))
    assert policy["research_enabled"] is False


def test_paid_research_workflows_cannot_dispatch_remote_compute():
    workflows = ROOT / ".github/workflows"
    assert (workflows / PAID_RESEARCH_WORKFLOWS[0]).is_file()
    assert (workflows / PAID_RESEARCH_WORKFLOWS[1]).is_file()
    for name in PAID_RESEARCH_WORKFLOWS:
        path = workflows / name
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8")
        assert re.search(r"(?m)^  workflow_dispatch:\s*$", source), name
        assert not re.search(r"(?m)^  (?:schedule|push|pull_request):\s*$", source), name
        paid_jobs = [(job, block) for job, block in _job_blocks(source)
                     if re.search(r"\bmodal\s+run\b", block)]
        assert paid_jobs, f"{name}: expected at least one research compute job"
        for job, block in paid_jobs:
            assert re.search(r"(?m)^    if:\s*\$\{\{\s*false\s*\}\}\s*$", block), (
                f"{name}/{job}: remote compute must remain job-level disabled "
                "until fresh owner authorization and provider-side hard caps"
            )
