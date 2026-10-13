"""C2: hakem motor = numba olay döngüsü (kepler/referee_core.py) + vektörel hazırlık/muhasebe. NautilusTrader'ın yerini aldı (eski hakem: git 23ee215).

Sözleşme: target[t] = t barı (açılış zamanı t) KAPANDIĞINDA istenen işaretli notional (USDT); NaN = mevcut pozisyonu tut.
Miktar yalnızca hedef DEĞİŞTİĞİNDE dolum fiyatından yeniden hesaplanır (lot adımına aşağı yuvarlanır); aynı hedef sürdükçe işlem yok.
Dolum (varsayılan fill="next_open"): karar t barının kapanışında bilinir, SONRAKİ barın açılış fiyatından dolar (her bar iki olay:
açılış tiki = karar anı, gövde (o,h,l,c) = stop/likidasyon eşleşmesi). fill="close" (eski, iyimser: karar barının kapanışından) yalnızca testler içindir;
`evaluate` reddeder. Son barın hedefi dolmaz. Likidasyondan sonra hesap ölü: yeni işlem yok (kalan marj likidasyon ücretiyle kaybedilir). Açık pozisyonun
çıkış maliyeti (fee+slip) son kapanıştan düşülür (close_out). Maliyet: taker fee + slippage (bps, gidiş-dönüş; yan başına yarısı) komisyona girer.
Funding: T anındaki oran, T'den ÖNCE (T'de yapılan dolumlardan önce) tutulan pozisyon x mark fiyat; işaret: oran>0 iken long öder.
Likidasyon: her pozisyon değişiminde likidasyon fiyatında reduce-only STOP; tetik MARK H/L'siyle (mark yoksa kline); gap'te açılıştan, bar içinde seviyeden dolar.
Hacim sınırı (L1 bar yürütmesi): her tikin boyutu = bar hacmi/4 (lot adımına bölünmüş); piyasa/stop emri tik boyutu kadar tek fiyattan dolar, KALANI son dolum fiyatının 1 tick ötesinden
(alış +, satış -) dolar. Marj: artıran/çeviren emir, başlangıç marjı (|notional|/kaldıraç^2: Nautilus LeveragedMarginModel, margin_init=1/kaldıraç) - bakım marjı kilidini bakiyeden
aşıyorsa REDDEDİLİR (n_rejected; defter reddeden koşuyu kabul etmez); kitap fiyatı stop seviyesindeyse stop da reddedilir.
"""
from dataclasses import dataclass
from decimal import Decimal

import numpy as np
import pandas as pd

from kepler import referee_core as core
from kepler import tape

HOUR_NS = core.HOUR


@dataclass(frozen=True)
class Spec:
    tick: str = "0.1"
    step: str = "0.001"
    min_notional: float = 5.0
    fee_rt_bps: float = 10.0
    slip_rt_bps: float = 0.0
    leverage: int = 10
    mmr: float = 0.005  # bakım marjı oranı (sembole/kademeye göre değişir; UNKNOWN: gerçek kademe tablosu alınmadı)
    capital: float = 500.0
    liq: bool = True
    native_liq: bool = False  # yalnızca test uyumu: eski motorun kendi likidasyonu bar verisinde işe yaramıyordu; burada liq=False ile aynı (likidasyon yok)
    liq_fee_rate: float | None = None  # None -> mmr (kalan bakım marjı kaybedilir; gerçek Binance ücreti UNKNOWN); motorun taker fee'si bunun İÇİNDE sayılır (çifte sayım yok)
    fill: str = "next_open"  # "next_open" | "close" (yalnızca test/eski)
    close_out: bool = True  # açık pozisyonu son kapanıştan çıkış fee+slip ile değerle
    delay: int = 0  # ek gecikme (bar): dolum karardan sonraki (1 + delay). mevcut barda; stres testi (K3)
    gross_cap: float | None = None  # toplam brüt notional tavanı (USDT); artıran emir kalan alana küçülür (portföy, §6.5)
    equity_scale: bool = False  # True: yeni/değişen hedef notional (ve gross_cap) x equity / capital, equity = bakiye + gerçekleşmemiş PnL, emir anında (BACKTEST §5.1)


def ns(index) -> list[int]:
    return [int(x) for x in pd.DatetimeIndex(index).as_unit("ns").asi8]


def _dp(s: str) -> int:
    return max(0, -Decimal(s).as_tuple().exponent)


