"""B3: dönemsel hacim evreni + dev verisi (Parquet). Yalnızca DEV_END'e kadar; mühürlü dönem hiç indirilmez.

  python -m kepler.universe --root /data        # idempotent, devam ettirilebilir

Evren (nedensel): ay M üyeleri = M-1 ayının USDT-M perp quote volume sıralaması (ilk TOP_N).
Delist olmuş ve sonradan listelenmiş kontratlar da dahil (survivorship düzeltmesi).
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from kepler import data

START, RANK_START, TOP_N = "2022-01", "2021-12", 20
STABLE_BASES = ("USDC", "BUSD", "TUSD", "FDUSD")  # stable/USDT çiftleri majör değil
KINDS = ("klines", "markPriceKlines", "fundingRate")


def month_shift(m: str, k: int) -> str:
    p = pd.Period(m, "M") + k
    return str(p)


def _month_volume(path: Path) -> tuple[str, float, int]:
    df = data.read_zip_csv(path)
    return path.stem[-7:], float(df["quote_volume"].sum()), len(df)


def monthly_volume(root: Path, syms: list[str], workers: int = 32) -> pd.DataFrame:
    def one(sym):
        ms = [m for m in data.months("klines", sym, "1d") if RANK_START <= m]
        paths = data.fetch_many([data.key("klines", sym, m, "1d") for m in ms], root, workers=1)
        return [(sym, *_month_volume(p)) for p in paths]

    with ThreadPoolExecutor(workers) as ex:
        rows = [r for part in ex.map(one, syms) for r in part]
    return pd.DataFrame(rows, columns=["sym", "month", "quote_volume", "days"])


def build_universe(vol: pd.DataFrame, top_n: int = TOP_N) -> pd.DataFrame:
    rows = []
    for m in pd.period_range(START, data.DEV_END, freq="M").astype(str):
        prev = vol[vol.month == month_shift(m, -1)].nlargest(top_n, "quote_volume")
        rows += [(m, i + 1, r.sym, r.quote_volume) for i, r in enumerate(prev.itertuples())]
    return pd.DataFrame(rows, columns=["month", "rank", "sym", "prev_quote_volume"])


def to_tape(path: Path, kind: str) -> pd.DataFrame:
    df = data.read_zip_csv(path)
    tcol = "calc_time" if kind == "fundingRate" else "open_time"
    unit = "us" if df[tcol].abs().max() > 1e14 else "ms"  # kayıt: QC bu birimi ayrıca raporlar
    df.insert(0, "ts", pd.to_datetime(df.pop(tcol), unit=unit, utc=True))
    df["ts_unit"] = unit
    return df.drop(columns=[c for c in ("close_time", "ignore") if c in df.columns])


def build_symbol(root: Path, sym: str) -> dict:
    """Sembolün üç türü için ham zip'leri indirir, tek Parquet'e birleştirir. {kind: ay sayısı}."""
    out = {}
    for kind in KINDS:
        ms = [m for m in data.months(kind, sym) if m >= START]
        paths = data.fetch_many([data.key(kind, sym, m) for m in ms], root, workers=4)
        if not paths:
            out[kind] = 0
            continue
        df = pd.concat([to_tape(p, kind) for p in paths], ignore_index=True)
        dst = root / "tape" / kind / f"{sym}.parquet"
        dst.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(dst, index=False)
        out[kind] = len(ms)
    return out


def main(root: Path, workers: int = 16) -> None:
    root.mkdir(parents=True, exist_ok=True)
    syms = [s for s in data.symbols() if s[: -len("USDT")] not in STABLE_BASES]
    print(f"{len(syms)} USDT-M perp sembolü", flush=True)
    vol = monthly_volume(root, syms)
    (root / "tape").mkdir(exist_ok=True)
    vol.to_parquet(root / "tape" / "volume_1d.parquet", index=False)
    uni = build_universe(vol)
    uni.to_parquet(root / "tape" / "universe.parquet", index=False)
    need = sorted(uni.sym.unique())
    print(f"evren: {len(need)} sembol dev döneminde üye oldu", flush=True)
    with ThreadPoolExecutor(workers) as ex:
        for sym, res in zip(need, ex.map(lambda s: build_symbol(root, s), need)):
            print(sym, res, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/data"))
    main(ap.parse_args().root)
