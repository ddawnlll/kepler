"""Zone Fade v1 uzmanı: arz/talep bölgesinden dönüş, hacim profili (POC) hedefli. Tanım, parametre ve eşikler reports/zone_fade_protocol.md'de koddan önce sabitlendi (burada ayarlanmaz);
yaşam döngüsü BACKTEST §15.4: AKTIF -> IZLEMEDE -> POZISYONDA -> KAPALI, zone'a gelmeden süre/geçersizlik IPTAL.

Uzman `kepler/state.py`'den yalnızca karar anında (4h kapanış) bilinen durumu alır. Yönetici (`make_book`) kitap sözleşmesini (BACKTEST §4) üretir: book({sym: kl}) -> {sym: DataFrame[target, stop]}.
Hedefte çıkış ve koşullu giriş hakemde yok; sinyalle taklit edilir: tetik 4h kapanışında görülür -> hedef notional (sonraki açılışta dolar); 4h barın low'u (short için) hedefe değdiyse o
kapanışta hedef 0 (sonraki açılışta çık); stop hakemde (bar içi, mark H/L), taklit hakemle aynı tetik verisiyle günlük değil saatlik taranır (yalnızca durum eşitleme: yuvayı boşaltır, halt'ı açar)."""
from dataclasses import asdict, dataclass, replace

import numpy as np
import pandas as pd

from kepler import ledger
from kepler import state as stt

EXPERT_ID = "zone_fade_v1"
DAY = pd.Timedelta("1D")


@dataclass(frozen=True)
class Params:
    width: float = 1.0  # bölge genişliği, x ATR (K5: 0,75 / 1,0 / 1,25)
    impulse: float = 4.0  # impuls eşiği, x ATR (K5: 3 / 4 / 5)
    reach: float = 6.0  # S, fiyattan en çok 6 ATR uzakta
    stop_atr: float = 0.5  # stop = bölge dış kenarı ± 0,5 ATR
    rr: float = 2.0
    ttl_days: int = 30  # aday ömrü
    max_days: int = 40  # pozisyon ömrü
    risk: float = 0.005  # işlem başına risk, x sermaye
    sym_cap: float = 1.0  # sembol notional <= sym_cap x sermaye
    max_pos: int = 4
    max_side: int = 3
    ablate: str = ""  # K8: "no_impulse" | "no_trigger" | "no_poc" | "no_rr"


@dataclass
class Candidate:
    expert_id: str
    sym: str
    side: int  # -1 short (arz bölgesi), +1 long (talep bölgesi)
    zone: tuple  # (alt, üst)
    stop: float
    born: pd.Timestamp
    expiry: pd.Timestamp
    atr: float
    state: str = "AKTIF"
    why: str = ""
    target: float = np.nan
    ref: float = np.nan  # tetik kapanışı
    t_entry: pd.Timestamp | None = None
    t_exit: pd.Timestamp | None = None
    va: str = ""  # tetikte bölge türü: VA_disi / VA_ici (bilgi)
    id: str = ""

    def __post_init__(self):
        self.id = ledger.sha([self.expert_id, self.sym, self.side, self.zone, self.born])[:12]


def state_spec(sym: str) -> stt.StateSpec:
    return stt.StateSpec(sym, (stt.View("1d", 240, ("atr:14", "impulse:20")), stt.View("3d", 0, ("swing:2",)), stt.View("4h", 0, ("bars",)), stt.View("1h", 4320, ("profile:100",))))


