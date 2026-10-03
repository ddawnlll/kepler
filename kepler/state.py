"""Market state servisi v0 (BACKTEST §15). Yalnızca ilk uzmanın (Zone Fade, reports/zone_fade_protocol.md) istediği özellikleri sunar:
1d ATR (Wilder) + impuls genliği, 3d fractal swing seviyeleri (onaylı), 4h karar ızgarası ve lazy 1h hacim profili (POC/VAH/VAL). İstenmeyen hiçbir şey hesaplanmaz.

Girdi saatlik OHLCV (`tape.load` çıktısı; mühür sınırını aşan veri reddedilir). Zaman dilimleri 1970-01-01 çıpalı (3d = gün_no // 3), bar indeksi = açılış, kapanış = açılış + tf.
Karar anı t = tamamlanmış 4h barın kapanışı; yalnızca kapanışı <= t olan barlar görülür (oluşmakta olan bar servise girmez). Eksik saatlik bar sayısı view başına `missing`'de raporlanır."""
import hashlib
from dataclasses import asdict, dataclass
from typing import Callable

import numpy as np
import pandas as pd

from kepler import ledger, risk
from kepler.qc import SEAL_START

TF_HOURS = {"1h": 1, "4h": 4, "1d": 24, "3d": 72}
EPOCH = pd.Timestamp("1970-01-01", tz="UTC")
HOUR_NS = 3_600_000_000_000
STATS = dict(builds=0)  # önbellek testi için: gerçek hesap sayısı


def ns(x) -> np.ndarray:
    return pd.DatetimeIndex(x).as_unit("ns").asi8.copy()  # pandas 3: indeks çözünürlüğü ns olmayabilir


@dataclass(frozen=True)
class View:
    """tf ∈ {1h,4h,1d,3d}; lookback (bar): view ancak bu kadar tamamlanmış bar birikince geçerli, pencereli özellik (profile) pencereyi bu kadar bar alır; features: "atr:14", "impulse:20", "swing:2", "profile:100", "bars"."""
    tf: str
    lookback: int = 0
    features: tuple = ()


@dataclass(frozen=True)
class StateSpec:
    sym: str
    views: tuple
    context: tuple = ()

    @property
    def id(self) -> str:
        return ledger.sha(asdict(self))


@dataclass
class AsOf:
    """Karar anı t'de servis çıktısı. sw_hi / sw_lo: t'de onaylı swing fiyatları; profile(): [t - lookback bar, t) saatlik barlardan (lazy, önbellekli)."""
    t: pd.Timestamp
    widx: pd.Timestamp  # kararın yazılacağı saatlik bar (4h barın son mevcut saati)
    o: float
    h: float
    l: float
    c: float
    atr: float
    imp_up: float  # ATR biriminde yukarı impuls genliği (0 = yok)
    imp_dn: float
    valid: bool
    sw_hi: np.ndarray
    sw_lo: np.ndarray
    profile: Callable[[], dict]


