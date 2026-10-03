"""E3 funding carry (EV1 §2): düşük funding long, yüksek funding short, [-1, 1]."""
import pandas as pd

BASE_FUNDING = 0.0001 / 8 * 24 * 365  # 0,01%/8 saat taban faiz bileşeni, yıllık (0,1095)


def forecast(close: pd.DataFrame, st: dict, p) -> pd.DataFrame:
    return (2 * -(st["phi"] - BASE_FUNDING) / st["sigma"]).clip(-1, 1).fillna(0.0).where(st["active"])
