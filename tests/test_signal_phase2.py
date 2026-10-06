"""Faz 2 histerezis durum makinesi (reports/preregistration/neutral_zone_hysteresis.md): elle hesaplı geçişler. nautilus gerektirir (audit_fix zinciri); yoksa atlanır."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("nautilus_trader")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import signal_phase2 as p2  # noqa: E402


def states(vals, th_out=0.10, th_in=0.25):
    f = pd.DataFrame({"A": vals}, index=pd.date_range("2024-01-01", periods=len(vals), freq="1D", tz="UTC"))
    return p2.hyst_state(f, th_out, th_in)["A"].tolist()


def test_entry_needs_theta_in_and_stay_until_theta_out():
    # 0 -> 0,20 (<θ_in, flat) -> 0,30 (gir: +1) -> 0,15 (≥ θ_out: kal) -> 0,05 (< θ_out: çık) -> 0,20 (θ_in altı: flat kalır)
    assert states([0.0, 0.20, 0.30, 0.15, 0.05, 0.20]) == [0, 0, 1, 1, 0, 0]


def test_flip_needs_theta_in_on_the_other_side():
    # long iken −0,15: nötr/eşik arası ama θ_in'e ulaşmadı → |F| ≥ θ_out ama F<θ_out (negatif) ⇒ çıkış 0 (çevirme değil); doğrudan −0,30 ⇒ −1 (çevirme)
    assert states([0.40, -0.15]) == [1, 0]
    assert states([0.40, -0.30]) == [1, -1]
    assert states([-0.40, -0.12, -0.05, 0.30]) == [-1, -1, 0, 1]  # kısa: −0,12 kal (|F| ≥ θ_out), −0,05 çık, +0,30 gir


def test_nan_resets_state_and_neutral_zone_is_flat():
    f = pd.DataFrame({"A": [0.4, np.nan, 0.15, 0.05]}, index=pd.date_range("2024-01-01", periods=4, freq="1D", tz="UTC"))
    assert p2.hyst_state(f, 0.10, 0.25)["A"].tolist() == [1, 0, 0, 0]  # aktif olmayan gün s = 0; 0,15 < θ_in: yeniden girmez; 0,05 nötr
