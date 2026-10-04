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
DIV_RUN = 24  # bu kadar ardışık sapan bar = sembolün verisi artık kullanılamaz (divergence_cutoff)
FUND_MAX = 0.01  # |funding oranı| > %1 şüpheli
WICK = 0.5  # (high-low)/close > %50 tek saatlik mum: aşırı fitil
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
        if not iv.isin([1, 2, 4, 8]).all():  # gerçek veri: volatil semboller 1/2/4 saatlik aralığa geçiyor (TASKS "4 veya 8" varsayımı yanlış)
            out.append(_i("funding_interval", "ERROR", f"funding aralığı 1/2/4/8 saat dışında: {sorted(iv.unique())}", (~iv.isin([1, 2, 4, 8])).sum()))
        elif (iv != 8).any():
            out.append(_i("funding_interval_not_8h", "INFO", f"8 saat dışı aralık kullanılmış: {sorted(int(x) for x in iv.unique())}", (iv != 8).sum(), df.ts[iv != 8].iloc[0]))
        if df["last_funding_rate"].isna().any():
            out.append(_i("nan_funding_rate", "ERROR", "funding oranı NaN", df["last_funding_rate"].isna().sum()))
        f = df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
        exp = pd.to_timedelta(f["funding_interval_hours"].values, unit="h")
        exp = pd.concat([pd.Series(exp), pd.Series(exp).shift()], axis=1).max(axis=1)
        gaps = f.ts.diff() > exp + pd.Timedelta("1min")  # calc_time ms sapması boşluk sayılmaz
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
    if "volume" in df and ((df["volume"] < 0) | df["volume"].isna()).any():
        out.append(_i("negative_volume", "ERROR", "hacim < 0 veya NaN", ((df["volume"] < 0) | df["volume"].isna()).sum()))
    wick = ((h - l) / c) > WICK
    if wick.any():  # tutarlı ama aşırı geniş mum (hatalı print fitili): likidasyon stopunu yanlış tetikler
        out.append(_i("wick_outlier", "WARN", f"(high-low)/close > {WICK:.0%}", wick.sum(), ts[wick].iloc[0]))
    jump = (c / c.shift() - 1).abs() > JUMP
    # yalnızca komşu bar ise sıçrama say (boşluktan sonraki fark zaten 'gap' olarak raporlu)
    jump &= ts.diff() == HOUR
    if jump.any():
        out.append(_i("jump", "WARN", f"|saatlik getiri| > {JUMP:.0%}", jump.sum(), ts[jump].iloc[0]))
    return out


M_COLS = ["sum_open_interest", "sum_open_interest_value", "count_toptrader_long_short_ratio", "sum_toptrader_long_short_ratio",
          "count_long_short_ratio", "sum_taker_long_short_vol_ratio"]  # arşiv `metrics` ham sütunları (5 dakikalık)
M_STEP = pd.Timedelta("5min")


