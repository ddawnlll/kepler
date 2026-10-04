import io
import os
import zipfile

import numpy as np
import pandas as pd
import pytest

from kepler import data, positioning, qc, tape, universe

COLS = ["sum_open_interest", "sum_open_interest_value", "count_toptrader_long_short_ratio", "sum_toptrader_long_short_ratio",
        "count_long_short_ratio", "sum_taker_long_short_vol_ratio"]


def frame(n=288 * 2, start="2024-01-01"):
    """5 dk satırlar; i. satırın her sütunu 100+i (elle hesaplanabilir)."""
    ts = pd.date_range(start, periods=n, freq="5min", tz="UTC")
    return pd.DataFrame({"ts": ts, **{c: 100.0 + np.arange(n) for c in COLS}})


def zip_of(text: str) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("x.csv", text)
    return b.getvalue()


def test_key_days_and_seal_boundary(tmp_path, monkeypatch):
    k = data.key("metrics", "BTCUSDT", "2026-03-31")
    assert k == "data/futures/um/daily/metrics/BTCUSDT/BTCUSDT-metrics-2026-03-31.zip"
    for sealed in ("2026-04-01", "2026-04-02", "2027-01-15"):
        monkeypatch.setattr(data, "_get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ağa çıkılmamalıydı")))
        with pytest.raises(data.SealedError):
            data.fetch(data.key("metrics", "BTCUSDT", sealed), tmp_path)
    listing = [f"data/futures/um/daily/metrics/BTCUSDT/BTCUSDT-metrics-{d}.zip{s}" for d in ("2026-03-30", "2026-03-31", "2026-04-01", "2026-04-02") for s in ("", ".CHECKSUM")]
    monkeypatch.setattr(data, "list_bucket", lambda prefix, delimiter="/": (listing, []))
    assert data.days("BTCUSDT") == ["2026-03-30", "2026-03-31"]  # mühürlü gün adları bile dönmez, .CHECKSUM sayılmaz


def test_to_tape_keeps_raw_names_and_raw_rows(tmp_path):
    head = "create_time,symbol," + ",".join(COLS) + "\n"
    row = "2020-09-01 00:00:00,BTCUSDT,1,2,3,4,5,6\n"
    p = tmp_path / "m.zip"
    p.write_bytes(zip_of(head + row * 2 + "2020-09-01 00:05:00,BTCUSDT,1,2,3,4,5,6\n"))
    df = positioning.to_tape(p)
    assert list(df.columns) == ["ts"] + COLS and len(df) == 3  # kopya satır tape'te korunur (QC raporlar, düzeltmez)
    assert str(df.ts.dt.tz) == "UTC" and df.ts.iloc[2] == pd.Timestamp("2020-09-01 00:05", tz="UTC")


# ---- QC

def checks(df):
    return {i["check"]: i["severity"] for i in qc.check_metrics(df)}


def test_clean_metrics_have_no_issues():
    assert qc.check_metrics(frame()) == []


CASES = {
    "gap": (lambda d: d.drop(index=range(50, 53)).reset_index(drop=True), "WARN"),
    "duplicate_ts": (lambda d: pd.concat([d, d.iloc[[10]]], ignore_index=True), "WARN"),  # birebir kopya
    "non_monotonic_ts": (lambda d: d.iloc[::-1].reset_index(drop=True), "ERROR"),
    "not_utc": (lambda d: d.assign(ts=d.ts.dt.tz_localize(None)), "ERROR"),
    "misaligned_ts": (lambda d: d.assign(ts=d.ts + pd.Timedelta("7min")), "ERROR"),
    "nan_value": (lambda d: d.assign(sum_taker_long_short_vol_ratio=d.sum_taker_long_short_vol_ratio.where(d.index != 5, np.nan)), "WARN"),
    "non_positive_oi": (lambda d: d.assign(sum_open_interest=d.sum_open_interest.where(d.index != 9, 0.0)), "ERROR"),
    "non_positive_ratio": (lambda d: d.assign(count_long_short_ratio=d.count_long_short_ratio.where(d.index != 9, -1.0)), "WARN"),
    "oi_jump": (lambda d: d.assign(sum_open_interest=d.sum_open_interest.where(d.index != 20, 1000.0)), "WARN"),
    "sealed_period_leak": (lambda d: frame(start="2026-03-31 23:00"), "ERROR"),
}


@pytest.mark.parametrize("name", CASES)
def test_each_corruption_is_reported(name):
    fn, sev = CASES[name]
    got = checks(fn(frame()))
    assert got.get(name) == sev, (name, got)


def test_conflicting_duplicate_is_error_and_nothing_is_fixed():
    d = frame()
    bad = pd.concat([d, d.iloc[[10]].assign(sum_open_interest=999.0)], ignore_index=True)
    before = bad.copy()
    assert checks(bad)["duplicate_ts"] == "ERROR"
    pd.testing.assert_frame_equal(bad, before)  # kontrol veriyi değiştirmez


# ---- saatlik özellik: nedensellik, elle hesap, eksik veri

def test_hourly_hand_computed():
    h = positioning.hourly(frame(n=24))  # 2 saat, 12'şer satır: değerler 100..111 ve 112..123
    assert list(h.index) == list(pd.date_range("2024-01-01", periods=2, freq="1h", tz="UTC"))
    assert h.sum_open_interest.tolist() == [111.0, 123.0] and h.n.tolist() == [12, 12]  # saatin son satırı (xx:55)
    assert list(h.columns) == COLS + ["n"]  # ham adlar korunur


