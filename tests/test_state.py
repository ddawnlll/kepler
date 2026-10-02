"""Market state servisi v0 (BACKTEST §15.5): 7 kural. Beklenen değerler testte ELLE hesaplanmıştır (çıktıyı kendisiyle karşılaştıran test yok).

Ortak fixture: günlük mumlardan saatlik veri (gün = 24 bar; açılış O, bir saatte high H, bir saatte low L, son saatte kapanış C)."""
import numpy as np
import pandas as pd
import pytest

from kepler import state as S
from kepler.experts import zone_fade as zf

A = pytest.approx
T0 = pd.Timestamp("2022-01-01", tz="UTC")  # gün_no 18993 = 3 x 6331: 3d çıpasına hizalı


def hourly(days, start=T0):
    """days: [(O, H, L, C)] -> saatlik kl. Gün açılışı O, 1. saatte H, 2. saatte L, son saatte C; diğer saatler O'da düz."""
    rows = []
    for o, h, l, c in days:
        for k in range(24):
            r = [o, o, o, o]
            if k == 1:
                r[1] = h
            if k == 2:
                r[2] = l
            if k == 23:
                r[3], r[1], r[2] = c, max(o, c), min(o, c)
            rows.append(r + [1.0])
    return pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=pd.date_range(start, periods=24 * len(days), freq="1h", tz="UTC"))


def spec(*views):
    return S.StateSpec("X", tuple(views))


V_ALL = (S.View("1d", 20, ("atr:14", "impulse:20")), S.View("3d", 0, ("swing:2",)), S.View("4h", 0, ("bars",)), S.View("1h", 48, ("profile:10",)))


def walk(n_days=120, seed=3):
    r = np.random.default_rng(seed)
    n = 24 * n_days
    c = 100 * np.exp(np.cumsum(r.normal(0, 0.006, n)))
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame(dict(open=o, high=np.maximum(o, c) * (1 + r.uniform(0, 0.004, n)), low=np.minimum(o, c) * (1 - r.uniform(0, 0.004, n)), close=c, volume=r.uniform(1, 9, n)),
                        index=pd.date_range(T0, periods=n, freq="1h", tz="UTC"))


def perturb(kl, k, seed):
    alt = kl.copy()
    alt.iloc[k:, :4] = alt.iloc[k:, :4].to_numpy() * np.random.default_rng(seed).uniform(0.5, 1.5, (len(kl) - k, 4))
    alt.iloc[k:, 4] *= 3
    return alt


# ---- 1. nedensellik
@pytest.mark.parametrize("k", [24 * 40 + 1, 24 * 60 + 5, 24 * 61 + 11, 24 * 90 + 22])
def test_state_is_causal(k):
    kl = walk()
    full = S.MarketState(spec(*V_ALL), kl)
    cut = kl.index[k]  # ilk bozulan/kesilen saatin açılışı: ona kadar kapanan her karar anı aynı olmalı
    for other in (perturb(kl, k, 1), kl.iloc[:k]):
        st = S.MarketState(spec(*V_ALL), other)
        assert st.digest(upto=cut) == full.digest(upto=cut)
        for t in full.t[full.t <= cut.value][-40:]:  # profil de geçmişe bağlı kalmalı
            assert st.profile_at(int(t)) == full.profile_at(int(t))


# ---- 2. belirlenimlilik
def test_state_hash_is_deterministic():
    kl = walk()
    S._CACHE.clear()
    h1 = S.build({"X": kl}, [spec(*V_ALL)])["X"].digest()
    S._CACHE.clear()
    h2 = S.build({"X": kl.copy()}, [spec(*V_ALL)])["X"].digest()
    assert h1 == h2
    assert S.MarketState(spec(*V_ALL), kl.iloc[:-5]).digest() != h1  # farklı veri farklı özet


# ---- 3. pencere denkliği
def test_window_equals_full_series():
    kl = walk()
    full = S.MarketState(spec(*V_ALL), kl)
    lo, hi = pd.Timestamp("2022-03-01", tz="UTC"), pd.Timestamp("2022-04-10", tz="UTC")
    win = S.MarketState(spec(*V_ALL), kl[kl.index < hi])  # pencere sonu: veri hi'de biter, ısınma (veri başı) dahil
    m1, m2 = (full.t >= lo.value) & (full.t <= hi.value), (win.t >= lo.value) & (win.t <= hi.value)
    assert m1.sum() == m2.sum() > 100
    for name in ("o", "h", "l", "c", "atr", "imp_up", "imp_dn", "valid", "k_hi", "k_lo"):
        assert np.array_equal(getattr(full, name)[m1], getattr(win, name)[m2], equal_nan=True), name
    assert [full.at(i).t for i in np.flatnonzero(m1)] == [win.at(i).t for i in np.flatnonzero(m2)]


