"""Kepler Ensemble v1 (EV1), ana sistem: piyasa durumu -> uzmanlar -> aday -> risk motoru. Kurallar ve parametreler reports/ensemble_protocol.md'de koddan önce sabitlendi.
Bu dosya yalnızca KOMPOZİSYON: Params, aday birleştirme (combine), K1 rotasyonu, kitap sözleşmesi. Parçalar: kepler/market_state.py, kepler/experts/{trend,xs_momentum,carry}.py, kepler/portfolio.py.

Kitap sözleşmesi (BACKTEST §4): book({sym: kl}) -> {sym: DataFrame[target, stop]}; kl saatlik OHLCV + `fund_hr` (signals.with_funding). Karar her UTC gününün son
mevcut barına yazılır (gün kapanışı), diğer barlar NaN (tut); stop yok (NaN). Tüm girdiler <= gün kapanışı (nedensel)."""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from kepler.experts import carry, trend, xs_momentum
from kepler.experts.carry import BASE_FUNDING  # noqa: F401  (geriye uyum: en.BASE_FUNDING)
from kepler.market_state import market_state, panel  # noqa: F401  (geriye uyum: en.panel, en.market_state)
from kepler.portfolio import size  # noqa: F401  (geriye uyum: en.size)


@dataclass(frozen=True)
class Params:
    trend_L: tuple = (7, 14, 28, 56)
    xs_L: tuple = (14, 28, 56)
    carry_days: int = 7
    vol_days: int = 30
    corr_days: int = 90
    weights: tuple = (0.6, 0.2, 0.2)  # E1 trend, E2 kesitsel momentum, E3 carry
    tau: float = 0.20  # yıllık hedef portföy oynaklığı
    vol_floor: float = 0.25
    buffer: float = 0.2  # tam tahmin pozisyonunun oranı
    sym_cap: float = 1.0  # |n_i| <= sym_cap x sermaye
    gross_cap: float = 3.0  # sum |n_i| <= gross_cap x sermaye
    min_days: int = 90  # aktiflik: en az bu kadar günlük kapanış
    warm: int = 30  # panel geçmişi bu kadar günden azsa pozisyon yok
    risk: bool = True  # False: `no_risk` ablasyonu (n = K F / M)

    def scaled(self, s: float) -> "Params":
        """K5 komşusu: tüm geri bakışlar x s (tamsayıya yuvarlanır)."""
        r = lambda x: int(round(x * s))  # noqa: E731
        return replace(self, trend_L=tuple(r(x) for x in self.trend_L), xs_L=tuple(r(x) for x in self.xs_L), carry_days=r(self.carry_days), vol_days=r(self.vol_days), corr_days=r(self.corr_days))


def experts(close: pd.DataFrame, st: dict, p: Params) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(E1 trend, E2 kesitsel momentum, E3 carry), her biri [-1, 1]; aktif olmayan hücre NaN. Uzmanlar `kepler/experts/` altında."""
    return trend.forecast(close, st, p), xs_momentum.forecast(close, st, p), carry.forecast(close, st, p)


def combine(es, st: dict, p: Params) -> pd.DataFrame:
    """F = clip(F_raw · 0,5 / m_d, -1, 1); m_d = d'ye kadarki aktif hücrelerde |F_raw| ortalaması (genişleyen); panel geçmişi < warm gün ise 0."""
    act = st["active"]
    raw = sum(w * e.fillna(0.0) for w, e in zip(p.weights, es)).where(act)
    m = raw.abs().sum(axis=1).cumsum() / act.sum(axis=1).cumsum()
    warm = act.any(axis=1).cumsum() >= p.warm
    f = (raw.mul(0.5 / m.where(m > 0), axis=0)).clip(-1, 1)
    return f.where(warm, 0.0).where(act)


def rotate(f: pd.DataFrame, act: pd.DataFrame, u: float, rot_from: pd.Timestamp | None = None) -> pd.DataFrame:
    """K1 rotasyon null'u: her sembolün günlük F serisi (aktif olmayan gün 0) aynı k = floor(u · gün) ile dairesel kaydırılır, sonra aktif olmayan günler maskelenir.
    rot_from verilirse yalnızca o tarih ve sonrası satırlar (k bu kesitin gün sayısına göre) kaydırılır, öncesi aynen kalır (alt dönem null'u: reports/ensemble_decay_protocol.md)."""
    x, i = f.fillna(0.0).to_numpy().copy(), 0 if rot_from is None else int(f.index.searchsorted(rot_from))
    x[i:] = np.roll(x[i:], int(u * (len(f) - i)), axis=0)
    return pd.DataFrame(x, index=f.index, columns=f.columns).where(act)


def place(kl: pd.DataFrame, daily: pd.Series) -> pd.Series:
    """Günlük hedefi günün son mevcut saatlik barına yazar; diğer barlar NaN (tut). Son gün 23:00 barında bitmiyorsa (veri kesik) o gün karar yok (turtle._decision_bars)."""
    out = pd.Series(np.nan, index=kl.index)
    last = kl.index.to_series().groupby(kl.index.normalize()).max()
    last = last if last.iloc[-1].hour == 23 else last.iloc[:-1]
    out.loc[last.to_numpy()] = daily.reindex(last.index).fillna(0.0).to_numpy()
    return out


def forecasts(kls: dict[str, pd.DataFrame], p: Params, u: float | None = None, rot_from: pd.Timestamp | None = None) -> tuple[pd.DataFrame, dict]:
    close, _ = panel(kls)
    st = market_state(close, kls, p)
    f = combine(experts(close, st, p), st, p)
    return (rotate(f, st["active"], u, rot_from) if u is not None else f), st


def make_book(capital: float, p: Params = Params(), u: float | None = None, rot_from: pd.Timestamp | None = None):
    """Kitap fabrikası (evaluate.evaluate_book / run_book). u verilirse K1 rotasyon null'u (rot_from: yalnızca o tarihten sonrası kaydırılır)."""
    def book(kls):
        f, st = forecasts(kls, p, u, rot_from)
        n = size(f, st, capital, p)
        return {s: pd.DataFrame(dict(target=place(kl, n[s]), stop=np.nan), index=kl.index) for s, kl in kls.items()}
    return book
