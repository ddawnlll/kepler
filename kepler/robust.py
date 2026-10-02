"""Sağlamlık araçları (BACKTEST.md §10, §11): parametre komşuluğu, başlangıç kaydırma, nedensel rejim etiketi, al-tut benchmark, rotasyon null'ı için sinyal kaydırma, kart karar kuralı."""
import numpy as np
import pandas as pd

from kepler import referee, report


def neighbors(params: dict[str, int], pcts=(0.1, 0.2)) -> list[dict]:
    """Her parametre için {-p2, -p1, 0, +p1, +p2} kaymaları (yarım yukarı yuvarlanmış tamsayı, tekrarlar atılır); tam kartezyen ızgara, seçilenin kendisi hariç. Sıralı."""
    vals = {k: sorted({max(1, int(np.floor(v * (1 + s * p) + 0.5))) for p in pcts for s in (-1, 1)} | {v}) for k, v in params.items()}
    grid = [{}]
    for k, vs in vals.items():
        grid = [{**g, k: x} for g in grid for x in vs]
    return [g for g in grid if g != params]


def shift_windows(start, end, months=(0, 1, 2, 3)) -> list[tuple]:
    """Başlangıcı `months` ay kaydırılmış pencereler [(start + m ay, end)]; K6."""
    s = pd.Timestamp(start)
    return [(str((s + pd.DateOffset(months=m)).date()), str(pd.Timestamp(end).date())) for m in months]


def regime(btc_close: pd.Series) -> pd.Series:
    """Nedensel rejim etiketi (BTC günlük kapanış, UTC günü indeksli). Gün d etiketi yalnızca <= d-1 kapanışlarına bakar: 200 günlük EMA (min_periods=200) ve 30 günlük eğimi
    (EMA/EMA[-30] − 1): kapanış > EMA ve eğim > 0 → 'bull'; kapanış < EMA ve eğim < 0 → 'bear'; diğer → 'range'. EMA ve eğim ısınana kadar (230 gün) NaN."""
    ema = btc_close.ewm(span=200, min_periods=200, adjust=False).mean()
    slope = ema / ema.shift(30) - 1
    lab = pd.Series(np.where((btc_close > ema) & (slope > 0), "bull", np.where((btc_close < ema) & (slope < 0), "bear", "range")), index=btc_close.index, dtype=object)
    return lab.where(slope.notna()).shift(1)


def by_regime(r_daily: pd.Series, labels: pd.Series) -> dict[str, dict]:
    """Günlük getiri serisini rejime göre böler: {rejim: dict(n, toplam, ort)}; etiketsiz günler atılır."""
    lab = labels.reindex(r_daily.index)
    return {k: dict(n=int((lab == k).sum()), total=float(r_daily[lab == k].sum()), mean=float(r_daily[lab == k].mean())) for k in ("bull", "bear", "range")}


def buy_hold(data: dict[str, dict], spec: referee.Spec, notional: float, window: tuple) -> tuple[dict, pd.Series]:
    """Eşit notional al-tut (aynı hakem: fee, slip, funding, çıkış maliyeti): pencerenin ilk barında alınır, sonunda son kapanıştan değerlenir. (hakem sonucu, saatlik net PnL)."""
    lo, hi = (pd.Timestamp(x, tz="UTC") for x in window)
    win = {}
    for s, d in data.items():
        kl = d["kl"][(d["kl"].index >= lo) & (d["kl"].index < hi)]
        tgt = pd.Series(np.nan, index=kl.index)
        tgt.iloc[0] = notional
        mk = d.get("mark")
        win[s] = dict(d, kl=kl, target=tgt, mark=None if mk is None else mk[(mk.index >= lo) & (mk.index < hi)])
    res = referee.run_portfolio(win, spec)
    return res, report.book_pnl(win, res, spec)


def rotate_signal(sig, u: float):
    """Rotasyon null'ı için sinyali günlük karar dizisi üzerinde dairesel kaydırır: k = ⌊u·gün sayısı⌋ gün. Kararlar 23:00 barlarında kalır; işlem sayısı, tutma süreleri, yön oranı korunur."""
    def rot(kl):
        s = sig(kl)
        at = s.index.hour == 23
        out = pd.Series(np.nan, index=s.index)
        v = s[at].ffill().fillna(0.0).to_numpy()
        out[at] = np.roll(v, int(u * len(v)))
        return out
    return rot


def decision(passed: dict[str, bool]) -> str:
    """Karar kuralı (§11): K1–K9 hepsi geçerse ADAY; K1 ya da K2 kalırsa NO_EDGE; K3–K9'dan biri kalırsa ZAYIF. passed: {'K1': bool, ...}."""
    if not (passed["K1"] and passed["K2"]):
        return "NO_EDGE"
    return "ADAY" if all(passed[f"K{i}"] for i in range(3, 10)) else "ZAYIF"
