"""Binance arşiv istemcisi (data.binance.vision): liste, indirme, sha256, idempotent, devam ettirilebilir.

Mühür koruması: DEV_END'den sonraki aylar hiçbir yoldan indirilmez (fetch reddeder).
"""
import hashlib
import io
import re
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests

S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
CDN = "https://data.binance.vision"
BASE = "data/futures/um/monthly"
DEV_END = "2026-03"  # son dev ayı (bugünden 6 ay önce = 2026-04-01 sınırı); sonrası mühürlü


NAMES = {  # başlıksız dosyalar için sütun adları (sütun sayısına göre)
    12: ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "count",
         "taker_buy_volume", "taker_buy_quote_volume", "ignore"],
    3: ["calc_time", "funding_interval_hours", "last_funding_rate"],
}


class SealedError(Exception):
    """Mühürlü döneme ait bir dosya istendi."""


class ChecksumError(Exception):
    pass


def _get(url: str, **kw) -> requests.Response:
    return requests.get(url, timeout=60, **kw)


def list_bucket(prefix: str, delimiter: str = "/") -> tuple[list[str], list[str]]:
    """(keys, common_prefixes) — S3 ListBucketResult, `marker` ile sayfalama."""
    keys, prefixes, marker = [], [], ""
    while True:
        for i in range(6):  # liste çağrıları da geçici hatada yeniden denenir
            try:
                r = _get(S3, params={"delimiter": delimiter, "prefix": prefix, "marker": marker})
                r.raise_for_status()
                break
            except requests.RequestException:
                if i == 5:
                    raise
                time.sleep(min(2 ** i, 20))
        xml = r.text  # düz regex: S3 XML yanıtı basit; XML ayrıştırıcı saldırı yüzeyi açmaya değmez
        keys += re.findall(r"<Key>([^<]+)</Key>", xml)
        prefixes += re.findall(r"<CommonPrefixes><Prefix>([^<]+)</Prefix>", xml)
        if "<IsTruncated>true</IsTruncated>" not in xml:
            return keys, prefixes
        nm = re.search(r"<NextMarker>([^<]+)</NextMarker>", xml)
        marker = nm.group(1) if nm else (keys[-1] if keys else prefixes[-1])


def key(kind: str, sym: str, month: str, interval: str = "1h") -> str:
    if kind == "fundingRate":
        return f"{BASE}/fundingRate/{sym}/{sym}-fundingRate-{month}.zip"
    return f"{BASE}/{kind}/{sym}/{interval}/{sym}-{interval}-{month}.zip"


def symbols() -> list[str]:
    """Kalıcı (perpetual) USDT-M sembolleri; teslimli kontratlar (BTCUSDT_250627) hariç."""
    _, pre = list_bucket(f"{BASE}/klines/")
    return sorted(p.split("/")[-2] for p in pre if p.split("/")[-2].endswith("USDT"))


def months(kind: str, sym: str, interval: str = "1h") -> list[str]:
    """Arşivde bulunan aylar (yalnızca DEV_END'e kadar; mühürlü ay adları bile döndürülmez)."""
    sub = f"{sym}/" if kind == "fundingRate" else f"{sym}/{interval}/"
    keys, _ = list_bucket(f"{BASE}/{kind}/{sub}")
    found = (re.search(r"(\d{4}-\d{2})\.zip$", k) for k in keys)
    return sorted(m.group(1) for m in found if m and m.group(1) <= DEV_END)


def _check_dev(k: str) -> None:
    m = re.search(r"(\d{4}-\d{2})\.zip$", k)
    if not m or m.group(1) > DEV_END:
        raise SealedError(f"{k}: mühürlü dönem veya tanınmayan ay (> {DEV_END}); indirilmez")


def fetch(k: str, root: Path, retries: int = 4) -> Path:
    """Zip'i indirir, .CHECKSUM ile sha256 doğrular. Doğrulanmış dosya varsa dokunmaz (idempotent)."""
    _check_dev(k)
    dst = Path(root) / "raw" / k
    dst.parent.mkdir(parents=True, exist_ok=True)
    err = None
    side = dst.with_name(dst.name + ".sha256")
    if dst.exists() and side.exists() and hashlib.sha256(dst.read_bytes()).hexdigest() == side.read_text():
        return dst  # önceki indirmede doğrulanmış; ağa gitmeden yerel bütünlük kontrolü yeterli
    for i in range(retries):
        try:
            want = _get(f"{CDN}/{k}.CHECKSUM")
            want.raise_for_status()
            sha = want.text.split()[0].lower()
            if dst.exists() and hashlib.sha256(dst.read_bytes()).hexdigest() == sha:
                return dst
            r = _get(f"{CDN}/{k}")
            r.raise_for_status()
            if hashlib.sha256(r.content).hexdigest() != sha:
                raise ChecksumError(f"{k}: sha256 uyuşmuyor")
            tmp = dst.with_suffix(".part")
            tmp.write_bytes(r.content)
            tmp.replace(dst)
            dst.with_name(dst.name + ".sha256").write_text(sha)
            return dst
        except (requests.RequestException, ChecksumError) as e:  # bozuk dosya diske yazılmaz, yeniden denenir
            err = e
            time.sleep(min(2 ** i, 10))
    raise ChecksumError(f"{k}: {retries} denemede indirilemedi: {err}")


def fetch_many(keys: list[str], root: Path, workers: int = 32) -> list[Path]:
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(lambda k: fetch(k, root), keys))


def read_zip_csv(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        raw = z.read(z.namelist()[0])
    df = pd.read_csv(io.BytesIO(raw))
    if df.columns[0].lstrip("-").isdigit():  # başlıksız eski dosyalar: sütun sayısından adlandır
        names = NAMES.get(df.shape[1])
        if names is None:
            raise ValueError(f"{path}: başlık yok ve {df.shape[1]} sütun tanınmıyor")
        df = pd.read_csv(io.BytesIO(raw), header=None, names=names)
    return df
