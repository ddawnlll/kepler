"""G2 sinyalleri: elle hesaplı kural testleri + nedensellik (günlük karar, saat-23 barına yerleşim)."""
import numpy as np
import pandas as pd
import pytest

from kepler import audit
from kepler import signals as sg


def hourly(daily_close, start="2022-01-01"):
    """Her gün sabit fiyat (o=h=l=c): günlük kural değerleri elle hesaplanabilir."""
    idx = pd.date_range(start, periods=24 * len(daily_close), freq="1h", tz="UTC")
    c = np.repeat(np.array(daily_close, float), 24)
    return pd.DataFrame(dict(open=c, high=c, low=c, close=c, volume=1000.0), index=idx)


def decisions(s):
    d = s.dropna()
    assert (d.index.hour == 23).all()  # yalnızca günün son barında karar
    return d.groupby(d.index.normalize()).last()


def test_turtle_entry_exit_flip_on_ramp_then_drop():
    kl = hourly([100 + d for d in range(30)] + [80] * 10)
    s = decisions(sg.turtle(20, 10)(kl))
    # önceki 20 günün en yükseği ilk kez 20. günde aşılır (gün 0..19 = 20 gün) -> long; gün 30: kapanış 80 < 20 günlük en düşük (110) -> short'a çevirir
    assert s.iloc[:20].eq(0).all() and s.iloc[20] == 1 and s.iloc[29] == 1 and s.iloc[30] == -1
    # 10 gün sabit 80: short'tan çıkış için kapanış > 10 günlük en yüksek (80) gerekir; olmaz -> short sürer
    assert s.iloc[31:40].eq(-1).all()


def test_turtle_exit_to_flat():
    kl = hourly([100 + d for d in range(25)])
    assert decisions(sg.turtle(20, 10)(kl)).iloc[24] == 1
    kl = hourly([100 + d for d in range(25)] + [124] * 11 + [120])  # 11 gün 124'te yatay, sonra 120: 10 günlük en düşük (124) ihlal; 20 günlük en düşük (117) ihlal değil -> flat
    s = decisions(sg.turtle(20, 10)(kl))
    assert s.iloc[-1] == 0 and s.iloc[-2] == 1


def test_donchian_trend_filter_needs_350_days_of_ema():
    kl = hourly([100 + d for d in range(60)])
    assert decisions(sg.turtle(20, 10, trend=True)(kl)).eq(0).all()  # 350 gün EMA yok -> giriş yok
    assert decisions(sg.turtle(20, 10)(kl)).iloc[-1] == 1


def test_monthly_signals_only_at_month_end_bars():
    kl = hourly(list(np.linspace(100, 300, 500)))
    s = sg.tsmom()(kl).dropna()
    assert len(s) > 0 and s.index.normalize().is_month_end.all() and (s.index.hour == 23).all() and s.eq(1).all()  # 12 ay sonra: getiri > 0 -> long


def test_dual_momentum_long_leader_short_laggard_flat_middle():
    days = 500
    up, flat, down = (np.linspace(100, 300, days), np.full(days, 100.0), np.linspace(100, 40, days))
    panel = pd.DataFrame(dict(A=up, B=flat, C=down), index=pd.date_range("2022-01-01", periods=days, freq="1D", tz="UTC"))
    kl = hourly(list(up))
    assert sg.dual_mom(panel, "A")(kl).dropna().eq(1).all()
    assert sg.dual_mom(panel, "C")(kl).dropna().eq(-1).all()
    assert sg.dual_mom(panel, "B")(kl).dropna().eq(0).all()  # getirisi 0, medyan: ne long ne short


def test_carry_short_when_funding_positive_and_causal_funding_join():
    kl = hourly([100.0] * 120)
    f = pd.DataFrame({"last_funding_rate": 0.0001, "funding_interval_hours": 8}, index=pd.date_range("2022-01-01 00:00:00.004", periods=120 * 3, freq="8h", tz="UTC"))
    k2 = sg.with_funding(kl, f)
    assert k2.fund_hr.iloc[0] == pytest.approx(0.0001 / 8) and k2.fund_hr.iloc[-1] == pytest.approx(0.0001 / 8)
    assert sg.carry_funding()(k2).dropna().eq(-1).all() and len(sg.carry_funding()(k2).dropna()) >= 2


@pytest.mark.parametrize("name", ["s1", "s2", "trend", "tsmom", "carry", "dual"])
def test_all_signals_are_causal_and_unit_bounded(name):
    r = np.random.default_rng(3)
    kl = hourly(list(100 * np.exp(np.cumsum(r.normal(0, 0.03, 700)))))
    kl = kl.assign(close=kl.close * (1 + r.normal(0, 0.001, len(kl))))  # saat içi gürültü: kapanış/yüksek/düşük ayrışsın
    kl = kl.assign(high=kl[["open", "close"]].max(axis=1) * 1.001, low=kl[["open", "close"]].min(axis=1) * 0.999)
    f = pd.DataFrame({"last_funding_rate": r.normal(0.0001, 0.0001, 700 * 3), "funding_interval_hours": 8}, index=pd.date_range("2022-01-01", periods=700 * 3, freq="8h", tz="UTC"))
    kl = sg.with_funding(kl, f)
    panel = pd.DataFrame(dict(X=sg._daily(kl).close, Y=sg._daily(kl).close[::-1].to_numpy()))
    sig = dict(s1=sg.turtle(20, 10), s2=sg.turtle(55, 20), trend=sg.turtle(20, 10, True), tsmom=sg.tsmom(), carry=sg.carry_funding(), dual=sg.dual_mom(panel, "X"))[name]
    assert audit.check_causal(sig, kl) == []
    assert set(sig(kl).dropna().unique()) <= {-1.0, 0.0, 1.0}
