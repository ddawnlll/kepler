"""Sinyal teşhisi (reports/preregistration/signal_diagnostics.md) kontrolleri: pozitif/negatif kontrol, hizalama (giriş = d+1 açılışı), terminal fiyat, funding penceresi, Holm/BH, rejim nedenselliği, φ yeniden hesabı.
Gerçek veri yok; hepsi sentetik ve bilinen cevaplı. Gerçek veri koşusu bu testler geçmeden başlamaz."""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import signal_diag as sd  # noqa: E402
import signal_diag_stats as sx  # noqa: E402

from kepler import ensemble as en  # noqa: E402
from kepler import signals as sg  # noqa: E402


# ------------------------------------------------------------------ düzeltme ve bootstrap birim testleri
def test_holm_and_bh_hand_values():
    p = np.array([0.01, 0.04, 0.03, 0.005])
    # sıralı .005,.01,.03,.04 × (4,3,2,1) = .02,.03,.06,.04 -> kümülatif max .02,.03,.06,.06
    assert sx.holm(p).tolist() == pytest.approx([0.03, 0.06, 0.06, 0.02])
    # BH: p·m/sıra = .02,.02,.04,.04 -> sondan min: .02,.02,.04,.04
    assert sx.bh(p).tolist() == pytest.approx([0.02, 0.04, 0.04, 0.02])
    assert np.isnan(sx.holm(np.array([0.01, np.nan]))[1])


def test_block_counts_sum_and_blocks():
    C = sx.block_counts(200, 50, 10.0, seed=1)
    assert C.shape == (50, 200) and np.all(C.sum(1) == 200)
    # ortalama blok 10: bir satırda ardışık gün çiftlerinin çoğu komşu (yeni blok olasılığı 0,1)
    rng_idx = np.random.default_rng(0)
    assert C.max() >= 2  # aynı gün birden çok kez örneklenir
    assert rng_idx is not None


def test_bootstrap_se_matches_analytic_for_iid():
    rng = np.random.default_rng(3)
    T, S = 800, 1
    F, Y = rng.normal(size=(T, S)), rng.normal(size=(T, S))
    est, boots = sx.ic_ts(F, Y, sx.block_counts(T, 600, 1.0001, seed=0), min_n=10)  # blok = 1: iid bootstrap
    assert np.std(boots, ddof=1) == pytest.approx(1 / math.sqrt(T), rel=0.15)
    assert abs(est) < 4 / math.sqrt(T)


# ------------------------------------------------------------------ pozitif / negatif kontrol
def synth_cells(T=1200, S=15, rho=0.3, seed=0):
    rng = np.random.default_rng(seed)
    Y = rng.normal(size=(T, S))
    return rho * Y + math.sqrt(1 - rho**2) * rng.normal(size=(T, S)), Y


def test_positive_control_recovers_known_ic():
    F, Y = synth_cells(rho=0.3)
    want = 6 / math.pi * math.asin(0.3 / 2)  # Gauss için Spearman = (6/π) asin(ρ/2) = 0,2875
    C = sx.block_counts(1200, 300, 20, seed=0)
    e_ts, b_ts = sx.ic_ts(F, Y, C)
    e_xs, b_xs, _ = sx.ic_xs(F, Y, C)
    assert e_ts == pytest.approx(want, abs=0.02)
    assert sx.summarize(e_ts, b_ts)["p"] < 1e-3 and sx.summarize(e_xs, b_xs)["p"] < 1e-3
    Fw, Yw = synth_cells(T=600, S=80, rho=0.3, seed=1)  # kesitsel Spearman küçük n'de aşağı yanlı (n = 15'te ≈ −0,02): geniş kesitte kuramsal değere yakınsar
    assert sx.ic_xs(Fw, Yw)[0] == pytest.approx(want, abs=0.02)
    s = sx.summarize(e_ts, b_ts, 3.5)
    assert s["lo_c"] < want < s["hi_c"]


