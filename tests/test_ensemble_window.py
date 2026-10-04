"""EV1 sönme testi (reports/ensemble_decay_protocol.md): `rotate(..., rot_from)` yalnızca alt dönem satırlarını kaydırır. Beklenen değerler elle."""
import numpy as np
import pandas as pd
import pytest
from test_ensemble import P_SMALL, synth

from kepler import ensemble as en

DAYS = pd.date_range("2024-01-01", periods=8, freq="1D", tz="UTC")


def test_rotate_from_shifts_only_the_tail_with_common_k():
    f = pd.DataFrame({"A": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0], "B": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]}, index=DAYS)
    act = f.notna()
    act.loc[DAYS[6], "B"] = False
    r = en.rotate(f, act, 0.7, rot_from=DAYS[4])  # kuyruk 4 gün: k = ⌊0,7·4⌋ = 2 (⌊2,8⌋, 3 değil); roll([5,6,7,8], 2) = [7,8,5,6]
    assert r["A"].tolist() == [1.0, 2.0, 3.0, 4.0, 7.0, 8.0, 5.0, 6.0]  # öncesi aynen
    assert r["B"].iloc[:6].tolist() == [10.0, 20.0, 30.0, 40.0, 70.0, 80.0]  # aynı k, tüm semboller
    assert np.isnan(r["B"].iloc[6]) and r["B"].iloc[7] == 60.0  # B'nin 7. günü aktif değil -> maske


def test_rotate_without_rot_from_is_full_series_roll():
    f = pd.DataFrame({"A": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]}, index=DAYS)
    act = f.notna()
    assert en.rotate(f, act, 0.3).equals(en.rotate(f, act, 0.3, rot_from=DAYS[0]))  # k = ⌊0,3·8⌋ = 2
    assert en.rotate(f, act, 0.3)["A"].tolist() == [7.0, 8.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


def test_forecasts_rot_from_keeps_prefix_and_rolls_tail():
    kls = synth()  # 160 gün
    f, st = en.forecasts(kls, P_SMALL)
    lo = pd.Timestamp("2024-01-01", tz="UTC") + pd.Timedelta(days=100)
    fr, _ = en.forecasts(kls, P_SMALL, u=0.3, rot_from=lo)
    pd.testing.assert_frame_equal(fr.iloc[:100], f.iloc[:100])  # öncesi aynen
    assert (fr.notna() == st["active"]).all().all()
    k = int(0.3 * 60)  # kuyruk 60 gün: k = 18
    for s in ("AAA", "BBB"):
        assert fr[s].iloc[100 + k + 10] == pytest.approx(f[s].fillna(0.0).iloc[100 + 10])


def test_make_book_rot_from_wired_into_targets():
    kls = synth()
    lo = pd.Timestamp("2024-01-01", tz="UTC") + pd.Timedelta(days=100)
    base = en.make_book(10_000.0, P_SMALL)(kls)
    rot = en.make_book(10_000.0, P_SMALL, u=0.3, rot_from=lo)(kls)
    for s in kls:
        assert base[s].target[base[s].index < lo].equals(rot[s].target[rot[s].index < lo])  # öncesi aynı hedef
    assert not all(base[s].target.equals(rot[s].target) for s in kls)  # sonrası farklı