def bars(kl: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Takvim çıpalı tf barları (UTC; eksik takvim barı NaN satırı). Sütunlar: open high low close volume n (mevcut saatlik bar sayısı) last (barın son mevcut saatlik zamanı). index = açılış."""
    h = TF_HOURS[tf]
    key = np.asarray((kl.index - EPOCH) // pd.Timedelta(hours=h))
    g = kl.groupby(key)
    out = pd.DataFrame(dict(open=g.open.first(), high=g.high.max(), low=g.low.min(), close=g.close.last(), volume=g.volume.sum(), n=g.close.count()))
    out["last"] = pd.Series(kl.index, index=key).groupby(level=0).last()
    out = out.reindex(np.arange(key.min(), key.max() + 1))
    out["n"] = out.n.fillna(0).astype(int)
    out.index = (EPOCH + pd.to_timedelta(out.index.to_numpy() * h, unit="h")).as_unit("ns")
    return out


def _profile(H, L, V, bins: int) -> dict:
    """Hacim profili: 100 eşit kutu (min low -> max high); her barın hacmi [low, high]'in kestiği kutulara EŞİT dağıtılır (kutu = ⌊(fiyat - min)/w⌋, üst sınıra kısılır). POC = en yüksek
    hacimli kutunun merkezi (eşitlikte ilk/alt). Value area: POC'tan her adımda hacmi büyük komşu kutuyu (eşitlikte alt) ekle, toplamın %70'ine ulaşana kadar; VAL/VAH = aralığın alt/üst kenarı."""
    pmin, pmax = float(L.min()), float(H.max())
    w = (pmax - pmin) / bins
    if w <= 0:
        return dict(poc=pmin, vah=pmin, val=pmin, lo=pmin, hi=pmax, width=0.0)
    bl = np.clip(np.floor((L - pmin) / w).astype(int), 0, bins - 1)
    bh = np.clip(np.floor((H - pmin) / w).astype(int), 0, bins - 1)
    bl, bh = np.minimum(bl, bh), np.maximum(bl, bh)  # bozuk bar (high < low) sıfıra bölme üretmesin
    per = V / (bh - bl + 1)
    vol = np.cumsum(np.bincount(bl, weights=per, minlength=bins + 1) - np.bincount(bh + 1, weights=per, minlength=bins + 1))[:bins]
    poc = int(np.argmax(vol))
    a = b = poc
    acc, goal = vol[poc], 0.7 * vol.sum()
    while acc < goal and (a > 0 or b < bins - 1):
        up, dn = (vol[b + 1] if b < bins - 1 else -1.0), (vol[a - 1] if a > 0 else -1.0)
        if up > dn:
            b, acc = b + 1, acc + up
        else:
            a, acc = a - 1, acc + dn
    return dict(poc=pmin + (poc + 0.5) * w, vah=pmin + (b + 1) * w, val=pmin + a * w, lo=pmin, hi=pmax, width=w)


class MarketState:
    def __init__(self, spec: StateSpec, kl: pd.DataFrame):
        if kl.index[-1] >= SEAL_START:
            raise ValueError("mühürlü dönem verisi servise giremez")
        self.spec, self.id = spec, spec.id
        kl = kl[["open", "high", "low", "close", "volume"]].astype(float)
        f = {v.tf: (v, {x.split(":")[0]: [int(a) for a in x.split(":")[1:]] for x in v.features}) for v in spec.views}
        if any(tf not in TF_HOURS for tf in f) or any(k not in ("atr", "impulse", "swing", "profile", "bars") for _, ft in f.values() for k in ft):
            raise ValueError("v0 yalnızca atr, impulse, swing, profile, bars özelliklerini ve 1h/4h/1d/3d view'larını sunar")
        end = kl.index[-1] + pd.Timedelta("1h")
        self.missing = {}
        for tf in f:
            b = bars(kl, tf)
            done = b[b.index + pd.Timedelta(hours=TF_HOURS[tf]) <= end]
            self.missing[tf] = int((TF_HOURS[tf] * len(done) - done.n.sum()))
        # 4h karar ızgarası: tamamlanmış, en az bir saatlik barı olan 4h barlar
        b4 = bars(kl, "4h")
        b4 = b4[(b4.n > 0) & (b4.index + pd.Timedelta(hours=4) <= end)]
        self.t = ns(b4.index + pd.Timedelta(hours=4))
        self.widx = pd.DatetimeIndex(b4["last"])
        self.pos1h = kl.index.get_indexer(self.widx)
        self.o, self.h, self.l, self.c = (b4[k].to_numpy() for k in ("open", "high", "low", "close"))
        n = len(self.t)
        self.atr, self.imp_up, self.imp_dn = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
        self.valid = np.ones(n, dtype=bool)
        self.k_hi, self.k_lo = np.zeros(n, dtype=int), np.zeros(n, dtype=int)
        self.sw = dict(hi=(np.empty(0), np.empty(0, dtype=np.int64)), lo=(np.empty(0), np.empty(0, dtype=np.int64)))
        if "1d" in f:
            v, ft = f["1d"]
            d = bars(kl, "1d")
            d = d[(d.n > 0) & (d.index + pd.Timedelta(hours=24) <= end)]
            if not len(d):
                raise ValueError("tamamlanmış günlük bar yok")
            j = np.searchsorted(ns(d.index + pd.Timedelta(hours=24)), self.t, side="right") - 1  # t'de tamamlanmış son gün
            self.valid &= (j + 1) >= v.lookback
            if "atr" in ft:
                atr = risk.wilder_n(d, ft["atr"][0]).to_numpy()
                self.atr = np.where(j >= 0, atr[np.maximum(j, 0)], np.nan)
                if "impulse" in ft:
                    up, dn = np.full(len(d), np.nan), np.full(len(d), np.nan)
                    hi, lo, L = d.high.to_numpy(), d.low.to_numpy(), ft["impulse"][0]
                    for q in range(L - 1, len(d)):
                        hw, lw = hi[q - L + 1:q + 1], lo[q - L + 1:q + 1]
                        a, m = int(np.argmax(hw)), int(np.argmin(lw))  # eşitlikte ilk (kısıtlayıcı: önceki bar sayısı az)
                        up[q] = (hw[a] - lw[:a].min()) / atr[q] if a > 0 else 0.0  # max'tan ÖNCEKİ min low (max barı hariç)
                        dn[q] = (hw[:m].max() - lw[m]) / atr[q] if m > 0 else 0.0
                    self.imp_up, self.imp_dn = (np.where(j >= 0, x[np.maximum(j, 0)], np.nan) for x in (up, dn))
        if "3d" in f and "swing" in f["3d"][1]:
            k = f["3d"][1]["swing"][0]
            s3 = bars(kl, "3d")
            for name, x, cmp in (("hi", s3.high.to_numpy(), np.greater), ("lo", s3.low.to_numpy(), np.less)):
                m = len(x)
                ok = np.zeros(m, dtype=bool)
                if m > 2 * k:
                    ok[k:m - k] = np.all([cmp(x[k:m - k], x[k + s:m - k + s]) for s in range(-k, k + 1) if s], axis=0)  # NaN (eksik bar) karşılaştırması False
                i = np.flatnonzero(ok)
                conf = ns(s3.index[np.minimum(i + k, m - 1)] + pd.Timedelta(hours=72))  # sağdaki k bar kapanınca onaylanır
                self.sw[name] = (x[i], conf)
            self.k_hi = np.searchsorted(self.sw["hi"][1], self.t, side="right")
            self.k_lo = np.searchsorted(self.sw["lo"][1], self.t, side="right")
        self._p = None
        if "1h" in f and "profile" in f["1h"][1]:
            v, ft = f["1h"]
            self._p = (ns(kl.index), kl.high.to_numpy(), kl.low.to_numpy(), kl.volume.to_numpy(), v.lookback, ft["profile"][0])
            self.valid &= self._p[0][0] <= self.t - v.lookback * HOUR_NS  # pencere dolu: veri en az lookback bar öncesinden başlar
        self._cache: dict[int, dict] = {}

    def profile_at(self, t_ns: int) -> dict:
        """[t - lookback bar, t) saatlik barlardan hacim profili (kapanışı <= t); lazy, t başına bir kez hesaplanır."""
        if t_ns not in self._cache:
            ts, H, L, V, lb, bins = self._p
            lo, hi = np.searchsorted(ts, t_ns - lb * HOUR_NS, side="left"), np.searchsorted(ts, t_ns, side="left")
            self._cache[t_ns] = _profile(H[lo:hi], L[lo:hi], V[lo:hi], bins)
        return self._cache[t_ns]

    def at(self, i: int) -> AsOf:
        t = int(self.t[i])
        return AsOf(pd.Timestamp(t, unit="ns", tz="UTC"), self.widx[i], self.o[i], self.h[i], self.l[i], self.c[i], self.atr[i], self.imp_up[i], self.imp_dn[i], bool(self.valid[i]),
                    self.sw["hi"][0][:self.k_hi[i]], self.sw["lo"][0][:self.k_lo[i]], lambda: self.profile_at(t))

    def digest(self, upto=None) -> str:
        """Durum özeti (belirlenimlilik / nedensellik testleri): t <= upto olan karar anlarının tüm çıktıları + onaylı swing'ler; 9 basamak yuvarlama."""
        m = self.t <= (pd.Timestamp(upto).value if upto is not None else self.t[-1])
        r = lambda a: np.round(np.nan_to_num(np.asarray(a, float)[m], nan=-1.0), 9).tolist()  # noqa: E731
        k = int(self.k_hi[m][-1]) if m.any() else 0
        kl_ = int(self.k_lo[m][-1]) if m.any() else 0
        return ledger.sha([self.id, self.t[m].tolist(), r(self.o), r(self.h), r(self.l), r(self.c), r(self.atr), r(self.imp_up), r(self.imp_dn), self.valid[m].tolist(),
                           np.round(self.sw["hi"][0][:k], 9).tolist(), self.sw["hi"][1][:k].tolist(), np.round(self.sw["lo"][0][:kl_], 9).tolist(), self.sw["lo"][1][:kl_].tolist()])


_CACHE: dict = {}


def build(data: dict[str, pd.DataFrame], specs: list[StateSpec]) -> dict[str, MarketState]:
    """{sym: saatlik kl} + StateSpec listesi -> {sym: MarketState}. Önbellek anahtarı (spec.id, veri hash'i): aynı spec + aynı veri iki kez hesaplanmaz."""
    out = {}
    for sp in specs:
        kl = data[sp.sym]
        dh = hashlib.sha1(np.ascontiguousarray(kl[["open", "high", "low", "close", "volume"]].to_numpy(float)).tobytes() + ns(kl.index).tobytes()).hexdigest()
        if (sp.id, dh) not in _CACHE:
            STATS["builds"] += 1
            if len(_CACHE) >= 64:  # sınırlı önbellek (nedensellik denetimi onlarca bozulmuş veri üretir)
                _CACHE.pop(next(iter(_CACHE)))
            _CACHE[(sp.id, dh)] = MarketState(sp, kl)
        out[sp.sym] = _CACHE[(sp.id, dh)]
    return out
