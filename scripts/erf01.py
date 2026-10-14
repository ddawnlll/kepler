#!/usr/bin/env python3
"""ERF-01 one-shot daily onset forecast experiment. Never requests data after 2026-03."""
from __future__ import annotations

import argparse
import csv
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import json
import math
import random
import re
import shlex
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import sklearn
import pyarrow
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "erf01_data"
PARQUET_OUT = ROOT / "data" / "erf01"
SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT"]
FIRST_MONTH, LAST_MONTH = "2020-01", "2026-03"
SEAL = date(2026, 4, 1)
DAYS = (date(2020, 1, 1), date(2026, 3, 31))
FOLDS = [(date(y, m, 1), date(ny, nm, 1), f"{y}-{m:02d}") for y, m, ny, nm in [
    (2023, 1, 2023, 7), (2023, 7, 2024, 1), (2024, 1, 2024, 7),
    (2024, 7, 2025, 1), (2025, 1, 2025, 7), (2025, 7, 2026, 1), (2026, 1, 2026, 4)]]
BASE_NAMES = ["state_-1", "state_0", "state_1", "state_age_log"] + [f"symbol_{s}" for s in SYMS]
M1_NAMES = ["ret7", "ret21", "ret63", "z20", "er20", "rv5", "rv20"]
M2_NAMES = ["rv5_rv20", "volume_surprise20", "breadth_dispersion7", "funding_stress90"]
ALL_NAMES = BASE_NAMES + M1_NAMES + M2_NAMES


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def month_iter(first: str, last: str):
    y, m = map(int, first.split("-")); ey, em = map(int, last.split("-"))
    while (y, m) <= (ey, em):
        yield f"{y:04d}-{m:02d}"
        y, m = (y + (m == 12), 1 if m == 12 else m + 1)


def _get(url: str, attempts=4) -> bytes:
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Kepler-ERF01-research/1.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise FileNotFoundError(url) from e
            if i == attempts - 1:
                raise
        except Exception:
            if i == attempts - 1:
                raise
        time.sleep(1 + i)
    raise RuntimeError(url)


def _month_of(ts: str) -> str:
    return ts[:7]


def _combined_manifest():
    old = json.loads((ROOT / "data_manifest" / "manifest_pre2022.json").read_text())
    new = json.loads((ROOT / "data_manifest" / "manifest.json").read_text())
    out = {}
    for s in SYMS:
        a, b = old["symbols"].get(s, {}), new["symbols"].get(s, {})
        out[s] = {}
        for kind in ("klines", "fundingRate"):
            entries = [x[kind] for x in (a, b) if kind in x and x[kind].get("first")]
            if entries:
                out[s][kind] = {"first": min(x["first"] for x in entries), "last": max(x["last"] for x in entries)}
    return out


def _month_in_range(month: str, first: str, last: str) -> bool:
    return _month_of(first) <= month <= _month_of(last)


def _fetch_verified(url: str, path: Path) -> dict:
    """Fetch/reuse one source archive only after matching Binance's published SHA-256."""
    check_url = url + ".CHECKSUM"
    check_bytes = _get(check_url)
    token = check_bytes.decode("utf-8", "replace").strip().split()[0].lower()
    if not re.fullmatch(r"[0-9a-f]{64}", token):
        raise ValueError(f"unrecognized Binance checksum at {check_url}: {check_bytes[:120]!r}")
    if path.exists():
        blob = path.read_bytes()
        if sha(blob) != token:
            path.unlink()
            blob = _get(url)
    else:
        blob = _get(url)
    got = sha(blob)
    if got != token:
        raise ValueError(f"SHA-256 mismatch {url}: expected {token}, got {got}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        members = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError(f"expected one CSV in {url}: {members}")
        with zf.open(members[0]) as stream:
            text = io.TextIOWrapper(stream, encoding="utf-8-sig", newline="")
            rows = sum(bool(row and row[0].strip() and row[0].strip()[0].isdigit()) for row in csv.reader(text))
    return {"url": url, "sha256": got, "checksum_url": check_url, "checksum_sha256": token,
            "verification": "Binance published SHA-256 matched", "bytes": len(blob), "rows": rows}


def _save_acquisition(result):
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "acquisition.json.tmp"
    tmp.write_text(json.dumps(result, indent=2) + "\n")
    tmp.replace(OUT / "acquisition.json")


def _ensure_protocol():
    """Fail before downloading; file presence does not prove historical preregistration."""
    protocol = ROOT / "reports" / "erf01_protocol.md"
    if not protocol.is_file() or not protocol.read_text(encoding="utf-8").strip():
        raise FileNotFoundError(f"ERF-01 protocol missing or empty: {protocol}")
    return protocol


def _check_seal():
    from kepler.qc import SEAL_START
    if SEAL_START.date() != SEAL:
        raise RuntimeError(f"ERF-01 seal {SEAL} differs from kepler.qc {SEAL_START.date()}")


def _verify_acquisition(a: dict, raw: Path):
    records = a.get("records", [])
    if (not a.get("complete") or a.get("errors") or not records
            or len(records) != a.get("record_count") or len(records) != a.get("expected_archives")
            or not isinstance(a.get("workers"), int)):
        raise RuntimeError("incomplete or inconsistent ERF-01 acquisition")
    if Path(a["raw_root"]).resolve() != raw.resolve():
        raise RuntimeError("acquisition raw_root mismatches --raw-root")
    seen = set()
    for r in records:
        key = (r["symbol"], r["kind"], r["month"])
        if key in seen or r["symbol"] not in SYMS or r["kind"] not in ("klines", "fundingRate"):
            raise RuntimeError(f"duplicate/unknown archive: {key}")
        seen.add(key)
        if r["month"] > LAST_MONTH or r["month"] >= SEAL.strftime("%Y-%m"):
            raise RuntimeError(f"archive outside development window: {key}")
        path = raw / r["kind"] / r["symbol"] / f"{r['month']}.zip"
        if not path.is_file() or sha(path.read_bytes()) != r["sha256"]:
            raise RuntimeError(f"missing or modified source archive: {path}")


def fetch(raw: Path, workers=12):
    _ensure_protocol()
    _check_seal()
    if workers < 1:
        raise ValueError("workers must be >= 1")
    manifest = _combined_manifest()
    jobs, errors = [], []
    for sym in SYMS:
        for kind, folder, suffix in (("klines", "klines", f"{sym}-1d-"), ("fundingRate", "fundingRate", f"{sym}-fundingRate-")):
            rng = manifest.get(sym, {}).get(kind)
            if not rng:
                errors.append(f"manifest has no {kind} range for {sym}")
                continue
            for month in month_iter(FIRST_MONTH, LAST_MONTH):
                if not _month_in_range(month, rng["first"], rng["last"]):
                    continue
                if month >= "2026-04":
                    raise AssertionError("G3 boundary guard")
                if kind == "klines":
                    url = f"https://data.binance.vision/data/futures/um/monthly/klines/{sym}/1d/{suffix}{month}.zip"
                else:
                    url = f"https://data.binance.vision/data/futures/um/monthly/fundingRate/{sym}/{suffix}{month}.zip"
                jobs.append((url, raw / folder / sym / f"{month}.zip", sym, kind, month))
    result = {"period_requested": [FIRST_MONTH, LAST_MONTH], "seal_start": SEAL.isoformat(), "symbols": SYMS,
              "records": [], "errors": errors, "record_count": 0, "expected_archives": len(jobs), "raw_root": str(raw),
              "workers": workers, "complete": False}
    _save_acquisition(result)
    def one(job):
        url, target, sym, kind, month = job
        rec = _fetch_verified(url, target)
        rec.update(symbol=sym, kind=kind, month=month)
        return rec
    failures = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, j): j for j in jobs}
        for done, future in enumerate(as_completed(futures), 1):
            job = futures[future]
            try:
                result["records"].append(future.result())
            except FileNotFoundError:
                failures.append(f"missing archive within manifest range: {job[0]}")
            except Exception as exc:
                failures.append(f"{job[0]}: {type(exc).__name__}: {exc}")
            result["record_count"] = len(result["records"])
            if done % 50 == 0 or done == len(jobs):
                result["errors"] = errors + failures
                _save_acquisition(result)
                print(f"verified {done}/{len(jobs)} source archives", flush=True)
    result["records"].sort(key=lambda x: (x["symbol"], x["kind"], x["month"]))
    result["errors"] = sorted(errors + failures)
    result["record_count"] = len(result["records"])
    result["downloaded_bytes"] = sum(x["bytes"] for x in result["records"])
    result["complete"] = not result["errors"] and result["record_count"] == result["expected_archives"]
    _save_acquisition(result)
    if not result["complete"]:
        raise RuntimeError(f"acquisition incomplete: {result['record_count']}/{result['expected_archives']} verified; see {OUT / 'acquisition.json'}")
    return result


