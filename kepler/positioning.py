"""Pozisyonlanma verisi (OI, kalabalık long/short, taker akışı): arşiv `metrics` (5 dk) -> tape + nedensel saatlik özellikler.

  python -m kepler.positioning --root /data --out data_manifest [--syms BTCUSDT ...]   # idempotent, devam ettirilebilir

Bu modül yalnızca veriyi getirir; hipotez/sinyal yok. Tape ham satırları olduğu gibi tutar (kopya/boşluk dahil; qc.check_metrics raporlar).
`create_time` anlamı (dönem başı mı sonu mu) çağa göre değişiyor (BACKTEST §14); bu yüzden saatlik özellik muhafazakâr alınır.
"""
import argparse
import json
from pathlib import Path

import pandas as pd

from kepler import data, qc, tape
from kepler.universe import RAW

EXT = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT"]  # çekirdek-5 + genişletilmiş-9
K7 = ["1000PEPEUSDT", "1000SHIBUSDT", "APEUSDT", "APTUSDT", "ARBUSDT", "BCHUSDT", "ETCUSDT", "FILUSDT", "GMTUSDT", "LTCUSDT", "MATICUSDT",
      "NEARUSDT", "OPUSDT", "SUIUSDT"]  # K7 evreni (scripts/zone_fade.py kuralı, data_manifest/manifest.json'dan türetildi)
SYMS = EXT + K7


def to_tape(path: Path) -> pd.DataFrame:
    """Günlük zip -> `ts` (create_time, UTC) + ham değer sütunları (adlar değişmez; `symbol` dosya adında olduğu için atılır)."""
    df = data.read_zip_csv(path)
    df.insert(0, "ts", pd.to_datetime(df.pop("create_time"), utc=True))
    return df.drop(columns="symbol")


def build_symbol(root: Path, sym: str, workers: int = 16) -> str:
    """Sembolün tüm günlük zip'lerini (DEV_END'e kadar) indirir, tek Parquet'e birleştirir; gün -> zip sha256 yanına yazılır."""
    dst = root / "tape" / "metrics" / f"{sym}.parquet"
    if dst.exists():  # parquet en son ve atomik yazılır: varlığı "tamamlandı" demek
        return "cached"
    ds = data.days(sym)
    paths = data.fetch_many([data.key("metrics", sym, d) for d in ds], RAW, workers)
    df = pd.concat([to_tape(p) for p in paths], ignore_index=True)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.with_suffix(".sha.json").write_text(json.dumps({d: p.with_name(p.name + ".sha256").read_text() for d, p in zip(ds, paths)}))
    df.to_parquet(dst.with_suffix(".tmp"), index=False)
    dst.with_suffix(".tmp").replace(dst)
    return f"{len(ds)} gün"


def hourly(m: pd.DataFrame) -> pd.DataFrame:
    """5 dk ham satırlardan saatlik özellik. İndeks = bar AÇILIŞ zamanı (klines ile aynı); t satırı t+1h kapanışında bilinir.

    Bar [H, H+1h) için yalnızca create_time ∈ [H, H+55dk] satırlarının SON değeri alınır. create_time dönem sonu ise bu
    satır kapanıştan en az 5 dk önce, dönem başı ise tam kapanışta bilinir: iki anlam altında da geleceğe bakmaz. Yinelenen zaman damgasında
    son satır; satırı olmayan saat üretilmez; `n` = saatteki ham satır sayısı (12 = tam, az = eksik veri). Sütun adları ham kalır."""
    m = m.drop_duplicates("ts", keep="last").sort_values("ts").set_index("ts")
    m = m[m.index - m.index.floor("1h") <= pd.Timedelta("55min")]  # saniye sapmalı (xx:59:59) satırlar da kapanışa 5 dk'dan yakın alınmaz
    g = m.resample("1h")  # etiket ve kapanış solda: [H, H+1h) -> H
    out = g.last()
    out["n"] = g.size()
    return out[out.n > 0]


def load(root, sym: str, start=None, end=None) -> pd.DataFrame:
    """Sembolün saatlik pozisyonlanma özellikleri (UTC bar-açılış indeksli). `end` mühür sınırını aşamaz; kullanılamaz-kesim tape.load ile aynı."""
    lo, hi = pd.Timestamp(start or "1970-01-01", tz="UTC"), pd.Timestamp(end, tz="UTC") if end else qc.SEAL_START
    if hi > qc.SEAL_START:
        raise ValueError(f"end={hi} mühür başlangıcını ({qc.SEAL_START}) aşıyor")
    cut = tape._usable(root).get(sym)
    hi = min(hi, pd.Timestamp(cut)) if cut else hi
    m = pd.read_parquet(Path(root) / "tape" / "metrics" / f"{sym}.parquet")
    return hourly(m[m.ts < hi]).loc[lambda h: h.index >= lo]


def main(root: Path, out: Path, syms: list[str], workers: int = 16) -> None:
    out.mkdir(parents=True, exist_ok=True)
    manifest, issues = {}, []
    for sym in syms:
        print(sym, build_symbol(root, sym, workers), flush=True)
        p = root / "tape" / "metrics" / f"{sym}.parquet"
        df = pd.read_parquet(p)
        issues += [{"sym": sym, **x} for x in qc.check_metrics(df)]
        manifest[sym] = {"first": str(df.ts.min()), "last": str(df.ts.max()), "rows": len(df), "days": int(df.ts.dt.normalize().nunique()),
                         "parquet_sha256": qc.sha256_file(p), "zip_sha256": json.loads(p.with_suffix(".sha.json").read_text())}
    (out / "metrics_manifest.json").write_text(json.dumps({"dev_end": data.DEV_END, "seal_start": str(qc.SEAL_START), "symbols": manifest}, indent=1))
    pd.DataFrame(issues, columns=["sym", "check", "severity", "detail", "count", "first"]).to_csv(out / "metrics_quality_issues.csv", index=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/data"))
    ap.add_argument("--out", type=Path, default=Path("data_manifest"))
    ap.add_argument("--syms", nargs="*", default=SYMS)
    a = ap.parse_args()
    main(a.root, a.out, a.syms)
