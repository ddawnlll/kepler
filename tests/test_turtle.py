"""V3 risk motoru / Turtle yöneticisi (BACKTEST.md §5.2, §12.2 madde 14-18). Beklenen değerler ELLE.

Fixture: gün d: kapanış 100+d, high = kapanış+1, low = kapanış-1 -> TR = 2 her gün, N = 2 (Wilder seed ortalaması). Sermaye 10000, risk %1 -> u = 100/2 = 50 adet."""
import numpy as np
import pandas as pd

from kepler import risk
from kepler import signals as sg
from kepler.referee import Spec, run_portfolio
from kepler.turtle import turtle_book

DAYS = pd.date_range("2024-01-01", periods=60, freq="1D", tz="UTC")


def hourly(rows):
    """Günlük (o,h,l,c) listesinden saatlik tape: h0 = (o,o,o,o), h1 = (o,h,h,h), h2 = (h,h,l,l), araya (l,l,l,l), son saat kapanışa gider; günlük birleşim = (o,h,l,c)."""
    out, idx = [], []
    for day, (o, h, l, c) in zip(DAYS, rows):  # noqa: E741
        bars = [(o, o, o, o), (o, h, h, h), (h, h, l, l)] + [(l, l, l, l)] * 20 + [(l, max(l, c), min(l, c), c)]
        out += bars
        idx += [day + pd.Timedelta(hours=i) for i in range(24)]
    return pd.DataFrame(out, columns=["open", "high", "low", "close"], index=pd.DatetimeIndex(idx)).assign(volume=1000.0)


def trend(n=60):
    return [(100 + d - 1, 101 + d, 99 + d, 100 + d) for d in range(n)]


