"""V2 portföy hakemi (BACKTEST.md §6.5, §12.2 madde 9-13) + 1 bar gecikme modu (madde 25). Beklenen değerler ELLE (madde 9 hariç: eski tek-sembol hakemden alınan sabit sayılar)."""
import numpy as np
import pandas as pd

from kepler.referee import Spec, run, run_portfolio
from tests.golden import fixture
from tests.test_referee import A, bars
from tests.test_stops import series


def sp(**kw):
    return Spec(**{**dict(tick="0.01", step="0.001", capital=10000.0, liq=False, fee_rt_bps=10.0), **kw})


def test_single_symbol_portfolio_equals_pre_rewrite_referee():
    """Madde 9: çok sembollü yeniden yazımdan ÖNCEKİ hakemin (git 22901ab) bu fixture'daki çıktıları sabit sayı olarak yazıldı (en az 28 dolum, funding, likidasyon)."""
    kl, tgt, funding, mark = fixture()
    kw = dict(tick="0.01", step="0.001", leverage=10, liq=True, fee_rt_bps=10.0, slip_rt_bps=2.0)
    s = run(kl, tgt, Spec(capital=5000.0, **kw), funding, mark)["summary"]
    assert s["n_fills"] == 28 and s["n_liq"] == 0 and s["funding"] == A(-3.714816, abs=1e-6) and s["net_pnl"] == A(-2340.724875, abs=1e-6)
    p = run_portfolio({"X": dict(kl=kl, target=tgt, funding=funding, mark=mark)}, Spec(capital=5000.0, **kw))["summary"]
    assert p["net_pnl"] == s["net_pnl"] and p["funding"] == s["funding"]
    s = run(kl, tgt, Spec(capital=500.0, **kw), funding, mark)["summary"]  # 10x: erken likidasyon, hesap ölür
    assert s["n_fills"] == 2 and s["n_liq"] == 1 and s["liq_fee"] == A(24.337251, abs=1e-6) and s["net_pnl"] == A(-499.84637, abs=1e-6) and s["funding"] == A(0.15476, abs=1e-6)


def test_gross_cap_shrinks_the_increasing_order_of_the_second_symbol():
    """Madde 10: sermaye 1000, tavan 1000, her biri 600 notional hedef. A 600/100 = 6.000; B'nin kalan alanı 1000-600 = 400 -> 400/100 = 4.000 (600 değil)."""
    a, b = bars([100] * 4), bars([100] * 4)
    t = series(a, b0=600.0)
    r = run_portfolio({"A": dict(kl=a, target=t), "B": dict(kl=b, target=t)}, sp(capital=1000.0, leverage=2, gross_cap=1000.0))
    f = r["fills"].set_index("sym")
    assert f.qty["A"] == 6.0 and f.qty["B"] == 4.0 and r["summary"]["n_rejected"] == 0
    r = run_portfolio({"A": dict(kl=a, target=t), "B": dict(kl=b, target=t)}, sp(capital=1000.0, leverage=2))  # tavan yok: 6 + 6
    assert list(r["fills"].qty) == [6.0, 6.0]


def test_funding_of_two_symbols_is_the_sum():
    """Madde 11: A long 1000@100 (10 adet), mark 102, oran 1e-4 -> -10*102*1e-4 = -0.102; B short 1000@200 (5 adet), mark 204, oran 2e-4 -> +5*204*2e-4 = +0.204; toplam +0.102."""
    a, b = bars([100] * 12), bars([200] * 12)
    f = lambda r: pd.DataFrame({"last_funding_rate": [r]}, index=[pd.Timestamp("2024-01-01 08:00:00.005", tz="UTC")])  # noqa: E731
    d = dict(A=dict(kl=a, target=series(a, b0=1000.0), funding=f(1e-4), mark=a.assign(close=102.0)), B=dict(kl=b, target=series(b, b0=-1000.0), funding=f(2e-4), mark=b.assign(close=204.0)))
    s = run_portfolio(d, sp(fee_rt_bps=0))["summary"]
    assert s["funding"] == A(-0.102 + 0.204) and s["funding_missed"] == 0


def test_liquidation_of_one_symbol_leaves_the_other_open():
    """Madde 12: sermaye 1000, 10x. A 9000@100 = 90 adet, WB 995.5 -> LP = (9000-995.5)/(90*0.995) = 89.386 -> 89.39. B 100@100 = 1 adet kalır.
    net = -(100-89.39)*90 - 4.5 (A giriş) - 90*89.39*0.0005 (A çıkış, motor fee'si; liq_fee_rate=0) - 0.05 (B giriş) = -963.47255."""
    rows = [(100, 100, 100, 100), (100, 100, 100, 100), (100, 100, 80, 85), (85, 85, 85, 85), (85, 85, 85, 85)]
    a, b = bars([100] * 5, rows=rows), bars([100] * 5)
    spc = sp(capital=1000.0, leverage=10, liq=True, mmr=0.005, liq_fee_rate=0.0, close_out=False)
    r = run_portfolio({"A": dict(kl=a, target=series(a, b0=9000.0)), "B": dict(kl=b, target=series(b, b0=100.0))}, spc)
    f = r["fills"]
    assert list(f.sym) == ["A", "B", "A"] and list(f.liq) == [False, False, True] and f.px.iloc[2] == A(89.39)
    assert r["summary"]["n_liq"] == 1 and r["summary"]["end_position"] == 1.0 and r["summary"]["net_pnl"] == A(-963.47255)


