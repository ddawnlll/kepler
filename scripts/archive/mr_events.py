"""KEŞİF (ön kayıtsız; kullanıcı kararı 2026-10-05): aşırı z sonrası ileri getiri olay çalışması. Soru: saatlik bantta aşırı hareketten sonra fiyat h saat içinde geri dönüyor mu, nerede (coin, dönem, rejim, ADX, hacim şoku)?
Olay: |z| >= 2 olan saat kapanışı (z = (C - SMA_n) / std_n, n = 20 ya da 80 saat); sinyal yönü = geri dönüş (-sign z). Giriş = SONRAKİ barın açılışı (işlem yapılabilir), çıkış = h saat sonra açılış.
Çıktı: geri dönüş yönlü ortalama getiri (bps; pozitif = geri dönüş var), t (olay ortalaması / gün-kümeli standart hata), olay sayısı. Maliyet eşiği: fee 10 + slip 2 = 12 bps gidiş-dönüş.
Kullanım: python scripts/mr_events.py --out /data/mr_events"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ensemble as E  # noqa: E402

from kepler import indicators as ix, robust  # noqa: E402

HS = (1, 2, 4, 8, 24)
BIG = {"BTCUSDT", "ETHUSDT"}


def events(sym: str, kl: pd.DataFrame, n: int, reg: pd.Series) -> pd.DataFrame:
    c, o = kl.close, kl.open
    sd = c.rolling(n).std(ddof=0)
    z = ((c - c.rolling(n).mean()) / sd.where(sd > 0))
    adx = ix.adx(kl)["adx"]
    vr = kl.volume / kl.volume.rolling(24).mean().shift(1)
    sel = z.abs() >= 2.0
    d = pd.DataFrame(dict(z=z, adx=adx, vr=vr), index=kl.index)[sel]
    d["sign"] = -np.sign(d.z)
    entry = o.shift(-1)[sel]  # sonraki açılış
    for h in HS:
        d[f"r{h}"] = d.sign * (o.shift(-1 - h)[sel] / entry - 1) * 1e4
    d["sym"], d["day"] = sym, d.index.normalize()
    d["regime"] = reg.reindex(d.day).to_numpy()
    d["era"] = np.where(d.index < "2022-01-01", "2020-21", "2022-26")
    d["size"] = "BTC/ETH" if sym in BIG else "alt"
    d["trend"] = np.where(d.adx > 25, "ADX>25", "ADX<=25")
    d["volspike"] = np.where(d.vr > 2.0, "hacim>2x", "hacim<=2x")
    return d.dropna(subset=[f"r{HS[-1]}"])


def table(df: pd.DataFrame, by) -> list:
    rows = []
    for key, g in df.groupby(by):
        row = dict(key=key if isinstance(key, str) else "/".join(map(str, key)), n=len(g))
        for h in HS:
            r = g[f"r{h}"]
            mu = float(r.mean())
            se = float(np.sqrt(((r - mu).groupby(g["day"]).sum() ** 2).sum()) / len(r))  # olay ortalaması için gün-kümeli standart hata (aynı günün olayları ilişkili)
            row[f"r{h}"], row[f"t{h}"] = mu, (mu / se if se > 0 else None)
        rows.append(row)
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/data/mr_events")
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    E.load(E.EXT, [("/data/pre2022", None, E.SPLIT), ("/data", E.SPLIT, None)])
    reg = robust.regime(E.D["BTCUSDT"]["kl"].close.resample("1D").last())
    res = {}
    for n in (20, 80):
        df = pd.concat([events(s, E.D[s]["kl"], n, reg) for s in E.EXT])
        df = df[(df.index >= "2020-04-01") & (df.index < "2026-04-01")]
        res[f"n{n}"] = dict(all=table(df.assign(k="hepsi"), "k"), **{b: table(df, b) for b in ("size", "era", "regime", "trend", "volspike", "sym")},
                            era_x_trend=table(df, ["era", "trend"]), size_x_vol=table(df, ["size", "volspike"]))
        print(f"n={n}: {len(df)} olay", flush=True)
    Path(a.out, "events.json").write_text(json.dumps(res, default=str))
