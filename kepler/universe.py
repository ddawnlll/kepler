"""B3: dönemsel hacim evreni + dev verisi (Parquet). Yalnızca DEV_END'e kadar; mühürlü dönem hiç indirilmez.

  python -m kepler.universe --root /data        # idempotent, devam ettirilebilir

Evren (nedensel): ay M üyeleri = M-1 ayının USDT-M perp quote volume sıralaması (ilk TOP_N).
Delist olmuş ve sonradan listelenmiş kontratlar da dahil (survivorship düzeltmesi).
"""
import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from kepler import data

START, RANK_START, TOP_N = "2022-01", "2021-12", 20
# EVREN KURALI (G2'den ÖNCE, sinyale bakmadan sabitlendi; sonradan değiştirilirse seçim sayılır): soru "kripto perp'te edge var mı".
# Kripto dinamiği taşımayanlar sıralamadan ÖNCE çıkarılır (yerlerine sıradaki girer): stable/fiyatı sabit, emtia/değerli maden
# (altın/gümüş izleyen kontratlar dahil), endeks perp'leri, hisse/FX. Sıra dışı tek istisna yok.
EXCLUDE_BASES = frozenset({"USDC", "BUSD", "TUSD", "FDUSD", "USDP", "DAI", "EUR", "GBP", "XAU", "XAG", "XPT", "XPD", "PAXG", "XAUT",
                           "BTCDOM", "DEFI", "TSLA", "NVDA", "AAPL", "COIN", "MSTR", "QQQ", "SPY", "CL", "BZ", "NATGAS"})


def eligible(sym: str) -> bool:
    return sym.removesuffix("USDT") not in EXCLUDE_BASES
KINDS = ("klines", "markPriceKlines", "fundingRate")
RAW = Path(os.environ.get("KEPLER_RAW", "/tmp/kepler_raw"))  # ham zip'ler konteyner diskinde; kalıcı olan Parquet + sha listesi


def month_shift(m: str, k: int) -> str:
    p = pd.Period(m, "M") + k
    return str(p)


def _month_volume(path: Path) -> tuple[str, float, int]:
    df = data.read_zip_csv(path)
    return path.stem[-7:], float(df["quote_volume"].sum()), len(df)


def sym_volume(root: Path, sym: str, rank_start: str = RANK_START, end: str = data.DEV_END) -> pd.DataFrame:
    """Sembol başına aylık toplam quote volume; sonuç Parquet'e yazılır (devam ettirilebilir)."""
    cache = root / "tape" / "vol" / f"{sym}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    ms = [m for m in data.months("klines", sym, "1d") if rank_start <= m <= end]
    paths = data.fetch_many([data.key("klines", sym, m, "1d") for m in ms], RAW, workers=1)
    df = pd.DataFrame([(sym, *_month_volume(p)) for p in paths], columns=["sym", "month", "quote_volume", "days"])
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache, index=False)
    return df


def monthly_volume(root: Path, syms: list[str], workers: int = 32, rank_start: str = RANK_START, end: str = data.DEV_END) -> pd.DataFrame:
    parts = []
    with ThreadPoolExecutor(workers) as ex:
        for k, df in enumerate(ex.map(lambda s: sym_volume(root, s, rank_start, end), syms), 1):
            parts.append(df)
            if k % 20 == 0:
                print(f"  {k}/{len(syms)} sembol", flush=True)
    return pd.concat(parts, ignore_index=True)


def build_universe(vol: pd.DataFrame, top_n: int = TOP_N, start: str = START, end: str = data.DEV_END) -> pd.DataFrame:
    rows = []
    for m in pd.period_range(start, end, freq="M").astype(str):
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


def build_symbol(root: Path, sym: str, start: str = START, end: str = data.DEV_END) -> dict:
    """Sembolün üç türü için zip'leri indirir, tek Parquet'e birleştirir; zip sha256 listesi yanına yazılır. {kind: ay sayısı}."""
    out = {}
    for kind in KINDS:
        dst = root / "tape" / kind / f"{sym}.parquet"
        if dst.exists():  # devam: bu tür tamamlanmış
            out[kind] = "cached"
            continue
        ms = [m for m in data.months(kind, sym) if start <= m <= end]
        paths = data.fetch_many([data.key(kind, sym, m) for m in ms], RAW, workers=4)
        if not paths:
            out[kind] = 0
            continue
        df = pd.concat([to_tape(p, kind) for p in paths], ignore_index=True)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.with_suffix(".sha.json").write_text(json.dumps({m: p.with_name(p.name + ".sha256").read_text() for m, p in zip(ms, paths)}))
        df.to_parquet(dst.with_suffix(".tmp"), index=False)
        dst.with_suffix(".tmp").replace(dst)  # parquet en son, atomik: varlığı "tamamlandı" demek
        out[kind] = len(ms)
    return out


def main(root: Path, stage: str = "all", shard: str = "0/1", workers: int = 32, start: str = START, rank_start: str = RANK_START, end: str = data.DEV_END) -> None:
    """Aşamalar: rank (1d hacim indir, paralel parçalanabilir) -> universe (parçaları birleştir) -> build (1h/mark/funding)."""
    i, n = map(int, shard.split("/"))
    tape = root / "tape"
    tape.mkdir(parents=True, exist_ok=True)
    syms = data.symbols()
    if stage in ("rank", "all"):
        print(f"{len(syms)} USDT-M perp sembolü; parça {shard}", flush=True)
        monthly_volume(root, syms[i::n], workers, rank_start, end).to_parquet(tape / f"vol_shard_{i}_of_{n}.parquet", index=False)
    if stage in ("universe", "all"):
        vol = pd.concat([pd.read_parquet(p) for p in sorted(tape.glob("vol_shard_*_of_*.parquet"))], ignore_index=True).drop_duplicates(["sym", "month"])
        missing = {s for s in syms if eligible(s) and not (tape / "vol" / f"{s}.parquet").exists()}  # boş (dev penceresinde verisi olmayan) semboller de dosya bırakır
        if missing:
            raise RuntimeError(f"rank parçaları eksik: {len(missing)} sembolün hacmi yok (örn. {sorted(missing)[:3]}); eksik parçaları çalıştır")
        vol.to_parquet(tape / "volume_1d.parquet", index=False)
        build_universe(vol[vol.sym.map(eligible)], start=start, end=end).to_parquet(tape / "universe.parquet", index=False)  # filtre sıralamadan önce
    if stage in ("build", "all"):
        need = sorted(pd.read_parquet(tape / "universe.parquet").sym.unique())
        print(f"evren: {len(need)} sembol dev döneminde üye oldu; parça {shard}", flush=True)
        with ThreadPoolExecutor(max(1, workers // 4)) as ex:
            for sym, res in zip(need[i::n], ex.map(lambda s: build_symbol(root, s, start, end), need[i::n])):
                print(sym, res, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/data"))
    ap.add_argument("--stage", default="all", choices=["rank", "universe", "build", "all"])
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--start", default=START, help="ilk evren ayı (pre2022: 2019-09)")
    ap.add_argument("--rank-start", default=RANK_START, help="hacim sıralaması için ilk ay (pre2022: 2019-08)")
    ap.add_argument("--end", default=data.DEV_END, help="son ay (pre2022: 2021-12; DEV_END'i aşamaz)")
    a = ap.parse_args()
    if a.end > data.DEV_END:
        raise SystemExit(f"--end {a.end} mühür sınırını ({data.DEV_END}) aşıyor")
    main(a.root, a.stage, a.shard, start=a.start, rank_start=a.rank_start, end=a.end)
