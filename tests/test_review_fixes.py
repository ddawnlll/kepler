"""Bağımsız inceleme bulgularından gelen düzeltmelerin testleri (QC, defter, veri istemcisi, hakem)."""
import hashlib

import numpy as np
import pandas as pd
import pytest

from kepler import data, ledger, qc
from kepler.referee import run
from tests.test_data import K, FakeNet, make_zip
from tests.test_qc import checks, clean
from tests.test_referee import A, LIQ, bars, spec, tgt


# ---- QC
def test_funding_intervals_1_2_4_8_are_valid_info_not_error():
    # gerçek veri: 34 sembol 1/2/4 saatlik aralık kullanıyor; hata değil, bilgi
    d = clean(kind="fundingRate").assign(funding_interval_hours=1)
    d["ts"] = pd.date_range("2024-01-01", periods=len(d), freq="1h", tz="UTC")
    assert [(g["check"], g["severity"]) for g in qc.check_frame(d, "fundingRate")] == [("funding_interval_not_8h", "INFO")]


def test_funding_nan_rate_and_ms_jitter():
    d = clean(kind="fundingRate")
    assert "nan_funding_rate" in checks(d.assign(last_funding_rate=d.last_funding_rate.where(d.index != 3, np.nan)), "fundingRate")
    j = d.assign(ts=d.ts + pd.to_timedelta(np.arange(len(d)) * 4, unit="ms"))  # birikimli ms sapması boşluk sayılmaz
    assert qc.check_frame(j, "fundingRate") == []


def test_wick_outlier_and_nan_volume():
    d = clean()
    d.loc[10, "high"] = 200.0  # tutarlı mum ama (high-low)/close ~ %100
    assert "wick_outlier" in checks(d)
    v = clean()
    assert "negative_volume" in checks(v.assign(volume=v.volume.where(v.index != 4, np.nan)))


# ---- defter
def test_referee_result_with_rejections_or_missing_funding_is_not_ledgered(tmp_path):
    p = tmp_path / "l.jsonl"
    for bad in ({"net_pnl": 1.0, "n_rejected": 2}, {"net_pnl": 1.0, "funding_missed": 1}, {"net_pnl": float("nan"), "n_rejected": 0}):
        with pytest.raises(ValueError):
            ledger.record(p, "referee", "h", {}, "c", "d", result=bad)
    assert ledger.trial_count(p) == 0
    ledger.record(p, "referee", "h", {}, "c", "d", result={"net_pnl": 1.0, "n_rejected": 0, "funding_missed": 0})
    assert ledger.trial_count(p) == 1


# ---- veri istemcisi
def test_resume_repairs_missing_sidecar(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "_get", FakeNet([make_zip()]))
    p = data.fetch(K, tmp_path)
    side = p.with_name(p.name + ".sha256")
    side.unlink()  # yarım kalmış önceki koşu
    data.fetch(K, tmp_path)
    assert side.read_text() == hashlib.sha256(make_zip()).hexdigest()


# ---- hakem
def test_summary_reports_rejections_and_missing_funding():
    kl = bars([100] * 12)
    s = run(kl, tgt(kl, b0=100.0, b9=0.0), spec(fee_rt_bps=0))["summary"]
    assert s["n_rejected"] == 0 and s["funding_missed"] == 0
    mark = kl.assign(close=np.where(np.arange(12) == 7, np.nan, 102.0))  # 08:00 olayı veri aralığında ama mark NaN
    f = pd.DataFrame({"last_funding_rate": [1e-4]}, index=[pd.Timestamp("2024-01-01 08:00", tz="UTC")])
    s = run(kl, tgt(kl, b0=100.0, b9=0.0), spec(fee_rt_bps=0), funding=f, mark=mark)["summary"]
    assert s["funding_mark_fallback"] == 1 and s["funding_missed"] == 0  # mark yok -> kline kapanışı (100) kullanılır, sayılır
    assert s["funding"] == A(-1.0 * 100 * 1e-4)
    kl2, mark2 = kl.drop(kl.index[7]), mark.drop(kl.index[7])  # ne kline ne mark barı var: sessizce atlanmaz
    t2 = tgt(kl, b0=100.0, b9=0.0).drop(kl.index[7])
    s = run(kl2, t2, spec(fee_rt_bps=0), funding=f, mark=mark2)["summary"]
    assert s["funding_missed"] == 1 and s["funding"] == 0
    with pytest.raises(ValueError, match="NaN"):
        run(kl, tgt(kl, b0=100.0), spec(), funding=f.assign(last_funding_rate=np.nan))


def test_run_rejects_misaligned_or_naive_targets():
    kl = bars([100] * 6)
    with pytest.raises(ValueError):
        run(kl, tgt(kl, b0=100.0).shift(1, freq="30min"), spec())
    with pytest.raises(ValueError):
        run(kl, tgt(kl, b0=100.0).tz_localize(None), spec())


def test_gap_through_liquidation_fills_at_gap_price_not_at_lp():
    """İnceleme şüphesi (gap'te tetik fiyatından dolum = iyimser) YANLIŞ çıktı: bar açılışı likidasyon fiyatının (94.79)
    altında (80) ise stop piyasa fiyatından (80) dolar. Kayıp LP'den değil gap fiyatından hesaplanır (gerçekçi)."""
    kl = bars([100, 80, 80], rows=[(100, 100, 100, 100), (80, 80, 80, 80), (80, 80, 80, 80)])
    r = run(kl, tgt(kl, b0=10000.0), spec(**LIQ))
    assert r["fills"].px.iloc[1] == A(80.0) and r["summary"]["n_liq"] == 1


def test_liquidation_price_after_flip_uses_balance_after_realized_pnl_and_fee():
    # 1000 sermaye, 100@100 long (fee 5). Bar1 kapanış 110: hedef -5000 -> tek emirle çevir: sat 100 + short 45.454 (=5000/110)
    # sat qty 145.454 @110: fee = 145.454*110*0.0005 = 7.99997; realize +1000 => WB = 1000-5+1000-7.99997
    # short s=45.454, E=110: LP = (WB + s*E)/(s*(1+mmr))
    kl = bars([100, 110, 110], rows=[(100, 100, 100, 100), (110, 110, 110, 110), (110, 150, 110, 110)])
    r = run(kl, tgt(kl, b0=10000.0, b1=-5000.0), spec(**LIQ))
    f = r["fills"]
    assert list(f.qty[:2]) == [100.0, 145.454] and r["summary"]["n_liq"] == 1
    lp = (1000 - 5 + 1000 - 145.454 * 110 * 0.0005 + 45.454 * 110) / (45.454 * 1.05)
    assert f.px.iloc[2] == A(round(lp, 2), abs=0.011)
