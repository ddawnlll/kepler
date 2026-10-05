"""Kepler Ensemble: TEK altyapı. piyasa durumu -> uzmanlar -> aday -> risk motoru -> hakem. Uzmanlar (`REG`) takılabilir üyelerdir; bileşim `Params.names` (üyeler) + `Params.weights` (ağırlıklar).
EV1 ayrı bir sistem değil, bu altyapının VARSAYILAN bileşimidir: names = (trend, xs_momentum, carry), weights = (0,6; 0,2; 0,2). Başka bir uzman eklemek = names/weights'e eklemek;
tek uzman testi = tek üyeli bileşim. Kurallar ve parametreler reports/ensemble_protocol.md'de koddan önce sabitlendi (EV1) ve reports/edge_experts_protocol.md'de (diğer üyeler).
Bu dosya yalnızca KOMPOZİSYON: Params, aday birleştirme (combine), K1 rotasyonu, kitap sözleşmesi. Parçalar: kepler/market_state.py, kepler/experts/*.py, kepler/portfolio.py.

Kitap sözleşmesi (BACKTEST §4): book({sym: kl}) -> {sym: DataFrame[target, stop]}; kl saatlik OHLCV + `fund_hr` (signals.with_funding). Karar her UTC gününün son
mevcut barına yazılır (gün kapanışı), diğer barlar NaN (tut); stop yok (NaN). Tüm girdiler <= gün kapanışı (nedensel)."""
import math
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from kepler.experts import bollinger, carry, fundcrowd, lowvol, nearhigh, orderflow, trend, volrev, xs_momentum
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
    names: tuple = ("trend", "xs_momentum", "carry")  # bileşim üyeleri (REG anahtarları), weights ile aynı sırada; varsayılan = EV1
    weights: tuple = (0.6, 0.2, 0.2)  # varsayılan EV1: E1 trend, E2 kesitsel momentum, E3 carry; negatif ağırlık = ters yön
    tau: float = 0.20  # yıllık hedef portföy oynaklığı
    vol_floor: float = 0.25
    buffer: float = 0.2  # tam tahmin pozisyonunun oranı
    sym_cap: float = 1.0  # |n_i| <= sym_cap x sermaye
    gross_cap: float = 3.0  # sum |n_i| <= gross_cap x sermaye
    min_days: int = 90  # aktiflik: en az bu kadar günlük kapanış
    warm: int = 30  # panel geçmişi bu kadar günden azsa pozisyon yok
    risk: bool = True  # False: `no_risk` ablasyonu (n = K F / M)
    expert: str = ""  # kısayol: dolu ise bileşim = (expert,) ağırlık 1 (tek uzman testi); names/weights'in yerine geçer
    xp: tuple = ()  # uzman parametrelerini geçersiz kılma (K5 komşusu), (ad, değer) çiftleri
    flip: bool = False  # kısayol: expert ile birlikte ağırlık -1 (yön testi, bilgi)

    def scaled(self, s: float) -> "Params":
        """K5 komşusu: tüm geri bakışlar x s (tamsayıya yuvarlanır)."""
        r = lambda x: int(round(x * s))  # noqa: E731
        return replace(self, trend_L=tuple(r(x) for x in self.trend_L), xs_L=tuple(r(x) for x in self.xs_L), carry_days=r(self.carry_days), vol_days=r(self.vol_days), corr_days=r(self.corr_days))


REG = dict(trend=trend, xs_momentum=xs_momentum, carry=carry, bollinger=bollinger, lowvol=lowvol, nearhigh=nearhigh, fundcrowd=fundcrowd, volrev=volrev, orderflow=orderflow)


EV1_NAMES = ("trend", "xs_momentum", "carry")
NEW_NAMES = ("bollinger", "lowvol", "nearhigh", "fundcrowd", "volrev", "orderflow")
PRESETS = {  # adlandırılmış bileşimler (Params(**PRESETS[ad])); ağırlıklar sonuca bakmadan sabitlendi, varsayılan Params() hâlâ EV1
    "ev1": dict(names=EV1_NAMES, weights=(0.6, 0.2, 0.2)),
    "all9_equal": dict(names=EV1_NAMES + NEW_NAMES, weights=(1 / 9,) * 9),  # 9 uzman eşit ağırlık
    "ev1_plus_new": dict(names=EV1_NAMES + NEW_NAMES, weights=(0.6, 0.2, 0.2) + (0.1,) * 6),  # EV1 aynen + her yeni uzmana 0,1
}


def composition(p: Params) -> tuple[tuple, tuple]:
    """(üye adları, ağırlıklar): `expert` kısayolu doluysa tek üye, değilse names/weights (varsayılan = EV1)."""
    return ((p.expert,), (-1.0 if p.flip else 1.0,)) if p.expert else (tuple(p.names), tuple(p.weights))


def experts(close: pd.DataFrame, st: dict, p: Params) -> tuple[pd.DataFrame, ...]:
    """Bileşimdeki her üyenin tahmini (varsayılan EV1: trend, kesitsel momentum, carry), her biri [-1, 1]; aktif olmayan hücre NaN. Uzmanlar `kepler/experts/` altında, kayıt `REG`."""
    return tuple(REG[n].forecast(close, st, p) for n in composition(p)[0])


def combine(es, st: dict, p: Params) -> pd.DataFrame:
    """F = clip(F_raw · 0,5 / m_d, -1, 1); m_d = d'ye kadarki aktif hücrelerde |F_raw| ortalaması (genişleyen); panel geçmişi < warm gün ise 0."""
    act = st["active"]
    raw = sum(w * e.fillna(0.0) for w, e in zip(composition(p)[1], es)).where(act)
    ab = raw.abs()
    tot = pd.Series([math.fsum(r[~np.isnan(r)]) for r in ab.to_numpy()], index=ab.index) if composition(p)[0] != EV1_NAMES else ab.sum(axis=1)  # EV1 dışı bileşimler: sütun sayısından bağımsız tam toplam (audit kesik panelde 1 ulp farkını sızıntı sanmasın); EV1 sayısal yolu aynen dondurulmuş
    m = tot.cumsum() / act.sum(axis=1).cumsum()
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
