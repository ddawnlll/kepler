"""Nedensellik kapısı boyutlamayı, deney kimliği tüm paket davranışını kapsar."""
from pathlib import Path

import pandas as pd
import pytest

from kepler import evaluate as ev, ledger
from kepler.referee import Spec
from tests.test_trust import market


def unit(kl):
    return pd.Series(1.0, index=kl.index)


def sp():
    return Spec(tick="0.01", capital=10000.0, slip_rt_bps=2.0)


def test_leaking_sizer_cannot_be_recorded_as_causal(tmp_path):
    def leak(kl, u, capital):
        return u * kl.close.shift(-1)

    path = tmp_path / "ledger.jsonl"
    with pytest.raises(AssertionError, match="geleceğe"):
        ev.evaluate(unit, market(), [sp()], path, "regression", "synthetic", size=leak)
    assert not path.exists()


def test_nondeterministic_sizer_is_rejected_even_with_causality_stubbed(tmp_path, monkeypatch):
    monkeypatch.setattr(ev.audit, "assert_causal", lambda *a: None)
    calls = []

    def changing(kl, u, capital):
        calls.append(1)
        return u * (100.0 + len(calls))

    path = tmp_path / "ledger.jsonl"
    with pytest.raises(ValueError, match="belirlenimsiz"):
        ev.evaluate(unit, market(), [sp()], path, "regression", "synthetic", size=changing)
    assert not path.exists()


def test_valid_sizer_is_audited_and_recorded(tmp_path):
    def size(kl, u, capital):
        return u * capital / 10

    result = ev.evaluate(unit, market(), [sp()], tmp_path / "ledger.jsonl", "regression", "synthetic", size=size)[0]
    assert result["row"]["config"]["audit_causal"] is True
    assert result["res"]["summary"]["n_fills"] > 0


def test_core_source_change_changes_experiment_hash(tmp_path, monkeypatch):
    kl, path = market(), tmp_path / "ledger.jsonl"
    before = ev.evaluate(unit, kl, [sp()], path, "regression", "synthetic")[0]
    original = Path.read_bytes
    core = Path(ev.__file__).parent / "referee_core.py"

    def changed(file, *args, **kwargs):
        text = original(file, *args, **kwargs)
        return text + b"\n# changed core source\n" if file.resolve() == core.resolve() else text

    monkeypatch.setattr(Path, "read_bytes", changed)
    after = ev.evaluate(unit, kl, [sp()], path, "regression", "synthetic")[0]
    assert before["row"]["config_hash"] == after["row"]["config_hash"]
    assert before["row"]["code_hash"] != after["row"]["code_hash"]


@pytest.mark.parametrize("book", [False, True])
def test_experiment_hash_includes_core_risk_report_and_experts(tmp_path, monkeypatch, book):
    paths = set()
    original = ledger.code_hash

    def capture(*files):
        paths.update(Path(p).resolve() for p in files)
        return original(*files)

    monkeypatch.setattr(ledger, "code_hash", capture)
    kl = market()
    path = tmp_path / "ledger.jsonl"
    if book:
        def producer(kls):
            return {s: pd.DataFrame({"target": 100.0, "stop": float("nan")}, index=k.index) for s, k in kls.items()}
        ev.evaluate_book(producer, {"X": {"kl": kl}}, [sp()], path, "regression", "synthetic")
    else:
        ev.evaluate(unit, kl, [sp()], path, "regression", "synthetic")
    package = Path(ev.__file__).parent
    for file in ["referee_core.py", "risk.py", "report.py", "portfolio.py", "ensemble.py", "experts/trend.py"]:
        assert (package / file).resolve() in paths, file
