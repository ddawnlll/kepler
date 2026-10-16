from datetime import date, timedelta
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType

import numpy as np

from experiments.erf01 import tape_adapter
from experiments.market_intelligence.h5 import _within_fold_support, run_support_census


def test_support_window_is_inside_one_test_fold_and_before_seal():
    onset = date(2023, 5, 20)
    q = {onset - timedelta(days=i): 0.0 for i in range(7, 15)}
    event = {"status": "CONFIRMED", "confirmation_date": (onset + timedelta(days=10)).isoformat()}
    assert _within_fold_support(event, onset, q, date(2023, 1, 1), date(2024, 1, 1), date(2026, 4, 1))
    assert not _within_fold_support(event, onset, q, onset - timedelta(days=13),
                                    date(2024, 1, 1), date(2026, 4, 1))
    assert not _within_fold_support(event, onset, q, date(2023, 1, 1),
                                    date(2024, 1, 1), onset + timedelta(days=10))
    assert not _within_fold_support(event, onset, q, date(2023, 1, 1),
                                    date(2024, 1, 1), onset + timedelta(days=11))
    assert _within_fold_support(event, onset, q, date(2023, 1, 1),
                                date(2024, 1, 1), onset + timedelta(days=12))
    del q[onset - timedelta(days=10)]
    assert not _within_fold_support(event, onset, q, date(2023, 1, 1),
                                    date(2024, 1, 1), date(2026, 4, 1))


def test_synthetic_support_census_writes_no_scores_and_preserves_onset():
    # Use a local temporary directory so this remains safe under pytest and
    # when invoked directly by the bounded synthetic validation harness.
    with tempfile.TemporaryDirectory(prefix="pmi-h5-synthetic-") as temporary:
        out_dir = Path(temporary) / "run"
        original_loader = tape_adapter.load_development
        original_pipeline = sys.modules.get("experiments.erf01.pipeline")
        try:
            start, last = date(2020, 1, 1), date(2026, 3, 31)
            days = [start + timedelta(days=i) for i in range((last - start).days + 1)]
            onset = date(2023, 3, 15)
            q = np.zeros(len(days), dtype=float)
            index = (onset - start).days
            q[index:] = 1.0
            fake_pipeline = ModuleType("experiments.erf01.pipeline")
            fake_pipeline.DAYS = (start, last)
            fake_pipeline.FOLDS = [(date(2023, 1, 1), date(2024, 1, 1), "2023")]
            fake_pipeline.SYMS = ["A"]
            fake_pipeline.SEAL = date(2026, 4, 1)
            fake_pipeline.make_panel = lambda prices, funding: (days, {"A": {"q": q}})
            sys.modules["experiments.erf01.pipeline"] = fake_pipeline

            def fake_loader(root, symbols, first_day, last_day, seal):
                source = {"symbol": "A", "kind": "klines", "sha256": "a" * 64, "bytes": 1}
                return ({"A": {}}, {"A": []}, [], {"A": {"qc_findings": []}},
                        {"records": [source], "source_bytes": 1})

            tape_adapter.load_development = fake_loader
            result = run_support_census(Path("/synthetic/staging"), out_dir)
        finally:
            tape_adapter.load_development = original_loader
            if original_pipeline is None:
                sys.modules.pop("experiments.erf01.pipeline", None)
            else:
                sys.modules["experiments.erf01.pipeline"] = original_pipeline

        assert result["science_status"] == "EXPLORATORY"
        assert result["support_gate"] == "INCONCLUSIVE"
        assert result["scored_status"] == "NOT_RUN"
        assert result["warning_scores_emitted"] is False
        assert result["candidate_counts"]["confirmed"] == 1
        event_text = (out_dir / "events.jsonl").read_text(encoding="utf-8")
        event = json.loads(event_text)
        assert event["onset_date"] == onset.isoformat()
        assert event["confirmation_date"] == (onset + timedelta(days=10)).isoformat()
        assert event["support_eligible"] is True
        assert (out_dir / "metrics.json").is_file()
        assert (out_dir / "manifest.json").is_file()
