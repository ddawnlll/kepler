"""E3b kesitsel carry (reports/preregistration/carry_rebuild.md): F = xrank(-phi): aktif semboller arasında 7 günlük funding'in kesitsel sırası, en düşük funding +1 (dolar-nötr; sabit taban ve σ ölçeği yok).
Piyasa geneli funding düzeyi ortak faktördür (yönlü kullanımı piyasa zamanlaması); göreli funding sembolün long kalabalığıdır. `ensemble.REG`'e eklenmedi (ayrı karar)."""
import pandas as pd

from kepler.experts._interface import xrank


def forecast(close: pd.DataFrame, st: dict, p) -> pd.DataFrame:
    return xrank(-st["phi"], st["active"])
