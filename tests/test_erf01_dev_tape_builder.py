"""Gates for Binance timestamp units and DEV-only tape staging."""
import json
from pathlib import Path

import pandas as pd
import pytest

from scripts import erf01_dev_tape_builder as builder


def test_datetime_unit_normalisation_milliseconds_and_microseconds():
    raw = pd.Series([1735689600000, 1735689600000000])
    ts = builder._timestamp(raw)
    assert str(ts.iloc[0]) == "2025-01-01 00:00:00+00:00"
    assert ts.iloc[0] == ts.iloc[1]


def test_plan_requires_manifest_stream_and_preseal_range(tmp_path):
    (tmp_path / "data_manifest").mkdir()
    one = {"symbols": {"BTCUSDT": {
        "klines": {"first": "2025-01-01", "last": "2025-01-31", "zip_sha256": {"2025-01": "a"}},
        "fundingRate": {"first": "2025-01-01", "last": "2025-01-31"}}}}
    (tmp_path / "data_manifest" / "manifest.json").write_text(json.dumps(one))
    (tmp_path / "data_manifest" / "manifest_pre2022.json").write_text('{"symbols":{}}')
    with pytest.raises(RuntimeError, match="markPriceKlines"):
        builder._plans(tmp_path, "BTCUSDT")
    one["symbols"]["BTCUSDT"]["markPriceKlines"] = {
        "first": "2025-01-01", "last": "2025-01-31"}
    (tmp_path / "data_manifest" / "manifest.json").write_text(json.dumps(one))
    result = builder._plans(tmp_path, "BTCUSDT")
    assert result["klines"] == [("2025-01", "a")]
    assert result["fundingRate"] == [("2025-01", None)]


def test_archive_month_rejects_out_of_range_and_duplicate(monkeypatch, tmp_path):
    frame = pd.DataFrame({
        "open_time": [1735689600000, 1735776000000],
        "open":[100.,101.],"high":[102.,103.],"low":[99.,100.],
        "close":[101.,102.],"volume":[1.,1.]
    })
    monkeypatch.setattr(builder.data,"read_zip_csv", lambda *_:frame.copy())
    good=builder._parse_month(tmp_path, "klines", "2025-01")
    assert len(good)==2 and set(good["ts_unit"])=={"ms"}
    bad=frame.copy()
    bad.loc[1,"open_time"]=1775001600000  # 2026-04, sealed and wrong archive month
    monkeypatch.setattr(builder.data,"read_zip_csv",lambda *_:bad.copy())
    with pytest.raises(RuntimeError,match="out-of-month"):
        builder._parse_month(tmp_path,"klines","2025-01")
    duplicate=frame.copy()
    duplicate.loc[1,"open_time"]=duplicate.loc[0,"open_time"]
    monkeypatch.setattr(builder.data,"read_zip_csv",lambda *_:duplicate.copy())
    with pytest.raises(RuntimeError,match="duplicate"):
        builder._parse_month(tmp_path,"klines","2025-01")
