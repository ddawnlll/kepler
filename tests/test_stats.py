"""Değerlendirme araçları (BACKTEST.md §9–§11, §12.2 madde 19-25). Beklenen değerler ELLE (math.erf tabanlı bağımsız aritmetik) yazıldı."""
import numpy as np
import pandas as pd
import pytest

from kepler import robust, stats
from kepler.referee import Spec
from tests.test_referee import A, bars

R5 = np.array([1, 2, 3, 4, 5]) * 0.01  # ort 0.03, std(ddof=1) = sqrt(2.5)*0.01, g3 = 0, g4 = mean(d^4)/sd0^4 = 6.8/4 = 1.7, T = 5


def test_moments_psr_dsr_hand_values():
    sr, g3, g4, t = stats.moments(R5)
    assert sr == A(0.03 / (np.sqrt(2.5) * 0.01)) and sr == A(1.8973666) and g3 == A(0, abs=1e-12) and g4 == A(1.7) and t == 5
    # PSR(0) = Φ(SR·√(T-1)/√(1 + (g4-1)/4·SR²)) = Φ(1.8973666·2 / 1.2767145) = Φ(2.972316)
    assert stats.psr(R5) == A(0.99852194, abs=1e-6)
    # DSR, N=3 deneme SR'ları [0,1,2] (std 1): SR0 = (1-γ)Φ⁻¹(2/3) + γΦ⁻¹(1-1/(3e)) = 0.4227843*0.4307273 + 0.5772157*1.1619569 = 0.8528045; DSR = Φ((SR-SR0)·2/1.2767145)
    assert stats.sr0_from_trials([0.0, 1.0, 2.0]) == A(0.8528045, abs=1e-6) and stats.dsr(R5, [0.0, 1.0, 2.0]) == A(0.94911456, abs=1e-6)


def test_min_trl_matches_the_documented_years():
    sr_d = 0.1  # normal getiri: 1 + (1 + 0.5·0.01)·(1.6448536/0.1)² = 1 + 1.005·270.5543 = 272.9071
    assert stats.min_trl(sr_d) == A(272.907117, abs=1e-4)
    yrs = {a: stats.min_trl(a / np.sqrt(365)) / 365 for a in (0.7, 1.0, 1.5)}  # BACKTEST.md §9.2: ~5,5 / ~2,7 / ~1,2 yıl
    assert yrs[0.7] == A(5.528, abs=1e-3) and yrs[1.0] == A(2.712, abs=1e-3) and yrs[1.5] == A(1.209, abs=1e-3)


def test_rotation_p_and_bonferroni_hand_values():
    null = list(range(1, 11))  # B = 10
    assert stats.rotation_p(8, null) == A(4 / 11) and stats.rotation_p(11, null) == A(1 / 11) and stats.rotation_p(0, null) == A(1.0)  # #{null >= 8} = 3 -> (1+3)/11
    assert stats.bonferroni(0.04, 12) == A(0.48) and stats.bonferroni(0.04, 30) == 1.0


def test_rotation_null_preserves_trades_and_long_short_mix():
    kl = bars([100.0] * (24 * 8))
    v = np.array([1.0, 1, 0, -1, -1, -1, 0, 1])  # günlük kararlar
    sig = lambda k: pd.Series(np.where(k.index.hour == 23, np.repeat(v, 24), np.nan), index=k.index)  # noqa: E731
    out = robust.rotate_signal(sig, 0.25)(kl)  # k = ⌊0.25·8⌋ = 2 gün: np.roll(v, 2) = [0,1,1,1,0,-1,-1,-1]
    d = out[out.index.hour == 23].to_numpy()
    assert list(d) == [0, 1, 1, 1, 0, -1, -1, -1] and out.dropna().index.hour.unique().tolist() == [23]
    assert sorted(d) == sorted(v) and (np.diff(np.r_[d, d[0]]) != 0).sum() == (np.diff(np.r_[v, v[0]]) != 0).sum() == 4  # yön oranı ve (dairesel) geçiş sayısı korunur


