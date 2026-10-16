"""Known-answer tests for the unscored canonical-data smoke entry point."""
from datetime import date, datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.market_intelligence import smoke


def _valid_adapter_result(funding_timestamp_ms: int):
    days = [date(2026, 3, 1 + i) for i in range(7)]
    prices = {smoke.SYMBOL: {day: (1, 1, 1, 1, 1, 0, float("nan")) for day in days}}
    funding_records = [(smoke.SYMBOL, funding_timestamp_ms, 8.0, 0.0, 0.0)]
    metadata = {smoke.SYMBOL: {"qc_findings": [{
        "check": "fixture", "severity": "INFO", "detail": "synthetic", "count": 0, "first": "",
    }]}}
    records = [{"symbol": smoke.SYMBOL, "kind": kind, "sha256": f"{i:064x}",
                "bytes": 100, "path": f"/synthetic/{kind}"}
               for i, kind in enumerate(("klines", "markPriceKlines", "fundingRate"), 1)]
    acquisition = {"record_count": 3, "source_bytes": 300, "records": records}
    return prices, {}, funding_records, metadata, acquisition


class PmiSmokeTests(unittest.TestCase):
    def test_success_is_unscored_and_writes_hashable_receipt(self):
        seal_ms = int(datetime(2026, 4, 1, tzinfo=timezone.utc).timestamp() * 1000)
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "run"
            with patch.object(smoke, "load_development", return_value=_valid_adapter_result(seal_ms - 1)):
                result = smoke.run_smoke(Path(temp), out, run_url="https://example.invalid/run")
            self.assertEqual(result["status"], "DATA_READY")
            self.assertFalse(result["scored"])
            self.assertNotIn("scores", result)
            metrics = json.loads((out / "metrics.json").read_text())
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertEqual(metrics["preflight_id"], manifest["preflight_id"])
            self.assertEqual(metrics["source_validation"]["source_file_count"], 3)
            self.assertEqual(metrics["source_validation"]["qc_severity_counts"]["INFO"], 1)

    def test_seal_boundary_is_rejected_and_recorded(self):
        seal_ms = int(datetime(2026, 4, 1, tzinfo=timezone.utc).timestamp() * 1000)
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "run"
            with patch.object(smoke, "load_development", return_value=_valid_adapter_result(seal_ms)):
                result = smoke.run_smoke(Path(temp), out)
            self.assertEqual(result["status"], "DATA_BLOCKED")
            self.assertIn("exclusive development seal", result["failure"]["reason"])
            self.assertEqual(json.loads((out / "manifest.json").read_text())["status"], "DATA_BLOCKED")

    def test_adapter_failure_is_recorded_without_fabricated_metrics(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "run"
            with patch.object(smoke, "load_development", side_effect=FileNotFoundError("missing fixture")):
                result = smoke.run_smoke(Path(temp), out)
            self.assertEqual(result["status"], "DATA_BLOCKED")
            self.assertNotIn("source_validation", result)
            self.assertEqual(json.loads((out / "metrics.json").read_text())["scored"], False)

    def test_output_path_is_immutable(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "run"
            out.mkdir()
            with self.assertRaises(FileExistsError):
                smoke.run_smoke(Path(temp), out)


if __name__ == "__main__":
    unittest.main()