# ---- 4. toplama
def test_3d_anchor_dates_and_incomplete_bar_not_served():
    # 2021-12-30 00:00'dan 2022-01-08 10:00'a. gün_no(2022-01-01) = 52 x 365 + 13 artık = 18993 = 3 x 6331.
    idx = pd.date_range("2021-12-30", "2022-01-08 10:00", freq="1h", tz="UTC")
    kl = pd.DataFrame(dict(open=1.0, high=2.0, low=0.5, close=1.5, volume=1.0), index=idx)
    b = S.bars(kl, "3d")
    # beklenen 3d açılışları: 29 Ara (gün 18990), 1 Oca, 4 Oca, 7 Oca
    assert [str(x.date()) for x in b.index] == ["2021-12-29", "2022-01-01", "2022-01-04", "2022-01-07"]
    assert list(b.n) == [48, 72, 72, 35]  # ilk bar yarım (29 Ara yok: 24 saat eksik), son bar oluşmakta (24 + 11 saat)
    st = S.MarketState(spec(S.View("3d", 0, ("swing:2",)), S.View("4h", 0, ("bars",))), kl)
    assert st.missing["3d"] == 24  # tamamlanmış barlar: 29 Ara (24 eksik), 1 Oca, 4 Oca; 7 Oca tamamlanmadı (sayılmaz)
    assert st.t[-1] == pd.Timestamp("2022-01-08 08:00", tz="UTC").value  # 08:00-12:00 4h barı veride bitmiyor (son bar 10:00): karar yok
    assert S.bars(kl, "1d").index[0] == pd.Timestamp("2021-12-30", tz="UTC") and S.bars(kl, "4h").index[1] == pd.Timestamp("2021-12-30 04:00", tz="UTC")


def test_missing_bar_count_and_gap():
    kl = hourly([(100, 101, 99, 100)] * 4)
    kl = kl.drop(kl.index[[30, 31, 70]])  # 2. günde 2, 3. günde 1 saatlik bar yok
    st = S.MarketState(spec(S.View("1h", 0, ()), S.View("4h", 0, ("bars",)), S.View("1d", 0, ())), kl)
    assert st.missing == {"1h": 3, "4h": 3, "1d": 3}  # 4h: 4-8 barında 2, 68-72 barında 1 eksik saat; 1d: 2. gün 2, 3. gün 1


def test_last_completed_day_only():
    kl = hourly([(100, 101, 99, 100)] * 14 + [(100, 108, 92, 100), (100, 101, 99, 100), (100, 101, 99, 100)])
    st = S.MarketState(spec(S.View("1d", 0, ("atr:14",)), S.View("4h", 0, ("bars",))), kl)
    at = lambda s: st.at(int(np.flatnonzero(st.t == pd.Timestamp(s, tz="UTC").value)[0]))  # noqa: E731
    # TR: ilk 14 gün 2 -> ATR[13] = 2; gün 14 TR 16 -> (13*2 + 16)/14 = 3; gün 15 TR 2 -> (13*3 + 2)/14 = 41/14
    assert at("2022-01-15 00:00").atr == A(2.0)  # gün 13 tamamlandı
    assert at("2022-01-16 00:00").atr == A(3.0)
    assert at("2022-01-16 04:00").atr == A(3.0) and at("2022-01-16 20:00").atr == A(3.0)  # gün 15 oluşuyor: servise girmez
    assert at("2022-01-17 00:00").atr == A(41 / 14)