def check_metrics(df: pd.DataFrame) -> list[dict]:
    """Pozisyonlanma (`metrics`) sembol tape'i için kontroller; ham satırlar üzerinde, düzeltme yok. Boş liste = temiz."""
    out, ts = [], df["ts"]
    if ts.dt.tz is None or str(ts.dt.tz) != "UTC":
        return [_i("not_utc", "ERROR", "zaman damgası UTC değil", len(df))]
    n_dup = int(ts.duplicated().sum())
    if n_dup:  # birebir kopya = WARN; aynı zamana farklı değerler = ERROR (hangisinin doğru olduğu bilinmez)
        conflict = df.drop_duplicates().ts.duplicated().any()
        out.append(_i("duplicate_ts", "ERROR" if conflict else "WARN", "yinelenen zaman damgası" + (" (çelişkili değerler)" if conflict else " (birebir kopya)"), n_dup, ts[ts.duplicated()].iloc[0]))
    if (ts.diff() < pd.Timedelta(0)).any():
        out.append(_i("non_monotonic_ts", "ERROR", "zaman damgaları artan değil", (ts.diff() < pd.Timedelta(0)).sum()))
    if ts.max() >= SEAL_START:
        out.append(_i("sealed_period_leak", "ERROR", f"mühür sınırı ({SEAL_START}) sonrası veri var", (ts >= SEAL_START).sum(), ts.max()))
    if ((ts.dt.minute % 5) | ts.dt.second | ts.dt.microsecond).ne(0).any():
        out.append(_i("misaligned_ts", "ERROR", "5 dakikaya hizalı değil", ((ts.dt.minute % 5) | ts.dt.second).ne(0).sum()))
    u = df.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    d = u.ts.diff()
    if (d > M_STEP).any():
        out.append(_i("gap", "WARN", f"eksik satır: {int(((d[d > M_STEP] / M_STEP) - 1).sum())} adet, {int((d > M_STEP).sum())} boşluk (en uzun {d.max()})", (d > M_STEP).sum(), u.ts[d > M_STEP].iloc[0]))
    nan = [c for c in M_COLS if df[c].isna().any()]
    if nan:
        out.append(_i("nan_value", "WARN", f"NaN: {nan}", df[nan].isna().any(axis=1).sum()))
    bad = (df["sum_open_interest"] <= 0) | (df["sum_open_interest_value"] <= 0)
    if bad.any():
        out.append(_i("non_positive_oi", "ERROR", "OI <= 0", bad.sum(), ts[bad].iloc[0]))
    neg = (df[M_COLS[2:]] <= 0).any(axis=1)
    if neg.any():
        out.append(_i("non_positive_ratio", "WARN", "oran <= 0", neg.sum(), ts[neg].iloc[0]))
    jump = (u.sum_open_interest.pct_change().abs() > JUMP) & (d == M_STEP)  # yalnızca komşu satır; boşluk zaten 'gap'
    if jump.any():
        out.append(_i("oi_jump", "WARN", f"|5 dk OI değişimi| > {JUMP:.0%}", jump.sum(), u.ts[jump].iloc[0]))
    return out


def check_mark_vs_kline(kl: pd.DataFrame, mk: pd.DataFrame) -> list[dict]:
    m = kl.set_index("ts")["close"].to_frame("k").join(mk.set_index("ts")["close"].rename("m"), how="inner")
    div = ((m.k / m.m) - 1).abs() > MARK_DIV
    return [_i("mark_kline_divergence", "WARN", f"kline ile mark close farkı > {MARK_DIV:.0%}", div.sum(), m.index[div][0])] if div.any() else []


def divergence_cutoff(kl: pd.DataFrame, mk: pd.DataFrame):
    """KURAL (G2'den önce sabit, sinyale bakmadan): kline~mark farkı >%5 olan >=24 ARDIŞIK bar görülürse (ölü/göç etmiş/bayat kontrat)
    sembolün verisi o koşunun BAŞLANGICINDAN itibaren kullanılamaz. Önceki veri kalır (nedensel: yalnızca sonrası atılır). Yoksa None."""
    m = kl.set_index("ts").close.to_frame("k").join(mk.set_index("ts").close.rename("m"), how="inner")
    bad = (((m.k / m.m) - 1).abs() > MARK_DIV).astype(int)
    run = bad.rolling(DIV_RUN).sum() == DIV_RUN
    return m.index[run.to_numpy().argmax() - DIV_RUN + 1] if run.any() else None


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
            raw = json.loads(p.with_suffix(".sha.json").read_text())  # ay -> zip sha256 (indirme anında doğrulanmış)
            man_syms[sym][kind] = {"first": str(df.ts.min()), "last": str(df.ts.max()), "rows": len(df), "parquet_sha256": sha256_file(p), "zip_sha256": raw}
        if "klines" in frames and "markPriceKlines" in frames:
            issues += [{"sym": sym, "kind": "klines~mark", **x} for x in check_mark_vs_kline(frames["klines"], frames["markPriceKlines"])]
            cut = divergence_cutoff(frames["klines"], frames["markPriceKlines"])
            man_syms[sym]["usable_until"] = str(cut) if cut is not None else None
            if cut is not None:
                issues.append({"sym": sym, "kind": "klines~mark", **_i("usable_window_truncated", "WARN", f"{DIV_RUN}+ ardışık bar kline~mark >{MARK_DIV:.0%}: veri bu andan itibaren kullanılamaz", 0, cut)})
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
    (a.root / "tape" / "usable.json").write_text(json.dumps({s: v["usable_until"] for s, v in man["symbols"].items() if v.get("usable_until")}))  # tape.load bunu uygular
    print(iss.severity.value_counts().to_dict())
