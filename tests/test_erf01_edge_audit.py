"""Prevent a single lucky alert from obtaining false ERF-01 'edge' status."""
from scripts.erf01_edge_audit import assess


def example():
    return {
        "data": {"source": "kepler_tape", "canonical_qc": True},
        "counts": {"confirmed_onsets_oos": 100},
        "forecast_gate_passed": True, "verdict": "INCONCLUSIVE",
        "operational_gate": {"passed": True, "alerts": 1},
    }


def alert(i: int, true: bool = True):
    return {
        "fold": f"fold-{i % 5}", "date": f"2025-01-{i + 1:02d}",
        "symbol": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"][i % 4],
        "true_alert": true, "matched_onset": f"2025-02-{i + 1:02d}" if true else "",
    }


def test_missing_market_data_never_certifies():
    m = example()
    m["data"]["canonical_qc"] = False
    assert assess(m, [alert(0)])["status"] == "NOT_RUN"


def test_one_lucky_alert_cannot_certify_edge():
    result = assess(example(), [alert(0)])
    assert result["status"] == "INSUFFICIENT_OPERATIONAL_EVIDENCE"
    assert not result["checks"]["confirmed_alerts"]
    assert not result["checks"]["onset_recall"]


def test_duplicate_or_mismatched_alert_counts_are_invalid():
    m = example()
    assert assess(m, [alert(0), alert(0)])["status"] == "INVALID"
    m["operational_gate"]["alerts"] = 2
    assert assess(m, [alert(0), alert(0)])["status"] == "INVALID"


def test_good_forecast_still_is_not_economic_edge():
    m = example()
    m["operational_gate"]["alerts"] = 24
    rows = [alert(i) for i in range(24)]
    res = assess(m, rows)
    assert res["status"] == "FORECAST_CANDIDATE_ONLY"
    assert res["economic_edge"] == "NOT_RUN"
    assert res["independent_confirmation"] == "NOT_RUN"


def test_frozen_screen_gate_must_pass_first():
    m = example()
    m["forecast_gate_passed"] = False
    assert assess(m, [alert(0)])["status"] == "NO_EDGE_OR_INCONCLUSIVE"