# ---- 5. özellikler elle hesaplı
def test_impulse_ramp_hand_computed():
    # gün i: O=100+i, H=102+i, L=98+i, C=101+i; önceki kapanış = 100+i -> TR = 4 her gün, ATR = 4
    up = hourly([(100 + i, 102 + i, 98 + i, 101 + i) for i in range(30)])
    st = S.MarketState(spec(S.View("1d", 0, ("atr:14", "impulse:20")), S.View("4h", 0, ("bars",))), up)
    a = st.at(int(np.flatnonzero(st.t == pd.Timestamp("2022-01-26", tz="UTC").value)[0]))  # gün 24 tamamlandı; pencere gün 5..24
    # max high = H24 = 126 (pencerenin sonu), ondan ÖNCEKİ min low = L5 = 103 -> 23; 23/4 = 5,75. min low = L5 pencere başı: öncesi yok -> 0
    assert a.atr == A(4.0) and a.imp_up == A(5.75) and a.imp_dn == 0.0
    dn = hourly([(130 - i, 132 - i, 128 - i, 129 - i) for i in range(30)])  # ayna: önceki kapanış 130-i -> TR = |L - pc| ... H-L = 4, |H-pc| = 2
    st = S.MarketState(spec(S.View("1d", 0, ("atr:14", "impulse:20")), S.View("4h", 0, ("bars",))), dn)
    a = st.at(int(np.flatnonzero(st.t == pd.Timestamp("2022-01-26", tz="UTC").value)[0]))
    # min low = L24 = 104; ondan ÖNCEKİ max high = H5 = 127 -> 23; 23/4 = 5,75
    assert a.atr == A(4.0) and a.imp_dn == A(5.75) and a.imp_up == 0.0


def test_impulse_uses_only_bars_before_the_extreme():
    # gün 0-19 düz (H 101, L 99, TR 2), gün 20: O 100 H 130 L 90 C 100 -> TR = 40; ATR[20] = (13*2 + 40)/14 = 66/14
    kl = hourly([(100, 101, 99, 100)] * 20 + [(100, 130, 90, 100)] + [(100, 101, 99, 100)] * 3)
    st = S.MarketState(spec(S.View("1d", 0, ("atr:14", "impulse:20")), S.View("4h", 0, ("bars",))), kl)
    a = st.at(int(np.flatnonzero(st.t == pd.Timestamp("2022-01-22", tz="UTC").value)[0]))  # gün 20 tamamlandı; pencere gün 1..20
    atr = 66 / 14
    assert a.atr == A(atr)
    assert a.imp_up == A((130 - 99) / atr)  # max'ın kendi low'u (90) hariç: ondan ÖNCEKİ min low = 99 (dahil olsaydı 40/ATR)
    assert a.imp_dn == A((101 - 90) / atr)  # min low = 90 (günün kendisi); ondan önceki max high = 101


def test_swing_fractal_hand_computed_and_confirmation_time():
    hi, lo = [10, 12, 15, 13, 11, 14, 16, 12, 9], [5, 6, 8, 7, 4, 9, 10, 6, 3]  # 3d barlar: 1 Oca'dan her 3 günde bir
    rows = []
    for h, l in zip(hi, lo):
        rows += [[(h + l) / 2, h, l, (h + l) / 2, 1.0]] * 72
    kl = pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=pd.date_range(T0, periods=72 * 9, freq="1h", tz="UTC"))
    st = S.MarketState(spec(S.View("3d", 0, ("swing:2",)), S.View("4h", 0, ("bars",))), kl)
    # swing tepe: i=2 (15 > 12, 10, 13, 11) ve i=6 (16 > 11, 14, 12, 9); i=5 (14) 16'dan küçük -> değil. Onay = i+2 barının kapanışı:
    # bar 4 (13-15 Oca) 16 Oca 00:00'da kapanır; bar 8 (25-27 Oca) 28 Oca 00:00'da
    assert list(st.sw["hi"][0]) == [15.0, 16.0]
    assert [pd.Timestamp(t, unit="ns", tz="UTC") for t in st.sw["hi"][1]] == [pd.Timestamp("2022-01-16", tz="UTC"), pd.Timestamp("2022-01-28", tz="UTC")]
    # swing dip: yalnız i=4 (4 < 8, 7, 9, 6); bar 6 (19-21 Oca) 22 Oca 00:00'da kapanınca onaylı. i=8'in sağında bar yok.
    assert list(st.sw["lo"][0]) == [4.0] and pd.Timestamp(st.sw["lo"][1][0], unit="ns", tz="UTC") == pd.Timestamp("2022-01-22", tz="UTC")
    get = lambda s: st.at(int(np.flatnonzero(st.t == pd.Timestamp(s, tz="UTC").value)[0]))  # noqa: E731
    assert list(get("2022-01-15 20:00").sw_hi) == [] and list(get("2022-01-16 00:00").sw_hi) == [15.0]  # onay anında dahil, bir karar önce değil
    assert list(get("2022-01-27 20:00").sw_hi) == [15.0] and list(get("2022-01-28 00:00").sw_hi) == [15.0, 16.0]
    assert list(get("2022-01-21 20:00").sw_lo) == [] and list(get("2022-01-22 00:00").sw_lo) == [4.0]