def form(a: stt.AsOf, sym: str, p: Params) -> Candidate | None:
    """Aday oluşumu (4h kapanışta, açık aday/pozisyon yokken). Arz: yukarı impuls + fiyatın üstündeki, S <= close + 6 ATR en yakın onaylı swing tepe. Talep: ayna. İkisi birden uygun ise
    (protokol sıra vermiyor) fiyata daha yakın olan S, eşitlikte short."""
    if not a.valid or not np.isfinite(a.atr):
        return None
    atr, c, cands = a.atr, a.c, []
    if p.ablate == "no_impulse" or a.imp_up >= p.impulse:
        up = a.sw_hi[(a.sw_hi > c) & (a.sw_hi <= c + p.reach * atr)]
        if len(up):
            cands.append((float(up.min()) - c, -1, float(up.min())))
    if p.ablate == "no_impulse" or a.imp_dn >= p.impulse:
        dn = a.sw_lo[(a.sw_lo < c) & (a.sw_lo >= c - p.reach * atr)]
        if len(dn):
            cands.append((c - float(dn.max()), 1, float(dn.max())))
    if not cands:
        return None
    _, side, S = min(cands)
    zone, stop = ((S - p.width * atr, S), S + p.stop_atr * atr) if side < 0 else ((S, S + p.width * atr), S - p.stop_atr * atr)
    return Candidate(EXPERT_ID, sym, side, zone, stop, a.t, a.t + p.ttl_days * DAY, atr)


def watch(c: Candidate, a: stt.AsOf, p: Params) -> str | None:
    """AKTIF/IZLEMEDE adayı, t'de kapanan 4h bara göre günceller (sıra: süre, zone'a giriş, geçersizlik, tetik). 'trigger' döner ya da durumu IPTAL yapar."""
    s = c.side
    if a.t >= c.expiry:
        c.state, c.why = "IPTAL", "expiry"
        return None
    touched = a.h >= c.zone[0] if s < 0 else a.l <= c.zone[1]
    if touched and c.state == "AKTIF":
        c.state = "IZLEMEDE"
    if (a.c > c.stop) if s < 0 else (a.c < c.stop):  # 4h kapanış bölgenin ötesinde: geçersiz
        c.state, c.why = "IPTAL", "invalid"
        return None
    rejected = a.c < c.zone[0] if s < 0 else a.c > c.zone[1]
    if c.state != "IZLEMEDE" or not touched or not (rejected or p.ablate == "no_trigger"):
        return None
    c.ref = a.c
    if p.ablate == "no_poc":
        c.target = c.ref + s * 2 * abs(c.stop - c.ref)  # hedef = 2R sabit (R = |tetik kapanışı - stop|); R:R filtresi anlamsız
        return "trigger"
    pf = a.profile()
    c.target = pf["poc"]
    c.va = "VA_disi" if ((c.zone[0] > pf["vah"]) if s < 0 else (c.zone[1] < pf["val"])) else "VA_ici"
    if p.ablate != "no_rr" and not s * (c.target - c.ref) / abs(c.stop - c.ref) >= p.rr:
        c.state, c.why = "IPTAL", "rr"
        return None
    return "trigger"


def hold(c: Candidate, a: stt.AsOf, stop_hit: bool, p: Params) -> str | None:
    """POZISYONDA aday, t'de kapanan 4h bara göre: stop (hakemde vurdu; aynı barda hedef de varsa STOP, kötümser) > hedef (bar low/high hedefe değdi: kapanışta hedef 0) > zaman (> max_days)."""
    why = "stop" if stop_hit else "target" if ((a.l <= c.target) if c.side < 0 else (a.h >= c.target)) else "time" if a.t - c.t_entry > p.max_days * DAY else None
    if why:
        c.state, c.why, c.t_exit = "KAPALI", why, a.t
    return why


def _trigger(kl: pd.DataFrame, mark: pd.DataFrame | None):
    """Hakemin tetik verisi (referee.run_portfolio): mark H/L (mark yoksa kline), O/C aralığın içinde. (zaman ns, high, low)."""
    hi, lo = kl.high, kl.low
    if mark is not None and {"high", "low"} <= set(mark.columns):
        hi, lo = mark.high.reindex(kl.index).fillna(kl.high), mark.low.reindex(kl.index).fillna(kl.low)
    return stt.ns(kl.index), pd.concat([hi, kl.open, kl.close], axis=1).max(axis=1).to_numpy(), pd.concat([lo, kl.open, kl.close], axis=1).min(axis=1).to_numpy()


