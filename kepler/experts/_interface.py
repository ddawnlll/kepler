"""Sürekli tahmin uzmanı sözleşmesi (`forecast` türü). Aday yaşam döngüsü türü (Zone Fade) ayrı kalır.

Uzman yalnızca TAHMİN verir: [gün x sembol] DataFrame, değerler [-1, 1], aktif olmayan hücre NaN. Büyüklük, kaldıraç ve tavanlar uzmanda değil risk katmanındadır
(ARCHITECTURE; tests/test_architecture.py bunu import kurallarıyla zorlar). Girdiler yalnızca `d` gününe kadar (dahil) bilinen veridir: nedensellik uzmanın değil arayüzün sorumluluğudur,
`audit.check_causal_book` ve poisoning testi ensemble'ı uçtan uca sınar."""
from typing import Protocol

import pandas as pd


class ForecastExpert(Protocol):
    def __call__(self, close: pd.DataFrame, st: dict, p) -> pd.DataFrame:
        """close: günlük kapanış paneli; st: `market_state.market_state` çıktısı; p: ensemble Params."""


def par(p, default: dict) -> dict:
    """Uzman parametreleri: ön kayıtlı sabit varsayılan + K5 komşusu için `p.xp` (çift listesi) geçersiz kılması."""
    return {**default, **dict(getattr(p, "xp", ()))}


def scale(default: dict, s: float) -> tuple:
    """K5 komşusu: tüm parametreler x s (tamsayılar yuvarlanır), `Params.xp` biçiminde."""
    return tuple((k, max(1, int(round(v * s))) if isinstance(v, int) else v * s) for k, v in default.items())


def xrank(x: pd.DataFrame, act: pd.DataFrame) -> pd.DataFrame:
    """Aktif semboller arasında kesitsel sıra [-1, 1] (en büyük +1; ortalama sıra); n < 4 ise 0 (xs_momentum ile aynı formül)."""
    x = x.where(act)
    n = x.notna().sum(axis=1)
    q = 2 * (x.rank(axis=1, method="average") - 1).div((n - 1).where(n >= 4), axis=0) - 1
    return q.where(x.notna()).fillna(0.0).where(act)