def test_volume_profile_poc_vah_val_hand_computed():
    # 10 kutu, aralık [0, 100] -> genişlik 10. Kutu = ⌊fiyat/10⌋ (üst sınır 9'a kısılır); hacim kestiği kutulara eşit.
    H, L, V = np.array([20.0, 60.0, 55.0, 100.0]), np.array([0.0, 40.0, 45.0, 90.0]), np.array([40.0, 30.0, 20.0, 10.0])
    # bar 1: kutu 0..2 (13,33 x3); bar 2: kutu 4..6 (10 x3); bar 3: kutu 4..5 (10 x2); bar 4: kutu 9 (10).
    # kutular: [13,33 13,33 13,33 0 20 20 10 0 0 10], toplam 100. POC: 20 eşitliği -> ilk = kutu 4, merkez 45.
    # VA (hedef 70): 20 -> +kutu 5 (40) -> +kutu 6 (50) -> 3 ve 7 boş (eşit: alt) +kutu 3 (50) -> +kutu 2 (63,33) -> +kutu 1 (76,67 >= 70): kutu 1..6 -> VAL = 10, VAH = 70
    p = S._profile(H, L, V, 10)
    assert p["poc"] == A(45.0) and p["val"] == A(10.0) and p["vah"] == A(70.0) and p["lo"] == 0.0 and p["hi"] == 100.0 and p["width"] == A(10.0)


def test_profile_window_is_closed_bars_only():
    # 12 saatlik bar; lookback 4 saat; karar 08:00 -> pencere [04:00, 08:00): saat 4-7. Saat 3 (pencere öncesi) ve saat 8 (>= t) uç değerli: dışarıda kalmalı.
    rows = [[50, 1000, -1000, 50, 1000.0]] * 12
    for k, (h, l, v) in zip(range(4, 8), [(20, 0, 40), (60, 40, 30), (55, 45, 20), (100, 90, 10)]):
        rows[k] = [50, h, l, 50, v]
    kl = pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"], index=pd.date_range(T0, periods=12, freq="1h", tz="UTC"))
    st = S.MarketState(spec(S.View("4h", 0, ("bars",)), S.View("1h", 4, ("profile:10",))), kl)
    p = st.profile_at(pd.Timestamp("2022-01-01 08:00", tz="UTC").value)
    assert p["poc"] == A(45.0) and p["val"] == A(10.0) and p["vah"] == A(70.0)
    assert st.valid.all()  # her karar anında 4 saatlik pencere dolu (t - 4 saat >= ilk bar)
    st5 = S.MarketState(spec(S.View("4h", 0, ("bars",)), S.View("1h", 5, ("profile:10",))), kl)
    assert list(st5.valid) == [False, True, True]  # t = 04:00: pencere 5 saat ister, veri 4 saatlik


def test_service_rejects_sealed_period_and_unknown_features():
    kl = hourly([(100, 101, 99, 100)] * 2, start=pd.Timestamp("2026-03-31", tz="UTC"))
    with pytest.raises(ValueError, match="mühür"):
        S.MarketState(spec(S.View("4h", 0, ("bars",))), kl)
    with pytest.raises(ValueError, match="v0"):
        S.MarketState(spec(S.View("4h", 0, ("ema:20",))), hourly([(100, 101, 99, 100)] * 2))


# ---- 6. aday yaşam döngüsü (arz bölgesi: S = 105, ATR = 4 -> bölge [101, 105], stop 107; ayna: talep S = 95 -> bölge [95, 99], stop 93)
def bar(t, o, h, l, c, poc=80.0):
    return S.AsOf(pd.Timestamp(t, tz="UTC"), pd.Timestamp(t, tz="UTC"), o, h, l, c, 4.0, 0.0, 0.0, True, np.array([]), np.array([]), lambda: dict(poc=poc, vah=poc + 5, val=poc - 5))


def sup(**kw):
    p = zf.Params(**kw)
    c = zf.Candidate(zf.EXPERT_ID, "X", -1, (101.0, 105.0), 107.0, pd.Timestamp("2022-06-01", tz="UTC"), pd.Timestamp("2022-07-01", tz="UTC"), 4.0)
    return c, p


