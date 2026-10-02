"""Risk motoru, rapor, 4h/1d türetme, durum özeti: elle hesaplı testler."""
import json

import numpy as np
import pandas as pd
import pytest

from factory import enqueue, status
from kepler import ledger, report, risk, tape
from kepler.referee import Spec, run
from tests.test_referee import A, bars, tgt


def sp(**kw):
    return Spec(**{**dict(tick="0.01", step="0.001", capital=10000.0, liq=True, fee_rt_bps=10.0), **kw})


def test_trades_table_long_short_flip_hand_computed():
    kl = bars([100, 100, 110, 110, 99, 99])
    r = run(kl, tgt(kl, b0=100.0, b2=-110.0, b4=0.0), sp(fee_rt_bps=0))
    t = report.trades(r["fills"])
    # long 100 -> 110 (+%10 = 1000 bps), sonra short 110 -> 99 (+%10 = 1000 bps); çevirme iki işlem
    assert list(t.side) == ["long", "short"] and list(t.gross_bps.round(0)) == [1000.0, 1000.0]
    assert report.markdown("x", r).count("| long |") == 1 and "işlem 2" in report.markdown("x", r)


def test_hourly_pnl_reconstructs_referee_net():
    kl = bars(list(np.round(100 * np.exp(np.cumsum(np.random.default_rng(2).normal(0, 0.01, 300))), 2)))  # fiyatlar tick (0.01) üstünde: dolum yuvarlaması yok
    t = pd.Series(np.where(np.arange(300) % 40 < 20, 1000.0, -1000.0), index=kl.index)
    r = run(kl, t, sp(slip_rt_bps=2.0))
    assert report.hourly_pnl(kl, None, None, r["fills"], sp(slip_rt_bps=2.0)).sum() == A(r["summary"]["net_pnl"], abs=1e-6)


def test_vol_target_is_causal_capped_and_banded():
    r = np.random.default_rng(5)
    kl = bars(list(100 * np.exp(np.cumsum(r.normal(0, 0.004, 24 * 120)))))
    unit = pd.Series(1.0, index=kl.index)
    t = risk.vol_target(kl, unit, 1000.0, target_vol=0.2, max_lev=3.0, band=0.25)
    assert t.dropna().abs().max() <= 3000.0 + 1e-9 and t.iloc[: 24 * 31].isna().all()  # 30 gün ısınma + 1 gün gecikme
    # nedensellik: gelecek bozulunca geçmiş hedef değişmez
    k = 24 * 90
    alt = kl.copy()
    alt.iloc[k:, :4] = alt.iloc[k:, :4].to_numpy() * 1.7
    assert t.iloc[:k].equals(risk.vol_target(alt, unit, 1000.0).iloc[:k])
    # bant: ardışık farklı hedefler en az %25 farklı
    ch = t.dropna()[t.dropna().diff().abs() > 0]
    assert ((ch / ch.shift()).dropna().sub(1).abs() > 0.25 - 1e-9).all()


def test_vol_target_hand_value():
    # günlük getiri ±%1 dönüşümlü: std ~0.01 -> yıllık 0.01*sqrt(365)=0.191; hedef 0.2 -> kaldıraç ~1.047
    c = np.repeat(100 * np.cumprod(np.where(np.arange(60) % 2 == 0, 1.01, 1 / 1.01)), 24)
    kl = bars(list(c))
    v = risk.realized_vol(kl, 30).dropna()
    assert v.iloc[-1] == A(np.std(np.log(c[::24])[-31:][1:] - np.log(c[::24])[-31:][:-1], ddof=1) * np.sqrt(365), rel=0.2)


def test_kill_switch_flattens_at_drawdown_and_stays_flat():
    idx = pd.date_range("2024-01-01", periods=6, freq="1h", tz="UTC")
    eq = pd.Series([1000, 1100, 1000, 780, 900, 1200], index=idx, dtype=float)  # tepe 1100; 780 -> %29 düşüş
    t, at = risk.kill_switch(pd.Series(1000.0, index=idx), eq, 0.25)
    assert at == idx[3] and list(t) == [1000.0, 1000.0, 1000.0, 0.0, 0.0, 0.0]  # toparlanma insan onayına kadar işlem açmaz
    t, at = risk.kill_switch(pd.Series(1000.0, index=idx), eq, 0.35)
    assert at is None and t.eq(1000.0).all()


