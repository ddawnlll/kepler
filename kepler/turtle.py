"""Tam Turtle yöneticisi (V3; BACKTEST.md §5.2): sinyal yalnızca YÖN verir; bu modül N-boyutlama, 2N stop, piramitleme ve birim sınırlarını (sembol / korele grup / tek yön
toplam) ekler. Saf ve nedensel: gün d kararı yalnızca <= d kapanışına bakar. Karar günlük, saatlik hedefe `signals._put` ile (23:00 barı) yazılır; dolum sonraki açılış.

Kurallar (ön kayıt reports/full_systems_protocol.md ile aynı):
- Birim: qty u = capital * risk / N (N = giriş günü Wilder N, pozisyon boyunca sabit); hedef notional = yön * birim_sayısı * u * kapanış.
- Giriş: yön sinyali 0'dan ±1'e geçince 1 birim. Piramit: kapanış, son birimin referans kapanışından yön * add_n * N kadar ilerlediyse (günde en çok 1) +1 birim, en çok max_units.
- Stop: referans kapanış - yön * stop_n * N (her birim eklenince tüm pozisyon için son referanstan yeniden kurulur). Hakem stopu bar içinde yürütür; burada günlük H/L ile taklit edilir
  (durum eşitleme: taklit stop vurduysa hedef 0 yazılır; yön sinyali değişene kadar yeniden giriş yok = `halt`).
- Çıkış/çevirme: yön sinyali değişince tüm pozisyon kapanır; ters yöne geçtiyse 1 birimle yeni giriş.
- Sınırlar: giriş/ekleme yalnızca sembol < max_units, aynı gruptaki aynı yön birimleri < group_cap ve toplam aynı yön birimleri < total_cap ise. Günde İKİ GEÇİŞ: önce tüm semboller için
  stop taklidi + çıkış/çevirme (alan açar), sonra girişler/eklemeler alfabetik sırayla. Engellenen giriş, sinyal yönü değişene kadar tekrar denenmez (kaçan kırılım).
- Veri boşlukları: eksik günler atılır (N sürekli kalır); yön günlük son değerle (ffill) alınır; hedef/stop günün SON MEVCUT barına yazılır (23:00 yoksa 22:00; veri günün ortasında bitiyorsa o gün karar yok).
- Stop taklidi hakemle aynı tetik verisini kullanır: mark H/L (yoksa kline), seviye tick'e yuvarlanır."""
import numpy as np
import pandas as pd

from kepler import risk
from kepler import signals as sg

PARAMS = dict(risk=0.01, nd=20, stop_n=2.0, add_n=0.5, max_units=4, group_cap=6, total_cap=12, stop=True, pyramid=True, limits=True, fixed=None)


def _decision_bars(kl: pd.DataFrame) -> pd.Series:
    """Her günün son mevcut barı (gün -> zaman). Son gün 23:00 barında bitmiyorsa (veri kesik) o gün karar yok."""
    last = kl.index.to_series().groupby(kl.index.normalize()).last()
    return last if last.iloc[-1].hour == 23 else last.iloc[:-1]


def _hourly(kl: pd.DataFrame, tgt: pd.Series, stp: pd.Series) -> pd.DataFrame:
    last = _decision_bars(kl)
    day = kl.index.normalize()
    cur, prev = stp.reindex(day).to_numpy(), stp.shift(1).reindex(day).to_numpy()  # t günündeki saatlerde geçerli stop = önceki gün kararı; günün son barında yeni karar
    target = pd.Series(np.nan, index=kl.index)
    target[last.to_numpy()] = tgt.reindex(last.index).to_numpy()
    return pd.DataFrame(dict(target=target, stop=np.where(kl.index.isin(last.to_numpy()), cur, prev)), index=kl.index)


def _daily_dirs(x: pd.Series) -> pd.Series:
    return x.ffill().fillna(0.0).groupby(x.index.normalize()).last()  # günün son değeri; kararı olmayan gün önceki yönü taşır


def _trigger_daily(kl: pd.DataFrame, mark: pd.DataFrame | None) -> pd.DataFrame:
    """Hakemin tetik H/L'si (mark varsa mark; O/C aralığın içinde) günlüğe toplanmış."""
    hi, lo = kl.high, kl.low
    if mark is not None and {"high", "low"} <= set(mark.columns):
        hi, lo = mark.high.reindex(kl.index).fillna(kl.high), mark.low.reindex(kl.index).fillna(kl.low)
    hi, lo = pd.concat([hi, kl.open, kl.close], axis=1).max(axis=1), pd.concat([lo, kl.open, kl.close], axis=1).min(axis=1)
    return pd.DataFrame(dict(high=hi.resample("1D").max(), low=lo.resample("1D").min())).dropna()