def test_portfolio_equals_sum_of_independent_runs_when_cap_does_not_bind():
    """Madde 13: A long 1000@100 -> 110 (+100), B short 1000@50 (20 adet) -> 40 (+200); fee yan 5 bps: 0.0005*(2100 + 1800) = 1.95 -> net 298.05."""
    a, b = bars([100, 100, 110, 110, 110]), bars([50, 50, 40, 40, 40])
    ta, tb = series(a, b0=1000.0, b2=0.0), series(b, b0=-1000.0, b2=0.0)
    s = run_portfolio({"A": dict(kl=a, target=ta), "B": dict(kl=b, target=tb)}, sp(gross_cap=1e9))["summary"]
    assert s["net_pnl"] == A(298.05) and s["net_pnl"] == A(run(a, ta, sp())["summary"]["net_pnl"] + run(b, tb, sp())["summary"]["net_pnl"])


def test_one_bar_delay_fills_at_the_second_following_open():
    """Madde 25: karar b0 kapanışı; varsayılan dolum b1 açılışı (101), delay=1 -> b2 açılışı (102): 100/102 = 0.98039 -> 0.980 adet."""
    rows = [(100, 100, 100, 100), (101, 101, 101, 101), (102, 102, 102, 102), (103, 103, 103, 103)]
    kl = bars([100] * 4, rows=rows)
    t = series(kl, b0=100.0)
    f0, f1 = run(kl, t, sp())["fills"], run(kl, t, sp(delay=1))["fills"]
    assert list(f0.px) == [101.0] and list(f0.qty) == [0.990] and list(f1.px) == [102.0] and list(f1.qty) == [0.980]


def test_gross_cap_never_turns_an_increasing_target_into_a_reduction():
    """Bulgu 2: A 6 adet, fiyat 100 -> 200 (A'nın brütü 1200); B 3 adet (300) iken hedefi 400'e çıkarır: kalan alan 1000-1200 < 0, B'nin mevcut 3 adedi KÜÇÜLMEZ (satış yok)."""
    a = bars([100, 100, 200, 200, 200, 200])
    b = bars([100, 100, 100, 100, 100, 100])
    ta, tb = series(a, b0=600.0), series(b, b0=300.0, b3=400.0)
    r = run_portfolio({"A": dict(kl=a, target=ta), "B": dict(kl=b, target=tb)}, sp(capital=1000.0, leverage=5, gross_cap=1000.0))
    f = r["fills"]
    assert list(f.sym) == ["A", "B"] and list(f.side) == ["BUY", "BUY"] and r["summary"]["end_position"] == 9.0  # 6 + 3, hiç satış yok


def test_funding_at_the_instant_of_a_gap_stop_uses_the_pre_fill_position():
    """Bulgu 4: 10 adet long, stop 95; 08:00 açılışı 90'a gap'ler (stop o tikte 90'dan dolar). T = 08:00 funding'i T'den ÖNCE tutulan 10 adetle ödenir: -10*mark 100*1e-4 = -0.1."""
    rows = [(100, 100, 100, 100)] * 8 + [(90, 90, 90, 90)] * 4
    kl = bars([100] * 12, rows=rows)
    f = pd.DataFrame({"last_funding_rate": [1e-4]}, index=[pd.Timestamp("2024-01-01 08:00:00.005", tz="UTC")])
    r = run(kl, series(kl, b0=1000.0), sp(fee_rt_bps=0), funding=f, mark=kl.assign(close=100.0), stop=pd.Series(95.0, index=kl.index))
    assert list(r["fills"].px) == [100.0, 90.0] and r["summary"]["funding"] == A(-0.1)


def test_partial_stop_fills_do_not_create_rejected_orders():
    """Bulgu 5: düşük hacimli barda stop parçalı dolsa da reduce-only yeniden emir reddi (n_rejected) olmaz."""
    rows = [(100,) * 4, (100,) * 4, (99, 100, 94, 96), (100,) * 4]
    kl = bars([100] * 4, rows=rows).assign(volume=0.5)
    r = run(kl, series(kl, b0=1000.0), sp(liq=False), stop=pd.Series(95.0, index=kl.index))
    assert r["summary"]["n_rejected"] == 0 and r["summary"]["end_position"] == 0