def dirs_from(start, stop=None):
    def sig(kl):
        d = pd.Series(0.0, index=DAYS[: len(kl) // 24])
        d.iloc[start:stop] = 1.0
        return sg._put(kl, d)
    return sig


def emits(book, sym="A"):
    t = book[sym].target.dropna()
    return [((d - DAYS[0]).days, v) for d, v in t.items()]  # (gün indeksi 0.., hedef)


def test_wilder_n_hand_computed():
    d = pd.DataFrame(dict(high=[10, 11, 12, 13], low=[8, 9, 9, 11], close=[9, 10, 11, 12]), index=DAYS[:4])
    # TR = [2, max(2,|11-9|,|9-9|)=2, max(3,|12-10|,|9-10|)=3, max(2,|13-11|,|11-11|)=2]; N2 = (2+2+3)/3 = 7/3; N3 = (2*7/3 + 2)/3 = 20/9
    n = risk.wilder_n(d, 3)
    assert n.iloc[:2].isna().all() and n.iloc[2] == pytest_approx(7 / 3) and n.iloc[3] == pytest_approx(20 / 9)


def pytest_approx(x):
    import pytest
    return pytest.approx(x, rel=1e-12)


def test_unit_size_and_stop_from_n():
    kl = hourly(trend())
    book, info = turtle_book({"A": kl}, {"A": dirs_from(25)}, 10000.0, {"A": "g"})
    assert emits(book)[0] == (25, 50 * 125.0) and info["entries"] == 1  # u = 10000*0.01/2 = 50 adet, kapanış 125 -> notional 6250
    assert book["A"].stop[pd.Timestamp("2024-01-26 23:00", tz="UTC")] == 121.0  # 125 - 2*2


def test_pyramiding_adds_every_half_n_and_stops_at_four_units():
    kl = hourly(trend())
    book, info = turtle_book({"A": kl}, {"A": dirs_from(25)}, 10000.0, {"A": "g"})
    # +0.5N = +1 her gün: birim 2 (d26) 50*2*126, 3 (d27) 50*3*127, 4 (d28) 50*4*128; d29'da 4 birim dolu -> ekleme yok
    assert emits(book) == [(25, 6250.0), (26, 12600.0), (27, 19050.0), (28, 25600.0)] and info["adds"] == 3
    st = book["A"].stop
    assert [st[pd.Timestamp(f"2024-01-{d} 23:00", tz="UTC")] for d in (26, 27, 28, 29)] == [121.0, 122.0, 123.0, 124.0]  # her ekleme stopu son referansa taşır (ref - 4)
    assert st[pd.Timestamp("2024-01-30 10:00", tz="UTC")] == 124.0 and st[pd.Timestamp("2024-01-25 10:00", tz="UTC")] != st[pd.Timestamp("2024-01-25 10:00", tz="UTC")]  # gün içinde dünkü karar; giriş öncesi stop yok


def test_unit_limits_group_and_total():
    kl = hourly(trend())
    three = {"A": kl, "B": kl, "C": kl}
    dirs = {s: dirs_from(25) for s in three}
    book, info = turtle_book({"A": kl, "B": kl}, {"A": dirs_from(25), "B": dirs_from(25)}, 10000.0, {"A": "g", "B": "g"})  # aynı grup, tavan 6: 3 + 3, 4. birimler engellenir
    assert [d for d, _ in emits(book, "A")] == [25, 26, 27] and [d for d, _ in emits(book, "B")] == [25, 26, 27]
    book, info = turtle_book(three, dirs, 10000.0, {"A": "g", "B": "g", "C": "h"}, total_cap=7)  # toplam tavan 7: d25-26 altı birim, d27'de yalnız A (7. birim)
    assert [d for d, _ in emits(book, "A")] == [25, 26, 27] and [d for d, _ in emits(book, "B")] == [25, 26] and [d for d, _ in emits(book, "C")] == [25, 26]


def test_emulated_stop_flattens_blocks_reentry_until_signal_changes():
    rows = trend()
    rows[26] = (125, 126, 120, 126)  # d26: düşük 120 <= d25 kararının stopu 121 -> taklit stop
    kl = hourly(rows)

    def sig(k):
        d = pd.Series(0.0, index=DAYS)
        d.iloc[25:29], d.iloc[31:35] = 1.0, 1.0  # yön +1 (d25-28), 0 (d29-30), tekrar +1 (d31-34)
        return sg._put(k, d)
    book, info = turtle_book({"A": kl}, {"A": sig}, 10000.0, {"A": "g"})
    e = emits(book)
    assert e[0] == (25, 6250.0) and e[1] == (26, 0.0) and info["stops"] == 1  # d27-28 sinyal hâlâ +1: yeniden giriş yok
    assert [d for d, _ in e[2:]][0] == 31 and e[2][1] > 0  # sinyal 0'a, sonra yeniden +1'e dönünce yeni giriş


def test_fixed_mode_without_stop_pyramid_limits_is_the_g2_rule():
    kl = hourly(trend())

    def sig(k):
        d = pd.Series(0.0, index=DAYS)
        d.iloc[25:30], d.iloc[30:35] = 1.0, -1.0
        return sg._put(k, d)
    book, _ = turtle_book({"A": kl}, {"A": sig}, 10000.0, {"A": "g"}, fixed=1000.0, stop=False, pyramid=False, limits=False)
    assert emits(book) == [(25, 1000.0), (30, -1000.0), (35, 0.0)] and book["A"].stop.isna().all()  # girişte ±1000, çevirmede tersi, çıkışta 0


def test_book_run_never_exceeds_gross_cap():
    kl = hourly(trend())
    book, _ = turtle_book({"A": kl, "B": kl}, {"A": dirs_from(25), "B": dirs_from(25)}, 10000.0, {"A": "g", "B": "h"})
    cap = 20000.0  # iki sembol 4 birimlik hedef ~ 25600 + 25600 > 20000
    r = run_portfolio({s: dict(kl=kl, target=b.target, stop=b.stop) for s, b in book.items()}, Spec(tick="0.01", step="0.001", capital=10000.0, leverage=10, liq=False, gross_cap=cap))
    pos, last, worst = {}, {}, 0.0
    for x in r["fills"].itertuples():  # her dolumdan sonra brüt (her sembol son dolum fiyatıyla; diğer sembolün fiyatı <= 1 gün eski: ~%1 pay)
        pos[x.sym], last[x.sym] = pos.get(x.sym, 0.0) + (x.qty if x.side == "BUY" else -x.qty), x.px
        worst = max(worst, sum(abs(pos[k]) * last[k] for k in pos))
    assert 19000 < worst <= cap * 1.01 and r["summary"]["n_rejected"] == 0  # tavan bağlıyor (19000'in üstüne çıkar) ama aşılmaz


def sp(**kw):
    return Spec(**{**dict(tick="0.01", step="0.001", capital=10000.0, leverage=10, liq=True, fee_rt_bps=10.0, slip_rt_bps=2.0), **kw})


def test_evaluate_book_runs_audits_and_records(tmp_path):
    from kepler import evaluate as ev
    kl = hourly(trend())
    book = lambda kls: turtle_book(kls, {s: dirs_from(25) for s in kls}, 10000.0, {s: "g" for s in kls})[0]  # noqa: E731
    out = ev.evaluate_book(book, {"A": dict(kl=kl), "B": dict(kl=kl)}, [sp()], tmp_path / "l.jsonl", "h", "d", name="t")
    row = out[0]["row"]
    assert row["config"]["book"] is True and row["config"]["audit_causal"] is True and row["result"]["n_rejected"] == 0 and row["result"]["n_fills"] > 2


def test_evaluate_book_rejects_a_leaking_panel_signal(tmp_path):
    import pytest
    from kepler import evaluate as ev
    kl = hourly(trend())

    def leak(kls):  # her barda bir sonraki barın kapanışına bakar
        return {s: pd.DataFrame(dict(target=np.where(k.close.shift(-1) > k.close, 1000.0, -1000.0), stop=np.nan), index=k.index) for s, k in kls.items()}
    with pytest.raises(AssertionError, match="geleceğe"):
        ev.evaluate_book(leak, {"A": dict(kl=kl)}, [sp()], tmp_path / "l.jsonl", "h", "d")


def test_book_kill_switch_flattens_at_25pct_drawdown_and_stays_flat(tmp_path):
    """Madde 18: sermaye 1000, 10 adet long @100; fiyat 40. barda 70'e düşer -> bar 39 PnL = 10*(70-100) = -300 (%30 > %25): tetik b39, hedef 0, b40 açılışında 70'den satış;
    sonra yeniden giriş yok. net = -300 - 0.0006*(1000 + 700) = -301.02 (fee 10 + slip 2 bps rt)."""
    from kepler import evaluate as ev
    from tests.test_referee import bars
    kl = bars([100.0] * 40 + [70.0] * 60)
    t = pd.Series(np.nan, index=kl.index)
    t.iloc[5], t.iloc[80] = 1000.0, 1000.0  # b80'de aynı hedef yeniden verilir: kill switch yüzünden işlem yok
    book = lambda kls: {s: pd.DataFrame(dict(target=t.reindex(k.index), stop=np.nan)) for s, k in kls.items()}  # noqa: E731
    out = ev.evaluate_book(book, {"A": dict(kl=kl)}, [sp(capital=1000.0)], tmp_path / "l.jsonl", "h", "d", kill_dd=0.25)[0]
    f, s = out["res"]["fills"], out["res"]["summary"]
    assert list(f.side) == ["BUY", "SELL"] and list(f.px) == [100.0, 70.0] and out["row"]["config"]["kill_at"] == str(kl.index[39])
    assert s["end_position"] == 0 and s["net_pnl"] == pytest_approx(-300 - 0.0006 * 1700)
