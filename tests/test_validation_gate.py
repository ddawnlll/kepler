"""A validation command must reject differences and match duplicate fills one-to-one."""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import referee_validate as rv


def reference(tmp_path, monkeypatch):
    monkeypatch.setattr(rv, "REF", tmp_path)
    monkeypatch.setattr(rv, "OUT", str(tmp_path))
    d = tmp_path / "fixture"
    d.mkdir()
    fills = pd.DataFrame(dict(sym=["A", "A"], ts=[1, 1], side=["BUY", "BUY"], qty=[1., 1.], px=[100., 100.1], commission=[.1, .1]))
    fills.to_csv(d / "fills.csv", index=False)
    summary = dict(net_pnl=2., funding=0., n_fills=2, n_rejected=0, funding_missed=0)
    (d / "meta.json").write_text(json.dumps(dict(cap=1000, summary=summary)))
    return dict(fills=fills, summary=summary)


def test_equal_duplicate_fills_match_once_and_gate_passes(tmp_path, monkeypatch):
    res = reference(tmp_path, monkeypatch)
    c = rv.compare("fixture", res, 1.)
    assert c["rows_matched"] == 2 and c["economic_pass"]


def test_price_summary_and_invalid_engine_cannot_pass(tmp_path, monkeypatch):
    res = reference(tmp_path, monkeypatch)
    res["fills"].loc[1, "px"] += .01
    assert not rv.compare("fixture", res, 1.)["economic_pass"]
    res["fills"].loc[1, "px"] -= .01
    res["summary"]["net_pnl"] += .1
    assert not rv.compare("fixture", res, 1.)["economic_pass"]
    res["summary"]["net_pnl"] -= .1
    res["summary"]["n_rejected"] = 1
    assert not rv.compare("fixture", res, 1.)["economic_pass"]
