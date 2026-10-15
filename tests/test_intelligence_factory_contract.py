"""Research entrypoint registry and provenance boundary."""
from factory.entrypoints import RESEARCH_ENTRYPOINTS
from factory.research import fingerprint
from pathlib import Path

def test_atlas_is_explicitly_registered():
    assert "experiments/erf01/atlas.py" in RESEARCH_ENTRYPOINTS
    assert all(path.endswith(".py") and ".." not in path for path in RESEARCH_ENTRYPOINTS)

def test_scientific_source_is_in_code_hash(monkeypatch, tmp_path):
    from kepler import ledger
    root = tmp_path
    for name in ("kepler", "scripts", "experiments"):
        (root / name).mkdir()
    for name in ("pyproject.toml", "uv.lock"):
        (root / name).write_text("v1")
    (root / "kepler" / "ledger.py").write_text("v1")
    (root / "experiments" / "example.py").write_text("v1")
    monkeypatch.setattr(ledger, "__file__", str(root / "kepler" / "ledger.py"))
    first = ledger.code_hash()
    (root / "experiments" / "example.py").write_text("v2")
    assert ledger.code_hash() != first