def liq_price(q: Decimal, entry: float, wb: float, mmr: float) -> float | None:
    """Tek sembol, cross: özsermaye = WB + q(P-E) <= mmr*|q|*P. Likidasyon yok (None) ise kaldıraçsız/güvenli."""
    qf = float(q)
    p = (qf * entry - wb) / (qf * (1 - mmr)) if qf > 0 else (wb - qf * entry) / (-qf * (1 + mmr))
    return p if p > 0 else None


def _shift(a: np.ndarray, k: int) -> np.ndarray:
    out = np.full(len(a), np.nan)
    if k < len(a):
        out[k:] = a[: len(a) - k]
    return out


def _prep(sym: str, d: dict, spec: Spec):
    """Sembol verisini çekirdek dizilerine çevir: kline (+ mark H/L), tick yuvarlama, karar -> yuva kaydırma (bisect_left(yuvalar, kapanış) + delay = j + 1 + delay)."""
    kl, target, funding = d["kl"], d["target"], d.get("funding")
    if not (kl.index.is_monotonic_increasing and kl.index.is_unique):
        raise ValueError("kl indeksi artan ve tekil olmalı")
    t0 = np.asarray(ns(kl.index), np.int64)
    if len(kl) == 0 or (np.diff(t0) % HOUR_NS).any() or t0[0] % HOUR_NS:
        raise ValueError("kl boş ya da saatlik hizalı değil")
    tape.check_target(kl, target)  # yanlış hizalı/tz'siz hedef sessizce sıfır işleme dönüşmesin
    if funding is not None and funding["last_funding_rate"].isna().any():
        raise ValueError("funding oranında NaN var (QC'den geçmemiş veri)")
    tick, step = d.get("tick") or spec.tick, d.get("step") or spec.step
    pp, sp = _dp(tick), _dp(step)
    mark = d.get("mark")
    hi, lo = kl.high, kl.low
    if mark is not None and {"high", "low"} <= set(mark.columns):  # likidasyon stopu MARK fiyatının H/L'siyle tetiklenir (Binance); eksik mark barında kline H/L
        hi, lo = mark.high.reindex(kl.index).fillna(kl.high), mark.low.reindex(kl.index).fillna(kl.low)
    o, c = kl.open.to_numpy(float), kl.close.to_numpy(float)
    h, l = np.fmax.reduce([hi.to_numpy(float), o, c]), np.fmin.reduce([lo.to_numpy(float), o, c])  # noqa: E741  O/C [L,H] içinde kalsın
    q = lambda a: np.rint(a * 10.0**pp) / 10.0**pp  # noqa: E731  tick ondalığına yuvarla (Price.from_str karşılığı)
    o, h, l, c = q(o), q(h), q(l), q(c)  # noqa: E741
    if not all(np.isfinite(a).all() and (a > 0).all() for a in (o, h, l, c)):
        raise ValueError(f"{sym}: kline OHLC'de NaN/sonsuz/pozitif olmayan fiyat (QC'den geçmemiş veri)")
    vol = kl.volume.to_numpy(float)
    if not (np.isfinite(vol).all() and (vol >= 0).all()):
        raise ValueError(f"{sym}: hacimde NaN/sonsuz/negatif değer (QC'den geçmemiş veri)")
    inc, incs = max(int(round(float(step) * 10.0**sp)), 1), np.rint(vol * 10.0**sp).astype(np.int64)  # BarTickSizes: hacim lot adımının katına inip 4 tike bölünür
    incs //= inc
    path = incs // 4
    sz = np.zeros((len(kl), 4), np.int64)
    big = incs >= 4
    sz[big] = np.c_[path, path, path, incs - 3 * path][big]
    sz[incs == 1, 3], sz[incs == 2, 1], sz[incs == 2, 2], sz[incs == 3, :3] = 1, 1, 1, 1
    sh = 1 + spec.delay if spec.fill == "next_open" else spec.delay
    stop = d.get("stop")
    tg = _shift(target.astype(float).to_numpy(), sh)
    st = _shift(stop.astype(float).to_numpy() if stop is not None else np.full(len(kl), np.nan), sh)
    return dict(t0=t0, o=o, h=h, l=l, c=c, tg=tg, st=st, sz=sz * inc, u=(10.0**sp, 10.0**pp, float(tick)))


