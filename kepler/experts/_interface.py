"""Sürekli tahmin uzmanı sözleşmesi (`forecast` türü; docs/factory.md WP1). Aday yaşam döngüsü türü (Zone Fade) ayrı kalır, onu taşımak WP1'in devamıdır.

Uzman yalnızca TAHMİN verir: [gün x sembol] DataFrame, değerler [-1, 1], aktif olmayan hücre NaN. Büyüklük, kaldıraç ve tavanlar uzmanda değil risk katmanındadır
(ARCHITECTURE; tests/test_architecture.py bunu import kurallarıyla zorlar). Girdiler yalnızca `d` gününe kadar (dahil) bilinen veridir: nedensellik uzmanın değil arayüzün sorumluluğudur,
`audit.check_causal_book` ve poisoning testi ensemble'ı uçtan uca sınar."""
from typing import Protocol

import pandas as pd


class ForecastExpert(Protocol):
    def __call__(self, close: pd.DataFrame, st: dict, p) -> pd.DataFrame:
        """close: günlük kapanış paneli; st: `market_state.market_state` çıktısı; p: ensemble Params."""
