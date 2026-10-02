"""Tam Turtle yöneticisi (V3; BACKTEST.md §5.2): sinyal yalnızca YÖN verir; bu modül N-boyutlama, 2N stop, piramitleme ve birim sınırlarını (sembol / korele grup / tek yön
toplam) ekler. Saf ve nedensel: gün d kararı yalnızca <= d kapanışına bakar. Karar günlük, saatlik hedefe `signals._put` ile (23:00 barı) yazılır; dolum sonraki açılış.

Kurallar (ön kayıt reports/full_systems_protocol.md ile aynı):
- Birim: qty u = capital * risk / N (N = giriş günü Wilder N, pozisyon boyunca sabit); hedef notional = yön * birim_sayısı * u * kapanış.
- Giriş: yön sinyali 0'dan ±1'e geçince 1 birim. Piramit: kapanış, son birimin referans kapanışından yön * add_n * N kadar ilerlediyse (günde en çok 1) +1 birim, en çok max_units.
- Stop: referans kapanış - yön * stop_n * N (her birim eklenince tüm pozisyon için son referanstan yeniden kurulur). Hakem stopu bar içinde yürütür; burada günlük H/L ile taklit edilir
  (durum eşitleme: taklit stop vurduysa hedef 0 yazılır; yön sinyali değişene kadar yeniden giriş yok = `halt`).
- Çıkış/çevirme: yön sinyali değişince tüm pozisyon kapanır; ters yöne geçtiyse 1 birimle yeni giriş.
- Sınırlar: giriş/ekleme yalnızca sembol < max_units, aynı gruptaki aynı yön birimleri < group_cap ve toplam aynı yön birimleri < total_cap ise; sembolleri alfabetik sırayla işler.
  Engellenen giriş, sinyal yönü değişene kadar tekrar denenmez (kaçan kırılım)."""
import numpy as np
import pandas as pd

from kepler import risk
from kepler import signals as sg

PARAMS = dict(risk=0.01, nd=20, stop_n=2.0, add_n=0.5, max_units=4, group_cap=6, total_cap=12, stop=True, pyramid=True, limits=True, fixed=None)


def _hourly(kl: pd.DataFrame, tgt: pd.Series, stp: pd.Series) -> pd.DataFrame:
    day = kl.index.normalize()
    cur, prev = stp.reindex(day).to_numpy(), stp.shift(1).reindex(day).to_numpy()  # t günündeki saatlerde geçerli stop = önceki gün kararı; 23:00 barında yeni karar
    return pd.DataFrame(dict(target=sg._put(kl, tgt), stop=np.where(kl.index.hour == 23, cur, prev)), index=kl.index)


def _daily_dirs(x: pd.Series) -> pd.Series:
    x = x.ffill().fillna(0.0)
    x = x[x.index.hour == 23]  # kararlar günün 23:00 barında (kapanış 00:00 UTC)
    return pd.Series(x.to_numpy(), index=x.index.normalize())


def turtle_book(data: dict[str, pd.DataFrame], dirs: dict, capital: float, groups: dict[str, str], **kw):
    """data[sym] = saatlik kl; dirs[sym] = yön sinyali (callable, sinyal sözleşmesi: saatlik, kararlar 23:00 barında). Dönüş: ({sym: DataFrame[target, stop]}, bilgi sayaçları)."""
    P = {**PARAMS, **kw}
    D = {s: sg._daily(kl) for s, kl in data.items()}
    N = {s: risk.wilder_n(D[s], P["nd"]) for s in D}
    sig = {s: _daily_dirs(dirs[s](data[s])) for s in D}
    st = {s: dict(dir=0, units=0, u=0.0, ref=np.nan, n=np.nan, halt=0, stop=np.nan) for s in D}
    T, S, info = {s: {} for s in D}, {s: {} for s in D}, dict(stops=0, blocked=0, entries=0, adds=0)
    for day in sorted(set().union(*[d.index for d in D.values()])):
        for s in sorted(D):
            if day not in D[s].index:
                continue
            row, q, d, emit = D[s].loc[day], st[s], int(np.sign(sig[s].get(day, 0.0))), None
            if q["dir"] and P["stop"] and ((q["dir"] > 0 and row.low <= q["stop"]) or (q["dir"] < 0 and row.high >= q["stop"])):  # taklit stop: pozisyon dün kararıyla stop'a vurdu
                q.update(halt=q["dir"], dir=0, units=0, stop=np.nan)
                emit, info["stops"] = 0.0, info["stops"] + 1
            if q["halt"] and d != q["halt"]:
                q["halt"] = 0
            n = N[s].get(day, np.nan)

            def room(dd):  # birim sınırları (sembol alfabetik sırasıyla güncel durum)
                if not P["limits"]:
                    return True
                same = [t for t in D if st[t]["dir"] == dd]
                return sum(st[t]["units"] for t in same if groups[t] == groups[s]) < P["group_cap"] and sum(st[t]["units"] for t in same) < P["total_cap"]

            def size(q, units):
                q["stop"] = row.close - q["dir"] * P["stop_n"] * q["n"] if P["stop"] else np.nan
                return q["dir"] * units * q["u"] * row.close

            if not q["halt"]:
                if q["dir"] and d != q["dir"]:  # çıkış ya da çevirme
                    q.update(dir=0, units=0, stop=np.nan)
                    emit = 0.0
                if q["dir"] == 0 and d:  # giriş
                    ok = room(d) and (P["fixed"] is not None or not np.isnan(n))
                    if ok:
                        q.update(dir=d, units=1, n=n, ref=row.close, u=(P["fixed"] / row.close if P["fixed"] is not None else capital * P["risk"] / n))
                        emit, info["entries"] = size(q, 1), info["entries"] + 1
                    else:
                        q["halt"], info["blocked"] = d, info["blocked"] + 1
                elif q["dir"] and d == q["dir"] and P["pyramid"] and q["units"] < P["max_units"] and (row.close - q["ref"]) * q["dir"] >= P["add_n"] * q["n"] and room(d):
                    q["units"] += 1
                    q["ref"] = row.close
                    emit, info["adds"] = size(q, q["units"]), info["adds"] + 1
            if emit is not None:
                T[s][day] = emit
            S[s][day] = q["stop"]
    return {s: _hourly(data[s], pd.Series(T[s], dtype=float), pd.Series(S[s], dtype=float)) for s in D}, info
