"""Korumalı çekirdek: Edit/Write ve Bash (silme, taşıma, üzerine yazma) kilit kapalıyken reddedilir; okuma serbest."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / ".claude" / "hooks" / "guard.py"


def _guard():
    spec = importlib.util.spec_from_file_location("kepler_guard_protection", GUARD)
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    return g


def test_core_files_and_existing_tests_are_denied_without_unlock():
    g = _guard()
    with patch.dict(os.environ, {"KEPLER_CORE_UNLOCK": "0"}):
        assert g.classify("kepler/referee_core.py", is_new=False)[0] == "deny"
        assert g.classify("kepler/referee_core.py", is_new=True)[0] == "deny"
        assert g.classify("tests/test_enqueue.py", is_new=False)[0] == "deny"
        assert g.classify("factory/enqueue.py", is_new=False)[0] == "deny"
        assert g.classify("tests/test_new_thing.py", is_new=True)[0] == "allow"  # yeni test serbest


def test_bash_destructive_commands_on_core_are_denied():
    g = _guard()
    for cmd in ["rm kepler/referee_core.py", "git rm -q kepler/referee.py", "rm -rf kepler", "rm kepler/*.py",
                "sed -i 's/a/b/' kepler/evaluate.py", "echo x >kepler/referee.py", "mv state/queue.jsonl /tmp/q",
                "find . -name '*.pyc' -delete", "cat x; rm kepler/risk.py", "dd if=/dev/zero of=kepler/state.py"]:
        assert g.bash_hits(cmd), cmd


def test_bash_reads_and_scratch_writes_are_allowed():
    g = _guard()
    for cmd in ["cat kepler/referee.py > /tmp/x", "git diff kepler/referee.py", "python3 -m pytest -q 2>&1 | tail -3",
                "echo ok >> reports/a.md", "rm /tmp/scratch.txt", "echo x > 2>&1"]:
        assert g.bash_hits(cmd) == [], cmd


def test_pretool_blocks_bash_rm_and_passes_reads_end_to_end():
    def run(cmd, unlock="0"):
        ev = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
        return subprocess.run([sys.executable, str(GUARD), "pretool"], input=ev, text=True, capture_output=True,
                              env={**os.environ, "KEPLER_CORE_UNLOCK": unlock}).returncode
    assert run("rm kepler/referee_core.py") == 2
    assert run("cat kepler/referee_core.py") == 0
    assert run("rm kepler/referee_core.py", unlock="1") == 0  # kilit açıkken serbest