def _csv_rows(zip_path: Path):
    with zipfile.ZipFile(zip_path) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        text = io.TextIOWrapper(zf.open(name), encoding="utf-8-sig", newline="")
        yield from csv.reader(text)


def _date_ms(x: str) -> date:
    return datetime.fromtimestamp(int(float(x)) / 1000, tz=timezone.utc).date()


def _parse_archive(raw: Path):
    klines, fund, fund_records = {s: {} for s in SYMS}, {s: [] for s in SYMS}, []
    metadata = {s: {"klines_archives": 0, "daily_rows": 0, "funding_archives": 0, "funding_rows": 0,
                    "bad_ohlc": 0, "duplicate_days": 0, "funding_extreme_abs_gt_1pct": 0} for s in SYMS}
    manifest = _combined_manifest()
    for sym in SYMS:
        for month in month_iter(FIRST_MONTH, LAST_MONTH):
            if not _month_in_range(month, manifest[sym]["klines"]["first"], manifest[sym]["klines"]["last"]):
                continue
            p = raw / "klines" / sym / f"{month}.zip"
            for i, row in enumerate(_csv_rows(p)):
                if not row or not row[0].strip() or not row[0].strip()[0].isdigit():
                    continue
                open_ms = int(float(row[0]))
                dt = _date_ms(row[0])
                if dt >= SEAL:
                    raise AssertionError("Downloaded/parsed sealed data")
                o, h, l, c, v = map(float, row[1:6])
                quote_volume = float(row[7]) if len(row) > 7 else math.nan
                if not all(math.isfinite(x) for x in (o, h, l, c, v)) or min(o, h, l, c) <= 0 or v < 0 or h < max(o, c, l) or l > min(o, c, h):
                    metadata[sym]["bad_ohlc"] += 1
                    continue
                if dt in klines[sym]:
                    metadata[sym]["duplicate_days"] += 1
                else:
                    klines[sym][dt] = (o, h, l, c, v, open_ms, quote_volume)
            metadata[sym]["klines_archives"] += 1
        for month in month_iter(FIRST_MONTH, LAST_MONTH):
            fr = manifest[sym].get("fundingRate")
            if not fr or not _month_in_range(month, fr["first"], fr["last"]):
                continue
            p = raw / "fundingRate" / sym / f"{month}.zip"
            for row in _csv_rows(p):
                if not row or not row[0].strip() or not row[0].strip()[0].isdigit():
                    continue
                ts = int(float(row[0]))
                if datetime.fromtimestamp(ts / 1000, timezone.utc).date() >= SEAL:
                    raise AssertionError("Funding archive contains sealed data")
                interval, rate = float(row[1]), float(row[2])
                if interval <= 0 or not math.isfinite(rate):
                    continue
                if abs(rate) > .01:
                    metadata[sym]["funding_extreme_abs_gt_1pct"] += 1
                rate_8h = rate * 8.0 / interval
                fund[sym].append((ts, rate_8h))
                fund_records.append((sym, ts, interval, rate, rate_8h))
            metadata[sym]["funding_archives"] += 1
    for sym in SYMS:
        metadata[sym]["daily_rows"] = len(klines[sym])
        metadata[sym]["funding_rows"] = len(fund[sym])
        fund[sym].sort()
    return klines, fund, fund_records, metadata


