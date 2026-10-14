"""#12: deney kimliği (receipt). Davranışı değiştiren her şey kimliği değiştirir; köken/run kimliği değiştirmez."""
import shutil
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest

from kepler import ledger, receipt


def frame(px=100.0, n=48):
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    c = np.full(n, px)
    return pd.DataFrame(dict(open=c, high=c, low=c, close=c, volume=1e6), index=idx)


def fund(rate=0.0001):
    return pd.DataFrame({"last_funding_rate": [rate]}, index=[pd.Timestamp("2024-01-01 08:00", tz="UTC")])


def data(px=100.0, rate=0.0001, mark_px=None):
    kl = frame(px)
    return {"A": dict(kl=kl, funding=fund(rate), mark=frame(mark_px or px))}


@dataclass(frozen=True)
class P:
    risk_unit: float = 1.0


def make_book(p, mem):
    def book(kls):
        return p.risk_unit, mem  # closure: p ve üyelik tablosu
    return book


MEM = pd.DataFrame({"sym": ["A", "B"], "month": ["2024-01", "2024-01"]})
CFG = dict(name="x", params=dict(a=1))


def eid(cfg=CFG, d=None, book=None, **kw):
    return receipt.make(cfg, d or data(), book=book or make_book(P(), MEM), **kw)["economic_id"]


def test_same_inputs_same_id_run_attempt_separate():
    a, b = receipt.make(CFG, data(), book=make_book(P(), MEM)), receipt.make(CFG, data(), book=make_book(P(), MEM), attempt=2)
    assert a["economic_id"] == b["economic_id"] and a["run_id"] != b["run_id"] and b["attempt"] == 2


def test_closure_param_change_changes_id():  # E06: risk birimi x0,5 eskiden aynı kimlikti
    assert eid(book=make_book(P(0.5), MEM)) != eid(book=make_book(P(1.0), MEM))


def test_config_change_changes_id():
    assert eid(cfg=dict(name="x", params=dict(a=2))) != eid()


def test_membership_change_changes_id():
    mem2 = MEM.copy()
    mem2.loc[1, "month"] = "2024-02"
    assert eid(book=make_book(P(), mem2)) != eid()


def test_price_funding_mark_changes_change_id_symbol_list_alone_is_not_enough():
    base = eid()
    assert eid(d=data(px=101.0)) != base and eid(d=data(rate=0.0002)) != base and eid(d=data(mark_px=100.5)) != base
    d = data()
    d["A"]["kl"] = d["A"]["kl"].copy()
    d["A"]["kl"].iloc[5, 3] += 1e-6  # tek bar kapanışı
    assert eid(d=d) != base


def test_cut_changes_id():
    assert eid(cut=("2024-01-01", "2024-01-02")) != eid(cut=("2024-01-01", "2024-01-03"))


def test_code_change_in_package_changes_id(tmp_path, monkeypatch):
    shutil.copytree(receipt.ROOT / "kepler", tmp_path / "kepler", ignore=shutil.ignore_patterns("__pycache__"))
    monkeypatch.setattr(receipt, "ROOT", tmp_path)
    before = receipt.code_hash()
    (tmp_path / "kepler" / "portfolio.py").write_text((tmp_path / "kepler" / "portfolio.py").read_text() + "\n# davranış değişikliği\n")
    assert receipt.code_hash() != before


def test_provenance_has_no_secrets_and_legacy_marker(tmp_path):
    r = receipt.make(CFG, data(), book=make_book(P(), MEM))
    assert set(r["provenance"]) == {"git_sha", "dirty_diff_sha", "lock_sha", "python", "packages"}
    assert receipt.provenance_status({"trial": 1}) == "legacy_partial_provenance" and receipt.provenance_status({"receipt": r}) == "full"
    p = tmp_path / "l.jsonl"
    row = ledger.record(p, "referee", "h", dict(audit_causal=True), r["code_hash"], "d", result=dict(net_pnl=1.0), receipt=r)
    assert row["economic_id"] == r["economic_id"] and ledger.trial_count(p) == 1
