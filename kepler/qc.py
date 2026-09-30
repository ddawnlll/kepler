"""B2: kalite kontrolü + manifest. Sorunları listeler; hiçbir şeyi sessizce düzeltmez.

  python -m kepler.qc --root /data --out data_manifest     # manifest.json + quality_report.md
"""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from kepler import data

HOUR = pd.Timedelta("1h")
JUMP = 0.30  # saatlik |close/önceki close - 1| bu değerden büyükse "anormal sıçrama"
MARK_DIV = 0.05  # kline close ile mark close arası göreli fark
FUND_MAX = 0.01  # |funding oranı| > %1 şüpheli
SEAL_START = pd.Timestamp(f"{pd.Period(data.DEV_END, 'M') + 1}-01", tz="UTC")


def _i(check, sev, detail, count, first=None):
    return {"check": check, "severity": sev, "detail": detail, "count": int(count), "first": str(first) if first is not None else ""}


def check_frame(df: pd.DataFrame, kind: str) -> list[dict]:
    """Tek sembol/tür için kontroller. Boş liste = temiz."""
    out, ts = [], df["ts"]
    if ts.dt.tz is None or str(ts.dt.tz) != "UTC":
        return [_i("not_utc", "ERROR", "zaman damgası UTC değil", len(df))]  # diğer kontroller güvenilmez
    if (df.get("ts_unit", pd.Series("ms")) != "ms").any():
        out.append(_i("ts_unit_not_ms", "WARN", "mikrosaniye zaman damgası (ms'ye çevrildi)", (df["ts_unit"] != "ms").sum()))
    dup = ts.duplicated(keep=False)
    if dup.any():
        out.append(_i("duplicate_ts", "ERROR", "yinelenen zaman damgası", dup.sum(), ts[dup].iloc[0]))
    if not ts.is_monotonic_increasing:
        out.append(_i("non_monotonic_ts", "ERROR", "zaman damgaları artan değil", (ts.diff() < pd.Timedelta(0)).sum()))
    if ts.max() >= SEAL_START:
        out.append(_i("sealed_period_leak", "ERROR", f"mühür sınırı ({SEAL_START}) sonrası veri var", (ts >= SEAL_START).sum(), ts.max()))
    d = ts.sort_values().drop_duplicates().diff()
    if kind == "fundingRate":
        iv = df["funding_interval_hours"]
        if not iv.isin([4, 8]).all():
            out.append(_i("funding_interval", "ERROR", f"funding aralığı 4/8 saat dışında: {sorted(iv.unique())}", (~iv.isin([4, 8])).sum()))
        f = df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
        exp = pd.to_timedelta(f["funding_interval_hours"].values, unit="h")
        exp = pd.concat([pd.Series(exp), pd.Series(exp).shift()], axis=1).max(axis=1)
        gaps = f.ts.diff() > exp
        if gaps.any():
            out.append(_i("gap", "WARN", "funding kaydı eksik (aralık > bildirilen)", gaps.sum(), f.ts[gaps].iloc[0]))
        if (df["last_funding_rate"].abs() > FUND_MAX).any():
            out.append(_i("funding_extreme", "WARN", f"|oran| > {FUND_MAX}", (df["last_funding_rate"].abs() > FUND_MAX).sum()))
        return out
    if (ts.dt.minute | ts.dt.second | ts.dt.microsecond).ne(0).any():
        out.append(_i("misaligned_ts", "ERROR", "saat sınırına hizalı değil", ((ts.dt.minute | ts.dt.second) != 0).sum()))
    g = d > HOUR
    if g.any():
        out.append(_i("gap", "WARN", f"eksik bar: {int(((d[g] / HOUR) - 1).sum())} adet, {int(g.sum())} boşluk", g.sum(), ts.loc[g[g].index[0]]))
    o, h, l, c = (df[x] for x in ("open", "high", "low", "close"))
    if df[["open", "high", "low", "close"]].isna().any().any():
        out.append(_i("nan_price", "ERROR", "NaN fiyat", df[["open", "high", "low", "close"]].isna().any(axis=1).sum()))
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        out.append(_i("non_positive_price", "ERROR", "fiyat <= 0", (df[["open", "high", "low", "close"]] <= 0).any(axis=1).sum()))
    bad = (h < l) | (h < o.combine(c, max)) | (l > o.combine(c, min))
    if bad.any():
        out.append(_i("inconsistent_candle", "ERROR", "high<low veya open/close [low,high] dışında", bad.sum(), ts[bad].iloc[0]))
    if "volume" in df and (df["volume"] < 0).any():
        out.append(_i("negative_volume", "ERROR", "hacim < 0", (df["volume"] < 0).sum()))
    jump = (c / c.shift() - 1).abs() > JUMP
    # yalnızca komşu bar ise sıçrama say (boşluktan sonraki fark zaten 'gap' olarak raporlu)
    jump &= ts.diff() == HOUR
    if jump.any():
        out.append(_i("jump", "WARN", f"|saatlik getiri| > {JUMP:.0%}", jump.sum(), ts[jump].iloc[0]))
    return out