def _write_input_parquet(klines, fund_records):
    import pyarrow as pa
    import pyarrow.parquet as pq
    PARQUET_OUT.mkdir(parents=True, exist_ok=True)
    price_rows = []
    for sym in SYMS:
        for d, vals in sorted(klines[sym].items()):
            price_rows.append({"ts": datetime.combine(d, datetime.min.time(), timezone.utc),
                               "source_open_time": datetime.fromtimestamp(vals[5] / 1000, timezone.utc),
                               "symbol": sym, "open": vals[0], "high": vals[1], "low": vals[2],
                               "close": vals[3], "volume": vals[4], "quote_volume": vals[6]})
    rates = [{"symbol": sym, "calc_time": datetime.fromtimestamp(ts / 1000, timezone.utc),
              "funding_interval_hours": interval, "last_funding_rate": rate, "rate_per_8h": rate8}
             for sym, ts, interval, rate, rate8 in sorted(fund_records, key=lambda x: (x[0], x[1]))]
    outputs = {}
    for name, records in (("daily_klines.parquet", price_rows), ("funding.parquet", rates)):
        path = PARQUET_OUT / name
        tmp = path.with_suffix(".parquet.tmp")
        table = pa.Table.from_pylist(records)
        pq.write_table(table, tmp, compression="zstd", use_dictionary=["symbol"], write_statistics=True)
        tmp.replace(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        try:
            display_path = str(path.relative_to(ROOT))
        except ValueError:
            display_path = str(path)
        outputs[name] = {"path": display_path, "rows": len(records), "bytes": path.stat().st_size, "sha256": digest}
    return outputs


def _read_input_parquet():
    import pyarrow.parquet as pq
    daily = pq.read_table(PARQUET_OUT / "daily_klines.parquet").to_pylist()
    fund_rows = pq.read_table(PARQUET_OUT / "funding.parquet").to_pylist()
    klines, funding, fund_records = {s: {} for s in SYMS}, {s: [] for s in SYMS}, []
    for r in daily:
        sym, d = r["symbol"], r["ts"].date()
        source_ms = int(r["source_open_time"].timestamp() * 1000)
        klines[sym][d] = (r["open"], r["high"], r["low"], r["close"], r["volume"], source_ms, r["quote_volume"])
    for r in fund_rows:
        sym, ts = r["symbol"], int(r["calc_time"].timestamp() * 1000)
        interval, rate, rate8 = r["funding_interval_hours"], r["last_funding_rate"], r["rate_per_8h"]
        funding[sym].append((ts, rate8))
        fund_records.append((sym, ts, interval, rate, rate8))
    for sym in SYMS:
        funding[sym].sort()
    return klines, funding, fund_records


def _parquet_inventory():
    files = {}
    for name in ("daily_klines.parquet", "funding.parquet"):
        path = PARQUET_OUT / name
        if not path.exists():
            return None
        import pyarrow.parquet as pq
        data = path.read_bytes()
        files[name] = {"path": str(path.relative_to(ROOT)), "rows": pq.read_metadata(path).num_rows,
                       "bytes": len(data), "sha256": sha(data)}
    return files


def _roll_sum(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(x.size, np.nan)
    for i in range(n - 1, x.size):
        z = x[i - n + 1:i + 1]
        if np.isfinite(z).all():
            out[i] = z.sum()
    return out


def _roll_median_log_ratio(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(x.size, np.nan)
    for i in range(n - 1, x.size):
        w = x[i - n + 1:i + 1]
        if np.isfinite(w).all() and np.all(w > 0):
            med = float(np.median(w))
            if med > 0:
                out[i] = math.log(w[-1] / med)
    return out


def _funding_stress(events: list[tuple[int, float]], days: list[date]) -> np.ndarray:
    out = np.full(len(days), np.nan)
    if not events:
        return out
    ts = np.asarray([x[0] for x in events], dtype=np.int64)
    rates = np.asarray([x[1] for x in events], dtype=np.float64)
    for i, d in enumerate(days):
        end = int(datetime.combine(d + timedelta(days=1), datetime.min.time(), timezone.utc).timestamp() * 1000)
        lo90, lo37, lo7 = end - 90 * 86400000, end - 37 * 86400000, end - 7 * 86400000
        a, b, c = np.searchsorted(ts, [lo90, lo37, lo7], side="left")
        e = np.searchsorted(ts, end, side="left")  # strictly before close
        if e - a < 45 or c == e or b == c:
            continue
        hist = rates[a:e]
        sd = float(np.std(hist, ddof=0))
        if sd > 0:
            out[i] = (float(np.mean(rates[c:e])) - float(np.mean(rates[b:c]))) / sd
    return out


def make_panel(klines, funding):
    days = [DAYS[0] + timedelta(days=i) for i in range((DAYS[1] - DAYS[0]).days + 1)]
    nd = len(days); date_index = {d: i for i, d in enumerate(days)}
    panel = {}
    for sym in SYMS:
        arr = np.full((nd, 5), np.nan)
        for d, vals in klines[sym].items():
            if d in date_index:
                arr[date_index[d]] = vals[:5]
        o, h, l, c, vol = arr.T
        ret = np.full(nd, np.nan)
        good = np.isfinite(c[1:]) & np.isfinite(c[:-1])
        # Exact adjacent calendar days only; a missing day breaks the return.
        ret[1:][good] = np.log(c[1:][good] / c[:-1][good])
        rsum20, abs20, sq20 = _roll_sum(ret, 20), _roll_sum(np.abs(ret), 20), _roll_sum(ret * ret, 20)
        z20 = np.divide(rsum20, np.sqrt(sq20 + 1e-12), out=np.full(nd, np.nan), where=np.isfinite(sq20))
        er20 = np.divide(np.abs(rsum20), abs20 + 1e-12, out=np.full(nd, np.nan), where=np.isfinite(abs20))
        q = np.full(nd, np.nan)
        valid = np.isfinite(z20) & np.isfinite(er20)
        q[valid] = 0
        q[valid & (z20 >= 1.25) & (er20 >= .35)] = 1
        q[valid & (z20 <= -1.25) & (er20 >= .35)] = -1
        age = np.full(nd, np.nan)
        for i in range(nd):
            if not np.isfinite(q[i]):
                continue
            age[i] = 1 if i == 0 or not np.isfinite(q[i-1]) or q[i] != q[i-1] else age[i-1] + 1
        ret7, ret21, ret63 = (_roll_sum(ret, n) for n in (7, 21, 63))
        rv5 = np.sqrt(_roll_sum(ret * ret, 5)); rv20 = np.sqrt(sq20)
        vol_surp = _roll_median_log_ratio(vol, 20)
        fund = _funding_stress(funding[sym], days)
        panel[sym] = {"open": o, "high": h, "low": l, "close": c, "volume": vol, "ret": ret, "q": q, "age": age,
                      "z20": z20, "er20": er20, "ret7": ret7, "ret21": ret21, "ret63": ret63,
                      "rv5": rv5, "rv20": rv20, "volume_surprise20": vol_surp, "funding_stress90": fund}
    # One same-origin breadth/dispersion scalar, only when >=3 symbols have complete trailing returns.
    breadth = np.full((len(SYMS), nd), np.nan)
    for i in range(nd):
        xs = np.asarray([panel[s]["ret7"][i] for s in SYMS])
        xs = xs[np.isfinite(xs)]
        if xs.size >= 3:
            sd = float(np.std(xs, ddof=0))
            value = float(np.mean(xs) / sd) if sd > 0 else 0.0
            breadth[:, i] = value
    for j, sym in enumerate(SYMS):
        p = panel[sym]
        with np.errstate(divide="ignore", invalid="ignore"):
            p["rv5_rv20"] = p["rv5"] / p["rv20"]
        p["breadth_dispersion7"] = breadth[j]
        p["base"] = np.column_stack([*(p["q"] == v for v in (-1, 0, 1)), np.log1p(p["age"]),
                                      *(np.full(nd, float(s == sym)) for s in SYMS)])
        p["m1"] = np.column_stack([p[k] for k in M1_NAMES])
        p["m2"] = np.column_stack([p[k] for k in M2_NAMES])
        p["features"] = np.column_stack([p["base"], p["m1"], p["m2"]])
    return days, panel


def labels_for(panel, days):
    n = len(days); outcomes = {}; events = []; candidates = []
    for sym in SYMS:
        q = panel[sym]["q"]
        confirmed, candidate = [], []
        for i in range(10, n - 10):
            if not np.isfinite(q[i]) or q[i] == 0 or not np.all(q[i-10:i] == 0):
                continue
            sign = int(q[i]); after = q[i+1:i+11]
            ok = int(np.count_nonzero(after == sign)) >= 8
            rec = {"symbol": sym, "onset": days[i].isoformat(), "direction": "up" if sign > 0 else "down",
                   "confirmed": bool(ok), "confirmation": days[i+10].isoformat()}
            candidate.append(rec)
            if ok:
                confirmed.append((i, sign)); events.append(rec)
        candidates.extend(candidate)
        y = np.full(n, -1, dtype=np.int8)
        # Need the complete maximum outcome path (7-day onset + 10-day confirmation).
        for t in range(0, n - 17):
            hits = [(e, sign) for e, sign in confirmed if t < e <= t + 7]
            if not hits:
                y[t] = 0
            else:
                hits.sort()
                y[t] = 1 if hits[0][1] > 0 else 2
        outcomes[sym] = y
    return outcomes, events, candidates


def _rows(panel, labels, days):
    rows = []
    for sym in SYMS:
        p, y = panel[sym], labels[sym]
        for i in range(len(days)):
            x = p["features"][i]
            if y[i] >= 0 and np.isfinite(x).all():
                rows.append((days[i], sym, int(y[i]), x))
    return rows


def _fit_predict(train, test, model_cols, return_train=False):
    Xtr = np.asarray([r[3][model_cols] for r in train], dtype=float)
    ytr = np.asarray([r[2] for r in train], dtype=int)
    Xte = np.asarray([r[3][model_cols] for r in test], dtype=float)
    if len(set(ytr)) < 2:
        raise RuntimeError(f"training fold has fewer than two target classes: {np.bincount(ytr, minlength=3)}")
    scaler = StandardScaler().fit(Xtr)
    model = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000, class_weight=None, random_state=0)
    model.fit(scaler.transform(Xtr), ytr)
    def expand(raw, n):
        probs = np.full((n, 3), 1e-15)
        for j, cls in enumerate(model.classes_):
            probs[:, int(cls)] = raw[:, j]
        return probs / probs.sum(axis=1, keepdims=True)
    probs = expand(model.predict_proba(scaler.transform(Xte)), len(test))
    train_probs = expand(model.predict_proba(scaler.transform(Xtr)), len(train)) if return_train else None
    return probs, int(model.n_iter_[0]), train_probs


def _scores(y: np.ndarray, prob: np.ndarray):
    one = np.eye(3)[y]
    return np.sum((prob - one) ** 2, axis=1), -np.log(np.maximum(prob[np.arange(len(y)), y], 1e-15))


def _moving_block_ci(by_date: dict[date, float], B=2000, block=28, seed=20261014):
    ds = sorted(by_date); x = np.asarray([by_date[d] for d in ds], dtype=float)
    if len(x) < block:
        return {"n_dates": len(x), "observed": float(x.mean()), "p05": None, "p025": None, "p975": None, "replicates": 0}
    rng = np.random.default_rng(seed); reps = np.empty(B)
    n = len(x)
    for b in range(B):
        sample = []
        while len(sample) < n:
            start = int(rng.integers(0, n - block + 1))
            sample.extend(x[start:start + block])
        reps[b] = np.mean(sample[:n])
    return {"n_dates": n, "observed": float(x.mean()), "p05": float(np.quantile(reps, .05)),
            "p025": float(np.quantile(reps, .025)), "p975": float(np.quantile(reps, .975)), "replicates": B,
            "block_days": block, "seed": seed}


def _cluster_events(events):
    dates = sorted(date.fromisoformat(e["onset"]) for e in events)
    clusters = []
    for d in dates:
        if not clusters or (d - clusters[-1][-1]).days > 14:
            clusters.append([d])
        else:
            clusters[-1].append(d)
    return len(clusters)


def _alert_episodes(rows, probs, threshold, last=None):
    order = sorted(range(len(rows)), key=lambda i: (rows[i][1], rows[i][0]))
    alerts = []
    if last is None:
        last = {}
    for i in order:
        d, sym, y, _ = rows[i]
        score = float(max(probs[i, 1], probs[i, 2]))
        if score < threshold:
            continue
        if sym in last and (d - last[sym]).days < 7:
            continue
        side = 1 if probs[i, 1] >= probs[i, 2] else 2
        alerts.append({"date": d, "symbol": sym, "y": y, "side": side, "score": score})
        last[sym] = d
    return alerts


def _choose_threshold(calibration, calibration_probs):
    """Threshold is chosen on an out-of-training chronological calibration slice."""
    directional = np.maximum(calibration_probs[:, 1], calibration_probs[:, 2])
    candidates = sorted(set(float(x) for x in np.quantile(directional, np.linspace(0, 1, 101))))
    candidates.append(float(np.nextafter(np.max(directional), np.inf)))
    exposure = len(set((r[0], r[1]) for r in calibration)) / 365.25
    for threshold in candidates:
        alerts = _alert_episodes(calibration, calibration_probs, threshold)
        false = sum(a["y"] == 0 or a["side"] != a["y"] for a in alerts)
        rate = false / exposure if exposure else math.inf
        if rate <= 3.0:
            return threshold, rate, false, exposure
    raise AssertionError("above-maximum threshold must meet false-alarm ceiling")


def _calibration_split(train, purge_days=17):
    dates = sorted({r[0] for r in train})
    if len(dates) < 2:
        raise RuntimeError("too few dates for calibration")
    start = dates[min(len(dates)-1, max(1, int(len(dates)*.80)))]
    early = [r for r in train if r[0] < start - timedelta(days=purge_days)]
    heldout = [r for r in train if r[0] >= start]
    if not early or not heldout:
        raise RuntimeError("no purged training/calibration rows")
    return early, heldout


def _operational_gate(fold_contexts, events, oos_events):
    alert_rows, thresholds, matched = [], [], set()
    event_map = {}
    for e in events:
        event_map.setdefault(e["symbol"], []).append((date.fromisoformat(e["onset"]), 1 if e["direction"] == "up" else 2))
    all_alerts = []
    last_test_alert = {}  # carry suppression across test-fold boundaries
    for ctx in fold_contexts:
        threshold, train_rate, train_false, exposure = _choose_threshold(ctx["calibration"], ctx["calibration_probs"])
        thresholds.append({"fold": ctx["fold"], "threshold": threshold, "train_false_alarms": train_false,
                           "calibration_asset_years": exposure, "calibration_false_per_asset_year": train_rate})
        alerts = _alert_episodes(ctx["test"], ctx["test_probs"], threshold, last_test_alert)
        for a in alerts:
            hits = [(d, side) for d, side in event_map.get(a["symbol"], []) if a["date"] < d <= a["date"] + timedelta(days=7)]
            hits.sort()
            hit = hits[0] if hits else None
            correct = bool(hit and hit[1] == a["side"])
            lead = (hit[0] - a["date"]).days if correct else None
            row = {"fold": ctx["fold"], "date": a["date"].isoformat(), "symbol": a["symbol"],
                   "predicted_direction": "up" if a["side"] == 1 else "down", "score": a["score"],
                   "matched_onset": hit[0].isoformat() if hit and correct else "", "lead_days": lead if lead is not None else "",
                   "true_alert": correct}
            alert_rows.append(row); all_alerts.append(row)
            if correct:
                matched.add((a["symbol"], hit[0].isoformat()))
    false_count = sum(not a["true_alert"] for a in all_alerts)
    # Asset-year denominator is all scored test exposure, including dates without an alert.
    test_days = set()
    for ctx in fold_contexts:
        test_days.update((r[0], r[1]) for r in ctx["test"])
    exposure = len(test_days) / 365.25
    false_rate = false_count / exposure if exposure else math.inf
    leads = [int(a["lead_days"]) for a in all_alerts if a["lead_days"] != ""]
    precision = len(leads) / len(all_alerts) if all_alerts else 0.0
    recall = len(matched) / len(oos_events) if oos_events else 0.0
    summary = {"threshold_by_fold": thresholds, "alerts": len(all_alerts), "true_alerts": len(leads),
               "false_alerts": false_count, "test_asset_years": exposure, "false_alerts_per_asset_year": false_rate,
               "precision": precision, "event_recall": recall, "events_matched": len(matched),
               "oos_events": len(oos_events), "median_lead_days": float(np.median(leads)) if leads else None,
               "lead_days": leads, "passed": bool(leads and false_rate <= 3.0 and float(np.median(leads)) >= 2.0)}
    return summary, alert_rows


def _posthoc_event_diagnostic(preds, events, B=50000, seed=20261014):
    """Exploratory frozen-prediction check; cannot change the registered primary verdict."""
    keyed = {}
    for r in preds:
        keyed[(r["symbol"], date.fromisoformat(r["date"]), r["model"])] = r
    rows = []
    for e in events:
        onset = date.fromisoformat(e["onset"])
        side = 1 if e["direction"] == "up" else 2
        origins = [onset - timedelta(days=lead) for lead in range(1, 8)]
        origins = [d for d in origins if (e["symbol"], d, "M1") in keyed and (e["symbol"], d, "M2") in keyed
                   and int(keyed[(e["symbol"], d, "M1")]["y"]) == side
                   and int(keyed[(e["symbol"], d, "M2")]["y"]) == side]
        if not origins:
            continue
        cls = "p_up" if side == 1 else "p_down"
        nll = {}
        for model in ("M1", "M2"):
            nll[model] = float(np.mean([-math.log(max(keyed[(e["symbol"], d, model)][cls], 1e-15)) for d in origins]))
        rows.append({"symbol": e["symbol"], "onset": onset, "origins": len(origins),
                     "nll_m1": nll["M1"], "nll_m2": nll["M2"], "improvement_m1_minus_m2": nll["M1"] - nll["M2"]})
    ordered = sorted(rows, key=lambda x: x["onset"])
    clusters = []
    for r in ordered:
        if not clusters or (r["onset"] - clusters[-1][-1]["onset"]).days > 14:
            clusters.append([r])
        else:
            clusters[-1].append(r)
    cluster_means = np.asarray([np.mean([r["improvement_m1_minus_m2"] for r in g]) for g in clusters])
    boot = None
    if cluster_means.size:
        rng = np.random.default_rng(seed)
        reps = np.mean(rng.choice(cluster_means, size=(B, cluster_means.size), replace=True), axis=1)
        boot = {"replicates": B, "seed": seed, "cluster_days": 14,
                "p025": float(np.quantile(reps, .025)), "p975": float(np.quantile(reps, .975))}
    return {"status": "POSTHOC_EXPLORATORY; not used to alter registered verdict",
            "eligible_events": len(rows), "unique_14day_clusters": len(clusters),
            "mean_origins_per_event": float(np.mean([r["origins"] for r in rows])) if rows else None,
            "mean_directional_nll_m1": float(np.mean([r["nll_m1"] for r in rows])) if rows else None,
            "mean_directional_nll_m2": float(np.mean([r["nll_m2"] for r in rows])) if rows else None,
            "event_equal_improvement_m1_minus_m2": float(np.mean([r["improvement_m1_minus_m2"] for r in rows])) if rows else None,
            "cluster_equal_improvement_m1_minus_m2": float(np.mean(cluster_means)) if cluster_means.size else None,
            "cluster_bootstrap_95": boot}


def run(raw: Path, trial_ledger: Path | None = None, *, source="archive", data_root=Path("/data")):
    protocol = _ensure_protocol()
    _check_seal()
    if source == "tape":
        from erf01_tape import load_development
        klines, funding, fund_records, qc, acquisition = load_development(
            data_root, SYMS, DAYS[0], DAYS[1], SEAL)
        _save_acquisition(acquisition)
        parquet_files = _write_input_parquet(klines, fund_records)
        parquet_reused = False
    elif source == "archive":
        acq_path = OUT / "acquisition.json"
        if not acq_path.exists():
            raise FileNotFoundError(f"{acq_path} missing; run --stage fetch first")
        acquisition = json.loads(acq_path.read_text())
        _verify_acquisition(acquisition, raw)
        parquet_files = _parquet_inventory()
        prior_metrics_path = OUT / "metrics.json"
        prior_metrics = json.loads(prior_metrics_path.read_text()) if prior_metrics_path.exists() else {}
        parquet_reused = bool(parquet_files and parquet_files == prior_metrics.get("data", {}).get("parquet_files")
                              and prior_metrics.get("data", {}).get("source") == "binance_archive")
        if parquet_reused:
            klines, funding, fund_records = _read_input_parquet()
            qc = prior_metrics["data"]["rows_by_symbol"]
        else:
            klines, funding, fund_records, qc = _parse_archive(raw)
            parquet_files = _write_input_parquet(klines, fund_records)
    else:
        raise ValueError(f"unknown ERF-01 data source: {source}")
    days, panel = make_panel(klines, funding)
    labels, events, candidates = labels_for(panel, days)
    rows = _rows(panel, labels, days)
    if not rows:
        raise RuntimeError("no complete labeled rows")
    index = {d: i for i, d in enumerate(days)}
    preds, fold_stats, fold_contexts = [], [], []
    model_masks = {"M0": np.arange(len(BASE_NAMES)),
                   "M1": np.arange(len(BASE_NAMES) + len(M1_NAMES)),
                   "M2": np.arange(len(ALL_NAMES))}
    all_dates = set()
    for start, end, name in FOLDS:
        si, ei = index[start], index.get(end, len(days))
        # Strictly purge rows whose outcome could mature on/after the first test date.
        train = [r for r in rows if index[r[0]] < si - 17]
        test = [r for r in rows if si <= index[r[0]] < ei]
        if not train or not test:
            fold_stats.append({"fold": name, "train_rows": len(train), "test_rows": len(test), "status": "empty"})
            continue
        predfold = []
        iters = {}
        m2_test_probs = None
        for model_name, cols in model_masks.items():
            probs, it, _ = _fit_predict(train, test, cols)
            iters[model_name] = it
            if model_name == "M2":
                m2_test_probs = probs
            brier, logloss = _scores(np.asarray([r[2] for r in test]), probs)
            for k, row in enumerate(test):
                predfold.append({"date": row[0].isoformat(), "symbol": row[1], "y": row[2], "model": model_name,
                                 "p_none": float(probs[k, 0]), "p_up": float(probs[k, 1]), "p_down": float(probs[k, 2]),
                                 "brier": float(brier[k]), "logloss": float(logloss[k])})
        cal_early, calibration = _calibration_split(train)
        calibration_probs, _, _ = _fit_predict(cal_early, calibration, model_masks["M2"])
        fold_contexts.append({"fold": name, "calibration": calibration, "test": test,
                              "calibration_probs": calibration_probs, "test_probs": m2_test_probs})
        preds.extend(predfold)
        fold_stats.append({"fold": name, "start": start.isoformat(), "end_exclusive": end.isoformat(),
                           "train_start": min(r[0] for r in train).isoformat(), "train_last": max(r[0] for r in train).isoformat(),
                           "train_rows": len(train), "calibration_rows": len(calibration), "test_rows": len(test), "test_asset_rows": len(test),
                           "iterations": iters, "status": "ok"})
        all_dates.update(r[0] for r in test)
        print(f"fold {name}: train {len(train):,}, test {len(test):,} asset-days", flush=True)
    # Predictions share test target rows; collapse per model/date before paired inference.
    by_model_date = {}
    for r in preds:
        by_model_date.setdefault((r["model"], date.fromisoformat(r["date"])), []).append(r["brier"])
    model_day = {k: float(np.mean(v)) for k, v in by_model_date.items()}
    common_dates = sorted(d for d in all_dates if all((m, d) in model_day for m in ("M0", "M1", "M2")))
    d_m1 = {d: model_day[("M1", d)] - model_day[("M2", d)] for d in common_dates}
    boot = _moving_block_ci(d_m1)
    b1 = float(np.mean([model_day[("M1", d)] for d in common_dates]))
    b2 = float(np.mean([model_day[("M2", d)] for d in common_dates]))
    relative = (b1 - b2) / b1 if b1 else 0.0
    scored_origins = {(r[1], r[0]) for ctx in fold_contexts for r in ctx["test"]}
    event_oos = []
    for e in events:
        onset = date.fromisoformat(e["onset"])
        if any((e["symbol"], onset - timedelta(days=lead)) in scored_origins for lead in range(1, 8)):
            event_oos.append(e)
    up = sum(e["direction"] == "up" for e in event_oos); down = sum(e["direction"] == "down" for e in event_oos)
    event_counts = {}
    for e in event_oos:
        onset = date.fromisoformat(e["onset"])
        fold = next(name for start, end, name in FOLDS if start <= onset < end)
        key = f"{fold}|{e['symbol']}|{e['direction']}"
        event_counts[key] = event_counts.get(key, 0) + 1
    nonempty = sum(x["status"] == "ok" for x in fold_stats)
    sufficient = up >= 30 and down >= 30 and nonempty >= 5
    forecast_gate = sufficient and relative >= .05 and boot["p05"] is not None and boot["p05"] > 0
    operational, alert_rows = (None, [])
    if forecast_gate:
        operational, alert_rows = _operational_gate(fold_contexts, events, event_oos)
    final_gate = bool(forecast_gate and operational and operational["passed"])
    verdict = "INCONCLUSIVE" if not sufficient or final_gate else "NO_EDGE"  # no economic referee has run
    posthoc = _posthoc_event_diagnostic(preds, events)
    metrics = {"verdict": verdict, "scope": "fixed survivor-biased extended-9; daily confirmed q-state transitions; development data only",
               "sealed_boundary": SEAL.isoformat(), "no_economic_test": True,
               "historically_preregistered": False, "independent_confirmation": False,
               "data": {"source": "kepler_tape" if source == "tape" else "binance_archive",
                        "canonical_qc": source == "tape", "requested_first_month": FIRST_MONTH,
                        "requested_last_month": LAST_MONTH, "rows_by_symbol": qc,
                        "archives": acquisition["record_count"], "source_archive_bytes": acquisition["downloaded_bytes"],
                        "source_bytes": acquisition.get("source_bytes", acquisition["downloaded_bytes"]),
                        "sha256_archive_manifest": sha((OUT / "acquisition.json").read_bytes()),
                        "first_date": min(min(v) for v in klines.values() if v).isoformat(),
                        "last_date": max(max(v) for v in klines.values() if v).isoformat(),
                        "parsed_after_seal": False, "parquet_files": parquet_files,
                        "parquet_total_bytes": sum(x["bytes"] for x in parquet_files.values())},
               "counts": {"complete_asset_days": len(rows), "candidate_crossings": len(candidates),
                          "confirmed_onsets_all": len(events), "confirmed_onsets_oos": len(event_oos),
                          "confirmed_oos_by_fold_symbol_direction": event_counts,
                          "confirmed_up_oos": up, "confirmed_down_oos": down,
                          "unique_14day_oos_event_clusters": _cluster_events(event_oos),
                          "unconfirmed_crossings_all": sum(not e["confirmed"] for e in candidates),
                          "oos_folds_nonempty": nonempty},
               "forecast": {"brier_m1": b1, "brier_m2": b2, "brier_improvement_m1_minus_m2": b1 - b2,
                            "relative_brier_improvement": relative, "brier_improvement_block_bootstrap": boot,
                            "n_scored_dates": len(common_dates),
                            "logloss_m1": float(np.mean([r["logloss"] for r in preds if r["model"] == "M1"])),
                            "logloss_m2": float(np.mean([r["logloss"] for r in preds if r["model"] == "M2"]))},
               "folds": fold_stats, "forecast_gate_passed": bool(forecast_gate), "operational_gate": operational,
               "posthoc_event_diagnostic": posthoc,
                "runtime": {"python": sys.version.split()[0], "numpy": np.__version__, "scikit_learn": sklearn.__version__,
                            "pyarrow": pyarrow.__version__, "device": "CPU", "reproduction_command": shlex.join([sys.executable, "scripts/erf01.py", *sys.argv[1:]])},
                "execution": {"parallel_archive_fetch_workers": acquisition.get("workers"), "archive_count_verified": acquisition["record_count"],
                              "archive_errors": len(acquisition["errors"]), "parquet_reused_for_model_run": parquet_reused},
               "economic_stage": "NOT_RUN: forecasting screen is not an economic referee verdict",
               "screening_gate_passed": final_gate,
               "trial_ledger": {"status": "NOT_RECORDED", "trial": None},
               "protocol_sha256": sha((ROOT / "reports" / "erf01_protocol.md").read_bytes()),
               "code_sha256": sha(Path(__file__).read_bytes())}
    if trial_ledger is not None:
        from kepler import ledger  # append-only screening trial; never a referee result
        config = {"experiment": "ERF-01", "symbols": SYMS, "first": FIRST_MONTH,
                  "last": LAST_MONTH, "models": ["M0", "M1", "M2"], "protocol_sha256": metrics["protocol_sha256"]}
        fingerprint = sha(json.dumps([config, metrics["code_sha256"], metrics["data"]["sha256_archive_manifest"]],
                                     sort_keys=True).encode())
        entry = ledger.record(trial_ledger, "screen", "ERF-01 early regime onset", config,
                              metrics["code_sha256"], metrics["data"]["sha256_archive_manifest"],
                              score=float(relative), event_id=fingerprint)
        metrics["trial_ledger"] = {"status": "SCREEN_ONLY", "trial": entry.get("trial"),
                                   "path": str(trial_ledger), "event_id": fingerprint}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    with (OUT / "events.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["symbol", "onset", "direction", "confirmed", "confirmation"], lineterminator="\n"); w.writeheader(); w.writerows(events)
    with (OUT / "candidates.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["symbol", "onset", "direction", "confirmed", "confirmation"], lineterminator="\n"); w.writeheader(); w.writerows(candidates)
    with (OUT / "oos_predictions.csv").open("w", newline="") as f:
        fields = ["date", "symbol", "y", "model", "p_none", "p_up", "p_down", "brier", "logloss"]
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n"); w.writeheader(); w.writerows(preds)
    with (OUT / "alerts.csv").open("w", newline="") as f:
        fields = ["fold", "date", "symbol", "predicted_direction", "score", "matched_onset", "lead_days", "true_alert"]
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n"); w.writeheader(); w.writerows(alert_rows)
    _write_report(metrics)
    print(json.dumps({"verdict": verdict, "events_up": up, "events_down": down, "relative_brier_improvement": relative,
                      "bootstrap_lower_one_sided": boot["p05"], "forecast_gate_passed": bool(forecast_gate),
                      "operational_gate_passed": bool(operational and operational["passed"]), "economic_stage_run": False}, indent=2))
    return metrics


def _fmt(x, nd=4):
    return "n/a" if x is None else f"{x:.{nd}f}"


def _ci_text(b):
    if not b:
        return "unavailable (no eligible events)"
    lo, hi = b["p025"], b["p975"]
    return f"[{lo:.4f}, {hi:.4f}]" + (" (includes zero)" if lo <= 0 <= hi else " (excludes zero)")


def _write_report(m):
    f = m["forecast"]; c = m["counts"]; data = m["data"]
    funding_extreme = {s: v["funding_extreme_abs_gt_1pct"] for s, v in data["rows_by_symbol"].items() if v.get("funding_extreme_abs_gt_1pct")}
    lo = f["brier_improvement_block_bootstrap"].get("p05")
    ph = m["posthoc_event_diagnostic"]
    txt = [f"# ERF-01 — {m['verdict']}", "", "Historical, survivor-biased nine-contract daily onset-forecast test. This is not independent confirmatory evidence.", "",
           "## Kepler prior evidence and independence", "",
           "- No prior Kepler report directly tested confirmed directional-onset hazard; adjacent results are not H1-A evidence.",
           "- Prior G2 reported NO_EDGE; the 88-configuration search had no validation candidate after multiplicity controls. The ensemble-decay test was also below its DSR threshold. These support a skeptical prior, not an automatic rejection of this target.",
           "- Existing trend diagnostics were in-sample and did not find reliable time-series IC; prior Kepler dates are extensively seen and cannot serve as independent confirmation here.",
           "- Trial inventory is inconsistent across snapshots: `reports/trial_inventory.md` records 4,117 repository / 5,434 Volume rows (2026-10-03), while later `TASKS.md` records repo N=5,091. This is not a reconciled statistical N. ERF-01 makes no DSR/independent-edge claim.", "",
           f"Protocol: `reports/erf01_protocol.md` (SHA-256 `{m['protocol_sha256']}`). Code SHA-256 `{m['code_sha256']}`.",
           f"Data: Binance USDT-M monthly daily klines + funding, {data['first_date']} through {data['last_date']} (strictly before sealed boundary {m['sealed_boundary']}); {data['archives']} verified archives ({data['source_archive_bytes']:,} compressed bytes). No G3 data accessed.", "",
           "## Primary results", "", "| Measure | Result |", "|---|---:|",
           f"| Confirmed OOS onsets (up / down) | {c['confirmed_up_oos']} / {c['confirmed_down_oos']} |",
           f"| OOS 14-day event clusters | {c['unique_14day_oos_event_clusters']} |",
           f"| Non-empty rolling-origin folds | {c['oos_folds_nonempty']} / 7 |",
           f"| Scored calendar dates | {f['n_scored_dates']} |",
           f"| M1 multiclass Brier | {f['brier_m1']:.6f} |", f"| M2 multiclass Brier | {f['brier_m2']:.6f} |",
           f"| Relative Brier improvement (M1→M2) | {100*f['relative_brier_improvement']:.2f}% |",
           f"| Paired date-block bootstrap mean improvement (M1−M2, signed) | {f['brier_improvement_m1_minus_m2']:.8f} |",
           f"| Two-sided 95% block-bootstrap interval | [{f['brier_improvement_block_bootstrap']['p025']}, {f['brier_improvement_block_bootstrap']['p975']}] |",
           f"| One-sided 95% block-bootstrap lower bound | {lo if lo is not None else 'unavailable'} |",
           f"| M1 / M2 log loss | {f['logloss_m1']:.6f} / {f['logloss_m2']:.6f} |", "",
           "## Post-hoc event-level diagnostic (exploratory only)", "",
           f"- {ph['status']}.",
           f"- Directional NLL/event M1 vs. M2: {_fmt(ph['mean_directional_nll_m1'])} / {_fmt(ph['mean_directional_nll_m2'])}; event-equal improvement M1−M2: {_fmt(ph['event_equal_improvement_m1_minus_m2'])}.",
           f"- Equal-weight 14-day clusters: {ph['unique_14day_clusters']}; cluster-bootstrap 95% interval: {_ci_text(ph['cluster_bootstrap_95'])}.", "",
           "## Execution record", "",
           f"- Parallel fetch verified {m['execution']['archive_count_verified']}/{data['archives']} source archives using {m['execution']['parallel_archive_fetch_workers']} workers; archive/checksum errors: {m['execution']['archive_errors']}. Model run reused Parquet: {m['execution']['parquet_reused_for_model_run']}.",
           f"- Runtime: Python {m['runtime']['python']}, NumPy {m['runtime']['numpy']}, scikit-learn {m['runtime']['scikit_learn']}, PyArrow {m['runtime']['pyarrow']} ({m['runtime']['device']}). Reproduce with `{m['runtime']['reproduction_command']}`.",
           "",
           "## Fold record", "", "| Test origin | Train rows | Test asset-days | Status |", "|---|---:|---:|---|"]
    for x in m["folds"]:
        txt.append(f"| {x['fold']} | {x.get('train_rows', 0)} | {x.get('test_asset_rows', 0)} | {x['status']} |")
    if m.get("operational_gate"):
        op = m["operational_gate"]
        txt += ["", "## Conditional operational alert gate", "",
                f"- Alert episodes / true / false: {op['alerts']} / {op['true_alerts']} / {op['false_alerts']}.",
                f"- Precision / confirmed-event recall: {op['precision']:.3f} / {op['event_recall']:.3f}.",
                f"- False alerts per asset-year: {op['false_alerts_per_asset_year']:.3f}; median lead: {op['median_lead_days']} days.",
                f"- Operational gate passed: {op['passed']}.", ""]
    txt += ["", "## Protocol checks and limits", "",
            f"- Input Parquet (local ignored data archive): `{data['parquet_files']}`; total {data['parquet_total_bytes']} bytes. Parquet hashes are in `metrics.json`; source archive hashes are in `acquisition.json`.",
            f"- Dataset QC by symbol: `{data['rows_by_symbol']}`. Bad OHLC/duplicate day counts and missing archive errors are in `reports/erf01_data/acquisition.json` / `metrics.json`.",
            f"- Confirmed candidate events total {c['confirmed_onsets_all']}; OOS-direction floor is 30 per direction (observed {c['confirmed_up_oos']} up / {c['confirmed_down_oos']} down); {c['unconfirmed_crossings_all']} unconfirmed candidate crossings were recorded.",
            f"- Funding QC: events with |rate| > 1% by symbol: {funding_extreme or 'none'}; preserved as source observations, not silently corrected.",
            f"- Verdict {m['verdict']}: event floor {'met' if c['confirmed_up_oos'] >= 30 and c['confirmed_down_oos'] >= 30 else 'NOT met'} (up {c['confirmed_up_oos']}/30, down {c['confirmed_down_oos']}/30); M2 point improvement {100*f['relative_brier_improvement']:.2f}%; forecast gate passed: {m['forecast_gate_passed']}; operational gate run: {m['operational_gate'] is not None}.",
            "- Feature rows and labels are timestamped causally; training outcome labels are purged strictly before each test origin. H1-B after-onset detections do not count as positive forecasts.",
            "- The historical date range has prior Kepler exposure. Walk-forward folds prevent fitting to the future within each split but do not restore pristine data status.",
            "- The fixed nine are current-survivor contracts; results do not generalize to delisted/universe-wide assets.",
            f"- Economic test is gated on forecasting and operational skill (forecast gate passed: {m['forecast_gate_passed']}; operational gate passed: {bool(m['operational_gate'] and m['operational_gate']['passed'])}). Kepler's Numba referee was not invoked and no live orders were sent. No production/core code was changed.",
            "- Detailed reproducibility artifacts: `reports/erf01_data/metrics.json`, `events.csv`, `candidates.csv`, `oos_predictions.csv`, and `acquisition.json`.", ""]
    report_text = "\n".join(txt) + "\n"
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.md").write_text(report_text)
    if OUT.is_relative_to(ROOT):
        (ROOT / "reports" / "erf01.md").write_text(report_text)


def self_test():
    # Lookahead mutant: changing future prices must not change any past q/features.
    n = 260; rng = np.random.default_rng(7); r = rng.normal(0, .01, n)
    close = 100 * np.exp(np.cumsum(r)); qv = np.exp(rng.normal(10, .3, n))
    def causal_features(c, v):
        rr = np.r_[np.nan, np.diff(np.log(c))]
        ss, aa, qq = _roll_sum(rr, 20), _roll_sum(np.abs(rr), 20), _roll_sum(rr*rr, 20)
        z = ss / np.sqrt(qq + 1e-12); er = np.abs(ss) / (aa + 1e-12)
        return np.column_stack([z, er, np.sqrt(_roll_sum(rr*rr, 5)), _roll_median_log_ratio(v, 20)])
    a = causal_features(close, qv); k = 190
    close2, qv2 = close.copy(), qv.copy(); close2[k+1:] *= np.exp(rng.normal(0, 2, n-k-1)); qv2[k+1:] *= 1000
    b = causal_features(close2, qv2)
    assert np.array_equal(a[:k+1], b[:k+1], equal_nan=True)
    # End-to-end feature cutoff mutant: future prices, volume and funding cannot alter past panel features.
    test_dates = [DAYS[0] + timedelta(days=i) for i in range(240)]
    test_kl, test_fund = {s: {} for s in SYMS}, {s: [] for s in SYMS}
    for j, sym in enumerate(SYMS):
        rg = np.random.default_rng(100 + j)
        rr = rg.normal(0, .015, len(test_dates))
        cc = 100 * np.exp(np.cumsum(rr)); vv = np.exp(rg.normal(8, .2, len(test_dates)))
        for i, d in enumerate(test_dates):
            oo = cc[i-1] if i else cc[i]
            test_kl[sym][d] = (oo, max(oo, cc[i]) * 1.002, min(oo, cc[i]) * .998, cc[i], vv[i],
                               int(datetime.combine(d, datetime.min.time(), timezone.utc).timestamp() * 1000), vv[i] * cc[i])
            for hour in (8, 16):
                ts = int(datetime.combine(d, datetime.min.time(), timezone.utc).timestamp() * 1000) + hour * 3600000
                test_fund[sym].append((ts, float(rg.normal(0, .0002))))
    _, past_panel = make_panel(test_kl, test_fund)
    mutated_kl = {s: dict(v) for s, v in test_kl.items()}
    mutated_fund = {s: list(v) for s, v in test_fund.items()}
    cutoff = 190
    cutoff_close_ms = int(datetime.combine(test_dates[cutoff] + timedelta(days=1), datetime.min.time(), timezone.utc).timestamp() * 1000)
    for sym in SYMS:
        for d in test_dates[cutoff+1:]:
            row = mutated_kl[sym][d]
            mutated_kl[sym][d] = tuple(x * 2 if j < 6 else x * 100 for j, x in enumerate(row))
        mutated_fund[sym] = [(ts, rate + .01 if ts >= cutoff_close_ms else rate) for ts, rate in mutated_fund[sym]]
    _, future_panel = make_panel(mutated_kl, mutated_fund)
    for sym in SYMS:
        assert np.array_equal(past_panel[sym]["features"][:cutoff+1], future_panel[sym]["features"][:cutoff+1], equal_nan=True)
    # Onset requires prior ten q=0 and persistence confirmed on >=8 of the next ten.
    # Checked by a hand-constructed q stream using the same event criterion.
    q = np.zeros(40); q[12:] = 1; q[21:23] = 0
    assert np.count_nonzero(q[13:23] == 1) == 8
    assert np.count_nonzero(q[13:23] == 1) >= 8 and np.all(q[2:12] == 0)
    qstream = np.zeros(40); qstream[10:18] = 1; qstream[18:20] = 0; qstream[20:] = 1
    test_days = [DAYS[0] + timedelta(days=i) for i in range(40)]
    dummy = {s: {"q": qstream.copy()} for s in SYMS}
    ys, evs, cands = labels_for(dummy, test_days)
    assert len(evs) == len(SYMS) and all(e["confirmed"] for e in evs)
    assert all(ys[s][3] == 1 and ys[s][4] == 1 and ys[s][10] == 0 for s in SYMS)
    qstream[18:22] = 0
    dummy = {s: {"q": qstream.copy()} for s in SYMS}
    ys, evs, cands = labels_for(dummy, test_days)
    assert not evs and len(cands) == len(SYMS) and all(ys[s][3] == 0 for s in SYMS)
    print("ERF-01 self-test: future-corruption + confirmed/failed onset labels PASS")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["fetch", "run", "all", "self-test"], default="all")
    ap.add_argument("--raw-root", type=Path, default=Path("/tmp/kepler_erf01_raw"))
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--trial-ledger", type=Path, default=None,
                    help="append-only Kepler screening-trial ledger (not a referee result)")
    ap.add_argument("--source", choices=["archive", "tape"], default="archive")
    ap.add_argument("--data-root", type=Path, default=Path("/data"))
    ap.add_argument("--out-root", type=Path, default=None)
    ap.add_argument("--parquet-root", type=Path, default=None)
    args = ap.parse_args()
    global OUT, PARQUET_OUT
    if args.out_root is not None:
        OUT = args.out_root
    elif args.source == "tape":
        OUT = args.data_root / "erf01" / "results"
    if args.parquet_root is not None:
        PARQUET_OUT = args.parquet_root
    elif args.source == "tape":
        PARQUET_OUT = args.data_root / "erf01" / "parquet"
    if args.stage == "self-test":
        self_test(); return
    _ensure_protocol()
    _check_seal()
    if args.stage in ("fetch", "all") and args.source == "archive":
        fetch(args.raw_root, workers=args.workers)
    elif args.stage == "fetch":
        raise ValueError("fetch is only supported for --source archive")
    if args.stage in ("run", "all"):
        run(args.raw_root, trial_ledger=args.trial_ledger, source=args.source, data_root=args.data_root)


if __name__ == "__main__":
    main()