def test_form_picks_nearest_confirmed_level_within_reach():
    a = bar("2022-06-01 04:00", 100, 100, 100, 100)
    a.imp_up, a.sw_hi = 4.0, np.array([99.0, 104.0, 110.0, 130.0])  # 99 fiyatın altı; 104 ve 110 üstünde, 6 ATR = 24 -> 124'e kadar; 130 dışında; en yakın = 104
    c = zf.form(a, "X", zf.Params())
    assert c.side == -1 and c.zone == (100.0, 104.0) and c.stop == 106.0 and c.state == "AKTIF" and c.expiry - c.born == pd.Timedelta("30D")
    a.imp_up = 3.99  # eşik 4 ATR: altında aday yok
    assert zf.form(a, "X", zf.Params()) is None
    a.imp_up, a.imp_dn, a.sw_lo = 0.0, 5.0, np.array([97.0, 80.0, 70.0])  # talep: fiyatın altındaki en yakın (97), 100 - 24 = 76'ya kadar -> 70 dışarıda
    c = zf.form(a, "X", zf.Params())
    assert c.side == 1 and c.zone == (97.0, 101.0) and c.stop == 95.0


def test_never_touched_cancels_on_expiry():
    c, p = sup()
    assert zf.watch(c, bar("2022-06-15", 98, 100.9, 97, 99), p) is None and c.state == "AKTIF"  # high 100,9 < alt 101: zone'a girmedi
    assert zf.watch(c, bar("2022-06-30 20:00", 98, 100, 97, 99), p) is None and c.state == "AKTIF"
    assert zf.watch(c, bar("2022-07-01 00:00", 98, 100, 97, 99), p) is None and (c.state, c.why) == ("IPTAL", "expiry")  # 30. gün


def test_invalid_close_above_stop_level_cancels():
    c, p = sup()
    assert zf.watch(c, bar("2022-06-02", 100, 108, 100, 107.0), p) is None and c.state == "IZLEMEDE"  # 107 > 107 değil: geçerli
    assert zf.watch(c, bar("2022-06-03", 100, 109, 100, 107.01), p) is None and (c.state, c.why) == ("IPTAL", "invalid")


def test_trigger_requires_touch_and_close_below_zone():
    c, p = sup()
    assert zf.watch(c, bar("2022-06-02", 100, 103, 100, 102), p) is None and c.state == "IZLEMEDE"  # girdi ama kapanış bölge içinde: tetik yok
    assert zf.watch(c, bar("2022-06-03", 100, 100.5, 98, 99), p) is None and c.state == "IZLEMEDE"  # kapanış < alt ama high alt'a girmedi: tetik yok
    assert zf.watch(c, bar("2022-06-04", 100, 104, 98, 100.5), p) == "trigger" and c.ref == 100.5 and c.target == 80.0  # (100,5-80)/(107-100,5) = 3,15 >= 2


def test_same_bar_touch_and_trigger_and_rr_boundary():
    # high 104 >= 101 (girdi) ve kapanış 99 < 101 (reddedildi) aynı barda; R = 107 - 99 = 8
    c, p = sup()
    assert zf.watch(c, bar("2022-06-02", 100, 104, 98, 99.0, poc=83.0), p) == "trigger" and c.target == 83.0  # (99-83)/8 = 2,0: sınır dahil
    c, p = sup()
    assert zf.watch(c, bar("2022-06-02", 100, 104, 98, 99.0, poc=83.01), p) is None and (c.state, c.why) == ("IPTAL", "rr")  # 15,99/8 = 1,99875
    c, p = sup()
    assert zf.watch(c, bar("2022-06-02", 100, 104, 98, 99.0, poc=84.5), p) is None and (c.state, c.why) == ("IPTAL", "rr")  # 14,5/8 = 1,8125


def test_hold_stop_target_time_and_same_bar_stop_wins():
    c, p = sup()
    c.state, c.target, c.t_entry = "POZISYONDA", 90.0, pd.Timestamp("2022-06-04", tz="UTC")
    assert zf.hold(c, bar("2022-06-05", 100, 101, 91, 95), False, p) is None and c.state == "POZISYONDA"  # low 91 > hedef 90
    assert zf.hold(c, bar("2022-06-06", 100, 101, 90, 95), False, p) == "target" and c.state == "KAPALI"
    c.state = "POZISYONDA"
    assert zf.hold(c, bar("2022-06-06", 100, 101, 85, 95), True, p) == "stop"  # aynı barda hem hedef (low 85 <= 90) hem stop: stop (kötümser)
    c.state = "POZISYONDA"
    assert zf.hold(c, bar("2022-07-14 00:00", 100, 101, 95, 99), False, p) is None  # tam 40 gün: geçmedi
    assert zf.hold(c, bar("2022-07-14 04:00", 100, 101, 95, 99), False, p) == "time"  # > 40 gün