def test_bootstrap_is_seeded_and_block_length_one_is_iid():
    a, b = stats.stationary_bootstrap(500, 20, 50, seed=3), stats.stationary_bootstrap(500, 20, 50, seed=3)
    assert (a == b).all() and not (a == stats.stationary_bootstrap(500, 20, 50, seed=4)).all()
    nxt = lambda idx: ((idx[:, 1:] == (idx[:, :-1] + 1) % 500)).mean()  # noqa: E731  ardışık indeks oranı
    assert nxt(stats.stationary_bootstrap(500, 1, 200, seed=1)) < 0.006  # L=1: iid, şansa bağlı ~1/500
    assert nxt(stats.stationary_bootstrap(500, 20, 200, seed=1)) == A(1 - 1 / 20, abs=0.01)  # L=20: 1 - 1/L ≈ 0.95 devam
    assert stats.stationary_bootstrap(500, 1, 200, seed=1).mean() == A(249.5, abs=2.0)  # iid düzgün başlangıç


def test_max_drawdown_and_bootstrap_summary():
    # equity (toplamsal) = 0.1, -0.1, -0.05, -0.1, 0.1; tepe (0 dahil) = 0.1 -> dd = 0, 0.2, 0.15, 0.2, 0 -> maks 0.2
    assert stats.max_drawdown([0.1, -0.2, 0.05, -0.05, 0.2]) == A(0.2)
    r = np.random.default_rng(0).normal(0.001, 0.01, 300)
    s1, s2 = stats.bootstrap_summary(r, 20, 300, 5), stats.bootstrap_summary(r, 20, 300, 5)
    assert s1 == s2 and s1["sharpe"][0] <= s1["sharpe"][1] <= s1["sharpe"][2] and 0 <= s1["maxdd"][0] <= s1["maxdd"][1]


def test_newey_west_alpha_hand_values_and_recovery():
    x, y = [0, 1, 2, 3], [1, 2, 2, 5]  # a = 0.7, b = 1.2, e = [0.3, 0.1, -1.1, 0.7], a = Σ w_i y_i, w = [0.7, 0.4, 0.1, -0.2]
    a, b, t0 = stats.nw_alpha(y, x, lag=0)  # Var = Σ w²e² = 0.0774 -> t = 0.7/0.278209 = 2.5161
    assert a == A(0.7) and b == A(1.2) and t0 == A(0.7 / np.sqrt(0.0774))
    t1 = stats.nw_alpha(y, x, lag=1)[2]  # + 2·(1/2)·Σ (w_i e_i)(w_{i+1} e_{i+1}) = 0.0194 -> Var = 0.0968 -> t = 2.2498
    assert t0 == A(2.5161, abs=1e-4) and t1 == A(0.7 / np.sqrt(0.0968)) and t1 == A(2.2498, abs=1e-4)
    rng = np.random.default_rng(2)
    rb = rng.normal(0, 0.02, 4000)
    a, b, t = stats.nw_alpha(0.001 + 0.5 * rb + rng.normal(0, 0.002, 4000), rb)  # madde 23: a ≈ 0.001, b ≈ 0.5
    assert a == A(0.001, abs=1.5e-4) and b == A(0.5, abs=0.01) and t > 10


def test_regime_labels_hand_cases_and_causality():
    up = pd.Series(100.0 + np.arange(400), index=pd.date_range("2022-01-01", periods=400, freq="1D", tz="UTC"))
    lab = robust.regime(up)
    assert lab.iloc[:230].isna().all() and (lab.iloc[230:] == "bull").all()  # EMA index 199'dan, eğim 229'dan geçerli; etiket 1 gün gecikir
    assert (robust.regime(1000.0 - up).iloc[230:] == "bear").all() and (robust.regime(pd.Series(100.0, index=up.index)).iloc[230:] == "range").all()  # sabit: eğim 0 -> yatay
    alt = up.copy()
    alt.iloc[300:] = alt.iloc[300:] * np.random.default_rng(1).uniform(0.3, 3.0, 100)  # gelecek bozulur
    assert robust.regime(alt).iloc[:301].equals(lab.iloc[:301]) and not robust.regime(alt).iloc[301:].equals(lab.iloc[301:])  # etiket[d] <= d-1 verisi: 300'e kadar değişmez


