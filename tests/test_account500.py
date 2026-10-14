"""#16: $500 uygulanabilirlik ölçütleri ve metrikleri (sentetik; gerçek replay Modal'de scripts/account500.py)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import account500 as a5  # noqa: E402


def M(**kw):
    base = dict(blocked_share=0.01, net_rel_diff=0.01, abs_dsharpe=0.02, n_rejected=0, n_engine_unfilled=0, n_liq=0, recon_ok=True, unmapped_target_share=0.0)
    return {**base, **kw}


def test_verdict_never_pass_with_permanent_unknowns_and_fails_on_violations():
    v = a5.verdict(M())
    assert v["overall"] == "UNKNOWN" and not v["failed"] and "hesap ücreti/VIP/indirim" in v["permanent_unknown"]  # ücret doğrulanmadan PASS yok
    assert a5.verdict(M(blocked_share=0.17))["overall"] == "FAIL"  # %17 niyet gönderilemiyor (issue örneği)
    assert a5.verdict(M(net_rel_diff=0.06))["failed"] == ["C2_outcome"] and a5.verdict(M(abs_dsharpe=0.11))["overall"] == "FAIL"
    assert a5.verdict(M(n_liq=1))["failed"] == ["C3_integrity"] and a5.verdict(M(recon_ok=False))["overall"] == "FAIL"
    assert a5.verdict(M(unmapped_target_share=0.2))["criteria"]["C4_rules_coverage"][0] == "UNKNOWN"  # eşlenmemiş sembol: bilinmiyor, FAIL değil


def test_metrics_blocked_deviation_and_no_round_up():
    it = pd.DataFrame(dict(sym=["A", "A", "A"], ts=[1, 2, 3], target_notional=[100.0, 104.0, -50.0], px=[100.0, 100.0, 100.0], pos_qty=[0.0, 1.0, 1.0], want_qty=[1.0, 1.04, -0.5],
                           delta_qty=[1.0, 0.04, -1.5], gap_notional=[0.0, 4.0, -100.0], status=["sent", "blocked_minimum", "sent"], filled_qty=[1.0, 0.0, 1.5], reason=["", "", ""]))
    fills = pd.DataFrame(dict(qty=[1.0, 1.5], px=[100.0, 100.0]))
    s = dict(net_pnl=10.0, blocked_notional=4.0, fee=0.1, slippage=0.0, funding=0.0, gross_pnl=10.1, n_fills=2, n_rejected=0, n_engine_unfilled=0, n_liq=0, funding_missed=0)
    res, ref = dict(summary=s, fills=fills, sharpe=1.0), dict(summary=dict(s, net_pnl=10.2), sharpe=1.05)
    m = a5.metrics(res, ref, it, 0.0, dict(ok=True, diff=0.0), cap=500.0)
    assert m["blocked_share"] == pytest.approx(1 / 3) and m["net_rel_diff"] == pytest.approx(0.2 / 10.2) and m["abs_dsharpe"] == pytest.approx(0.05)
    # bloke satırda fiilen tutulan 1,0 birim (100) vs hedef 104: sapma 4/104; gönderilende hedef gerçekleşen 'want' ile ölçülür (sert yukarı yuvarlama yok)
    assert m["dev_median"] == 0 and m["risk_dev_share"] == pytest.approx(4 / 254) and m["turnover_x_cap"] == pytest.approx(250 / 500)
    assert a5.SCENARIOS["stress_16+4"] == (16.0, 4.0) and a5.SCENARIOS["model_10+2"] == (10.0, 2.0)


def test_rules_file_is_dated_and_sourced():
    import json
    d = json.loads(a5.RULES.read_text())
    assert d["fetched_utc"].startswith("2026-") and d["source"].startswith("https://contract.mexc.com") and "BTCUSDT" in d["symbols"] and d["symbols"]["BTCUSDT"]["minVol"] >= 1
