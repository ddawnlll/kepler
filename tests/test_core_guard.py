"""Korumalı çekirdek listesi motor değişince boşluk bırakmaz (stdlib)."""
import importlib.util
import os
from pathlib import Path
from unittest.mock import patch


def test_referee_core_is_protected_without_an_unlock():
    path = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "guard.py"
    spec = importlib.util.spec_from_file_location("kepler_guard_regression", path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    with patch.dict(os.environ, {"KEPLER_CORE_UNLOCK": "0"}):
        verdict, _ = guard.classify("kepler/referee_core.py", is_new=False)
    assert verdict == "deny"