def test_regime_breakdown():
    idx = pd.date_range("2024-01-01", periods=6, freq="1D", tz="UTC")
    lab = pd.Series(["bull", "bull", "bear", "range", "bear", np.nan], index=idx, dtype=object)
    out = robust.by_regime(pd.Series([0.01, 0.03, -0.02, 0.0, -0.04, 0.5], index=idx), lab)
    assert out["bull"] == dict(n=2, total=A(0.04), mean=A(0.02)) and out["bear"]["total"] == A(-0.06) and out["range"]["n"] == 1  # etiketsiz gün (0.5) sayılmaz


def test_neighbors_grid_and_dedup_hand_values():
    g = robust.neighbors(dict(entry=55, exit=20))  # entry {44, 50 (49.5), 55, 61 (60.5), 66}, exit {16, 18, 20, 22, 24}: 5×5 - 1
    assert len(g) == 24 and {x["entry"] for x in g} == {44, 50, 55, 61, 66} and {x["exit"] for x in g} == {16, 18, 20, 22, 24} and dict(entry=55, exit=20) not in g
    assert robust.neighbors(dict(w=5)) == [dict(w=4), dict(w=6)]  # 4.5 -> 5 (kendisi), 5.5 -> 6, 4, 6: tekrarlar atılır


def test_start_shift_windows_and_decision_rule():
    assert robust.shift_windows("2023-03-01", "2026-04-01") == [("2023-03-01", "2026-04-01"), ("2023-04-01", "2026-04-01"), ("2023-05-01", "2026-04-01"), ("2023-06-01", "2026-04-01")]
    ok = {f"K{i}": True for i in range(1, 10)}
    assert robust.decision(ok) == "ADAY" and robust.decision({**ok, "K5": False}) == "ZAYIF" and robust.decision({**ok, "K1": False, "K5": False}) == "NO_EDGE" and robust.decision({**ok, "K2": False}) == "NO_EDGE"


def test_buy_hold_benchmark_and_warmup_exclusion():
    kl = bars([100, 100, 110, 110])  # b0 kararı -> b1 açılışı 100'den 10 adet; son kapanış 110: +100 brüt; fee 0.0005·1000 = 0.5, çıkış 0.0005·1100 = 0.55
    res, pnl = robust.buy_hold({"A": dict(kl=kl)}, Spec(tick="0.01", step="0.001", capital=10000.0, liq=False, fee_rt_bps=10.0), 1000.0, ("2024-01-01", "2024-01-02"))
    assert res["summary"]["net_pnl"] == A(98.95) and pnl.sum() == A(98.95)
    r = stats.sharpe_series(pd.Series([0.0, 0.0, 0.0, 1.0, 2.0]), 10.0, warmup_days=3)  # ısınma günleri dışlanır
    assert list(r) == [0.1, 0.2]


def test_path_stats_and_trade_mc_hand_values():
    # [3,-1,-2,2]: equity 3,2,0,2; tepe 3 -> DD 3; en uzun zarar serisi 2 (-1,-2); en kötü ardışık zarar toplamı 3
    dd, streak, worst = stats.path_stats([[3, -1, -2, 2], [-1, 1, 0, 0], [1, 1, 1, 1]])
    assert list(dd) == [3, 1, 0] and list(streak) == [2, 1, 0] and list(worst) == [3, 1, 0]
    # [1,-1]'in iki sırası da DD = 1 (1->0 ya da 0->-1); permütasyonlar toplamı korur
    paths = stats.trade_mc([1.0, -1.0], B=50, seed=1)
    assert paths.shape == (50, 2) and (paths.sum(1) == 0).all() and (stats.path_stats(paths)[0] == 1).all()
    assert (stats.trade_mc([1.0, 2.0, -3.0, 4.0], 20, 7) == stats.trade_mc([1.0, 2.0, -3.0, 4.0], 20, 7)).all()
    # kill: yol A [1,-2,5]: eq 1,-1,4; DD 0,2,... eşik 1,5 -> 2. adımda DD 2 > 1,5 tetik, final = -1; yol B [1,1,1]: tetik yok, final 3
    k = stats.kill_stats([[1, -2, 5], [1, 1, 1]], 1.5)
    assert k["p_trip"] == 0.5 and k["mean_final"] == A((-1 + 3) / 2) and k["mean_final_nokill"] == A((4 + 3) / 2)


