"""Risk motoru (ARCHITECTURE): volatilite hedefleme + sert tavanlar + yeniden-dengeleme bandı + kill switch. Saf fonksiyonlar; sinyal yalnızca yön verir.
Parametreler G2 sonuçlarından ÖNCE ayarlanmaz (ARCHITECTURE); varsayılanlar kitap-bağımsız muhafazakâr başlangıç değerleridir, sonuca göre oynanmaz."""
import numpy as np
import pandas as pd

from kepler import report


def realized_vol(kl: pd.DataFrame, days: int = 30) -> pd.Series:
    """Nedensel yıllık oynaklık, saatlik indekste: günlük log-getiri std (son `days` gün) x sqrt(365); bugünün değeri yalnızca TAMAMLANMIŞ günlerden (shift(1))."""
    v = (np.log(kl.close.resample("1D").last()).diff().rolling(days).std() * np.sqrt(365)).shift(1)
    return pd.Series(v.reindex(kl.index.normalize()).to_numpy(), index=kl.index)


def vol_target(kl: pd.DataFrame, unit: pd.Series, capital: float, target_vol: float = 0.20, max_lev: float = 3.0, band: float = 0.25, days: int = 30) -> pd.Series:
    """hedef notional = yön x capital x min(max_lev, hedef_vol / gerçekleşen_vol). Band: önceki notional'dan göreli sapma < band ise yeniden boyutlama yok (fee)."""
    lev = (target_vol / realized_vol(kl, days)).clip(upper=max_lev)
    want = (unit.ffill() * capital * lev).where(unit.ffill().notna() & lev.notna())
    out, last = [], 0.0
    for w in want.to_numpy():
        if np.isnan(w):
            out.append(np.nan)
            continue
        if w == 0 or last == 0 or np.sign(w) != np.sign(last) or abs(w - last) / abs(last) > band:
            last = w
        out.append(last)
    return pd.Series(out, index=unit.index)


def kill_switch(target: pd.Series, equity: pd.Series, max_dd: float) -> tuple[pd.Series, pd.Timestamp | None]:
    """Equity tepe noktasından max_dd düşünce hedef o andan itibaren 0 (tüm pozisyonlar kapanır, insan onayına kadar durur). (yeni hedef, tetik zamanı)."""
    dd = 1 - equity / equity.cummax()
    hit = dd.index[dd > max_dd]
    if not len(hit):
        return target, None
    out = target.copy()
    out.loc[hit[0]:] = 0.0
    return out, hit[0]


def equity_curve(kl, mark, funding, res, spec) -> pd.Series:
    return spec.capital + report.hourly_pnl(kl, mark, funding, res["fills"], spec).cumsum()
