"""Zone Fade yöneticisi (kitap sözleşmesi): hedef/stop serileri, boyut, portföy sınırları, stop taklidi, nedensellik, hakemle uçtan uca. Beklenen değerler elle.

Yönetici testlerinde servis sahte durumla değiştirilir (karar anı başına elle verilen 4h bar ve seviyeler); gerçek servis tests/test_state.py'de. Sahte plan: karar k, T0 + 4(k+1) saatte
kapanan 4h barın sonudur; kararın yazıldığı saatlik bar indeksi 4k+3."""
import numpy as np
import pandas as pd
import pytest

from kepler import audit
from kepler import state as stt
from kepler.experts import zone_fade as zf

A = pytest.approx
T0 = pd.Timestamp("2022-01-01", tz="UTC")


class Fake:
    def __init__(self, n_dec, plan):
        self.t = np.array([(T0 + pd.Timedelta(hours=4 * (k + 1))).value for k in range(n_dec)])
        self.pos1h = np.array([4 * k + 3 for k in range(n_dec)])
        self.plan = plan

    def at(self, i):
        d = dict(o=100.0, h=100.5, l=99.5, c=100.0, atr=4.0, imp_up=0.0, imp_dn=0.0, sw_hi=[], sw_lo=[], poc=83.0)
        d.update(self.plan.get(i, {}))
        t = pd.Timestamp(int(self.t[i]), unit="ns", tz="UTC")
        return stt.AsOf(t, t - pd.Timedelta("1h"), d["o"], d["h"], d["l"], d["c"], d["atr"], d["imp_up"], d["imp_dn"], True, np.array(d["sw_hi"], float), np.array(d["sw_lo"], float),
                        lambda: dict(poc=d["poc"], vah=d["poc"] + 5, val=d["poc"] - 5))


def flat(n, over=None, price=100.0):
    kl = pd.DataFrame(dict(open=price, high=price, low=price, close=price, volume=1.0), index=pd.date_range(T0, periods=n, freq="1h", tz="UTC"))
    for h, kw in (over or {}).items():
        for k, v in kw.items():
            kl.iloc[h, kl.columns.get_loc(k)] = v
    return kl