def _funding(kl, mark, funding, keys, vals):
    """Funding olayları: T'den ÖNCE tutulan pozisyon (keys[j] >= T ilk anahtar) x mark kapanışı (T'de biten bar; yoksa kline kapanışı) x oran. (toplam, kaçan, kline'a düşen)."""
    if funding is None or not len(funding):
        return 0.0, 0, 0
    ts = np.asarray(ns(pd.DatetimeIndex(funding.index).round("1min")), np.int64)
    rate = funding["last_funding_rate"].to_numpy(float)
    t0 = np.asarray(ns(kl.index), np.int64)
    ok = (t0[0] + HOUR_NS <= ts) & (ts <= t0[-1] + HOUR_NS)
    ts, rate = ts[ok], rate[ok]
    src = mark if mark is not None else kl
    mk_close = np.asarray(ns(src.index), np.int64) + HOUR_NS
    order = np.argsort(mk_close, kind="stable")
    mk_close, mk_val = mk_close[order], src.close.to_numpy(float)[order]
    i = np.searchsorted(mk_close, ts, side="right") - 1  # yinelenen anahtarda sonuncusu (dict semantiği)
    hit = (i >= 0) & (mk_close[np.maximum(i, 0)] == ts)
    c = np.where(hit, mk_val[np.maximum(i, 0)], np.nan)
    fallback = 0
    if mark is not None:
        miss = np.isnan(c)
        j = np.searchsorted(t0, ts - HOUR_NS)
        kh = (j < len(t0)) & (t0[np.minimum(j, len(t0) - 1)] == ts - HOUR_NS)
        c2 = np.where(kh, kl.close.to_numpy(float)[np.minimum(j, len(t0) - 1)], np.nan)
        c = np.where(miss, c2, c)
        fallback = int((miss & ~np.isnan(c2)).sum())
    jk = np.searchsorted(keys, ts, side="left")
    bad = np.isnan(c) | (jk == len(keys))
    pos = vals[np.minimum(jk, len(keys) - 1)]
    return float(np.sum(np.where(bad, 0.0, -pos * np.where(bad, 0.0, c) * rate))), int(bad.sum()), fallback


def run(kl: pd.DataFrame, target: pd.Series, spec: Spec = Spec(), funding: pd.DataFrame | None = None, mark: pd.DataFrame | None = None, stop: pd.Series | None = None) -> dict:
    """Tek sembol = run_portfolio'nun tek sembollü hali. kl: ts(bar açılışı, UTC) indeksli open/high/low/close/volume. Dönüş: {'summary', 'fills', 'rejected'}."""
    return run_portfolio({"SYM": dict(kl=kl, target=target, funding=funding, mark=mark, stop=stop)}, spec)


