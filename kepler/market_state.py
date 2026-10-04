"""Piyasa durumu (EV1 girdileri): günlük kapanış paneli, oynaklık, aktiflik, funding. Saf ve nedensel; uzmanlar ve boyutlama bunu okur, kendileri hesaplamaz.
`p`: `ensemble.Params` benzeri (vol_days, vol_floor, min_days, carry_days alanları); burada import edilmez (katman: market_state < experts < ensemble)."""
import numpy as np
import pandas as pd


def panel(kls: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(günlük kapanış [gün x sembol], günün son barındaki 7 günlük ortalama funding yıllık [gün x sembol]); veri olmayan gün NaN."""
    close = pd.DataFrame({s: kl.close.resample("1D").last() for s, kl in kls.items()})
    fund = pd.DataFrame({s: (kl.fund_hr if "fund_hr" in kl else pd.Series(np.nan, index=kl.index)) for s, kl in kls.items()})
    return close.sort_index(), fund


def market_state(close: pd.DataFrame, kls: dict[str, pd.DataFrame], p) -> dict:
    """sigma (yıllık, tabanlı), ret (günlük log getiri), active (bool), phi (yıllık funding, carry_days ortalaması)."""
    ret = np.log(close).diff()
    sigma = (ret.rolling(p.vol_days, min_periods=max(2, int(p.vol_days * 2 / 3))).std() * np.sqrt(365)).clip(lower=p.vol_floor)
    active = (close.notna().cumsum() >= p.min_days) & close.notna() & sigma.notna()
    phi = pd.DataFrame({s: (kl.fund_hr.rolling(f"{24 * p.carry_days}h").mean() * 24 * 365).resample("1D").last() if "fund_hr" in kl else pd.Series(dtype=float)
                        for s, kl in kls.items()}).reindex(index=close.index, columns=close.columns)
    return dict(ret=ret, sigma=sigma, active=active, phi=phi)