def make_book(capital: float, p: Params = Params(), marks: dict | None = None, ticks: dict | None = None):
    """Kitap fabrikası (evaluate.evaluate_book / run_book). Boyut: risk = p.risk x sermaye, notional = risk / (|tetik kapanışı - stop| / tetik kapanışı), sembol başına <= sym_cap x sermaye.
    Portföy: eşzamanlı en çok max_pos pozisyon, aynı yönde en çok max_side; aynı barda fazla tetik alfabetik sırayla, sınır aşılırsa aday IPTAL (limit). Son çağrının adayları `book.log`'da."""
    marks, ticks = marks or {}, ticks or {}

    def book(kls):
        syms = sorted(kls)
        S = {s: stt.build({s: kls[s]}, [state_spec(s)])[s] for s in syms}
        trig = {s: _trigger(kls[s], marks.get(s)) for s in syms}
        tgt = {s: np.full(len(kls[s]), np.nan) for s in syms}
        stp = {s: np.full(len(kls[s]), np.nan) for s in syms}
        idx = {s: {t: i for i, t in enumerate(S[s].t.tolist())} for s in syms}
        cand, pos, log = {}, {}, []

        def close(s, w1):  # pozisyon kapanış kararı: stop serisi o ana kadar, hedef 0 yazılır
            q = pos.pop(s)
            stp[s][q["w"]:w1] = q["stop"]
            tgt[s][w1] = 0.0
            log.append(q["c"])

        for t in sorted(set().union(*[idx[s].keys() for s in syms])):
            here = [s for s in syms if t in idx[s]]
            A = {s: S[s].at(idx[s][t]) for s in here}
            for s in here:  # 1. çıkışlar (alan açar)
                if s in pos:
                    q, (t1, hi, lo) = pos[s], trig[s]
                    i1 = int(np.searchsorted(t1, t, side="left"))
                    seg = (hi[q["scan"]:i1] >= q["stop"]) if q["c"].side < 0 else (lo[q["scan"]:i1] <= q["stop"])  # hakemin stop tetiği: mark H/L, giriş barından itibaren
                    q["hit"], q["scan"] = q["hit"] or bool(seg.any()), max(q["scan"], i1)
                    if hold(q["c"], A[s], q["hit"], p):
                        close(s, int(S[s].pos1h[idx[s][t]]))
            trigs = []
            for s in here:  # 2. adaylar
                if s in cand:
                    c = cand[s]
                    if watch(c, A[s], p) == "trigger":
                        trigs.append(s)
                    elif c.state == "IPTAL":
                        log.append(cand.pop(s))
            for s in trigs:  # 3. girişler (alfabetik; portföy sınırları)
                c = cand.pop(s)
                if len(pos) >= p.max_pos or sum(q["c"].side == c.side for q in pos.values()) >= p.max_side:
                    c.state, c.why = "IPTAL", "limit"
                    log.append(c)
                    continue
                stop = float(np.round(c.stop / ticks[s]) * ticks[s]) if s in ticks else c.stop
                c.state, c.t_entry = "POZISYONDA", A[s].t
                w = int(S[s].pos1h[idx[s][t]])
                tgt[s][w] = c.side * min(p.risk * capital / (abs(c.ref - stop) / c.ref), p.sym_cap * capital)
                pos[s] = dict(c=c, w=w, stop=stop, hit=False, scan=int(np.searchsorted(trig[s][0], t, side="left")))
            for s in here:  # 4. oluşum
                if s not in cand and s not in pos:
                    c = form(A[s], s, p)
                    if c is not None:
                        cand[s] = c
        for s, q in pos.items():
            stp[s][q["w"]:] = q["stop"]
        book.log = log + [q["c"] for q in pos.values()] + list(cand.values())
        return {s: pd.DataFrame(dict(target=tgt[s], stop=stp[s]), index=kls[s].index) for s in syms}

    book.log = []
    return book
