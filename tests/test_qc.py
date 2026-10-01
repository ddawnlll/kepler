import numpy as np
import pandas as pd
import pytest

from kepler import qc


def clean(n=200, kind="klines"):
    ts = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    if kind == "fundingRate":
        ts = pd.date_range("2024-01-01", periods=n, freq="8h", tz="UTC")
        return pd.DataFrame({"ts": ts, "funding_interval_hours": 8, "last_funding_rate": 0.0001, "ts_unit": "ms"})
    c = 100 + np.sin(np.arange(n) / 10)
    return pd.DataFrame({"ts": ts, "open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 10.0, "ts_unit": "ms"})


def checks(df, kind="klines"):
    return {i["check"] for i in qc.check_frame(df, kind)}


def test_clean_frames_have_no_issues():
    assert qc.check_frame(clean(), "klines") == []
    assert qc.check_frame(clean(kind="fundingRate"), "fundingRate") == []


def corrupt(fn, kind="klines"):
    df = clean(kind=kind)
    return fn(df) or df


CASES = {
    "gap": lambda d: d.drop(index=range(50, 53)).reset_index(drop=True),
    "duplicate_ts": lambda d: pd.concat([d, d.iloc[[10]]], ignore_index=True),
    "non_monotonic_ts": lambda d: d.iloc[::-1].reset_index(drop=True),
    "not_utc": lambda d: d.assign(ts=d.ts.dt.tz_localize(None)),
    "misaligned_ts": lambda d: d.assign(ts=d.ts + pd.Timedelta("7min")),
    "ts_unit_not_ms": lambda d: d.assign(ts_unit="us"),
    "inconsistent_candle": lambda d: d.assign(high=d.high.where(d.index != 5, d.low - 5)),
    "nan_price": lambda d: d.assign(close=d.close.where(d.index != 7, np.nan)),
    "non_positive_price": lambda d: d.assign(low=d.low.where(d.index != 9, 0.0)),
    "negative_volume": lambda d: d.assign(volume=d.volume.where(d.index != 3, -1.0)),
    "jump": lambda d: d.assign(close=d.close.where(d.index != 20, 200.0), high=d.high.where(d.index != 20, 201.0)),
    "sealed_period_leak": lambda d: d.assign(ts=d.ts + pd.Timedelta(days=900)),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_each_kline_check_fires(name):
    assert name in checks(CASES[name](clean()))


def test_candle_where_open_outside_range():
    d = clean()
    d.loc[4, "open"] = d.loc[4, "high"] + 3  # open > high
    assert "inconsistent_candle" in checks(d)


FUND = {
    "funding_interval": lambda d: d.assign(funding_interval_hours=d.funding_interval_hours.where(d.index != 4, 6)),
    "gap": lambda d: d.drop(index=range(10, 12)).reset_index(drop=True),
    "funding_extreme": lambda d: d.assign(last_funding_rate=d.last_funding_rate.where(d.index != 2, 0.05)),
    "duplicate_ts": lambda d: pd.concat([d, d.iloc[[3]]], ignore_index=True),
}


@pytest.mark.parametrize("name", sorted(FUND))
def test_each_funding_check_fires(name):
    assert name in checks(FUND[name](clean(kind="fundingRate")), "fundingRate")


def test_funding_4h_interval_is_accepted_not_gap():
    d = clean(kind="fundingRate").assign(funding_interval_hours=4)
    d["ts"] = pd.date_range("2024-01-01", periods=len(d), freq="4h", tz="UTC")
    assert [g["check"] for g in qc.check_frame(d, "fundingRate")] == ["funding_interval_not_8h"]  # yalnızca bilgi, boşluk yok


def test_mark_kline_divergence():
    kl, mk = clean(), clean()
    assert qc.check_mark_vs_kline(kl, mk) == []
    mk.loc[30, "close"] = 130.0
    assert qc.check_mark_vs_kline(kl, mk)[0]["check"] == "mark_kline_divergence"


def test_real_data_issues_are_reported_not_fixed():
    d = CASES["gap"](clean())
    n = len(d)
    qc.check_frame(d, "klines")
    assert len(d) == n  # kontrol veriyi değiştirmez