def test_aggregate_4h_and_1d():
    kl = bars(list(range(100, 148)), rows=[(100 + i, 100 + i + 0.5, 100 + i - 0.5, 100 + i + 0.1) for i in range(48)])
    a4 = tape.aggregate(kl, "4h")
    assert len(a4) == 12 and a4.open.iloc[0] == 100 and a4.high.iloc[0] == 103.5 and a4.low.iloc[0] == 99.5 and a4.close.iloc[0] == A(103.1) and a4.volume.iloc[0] == 4000 and (a4.n == 4).all()
    d1 = tape.aggregate(kl, "1D")
    assert len(d1) == 2 and d1.close.iloc[1] == A(147.1) and d1.high.iloc[0] == 123.5


def test_evaluate_with_risk_sizing_and_kill_switch(tmp_path):
    from kepler import evaluate as ev
    r = np.random.default_rng(9)
    kl = bars(list(100 * np.exp(np.cumsum(r.normal(0, 0.004, 24 * 150)))))
    sig = lambda k: np.sign(k.close.pct_change(24)).astype(float)  # noqa: E731
    out = ev.evaluate(sig, kl, [sp(slip_rt_bps=2.0, capital=1000.0)], tmp_path / "l.jsonl", "h", "d", size=lambda k, u, cap: risk.vol_target(k, u, cap), kill_dd=0.05)[0]
    row = out["row"]["config"]
    assert row["sized"] is True and row["kill_dd"] == 0.05 and out["row"]["result"]["n_rejected"] == 0
    if row["kill_at"] != "None":  # tetiklendiyse sonrası işlem yok: son dolum tetik zamanından sonra pozisyonu sıfıra getirir
        assert out["res"]["summary"]["end_position"] == 0


def test_status_is_query_only_and_counts_queue(tmp_path):
    p = tmp_path / "l.jsonl"
    ledger.record(p, "screen", "h", {"name": "a"}, "c", "d", score=1.0)
    ledger.record(p, "referee", "h", {"name": "a", "audit_causal": True}, "c", "d", result={"net_pnl": 12.5})
    ledger.record(p, "referee", "h", {"name": "b", "audit_causal": True}, "c", "d", result={"net_pnl": -3.0})
    q = tmp_path / "q.jsonl"
    enqueue.enqueue("sekreter", "C", "request", "mührü aç", path=q)
    out = status.status([str(p)], {"x|y": {"cand": False}, "z|y": {"cand": True}}, queue=q)
    assert out[0].startswith("deneme: 3 (hakem 2, eleme 1)") and "a 12.5" in out[1] and "aday: 1 (z|y)" in out[2] and "kullanıcı bekleyen 1" in out[3]
    assert len(out) <= 6 and status.status([], None, queue=tmp_path / "none.jsonl")[0] == "defter boş: deneme 0"


def test_status_accepts_search_summary_shape(tmp_path):
    out = status.status([], {"summary": {"donchian": {"cand": False}}, "search": []}, queue=tmp_path / "q.jsonl")
    assert any(l.startswith("aday: 0") and "yapılandırma 1" in l for l in out)


def test_trades_values_open_leg_at_close_price():
    """Sonda açık bacak (close_px): long 2 @100 açık, son kapanış 110 -> değerleme satırı pnl = (110-100)·2 = 20, notional 200, brüt 1000 bps; kapanmış işlem değişmez."""
    t0, t1 = 1_700_000_000_000_000_000, 1_700_000_000_000_000_000 + 3_600_000_000_000
    fills = pd.DataFrame(dict(sym="A", ts=[t0], side=["BUY"], qty=[2.0], px=[100.0]))
    assert len(report.trades(fills)) == 0
    r = report.trades(fills, 110.0, t1).iloc[0]
    assert r.pnl == 20.0 and r.notional == 200.0 and r.gross_bps == A(1000.0) and r.hours == 1.0 and r.side == "long"
