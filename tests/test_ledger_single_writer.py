"""Tek yazarlı defter: işçiler ayrı teslim dosyası yazar, merkezi `ingest` doğrular ve ekler; tekrar teslim sayılmaz."""
import json
from pathlib import Path

import pytest

from factory.ingest import ingest
from kepler import evaluate, ledger

CFG = {"name": "a", "audit_causal": True}


def _worker(stage, n):
    return ledger.record(ledger.Staging(stage), "referee", f"h{n}", {"name": f"a{n}", "audit_causal": True}, "code", "data", result={"net_pnl": float(n)})


def test_workers_never_touch_the_ledger_and_ingest_counts_each_once(tmp_path):
    stage, book = tmp_path / "staging", tmp_path / "ledger.jsonl"
    _worker(stage, 1)
    _worker(stage, 2)
    assert not book.exists()  # işçi defteri değiştirmez
    assert ingest(book, stage) == dict(added=2, duplicate=0, rejected=0)
    assert [r["trial"] for r in map(json.loads, book.read_text().splitlines())] == [1, 2]
    assert not list(stage.glob("*.json"))  # işlenenler silinir
    _worker(stage, 1)  # aynı deneme yeniden teslim edildi (örn. yeniden koşu)
    assert ingest(book, stage) == dict(added=0, duplicate=1, rejected=0)
    assert len(book.read_text().splitlines()) == 2  # ne çift kayıt ne sayaç sapması


def test_tampered_or_corrupt_deliveries_are_rejected_not_counted(tmp_path):
    stage, book = tmp_path / "staging", tmp_path / "ledger.jsonl"
    good = _worker(stage, 3)
    bad = stage / f"{good['delivery']}.json"
    body = json.loads(bad.read_text())
    body["result"]["net_pnl"] = 999.0  # içerik değişti, kimlik eski
    bad.write_text(json.dumps(body))
    (stage / "junk.json").write_text("{not json")
    assert ingest(book, stage) == dict(added=0, duplicate=0, rejected=2)
    assert (stage / "rejected").is_dir() and not book.exists()


def test_staging_keeps_the_referee_gates(tmp_path):
    with pytest.raises(ValueError):  # nedensellik denetimi geçmemiş
        ledger.record(ledger.Staging(tmp_path), "referee", "h", {"name": "a"}, "c", "d", result={"net_pnl": 1.0})
    with pytest.raises(ValueError):  # eksik funding: geçerli sonuç değil
        ledger.record(ledger.Staging(tmp_path), "referee", "h", CFG, "c", "d", result={"net_pnl": 1.0, "funding_missed": 2})


def test_evaluate_can_stage_into_a_worker_dir(tmp_path):
    import pandas as pd

    from kepler.referee import Spec

    idx = pd.date_range("2024-01-01", periods=400, freq="1h", tz="UTC")
    px = 100 + pd.Series(range(400), index=idx, dtype=float).mul(0.05)
    kl = pd.DataFrame({"open": px, "high": px + 0.5, "low": px - 0.5, "close": px, "volume": 1000.0}, index=idx)
    sp = Spec(tick="0.01", step="0.001", capital=10000.0, liq=True, fee_rt_bps=10.0, slip_rt_bps=2.0)
    out = evaluate.evaluate(lambda k: pd.Series(1.0, index=k.index), kl, [sp], ledger.Staging(tmp_path / "w"), "h", "d")
    assert out[0]["row"]["config_hash"] and out[0]["row"]["delivery"]
    assert not (tmp_path / "ledger.jsonl").exists()


def test_fingerprint_covers_core_deps_and_loaded_project_modules():
    seen = []
    orig = ledger.code_hash
    try:
        ledger.code_hash = lambda *paths: seen.extend(Path(p).resolve() for p in paths) or orig(*paths)
        ledger.code_fingerprint()
    finally:
        ledger.code_hash = orig
    root = ledger.ROOT
    assert (root / "pyproject.toml").resolve() in seen and (root / "uv.lock").resolve() in seen
    assert (root / "kepler" / "referee_core.py").resolve() in seen
    assert (root / "factory" / "enqueue.py").resolve() in seen  # yüklü proje modülü (scripts/factory) de parmak izine girer