def turtle_book(data: dict[str, pd.DataFrame], dirs: dict, capital: float, groups: dict[str, str], marks: dict | None = None, ticks: dict | None = None, **kw):
    """data[sym] = saatlik kl; dirs[sym] = yön sinyali (callable, sinyal sözleşmesi: saatlik, kararlar 23:00 barında); marks/ticks (isteğe bağlı): hakemin tetik verisi ve fiyat adımı.
    Dönüş: ({sym: DataFrame[target, stop]}, bilgi sayaçları)."""
    P = {**PARAMS, **kw}
    marks, ticks = marks or {}, ticks or {}
    D = {s: sg._daily(kl).dropna() for s, kl in data.items()}
    TH = {s: _trigger_daily(data[s], marks.get(s)) for s in D}
    N = {s: risk.wilder_n(D[s], P["nd"]) for s in D}
    sig = {s: _daily_dirs(dirs[s](data[s])) for s in D}
    st = {s: dict(dir=0, units=0, u=0.0, ref=np.nan, n=np.nan, halt=0, stop=np.nan) for s in D}
    T, S, info = {s: {} for s in D}, {s: {} for s in D}, dict(stops=0, blocked=0, entries=0, adds=0)

    def room(s, dd):  # birim sınırları (güncel durum)
        if not P["limits"]:
            return True
        same = [t for t in D if st[t]["dir"] == dd]
        return sum(st[t]["units"] for t in same if groups[t] == groups[s]) < P["group_cap"] and sum(st[t]["units"] for t in same) < P["total_cap"]

    def size(s, q, close, units):
        raw = close - q["dir"] * P["stop_n"] * q["n"]
        q["stop"] = (np.round(raw / ticks[s]) * ticks[s] if s in ticks else raw) if P["stop"] else np.nan
        return q["dir"] * units * q["u"] * close

    for day in sorted(set().union(*[d.index for d in D.values()])):
        syms, pend = [s for s in sorted(D) if day in D[s].index], {}
        for s in syms:  # 1. geçiş: taklit stop ve çıkış/çevirme (yalnız azaltır, alan açar)
            q, d, emit = st[s], int(np.sign(sig[s].get(day, 0.0))), None
            if q["dir"] and P["stop"] and day in TH[s].index and ((q["dir"] > 0 and TH[s].low[day] <= q["stop"]) or (q["dir"] < 0 and TH[s].high[day] >= q["stop"])):  # pozisyon dün kararıyla stop'a vurdu
                q.update(halt=q["dir"], dir=0, units=0, stop=np.nan)
                emit, info["stops"] = 0.0, info["stops"] + 1
            if q["halt"] and d != q["halt"]:
                q["halt"] = 0
            if not q["halt"] and q["dir"] and d != q["dir"]:
                q.update(dir=0, units=0, stop=np.nan)
                emit = 0.0
            pend[s] = (d, emit)
        for s in syms:  # 2. geçiş: giriş / ekleme, alfabetik
            (d, emit), q, row = pend[s], st[s], D[s].loc[day]
            n = N[s].get(day, np.nan)
            if not q["halt"]:
                if q["dir"] == 0 and d:  # giriş
                    if room(s, d) and (P["fixed"] is not None or not np.isnan(n)):
                        q.update(dir=d, units=1, n=n, ref=row.close, u=(P["fixed"] / row.close if P["fixed"] is not None else capital * P["risk"] / n))
                        emit, info["entries"] = size(s, q, row.close, 1), info["entries"] + 1
                    else:
                        q["halt"], info["blocked"] = d, info["blocked"] + 1
                elif q["dir"] and d == q["dir"] and P["pyramid"] and q["units"] < P["max_units"] and (row.close - q["ref"]) * q["dir"] >= P["add_n"] * q["n"] and room(s, d):
                    q["units"] += 1
                    q["ref"] = row.close
                    emit, info["adds"] = size(s, q, row.close, q["units"]), info["adds"] + 1
            if emit is not None:
                T[s][day] = emit
            S[s][day] = q["stop"]
    return {s: _hourly(data[s], pd.Series(T[s], dtype=float), pd.Series(S[s], dtype=float)) for s in D}, info
