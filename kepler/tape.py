"""C1: tape yükleme (Parquet -> DuckDB) + hedef-pozisyon sözleşmesi.

Sinyal = saf fonksiyon: signal(kl: DataFrame) -> Series. kl: UTC bar-açılış zamanı indeksli open/high/low/close/volume.
Seri kl ile AYNI indeksli, float: t'deki değer = t barı kapandığında istenen işaretli notional (USDT);
>0 long, <0 short, 0 flat, NaN = mevcut pozisyonu tut. Yalnızca t ve öncesi veriye bakabilir (C4 nedensellik testi denetler).
vectorbt (eleme) ve Nautilus (hakem) aynı seriyi oynatır.
"""
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from kepler.qc import SEAL_START

KINDS = {"klines": "klines", "mark": "markPriceKlines", "funding": "fundingRate"}


def _usable(root) -> dict:
    p = Path(root) / "tape" / "usable.json"
    return json.loads(p.read_text()) if p.exists() else {}


def membership(root) -> pd.DataFrame:
    """Aylık evren (month, rank, sym): kullanılamaz hale gelen (divergence_cutoff) sembol o aydan itibaren çıkar, yerine yenisi konmaz."""
    uni, cut = pd.read_parquet(Path(root) / "tape" / "universe.parquet"), _usable(root)
    start = pd.to_datetime(uni.month + "-01", utc=True)
    return uni[[(s not in cut or m <= pd.Timestamp(cut[s])) for s, m in zip(uni.sym, start)]].reset_index(drop=True)  # kesim ayı üye kalır; load() veriyi kesim anında keser


def load(root, sym: str, start=None, end=None) -> dict[str, pd.DataFrame]:
    """{'klines','mark','funding'}: ts indeksli. `end` mühür sınırını aşamaz (dev dönemi dışı veri ajan ortamına girmez)."""
    lo, hi = pd.Timestamp(start or "1970-01-01", tz="UTC"), pd.Timestamp(end, tz="UTC") if end else SEAL_START
    if hi > SEAL_START:
        raise ValueError(f"end={hi} mühür başlangıcını ({SEAL_START}) aşıyor")
    cut = _usable(root).get(sym)  # qc.divergence_cutoff: bayat/ölü kontrat verisi (kline~mark sapması) kullanıcıya hiç verilmez
    hi = min(hi, pd.Timestamp(cut)) if cut else hi
    out = {}
    for name, kind in KINDS.items():
        p = Path(root) / "tape" / kind / f"{sym}.parquet"
        df = duckdb.execute(f"select * exclude (ts_unit) from read_parquet('{p}') where ts >= ? and ts < ? order by ts", [lo, hi]).df()
        out[name] = df.set_index(pd.DatetimeIndex(df.pop("ts")).tz_convert("UTC"))
    return out


def check_target(kl: pd.DataFrame, target: pd.Series) -> pd.Series:
    """Sözleşmeyi doğrular (sessizce düzeltmez); geçerliyse seriyi döndürür."""
    if not isinstance(target, pd.Series) or not target.index.equals(kl.index):
        raise ValueError("hedef serisi kl ile aynı indekse sahip pd.Series olmalı")
    if not pd.api.types.is_float_dtype(target) or np.isinf(target.to_numpy()).any():
        raise ValueError("hedef float olmalı ve sonsuz değer içermemeli (NaN = tut)")
    return target