def run_portfolio(data: dict[str, dict], spec: Spec = Spec()) -> dict:
    """Tek USDT hesap, ortak marj. data[sym] = dict(kl, target, funding=None, mark=None, stop=None, tick=None, step=None).
    stop[t] = t kapanışında bilinen koruyucu stop fiyatı (NaN = stop yok), t+1 açılışından itibaren geçerli. Sembol başına likidasyon (cross-margin likidasyonu yok)."""
    if spec.fill not in ("next_open", "close"):
        raise ValueError("fill next_open veya close olmalı")
    side_fee = (spec.fee_rt_bps + spec.slip_rt_bps) / 2 / 1e4
    syms, prep = list(data), [_prep(s, d, spec) for s, d in data.items()]
    n = np.array([len(p["t0"]) for p in prep])
    off = np.r_[0, np.cumsum(n)]
    cat = lambda key: np.concatenate([p[key] for p in prep])  # noqa: E731
    T0, O, H, L, C, TG, ST, SZ = (cat(k) for k in ("t0", "o", "h", "l", "c", "tg", "st", "sz"))
    U = np.array([p["u"] for p in prep])
    close_mode = spec.fill == "close"
    bar, sym = np.arange(off[-1]), np.repeat(np.arange(len(syms)), n)
    if close_mode:
        ev_t, ev_b, ev_k, ev_kind = T0 + HOUR_NS, bar, sym, np.full(len(bar), core.KIND_CLOSE, np.int8)
    else:
        ev_t, ev_b, ev_k = np.r_[T0, T0 + HOUR_NS - 1], np.r_[bar, bar], np.r_[sym, sym]
        ev_kind = np.r_[np.zeros(len(bar), np.int8), np.ones(len(bar), np.int8)]
    o_ = np.lexsort((ev_k, ev_t))  # zaman, sonra sembol sırası (eski motor: veri ekleme sırası)
    ev_k, ev_b, ev_kind = ev_k[o_].astype(np.int64), ev_b[o_].astype(np.int64), ev_kind[o_]
    P = np.array([side_fee, spec.leverage, spec.mmr, float(spec.liq and not spec.native_liq), spec.min_notional, spec.capital, float(spec.equity_scale), spec.gross_cap or 0.0, float(close_mode)])
    cap = 2 * len(bar) + 4096
    while True:
        FI, FF, PI, PF, RJ = np.zeros((cap, 4), np.int64), np.zeros((cap, 3)), np.zeros((cap, 3), np.int64), np.zeros(cap), np.zeros((len(ev_k) + 1, 3), np.int64)
        PRE, END = np.zeros(len(bar), np.int64), np.zeros(len(bar), np.int64)
        F, I, G, N = core.simulate(ev_k, ev_b, ev_kind, T0, O, H, L, C, SZ, TG, ST, U, P, cap, FI, FF, PI, PF, RJ, PRE, END)
        if N[0] >= 0:
            break
        cap *= 2
    nf, npos, nrej = int(N[0]), int(N[1]), int(N[2])
    for k in range(len(syms)):
        if I[k, core.LOT] != 0:
            PF[I[k, core.COPEN]] = F[k, core.CYC]  # açık döngü: o ana kadarki realize (komisyon dahil)
    fi, ff = FI[:nf], FF[:nf]
    fills = pd.DataFrame(dict(sym=np.array(syms, dtype=object)[fi[:, 0]], ts=fi[:, 1], side=np.where(fi[:, 2] > 0, "BUY", "SELL"), qty=ff[:, 0], px=ff[:, 1], commission=ff[:, 2],
                              liq=(fi[:, 3] & 1) > 0, stop=(fi[:, 3] & 2) > 0))
    pi = PI[:npos]
    positions = pd.DataFrame(dict(opened=pd.to_datetime(pi[:, 0], utc=True), closed=pd.to_datetime(np.where(pi[:, 1] > 0, pi[:, 1], np.iinfo(np.int64).min), utc=True), realized=PF[:npos]))
    notional = float((fills.qty * fills.px).sum())
    fee, slip = notional * spec.fee_rt_bps / 2 / 1e4, notional * spec.slip_rt_bps / 2 / 1e4
    lq = fills[fills.liq]
    liq_fee = float((lq.qty * lq.px).sum()) * max(0.0, (spec.mmr if spec.liq_fee_rate is None else spec.liq_fee_rate) - side_fee)  # motor taker fee'yi zaten kesti
    last = [float(d["kl"].close.iloc[-1]) for d in data.values()]
    end_pos = {s: I[k, core.LOT] / U[k, 0] for k, s in enumerate(syms)}
    unreal = sum(end_pos[s] * (last[k] - F[k, core.AVG]) for k, s in enumerate(syms) if I[k, core.LOT] != 0)
    exit_cost = sum(abs(end_pos[s]) * last[k] * side_fee for k, s in enumerate(syms)) if spec.close_out else 0.0
    fund, missed, fallback = 0.0, 0, 0
    for k, (s, d) in enumerate(data.items()):
        sl, kl = slice(off[k], off[k + 1]), d["kl"]
        pre, end, t0 = PRE[sl] / U[k, 0], END[sl] / U[k, 0], prep[k]["t0"]
        if close_mode:
            keys, vals = t0 + HOUR_NS, pre
        else:  # gövde sonu anahtarı = kapanış; açılış anahtarı yalnızca bir önceki barın kapanışına eşit değilse (ilk bar, boşluk sonrası) eklenir (setdefault semantiği)
            new = np.r_[True, t0[1:] != t0[:-1] + HOUR_NS]
            keys, vals = np.r_[t0 + HOUR_NS, t0[new]], np.r_[end, pre[new]]
        srt = np.argsort(keys, kind="stable")
        f, m, fb = _funding(kl, d.get("mark"), d.get("funding"), keys[srt], vals[srt])
        fund, missed, fallback = fund + f, missed + m, fallback + fb
    bal = float(G[0])
    net = bal + unreal - spec.capital + fund - liq_fee - exit_cost
    rejected = [f"OrderRejected(sym={syms[r[0]]} ts={r[1]} qty={r[2] / U[r[0], 0]}: {'stop kitap fiyatında' if r[2] == 0 else 'marj/piyasa yok'})" for r in RJ[:nrej]]
    return dict(summary=dict(net_pnl=net, gross_pnl=net + fee + slip + exit_cost - fund + liq_fee, fee=fee, slippage=slip, funding=fund, liq_fee=liq_fee, exit_cost=exit_cost,
                             n_fills=nf, n_liq=int(fills.liq.sum()), n_stop=int(fills.stop.sum()), end_position=next(iter(end_pos.values())) if len(end_pos) == 1 else sum(abs(v) for v in end_pos.values()),
                             engine_commission=float(fills.commission.sum()), n_rejected=len(rejected), funding_missed=missed, funding_mark_fallback=fallback),
                fills=fills, positions=positions, rejected=rejected)