def test_hourly_never_uses_rows_at_or_after_bar_close():
    d = frame(n=36)  # 3 saat
    base = positioning.hourly(d)
    for k in (12, 13, 20, 35):  # H+60dk ve sonrası satırları boz
        spoiled = d.copy()
        spoiled.loc[k:, COLS] = 1e9
        got = positioning.hourly(spoiled)
        pd.testing.assert_frame_equal(got.loc[: base.index[(k // 12) - 1]], base.loc[: base.index[(k // 12) - 1]])  # k'dan önce biten barlar aynı
    cut = positioning.hourly(d.iloc[:12])  # gelecek hiç yokken de ilk bar aynı
    assert cut.iloc[0].tolist() == base.iloc[0].tolist()
    # bar 0'ın değeri xx:55 satırı (create_time < kapanış): 12. satırı (01:00) bozmak onu değiştirmez
    assert positioning.hourly(d.assign(sum_open_interest=d.sum_open_interest.where(d.index != 12, -5.0))).sum_open_interest.iloc[0] == 111.0


def test_hourly_ignores_rows_closer_than_5min_to_close():
    d = frame(n=12)
    d.loc[11, "ts"] += pd.Timedelta("4min59s")  # 00:59:59: kapanışa 5 dk'dan yakın
    assert positioning.hourly(d).sum_open_interest.iloc[0] == 110.0 and positioning.hourly(d).n.iloc[0] == 11


def test_hourly_missing_data():
    d = frame(n=36).drop(index=[11, *range(12, 24)]).reset_index(drop=True)  # 00:55 yok, 01:00-01:55 saati tamamen yok
    h = positioning.hourly(d)
    assert list(h.index.hour) == [0, 2] and h.n.tolist() == [11, 12]  # boş saat üretilmez
    assert h.sum_open_interest.iloc[0] == 110.0  # 00:55 yoksa en son bilinen (00:50), asla sonraki saatten değil


def test_hourly_duplicate_keeps_last_and_is_order_independent():
    d = frame(n=12)
    dup = pd.concat([d, d.iloc[[11]].assign(sum_open_interest=777.0)], ignore_index=True)
    assert positioning.hourly(dup).sum_open_interest.iloc[0] == 777.0
    assert positioning.hourly(d.sample(frac=1, random_state=1)).sum_open_interest.iloc[0] == 111.0


# ---- yükleme: mühür, kesim

def write_metrics(root, sym="TESTUSDT", **kw):
    p = root / "tape" / "metrics" / f"{sym}.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    frame(**kw).to_parquet(p, index=False)


def test_load_refuses_sealed_period_and_never_returns_it(tmp_path):
    write_metrics(tmp_path, n=288 * 3, start="2026-03-30")  # 03-30 .. 04-01 (mühürlü gün dahil, sızmış gibi)
    with pytest.raises(ValueError):
        positioning.load(tmp_path, "TESTUSDT", end="2026-05-01")
    h = positioning.load(tmp_path, "TESTUSDT")
    assert h.index.max() < qc.SEAL_START and h.index.max() == pd.Timestamp("2026-03-31 23:00", tz="UTC")


def test_load_window_and_usable_cut(tmp_path):
    write_metrics(tmp_path, n=288 * 3)
    assert len(positioning.load(tmp_path, "TESTUSDT", start="2024-01-02", end="2024-01-03")) == 24
    (tmp_path / "tape").mkdir(exist_ok=True)
    (tmp_path / "tape" / "usable.json").write_text('{"TESTUSDT": "2024-01-02 00:00:00+00:00"}')
    assert positioning.load(tmp_path, "TESTUSDT").index.max() < pd.Timestamp("2024-01-02", tz="UTC")


# ---- taker alış hacmi klines tape'inde zaten var

def test_klines_tape_carries_taker_columns(tmp_path):
    row = "1638316800000,1.0,2.0,0.5,1.5,10,1638320399999,15.0,3,5,7.5,0\n"
    p = tmp_path / "k.zip"
    p.write_bytes(zip_of(row * 2))
    df = universe.to_tape(p, "klines")
    assert {"taker_buy_volume", "taker_buy_quote_volume"} <= set(df.columns) and df.taker_buy_volume.tolist() == [5, 5]
    df["ts"] = pd.date_range("2021-12-01", periods=2, freq="1h", tz="UTC")
    d = tmp_path / "tape" / "klines"
    d.mkdir(parents=True)
    df.to_parquet(d / "TESTUSDT.parquet", index=False)
    for kind in ("markPriceKlines", "fundingRate"):
        (tmp_path / "tape" / kind).mkdir()
        df.to_parquet(tmp_path / "tape" / kind / "TESTUSDT.parquet", index=False)
    assert {"taker_buy_volume", "taker_buy_quote_volume"} <= set(tape.load(tmp_path, "TESTUSDT")["klines"].columns)


@pytest.mark.skipif(not os.getenv("KEPLER_NET"), reason="ağ testi: KEPLER_NET=1")
def test_real_btc_days(tmp_path):
    ds = data.days("BTCUSDT")
    assert ds[0] == "2020-09-01" and ds[-1] == "2026-03-31"
    for d in ("2020-09-01", "2024-06-15"):
        p = data.fetch(data.key("metrics", "BTCUSDT", d), tmp_path)
        assert (p.with_name(p.name + ".sha256")).exists()
        df = positioning.to_tape(p)
        assert set(qc.M_COLS) <= set(df.columns) and df.ts.dt.date.nunique() == 1
    assert not [i for i in qc.check_metrics(df) if i["severity"] == "ERROR"]