def check_mark_vs_kline(kl: pd.DataFrame, mk: pd.DataFrame) -> list[dict]:
    m = kl.set_index("ts")["close"].to_frame("k").join(mk.set_index("ts")["close"].rename("m"), how="inner")
    div = ((m.k / m.m) - 1).abs() > MARK_DIV
    return [_i("mark_kline_divergence", "WARN", f"kline ile mark close farkı > {MARK_DIV:.0%}", div.sum(), m.index[div][0])] if div.any() else []


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_all(root: Path) -> tuple[dict, pd.DataFrame]:
    tape = root / "tape"
    uni = pd.read_parquet(tape / "universe.parquet")
    issues, man_syms = [], {}
    for sym in sorted(uni.sym.unique()):
        man_syms[sym] = {}
        frames = {}
        for kind in ("klines", "markPriceKlines", "fundingRate"):
            p = tape / kind / f"{sym}.parquet"
            if not p.exists():
                issues.append({"sym": sym, "kind": kind, **_i("missing_file", "WARN", "bu tür için dosya yok", 0)})
                continue
            df = pd.read_parquet(p)
            frames[kind] = df
            issues += [{"sym": sym, "kind": kind, **x} for x in check_frame(df, kind)]
            raw = {z.name[-14:-4]: z.with_name(z.name + ".sha256").read_text() for z in sorted((root / "raw" / data.BASE / kind / sym).rglob("*.zip"))}
            man_syms[sym][kind] = {"first": str(df.ts.min()), "last": str(df.ts.max()), "rows": len(df), "parquet_sha256": sha256_file(p), "zip_sha256": raw}
        if "klines" in frames and "markPriceKlines" in frames:
            issues += [{"sym": sym, "kind": "klines~mark", **x} for x in check_mark_vs_kline(frames["klines"], frames["markPriceKlines"])]
        if "klines" in frames:  # listeleme / delist: dev penceresi içinde son bar erken bitiyorsa delist adayı
            last = frames["klines"].ts.max()
            if last < SEAL_START - pd.Timedelta("2D"):
                issues.append({"sym": sym, "kind": "klines", **_i("delisted", "INFO", f"son bar {last}; delist/duraklatma", 0, last)})
    manifest = {
        "dev_end": data.DEV_END, "seal_start": str(SEAL_START), "top_n": int(uni["rank"].max()),
        "universe": {m: g.sort_values("rank").sym.tolist() for m, g in uni.groupby("month")},
        "symbols": man_syms,
    }
    return manifest, pd.DataFrame(issues, columns=["sym", "kind", "check", "severity", "detail", "count", "first"])


def report_md(iss: pd.DataFrame, man: dict) -> str:
    n = len(man["symbols"])
    lines = [f"# Veri kalite raporu (dev dönemi ≤ {man['dev_end']}; mühür ≥ {man['seal_start'][:10]})", "",
             f"Sembol sayısı: {n}; aylık evren: {len(man['universe'])} ay × top {man['top_n']}.",
             f"Bulgu sayısı: {len(iss)} ({iss.severity.value_counts().to_dict()}). Hiçbir bulgu sessizce düzeltilmedi.", ""]
    if iss.empty:
        return "\n".join(lines + ["Temiz."])
    lines += ["## Kontrole göre özet", "", "| kontrol | önem | sembol | kayıt |", "|---|---|---|---|"]
    for (chk, sev), g in iss.groupby(["check", "severity"]):
        lines.append(f"| {chk} | {sev} | {g.sym.nunique()} | {g['count'].sum()} |")
    lines.append("")
    lines += ["## Ayrıntı (ERROR önce)", "", "| sembol | tür | kontrol | önem | adet | ilk | açıklama |", "|---|---|---|---|---|---|---|"]
    for r in iss.assign(o=iss.severity.map({"ERROR": 0, "WARN": 1, "INFO": 2})).sort_values(["o", "check", "sym"]).itertuples():
        lines.append(f"| {r.sym} | {r.kind} | {r.check} | {r.severity} | {r.count} | {r.first[:16]} | {r.detail} |")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("/data"))
    ap.add_argument("--out", type=Path, default=Path("/data/manifest"))
    a = ap.parse_args()
    man, iss = run_all(a.root)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "manifest.json").write_text(json.dumps(man, separators=(",", ":")))
    (a.out / "quality_report.md").write_text(report_md(iss, man))
    iss.to_csv(a.out / "quality_issues.csv", index=False)
    print(iss.severity.value_counts().to_dict())
