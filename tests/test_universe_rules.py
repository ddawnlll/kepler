"""G2 öncesi, sinyalden bağımsız evren kuralları: emtia/stable çıkarma (sıralamadan önce), kline~mark ayrışma kesimi."""
import json

import numpy as np
import pandas as pd

from kepler import qc, tape, universe


def test_non_crypto_excluded_before_ranking_so_next_symbol_enters():
    rows = []
    for m, base in (("2021-12", 100.0), ("2022-01", 100.0)):
        for i, s in enumerate(["BTCUSDT", "XAUUSDT", "XAGUSDT", "PAXGUSDT", "USDCUSDT", "ETHUSDT", "SOLUSDT"]):
            rows.append((s, m, base * (10 - i), 30))
    vol = pd.DataFrame(rows, columns=["sym", "month", "quote_volume", "days"])
    uni = universe.build_universe(vol[vol.sym.map(universe.eligible)], top_n=3)
    jan = uni[uni.month == "2022-01"]
    assert list(jan.sym) == ["BTCUSDT", "ETHUSDT", "SOLUSDT"] and list(jan["rank"]) == [1, 2, 3]  # emtia/stable yerine sıradakiler girdi
    for s in ("XAUUSDT", "XAGUSDT", "PAXGUSDT", "USDCUSDT"):
        assert not universe.eligible(s)
    assert universe.eligible("BTCUSDT") and universe.eligible("1000SHIBUSDT")


def test_build_universe_window_is_parameterized():
    """pre2022 koşusu: ay aralığı parametre (start/end); ay M üyeleri M-1 hacminden (nedensel), aralık dışı ay yok."""
    vol = pd.DataFrame([(s, m, v, 30) for m in ("2019-08", "2019-09", "2019-10") for s, v in (("AUSDT", 3.0), ("BUSDT", 2.0), ("CUSDT", 1.0))], columns=["sym", "month", "quote_volume", "days"])
    uni = universe.build_universe(vol, top_n=2, start="2019-09", end="2019-10")
    assert sorted(uni.month.unique()) == ["2019-09", "2019-10"] and list(uni[uni.month == "2019-09"].sym) == ["AUSDT", "BUSDT"]


def frames(n=400, diverge_from=None, run=30):
    ts = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    c = np.full(n, 100.0)
    m = c.copy()
    if diverge_from is not None:
        m[diverge_from:diverge_from + run] = 80.0  # %25 sapma
    mk = lambda x: pd.DataFrame({"ts": ts, "close": x})  # noqa: E731
    return mk(c), mk(m), ts


def test_divergence_cutoff_needs_24_consecutive_bars():
    kl, mk, ts = frames(diverge_from=200, run=30)
    assert qc.divergence_cutoff(kl, mk) == ts[200]  # koşunun BAŞLANGICI
    kl, mk, _ = frames(diverge_from=200, run=23)
    assert qc.divergence_cutoff(kl, mk) is None  # 23 bar: geçici sapma (fitil/çöküş), kesim yok
    kl, mk, _ = frames()
    assert qc.divergence_cutoff(kl, mk) is None


def test_tape_load_clips_at_cutoff_and_membership_drops_symbol_after(tmp_path):
    from tests.test_tape_ledger import write_tape

    write_tape(tmp_path, n=96)  # 2024-01-01 .. 2024-01-04
    (tmp_path / "tape" / "usable.json").write_text(json.dumps({"TESTUSDT": "2024-01-02 00:00:00+00:00"}))
    t = tape.load(tmp_path, "TESTUSDT")
    assert t["klines"].index.max() < pd.Timestamp("2024-01-02", tz="UTC") and len(t["klines"]) == 24  # sonrası verilmez
    pd.DataFrame({"month": ["2023-12", "2024-01", "2024-02"], "rank": 1, "sym": "TESTUSDT", "prev_quote_volume": 1.0}).to_parquet(tmp_path / "tape" / "universe.parquet")
    assert list(tape.membership(tmp_path).month) == ["2023-12", "2024-01"]  # kesim ayı üye, sonrası düşer; yerine yenisi konmaz