def test_cscv_pbo_hand_values():
    # A = [1,1,-1,-1], B = [.5]*4, S=4 blok (1 gözlem/blok), metrik ortalama; 6 bölme:
    # (0,1): IS-en-iyi A, OOS (2,3): A=-1 < B=.5 -> sıra 1, ω=1/3, λ=-ln2; (2,3): IS-en-iyi B, OOS (0,1): A=1 > .5 -> B sırası 1, λ=-ln2;
    # diğer dört bölmede IS A=0 < B=.5 -> B; OOS'ta A=0 < B -> B sırası 2, ω=2/3, λ=+ln2. PBO = 2/6; IS-en-iyinin OOS ort. < 0 yalnız (0,1) -> 1/6
    R = np.column_stack([[1, 1, -1, -1], [0.5] * 4]).astype(float)
    out = stats.cscv(R, S=4, metric="mean")
    assert out["n_splits"] == 6 and out["pbo"] == A(2 / 6) and out["loss"] == A(1 / 6)
    assert sorted(np.round(out["lam"], 6)) == sorted(np.round([-np.log(2)] * 2 + [np.log(2)] * 4, 6)) and out["lam_median"] == A(np.log(2))
    # eşitlik: iki aynı sütun -> ortalama sıra 1,5 -> ω = 0,5 -> λ = 0 -> PBO = 1
    assert stats.cscv(np.ones((8, 2)), S=4, metric="mean")["pbo"] == 1.0


def test_nw_lrv_and_spa_hand_values():
    d = np.array([[1.0], [-1.0], [1.0], [3.0]])  # ort 1, sapmalar 0,-2,0,2 -> ddof=0 varyans = 8/4 = 2
    assert stats.nw_lrv(d, 0)[0] == A(2.0)
    # lag 1: γ0 = 2, γ1 = (u1u0 + u2u1 + u3u2)/4 = (0 + 0 + 0)/4 = 0 -> 2
    assert stats.nw_lrv(d, 1)[0] == A(2.0)
    r = stats.spa(d, B=200, seed=0, lag=0)
    assert r["stat"] == A(np.sqrt(4) * 1 / np.sqrt(2)) and r["best"] == 0 and r["K"] == 1 and r["n"] == 4  # T = √4·1/√2 = √2
    # her bootstrap yolunda g_l <= g_c <= g_u -> p_lower <= p_consistent <= p_upper; sabit tohum -> aynı sonuç
    rng = np.random.default_rng(3)
    z = rng.normal(0, 1, (300, 6))
    a, b = stats.spa(z, B=400, seed=1), stats.spa(z, B=400, seed=1)
    assert all(a[k] == b[k] for k in ("stat", "p_lower", "p_consistent", "p_upper"))
    assert a["p_lower"] <= a["p_consistent"] <= a["p_upper"] and a["p_consistent"] > 0.05  # sinyalsiz gürültü: reddedilmez
    z[:, 2] += 0.5  # t ≈ √300·0.5 = 8,7: güçlü üstünlük -> p ≈ 0
    s = stats.spa(z, B=400, seed=1)
    assert s["best"] == 2 and s["p_consistent"] < 0.01 and s["p_upper"] < 0.01
    assert stats.spa(np.zeros((50, 3)), B=100)["stat"] == 0.0 and stats.spa(np.zeros((50, 3)), B=100)["p_upper"] == 1.0  # sabit sütunlar: t = 0
