"""Editing core code and existing tests does not require a magic environment switch."""
import importlib.util
from pathlib import Path


def _guard():
    path = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "guard.py"
    spec = importlib.util.spec_from_file_location("kepler_guard_regression", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_core_and_existing_tests_are_editable():
    guard = _guard()
    for path in ("kepler/referee_core.py", "tests/test_referee.py", "AGENTS.md", "factory/runner.py"):
        assert guard.classify(path, is_new=False)[0] == "allow"


def test_generated_evidence_is_not_agent_edited():
    guard = _guard()
    for path in ("ledger/trials.jsonl", "registry/events.jsonl", "state/queue.jsonl"):
        assert guard.classify(path, is_new=False)[0] == "deny"