def lng():
    c = zf.Candidate(zf.EXPERT_ID, "X", 1, (95.0, 99.0), 93.0, pd.Timestamp("2022-06-01", tz="UTC"), pd.Timestamp("2022-07-01", tz="UTC"), 4.0)
    return c, zf.Params()


def test_long_zone_mirror():
    c, p = lng()
    assert zf.watch(c, bar("2022-06-02", 100, 102, 99.5, 101), p) is None and c.state == "AKTIF"  # low 99,5 > üst 99: girmedi
    assert zf.watch(c, bar("2022-06-03", 100, 101, 98, 98.5), p) is None and c.state == "IZLEMEDE"  # girdi ama kapanış 98,5 <= üst: tetik yok
    assert zf.watch(c, bar("2022-06-04", 100, 104, 99.2, 101), p) is None and c.state == "IZLEMEDE"  # kapanış > üst ama low 99,2 > 99: girmedi, tetik yok
    assert zf.watch(c, bar("2022-06-05", 100, 101, 92.9, 92.9), p) is None and (c.state, c.why) == ("IPTAL", "invalid")  # kapanış 92,9 < 93 (stop): geçersiz
    # tetik + R:R: ref 99,5, R = 99,5 - 93 = 6,5; hedef >= 99,5 + 13 = 112,5
    c, p = lng()
    assert zf.watch(c, bar("2022-06-03", 100, 101, 98, 99.5, poc=112.5), p) == "trigger" and c.target == 112.5 and c.ref == 99.5  # 13/6,5 = 2,0 sınır dahil
    c, p = lng()
    assert zf.watch(c, bar("2022-06-03", 100, 101, 98, 99.5, poc=111.0), p) is None and (c.state, c.why) == ("IPTAL", "rr")  # 11,5/6,5 = 1,77
    # çıkışlar: hedef = bar HIGH'ı >= 112,5; aynı barda stop da varsa stop
    c, p = lng()
    zf.watch(c, bar("2022-06-03", 100, 101, 98, 99.5, poc=112.5), p)
    c.state, c.t_entry = "POZISYONDA", pd.Timestamp("2022-06-03", tz="UTC")
    assert zf.hold(c, bar("2022-06-04", 100, 112.4, 99, 100), False, p) is None
    assert zf.hold(c, bar("2022-06-05", 100, 112.5, 99, 100), False, p) == "target"
    c.state = "POZISYONDA"
    assert zf.hold(c, bar("2022-06-06", 100, 113, 99, 100), True, p) == "stop"


def test_no_trigger_ablation_enters_on_first_touch():
    c, p = sup(ablate="no_trigger")
    assert zf.watch(c, bar("2022-06-02", 100, 102, 99, 102.0, poc=84.0), p) == "trigger" and c.ref == 102.0  # kapanış bölge içinde: normalde tetik yok; (102-84)/(107-102) = 3,6 >= 2


def test_no_poc_ablation_target_is_2r():
    c, p = sup(ablate="no_poc")
    assert zf.watch(c, bar("2022-06-02", 100, 104, 98, 99.0), p) == "trigger"  # R = 107 - 99 = 8 -> hedef 99 - 16 = 83
    assert c.target == 83.0 and c.va == ""
    c, p = sup(ablate="no_rr")
    assert zf.watch(c, bar("2022-06-02", 100, 104, 98, 99.0, poc=95.0), p) == "trigger" and c.target == 95.0  # (99-95)/8 = 0,5: filtre kapalı


# ---- 7. önbellek
def test_cache_same_spec_once_different_spec_new_hash():
    kl = walk(60)
    S._CACHE.clear()
    n0 = S.STATS["builds"]
    a = S.build({"X": kl}, [spec(*V_ALL)])["X"]
    b = S.build({"X": kl.copy()}, [spec(*V_ALL)])["X"]
    assert a is b and S.STATS["builds"] == n0 + 1
    other = spec(S.View("1d", 20, ("atr:14", "impulse:20")), S.View("4h", 0, ("bars",)))
    assert other.id != spec(*V_ALL).id and S.build({"X": kl}, [other])["X"] is not a and S.STATS["builds"] == n0 + 2
    assert S.build({"X": kl.iloc[:-1]}, [spec(*V_ALL)])["X"] is not a and S.STATS["builds"] == n0 + 3  # aynı spec, farklı veri: yeniden hesap
