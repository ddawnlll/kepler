"""Kepler Ensemble v1 (EV1): piyasa durumu -> uzmanlar -> aday -> risk motoru. Kurallar ve parametreler reports/ensemble_protocol.md'de koddan önce sabitlendi.

Kitap sözleşmesi (BACKTEST §4): book({sym: kl}) -> {sym: DataFrame[target, stop]}; kl saatlik OHLCV + `fund_hr` (signals.with_funding). Karar her UTC gününün son
mevcut barına yazılır (gün kapanışı), diğer barlar NaN (tut); stop yok (NaN). Tüm girdiler <= gün kapanışı (nedensel)."""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

BASE_FUNDING = 0.0001 / 8 * 24 * 365  # 0,01%/8 saat taban faiz bileşeni, yıllık (0,1095)


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


def panel(kls: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(günlük kapanış [gün x sembol], günün son barındaki 7 günlük ortalama funding yıllık [gün x sembol]); veri olmayan gün NaN."""
    close = pd.DataFrame({s: kl.close.resample("1D").last() for s, kl in kls.items()})
    fund = pd.DataFrame({s: (kl.fund_hr if "fund_hr" in kl else pd.Series(np.nan, index=kl.index)) for s, kl in kls.items()})
    return close.sort_index(), fund


def market_state(close: pd.DataFrame, kls: dict[str, pd.DataFrame], p: Params) -> dict:
    """sigma (yıllık, tabanlı), ret (günlük log getiri), active (bool), phi (yıllık funding, carry_days ortalaması)."""
    ret = np.log(close).diff()
    sigma = (ret.rolling(p.vol_days, min_periods=max(2, int(p.vol_days * 2 / 3))).std() * np.sqrt(365)).clip(lower=p.vol_floor)
    active = (close.notna().cumsum() >= p.min_days) & close.notna() & sigma.notna()
    phi = pd.DataFrame({s: (kl.fund_hr.rolling(f"{24 * p.carry_days}h").mean() * 24 * 365).resample("1D").last() if "fund_hr" in kl else pd.Series(dtype=float)
                        for s, kl in kls.items()}).reindex(index=close.index, columns=close.columns)
    return dict(ret=ret, sigma=sigma, active=active, phi=phi)


def experts(close: pd.DataFrame, st: dict, p: Params) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(E1 trend, E2 kesitsel momentum, E3 carry), her biri [-1, 1]; aktif olmayan hücre NaN."""
    cf, act, sd = close.ffill(), st["active"], st["sigma"] / np.sqrt(365)
    e1 = sum((np.log(cf / cf.shift(L)) / (sd * np.sqrt(L)) / 2).clip(-1, 1) for L in p.trend_L) / len(p.trend_L)
    qs = []
    for L in p.xs_L:
        r = np.log(cf / cf.shift(L)).where(act)
        n = r.notna().sum(axis=1)
        q = 2 * (r.rank(axis=1, method="average") - 1).div((n - 1).where(n >= 4), axis=0) - 1
        qs.append(q.where(r.notna()).fillna(0.0))
    e2 = sum(qs) / len(qs)
    e3 = (2 * -(st["phi"] - BASE_FUNDING) / st["sigma"]).clip(-1, 1).fillna(0.0)
    return e1.where(act), e2.where(act), e3.where(act)


def combine(es, st: dict, p: Params) -> pd.DataFrame:
    """F = clip(F_raw · 0,5 / m_d, -1, 1); m_d = d'ye kadarki aktif hücrelerde |F_raw| ortalaması (genişleyen); panel geçmişi < warm gün ise 0."""
    act = st["active"]
    raw = sum(w * e.fillna(0.0) for w, e in zip(p.weights, es)).where(act)
    m = raw.abs().sum(axis=1).cumsum() / act.sum(axis=1).cumsum()
    warm = act.any(axis=1).cumsum() >= p.warm
    f = (raw.mul(0.5 / m.where(m > 0), axis=0)).clip(-1, 1)
    return f.where(warm, 0.0).where(act)


def rotate(f: pd.DataFrame, act: pd.DataFrame, u: float) -> pd.DataFrame:
    """K1 rotasyon null'u: her sembolün günlük F serisi (aktif olmayan gün 0) aynı k = floor(u · gün) ile dairesel kaydırılır, sonra aktif olmayan günler maskelenir."""
    k = int(u * len(f))
    return pd.DataFrame(np.roll(f.fillna(0.0).to_numpy(), k, axis=0), index=f.index, columns=f.columns).where(act)


def size(f: pd.DataFrame, st: dict, capital: float, p: Params) -> pd.DataFrame:
    """Risk motoru: günlük hedef notional [gün x sembol] (aktif olmayan = 0). Yol bağımlı (tampon), gün gün."""
    syms, ret, sig, act = list(f.columns), st["ret"].to_numpy(), st["sigma"].to_numpy(), st["active"].to_numpy()
    fv, out, prev = f.to_numpy(), np.zeros(f.shape), np.zeros(len(syms))
    for d in range(len(f)):
        a = act[d] & ~np.isnan(fv[d])
        tgt, u = np.zeros(len(syms)), np.full(len(syms), np.inf)
        idx = np.flatnonzero(a)
        if len(idx):
            m, s, fa = len(idx), sig[d, idx], fv[d, idx]
            if p.risk:
                lo = max(0, d - p.corr_days + 1)
                rho = pd.DataFrame(ret[lo:d + 1, idx]).corr(min_periods=30).fillna(1.0).to_numpy().copy()  # örtüşmesi yetersiz çift: korelasyon 1 (muhafazakâr)
                np.fill_diagonal(rho, 1.0)
                w = np.full(m, 1.0 / m)
                idm = min(2.5, 1.0 / np.sqrt(w @ np.clip(rho, 0, None) @ w))
                unit = capital * p.tau * w * idm / s
                n = unit * fa
                v = np.sqrt(max(n @ (np.outer(s, s) * rho) @ n, 0.0)) / capital
                if v > p.tau:
                    n *= p.tau / v
            else:
                unit = np.full(m, capital / m)
                n = unit * fa
            n = np.clip(n, -p.sym_cap * capital, p.sym_cap * capital)
            g = np.abs(n).sum()
            if g > p.gross_cap * capital:
                n *= p.gross_cap * capital / g
            tgt[idx], u[idx] = n, unit
        move = np.abs(tgt - prev) > np.where(np.isinf(u), np.inf, p.buffer * np.where(np.isinf(u), 0.0, u))
        prev = np.where(~a, 0.0, np.where(move, tgt, prev))
        out[d] = prev
    return pd.DataFrame(out, index=f.index, columns=syms)


def place(kl: pd.DataFrame, daily: pd.Series) -> pd.Series:
    """Günlük hedefi günün son mevcut saatlik barına yazar; diğer barlar NaN (tut). Son gün 23:00 barında bitmiyorsa (veri kesik) o gün karar yok (turtle._decision_bars)."""
    out = pd.Series(np.nan, index=kl.index)
    last = kl.index.to_series().groupby(kl.index.normalize()).max()
    last = last if last.iloc[-1].hour == 23 else last.iloc[:-1]
    out.loc[last.to_numpy()] = daily.reindex(last.index).fillna(0.0).to_numpy()
    return out


def forecasts(kls: dict[str, pd.DataFrame], p: Params, u: float | None = None) -> tuple[pd.DataFrame, dict]:
    close, _ = panel(kls)
    st = market_state(close, kls, p)
    f = combine(experts(close, st, p), st, p)
    return (rotate(f, st["active"], u) if u is not None else f), st


def make_book(capital: float, p: Params = Params(), u: float | None = None):
    """Kitap fabrikası (evaluate.evaluate_book / run_book). u verilirse K1 rotasyon null'u."""
    def book(kls):
        f, st = forecasts(kls, p, u)
        n = size(f, st, capital, p)
        return {s: pd.DataFrame(dict(target=place(kl, n[s]), stop=np.nan), index=kl.index) for s, kl in kls.items()}
    return book