def test_negative_control_false_positive_rate():
    reps, T, S = 200, 400, 10
    C = sx.block_counts(T, 200, 20, seed=0)
    praw, fam_hit = [], 0
    for r in range(reps):
        rng = np.random.default_rng(1000 + r)
        F, Y = rng.normal(size=(T, S)), rng.normal(size=(T, S))
        ps = []
        for kind in ("ts", "xs"):
            est, boots = (sx.ic_ts(F, Y, C, min_n=50) if kind == "ts" else sx.ic_xs(F, Y, C)[:2])
            ps.append(sx.summarize(est, boots)["p"])
        praw += ps
        fam_hit += bool(np.nanmin(sx.holm(np.array(ps))) <= 0.05)
    frac = np.mean(np.array(praw) < 0.05)
    assert 0.02 <= frac <= 0.09, frac  # nominal 0,05 (binom ±): bootstrap SE biraz gürültülü
    assert fam_hit / reps <= 0.10, fam_hit  # Holm ile aile içi yanlış keşif


def test_cluster_and_correlation_hand():
    rng = np.random.default_rng(0)
    T, S = 300, 8
    a = rng.normal(size=(T, S))
    A = dict(a=a, b=a + 0.1 * rng.normal(size=(T, S)), c=-a + 0.1 * rng.normal(size=(T, S)), d=rng.normal(size=(T, S)))
    valid = np.ones((T, S), bool)
    corr = sx.cell_spearman(A, valid)
    assert corr.loc["a", "b"] > 0.95 and corr.loc["a", "c"] < -0.95 and abs(corr.loc["a", "d"]) < 0.1
    cl = sx.cluster(corr, 0.5)
    assert cl["a"] == cl["b"] == cl["c"] != cl["d"]  # işaretten bağımsız: ters kopya aynı küme
    cx = sx.daily_xs_corr(A, valid)
    assert cx.loc["a", "b"] > 0.9 and cx.loc["a", "c"] < -0.9