def make(monkeypatch, plans, kl, p=None, capital=10_000.0, **kw):
    monkeypatch.setattr(zf.stt, "build", lambda data, specs: {sp.sym: Fake(len(kl) // 4, plans[sp.sym]) for sp in specs})
    book = zf.make_book(capital, p or zf.Params(), **kw)
    return book({s: kl for s in plans}), book


SHORT = {0: dict(imp_up=5.0, sw_hi=[105.0])}  # k=0'da aday: S = 105, ATR 4 -> bölge [101, 105], stop 107
LONG = {0: dict(imp_dn=5.0, sw_lo=[95.0])}  # S = 95 -> bölge [95, 99], stop 93
TRIG_S = dict(o=100, h=104, l=98, c=99.0, poc=83.0)  # short tetik: R = 107 - 99 = 8, ödül 99 - 83 = 16: R:R 2,0
TRIG_L = dict(o=100, h=101, l=98, c=99.5, poc=112.5)  # long tetik: R = 99,5 - 93 = 6,5, ödül 13: R:R 2,0
N_S = 50 * 99 / 8  # risk 0,005 x 10000 = 50; notional = 50 / (8 / 99) = 618,75
N_L = 50 * 99.5 / 6.5  # 765,3846...


def test_short_trade_target_exit_hand_computed(monkeypatch):
    out, book = make(monkeypatch, {"A": {**SHORT, 1: TRIG_S, 2: dict(l=90.0), 3: dict(l=83.0)}}, flat(40))  # k=3 barının low'u hedefe (83) değdi
    o = out["A"]
    assert o.target.iloc[7] == A(-N_S) and N_S == A(618.75) and o.target.iloc[15] == 0.0 and o.target.dropna().index.tolist() == [o.index[7], o.index[15]]  # tetik k=1 (saat 7), çıkış kararı k=3 (saat 15)
    assert o.stop.iloc[:7].isna().all() and (o.stop.iloc[7:15] == 107.0).all() and np.isnan(o.stop.iloc[15]) and o.stop.iloc[16:].isna().all()
    c = book.log[0]
    assert (c.side, c.state, c.why, c.ref, c.target, c.zone, c.stop) == (-1, "KAPALI", "target", 99.0, 83.0, (101.0, 105.0), 107.0) and c.va == "VA_disi"  # bölge alt 101 > VAH 88


def test_stop_emulation_uses_hourly_trigger_data_from_entry_bar(monkeypatch):
    plan = {"A": {**SHORT, 1: TRIG_S, 2: dict(l=80.0)}}  # k=2 barında hedefe (83) de değdi
    out, book = make(monkeypatch, plan, flat(40, {10: dict(high=108.0)}))  # saat 10 (k=2 barı: saat 8-11): high 108 >= stop 107
    o = out["A"]
    assert o.target.dropna().index.tolist() == [o.index[7], o.index[11]] and o.target.iloc[11] == 0.0  # çıkış kararı k=2 (saat 11): stop hakemde dolar, taklit yuvayı boşaltır
    assert (o.stop.iloc[7:11] == 107.0).all() and np.isnan(o.stop.iloc[11])
    assert book.log[0].why == "stop"  # aynı barda hedef de vardı: stop kabul edilir (kötümser)
    # giriş kararının kendi saati (7) pozisyondan ÖNCE: o saatteki spike stop sayılmaz; pozisyon açık kalır
    out, book = make(monkeypatch, plan, flat(40, {7: dict(high=108.0)}))
    assert book.log[0].state == "KAPALI" and book.log[0].why == "target"  # k=2'de hedef (low 80 <= 83) -> hedef çıkışı; stop yok
    out, book = make(monkeypatch, {"A": {**SHORT, 1: TRIG_S}}, flat(40, {7: dict(high=108.0)}))
    assert book.log[0].state == "POZISYONDA" and (out["A"].stop.iloc[7:] == 107.0).all()


def test_time_exit_after_40_days(monkeypatch):
    n = 24 * 42
    out, book = make(monkeypatch, {"A": {**SHORT, 1: TRIG_S}}, flat(n))
    c = book.log[0]
    # giriş kararı T0 + 8 saat; 40 gün sonrası T0 + 8 saat + 960 saat; ilk 4h kapanış > bu: T0 + 972 saat (k = 242, saat 971)
    assert (c.why, c.t_exit) == ("time", T0 + pd.Timedelta(hours=972)) and out["A"].target.iloc[971] == 0.0


def test_portfolio_limits_side_and_total(monkeypatch):
    # A,B,C,D short + E long aynı barda tetik: yön sınırı 3 -> D iptal (limit), E (long) girer
    plans = {s: {**SHORT, 1: TRIG_S} for s in "ABCD"} | {"E": {**LONG, 1: TRIG_L}}
    out, book = make(monkeypatch, plans, flat(24))
    got = {s: out[s].target.dropna() for s in plans}
    assert [s for s in plans if len(got[s])] == ["A", "B", "C", "E"] and got["E"].iloc[0] == A(N_L) and got["A"].iloc[0] == A(-N_S)
    assert [(c.sym, c.why) for c in book.log if c.state == "IPTAL"] == [("D", "limit")]
    # A s, B l, C s, D l, E s, F s: toplam sınır 4 -> E ve F iptal
    plans = {"A": {**SHORT, 1: TRIG_S}, "B": {**LONG, 1: TRIG_L}, "C": {**SHORT, 1: TRIG_S}, "D": {**LONG, 1: TRIG_L}, "E": {**SHORT, 1: TRIG_S}, "F": {**SHORT, 1: TRIG_S}}
    out, book = make(monkeypatch, plans, flat(24))
    assert [s for s in plans if len(out[s].target.dropna())] == ["A", "B", "C", "D"] and [(c.sym, c.why) for c in book.log if c.state == "IPTAL"] == [("E", "limit"), ("F", "limit")]


def test_sizing_cap_and_stop_tick(monkeypatch):
    out, _ = make(monkeypatch, {"A": {**SHORT, 1: TRIG_S}}, flat(24), p=zf.Params(sym_cap=0.05))
    assert out["A"].target.iloc[7] == A(-500.0)  # 618,75 > 0,05 x 10000 = 500
    plan = {"A": {0: dict(imp_up=5.0, sw_hi=[104.9]), 1: TRIG_S}}  # stop ham = 104,9 + 2 = 106,9; tick 0,5 -> 107,0
    out, _ = make(monkeypatch, plan, flat(24), ticks={"A": 0.5})
    assert (out["A"].stop.iloc[7:] == 107.0).all() and out["A"].target.iloc[7] == A(-N_S)  # boyut kuantize stoptan (107): ayni 618,75


def test_state_machine_blocks_second_candidate_until_closed(monkeypatch):
    # açık aday/pozisyon varken yeni aday oluşmaz: k=1'de imp ve S tekrar var ama aday zaten AKTIF
    out, book = make(monkeypatch, {"A": {**SHORT, 1: dict(imp_up=5.0, sw_hi=[103.0])}}, flat(24))
    assert len(book.log) == 1 and book.log[0].zone == (101.0, 105.0)


# ---- gerçek servis: nedensellik denetimi (geleceği bozunca geçmiş kararlar ve stop seviyeleri değişmez)
def test_book_is_causal_with_real_state(monkeypatch):
    monkeypatch.setattr(zf, "state_spec", lambda sym: stt.StateSpec(sym, (stt.View("1d", 30, ("atr:14", "impulse:20")), stt.View("3d", 0, ("swing:2",)), stt.View("4h", 0, ("bars",)), stt.View("1h", 24 * 20, ("profile:100",)))))
    data = {}
    for k, s in enumerate("ABC"):
        r = np.random.default_rng(10 + k)
        n = 24 * 150
        c = 100 * np.exp(np.cumsum(r.normal(0, 0.012, n)))
        o = np.r_[c[0], c[:-1]]
        data[s] = pd.DataFrame(dict(open=o, high=np.maximum(o, c) * (1 + r.uniform(0, 0.004, n)), low=np.minimum(o, c) * (1 - r.uniform(0, 0.004, n)), close=c, volume=r.uniform(1, 9, n)),
                               index=pd.date_range(T0, periods=n, freq="1h", tz="UTC"))
    book = zf.make_book(10_000.0, zf.Params(impulse=1.0, ablate="no_rr"))
    out = book(data)
    assert sum(c.state in ("KAPALI", "POZISYONDA") for c in book.log) >= 3  # denetim anlamlı: gerçekten işlem var
    assert audit.check_causal_book(book, data) == []
    assert all(out[s].equals(book(data)[s]) for s in data)  # belirlenimli


# ---- hakemle uçtan uca: taklit gerçekten sonraki açılışta girer/çıkar, stop seviyesinde dolar (Nautilus gerekir; Modal'de koşar)
def hakem(out, kl):
    from kepler import referee
    sp = referee.Spec(tick="0.01", step="0.001", capital=10_000.0, liq=False, fee_rt_bps=0.0, slip_rt_bps=0.0)
    return referee.run_portfolio({"A": dict(kl=kl, target=out["A"].target, stop=out["A"].stop)}, sp)


def test_end_to_end_target_exit_fills_at_next_open(monkeypatch):
    pytest.importorskip("nautilus_trader")
    kl = flat(40, {h: dict(open=90.0, high=90.0, low=90.0, close=90.0) for h in range(16, 40)} | {13: dict(low=83.0)})
    out, _ = make(monkeypatch, {"A": {**SHORT, 1: TRIG_S, 3: dict(l=83.0)}}, kl)
    r = hakem(out, kl)
    f = r["fills"]
    # giriş: karar saat 7 -> saat 8 açılışı (100): short 618,75 / 100 = 6,187 (lot 0,001 aşağı). çıkış kararı saat 15 -> saat 16 açılışı (90). brüt = 6,187 x (100 - 90) = 61,87
    assert list(f.side) == ["SELL", "BUY"] and list(f.px) == [100.0, 90.0] and list(f.qty) == [6.187, 6.187] and not f.stop.any()
    assert pd.Timestamp(f.ts[0], unit="ns", tz="UTC") == T0 + pd.Timedelta(hours=8) and pd.Timestamp(f.ts[1], unit="ns", tz="UTC") == T0 + pd.Timedelta(hours=16)
    assert r["summary"]["net_pnl"] == A(61.87) and r["summary"]["n_rejected"] == 0


def test_end_to_end_stop_fills_at_level_and_flat_target_clears_halt(monkeypatch):
    pytest.importorskip("nautilus_trader")
    kl = flat(40, {10: dict(high=108.0)})
    out, _ = make(monkeypatch, {"A": {**SHORT, 1: TRIG_S}}, kl)
    r = hakem(out, kl)
    f = r["fills"]
    assert list(f.side) == ["SELL", "BUY"] and list(f.px) == [100.0, 107.0] and list(f.stop) == [False, True] and r["summary"]["n_stop"] == 1  # stop seviyesinden (açılış 100 < 107: gap yok)
    assert r["summary"]["net_pnl"] == A(6.187 * (100 - 107)) and r["summary"]["n_rejected"] == 0  # -43,309


# ---- K1 null: ortak ofset dairesel kaydırma (elle)
def test_rotate_book_shifts_target_and_stop_with_common_offset():
    n = 20
    kl = flat(n, price=100.0)
    kl["close"] = np.arange(100.0, 100.0 + n)  # kapanış 100, 101, ... (saat i -> 100 + i)
    tg = np.full(n, np.nan)
    st = np.full(n, np.nan)
    tg[3], st[3:8] = -500.0, 110.0  # saat 3'te short (giriş kapanışı 103), stop 110; saat 8'de çıkış
    tg[8] = 0.0
    out = {"A": pd.DataFrame(dict(target=tg, stop=st), index=kl.index)}
    lo, hi = kl.index[0], kl.index[-1] + pd.Timedelta("1h")
    # u = 0,25 -> k = 5: pozisyon saat 8..12'ye kayar (ffill'li hedef: -500 saat 8-12, 0 sonra)
    abs_ = zf.rotate_book(out, {"A": kl}, lo, hi, 0.25, relative=False)["A"]
    assert (abs_.target.iloc[8:13] == -500.0).all() and (abs_.target.iloc[:8] == 0.0).all() and (abs_.target.iloc[13:] == 0.0).all()
    assert (abs_.stop.iloc[8:13] == 110.0).all() and abs_.stop.iloc[:8].isna().all()
    # göreli: stop / giriş kapanışı = 110 / 103; kaymış pozisyonun açılış kapanışı = saat 8 kapanışı = 108 -> stop = 108 x 110/103
    rel = zf.rotate_book(out, {"A": kl}, lo, hi, 0.25, relative=True)["A"]
    assert (rel.stop.iloc[8:13] == pytest.approx(108 * 110 / 103)).all() and (rel.target.iloc[8:13] == -500.0).all()
    # dairesel: u = 0,9 -> k = 18: pozisyon saat 21..25 -> saat 1, 2 (sarar) ... hedef -500 saat 21-25 mod 20 = 1..5
    wrap = zf.rotate_book(out, {"A": kl}, lo, hi, 0.9, relative=False)["A"]
    assert (wrap.target.iloc[1:6] == -500.0).all() and wrap.target.iloc[0] == 0.0 and wrap.target.iloc[6:].eq(0.0).all()
