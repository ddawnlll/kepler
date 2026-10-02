"""Denklik (BACKTEST §6.5, madde 9) için sabit fixture: rastgele yürüyüş + funding + mark, 10x'te likidasyon dahil. Tek sembollü yeni motorun çıktısı,
çok sembollü yeniden yazımdan ÖNCEKİ hakemden (git 22901ab) alınan sabit sayılarla eşleşir."""
import numpy as np
import pandas as pd


def fixture(seed=7, n=900):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.012, n)))
    o = np.r_[c[0], c[:-1]] * (1 + rng.normal(0, 0.002, n))
    h, l = np.maximum(o, c) * (1 + rng.uniform(0, 0.01, n)), np.minimum(o, c) * (1 - rng.uniform(0, 0.01, n))
    kl = pd.DataFrame(dict(open=o, high=h, low=l, close=c, volume=1000.0), index=idx)
    mark = kl.assign(close=c * (1 + rng.normal(0, 1e-4, n)), high=h * 1.0005, low=l * 0.9995)
    fi = pd.date_range("2024-01-01 08:00", periods=n // 8, freq="8h", tz="UTC")
    funding = pd.DataFrame(dict(last_funding_rate=rng.normal(1e-4, 2e-4, len(fi)), funding_interval_hours=8), index=fi)
    tgt = pd.Series(np.nan, index=idx)
    for i in range(5, n - 1, 37):
        tgt.iloc[i] = float(rng.choice([-6000.0, -2500.0, 0.0, 2500.0, 6000.0]))
    return kl, tgt, funding, mark