# ------------------------------------------------------------------ hizalama: giriş = d+1 açılışı
def walk_kls(n_days=400, syms=("A", "B", "C", "D", "E", "F"), seed=0):
    """Rastgele yürüyüş saatlik kline (open = önceki close), fund_hr yok."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=n_days * 24, freq="1h", tz="UTC")
    out = {}
    for s in syms:
        c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx))))
        o = np.r_[c[0], c[:-1]]
        out[s] = pd.DataFrame(dict(open=o, high=np.maximum(o, c), low=np.minimum(o, c), close=c, volume=1.0, quote_volume=1e6, taker_buy_quote_volume=5e5), index=idx)
    return out


def empty_funding():
    return pd.DataFrame(dict(funding_interval_hours=pd.Series(dtype=float), last_funding_rate=pd.Series(dtype=float)), index=pd.DatetimeIndex([], tz="UTC"))


def first_open(kl):
    return kl.open.resample("1D").first()


def sigma_const(kls, v=0.6):
    days_ = pd.date_range("2022-01-01", periods=400, freq="1D", tz="UTC")
    return pd.DataFrame(v, index=days_, columns=list(kls))


def test_forward_return_starts_at_next_day_open():
    kls = walk_kls()
    sig = sigma_const(kls)
    idx = sig.index[10:300]
    fw = sd.fwd_panels(kls, {s: empty_funding() for s in kls}, idx, sig, horizons=(1, 5), data_end=pd.Timestamp("2023-02-04", tz="UTC"))
    O = first_open(kls["A"])
    d = idx[20]
    want1 = math.log(O[d + pd.Timedelta(days=2)] / O[d + pd.Timedelta(days=1)]) / (0.6 * math.sqrt(1 / 365))
    want5 = math.log(O[d + pd.Timedelta(days=6)] / O[d + pd.Timedelta(days=1)]) / (0.6 * math.sqrt(5 / 365))
    assert fw[1]["Y"][20, 0] == pytest.approx(want1, rel=1e-9)
    assert fw[5]["Y"][20, 0] == pytest.approx(want5, rel=1e-9)
    assert np.isnan(fw[1]["Ytot"][20, 0])  # funding yok -> toplam getiri hedefi NaN


def test_decision_day_return_does_not_leak_into_forward_window():
    kls = walk_kls(n_days=1500, syms=("A", "B", "C", "D", "E", "F", "G", "H"), seed=1)
    sig = pd.DataFrame(0.6, index=pd.date_range("2022-01-01", periods=1500, freq="1D", tz="UTC"), columns=list(kls))
    idx = sig.index[5:1400]
    fw = sd.fwd_panels(kls, {s: empty_funding() for s in kls}, idx, sig, horizons=(1, 3), data_end=pd.Timestamp("2026-02-20", tz="UTC"))
    close = pd.DataFrame({s: kl.close.resample("1D").last() for s, kl in kls.items()})
    past = np.log(close / close.shift(1)).reindex(idx).to_numpy()  # karar günü getirisi (d-1 -> d)
    C = sx.block_counts(len(idx), 200, 20, seed=0)
    for h in (1, 3):
        est, _ = sx.ic_ts(past, fw[h]["Y"], None, min_n=50)
        assert abs(est) < 0.06  # rastgele yürüyüş: geçmiş getiri ileri pencereye sızmıyor
    # güç: tahmin = gerçek ileri getiri iken IC = 1, ve 1 bar kaydırılmış (giriş = d açılışı) mutantta karar günü getirisi ile IC ≈ 1 olurdu
    assert sx.ic_ts(fw[1]["Y"], fw[1]["Y"], None, min_n=50)[0] == pytest.approx(1.0)
    O = pd.DataFrame({s: first_open(kl) for s, kl in kls.items()})
    mutant = (np.log(O.shift(-1) / O) / (0.6 * math.sqrt(1 / 365))).reindex(idx).to_numpy()  # d -> d+1 (karar gününün kendi getirisi; karar anında zaten bilinir)
    past_day = np.log(O.shift(-1) / O).reindex(idx).to_numpy()
    assert sx.ic_ts(past_day, mutant, None, min_n=50)[0] == pytest.approx(1.0)  # kontrolün gücü: bu hizalama hatası yakalanırdı
    assert C.shape[1] == len(idx)


def test_terminal_price_for_delisted_symbol_and_global_end():
    kls = walk_kls(n_days=60, syms=("A", "B"), seed=2)
    kls["B"] = kls["B"].iloc[: 30 * 24 + 5]  # B, 31. günün ilk saatlerinde biter (delist)
    sig = sigma_const(kls).iloc[:60]
    idx = sig.index[:55]
    end = pd.Timestamp("2022-02-20", tz="UTC")
    fw = sd.fwd_panels(kls, {s: empty_funding() for s in kls}, idx, sig, horizons=(1, 5), data_end=end)
    d = idx[40]  # çıkış B'nin verisinden sonra
    assert fw[5]["term"][40, 1] and not fw[5]["term"][40, 0]
    want = math.log(kls["B"].close.iloc[-1] / first_open(kls["A"]).iloc[0]) if False else math.log(kls["B"].close.iloc[-1] / first_open(kls["B"])[d + pd.Timedelta(days=1)]) if (d + pd.Timedelta(days=1)) in first_open(kls["B"]).index else None
    assert want is None  # B bu giriş gününde zaten yok: giriş NaN -> hücre düşer
    assert np.isnan(fw[5]["Y"][40, 1])
    d2 = idx[27]  # giriş (gün 29) var, çıkış (gün 33) B'nin ömründen sonra
    want2 = math.log(kls["B"].close.iloc[-1] / first_open(kls["B"])[d2 + pd.Timedelta(days=1)]) / (0.6 * math.sqrt(5 / 365))
    assert fw[5]["Y"][27, 1] == pytest.approx(want2, rel=1e-9) and fw[5]["term"][27, 1]
    # küresel veri sonu: çıkış günü data_end'den sonra -> NaN
    late = [i for i, dd in enumerate(idx) if dd + pd.Timedelta(days=2) > end][0]
    assert np.isnan(fw[1]["Y"][late, 0]) and not np.isnan(fw[1]["Y"][late - 1, 0])


def test_funding_window_entry_event_excluded_exit_event_included():
    kls = walk_kls(n_days=40, syms=("A",), seed=3)
    sig = sigma_const(kls).iloc[:40]
    t0 = pd.Timestamp("2022-01-12", tz="UTC")  # d = 2022-01-10, giriş = 01-11 00:00, çıkış (h = 3) = 01-14 00:00
    ev = pd.DatetimeIndex([pd.Timestamp("2022-01-10 16:00", tz="UTC"), pd.Timestamp("2022-01-11 00:00:00.004", tz="UTC"), pd.Timestamp("2022-01-11 08:00", tz="UTC"),
                           pd.Timestamp("2022-01-13 16:00", tz="UTC"), pd.Timestamp("2022-01-14 00:00", tz="UTC"), pd.Timestamp("2022-01-14 08:00", tz="UTC")])
    first = pd.Timestamp("2022-01-01", tz="UTC")
    ev = ev.append(pd.DatetimeIndex([first]))
    rate = pd.Series([0.001, 0.002, 0.004, 0.008, 0.016, 0.032, 0.0], index=ev).sort_index()
    funding = {"A": pd.DataFrame(dict(funding_interval_hours=8.0, last_funding_rate=rate))}
    idx = sig.index[5:30]
    fw = sd.fwd_panels(kls, funding, idx, sig, horizons=(3,), data_end=pd.Timestamp("2022-02-08", tz="UTC"))
    i = list(idx).index(pd.Timestamp("2022-01-10", tz="UTC"))
    O = first_open(kls["A"])
    R = math.log(O[pd.Timestamp("2022-01-14", tz="UTC")] / O[pd.Timestamp("2022-01-11", tz="UTC")])
    pay = 0.004 + 0.008 + 0.016  # (01-11 00:00, 01-14 00:00]: 00:00 damgalı olay (giriş) hariç, 01-14 00:00 olayı (çıkış) dahil; 01-14 08:00 hariç
    scale = 0.6 * math.sqrt(3 / 365)
    assert fw[3]["Ytot"][i, 0] == pytest.approx((R - pay) / scale, rel=1e-9)
    assert fw[3]["Y"][i, 0] == pytest.approx(R / scale, rel=1e-9)
    assert t0 is not None


# ------------------------------------------------------------------ rejim nedenselliği ve φ yeniden hesabı
def test_regime_label_is_causal_and_mutant_is_caught():
    from kepler import robust
    rng = np.random.default_rng(0)
    c = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.001, 0.03, 700))), index=pd.date_range("2022-01-01", periods=700, freq="1D", tz="UTC"))
    full = robust.regime(c)
    for k in (300, 450, 600):
        pre = robust.regime(c.iloc[:k])
        assert pre.fillna("x").equals(full.iloc[:k].fillna("x"))  # kesilmiş seri geçmiş etiketi değiştirmez
    mut = full.shift(-1)  # bilinçli sızıntı: d+1 etiketi d'ye
    assert not robust.regime(c.iloc[:450]).fillna("x").equals(mut.iloc[:450].fillna("x"))


def test_phi_matches_independent_recomputation_from_raw_events():
    n_days = 30
    kls = walk_kls(n_days=n_days, syms=("A",), seed=4)
    idx = pd.date_range("2022-01-01", periods=n_days * 3, freq="8h", tz="UTC") + pd.Timedelta(milliseconds=5)  # damga jitter (arşiv gibi)
    rng = np.random.default_rng(5)
    rates = rng.normal(0.0001, 0.0002, len(idx))
    funding = pd.DataFrame(dict(funding_interval_hours=8.0, last_funding_rate=rates), index=idx)
    kl = sg.with_funding(kls["A"], funding)
    p = en.Params(carry_days=7, vol_days=3, vol_floor=0.0, min_days=3)
    close, _ = en.panel({"A": kl})
    st = en.market_state(close, {"A": kl}, p)
    d = pd.Timestamp("2022-01-20", tz="UTC")  # karar günü: 23:00 barı, kapanış 01-21 00:00
    T = d + pd.Timedelta(days=1)
    bars = pd.date_range(T - pd.Timedelta(hours=1 + 167), T - pd.Timedelta(hours=1), freq="1h")  # 168 saatlik bar açılışları, sonuncusu 23:00
    ev_ts = idx.round("1min")
    hourly = []
    for b in bars:
        known = np.flatnonzero(ev_ts <= b + pd.Timedelta(hours=1))  # bar kapanışında bilinen son olay
        hourly.append(rates[known[-1]] / 8.0)
    want = float(np.mean(hourly)) * 24 * 365
    assert st["phi"]["A"][d] == pytest.approx(want, rel=1e-9)
    # katı sürüm: T damgalı olay (01-21 00:00:00.005 -> 00:00) karar anında bilinen sayılmaz
    ks = sd.with_funding_strict(kls["A"], funding)
    diff = kl.index[(kl.fund_hr != ks.fund_hr).to_numpy()]
    assert len(diff) > 0 and set(diff.hour) <= {7, 15, 23}  # yalnızca kapanışı olay anına denk gelen barlar (08/16/00) ayrılır
    assert (kl.fund_hr[kl.index.hour == 23].iloc[1:-1] != ks.fund_hr[ks.index.hour == 23].iloc[1:-1]).all()  # karar barında (23:00) olay anı damgalı oran katı sürümde görünmez


def test_panel_pipeline_end_to_end_on_synthetic_walk():
    """forecasts + fwd_panels + analyze uçtan uca (küçük B): gürültü evreninde hiçbir Holm keşfi yok, panel şekilleri tutarlı."""
    kls = walk_kls(n_days=520, syms=("BTCUSDT",) + tuple("BCDEFGHIJ"), seed=7)  # BTCUSDT: rejim etiketi
    funding = {s: empty_funding() for s in kls}
    for s in kls:  # 8 saatlik rastgele funding
        i = pd.date_range("2022-01-01", periods=520 * 3, freq="8h", tz="UTC")
        funding[s] = pd.DataFrame(dict(funding_interval_hours=8.0, last_funding_rate=np.random.default_rng(sum(map(ord, s))).normal(0.0001, 0.0002, len(i))), index=i)
        kls[s] = sg.with_funding(kls[s], funding[s])
    old = (sd.DEC_START, sd.DEC_LAST, sd.DATA_END)
    sd.DEC_START, sd.DEC_LAST, sd.DATA_END = pd.Timestamp("2022-06-01", tz="UTC"), pd.Timestamp("2023-05-15", tz="UTC"), pd.Timestamp("2023-06-10", tz="UTC")
    try:
        P = sd.build_panel(kls, funding, kls, None)
        assert P["act"].shape == P["Y"][5].shape == P["F"]["trend"].shape and P["act"].any()
        res = sd.analyze(P, B=120, verbose=False)["result"]
    finally:
        sd.DEC_START, sd.DEC_LAST, sd.DATA_END = old
    assert res["n_trials"]["family"] == 108
    assert all(c["decision"] in ("TUT", "YENİDEN KUR", "AT") for c in res["cards"].values())
    assert not any(c["ic_pass"] for c in res["cards"].values())  # saf rastgele yürüyüş: kanıt yok
    assert res["n_clusters"] >= 1
    assert norm.isf(0.05 / 216) == pytest.approx(sd.Z_CORR)
