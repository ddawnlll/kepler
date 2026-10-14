"""#18: QC bayrakları gerçek pozisyon/settlement olaylarıyla kesişir; etki notional ve USDT cinsinden; politikalar aynı muhasebe yolunda."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import qc_impact as qi  # noqa: E402

from kepler import report  # noqa: E402
from kepler.referee import Spec, run_portfolio  # noqa: E402

A = pytest.approx


def setup(n=30):
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    c = np.full(n, 100.0)
    kl = pd.DataFrame(dict(open=c, high=c, low=c, close=c, volume=1e6), index=idx).drop(idx[[14, 15]])  # 14:00-15:00 boşluk
    mark = kl.assign(close=kl.close)
    mark.loc[idx[20], "close"] = 110.0  # %10 mark/last ayrışması
    mark = mark.drop(idx[5])  # funding T=06:00 anında mark barı yok -> mark_fallback
    ts = [pd.Timestamp("2024-01-01 06:00", tz="UTC"), pd.Timestamp("2024-01-01 08:00", tz="UTC"), pd.Timestamp("2024-01-01 16:00", tz="UTC"), pd.Timestamp("2024-01-01 21:00", tz="UTC")]
    fund = pd.DataFrame(dict(last_funding_rate=[0.0001, 0.02, 0.0001, 0.0001], funding_interval_hours=[2, 2, 8, 8]), index=ts)  # 08:00 aşırı; 21:00 tutarsız (16:00'dan 5h, bildirilen 8)
    tgt = pd.Series(np.nan, index=kl.index)
    tgt.iloc[1] = 1000.0
    return dict(X=dict(kl=kl, mark=mark, funding=fund, target=tgt)), Spec(capital=10000.0, fee_rt_bps=10.0, slip_rt_bps=2.0, tick="0.01", step="0.001", fill="next_open", liq=False)


def test_flags_legit_interval_vs_inconsistent_and_bar_flags():
    data, sp = setup()
    fl = qi.flags(data["X"]["kl"], data["X"]["mark"], data["X"]["funding"])
    ev = fl["fund_events"]
    assert list(fl["gap"]) == [pd.Timestamp("2024-01-01 16:00", tz="UTC")] and list(fl["mark_last_div"]) == [pd.Timestamp("2024-01-01 20:00", tz="UTC")]
    assert bool(ev.loc[pd.Timestamp("2024-01-01 08:00", tz="UTC"), "fund_extreme"]) and bool(ev.loc[pd.Timestamp("2024-01-01 06:00", tz="UTC"), "mark_fallback"])
    assert ev.loc[pd.Timestamp("2024-01-01 08:00", tz="UTC"), "interval_consistent"]  # 2h aralık, 06->08 = 2h: meşru, anomali değil
    assert not ev.loc[pd.Timestamp("2024-01-01 21:00", tz="UTC"), "interval_consistent"]  # 16->21 = 5h ≠ 8h: UNKNOWN


def test_impact_hand_amounts_and_totals_match_referee():
    data, sp = setup()
    res = run_portfolio(data, sp)
    imp = qi.impact(data, res, sp)
    k = imp["kinds"]
    # 10 birim açık (09'dan itibaren değil: karar 01:00 kapanışta, dolum 02:00 açılışı): 06:00 ve 08:00'de pozisyon 10 birim.
    assert k["fund_extreme"]["funding"] == A(-10 * 100 * 0.02) and k["fund_extreme"]["n_with_position"] == 1 and k["fund_extreme"]["notional_max"] == A(1000.0)
    assert k["mark_fallback"]["funding"] == A(-10 * 100 * 0.0001)  # mark yok: kline kapanışı 100
    assert imp["totals"]["funding"] == A(res["summary"]["funding"], abs=1e-9)  # kesişim toplamı hakem funding'i ile aynı
    assert k["fund_interval_inconsistent"]["n_flags"] == 1 and imp["unknown_interval_events"] == 1
    assert k["mark_last_div"]["n_flags"] == 1 and k["mark_last_div"]["n_with_position"] == 1 and k["gap"]["n_flags"] == 1
    assert k["fund_extreme"]["net"] == A(k["fund_extreme"]["price"] + k["fund_extreme"]["funding"] - k["fund_extreme"]["cost"])


def test_policies_same_accounting_path_and_point_in_time():
    data, sp = setup()
    res = run_portfolio(data, sp)
    base = res["summary"]["funding"]
    p1 = qi.apply_policy(data, res, "P1_funding_exclude_flagged")
    r1 = run_portfolio({s: dict(d, target=data[s]["target"]) for s, d in p1.items()}, sp)
    assert r1["summary"]["funding"] == A(base + 20.0 + 0.1 + 0.0 + 0.0, abs=0.5)  # 08:00 aşırı (−20) ve 06:00 mark_fallback (−0,1) ve 20:00 ayrışma çıkar
    p2 = qi.apply_policy(data, res, "P2_funding_adverse_flagged")
    r2 = run_portfolio({s: dict(d, target=data[s]["target"]) for s, d in p2.items()}, sp)
    assert r2["summary"]["funding"] <= base + 1e-9  # aleyhe çevirme funding'i artırmaz (long öder)
    assert report.reconcile(data, res, sp)["ok"] and report.reconcile(p1, r1, sp)["ok"]
    with pytest.raises(ValueError):
        qi.apply_policy(data, res, "P9_best_sharpe")  # politika kümesi önceden kapalı
    assert qi.POLICIES[0] == "P0_original"


def test_p2_requires_actual_fills_instead_of_intended_target():
    data, sp = setup()
    res = run_portfolio(data, sp)
    tg = {"X": pd.DataFrame(dict(target=data["X"]["target"]))}
    assert qi.apply_policy(data, res, "P2_funding_adverse_flagged")["X"]["funding"].equals(data["X"]["funding"])
    with pytest.raises(ValueError, match="actual fills"):
        qi.apply_policy(data, None, "P2_funding_adverse_flagged", tg)


def test_qc_funding_impact_uses_pre_settlement_fills_and_policy_identity():
    from kepler import receipt
    data, sp = setup()
    data["X"]["target"] = -data["X"]["target"]
    res = run_portfolio(data, sp)
    p2 = qi.apply_policy(data, res, "P2_funding_adverse_flagged")
    assert qi.impact(data, res, sp)["totals"]["funding"] == A(res["summary"]["funding"])
    assert p2["X"]["funding"].loc[pd.Timestamp("2024-01-01 08:00", tz="UTC"), "last_funding_rate"] == -.02
    assert receipt.data_manifest(data)["id"] != receipt.data_manifest(p2)["id"]
